"""SQLite schema and repository functions (ADR 0007: SQLite is canonical)."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from velometer.config import CityConfig, ClassifierParameters
from velometer.models import (
    ActivityYear,
    Boundary,
    City,
    Completeness,
    ExternalFigure,
    Metric,
    Population,
    RoadLength,
    TierLength,
)

SCHEMA_VERSION = 6
_RESULT_TABLES = (
    "duplicates",
    "completeness",
    "metrics",
    "road_lengths",
    "tier_lengths",
    "activity",
    "diagnostics",
    "runs",
)


class SchemaError(Exception):
    """The database schema cannot be used or migrated safely."""


# v4: one row per (run, city, preset, basis); a preset with a parameterised basis has one per basis.
_METRICS_COLUMNS = """
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL REFERENCES cities(id),
  preset TEXT NOT NULL,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('per_side','qecio_weighted')),
  value REAL, numerator_km REAL NOT NULL, denominator_km REAL NOT NULL, per_100k REAL,
  PRIMARY KEY (run_id, city_id, preset, length_basis)
"""

# v6: yearly mapper aggregates per (city, boundary, year, history set, activity.yaml sha256).
_ACTIVITY_TABLE_COLUMNS = """
  city_id TEXT NOT NULL REFERENCES cities(id), boundary_kind TEXT NOT NULL,
  year INTEGER NOT NULL, history_set_md5 TEXT NOT NULL, activity_sha256 TEXT NOT NULL,
  n_edits INTEGER NOT NULL, n_changesets INTEGER NOT NULL, n_mappers INTEGER NOT NULL,
  top_mapper_share REAL NOT NULL, n_ways_created_cycling INTEGER NOT NULL,
  n_ways_deleted_cycling INTEGER NOT NULL,
  PRIMARY KEY (city_id, boundary_kind, year, history_set_md5, activity_sha256)
