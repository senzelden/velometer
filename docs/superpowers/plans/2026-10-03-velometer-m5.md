# velometer M5: scale to 21 cities — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 16 cities to the 5 pilots on the same footing: report classifier, LAU and FUA, 2018–2026 history, comparison layers, every gap and flag explained. No city enters the report before its country passes a trust gate.

**Architecture:**
- **Part 1 (Tasks 1–11, offline, TDD)** prepares the code:
  - hardened migrations and a peak-memory record per run;
  - city facts moved from code into `cities.yaml`: OSM admin boundary, Urban Audit population, BikeNetKit id, NUTS3 match;
  - scoped QECIO ratios and gap-aware rankings;
  - a trust layer: `config/trust.yaml`, diagnostics, golden samples, `trust --check`, and filtering of every report surface;
  - charts and an app cache that work at 21 cities;
  - methodology additions.
- **Task 12** is conditional: streaming classification, built only if the memory gate trips.
- **Part 2 (Tasks 13–18)** is execution on real data, in the spec's order: onboard → your sign-off → classifier → memory gate → full run → explanations → report.

**Tech Stack:** Python 3.13, uv, typer, Pydantic v2, SQLite, osmium-tool, pyosmium, shapely, FastAPI, Jinja2, altair + vl-convert-python, matplotlib, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-03-velometer-m5-design.md`. Also read `docs/superpowers/rulings-m4.md`, the M4 spec and ADRs 0001–0008. HANDOVER §9 (M5) and §10 (pitfalls).

## Global Constraints

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest`. Network tests are `@pytest.mark.slow` and deselected by default.
- Tests never touch the network, the real `velometer.sqlite` or `data/`. They build fixture DBs in `tmp_path` with the M3 fakes (`tests/test_run_history.py`) and `tests/report_fixture.py`.
- Lengths are computed only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006). Every chart, CSV and page footer carries `Map data © OpenStreetMap contributors, ODbL 1.0`.
- Classifier rules are data. Never edit `config/classifier/v1.yaml` or `v2.yaml`; a rule change is `v3.yaml` (ADR 0005), and only in Task 14.
- **Never type OSM ids, LAU/FUA/NUTS codes, Geofabrik region ids or BikeNetKit ids from memory.** Query them, and record the query and its date in the file's header comment.
- `config/trust.yaml` is **not** part of `config_sha256`. Signing off a country must never invalidate runs.
- The app binds only to loopback. Scripts come only from `/static/`, and the only external host is the OSM tile server (decided after M4).
- Mapper data is aggregate only: no uid or username in any table, CSV, page or doc.
- OSM credentials come only from `pass` or the stored Geofabrik cookie. Never print, log or write them.
- Commits:
  - stage explicit paths;
  - end with one trailer, `Assisted-by: Claude:<model-id>`, carrying the implementer's own model id;
  - never commit `data/` or `velometer.sqlite`;
  - never push.
- Every new test must fail without its change. Red-proof it by breaking the rule under test, and say how in the task report.

## Review Focus

1. **A city whose country is pending, seen through any report surface.** That covers the index, the city page (404), the CSV, the charts, the methodology, `reconcile --check` and `timeseries --check`. The city is absent everywhere, and `velometer results` still shows it with an `untrusted` mark. Pinned in Task 6.
2. **A city that has no figure from one ranking source** (most of the new cities for Clean Cities). Its line breaks at that column; it is not drawn straight across. The city is not ranked there, nothing raises, and the column header says `n=`. Pinned in Task 5.
3. **Two QECIO rows of the same metric for one city, or a QECIO row of another NUTS3 unit.** The duplicate raises a `ConfigError` naming the city and metric. The other unit's row is ignored. Pinned in Task 5.
4. **A DB or config change while the app is running.** The next request reflects it: the cache key covers the DB file and every config and docs file the pages read. Pinned in Task 10.
5. **A migration interrupted after its DDL.** The DB stays at its old `user_version` with its old tables. Pinned in Task 1.

---

## Part 1 — Build (offline)

### Task 1: Migration hardening (carried R14 minors)

**Files:**
- Modify: `src/velometer/db.py` (`create_schema`)
- Modify: `src/velometer/cli.py` (`migrate`)
- Test: `tests/test_db.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `create_schema(conn, activity_sha256_for_v5=None)`, unchanged in signature. It now runs every migration step, the schema script and `PRAGMA user_version` inside **one** explicit transaction: `BEGIN` … `COMMIT`, with `ROLLBACK` on any exception.
  - `velometer migrate [--activity-sha SHA]`, where `--activity-sha` becomes optional.

**Background:** `conn.executescript(_SCHEMA)` issues an implicit `COMMIT` before it runs. So today a migration step is committed before `user_version` is set. The fix:
- split `_SCHEMA` into statements and run each with `conn.execute` inside the open transaction;
- `PRAGMA user_version` is transactional in SQLite.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db.py
def test_interrupt_after_schema_ddl_keeps_old_version(tmp_path, monkeypatch):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=0)              # existing helper
    monkeypatch.setattr(db, "_set_user_version", lambda conn, v: (_ for _ in ()).throw(RuntimeError))
    with open_db(path) as conn, pytest.raises(RuntimeError):
        create_schema(conn)
    with open_db(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        cols = {r[1] for r in conn.execute("PRAGMA table_info(activity)")}
        assert "activity_sha256" not in cols             # the v6 rebuild rolled back too
```

(`_set_user_version(conn, v)` is the new one-line helper that `create_schema` calls last inside the transaction; the test patches it to fail.)

```python
# tests/test_cli.py
def test_migrate_without_activity_sha_on_empty_activity(tmp_path):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=0)
    r = runner.invoke(app, ["migrate", "--db", str(path)])
    assert r.exit_code == 0, r.output
    assert "schema v6" in r.output


def test_migrate_without_activity_sha_on_v5_rows_explains(tmp_path):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=2)
    r = runner.invoke(app, ["migrate", "--db", str(path)])
    assert r.exit_code == 1
    assert "--activity-sha" in r.output
```

- [ ] **Step 2: Run and confirm failure.**
  - Run: `uv run pytest -q tests/test_db.py tests/test_cli.py -k "interrupt_after or migrate_without"`
  - Expected: FAIL. The version is already 6 after the interrupt, and `--activity-sha` is required.
- [ ] **Step 3: Implement.**
  - In `create_schema`:
    - `conn.isolation_level = None`, then `conn.execute("BEGIN")`;
    - the migrations;
    - `_repair_done_key_index`;
    - `for stmt in _statements(_SCHEMA): conn.execute(stmt)`, where `_statements` splits on `;` at line end and drops blanks;
    - `_set_user_version(conn, SCHEMA_VERSION)`;
    - `conn.execute("COMMIT")`;
    - on `BaseException`: `ROLLBACK` and re-raise;
    - restore `isolation_level` in `finally`.
  - Remove the per-migration `BEGIN`s in `_migrate_3_to_4` and `_migrate_5_to_6`, since `create_schema` owns the transaction.
  - In `migrate`: `activity_sha: str | None = typer.Option(None, ...)`, validated only when given.
