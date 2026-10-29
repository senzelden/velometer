"""README images: the Berlin tier map and the compare chart, each in the light and the dark theme.

Drives headless Chrome over a served static edition with the render pass's helpers and writes
`docs/img/readme/{tiermap-berlin,compare-headline}-{light,dark}.png`, each clipped to its page
element. The tier map needs the basemap tiles, which an export does not contain, so the usual
source is the deployed site: behind the preview lock, the user `preview` with the password from
`$VELOMETER_PREVIEW_PASSWORD` (direnv + pass), sent to that origin only, never on a command line;
`--site` serves a local export instead (the map then draws without its basemap).

    uv run --group dev python tools/readme_shots.py --url https://velometer.zaehlwerk-datalab.de
    uv run --group dev python tools/readme_shots.py --site DIR [--base /]
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_pass as rp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img" / "readme"
WIDTH = 1280
SCALE = 2  # device pixels per CSS pixel: sharp on high-density screens at half the width

# name -> (page under the base, JS that is true once drawn, first element, last element)
SHOTS = {
    "tiermap-berlin": (
        "city/berlin/tiers?kind=fua&tiers=ABC&at=52.515,13.40,12",
        None,  # the render pass's own wait: a tile drawn and the status past its loading text
        ".tiermap-controls fieldset.tiers",
        "#tiermap-status",
    ),
    "compare-headline": (
        "compare",
        "!!document.querySelector('[data-compare-chart]:not([hidden]) svg')",
        "[data-compare-title]",
        "[data-compare-chart]",
    ),
}

CLIP_JS = """(() => {
  const a = document.querySelector(%r).getBoundingClientRect();
  const b = document.querySelector(%r).getBoundingClientRect();
  const x = Math.min(a.left, b.left) - 12, y = a.top + window.scrollY - 12;
  return {x: Math.max(0, x), y: Math.max(0, y),
          width: Math.max(a.right, b.right) - x + 12, height: b.bottom + window.scrollY - y + 12};
})()"""


def shoot(devtools: str, origin: str, base: str, theme: str) -> list[str]:
    errors = []
    for name, (page, drawn, first, last) in SHOTS.items():
        t = rp.open_tab(devtools, WIDTH, theme)
        try:
            t.call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=900,
                   deviceScaleFactor=SCALE, mobile=False)  # fmt: skip
            errors += rp.navigate(t, origin + base + page)
            late = rp._wait_map(t, "not drawn") if drawn is None else (
                [] if t.wait_js(drawn, 20) else ["not drawn within 20 s"])  # fmt: skip
            if late:
                errors += [f"{name} ({theme}): {e}" for e in late]
                continue
            t.pump(1.5)  # the last tiles and the line labels
            clip = t.js(CLIP_JS % (first, last))
            shot = t.call("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                          clip={**clip, "scale": 1})  # fmt: skip
            path = OUT / f"{name}-{theme}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            # 256 colours: a map tile and a chart lose nothing visible, the file a factor of 3-4
            img = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")
            img.quantize(256, dither=Image.Dither.NONE).save(path, optimize=True)
            print(path.relative_to(ROOT))
        finally:
            t.close()
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="origin of a deployed site, e.g. https://velometer.example")
    src.add_argument("--site", type=Path, help="exported static edition, served locally")
    ap.add_argument("--base", default="/", help="base path the site was exported for")
    ap.add_argument(
        "--auth",
        help="USER:PASS for a locked site (with --url; default: $VELOMETER_PREVIEW_PASSWORD)",
    )
    ap.add_argument("--chrome", default=rp.CHROME)
    a = ap.parse_args(argv)
    if a.auth is not None and (not a.url or ":" not in a.auth):
        ap.error("--auth takes USER:PASS and needs --url")
    rp.AUTH = rp.resolve_auth(a.auth, a.url)
    rp.AUTH_ORIGIN = rp.origin_of(a.url) if a.url and rp.AUTH else None
    base = rp._norm_base(a.base)
    with contextlib.ExitStack() as stack:
        if a.url:
            origin = stack.enter_context(rp.running(a.url.rstrip("/"), base))
        else:
            origin = stack.enter_context(rp.serve(a.site, base))
        devtools = stack.enter_context(rp.chrome(a.chrome))
        errors = [e for theme in ("light", "dark") for e in shoot(devtools, origin, base, theme)]
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
