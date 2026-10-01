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
    Boundary,
    City,
    Completeness,
    ExternalFigure,
    Metric,
    Population,
    RoadLength,
    TierLength,
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
    for t in (*_RESULT_TABLES, "external_figures"):
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
        (
            key.city_id,
            key.osm_timestamp,
            key.boundary_kind,
            key.boundary_sha256,
            key.classifier_version,
            key.classifier_parameters,
        ),
    ).fetchone()
    return row[0] if row else None


def start_run(conn, key: RunKey, *, git_commit: str, region_md5: str) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (city_id, started_at, classifier_version, classifier_parameters, "
            "git_commit, osm_timestamp, region_md5, boundary_kind, boundary_sha256, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,'running')",
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
            ),
        )
    return cur.lastrowid


def fail_run(conn, run_id: int, error: str) -> None:
    with conn:
        conn.execute(
            "UPDATE runs SET status='failed', error=?, finished_at=? WHERE id=?",
            (error, _now(), run_id),
        )


def complete_run(conn, run_id: int, city_id: str, result, metrics: list[Metric]) -> None:
    """Write every result row and mark the run done, atomically.

    Dual-carriageway rows store distance_m = 0.0 because DualPair carries no distance.
    """
    with conn:  # one transaction: commit on success, rollback on any exception
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
            (run_id, "dual_carriageway", p.way_id, partner, "", p.overlap_share, 0.0)
            for p in result.dual_pairs
            for partner in p.partner_ids
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO duplicates (run_id, kind, way_id_separate, way_id_road, side, "
            "overlap_share, distance_m) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        conn.execute("UPDATE runs SET status='done', finished_at=? WHERE id=?", (_now(), run_id))


def latest_done_run(conn: sqlite3.Connection, city_id: str, boundary_kind: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM runs WHERE status='done' AND city_id=? AND boundary_kind=? "
        "ORDER BY osm_timestamp DESC, id DESC LIMIT 1",
        (city_id, boundary_kind),
    ).fetchone()
    return row[0] if row else None


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
