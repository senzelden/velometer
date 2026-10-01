import sqlite3

import pytest

from velometer.config import default_config_dir, load_cities
from velometer.db import (
    SCHEMA_VERSION,
    RunKey,
    SchemaError,
    complete_run,
    connect,
    create_schema,
    fail_run,
    fetch_boundary,
    fetch_cities,
    fetch_external_figures,
    fetch_run_results,
    find_done_run,
    latest_done_run,
    open_db,
    replace_external_figures,
    set_population,
    start_run,
    upsert_boundary,
    upsert_cities,
)
from velometer.models import (
    Boundary,
    Completeness,
    ExternalFigure,
    Metric,
    Population,
    RoadLength,
    TierLength,
)
from velometer.pipeline.measure import MeasureResult, PlainOnewayReport
from velometer.pipeline.types import DualPair, DuplicateFlag

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
    upsert_cities(conn, load_cities(default_config_dir() / "cities.yaml"))
    conn.execute(
        "INSERT INTO runs (id, city_id, started_at, classifier_version, classifier_parameters,"
        " git_commit, osm_timestamp, region_md5, boundary_kind, boundary_sha256, status)"
        " VALUES (1, 'berlin', 't', 'v1', '{}', 'c', 't', 'm', 'lau', 's', 'done')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tier_lengths (run_id, city_id, tier, subtype, length_basis,"
            " length_km, n_ways) VALUES (1, 'berlin', 'A', NULL, 'lane', 1.0, 1)"
        )


KEY = RunKey("berlin", "2026-09-30T20:22:42Z", "lau", "abc", "v1", '{"p":"x"}')


def _result():
    return MeasureResult(
        tier_lengths=[
            TierLength(tier="A", subtype=None, length_basis="per_side", length_km=2.0, n_ways=3)
        ],
        road_lengths=[
            RoadLength(road_class=c, length_km=10.0)
            for c in (
                "main_excl_motorway",
                "main_incl_motorway",
                "main_incl_motorway_raw",
                "all_public",
            )
        ],
        duplicates=[DuplicateFlag(1, 2, "right", 0.9, 4.0)],
        dual_pairs=[DualPair(5, (6,), 0.8)],
        classified=[],
        unknown_values={},
        plain_oneway=PlainOnewayReport("traffic_side", "both_sides", 0, 0.0, {}),
        completeness=[
            Completeness(
                tier="A", share_with_width=0.5, share_with_surface=1.0, share_with_segregated=0.0
            )
        ],
    )


def _metrics():
    return [
        Metric(
            preset="ours_headline",
            length_basis="per_side",
            value=20.0,
            numerator_km=2.0,
            denominator_km=10.0,
            per_100k=0.05,
        )
    ]


@pytest.fixture
def conn(tmp_path, cities):
    with open_db(tmp_path / "v.sqlite") as c:
        create_schema(c)
        upsert_cities(c, cities)
        yield c


@pytest.fixture
def cities():
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
    fig = ExternalFigure(
        city_id="berlin",
        source="clean_cities_2025",
        metric_name="protected_km",
        value=925,
        unit="km",
        reference_date=None,
        network_scope="whole_network",
        length_basis="unknown",
        source_url="https://x",
        retrieved_at="2026-10-01",
    )
    for _ in range(2):
        replace_external_figures(conn, "clean_cities_2025", [fig])
    assert len(fetch_external_figures(conn, "berlin")) == 1


def test_v1_db_with_external_figures_refuses_to_migrate(tmp_path):
    path = tmp_path / "v.sqlite"
    c = sqlite3.connect(path)
    c.executescript(
        "CREATE TABLE external_figures (id INTEGER PRIMARY KEY, source TEXT);"
        "INSERT INTO external_figures VALUES (1, 'x'); PRAGMA user_version = 1;"
    )
    c.close()
    with open_db(path) as c, pytest.raises(SchemaError, match="external_figures"):
        create_schema(c)


def test_boundary_roundtrip_and_upsert(conn):
    b = Boundary(
        city_id="berlin",
        kind="lau",
        source="gisco",
        source_version="2024",
        area_km2=891.8,
        path="data/b.gpkg",
        sha256="aa",
    )
    assert fetch_boundary(conn, "berlin", "lau") is None
    upsert_boundary(conn, b)
    assert fetch_boundary(conn, "berlin", "lau") == b
    upsert_boundary(conn, b.model_copy(update={"sha256": "bb"}))
    assert fetch_boundary(conn, "berlin", "lau").sha256 == "bb"


def test_set_population_and_nuts3_roundtrip(conn):
    set_population(conn, "berlin", Population(value=3782202, year=2024, source="gisco_lau"))
    berlin = next(c for c in fetch_cities(conn) if c.id == "berlin")
    assert berlin.population == Population(value=3782202, year=2024, source="gisco_lau")
    assert berlin.nuts3_code == "DE300"


def test_latest_done_run_picks_newest_osm_timestamp(conn):
    old = KEY.__class__(**{**KEY.__dict__, "osm_timestamp": "2026-01-01T00:00:00Z"})
    new = KEY.__class__(**{**KEY.__dict__, "osm_timestamp": "2026-09-30T00:00:00Z"})
    new_id = start_run(conn, new, git_commit="g", region_md5="m")
    complete_run(conn, new_id, "berlin", _result(), _metrics())
    old_id = start_run(conn, old, git_commit="g", region_md5="m")  # started later, older data
    complete_run(conn, old_id, "berlin", _result(), _metrics())
    assert old_id > new_id
    assert latest_done_run(conn, "berlin", "lau") == new_id


def test_fetch_run_results_maps_empty_subtype_to_none(conn):
    rid = start_run(conn, KEY, git_commit="g", region_md5="m")
    result = _result()
    result.tier_lengths.append(
        TierLength(tier="B", subtype="lane", length_basis="per_side", length_km=1.0, n_ways=1)
    )
    complete_run(conn, rid, "berlin", result, _metrics())
    assert conn.execute("SELECT subtype FROM tier_lengths WHERE tier='A'").fetchone()[0] == ""
    subtypes = {t.tier: t.subtype for t in fetch_run_results(conn, rid).tier_lengths}
    assert subtypes == {"A": None, "B": "lane"}
