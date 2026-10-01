"""SQLite schema and repository functions (ADR 0007: SQLite is canonical)."""

import sqlite3
from pathlib import Path

from velometer.config import CityConfig
from velometer.models import City, Population

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cities (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, country_iso2 TEXT NOT NULL,
  lau_code TEXT, fua_code TEXT, osm_relation_id INTEGER NOT NULL, epsg INTEGER NOT NULL,
  geofabrik_region TEXT NOT NULL,
  population_value INTEGER, population_year INTEGER, population_source TEXT
);
CREATE TABLE IF NOT EXISTS boundaries (
  city_id TEXT NOT NULL REFERENCES cities(id),
  kind TEXT NOT NULL CHECK (kind IN ('lau','fua','osm_admin')),
  source TEXT NOT NULL, source_version TEXT NOT NULL, area_km2 REAL NOT NULL,
  path TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY (city_id, kind)
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, classifier_version TEXT NOT NULL,
  git_commit TEXT NOT NULL, osm_timestamp TEXT NOT NULL,
  boundary_kind TEXT NOT NULL CHECK (boundary_kind IN ('lau','fua','osm_admin','none')),
  status TEXT NOT NULL CHECK (status IN ('running','done','failed'))
);
CREATE TABLE IF NOT EXISTS tier_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('A','B','C','D','E','excluded')), subtype TEXT,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('per_side','qecio_weighted')),
  length_km REAL NOT NULL, n_ways INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS road_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL,
  road_class TEXT NOT NULL CHECK (road_class IN
    ('main_excl_motorway','main_incl_motorway','main_incl_motorway_raw','all_public')),
  length_km REAL NOT NULL, PRIMARY KEY (run_id, city_id, road_class)
);
CREATE TABLE IF NOT EXISTS metrics (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL, preset TEXT NOT NULL,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('per_side','qecio_weighted')),
  value REAL, numerator_km REAL NOT NULL, denominator_km REAL NOT NULL,
  PRIMARY KEY (run_id, city_id, preset)
);
CREATE TABLE IF NOT EXISTS completeness (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL, tier TEXT NOT NULL,
  share_with_width REAL NOT NULL, share_with_surface REAL NOT NULL,
  share_with_segregated REAL NOT NULL, PRIMARY KEY (run_id, city_id, tier)
);
CREATE TABLE IF NOT EXISTS external_figures (
  id INTEGER PRIMARY KEY, city_id TEXT NOT NULL, source TEXT NOT NULL,
  metric_name TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, reference_date TEXT,
  network_scope TEXT NOT NULL,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('streckenlaenge','reallaenge','unknown')),
  source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS duplicates (
  run_id INTEGER REFERENCES runs(id),
  kind TEXT NOT NULL CHECK (kind IN ('parallel','dual_carriageway')),
  way_id_separate INTEGER NOT NULL, way_id_road INTEGER NOT NULL, side TEXT,
  overlap_share REAL NOT NULL, distance_m REAL NOT NULL, resolved INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def upsert_cities(conn: sqlite3.Connection, cities: list[CityConfig]) -> int:
    conn.executemany(
        """
        INSERT INTO cities (id, name, country_iso2, lau_code, fua_code, osm_relation_id, epsg,
                            geofabrik_region)
        VALUES (:id, :name, :country_iso2, :lau_code, :fua_code, :osm_relation_id, :epsg,
                :geofabrik_region)
        ON CONFLICT(id) DO UPDATE SET
          name=excluded.name, country_iso2=excluded.country_iso2, lau_code=excluded.lau_code,
          fua_code=excluded.fua_code, osm_relation_id=excluded.osm_relation_id,
          epsg=excluded.epsg, geofabrik_region=excluded.geofabrik_region
        """,
        [c.model_dump() for c in cities],
    )
    conn.commit()
    return len(cities)


def fetch_cities(conn: sqlite3.Connection) -> list[City]:
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM cities ORDER BY id").fetchall()
    finally:
        conn.row_factory = None
    out = []
    for r in rows:
        d = dict(r)
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
