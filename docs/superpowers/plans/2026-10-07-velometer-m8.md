# velometer M8 Implementation Plan: organisations, plans and counters

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an organisations page (who produces each figure, how, and its political role), a
plans overview with a Berlin deep-dive (targets vs. every reporting document vs. infraVelo
projects vs. our mapped km on the planned network), and open bike-counter data for seven cities.

**Architecture:** Profiles and explanatory texts are YAML content checked by the M7
`velometer.content` machinery, extended with organisation and plan models and new fact families.
Plan targets and reported figures are curated data in `config/plans/`. The Berlin overlay and the
counters are new pipeline steps (`velometer plans …`, `velometer counters …`) that write new
tables in schema v9; the read-only app reads them through `ReportData`.

**Tech Stack:** Python 3 / uv, typer, Pydantic v2, SQLite, shapely (STRtree), openpyxl (Berlin
XLSX; check `pyproject.toml`, add with `uv add` only if absent), httpx or urllib (follow
`sources/download.py`), FastAPI + Jinja, vanilla ES modules + SVG with `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-07-velometer-m8-design.md` (read it first; § numbers
below refer to it). Feasibility log: `docs/review/m8-feasibility.md` (URLs, licences, documents).

## Global Constraints

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test "src/velometer/app/static/js/tests/*.test.mjs"`. Network tests are `@pytest.mark.slow`.
- OSM lengths are **mapped km** (ADR 0006). Outside quotes, no construction verb for OSM figures
  (`built`, `constructed`, `opened`, `removed`); the existing check applies to every new prose file.
- Quotes and factual claims about organisations come only from external sources in the registry;
  project documents are cited as data, never quoted (spec §2.6). Excerpts ≤ 60 words, verbatim,
  original language, `gloss_en` when not English.
- Counters are context: never "cycling in <city>", always "recorded at counter sites"; no causal
  wording between counts and km (spec §2.12). 2020 is marked as the COVID year on counter charts.
- Reported plan figures are stored as printed; disagreements are kept as revisions, typos get a
  `note`, never a correction (spec §2.8).
- Lengths only in the city's projected EPSG (Berlin EPSG:25833). Never type OSM ids from memory.
  No mapper uid/username anywhere. Never print, log or write credentials.
- No new OSM runs. M8 writes `velometer.sqlite` only into its new tables (`plan_overlay`,
  `counter_*`) and only after `cp velometer.sqlite data/velometer-pre-m8.sqlite` (once, Task 1).
- The app stays on 127.0.0.1, read-only, CSP unchanged: the only external host is
  `tile.openstreetmap.org`. No npm packages, no build step.
- Every downloaded dataset records URL, licence and retrieval timestamp; raw files live under
  `data/` (git-ignored) and are never committed.
- Never call `web.archive.org/save`. Never send the user's e-mail address anywhere.
- Commits: explicit paths, one trailer line `Assisted-by: Claude:claude-opus-5-5`.

**Plan rulings (recorded):**
- R1: the `/plans/berlin` explanatory text and the counter explainer are content files
  (`content/plans/berlin.yaml`, `content/counters.yaml`) with the M7 `Explainer`-like shape, so
  their numbers are declared facts and their quotes registry excerpts.
- R2: `Source.kind` gains `research` (the BikeNetKit paper and similar); existing sources are
  unchanged.
- R3: the app reads `config/plans/` directly (like `config/differences.yaml`); the page-cache
  fingerprint already covers `config_dir`.
- R4: `report/change.py`'s side extraction becomes a public helper
  `classified_sides(ways, cfg, epsg, boundary) -> dict[(way_id, side), Side]` reused by the overlay;
  `report change` output must be byte-identical before and after (test).
- R5: the counter site map is a server-rendered inline SVG of the LAU boundary (simplified) and
  the site points; no tiles at request time (the app has no live tile map today; spec §5.5 said
  "OSM tiles, as M6", but M6 maps are static images). Cost if wrong: a later tile layer.

## Review Focus

1. Hourly counter data across DST changes (23- and 25-hour local days) → a day is complete when
   every local hour of that day is present, so DST days are not marked incomplete (Task 6 test).
2. Overlapping counter files (Paris yearly archive + rolling 13-month dataset; Berlin re-issued
   XLSX) → counts are de-duplicated on (site, local hour) and the load is idempotent (Task 6 test).
3. A portal changes a column name or a yearly file is missing → the adapter raises
   `CounterFormatError` naming file and column; other cities still load (Task 6/7 tests).
4. A plan item with reports but `target_kind: none`, or a city with no plan → `/plans` and
   `/plans/berlin` render the reported markers or a note, never a 500 (Task 9 test).
5. WFS geometry that is MultiLineString, zero-length or outside the LAU boundary → the overlay
   explodes multi-parts, skips empty parts and clips to the boundary (Task 5 test).

---

### Task 1: Schema v9, repositories and `ReportData` accessors

**Files:**
- Modify: `src/velometer/db.py` (SCHEMA_VERSION 9, `_migrate_8_to_9`, new tables, repositories)
- Modify: `src/velometer/report/data.py` (accessors)
- Test: `tests/test_db_m8.py`

**Interfaces:**
- Produces (db.py):
  - `replace_plan_overlay(conn, city_id: str, rows: list[OverlayRow]) -> None` (deletes the city's
    rows of the same `overlay_version`, inserts)
  - `@dataclass(frozen=True) OverlayRow(run_id: int, city_id: str, network_class: str, tier: str,
    mapped_km: float, network_km: float, overlay_version: str, network_retrieved_at: str)`
  - `replace_counter_sites(conn, city_id, sites: list[CounterSite])`,
    `upsert_counter_daily(conn, rows: list[CounterDay])`,
    `replace_counter_monthly(conn, city_id, rows: list[CounterMonth])`,
    `replace_counter_index(conn, city_id, rows: list[CounterIndexYear])`
  - dataclasses `CounterSite(city_id, site_id, name, lat: float|None, lon: float|None, source,
    licence, url, retrieved_at, first_day: str|None, last_day: str|None)`,
    `CounterDay(city_id, site_id, day: str, count: int, complete: bool)`,
    `CounterMonth(city_id, site_id, month: str, day_type: str, avg_daily: float)`,
    `CounterIndexYear(city_id, year: int, index: float|None, sites: int, base_year: int,
    series: str)` (`series` is `counts` or `avg_daily_intensity`)
- Produces (ReportData): `plan_overlay(city_id) -> list[OverlayRow]`,
  `counter_sites(city_id) -> list[CounterSite]`, `counter_index(city_id) -> list[CounterIndexYear]`,
  `counter_cities() -> list[str]`. Each returns `[]` when the table is absent (a v8 DB opened
  read-only must still serve every M7 page).

Schema additions (appended to `_SCHEMA`; `_migrate_8_to_9` is a no-op body with a docstring,
"additive: tables come from the schema script"):

```sql
CREATE TABLE IF NOT EXISTS plan_overlay (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL, network_class TEXT NOT NULL,
  tier TEXT NOT NULL, mapped_km REAL NOT NULL, network_km REAL NOT NULL,
  overlay_version TEXT NOT NULL, network_retrieved_at TEXT NOT NULL,
  PRIMARY KEY (run_id, network_class, tier, overlay_version));