"""

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
  status TEXT NOT NULL CHECK (status IN ('running','done','failed')), error TEXT,
  population_value INTEGER, population_year INTEGER, population_source TEXT,
  config_sha256 TEXT,
  source TEXT NOT NULL DEFAULT 'current' CHECK (source IN ('current','history'))
);
CREATE UNIQUE INDEX IF NOT EXISTS runs_done_key ON runs (
  city_id, osm_timestamp, boundary_kind, boundary_sha256, classifier_version,
  classifier_parameters, config_sha256, source, region_md5) WHERE status = 'done';
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
CREATE TABLE IF NOT EXISTS metrics (@METRICS@);
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
CREATE TABLE IF NOT EXISTS activity (@ACTIVITY@);
CREATE TABLE IF NOT EXISTS history_sets (
  set_md5 TEXT PRIMARY KEY, regions_json TEXT NOT NULL, index_path TEXT NOT NULL,
  index_sha256 TEXT NOT NULL, uncovered_km2 REAL NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS diagnostics (
  run_id INTEGER NOT NULL REFERENCES runs(id), key TEXT NOT NULL, value REAL NOT NULL,
  PRIMARY KEY (run_id, key)
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
_SCHEMA = _SCHEMA.replace("@METRICS@", _METRICS_COLUMNS).replace(
    "@ACTIVITY@", _ACTIVITY_TABLE_COLUMNS
)


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
    for t in (*_RESULT_TABLES, "external_figures"):
        if t in present and conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]:
            raise SchemaError(f"v1 database has results in {t!r}; refusing to migrate")
    for t in (*_RESULT_TABLES, "external_figures"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    if "cities" in present:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cities)")}
        if "nuts3_code" not in cols:
            conn.execute("ALTER TABLE cities ADD COLUMN nuts3_code TEXT")


# v3 columns of runs: the population a run used, and the sha256 of its classifier + presets YAML.
_RUNS_V3_COLUMNS = {
    "population_value": "INTEGER",
    "population_year": "INTEGER",
    "population_source": "TEXT",
    "config_sha256": "TEXT",
}


def _migrate_2_to_3(conn: sqlite3.Connection) -> None:
    """Additive: existing runs keep NULL population and config_sha256, so no new run reuses them."""
    if "runs" not in _tables(conn):
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
    for name, sql_type in _RUNS_V3_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {sql_type}")
    conn.execute("DROP INDEX IF EXISTS runs_done_key")  # recreated with config_sha256


def _migrate_3_to_4(conn: sqlite3.Connection) -> None:
    """Rebuild metrics with the basis in the primary key; existing rows are copied unchanged."""
    if "metrics" not in _tables(conn):
        return
    if not conn.in_transaction:  # DDL does not open one: make the rebuild atomic
        conn.execute("BEGIN")
    conn.execute("DROP TABLE IF EXISTS metrics_v4")
    conn.execute(f"CREATE TABLE metrics_v4 ({_METRICS_COLUMNS})")
    conn.execute(
        "INSERT INTO metrics_v4 (run_id, city_id, preset, length_basis, value, numerator_km, "
        "denominator_km, per_100k) SELECT run_id, city_id, preset, length_basis, value, "
        "numerator_km, denominator_km, per_100k FROM metrics"
    )
    conn.execute("DROP TABLE metrics")
    conn.execute("ALTER TABLE metrics_v4 RENAME TO metrics")


def _migrate_4_to_5(conn: sqlite3.Connection) -> None:
    """Additive: existing runs become source='current'; the key index is rebuilt with source."""
    if "runs" not in _tables(conn):
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
    if "source" not in cols:
        conn.execute(
            "ALTER TABLE runs ADD COLUMN source TEXT NOT NULL DEFAULT 'current' "
            "CHECK (source IN ('current','history'))"
        )
    conn.execute("DROP INDEX IF EXISTS runs_done_key")  # recreated with source


def _after_activity_copy(conn: sqlite3.Connection) -> None:
    """No-op; the atomicity test patches it to fail between the copy and the swap."""


def _migrate_5_to_6(conn: sqlite3.Connection, activity_sha256: str | None) -> None:
    """Rebuild activity with the activity.yaml sha256 in the key; rows keep the given sha."""
    if "activity" not in _tables(conn):
        return
    n_rows = conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
    if n_rows and activity_sha256 is None:
        raise SchemaError(
            f"v5 database has {n_rows} activity rows that predate activity_sha256; run "
            "`velometer migrate --activity-sha <sha>` with the sha256 of the activity.yaml "
            "they were computed with (the earlier sha256sum of config/activity.yaml)"
        )
    if not conn.in_transaction:  # DDL does not open one: make the rebuild atomic
        conn.execute("BEGIN")
    conn.execute("DROP TABLE IF EXISTS activity_v6")
    conn.execute(f"CREATE TABLE activity_v6 ({_ACTIVITY_TABLE_COLUMNS})")
    conn.execute(
        "INSERT INTO activity_v6 (city_id, boundary_kind, year, history_set_md5, activity_sha256, "
        "n_edits, n_changesets, n_mappers, top_mapper_share, n_ways_created_cycling, "
        "n_ways_deleted_cycling) SELECT city_id, boundary_kind, year, history_set_md5, ?, "
        "n_edits, n_changesets, n_mappers, top_mapper_share, n_ways_created_cycling, "
        "n_ways_deleted_cycling FROM activity",
        (activity_sha256,),
    )
    _after_activity_copy(conn)
    conn.execute("DROP TABLE activity")
    conn.execute("ALTER TABLE activity_v6 RENAME TO activity")


_MIGRATIONS = {
    1: _migrate_1_to_2,
    2: _migrate_2_to_3,
    3: _migrate_3_to_4,
    4: _migrate_4_to_5,
}  # 5 -> 6 takes the activity sha and is called by create_schema directly


def _repair_done_key_index(conn: sqlite3.Connection) -> None:
    """A v5 database made before region_md5 joined the key keeps the old index: drop it so the
    schema script recreates it."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name='runs_done_key'").fetchone()
    if row and "region_md5" not in row[0]:
        conn.execute("DROP INDEX runs_done_key")


