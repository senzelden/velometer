# M9 static edition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `velometer app export --out dist/ [--base /path/]` writes a static edition of the whole
reader app that any static host can serve under any path, rendered from the existing FastAPI app.

**Architecture:** A base-path helper `u()` threads through templates, Python-built links and JS;
`export.py` enumerates URLs from the data, renders each through Starlette's TestClient, maps URLs
to files, copies static assets, scans every written file for unresolved references, and writes
`build.json`. The live app keeps base `/` and its HTML is unchanged except a CSP meta tag.

**Tech Stack:** Python 3.12 (uv, FastAPI/Starlette, Jinja2, Typer, pytest, ruff), plain ES
modules with `node --test`, headless Chrome for the render pass.

**Spec:** `docs/superpowers/specs/2026-10-09-velometer-m9-design.md` (binding).

## Global Constraints

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test "src/velometer/app/static/js/tests/*.test.mjs"`. Network tests are `@pytest.mark.slow`.
- No pipeline, classifier, run or DB change; no displayed number changes. `velometer.sqlite` is
  opened read-only by the app and the export and never written (md5 unchanged).
- OSM figures are "mapped km" (ADR 0006); no construction verbs for OSM figures.
- The only external host is `tile.openstreetmap.org`; no npm packages, no build step for JS/CSS.
- ODbL / OSM attribution and every existing attribution line stay on every exported page.
- The live app (`velometer serve`, base `/`) renders the same HTML as before M9 except the CSP
  meta tag.
- Tests assert rules, not today's values; each change has a test that fails without it
  (red-proof by breaking the rule).
- Commits: explicit paths, one trailer line `Assisted-by: Claude:claude-opus-5-5`. Never push.
  `dist/` stays git-ignored; never commit export output.

## Review Focus

- A base path given without slashes (`velometer`, `/velometer`, `velometer/`) normalises to
  `/velometer/`; `/` stays `/` (Task 1).
- A link built in Python (narratives, compare `href`, plan and organisation pages) or in JS
  (panel fetch, compare history, nav) that bypasses `u()`/`base()` breaks only under a non-root
  base — the rule tests must render under `/velometer/` (Tasks 1, 2, 4).
- `--clean` on a directory that is not a previous export must refuse and delete nothing (Task 3).
- A city without a given tab, plan page or subareas CSV must not be exported or linked (Task 3).
- Compare opened at `/velometer/compare?c=…&m=…` in the static edition draws that state (Task 5).

---

### Task 1: Base path in the app (`u()`, templates, Python links, meta tags)

**Files:**
- Create: `src/velometer/app/urls.py`
- Modify: `src/velometer/app/main.py` (`create_app` ~269 gains `base_path: str = "/"` and
  `static_edition: dict | None = None`; Jinja globals; `CSP` ~105 exposed to the template),
  `src/velometer/app/templates/base.html` and every template with an internal
  `href`/`src`/`action` (64 occurrences today), Python modules that build internal links:
  `main.py` (compare `href` lambda, redirects), `compare.py`, `narrative.py`, `story.py`,
  `organisations.py`, `plans_pages.py`, `counts.py` (whatever builds `/city/`, `/compare`,
  `/data/`, `/maps/`, `/plans`, `/organisations`, `/methodology`, `/static/` strings)
- Test: `tests/test_urls.py` (new), `tests/test_app_base.py` (new)

**Interfaces:**
- Produces: `urls.normalise_base(base: str) -> str` (returns `/` or `/x/…/`);
  `urls.make_u(base: str) -> Callable[[str], str]` (`u("/city/berlin")` →
  `"/velometer/city/berlin"`; keeps query and fragment; leaves external and `#` URLs
  untouched; raises `ValueError` on a path not starting with `/`); Jinja global `u`;
  `create_app(..., base_path="/", static_edition=None)`; `app.state.base_path`;
  `main.CSP` (string) and `main.csp_meta(csp: str) -> str` (policy minus header-only directives:
  `frame-ancestors`, `report-uri`, `report-to`, `sandbox`).

- [ ] **Step 1:** Failing tests in `tests/test_urls.py`: normalisation table (`""`, `/`,
  `velometer`, `/velometer`, `velometer/`, `/a/b` → `/`, `/`, `/velometer/`, `/velometer/`,
  `/velometer/`, `/a/b/`); `u` prefixes, keeps `?q=1#x`, leaves `https://…`, `mailto:`, `#x`
  unchanged, refuses `city/berlin`; `csp_meta` drops exactly the header-only directives.