- [ ] **Step 4: Run all DB and CLI tests.**
  - Run: `uv run pytest -q tests/test_db.py tests/test_cli.py`
  - Expected: PASS, including the existing v6 atomicity test.
- [ ] **Step 5: Commit.** Run `git commit -m "fix(db): one transaction per migration incl. user_version; --activity-sha optional"`.

### Task 2: Peak memory per run

**Files:**
- Create: `src/velometer/memory.py`
- Modify: `src/velometer/run.py` (`run_city`, `run_history`)
- Test: `tests/test_memory.py`, `tests/test_run.py`, `tests/test_run_history.py`

**Interfaces:**
- Produces:
  - `class PeakRss`, a context manager. A daemon thread samples `/proc/self/statm` (resident pages × page size) every `interval_s` (default 0.2). It also samples once on enter and once on exit. After exit, `.peak_mb: float` holds the maximum seen inside the block.
  - Every run, current and history, writes the diagnostics key `peak_rss_mb`, measured around `read_ways` + `measure` + `compute_metrics`. `run_city` now passes `diagnostics={"peak_rss_mb": …}` to `complete_run`. `run_history` adds the key to its existing dict.

**Why diagnostics rather than a schema v7 column (ruling for `rulings-m5.md`):** the `diagnostics` table already holds per-run key/value rows. A column would need a migration for one number. `ru_maxrss` is not usable, because runs execute in one process and it never goes down.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_memory.py
from velometer.memory import PeakRss


def test_peak_sees_an_allocation_inside_the_block():
    with PeakRss(interval_s=0.01) as before:
        pass
    with PeakRss(interval_s=0.01) as p:
        blob = bytearray(200 * 1024 * 1024)
        blob[::4096] = b"x" * len(blob[::4096])      # touch every page so it is resident
        del blob
    assert p.peak_mb >= before.peak_mb + 150
```

```python
# tests/test_run.py
def test_current_run_records_peak_rss(tmp_path):
    ...  # run_city with _current_deps -> fetch_diagnostics(conn, run_id)["peak_rss_mb"] > 0
```

```python
# tests/test_run_history.py
def test_history_run_records_peak_rss(tmp_path):
    ...  # run_history over 2 years -> every run's diagnostics has peak_rss_mb > 0, legacy_km too
```

- [ ] **Step 2: Run and confirm failure.** Run `uv run pytest -q tests/test_memory.py tests/test_run.py tests/test_run_history.py -k peak`. It fails: `velometer.memory` doesn't exist yet.
- [ ] **Step 3: Implement.**

```python
# src/velometer/memory.py
"""Peak resident memory of this process during a block (Linux /proc), for the ADR 0007 gate."""

import os
import threading
from pathlib import Path

_PAGE = os.sysconf("SC_PAGE_SIZE")


def rss_mb() -> float:
    resident = int(Path("/proc/self/statm").read_text().split()[1])
    return resident * _PAGE / 2**20


class PeakRss:
    def __init__(self, interval_s: float = 0.2):
        self.interval_s = interval_s
        self.peak_mb = 0.0
        self._stop = threading.Event()

    def _sample(self) -> None:
        self.peak_mb = max(self.peak_mb, rss_mb())

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._sample()

    def __enter__(self) -> "PeakRss":
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._sample()
        self._stop.set()
        self._thread.join()
```

  In `run_city`, wrap the read/measure/metrics lines in `with PeakRss() as peak:` and pass `diagnostics={"peak_rss_mb": peak.peak_mb}`. In `run_history`, do the same and set `diagnostics["peak_rss_mb"] = peak.peak_mb`.
- [ ] **Step 4: Run and confirm pass.** Run `uv run pytest -q tests/test_memory.py tests/test_run.py tests/test_run_history.py tests/test_timeseries.py`. Timeseries must stay green, since `_point` ignores unknown diagnostics keys.
- [ ] **Step 5: Commit.** Run `git commit -m "feat(run): record peak RSS of every run as a diagnostic"`.

### Task 3: Boundaries, population and EPSG for new cities

**Files:**
- Modify: `src/velometer/config.py` (`CityConfig`)
- Modify: `src/velometer/sources/boundaries.py` (`city_boundary`, `population`)
- Modify: `src/velometer/cli.py` (`boundaries fetch`)
- Test: `tests/test_config.py`, `tests/test_boundaries.py`

**Interfaces:**
- Produces, as new optional `CityConfig` fields:
  - `admin_boundary: Literal["gisco", "osm_relation"] = "gisco"`. With `osm_relation`, `city_boundary(city, "lau", …)` builds the admin layer from `osm_relation_id`, following the existing `osm_admin` path. The boundary row keeps `kind="lau"`, with `source=f"OSM relation {id}"`. Population still comes from the GISCO LAU feature, which is looked up by `lau_code` for its properties only.
  - `population_urau: str | None`, an Urban Audit city code such as `FR003C`. It is used only when LAU has no population and `population_nuts3` is unset.
  - The `epsg` validator also requires `25828 <= epsg <= 25838` (ETRS89 / UTM 28N–38N).
- Also produced:
  - `population(city, lau_props, fetch_json=None)`. Its fallback order is LAU `POP_2024`, then `population_nuts3` (`demo_r_pjangrp3`), then `population_urau` (`urb_cpop1`, indicator `DE1001V`, the latest year with a positive value). The year comes from the response, not a constant.
  - `utm_epsg(lon: float) -> int`, which returns `25800 + floor((lon + 180) / 6) + 1`.
  - `check_epsg(city, polygon_4326) -> None`, which raises `ValueError` when `utm_epsg(centroid.x) != city.epsg`. `write_boundary` calls it for `lau` and `osm_relation` boundaries, not FUA, since a FUA may straddle zones.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_boundaries.py
URAU_JSON = {  # the shape of the Eurostat JSON-stat response (dimension time, values by index)
    "value": {"0": 515695.0, "2": 522250.0},
    "dimension": {"time": {"category": {"index": {"2021": 0, "2022": 1, "2023": 2}}}},
}


def test_population_falls_back_to_urban_audit_latest_year():
    city = CITY.model_copy(update={"population_urau": "FR003C", "population_nuts3": None})
    pop = population(city, {"POP_2024": 0}, fetch_json=lambda url: URAU_JSON)
    assert (pop.value, pop.year) == (522250, 2023)
    assert "urb_cpop1 FR003C" in pop.source


def test_population_nuts3_wins_over_urau():
    ...  # both set -> the demo_r_pjangrp3 fake is used, the urb_cpop1 fake is never called


def test_utm_epsg_rule():
    assert utm_epsg(13.4) == 25833 and utm_epsg(2.35) == 25831 and utm_epsg(24.9) == 25835


def test_lau_with_wrong_epsg_is_refused(tmp_path):
    city = CITY.model_copy(update={"epsg": 25832})       # Berlin is 25833
    with pytest.raises(ValueError, match="EPSG 25832.*UTM zone.*25833"):
        check_epsg(city, box(13.3, 52.4, 13.5, 52.6))


def test_osm_relation_admin_boundary_keeps_kind_lau(tmp_path, monkeypatch):
    ...  # admin_boundary=osm_relation: relation_polygon fake -> rec.boundary.kind == "lau",
         # rec.boundary.source == "OSM relation 62422"; population from the GISCO props fake
```

