# tools

Developer tools that are not part of the velometer package and stay out of the gate.
`render_pass.py` imports `velometer.i18n` (M12): its English-leak step uses the same phrase,
visibility and word rules as `tests/test_m12_leak.py`, so it runs in the project environment
(`uv run --group dev`), not as a stdlib-only script.

## render_pass.py

Audits the exported static edition in headless Chrome (M10 spec decision 7). It serves the export
with `python -m http.server` on 127.0.0.1 under the base path and drives
`/usr/bin/google-chrome --headless=new` over the DevTools protocol (`websocket-client`, in the
`dev` dependency group). For every page × theme (`prefers-color-scheme`) × width it records:

- axe-core violations for the tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`;
- overflow: boxes whose content is wider than they are. This covers scrollers, boxes that clip
  the content (marked `clipped`), and boxes the content spills out of, including a leaf's own
  text. It also covers the document being wider than the layout viewport (`:root`). Not counted:
  prose tables, the Leaflet map, `text-overflow: ellipsis`, visually hidden boxes of 1px or less,
  and a box whose only spill is a prose table;
- errors: a failed navigation, a document that is not 200 (304 from the cache counts as 200), or
  a load event that has not fired within 30 s;
- console messages (console API, uncaught exceptions, browser log errors and warnings such as
  failed loads);
- CSP violations (DevTools `Audits` issues);
- the hosts requested;
- a full-page screenshot in `<out>/shots/<slug>-<theme>-<width>.png`.

```bash
uv run velometer app export --out "$SCRATCH/site/velometer" --base /velometer/ --clean
uv run --group dev python tools/render_pass.py --site "$SCRATCH/site/velometer" \
    --base /velometer/ --out tools/out/NAME [--themes light,dark] [--widths 1280,390,320] \
    [--pages all|types|/velometer/compare,...] [--flip] [--interact] [--keyboard] [--chrome PATH]
```

- `--pages all` (default) visits every exported page, the German `/de/` tree included. HTML
  fragments (the city panels) and `404.html` are skipped. `--pages types` keeps every page
  outside `/city/` and `/de/city/` plus, in each language, the tabs of Berlin and of the first
  city whose tab list differs from Berlin's.
- Every page visit checks the language (M12): `<html lang>` is `de` under `<base>de` and `en`
  elsewhere, and every `link[rel=alternate]` resolves to an exported page (fetched from the
  server). On a German page it also runs the English-leak step after the JS has drawn: the live
  document's visible text (`i18n.visible_text`) and the labels a reader hears (`aria-label`,
  `title`, `img[alt]`) outside subtrees in another language hold no phrase of
  `i18n.leak_phrases()` or `i18n.content_phrases()`, no common English word
  (`i18n.english_words`, proper names passed over) and no `[data-fallback]` element.
- `--flip` changes how the page visits run (it combines with `--interact` and `--keyboard`, which
  run as usual). Each page loads in light, the emulated scheme switches to dark
  mid-page, and after 500 ms the page is audited and shot as `<slug>-flipped-<width>.png`.
- `--interact` adds one visit per theme and width to `<base>compare`. It switches to the table
  view and clicks the first city link, the way a reader would, and waits for the city panel to
  load. Then it runs the same checks with the panel open, presses Escape, and checks that the
  panel closed and focus went back to the link. Screenshots are `compare-panel-<theme>-<width>.png`.
  It also adds three more visits per theme and width (M11): `city/berlin/time` with the first Cite
  opened and its Copy button pressed (three blocks, live region "Copied" or "Press Ctrl+C to
  copy"); `city/berlin/tiers` with the Download menu, saving SVG, PNG and CSV into the out
  directory (the SVG has no `var(` and names OpenStreetMap contributors); and `permalinks`, the
  tier map loaded from `?kind&tiers&at` (the view is read back from the tile under the map's
  centre, `MAP_VIEW_JS`; `map.js` exposes no hook), a zoom and a drag that rewrite `at`, a story
  `#step-` and a compare `panel=` URL that reopen their state, and a hostile query that opens the
  defaults with a clean console. The city panel's fragment root must carry the page's `lang`.
  The German edition gets the same cite, download and permalink visits on its own pages
  (`de/city/berlin/time`, `de/city/berlin/tiers`, `de/stories`, `de/compare`), with German
  expectations: the citation says "[Datensatz]" and carries the `/de/` address, Copy and the
  downloads announce in German, the SVG names "OpenStreetMap-Mitwirkende" with the German source
  line and German month labels ("Okt. 2026"), and the CSV keeps the English preamble over the
  table's German header with dot-decimal cells. One more entry per theme and width
  (`<base>de (search, switch)`, with `steps`) types "krakau" in the German nav search and must
  land on `de/city/krakow`, and switches a German Compare permalink to English with its query and
  hash kept. Downloaded files are kept beside the screenshots
  (`[de-]saved-<theme>-<width>.{svg,png,csv}`; the page screenshot is `[de-]download-…png`).
- `--keyboard` adds one scripted keyboard pass per theme (entry `kind: keyboard`, no axe or
  screenshot). It sends real key events with `Input.dispatchKeyEvent` and checks, step by step:
  the skip link (first Tab, visible ring, Enter moves focus to `main`), the Cities menu (Enter
  opens, Escape closes and returns focus), the phone menu at 390 px, a city's tabs, Compare (tick
  a city, change the metric, switch to the table view, re-sort with focus kept, open the panel,
  Escape returns focus to the opener, back to the chart view with every ARIA id reference
  resolving and no axe violation), the nav search (type, Escape twice, arrows, Enter lands on the
  city, "zzz" shows "No match", axe with the list open; at 1280 and 320 px) and the tier and
  counter maps (`+` and `-` zoom). Each step
  is a line in the entry's `steps` (`ok`/`FAIL`); a failed step is an error, so the exit status
  is 1. Use `--pages ""` to run it alone.
