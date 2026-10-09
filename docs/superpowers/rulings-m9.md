# M9 rulings

The static edition (spec `docs/superpowers/specs/2026-10-09-velometer-m9-design.md`, plan
`docs/superpowers/plans/2026-10-09-velometer-m9.md`). These are the controller rulings from the SDD
ledger (`.superpowers/sdd/2026-10-09-velometer-m9/progress.md`), in readable form, by task. Each
gives the decision, the reason, and what it costs.

## Pre-flight

- **URL test cases have one owner per step.** Task 1 wrote its URL cases inline; Task 2 moved
  them into `tests/url_cases.json`, which both pytest (`app/urls.py`) and `node --test`
  (`static/js/base.js`) read. No two tasks own the same file at once. Cost: a small test move in
  Task 2.

## Task 1 (base path, `u()`, CSP meta tag)

- **`u()` lives in the templates; Python modules keep returning plain paths.** The exception is
  the three URLs that reach the JS through a page's JSON config (`tiermap.kinds[].url`,
  `change_map.url`, the story config's step `href`): `main.py` adds the base to them, so no module
  signature changes. Cost: a double-base risk in the JS, which Task 2 handled (those three are
  never passed through `url()` again, and tests check they carry the base exactly once under `/`
  and `/velometer/`).
- **`test_app.py::_loaded_hosts` ignores the CSP meta tag.** The policy names the tile host but
  loads nothing from it. Cost: none.
- **The live app may differ from M8 by two meta tags, not one.** The spec's Components section and
  the brief require both the CSP meta tag and `<meta name="velometer-base">`; the constraint's
  "except the CSP meta tag" wording was a plan slip. Cost: none.
- **Header-only CSP directives are documented in HANDOVER, not only in a code comment** (spec
  decision 6). Done in Task 5: HANDOVER §8 "Serving the static edition" lists `frame-ancestors`,
  `report-uri`, `report-to` and `sandbox` (`main.HEADER_ONLY_DIRECTIVES`). Cost: a docs line.

## Task 3 (`velometer app export`)

- **`404.html` is an HTML page.** Spec decision 2 intends a 404 page, but the app's 404 was
  FastAPI's JSON default. Task 4 added an HTML 404 for page routes (layout, nav, a link home); the
  JSON 404 stays for `/data`, `/maps` and `/static`; the export writes `404.html` from it. Cost:
  one template and a handler.
- **Task 3's own rulings are accepted:** the `-dirty` marker stays in the footer commit;
  `build.json` lists OSM timestamps per city, sorted and deduplicated; the output is built in a
  staging directory and swapped in only when complete; `--config` and `--config-dir` are both
  accepted; the Starlette TestClient warning is silenced inside the export only. Cost: none.
- **Fix round 1 also takes Minors M-1, M-2, M-3, M-4 and M-7**, because the export deletes files
  and safety around deletion is not optional: `ExportError` messages instead of tracebacks, with
  a failing URL named on a 500 (M-1); refuse `/`, `$HOME`, the repository root and any directory
  that contains an input (M-2); re-check the guard right before deletion (M-3); the staging
  directory sits outside the repo or is git-ignored (M-4); `--base` is validated (M-7). Cost: a
  larger fix round.
- **The CLI refuses `--out .` and any parent of the working directory**, because the relative
  `data/plans` default is an input inside such an `--out`. Refusing is safer than supporting it.
  HANDOVER §8 documents it (Task 5). Cost: one doc line.

## Task 4 (reference scan, HTML 404, static compare note)

- **`export.UNVENDORED` allows exactly three unvendored images from `leaflet.css`**
  (`layers.png`, `layers-2x.png`, `marker-icon.png`), matching `static/vendor/VERSIONS`. A test
  guards that the app's JS never calls `L.marker`, `L.icon` or `L.control`. Cost: a broken image
  if a later map uses markers or controls, but that test fails first.
- **Export tests use a content copy whose city links point at the fixture DB's city.** The
  shipped content links to cities the fixture lacks; the real export scans clean. Cost: none.