def create_schema(conn: sqlite3.Connection, activity_sha256_for_v5: str | None = None) -> None:
    """Create or migrate the schema. A v5 database with activity rows needs the sha256 of the
    activity.yaml they were computed with (`velometer migrate --activity-sha`)."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise SchemaError(
            f"database schema v{current} is newer than this velometer (v{SCHEMA_VERSION})"
        )
    with conn:
        for v in range(max(current, 1), SCHEMA_VERSION):
            if not current:  # a fresh database (user_version 0) needs no migration
                continue
            if v == 5:
                _migrate_5_to_6(conn, activity_sha256_for_v5)
            else:
                _MIGRATIONS[v](conn)
        _repair_done_key_index(conn)
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


@dataclass(frozen=True)
class RunKey:
    city_id: str
    osm_timestamp: str
    boundary_kind: str
    boundary_sha256: str
    classifier_version: str
    classifier_parameters: str  # canonical JSON: json.dumps(params, sort_keys=True)
    config_sha256: str  # run.config_sha256: classifier, presets, activity YAML
    source: str = "current"  # 'history' for a yearly history run (M3)


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


DEFAULT_PARAMETERS = canonical_parameters(ClassifierParameters().model_dump())


def find_done_run(conn, key: RunKey) -> int | None:
    row = conn.execute(
        "SELECT id FROM runs WHERE status='done' AND city_id=? AND osm_timestamp=? AND "
        "boundary_kind=? AND boundary_sha256=? AND classifier_version=? AND "
        "classifier_parameters=? AND config_sha256=? AND source=?",
        (
            key.city_id,
            key.osm_timestamp,
            key.boundary_kind,
            key.boundary_sha256,
            key.classifier_version,
            key.classifier_parameters,
            key.config_sha256,
            key.source,
        ),
    ).fetchone()
    return row[0] if row else None


def start_run(
    conn,
    key: RunKey,
    *,
    git_commit: str,
    region_md5: str,
    population: Population | None = None,
) -> int:
    """Insert a `running` row; the population used for per-100k is recorded on it."""
    if not key.config_sha256:
        raise ValueError("a run needs a config_sha256 (a run without one can never be reused)")
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (city_id, started_at, classifier_version, classifier_parameters, "
            "git_commit, osm_timestamp, region_md5, boundary_kind, boundary_sha256, status, "
            "population_value, population_year, population_source, config_sha256, source) "
            "VALUES (?,?,?,?,?,?,?,?,?,'running',?,?,?,?,?)",
            (
                key.city_id,
                _now(),
                key.classifier_version,
                key.classifier_parameters,
                git_commit,
                key.osm_timestamp,
                region_md5,
                key.boundary_kind,
                key.boundary_sha256,
                population.value if population else None,
                population.year if population else None,
                population.source if population else None,
                key.config_sha256,
                key.source,
            ),
        )
    return cur.lastrowid


def fail_run(conn, run_id: int, error: str) -> None:
    with conn:
        conn.execute(
            "UPDATE runs SET status='failed', error=?, finished_at=? WHERE id=?",
            (error, _now(), run_id),
        )


def complete_run(
    conn,
    run_id: int,
    city_id: str,
    result,
    metrics: list[Metric],
    *,
    supersedes: int | None = None,
    diagnostics: dict[str, float] | None = None,
) -> None:
    """Write every result row and mark the run done, atomically.

    With `supersedes`, that done run is retired (status failed) in the same transaction, so a
    failure leaves it done and untouched.

    Dual-carriageway rows hold one row per (way, partner) pair: overlap_share is the share of the
    way within the pairing distance of that partner, distance_m their minimum distance.
    `diagnostics` (key -> value) lands in the diagnostics table in the same transaction.
    """
    with conn:  # one transaction: commit on success, rollback on any exception
        if supersedes is not None:
            conn.execute(
                "UPDATE runs SET status='failed', error=? WHERE id=?",
                (f"superseded by run {run_id}", supersedes),
            )
        conn.executemany(
            "INSERT INTO tier_lengths VALUES (?,?,?,?,?,?,?)",
            [
                (run_id, city_id, t.tier, t.subtype or "", t.length_basis, t.length_km, t.n_ways)
                for t in result.tier_lengths
            ],
        )
        conn.executemany(
            "INSERT INTO road_lengths VALUES (?,?,?,?)",
            [(run_id, city_id, r.road_class, r.length_km) for r in result.road_lengths],
        )
        conn.executemany(
            "INSERT INTO diagnostics (run_id, key, value) VALUES (?,?,?)",
            [(run_id, k, v) for k, v in (diagnostics or {}).items()],
        )
        conn.executemany(
            "INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    run_id,
                    city_id,
                    m.preset,
                    m.length_basis,
                    m.value,
                    m.numerator_km,
                    m.denominator_km,
                    m.per_100k,
                )
                for m in metrics
            ],
        )
        conn.executemany(
            "INSERT INTO completeness VALUES (?,?,?,?,?,?)",
            [
                (
                    run_id,
                    city_id,
                    c.tier,
                    c.share_with_width,
                    c.share_with_surface,
                    c.share_with_segregated,
                )
                for c in result.completeness
            ],
        )
        rows = [
            (
                run_id,
                "parallel",
                d.standalone_way_id,
                d.road_way_id,
                d.road_side,
                d.overlap_share,
                d.distance_m,
            )
            for d in result.duplicates
        ]
        rows += [
            (run_id, "dual_carriageway", p.way_id, partner, "", share, dist)
            for p in result.dual_pairs
            for partner, share, dist in zip(
                p.partner_ids, p.partner_shares, p.partner_distances_m, strict=True
            )
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO duplicates (run_id, kind, way_id_separate, way_id_road, side, "
            "overlap_share, distance_m) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        conn.execute("UPDATE runs SET status='done', finished_at=? WHERE id=?", (_now(), run_id))


def latest_done_run(
    conn: sqlite3.Connection,
    city_id: str,
    boundary_kind: str,
    classifier_version: str = "v1",
    classifier_parameters: str = DEFAULT_PARAMETERS,
    config_sha256: str | None = None,
) -> int | None:
    """Newest done run for this classifier version and parameters (canonical JSON).

    Runs with other parameters (a `both_sides` sensitivity run) or another classifier version
    never displace it. With `config_sha256`, only runs of that config count, so a report names
    the runs of the config on disk even after an edit and revert (A, B, A).
    """
    sql = (
        "SELECT id FROM runs WHERE status='done' AND source='current' AND city_id=? "
        "AND boundary_kind=? AND classifier_version=? AND classifier_parameters=? "
    )
    args: tuple = (city_id, boundary_kind, classifier_version, classifier_parameters)
    if config_sha256 is not None:
        sql += "AND config_sha256=? "
        args += (config_sha256,)
    row = conn.execute(sql + "ORDER BY osm_timestamp DESC, id DESC LIMIT 1", args).fetchone()
    return row[0] if row else None


def history_runs(
    conn: sqlite3.Connection,
    city_id: str,
    boundary_kind: str,
    *,
    classifier_version: str,
    classifier_parameters: str,
    config_sha256: str,
    history_set_md5: str,
) -> dict[str, int]:
    """Done history runs of this config, as osm_timestamp -> run_id.

    A history run records its history set's md5 in `region_md5`.
    """
    rows = conn.execute(
        "SELECT osm_timestamp, id FROM runs WHERE status='done' AND source='history' "
        "AND city_id=? AND boundary_kind=? AND classifier_version=? AND classifier_parameters=? "
        "AND config_sha256=? AND region_md5=?",
        (
            city_id,
            boundary_kind,
            classifier_version,
            classifier_parameters,
            config_sha256,
            history_set_md5,
        ),
    ).fetchall()
    return dict(rows)


def latest_history_set(
    conn: sqlite3.Connection,
    city_id: str,
    boundary_kind: str,
    *,
    classifier_version: str,
    classifier_parameters: str,
    config_sha256: str,
) -> str | None:
    """md5 of the most recently recorded history set that has done history runs of this config."""
    row = conn.execute(
        "SELECT h.set_md5 FROM history_sets h WHERE EXISTS ("
        "SELECT 1 FROM runs r WHERE r.region_md5=h.set_md5 AND r.status='done' "
        "AND r.source='history' AND r.city_id=? AND r.boundary_kind=? "
        "AND r.classifier_version=? AND r.classifier_parameters=? AND r.config_sha256=?) "
        "ORDER BY h.recorded_at DESC, h.rowid DESC LIMIT 1",
        (city_id, boundary_kind, classifier_version, classifier_parameters, config_sha256),
    ).fetchone()
    return row[0] if row else None


def upsert_history_set(
    conn: sqlite3.Connection,
    set_md5: str,
    regions: list[dict],
    *,
    index_path: str,
    index_sha256: str,
    uncovered_km2: float,
) -> None:
    """Record which region files (and which index) make up a history set; once per set.

    `regions` is a list of {region, md5, md5_source, fetched_at}. A repeat call for the same
    set keeps the first row (the set md5 already pins the files).
    """
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO history_sets (set_md5, regions_json, index_path, index_sha256, "
            "uncovered_km2, recorded_at) VALUES (?,?,?,?,?,?)",
            (set_md5, json.dumps(regions), index_path, index_sha256, uncovered_km2, _now()),
        )


def fetch_history_set(conn: sqlite3.Connection, set_md5: str) -> dict | None:
    row = conn.execute(
        "SELECT regions_json, index_path, index_sha256, uncovered_km2, recorded_at "
        "FROM history_sets WHERE set_md5=?",
        (set_md5,),
    ).fetchone()
    if row is None:
        return None
    return {
        "set_md5": set_md5,
        "regions": json.loads(row[0]),
        "index_path": row[1],
        "index_sha256": row[2],
        "uncovered_km2": row[3],
        "recorded_at": row[4],
    }


def fetch_diagnostics(conn: sqlite3.Connection, run_id: int) -> dict[str, float]:
    rows = conn.execute("SELECT key, value FROM diagnostics WHERE run_id=?", (run_id,))
    return dict(rows.fetchall())


_ACTIVITY_COLUMNS = (
    "city_id, boundary_kind, year, history_set_md5, n_edits, n_changesets, n_mappers, "
    "top_mapper_share, n_ways_created_cycling, n_ways_deleted_cycling"
)  # the ActivityYear fields; the table adds activity_sha256 after history_set_md5


def replace_activity(
    conn: sqlite3.Connection,
    city_id: str,
    boundary_kind: str,
    history_set_md5: str,
    activity_sha256: str,
    rows: list[ActivityYear],
) -> None:
    """Replace this (city, boundary, history set, activity.yaml)'s yearly aggregates, atomically."""
    fields = [c.strip() for c in _ACTIVITY_COLUMNS.split(",")]
    with conn:
        conn.execute(
            "DELETE FROM activity WHERE city_id=? AND boundary_kind=? AND history_set_md5=? "
            "AND activity_sha256=?",
            (city_id, boundary_kind, history_set_md5, activity_sha256),
        )
        conn.executemany(
            f"INSERT INTO activity ({_ACTIVITY_COLUMNS}, activity_sha256) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(*(r.model_dump()[f] for f in fields), activity_sha256) for r in rows],
        )


