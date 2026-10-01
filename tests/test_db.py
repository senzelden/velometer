import sqlite3

import pytest

from velometer.config import default_config_dir, load_cities
from velometer.db import SCHEMA_VERSION, connect, create_schema, fetch_cities, upsert_cities

TABLES = {
    "cities",
    "boundaries",
    "runs",
    "tier_lengths",
    "road_lengths",
    "metrics",
    "completeness",
    "external_figures",
    "duplicates",
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def test_schema_has_all_tables_and_version(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    create_schema(conn)
    assert _tables(conn) >= TABLES
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_create_schema_and_upsert_are_idempotent(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    cities = load_cities(default_config_dir() / "cities.yaml")
    for _ in range(2):
        create_schema(conn)
        upsert_cities(conn, cities)
    assert sorted(c.id for c in fetch_cities(conn)) == sorted(c.id for c in cities)


def test_upsert_updates_changed_fields(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    create_schema(conn)
    cities = load_cities(default_config_dir() / "cities.yaml")
    upsert_cities(conn, cities)
    changed = [cities[0].model_copy(update={"lau_code": "DE_11000000"})]
    upsert_cities(conn, changed)
    berlin = next(c for c in fetch_cities(conn) if c.id == cities[0].id)
    assert berlin.lau_code == "DE_11000000"


def test_tier_lengths_reject_unknown_basis(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    create_schema(conn)
    conn.execute(
        "INSERT INTO runs (id, started_at, classifier_version, git_commit,"
        " osm_timestamp, boundary_kind, status) VALUES (1, 't', 'v1', 'c', 't',"
        " 'lau', 'done')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tier_lengths (run_id, city_id, tier, subtype, length_basis,"
            " length_km, n_ways) VALUES (1, 'berlin', 'A', NULL, 'lane', 1.0, 1)"
        )
