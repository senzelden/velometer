from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.test_run_history import CFG_DIR, CITY, Fakes, _current_deps
from velometer import run as R
from velometer import timeseries as T
from velometer.cli import app
from velometer.config import load_activity
from velometer.db import (
    create_schema,
    fetch_activity,
    latest_history_set,
    open_db,
    replace_activity,
    upsert_cities,
)
from velometer.models import ActivityYear

CFG = load_activity(CFG_DIR / "activity.yaml")  # pct 10, min 25 km, factor 2, share 0.5, drift 50


def pt(label, ab_km, edits=None, share=0.1, legacy=0.0, unrec=0.0):
    act = None
    if edits is not None:
        act = ActivityYear(
            city_id="c",
            boundary_kind="lau",
            year=0,
            history_set_md5="m",
            n_edits=edits,
            n_changesets=1,
            n_mappers=1,
            top_mapper_share=share,
            n_ways_created_cycling=0,
            n_ways_deleted_cycling=0,
        )
    return T.YearPoint(
        label, 1, f"{label}-01-01T00:00:00Z", 1.0, ab_km, dict.fromkeys("ABCDE", 0.0), act,
        legacy, unrec,
    )  # fmt: skip


def rules(points, fraction=1.0):
    return {f.label: set(f.rules) for f in T.flags(points, CFG, current_fraction=fraction)}


def test_km_jump_at_threshold_flags_and_just_below_does_not():
    # pct part dominates: 10% of 1000 = 100
    assert rules([pt("2018", 1000), pt("2019", 1100)]) == {"2019": {"km_jump"}}
    assert rules([pt("2018", 1000), pt("2019", 900)]) == {"2019": {"km_jump"}}  # drops count
    assert rules([pt("2018", 1000), pt("2019", 1099.9)]) == {}
    # min_km dominates: max(10, 25) = 25
    assert rules([pt("2018", 100), pt("2019", 125)]) == {"2019": {"km_jump"}}
    assert rules([pt("2018", 100), pt("2019", 124.9)]) == {}


def test_activity_spike_at_threshold_uses_median_of_year_points():
    pts = [pt(str(y), 5, 10) for y in (2017, 2018, 2019)]
    pts += [pt("2020", 5, 20), pt("2021", 5, 19)]
    # median 10 -> limit 20
    assert rules(pts) == {"2020": {"activity_spike"}}


def test_no_activity_means_no_spike():
    assert rules([pt("2018", 5), pt("2019", 5)]) == {}


def test_campaign_needs_both_jump_and_spike():
    base = [pt("2018", 100, 10), pt("2019", 100, 10)]
    assert rules([*base, pt("2020", 200, 10)]) == {"2020": {"km_jump"}}
    assert rules([*base, pt("2020", 100, 40)]) == {"2020": {"activity_spike"}}
    assert rules([*base, pt("2020", 200, 40)]) == {
        "2020": {"km_jump", "activity_spike", "campaign_suspected"}
    }


def test_single_mapper_needs_a_jump():
    assert rules([pt("2018", 100, 10), pt("2019", 100, 10, share=0.9)]) == {}
    assert rules([pt("2018", 100, 10), pt("2019", 200, 10, share=0.5)]) == {
        "2019": {"km_jump", "single_mapper"}
    }
    assert rules([pt("2018", 100, 10), pt("2019", 200, 10, share=0.49)]) == {"2019": {"km_jump"}}


def test_current_point_thresholds_scale_with_window():
    hist = [pt("2025", 100, 10), pt("2026", 100, 10)]
    # half a year: min_km 25 -> 12.5; 10% of 100 = 10
    assert rules([*hist, pt("current", 112.5)], 0.5) == {"current": {"km_jump"}}
    assert rules([*hist, pt("current", 112.4)], 0.5) == {}
    assert rules([*hist, pt("current", 112.5)], 1.0) == {}  # unscaled needs 25
    # spike: limit 2 * 10 * 0.5 = 10
    assert rules([*hist, pt("current", 100, 10)], 0.5) == {"current": {"activity_spike"}}
    assert rules([*hist, pt("current", 100, 9)], 0.5) == {}
    # the percentage does not scale: 10% of 1000 = 100 even at a tiny window
    big = [pt("2025", 1000), pt("2026", 1000), pt("current", 1099, None)]
    assert rules(big, 0.01) == {}
    big[-1] = pt("current", 1100, None)
    assert rules(big, 0.01) == {"current": {"km_jump"}}