def fetch_activity(
    conn: sqlite3.Connection,
    city_id: str,
    boundary_kind: str,
    history_set_md5: str,
    activity_sha256: str,
) -> list[ActivityYear]:
    return [
        ActivityYear(**r)
        for r in _rows(
            conn,
            f"SELECT {_ACTIVITY_COLUMNS} FROM activity WHERE city_id=? AND boundary_kind=? "
            "AND history_set_md5=? AND activity_sha256=? ORDER BY year",
            (city_id, boundary_kind, history_set_md5, activity_sha256),
        )
    ]


def fetch_run(conn: sqlite3.Connection, run_id: int) -> dict:
    """The run row as a dict (provenance: commit, OSM timestamp, boundary sha, population)."""
    rows = _rows(conn, "SELECT * FROM runs WHERE id=?", (run_id,))
    if not rows:
        raise KeyError(f"no run {run_id}")
    return rows[0]


def _rows(conn: sqlite3.Connection, sql: str, args: tuple) -> list[dict]:
    cur = conn.execute(sql, args)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]


def fetch_run_results(conn: sqlite3.Connection, run_id: int) -> RunResults:
    run = conn.execute("SELECT city_id, osm_timestamp FROM runs WHERE id=?", (run_id,)).fetchone()
    if run is None:
        raise KeyError(f"no run {run_id}")
    tiers = _rows(
        conn,
        "SELECT run_id, city_id, tier, subtype, length_basis, length_km, n_ways "
        "FROM tier_lengths WHERE run_id=? ORDER BY tier, subtype, length_basis",
        (run_id,),
    )
    for t in tiers:
        t["subtype"] = t["subtype"] or None
    return RunResults(
        run_id=run_id,
        city_id=run[0],
        osm_timestamp=run[1],
        tier_lengths=[TierLength(**t) for t in tiers],
        road_lengths=[
            RoadLength(**r)
            for r in _rows(
                conn,
                "SELECT run_id, city_id, road_class, length_km FROM road_lengths "
                "WHERE run_id=? ORDER BY road_class",
                (run_id,),
            )
        ],
        metrics=[
            Metric(**m)
            for m in _rows(
                conn,
                "SELECT run_id, city_id, preset, length_basis, value, numerator_km, "
                "denominator_km, per_100k FROM metrics WHERE run_id=? ORDER BY preset",
                (run_id,),
            )
        ],
        completeness=[
            Completeness(**c)
            for c in _rows(
                conn,
                "SELECT run_id, city_id, tier, share_with_width, share_with_surface, "
                "share_with_segregated FROM completeness WHERE run_id=? ORDER BY tier",
                (run_id,),
            )
        ],
    )


