# velometer M4: report and app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private, local, read-only velometer app with city pages, interactive charts and CSV downloads, plus static charts, tier maps and a bilingual generated methodology. All of it reads one report classifier and one config identity, which this plan sets up first.

**Architecture:** Part 1 makes the data consistent:
- `activity.yaml` joins the run identity (schema v6);
- current runs for FUA boundaries merge their covering regions;
- `config/report.yaml` names the report classifier for every surface.

Part 2 builds presentation on one shared read layer, `velometer.report.data`:
- altair chart builders, shared by the app (vega-embed) and the docs (vl-convert PNG);
- the CSV;
- the methodology renderer (Jinja templates for EN and DE);
- matplotlib tier maps;
- a FastAPI + Jinja app that opens SQLite read-only.

**Tech Stack:** Python 3.13, uv, typer, Pydantic v2, SQLite, osmium-tool, FastAPI, uvicorn, Jinja2, altair + vl-convert-python, markdown, matplotlib, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-02-velometer-m4-design.md`. Also read `docs/superpowers/rulings-m3.md` and ADRs 0001–0008.

## Global Constraints

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest`. Network tests are `@pytest.mark.slow` and deselected by default.
- Tests never touch the network, the real `velometer.sqlite` or `data/`. They build fixture DBs in `tmp_path`, using the M3 fakes in `tests/test_run_history.py`.
- Lengths are computed only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006), and every chart, CSV and page footer says so, together with `Map data © OpenStreetMap contributors, ODbL 1.0`.
- The app binds only to loopback (`127.0.0.1`, `::1`, `localhost`) and makes no external request. Scripts come only from `/static/`.
- Classifier rules are data. Never change `config/classifier/v1.yaml` or `v2.yaml`.
- Mapper data is aggregate only: no uid or username in any table, CSV, page or doc.
- OSM credentials come only from `pass` and are injected inline for a single command. Never print, log or write them.
- Commits:
  - stage explicit paths;
  - end with one trailer, `Assisted-by: Claude:<model-id>`, carrying the implementer's own model id;
  - never commit `data/` or `velometer.sqlite`;
  - never push.
- Every new test must fail without its change. Red-proof by breaking the rule under test, and say how in the task report.

## Review Focus

1. **A v5 DB opened by the new code.** It migrates to v6 in one transaction, and the existing activity rows keep their history (`activity_sha256` = the M3 marker sha `de066a28e74c…`, the full sha of the `activity.yaml` they were computed with). Pinned in Task 1.
2. **A city with history runs but no current run, or the reverse, on any page or CSV.** It renders "no run", never a 500. Pinned in Task 4 (data layer) and Task 8 (app).
3. **`serve --host 0.0.0.0` or a LAN address.** It is refused with exit 2. Pinned in Task 8.
4. **A methodology edited by hand inside a generated section.** `report methodology --check` fails and names the file. Pinned in Task 6.
5. **Rank ties and missing published figures** (a city without a QECIO row). A tie gets the same rank; a missing value leaves the city out of that column. Neither raises. Pinned in Task 5.

---

### Task 1: Schema v6 — `activity.yaml` in run identity

**Files:**
- Modify:
  - `src/velometer/run.py`: `config_sha256`, `run_city`, `run_history`, `_write_activity`
  - `src/velometer/db.py`: `SCHEMA_VERSION`, `_SCHEMA` activity table, `_MIGRATIONS[5]`, `replace_activity`, `fetch_activity`
  - `src/velometer/cli.py`: `run_selector`
  - `src/velometer/timeseries.py`: drop the `activity=` marker parts; activity read by sha
  - `scripts/render_m2_results.py` and `scripts/render_m3_timeseries.py`: `config_sha256` callers
- Test: `tests/test_db.py`, `tests/test_run.py`, `tests/test_run_history.py`, `tests/test_timeseries.py`

**Interfaces:**
- Produces:
  - `config_sha256(classifier_path: Path, presets_path: Path, activity_path: Path) -> str`. It hashes the three files in that order, each as `name NUL bytes NUL`.
  - `Selector` gains `activity_sha256: str`, the sha256 hex of `activity.yaml` bytes. `run_selector` fills it.
  - `replace_activity(conn, city_id, boundary_kind, history_set_md5, activity_sha256, rows)`.
  - `fetch_activity(conn, city_id, boundary_kind, history_set_md5, activity_sha256) -> list[ActivityYear]`.
  - `velometer.run.file_sha256(path: Path) -> str`, the hex sha256 of the bytes.
  - Schema v6: `activity` gains `activity_sha256 TEXT NOT NULL`, and its primary key becomes `(city_id, boundary_kind, year, history_set_md5, activity_sha256)`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db.py
M3_ACTIVITY_SHA = "de066a28e74c"  # prefix recorded in docs/review/m3_timeseries.md's marker


def test_v5_to_v6_keeps_activity_rows_under_the_given_sha(tmp_path):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=3)          # helper: create_schema at v5 SQL + 3 rows
    with open_db(path) as conn:
        create_schema(conn, activity_sha256_for_v5="f" * 64)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
        shas = {r[0] for r in conn.execute("SELECT activity_sha256 FROM activity")}
        assert shas == {"f" * 64}
        assert conn.execute("SELECT count(*) FROM activity").fetchone()[0] == 3