CREATE TABLE IF NOT EXISTS counter_sites (
  city_id TEXT NOT NULL, site_id TEXT NOT NULL, name TEXT NOT NULL, lat REAL, lon REAL,
  source TEXT NOT NULL, licence TEXT NOT NULL, url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  first_day TEXT, last_day TEXT, PRIMARY KEY (city_id, site_id));
CREATE TABLE IF NOT EXISTS counter_daily (
  city_id TEXT NOT NULL, site_id TEXT NOT NULL, day TEXT NOT NULL, count INTEGER NOT NULL
  CHECK (count >= 0), complete INTEGER NOT NULL, PRIMARY KEY (city_id, site_id, day));
CREATE TABLE IF NOT EXISTS counter_monthly (
  city_id TEXT NOT NULL, site_id TEXT NOT NULL, month TEXT NOT NULL, day_type TEXT NOT NULL,
  avg_daily REAL NOT NULL, PRIMARY KEY (city_id, site_id, month, day_type));
CREATE TABLE IF NOT EXISTS counter_index (
  city_id TEXT NOT NULL, year INTEGER NOT NULL, idx REAL, sites INTEGER NOT NULL,
  base_year INTEGER NOT NULL, series TEXT NOT NULL, PRIMARY KEY (city_id, year, series));