def test_current_point_not_in_the_median():
    pts = [pt("2025", 5, 10), pt("2026", 5, 30), pt("current", 5, 40)]
    # median of the years is 20, limit 40 (a median including current would be 30)
    assert rules(pts)["current"] == {"activity_spike"}


def test_first_point_never_flagged_by_change_rules():
    got = rules([pt("2018", 1e6, 10, share=1.0, legacy=100, unrec=100)])
    assert got == {}


def test_tag_drift_at_threshold_and_ignores_zero_previous():
    assert rules([pt("2018", 5, legacy=100), pt("2019", 5, legacy=150)]) == {"2019": {"tag_drift"}}
    assert rules([pt("2018", 5, legacy=100), pt("2019", 5, legacy=149.9)]) == {}
    assert rules([pt("2018", 5, unrec=100), pt("2019", 5, unrec=50)]) == {"2019": {"tag_drift"}}
    assert rules([pt("2018", 5, legacy=0), pt("2019", 5, legacy=500, unrec=500)]) == {}


def test_missing_drift_diagnostics_never_flag_tag_drift():
    # Current (M2) runs record no drift diagnostics: unknown is not 0 km, so no tag_drift.
    known, unknown = dict(legacy=100, unrec=100), dict(legacy=None, unrec=None)
    assert rules([pt("2026", 5, **known), pt("current", 5, **unknown)]) == {}
    assert rules([pt("2025", 5, **unknown), pt("2026", 5, **known)]) == {}


def test_point_without_diagnostics_reads_none_and_renders_na(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=_current_deps(tmp_path))
        fakes = Fakes(tmp_path)
        R.run_history(
            conn, CITY, range(2019, 2021), data_dir=tmp_path, config_dir=CFG_DIR,
            deps=fakes.deps(),
        )  # fmt: skip
        pts = T.series(conn, "berlin", "lau", _selector(), fakes.set_md5)
    assert pts[-1].label == "current"
    assert pts[-1].legacy_km is None and pts[-1].unrecognised_km is None
    assert pts[0].legacy_km is not None and pts[0].unrecognised_km is not None
    row = T.render_block({("berlin", "lau"): pts}, []).splitlines()
    assert [r for r in row if r.startswith("| current ")][0].count("| n/a ") >= 2


def test_current_fraction_clamped_and_leap_aware():
    assert T.current_fraction("2026-07-02T12:00:00Z") == pytest.approx(182.5 / 365)
    assert T.current_fraction("2024-07-02T00:00:00Z") == pytest.approx(183 / 366)
    assert 0 < T.current_fraction("2026-01-01T00:00:00Z") <= 1
    assert T.current_fraction("2026-12-31T23:59:59Z") <= 1


def _flag(label="2020"):
    return T.Flag("berlin", "lau", label, ("km_jump",), "")


def _report(tmp_path, body="", marker="berlin/lau=abcd1234"):
    p = tmp_path / "r.md"
    p.write_text(
        f"pre\n{T.BEGIN}\nold\n{T.END}\n\n## Explanations\n\n"
        f"<!-- explained-against: {marker} -->\n\n{body}"
    )
    return p


def test_check_requires_explanation_per_flag_and_fresh_marker(tmp_path):
    p = _report(tmp_path, "### berlin/lau/2020\ntext\n\n### berlin/lau/2019\nstale\n")
    assert T.missing_explanations(p, [_flag("2020")]) == []
    assert T.missing_explanations(p, [_flag("2020"), _flag("2021")]) == ["berlin/lau/2021"]
    assert T.stale_explanations(p, [_flag("2020")]) == ["berlin/lau/2019"]
    assert T.stale_explanations(p, [_flag("2020")], {"paris"}) == []
    sets = {("berlin", "lau"): "abcd1234" + "0" * 24}
    assert T.unexplained_sets(p, sets) == []
    assert len(T.unexplained_sets(p, {("berlin", "lau"): "ffff0000" + "0" * 24})) == 1
    assert len(T.unexplained_sets(p, {("paris", "fua"): "ffff0000" + "0" * 24})) == 1
    assert T.explained_against_marker(sets) == "<!-- explained-against: berlin/lau=abcd1234 -->"


def test_write_keeps_text_outside_markers_and_is_idempotent(tmp_path):
    p = _report(tmp_path, "### berlin/lau/2020\ntext\n")
    before = p.read_text()
    T.write_report(p, f"{T.BEGIN}\nnew\n{T.END}")
    once = p.read_text()
    assert once == before.replace("old", "new")
    T.write_report(p, f"{T.BEGIN}\nnew\n{T.END}")
    assert p.read_text() == once
    p.write_text("no markers")
    with pytest.raises(ValueError, match="markers"):
        T.write_report(p, "x")