def test_v6_migration_is_atomic(tmp_path, monkeypatch):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=3)
    monkeypatch.setattr(db, "_after_activity_copy", lambda conn: (_ for _ in ()).throw(RuntimeError))
    with open_db(path) as conn, pytest.raises(RuntimeError):
        create_schema(conn, activity_sha256_for_v5="f" * 64)
    with open_db(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        assert conn.execute("SELECT count(*) FROM activity").fetchone()[0] == 3


def test_activity_is_keyed_by_activity_sha(tmp_path):
    ...  # replace_activity(..., "a"*64, rows) and (..., "b"*64, other_rows); fetch by each sha
         # returns only its rows; replace for "a" leaves "b" untouched
```

```python
# tests/test_run.py
def test_config_sha_covers_activity_yaml(tmp_path):
    d = _copy_config(tmp_path)
    before = R.config_sha256(d / "classifier/v2.yaml", d / "presets.yaml", d / "activity.yaml")
    (d / "activity.yaml").write_text((d / "activity.yaml").read_text() + "\n# edit\n")
    after = R.config_sha256(d / "classifier/v2.yaml", d / "presets.yaml", d / "activity.yaml")
    assert before != after
```

```python
# tests/test_run_history.py
def test_editing_activity_yaml_reruns_every_year_and_old_runs_are_not_selected(tmp_path):
    ...  # run_history over range(2025, 2027) with a copied config; edit activity.yaml;
         # run again -> all outcomes "done" (not "skipped"); history_runs with the new
         # config sha returns the new ids only; fetch_activity(new sha) non-empty
```

```python
# tests/test_timeseries.py
def test_marker_has_no_activity_part_and_check_ignores_it(...):
    ...  # explained_against_marker(sets) contains no "activity="; a report whose marker
         # still carries activity=<old> passes --check when the sets match
```

`create_schema` takes a keyword `activity_sha256_for_v5: str | None = None`. When it is None and a v5 DB has activity rows, it raises `SchemaError`. That error tells the user to run `velometer migrate --activity-sha <sha>`, a new CLI command (added in this task) that passes the value. On a fresh DB, or on a v5 DB with an empty activity table, the argument is not needed.

- [ ] **Step 2: Run and confirm failure**

Run: `uv run pytest -q tests/test_db.py tests/test_run.py tests/test_run_history.py tests/test_timeseries.py`
Expected: FAIL (`config_sha256` takes 2 args; no v6).

- [ ] **Step 3: Implement**

```python
# run.py
def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_sha256(classifier_path: Path, presets_path: Path, activity_path: Path) -> str:
    """sha256 over the classifier, presets and activity YAML, each as `<name> NUL <bytes> NUL`."""
    digest = hashlib.sha256()
    for path in (classifier_path, presets_path, activity_path):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()
```

`_migrate_5_to_6(conn, activity_sha256)` runs inside the `create_schema` transaction:
1. Create `activity_v6` with the new column and primary key.
2. Copy the rows with the given sha.
3. Call the `_after_activity_copy(conn)` hook, which is a no-op normally and gives the atomicity test an injection point.
4. Drop `activity` and rename `activity_v6` to `activity`.

Update `_SCHEMA` so a fresh DB matches exactly, and test that `sqlite_master` of a migrated DB equals that of a fresh one, as the M3 migration test does.

Every `config_sha256` caller passes `config_dir / "activity.yaml"`. `run_history` and `_write_activity` pass `file_sha256(config_dir / "activity.yaml")` to `replace_activity` and `fetch_activity`. In `timeseries`:
- `series` and `build_city` read activity with `selector.activity_sha256`;
- remove `activity_sha`, `explained_activity` and `unexplained_activity`, and the `activity` argument of `explained_against_marker`;
- `_marker_items` ignores an `activity=` item, so an old marker still parses.

The CLI `timeseries --check` no longer checks activity.

- [ ] **Step 4: Run the tests and the gate.** Every existing test must still pass, with callers updated.
- [ ] **Step 5: Commit**

```bash
git add src/velometer/run.py src/velometer/db.py src/velometer/cli.py src/velometer/timeseries.py scripts/render_m2_results.py scripts/render_m3_timeseries.py tests/test_db.py tests/test_run.py tests/test_run_history.py tests/test_timeseries.py
git commit -m "feat: schema v6 puts activity.yaml in run identity and activity keys"
```

---

### Task 2: FUA current runs from their covering regions

**Files:**
- Modify:
  - `src/velometer/run.py`: `RunDeps`, `run_city`
  - `src/velometer/osmium.py`: add `merge(srcs, dst)`
- Test: `tests/test_run.py`, `tests/test_osmium.py`

**Interfaces:**
- Consumes (from `velometer.sources.geofabrik`):
  - `regions_for(polygon_wgs84, index, *, buffer_m=0, tolerance_frac=0.001, tolerance_km2=1.0) -> RegionSelection(regions: list[str], uncovered_km2: float)`. It raises `ValueError` when the leaf regions cannot cover the polygon.
  - `load_index(path) -> dict[str, dict]` and `fetch_region(region, data_dir, client=None, *, retries, backoff_s) -> RegionFile(region, path, url, md5, osm_timestamp)`.
  - `history_set_md5(files: list[HistoryFile])`, which hashes the sorted `region:md5` lines.
  - `upsert_history_set(conn, set_md5, regions: list[dict], *, index_path, index_sha256, uncovered_km2)` from `db.py`.
- Produces:
  - `geofabrik.set_md5(pairs: list[tuple[str, str]]) -> str`, the md5 over the sorted `region:md5` lines. `history_set_md5` is rewritten to call it, so its values are unchanged. A test pins one known value from the existing test suite.
  - `osmium.merge(srcs: list[Path], dst: Path) -> Path`. It runs `osmium merge` without `--with-history`, writing atomically through `_atomic` with a `.part.osm.pbf` file.
  - `RunDeps` gains `load_index: Callable[[Path], dict[str, dict]] = geofabrik.load_index`, `regions_for = geofabrik.regions_for` and `merge = osmium.merge`.
  - The `history_sets` table also records the region sets of current runs. The md5s differ from history sets because the files differ, so the two never collide.

Behaviour of `run_city`:
- If the city's own region covers the boundary (the current R18 guard condition), nothing changes.
- Otherwise:
  1. Call `deps.regions_for(boundary in WGS84, index)`, where `index` is the Geofabrik index the history runs use (same path and loader as `run_history`). A `ValueError` from it is re-raised as the existing R18 `ValueError`, carrying the original message, before any run row is written.
  2. Each region in the selection is fetched with `deps.fetch_region`.
  3. With one region, its file is used directly. With more, `deps.merge` writes `data/raw/merged/<city>_<kind>_<set_md5[:8]>.osm.pbf`, which is reused if present.
  4. `region_md5 = set_md5([(f.region, f.md5) for f in files])`.
  5. `osm_timestamp` is the minimum of the region timestamps.
  6. `upsert_history_set(...)` records the regions (`region`, `md5`, `md5_source: "published"`, `fetched_at`), the index path and sha256, and `uncovered_km2`.
  7. Snapshot and measure continue as today.

- [ ] **Step 1: Write failing tests**

```python
def test_current_fua_run_merges_covering_regions(tmp_path):
    deps = _fua_deps(tmp_path, regions={"r1": "a" * 32, "r2": "b" * 32})  # fake fetch_region,
    # load_index with two leaves covering the boundary, merge that copies the first file
    out = R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG, boundary_kind="fua", deps=deps)
    assert out.status == "done"
    row = fetch_run(conn, out.run_id)
    assert row["source"] == "current" and row["region_md5"] == expected_set_md5(["a"*32, "b"*32])
    hs = fetch_history_set(conn, row["region_md5"])
    assert [r["region"] for r in json.loads(hs["regions_json"])] == ["r1", "r2"]
    assert deps.merge_calls == 1