```python
# tests/test_config.py
def test_epsg_must_be_etrs89_utm():
    with pytest.raises(ValidationError):
        CityConfig.model_validate({**BERLIN, "epsg": 3857})
```

- [ ] **Step 2: Run and confirm failure.** Run `uv run pytest -q tests/test_boundaries.py tests/test_config.py`.
- [ ] **Step 3: Implement.**
  - The `urb_cpop1` URL constant is `EUROSTAT_URAU = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_cpop1?format=JSON&lang=EN&cities={code}&indic_ur=DE1001V"`.
  - The latest year is the highest time index whose `value` entry is positive.
  - Mark one live check `@pytest.mark.slow`: `test_urb_cpop1_live_lyon` fetches FR003C and asserts a value between 400k and 700k.
- [ ] **Step 4: Run and confirm pass.** Run `uv run pytest -q tests/test_boundaries.py tests/test_config.py tests/test_run.py`.
- [ ] **Step 5: Commit.** Run `git commit -m "feat(boundaries): OSM-relation admin layer, Urban Audit population, EPSG zone rule"`.

### Task 4: External-source ids move into `cities.yaml`

**Files:**
- Modify: `src/velometer/config.py` (`CityConfig`)
- Modify: `src/velometer/sources/external.py`
- Modify: `config/cities.yaml`, filling the 5 pilots with today's values
- Test: `tests/test_external.py`

**Interfaces:**
- Produces, as new optional `CityConfig` fields:
  - `bikenetkit_id: str | None`;
  - `nuts3_is_city: bool | None` (None = not assessed);
  - `nuts3_note: str | None`.
- `BIKENETKIT_IDS` and `QECIO_CITY_NOTES` are deleted.
  - `bikenetkit_figures` reads `city.bikenetkit_id` and skips cities without one.
  - `qecio_figures` appends `city.nuts3_note`, plus `"NUTS3 unit is not the city"` when `nuts3_is_city is False`.
  - A city without `nuts3_code` gets no QECIO rows.
- The pilot values:
  - `bikenetkit_id`: berlin_de, paris_fr, vienna_at, copenhagen_dk, wroclaw_pl;
  - `nuts3_is_city`: true for Berlin, Paris and Vienna; false for Copenhagen (with the existing DK011 note as `nuts3_note`) and Wrocław (PL514 is Miasto Wrocław, so **verify** against the research doc before setting it).
- `load_all` output stays row-for-row identical for the pilots. A test pins this.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_external.py
def test_pilot_rows_unchanged_after_moving_ids_to_config(tmp_path):
    ...  # qecio_figures + bikenetkit_figures on the existing fixtures with load_cities(config)
         # equal the stored golden rows (notes included) captured before the change:
         # tests/fixtures/external/pilot_rows.json (write it in this step from the old code)


def test_city_without_bikenetkit_id_is_skipped(tmp_path): ...


def test_nuts3_not_city_is_noted():
    city = CITY.model_copy(update={"nuts3_is_city": False, "nuts3_note": None})
    rows = qecio_figures(QECIO_FIXTURE, [city])
    assert all("NUTS3 unit is not the city" in r.note for r in rows)
```

- [ ] **Step 2: Run and confirm failure.** Before changing the code, write `pilot_rows.json` from the current code, so the golden rows record today's output.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** `uv run pytest -q tests/test_external.py tests/test_config.py`.
- [ ] **Step 5: Commit.** Run `git commit -m "refactor(external): BikeNetKit ids and NUTS3 notes are city config"`.

### Task 5: Scoped QECIO ratio and gap-aware rankings (carried)

**Files:**
- Modify: `src/velometer/config.py` (`ExternalRatioRanking`; `ReportConfig` gains nothing here)
- Modify: `src/velometer/report/data.py` (`_ranking_value`, `RankEntry`, `ranks`)
- Modify: `src/velometer/report/charts.py` (`rankings_flip`)
- Modify: `config/report.yaml`
- Modify: `tests/report_fixture.py`, where the fixture QECIO scope becomes `nuts3_<code>`
- Test: `tests/test_report_data.py`, `tests/test_charts.py`

**Interfaces:**
- `ExternalRatioRanking` gains `scope: str`, required. It is a format string over city config fields, for example `"nuts3_{nuts3_code}"`. A city whose field is None has no value.
- `_ranking_value` takes, for ratio rankings, only figures with `network_scope == scope.format(**city_fields)`. When a metric has **two** such figures, it raises `ConfigError(f"{city_id}: {source} {metric}: 2 figures with scope {scope}")`.
- `ReportData.ranking_rows() -> list[RankingRow]` is new. It returns one row per (source, city), **including** cities with no value:

  ```python
  class RankingRow(_Frozen):
      source_id: str
      source_label: str
      city_id: str
      value: float | None
      rank: int | None       # None: no figure from this source
      n_ranked: int          # cities with a value in this source
  ```

- `ranks()` stays, filtered to rows with a rank, for existing callers.
- `rankings_flip` draws from `ranking_rows()`:
  - `mark_line(invalid="break-paths-filter-domains")`, so a null rank breaks the line;
  - points only where the rank is non-null;
  - each column label is `f"{label} (n={n_ranked})"`;
  - the tooltip says `not published` where the value is null.
- `config/report.yaml`'s `published_qecio` gains `scope: "nuts3_{nuts3_code}"`.

**Detail:** `ReportData` needs city config fields (`nuts3_code`) for the scope format. It loads `cities.yaml` from `config_dir` next to `fetch_cities`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report_data.py
def test_qecio_ratio_ignores_other_scopes(report_db):
    ...  # add a qecio row for berlin with network_scope "nuts3_XX000" and a huge value;
         # the berlin QECIO ratio stays 50.0


def test_qecio_ratio_duplicate_same_scope_raises(report_db):
    ...  # add a second cycle_tracks_km for berlin with scope nuts3_DE300 -> ConfigError naming
         # berlin and cycle_tracks_km


def test_ranking_rows_include_cities_without_a_figure(report_db):
    rows = data.ranking_rows()
    paris_qecio = next(r for r in rows if r.source_id == "published_qecio" and r.city_id == "paris")
    assert paris_qecio.rank is None and paris_qecio.value is None
    assert {r.n_ranked for r in rows if r.source_id == "published_qecio"} == {1}
```

