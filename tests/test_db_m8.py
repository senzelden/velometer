"""Schemas v9 and v10: plan overlay and counter tables, their repositories, ReportData accessors."""

import re
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
    replace_counter_daily,
    replace_counter_index,
    replace_counter_monthly,
    replace_counter_sites,
    replace_plan_overlay,
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


def test_fresh_db_has_the_five_tables_at_the_current_version(conn):
    assert SCHEMA_VERSION == 10
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert set(NEW_TABLES) <= _tables(conn)


def _fill_every_table(conn) -> None:
    """One row in every table: a value per column that its type and any `CHECK (col IN ...)`
    accept (foreign keys are off on a plain connection)."""
    for name, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
        allowed = dict(re.findall(r"CHECK \((\w+) IN\s*\('([^']+)'", sql))
        cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
        values = []
        for _cid, col, decl, *_ in cols:
            if col in allowed:
                values.append(allowed[col])
            elif "INT" in decl.upper():
                values.append(1)
            elif "REAL" in decl.upper():
                values.append(1.0)
            else:
                values.append("x")
        conn.execute(f"INSERT INTO {name} VALUES ({','.join('?' * len(values))})", values)
    conn.commit()


def test_v8_db_migrates_with_row_counts_unchanged(tmp_path):
    path = tmp_path / "v8.sqlite"
    c = _v8_db(path)
    _fill_every_table(c)
    before = {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in _tables(c)}
    assert before and all(n > 0 for n in before.values())  # every preserved table has rows
    assert not set(NEW_TABLES) & _tables(c)
    create_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert set(NEW_TABLES) <= _tables(c)
    for t, n in before.items():
        assert c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] == n
    c.close()


def _day(site="s1", day="2024-01-01", count=10, complete=True, city="berlin"):
    return CounterDay(city, site, day, count, complete)


def test_replace_counter_daily_replaces_only_that_citys_days(conn):
    replace_counter_daily(conn, "paris", [_day("p1", city="paris")])
    replace_counter_daily(conn, "berlin", [_day(), _day(day="2024-01-02", count=20)])
    replace_counter_daily(conn, "berlin", [_day(count=99, complete=False)])
    got = conn.execute(
        "SELECT city_id, site_id, day, count, complete FROM counter_daily ORDER BY 1"
    ).fetchall()
    # the day the new rows no longer give is gone; the other city's rows stay
    assert [tuple(r) for r in got] == [
        ("berlin", "s1", "2024-01-01", 99, 0),
        ("paris", "p1", "2024-01-01", 10, 1),
    ]


def test_negative_count_is_refused(conn):
    with pytest.raises(sqlite3.IntegrityError):
        replace_counter_daily(conn, "berlin", [_day(count=-1)])


def test_replace_plan_overlay_replaces_only_the_same_version(conn):
    _run(conn)
    replace_plan_overlay(conn, "berlin", "v1", [_overlay("v1", 1.0)])
    replace_plan_overlay(conn, "berlin", "v2", [_overlay("v2", 5.0)])
    replace_plan_overlay(conn, "berlin", "v1", [_overlay("v1", 3.0, tier="B")])
    rows = conn.execute(
        "SELECT overlay_version, tier, mapped_km FROM plan_overlay ORDER BY 1, 2"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("v1", "B", 3.0), ("v2", "A", 5.0)]


def test_replace_plan_overlay_with_no_rows_clears_that_version(conn):
    """The overlay CLI's scope: the city's rows of the version it ran, even when it has none."""
    _run(conn)
    _run(conn, 2)
    replace_plan_overlay(conn, "berlin", "v1", [_overlay("v1")])
    replace_plan_overlay(conn, "berlin", "v2", [_overlay("v2")])
    replace_plan_overlay(conn, "paris", "v1", [OverlayRow(2, "paris", "p", "A", 1, 2, "v1", "t")])
    replace_plan_overlay(conn, "berlin", "v1", [])
    rows = conn.execute("SELECT city_id, overlay_version FROM plan_overlay ORDER BY 1").fetchall()
    assert [tuple(r) for r in rows] == [("berlin", "v2"), ("paris", "v1")]