def test_current_fua_single_covering_region_needs_no_merge(tmp_path): ...
def test_current_fua_timestamp_is_the_oldest_region(tmp_path): ...
def test_current_run_without_any_covering_set_still_fails_before_a_run_row(tmp_path): ...
def test_merged_file_is_reused(tmp_path): ...          # second run: merge not called
def test_osmium_merge_writes_atomically(tmp_path): ... # tests/test_osmium.py, real osmium on fixtures
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** as described. The LAU path must stay byte-identical in behaviour; the existing `tests/test_run.py` must pass unchanged.
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add src/velometer/run.py src/velometer/osmium.py tests/test_run.py tests/test_osmium.py
git commit -m "feat: current runs for boundaries beyond the city extract merge their covering regions"
```

---

### Task 3: `config/report.yaml`, the report classifier everywhere

**Files:**
- Create: `config/report.yaml`
- Modify:
  - `src/velometer/config.py`: add `ReportConfig` and `load_report`; remove `report_classifier` from `HistoryConfig`
  - `config/history.yaml`
  - `src/velometer/cli.py`: `run`, `reconcile`, `timeseries` and `classify`-free defaults
  - `scripts/render_m3_timeseries.py`
  - `docs/review/m2_results.md`: add a one-line note
- Test: `tests/test_config.py`, `tests/test_cli.py`, `tests/test_reconcile.py`, `tests/test_timeseries.py`

`config/report.yaml`:

```yaml
# Report surfaces (reconcile, timeseries, charts, methodology, app) and the default run
# classifier use this classifier with its default parameters (M4 spec section 3.3).
report_classifier: v2
rankings:
  - {id: ours_headline, label: "Ours: headline", kind: preset, preset: ours_headline}
  - {id: ours_ecf_qecio, label: "Ours: QECIO method", kind: preset, preset: ecf_qecio}
  - {id: ours_clean_cities, label: "Ours: Clean Cities method", kind: preset, preset: clean_cities_2025}
  - id: published_clean_cities
    label: "Clean Cities 2025 (published)"
    kind: external
    source: clean_cities_2025
    metric: protected_share_pct
    scope: whole_network
    note: "city network as published; Vienna whole-network value"
  - id: published_qecio
    label: "QECIO v2.10 (published)"
    kind: external_ratio
    source: qecio_v2_10
    numerator: [cycle_tracks_km, cycle_lanes_km, shared_pedestrians_km]
    denominator: main_roads_km
    note: "NUTS3 region (Berlin DE300, Paris FR101, Vienna AT130, Copenhagen DK011, Wroclaw PL514)"