def upsert_boundary(conn: sqlite3.Connection, b: Boundary) -> None:
    with conn:
        conn.execute(
            "INSERT INTO boundaries (city_id, kind, source, source_version, area_km2, path, "
            "sha256) VALUES (:city_id, :kind, :source, :source_version, :area_km2, :path, "
            ":sha256) ON CONFLICT(city_id, kind) DO UPDATE SET source=excluded.source, "
            "source_version=excluded.source_version, area_km2=excluded.area_km2, "
            "path=excluded.path, sha256=excluded.sha256",
            b.model_dump(),
        )


def fetch_boundary(conn: sqlite3.Connection, city_id: str, kind: str) -> Boundary | None:
    rows = _rows(
        conn,
        "SELECT city_id, kind, source, source_version, area_km2, path, sha256 FROM boundaries "
        "WHERE city_id=? AND kind=?",
        (city_id, kind),
    )
    return Boundary(**rows[0]) if rows else None


def set_population(conn: sqlite3.Connection, city_id: str, pop: Population) -> None:
    with conn:
        conn.execute(
            "UPDATE cities SET population_value=?, population_year=?, population_source=? "
            "WHERE id=?",
            (pop.value, pop.year, pop.source, city_id),
        )


def replace_external_figures(
    conn: sqlite3.Connection, source: str, figures: list[ExternalFigure]
) -> None:
    with conn:
        conn.execute("DELETE FROM external_figures WHERE source=?", (source,))
        conn.executemany(
            "INSERT INTO external_figures (city_id, source, metric_name, value, unit, "
            "reference_date, network_scope, length_basis, source_url, retrieved_at, note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    f.city_id,
                    f.source,
                    f.metric_name,
                    f.value,
                    f.unit,
                    f.reference_date.isoformat() if f.reference_date else None,
                    f.network_scope,
                    f.length_basis,
                    f.source_url,
                    f.retrieved_at.isoformat(),
                    f.note,
                )
                for f in figures
            ],
        )