def test_replace_plan_overlay_leaves_other_cities(conn):
    _run(conn)
    _run(conn, 2)
    other = OverlayRow(2, "paris", "primary", "A", 1.0, 2.0, "v1", "t")
    replace_plan_overlay(conn, "paris", "v1", [other])
    replace_plan_overlay(conn, "berlin", "v1", [_overlay("v1")])
    assert conn.execute("SELECT count(*) FROM plan_overlay").fetchone()[0] == 2


def test_replace_plan_overlay_refuses_a_row_of_another_version(conn):
    _run(conn)
    replace_plan_overlay(conn, "berlin", "v2", [_overlay("v2")])
    with pytest.raises(ValueError, match="overlay_version 'v1'"):
        replace_plan_overlay(conn, "berlin", "v2", [_overlay("v1")])
    assert conn.execute("SELECT overlay_version FROM plan_overlay").fetchall()[0][0] == "v2"


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

    y = CounterIndexYear("berlin", 2020, None, 3, 2019, "counts", "v2")
    replace_counter_index(
        conn, "berlin", [y, CounterIndexYear("berlin", 2021, 1.1, 3, 2019, "counts", "v2")]
    )
    replace_counter_index(conn, "berlin", [y])
    rows = conn.execute("SELECT year, idx, series FROM counter_index").fetchall()
    assert [tuple(r) for r in rows] == [(2020, None, "counts")]


def _another_citys(table):
    """The replace_* call of `table` given a paris row under city berlin."""
    paris = {
        "plan_overlay": lambda c: replace_plan_overlay(
            c, "berlin", "v1", [OverlayRow(1, "paris", "p", "A", 1.0, 2.0, "v1", "t")]
        ),
        "counter_sites": lambda c: replace_counter_sites(c, "berlin", [_site("p1", "paris")]),
        "counter_daily": lambda c: replace_counter_daily(c, "berlin", [_day(city="paris")]),
        "counter_monthly": lambda c: replace_counter_monthly(
            c, "berlin", [CounterMonth("paris", "p1", "2024-01", "all", 5.0)]
        ),
        "counter_index": lambda c: replace_counter_index(
            c, "berlin", [CounterIndexYear("paris", 2020, 1.0, 3, 2019, "counts", "v2")]
        ),
    }
    return paris[table]


def _berlin_row(table):
    return {
        "plan_overlay": lambda c: replace_plan_overlay(c, "berlin", "v1", [_overlay("v1")]),
        "counter_sites": lambda c: replace_counter_sites(c, "berlin", [_site()]),
        "counter_daily": lambda c: replace_counter_daily(c, "berlin", [_day()]),
        "counter_monthly": lambda c: replace_counter_monthly(
            c, "berlin", [CounterMonth("berlin", "s1", "2024-01", "all", 5.0)]
        ),
        "counter_index": lambda c: replace_counter_index(
            c, "berlin", [CounterIndexYear("berlin", 2020, 1.0, 3, 2019, "counts", "v2")]
        ),
    }[table]


@pytest.mark.parametrize("table", NEW_TABLES)
def test_replace_refuses_a_row_of_another_city_and_writes_nothing(conn, table):
    _run(conn)
    _berlin_row(table)(conn)
    with pytest.raises(ValueError, match="city_id 'paris'.*'berlin'"):
        _another_citys(table)(conn)
    rows = conn.execute(f"SELECT city_id FROM {table}").fetchall()
    assert [r[0] for r in rows] == ["berlin"]  # the berlin row was not deleted either


def test_optional_rows_tells_a_missing_table_by_the_schema_not_the_message(fixture_db):
    _, cfg, conn, data = fixture_db
    assert data._optional_rows("no_such_table_here", "SELECT 1 FROM no_such_table_here") == []
    # a present table whose query fails with a 'no such table' message is an error, not []
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        data._optional_rows("counter_sites", "SELECT * FROM counter_sites JOIN gone")


def _data(conn, cfg):
    return ReportData(conn, cfg)