```python
# tests/test_charts.py
def test_rankings_line_breaks_at_a_missing_source(report_db):
    spec = charts.rankings_flip(data)
    values = _rows(spec)                                      # existing helper: inline data rows
    assert any(v["city"] == "Paris" and v["rank"] is None for v in values)
    assert _mark(spec)["invalid"] == "break-paths-filter-domains"
    assert any("(n=1)" in v["source"] for v in values)
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** `uv run pytest -q tests/test_report_data.py tests/test_charts.py tests/test_app.py tests/test_config.py`.
- [ ] **Step 5: Commit.** Run `git commit -m "fix(report): QECIO ratio by city NUTS3 scope; rankings break at missing figures"`.

### Task 6: Trust config and report filtering

**Files:**
- Create: `config/trust.yaml`
- Modify: `src/velometer/config.py` (`TrustConfig`, `load_trust`)
- Modify: `src/velometer/selection.py` (`trusted_countries`)
- Modify: `src/velometer/report/data.py` (`ReportData.cities`)
- Modify: `src/velometer/cli.py` (`_report_cities` for `reconcile`, `timeseries`, `report *`; an untrusted mark in `results`)
- Modify: `src/velometer/app/main.py` (`known` relies on the filtered cities → 404)
- Modify: `tests/conftest.py` (`report_db_with_trust(countries=...)`, which builds the report fixture and rewrites its config copy's `trust.yaml`)
- Test: `tests/test_trust.py`, `tests/test_report_data.py`, `tests/test_cli.py`, `tests/test_app.py`

**Interfaces:**
- `config/trust.yaml`:

  ```yaml
  # Per-country trust gate (M5 spec section 3). Not part of config_sha256: signing off a country
  # never invalidates runs. Report surfaces show only cities of trusted countries.
  thresholds:            # set in Task 13 from the pilots (largest pilot value x 1.25)
    unrecognised_share_max: 1.0
    excluded_share_max: 1.0
    b_share_of_ab_max: 1.0
    boundary_diff_pct_max: 5.0
  countries:
    DE: {status: trusted, basis: "berlin golden set (M1)"}
    FR: {status: trusted, basis: "M2 reconciliation", pilot: paris}
    AT: {status: trusted, basis: "M2 reconciliation", pilot: vienna}
    DK: {status: trusted, basis: "M2 reconciliation", pilot: copenhagen}
    PL: {status: trusted, basis: "M2 reconciliation", pilot: wroclaw}
  ```

  The thresholds of 1.0 are deliberately permissive until Task 13 sets them from data. Task 13 must change them, and `trust --check` (Task 8) fails while any threshold is still 1.0 for a share.
- Models:

  ```python
  class TrustThresholds(_Strict):
      unrecognised_share_max: float = Field(gt=0, le=1)
      excluded_share_max: float = Field(gt=0, le=1)
      b_share_of_ab_max: float = Field(gt=0, le=1)
      boundary_diff_pct_max: float = Field(gt=0)

  class CountryTrust(_Strict):
      status: Literal["pending", "trusted"]
      basis: str
      pilot: str | None = None                 # same-country pilot city for comparison
      golden: str | None = None                # "tests/fixtures/golden/<cc>" (no extension)
      classifier_reviewed: str | None = None   # e.g. "v2"; required when golden is set and trusted
      signed_off: date | None = None           # required when golden is set and trusted

  class TrustConfig(_Strict):
      thresholds: TrustThresholds
      countries: dict[str, CountryTrust]       # key: ISO2

  def load_trust(path: Path) -> TrustConfig
  ```

- `trusted_countries(config_dir) -> frozenset[str]`, in `selection.py`.
- `ReportData.cities()` keeps only cities whose `country_iso2` is trusted. A country missing from `trust.yaml` counts as **pending**: absent means untrusted.
- `ReportData.all_cities()` is new and unfiltered. Only `results` uses it.
- CLI `reconcile`, `timeseries`, `report csv|charts|methodology|maps`: city iteration and `--city` validation use the trusted cities. Asking for an untrusted city with `--city` exits 2 with `"<id> is not trusted yet (country XX pending, see config/trust.yaml)"`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_trust.py
def test_absent_country_is_untrusted(tmp_path):
    cfg = _config_with_trust(tmp_path, countries={"DE": TRUSTED})
    assert trusted_countries(cfg) == frozenset({"DE"})


def test_trusted_with_golden_requires_signoff(tmp_path):
    with pytest.raises(ConfigError, match="signed_off"):
        _load(countries={"NL": {"status": "trusted", "basis": "x", "golden": "g/nl"}})
```

```python
# tests/test_report_data.py  (report fixture: berlin=DE, paris=FR)
def test_untrusted_country_is_absent_from_every_report_surface(report_db_with_trust):
    db, cfg = report_db_with_trust(countries={"DE": TRUSTED})        # FR pending
    data = ReportData(open_readonly(db), cfg)
    assert [c.id for c in data.cities()] == ["berlin"]
    assert all(r["city_id"] == "berlin" for r in data.csv_rows())
    assert all(r.city_id == "berlin" for r in data.ranking_rows())
    assert "paris" not in json.dumps(charts.headline_over_time(data))
    assert "Paris" not in methodology.render(methodology.methodology_facts(data), "en")
```

```python
# tests/test_app.py
def test_untrusted_city_page_is_404(...): ...   # /city/paris -> 404 with FR pending
```

