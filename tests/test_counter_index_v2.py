"""M13 Task 2: counter index v2 (pooled mean per complete day), stored beside v1 by method."""

import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import pytest

from tests.test_app import _client, _text, setup  # noqa: F401 - `setup` is a fixture
from tests.test_app_m8_counts import _app, _index, _seed
from tests.test_content_m8 import _write
from tests.test_counters import _cfg, _check_db
from tests.test_counters import _site as _check_site
from velometer.content.facts import FactError, evaluate
from velometer.counters.check import check_counters
from velometer.counters.index import chain_index, chain_index_v1
from velometer.counters.model import INDEX_METHOD, INDEX_METHODS, DayCount
from velometer.db import CounterIndexYear, replace_counter_index, replace_counter_sites
from velometer.report.data import ReportData


def _year(site, year, per_day, skip=0):
    """A site's days in `year`, each counting `per_day`, with the last `skip` days incomplete."""
    first = date(year, 1, 1)
    n = (date(year + 1, 1, 1) - first).days
    return [DayCount(site, first + timedelta(i), per_day, i < n - skip) for i in range(n)]


def _sites(year, spec):
    return [d for site, per_day, skip in spec for d in _year(site, year, per_day, skip)]


def test_v2_link_is_unmoved_by_a_coverage_difference_at_equal_daily_volume():
    # every site counts the same per day in both years; site c has 30 fewer complete days in
    # 2021 (still >= 90 %). The brief's fixture gave the sites 100, 200 and 300 per day: under the
    # pooled mean that still moves the link (c's days weigh less in the 2021 pool), so the
    # equal-volume case is equal at every site (ruling, task-2-report.md).
    days = _sites(2020, [("a", 100, 0), ("b", 100, 0), ("c", 100, 0)])
    days += _sites(2021, [("a", 100, 0), ("b", 100, 0), ("c", 100, 30)])
    v2 = dict((y, i) for y, i, _ in chain_index(days, 2020))
    v1 = dict((y, i) for y, i, _ in chain_index_v1(days, 2020))
    assert v2[2021] == 100.0  # same mean per complete day
    assert v1[2021] < 100.0  # the v1 sum falls with coverage


def test_a_coverage_difference_at_a_busier_site_still_moves_v2_by_its_weight_in_the_pool():
    # the residual effect the methodology names: pooling weights each site by its complete
    # days, so a busier site with fewer of them lowers the pooled mean; v1 falls further
    days = _sites(2020, [("a", 100, 0), ("b", 200, 0), ("c", 300, 0)])
    days += _sites(2021, [("a", 100, 0), ("b", 200, 0), ("c", 300, 30)])
    v2 = dict((y, i) for y, i, _ in chain_index(days, 2020))[2021]
    v1 = dict((y, i) for y, i, _ in chain_index_v1(days, 2020))[2021]
    pooled_2021 = (100 * 365 + 200 * 365 + 300 * 335) / (365 + 365 + 335)
    assert v2 == pytest.approx(100 * pooled_2021 / 200)  # 2020's pooled mean is 200
    assert v1 < v2 < 100.0


def test_v2_link_is_the_pooled_mean_ratio():
    days = _sites(2020, [("a", 100, 0), ("b", 100, 0), ("c", 100, 0)])
    days += _sites(2021, [("a", 110, 0), ("b", 110, 0), ("c", 110, 0)])
    assert dict((y, i) for y, i, _ in chain_index(days, 2020))[2021] == pytest.approx(110.0)


def test_v2_pools_counts_and_complete_days_over_the_sites_not_site_means():
    # pooled: (sum of counts) / (sum of complete days), not the mean of the sites' means
    days = _sites(2021, [("a", 100, 0), ("b", 100, 0), ("c", 100, 0)])
    days += _sites(2022, [("a", 100, 0), ("b", 100, 0), ("c", 400, 36)])
    n = 365
    pooled = (100 * n + 100 * n + 400 * (n - 36)) / (3 * n - 36) / 100
    out = dict((y, i) for y, i, _ in chain_index(days, 2021))
    assert out[2022] == pytest.approx(100 * pooled)
    assert out[2022] != pytest.approx(100 * (1 + 1 + 4) / 3)  # the mean of means


def test_v1_is_the_ratio_of_summed_counts():
    days = _sites(2020, [("a", 100, 0), ("b", 200, 0), ("c", 300, 0)])
    days += _sites(2021, [("a", 100, 0), ("b", 200, 0), ("c", 300, 30)])
    v1 = dict((y, i) for y, i, _ in chain_index_v1(days, 2020))
    # 2020 is a leap year: 366 complete days per site; 2021 has 365, c only 335
    before = (100 + 200 + 300) * 366
    after = (100 + 200) * 365 + 300 * 335
    assert v1[2021] == pytest.approx(100 * after / before)


def test_v2_keeps_the_qualifying_rule_and_the_chain_break():
    # c falls below 90 % complete days in 2022: the link has two sites, so no value, and the
    # chain stays broken beyond it, as in v1
    days = _sites(2021, [("a", 10, 0), ("b", 10, 0), ("c", 10, 0)])
    days += _sites(2022, [("a", 10, 0), ("b", 10, 0), ("c", 10, 60)])
    days += _sites(2023, [("a", 10, 0), ("b", 10, 0), ("c", 10, 0)])
    for fn in (chain_index, chain_index_v1):
        assert fn(days, 2021) == [(2021, 100.0, 3), (2022, None, 2), (2023, None, 2)]