# --- CLI over a DB built with the fake history deps -----------------------------------------


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "v.sqlite"
    fakes = Fakes(tmp_path)
    with open_db(path) as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_history(
            conn, CITY, range(2019, 2022), data_dir=tmp_path, config_dir=CFG_DIR,
            deps=fakes.deps(),
        )  # fmt: skip
    return path, fakes.set_md5


def _spike(path, set_md5, year=2020):
    with open_db(path) as conn:
        rows = fetch_activity(conn, "berlin", "lau", set_md5)
        rows = [r.model_copy(update={"n_edits": 50}) if r.year == year else r for r in rows]
        replace_activity(conn, "berlin", "lau", set_md5, rows)


def _ts(db, report, *args):
    return CliRunner().invoke(
        app,
        ["timeseries", "--db", str(db[0]), "--city", "berlin", "--boundary", "lau",
         "--report", str(report), *args],
    )  # fmt: skip


def test_cli_prints_series_and_notes_missing_current(db, tmp_path):
    res = _ts(db, _report(tmp_path))
    assert res.exit_code == 0, res.output
    assert "#### berlin/lau" in res.output
    assert "| 2019 |" in res.output and "| 2021 |" in res.output
    assert "no current point" in res.output
    assert f"`{db[1][:8]}`" in res.output and "population 2024 held constant" in res.output


def test_cli_check_fails_on_unexplained_flag_then_passes(db, tmp_path):
    _spike(*db)
    report = _report(tmp_path, marker=f"berlin/lau={db[1][:8]}")
    res = _ts(db, report, "--check")
    assert res.exit_code == 1
    assert "missing explanation: ### berlin/lau/2020" in res.output
    report.write_text(report.read_text() + "### berlin/lau/2020\nA bulk import.\n")
    assert _ts(db, report, "--check").exit_code == 0


def test_cli_check_fails_on_stale_marker_and_prints_the_fix(db, tmp_path):
    res = _ts(db, _report(tmp_path, marker="berlin/lau=deadbeef"), "--check")
    assert res.exit_code == 1
    assert f"<!-- explained-against: berlin/lau={db[1][:8]} -->" in res.output


def test_cli_check_fails_without_history_runs_or_report(db, tmp_path):
    res = CliRunner().invoke(
        app,
        ["timeseries", "--db", str(db[0]), "--city", "paris", "--boundary", "lau",
         "--report", str(_report(tmp_path)), "--check"],
    )  # fmt: skip
    assert res.exit_code == 1 and "no history runs for paris/lau" in res.output
    res = _ts(db, tmp_path / "nope.md", "--check")
    assert res.exit_code == 1 and "error:" in res.output


def test_cli_check_warns_on_stale_heading_without_failing(db, tmp_path):
    report = _report(tmp_path, "### berlin/lau/2020\nx\n", marker=f"berlin/lau={db[1][:8]}")
    res = _ts(db, report, "--check")
    assert res.exit_code == 0
    assert "warning: ### berlin/lau/2020 matches no flag" in res.output


def test_cli_write_fills_the_block_and_marks_flags(db, tmp_path):
    _spike(*db)
    report = _report(tmp_path)
    assert _ts(db, report, "--write").exit_code == 0
    text = report.read_text()
    assert "#### berlin/lau" in text and "activity_spike" in text and "old\n" not in text
    assert text.startswith("pre\n") and "## Explanations" in text
    assert _ts(db, report, "--write").exit_code == 0
    assert report.read_text() == text


def test_committed_report_has_markers_and_no_flags_to_explain():
    p = Path(__file__).parent.parent / "docs" / "review" / "m3_timeseries.md"
    text = p.read_text()
    assert T.BEGIN in text and T.END in text and "## Explanations" in text
    assert T.explained_against(p) == {}


def _selector():
    from velometer.cli import _run_selector

    return _run_selector(CFG_DIR, "v1")


def test_series_adds_current_point_with_next_year_activity(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=_current_deps(tmp_path))
        fakes = Fakes(tmp_path)
        R.run_history(
            conn, CITY, range(2019, 2022), data_dir=tmp_path, config_dir=CFG_DIR,
            deps=fakes.deps(),
        )  # fmt: skip
        pts = T.series(conn, "berlin", "lau", _selector(), fakes.set_md5)
        assert [p.label for p in pts] == ["2019", "2020", "2021", "current"]
        assert pts[-1].activity is not None and pts[-1].activity.year == 2022
        assert pts[0].activity.year == 2019
        assert pts[0].headline is not None and pts[0].ab_km >= 0
        cs = T.build_city(conn, "berlin", "lau", _selector())
        assert cs.current_fraction == pytest.approx(T.current_fraction(pts[-1].osm_timestamp))
        assert "current run" in cs.provenance and not cs.notes


