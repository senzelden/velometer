import sqlite3
from dataclasses import replace

import pytest

from velometer import db
from velometer.config import default_config_dir, load_cities
from velometer.db import (
    DEFAULT_PARAMETERS,
    SCHEMA_VERSION,
    RunKey,
    SchemaError,
    complete_run,
    create_schema,
    fail_run,
    fetch_activity,
    fetch_boundary,
    fetch_cities,
    fetch_diagnostics,
    fetch_external_figures,
    fetch_history_set,
    fetch_run,
    fetch_run_results,
    find_done_run,
    history_runs,
    latest_done_run,
    open_db,
    replace_activity,
    replace_external_figures,
    set_population,
    start_run,
    upsert_boundary,
    upsert_cities,
    upsert_history_set,
)
from velometer.models import (
    ActivityYear,
    Boundary,
    Completeness,
    ExternalFigure,
    Metric,
    Population,
    RoadLength,
    Subarea,
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
    "activity",
    "diagnostics",
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def test_schema_has_all_tables_and_version(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        assert _tables(conn) >= TABLES
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_create_schema_and_upsert_are_idempotent(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        cities = load_cities(default_config_dir() / "cities.yaml")
        for _ in range(2):
            create_schema(conn)
            upsert_cities(conn, cities)
        assert sorted(c.id for c in fetch_cities(conn)) == sorted(c.id for c in cities)


def test_upsert_updates_changed_fields(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        cities = load_cities(default_config_dir() / "cities.yaml")
        upsert_cities(conn, cities)
        changed = [cities[0].model_copy(update={"lau_code": "DE_11000000"})]
        upsert_cities(conn, changed)
        berlin = next(c for c in fetch_cities(conn) if c.id == cities[0].id)
        assert berlin.lau_code == "DE_11000000"


def test_tier_lengths_reject_unknown_basis(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
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


KEY = RunKey("berlin", "2026-09-30T20:22:42Z", "lau", "abc", "v1", DEFAULT_PARAMETERS, "cfg")


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
        dual_pairs=[DualPair(5, (6, 7), 0.8, (0.6, 0.3), (12.5, 30.0))],
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


def test_create_schema_inside_a_callers_transaction_is_a_clear_error(tmp_path):
    with open_db(tmp_path / "t.sqlite") as c:
        c.execute("BEGIN")
        with pytest.raises(SchemaError, match="must not run inside an open transaction"):
            create_schema(c)
        c.execute("ROLLBACK")


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
    assert kinds == ["dual_carriageway", "dual_carriageway", "parallel"]
    dual = conn.execute(
        "SELECT way_id_separate, way_id_road, overlap_share, distance_m FROM duplicates "
        "WHERE kind='dual_carriageway' ORDER BY way_id_road"
    ).fetchall()
    assert dual == [(5, 6, 0.6, 12.5), (5, 7, 0.3, 30.0)]  # per pair, not the way's share


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


def _key(**kw) -> RunKey:
    return RunKey(**{**KEY.__dict__, **kw})


def _done(conn, key: RunKey) -> int:
    rid = start_run(conn, key, git_commit="g", region_md5="m")
    complete_run(conn, rid, key.city_id, _result(), _metrics())
    return rid


def test_latest_done_run_ignores_other_parameters_and_classifier_versions(conn):
    default = _done(conn, KEY)
    both = '{"plain_cycleway_on_oneway":"both_sides"}'
    sensitivity = _done(conn, _key(classifier_parameters=both))
    other_version = _done(conn, _key(classifier_version="v2"))
    assert default < sensitivity < other_version
    assert latest_done_run(conn, "berlin", "lau") == default
    assert latest_done_run(conn, "berlin", "lau", "v1", both) == sensitivity
    assert latest_done_run(conn, "berlin", "lau", "v2") == other_version


def test_default_parameters_are_the_classifier_defaults_in_canonical_form():
    from velometer.config import load_classifier
    from velometer.db import canonical_parameters

    cfg = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
    assert canonical_parameters(cfg.parameters.model_dump()) == DEFAULT_PARAMETERS


def test_config_sha_is_part_of_the_run_key(conn):
    rid = _done(conn, KEY)
    assert find_done_run(conn, KEY) == rid
    assert find_done_run(conn, _key(config_sha256="other")) is None
    assert _done(conn, _key(config_sha256="other")) != rid  # coexists: unique index includes it


def test_start_run_records_the_population_it_used(conn):
    pop = Population(value=3782202, year=2024, source="GISCO LAU 2024 POP_2024")
    rid = start_run(conn, KEY, git_commit="g", region_md5="m", population=pop)
    row = conn.execute(
        "SELECT population_value, population_year, population_source, config_sha256 "
        "FROM runs WHERE id=?",
        (rid,),
    ).fetchone()
    assert row == (3782202, 2024, "GISCO LAU 2024 POP_2024", "cfg")
    # a later boundaries fetch overwrites cities.population, never the run row
    set_population(conn, "berlin", Population(value=1, year=2025, source="x"))
    assert conn.execute("SELECT population_value FROM runs WHERE id=?", (rid,)).fetchone()[0] == (
        3782202
    )


_V2_RUNS = (
    "CREATE TABLE runs (id INTEGER PRIMARY KEY, city_id TEXT NOT NULL REFERENCES cities(id), "
    "started_at TEXT NOT NULL, finished_at TEXT, classifier_version TEXT NOT NULL, "
    "classifier_parameters TEXT NOT NULL, git_commit TEXT NOT NULL, osm_timestamp TEXT NOT NULL, "
    "region_md5 TEXT NOT NULL, boundary_kind TEXT NOT NULL CHECK (boundary_kind IN "
    "('lau','fua','osm_admin','none')), boundary_sha256 TEXT NOT NULL, status TEXT NOT NULL "
    "CHECK (status IN ('running','done','failed')), error TEXT);"
    "CREATE UNIQUE INDEX runs_done_key ON runs (city_id, osm_timestamp, boundary_kind, "
    "boundary_sha256, classifier_version, classifier_parameters) WHERE status = 'done';"
)


def test_v2_db_with_done_runs_migrates_additively_and_old_runs_are_not_reused(tmp_path, cities):
    path = tmp_path / "v.sqlite"
    with open_db(path) as c:
        create_schema(c)
        upsert_cities(c, cities)
        c.execute("DROP TABLE duplicates")
        c.execute("DROP TABLE completeness")
        c.execute("DROP TABLE metrics")
        c.execute("DROP TABLE road_lengths")
        c.execute("DROP TABLE tier_lengths")
        c.execute("DROP TABLE runs")
        c.executescript(_V2_RUNS)
        c.execute(
            "INSERT INTO runs (id, city_id, started_at, classifier_version, classifier_parameters,"
            " git_commit, osm_timestamp, region_md5, boundary_kind, boundary_sha256, status) "
            "VALUES (1, 'berlin', 't', ?, ?, 'g', ?, 'm', 'lau', 'abc', 'done')",
            (KEY.classifier_version, KEY.classifier_parameters, KEY.osm_timestamp),
        )
        c.execute("PRAGMA user_version = 2")
        c.commit()
    with open_db(path) as c:
        create_schema(c)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert c.execute("SELECT id, status, config_sha256 FROM runs").fetchall() == [
            (1, "done", None)
        ]
        assert find_done_run(c, KEY) is None  # NULL config sha never matches
        new = _done(c, KEY)  # same key otherwise: the rebuilt unique index lets it complete
        assert latest_done_run(c, "berlin", "lau") == new
        assert c.execute("SELECT status FROM runs WHERE id=1").fetchone()[0] == "done"


def test_start_run_rejects_a_missing_or_empty_config_sha(conn):
    for bad in ("", None):
        with pytest.raises(ValueError, match="config_sha256"):
            start_run(conn, _key(config_sha256=bad), git_commit="g", region_md5="m")
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


def test_latest_done_run_with_a_config_sha_survives_an_edit_and_revert(conn):
    """A, then B, then A again: the A run is skipped as done, but B is newer by id."""
    a = _done(conn, _key(config_sha256="A"))
    b = _done(conn, _key(config_sha256="B"))
    assert find_done_run(conn, _key(config_sha256="A")) == a  # the revert reuses run a
    assert latest_done_run(conn, "berlin", "lau") == b  # unfiltered: the newest, stale one
    assert latest_done_run(conn, "berlin", "lau", config_sha256="A") == a
    assert latest_done_run(conn, "berlin", "lau", config_sha256="B") == b
    assert latest_done_run(conn, "berlin", "lau", config_sha256="C") is None


_V3_METRICS = (
    "CREATE TABLE metrics (run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL "
    "REFERENCES cities(id), preset TEXT NOT NULL, length_basis TEXT NOT NULL CHECK "
    "(length_basis IN ('per_side','qecio_weighted')), value REAL, numerator_km REAL NOT NULL, "
    "denominator_km REAL NOT NULL, per_100k REAL, PRIMARY KEY (run_id, city_id, preset));"
)


def test_v3_db_with_metric_rows_migrates_to_v4_and_keeps_them(tmp_path, cities):
    path = tmp_path / "v.sqlite"
    with open_db(path) as c:
        create_schema(c)
        upsert_cities(c, cities)
        rid = _done(c, KEY)
        c.execute("DROP TABLE metrics")
        c.executescript(_V3_METRICS)
        c.execute(
            "INSERT INTO metrics VALUES (?, 'berlin', 'clean_cities_2025', 'per_side', "
            "17.5, 1000.0, 5000.0, 12.5)",
            (rid,),
        )
        c.execute("PRAGMA user_version = 3")
        c.commit()
    with open_db(path) as c:
        create_schema(c)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert c.execute("SELECT * FROM metrics").fetchall() == [
            (rid, "berlin", "clean_cities_2025", "per_side", 17.5, 1000.0, 5000.0, 12.5)
        ]
        assert not any(t.startswith("metrics_") for t in _tables(c))
        # the v3 key (run, city, preset) is gone: the same preset may now sit on two bases
        c.execute(
            "INSERT INTO metrics VALUES (?, 'berlin', 'clean_cities_2025', 'qecio_weighted', "
            "9.0, 600.0, 5000.0, NULL)",
            (rid,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO metrics VALUES (?, 'berlin', 'clean_cities_2025', 'per_side', "
                "1, 1, 1, NULL)",
                (rid,),
            )


def test_two_bases_of_one_preset_are_stored_and_fetched(conn):
    rid = start_run(conn, KEY, git_commit="g", region_md5="m")
    both = [
        Metric(
            preset="clean_cities_2025",
            length_basis=b,
            value=v,
            numerator_km=v,
            denominator_km=100.0,
        )
        for b, v in (("per_side", 30.0), ("qecio_weighted", 18.0))
    ]
    complete_run(conn, rid, "berlin", _result(), both)
    got = fetch_run_results(conn, rid).metrics
    assert {(m.preset, m.length_basis, m.value) for m in got} == {
        ("clean_cities_2025", "per_side", 30.0),
        ("clean_cities_2025", "qecio_weighted", 18.0),
    }


SHA = "cfg"


def test_migration_4_to_5_keeps_runs_and_marks_them_current(tmp_path, cities):
    path = tmp_path / "v.sqlite"
    with open_db(path) as c:
        create_schema(c)
        upsert_cities(c, cities)
        rid = _done(c, KEY)
        # rewind to v4: no source column, the v4 key index, no activity/diagnostics tables
        c.execute("DROP INDEX runs_done_key")
        c.execute("ALTER TABLE runs DROP COLUMN source")
        c.execute(
            "CREATE UNIQUE INDEX runs_done_key ON runs (city_id, osm_timestamp, boundary_kind, "
            "boundary_sha256, classifier_version, classifier_parameters, config_sha256) "
            "WHERE status = 'done'"
        )
        c.execute("DROP TABLE activity")
        c.execute("DROP TABLE diagnostics")
        c.execute("DROP TABLE history_sets")
        c.execute("PRAGMA user_version = 4")
        c.commit()
        assert "source" not in {r[1] for r in c.execute("PRAGMA table_info(runs)")}
    with open_db(path) as c:
        create_schema(c)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert c.execute("SELECT id, source, status FROM runs").fetchall() == [
            (rid, "current", "done")
        ]
        assert {"activity", "diagnostics", "history_sets"} <= _tables(c)
        upsert_history_set(
            c, "h", [], index_path="i", index_sha256="s", uncovered_km2=0.0
        )  # the migrated table is usable
        assert find_done_run(c, KEY) == rid
        assert find_done_run(c, replace(KEY, source="history")) is None
        assert _done(c, replace(KEY, source="history")) != rid  # the rebuilt index has source


def test_history_and_current_runs_with_same_key_fields_are_distinct(conn):
    k_cur = _key(osm_timestamp="2026-01-01T00:00:00Z")
    k_his = replace(k_cur, source="history")
    a = start_run(conn, k_cur, git_commit="g", region_md5="m")
    complete_run(conn, a, "berlin", _result(), [])
    assert find_done_run(conn, k_his) is None
    b = start_run(conn, k_his, git_commit="g", region_md5="m")
    complete_run(conn, b, "berlin", _result(), [])  # the unique index allows both
    assert find_done_run(conn, k_his) == b
    assert find_done_run(conn, k_cur) == a


def test_run_source_rejects_unknown_values(conn):
    with pytest.raises(sqlite3.IntegrityError):
        start_run(conn, _key(source="bogus"), git_commit="g", region_md5="m")


def test_latest_done_run_ignores_history_runs(conn):
    current_id = _done(conn, _key(osm_timestamp="2026-01-01T00:00:00Z"))
    _done(conn, _key(osm_timestamp="2026-06-01T00:00:00Z", source="history"))  # later data
    assert latest_done_run(conn, "berlin", "lau", config_sha256=SHA) == current_id
    assert latest_done_run(conn, "berlin", "lau") == current_id


def test_history_runs_maps_timestamps_of_matching_done_history_runs(conn):
    def hist(ts, md5="h", **kw):
        rid = start_run(
            conn, _key(osm_timestamp=ts, source="history", **kw), git_commit="g", region_md5=md5
        )
        complete_run(conn, rid, "berlin", _result(), [])
        return rid

    a, b = hist("2019-01-01T00:00:00Z"), hist("2020-01-01T00:00:00Z")
    hist("2021-01-01T00:00:00Z", md5="other")  # another history set
    hist("2022-01-01T00:00:00Z", config_sha256="x")  # another config
    failed = start_run(
        conn,
        _key(osm_timestamp="2023-01-01T00:00:00Z", source="history"),
        git_commit="g",
        region_md5="h",
    )
    fail_run(conn, failed, "boom")
    _done(conn, _key(osm_timestamp="2024-01-01T00:00:00Z"))  # a current run
    got = history_runs(
        conn,
        "berlin",
        "lau",
        classifier_version="v1",
        classifier_parameters=DEFAULT_PARAMETERS,
        config_sha256=SHA,
        history_set_md5="h",
    )
    assert got == {"2019-01-01T00:00:00Z": a, "2020-01-01T00:00:00Z": b}


def _activity_row(year=2019, **kw):
    return ActivityYear(
        **{
            **dict(
                city_id="berlin",
                boundary_kind="lau",
                year=year,
                history_set_md5="h",
                n_edits=3,
                n_changesets=2,
                n_mappers=2,
                top_mapper_share=0.67,
                n_ways_created_cycling=1,
                n_ways_deleted_cycling=0,
            ),
            **kw,
        }
    )


SHA_A, SHA_B = "a" * 64, "b" * 64


def test_replace_activity_is_atomic_and_round_trips(conn):
    rows = [_activity_row(2019), _activity_row(2020, n_edits=9)]
    replace_activity(conn, "berlin", "lau", "h", SHA_A, rows)
    replace_activity(conn, "berlin", "lau", "h", SHA_A, rows)  # replace, not duplicate
    assert fetch_activity(conn, "berlin", "lau", "h", SHA_A) == rows
    other = [_activity_row(2019, history_set_md5="g")]
    replace_activity(conn, "berlin", "lau", "g", SHA_A, other)  # another set is left alone
    assert fetch_activity(conn, "berlin", "lau", "h", SHA_A) == rows
    assert fetch_activity(conn, "berlin", "lau", "g", SHA_A) == other
    # atomic: a failing replace (duplicate year) keeps the previous rows
    with pytest.raises(sqlite3.IntegrityError):
        replace_activity(
            conn, "berlin", "lau", "h", SHA_A, [_activity_row(2021), _activity_row(2021)]
        )
    assert fetch_activity(conn, "berlin", "lau", "h", SHA_A) == rows


def test_activity_is_keyed_by_activity_sha(conn):
    rows_a = [_activity_row(2019), _activity_row(2020)]
    rows_b = [_activity_row(2019, n_edits=77)]
    replace_activity(conn, "berlin", "lau", "h", SHA_A, rows_a)
    replace_activity(conn, "berlin", "lau", "h", SHA_B, rows_b)
    assert fetch_activity(conn, "berlin", "lau", "h", SHA_A) == rows_a
    assert fetch_activity(conn, "berlin", "lau", "h", SHA_B) == rows_b
    new_a = [_activity_row(2019, n_edits=5)]
    replace_activity(conn, "berlin", "lau", "h", SHA_A, new_a)  # replacing A leaves B untouched
    assert fetch_activity(conn, "berlin", "lau", "h", SHA_A) == new_a
    assert fetch_activity(conn, "berlin", "lau", "h", SHA_B) == rows_b
    assert fetch_activity(conn, "berlin", "lau", "h", "c" * 64) == []


_V5_ACTIVITY = """
CREATE TABLE activity (
  city_id TEXT NOT NULL REFERENCES cities(id), boundary_kind TEXT NOT NULL,
  year INTEGER NOT NULL, history_set_md5 TEXT NOT NULL,
  n_edits INTEGER NOT NULL, n_changesets INTEGER NOT NULL, n_mappers INTEGER NOT NULL,
  top_mapper_share REAL NOT NULL, n_ways_created_cycling INTEGER NOT NULL,
  n_ways_deleted_cycling INTEGER NOT NULL,
  PRIMARY KEY (city_id, boundary_kind, year, history_set_md5)
)
"""


def _make_v5_db_with_activity(path, rows):
    """A v5 database (activity without a sha) holding `rows` activity rows."""
    with open_db(path) as c:
        create_schema(c)
        upsert_cities(c, load_cities(default_config_dir() / "cities.yaml"))
        c.execute("DROP TABLE activity")
        c.execute(_V5_ACTIVITY)
        for i in range(rows):
            c.execute(
                "INSERT INTO activity VALUES ('berlin','lau',?,'h',3,2,2,0.67,1,0)", (2019 + i,)
            )
        c.execute("PRAGMA user_version = 5")
        c.commit()


def _master(c):
    """sqlite_master without the identifier quotes ALTER ... RENAME adds to a table's name."""
    rows = c.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
    return sorted((t, n, (sql or "").replace('"', "")) for t, n, sql in rows)


def test_v5_to_v6_keeps_activity_rows_under_the_given_sha(tmp_path):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=3)
    with open_db(path) as c:
        create_schema(c, activity_sha256_for_v5="f" * 64)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        shas = {r[0] for r in c.execute("SELECT activity_sha256 FROM activity")}
        assert shas == {"f" * 64}
        assert c.execute("SELECT count(*) FROM activity").fetchone()[0] == 3
        assert len(fetch_activity(c, "berlin", "lau", "h", "f" * 64)) == 3
    with open_db(tmp_path / "fresh.sqlite") as fresh, open_db(path) as migrated:
        create_schema(fresh)
        assert _master(migrated) == _master(fresh)  # the migrated schema equals a fresh one


def test_v6_migration_is_atomic(tmp_path, monkeypatch):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=3)

    def boom(conn):
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "_after_activity_copy", boom)
    with open_db(path) as c, pytest.raises(RuntimeError):
        create_schema(c, activity_sha256_for_v5="f" * 64)
    with open_db(path) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 5
        assert c.execute("SELECT count(*) FROM activity").fetchone()[0] == 3
        assert "activity_sha256" not in {r[1] for r in c.execute("PRAGMA table_info(activity)")}
        assert "activity_v6" not in _tables(c)


def test_interrupt_after_schema_ddl_keeps_old_version(tmp_path, monkeypatch):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=0)

    def boom(conn, v):
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "_set_user_version", boom)
    with open_db(path) as conn, pytest.raises(RuntimeError):
        create_schema(conn)
    with open_db(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        cols = {r[1] for r in conn.execute("PRAGMA table_info(activity)")}
        assert "activity_sha256" not in cols  # the v6 rebuild rolled back too


def test_v5_with_activity_rows_needs_the_sha(tmp_path):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=2)
    with open_db(path) as c, pytest.raises(SchemaError, match="velometer migrate --activity-sha"):
        create_schema(c)
    with open_db(path) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 5


def test_v5_with_empty_activity_migrates_without_a_sha(tmp_path):
    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=0)
    with open_db(path) as c:
        create_schema(c)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert "activity_sha256" in {r[1] for r in c.execute("PRAGMA table_info(activity)")}


_V8_TABLES = ("subareas", "subarea_tier_lengths", "subarea_road_lengths")


def _make_v6_db_with_runs(path, cities):
    """A v6 database: a done run, no peak_rss_kb column."""
    with open_db(path) as c:
        create_schema(c)
        upsert_cities(c, cities)
        rid = _done(c, KEY)
        for t in _V8_TABLES:
            c.execute(f"DROP TABLE {t}")
        c.execute("ALTER TABLE runs DROP COLUMN subarea_sha")
        c.execute("ALTER TABLE runs DROP COLUMN peak_rss_kb")
        c.execute("PRAGMA user_version = 6")
        c.commit()
    return rid


def test_v6_to_v7_adds_a_null_peak_rss_and_keeps_runs(tmp_path, cities):
    path = tmp_path / "v6.sqlite"
    rid = _make_v6_db_with_runs(path, cities)
    with open_db(path) as c:
        assert "peak_rss_kb" not in {r[1] for r in c.execute("PRAGMA table_info(runs)")}
        before = c.execute("SELECT * FROM runs").fetchall()
    with open_db(path) as c:
        create_schema(c)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert fetch_run(c, rid)["peak_rss_kb"] is None
        after = c.execute("SELECT * FROM runs").fetchall()
        assert [r[:-2] for r in after] == before  # runs untouched; NULL columns appended
        assert after[0][-2] is None  # peak_rss_kb; v8 adds subarea_sha after it
    with open_db(tmp_path / "fresh.sqlite") as fresh, open_db(path) as migrated:
        create_schema(fresh)
        cols = "SELECT name, type, \"notnull\", dflt_value, pk FROM pragma_table_info('runs')"
        assert migrated.execute(cols).fetchall() == fresh.execute(cols).fetchall()


def _make_v7_db_with_runs(path, cities):
    """A v7 database: a done run, no subarea tables, no runs.subarea_sha."""
    with open_db(path) as c:
        create_schema(c)
        upsert_cities(c, cities)
        rid = _done(c, KEY)
        for t in _V8_TABLES:
            c.execute(f"DROP TABLE {t}")
        c.execute("ALTER TABLE runs DROP COLUMN subarea_sha")
        c.execute("PRAGMA user_version = 7")
        c.commit()
    return rid


def test_v7_db_migrates_to_v8_keeping_every_row(tmp_path, cities):
    path = tmp_path / "v7.sqlite"
    rid = _make_v7_db_with_runs(path, cities)
    counts = "SELECT (SELECT count(*) FROM cities), (SELECT count(*) FROM runs), "
    counts += "(SELECT count(*) FROM tier_lengths), (SELECT count(*) FROM road_lengths)"
    with open_db(path) as c:
        assert not set(_V8_TABLES) & _tables(c)
        before = c.execute(counts).fetchall()
        runs_before = c.execute("SELECT * FROM runs").fetchall()
    with open_db(path) as c:
        create_schema(c)
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert set(_V8_TABLES) <= _tables(c)
        assert c.execute(counts).fetchall() == before
        assert fetch_run(c, rid)["subarea_sha"] is None
        after = c.execute("SELECT * FROM runs").fetchall()
        assert [r[:-1] for r in after] == runs_before  # one NULL column appended
    with open_db(tmp_path / "fresh.sqlite") as fresh, open_db(path) as migrated:
        create_schema(fresh)
        for t in ("runs", *_V8_TABLES):
            cols = f"SELECT name, type, \"notnull\", dflt_value, pk FROM pragma_table_info('{t}')"
            assert migrated.execute(cols).fetchall() == fresh.execute(cols).fetchall()


def test_interrupted_v7_to_v8_leaves_v7(tmp_path, cities, monkeypatch):
    path = tmp_path / "v7.sqlite"
    _make_v7_db_with_runs(path, cities)
    real = db._migrate_7_to_8

    def run_ddl_then_fail(conn):
        real(conn)
        raise RuntimeError("boom")

    monkeypatch.setitem(db._MIGRATIONS, 7, run_ddl_then_fail)
    with open_db(path) as c, pytest.raises(RuntimeError):
        create_schema(c)
    with open_db(path) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 7
        assert "subareas" not in _tables(c)
        assert "subarea_sha" not in {r[1] for r in c.execute("PRAGMA table_info(runs)")}


def test_subareas_upsert_and_rows_roundtrip(conn):
    rid = start_run(conn, KEY, git_commit="g", region_md5="m")
    conn.execute(
        "INSERT INTO subarea_tier_lengths "
        "VALUES (?, 'berlin', 'mitte', 'A', '', 'per_side', 2.5, 3)",
        (rid,),
    )
    conn.execute(
        "INSERT INTO subarea_tier_lengths "
        "VALUES (?, 'berlin', 'mitte', 'B', 'lane', 'per_side', 1, 2)",
        (rid,),
    )
    conn.execute(
        "INSERT INTO subarea_road_lengths VALUES (?, 'berlin', 'mitte', 'all_public', 40.5)",
        (rid,),
    )
    conn.commit()
    sub = Subarea(
        city_id="berlin",
        subarea_id="mitte",
        name="Mitte",
        source="osm",
        relation_id=None,
        area_km2=39.5,
        path="p",
        sha256="s",
    )
    db.upsert_subareas(conn, [sub])
    db.upsert_subareas(conn, [replace_name(sub, "Mitte 2")])  # upsert, not duplicate
    assert conn.execute("SELECT name, relation_id FROM subareas").fetchall() == [("Mitte 2", None)]
    rows = db.subarea_rows(conn, rid)
    tiers, roads = rows["mitte"]
    assert [(t.tier, t.subtype, t.city_id, t.run_id) for t in tiers] == [
        ("A", None, "berlin", rid),
        ("B", "lane", "berlin", rid),
    ]
    assert [(r.road_class, r.length_km) for r in roads] == [("all_public", 40.5)]
    assert db.subarea_rows(conn, rid + 1) == {}


def replace_name(sub, name):
    return sub.model_copy(update={"name": name})


def test_complete_run_stores_peak_rss(conn):
    rid = start_run(conn, KEY, git_commit="g", region_md5="m")
    complete_run(conn, rid, "berlin", _result(), _metrics(), peak_rss_kb=123_456)
    assert fetch_run(conn, rid)["peak_rss_kb"] == 123_456


def test_activity_table_has_no_user_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(activity)")}
    assert not cols & {"uid", "user", "user_id", "username", "mapper"}


def test_diagnostics_written_with_the_run_and_rolled_back_with_it(conn):
    rid = start_run(conn, KEY, git_commit="g", region_md5="m")
    complete_run(conn, rid, "berlin", _result(), _metrics(), diagnostics={"legacy_km": 1.5})
    assert fetch_diagnostics(conn, rid) == {"legacy_km": 1.5}
    other = start_run(
        conn, _key(osm_timestamp="2026-01-01T00:00:00Z"), git_commit="g", region_md5="m"
    )
    assert fetch_diagnostics(conn, other) == {}
    with pytest.raises(sqlite3.IntegrityError):  # duplicate metric rows
        complete_run(
            conn, other, "berlin", _result(), _metrics() + _metrics(), diagnostics={"x": 2.0}
        )
    assert fetch_diagnostics(conn, other) == {}
    assert conn.execute("SELECT COUNT(*) FROM diagnostics").fetchone()[0] == 1


def test_history_set_upsert_keeps_first_row_and_roundtrips(conn):
    regions = [{"region": "a", "md5": "m", "md5_source": "computed", "fetched_at": "2026-10-01"}]
    upsert_history_set(
        conn, "h", regions, index_path="p/index.json", index_sha256="x", uncovered_km2=0.25
    )
    upsert_history_set(conn, "h", [], index_path="other", index_sha256="y", uncovered_km2=9.0)
    got = fetch_history_set(conn, "h")
    assert got["regions"] == regions
    assert (got["index_path"], got["index_sha256"], got["uncovered_km2"]) == (
        "p/index.json",
        "x",
        0.25,
    )
    assert got["recorded_at"]
    assert fetch_history_set(conn, "missing") is None


def test_two_history_sets_may_each_hold_a_done_run_for_the_same_year(conn):
    k = _key(osm_timestamp="2020-01-01T00:00:00Z", source="history")
    ids = []
    for md5 in ("old", "new"):
        rid = start_run(conn, k, git_commit="g", region_md5=md5)
        complete_run(conn, rid, "berlin", _result(), [])
        ids.append(rid)
    assert len(set(ids)) == 2
    assert conn.execute("SELECT COUNT(*) FROM runs WHERE status='done'").fetchone()[0] == 2


def test_v5_db_with_old_done_key_index_is_repaired(tmp_path):
    path = tmp_path / "v.sqlite"
    with open_db(path) as c:
        create_schema(c)
        c.execute("DROP INDEX runs_done_key")
        c.execute(
            "CREATE UNIQUE INDEX runs_done_key ON runs (city_id, osm_timestamp, boundary_kind, "
            "boundary_sha256, classifier_version, classifier_parameters, config_sha256, source) "
            "WHERE status = 'done'"
        )
        c.commit()
    with open_db(path) as c:
        create_schema(c)
        sql = c.execute("SELECT sql FROM sqlite_master WHERE name='runs_done_key'").fetchone()[0]
        assert "region_md5" in sql
        create_schema(c)  # idempotent