```python
# tests/test_cli.py
def test_reconcile_check_skips_untrusted_and_city_flag_refuses(...): ...
def test_results_marks_untrusted(...): ...       # output line for paris contains "untrusted"
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** Write `config/trust.yaml` as above.
- [ ] **Step 4: Run the full gate.** `uv run pytest -q`.
- [ ] **Step 5: Commit.** Run `git commit -m "feat(trust): per-country trust config; report surfaces show trusted cities only"`.

### Task 7: Trust diagnostics

**Files:**
- Create: `src/velometer/trust.py`
- Modify: `src/velometer/cli.py` (a `trust` sub-app: `diagnose`)
- Test: `tests/test_trust.py`

**Interfaces:**
- Consumes:
  - `report.maps.snapshot_path(run_row, data_dir)`;
  - `pipeline.read.read_ways`;
  - `pipeline.measure.measure`;
  - `pipeline.activity.cycling_tags`;
  - `sources.boundaries.load_boundary_polygon` and `relation_polygon`;
  - `Selector.latest`.
- Produces:

  ```python
  class CityDiagnostics(BaseModel):
      city_id: str
      run_id: int                       # the current LAU run diagnosed
      osm_timestamp: str
      cycling_km: float                 # per-side km of sides whose way carries cycling tags
      unrecognised_share: float         # (no tier or unknown_value) & cycling tags, over cycling_km
      excluded_share: float             # tier "excluded" over cycling_km
      excluded_by_rule: dict[str, float]  # rule_id -> share of cycling_km
      tier_mix: dict[str, float]        # A..E -> share of A-E per_side km
      b_share_of_ab: float | None       # None when A+B = 0
      completeness: dict[str, dict[str, float]]   # tier -> {width, surface, segregated}
      top_unmatched: list[tuple[str, float]]       # (tag signature, km), 20 largest
      boundary_lau_km2: float
      boundary_osm_km2: float | None    # None when no region file is cached
      boundary_diff_pct: float | None

  class CountryDiagnostics(BaseModel):
      country: str
      classifier_version: str
      config_sha256: str
      cities: list[CityDiagnostics]

  def diagnose_city(conn, city: CityConfig, selector, data_dir, activity_cfg) -> CityDiagnostics
  def breaches(d: CityDiagnostics, t: TrustThresholds) -> list[str]   # metric names over limit
  def write_country(docs_dir, cd: CountryDiagnostics, thresholds, pilots: list[CityDiagnostics])
      # -> docs/review/trust/<cc>.json (machine) and the generated block of <cc>.md (between
      #    <!-- trust:begin --> / <!-- trust:end -->; hand-written notes outside it are kept)
  ```

- The tag signature is `highway=<v>` plus every tag whose key `cycling_tags` would count. Keys are sorted, joined with `;`, and the values are truncated to 40 characters.
- The boundary diff is computed against the OSM relation polygon, from the city's cached Geofabrik region file. It is `abs(lau - osm) / osm * 100`.
- CLI: `velometer trust diagnose --country XX [--db] [--data] [--config-dir] [--docs]`. It covers every city of that country with a current LAU run of the report config. The pilot comparison block uses `trust.yaml`'s `pilot`, when set, for FR and PL. A city with no current LAU run is an error: exit 1, naming the city.

- [ ] **Step 1: Write failing tests**, on the `mini_city.osm` fixture through the M3 fakes:

```python
def test_diagnose_shares_add_up(report_db, tmp_path):
    d = diagnose_city(conn, CITY, sel, data_dir, act)
    assert 0 <= d.unrecognised_share <= 1 and 0 <= d.excluded_share <= 1
    assert abs(sum(d.tier_mix.values()) - 1) < 1e-9
    assert d.excluded_share == pytest.approx(sum(d.excluded_by_rule.values()))


def test_breaches_names_each_metric_over_its_limit():
    d = _diag(unrecognised_share=0.2, excluded_share=0.1, b_share_of_ab=0.9, boundary_diff_pct=7)
    t = TrustThresholds(unrecognised_share_max=0.1, excluded_share_max=0.5,
                        b_share_of_ab_max=0.8, boundary_diff_pct_max=5)
    assert breaches(d, t) == ["unrecognised_share", "b_share_of_ab", "boundary_diff_pct"]


def test_write_country_keeps_hand_written_notes(tmp_path): ...
def test_top_unmatched_signature_has_only_cycling_keys(): ...
```

  The fixture expectations must be hand-computed from `mini_city.osm`'s known ways: state the numbers in the test, don't derive them from the code under test.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** `uv run pytest -q tests/test_trust.py tests/test_cli.py`.
- [ ] **Step 5: Commit.** Run `git commit -m "feat(trust): per-country tagging diagnostics and review file"`.

### Task 8: Golden samples and `trust --check`

**Files:**
- Modify: `src/velometer/trust.py`
- Modify: `src/velometer/cli.py` (`trust sample`, `trust check`)
- Modify: `src/velometer/osmium.py` (`getid`)
- Create: `tests/test_golden_countries.py`
- Modify: `tests/test_golden.py`, moving `check_golden` to `tests/golden_util.py` (shared)
- Test: `tests/test_trust.py`, `tests/test_osmium.py`

**Interfaces:**
- `osmium.getid(src: Path, way_ids: list[int], dst: Path) -> Path` runs `osmium getid -r -o dst src w<id>…`, atomically.
- `sample_ways(classified, way_lengths, tags_by_way, *, top_rules=6, per_rule=1, unmatched=3) -> list[Sample]`. It picks:
  - the longest way-side of each of the `top_rules` rules with the most km (tiers A–E and excluded);
  - then the longest side of each of the `unmatched` largest unmatched signatures;
  - deduplicated by way id.

  ```python
  class Sample(BaseModel):
      way_id: int
      city_id: str
      group: str                 # rule id, or "unmatched:<n>"
      name: str                  # the way's name tag or ""
      highway: str
      proposed: list[dict]       # [{side, tier, rule, subtype, bidirectional}], as berlin_golden
  ```

- `velometer trust sample --country XX [--extra-way ID]…` does the following:
  - samples from every city of the country, about 12 per country: the 6 top rules plus 3 unmatched over the merged per-country ranking, plus any `--extra-way` hotspots;
  - writes `tests/fixtures/golden/<cc>.osm` with `getid` from each city's current snapshot, merged with `osmium.merge`;
  - writes `tests/fixtures/golden/<cc>.yaml` in the `berlin_golden.yaml` schema (`source`, `classifier_version`, `ways[]` with `confirmed: false`, `note: ''`) and an ODbL header;
  - writes `docs/review/trust/<cc>_golden.md`, with one row per sample: an `https://www.openstreetmap.org/way/<id>` link, the tags (only cycling keys and highway), our tier and rule, and an empty **verdict** column.
- `velometer trust check` exits 1 for each of the following, with one line per problem:
  - (a) a trusted country with `golden` whose fixtures have any unconfirmed way, or whose confirmed ways don't match the report classifier (`check_golden` logic);
  - (b) a trusted country with `golden` whose `classifier_reviewed` is not `report_classifier`;
  - (c) a trusted country's `<cc>.json` whose `run_id`s are not the latest current LAU runs of the report config (stale: re-run `trust diagnose`);
  - (d) a breach (`breaches`) without a `### <city>/<metric>` heading in `<cc>.md`;
  - (e) any share threshold still at its placeholder value of 1.0;
  - (f) a trusted country (other than DE) with a city in `cities.yaml` but no `<cc>.json`.