```

**Interfaces:**
- Produces:
  - `ReportConfig(report_classifier: str, rankings: list[RankingSource])`, with `extra="forbid"`.
  - `RankingSource` is a discriminated union on `kind` (`preset` | `external` | `external_ratio`).
  - `load_report(path) -> ReportConfig`.
  - `velometer.cli.report_selector(config_dir: Path) -> Selector`, equal to `run_selector(config_dir, load_report(config_dir / "report.yaml").report_classifier)`.
- CLI defaults: `run --classifier`, `reconcile --classifier` and `timeseries --classifier` default to None, which means the report classifier. Each keeps the explicit override.

- [ ] **Step 1: Write failing tests**
  - `load_report` accepts the shipped file. It rejects an unknown key, an unknown `kind` and a preset id not in `presets.yaml`.
  - For each of `run`, `reconcile` and `timeseries`: with a copied config dir whose `report.yaml` names `v1`, the command reports or runs v1. With `v2`, it reports or runs v2. Assert this on the runs selected or created: this is the red-proof for each default.
  - `history.yaml` with a `report_classifier` key is rejected with a message pointing to `report.yaml`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** Update `tests/test_timeseries.py::config_dir` to write `report.yaml`, not `history.yaml`. Then add one line under the title of `docs/review/m2_results.md`: `> M2 record on classifier v1. Current figures: the app (velometer serve) and docs/methodology.md.`
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add config/report.yaml config/history.yaml src/velometer/config.py src/velometer/cli.py scripts/render_m3_timeseries.py docs/review/m2_results.md tests/test_config.py tests/test_cli.py tests/test_reconcile.py tests/test_timeseries.py
git commit -m "feat: config/report.yaml names the report classifier for every report surface"
```

---

### Task 4: Shared report read layer and CSV export

**Files:**
- Create: `src/velometer/report/__init__.py`, `src/velometer/report/data.py`, `src/velometer/report/csvexport.py`
- Modify: `src/velometer/cli.py` (add `report csv [--city X] [--out PATH]`)
- Test: `tests/test_report_data.py`, `tests/test_report_csv.py`

**Interfaces:**
- Consumes: `report_selector` (Task 3); `timeseries.build_city`, `city_flags`, `CitySeries`, `YearPoint`; `select_metric`; `fetch_run`, `fetch_run_results`, `fetch_external_figures`, `fetch_cities`; `load_report`, `load_history` and `load_activity`.
- Produces, in `velometer.report.data` (Pydantic models, `frozen=True`):

```python
class PresetValue(BaseModel):
    preset: str
    value: float | None          # percent, on the preset's reported basis
    per_100k: float | None

class CurrentPoint(BaseModel):
    city_id: str
    city_name: str
    kind: str                    # "lau" | "fua"
    run_id: int
    osm_timestamp: str
    classifier_version: str
    config_sha256: str
    ab_km: float
    tiers_km: dict[str, float]   # "A".."E", per side
    presets: list[PresetValue]
    population_value: int | None
    population_year: int | None

class RankEntry(BaseModel):
    source_id: str
    source_label: str
    city_id: str
    value: float
    rank: int                    # 1 = highest; ties share the lower rank number

class ReportData:               # plain class holding an open read-only connection
    def __init__(self, conn, config_dir: Path): ...
    def cities(self) -> list[City]
    def current(self, city_id: str, kind: str) -> CurrentPoint | None
    def series(self, city_id: str, kind: str) -> CitySeries | None
    def flags(self, city_id: str, kind: str) -> list[Flag]
    def ranks(self) -> list[RankEntry]
    def reconcile(self, city_id: str) -> CityReport | None   # reconcile_city with report selector
    def csv_rows(self, city_id: str | None = None) -> list[dict[str, str]]
```

- `velometer.report.data.open_readonly(db_path: Path) -> sqlite3.Connection` opens `file:<path>?mode=ro` with `uri=True` and `row_factory = sqlite3.Row`. It raises `FileNotFoundError` when the file is missing.
- `velometer.report.csvexport.to_csv(rows: list[dict[str, str]], commit: str, generated_at: str) -> str`. The first two lines are `# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km, not built km` and `# velometer <commit> generated <generated_at>`, followed by a header row and the data rows.
- CSV columns, in this order: `city_id, boundary_kind, label, run_id, osm_timestamp, classifier_version, config_sha256, tier_A_km, tier_B_km, tier_C_km, tier_D_km, tier_E_km, ab_km, ours_headline, ecf_qecio, clean_cities_2025, population_value, population_year, flags`. `flags` is the `;`-joined rule names, and an empty cell means None. Numbers are written with 3 decimals.

Ranking rules:
- **Presets:** the city's current LAU run, `select_metric(...).value`.
- **External:** the `ExternalFigure` with matching source, metric and `network_scope == scope`.
- **External ratio:** `sum(numerator metrics) / denominator × 100` from the city's figures of that source. A missing component drops the city from that source.
- **Ranks:** sort descending. Equal values (`round(value, 6)`) share the rank number of the first, and the next distinct value takes its 1-based position.