- [ ] **Step 2:** Failing rule tests in `tests/test_app_base.py`: build the app with the fixture
  DB used by `tests/test_app.py` and `base_path="/velometer/"`; render a representative set
  (`/`, `/cities`, `/compare`, `/city/<fixture city>`, every tab it has, `/stories`,
  `/differences`, `/organisations`, `/plans`, a plan page if the fixture has one,
  `/methodology`); parse every `href`, `src`, `action` and `content` of
  `meta[name=velometer-base]`; assert every internal reference starts with `/velometer/`
  (rule over all pages and attributes). With `base_path="/"`, assert the rendered HTML equals
  the same page rendered by the pre-change templates except for the CSP meta tag — implement
  as: for each page, removing the `<meta http-equiv="Content-Security-Policy" …>` and
  `<meta name="velometer-base" content="/">` lines yields exactly the HTML a test helper
  renders with `u` set to identity (so the test proves `u("/")` is identity, not a golden).
  Every page has `<meta http-equiv="Content-Security-Policy" content="{csp_meta(CSP)}">` and
  `<meta name="velometer-base" content="{base}">`.
- [ ] **Step 3:** Run, confirm red.
- [ ] **Step 4:** Implement `urls.py`; `create_app` registers `u` as a Jinja global and stores
  the base; route every template URL and every Python-built internal URL through `u` (the
  routes themselves stay at `/…`; only emitted URLs get the base). `static_edition` (a dict
  `{"commit": "<short>"}` or None) drives the footer line "Static edition · build <short>"
  in `base.html` — rendered only when set.
- [ ] **Step 5:** Focused tests, then the gate; `velometer serve` smoke: start on 127.0.0.1 on a
  free port, fetch `/` and one city page, stop by pid. Commit
  `feat(app): base path helper for every emitted URL, CSP meta tag`.

### Task 2: Base path in JS

**Files:**
- Create: `src/velometer/app/static/js/base.js`
- Modify: `src/velometer/app/static/js/data.js` (~19 fetch), `panel.js` (~46 fetch),
  `compare.js` (~59, ~133 `history.replaceState`, any built link), `nav.js` (~43),
  `static/map.js`, `static/changemap.js`, `static/countermap.js`, `city.js`, `overview.js`,
  `story.js`, `plan-chart.js`, `chart.js` — any script that builds an internal URL
- Test: `src/velometer/app/static/js/tests/base.test.mjs` (new), extend
  `compare-model.test.mjs` / existing tests where URL building lives

**Interfaces:**
- Consumes: `<meta name="velometer-base" content="…">` from Task 1.
- Produces: `base.js` exports `base(doc = globalThis.document) -> string` (normalised, falls
  back to `/` when the meta tag is absent) and `url(path, doc?) -> string` (same contract as
  Python `u`); every internal URL in JS goes through `url()`.

- [ ] **Step 1:** Failing node tests: `base()` with no document, with meta `/`, with
  `/velometer/`; `url()` table mirroring Python's (`tests/test_urls.py` cases — put them in a
  shared `tests/url_cases.json` read by both, like `tests/counter_cases.json`); compare's URL
  serialisation under base `/velometer/` yields `/velometer/compare?…`; the panel fetch URL
  under base yields `/velometer/city/<id>/panel`.
- [ ] **Step 2:** Rule test (node): no JS file under `static/` (excluding `vendor/` and
  `tests/`) contains a string literal starting with `"/` or `` `/ `` or `'/` followed by one of
  the app's route prefixes (`city`, `compare`, `data`, `maps`, `static`, `plans`,
  `organisations`, `methodology`, `cities`, `stories`, `differences`) outside `base.js` — every
  such URL must be built with `url()`. Red on the current code.
- [ ] **Step 3:** Implement; keep behaviour identical under base `/`.
- [ ] **Step 4:** Node tests, gate. Commit `feat(app): JS builds internal URLs from the base meta tag`.

### Task 3: `velometer app export`

**Files:**
- Create: `src/velometer/app/export.py`
- Modify: `src/velometer/cli.py` (new `app` Typer group with `export`; `serve` stays where it
  is), `.gitignore` (confirm `dist/` present — it is)
- Test: `tests/test_export.py` (new)

**Interfaces:**
- Consumes: `create_app(..., base_path, static_edition)` and `urls` from Task 1.
- Produces: `export.export_urls(data, app) -> list[str]` (decision 4 of the spec);
  `export.url_to_path(url: str, content_type: str) -> PurePosixPath` (decision 2);
  `export.run_export(out: Path, base: str, db: Path, config_dir: Path, maps: Path, docs: Path,
  content_dir: Path, plans_data_dir: Path, clean: bool) -> ExportResult` with
  `ExportResult(files: int, bytes: int, build: dict)`; CLI
  `velometer app export --out PATH [--base /] [--clean] [--db …] [--config …] [--maps …]
  [--docs …] [--content …]`.