```

- [ ] **Step 1: Back up the DB** once: `cp velometer.sqlite data/velometer-pre-m8.sqlite`.
- [ ] **Step 2: Failing tests** (`tests/test_db_m8.py`): a fresh DB has the five tables at
  user_version 9; a v8 fixture DB migrates to 9 with every existing row count unchanged;
  `upsert_counter_daily` twice with the same rows leaves one row per key (idempotent);
  a negative count raises `sqlite3.IntegrityError`; `replace_plan_overlay` replaces only rows of
  the same version; `ReportData` on a v8 DB opened read-only returns `[]` from all four accessors.
- [ ] **Step 3: Run** `uv run pytest tests/test_db_m8.py -v` → FAIL.
- [ ] **Step 4: Implement** as above.
- [ ] **Step 5: Run** the test file, then the gate → PASS. Run `uv run velometer migrate` on the
  real DB, then
  `timeseries --check`, `reconcile --check`, `content --check` → exit 0.
- [ ] **Step 6: Commit** `feat(db): schema v9 for plan overlay and counters`.

---

### Task 2: Content models, loaders, facts and checks for organisations, plans and counters

**Files:**
- Modify: `src/velometer/content/models.py`, `loader.py`, `facts.py`, `check.py`
- Create: `src/velometer/plans/__init__.py`, `src/velometer/plans/models.py` (plan config models
  and loader), `config/organisations.yaml` (`[]`), `config/plans/plans.yaml` (`[]`) and
  `config/plans/reports.csv` (header row only); Tasks 3–4 fill them
- Modify: `src/velometer/cli.py` (`content --check` reports the new problems)
- Test: `tests/test_content_m8.py`, `tests/test_plans_models.py`, fixtures under
  `tests/fixtures/content_m8/`

**Interfaces:**
- Produces (content/models.py):
  ```python
  class OrgSection(_Strict):
      heading: str
      paragraphs: list[str]
      dimensions: dict[str, str] | None = None   # keys ⊆ differences.yaml dimension ids

  class Organisation(_Strict):
      id: str
      name: str
      kind: Literal["official", "ngo", "index", "research", "parliament", "agency"]
      url: str
      sections: list[OrgSection]
      quotes: list[Quote] = []
      facts: list[Fact] = []
      data_refs: list[DataRef] = []
      literals: list[str] = []
  ```
  `Source.kind` gains `"research"` (R1/R2). `Explainer` is reused unchanged for
  `content/plans/berlin.yaml` and `content/counters.yaml`.
- Produces (loader.py): `load_organisations(dir: Path, errors: dict[str, str] | None = None) ->
  dict[str, Organisation]`; `load_document(path: Path) -> Explainer | None` (generalises
  `load_explainer`, which stays as an alias).
- Produces (plans/models.py):
  ```python
  class PlanItem(_Strict):
      id: str; label: str
      target_kind: Literal["km_per_year", "km_cumulative", "km_total", "share", "none"]
      targets: dict[int, float] = {}
      unit: str = "km"

  class Plan(_Strict):
      id: str; city: str; title: str; adopted: date | None; url: str
      status: Literal["current", "expired", "replaced"]
      successor: str | None = None; publisher: str; items: list[PlanItem]
      note: str | None = None

  class ReportRow(_Strict):
      plan_id: str; item_id: str; year: int; value: float; unit: str
      quantity: Literal["implemented_in_year", "implemented_cumulative",
                        "under_construction", "in_planning"]
      doc_type: Literal["drucksache", "rote_nummer", "report", "web"]
      doc_id: str; doc_date: date; url: str; locator: str; retrieved_at: date
      note: str | None = None
      publisher: str

  def load_plans(dir: Path) -> tuple[list[Plan], list[ReportRow]]
  def current_and_revisions(rows: list[ReportRow]) -> dict[tuple[str, str, int, str],
      tuple[ReportRow, list[ReportRow]]]   # key (plan, item, year, quantity); latest doc_date wins
  ```
- Produces (facts.py), new families (document in the module docstring):
  - `overlay.<city>.<class>.<YYYY-MM-DD>.<ab_km|network_km>` (A+B mapped km on that network class
    at that snapshot, from `ReportData.plan_overlay`)
  - `overlay_change.<city>.<class>.<from YYYY-MM-DD>.<to YYYY-MM-DD>` (difference of `ab_km`)
  - `plan.<plan_id>.<item_id>.<year>.<quantity>[.<doc_id with / replaced by _>]` (current value,
    or the named document's value; needs `config_dir` → plumb `config_dir` through `evaluate`
    as an optional keyword, default `None`, raising FactError when needed and absent)
  - `counter.<city>.<year>` (index value) and `counter_sites.<city>.<year>` (qualifying sites)
- Produces (check.py):
  - `causal_counter_wording(paragraph: str) -> list[str]`: if the paragraph matches
    `\b(counter|counts?|counted|cyclists recorded)\b` (case-insensitive), return every match of
    `\b(led to|lead to|leads to|because of|drove|driven by|thanks to|resulted in|caused|due to)\b`.
  - `check_content` / `check_content_offline` also check `content/organisations/*.yaml`,
    `content/plans/berlin.yaml`, `content/counters.yaml` with the M7 document rules (citations,
    quotes, numbers, construction verbs) plus `causal_counter_wording`; and coverage:
    every `(city, source)` in `config/external/figures.csv` and every reconcile source maps via
    `config/organisations.yaml` (`- {city: "*" | <id>, source: <id>, organisation: <id>}`) to a
    profile file; every Berlin `ReportRow.publisher` and Berlin `Plan.publisher` is a profile id;
    every report row's plan and item exist; URLs are https; units are non-empty.
  - Coverage problems are reported only when `content/organisations/` exists (so Task 2 lands
    green before Task 3 writes profiles); once it exists, a missing profile is a problem.

- [ ] **Step 1: Failing tests**, one per rule, each red-proofed by breaking the rule:
  a profile citing an unknown source; a profile quote that does not match its excerpt; an
  undeclared number in a profile; `causal_counter_wording("Counts rose because of new lanes")`
  returns `["because of"]` and `causal_counter_wording("Rents rose because of demand")` returns
  `[]`; a figures.csv pair with no mapping; a report row naming an unknown item; an `http://`
  plan URL; `current_and_revisions` picks the later `doc_date` and lists the earlier row as a
  revision (fixture: Vorrangnetz 2025 printed 10.8 in one document and 8.6 in a later one —
  synthetic doc ids); `plan.*` fact returns the current value, and with a doc suffix the named
  document's value; `overlay.*` and `counter.*` facts against a fixture DB with rows from Task 1.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; gate; the real
  `uv run velometer content --check` still exits 0.
- [ ] **Step 5: Commit** `feat(content): organisations, plans and counter documents with checks`.

---

### Task 3: Organisation research and profiles (research agents)

**Files:**
- Create: `content/organisations/<id>.yaml` (about 10, spec §3.2), `docs/review/m8-organisations.md`
- Modify: `content/sources/*.yaml` (new sources and excerpts; new file `content/sources/orgs.yaml`
  for sources not tied to a region), `config/organisations.yaml`

Runs in parallel with Task 4 (different files). Controller commits.

- [ ] **Step 1:** List the bodies from `config/external/figures.csv` (city, source) pairs, the
  reconcile sources in `config/reconcile.yaml`, and the Berlin plan publishers (SenMVKU,
  infraVelo, Abgeordnetenhaus). Write `config/organisations.yaml`.
- [ ] **Step 2:** For each body, find external sources for: who they are, legal form, funding
  (where public), mandate; how they measure (map to the six dimensions of
  `config/differences.yaml`, quoting the body's own method text where one exists); political role
  (concrete, sourced: e.g. Volksentscheid Fahrrad → Mobilitätsgesetz 2018; Clean Cities rankings
  cited in city debates; Senate progress reports as the basis of Hauptausschuss scrutiny). Add
  sources and ≤ 60-word excerpts to the registry; log every source reached or not reached in
  `docs/review/m8-organisations.md`.
- [ ] **Step 3:** Write profiles: three sections ("Who they are", "How they measure" with
  `dimensions`, "Political role"), 150–300 words each profile, plain and specific; every claim
  cited `[@source_id]`; our own reading marked as such; 0–3 quotes; numbers are declared facts or
  literals.
- [ ] **Step 4:** `uv run velometer content --check` has no problem naming an organisation file;
  `uv run velometer content --check --online` passes for the new sources.
- [ ] **Step 5: Commit** (controller) `content(m8): organisation profiles and sources`.

---

### Task 4: Plan research and plan data (research agents)

**Files:**
- Create/modify: `config/plans/plans.yaml`, `config/plans/reports.csv`,
  `content/plans/berlin.yaml`, `docs/review/m8-plans.md`, registry sources as needed

Runs in parallel with Task 3. Controller commits.

- [ ] **Step 1: Berlin.** Read every document in `docs/review/m8-feasibility.md` §B–C at the page
  (Radverkehrsplan vo19-013 targets; Rote Nummern 1392 I, 0389/0389 A, 1064, 1733 B-1, 1733 C,
  1733 E; Drucksachen 19/27049, 19/25987, 19/25700, 19/10136 and the seen-but-unread 19/26599,
  19/26333, 19/14625). Enter one `reports.csv` row per printed figure per plan item, year and
  quantity, with page locator; verify each value against the PDF text (`pdftotext -layout`) and
  record the check in the log. The Drs 19/27049 Ergänzungsnetz 2023 cell (55.1) is stored as
  printed with a note naming the 36.24 km total.
- [ ] **Step 2: The other 20 cities.** Confirm each plan of the feasibility log §D at the source
  (title, adoption date, status, km target or `none`, successor if expired); at most a few report
  rows each, only from official documents; publishers named (not profiled).
- [ ] **Step 3: `content/plans/berlin.yaml`** (Explainer shape, 200–400 words): why "reported",
  "completed projects" and "mapped on the network" differ, using declared `plan.*` facts for
  reported values (overlay facts are added in Task 5 Step 6). External quotes only.
- [ ] **Step 4:** `content --check` clean for plan files.
- [ ] **Step 5: Commit** (controller) `data(m8): plans, Berlin reporting documents`.

---

### Task 5: Berlin network fetch and overlay

**Files:**
- Create: `src/velometer/plans/berlin.py` (WFS fetch), `src/velometer/plans/overlay.py`,
  `config/plans/overlay_v1.yaml`, `config/plans/sources.yaml` (WFS URLs, layer names, licence)
- Modify: `src/velometer/report/change.py` (R4 helper), `src/velometer/cli.py` (`plans` app:
  `fetch`, `overlay`)
- Test: `tests/test_overlay.py`, `tests/test_change.py` (byte-identity guard)

**Interfaces:**
- Consumes: `OverlayRow`, `replace_plan_overlay` (Task 1); `_change_run`-style run lookup from
  `cli.py` (all Berlin LAU history runs of the report classifier plus the latest current run).
- Produces:
  - `change.classified_sides(ways, cfg, epsg, boundary) -> dict[tuple[int, str], Side]` (public
    `Side(tier, line, km)`; `compute_change` uses it).
  - `plans.berlin.fetch_layers(cfg: PlanSourcesConfig, out_dir: Path, fetch=_http_get) ->
    FetchResult(paths: dict[str, Path], retrieved_at: str)`: GeoJSON via WFS GetFeature with
    `outputFormat=application/json`, `srsName=EPSG:25833`, paged with `count`/`startIndex` until a
    page is short; writes `<layer>.geojson` and `retrieved.json`.
  - `plans.overlay.OverlayConfig(version: str, buffer_m: float, max_angle_deg: float,
    min_part_m: float)` loaded from `overlay_v1.yaml`:
    ```yaml
    version: overlay_v1
    buffer_m: 12
    max_angle_deg: 30
    min_part_m: 20
    ```
  - `plans.overlay.network_lines(geojson: dict, class_field: str = "ist_radvorrangnetz") ->
    dict[str, list[LineString]]` (MultiLineStrings exploded, empty parts dropped; class names
    normalised to `vorrangnetz` / `ergaenzungsnetz`)
  - `plans.overlay.on_network_km(sides: dict, network: list[LineString], boundary, cfg) ->
    dict[str, float]` (per tier A and B):
    ```python
    tree = STRtree(network)
    for side in sides.values():                      # tiers A, B only
        line = clip.inside(side.line)
        for seg in _segments(line, step_m=cfg.min_part_m / 2):   # densified pieces
            near = tree.query(seg.buffer(cfg.buffer_m))
            if any(_angle(seg, network[i]) <= cfg.max_angle_deg
                   and network[i].distance(seg) <= cfg.buffer_m for i in near):
                keep.append(seg)
        km = sum(merged parts of keep longer than min_part_m) / 1000
    ```
    (`_angle` = undirected angle between the piece and the nearest network segment's local
    direction, in [0, 90].)
- CLI: `velometer plans fetch berlin` and `velometer plans overlay berlin [--version overlay_v1]`
  (re-reads each run's snapshot, `check_totals`-style comparison against stored per_side A–E
  totals to 0.01 km, aborts on mismatch, then `replace_plan_overlay`).

- [ ] **Step 1: Failing tests** on synthetic geometry (EPSG:25833 coordinates): a side parallel
  to a network line at 8 m counts fully; at 20 m it does not; a side crossing at 90° contributes
  0 km (pieces at the crossing fail the angle test); a 15 m overlap is dropped
  (`min_part_m` 20); a MultiLineString network feature and a zero-length part are handled; a side
  half outside the boundary counts only its inside part; totals mismatch aborts with the tier and
  both values. Guard: `report change` on the existing fixture produces identical markdown and
  GeoJSON before and after the R4 refactor (golden file captured first).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; gate.
- [ ] **Step 5: Real run:** `uv run velometer plans fetch berlin` then
  `uv run velometer plans overlay berlin`; record wall time, network km per class (expect about
  873 / 1,508 km per the feasibility log; report the actual values), and A+B on-network km per
  snapshot in `docs/review/m8-overlay.md` with a sanity map PNG of one year (matched vs unmatched
  network) under `data/maps/` linked from the log.
- [ ] **Step 6:** Add `overlay.*` facts to `content/plans/berlin.yaml` where the text states the
  overlay result; `content --check` clean.
- [ ] **Step 7: Commit** `feat(plans): Berlin network overlay` (code, config, tests, log, content).

---

### Task 6: Counter framework, Berlin, Paris and Vienna adapters, index, check

**Files:**
- Create: `src/velometer/counters/__init__.py`, `counters/model.py` (normalised records),
  `counters/days.py` (hourly → daily), `counters/index.py`, `counters/check.py`,
  `counters/adapters/{berlin,paris,vienna}.py`, `config/counters.yaml`
- Modify: `src/velometer/cli.py` (`counters` app: `fetch`, `load`, `--check`)
- Test: `tests/test_counters.py`, fixtures `tests/fixtures/counters/<city>/…` (small files cut from
  the real portal formats, ≤ 50 KB each, 2–3 sites, spanning a DST change and a year boundary)

**Interfaces:**
- Consumes: Task 1 repositories and dataclasses.
- Produces:
  - `config/counters.yaml` entries `{city, adapter, source, licence, urls: [...], timezone,
    grain: hourly|daily|monthly}`; the 14 cities without data listed under `none:` with
    `checked: [portal names]` (from the feasibility log).
  - `counters.model.HourCount(site_id, local_hour: datetime (naive local), count: int)`,
    `DayCount(site_id, day: date, count: int, complete: bool)`, `Site(site_id, name, lat, lon)`.
  - Adapter protocol: `fetch(entry, out_dir, fetch=_http_get) -> list[Path]`;
    `parse(paths: list[Path], entry) -> tuple[list[Site], list[HourCount] | list[DayCount]]`;
    raises `CounterFormatError(path, detail)` on a missing sheet/column.
  - `counters.days.to_days(hours: list[HourCount], tz: str) -> list[DayCount]`: de-duplicate on
    (site, local_hour) keeping the last seen; a day is complete when it holds every local hour that
    exists on that date in `tz` (23 on spring-forward, 24, or 25 on fall-back, computed with
    `zoneinfo`).
  - `counters.index.chain_index(days: list[DayCount], base_year: int, min_valid: float = 0.9,
    min_sites: int = 3) -> list[tuple[int, float | None, int]]` (year, index, qualifying sites):
    ```python
    for y in years after base: link sites = sites with ≥ min_valid share of complete days in y-1 and y
    if len(link sites) < min_sites: index[y] = None, and every later year stays None
        (the chain is broken; no re-basing)
    ratio = sum(counts of link sites in y over complete days) / same for y-1
    index[y] = index[y-1] * ratio;  index[base] = 100.0
    years before base are chained backwards the same way (ratio inverted)
    ```
    "share of complete days" uses the calendar days of that year (365/366).
  - `counters.check.check_counters(conn, cfg) -> list[str]` (spec §5.4).

- [ ] **Step 1: Research step (implementer):** download each portal once into `data/counters/`,
  confirm URL, licence, columns and history; cut the fixtures; note in
  `docs/review/m8-counters.md`.
- [ ] **Step 2: Failing tests:** `to_days` on a fixture spanning the last Sunday of March (23
  local hours = complete) and October (25 = complete; 24 there = incomplete); duplicate hours from
  two overlapping files counted once; loading the same fixture twice gives the same DB rows;
  `chain_index` with a site dropping out after year 2 (index continues on the remaining sites),
  with 2 qualifying sites (None), and base year = 100.0; each adapter parses its fixture to the
  expected sites and a known day total checked by hand from the fixture; a fixture with a renamed
  column raises `CounterFormatError` naming the column; `counters --check` flags a city with no
  index year.
- [ ] **Step 3: Run** → FAIL. **Step 4: Implement.** **Step 5: Run** → PASS; gate.
- [ ] **Step 6: Real load** for Berlin, Paris, Vienna; `counters --check` exit 0; record site
  counts, years, and index values in `docs/review/m8-counters.md`.
- [ ] **Step 7: Commit** `feat(counters): counter framework and Berlin, Paris, Vienna`.

---

### Task 7: Helsinki, Madrid, Oslo and Barcelona adapters, counter explainer

**Files:**
- Create: `counters/adapters/{helsinki,madrid,oslo,barcelona}.py`, fixtures,
  `content/counters.yaml`
- Modify: `config/counters.yaml`, `docs/review/m8-counters.md`
- Test: `tests/test_counters_more.py`

**Interfaces:**
- Consumes: Task 6 protocol, `to_days`, `chain_index`.
- Madrid: base year 2020 (spec §2.13). Oslo: Statens vegvesen traffic-data GraphQL API (public,
  no key; confirm), bicycle points inside the Oslo LAU boundary only (point-in-polygon against
  the stored boundary), labelled "state counters" in `source`. Barcelona: monthly average daily
  intensity → `CounterMonth` rows; index from the yearly mean of a site's monthly values for
  `day_type` working days, same chaining with "valid" = 12 months present; `series =
  avg_daily_intensity`.
- `content/counters.yaml` (Explainer shape, 150–300 words): what counters measure and do not,
  site selection bias, the COVID year, why counts and mapped km are shown side by side without a
  causal claim; quotes from portal or official methodology pages only; `counter.*` facts for any
  number.

- [ ] **Step 1: Research step:** as Task 6 Step 1 for the four portals.
- [ ] **Step 2: Failing tests:** each adapter on its fixture (known totals); Oslo filters a point
  outside the boundary; Barcelona index with a site missing a month in one year (not valid that
  year); Madrid base year 2020 = 100.
- [ ] **Step 3–5:** implement, PASS, gate. **Step 6:** real load, `counters --check` exit 0 for all
  seven, log values; `content --check` clean.
- [ ] **Step 7: Commit** `feat(counters): Helsinki, Madrid, Oslo, Barcelona and the explainer`.

---

### Task 8: Review stop (user)

- [ ] Controller renders `docs/review/m8-content-review.md` from: organisation profiles (with
  sources), `config/plans` (Berlin rows grouped by plan item showing every document's value and
  the revisions), `content/plans/berlin.yaml`, `docs/review/m8-overlay.md` (numbers and the sanity
  map), the counter index table per city and `content/counters.yaml`, plus a "judgement calls"
  list. Ask the user one `AskUserQuestion` batch (Profiles, Plans, Overlay, Counters), each with a
  recommendation. Record verdicts in `docs/superpowers/rulings-m8.md`. Changes requested → one
  fix round, then continue.

---

### Task 9: Charts and app pages: organisations and plans

**Files:**
- Modify: `src/velometer/app/main.py`, `templates/_nav.html`, `templates/city/figures.html`
  (organisation links), `static/app.css`
- Create: `templates/organisations.html`, `templates/plans.html`, `templates/plans_berlin.html`,
  `static/js/plan-chart.js`, `static/js/tests/plan-chart.test.mjs`
- Test: `tests/test_app_m8.py`

**Interfaces:**
- Consumes: `load_organisations`, `load_plans`, `current_and_revisions`, `ReportData.plan_overlay`,
  `render_explainer`-style rendering from `app/narrative.py` for profiles and
  `content/plans/berlin.yaml`.
- Routes: `GET /organisations`, `GET /plans`, `GET /plans/berlin`; `/plans/<other>` → 404.
  Berlin's city page links to `/plans/berlin`; every other city page links to its `/plans` row
  (`/plans#<city_id>`).
- `plan-chart.js` (pure functions tested in node): `planSeries(targets, reports, overlay,
  projects) -> {target: [...], reported: [{year, value, doc, current: bool}], projects: [...],
  mapped: [...]}` and `renderPlanChart(svg, series, opts)` using `chart-core.js` scales; markers
  per document (current filled, revisions hollow), target as steps, `target_kind: none` → no
  target line.
- infraVelo "completed projects" series: summed `streckenlaenge` of `status == Abgeschlossen`
  features by `bauende` year and network class, computed at request time from
  `data/plans/berlin/radverkehrsmassnahmen.geojson` if present (page notes its absence otherwise),
  cached by fingerprint.

- [ ] **Step 1: Failing tests:** each route 200 with CSP header; no-JS content (profile text,
  plan table, document table with types and links) present in HTML; a plan item with
  `target_kind: none` renders reported markers only; a city with no plan shows a note on `/plans`;
  `/plans/paris` 404; Figures rows link to the organisation anchor; node tests for `planSeries`
  (revision flag, missing target, empty overlay).
- [ ] **Step 2–4:** FAIL, implement, PASS; gate.
- [ ] **Step 5: Commit** `feat(app): organisations and plans pages`.

---

### Task 10: App: Counts tab and compare metric

**Files:**
- Modify: `src/velometer/app/main.py` (tab registry), `app/series.py` (counter index in
  `/data/series.json`), `app/compare.py` (`METRICS` gains `counter_index`), templates
  `city/_tabs.html` (or wherever tabs are listed), create `templates/city/counts.html`,
  `static/js/compare-model.js` and tests, `tests/compare_cases.json`
- Test: `tests/test_app_m8_counts.py`, node tests

**Interfaces:**
- Counts tab only for `ReportData.counter_cities()`; other cities: no tab, and their compare line
  shows "no open counter data" in the table view.
- Chart: counter index and A+B mapped-km index (both 2019 = 100; Madrid 2020 = 100 for both, the
  km index rebased to match), COVID marker on 2020, a site map where coordinates exist (R5), else a site list; attribution line
  with licence and link; `content/counters.yaml` rendered below.

- [ ] **Step 1: Failing tests:** tab present for a fixture counter city and absent otherwise
  (`/city/<other>/counts` 404); attribution text present; Barcelona label says "average daily
  intensity"; compare parses `m=counter_index` and the py/js shared cases agree; a year with
  `idx = None` is a gap, not 0 (node test).
- [ ] **Step 2–4:** FAIL, implement, PASS; gate.
- [ ] **Step 5: Commit** `feat(app): counts tab and counter index in compare`.

---

### Task 11: Render check, docs, final

- [ ] Render every new route and the Counts tab for all seven counter cities at 1280 and 390 px
  (headless Chrome screenshots as in M7); no horizontal scroll, no console error, CSP violations
  none. Fix findings.
- [ ] Docs: HANDOVER §9 M8 entry (with the DB writes stated), CLAUDE.md latest line, ADR 0008 M8
  licence note (dl-de-zero-2.0, ODbL, CC BY 4.0, NLOD, Licence Ouverte not used), methodology
  section on counters and the overlay (`report methodology --check` exit 0),
  `docs/superpowers/rulings-m8.md` (rulings, follow-ups).
- [ ] All checks exit 0: `timeseries`, `reconcile`, `trust`, `report methodology`, `content`,
  `counters`. Commit `docs(m8): handover, ADR 0008 note, rulings`.
