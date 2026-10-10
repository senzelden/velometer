"""Render pass: drive headless Chrome over an exported static edition and audit every page.

M10 spec decision 7. Serves the export with `python -m http.server` on 127.0.0.1 under the base
path, opens each page × theme × width in headless Chrome over the DevTools protocol and records
axe-core violations (WCAG 2.1 A/AA tags), sideways overflow, console messages, CSP violations,
the hosts contacted and a full-page screenshot. `results.json` in `--out` holds one entry per
visit; the exit status is 1 when any visit has a finding, else 0.

axe-core is vendored in `tools/axe/` (pinned in `tools/axe/VERSION`) and injected through
`Runtime.evaluate`, which the page's CSP does not apply to; it is never served by the app.

    uv run --group dev python tools/render_pass.py --site DIR --base /velometer/ \
        --out tools/out/NAME [--themes light,dark] [--widths 1280,390,320] \
        [--pages all|types|<url>,...] [--flip]

`--flip` is a mode of its own: each page loads in light, the emulated scheme switches to dark
mid-page, and after 500 ms the page is audited and shot as `<slug>-flipped-<width>.png`.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
AXE_JS = HERE / "axe" / "axe.min.js"
CHROME = "/usr/bin/google-chrome"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
ALLOWED_HOSTS = {"127.0.0.1", "tile.openstreetmap.org"}
# pages in a city are /city/<slug>/<tab>; --pages types keeps Berlin plus the first city (by
# slug) whose tab list differs from Berlin's
TYPES_CITY = "berlin"

# Elements wider than their box, outside prose tables (allowed to scroll, spec decision 5) and
# the Leaflet map (its panes are positioned beyond the viewport by design). Elements that clip
# their overflow (overflow-x hidden/clip: ellipsis, visually hidden text) cannot scroll and are
# skipped, and so are boxes whose only spilling content is a prose table. The document itself
# overflowing the viewport is reported as ":root".
OVERFLOW_JS = r"""
(() => {
  const sel = (el) => {
    const parts = [];
    for (let e = el; e && e.nodeType === 1 && parts.length < 4; e = e.parentElement) {
      let s = e.localName;
      if (e.id) { parts.unshift(s + '#' + e.id); break; }
      const cls = [...e.classList].slice(0, 2);
      if (cls.length) s += '.' + cls.join('.');
      parts.unshift(s);
    }
    return parts.join(' > ');
  };
  // a box whose content spills only because a prose table sticks out of it (by design: prose
  // tables may be wider than the prose column) is not itself overflowing
  const onlyProse = (el) => {
    const right = el.getBoundingClientRect().left + el.clientWidth + 1;
    for (const d of el.querySelectorAll('*')) {
      if (d.closest('.prose table')) continue;
      if (d.getBoundingClientRect().right > right) return false;
    }
    return true;
  };
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.scrollWidth <= el.clientWidth + 1 || el.clientWidth === 0) continue;
    if (el.closest('.prose table') || el.closest('.leaflet-container')) continue;
    const ox = getComputedStyle(el).overflowX;
    if (ox === 'hidden' || ox === 'clip') continue;
    if (ox === 'visible' && onlyProse(el)) continue;
    out.push(sel(el) + ' (' + el.scrollWidth + '>' + el.clientWidth + ')');
  }
  const doc = document.documentElement.scrollWidth;
  if (doc > innerWidth) out.unshift(':root (' + doc + '>' + innerWidth + ')');
  return [...new Set(out)];
})()
"""

AXE_RUN_JS = """
axe.run(document, {runOnly: {type: 'tag', values: TAGS}, resultTypes: ['violations']})
  .then(r => r.violations.map(v => ({
    id: v.id, impact: v.impact,
    nodes: v.nodes.map(n => n.target.map(t => Array.isArray(t) ? t.join(' >>> ') : t)
                               .join(' >>> '))})))
