import re
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from velometer.cli import app
from velometer.db import connect, fetch_cities


def test_init_creates_db_with_cities_and_is_idempotent(tmp_path):
    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    for _ in range(2):
        result = runner.invoke(app, ["init", "--db", str(db)])
        assert result.exit_code == 0, result.output
    assert len(fetch_cities(connect(db))) == 5
    assert "5 cities" in result.output


def test_init_refuses_newer_schema(tmp_path):
    db = tmp_path / "v.sqlite"
    c = sqlite3.connect(db)
    c.execute("PRAGMA user_version = 99")
    c.close()
    result = CliRunner().invoke(app, ["init", "--db", str(db)])
    assert result.exit_code == 1
    assert "newer" in result.output


def test_classify_prints_tiers_roads_and_presets():
    fixture = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"
    result = CliRunner().invoke(app, ["classify", "--file", str(fixture), "--epsg", "25833"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert re.search(r"^A\s+-\s+per_side\s+2\.99\d\s+2$", out, re.M), out
    assert re.search(r"^main_excl_motorway\s+1\.99\d$", out, re.M), out
    assert re.search(r"^ours_headline\s+200\.0\s", out, re.M), out
    assert "skipped ways: 0" in out


def test_classify_rejects_geographic_epsg():
    fixture = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"
    result = CliRunner().invoke(app, ["classify", "--file", str(fixture), "--epsg", "4326"])
    assert result.exit_code == 1
    assert "EPSG:4326 is not a projected CRS" in result.output
    assert "ours_headline" not in result.output


def test_classify_reports_plain_oneway_mode_and_override(tmp_path):
    osm = tmp_path / "oneway.osm"
    osm.write_text(
        '<?xml version="1.0"?><osm version="0.6">'
        '<node id="1" lat="52.5" lon="13.4"/><node id="2" lat="52.5" lon="13.4147"/>'
        '<way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="tertiary"/>'
        '<tag k="oneway" v="yes"/><tag k="cycleway" v="track"/></way></osm>'
    )
    base = ["classify", "--file", str(osm), "--epsg", "25833"]
    default = CliRunner().invoke(app, base)
    assert default.exit_code == 0, default.output
    assert "plain_cycleway_on_oneway=traffic_side" in default.output
    assert re.search(r"1 ways.*both_sides.*A \+0\.99\d km", default.output), default.output
    both = CliRunner().invoke(app, [*base, "--plain-cycleway-on-oneway", "both_sides"])
    assert both.exit_code == 0, both.output
    assert "plain_cycleway_on_oneway=both_sides" in both.output
    assert re.search(r"^A\s+-\s+per_side\s+1\.99\d\s+1$", both.output, re.M), both.output
    bad = CliRunner().invoke(app, [*base, "--plain-cycleway-on-oneway", "sometimes"])
    assert bad.exit_code != 0


def test_results_command_prints_table_from_db(tmp_path, monkeypatch):
    from velometer import run as R

    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--db", str(db)]).exit_code == 0
    import tests.test_run as tr

    deps = tr._deps(tmp_path, [])  # built before the patch: _deps itself calls R.RunDeps
    monkeypatch.setattr(R, "RunDeps", lambda: deps)
    out = runner.invoke(
        app, ["run", "--cities", "berlin", "--db", str(db), "--data", str(tmp_path)]
    )
    assert out.exit_code == 0, out.output
    assert "berlin" in out.output and "done" in out.output
    table = runner.invoke(app, ["results", "--db", str(db)])
    assert table.exit_code == 0
    assert re.search(r"^berlin\s+2026-09-30\s+\d+\.\d", table.output, re.M), table.output


def test_classify_rejects_file_and_city_together(tmp_path):
    f = tmp_path / "x.osm"
    f.write_text("<osm/>")
    out = CliRunner().invoke(app, ["classify", "--file", str(f), "--city", "berlin"])
    assert out.exit_code == 2 and "mutually exclusive" in out.output


def test_run_exits_1_when_a_city_fails(tmp_path, monkeypatch):
    import tests.test_run as tr
    from velometer import run as R

    def boom(path):
        raise RuntimeError("disk on fire")

    deps = tr._deps(tmp_path, [], read=boom)
    monkeypatch.setattr(R, "RunDeps", lambda: deps)
    out = CliRunner().invoke(
        app,
        ["run", "--cities", "berlin", "--db", str(tmp_path / "v.sqlite"), "--data", str(tmp_path)],
    )
    assert out.exit_code == 1 and "berlin failed" in out.output


def _patched(monkeypatch, tmp_path, **kw):
    import tests.test_run as tr
    from velometer import run as R

    deps = tr._deps(tmp_path, [], **kw)
    monkeypatch.setattr(R, "RunDeps", lambda: deps)
    return deps


def test_osm_fetch_prints_region_path_and_md5(tmp_path, monkeypatch):
    _patched(monkeypatch, tmp_path)
    out = CliRunner().invoke(app, ["osm", "fetch", "--city", "berlin", "--data", str(tmp_path)])
    assert out.exit_code == 0, out.output
    assert "berlin" in out.output and "md5=md5" in out.output and "mini_city.osm" in out.output


def test_boundaries_fetch_all_skips_missing_code_and_stores_rest(tmp_path, monkeypatch):
    import shutil

    from velometer.config import default_config_dir

    cfg = tmp_path / "cfg"
    shutil.copytree(default_config_dir(), cfg)
    text = (cfg / "cities.yaml").read_text().replace("    fua_code: DE001F\n", "")
    assert "DE001F" not in text
    (cfg / "cities.yaml").write_text(text)
    _patched(monkeypatch, tmp_path)
    db = tmp_path / "v.sqlite"
    out = CliRunner().invoke(
        app,
        [
            "boundaries",
            "fetch",
            "--city",
            "berlin",
            "--config-dir",
            str(cfg),
            "--db",
            str(db),
            "--data",
            str(tmp_path),
        ],
    )
    assert out.exit_code == 0, out.output
    assert "berlin fua skipped" in out.output
    assert "berlin lau area_km2=" in out.output and "berlin osm_admin area_km2=" in out.output
    kinds = {r[0] for r in sqlite3.connect(db).execute("SELECT kind FROM boundaries")}
    assert kinds == {"lau", "osm_admin"}


def test_boundaries_fetch_unknown_kind_exits_2(tmp_path, monkeypatch):
    _patched(monkeypatch, tmp_path)
    out = CliRunner().invoke(
        app, ["boundaries", "fetch", "--kind", "bogus", "--db", str(tmp_path / "v.sqlite")]
    )
    assert out.exit_code == 2


def test_failing_fetch_exits_1_and_continues_with_next_city(tmp_path, monkeypatch):
    from velometer import run as R

    deps = _patched(monkeypatch, tmp_path)
    calls = []

    def flaky(region, data_dir):
        calls.append(region)
        if len(calls) == 1:
            raise RuntimeError("net down")
        return deps.fetch_region(region, data_dir)

    import dataclasses

    patched = dataclasses.replace(deps, fetch_region=flaky)
    monkeypatch.setattr(R, "RunDeps", lambda: patched)
    out = CliRunner().invoke(app, ["osm", "fetch", "--data", str(tmp_path)])
    assert out.exit_code == 1
    assert len(calls) == 5 and "failed RuntimeError: net down" in out.output
    assert "md5=md5" in out.output


def test_run_prints_dash_for_pre_run_failure(tmp_path, monkeypatch):
    import dataclasses

    from velometer import run as R

    deps = _patched(monkeypatch, tmp_path)

    def bad(*a, **kw):
        raise ValueError("no population")

    patched = dataclasses.replace(deps, city_boundary=bad)
    monkeypatch.setattr(R, "RunDeps", lambda: patched)
    out = CliRunner().invoke(
        app,
        ["run", "--cities", "berlin", "--db", str(tmp_path / "v.sqlite"), "--data", str(tmp_path)],
    )
    assert out.exit_code == 1 and "berlin failed run=- ValueError" in out.output


def test_external_load_offline_prints_rows_per_source(tmp_path):
    r = CliRunner().invoke(
        app,
        ["external", "load", "--no-qecio", "--no-bikenetkit", "--db", str(tmp_path / "v.sqlite")],
    )
    assert r.exit_code == 0, r.output
    from collections import Counter

    from velometer.config import default_config_dir
    from velometer.sources.external import load_figures_csv

    curated = load_figures_csv(default_config_dir() / "external" / "figures.csv")
    for source, n in Counter(f.source for f in curated).items():
        assert f"{source} {n} rows" in r.output


def test_reconcile_skips_cities_without_run(tmp_path):
    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--db", str(db)]).exit_code == 0
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    out = runner.invoke(
        app,
        ["reconcile", "--city", "berlin", "--db", str(db), "--report", str(report), "--write"],
    )
    assert out.exit_code == 0, out.output
    assert "no done" in out.output and "skipped" in out.output


def _external(conn, source, metric, value, scope="whole_network"):
    conn.execute(
        "INSERT INTO external_figures (city_id, source, metric_name, value, unit, "
        "reference_date, network_scope, length_basis, source_url, retrieved_at) "
        "VALUES ('berlin',?,?,?,'km','2026-09-30',?,'unknown','u','2026-10-01')",
        (source, metric, value, scope),
    )


def _required_rows_matching_ours(db: Path) -> int:
    """Insert Berlin's required external rows at our own values (no flagged gap); return run id."""
    with connect(db) as conn:
        (rid,) = conn.execute("SELECT MAX(id) FROM runs WHERE status='done'").fetchone()
        one = lambda sql: conn.execute(sql, (rid,)).fetchone()[0]  # noqa: E731
        cc = one("SELECT value FROM metrics WHERE run_id=? AND preset='clean_cities_2025'")
        main = one(
            "SELECT length_km FROM road_lengths WHERE run_id=? "
            "AND road_class='main_incl_motorway_raw'"
        )
        bnk = one(
            "SELECT SUM(length_km) FROM tier_lengths WHERE run_id=? AND tier IN ('A','B','E') "
            "AND length_basis='per_side'"
        )
        _external(conn, "clean_cities_2025", "protected_share_pct", cc)
        _external(conn, "qecio_v2_10", "main_roads_km", main, "nuts3_DE300")
        _external(conn, "bikenetkit_v1", "bike_network_km", bnk, "bikenetkit_bike_network")
        conn.commit()
    return rid


def test_reconcile_check_exits_1_until_the_gap_is_explained(tmp_path, monkeypatch):
    runner, db = _berlin_run(tmp_path, monkeypatch)
    rid = _required_rows_matching_ours(db)
    with connect(db) as conn:
        _external(conn, "clean_cities_2025", "network_km", 1e9)
        conn.commit()
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n\n## Explanations\n")
    rargs = ["reconcile", "--city", "berlin", "--db", str(db), "--report", str(report)]
    bad = runner.invoke(app, [*rargs, "--write", "--check"])
    assert bad.exit_code == 1
    assert "berlin/cc_network_km" in bad.output
    assert f"explained-against: berlin={rid}" in bad.output  # the marker to set is printed
    with report.open("a") as f:
        f.write("\n### berlin/cc_network_km\n\nBecause.\n")
    still = runner.invoke(app, [*rargs, "--check"])
    assert still.exit_code == 1 and "explanations out of date" in still.output
    with report.open("a") as f:
        f.write(f"\n<!-- explained-against: berlin={rid} -->\n")
    ok = runner.invoke(app, [*rargs, "--check"])
    assert ok.exit_code == 0, ok.output
    assert f"Provenance: run {rid} " in report.read_text()
    # other cities have no done run: --check over all cities fails, --city berlin passes
    all_cities = runner.invoke(
        app, ["reconcile", "--db", str(db), "--report", str(report), "--check"]
    )
    assert all_cities.exit_code == 1 and "no done run for paris" in all_cities.output


def test_reconcile_check_fails_when_a_required_comparison_has_no_figure(tmp_path, monkeypatch):
    runner, db = _berlin_run(tmp_path, monkeypatch)
    rid = _required_rows_matching_ours(db)
    with connect(db) as conn:
        conn.execute("DELETE FROM external_figures WHERE source='bikenetkit_v1'")
        conn.commit()
    report = tmp_path / "r.md"
    report.write_text(
        "<!-- reconcile:begin -->\n<!-- reconcile:end -->\n\n## Explanations\n\n"
        f"<!-- explained-against: berlin={rid} -->\n\n### berlin/old_gap\n"
    )
    rargs = ["reconcile", "--city", "berlin", "--db", str(db), "--report", str(report)]
    out = runner.invoke(app, [*rargs, "--check"])
    assert out.exit_code == 1
    assert "required comparison has no external figure: berlin/bnk_network_km" in out.output
    assert "warning: ### berlin/old_gap matches no flagged gap" in out.output


def _berlin_run(tmp_path, monkeypatch):
    from velometer import run as R

    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--db", str(db)]).exit_code == 0
    import tests.test_run as tr

    deps = tr._deps(tmp_path, [])
    monkeypatch.setattr(R, "RunDeps", lambda: deps)
    args = ["run", "--cities", "berlin", "--db", str(db), "--data", str(tmp_path)]
    assert runner.invoke(app, args).exit_code == 0
    return runner, db


def test_reconcile_write_with_city_keeps_other_cities(tmp_path, monkeypatch):
    runner, db = _berlin_run(tmp_path, monkeypatch)
    args = ["run", "--cities", "paris", "--db", str(db), "--data", str(tmp_path)]
    assert runner.invoke(app, args).exit_code == 0
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    out = runner.invoke(
        app, ["reconcile", "--city", "berlin", "--db", str(db), "--report", str(report), "--write"]
    )
    assert out.exit_code == 0, out.output
    text = report.read_text()
    assert "#### berlin" in text and "#### paris" in text


def test_reconcile_write_refuses_a_basis_override(tmp_path, monkeypatch):
    # the committed report block follows presets.yaml; an override is for looking, not writing
    runner, db = _berlin_run(tmp_path, monkeypatch)
    report = tmp_path / "r.md"
    before = "<!-- reconcile:begin -->\n<!-- reconcile:end -->\n"
    report.write_text(before)
    base = ["reconcile", "--city", "berlin", "--db", str(db), "--report", str(report)]
    out = runner.invoke(app, [*base, "--write", "--clean-cities-basis", "qecio_weighted"])
    assert out.exit_code == 2, out.output
    assert "--clean-cities-basis" in out.output
    assert report.read_text() == before


def test_reconcile_missing_markers_or_report_exit_1_without_traceback(tmp_path, monkeypatch):
    runner, db = _berlin_run(tmp_path, monkeypatch)
    base = ["reconcile", "--city", "berlin", "--db", str(db)]
    bad = tmp_path / "nomarkers.md"
    bad.write_text("# no markers\n")
    out = runner.invoke(app, [*base, "--report", str(bad), "--write"])
    assert out.exit_code == 1 and "error:" in out.output and out.exception.__class__ is SystemExit
    out = runner.invoke(app, [*base, "--report", str(tmp_path / "gone.md"), "--check"])
    assert out.exit_code == 1 and "error:" in out.output and out.exception.__class__ is SystemExit


def test_commands_on_a_newer_schema_exit_1_without_traceback(tmp_path):
    from velometer.db import SCHEMA_VERSION

    db = tmp_path / "v.sqlite"
    with sqlite3.connect(db) as c:
        c.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    for args in (
        ["run", "--cities", "berlin", "--data", str(tmp_path)],
        ["boundaries", "fetch", "--city", "berlin", "--data", str(tmp_path)],
        ["results"],
        ["reconcile", "--report", str(report)],
    ):
        out = CliRunner().invoke(app, [*args, "--db", str(db)])
        assert out.exit_code == 1, (args, out.output)
        assert out.exception.__class__ is SystemExit, args
        assert "database error" in out.output and "newer" in out.output, args


def test_external_load_bad_zip_or_gpkg_exits_1_without_traceback(tmp_path, monkeypatch):
    import zipfile

    from pyogrio.errors import DataSourceError

    from velometer.sources import external

    for exc in (zipfile.BadZipFile("not a zip"), DataSourceError("not a gpkg")):

        def boom(*a, exc=exc, **kw):
            raise exc

        monkeypatch.setattr(external, "load_all", boom)
        out = CliRunner().invoke(app, ["external", "load", "--db", str(tmp_path / "v.sqlite")])
        assert out.exit_code == 1 and out.exception.__class__ is SystemExit, out.output
        assert "external load failed" in out.output


MINI_CITY = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"


def _cc(output: str, preset_line: str = "clean_cities_2025") -> str:
    """The value column of the selected `clean_cities_2025` row of `classify --file`."""
    (m,) = re.findall(rf"^{preset_line}\s+([\d.]+)\s", output, re.M)
    return m


def test_classify_file_prints_the_cc_basis_and_the_other_basis_line():
    base = ["classify", "--file", str(MINI_CITY), "--epsg", "25833"]
    default = CliRunner().invoke(app, base)
    assert default.exit_code == 0, default.output
    assert "presets (clean_cities_basis=per_side)" in default.output
    assert _cc(default.output) == "100.1"
    assert (
        "clean_cities_2025 on qecio_weighted: 62.5% (switch with --clean-cities-basis)"
        in default.output
    )
    weighted = CliRunner().invoke(app, [*base, "--clean-cities-basis", "qecio_weighted"])
    assert weighted.exit_code == 0, weighted.output
    assert "presets (clean_cities_basis=qecio_weighted)" in weighted.output
    assert _cc(weighted.output) == "62.5"
    assert "clean_cities_2025 on per_side: 100.1% (switch" in weighted.output
    # fixed-basis presets do not move
    assert re.search(r"^ours_headline\s+200\.0\s", weighted.output, re.M)
    assert CliRunner().invoke(app, [*base, "--clean-cities-basis", "bogus"]).exit_code != 0


def test_results_prints_the_selected_basis_and_the_other_one(tmp_path, monkeypatch):
    runner, db = _berlin_run(tmp_path, monkeypatch)
    per_side = runner.invoke(app, ["results", "--db", str(db)])
    assert per_side.exit_code == 0, per_side.output
    assert "presets (clean_cities_basis=per_side)" in per_side.output
    assert re.search(
        r"^clean_cities_2025 on qecio_weighted: berlin \S+% \(switch", per_side.output, re.M
    )
    weighted = runner.invoke(
        app, ["results", "--db", str(db), "--clean-cities-basis", "qecio_weighted"]
    )
    assert "presets (clean_cities_basis=qecio_weighted)" in weighted.output
    assert re.search(r"^clean_cities_2025 on per_side: berlin \S+% \(switch", weighted.output, re.M)

    def cc_column(out: str) -> str:
        header, row = (
            next(
                (ln for ln in out.splitlines() if ln.startswith("city")),
                "",
            ),
            next(ln for ln in out.splitlines() if ln.startswith("berlin")),
        )
        return row.split()[header.split().index("clean_cities")]

    assert cc_column(per_side.output) != cc_column(weighted.output)
    with connect(db) as conn:
        rows = dict(
            conn.execute(
                "SELECT length_basis, value FROM metrics WHERE preset='clean_cities_2025'"
            ).fetchall()
        )
    assert cc_column(per_side.output) == f"{rows['per_side']:.1f}"
    assert cc_column(weighted.output) == f"{rows['qecio_weighted']:.1f}"


def test_classify_city_prints_the_selected_cc_value_and_basis(tmp_path, monkeypatch):
    _patched(monkeypatch, tmp_path)
    db = tmp_path / "v.sqlite"
    args = ["classify", "--city", "berlin", "--db", str(db), "--data", str(tmp_path)]
    out = CliRunner().invoke(app, args)
    assert out.exit_code == 0, out.output
    assert "presets (clean_cities_basis=per_side)" in out.output
    assert re.search(r"^berlin clean_cities_2025: 100\.1%", out.output, re.M), out.output
    assert "clean_cities_2025 on qecio_weighted:" in out.output
    again = CliRunner().invoke(
        app, [*args, "--clean-cities-basis", "qecio_weighted"]
    )  # skipped run
    assert re.search(r"^berlin clean_cities_2025: 62\.5%", again.output, re.M), again.output
    assert "clean_cities_2025 on per_side:" in again.output


def _cc_km_gap_line(output: str, key: str) -> str:
    (line,) = [ln for ln in output.splitlines() if ln.startswith(f"| `{key}`")]
    return line


def test_reconcile_switches_the_flagged_basis_and_always_shows_the_other(tmp_path, monkeypatch):
    runner, db = _berlin_run(tmp_path, monkeypatch)
    with connect(db) as conn:
        (per_side,) = conn.execute(
            "SELECT numerator_km FROM metrics WHERE preset='clean_cities_2025' "
            "AND length_basis='per_side'"
        ).fetchone()
        _external(conn, "clean_cities_2025", "protected_km", per_side)  # per_side matches exactly
        conn.commit()
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    args = ["reconcile", "--city", "berlin", "--db", str(db), "--report", str(report)]
    default = runner.invoke(app, args)
    assert default.exit_code == 0, default.output
    assert "presets (clean_cities_basis=per_side)" in default.output
    assert "clean_cities_basis=per_side" in default.output.split("Provenance:")[1].splitlines()[0]
    assert "| ok |" in _cc_km_gap_line(default.output, "berlin/cc_km")
    info = _cc_km_gap_line(default.output, "berlin/cc_km~qecio_weighted")
    assert "| info |" in info
    weighted = runner.invoke(app, [*args, "--clean-cities-basis", "qecio_weighted"])
    assert "clean_cities_basis=qecio_weighted" in weighted.output.split("Provenance:")[1]
    assert "**>20%**" in _cc_km_gap_line(weighted.output, "berlin/cc_km")
    assert "| info |" in _cc_km_gap_line(weighted.output, "berlin/cc_km~per_side")
    # --check follows the selected basis: the weighted reading flags cc_km (and wants a note)
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    check = runner.invoke(app, [*args, "--clean-cities-basis", "qecio_weighted", "--check"])
    assert check.exit_code == 1 and "missing explanation: ### berlin/cc_km" in check.output
    assert "cc_km~" not in check.output.split("missing explanation")[1]


def _stale_setup(tmp_path, monkeypatch):
    import shutil

    from velometer.config import default_config_dir

    cfg = tmp_path / "cfg"
    shutil.copytree(default_config_dir(), cfg)
    runner, db = None, tmp_path / "v.sqlite"
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--db", str(db), "--config-dir", str(cfg)]).exit_code == 0
    _patched(monkeypatch, tmp_path)
    run = ["run", "--cities", "berlin", "--db", str(db), "--data", str(tmp_path)]
    run += ["--config-dir", str(cfg)]
    return runner, db, cfg, run


def test_results_and_reconcile_report_the_config_on_disk_after_an_edit_and_revert(
    tmp_path, monkeypatch
):
    runner, db, cfg, run = _stale_setup(tmp_path, monkeypatch)
    presets = cfg / "presets.yaml"
    original = presets.read_text()
    first = runner.invoke(app, run)
    assert first.exit_code == 0 and "berlin done run=1" in first.output
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    rargs = ["--db", str(db), "--config-dir", str(cfg)]
    # B: edit the config. Nothing has been run on it yet: both commands say so.
    presets.write_text(original + "# edit\n")
    res = runner.invoke(app, ["results", *rargs])
    assert "no done runs" in res.output and "current config" in res.output
    assert "berlin has no done" in res.output  # runs exist, but of another config
    rec = runner.invoke(
        app, ["reconcile", "--city", "berlin", "--report", str(report), "--check", *rargs]
    )
    assert rec.exit_code == 1 and "no done run for berlin of the current config" in rec.output
    second = runner.invoke(app, run)
    assert "berlin done run=2" in second.output
    # A again: the A run is reused (skipped) and is what the reports name, not the newer B run
    presets.write_text(original)
    assert "berlin skipped run=1" in runner.invoke(app, run).output
    res = runner.invoke(app, ["results", *rargs])
    assert re.search(r"^berlin\s", res.output, re.M), res.output
    rec = runner.invoke(app, ["reconcile", "--city", "berlin", "--report", str(report), *rargs])
    assert "Provenance: run 1 " in rec.output