def fetch_external_figures(conn: sqlite3.Connection, city_id: str) -> list[ExternalFigure]:
    return [
        ExternalFigure(**r)
        for r in _rows(
            conn,
            "SELECT city_id, source, metric_name, value, unit, reference_date, network_scope, "
            "length_basis, source_url, retrieved_at, note FROM external_figures "
            "WHERE city_id=? ORDER BY id",
            (city_id,),
        )
    ]


def upsert_cities(conn: sqlite3.Connection, cities: list[CityConfig]) -> int:
    with conn:
        conn.executemany(
            """
            INSERT INTO cities (id, name, country_iso2, lau_code, fua_code, nuts3_code,
                                osm_relation_id, epsg, geofabrik_region)
            VALUES (:id, :name, :country_iso2, :lau_code, :fua_code, :nuts3_code,
                    :osm_relation_id, :epsg, :geofabrik_region)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name, country_iso2=excluded.country_iso2,
              lau_code=excluded.lau_code, fua_code=excluded.fua_code,
              nuts3_code=excluded.nuts3_code, osm_relation_id=excluded.osm_relation_id,
              epsg=excluded.epsg, geofabrik_region=excluded.geofabrik_region
            """,
            [c.model_dump() for c in cities],
        )
    return len(cities)


def fetch_cities(conn: sqlite3.Connection) -> list[City]:
    out = []
    for d in _rows(conn, "SELECT * FROM cities ORDER BY id", ()):
        pop = None
        if d["population_value"] is not None:
            pop = Population(
                value=d["population_value"],
                year=d["population_year"],
                source=d["population_source"],
            )
        for k in ("population_value", "population_year", "population_source"):
            d.pop(k)
        out.append(City(**d, population=pop))
    return out