- `tests/test_golden_countries.py` is parametrised over `tests/fixtures/golden/*.yaml` and uses the report classifier. A file with zero confirmed ways is skipped with the reason `"<cc>: 0/N confirmed (awaiting review)"`. On partial confirmation, it warns with the unconfirmed count, as Berlin's test does.

- [ ] **Step 1: Write failing tests**:
  - sampling on `mini_city`: deterministic picks, and dedupe by way id;
  - the YAML schema round-trips through the Berlin loader;
  - `trust check` gets one test per exit condition, (a) to (f). Each builds a tmp config, docs dir and fixture DB, and asserts exit 1 plus the specific message. A clean case asserts exit 0;
  - `getid` with a fake runner records the argv.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** `uv run pytest -q tests/test_trust.py tests/test_golden.py tests/test_golden_countries.py tests/test_osmium.py`.
- [ ] **Step 5: Commit.** Run `git commit -m "feat(trust): golden samples per country and trust check"`.

### Task 9: Charts at 21 cities

**Files:**
- Modify: `src/velometer/config.py` (`ReportConfig.highlight`, `comparison_set`, validated against `cities.yaml`)
- Modify: `src/velometer/report/charts.py`
- Modify: `config/report.yaml`
- Modify: `src/velometer/app/templates/index.html`, only if the vega-embed options need `actions: false` for the bound select; check first
- Test: `tests/test_charts.py`, `tests/test_config.py`

**Interfaces:**
- `ReportConfig` gains:
  - `highlight: list[str] = ["berlin"]`;
  - `comparison_set: list[str] = []`.
- `load_report(path, presets_path=None, cities_path=None)`: when `cities_path` is given, an unknown id in either list raises a `ConfigError` that names it. `ReportData` passes `config_dir / "cities.yaml"`.
- `config/report.yaml` gets `highlight: [berlin]` and `comparison_set: [paris, copenhagen, amsterdam, vienna]`. Amsterdam joins `cities.yaml` only in Task 13, so this task keeps `comparison_set: [paris, copenhagen, vienna]`, and Task 13 adds `amsterdam`.
- Every chart row gains `role` ∈ {`highlight`, `comparison`, `other`}.
- `headline_over_time`:
  - LAU only (FUA moves to the city page, spec §4.1);
  - layer 1: `role == other`, thin lines (`strokeWidth=1`) in `GREY = "#c9c8c3"`, no legend;
  - layer 2: `highlight` and `comparison` cities, coloured with `CITY_COLOURS` in config order, `strokeWidth=2.5` for highlight and 1.8 for comparison, labelled at the "now" point with a text mark;
  - a picker param:

    ```python
    pick = alt.selection_point(name="pick", fields=["city"], empty=False,
                               bind=alt.binding_select(options=[None, *other_names],
                                                       labels=["—", *other_names],
                                                       name="Highlight a city "))
    ```

    The grey layer's colour is `alt.condition(pick, alt.value(PICK_COLOUR), alt.value(GREY))`, with `PICK_COLOUR = "#7a5bd1"`, and `strokeWidth` is conditional in the same way.
  - The flag rings stay on the coloured layer only.
- `rankings_flip`: the same role layering. The grey lines are `strokeWidth=1` with no points.
- `tiers_small_multiples`: `columns=7`, **shared** y scale (`resolve_scale(y="shared")`), each panel 150×110. The facet sort is the city name.
- The PNG export is unchanged. vl-convert renders the bound select as nothing; the static colouring holds.

- [ ] **Step 1: Write failing tests**

```python
def test_headline_roles_follow_config(report_db, tmp_path):
    cfg = _with_report(tmp_path, highlight=["paris"], comparison_set=[])
    rows = _rows(charts.headline_over_time(ReportData(conn, cfg)))
    assert {r["role"] for r in rows if r["city_id"] == "paris"} == {"highlight"}
    assert {r["role"] for r in rows if r["city_id"] == "berlin"} == {"other"}


def test_headline_has_a_bound_picker(report_db):
    spec = charts.headline_over_time(data)
    params = [p for layer in spec["layer"] for p in layer.get("params", [])]
    assert any(p["name"] == "pick" and "bind" in p for p in params)


def test_headline_is_lau_only(report_db): ...
def test_small_multiples_shared_y_and_seven_columns(report_db): ...
def test_unknown_highlight_city_is_a_config_error(tmp_path): ...
```

(The PNG-at-21-cities test lives in Task 10, which builds the 21-city fixture.)

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** `uv run pytest -q tests/test_charts.py tests/test_app.py tests/test_config.py`.
- [ ] **Step 5: Render the three PNGs to `$TMPDIR` from the 21-city fixture and look at them**, at 1280 px for the app and at the PNG size. Note what you saw in the task report.
- [ ] **Step 6: Commit.** Run `git commit -m "feat(charts): Berlin focus with comparison set and picker; 7x3 tier multiples"`.

### Task 10: App cache and the 21-city fixture (carried)

**Files:**
- Create: `src/velometer/app/cache.py`
- Modify: `src/velometer/app/main.py`
- Modify: `tests/report_fixture.py` (`build_report_fixture_n(tmp_path, n_cities)`)
- Modify: `tests/conftest.py` (`report_db_21` fixture)
- Test: `tests/test_app.py`

**Interfaces:**
- `fingerprint(db_path, config_dir, docs_dir, maps_dir) -> tuple`. It is built from:
  - the DB's `(st_mtime_ns, st_size)`;
  - `(relpath, st_mtime_ns, st_size)` for every file under `config_dir` (recursive, sorted);
  - the same for `docs_dir/review/m3_timeseries.md`, `docs_dir/reconciliation.md`, `docs_dir/methodology.md` and `docs_dir/methodology.de.md`, plus every file under `maps_dir` matched by `*.png` or `*.geojson` (names only, plus mtimes). A missing file contributes `(relpath, None, None)`.
- `class PageCache` provides `get(name: str, fp: tuple, build: Callable[[], T]) -> T`. It holds one entry per name, rebuilds when `fp` differs, and is guarded by a `threading.Lock`.
- In `main.py`: the index context, each city context (keyed `city:<id>`) and each CSV text (keyed `csv:<id|all>`) go through the cache. The DB connection is opened lazily, only when `build` runs: the dependency yields a `LazyData` that opens `open_readonly` on first attribute access. The 503 behaviour stays.
- `build_report_fixture_n(tmp_path, n)` builds berlin and paris as today, plus `n - 2` synthetic cities: copies of `CITY` with ids `c03…cNN`, names `City 03…`, and country `DE` so they are trusted. Each gets history 2024–2026 and a current LAU run through the fakes.