- [ ] **Step 1: Write failing tests** on a fixture DB built with the M3 fakes (history and current, 2 cities, external figures inserted with `replace_external_figures`):

```python
def test_current_point_matches_cli_headline(fixture_db): ...
def test_city_without_current_run_gives_none_not_error(fixture_db): ...
def test_ranks_highest_first_and_ties_share_rank():
    assert _rank([("a", 50.0), ("b", 50.0), ("c", 40.0)]) == {"a": 1, "b": 1, "c": 3}
def test_external_ratio_needs_every_component(fixture_db): ...   # drop cycle_lanes_km -> city absent
def test_csv_header_comments_columns_and_no_user_columns(fixture_db):
    text = to_csv(ReportData(conn, cfg).csv_rows(), "abc123", "2026-10-02T00:00:00Z")
    lines = text.splitlines()
    assert lines[0].startswith("# Map data © OpenStreetMap contributors, ODbL 1.0")
    assert lines[1] == "# velometer abc123 generated 2026-10-02T00:00:00Z"
    header = lines[2].split(",")
    assert header == CSV_COLUMNS and not {"uid", "user", "username"} & set(header)
def test_csv_row_values_match_db(fixture_db): ...
def test_open_readonly_refuses_writes(tmp_path): ...  # INSERT raises sqlite3.OperationalError
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** `ReportData` reuses `timeseries.build_city` with `load_history(...).year_range()` and the report selector, and `reconcile.reconcile_city` with the report selector's version, parameters, config sha and presets. Do not re-implement either.
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add src/velometer/report/__init__.py src/velometer/report/data.py src/velometer/report/csvexport.py src/velometer/cli.py tests/test_report_data.py tests/test_report_csv.py
git commit -m "feat: shared read-only report data layer and CSV export"
```

---

### Task 5: Vega-Lite charts (app + docs PNG)

**Files:**
- Create: `src/velometer/report/charts.py`
- Modify:
  - `pyproject.toml`: runtime deps `altair`, `vl-convert-python`; `matplotlib` moves from dev to runtime
  - `src/velometer/cli.py`: `report charts [--out docs/review]`
- Test: `tests/test_charts.py`