""".replace("TAGS", json.dumps(AXE_TAGS))


def page_urls(site: Path, base: str) -> list[str]:
    """Every exported page: `<dir>/index.html` is `<base><dir>`, `index.html` is `<base>`.

    `404.html`, non-HTML files and HTML fragments (no `<html` element: the city panels, which are
    loaded into a page, not visited) are skipped.
    """
    base = _norm_base(base)
    urls = []
    for f in sorted(site.rglob("index.html")):
        head = f.read_text(encoding="utf-8", errors="replace")[:2048].lower()
        if "<html" not in head:
            continue
        rel = f.parent.relative_to(site).as_posix()
        urls.append(base if rel == "." else base + rel)
    return sorted(urls)


def type_urls(urls: list[str], base: str) -> list[str]:
    """One page per tab type: every page outside /city/, plus Berlin's and one other city's."""
    city_re = re.compile(re.escape(_norm_base(base)) + r"city/([^/]+)(?:/(.*))?$")
    tabs: dict[str, list[str]] = defaultdict(list)
    keep = []
    for u in urls:
        m = city_re.match(u)
        if m:
            tabs[m[1]].append(m[2] or "")
        else:
            keep.append(u)
    chosen = [TYPES_CITY] if TYPES_CITY in tabs else []
    ref = sorted(tabs.get(TYPES_CITY, []))
    for slug in sorted(tabs):
        if slug != TYPES_CITY and sorted(tabs[slug]) != ref:
            chosen.append(slug)
            break
    for slug in chosen:
        keep += [f"{_norm_base(base)}city/{slug}" + (f"/{t}" if t else "") for t in tabs[slug]]
    return sorted(keep)


def _norm_base(base: str) -> str:
    return "/" + base.strip("/") + "/" if base.strip("/") else "/"


def slug(url: str, base: str) -> str:
    path = url[len(_norm_base(base)) :] if url.startswith(_norm_base(base)) else url
    s = re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")
    return s or "index"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, seconds: float = 15) -> None:
    end = time.time() + seconds
    while True:
        try:
            urllib.request.urlopen(url, timeout=2).close()
            return
        except OSError:
            if time.time() > end:
                raise
            time.sleep(0.2)


class Tab:
    """One Chrome tab over a DevTools websocket; events are kept in arrival order."""

    def __init__(self, devtools: str, ws_url: str, target_id: str):
        import websocket  # dev dependency group

        self._wsmod = websocket
        self.devtools = devtools
        self.id = target_id
        self.ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
        self.n = 0
        self.events: list[dict] = []

    def call(self, method: str, **params):
        self.n += 1
        my = self.n
        self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == my:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            self.events.append(m)

    def pump(self, seconds: float) -> None:
        end = time.time() + seconds
        self.ws.settimeout(0.1)
        while time.time() < end:
            with contextlib.suppress(self._wsmod.WebSocketTimeoutException):
                self.events.append(json.loads(self.ws.recv()))
        self.ws.settimeout(120)

    def wait_event(self, method: str, since: int, cap: float = 30) -> None:
        end = time.time() + cap
        while time.time() < end:
            if any(e.get("method") == method for e in self.events[since:]):
                return
            self.pump(0.1)

    def js(self, expr: str, await_promise: bool = False):
        r = self.call(
            "Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=await_promise
        )
        if "exceptionDetails" in r:
            raise RuntimeError(f"js: {r['exceptionDetails']}")
        return r["result"].get("value")

    def close(self) -> None:
        self.ws.close()
        with contextlib.suppress(OSError):
            urllib.request.urlopen(f"{self.devtools}/json/close/{self.id}").close()


def open_tab(devtools: str, width: int, theme: str) -> Tab:
    req = urllib.request.Request(f"{devtools}/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(req) as r:
        info = json.load(r)
    t = Tab(devtools, info["webSocketDebuggerUrl"], info["id"])
    for domain in ("Page", "Network", "Runtime", "Log", "Audits"):
        t.call(f"{domain}.enable")
    phone = width < 600
    t.call(
        "Emulation.setDeviceMetricsOverride",
        width=width,
        height=844 if phone else 900,
        deviceScaleFactor=1,
        mobile=phone,
    )
    set_theme(t, theme)
    return t


def set_theme(t: Tab, theme: str) -> None:
    t.call(
        "Emulation.setEmulatedMedia",
        features=[{"name": "prefers-color-scheme", "value": theme}],
    )


def _args_text(args: list[dict]) -> str:
    return " ".join(str(a.get("value", a.get("description", a.get("type", "")))) for a in args)


def collect(events: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """(console, csp, hosts) from the DevTools events of one visit."""
    console, csp, hosts = [], [], set()
    for e in events:
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            parts = urlsplit(p["request"]["url"])
            if parts.scheme in ("http", "https", "ws", "wss"):
                hosts.add(parts.hostname or "")
        elif m == "Runtime.consoleAPICalled":
            console.append(f"console.{p['type']}: {_args_text(p.get('args', []))}")
        elif m == "Runtime.exceptionThrown":
            d = p["exceptionDetails"]
            console.append(f"exception: {d.get('exception', {}).get('description', d['text'])}")
        elif m == "Log.entryAdded" and p["entry"]["level"] in ("error", "warning"):
            en = p["entry"]
            console.append(f"log.{en['level']} [{en['source']}]: {en['text']} {en.get('url', '')}")
        elif m == "Audits.issueAdded" and p["issue"]["code"] == "ContentSecurityPolicyIssue":
            d = p["issue"]["details"].get("contentSecurityPolicyIssueDetails", {})
            loc = d.get("sourceCodeLocation", {})
            csp.append(
                f"{d.get('violatedDirective', '?')} {d.get('blockedURL', '')} "
                f"{d.get('contentSecurityPolicyViolationType', '')} "
                f"{loc.get('url', '')}:{loc.get('lineNumber', '')}".strip()
            )
    return console, csp, sorted(hosts)


def screenshot(t: Tab, path: Path, width: int) -> str:
    h = t.js("Math.max(1, Math.min(document.documentElement.scrollHeight, 16000))")
    shot = t.call(
        "Page.captureScreenshot",
        format="png",
        captureBeyondViewport=True,
        clip={"x": 0, "y": 0, "width": width, "height": h, "scale": 1},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(shot["data"]))
    return str(path)


def visit(devtools: str, origin: str, url: str, theme: str, width: int, shots: Path, base: str,
          flip: bool = False) -> dict:  # fmt: skip
    t = open_tab(devtools, width, "light" if flip else theme)
    try:
        since = len(t.events)
        t.call("Page.navigate", url=origin + url)
        t.wait_event("Page.loadEventFired", since)
        t.pump(1.5)
        if flip:
            set_theme(t, "dark")
            t.pump(0.5)
        # console, CSP and hosts belong to the page, not to axe: collect before injecting it
        console, csp, hosts = collect(t.events)
        overflow = t.js(OVERFLOW_JS)
        name = f"{slug(url, base)}-{'flipped' if flip else theme}-{width}.png"
        shot = screenshot(t, shots / name, width)
        t.js(AXE_JS.read_text(encoding="utf-8"))
        axe = t.js(AXE_RUN_JS, await_promise=True)
    finally:
        t.close()
    return {
        "url": url,
        "theme": "light->dark" if flip else theme,
        "width": width,
        "axe": axe,
        "overflow": overflow,
        "console": console,
        "csp": csp,
        "hosts": hosts,
        "screenshot": shot,
    }


def failures(r: dict) -> list[str]:
    out = []
    if r["axe"]:
        out.append(f"axe {len(r['axe'])}")
    if r["overflow"]:
        out.append(f"overflow {len(r['overflow'])}")
    if r["console"]:
        out.append(f"console {len(r['console'])}")
    if r["csp"]:
        out.append(f"csp {len(r['csp'])}")
    foreign = [h for h in r["hosts"] if h not in ALLOWED_HOSTS]
    if foreign:
        out.append(f"hosts {','.join(foreign)}")
    return out


@contextlib.contextmanager
def serve(site: Path, base: str):
    """`python -m http.server` on 127.0.0.1 with the site reachable under `base`."""
    root = Path(tempfile.mkdtemp(prefix="render-pass-root-"))
    rel = base.strip("/")
    if rel:
        link = root / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(site.resolve(), target_is_directory=True)
    else:
        root.rmdir()
        root = site.resolve()
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", "--bind", "127.0.0.1", str(port)],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    origin = f"http://127.0.0.1:{port}"
    try:
        wait_http(origin + base)
        yield origin
    finally:
        proc.terminate()
        proc.wait()
        if rel:
            shutil.rmtree(root, ignore_errors=True)


@contextlib.contextmanager
def chrome():
    port = free_port()
    profile = tempfile.mkdtemp(prefix="render-pass-chrome-")
    proc = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-component-update",
            "--hide-scrollbars",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    devtools = f"http://127.0.0.1:{port}"
    try:
        wait_http(devtools + "/json/version", 30)
        yield devtools
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        shutil.rmtree(profile, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", type=Path, required=True, help="exported static edition")
    ap.add_argument("--base", default="/velometer/", help="base path the site was exported for")
    ap.add_argument("--out", type=Path, required=True, help="results.json and shots/ go here")
    ap.add_argument("--themes", default="light,dark")
    ap.add_argument("--widths", default="1280,390,320")
    ap.add_argument(
        "--pages", default="all", help="all, types, or comma-separated URLs (base included)"
    )
    ap.add_argument("--flip", action="store_true", help="light, then dark mid-page (own mode)")
    a = ap.parse_args(argv)

    base = _norm_base(a.base)
    site = a.site.resolve()
    if not (site / "index.html").is_file():
        ap.error(f"{site} has no index.html; export the static edition first")
    themes = [x for x in a.themes.split(",") if x]
    if bad := [x for x in themes if x not in ("light", "dark")]:
        ap.error(f"unknown theme(s): {bad}")
    widths = [int(x) for x in a.widths.split(",") if x]
    if a.pages == "all":
        urls = page_urls(site, base)
    elif a.pages == "types":
        urls = type_urls(page_urls(site, base), base)
    else:
        urls = [u for u in a.pages.split(",") if u]
    if a.flip:
        themes = ["light->dark"]

    out = a.out
    shots = out / "shots"
    if shots.exists():
        shutil.rmtree(shots)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    total = len(urls) * len(themes) * len(widths)
    with serve(site, base) as origin, chrome() as devtools:
        for url in urls:
            for theme in themes:
                for width in widths:
                    r = visit(devtools, origin, url, theme, width, shots, base, flip=a.flip)
                    results.append(r)
                    bad = failures(r)
                    print(f"[{len(results)}/{total}] {url} {r['theme']} {width}: "
                          f"{'; '.join(bad) or 'ok'}", flush=True)  # fmt: skip
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")

    failed = [r for r in results if failures(r)]
    rules = Counter(v["id"] for r in results for v in r["axe"])
    print(f"\n{len(results)} visits, {len(failed)} with findings; results in {out}/results.json")
    for rule, n in rules.most_common():
        print(f"  axe {rule}: {n} visits")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