- [ ] **Step 1: Write failing tests**

```python
def test_second_request_does_not_query(client_21, monkeypatch):
    calls = Counter()
    real = ReportData.cities
    monkeypatch.setattr(ReportData, "cities", lambda self: calls.update(["q"]) or real(self))
    client_21.get("/"); first = calls["q"]
    client_21.get("/")
    assert first > 0 and calls["q"] == first


def test_db_change_invalidates(client_21, db_21):
    client_21.get("/")
    os.utime(db_21, ns=(time.time_ns(), time.time_ns() + 10**9))
    ...  # next request queries again


def test_config_change_invalidates(...): ...     # touch config/report.yaml -> re-query


def test_every_route_200_at_21_cities(client_21):
    for path in ["/", "/city/berlin", "/city/c21", "/data/all.csv", "/methodology"]:
        assert client_21.get(path).status_code == 200


def test_png_export_at_21_cities(report_db_21, tmp_path):
    paths = charts.write_pngs(ReportData(open_readonly(db), cfg), tmp_path)
    assert all(p.stat().st_size > 0 for p in paths if p.suffix == ".png")


def test_warm_page_times_are_reported(client_21, capsys):
    ...  # time each route warm (second call); print a table; no assertion on the numbers
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Run `uv run pytest -q tests/test_app.py -s -k "warm or every_route"` and record the warm timings in the task report. The target is under 500 ms. Then run `uv run pytest -q`.
- [ ] **Step 5: Commit.** Run `git commit -m "perf(app): page cache keyed on DB, config and docs fingerprints"`.

### Task 11: Methodology additions (EN + DE)

**Files:**
- Modify: `config/limitations.yaml`
- Modify: `src/velometer/report/methodology.py` (facts)
- Modify: `src/velometer/report/templates/methodology.en.md.j2` and `methodology.de.md.j2`
- Test: `tests/test_methodology.py`

**Interfaces:**
- `MethodologyFacts` gains:
  - `countries: list[CountryFact]` (`iso2`, `status`, `basis`, `classifier_reviewed`, `signed_off`, `n_golden_confirmed`, `n_golden`), trusted countries only;
  - per city, `boundary_source` (GISCO LAU, or OSM relation N) and `population_source`, which is the stored source string.
- New limitations, each with `en` and `de`:
  - `trust_gate`: what the gate checks, that golden samples are about 12 ways per new country, and that FR, PL, AT and DK were trusted through M2 reconciliation;
  - `population_urban_audit`: Lyon, Strasbourg and Bordeaux use Eurostat `urb_cpop1` city population for its latest year, which may not be 2024;
  - `qecio_nuts3_not_city`: the affected cities are named from `nuts3_is_city: false`. The text is generated: the template lists them from facts, not from the YAML text.
- German wording follows R7: "Kennzahlvariante"; tier B is "Geh- und Radweg (gemeinsam oder getrennt)".

- [ ] **Step 1: Write failing tests**:
  - both renders contain each trusted country's row and each city's boundary and population source;
  - the `qecio_nuts3_not_city` list follows `cities.yaml` (red-proof: flip a flag and the list changes);
  - `--check` fails when a new limitation lacks `de`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** Write the German prose yourself, carefully: it is published text.
- [ ] **Step 4: Run.** Run `uv run pytest -q tests/test_methodology.py`. Do **not** regenerate `docs/methodology*.md` here; Task 18 does that on real data.
- [ ] **Step 5: Commit.** Run `git commit -m "feat(methodology): trust gate, boundary and population sources, new limitations"`.

### Task 12 (conditional): Streaming classification

**Run only if Task 15 finds a run with `peak_rss_mb > 8192`.** Otherwise, skip it, and record the measured peaks in ADR 0007's notes (Task 18).

**Files:**
- Create: `src/velometer/pipeline/stream.py`
- Modify: `src/velometer/run.py` and `src/velometer/report/maps.py`, to use it
- Test: `tests/test_stream.py`

**Interfaces:**
- `measure_streaming(snapshot: Path, cfg, epsg, boundary) -> MeasureResult` gives the same result as `measure(read_ways(snapshot).ways, cfg, epsg, boundary=boundary)`. The difference is that a pyosmium `SimpleHandler` classifies each way as it is read and keeps only:
  - the classified sides with tier A–E or `excluded`, or with no tier but cycling tags (for drift);
  - main-road geometry for road lengths and dual carriageways;
  - `way_lengths`;
  - tags reduced to the keys that completeness, drift and `report maps` read (`keep_tag` ∪ the completeness keys ∪ the cycling keys).
- Dedupe and dual-carriageway detection keep their STRtree over the retained A–D sides and main roads only.

- [ ] **Step 1: Write failing tests.** For every fixture under `tests/fixtures/measure/` and `tests/fixtures/cases/`, `measure_streaming` equals `measure` field by field: tier lengths and road lengths exactly; duplicates and dual pairs as sets; completeness exactly.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Then, on real data, compare streaming against batch for Berlin LAU current and Paris FUA current. Tier and road km must match to 1e-9 km. Record the peak RSS of both.
- [ ] **Step 5: Commit.** Run `git commit -m "perf(pipeline): streaming classification (ADR 0007 gate tripped)"`.

---

## Part 2 — Execution (real data; the most capable model; the controller runs these)

Before Task 13, take a DB backup: `cp velometer.sqlite data/velometer-pre-m5.sqlite`. Credentials come only from the stored Geofabrik cookie or `pass`, injected inline (R10).

### Task 13: Onboard the 16 cities, run diagnostics and samples → **stop for your sign-off**

- [ ] **Step 1: `cities.yaml` entries, all queried, with each query recorded in the header comment:**
  - `osm_relation_id`, from Nominatim (`city=<name>&country=<country>&format=jsonv2`). Take the municipality relation, as for Copenhagen; never a place node.
  - `lau_code`, from `LAU_RG_01M_2024_3035.gpkg` by name and country (`GISCO_ID`).
  - `fua_code`, from URAU 2024 (`…F`).
  - `nuts3_code` and `nuts3_is_city`: whether the NUTS3 unit's area is within 5 % of the LAU area. Add a `nuts3_note` when it isn't.
  - `population_urau`: only for Lyon, Strasbourg and Bordeaux, the Urban Audit `…C` code, after checking that the Urban Audit city is the commune (its LAU code list or its area against the LAU).
  - `geofabrik_region`: from the cached Geofabrik index, the smallest region that covers the LAU.
  - `bikenetkit_id`: from the BikeNetKit zip listing (`bike_networks/*.gpkg`).
  - `epsg`: `utm_epsg(LAU centroid lon)`. `boundaries fetch` enforces it.
- [ ] **Step 2:** Run `velometer init`, then `boundaries fetch` for every city. Run the boundary check against the OSM relation for all 16 new cities and look hard at Oslo, Ljubljana and Bratislava (ADR 0004). Above 5 % difference: set `admin_boundary: osm_relation`, refetch, and record why in the `cities.yaml` comment.
- [ ] **Step 3:** Run the current LAU runs for the 16 cities, then `velometer results` (they show as untrusted).
- [ ] **Step 4: External figures:**
  - Clean Cities 2025 rows go into `config/external/figures.csv`, from the report PDF's Table 5 and its annex, with page references, for every one of the 21 cities that has a figure. Don't add rows for the others.
  - Then run `velometer external load --qecio --bikenetkit`.
- [ ] **Step 5: Thresholds.**
  - Run `trust diagnose` for DE, FR, AT, DK and PL, which covers the pilots plus Lyon, Strasbourg, Bordeaux, Warsaw and Kraków.
  - Set each share threshold to `round(max over the 5 pilots × 1.25, 3)`, capped at 1. Record the pilot values in a comment beside each threshold.
  - Explain any FR or PL non-pilot breach under `### <city>/<metric>` in `docs/review/trust/<cc>.md`.
- [ ] **Step 6:** Run `trust diagnose` and `trust sample` for NL, ES, SE, NO, FI, HU, CZ, SK and SI. Add `--extra-way` hotspots where the diagnostics show a country-specific pattern. Add `countries:` entries with `status: pending` and the `golden` path.
- [ ] **Step 7:** Read every golden page. For each sample, write a proposed verdict and a one-line reason, checked against the tags and the OSM wiki for that country's conventions. Collect the proposed v3 rule changes, if any, as a list. Each entry gives:
  - the rule;
  - the tag pattern;
  - the countries and km affected;
  - the effect on the pilots' km, measured with a scratch classifier copy in `$TMPDIR`.
- [ ] **Step 8:** Commit the config, figures and review files. Run `git commit -m "data(m5): onboard 16 cities; trust diagnostics and golden samples"`.
- [ ] **Step 9: STOP.** Present to you, in one message:
  - the 9 golden pages (links), with the proposed verdicts;
  - the threshold table;
  - any breaches;
  - any proposed v3 rules.

  Wait for the sign-off. Then:
  - set `confirmed: true` per way as you rule;
  - set `status: trusted`, `classifier_reviewed` and `signed_off` per country;
  - add `amsterdam` to `comparison_set`;
  - run `trust check`. It must exit 0 except for countries left pending at your choice.

### Task 14: Classifier v3 (only if you approved rule changes)

- [ ] **Step 1:** Write `config/classifier/v3.yaml` as v2 plus the approved rules. Add fixture tests in `tests/test_classifier_v3.py`, one per new rule, red-proofed. Re-run the golden sets (Berlin and every country) on v3. Any sample whose tier changes goes back to you for confirmation.
- [ ] **Step 2:** Set `report.yaml: report_classifier: v3`, and set `classifier_reviewed: v3` on the countries you re-confirm. Run the gate.
- [ ] **Step 3:** Re-run the current LAU runs for all 21 cities on v3, then re-run `trust diagnose` for every country. Commit.

### Task 15: Current FUA runs and the memory gate

- [ ] **Step 1:** Run the current FUA runs for all 21 cities. Read `peak_rss_mb` for every current run (LAU and FUA) from `diagnostics`.
- [ ] **Step 2:** If any run is over 8192 MB, do Task 12 now (implementer, review), then re-run that city. Otherwise record "gate not tripped" with the table of peaks.
- [ ] **Step 3:** Run `report maps` for all 21 cities, LAU and FUA, with `/usr/bin/time -v`, and record the peak. Look at 4 maps, including the largest FUA.

### Task 16: Full history run

- [ ] **Step 1:** Commit everything first, since a run must not carry `-dirty` (R10). Back up the DB: `data/velometer-pre-m5-run.sqlite`.
- [ ] **Step 2:** Run `osm fetch-history` for every new country's regions, LAU and FUA, and verify each file's published md5.
- [ ] **Step 3:**
  - Run `velometer run --cities all --years 2018-2026` (LAU), then with `--boundary fua`, unattended and sequential, in the background with a log in `data/`.
  - If v3 was introduced, the pilots rerun too; otherwise their v2 runs are skipped and only the missing pilot FUA years run.
  - Record wall clock per city and kind in `rulings-m5.md`, as ADR 0005's M3 table does.
- [ ] **Step 4:** Set `history.yaml`'s `required_kinds.default: [lau, fua]` and remove the now-redundant berlin and paris entries. No run may fail. A failure is diagnosed (systematic-debugging) and re-run, not skipped.

### Task 17: Explanations, in full prose (decision 2)

- [ ] **Step 1:** Run `timeseries --write` and `reconcile --write`, then list every missing heading from both `--check`s.
- [ ] **Step 2:** Dispatch one subagent per country (pilot countries included, for their new FUA flags). Each one gets:
  - the missing headings;
  - the run ids;
  - read access to the DB and snapshots;
  - the pilot explanations as the standard of evidence.

  Each heading needs a cause (**definition**, **boundary**, **mapping activity**, **tagging**, **scope** or **classifier**), the numbers that show it, and way-level evidence where the cause isn't plain from the run rows. Mapper data stays aggregate only.
- [ ] **Step 3:** Review every country's text against the numbers before committing. Spot-check at least 3 claims per country against the DB. Set the explained-against markers. Both `--check`s exit 0.
- [ ] **Step 4:** Commit per country: `docs(m5): explanations for <cc>`.

### Task 18: Report, verification and records

- [ ] **Step 1:** Run `report charts`, `report maps`, `report methodology` and `report csv`. Then run all four checks: `reconcile --check`, `timeseries --check`, `report methodology --check` and `trust check`, plus the gate.
- [ ] **Step 2:** Run `velometer serve`. Screenshot `/`, `/methodology` and every city page at 1280 and 390 px. Use the Chrome extension, or headless Chrome as in R15. Then check:
  - the picker works;
  - untrusted cities are absent;
  - 3 cities' numbers match the CLI;
  - the network log shows only `/static/` and the OSM tiles.
- [ ] **Step 3:** Update the records:
  - ADR 0007 notes: the peak-memory table and the streaming decision;
  - ADR 0004 notes: the boundary decisions for Oslo, Ljubljana and Bratislava;
  - ADR 0005 notes: the M5 run table;
  - `docs/superpowers/rulings-m5.md`: every ruling made, including Task 2's diagnostics-not-column choice;
  - `CLAUDE.md`'s "Latest delivered" line.
- [ ] **Step 4:** Run the final whole-branch review (most capable model), fix it, and commit.
