import sqlite3

import pytest

from tests.report_fixture import (
    SPIKE_YEAR,
    external_figures,
)
from velometer.cli import report_selector
from velometer.db import SCHEMA_VERSION, SchemaError, fetch_run, fetch_run_results
from velometer.pipeline.measure import select_metric
from velometer.report import methodology as mt
from velometer.report.data import ReportData, open_readonly, rank_values


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
    c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
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


def test_importing_the_data_layer_does_not_import_the_cli():
    import subprocess
    import sys

    code = (
        "import sys, velometer.report.data; "
        "assert 'velometer.cli' not in sys.modules and 'typer' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize("version", [SCHEMA_VERSION - 1, SCHEMA_VERSION + 1])
def test_open_readonly_refuses_another_schema_version(tmp_path, version):
    db = tmp_path / "old.sqlite"
    c = sqlite3.connect(db)
    c.execute(f"PRAGMA user_version = {version}")
    c.close()
    with pytest.raises(SchemaError, match=f"schema v{version}") as e:
        open_readonly(db)
    if version < SCHEMA_VERSION:
        assert "velometer migrate" in str(e.value)


def _fail_history(db_path, city_id, kind):
    """Mark every history run of city/kind failed in the (writable) fixture file."""
    with sqlite3.connect(db_path) as c:
        n = c.execute(
            "UPDATE runs SET status='failed' WHERE city_id=? AND boundary_kind=? "
            "AND source='history'",
            (city_id, kind),
        ).rowcount
    assert n


def test_current_run_without_history(fixture_db):
    """Review Focus 2, reverse case: a current run but no history series (berlin/fua)."""
    db_path, cfg, _conn, _data = fixture_db
    _fail_history(db_path, "berlin", "fua")
    conn = open_readonly(db_path)
    try:
        data = ReportData(conn, cfg)
        point = data.current("berlin", "fua")
        assert point is not None and data.series("berlin", "fua") is None
        fua = [(r["city_id"], r["boundary_kind"], r["label"]) for r in data.csv_rows("berlin")]
        fua = [r for r in fua if r[1] == "fua"]
        assert fua == [("berlin", "fua", "current")]
        facts = mt.methodology_facts(data)
        berlin = next(c for c in facts.cities if c.id == "berlin")
        kind = next(k for k in berlin.kinds if k.kind == "fua")
        assert kind.history_set is None and kind.history_osm_timestamps == []
        assert kind.current_osm_timestamp == point.osm_timestamp
    finally:
        conn.close()
