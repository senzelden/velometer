# velometer M2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce persisted, reproducible current-snapshot runs for the 5 pilot cities on the LAU boundary, with tiers, roads, presets and completeness. Reconcile them against Clean Cities 2025, QECIO v2.10 and BikeNetKit, and require a written explanation for every gap over 20%.

**Architecture:**
- Network access lives in `src/velometer/sources/`. `osmium` subprocesses live in `src/velometer/osmium.py`.
- Pipeline stages stay pure. `measure` gains boundary clipping and completeness.
- SQLite schema v2 adds run keys and a migration guard.
- `run.py` orchestrates each city with injected dependencies, so it is testable without network.
- `reconcile.py` compares through a declared map in `config/reconcile.yaml` and writes a generated block into `docs/reconciliation.md`.

**Tech Stack:** Python 3.14 via uv; pyosmium 4; osmium-tool 1.19 (CLI); shapely 2; pyproj; pyogrio (GPKG reading, no geopandas); httpx (now a runtime dependency); typer; Pydantic v2; SQLite.

**Spec:** `docs/superpowers/specs/2026-10-01-velometer-m2-design.md`. Executors also read `docs/research/m2-data-sources-2026-10-01.md`, the source of every code and URL in this plan, verified on 2026-10-01.

## Global Constraints

- **Gate:** `uv run ruff format --check . && uv run ruff check . && uv run pytest`. It must be green at every commit.
- **The default pytest pass has no network.** Network tests are `@pytest.mark.slow`. Tests needing the `osmium` binary use `@pytest.mark.skipif(shutil.which("osmium") is None, reason="osmium-tool not installed")`, never a silent pass.
- **Lengths only in the city's projected EPSG.** Use `velometer.pipeline.geometry.Projector` / `require_projected`.
- **Tag values are `;`-split with `velometer.pipeline.tags.parts`;** a condition holds if any part matches. Never compare whole values.
- **Never type OSM ids, GISCO, NUTS or FUA codes from memory.** Every code in this plan is copied from the research doc. A slow test asserts that each one selects exactly one feature.
- **`data/` and `velometer.sqlite` are gitignored.** Never commit downloaded or derived data files. `docs/review/*` may hold small rendered results.
- **Never write any email address into any file or header.** The contact is the optional `VELOMETER_CONTACT` env var, appended to the User-Agent only if set.
- **Commits:** stage explicit paths only. The message ends with exactly one trailer line, `Assisted-by: Claude:<your own model id>`. Never `Co-Authored-By` or `Claude-Session`. Don't change git config.
- **Bash** calls need `dangerouslyDisableSandbox: true`: bubblewrap is broken on this machine.
- **Python style:** ruff line-length 100; match the existing code. Frozen dataclasses for pipeline data, Pydantic `_Model` for persisted records.

## Review Focus

1. **Interrupted or corrupt download.** A truncated `.part` file or an md5 mismatch must never be used. A rerun re-downloads. Pinned in Task 4: `test_fetch_md5_mismatch_raises_and_leaves_no_file` and `test_existing_file_with_wrong_md5_is_refetched`.
2. **Rerun with different classifier parameters** (e.g. `--plain-cycleway-on-oneway both_sides`) must not reuse the done run from the default parameters. Pinned in Task 6: `test_run_key_includes_parameters`.
3. **MultiPolygon boundaries** (Copenhagen has islands; holes are possible) must clip correctly, and the 4326 GeoJSON handed to osmium must keep all parts. Pinned in Task 2 (`test_clip_multipolygon_with_hole`) and Task 5 (`test_boundary_geojson_keeps_all_parts`).
4. **A failed city run** must leave no partial result rows. It is recorded as `failed` with the error, the next city still runs, and the next invocation retries it. Pinned in Task 6: `test_failed_run_leaves_no_rows_and_is_retried`.
5. **A way entirely outside the boundary** that osmium's `smart` strategy kept must contribute 0 km to numerators and denominators. Pinned in Task 2: `test_way_outside_boundary_contributes_zero`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/velometer/db.py` (modify) | Schema v2, migration and guard, run repository, results/boundary/external I/O, `open_db` |
| `src/velometer/models.py` (modify) | `Run`, `Metric.per_100k`, optional `Completeness` ids, `City.nuts3_code` |
| `src/velometer/config.py` (modify) | `CityConfig.nuts3_code` |
| `config/cities.yaml` (modify) | Fill `lau_code`, `fua_code`, `nuts3_code` from the research doc |
| `src/velometer/pipeline/read.py` (modify) | Keep only `highway` ways |
| `src/velometer/pipeline/measure.py` (modify) | `boundary=` clipping, completeness |
| `src/velometer/osmium.py` (new) | osmium-tool wrappers |
| `src/velometer/pipeline/extract.py` (new) | Cached boundary snapshot via `osmium extract` |
| `src/velometer/sources/__init__.py`, `download.py`, `geofabrik.py` (new) | HTTP download with md5; Geofabrik region resolution |
| `src/velometer/sources/boundaries.py` (new) | GISCO LAU/FUA, OSM admin fallback, population |
| `src/velometer/run.py` (new) | `run_city` orchestration, run key, git commit |
| `src/velometer/sources/external.py` (new) | figures.csv, QECIO and BikeNetKit loaders |
| `config/external/figures.csv` (new) | Curated, cited external figures |
| `src/velometer/reconcile.py` (new), `config/reconcile.yaml` (new) | Gap computation and the markdown block |
| `docs/reconciliation.md` (new) | Generated tables plus hand-written explanations |
| `src/velometer/cli.py` (modify) | New commands |
| `scripts/render_m2_results.py` (new) | Results chart and table |
| `docs/adr/0004…`, `0007…` (modify) | GISCO/URAU codes and population rule; DuckDB measurement |

---

### Task 1: Schema v2, migration guard, run repository

**Files:**
- Modify: `src/velometer/db.py`, `src/velometer/models.py`, `src/velometer/config.py`, `config/cities.yaml`, `src/velometer/cli.py` (the `init` command uses `open_db`)
- Test: `tests/test_db.py` (extend)