def test_v2_link_with_no_counts_before_has_no_value():
    days = _sites(2021, [("a", 0, 0), ("b", 0, 0), ("c", 0, 0)])
    days += _sites(2022, [("a", 5, 0), ("b", 5, 0), ("c", 5, 0)])
    assert chain_index(days, 2022)[0] == (2021, None, 3)


def test_the_index_method_is_named_once():
    assert INDEX_METHOD == "v2"
    assert INDEX_METHODS == ("v1", "v2")


# --- review focus 2: v1 rows with a year that v2 lacks never reach a reader -----------------

V1_ONLY = 2012  # a year only the v1 rows have


def _seed_both(db_path, city="berlin"):
    """v2 rows from `_seed`'s default index, and v1 rows that also hold V1_ONLY."""
    _seed(db_path, city)
    v1 = {V1_ONLY: 77.7, 2019: 100.0, 2020: 120.0}
    with closing(sqlite3.connect(db_path)) as c:
        replace_counter_index(c, city, _index(city, v1, method="v1"))


def test_readers_never_see_a_v1_only_year(setup):  # noqa: F811
    db_path = setup[0]
    _seed_both(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        data = ReportData(conn, setup[1])
        rows = data.counter_index("berlin")
        assert rows and {r.method for r in rows} == {INDEX_METHOD}
        assert V1_ONLY not in {r.year for r in rows}
        assert V1_ONLY in {r.year for r in data.counter_index("berlin", "v1")}
    with _client(_app(setup)) as c:
        points = c.get("/data/series.json").json()["counters"]["cities"]["berlin"]["points"]
        assert V1_ONLY not in {p["year"] for p in points}
        assert {p["year"]: p["idx"] for p in points}[2020] == 114.6  # the v2 value
        html = c.get("/city/berlin/counts").text
    assert f'<th scope="row">{V1_ONLY}' not in html
    assert str(V1_ONLY) not in _text(html)


def test_a_fact_of_a_v1_only_year_is_a_missing_year_not_two_series(fixture_db, tmp_path):
    db_path, _cfg_dir, _conn, data = fixture_db
    v2 = _index("berlin", {2019: 100.0, 2020: 101.0})
    v1 = _index("berlin", {V1_ONLY: 50.0, 2019: 100.0, 2020: 99.0}, method="v1")
    _write(db_path, lambda c: replace_counter_index(c, "berlin", v2))
    _write(db_path, lambda c: replace_counter_index(c, "berlin", v1))
    assert evaluate("counter.berlin.2020", data, tmp_path) == 101.0
    assert evaluate("counter.base_year.berlin", data, tmp_path) == 2019
    with pytest.raises(FactError, match=f"no counter index year '{V1_ONLY}'") as e:
        evaluate(f"counter.berlin.{V1_ONLY}", data, tmp_path)
    assert "counter series" not in str(e.value)


# --- counters --check --------------------------------------------------------------------------


@pytest.fixture
def check_conn(tmp_path):
    """A fresh counters database, closed after the test."""
    with _check_db(tmp_path) as conn:
        yield conn


def _rows(method, base_value=100.0):
    return [
        CounterIndexYear("berlin", 2019, base_value, 5, 2019, "counts", method),
        CounterIndexYear("berlin", 2020, 110.0, 4, 2019, "counts", method),
    ]


def test_check_passes_v1_and_v2_rows(check_conn):
    conn = check_conn
    replace_counter_sites(conn, "berlin", [_check_site("berlin", "a")])
    replace_counter_index(conn, "berlin", _rows("v1"))
    replace_counter_index(conn, "berlin", _rows("v2"))
    assert check_counters(conn, _cfg("berlin")) == []


def test_check_flags_a_city_with_v1_rows_and_no_v2_rows(check_conn):
    conn = check_conn
    replace_counter_sites(conn, "berlin", [_check_site("berlin", "a")])
    replace_counter_index(conn, "berlin", _rows("v1"))
    problems = check_counters(conn, _cfg("berlin"))
    assert "berlin: v1 index rows but no v2 rows" in problems


def test_check_flags_a_v2_base_year_that_is_not_100(check_conn):
    conn = check_conn
    replace_counter_sites(conn, "berlin", [_check_site("berlin", "a")])
    replace_counter_index(conn, "berlin", _rows("v1"))
    replace_counter_index(conn, "berlin", _rows("v2", base_value=99.0))
    assert check_counters(conn, _cfg("berlin")) == ["berlin: index base year 2019 is 99.0, not 100"]


def test_check_ignores_v1_rows_for_the_index_checks(check_conn):
    # a v1 base year off 100 is not the headline; the checks read INDEX_METHOD rows
    conn = check_conn
    replace_counter_sites(conn, "berlin", [_check_site("berlin", "a")])
    replace_counter_index(conn, "berlin", _rows("v1", base_value=99.0))
    replace_counter_index(conn, "berlin", _rows("v2"))
    assert check_counters(conn, _cfg("berlin")) == []


def test_this_file_closes_every_connection_it_opens():
    """M13-T2b: a reader opened without closing it raised a ResourceWarning ("unclosed
    database") when it was collected; run the rest of this file and listen for it."""
    me = "tests/test_counter_index_v2.py"
    r = subprocess.run(
        [sys.executable, "-m", "pytest", me, "-q", "-p", "no:cacheprovider",
         "-W", "always::ResourceWarning",
         "--deselect", f"{me}::test_this_file_closes_every_connection_it_opens"],
        capture_output=True, text=True, check=False, cwd=Path(__file__).resolve().parents[1],
    )  # fmt: skip
    assert r.returncode == 0, r.stdout[-2000:]
    assert "unclosed database" not in r.stdout + r.stderr