**Interfaces:**
- Consumes: `ReportData` (Task 4).
- Produces:
  - `headline_over_time(data: ReportData) -> dict`: one line per city on LAU, and dashed FUA lines for cities with an FUA series. x is the labels `2018`…`2026`, `now`. A flagged point has `flagged: true` in its data row and is drawn as a ring layer. Tooltips show `city, kind, label, headline, ab_km, flags`.
  - `tier_composition(data: ReportData, city_id: str, kind: str = "lau") -> dict`: stacked bars of A–E per-side km per label.
  - `rankings_flip(data: ReportData) -> dict`: a slope chart, with x = the ranking source label in `report.yaml` order, y = rank (1 on top), and one colour per city.
  - `ATTRIBUTION = "Map data © OpenStreetMap contributors, ODbL 1.0 · OSM mapped km, not built km (ADR 0006)"` sits in every chart's `title.subtitle` or in a text mark.
  - `write_pngs(data: ReportData, out_dir: Path) -> list[Path]`: writes `m4_headline.png`, `m4_tiers.png` (small multiples of every city's LAU composition) and `m4_rankings.png`, each with its `.vl.json`, via `vl_convert.vegalite_to_png(spec, scale=2)`.
- The tier colours are the M3 chart's: `["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]` for A–E.

- [ ] **Step 1: Write failing tests** on the Task 4 fixture DB:

```python
def test_headline_spec_has_one_row_per_city_kind_label(fixture_data):
    spec = headline_over_time(fixture_data)
    rows = _data_rows(spec)                       # helper: datasets of the top-level spec
    assert {(r["city"], r["kind"], r["label"]) for r in rows} == EXPECTED_KEYS
    assert any(r["flagged"] for r in rows)        # fixture has one flag

def test_rankings_spec_orders_sources_as_report_yaml(fixture_data): ...
def test_rankings_tie_shares_rank_and_missing_city_is_absent(fixture_data): ...
def test_every_spec_carries_the_attribution(fixture_data): ...
def test_write_pngs_writes_nonempty_pngs_and_specs(fixture_data, tmp_path):
    paths = write_pngs(fixture_data, tmp_path)
    assert {p.name for p in paths} >= {"m4_headline.png", "m4_tiers.png", "m4_rankings.png"}
    assert all(p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" for p in paths if p.suffix == ".png")
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** with `alt.Chart(...).to_dict()`. Embed the data inline (`alt.data_transformers.disable_max_rows()`), so no external URL appears in a spec. A test asserts that no spec contains `"url"`.
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/velometer/report/charts.py src/velometer/cli.py tests/test_charts.py
git commit -m "feat: Vega-Lite charts for headline, tier composition and rankings flip"
```

---

### Task 6: Bilingual methodology (EN + DE) with `--check`

**Files:**
- Create:
  - `src/velometer/report/methodology.py`
  - `src/velometer/report/templates/methodology.en.md.j2`
  - `src/velometer/report/templates/methodology.de.md.j2`
  - `config/limitations.yaml`
- Modify:
  - `src/velometer/cli.py`: `report methodology [--check] [--docs docs]`
  - `pyproject.toml`: `jinja2`
- Test: `tests/test_methodology.py`

**Interfaces:**
- Consumes: `ReportData`; `load_classifier`, `load_presets`, `load_activity`, `load_history` and `load_report`.
- Produces:
  - `methodology_facts(data: ReportData) -> MethodologyFacts`, a Pydantic model containing:
    - `classifier_version`, `classifier_parameters`, `rules: list[RuleRow(id, tier, subtype, applies_to, match: str)]`;
    - `value_separators`;
    - `presets: list[PresetRow(id, numerator, denominator, basis)]`;
    - `cities: list[CityFacts(id, name, kinds: list[KindFacts(kind, current_osm_timestamp, history_set, history_osm_timestamps: list[str], population_value, population_year)])]`;
    - `snapshot_dates: list[str]`;
    - `flag_thresholds: dict[str, float]`;
    - `limitations: list[Limitation(id, en, de)]`.
  - `render(facts, lang: Literal["en","de"]) -> str`.
  - `write(docs_dir, facts) -> list[Path]` writes `methodology.md` (en) and `methodology.de.md` (de).
  - `check(docs_dir, facts) -> list[str]` returns problems: a file missing or differing from the render, or a limitation without `en` or `de`.
- `config/limitations.yaml` holds a list of `{id, en, de}` covering exactly the spec §4.4 list:
  - `mapped_km`
  - `population_2024`
  - `fua_no_per_100k`
  - `no_width_surface`
  - `classifier_gaps_excluded`
  - `published_scope`
  - `dirty_provenance_m3`
  - `history_vs_current_date`

  The implementer writes each sentence in both languages, factual and short, citing the ADR or ruling in brackets.
- The templates hold the hand-written prose and the generated sections. Every generated section is wrapped in `<!-- generated:<name> -->` … `<!-- /generated:<name> -->`, so a reader sees which parts are generated.
- Both files open with a line saying that they are generated, naming the command, and linking the other language.

- [ ] **Step 1: Write failing tests**

```python
def test_both_languages_list_classifier_version_and_every_city_timestamp(facts): ...
def test_check_passes_after_write_and_fails_after_hand_edit(facts, tmp_path):
    write(tmp_path, facts)
    assert check(tmp_path, facts) == []
    p = tmp_path / "methodology.de.md"
    p.write_text(p.read_text().replace("v2", "v9", 1))
    assert any("methodology.de.md" in m for m in check(tmp_path, facts))
def test_limitation_missing_a_language_fails_load(tmp_path): ...
def test_rules_table_lists_every_rule_of_the_report_classifier(facts): ...
def test_cli_report_methodology_check_exit_codes(...): ...   # 0 clean, 1 stale
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** The EN and DE prose covers:
  - what is measured (way sides, tiers A–E);
  - the headline and the three presets;
  - boundaries (LAU and FUA) and population;
  - history snapshots and flags;
  - comparison with published figures;
  - provenance;
  - licences (ODbL).

  Write `docs/methodology.md` and `docs/methodology.de.md` from the fixture-free real config only in Task 9. In this task, commit the templates and tests only.
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add src/velometer/report/methodology.py src/velometer/report/templates config/limitations.yaml src/velometer/cli.py pyproject.toml uv.lock tests/test_methodology.py
git commit -m "feat: generated bilingual methodology with a staleness check"
```

---

### Task 7: Tier maps per city

**Files:**
- Create: `src/velometer/report/maps.py`
- Modify: `src/velometer/cli.py` (`report maps [--city X] [--kind lau] [--data data]`)
- Test: `tests/test_maps.py`

**Interfaces:**
- Consumes: `ReportData.current`; `fetch_run`, `fetch_boundary`; `pipeline.extract.snapshot` naming; `read_ways`; `classify_ways`; the report classifier config.
- Produces:
  - `snapshot_path(run_row: dict, data_dir: Path) -> Path`. It is the current snapshot `data/snapshots/{city}_{kind}_{YYYYMMDD}_{region_md5[:8]}_{boundary_sha256[:8]}.osm.pbf`, the same name `pipeline.extract.snapshot` writes. Use a shared `snapshot_name(...)` helper extracted from `extract.snapshot` so the name has one definition.
  - `build_map(data: ReportData, city_id: str, kind: str, data_dir: Path, maps_dir: Path) -> Path | None`. It writes `maps_dir/<city>_<kind>.png` plus `maps_dir/<city>_<kind>.run` holding the run id. It skips the rebuild when the `.run` file matches the current run id. It returns None when there is no current run or no snapshot file.
- Drawing:
  - matplotlib Agg;
  - side geometries in the city EPSG;
  - tiers A–E in the M3 colours;
  - `excluded` and untiered sides omitted;
  - the boundary outline in grey;
  - an equal aspect ratio and no axes;
  - a legend;
  - a footer with the ODbL line plus "OSM <timestamp>, classifier <version>";
  - 150 dpi.

- [ ] **Step 1: Write failing tests** with a tiny snapshot built from `tests/fixtures/measure/mini_city.osm`. Convert it to `.osm.pbf` with `osmium cat` in the test (it needs osmium; skip if it is missing, as `test_osmium.py` does). The fixture DB has a run whose `snapshot_path` points at it.

```python
def test_build_map_writes_png_and_run_marker(...): ...
def test_build_map_skips_when_run_unchanged(...): ...   # monkeypatch plt.savefig to count
def test_build_map_rebuilds_when_run_changes(...): ...
def test_build_map_returns_none_without_snapshot(...): ...
def test_snapshot_name_is_shared_with_extract():
    assert extract_snapshot_name_args_produce(...) == maps.snapshot_path(row, data).name
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add src/velometer/report/maps.py src/velometer/pipeline/extract.py src/velometer/cli.py tests/test_maps.py
git commit -m "feat: static tier maps per city from the current snapshot"
```

---

### Task 8: FastAPI app and `velometer serve`

**Files:**
- Create:
  - `src/velometer/app/__init__.py`, `src/velometer/app/main.py`
  - `src/velometer/app/templates/base.html`, `index.html`, `city.html`, `methodology.html`
  - `src/velometer/app/static/app.css`
  - `src/velometer/app/static/vendor/vega.min.js`, `vega-lite.min.js`, `vega-embed.min.js` and their `LICENSE` files
- Modify:
  - `src/velometer/cli.py`: `serve`
  - `src/velometer/timeseries.py`: add `explanation(path: Path, key: str) -> str | None`
  - `pyproject.toml`: `fastapi`, `uvicorn`, `markdown`, plus `httpx` already present for TestClient
  - `.gitattributes`: mark `src/velometer/app/static/vendor/*.js` as `-diff linguist-vendored`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `ReportData`, `open_readonly`, `to_csv`, the chart builders, `timeseries.explanation`, `maps_dir`, and `docs/methodology*.md`.
- Produces:
  - `create_app(db_path: Path, config_dir: Path, maps_dir: Path, docs_dir: Path) -> FastAPI`. It opens a read-only connection per request with a dependency that closes it.
  - Routes (spec §4.6):

    | Route | Response |
    |---|---|
    | `GET /` | index |
    | `GET /city/{city_id}` | city page, or 404 |
    | `GET /methodology` and `GET /methodology/de` | methodology rendered with `markdown` (extensions `tables`, `fenced_code`) |
    | `GET /maps/{name}.png` | 404 unless `name` matches `^[a-z0-9_]+_(lau\|fua)$` and the file exists, which blocks path traversal |
    | `GET /data/all.csv` and `GET /data/{city_id}.csv` | `text/csv; charset=utf-8` with `Content-Disposition: attachment` |
    | `/static` | `StaticFiles` |

  - `velometer serve --host 127.0.0.1 --port 8000 --db velometer.sqlite --config-dir config --maps data/maps --docs docs`:
    - exits 2 unless the host is `127.0.0.1`, `::1` or `localhost`;
    - exits 1 with a message when the DB is missing;
    - otherwise runs `uvicorn.run(create_app(...), host, port)`.
- The vendored JS versions are exactly `alt.VEGA_VERSION`, `alt.VEGALITE_VERSION` and `alt.VEGAEMBED_VERSION` of the installed altair. Download each once from `https://cdn.jsdelivr.net/npm/<pkg>@<version>/build/<pkg>.min.js` together with its `LICENSE`, and record the versions in `src/velometer/app/static/vendor/VERSIONS`. A test asserts that `VERSIONS` matches altair's constants.
- Charts are embedded as `<div id="c1"></div><script>vegaEmbed('#c1', {{ spec | tojson }}, {actions: false})</script>`.
- The footer on every page is the ODbL line plus "OSM mapped km, not built km (ADR 0006)", a link to `/methodology`, and the classifier version with the config sha prefix.

- [ ] **Step 1: Write failing tests** with `fastapi.testclient.TestClient` on the Task 4 fixture DB, a `docs_dir` holding a minimal `methodology.md` and `methodology.de.md`, and a `m3_timeseries.md` with one explanation:

```python
@pytest.mark.parametrize("path", ["/", "/city/berlin", "/methodology", "/methodology/de",
                                  "/data/all.csv", "/data/berlin.csv"])
def test_routes_render(client, path):
    assert client.get(path).status_code == 200

def test_unknown_city_is_404(client): assert client.get("/city/nowhere").status_code == 404
def test_city_without_current_run_renders_no_run(client): ...      # "no run" in text, 200
def test_flag_explanation_text_on_city_page(client): ...
def test_map_route_blocks_traversal_and_missing(client):
    assert client.get("/maps/..%2Fsecret.png").status_code == 404
    assert client.get("/maps/berlin_lau.png").status_code in (200, 404)
def test_pages_reference_only_local_scripts(client):
    html = client.get("/").text
    assert re.findall(r'<script[^>]+src="([^"]+)"', html)
    assert all(s.startswith("/static/") for s in re.findall(r'<script[^>]+src="([^"]+)"', html))
    assert "http://" not in html.split("<footer")[0] and "https://" not in html.split("<footer")[0]
def test_app_never_writes_the_db(client, fixture_db_path): ...    # file mtime + md5 unchanged after all routes
def test_serve_refuses_non_loopback_host(): ...                   # CliRunner, exit 2, no uvicorn call
def test_serve_missing_db_exits_1(tmp_path): ...
def test_vendor_versions_match_altair(): ...
def test_csv_route_is_attachment_with_attribution(client): ...
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** The pages are plain, readable and responsive, with one stylesheet and no framework. Use the M3 chart palette and system fonts. The city page sections, in order:
  1. headline and presets;
  2. tier composition;
  3. LAU vs FUA;
  4. flagged years with explanations;
  5. comparison with published figures (reconcile rows: comparison, ours, theirs, gap %, flagged);
  6. tier map;
  7. provenance.

  A section without data shows a one-line "no run …" note.
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add src/velometer/app src/velometer/cli.py src/velometer/timeseries.py pyproject.toml uv.lock .gitattributes tests/test_app.py
git commit -m "feat: private read-only web app (velometer serve) with city pages and CSV"
```

---

### Task 9: Execute M4 on real data (most capable model, controller watching)

**Files:**
- Modify: `docs/reconciliation.md`, `docs/review/m3_timeseries.md`, `docs/review/m3_timeseries.png`, `docs/superpowers/rulings-m4.md` (create)
- Create: `docs/methodology.md`, `docs/methodology.de.md`, `docs/review/m4_headline.png`, `docs/review/m4_tiers.png`, `docs/review/m4_rankings.png` and their `.vl.json`

- [ ] **Step 1: Back up and migrate.**
  1. `cp velometer.sqlite data/velometer-pre-v6.sqlite`.
  2. `uv run velometer migrate --activity-sha <full sha256 of config/activity.yaml at commit 4e6a6a0>`. Compute it from `git show 4e6a6a0:config/activity.yaml | sha256sum`; its prefix must be `de066a28e74c`. Stop if it is not.
- [ ] **Step 2: Rerun on the report classifier.** Each command is timed. Credentials are injected inline only if a download needs them; if gpg is locked, stop and report.

```bash
uv run velometer run --cities all
uv run velometer run --cities berlin,paris --boundary fua
uv run velometer run --cities all --years 2018-2026
uv run velometer run --cities berlin,paris --years 2018-2026 --boundary fua
```

  Expected: 70 runs done, none failed. The FUA current runs record their region sets: Berlin `[brandenburg]`; Paris the 6 regions.
- [ ] **Step 3: Regenerate and re-explain.**
  1. Run `timeseries --write`. Re-check the explanations: the FUA series now have a current point, so remove stale headings and write explanations for new flags in the house style.
  2. Run `reconcile --write`. Re-check every explanation against the v2 numbers, and correct any text that cites v1-only values.
  3. Re-render the M3 chart.
- [ ] **Step 4: Report artefacts.** Run `report charts`, `report maps` (all cities, LAU and FUA where runs exist) and `report methodology`. View every PNG with Read and fix any rendering problems in the code, as tested commits.
- [ ] **Step 5: Browser check.**
  1. Start `uv run velometer serve` in the background.
  2. Open `/`, every `/city/<id>`, `/methodology`, `/methodology/de` and both CSV kinds in Chrome via the claude-in-chrome tools.
  3. Screenshot each page.
  4. Compare the headline numbers with `velometer reconcile` output.
  5. Confirm with the network log that every request goes to `127.0.0.1`.
  6. Stop the server.
- [ ] **Step 6: Checks and gate.** `reconcile --check`, `timeseries --check` and `report methodology --check` each exit 0, and the gate is green.
- [ ] **Step 7: Rulings and commit.** Write `docs/superpowers/rulings-m4.md` in the M3 format. Then commit, with no data files:

```bash
git add docs/methodology.md docs/methodology.de.md docs/reconciliation.md docs/review/m3_timeseries.md docs/review/m3_timeseries.png docs/review/m4_*.png docs/review/m4_*.vl.json docs/superpowers/rulings-m4.md
git commit -m "docs: M4 methodology (en, de), charts and reports on classifier v2 with run identity v6"
```

---

## Self-review notes (writer)

**Spec coverage:**

| Spec | Task |
|---|---|
| §3.1 identity v6 | 1 (and 9 for the real migration) |
| §3.2 FUA current | 2 |
| §3.3 report classifier | 3 (and 9 for reconcile re-explained) |
| §3.4 rerun | 9 |
| §4.1 layout | 4–8 |
| §4.2 charts | 5 |
| §4.3 CSV | 4 (route in 8) |
| §4.4 methodology | 6 (written in 9) |
| §4.5 maps | 7 |
| §4.6 app | 8 |
| §4.7 dependencies | 5, 6, 8 |
| §5 testing | each task |
| §6 execution | 9 |

**Type consistency:**
- `Selector` gains `activity_sha256` in Task 1, consumed in Tasks 4 and 8.
- `report_selector` comes from Task 3 and is used in Tasks 4–8.
- `ReportData` comes from Task 4 and is used in Tasks 5–8.
- `config_sha256` has 3 arguments everywhere from Task 1 on.
- `replace_activity` and `fetch_activity` take `activity_sha256` from Task 1 on.

**Known plan risk:** the Task 1 migration needs the activity sha the existing rows were computed with. Its value comes from git history (commit 4e6a6a0) and is cross-checked against the M3 marker prefix `de066a28e74c`.