**Interfaces:**
- Consumes: `MeasureResult` (`velometer.pipeline.measure`) with fields `tier_lengths`, `road_lengths`, `duplicates: list[DuplicateFlag]`, `dual_pairs: list[DualPair]`, `completeness: list[Completeness]` (added in Task 2; Task 1 tests build it explicitly), and `Metric`.
- Produces:
  - `SCHEMA_VERSION = 2`; `class SchemaError(Exception)`.
  - `open_db(path) -> contextmanager[sqlite3.Connection]` (connects, enables FKs, closes).
  - `create_schema(conn)`.
  - `RunKey` (frozen dataclass: `city_id, osm_timestamp, boundary_kind, boundary_sha256, classifier_version, classifier_parameters`).
  - `find_done_run(conn, key) -> int | None`.
  - `start_run(conn, key, *, git_commit, region_md5) -> int`.
  - `complete_run(conn, run_id, city_id, result, metrics) -> None` (one transaction: all rows plus status `done`).
  - `fail_run(conn, run_id, error) -> None`.
  - `latest_done_run(conn, city_id, boundary_kind) -> int | None`.
  - `fetch_run_results(conn, run_id) -> RunResults(tier_lengths, road_lengths, metrics, completeness, osm_timestamp, city_id)`.
  - `upsert_boundary(conn, Boundary)`; `fetch_boundary(conn, city_id, kind) -> Boundary | None`.
  - `set_population(conn, city_id, Population)`.
  - `replace_external_figures(conn, source, figures: list[ExternalFigure])` (delete that source's rows, then insert).
  - `fetch_external_figures(conn, city_id) -> list[ExternalFigure]`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_db.py`)

```python
import sqlite3

import pytest

from velometer.db import (
    SCHEMA_VERSION,
    RunKey,
    SchemaError,
    complete_run,
    create_schema,
    fail_run,
    fetch_external_figures,
    fetch_run_results,
    find_done_run,
    latest_done_run,
    open_db,
    replace_external_figures,
    start_run,
    upsert_cities,
)
from velometer.models import Completeness, ExternalFigure, Metric, RoadLength, TierLength
from velometer.pipeline.measure import MeasureResult, PlainOnewayReport
from velometer.pipeline.types import DualPair, DuplicateFlag

KEY = RunKey("berlin", "2026-09-30T20:22:42Z", "lau", "abc", "v1", '{"p":"x"}')


def _result():
    return MeasureResult(
        tier_lengths=[TierLength(tier="A", subtype=None, length_basis="per_side",
                                 length_km=2.0, n_ways=3)],
        road_lengths=[RoadLength(road_class=c, length_km=10.0) for c in
                      ("main_excl_motorway", "main_incl_motorway", "main_incl_motorway_raw",
                       "all_public")],
        duplicates=[DuplicateFlag(1, 2, "right", 0.9, 4.0)],
        dual_pairs=[DualPair(5, (6,), 0.8)],
        classified=[],
        unknown_values={},
        plain_oneway=PlainOnewayReport("traffic_side", "both_sides", 0, 0.0, {}),
        completeness=[Completeness(tier="A", share_with_width=0.5, share_with_surface=1.0,
                                   share_with_segregated=0.0)],
    )


def _metrics():
    return [Metric(preset="ours_headline", length_basis="per_side", value=20.0,
                   numerator_km=2.0, denominator_km=10.0, per_100k=0.05)]


@pytest.fixture
def conn(tmp_path, cities):
    with open_db(tmp_path / "v.sqlite") as c:
        create_schema(c)
        upsert_cities(c, cities)
        yield c


@pytest.fixture
def cities():
    from velometer.config import default_config_dir, load_cities

    return load_cities(default_config_dir() / "cities.yaml")


def test_schema_guard_refuses_newer_db(tmp_path):
    with open_db(tmp_path / "v.sqlite") as c:
        c.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        with pytest.raises(SchemaError, match="newer"):
            create_schema(c)


def test_v1_db_without_results_migrates_and_keeps_cities(tmp_path, cities):
    path = tmp_path / "v.sqlite"
    c = sqlite3.connect(path)
    c.executescript(
        "CREATE TABLE cities (id TEXT PRIMARY KEY, name TEXT NOT NULL, country_iso2 TEXT NOT "
        "NULL, lau_code TEXT, fua_code TEXT, osm_relation_id INTEGER NOT NULL, epsg INTEGER NOT "
        "NULL, geofabrik_region TEXT NOT NULL, population_value INTEGER, population_year "
        "INTEGER, population_source TEXT);"
        "CREATE TABLE runs (id INTEGER PRIMARY KEY, started_at TEXT NOT NULL);"
        "INSERT INTO cities VALUES ('berlin','Berlin','DE',NULL,NULL,62422,25833,"
        "'europe/germany/berlin',NULL,NULL,NULL);"
        "PRAGMA user_version = 1;"
    )
    c.close()
    with open_db(path) as c:
        create_schema(c)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert c.execute("SELECT id FROM cities").fetchall() == [("berlin",)]
        cols = {r[1] for r in c.execute("PRAGMA table_info(runs)")}
        assert {"city_id", "classifier_parameters", "boundary_sha256"} <= cols


def test_v1_db_with_results_refuses_to_migrate(tmp_path):
    path = tmp_path / "v.sqlite"
    c = sqlite3.connect(path)
    c.executescript(
        "CREATE TABLE runs (id INTEGER PRIMARY KEY, started_at TEXT NOT NULL);"
        "INSERT INTO runs VALUES (1, 'x'); PRAGMA user_version = 1;"
    )
    c.close()
    with open_db(path) as c, pytest.raises(SchemaError, match="results"):
        create_schema(c)


def test_run_lifecycle_and_results_roundtrip(conn):
    assert find_done_run(conn, KEY) is None
    rid = start_run(conn, KEY, git_commit="deadbeef", region_md5="m")
    complete_run(conn, rid, "berlin", _result(), _metrics())
    assert find_done_run(conn, KEY) == rid
    assert latest_done_run(conn, "berlin", "lau") == rid
    res = fetch_run_results(conn, rid)
    assert res.metrics[0].per_100k == pytest.approx(0.05)
    assert res.tier_lengths[0].length_km == 2.0
    assert res.completeness[0].share_with_width == 0.5
    kinds = sorted(r[0] for r in conn.execute("SELECT kind FROM duplicates"))
    assert kinds == ["dual_carriageway", "parallel"]


def test_failed_run_is_not_done_and_writes_no_results(conn):
    rid = start_run(conn, KEY, git_commit="deadbeef", region_md5="m")
    fail_run(conn, rid, "boom")
    assert find_done_run(conn, KEY) is None
    assert conn.execute("SELECT status, error FROM runs").fetchall() == [("failed", "boom")]
    assert conn.execute("SELECT COUNT(*) FROM tier_lengths").fetchone()[0] == 0


def test_complete_run_is_atomic(conn):
    rid = start_run(conn, KEY, git_commit="deadbeef", region_md5="m")
    bad = _metrics() + _metrics()  # duplicate (run, city, preset) violates the primary key
    with pytest.raises(sqlite3.IntegrityError):
        complete_run(conn, rid, "berlin", _result(), bad)
    assert conn.execute("SELECT COUNT(*) FROM tier_lengths").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM runs").fetchone()[0] == "running"


def test_replace_external_figures_is_idempotent(conn):
    fig = ExternalFigure(city_id="berlin", source="clean_cities_2025",
                         metric_name="protected_km", value=925, unit="km",
                         reference_date=None, network_scope="whole_network",
                         length_basis="unknown", source_url="https://x", retrieved_at="2026-10-01")
    for _ in range(2):
        replace_external_figures(conn, "clean_cities_2025", [fig])
    assert len(fetch_external_figures(conn, "berlin")) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with `ImportError: cannot import name 'RunKey'`. (`PlainOnewayReport` exists; `MeasureResult` lacks `completeness`, which this task adds as a field defaulting to an empty list.)

- [ ] **Step 3: Implement**

`models.py` changes:

```python
class City(_Model):
    ...
    nuts3_code: str | None = None  # NUTS3 unit, used for QECIO matching and population fallback


class Run(_Model):
    id: int | None = None
    city_id: str
    started_at: datetime
    finished_at: datetime | None = None
    classifier_version: str
    classifier_parameters: str  # canonical JSON (sorted keys)
    git_commit: str
    osm_timestamp: str
    region_md5: str
    boundary_kind: Literal["lau", "fua", "osm_admin", "none"]
    boundary_sha256: str
    status: Literal["running", "done", "failed"]
    error: str | None = None


class Metric(_Model):
    ...  # existing fields
    per_100k: float | None = None  # preset numerator km per 100k residents


class Completeness(_Model):
    run_id: int | None = None
    city_id: str | None = None
    tier: str
    share_with_width: float
    share_with_surface: float
    share_with_segregated: float
```

`config.py`: add `nuts3_code: str | None = None` to `CityConfig`.

`config/cities.yaml`: add `lau_code`, `fua_code`, `nuts3_code` per city, all copied from the research doc §1–§2 and §5. Replace the header comment line "lau_code / fua_code are filled in M2 (GISCO)" with "lau_code = GISCO LAU 2024 GISCO_ID; fua_code = URAU 2024 FUA code; nuts3_code = NUTS 2024 (see docs/research/m2-data-sources-2026-10-01.md)".

| City | lau_code | fua_code | nuts3_code |
|---|---|---|---|
| berlin | `DE_11000000` | `DE001F` | `DE300` |
| paris | `FR_75056` | `FR001F` | `FR101` |
| vienna | `AT_90001` | `AT001F` | `AT130` |
| copenhagen | `DK_101` | `DK001F` | `DK011` |
| wroclaw | `PL_1003021056401` | `PL004F` | `PL514` |

`MeasureResult` in `pipeline/measure.py` gains `completeness: list[Completeness] = field(default_factory=list)` as its last field (import `field` from dataclasses; Task 2 fills it).

`db.py`. Replace the schema and add the repository:

```python
"""SQLite schema and repository functions (ADR 0007: SQLite is canonical)."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from velometer.config import CityConfig
from velometer.models import (
    Boundary, City, Completeness, ExternalFigure, Metric, Population, RoadLength, TierLength,
)

SCHEMA_VERSION = 2
_RESULT_TABLES = ("duplicates", "completeness", "metrics", "road_lengths", "tier_lengths", "runs")


class SchemaError(Exception):
    """The database schema cannot be used or migrated safely."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cities (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, country_iso2 TEXT NOT NULL,
  lau_code TEXT, fua_code TEXT, nuts3_code TEXT, osm_relation_id INTEGER NOT NULL,
  epsg INTEGER NOT NULL, geofabrik_region TEXT NOT NULL,
  population_value INTEGER, population_year INTEGER, population_source TEXT
);
CREATE TABLE IF NOT EXISTS boundaries (
  city_id TEXT NOT NULL REFERENCES cities(id),
  kind TEXT NOT NULL CHECK (kind IN ('lau','fua','osm_admin')),
  source TEXT NOT NULL, source_version TEXT NOT NULL, area_km2 REAL NOT NULL,
  path TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY (city_id, kind)
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY, city_id TEXT NOT NULL REFERENCES cities(id),
  started_at TEXT NOT NULL, finished_at TEXT,
  classifier_version TEXT NOT NULL, classifier_parameters TEXT NOT NULL,
  git_commit TEXT NOT NULL, osm_timestamp TEXT NOT NULL, region_md5 TEXT NOT NULL,
  boundary_kind TEXT NOT NULL CHECK (boundary_kind IN ('lau','fua','osm_admin','none')),
  boundary_sha256 TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running','done','failed')), error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS runs_done_key ON runs (
  city_id, osm_timestamp, boundary_kind, boundary_sha256, classifier_version,
  classifier_parameters) WHERE status = 'done';
CREATE TABLE IF NOT EXISTS tier_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL REFERENCES cities(id),
  tier TEXT NOT NULL CHECK (tier IN ('A','B','C','D','E','excluded')),
  subtype TEXT NOT NULL DEFAULT '',
  length_basis TEXT NOT NULL CHECK (length_basis IN ('per_side','qecio_weighted')),
  length_km REAL NOT NULL, n_ways INTEGER NOT NULL,
  PRIMARY KEY (run_id, city_id, tier, subtype, length_basis)
);
CREATE TABLE IF NOT EXISTS road_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL REFERENCES cities(id),
  road_class TEXT NOT NULL CHECK (road_class IN
    ('main_excl_motorway','main_incl_motorway','main_incl_motorway_raw','all_public')),
  length_km REAL NOT NULL, PRIMARY KEY (run_id, city_id, road_class)
);
CREATE TABLE IF NOT EXISTS metrics (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL REFERENCES cities(id),
  preset TEXT NOT NULL,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('per_side','qecio_weighted')),
  value REAL, numerator_km REAL NOT NULL, denominator_km REAL NOT NULL, per_100k REAL,
  PRIMARY KEY (run_id, city_id, preset)
);
CREATE TABLE IF NOT EXISTS completeness (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL REFERENCES cities(id),
  tier TEXT NOT NULL, share_with_width REAL NOT NULL, share_with_surface REAL NOT NULL,
  share_with_segregated REAL NOT NULL, PRIMARY KEY (run_id, city_id, tier)
);
CREATE TABLE IF NOT EXISTS external_figures (
  id INTEGER PRIMARY KEY, city_id TEXT NOT NULL REFERENCES cities(id), source TEXT NOT NULL,
  metric_name TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, reference_date TEXT,
  network_scope TEXT NOT NULL,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('streckenlaenge','reallaenge','unknown')),
  source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS duplicates (
  run_id INTEGER NOT NULL REFERENCES runs(id),
  kind TEXT NOT NULL CHECK (kind IN ('parallel','dual_carriageway')),
  way_id_separate INTEGER NOT NULL, way_id_road INTEGER NOT NULL,
  side TEXT NOT NULL DEFAULT '',
  overlap_share REAL NOT NULL, distance_m REAL NOT NULL, resolved INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (run_id, kind, way_id_separate, way_id_road, side)
);
"""


@contextmanager
def open_db(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def connect(path: Path) -> sqlite3.Connection:  # kept for M1 callers and tests
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _tables(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _migrate_1_to_2(conn: sqlite3.Connection) -> None:
    present = _tables(conn)
    for t in _RESULT_TABLES:
        if t in present and conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]:
            raise SchemaError(f"v1 database has results in {t!r}; refusing to migrate")
    for t in (*_RESULT_TABLES, "external_figures"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    if "cities" in present:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cities)")}
        if "nuts3_code" not in cols:
            conn.execute("ALTER TABLE cities ADD COLUMN nuts3_code TEXT")


_MIGRATIONS = {1: _migrate_1_to_2}


def create_schema(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise SchemaError(
            f"database schema v{current} is newer than this velometer (v{SCHEMA_VERSION})"
        )
    with conn:
        for v in range(max(current, 1), SCHEMA_VERSION):
            if current:  # a fresh database (user_version 0) needs no migration
                _MIGRATIONS[v](conn)
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
```

Note that `executescript` issues its own COMMIT. Keep the migration plus DDL idempotent rather than relying on transaction rollback. The tests above pin the observable behaviour.

`upsert_cities` / `fetch_cities` add `nuts3_code` to the column list and the `ON CONFLICT` update.

The run repository:

```python
@dataclass(frozen=True)
class RunKey:
    city_id: str
    osm_timestamp: str
    boundary_kind: str
    boundary_sha256: str
    classifier_version: str
    classifier_parameters: str  # canonical JSON: json.dumps(params, sort_keys=True)


@dataclass(frozen=True)
class RunResults:
    run_id: int
    city_id: str
    osm_timestamp: str
    tier_lengths: list[TierLength]
    road_lengths: list[RoadLength]
    metrics: list[Metric]
    completeness: list[Completeness]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def canonical_parameters(params: dict) -> str:
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def find_done_run(conn, key: RunKey) -> int | None:
    row = conn.execute(
        "SELECT id FROM runs WHERE status='done' AND city_id=? AND osm_timestamp=? AND "
        "boundary_kind=? AND boundary_sha256=? AND classifier_version=? AND "
        "classifier_parameters=?",
        (key.city_id, key.osm_timestamp, key.boundary_kind, key.boundary_sha256,
         key.classifier_version, key.classifier_parameters),
    ).fetchone()
    return row[0] if row else None


def start_run(conn, key: RunKey, *, git_commit: str, region_md5: str) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (city_id, started_at, classifier_version, classifier_parameters, "
            "git_commit, osm_timestamp, region_md5, boundary_kind, boundary_sha256, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,'running')",
            (key.city_id, _now(), key.classifier_version, key.classifier_parameters, git_commit,
             key.osm_timestamp, region_md5, key.boundary_kind, key.boundary_sha256),
        )
    return cur.lastrowid


def fail_run(conn, run_id: int, error: str) -> None:
    with conn:
        conn.execute(
            "UPDATE runs SET status='failed', error=?, finished_at=? WHERE id=?",
            (error, _now(), run_id),
        )


def complete_run(conn, run_id: int, city_id: str, result, metrics: list[Metric]) -> None:
    """Write every result row and mark the run done, atomically."""
    with conn:  # one transaction: commit on success, rollback on any exception
        conn.executemany(
            "INSERT INTO tier_lengths VALUES (?,?,?,?,?,?,?)",
            [(run_id, city_id, t.tier, t.subtype or "", t.length_basis, t.length_km, t.n_ways)
             for t in result.tier_lengths],
        )
        conn.executemany(
            "INSERT INTO road_lengths VALUES (?,?,?,?)",
            [(run_id, city_id, r.road_class, r.length_km) for r in result.road_lengths],
        )
        conn.executemany(
            "INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?)",
            [(run_id, city_id, m.preset, m.length_basis, m.value, m.numerator_km,
              m.denominator_km, m.per_100k) for m in metrics],
        )
        conn.executemany(
            "INSERT INTO completeness VALUES (?,?,?,?,?,?)",
            [(run_id, city_id, c.tier, c.share_with_width, c.share_with_surface,
              c.share_with_segregated) for c in result.completeness],
        )
        rows = [(run_id, "parallel", d.standalone_way_id, d.road_way_id, d.road_side,
                 d.overlap_share, d.distance_m) for d in result.duplicates]
        rows += [(run_id, "dual_carriageway", p.way_id, partner, "", p.overlap_share, 0.0)
                 for p in result.dual_pairs for partner in p.partner_ids]
        conn.executemany(
            "INSERT OR IGNORE INTO duplicates (run_id, kind, way_id_separate, way_id_road, side, "
            "overlap_share, distance_m) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        conn.execute(
            "UPDATE runs SET status='done', finished_at=? WHERE id=?", (_now(), run_id)
        )
```

The dual-carriageway rows store `distance_m = 0.0` because `DualPair` carries no distance. Document this in the function docstring.

`latest_done_run`: `SELECT id FROM runs WHERE status='done' AND city_id=? AND boundary_kind=? ORDER BY osm_timestamp DESC, id DESC LIMIT 1`.

`fetch_run_results` reads the four tables back into models: `subtype ''` becomes `None`, and `osm_timestamp` and `city_id` come from `runs`.

`upsert_boundary`: `INSERT ... ON CONFLICT(city_id, kind) DO UPDATE SET` every column. `fetch_boundary` returns a model or None.

`set_population`: `UPDATE cities SET population_value=?, population_year=?, population_source=? WHERE id=?`.

`replace_external_figures`: in one `with conn:`, `DELETE FROM external_figures WHERE source=?`, then insert every figure. Dates go in as ISO strings. `fetch_external_figures` returns the models for a city.

`cli.py` `init`: use `with open_db(db) as conn:`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_db.py tests/test_cli.py -v`, then the full gate.
Expected: PASS. Then red-proof: delete the `current > SCHEMA_VERSION` branch, check that `test_schema_guard_refuses_newer_db` fails, and restore it.

- [ ] **Step 5: Commit**

```bash
git add src/velometer/db.py src/velometer/models.py src/velometer/config.py config/cities.yaml \
  src/velometer/pipeline/measure.py src/velometer/cli.py tests/test_db.py
git commit -m "feat: schema v2 with migration guard, run keys and result repository

Assisted-by: Claude:<model-id>"
```

---

### Task 2: Highway-only reading, boundary clipping, completeness

**Files:**
- Modify: `src/velometer/pipeline/read.py`, `src/velometer/pipeline/measure.py`
- Test: `tests/test_read.py`, `tests/test_measure.py` (extend)

**Interfaces:**
- Consumes: `Projector(epsg).line(coords) -> LineString`; `length_km(geom)` from `pipeline/geometry.py` (check that it works for MultiLineString/GeometryCollection, i.e. that it uses `.length`).
- Produces:
  - `measure(ways, cfg, epsg, boundary: shapely.geometry.base.BaseGeometry | None = None) -> MeasureResult`. `boundary` is a Polygon/MultiPolygon **in the city EPSG**.
  - `MeasureResult.completeness: list[Completeness]`: one per tier A–E present, with shares in [0, 1] weighted by clipped per_side length.
  - `clipped_length_km(line, boundary_prepared, boundary) -> float` (module-level helper).

- [ ] **Step 1: Write the failing tests**

`tests/test_read.py`:

```python
def test_only_highway_ways_are_read(tmp_path):
    osm = tmp_path / "x.osm"
    osm.write_text(
        '<?xml version="1.0"?><osm version="0.6">'
        '<node id="1" lat="52.5" lon="13.4"/><node id="2" lat="52.5" lon="13.41"/>'
        '<way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="cycleway"/></way>'
        '<way id="2"><nd ref="1"/><nd ref="2"/><tag k="building" v="yes"/></way>'
        "</osm>"
    )
    assert [w.id for w in read_ways(osm).ways] == [1]
```

`tests/test_measure.py`:

```python
from shapely import MultiPolygon, Polygon, box

from velometer.pipeline.geometry import Projector


def _proj_box(lon0, lat0, lon1, lat1, epsg=25833):
    p = Projector(epsg)
    ring = p.line(((lon0, lat0), (lon1, lat0), (lon1, lat1), (lon0, lat1), (lon0, lat0)))
    return Polygon(ring.coords)


TRACK = {"highway": "cycleway"}


def test_clip_counts_only_inside_part():
    way = WayRecord(1, TRACK, ((13.40, 52.5), (13.42, 52.5)))
    full = measure([way], CFG, 25833)
    half = measure([way], CFG, 25833, boundary=_proj_box(13.39, 52.49, 13.41, 52.51))
    assert km(half, "A", "per_side") == pytest.approx(km(full, "A", "per_side") / 2, rel=0.01)


def test_way_outside_boundary_contributes_zero():
    road = {"highway": "primary", "cycleway:both": "track"}
    ways = [WayRecord(1, road, ((13.50, 52.5), (13.52, 52.5)))]
    res = measure(ways, CFG, 25833, boundary=_proj_box(13.39, 52.49, 13.41, 52.51))
    assert km(res, "A", "per_side") == 0
    assert road_length(res, "main_excl_motorway") == 0


def test_clip_multipolygon_with_hole():
    outer = _proj_box(13.39, 52.49, 13.43, 52.51)
    hole = _proj_box(13.40, 52.495, 13.41, 52.505)
    other = _proj_box(13.44, 52.49, 13.45, 52.51)
    mp = MultiPolygon([Polygon(outer.exterior.coords, [hole.exterior.coords]), other])
    way = WayRecord(1, TRACK, ((13.38, 52.5), (13.46, 52.5)))  # crosses everything
    full_km = km(measure([way], CFG, 25833), "A", "per_side")
    res = measure([way], CFG, 25833, boundary=mp)
    # inside: 13.39-13.40 + 13.41-13.43 + 13.44-13.45 = 0.04 of 0.08 degrees of longitude
    assert km(res, "A", "per_side") == pytest.approx(full_km * 0.04 / 0.08, rel=0.01)


def test_completeness_shares_are_length_weighted():
    ways = [
        WayRecord(1, {"highway": "cycleway", "width": "2", "surface": "asphalt"},
                  ((13.40, 52.5), (13.42, 52.5))),
        WayRecord(2, {"highway": "cycleway"}, ((13.40, 52.6), (13.41, 52.6))),
        WayRecord(3, {"highway": "primary", "cycleway:right": "track",
                      "cycleway:right:width": "1.5"}, ((13.40, 52.7), (13.41, 52.7))),
    ]
    res = measure(ways, CFG, 25833)
    a = next(c for c in res.completeness if c.tier == "A")
    # widths: way 1 (2 units) + way 3 (1 unit) of 4 units; surface: way 1 only
    assert a.share_with_width == pytest.approx(3 / 4, rel=0.02)
    assert a.share_with_surface == pytest.approx(2 / 4, rel=0.02)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_read.py tests/test_measure.py -v`
Expected: FAIL. The building way is returned; `measure()` has no `boundary` argument; `completeness` is empty.

- [ ] **Step 3: Implement**

`read.py`: replace `if not obj.is_way() or len(obj.tags) == 0:` with `if not obj.is_way() or "highway" not in obj.tags:`. Update the docstring to "Return highway ways…". Some existing `test_read.py` tests rely on non-highway ways being returned: update them to use `highway` tags, and say so in the report.

`measure.py`:

```python
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

COMPLETENESS_KEYS = {
    "width": ("width", "cycleway:width"),
    "surface": ("surface", "cycleway:surface"),
    "segregated": ("segregated", "cycleway:segregated"),
}


def clipped_length_km(line, prepared, boundary: BaseGeometry) -> float:
    if prepared.contains(line):
        return length_km(line)
    if not prepared.intersects(line):
        return 0.0
    return length_km(line.intersection(boundary))


def _completeness(classified, lengths) -> list[Completeness]:
    totals: dict[str, float] = defaultdict(float)
    have: dict[tuple[str, str], float] = defaultdict(float)
    for c in classified:
        if c.tier not in ("A", "B", "C", "D", "E"):
            continue
        length = lengths[c.side.way_id]
        totals[c.tier] += length
        for name, keys in COMPLETENESS_KEYS.items():
            if any(c.side.tags.get(k) for k in keys):
                have[(c.tier, name)] += length
    return [
        Completeness(
            tier=t,
            share_with_width=have[(t, "width")] / total,
            share_with_surface=have[(t, "surface")] / total,
            share_with_segregated=have[(t, "segregated")] / total,
        )
        for t, total in sorted(totals.items())
        if total > 0
    ]
```

In `measure(...)`, add `boundary: BaseGeometry | None = None` and compute:

```python
    if boundary is None:
        lengths = {w.id: length_km(proj.line(w.coords)) for w in ways}
    else:
        prepared = prep(boundary)
        lengths = {
            w.id: clipped_length_km(proj.line(w.coords), prepared, boundary) for w in ways
        }
```

Then pass `completeness=_completeness(classified, lengths)` to `MeasureResult`. Every downstream use already reads `lengths[...]`: the tier sums, the road totals with dual factors, and `_plain_oneway_report`. Dedupe and pairing keep using the full geometry via `proj`. The segregated share is computed for every tier, but it is meaningful only for B; state this in the docstring.

- [ ] **Step 4: Run the tests** (the target tests, then the full gate). Expected: PASS. Red-proof: replace the clipped branch with the unclipped length, check that `test_clip_counts_only_inside_part` and `test_way_outside_boundary_contributes_zero` fail, then restore it.

- [ ] **Step 5: Commit**

```bash
git add src/velometer/pipeline/read.py src/velometer/pipeline/measure.py tests/test_read.py \
  tests/test_measure.py
git commit -m "feat: clip lengths at the boundary, completeness diagnostics, highway-only read

Assisted-by: Claude:<model-id>"
```

---

### Task 3: osmium-tool wrappers and cached boundary snapshots

**Files:**
- Create: `src/velometer/osmium.py`, `src/velometer/pipeline/extract.py`
- Test: `tests/test_osmium.py`

**Interfaces:**
- Produces:
  - `class OsmiumError(RuntimeError)`.
  - `require_osmium() -> str` (the version line).
  - `extract(src: Path, polygon_geojson: Path, dst: Path, strategy: str = "smart") -> Path`.
  - `fileinfo_timestamp(path: Path) -> datetime | None`.
  - `relation_polygon(src: Path, relation_id: int, dst_geojson: Path) -> Path`, which writes a FeatureCollection holding only Polygon/MultiPolygon features.
  - In `extract.py`: `snapshot(region_path: Path, region_md5: str, osm_timestamp: datetime, city_id: str, kind: str, boundary_geojson: Path, boundary_sha256: str, data_dir: Path) -> Path`.

- [ ] **Step 1: Write the failing tests** (`tests/test_osmium.py`)

```python
import json
import shutil
from datetime import UTC, datetime

import osmium as pyosmium
import pytest

from velometer.osmium import OsmiumError, extract, fileinfo_timestamp, relation_polygon
from velometer.pipeline.extract import snapshot
from velometer.pipeline.read import read_ways

needs_osmium = pytest.mark.skipif(
    shutil.which("osmium") is None, reason="osmium-tool not installed"
)
TS = "2026-09-30T20:22:42Z"


def _pbf(path):
    """Two ways: way 1 inside lon 13.40-13.41, way 2 at lon 13.50-13.51."""
    header = pyosmium.io.Header()
    header.set("osmosis_replication_timestamp", TS)
    with pyosmium.SimpleWriter(str(path), header=header) as w:
        for nid, lon in ((1, 13.40), (2, 13.41), (3, 13.50), (4, 13.51)):
            w.add_node(pyosmium.osm.mutable.Node(id=nid, location=(lon, 52.5), version=1))
        for wid, nodes in ((1, [1, 2]), (2, [3, 4])):
            w.add_way(pyosmium.osm.mutable.Way(id=wid, nodes=nodes, tags={"highway": "cycleway"},
                                               version=1))
    return path


def _poly(path):
    ring = [[13.39, 52.49], [13.42, 52.49], [13.42, 52.51], [13.39, 52.51], [13.39, 52.49]]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Polygon", "coordinates": [ring]}}]}))
    return path


@needs_osmium
def test_fileinfo_timestamp_reads_header(tmp_path):
    assert fileinfo_timestamp(_pbf(tmp_path / "r.osm.pbf")) == datetime(
        2026, 9, 30, 20, 22, 42, tzinfo=UTC)


@needs_osmium
def test_extract_keeps_only_ways_inside(tmp_path):
    out = extract(_pbf(tmp_path / "r.osm.pbf"), _poly(tmp_path / "b.geojson"),
                  tmp_path / "o.osm.pbf")
    assert [w.id for w in read_ways(out).ways] == [1]


@needs_osmium
def test_snapshot_is_cached_by_region_and_boundary(tmp_path):
    src, poly = _pbf(tmp_path / "r.osm.pbf"), _poly(tmp_path / "b.geojson")
    ts = datetime(2026, 9, 30, tzinfo=UTC)
    a = snapshot(src, "md5aaaaaaaa", ts, "berlin", "lau", poly, "sha1111111", tmp_path)
    mtime = a.stat().st_mtime_ns
    b = snapshot(src, "md5aaaaaaaa", ts, "berlin", "lau", poly, "sha1111111", tmp_path)
    assert a == b and b.stat().st_mtime_ns == mtime
    c = snapshot(src, "md5aaaaaaaa", ts, "berlin", "lau", poly, "sha2222222", tmp_path)
    assert c != a
    assert not list((tmp_path / "snapshots").glob("*.part*"))


@needs_osmium
def test_osmium_failure_raises_with_stderr(tmp_path):
    with pytest.raises(OsmiumError, match="osmium"):
        extract(tmp_path / "missing.osm.pbf", _poly(tmp_path / "b.geojson"),
                tmp_path / "o.osm.pbf")


@needs_osmium
def test_relation_polygon_writes_only_areas(tmp_path):
    # a closed boundary relation around way 1's square
    path = tmp_path / "rel.osm.pbf"
    with pyosmium.SimpleWriter(str(path)) as w:
        pts = [(10, 13.39, 52.49), (11, 13.42, 52.49), (12, 13.42, 52.51), (13, 13.39, 52.51)]
        for nid, lon, lat in pts:
            w.add_node(pyosmium.osm.mutable.Node(id=nid, location=(lon, lat), version=1))
        w.add_way(pyosmium.osm.mutable.Way(id=20, nodes=[10, 11, 12, 13, 10], version=1))
        w.add_relation(pyosmium.osm.mutable.Relation(
            id=30, members=[("w", 20, "outer")],
            tags={"type": "boundary", "boundary": "administrative"}, version=1))
    out = relation_polygon(path, 30, tmp_path / "rel.geojson")
    feats = json.loads(out.read_text())["features"]
    assert feats and {f["geometry"]["type"] for f in feats} <= {"Polygon", "MultiPolygon"}
```

If pyosmium's mutable-object or Header API differs from the above, adapt the *helper*, never the assertions, and note it in the report. Check with `uv run python -c "import osmium; help(osmium.SimpleWriter)"`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_osmium.py -v`
Expected: FAIL with `ModuleNotFoundError: velometer.osmium`.

- [ ] **Step 3: Implement** `src/velometer/osmium.py`

```python
"""Thin wrappers around the osmium-tool CLI (the only place velometer shells out to osmium)."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

INSTALL_HINT = "osmium-tool not found; install it with: sudo apt install osmium-tool"


class OsmiumError(RuntimeError):
    pass


def _run(*args: str) -> str:
    if shutil.which("osmium") is None:
        raise OsmiumError(INSTALL_HINT)
    proc = subprocess.run(["osmium", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise OsmiumError(f"osmium {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def require_osmium() -> str:
    return _run("--version").splitlines()[0]


def extract(src: Path, polygon_geojson: Path, dst: Path, strategy: str = "smart") -> Path:
    _run("extract", "-p", str(polygon_geojson), "-s", strategy, "--overwrite",
         "-o", str(dst), str(src))
    return dst


def fileinfo_timestamp(path: Path) -> datetime | None:
    raw = _run("fileinfo", "-g", "header.option.osmosis_replication_timestamp",
               str(path)).strip()
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None


def relation_polygon(src: Path, relation_id: int, dst_geojson: Path) -> Path:
    rel = dst_geojson.with_name(dst_geojson.stem + ".rel.osm.pbf")
    _run("getid", "-r", "--overwrite", "-o", str(rel), str(src), f"r{relation_id}")
    raw = dst_geojson.with_name(dst_geojson.stem + ".all.geojson")
    _run("export", "--overwrite", "-f", "geojson", "-o", str(raw), str(rel))
    feats = [f for f in json.loads(raw.read_text())["features"]
             if f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
    if not feats:
        raise OsmiumError(f"relation {relation_id} did not assemble into an area")
    dst_geojson.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    rel.unlink()
    raw.unlink()
    return dst_geojson
```

Check the exact `fileinfo -g` variable name against `osmium fileinfo -e -j <file>` output; osmium 1.19 documents `header.option.<name>`. If it differs, fix the code and keep the test.

`src/velometer/pipeline/extract.py`:

```python
"""Cached per-city snapshots clipped from a region extract (osmium extract, strategy smart)."""

from datetime import datetime
from pathlib import Path

from velometer.osmium import extract


def snapshot(region_path: Path, region_md5: str, osm_timestamp: datetime, city_id: str,
             kind: str, boundary_geojson: Path, boundary_sha256: str, data_dir: Path) -> Path:
    out_dir = data_dir / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = (f"{city_id}_{kind}_{osm_timestamp:%Y%m%d}_{region_md5[:8]}_"
            f"{boundary_sha256[:8]}.osm.pbf")
    dst = out_dir / name
    if dst.exists():
        return dst
    part = out_dir / (name.removesuffix(".osm.pbf") + ".part.osm.pbf")
    extract(region_path, boundary_geojson, part)
    part.replace(dst)
    return dst
```

- [ ] **Step 4: Run the tests and the gate.** Expected: PASS (or SKIPPED, with the reason shown, if osmium is missing; it is installed on this machine). Red-proof: make `snapshot` skip the cache check and check that the mtime assertion fails.

- [ ] **Step 5: Commit**

```bash
git add src/velometer/osmium.py src/velometer/pipeline/extract.py tests/test_osmium.py
git commit -m "feat: osmium-tool wrappers and cached boundary snapshots

Assisted-by: Claude:<model-id>"
```

---

### Task 4: Downloads with md5 and Geofabrik regions

**Files:**
- Create: `src/velometer/sources/__init__.py` (empty docstring), `src/velometer/sources/download.py`, `src/velometer/sources/geofabrik.py`
- Modify: `pyproject.toml`: move `httpx>=0.27` from the dev group to `dependencies`, then run `uv lock`.
- Test: `tests/test_download.py`

**Interfaces:**
- Produces:
  - `user_agent() -> str` (`"velometer/<version>"`, plus `"; <VELOMETER_CONTACT>"` only if that env var is set).
  - `class DownloadError(RuntimeError)`.
  - `md5_of(path) -> str`.
  - `fetch(url, dst, *, md5: str | None = None, client: httpx.Client | None = None, retries: int = 3, backoff_s: float = 5.0) -> Path`.
  - `geofabrik.RegionFile(region, path, url, md5, osm_timestamp: datetime)`.
  - `geofabrik.resolve_dated(region, client) -> str`.
  - `geofabrik.fetch_region(region, data_dir, client=None) -> RegionFile`.

- [ ] **Step 1: Write the failing tests** (`tests/test_download.py`)

```python
import hashlib

import httpx
import pytest

from velometer.sources import download, geofabrik
from velometer.sources.download import DownloadError, fetch, user_agent

BODY = b"x" * 10_000
MD5 = hashlib.md5(BODY).hexdigest()


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_writes_file_and_verifies_md5(tmp_path):
    c = _client(lambda r: httpx.Response(200, content=BODY))
    out = fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c, backoff_s=0)
    assert out.read_bytes() == BODY


def test_fetch_md5_mismatch_raises_and_leaves_no_file(tmp_path):
    c = _client(lambda r: httpx.Response(200, content=b"corrupt"))
    with pytest.raises(DownloadError, match="md5"):
        fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c, backoff_s=0)
    assert list(tmp_path.iterdir()) == []


def test_existing_file_with_right_md5_is_not_refetched(tmp_path):
    (tmp_path / "f.pbf").write_bytes(BODY)
    c = _client(lambda r: pytest.fail("network used"))
    fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c)


def test_existing_file_with_wrong_md5_is_refetched(tmp_path):
    (tmp_path / "f.pbf").write_bytes(b"stale")
    c = _client(lambda r: httpx.Response(200, content=BODY))
    fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c, backoff_s=0)
    assert (tmp_path / "f.pbf").read_bytes() == BODY


def test_fetch_retries_then_succeeds(tmp_path):
    calls = []

    def handler(r):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, content=BODY)

    fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=_client(handler), backoff_s=0)
    assert len(calls) == 3


def test_user_agent_has_contact_only_when_set(monkeypatch):
    monkeypatch.delenv("VELOMETER_CONTACT", raising=False)
    assert user_agent().startswith("velometer/") and ";" not in user_agent()
    monkeypatch.setenv("VELOMETER_CONTACT", "https://example.org/velometer")
    assert user_agent().endswith("; https://example.org/velometer")


def test_resolve_dated_follows_latest_redirect():
    def handler(r):
        assert r.method == "HEAD"
        return httpx.Response(307, headers={"location": "berlin-260930.osm.pbf"})

    url = geofabrik.resolve_dated("europe/germany/berlin", _client(handler))
    assert url == "https://download.geofabrik.de/europe/germany/berlin-260930.osm.pbf"


def test_fetch_region_reads_md5_and_header_timestamp(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    def handler(r):
        if r.method == "HEAD":
            return httpx.Response(307, headers={"location": "berlin-260930.osm.pbf"})
        if r.url.path.endswith(".md5"):
            return httpx.Response(200, text=f"{MD5}  berlin-260930.osm.pbf\n")
        return httpx.Response(200, content=BODY)

    ts = datetime(2026, 9, 30, 20, 22, 42, tzinfo=UTC)
    monkeypatch.setattr(geofabrik, "fileinfo_timestamp", lambda p: ts)
    rf = geofabrik.fetch_region("europe/germany/berlin", tmp_path, client=_client(handler))
    assert rf.md5 == MD5 and rf.osm_timestamp == ts
    assert rf.path == tmp_path / "raw" / "berlin-260930.osm.pbf"
```

- [ ] **Step 2: Run the tests to verify they fail.** Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`download.py`:

```python
"""HTTP downloads: streamed to .part, md5-verified, atomically renamed, bounded retries."""

import hashlib
import os
import time
from importlib.metadata import version
from pathlib import Path

import httpx


class DownloadError(RuntimeError):
    pass


def user_agent() -> str:
    base = f"velometer/{version('velometer')}"
    contact = os.environ.get("VELOMETER_CONTACT")
    return f"{base}; {contact}" if contact else base


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def new_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": user_agent()}, timeout=120,
                        follow_redirects=True)


def fetch(url: str, dst: Path, *, md5: str | None = None, client: httpx.Client | None = None,
          retries: int = 3, backoff_s: float = 5.0) -> Path:
    if dst.exists() and (md5 is None or md5_of(dst) == md5):
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    own = client is None
    client = client or new_client()
    try:
        for attempt in range(1, retries + 1):
            try:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with part.open("wb") as f:
                        for chunk in resp.iter_bytes(1 << 20):
                            f.write(chunk)
                break
            except httpx.HTTPError as e:
                part.unlink(missing_ok=True)
                if attempt == retries:
                    raise DownloadError(f"{url}: {e}") from e
                time.sleep(backoff_s * attempt)
        if md5 is not None and md5_of(part) != md5:
            part.unlink()
            raise DownloadError(f"{url}: md5 mismatch (expected {md5})")
        part.replace(dst)
        return dst
    finally:
        if own:
            client.close()
```

`geofabrik.py`:

```python
"""Geofabrik public extracts: resolve the dated file behind -latest, fetch it, read its time."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlparse

import httpx

from velometer.osmium import fileinfo_timestamp
from velometer.sources.download import fetch, new_client

BASE = "https://download.geofabrik.de"


@dataclass(frozen=True)
class RegionFile:
    region: str
    path: Path
    url: str
    md5: str
    osm_timestamp: datetime


def resolve_dated(region: str, client: httpx.Client) -> str:
    latest = f"{BASE}/{region}-latest.osm.pbf"
    resp = client.head(latest, follow_redirects=False)
    if resp.status_code in (301, 302, 307, 308):
        return urljoin(latest, resp.headers["location"])
    resp.raise_for_status()
    return latest


def fetch_region(region: str, data_dir: Path, client: httpx.Client | None = None) -> RegionFile:
    own = client is None
    client = client or new_client()
    try:
        url = resolve_dated(region, client)
        md5_resp = client.get(url + ".md5")
        md5_resp.raise_for_status()
        md5 = md5_resp.text.split()[0]
        dst = data_dir / "raw" / PurePosixPath(urlparse(url).path).name
        fetch(url, dst, md5=md5, client=client)
    finally:
        if own:
            client.close()
    ts = fileinfo_timestamp(dst)
    if ts is None:
        raise RuntimeError(f"{dst}: no osmosis_replication_timestamp in the PBF header")
    return RegionFile(region, dst, url, md5, ts)
```

- [ ] **Step 4: Run the tests and the gate.** Red-proof: drop the md5 comparison and check that `test_fetch_md5_mismatch_raises_and_leaves_no_file` fails.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/velometer/sources/__init__.py \
  src/velometer/sources/download.py src/velometer/sources/geofabrik.py tests/test_download.py
git commit -m "feat: md5-verified downloads and Geofabrik region resolution

Assisted-by: Claude:<model-id>"
```

---

### Task 5: Boundaries (GISCO LAU/FUA, OSM admin) and population

**Files:**
- Create: `src/velometer/sources/boundaries.py`
- Modify: `pyproject.toml` (add `pyogrio>=0.10`; `uv lock`), `docs/adr/0004-two-boundary-layers.md`
- Test: `tests/test_boundaries.py`

**Interfaces:**
- Consumes: `CityConfig` (with `lau_code`, `fua_code`, `nuts3_code`, `epsg`, `osm_relation_id`); `download.fetch`; `osmium.relation_polygon`; `models.Boundary`, `models.Population`.
- Produces:
  - `LAU_URL`, `FUA_URL`, `GISCO_VERSION = "LAU 2024 / URAU 2024"`.
  - `BoundaryRecord(boundary: Boundary, geojson_path: Path, polygon: BaseGeometry)`, where the polygon is in the city EPSG.
  - `select_feature(gpkg: Path, field: str, code: str) -> tuple[BaseGeometry, dict]` (source CRS 3035; raises unless exactly one match).
  - `write_boundary(city, kind, geom_3035, source, data_dir) -> BoundaryRecord`.
  - `city_boundary(city, kind, data_dir, region_path=None) -> tuple[BoundaryRecord, Population | None]` (population only for `lau`).
  - `load_boundary_polygon(geojson_path, epsg) -> BaseGeometry`.
  - `population(city, lau_props, fetch_json=...) -> Population | None`.

- [ ] **Step 1: Write the failing tests** (`tests/test_boundaries.py`)

```python
import json

import numpy as np
import pyogrio
import pytest
import shapely
from shapely import MultiPolygon, Polygon

from velometer.config import CityConfig
from velometer.sources import boundaries as b

CITY = CityConfig(id="berlin", name="Berlin", country_iso2="DE", epsg=25833,
                  geofabrik_region="europe/germany/berlin", osm_relation_id=62422,
                  lau_code="DE_11000000", fua_code="DE001F", nuts3_code="DE300")


def _gpkg(path, rows):
    """rows: list of (code, geometry_in_3035, pop)."""
    geoms = np.array([shapely.to_wkb(g) for _, g, _ in rows], dtype=object)
    fields = {"GISCO_ID": np.array([c for c, _, _ in rows], dtype=object),
              "POP_2024": np.array([p for _, _, p in rows], dtype=np.int64)}
    pyogrio.write(str(path), geoms, fields, geometry_type="MultiPolygon", crs="EPSG:3035",
                  driver="GPKG")
    return path


def _sq(x, y, d=1000):
    return Polygon([(x, y), (x + d, y), (x + d, y + d), (x, y + d)])


def test_select_feature_requires_exactly_one(tmp_path):
    g = _gpkg(tmp_path / "l.gpkg", [("DE_11000000", MultiPolygon([_sq(4.5e6, 3.27e6)]), 5),
                                     ("DE_X", MultiPolygon([_sq(4.6e6, 3.27e6)]), 1)])
    geom, props = b.select_feature(g, "GISCO_ID", "DE_11000000")
    assert props["POP_2024"] == 5 and geom.area == pytest.approx(1e6)
    with pytest.raises(ValueError, match="0 features"):
        b.select_feature(g, "GISCO_ID", "nope")


def test_boundary_geojson_keeps_all_parts(tmp_path):
    mp = MultiPolygon([_sq(4.5e6, 3.27e6), _sq(4.51e6, 3.27e6)])
    rec = b.write_boundary(CITY, "lau", mp, "GISCO", tmp_path)
    gj = json.loads(rec.geojson_path.read_text())
    assert gj["features"][0]["geometry"]["type"] == "MultiPolygon"
    assert len(gj["features"][0]["geometry"]["coordinates"]) == 2
    assert rec.boundary.area_km2 == pytest.approx(2.0, rel=0.02)  # in the city EPSG
    assert rec.polygon.area == pytest.approx(2e6, rel=0.02)
    assert len(rec.boundary.sha256) == 64


def test_population_uses_lau_value_else_nuts3_fallback():
    pop = b.population(CITY, {"POP_2024": 3782202}, fetch_json=lambda url: pytest.fail("net"))
    assert (pop.value, pop.year, pop.source) == (3782202, 2024, "GISCO LAU 2024 POP_2024")
    paris = CITY.model_copy(update={"id": "paris", "nuts3_code": "FR101"})
    payload = {"value": {"0": 2084894}}
    pop = b.population(paris, {"POP_2024": 0}, fetch_json=lambda url: payload)
    assert pop.value == 2084894 and "demo_r_pjangrp3" in pop.source and pop.year == 2024


@pytest.mark.slow
def test_every_pilot_city_code_selects_exactly_one_feature(tmp_path_factory):
    """Network: download GISCO once; assert the rule that each configured code is unique."""
    from velometer.config import default_config_dir, load_cities

    data = tmp_path_factory.mktemp("data")
    lau, fua = b.fetch_gisco(data)
    for city in load_cities(default_config_dir() / "cities.yaml"):
        b.select_feature(lau, "GISCO_ID", city.lau_code)
        b.select_feature(fua, b.FUA_FIELD, city.fua_code)
```

- [ ] **Step 2: Run the tests to verify they fail.** Expected: `ModuleNotFoundError` (pyogrio missing, then the module missing).

- [ ] **Step 3: Implement** `src/velometer/sources/boundaries.py`

```python
"""City boundaries: GISCO LAU 2024 (default), URAU 2024 FUA, OSM admin relation (fallback)."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pyogrio
import shapely
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from velometer.config import CityConfig
from velometer.models import Boundary, Population
from velometer.osmium import relation_polygon
from velometer.sources.download import fetch, new_client

GISCO = "https://gisco-services.ec.europa.eu/distribution/v2"
LAU_URL = f"{GISCO}/lau/gpkg/LAU_RG_01M_2024_3035.gpkg"
FUA_URL = f"{GISCO}/urau/gpkg/URAU_RG_100K_2024_3035_FUA.gpkg"
FUA_FIELD = "URAU_CODE"
GISCO_VERSION = {"lau": "LAU 2024 (1:1M)", "fua": "URAU 2024 FUA (1:100k)"}
EUROSTAT_POP = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_pjangrp3"
    "?geo={nuts3}&sex=T&age=TOTAL&unit=NR&time=2024&format=JSON"
)


@dataclass(frozen=True)
class BoundaryRecord:
    boundary: Boundary
    geojson_path: Path
    polygon: BaseGeometry  # city EPSG


def fetch_gisco(data_dir: Path) -> tuple[Path, Path]:
    d = data_dir / "external" / "gisco"
    return fetch(LAU_URL, d / "LAU_RG_01M_2024_3035.gpkg"), fetch(
        FUA_URL, d / "URAU_RG_100K_2024_3035_FUA.gpkg")


def select_feature(gpkg: Path, field: str, code: str) -> tuple[BaseGeometry, dict]:
    escaped = code.replace("'", "''")
    meta, _, geoms, values = pyogrio.raw.read(str(gpkg), where=f"{field} = '{escaped}'")
    if len(geoms) != 1:
        raise ValueError(f"{gpkg.name}: {field}={code!r} matched {len(geoms)} features")
    props = {name: values[i][0] for i, name in enumerate(meta["fields"])}
    return shapely.from_wkb(geoms[0]), props


def _to(geom: BaseGeometry, src: int, dst: int) -> BaseGeometry:
    tf = Transformer.from_crs(src, dst, always_xy=True)
    return transform(tf.transform, geom)


def write_boundary(city: CityConfig, kind: str, geom_3035: BaseGeometry, source: str,
                   data_dir: Path, src_epsg: int = 3035) -> BoundaryRecord:
    wgs = _to(geom_3035, src_epsg, 4326)
    out = data_dir / "boundaries" / f"{city.id}_{kind}.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    feature = {"type": "Feature", "properties": {"city_id": city.id, "kind": kind},
               "geometry": json.loads(shapely.to_geojson(wgs))}
    out.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
    projected = _to(geom_3035, src_epsg, city.epsg)
    record = Boundary(
        city_id=city.id, kind=kind, source=source,
        source_version=GISCO_VERSION.get(kind, "OSM admin relation"),
        area_km2=projected.area / 1e6, path=str(out),
        sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
    )
    return BoundaryRecord(record, out, projected)


def load_boundary_polygon(geojson_path: Path, epsg: int) -> BaseGeometry:
    feats = json.loads(geojson_path.read_text())["features"]
    geom = shapely.union_all([shapely.from_geojson(json.dumps(f["geometry"])) for f in feats])
    return _to(geom, 4326, epsg)


def population(city: CityConfig, lau_props: dict,
               fetch_json: Callable[[str], dict] | None = None) -> Population | None:
    value = int(lau_props.get("POP_2024") or 0)
    if value > 0:
        return Population(value=value, year=2024, source="GISCO LAU 2024 POP_2024")
    if not city.nuts3_code:
        return None
    url = EUROSTAT_POP.format(nuts3=city.nuts3_code)
    data = (fetch_json or _get_json)(url)
    return Population(value=int(next(iter(data["value"].values()))), year=2024,
                      source=f"Eurostat demo_r_pjangrp3 {city.nuts3_code} 2024")


def _get_json(url: str) -> dict:
    with new_client() as c:
        r = c.get(url)
        r.raise_for_status()
        return r.json()


def city_boundary(city: CityConfig, kind: str, data_dir: Path,
                  region_path: Path | None = None) -> tuple[BoundaryRecord, Population | None]:
    if kind in ("lau", "fua"):
        lau, fua = fetch_gisco(data_dir)
        gpkg, field, code = ((lau, "GISCO_ID", city.lau_code) if kind == "lau"
                             else (fua, FUA_FIELD, city.fua_code))
        if not code:
            raise ValueError(f"{city.id}: no {kind}_code configured")
        geom, props = select_feature(gpkg, field, code)
        rec = write_boundary(city, kind, geom, "Eurostat GISCO", data_dir)
        return rec, (population(city, props) if kind == "lau" else None)
    if region_path is None:
        raise ValueError("osm_admin boundaries need the city's Geofabrik region file")
    gj = relation_polygon(region_path, city.osm_relation_id,
                          data_dir / "boundaries" / f"{city.id}_osm_admin.raw.geojson")
    geom = load_boundary_polygon(gj, 4326)
    rec = write_boundary(city, "osm_admin", geom, f"OSM relation {city.osm_relation_id}",
                         data_dir, src_epsg=4326)
    gj.unlink()
    return rec, None
```

Before trusting `FUA_FIELD = "URAU_CODE"` and the `pyogrio.raw.read` return shape, verify both against the real files, and fix the code (not the tests) if they differ:
- `uv run python -c "import pyogrio; print(pyogrio.read_info('data/external/gisco/URAU_RG_100K_2024_3035_FUA.gpkg'))"` after one `fetch_gisco`;
- `help(pyogrio.raw.read)`.

`docs/adr/0004-two-boundary-layers.md`: append a `## Notes (2026-10-01, M2)` section with these points:
- The LAU source is `LAU_RG_01M_2024_3035.gpkg`, keyed by `GISCO_ID`.
- The FUA source is URAU 2024, keyed by the `…F` codes. `DE001L1` is the retired scheme.
- Population is LAU `POP_2024`. When it is 0 or missing (all French LAUs), it comes from Eurostat `demo_r_pjangrp3` for the NUTS3 unit identical to the commune (Paris = FR101).
- Berlin's LAU figure (census-based) differs from NUTS3 (register): about 3.3%.
- The OSM admin fallback is assembled offline from the region extract with `osmium getid -r` + `export`.

- [ ] **Step 4: Run the tests and the gate.** Expected: PASS; the slow test is deselected. Red-proof: let `select_feature` accept more than one match and check that the 0-feature test still fails, while a 2-match case would pass. Add the assertion `with pytest.raises(ValueError, match="2 features")` by duplicating a row code, and check that it fails without the guard.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/velometer/sources/boundaries.py tests/test_boundaries.py \
  docs/adr/0004-two-boundary-layers.md
git commit -m "feat: GISCO LAU/FUA and OSM admin boundaries with population

Assisted-by: Claude:<model-id>"
```

---

### Task 6: Run orchestration and CLI

**Files:**
- Create: `src/velometer/run.py`
- Modify: `src/velometer/cli.py`
- Test: `tests/test_run.py`, `tests/test_cli.py` (extend)

**Interfaces:**
- Consumes everything above:
  - `fetch_region`;
  - `city_boundary`, `load_boundary_polygon`;
  - `snapshot`;
  - `read_ways`;
  - `measure(..., boundary=)`;
  - `compute_metrics`;
  - from db: `RunKey`, `canonical_parameters`, `find_done_run`, `start_run`, `complete_run`, `fail_run`, `upsert_boundary`, `set_population`, `fetch_boundary`, `fetch_cities`, `open_db`, `create_schema`, `upsert_cities`.
- Produces:
  - `RunDeps` (a frozen dataclass of callables: `fetch_region`, `city_boundary`, `snapshot`, `read_ways`; defaults are the real ones).
  - `RunOutcome(city_id, status: Literal["done","skipped","failed"], run_id: int | None, error: str | None)`.
  - `git_commit() -> str` (`"<sha>"` or `"<sha>-dirty"`; `"unknown"` outside git).
  - `run_city(conn, city, *, data_dir, config_dir, boundary_kind="lau", classifier="v1", parameters: dict[str, str] | None = None, force=False, deps=RunDeps()) -> RunOutcome`.
  - `with_per_100k(metrics, population_value) -> list[Metric]`.

- [ ] **Step 1: Write the failing tests** (`tests/test_run.py`)

```python
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from shapely import box

from velometer import run as R
from velometer.config import default_config_dir, load_cities
from velometer.db import create_schema, open_db, upsert_cities
from velometer.models import Boundary, Population
from velometer.pipeline.read import read_ways
from velometer.sources.boundaries import BoundaryRecord
from velometer.sources.geofabrik import RegionFile

CFG_DIR = default_config_dir()
CITY = next(c for c in load_cities(CFG_DIR / "cities.yaml") if c.id == "berlin")
MINI = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"


def _deps(tmp_path, calls, read=None):
    def fetch_region(region, data_dir):
        calls.append("fetch")
        return RegionFile(region, MINI, "u", "md5", datetime(2026, 9, 30, tzinfo=UTC))

    def city_boundary(city, kind, data_dir, region_path=None):
        b = Boundary(city_id=city.id, kind=kind, source="t", source_version="t",
                     area_km2=1e6, path=str(tmp_path / "b.geojson"), sha256="s" * 64)
        return BoundaryRecord(b, tmp_path / "b.geojson", box(-1e9, -1e9, 1e9, 1e9)), \
            Population(value=100_000, year=2024, source="t")

    def snapshot(*args, **kw):
        calls.append("snapshot")
        return MINI

    return R.RunDeps(fetch_region=fetch_region, city_boundary=city_boundary,
                     snapshot=snapshot, read_ways=read or read_ways)


@pytest.fixture
def conn(tmp_path):
    with open_db(tmp_path / "v.sqlite") as c:
        create_schema(c)
        upsert_cities(c, load_cities(CFG_DIR / "cities.yaml"))
        yield c


def _run(conn, tmp_path, deps, **kw):
    return R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=deps, **kw)


def test_run_persists_and_second_run_is_skipped(conn, tmp_path):
    calls = []
    first = _run(conn, tmp_path, _deps(tmp_path, calls))
    assert first.status == "done"
    second = _run(conn, tmp_path, _deps(tmp_path, calls))
    assert second.status == "skipped" and second.run_id == first.run_id
    assert calls.count("snapshot") == 1  # no rework when skipped
    per_100k = conn.execute(
        "SELECT per_100k FROM metrics WHERE preset='ours_headline'").fetchone()[0]
    num = conn.execute(
        "SELECT numerator_km FROM metrics WHERE preset='ours_headline'").fetchone()[0]
    assert per_100k == pytest.approx(num)  # population is exactly 100k


def test_run_key_includes_parameters(conn, tmp_path):
    a = _run(conn, tmp_path, _deps(tmp_path, []))
    b = _run(conn, tmp_path, _deps(tmp_path, []),
             parameters={"plain_cycleway_on_oneway": "both_sides"})
    assert b.status == "done" and b.run_id != a.run_id


def test_force_reruns(conn, tmp_path):
    a = _run(conn, tmp_path, _deps(tmp_path, []))
    b = _run(conn, tmp_path, _deps(tmp_path, []), force=True)
    assert b.status == "done" and b.run_id != a.run_id


def test_failed_run_leaves_no_rows_and_is_retried(conn, tmp_path):
    def boom(path):
        raise RuntimeError("disk on fire")

    failed = _run(conn, tmp_path, _deps(tmp_path, [], read=boom))
    assert failed.status == "failed" and "disk on fire" in failed.error
    assert conn.execute("SELECT COUNT(*) FROM tier_lengths").fetchone()[0] == 0
    retried = _run(conn, tmp_path, _deps(tmp_path, []))
    assert retried.status == "done"


def test_git_commit_marks_dirty_tree(monkeypatch):
    outputs = {("rev-parse", "HEAD"): "abc123\n", ("status", "--porcelain"): " M x\n"}
    monkeypatch.setattr(R, "_git", lambda *a: outputs[a])
    assert R.git_commit() == "abc123-dirty"
```

CLI test (append to `tests/test_cli.py`):

```python
def test_results_command_prints_table_from_db(tmp_path, monkeypatch):
    from velometer import run as R

    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--db", str(db)]).exit_code == 0
    # reuse the stubbed deps from test_run via monkeypatching the default deps
    import tests.test_run as tr

    monkeypatch.setattr(R, "RunDeps", lambda: tr._deps(tmp_path, []))
    out = runner.invoke(app, ["run", "--cities", "berlin", "--db", str(db),
                              "--data", str(tmp_path)])
    assert out.exit_code == 0, out.output
    assert "berlin" in out.output and "done" in out.output
    table = runner.invoke(app, ["results", "--db", str(db)])
    assert table.exit_code == 0
    assert re.search(r"^berlin\s+2026-09-30\s+\d+\.\d", table.output, re.M), table.output
```

(If importing `tests.test_run` fails because `tests` is not a package, add an empty `tests/__init__.py`. Record that ruling in the report.)

- [ ] **Step 2: Run the tests to verify they fail.** Expected: `ModuleNotFoundError: velometer.run`.

- [ ] **Step 3: Implement** `src/velometer/run.py`

```python
"""Orchestrate one persisted city run: region -> boundary -> snapshot -> measure -> SQLite."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from velometer.config import CityConfig, load_classifier, load_presets
from velometer.db import (
    RunKey, canonical_parameters, complete_run, fail_run, find_done_run, set_population,
    start_run, upsert_boundary,
)
from velometer.models import Metric
from velometer.pipeline.extract import snapshot as _snapshot
from velometer.pipeline.measure import compute_metrics, measure
from velometer.pipeline.read import read_ways as _read_ways
from velometer.sources.boundaries import city_boundary as _city_boundary
from velometer.sources.geofabrik import fetch_region as _fetch_region


@dataclass(frozen=True)
class RunDeps:
    fetch_region: Callable = _fetch_region
    city_boundary: Callable = _city_boundary
    snapshot: Callable = _snapshot
    read_ways: Callable = _read_ways


@dataclass(frozen=True)
class RunOutcome:
    city_id: str
    status: Literal["done", "skipped", "failed"]
    run_id: int | None = None
    error: str | None = None


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def git_commit() -> str:
    try:
        sha = _git("rev-parse", "HEAD").strip()
        dirty = bool(_git("status", "--porcelain").strip())
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


def with_per_100k(metrics: list[Metric], population: int | None) -> list[Metric]:
    if not population:
        return metrics
    return [m.model_copy(update={"per_100k": m.numerator_km / population * 100_000})
            for m in metrics]


def run_city(conn, city: CityConfig, *, data_dir: Path, config_dir: Path,
             boundary_kind: str = "lau", classifier: str = "v1",
             parameters: dict[str, str] | None = None, force: bool = False,
             deps: RunDeps | None = None) -> RunOutcome:
    deps = deps or RunDeps()
    cfg = load_classifier(config_dir / "classifier" / f"{classifier}.yaml")
    if parameters:
        cfg = cfg.with_parameters(**parameters)
    presets = load_presets(config_dir / "presets.yaml", cfg)
    region = deps.fetch_region(city.geofabrik_region, data_dir)
    rec, pop = deps.city_boundary(city, boundary_kind, data_dir, region_path=region.path)
    upsert_boundary(conn, rec.boundary)
    if pop is not None:
        set_population(conn, city.id, pop)
    key = RunKey(
        city_id=city.id,
        osm_timestamp=region.osm_timestamp.isoformat().replace("+00:00", "Z"),
        boundary_kind=boundary_kind,
        boundary_sha256=rec.boundary.sha256,
        classifier_version=cfg.version,
        classifier_parameters=canonical_parameters(cfg.parameters.model_dump()),
    )
    done = find_done_run(conn, key)
    if done is not None and not force:
        return RunOutcome(city.id, "skipped", done)
    if done is not None:  # force: retire the old done row so the unique index admits the new one
        with conn:
            conn.execute("UPDATE runs SET status='failed', error='superseded by --force' "
                         "WHERE id=?", (done,))
    run_id = start_run(conn, key, git_commit=git_commit(), region_md5=region.md5)
    try:
        snap = deps.snapshot(region.path, region.md5, region.osm_timestamp, city.id,
                             boundary_kind, rec.geojson_path, rec.boundary.sha256, data_dir)
        ways = deps.read_ways(snap).ways
        result = measure(ways, cfg, city.epsg, boundary=rec.polygon)
        metrics = with_per_100k(compute_metrics(result, presets), pop.value if pop else None)
        complete_run(conn, run_id, city.id, result, metrics)
    except Exception as e:  # noqa: BLE001 - recorded on the run row, then the next city runs
        fail_run(conn, run_id, f"{type(e).__name__}: {e}")
        return RunOutcome(city.id, "failed", run_id, f"{type(e).__name__}: {e}")
    return RunOutcome(city.id, "done", run_id)
```

Note: `--force` marks the superseded done run `failed` with the error `superseded by --force`. Its result rows stay but are no longer "latest". Document this in the docstring.

Also: when population comes from the DB rather than the fetch, it is `None` here for FUA/osm_admin runs, so per_100k stays None for those. That is acceptable for M2 (FUA runs are M3).

CLI additions in `cli.py`. All new commands take `--db` (default `velometer.sqlite`) and `--data` (default `data`), use `open_db` + `create_schema`, and load cities from `--config-dir`.
- `boundaries fetch [--city X] [--kind lau|fua|osm_admin|all]` (default `all`; osm_admin needs the region, so it fetches the region first).
- `osm fetch [--city X]`: prints the region, path, OSM timestamp and md5.
- `classify`: keep the M1 `--file/--epsg` mode. Add `--city X [--boundary lau] [--force] [--plain-cycleway-on-oneway ...]`, which calls `run_city`. `--file` and `--city` are mutually exclusive; giving both exits 2 with a message.
- `run --cities all|a,b [--boundary lau] [--force]`: loops `run_city`, prints one line per city (`<city> <status> run=<id> [error]`), and exits 1 if any city failed.
- `results [--boundary lau]`: one row per city with a done run. Columns: `city`, `osm_date`, `headline` (ours_headline value), `ecf_qecio`, `clean_cities`, `A_km`, `B_km`, `C_km`, `D_km`, `E_km` (per_side), `main_km` (`main_excl_motorway`), `headline_per_100k`.

Use typer sub-apps for `boundaries` and `osm`: `boundaries_app = typer.Typer(); app.add_typer(boundaries_app, name="boundaries")`.

- [ ] **Step 4: Run the tests and the gate.** Red-proof: remove `classifier_parameters` from the key comparison in `find_done_run`, check that `test_run_key_includes_parameters` fails, then restore it.

- [ ] **Step 5: Commit**

```bash
git add src/velometer/run.py src/velometer/cli.py tests/test_run.py tests/test_cli.py
git commit -m "feat: persisted, resumable city runs and boundaries/osm/run/results commands

Assisted-by: Claude:<model-id>"
```

---

### Task 7: External figures (curated CSV, QECIO, BikeNetKit)

**Files:**
- Create: `config/external/figures.csv`, `src/velometer/sources/external.py`
- Modify: `src/velometer/cli.py` (`external load`)
- Test: `tests/test_external.py`, `tests/fixtures/external/qecio_summary_head.csv`

**Interfaces:**
- Consumes: `ExternalFigure`; `replace_external_figures`; `download.fetch`; `CityConfig.nuts3_code`.
- Produces:
  - `load_figures_csv(path) -> list[ExternalFigure]` (validates every row).
  - `QECIO_URL`; `qecio_figures(csv_path, cities) -> list[ExternalFigure]`.
  - `BIKENETKIT_FILES` (name → md5); `BIKENETKIT_IDS` (city id → BikeNetKit cityid).
  - `bikenetkit_figures(zip_dir, cities) -> list[ExternalFigure]`.
  - `load_all(conn, data_dir, config_dir, *, qecio: bool, bikenetkit: bool) -> dict[str, int]` (rows per source).

- [ ] **Step 1: Write the curated `config/external/figures.csv`**

The values come from `docs/research/m2-data-sources-2026-10-01.md` §6 and the handover §10 pitfalls 5 and 6. `retrieved_at` is `2026-10-01` for every row.

**Header:**
```
city_id,source,metric_name,value,unit,reference_date,network_scope,length_basis,source_url,retrieved_at,note
```

**Clean Cities 2025 rows** (source `clean_cities_2025`, `reference_date` 2025-05-14, `length_basis` unknown). The `source_url` for the PDF rows is `https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf`; their note is "Table 5, report p.16; city-submitted vs OSM source not stated per city".
- berlin: `protected_km` 925, `network_km` 5350, `protected_share_pct` 17.
- paris: 822, 1700, 48.
- copenhagen: 397, 926, 43.
- wroclaw: 355, 1769, 20.
- vienna: `protected_km` 384, `network_km` 2844, `protected_share_pct` 14, with `network_scope` `whole_network`.
- vienna, the July 2025 web correction: `protected_km` 625.1, `network_km` 2844, `protected_share_pct` 22.0.
  - `network_scope` is `incl_traffic_calmed_restricted_access`.
  - `source_url` is `https://cleancitiescampaign.org/city-ranking-2025-cycling-infrastructure/`.
  - The note is "web correction July 2025; adds traffic-calmed roads with restricted motor access (city-submitted); not like-for-like with protected".

**Berlin official 2025 rows** (`metric_name` `new_cycle_infra_km`, `reference_date` 2025-12-31, `length_basis` unknown, `source_url` empty):

| source | value | network_scope | note |
|---|---|---|---|
| `official` | 21.2 | `whole_network` | "Senate Fortschrittsbericht via dpa, Sep 2026; basis unknown; per handover research 27 Sep 2026; re-verify before publication" |
| `official` | 20.5 | `whole_network` | "Senate preliminary, Dec 2025; per handover research; re-verify" |
| `official` | 17.3 | `vorrangnetz_ergaenzungsnetz` | "infraVelo; per handover research; re-verify" |
| `changing_cities` | 25.2 | `whole_network` | "Changing Cities monitor; per handover research; re-verify" |

- [ ] **Step 2: Write the failing tests** (`tests/test_external.py`)

```python
import csv
import zipfile
from pathlib import Path

import numpy as np
import pyogrio
import pytest
import shapely
from shapely import LineString

from velometer.config import default_config_dir, load_cities
from velometer.sources import external as X

CFG = default_config_dir()
CITIES = load_cities(CFG / "cities.yaml")
FIX = Path(__file__).parent / "fixtures" / "external"


def test_curated_figures_all_validate_and_are_cited():
    figs = X.load_figures_csv(CFG / "external" / "figures.csv")
    assert {f.city_id for f in figs} <= {c.id for c in CITIES}
    for f in figs:
        assert f.source_url or "re-verify" in f.note, f
    cc = {(f.city_id, f.metric_name, f.network_scope): f.value for f in figs
          if f.source == "clean_cities_2025"}
    assert cc[("berlin", "protected_km", "whole_network")] == 925
    assert cc[("vienna", "protected_share_pct", "incl_traffic_calmed_restricted_access")] == 22.0


def test_qecio_rows_map_by_nuts3_and_carry_data_date():
    figs = X.qecio_figures(FIX / "qecio_summary_head.csv", CITIES)
    berlin = {f.metric_name: f.value for f in figs if f.city_id == "berlin"}
    assert berlin["main_roads_km"] == pytest.approx(2149.623)
    assert berlin["cycle_tracks_km"] == pytest.approx(679.471)
    assert all(str(f.reference_date) == "2024-01-10" for f in figs if f.city_id == "berlin")
    assert not [f for f in figs if f.city_id == "paris"]  # not in the 2-row fixture


def test_bikenetkit_network_km_is_measured_in_city_epsg(tmp_path):
    # a gpkg "edges" layer with one 1 km line near Berlin (EPSG:4326 lon/lat)
    gpkg = tmp_path / "berlin_de.gpkg"
    line = LineString([(13.4, 52.5), (13.4147, 52.5)])
    pyogrio.write(str(gpkg), np.array([shapely.to_wkb(line)], dtype=object),
                  {"osmid": np.array([1])}, geometry_type="LineString", crs="EPSG:4326",
                  layer="edges", driver="GPKG")
    with zipfile.ZipFile(tmp_path / "bike_networks.zip", "w") as z:
        z.write(gpkg, "bike_networks/berlin_de.gpkg")
    figs = X.bikenetkit_figures(tmp_path, [c for c in CITIES if c.id == "berlin"])
    (f,) = figs
    assert f.metric_name == "bike_network_km" and f.value == pytest.approx(1.0, abs=0.01)
```

`tests/fixtures/external/qecio_summary_head.csv`: copy the **real header line** of `Summary-all.csv` plus the Berlin DE300 row and one non-pilot row. Download it once with `curl -s https://european-cyclists-federation.github.io/Download/Summary/Summary-all.csv | head -1` and `grep -m1 DE300`, plus any other row, so the parser is tested against the real column names. Commit the 3-line file; the data is small and ODbL/OSM-derived, so add an attribution comment in the test docstring.

- [ ] **Step 3: Run the tests to verify they fail.** Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement** `src/velometer/sources/external.py`

```python
"""External comparison figures: curated CSV, ECF QECIO v2.10 summary, BikeNetKit (Zenodo)."""

import csv
import zipfile
from datetime import date
from pathlib import Path

import pyogrio
import shapely

from velometer.config import CityConfig
from velometer.models import ExternalFigure
from velometer.pipeline.geometry import Projector, length_km
from velometer.sources.download import fetch

QECIO_URL = "https://european-cyclists-federation.github.io/Download/Summary/Summary-all.csv"
QECIO_COLUMNS = {  # metric_name -> Summary-all.csv column (v2.10)
    "main_roads_km": "overview-main-road-network",
    "cycle_tracks_km": "overview-cycle_tracks-km",
    "cycle_lanes_km": "overview-cycle_lanes-km",
    "shared_pedestrians_km": "overview-shared_pedestrians-km",
    "total_cycle_infra_km": "overview-total-cycle-infrastructure",
}
ZENODO = "https://zenodo.org/api/records/22271229/files/{name}/content"
BIKENETKIT_FILES = {
    "bike_networks.zip": "ffccda3c4fa40953a31d4cb8d88930d5",
    "boundaries.zip": "655c204a16f17b644e6a22d40cf1f68a",
}
BIKENETKIT_IDS = {"berlin": "berlin_de", "paris": "paris_fr", "vienna": "vienna_at",
                  "copenhagen": "copenhagen_dk", "wroclaw": "wroclaw_pl"}
RETRIEVED = date(2026, 10, 1)


def load_figures_csv(path: Path) -> list[ExternalFigure]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return [ExternalFigure.model_validate({**r, "reference_date": r["reference_date"] or None})
            for r in rows]


def qecio_figures(csv_path: Path, cities: list[CityConfig]) -> list[ExternalFigure]:
    by_nuts = {c.nuts3_code: c for c in cities if c.nuts3_code}
    out = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            city = by_nuts.get(row["NUTS_ID"])
            if city is None:
                continue
            ref = date.fromisoformat(row["Date"].strip()[:10])
            for metric, col in QECIO_COLUMNS.items():
                out.append(ExternalFigure(
                    city_id=city.id, source="qecio_v2_10", metric_name=metric,
                    value=float(row[col]), unit="km", reference_date=ref,
                    network_scope=f"nuts3_{row['NUTS_ID']}", length_basis="unknown",
                    source_url=QECIO_URL, retrieved_at=RETRIEVED,
                    note=f"NUTS3 {row['NUTS_ID']} ({row['City']}); QECIO halves "
                         "unidirectional infrastructure",
                ))
    return out


def bikenetkit_figures(zip_dir: Path, cities: list[CityConfig]) -> list[ExternalFigure]:
    out = []
    with zipfile.ZipFile(zip_dir / "bike_networks.zip") as z:
        for city in cities:
            cid = BIKENETKIT_IDS.get(city.id)
            if cid is None:
                continue
            target = zip_dir / "bikenetkit" / f"{cid}.gpkg"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(f"bike_networks/{cid}.gpkg"))
            meta, _, geoms, _ = pyogrio.raw.read(str(target), layer="edges")
            src_epsg = int(meta["crs"].split(":")[-1])
            proj = Projector(city.epsg)
            total = 0.0
            for wkb in geoms:
                g = shapely.from_wkb(wkb)
                if src_epsg != 4326:
                    raise ValueError(f"{target.name}: expected EPSG:4326, got {meta['crs']}")
                for part in getattr(g, "geoms", [g]):
                    total += length_km(proj.line(tuple(part.coords)))
            out.append(ExternalFigure(
                city_id=city.id, source="bikenetkit_v1", metric_name="bike_network_km",
                value=total, unit="km", reference_date=None,
                network_scope="bikenetkit_bike_network", length_basis="unknown",
                source_url="https://doi.org/10.5281/zenodo.22271229", retrieved_at=RETRIEVED,
                note="OSM/Nominatim city boundary; includes cycleway, designated paths, "
                     "living streets, cycle streets and side tracks (no lanes); undirected "
                     "edges counted once; snapshot 'summer 2026' (unverified)",
            ))
    return out
```

`load_all(conn, data_dir, config_dir, *, qecio, bikenetkit)`:
- Load the curated CSV and call `replace_external_figures` once per source in it (`clean_cities_2025`, `official`, `changing_cities`).
- If `qecio`: `fetch(QECIO_URL, data_dir/"external"/"qecio"/"Summary-all.csv")` (no md5 published), then `replace_external_figures(conn, "qecio_v2_10", ...)`.
- If `bikenetkit`: fetch both zips with their md5 into `data_dir/"external"/"bikenetkit"`, then `replace_external_figures(conn, "bikenetkit_v1", ...)`.
- Return the row counts.

Before relying on the BikeNetKit gpkg `edges` layer name and its CRS, verify both on the real file with `pyogrio.list_layers` / `read_info` after downloading, and adapt the code if they differ (osmnx `save_graph_geopackage` writes `nodes`/`edges` in EPSG:4326). Report what you found.

CLI: `external load [--figures PATH] [--qecio/--no-qecio] [--bikenetkit/--no-bikenetkit]`, with both flags defaulting to on. It prints the rows per source.

- [ ] **Step 5: Run the tests and the gate.** Red-proof: map QECIO by the `City` column instead of `NUTS_ID` and check that the Berlin test fails.

- [ ] **Step 6: Commit**

```bash
git add config/external/figures.csv src/velometer/sources/external.py src/velometer/cli.py \
  tests/test_external.py tests/fixtures/external/qecio_summary_head.csv
git commit -m "feat: curated external figures, QECIO v2.10 and BikeNetKit loaders

Assisted-by: Claude:<model-id>"
```

---

### Task 8: Reconcile and docs/reconciliation.md

**Files:**
- Create: `src/velometer/reconcile.py`, `config/reconcile.yaml`, `docs/reconciliation.md`
- Modify: `src/velometer/cli.py` (`reconcile`)
- Test: `tests/test_reconcile.py`

**Interfaces:**
- Consumes: `latest_done_run`, `fetch_run_results` (`RunResults`), `fetch_external_figures`; `ExternalFigure`.
- Produces:
  - `Gap` (frozen dataclass: `city_id, comparison, key, ours: float | None, theirs: float, unit, gap_pct: float | None, flagged: bool, informational: bool, tags: tuple[str, ...], source: str, reference_date: date | None, note: str`).
  - `load_comparisons(path) -> list[Comparison]`.
  - `ours_value(results, spec) -> float | None`.
  - `gaps_for(results, figures, comparisons, *, threshold, date_gap_days, mismatch) -> list[Gap]`.
  - `reconcile_city(conn, city_id, config_path, boundary_kind="lau") -> list[Gap]`.
  - `render_block(gaps_by_city) -> str`.
  - `write_report(path, gaps_by_city)`: replaces only the text between the markers.
  - `missing_explanations(path, gaps) -> list[str]`.

- [ ] **Step 1: Write `config/reconcile.yaml`**

```yaml
# Comparison map (spec §3). ours: either {preset} (metric value), {road_class} (km),
# or {tiers, basis, exclude?} (sum of tier km). Gap = (ours - theirs) / theirs.
threshold: 0.20
date_gap_days: 365
comparisons:
  - id: cc_ratio
    external: {source: clean_cities_2025, metric_name: protected_share_pct}
    ours: {preset: clean_cities_2025}
  - id: cc_km
    external: {source: clean_cities_2025, metric_name: protected_km}
    ours: {tiers: [A, B], basis: per_side}
  - id: cc_network_km
    external: {source: clean_cities_2025, metric_name: network_km}
    ours: {road_class: all_public}
  - id: qecio_main_km
    external: {source: qecio_v2_10, metric_name: main_roads_km}
    ours: {road_class: main_incl_motorway_raw}
  - id: qecio_tracks_km
    external: {source: qecio_v2_10, metric_name: cycle_tracks_km}
    ours: {tiers: [A, B/segregated], basis: qecio_weighted}
  - id: qecio_lanes_km
    external: {source: qecio_v2_10, metric_name: cycle_lanes_km}
    ours: {tiers: [C, D], basis: qecio_weighted}
  - id: qecio_shared_km
    external: {source: qecio_v2_10, metric_name: shared_pedestrians_km}
    ours: {tiers: [B], exclude: [B/segregated], basis: qecio_weighted}
  - id: qecio_total_km
    external: {source: qecio_v2_10, metric_name: total_cycle_infra_km}
    ours: {tiers: [A, B, C, D], basis: qecio_weighted}
    tags: [definition_mismatch]   # QECIO total also counts limited-access roads
  - id: bnk_network_km
    external: {source: bikenetkit_v1, metric_name: bike_network_km}
    ours: {tiers: [A, B, E], basis: per_side}
    tags: [definition_mismatch, boundary_mismatch]
  - id: official_new_km
    external: {source: [official, changing_cities], metric_name: new_cycle_infra_km}
    informational: true   # new km in a year, not stock: listed, never flagged
boundary_mismatch:
  qecio_v2_10: [copenhagen]   # DK011 Byen København != Københavns Kommune
```

- [ ] **Step 2: Write the failing tests** (`tests/test_reconcile.py`)

```python
from datetime import date
from pathlib import Path

import pytest

from velometer import reconcile as RC
from velometer.db import RunResults
from velometer.models import ExternalFigure, Metric, RoadLength, TierLength

CFG = Path(__file__).resolve().parents[1] / "config" / "reconcile.yaml"


def _results():
    t = lambda tier, km, basis="per_side", sub=None: TierLength(  # noqa: E731
        tier=tier, subtype=sub, length_basis=basis, length_km=km, n_ways=1)
    return RunResults(
        run_id=1, city_id="berlin", osm_timestamp="2026-09-30T20:22:42Z",
        tier_lengths=[t("A", 600), t("B", 300), t("B", 100, sub="segregated"),
                      t("A", 300, "qecio_weighted"), t("B", 100, "qecio_weighted", "segregated"),
                      t("B", 150, "qecio_weighted")],
        road_lengths=[RoadLength(road_class="all_public", length_km=5000)],
        metrics=[Metric(preset="clean_cities_2025", length_basis="per_side", value=20.0,
                        numerator_km=1000, denominator_km=5000)],
        completeness=[],
    )


def _fig(source, metric, value, scope="whole_network", ref=date(2025, 5, 14)):
    return ExternalFigure(city_id="berlin", source=source, metric_name=metric, value=value,
                          unit="km", reference_date=ref, network_scope=scope,
                          length_basis="unknown", source_url="u", retrieved_at=date(2026, 10, 1))


def test_ours_value_sums_tiers_with_subtype_and_exclude():
    comps = {c.id: c for c in RC.load_comparisons(CFG)}
    r = _results()
    assert RC.ours_value(r, comps["cc_km"].ours) == 1000  # A 600 + B 300 + B/segregated 100
    assert RC.ours_value(r, comps["qecio_tracks_km"].ours) == 400  # A 300 + B/seg 100
    assert RC.ours_value(r, comps["qecio_shared_km"].ours) == 150  # B minus B/segregated
    assert RC.ours_value(r, comps["cc_ratio"].ours) == 20.0


def test_gaps_flag_over_threshold_and_tag_date_gap():
    comps = RC.load_comparisons(CFG)
    figs = [_fig("clean_cities_2025", "protected_km", 925),          # +8% -> not flagged
            _fig("clean_cities_2025", "network_km", 5350),           # -6.5%
            _fig("clean_cities_2025", "protected_share_pct", 17),     # +17.6%
            _fig("qecio_v2_10", "cycle_tracks_km", 679.471, "nuts3_DE300", date(2024, 1, 10))]
    gaps = {g.comparison: g for g in RC.gaps_for(_results(), figs, comps, threshold=0.2,
                                                date_gap_days=365, mismatch={})}
    assert not gaps["cc_km"].flagged
    assert gaps["qecio_tracks_km"].flagged  # 400 vs 679 = -41%
    assert "date_gap" in gaps["qecio_tracks_km"].tags
    assert gaps["cc_km"].gap_pct == pytest.approx((1000 - 925) / 925)


def test_informational_comparisons_are_never_flagged():
    comps = RC.load_comparisons(CFG)
    figs = [_fig("official", "new_cycle_infra_km", 21.2)]
    (g,) = RC.gaps_for(_results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={})
    assert g.informational and not g.flagged and g.ours is None


def test_write_report_replaces_only_generated_block_and_check_finds_missing(tmp_path):
    md = tmp_path / "reconciliation.md"
    md.write_text("# R\n\nintro\n\n<!-- reconcile:begin -->\nold\n<!-- reconcile:end -->\n\n"
                  "## Explanations\n\n### berlin/qecio_tracks_km\n\nBecause.\n")
    comps = RC.load_comparisons(CFG)
    figs = [_fig("qecio_v2_10", "cycle_tracks_km", 679.471, "nuts3_DE300"),
            _fig("qecio_v2_10", "cycle_lanes_km", 10, "nuts3_DE300")]
    gaps = RC.gaps_for(_results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={})
    RC.write_report(md, {"berlin": gaps})
    text = md.read_text()
    assert "old" not in text and "intro" in text and "Because." in text
    assert "qecio_tracks_km" in text.split("<!-- reconcile:end -->")[0]
    assert RC.missing_explanations(md, gaps) == ["berlin/qecio_lanes_km"]
```

- [ ] **Step 3: Run the tests to verify they fail.** Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement** `src/velometer/reconcile.py`

```python
"""Compare our latest run per city with external figures (config/reconcile.yaml)."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from velometer.db import RunResults, fetch_external_figures, fetch_run_results, latest_done_run
from velometer.models import ExternalFigure

BEGIN, END = "<!-- reconcile:begin -->", "<!-- reconcile:end -->"


@dataclass(frozen=True)
class Comparison:
    id: str
    sources: tuple[str, ...]
    metric_name: str
    ours: dict | None
    informational: bool
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Gap:
    city_id: str
    comparison: str
    key: str
    ours: float | None
    theirs: float
    unit: str
    gap_pct: float | None
    flagged: bool
    informational: bool
    tags: tuple[str, ...]
    source: str
    reference_date: date | None
    note: str


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def load_comparisons(path: Path) -> list[Comparison]:
    out = []
    for c in load_config(path)["comparisons"]:
        src = c["external"]["source"]
        out.append(Comparison(
            id=c["id"], sources=tuple(src if isinstance(src, list) else [src]),
            metric_name=c["external"]["metric_name"], ours=c.get("ours"),
            informational=bool(c.get("informational", False)), tags=tuple(c.get("tags", [])),
        ))
    return out


def _matches(t, entries) -> bool:
    for e in entries:
        tier, _, sub = e.partition("/")
        if t.tier == tier and (not sub or t.subtype == sub):
            return True
    return False


def ours_value(r: RunResults, spec: dict | None) -> float | None:
    if spec is None:
        return None
    if "preset" in spec:
        return next((m.value for m in r.metrics if m.preset == spec["preset"]), None)
    if "road_class" in spec:
        return next((x.length_km for x in r.road_lengths if x.road_class == spec["road_class"]),
                    None)
    return sum(t.length_km for t in r.tier_lengths
               if t.length_basis == spec["basis"] and t.tier != "excluded"
               and _matches(t, spec["tiers"]) and not _matches(t, spec.get("exclude", [])))


def gaps_for(r: RunResults, figures: list[ExternalFigure], comparisons: list[Comparison], *,
             threshold: float, date_gap_days: int, mismatch: dict) -> list[Gap]:
    ours_date = datetime.fromisoformat(r.osm_timestamp.replace("Z", "+00:00")).date()
    out = []
    for comp in comparisons:
        figs = [f for f in figures
                if f.source in comp.sources and f.metric_name == comp.metric_name]
        for f in figs:
            ours = None if comp.informational else ours_value(r, comp.ours)
            gap = (ours - f.value) / f.value if ours is not None and f.value else None
            tags = list(comp.tags)
            if f.reference_date and abs((ours_date - f.reference_date).days) > date_gap_days:
                tags.append("date_gap")
            if r.city_id in mismatch.get(f.source, []):
                tags.append("boundary_mismatch")
            key = f"{r.city_id}/{comp.id}"
            if f.network_scope not in ("whole_network",) and not f.network_scope.startswith(
                    "nuts3_") and f.network_scope != "bikenetkit_bike_network":
                key += f"@{f.network_scope}"
            if len(comp.sources) > 1:
                key += f"#{f.source}:{f.value:g}"
            out.append(Gap(
                city_id=r.city_id, comparison=comp.id, key=key, ours=ours, theirs=f.value,
                unit=f.unit, gap_pct=gap,
                flagged=(not comp.informational and gap is not None and abs(gap) > threshold),
                informational=comp.informational, tags=tuple(dict.fromkeys(tags)),
                source=f.source, reference_date=f.reference_date, note=f.note,
            ))
    return out


def reconcile_city(conn, city_id: str, config_path: Path,
                   boundary_kind: str = "lau") -> list[Gap]:
    cfg = load_config(config_path)
    run_id = latest_done_run(conn, city_id, boundary_kind)
    if run_id is None:
        return []
    return gaps_for(fetch_run_results(conn, run_id), fetch_external_figures(conn, city_id),
                    load_comparisons(config_path), threshold=cfg["threshold"],
                    date_gap_days=cfg["date_gap_days"],
                    mismatch=cfg.get("boundary_mismatch", {}))


def _fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "–"
    return f"{v * 100:+.1f}%" if pct else f"{v:,.1f}"


def render_block(gaps_by_city: dict[str, list[Gap]]) -> str:
    lines = [BEGIN, ""]
    for city, gaps in sorted(gaps_by_city.items()):
        lines += [f"#### {city}", "",
                  "| key | ours | theirs | gap | flag | tags | source (date) |",
                  "|---|---:|---:|---:|---|---|---|"]
        for g in gaps:
            flag = "info" if g.informational else ("**>20%**" if g.flagged else "ok")
            lines.append(
                f"| `{g.key}` | {_fmt(g.ours)} | {_fmt(g.theirs)} | {_fmt(g.gap_pct, True)} "
                f"| {flag} | {', '.join(g.tags)} | {g.source} ({g.reference_date or '?'}) |")
        lines.append("")
    lines.append(END)
    return "\n".join(lines)


def write_report(path: Path, gaps_by_city: dict[str, list[Gap]]) -> None:
    text = path.read_text()
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"{path}: markers {BEGIN} / {END} not found")
    path.write_text(pattern.sub(lambda m: render_block(gaps_by_city), text, count=1))


def missing_explanations(path: Path, gaps: list[Gap]) -> list[str]:
    text = path.read_text()
    headings = set(re.findall(r"^### (\S+)\s*$", text, re.M))
    return [g.key for g in gaps if g.flagged and g.key not in headings]
```

`docs/reconciliation.md` (initial):

```markdown
# Reconciliation: velometer vs published figures

Generated by `velometer reconcile --write` from the latest done LAU run per city and the
external figures in the database (`config/external/figures.csv`, QECIO v2.10, BikeNetKit).
Gap = (ours − theirs) / theirs. Every gap flagged **>20%** needs an explanation below, under a
heading `### <key>`; `velometer reconcile --check` enforces this.

Comparison map: `config/reconcile.yaml`. Our numbers are OSM *mapped* km (ADR 0006).

<!-- reconcile:begin -->
<!-- reconcile:end -->

## Explanations
```

CLI: `reconcile [--city X] [--boundary lau] [--write] [--check] [--report docs/reconciliation.md]`.
- It prints the gap table to stdout.
- `--write` calls `write_report`.
- `--check` prints the missing keys and exits 1 if there are any.
- A city without a done run is skipped, and a note is printed.

- [ ] **Step 5: Run the tests and the gate.** Red-proof: make `missing_explanations` ignore `flagged`, check that the test fails (it would list every key), then restore it.

- [ ] **Step 6: Commit**

```bash
git add src/velometer/reconcile.py config/reconcile.yaml docs/reconciliation.md \
  src/velometer/cli.py tests/test_reconcile.py
git commit -m "feat: reconcile against external figures with an enforced explanations check

Assisted-by: Claude:<model-id>"
```

---

### Task 9: Execute M2: real runs, results chart, reconciliation explanations

This task is executed with the controller's oversight, on the most capable model. It needs network access and about 2 GB of downloads into `data/` (gitignored).

**Files:**
- Create: `scripts/render_m2_results.py`, `docs/review/m2_results.md`, `docs/review/m2_results.png`
- Modify: `docs/reconciliation.md` (explanations), `docs/adr/0007-sqlite-canonical-duckdb-for-geometry.md` (measured runtime)

- [ ] **Step 1: Fetch and run.** Use `/usr/bin/time -v` for the Berlin run.

```bash
uv run velometer init
uv run velometer boundaries fetch --kind all
uv run velometer external load
/usr/bin/time -v uv run velometer classify --city berlin 2> data/berlin_time.txt
uv run velometer run --cities all
uv run velometer results
```

Expected: 5 cities `done`. Any `failed` city is investigated and fixed through a code change with a test, not by retrying blindly.

- [ ] **Step 2: Record the measurement in ADR 0007.** Append `## Notes (M2 measurement)` with the Berlin wall time, the max RSS and the way count. Then:
  - if both are under the thresholds (10 min, 8 GB), state "DuckDB not needed at city scale";
  - otherwise stop and report; a DuckDB task is a new plan.

- [ ] **Step 3: Write `scripts/render_m2_results.py`.** It reads the DB (latest done LAU run per city) and writes two files.

  `docs/review/m2_results.md`:
  - the `results` table;
  - classifier version and parameters, OSM timestamps, boundary areas, population and its source;
  - completeness per tier;
  - the ODbL attribution.

  `docs/review/m2_results.png` (matplotlib, Agg; 3 panels):
  - (a) the headline value per city, as bars;
  - (b) tier composition A–E per_side km, as stacked bars;
  - (c) the three presets side by side per city.

  Run it, then **view the PNG with the Read tool** and fix any rendering issue.

- [ ] **Step 4: Reconcile.** Run `uv run velometer reconcile --write`. For every flagged key, investigate with evidence and write a `### <key>` explanation of 2–6 sentences under `## Explanations`. Evidence includes:
  - the boundary areas (ours vs theirs);
  - the definition differences from `config/reconcile.yaml` tags and the research doc;
  - the data date gap;
  - per-tier breakdowns;
  - where useful, a few example ways (via `velometer classify --file` on a small Overpass-free extract made with `osmium extract -b`).

  Each explanation states the cause and whether it is a **definition**, **boundary**, **date** or **classifier** issue. Classifier suspicions are listed for the user's golden review; the rules are not changed. Then run `uv run velometer reconcile --check`; it must exit 0.

- [ ] **Step 5: Gate, then commit** (no data files).

```bash
git add scripts/render_m2_results.py docs/review/m2_results.md docs/review/m2_results.png \
  docs/reconciliation.md docs/adr/0007-sqlite-canonical-duckdb-for-geometry.md
git commit -m "docs: M2 results for 5 pilot cities and reconciliation with explanations

Assisted-by: Claude:<model-id>"
```

---

## Self-review notes (writer)

**Spec coverage:**

| Spec section | Task |
|---|---|
| §2.1 osmium | Task 3 |
| §2.2 clip | Task 2 |
| §2.3 BikeNetKit | Task 7 |
| §2.4 v1 now | Task 9 |
| §2.5–2.6 codes | Task 1 (yaml) and Task 5 (slow uniqueness test) |
| §2.7 population | Task 5 |
| §2.8 Geofabrik | Task 4 |
| §2.9 QECIO mismatch | Task 8 yaml |
| §2.10 CC figures | Task 7 csv |
| §2.11 BNK definition | Task 8 yaml |
| §2.12 DuckDB by measurement | Task 9 step 2 |
| §3 units | Tasks 1–8 |
| §4 tests | per task |
| §5 execution | Task 9 |

**Type consistency:**
- `RunResults` (Task 1) is used by Task 8.
- `BoundaryRecord` (Task 5) is used by Task 6.
- `snapshot` has the same signature in Tasks 3 and 6.
- `measure(boundary=)` (Task 2) is used by Task 6.
- `Metric.per_100k` (Task 1) is used by Task 6.

Implementers must keep these names exactly.