def test_reportdata_accessors_roundtrip(fixture_db):
    db_path, cfg, _, _ = fixture_db
    w = sqlite3.connect(db_path)
    w.row_factory = sqlite3.Row
    run_id = w.execute("SELECT id FROM runs LIMIT 1").fetchone()[0]
    replace_plan_overlay(w, "berlin", "v1", [_overlay(run_id=run_id)])
    replace_counter_sites(w, "berlin", [_site()])
    replace_counter_index(
        w, "berlin", [CounterIndexYear("berlin", 2021, 1.1, 3, 2019, "counts", "v2")]
    )
    w.close()
    ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    data = _data(ro, cfg)
    assert data.plan_overlay("berlin") == [_overlay(run_id=run_id)]
    assert data.counter_sites("berlin") == [_site()]
    assert data.counter_index("berlin") == [
        CounterIndexYear("berlin", 2021, 1.1, 3, 2019, "counts", "v2")
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


# --- v10: counter_index keyed by method (M13 Task 2) -------------------------------------------

V9_COUNTER_INDEX = """CREATE TABLE counter_index (
  city_id TEXT NOT NULL, year INTEGER NOT NULL, idx REAL, sites INTEGER NOT NULL,
  base_year INTEGER NOT NULL, series TEXT NOT NULL, PRIMARY KEY (city_id, year, series)
)"""
V9_ROWS = [
    ("berlin", 2019, 100.0, 12, 2019, "counts"),
    ("berlin", 2020, 114.6, 11, 2019, "counts"),
    ("berlin", 2021, None, 2, 2019, "counts"),
    ("barcelona", 2019, 100.0, 4, 2019, "avg_daily_intensity"),
]


def v9_db(path, rows=V9_ROWS):
    """A schema-9 database: the current schema with M8's counter_index (no method), filled."""
    conn = sqlite3.connect(path)
    create_schema(conn)
    conn.execute("DROP TABLE counter_index")
    conn.execute(V9_COUNTER_INDEX)
    conn.executemany("INSERT INTO counter_index VALUES (?,?,?,?,?,?)", rows)
    conn.execute("PRAGMA user_version = 9")
    conn.commit()
    return conn


def test_v9_db_migrates_with_every_index_row_tagged_v1(tmp_path):
    c = v9_db(tmp_path / "v9.sqlite")
    create_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 10
    got = c.execute(
        "SELECT city_id, year, idx, sites, base_year, series, method FROM counter_index"
    ).fetchall()
    assert sorted(got, key=repr) == sorted([(*r, "v1") for r in V9_ROWS], key=repr)
    cols = [r[1] for r in c.execute("PRAGMA table_info(counter_index)")]
    assert cols[-1] == "method"
    # the method is part of the key: a v2 row of the same year sits beside the v1 row
    c.execute("INSERT INTO counter_index VALUES ('berlin', 2020, 99.0, 11, 2019, 'counts', 'v2')")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO counter_index VALUES ('berlin', 2020, 1, 1, 2019, 'counts', 'v3')")
    c.close()


def _iy(year, idx, method, city="berlin"):
    return CounterIndexYear(city, year, idx, 4, 2019, "counts", method)


def test_replace_counter_index_with_v2_rows_leaves_the_v1_rows(conn):
    replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v1"), _iy(2020, 90.0, "v1")])
    replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v2"), _iy(2020, 95.0, "v2")])
    replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v2")])
    rows = conn.execute("SELECT year, idx, method FROM counter_index ORDER BY 3, 1").fetchall()
    assert [tuple(r) for r in rows] == [
        (2019, 100.0, "v1"),
        (2020, 90.0, "v1"),
        (2019, 100.0, "v2"),
    ]


def test_replace_counter_index_refuses_rows_of_two_methods(conn):
    replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v1")])
    with pytest.raises(ValueError, match="method"):
        replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v2"), _iy(2020, 1.0, "v1")])
    with pytest.raises(ValueError, match="method"):
        replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v2")], method="v1")
    assert conn.execute("SELECT method FROM counter_index").fetchall()[0][0] == "v1"


def test_replace_counter_index_with_no_rows_clears_the_named_method(conn):
    replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v1")])
    replace_counter_index(conn, "berlin", [_iy(2019, 100.0, "v2")])
    replace_counter_index(conn, "berlin", [], method="v2")
    assert [r[0] for r in conn.execute("SELECT method FROM counter_index")] == ["v1"]
    with pytest.raises(ValueError, match="method"):
        replace_counter_index(conn, "berlin", [])  # no rows and no method: no scope to clear
