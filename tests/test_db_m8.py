"""Schema v9: plan overlay and counter tables, their repositories and the ReportData accessors."""

import sqlite3

import pytest

from velometer.db import (
    SCHEMA_VERSION,
    CounterDay,
    CounterIndexYear,
    CounterMonth,
    CounterSite,
    OverlayRow,
    create_schema,
    replace_counter_index,
    replace_counter_monthly,
    replace_counter_sites,
    replace_plan_overlay,
    upsert_counter_daily,
)
from velometer.report.data import ReportData

NEW_TABLES = ("plan_overlay", "counter_sites", "counter_daily", "counter_monthly", "counter_index")


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _v8_db(path):
    """A v8 database: the current schema without the five M8 tables, user_version 8."""
    conn = sqlite3.connect(path)
    create_schema(conn)
    for t in NEW_TABLES:
        conn.execute(f"DROP TABLE {t}")
    conn.execute("PRAGMA user_version = 8")
    conn.commit()
    return conn


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "v9.sqlite")
    c.row_factory = sqlite3.Row
    create_schema(c)
    yield c
    c.close()


def _run(conn, run_id=1):
    conn.execute(
        """INSERT INTO runs (id, city_id, started_at, classifier_version, classifier_parameters,
  git_commit, osm_timestamp, region_md5, boundary_kind, boundary_sha256, status)
  VALUES (?, 'berlin', 't', 'v', '{}', 'g', 't', 'm', 'lau', 's', 'done')""",
        (run_id,),
    )
    conn.commit()


def _overlay(version="v1", km=1.0, run_id=1, cls="primary", tier="A"):
    return OverlayRow(run_id, "berlin", cls, tier, km, km * 2, version, "2026-10-07T00:00:00Z")


def test_fresh_db_has_the_five_tables_at_v9(conn):
    assert SCHEMA_VERSION == 9
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 9
    assert set(NEW_TABLES) <= _tables(conn)


def test_v8_db_migrates_with_row_counts_unchanged(tmp_path):
    path = tmp_path / "v8.sqlite"
    c = _v8_db(path)
    _run(c)
    before = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in _tables(c)}
    assert not set(NEW_TABLES) & _tables(c)
    create_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 9
    assert set(NEW_TABLES) <= _tables(c)
    for t, n in before.items():
        assert c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] == n
    c.close()


def test_upsert_counter_daily_is_idempotent(conn):
    rows = [CounterDay("berlin", "s1", "2024-01-01", 10, True)]
    rows.append(CounterDay("berlin", "s1", "2024-01-02", 20, False))
    upsert_counter_daily(conn, rows)
    upsert_counter_daily(conn, rows)
    assert conn.execute("SELECT count(*) FROM counter_daily").fetchone()[0] == 2
    upsert_counter_daily(conn, [CounterDay("berlin", "s1", "2024-01-01", 99, False)])
    got = conn.execute(
        "SELECT count, complete FROM counter_daily WHERE day='2024-01-01'"
    ).fetchone()
    assert tuple(got) == (99, 0)


def test_negative_count_is_refused(conn):
    with pytest.raises(sqlite3.IntegrityError):
        upsert_counter_daily(conn, [CounterDay("berlin", "s1", "2024-01-01", -1, True)])


def test_replace_plan_overlay_replaces_only_the_same_version(conn):
    _run(conn)
    replace_plan_overlay(conn, "berlin", [_overlay("v1", 1.0), _overlay("v2", 5.0)])
    replace_plan_overlay(conn, "berlin", [_overlay("v1", 3.0, tier="B")])
    rows = conn.execute(
        "SELECT overlay_version, tier, mapped_km FROM plan_overlay ORDER BY 1, 2"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("v1", "B", 3.0), ("v2", "A", 5.0)]


def test_replace_plan_overlay_leaves_other_cities(conn):
    _run(conn)
    _run(conn, 2)
    other = OverlayRow(2, "paris", "primary", "A", 1.0, 2.0, "v1", "t")
    replace_plan_overlay(conn, "paris", [other])
    replace_plan_overlay(conn, "berlin", [_overlay("v1")])
    assert conn.execute("SELECT count(*) FROM plan_overlay").fetchone()[0] == 2


def _site(site_id="s1", city="berlin"):
    return CounterSite(
        city, site_id, "Site", 52.5, 13.4, "src", "CC-BY", "http://x", "t", None, None
    )


def test_replace_counter_tables_are_per_city(conn):
    replace_counter_sites(conn, "berlin", [_site("s1"), _site("s2")])
    replace_counter_sites(conn, "paris", [_site("p1", "paris")])
    replace_counter_sites(conn, "berlin", [_site("s3")])
    got = {r[0] for r in conn.execute("SELECT site_id FROM counter_sites")}
    assert got == {"s3", "p1"}

    replace_counter_monthly(conn, "berlin", [CounterMonth("berlin", "s3", "2024-01", "all", 5.0)])
    replace_counter_monthly(conn, "berlin", [CounterMonth("berlin", "s3", "2024-02", "all", 6.0)])
    assert [r[0] for r in conn.execute("SELECT month FROM counter_monthly")] == ["2024-02"]

    y = CounterIndexYear("berlin", 2020, None, 3, 2019, "counts")
    replace_counter_index(
        conn, "berlin", [y, CounterIndexYear("berlin", 2021, 1.1, 3, 2019, "counts")]
    )
    replace_counter_index(conn, "berlin", [y])
    rows = conn.execute("SELECT year, idx, series FROM counter_index").fetchall()
    assert [tuple(r) for r in rows] == [(2020, None, "counts")]


def _data(conn, cfg):
    return ReportData(conn, cfg)


def test_reportdata_accessors_roundtrip(fixture_db):
    db_path, cfg, _, _ = fixture_db
    w = sqlite3.connect(db_path)
    w.row_factory = sqlite3.Row
    run_id = w.execute("SELECT id FROM runs LIMIT 1").fetchone()[0]
    replace_plan_overlay(w, "berlin", [_overlay(run_id=run_id)])
    replace_counter_sites(w, "berlin", [_site()])
    replace_counter_index(w, "berlin", [CounterIndexYear("berlin", 2021, 1.1, 3, 2019, "counts")])
    w.close()
    ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    data = _data(ro, cfg)
    assert data.plan_overlay("berlin") == [_overlay(run_id=run_id)]
    assert data.counter_sites("berlin") == [_site()]
    assert data.counter_index("berlin") == [
        CounterIndexYear("berlin", 2021, 1.1, 3, 2019, "counts")
    ]
    assert data.counter_cities() == ["berlin"]
    assert data.plan_overlay("paris") == []
    ro.close()


def test_reportdata_on_a_v8_db_returns_empty_everywhere(fixture_db, tmp_path):
    _, cfg, _, _ = fixture_db
    path = tmp_path / "v8.sqlite"
    _v8_db(path).close()
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    data = _data(ro, cfg)
    assert data.plan_overlay("berlin") == []
    assert data.counter_sites("berlin") == []
    assert data.counter_index("berlin") == []
    assert data.counter_cities() == []
    ro.close()