- `--chrome PATH` sets the Chrome binary. The default is `$VELOMETER_CHROME`, else
  `/usr/bin/google-chrome`. A missing binary is a usage error.
- The exit status is 1 if any visit has an error, an axe violation, overflow, a console message,
  a CSP violation or a host other than `127.0.0.1` and `tile.openstreetmap.org`. It is also 1
  when nothing was visited. Otherwise it is 0.
- `<out>/results.json` lists one entry per visit and is rewritten after every visit:
  `{url, theme, width, kind: page|flip|interact, axe: [{id, impact, nodes}], overflow, console,
  csp, hosts, errors, screenshot}`.
- `tools/out/` is git-ignored.

The tool contacts `tile.openstreetmap.org` because the maps do. The browser cache is kept
between visits, so each tile is fetched only once per run.

## orca_pass.py

Runs the real Orca screen reader (`/usr/bin/orca`, 50.x) over the exported static edition (M13
spec §4.7) and logs what it says, without touching the desktop it runs next to. Everything runs
inside `dbus-run-session`, so Orca, Chrome and their AT-SPI bus are private to the run:

- no display: `DISPLAY` is unset and `WAYLAND_DISPLAY` names a socket that does not exist;
  Chrome runs headless (`--ozone-platform=headless --headless=new --app=URL`) with
  `--force-renderer-accessibility` and still registers with the private AT-SPI bus;
- no audio: a stub blocks Orca's `speechd` import and Orca gets a speech server that only writes;
  each utterance lands in Orca's debug log as `SPEECH OUTPUT: '<text>' <voice>`, the voice
  carrying the language Orca switched to (`lang`);
- Orca's settings stay out of the user's: `HOME`, `XDG_*` point into `--out`, and
  `GSETTINGS_BACKEND=memory`.

Keys reach the page as real key events through CDP `Input.dispatchKeyEvent` (Tab, Shift+Tab,
Enter, Escape, arrows, typed letters). Orca's own browse-mode keys (H, T, table navigation, say
all) are sent as the same commands over Orca's D-Bus remote control, because without a display no
key reaches Orca. Each page loads in a fresh Chrome (navigating one tab left Orca on the previous
page's objects).

```bash
uv run velometer app export --out "$SCRATCH/site" --base /velometer/ --clean
uv run --group dev python tools/orca_pass.py --site "$SCRATCH/site" --base /velometer/ \
    --out "$SCRATCH/orca" [--editions en,de] [--steps home,compare-table,...]
```

`--out` gets `transcript.md` (per step: the keys, the DOM focus, Orca's locus, what Orca said and
in which language), `steps.json` and Orca's raw `orca-debug.log`. The review log of M13 is
`docs/review/m13-screen-reader.md`.

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
