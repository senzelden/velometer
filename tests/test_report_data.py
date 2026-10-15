import sqlite3

import pytest
import yaml

from tests.report_fixture import (
    CLASSIFIER,
    SPIKE_YEAR,
    _figure,
    external_figures,
)
from velometer.cli import report_selector
from velometer.config import ConfigError
from velometer.db import (
    SCHEMA_VERSION,
    SchemaError,
    fetch_run,
    fetch_run_results,
    open_db,
    replace_external_figures,
)
from velometer.pipeline.measure import select_metric
from velometer.report import methodology as mt
from velometer.report.data import ReportData, open_readonly, rank_values


def _rank(pairs):
    return rank_values(pairs)


def test_ranks_highest_first_and_ties_share_rank():
    assert _rank([("a", 50.0), ("b", 50.0), ("c", 40.0)]) == {"a": 1, "b": 1, "c": 3}
    assert _rank([("a", 1.0), ("b", 1.0000001), ("c", 2.0)]) == {"c": 1, "a": 2, "b": 2}


def test_with_lang_shares_the_connection_and_keeps_the_original(fixture_db):
    _, _, conn, data = fixture_db
    de = data.with_lang("de")
    assert de.conn is conn and de.lang == "de"
    assert data.lang == "en"
    assert de is not data


def test_current_point_matches_cli_headline(fixture_db):
    _, cfg, conn, data = fixture_db
    cur = data.current("berlin", "lau")
    sel = report_selector(cfg)
    run_id = sel.latest(conn, "berlin", "lau")
    metric = select_metric(fetch_run_results(conn, run_id).metrics, "ours_headline", sel.presets)
    head = next(p for p in cur.presets if p.preset == "ours_headline")
    assert cur.run_id == run_id and head.value == metric.value and head.value is not None
    assert head.per_100k == metric.per_100k and head.per_100k is not None
    assert cur.classifier_version == CLASSIFIER and cur.config_sha256 == sel.config_sha256
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


def _add_qecio(db_path, city_id, *extra):
    """Add QECIO figures (metric, value, scope) through a writable connection (the fixture's is
    read-only)."""
    with open_db(db_path) as w:
        figs = external_figures()["qecio_v2_10"]
        added = [_figure(city_id, "qecio_v2_10", m, v, sc) for m, v, sc in extra]
        replace_external_figures(w, "qecio_v2_10", [*figs, *added])


def test_qecio_ratio_ignores_other_scopes(fixture_db):
    db_path, _, _, data = fixture_db
    _add_qecio(db_path, "berlin", ("main_roads_km", 1.0, "nuts3_XX000"))
    q = _by(data.ranks(), "published_qecio")
    assert q["berlin"].value == pytest.approx(50.0)


def test_qecio_ratio_duplicate_same_scope_raises(fixture_db):
    db_path, _, _, data = fixture_db
    _add_qecio(db_path, "berlin", ("cycle_tracks_km", 7.0, "nuts3_DE300"))
    with pytest.raises(ConfigError, match=r"berlin.*cycle_tracks_km|cycle_tracks_km.*berlin"):
        data.ranks()


def test_ranking_rows_include_cities_without_a_figure(fixture_db):
    rows = fixture_db[3].ranking_rows()
    paris = next(r for r in rows if r.source_id == "published_qecio" and r.city_id == "paris")
    assert paris.rank is None and paris.value is None
    assert {r.n_ranked for r in rows if r.source_id == "published_qecio"} == {1}
    assert {r.city_id for r in rows if r.source_id == "ours_headline"} == {"berlin", "paris"}


def test_ranks_is_the_ranked_part_of_ranking_rows(fixture_db):
    data = fixture_db[3]
    ranked = [r for r in data.ranking_rows() if r.rank is not None]
    assert [(r.source_id, r.city_id, r.rank) for r in data.ranks()] == [
        (r.source_id, r.city_id, r.rank) for r in ranked
    ]


def test_scope_pattern_with_unknown_field_is_a_config_error(fixture_db):
    _db, cfg, conn, _data = fixture_db
    path = cfg / "report.yaml"
    doc = yaml.safe_load(path.read_text())
    bad = next(r for r in doc["rankings"] if r["id"] == "published_qecio")
    bad["scope"] = "nuts3_{no_such_field}"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(ConfigError, match="published_qecio"):
        ReportData(conn, cfg).ranking_rows()