- **Fix round 1 also takes Minor 2 and Minor 5:** `http://tile.openstreetmap.org` is no longer
  accepted as a loaded host, because the CSP is https-only and the constraint names the https
  host; the 404 test is scoped to `<main>`, so the nav link alone cannot satisfy it. Cheap, and
  Minor 2 is a constraint. Cost: none.

## Task 5 (render pass, docs)

- **The render pass found nothing that breaks the static edition, so M9 has no Task 5 code
  change.** The real export under `/velometer/`, served by `python -m http.server`, passed every
  check on 20 page URLs at 1280 and 390 px, plus the carried interactive checks (compare history,
  the city panel through the directory redirect, overview click-through, a compare `?…` state,
  maps). Evidence: `.superpowers/sdd/2026-10-09-velometer-m9/task-5-report.md`.
- **A host's own 404 is noted, not fixed.** `python -m http.server` answers unknown paths with
  its own error page, not `404.html`. The exported `404.html` renders correctly at
  `/velometer/404.html` (no console errors, no CSP violations). HANDOVER says to point the host's
  not-found page at it. Cost: none.
- **CLAUDE.md "Next:" names M10 (not yet specced).** The user chose the four-milestone roadmap
  (spec §2), so "none planned" would be stale. Cost: none.

## Follow-ups

Deferred review minors, by task:

- T1: `urls._is_external` treats only letters-only schemes as external (`web+foo:` raises).
- T1: the unit filter lambda parameter `u` shadows the `u()` helper (`main.py`, the `unit`
  filter).
- T2: the literal-route rule misses a bare `"/"`, joined strings, routes after `${x}` and a
  relative `"city/…"` (none exist today). Add a comment saying what it covers.
- T2: `base.test.mjs` finds `url_cases.json` by six `../` (it fails loudly if moved).
- T2: a `base.test.mjs` assertion (around line 87) does not match its test name.
- T2: `base()` queries the DOM on every `url()` call (negligible).
- T3: `plans_data_dir` has no CLI option (always `data/plans`, as `serve`).
- T3: the test map regex copies the implementation's (M-5).
- T3: the test follows redirects and the code does not (M-6).
- T3: every page is rendered twice (M-8).
- T3: the `validate_base` regex's `$` accepts a trailing newline (use `fullmatch`).
- T3: rollback catches `OSError` only. A Ctrl-C mid-swap leaves `out` half-swapped with the old
  export in `.velometer-staging-*-old-*`, and no message names it.
- T3: a failed rollback rename leaves the old contents in the set-aside directory, and only the
  errno hints at it.
- T3: `out.mkdir` runs before the `try`, so a failed set-aside creation leaves an empty `out`.
- T4: the Leaflet allowlist guard ignores `L.geoJSON`'s default marker for Point features (no
  map draws Point features today). A Point layer would load the unvendored `marker-icon.png`.
- T4: the JS scan skips lines starting with `*` as comments.
- T4: an `export.py` docstring line is about 140 characters.
- T4 (noted): the JS scan checks only literal `url()` paths. Runtime-built city and panel URLs
  rely on the export writing every city page and panel.

Hosting and later work:

- **Size:** the export is about 252 MB (258 files), 237 MB of it tier-map GeoJSON. Simplify or
  compress before hosting (HANDOVER §12 Q4, publishing, stays open).
- **Live-vs-main identity (done, clean):** the M9 final review rendered all 232 export URLs
  plus `/404` and a compare `?…` state on `m9` and `main` at base `/`. The 103 HTML pages differ
  by exactly the two meta lines. The panels, PNGs, GeoJSON and `series.json` are identical.
  The CSVs differ only in the existing `# velometer <commit> generated <time>` preamble line,
  and `/404` is the ruled HTML page. Not a standing test.
- **Render-pass observations (out of scope for M9):**
  - At 390 px the wide tables (overview key numbers and rankings) are readable only
    inside their own scroll boxes. The page itself does not scroll sideways. This is M10's
    phone-table work.
  - After the directory redirect, Compare shows `/velometer/compare/?…` (with the slash) until
    the first change of selection, which rewrites it to `/velometer/compare?…`. Both URLs work.
    This is cosmetic.
  - Dark theme and accessibility were not checked (M10).