- [ ] **Step 1:** Failing tests with the fixture DB and a tmp `out`:
  - `url_to_path`: `/` → `index.html`; `/city/berlin` (text/html) → `city/berlin/index.html`;
    `/data/series.json` → `data/series.json`; `/data/berlin.csv` → `data/berlin.csv`;
    `/maps/x.png` → `maps/x.png`; a query string is refused.
  - `export_urls`: every URL returns 200 from the app; every city in the fixture has
    `/city/<id>` and its panel; a tab the app answers with 404 for a city is absent; every
    `/maps/…` URL referenced by an exported city page is present; `/data/series.json`,
    `/data/all.csv` present.
  - `run_export`: writes every enumerated URL to its path; copies `static/` (excluding
    `js/tests/`); writes `404.html` from the app's 404 response; writes `build.json` with keys
    `commit`, `commit_full`, `dirty`, `classifier_versions`, `osm_timestamps`, `base`,
    `built_at` (ISO UTC); every exported HTML page has the footer line "Static edition · build
    <commit>"; the fixture DB md5 is unchanged.
  - Guard: a non-empty `out` without `--clean` → error, nothing written; `--clean` on a
    directory without `build.json` → error, nothing deleted; `--clean` on a previous export →
    replaced.
  - A non-200 for an enumerated URL fails the export naming the URL and status (inject via a
    monkeypatched enumeration).
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Implement. Render with `TestClient(app, base_url="http://127.0.0.1:8000")`
  (the app's TrustedHost list). Build stamp from `git rev-parse` (no network); classifier
  versions and OSM timestamps from the read-only DB through the existing `ReportData`.
- [ ] **Step 4:** Focused tests, gate. Real export into the scratchpad
  (`/tmp/claude-1000/-home-senzelden-code-bike-infrastructure/7f268115-1621-46bb-9363-794aa122081a/scratchpad/m9-dist`,
  never the repo) with base `/`; report file count, size, time; md5 of `velometer.sqlite`
  before/after. Commit `feat(app): velometer app export writes the static edition`.

### Task 4: Reference scan, equality and the static compare note

**Files:**
- Modify: `src/velometer/app/export.py`, `src/velometer/app/templates/compare.html` (lede line
  in the static edition), `src/velometer/app/main.py` (pass `static_edition` to compare)
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `export.scan_references(out: Path, base: str) -> list[Unresolved]` with
  `Unresolved(file: str, ref: str)`; `run_export` calls it and fails listing every unresolved
  reference; foreign hosts other than `tile.openstreetmap.org` (and the attribution links'
  `https://` targets, which are links, not loaded resources — state the rule) fail.

- [ ] **Step 1:** Failing tests:
  - scan finds `href`, `src`, `action`, `<meta name=velometer-base>`, CSS `url(...)`, and JS
    string literals passed to `url()`/fetch that resolve to files; a planted dangling
    `href="/velometer/nowhere"` in a copy is reported with its file; a planted
    `<script src="https://cdn.example/x.js">` is reported as a foreign loaded resource; an
    `<a href="https://www.openstreetmap.org/copyright">` link is allowed.
  - Base rule over the whole export with `--base /velometer/`: no internal reference in any
    exported HTML/CSS/JS starts with `/` without `/velometer/`.
  - Equality: for every exported HTML page (base `/`), the file equals the live app's response
    for the same URL with `static_edition=None`, after removing the single footer line.
  - Every exported HTML file carries the CSP meta tag equal to `csp_meta(CSP)`.
  - Static compare: the exported `compare/index.html` lede says, in one line, that without
    JavaScript the static edition shows the default selection; the live app's compare does not.
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Real export with `--base /velometer/` into the scratchpad; scan passes; report
  counts. Gate. Commit `feat(app): export proves every reference resolves, static compare note`.

### Task 5: Render pass of the static edition, docs

**Files:**
- Modify: whatever the render pass shows broken (with tests), `HANDOVER.md` (§8 CLI
  `app export`, §9 M9 entry, a "Serving the static edition" note: directory redirect that keeps
  the query string, base path, no server code, CSP meta vs header), `CLAUDE.md` (latest line),
  `docs/superpowers/rulings-m9.md` (new: rulings and follow-ups)

- [ ] **Step 1:** Export the real data with `--base /velometer/` into the scratchpad. Serve it
  with `python -m http.server --bind 127.0.0.1 <port>` from a parent directory so the site sits
  under `/velometer/`. Headless Chrome at 1280 and 390 px on: `/velometer/`, `/cities`,
  `/compare`, `/compare?<a non-default state with 3 cities, a non-default metric and view>`,
  one city per tab type (story, time, tiers, figures, counts, bezirke) incl. Berlin, `/plans`,
  `/plans/berlin`, `/organisations`, `/stories`, `/differences`, `/methodology`,
  `/methodology/de`, `/404-test` (expect the 404 page if the server serves it, else note).
  Check: no horizontal scroll, no console errors, no CSP violations, no request to a host
  other than 127.0.0.1 and `tile.openstreetmap.org`, the compare state in the URL is drawn,
  a city panel opens from compare, maps load. Screenshots in the scratchpad; paths in the
  report. Fix findings with failing tests first.
- [ ] **Step 2:** Docs as listed. `velometer.sqlite` md5 unchanged; the six checks
  (`counters --check`, `content --check`, `report methodology --check`, `timeseries --check`,
  `reconcile --check`, `trust check`) exit 0; gate. Commit `docs(m9): handover, rulings, static edition note`.