def test_latest_history_set_is_the_most_recently_recorded_with_done_runs(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        sel = _selector()
        kw = dict(
            classifier_version=sel.version,
            classifier_parameters=sel.parameters,
            config_sha256=sel.config_sha256,
        )
        assert latest_history_set(conn, "berlin", "lau", **kw) is None
        for md5 in ("old", "new"):
            f = Fakes(tmp_path, md5=md5)
            R.run_history(
                conn, CITY, range(2019, 2021), data_dir=tmp_path, config_dir=CFG_DIR,
                deps=f.deps(),
            )  # fmt: skip
        assert latest_history_set(conn, "berlin", "lau", **kw) == Fakes(tmp_path, "new").set_md5
        assert latest_history_set(conn, "berlin", "fua", **kw) is None
        assert latest_history_set(conn, "paris", "lau", **kw) is None


def test_zero_median_means_no_spike():
    pts = [pt("2018", 5, 0), pt("2019", 5, 0), pt("2020", 5, 7)]
    assert rules(pts) == {}


def test_ab_km_is_tiers_a_and_b_on_per_side_and_headline_is_the_preset_metric(db):
    path, set_md5 = db
    with open_db(path) as conn:
        run_id = min(T.series(conn, "berlin", "lau", _selector(), set_md5), key=lambda p: p.run_id)
        run_id = run_id.run_id
        conn.execute("DELETE FROM tier_lengths WHERE run_id=?", (run_id,))
        for tier, basis, km in [
            ("A", "per_side", 10.0),
            ("B", "per_side", 20.0),
            ("C", "per_side", 40.0),
            ("A", "qecio_weighted", 5.0),
            ("B", "qecio_weighted", 100.0),
        ]:
            conn.execute(
                "INSERT INTO tier_lengths (run_id, city_id, tier, subtype, length_basis, "
                "length_km, n_ways) VALUES (?, 'berlin', ?, '', ?, ?, 1)",
                (run_id, tier, basis, km),
            )
        conn.execute(
            "UPDATE metrics SET value=7.5 WHERE run_id=? AND preset='ours_headline' "
            "AND length_basis='per_side'",
            (run_id,),
        )
        conn.commit()
        p = next(x for x in T.series(conn, "berlin", "lau", _selector(), set_md5))
        assert p.run_id == run_id
        assert p.ab_km == pytest.approx(30.0)
        assert p.tiers_km["C"] == pytest.approx(40.0) and p.tiers_km["A"] == pytest.approx(10.0)
        assert p.headline == pytest.approx(7.5)


def test_cli_check_fails_when_generated_block_markers_are_missing(db, tmp_path):
    report = _report(tmp_path, marker=f"berlin/lau={db[1][:8]}")
    report.write_text(report.read_text().replace(T.BEGIN, "").replace(T.END, ""))
    res = _ts(db, report, "--check")
    assert res.exit_code == 1 and "markers" in res.output


def _no_boundary(db, report, *cities):
    args = ["timeseries", "--db", str(db[0]), "--report", str(report), "--check"]
    for c in cities:
        args += ["--city", c]
    return CliRunner().invoke(app, args)


def test_cli_check_requires_fua_for_berlin_but_not_vienna(db, tmp_path):
    report = _report(tmp_path, marker=f"berlin/lau={db[1][:8]}")
    res = _no_boundary(db, report, "berlin")
    assert res.exit_code == 1 and "no history runs for berlin/fua" in res.output
    # vienna has no history at all: lau is required, fua is not
    res = _no_boundary(db, report, "vienna")
    assert "no history runs for vienna/lau" in res.output
    assert "vienna/fua" not in res.output


def test_history_config_is_strict_and_has_a_default(tmp_path):
    from velometer.config import ConfigError, load_history

    h = load_history(CFG_DIR / "history.yaml")
    assert h.required("berlin") == ["lau", "fua"] and h.required("vienna") == ["lau"]
    bad = tmp_path / "h.yaml"
    bad.write_text('years: "2018-2026"\nrequired_kinds: {berlin: [lau]}\n')
    with pytest.raises(ConfigError):
        load_history(bad)
    bad.write_text('years: "2018-2026"\nrequired_kinds: {default: [lau]}\nextra: 1\n')
    with pytest.raises(ConfigError):
        load_history(bad)
