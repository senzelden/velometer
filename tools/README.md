# tools

Developer tools that are not part of the velometer package and stay out of the gate.

## render_pass.py

Audits the exported static edition in headless Chrome (M10 spec decision 7). It serves the export
with `python -m http.server` on 127.0.0.1 under the base path and drives
`/usr/bin/google-chrome --headless=new` over the DevTools protocol (`websocket-client`, in the
`dev` dependency group). For every page × theme (`prefers-color-scheme`) × width it records:

- axe-core violations for the tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`;
- overflow: elements wider than their box (not counting prose tables, the Leaflet map and
  elements that clip their overflow), and the document wider than the viewport (`:root`);
- console messages (console API, uncaught exceptions, browser log errors and warnings such as
  failed loads);
- CSP violations (DevTools `Audits` issues);
- the hosts requested;
- a full-page screenshot in `<out>/shots/<slug>-<theme>-<width>.png`.

```bash
uv run velometer app export --out "$SCRATCH/site/velometer" --base /velometer/ --clean
uv run --group dev python tools/render_pass.py --site "$SCRATCH/site/velometer" \
    --base /velometer/ --out tools/out/NAME [--themes light,dark] [--widths 1280,390,320] \
    [--pages all|types|/velometer/compare,...] [--flip]
```

- `--pages all` (default) visits every exported page. HTML fragments (the city panels) and
  `404.html` are skipped. `--pages types` keeps every page outside `/city/` plus the tabs of
  Berlin and of the first city whose tab list differs from Berlin's.
- `--flip` is a separate mode. Each page loads in light, the emulated scheme switches to dark
  mid-page, and after 500 ms the page is audited and shot as `<slug>-flipped-<width>.png`.
- The exit status is 1 if any visit has an axe violation, overflow, a console message, a CSP
  violation or a host other than `127.0.0.1` and `tile.openstreetmap.org`. Otherwise it is 0.
- `<out>/results.json` lists one entry per visit:
  `{url, theme, width, axe: [{id, impact, nodes}], overflow, console, csp, hosts, screenshot}`.
- `tools/out/` is git-ignored.

The tool contacts `tile.openstreetmap.org` because the maps do. The browser cache is kept
between visits, so each tile is fetched only once per run.

## axe/

axe-core is pinned in `axe/VERSION` (version, sha256 of `axe.min.js`, date vendored) and
licensed MPL-2.0 (`axe/LICENSE`). It is injected by the render pass through `Runtime.evaluate`.
It is never served by the app and never exported, because the export copies only
`src/velometer/app/static/`. `tests/test_tools.py` pins the hash and checks the static
directory.

To upgrade it, take the newest 4.x release on `registry.npmjs.org/axe-core` that is at least
14 days old. Download `axe.min.js` and `LICENSE` from
`cdn.jsdelivr.net/npm/axe-core@<version>/`, check them against the npm tarball, and rewrite
`VERSION`.
