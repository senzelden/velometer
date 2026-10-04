import re
import shutil
from pathlib import Path

import pytest
import yaml
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
from velometer.selection import trusted_countries

CFG = load_activity(
    CFG_DIR / "activity.yaml"
)  # pct 10, min 25 km, factor 2, share 0.5, drift 50 % and 5 km
OLD_ACTIVITY_PART = "de066a28e74c"  # the marker of docs/review/m3_timeseries.md before v6
CURRENT_TS = "2026-07-01T00:00:00Z"  # current points in unit tests follow the 2026 history year


# A per-city override (berlin needs FUA, every other city LAU only), pinned here so the tests of
# the override rule do not depend on the shipped required_kinds.
REQUIRED_KINDS = "required_kinds:\n  default: [lau]\n  berlin: [lau, fua]\n"


def config_dir(tmp_path, years="2019-2021", report_classifier="v1") -> Path:
    """A copy of config/ whose history.yaml series is `years`, whose required_kinds is
    REQUIRED_KINDS, and whose report.yaml classifier is the one the fake runs use (run_history's
    default, v1); classifier/presets sha unchanged."""
    d = tmp_path / "config"
    if not d.exists():
        shutil.copytree(CFG_DIR, d)
    doc = yaml.safe_load((CFG_DIR / "history.yaml").read_text())
    assert "required_kinds" in doc, "config/history.yaml has no required_kinds block"
    doc["years"] = years
    doc["required_kinds"] = yaml.safe_load(REQUIRED_KINDS)["required_kinds"]
    (d / "history.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    rep = (CFG_DIR / "report.yaml").read_text()
    rep = re.sub(r"report_classifier: \S+", f"report_classifier: {report_classifier}", rep)
    (d / "report.yaml").write_text(rep)
    return d


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
    ts = CURRENT_TS if label == "current" else f"{label}-01-01T00:00:00Z"
    return T.YearPoint(
        label, 1, ts, 1.0, ab_km, dict.fromkeys("ABCDE", 0.0), act,
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


def test_tag_drift_needs_the_km_floor_as_well_as_the_percentage():
    # +100% but only +4.9 km: below tag_drift_min_km (5)
    assert rules([pt("2018", 5, unrec=4.9), pt("2019", 5, unrec=9.8)]) == {}
    # +100% and exactly +5 km: flagged
    assert rules([pt("2018", 5, unrec=5), pt("2019", 5, unrec=10)]) == {"2019": {"tag_drift"}}
    # -100% of 4 km: a large share but a small move, not flagged
    assert rules([pt("2018", 5, legacy=4), pt("2019", 5, legacy=0)]) == {}


def test_tag_drift_floor_scales_for_the_current_point():
    # half a year: the floor is 2.5 km, so +3 km (+100%) flags only at fraction 0.5
    pts = [pt("2026", 5, unrec=3), pt("current", 5, unrec=6)]
    assert rules(pts, fraction=0.5) == {"current": {"tag_drift"}}
    assert rules(pts, fraction=1.0) == {}


def test_tag_drift_min_km_is_configured_with_the_recommended_default():
    assert CFG.flags.tag_drift_min_km == 5


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
            conn, CITY, range(2025, 2027), data_dir=tmp_path, config_dir=CFG_DIR,
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


def _report(tmp_path, body="", marker="berlin/lau=abcd1234", activity=None):
    p = tmp_path / "r.md"
    marker += f" activity={activity}" if activity else ""
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
    assert T.stale_explanations(p, [_flag("2020")], {("paris", "lau")}) == []
    assert T.stale_explanations(p, [_flag("2020")], {("berlin", "fua")}) == []
    assert T.stale_explanations(p, [_flag("2020")], {("berlin", "lau")}) == ["berlin/lau/2019"]
    sets = {("berlin", "lau"): "abcd1234" + "0" * 24}
    assert T.unexplained_sets(p, sets) == []
    assert len(T.unexplained_sets(p, {("berlin", "lau"): "ffff0000" + "0" * 24})) == 1
    assert len(T.unexplained_sets(p, {("paris", "fua"): "ffff0000" + "0" * 24})) == 1
    assert T.explained_against_marker(sets) == "<!-- explained-against: berlin/lau=abcd1234 -->"
    assert T.explained_against(p) == {"berlin/lau": "abcd1234"}


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
    """berlin/lau 2019-2021, every year of a config whose history.yaml series is 2019-2021."""
    path = tmp_path / "v.sqlite"
    fakes = Fakes(tmp_path)
    cfg = config_dir(tmp_path)
    with open_db(path) as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_history(
            conn, CITY, range(2019, 2022), data_dir=tmp_path, config_dir=cfg, deps=fakes.deps()
        )
    return path, fakes.set_md5, cfg


def _spike(path, set_md5, cfg, year=2020):
    sha = R.file_sha256(cfg / "activity.yaml")
    with open_db(path) as conn:
        rows = fetch_activity(conn, "berlin", "lau", set_md5, sha)
        rows = [r.model_copy(update={"n_edits": 50}) if r.year == year else r for r in rows]
        replace_activity(conn, "berlin", "lau", set_md5, sha, rows)


def _ts(db, report, *args):
    return CliRunner().invoke(
        app,
        ["timeseries", "--db", str(db[0]), "--city", "berlin", "--boundary", "lau",
         "--report", str(report), "--config-dir", str(db[2]), *args],
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
    want = f"<!-- explained-against: berlin/lau={db[1][:8]} -->"
    assert want in res.output


def test_cli_check_fails_without_history_runs_or_report(db, tmp_path):
    res = CliRunner().invoke(
        app,
        ["timeseries", "--db", str(db[0]), "--city", "paris", "--boundary", "lau",
         "--report", str(_report(tmp_path)), "--config-dir", str(db[2]), "--check"],
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


def test_committed_report_markers_and_headings_are_well_formed():
    # The DB is not in the repo: check the report's shape, not today's flags (`--check` does).
    from velometer.config import load_cities
    from velometer.reconcile import headings

    p = Path(__file__).parent.parent / "docs" / "review" / "m3_timeseries.md"
    text = p.read_text()
    assert T.BEGIN in text and T.END in text and "## Explanations" in text
    cities = {c.id for c in load_cities(CFG_DIR / "cities.yaml")}
    marker = T.explained_against(p)
    for key, set_md5 in marker.items():
        city, kind = key.split("/")
        assert city in cities and kind in ("lau", "fua") and len(set_md5) == 8
    for h in headings(text.split("## Explanations", 1)[1]):
        city, kind, label = h.split("/")
        assert f"{city}/{kind}" in marker, h  # every explanation names a marked set
        assert label == T.CURRENT or (label.isdigit() and len(label) == 4), h


def test_committed_construction_causes_cite_a_source():
    # ADR 0006: OSM gives mapped km, not built km. "construction" means new ways mapped that are
    # consistent with known construction, so an explanation that names it must cite the source
    from velometer.reconcile import headings

    p = Path(__file__).parent.parent / "docs" / "review" / "m3_timeseries.md"
    explained = p.read_text().split("## Explanations", 1)[1]
    legend = explained.split("Causes used below:", 1)[1].split("\n\n", 1)[0]
    assert "**construction** (new ways mapped, consistent with known construction" in legend
    assert "built and mapped" not in legend
    for h in headings(explained):
        text = T.explanation(p, h)
        if text.startswith("Cause: **construction**"):
            assert "https://" in text, h


def _selector():
    from velometer.cli import run_selector

    return run_selector(CFG_DIR, "v1")


def test_series_adds_current_point_with_next_year_activity(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=_current_deps(tmp_path))
        fakes = Fakes(tmp_path)
        R.run_history(
            conn, CITY, range(2024, 2027), data_dir=tmp_path, config_dir=CFG_DIR,
            deps=fakes.deps(),
        )  # fmt: skip
        pts = T.series(conn, "berlin", "lau", _selector(), fakes.set_md5)
        assert [p.label for p in pts] == ["2024", "2025", "2026", "current"]
        assert pts[-1].activity is not None and pts[-1].activity.year == 2027
        assert pts[0].activity.year == 2024
        assert pts[0].headline is not None and pts[0].ab_km >= 0
        cs = T.build_city(conn, "berlin", "lau", _selector(), range(2024, 2027))
        assert cs.current_fraction == pytest.approx(T.current_fraction(pts[-1].osm_timestamp))
        assert "current run" in cs.provenance and not cs.notes and cs.missing_years == ()


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
    path, set_md5, _ = db
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
    args += ["--config-dir", str(db[2])]
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
    from velometer.config import ConfigError, load_cities, load_history

    h = load_history(CFG_DIR / "history.yaml")
    trusted = trusted_countries(CFG_DIR)
    cities = [c for c in load_cities(CFG_DIR / "cities.yaml") if c.country_iso2 in trusted]
    assert cities
    for c in cities:  # M5: every trusted city has a LAU and a FUA series, however it is listed
        assert {"lau", "fua"} <= set(h.required(c.id)), c.id
    assert h.year_range() == range(2018, 2027)
    override = tmp_path / "o.yaml"
    override.write_text(f'years: "2018-2026"\n{REQUIRED_KINDS}')
    o = load_history(override)
    assert o.required("berlin") == ["lau", "fua"] and o.required("vienna") == ["lau"]
    bad = tmp_path / "h.yaml"
    bad.write_text('years: "2026-2018"\nrequired_kinds: {default: [lau]}\n')
    with pytest.raises(ConfigError):
        load_history(bad)
    bad.write_text('years: "2018-2026"\nrequired_kinds: {berlin: [lau]}\n')
    with pytest.raises(ConfigError):
        load_history(bad)
    bad.write_text('years: "2018-2026"\nrequired_kinds: {default: [lau]}\nextra: 1\n')
    with pytest.raises(ConfigError):
        load_history(bad)


# --- R19: complete year ranges, activity.yaml in the marker, --boundary, population -------------


def test_change_rules_never_compare_across_a_gap():
    assert rules([pt("2019", 100), pt("2021", 200)]) == {}
    assert rules([pt("2019", 5, legacy=100), pt("2021", 5, legacy=500)]) == {}
    assert rules([pt("2019", 100), pt("2020", 200)]) == {"2020": {"km_jump"}}  # control
    # a current point compares only with the 1 January of its own year (CURRENT_TS is 2026)
    assert rules([pt("2025", 100), pt("current", 200)], 0.5) == {}
    assert rules([pt("2026", 100), pt("current", 200)], 0.5) == {"current": {"km_jump"}}


def _bump_ab(path, label, km=1000.0):
    with open_db(path) as conn:
        conn.execute(
            "UPDATE tier_lengths SET length_km = length_km + ? WHERE tier='A' AND "
            "length_basis='per_side' AND run_id IN (SELECT id FROM runs WHERE status='done' "
            "AND source='history' AND osm_timestamp=?)",
            (km, f"{label}-01-01T00:00:00Z"),
        )
        conn.commit()


def test_cli_check_fails_on_a_missing_year_and_flags_no_jump_across_it(tmp_path):
    path = tmp_path / "v.sqlite"
    fakes = Fakes(tmp_path, fail_year=2020)
    cfg = config_dir(tmp_path)
    with open_db(path) as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_history(
            conn, CITY, range(2019, 2022), data_dir=tmp_path, config_dir=cfg, deps=fakes.deps()
        )
    _bump_ab(path, "2021")  # 2019 -> 2021 would be a km_jump if compared
    db = (path, fakes.set_md5, cfg)
    report = _report(tmp_path, marker=f"berlin/lau={fakes.set_md5[:8]}")
    res = _ts(db, report, "--check")
    assert res.exit_code == 1, res.output
    assert "missing history year berlin/lau/2020" in res.output
    assert "km_jump" not in res.output
    assert "berlin/lau/2020 has no done history run" in res.output  # the note


def test_series_without_the_current_year_has_no_current_point_and_a_note(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=_current_deps(tmp_path))
        fakes = Fakes(tmp_path)
        R.run_history(
            conn, CITY, range(2022, 2025), data_dir=tmp_path, config_dir=CFG_DIR,
            deps=fakes.deps(),
        )  # fmt: skip
        cs = T.build_city(conn, "berlin", "lau", _selector(), range(2022, 2025))
    assert [p.label for p in cs.points] == ["2022", "2023", "2024"]
    assert any("does not follow the last history year 2024" in n for n in cs.notes), cs.notes
    assert "no current run" in cs.provenance


def test_marker_has_no_activity_part_and_check_ignores_it(db, tmp_path):
    sets = {("berlin", "lau"): db[1]}
    assert "activity=" not in T.explained_against_marker(sets)
    assert not hasattr(T, "unexplained_activity") and not hasattr(T, "activity_sha")
    report = _report(tmp_path, marker=f"berlin/lau={db[1][:8]}", activity=OLD_ACTIVITY_PART)
    assert T.explained_against(report) == {"berlin/lau": db[1][:8]}  # the old part is ignored
    res = _ts(db, report, "--check")
    assert res.exit_code == 0, res.output


def test_cli_check_boundary_fua_applies_only_to_cities_requiring_fua(tmp_path):
    path = tmp_path / "v.sqlite"
    fakes = Fakes(tmp_path)
    cfg = config_dir(tmp_path)
    with open_db(path) as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        for kind in ("lau", "fua"):
            R.run_history(
                conn, CITY, range(2019, 2022), data_dir=tmp_path, config_dir=cfg,
                boundary_kind=kind, deps=fakes.deps(),
            )  # fmt: skip
    marker = f"berlin/fua={fakes.set_md5[:8]} berlin/lau={fakes.set_md5[:8]}"
    report = _report(tmp_path, "### berlin/lau/2020\nx\n", marker=marker)
    args = ["timeseries", "--db", str(path), "--report", str(report), "--config-dir", str(cfg)]
    args += ["--check", "--boundary", "fua", "--city", "berlin", "--city", "vienna"]
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 0, res.output  # vienna needs lau only
    assert "vienna/fua" not in res.output
    assert "berlin/lau/2020" not in res.output  # a LAU heading is not checked under --boundary fua


def test_provenance_without_population_says_so(tmp_path):
    fakes = Fakes(tmp_path)
    base = fakes.deps()

    def no_population(city, kind, data_dir, region_path=None):
        rec, _ = base.city_boundary(city, kind, data_dir, region_path)
        return rec, None

    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        from velometer.config import load_cities

        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        R.run_history(
            conn, CITY, range(2019, 2021), data_dir=tmp_path, config_dir=CFG_DIR,
            boundary_kind="fua", deps=fakes.deps(city_boundary=no_population),
        )  # fmt: skip
        cs = T.build_city(conn, "berlin", "fua", _selector())
    assert "no population (per-100k n/a)" in cs.provenance
    assert "None" not in cs.provenance


def test_bumped_ab_km_without_a_gap_is_a_km_jump(db, tmp_path):
    # control for the gap test: the same bump between consecutive years is flagged
    _bump_ab(db[0], "2021")
    res = _ts(db, _report(tmp_path, marker=f"berlin/lau={db[1][:8]}"))
    assert res.exit_code == 0 and "km_jump" in res.output


def test_adr_0005_note_counts_history_runs_as_series_times_years():
    adr = (
        Path(__file__).parent.parent
        / "docs"
        / "adr"
        / "0005-annual-snapshots-versioned-classifier.md"
    )
    text = " ".join(adr.read_text().split())
    m = re.search(r"(\d+) history runs \((\d+) city/boundary series × (\d+) years", text)
    assert m is not None
    assert int(m[1]) == int(m[2]) * int(m[3])


def test_report_classifier_is_the_newest_shipped_classifier():
    """Reports use the newest classifier version in config/classifier/ (v2 in M4, v3 in M5)."""
    from velometer.config import load_report

    newest = max(int(p.stem.removeprefix("v")) for p in (CFG_DIR / "classifier").glob("v*.yaml"))
    assert load_report(CFG_DIR / "report.yaml").report_classifier == f"v{newest}"


def test_cli_timeseries_defaults_to_the_report_classifier(db, tmp_path):
    # db holds v1 history runs only: v1 as report classifier finds them, v2 does not
    report = _report(tmp_path, marker=f"berlin/lau={db[1][:8]}")
    assert "no history runs" not in _ts(db, report).output
    rep = db[2] / "report.yaml"
    rep.write_text(rep.read_text().replace("report_classifier: v1", "report_classifier: v2"))
    assert "no history runs for berlin/lau" in _ts(db, report, "--check").output
    assert "no history runs" not in _ts(db, report, "--classifier", "v1").output


# --- explanation text (the app's flagged-years section) ------------------------------------

EXPLAINED = """# M3 time series

<!-- timeseries:begin -->
#### berlin/lau

| year | ... |
<!-- timeseries:end -->

## Explanations

<!-- explained-against: berlin/lau=c3335f42 -->

### berlin/lau/2019

Cause: **tag drift**, first paragraph.

Second paragraph.

### berlin/lau/2022

Cause: campaign.

## Afterword

Not part of any explanation.

### berlin/lau/2026
"""


def test_explanation_is_the_text_under_its_heading(tmp_path):
    p = tmp_path / "m3_timeseries.md"
    p.write_text(EXPLAINED)
    assert T.explanation(p, "berlin/lau/2019") == (
        "Cause: **tag drift**, first paragraph.\n\nSecond paragraph."
    )
    assert T.explanation(p, "berlin/lau/2022") == "Cause: campaign."  # stops at `## `


def test_explanation_none_when_absent_empty_or_unreadable(tmp_path):
    p = tmp_path / "m3_timeseries.md"
    p.write_text(EXPLAINED)
    assert T.explanation(p, "berlin/lau/2020") is None
    assert T.explanation(p, "berlin/lau/201") is None  # no prefix match
    assert T.explanation(p, "berlin/lau") is None  # the generated block's #### heading
    assert T.explanation(p, "berlin/lau/2026") is None  # heading without text
    assert T.explanation(tmp_path / "missing.md", "berlin/lau/2019") is None


def test_explanation_reads_utf8_under_a_non_utf8_locale(tmp_path):
    """m3_timeseries.md carries non-ASCII ("Plan Vélo", "June–August"); a C locale with UTF-8
    mode off must still read it (it used to raise UnicodeDecodeError, a 500 on the city page)."""
    import os
    import subprocess
    import sys

    p = tmp_path / "m3_timeseries.md"
    p.write_text("### paris/lau/2021\n\nPlan Vélo, June–August.\n", encoding="utf-8")
    code = (
        "import locale, sys; from velometer import timeseries as T; "
        "assert locale.getencoding().lower() != 'utf-8', locale.getencoding(); "
        f"sys.stdout.buffer.write(T.explanation({str(p)!r}, 'paris/lau/2021').encode('utf-8'))"
    )
    env = {**os.environ, "LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, check=False)
    assert r.returncode == 0, r.stderr.decode()
    assert r.stdout.decode("utf-8") == "Plan Vélo, June–August."