def test_city_without_the_scope_field_has_no_value(fixture_db):
    db_path, _, _, data = fixture_db
    # a figure set whose scope is what str.format would make of None: it must not match
    _add_qecio(
        db_path,
        "berlin",
        ("cycle_tracks_km", 1.0, "nuts3_None"),
        ("cycle_lanes_km", 1.0, "nuts3_None"),
        ("shared_pedestrians_km", 1.0, "nuts3_None"),
        ("main_roads_km", 2.0, "nuts3_None"),
    )
    data.city_fields()["berlin"]["nuts3_code"] = None
    rows = data.ranking_rows()
    berlin = next(r for r in rows if r.source_id == "published_qecio" and r.city_id == "berlin")
    assert berlin.value is None and berlin.rank is None


def test_untrusted_country_is_absent_from_every_report_surface(report_db_with_trust):
    import json

    from velometer.report import charts, methodology

    db, cfg = report_db_with_trust(countries={"DE": {"status": "trusted", "basis": "t"}})
    conn = open_readonly(db)
    try:
        data = ReportData(conn, cfg)  # FR pending
        assert [c.id for c in data.cities()] == ["berlin"]
        assert {c.id for c in data.all_cities()} == {"berlin", "paris"}
        assert data.csv_rows() and all(r["city_id"] == "berlin" for r in data.csv_rows())
        assert data.csv_rows("paris") == []
        assert all(r.city_id == "berlin" for r in data.ranking_rows())
        assert "paris" not in json.dumps(charts.headline_over_time(data))
        assert "Paris" not in methodology.render(methodology.methodology_facts(data), "en")
    finally:
        conn.close()


def test_country_absent_from_trust_yaml_is_pending(report_db_with_trust):
    db, cfg = report_db_with_trust(countries={})
    conn = open_readonly(db)
    try:
        assert ReportData(conn, cfg).cities() == []
    finally:
        conn.close()


# --- subareas (M6 Task 10) -------------------------------------------------------------------


@pytest.fixture
def sub_data(tmp_path):
    from tests.report_fixture import build_report_fixture_subareas

    db_path, cfg = build_report_fixture_subareas(tmp_path)
    conn = open_readonly(db_path)
    yield ReportData(conn, cfg)
    conn.close()


def test_subareas_rows_of_the_current_run(sub_data):
    rows = sub_data.subareas("berlin")
    assert [r.name for r in rows] == ["East", "West", "Outside the 2 Bezirke (districts), at the LAU edge"]
    assert [r.remainder for r in rows] == [False, False, True]  # the remainder last, set apart
    assert rows[2].subarea_id == "remainder" and rows[2].tier_km["A"] == 0.5
    west = rows[1]
    assert west.subarea_id == "west" and west.headline == pytest.approx(4.0)
    assert west.tier_km["A"] == 3.0 and west.tier_km["B"] == 1.0 and west.tier_km["C"] == 0.0
    assert west.a_share_of_ab == pytest.approx(75.0)
    assert rows[0].a_share_of_ab == pytest.approx(25.0)


def test_subareas_is_none_without_subareas(sub_data):
    assert sub_data.subareas("paris") is None  # a city without subareas in config


def test_subareas_is_none_for_a_city_whose_config_has_none(fixture_db):
    assert fixture_db[3].subareas("berlin") is None


def test_subarea_surfaces_are_empty_for_an_untrusted_country(tmp_path):
    from tests.report_fixture import build_report_fixture_subareas

    db_path, cfg = build_report_fixture_subareas(tmp_path)
    trust = yaml.safe_load((cfg / "trust.yaml").read_text())
    trust["countries"] = {"FR": {"status": "trusted", "basis": "t"}}  # DE is pending
    (cfg / "trust.yaml").write_text(yaml.safe_dump(trust))
    conn = open_readonly(db_path)
    try:
        data = ReportData(conn, cfg)
        assert data.subareas("berlin") is None
        assert data.subarea_series("berlin") == {}
        assert data.subarea_csv_rows("berlin") == []
    finally:
        conn.close()


def test_subarea_series_and_csv_rows(sub_data):
    series = sub_data.subarea_series("berlin")
    assert set(series) == {"west", "east"}
    assert [p.label for p in series["west"]] == ["2024", "2025", "2026", "current"]
    assert sub_data.subarea_series("paris") == {}
    rows = sub_data.subarea_csv_rows("berlin")
    assert {r["run_id"] for r in rows} == {str(p.run_id) for p in series["west"]}
    for run_id in {r["run_id"] for r in rows}:  # per run: west/east rows, then the remainder's
        ids = [r["subarea_id"] for r in rows if r["run_id"] == run_id]
        assert ids[-2:] == ["remainder"] * 2 and "remainder" not in ids[:-2]
    assert {r["name"] for r in rows if r["subarea_id"] == "remainder"} == {
        "Outside the 2 Bezirke (districts), at the LAU edge"
    }
    assert sub_data.subarea_csv_rows("paris") == []
