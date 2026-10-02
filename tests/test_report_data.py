import sqlite3

import pytest

from tests.report_fixture import SPIKE_YEAR, build_report_fixture, external_figures
from velometer.cli import report_selector
from velometer.db import fetch_run, fetch_run_results
from velometer.pipeline.measure import select_metric
from velometer.report.data import ReportData, open_readonly, rank_values


@pytest.fixture
def fixture_db(tmp_path):
    db_path, cfg = build_report_fixture(tmp_path)
    conn = open_readonly(db_path)
    yield db_path, cfg, conn, ReportData(conn, cfg)
    conn.close()


def _rank(pairs):
    return rank_values(pairs)


def test_ranks_highest_first_and_ties_share_rank():
    assert _rank([("a", 50.0), ("b", 50.0), ("c", 40.0)]) == {"a": 1, "b": 1, "c": 3}
    assert _rank([("a", 1.0), ("b", 1.0000001), ("c", 2.0)]) == {"c": 1, "a": 2, "b": 2}


def test_current_point_matches_cli_headline(fixture_db):
    _, cfg, conn, data = fixture_db
    cur = data.current("berlin", "lau")
    sel = report_selector(cfg)
    run_id = sel.latest(conn, "berlin", "lau")
    metric = select_metric(fetch_run_results(conn, run_id).metrics, "ours_headline", sel.presets)
    head = next(p for p in cur.presets if p.preset == "ours_headline")
    assert cur.run_id == run_id and head.value == metric.value and head.value is not None
    assert head.per_100k == metric.per_100k and head.per_100k is not None
    assert cur.classifier_version == "v2" and cur.config_sha256 == sel.config_sha256
    assert cur.city_name == "Berlin" and cur.kind == "lau"
    assert set(cur.tiers_km) == set("ABCDE") and cur.ab_km == pytest.approx(
        cur.tiers_km["A"] + cur.tiers_km["B"]
    )
    assert (cur.population_value, cur.population_year) == (100_000, 2024)
    assert cur.osm_timestamp == fetch_run(conn, run_id)["osm_timestamp"]


def test_fua_current_has_no_population(fixture_db):
    cur = fixture_db[3].current("berlin", "fua")
    assert cur is not None and cur.population_value is None and cur.population_year is None
    assert all(p.per_100k is None for p in cur.presets)


def test_city_without_current_run_gives_none_not_error(fixture_db):
    data = fixture_db[3]
    assert data.current("paris", "lau") is None
    assert data.current("paris", "fua") is None
    cs = data.series("paris", "lau")  # history exists, the current point does not
    assert cs is not None and [p.label for p in cs.points] == ["2024", "2025", "2026"]
    assert data.series("paris", "fua") is None and data.flags("paris", "fua") == []
    assert {r["label"] for r in data.csv_rows("paris")} == {"2024", "2025", "2026"}


def test_series_and_flags_reuse_the_timeseries_rules(fixture_db):
    data = fixture_db[3]
    assert [p.label for p in data.series("berlin", "lau").points] == [
        "2024", "2025", "2026", "current",
    ]  # fmt: skip
    flagged = {f.label: f.rules for f in data.flags("berlin", "lau")}
    assert flagged == {SPIKE_YEAR: ("activity_spike",)}


def test_reconcile_uses_the_report_selector(fixture_db):
    _, cfg, conn, data = fixture_db
    rep = data.reconcile("berlin")
    assert rep is not None and rep.run_id == data.current("berlin", "lau").run_id
    assert data.reconcile("paris") is None


def _by(ranks, source):
    return {r.city_id: r for r in ranks if r.source_id == source}


def test_ranks_per_source(fixture_db):
    ranks = fixture_db[3].ranks()
    cc = _by(ranks, "published_clean_cities")
    assert (cc["berlin"].value, cc["berlin"].rank) == (30.0, 1)
    assert (cc["paris"].value, cc["paris"].rank) == (20.0, 2)
    ours = _by(ranks, "ours_headline")
    assert set(ours) == {"berlin"}  # paris has history but no current run
    assert ours["berlin"].rank == 1 and ours["berlin"].value is not None
    assert cc["berlin"].source_label == "Clean Cities 2025 (published)"
    assert all(r.rank >= 1 for r in ranks)


def test_external_ratio_is_sum_over_denominator_in_percent(fixture_db):
    q = _by(fixture_db[3].ranks(), "published_qecio")
    assert q["berlin"].value == pytest.approx(50.0)


def test_external_ratio_needs_every_component(fixture_db):
    # paris has no cycle_lanes_km: it is absent, not ranked on a partial sum
    q = _by(fixture_db[3].ranks(), "published_qecio")
    assert set(q) == {"berlin"}
    assert "cycle_lanes_km" not in {
        f.metric_name for f in external_figures()["qecio_v2_10"] if f.city_id == "paris"
    }


def test_external_scope_must_match(fixture_db, tmp_path):
    _, cfg, conn, data = fixture_db
    rows = [r for r in data.ranks() if r.source_id == "published_clean_cities"]
    assert len(rows) == 2  # whole_network figures only: a nuts3-scope row would not count


def test_open_readonly_refuses_writes(tmp_path):
    db = tmp_path / "x.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE t (a)")
    c.commit()
    c.close()
    ro = open_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO t VALUES (1)")
    ro.close()


def test_open_readonly_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_readonly(tmp_path / "nope.sqlite")
    assert not (tmp_path / "nope.sqlite").exists()  # and it did not create one
