import re
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from velometer.cli import app
from velometer.config import default_config_dir, load_cities
from velometer.db import SCHEMA_VERSION, connect, fetch_cities


def test_init_creates_db_with_cities_and_is_idempotent(tmp_path):
    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    for _ in range(2):
        result = runner.invoke(app, ["init", "--db", str(db)])
        assert result.exit_code == 0, result.output
    n = len(load_cities(default_config_dir() / "cities.yaml"))
    assert len(fetch_cities(connect(db))) == n
    assert f"{n} cities" in result.output


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


def test_boundaries_fetch_lau_of_an_osm_relation_city_fetches_the_region_first(
    tmp_path, monkeypatch
):
    import dataclasses
    import shutil

    from velometer import run as R

    cfg = tmp_path / "cfg"
    shutil.copytree(default_config_dir(), cfg)
    text = (cfg / "cities.yaml").read_text()
    marker = "    osm_relation_id: 62422\n"
    assert text.count(marker) == 1
    (cfg / "cities.yaml").write_text(
        text.replace(marker, marker + "    admin_boundary: osm_relation\n")
    )
    deps = _patched(monkeypatch, tmp_path)
    seen = []

    def spy(city, kind, data_dir, region_path=None):
        seen.append((kind, region_path))
        return deps.city_boundary(city, kind, data_dir, region_path=region_path)

    fetched = []

    def fetch(region, data_dir):
        fetched.append(region)
        return deps.fetch_region(region, data_dir)

    monkeypatch.setattr(
        R, "RunDeps", lambda: dataclasses.replace(deps, city_boundary=spy, fetch_region=fetch)
    )

    def invoke(*extra):
        return CliRunner().invoke(
            app,
            ["boundaries", "fetch", "--city", "berlin", "--config-dir", str(cfg)]
            + [*extra, "--db", str(tmp_path / "v.sqlite"), "--data", str(tmp_path)],
        )

    out = invoke("--kind", "lau")
    assert out.exit_code == 0, out.output
    assert fetched == ["europe/germany/berlin"]
    assert seen and seen[0][0] == "lau" and seen[0][1] is not None
    # the FUA is not an OSM layer: no region needed
    seen.clear()
    fetched.clear()
    assert invoke("--kind", "fua").exit_code == 0
    assert fetched == [] and seen == [("fua", None)]


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
    n = len(load_cities(default_config_dir() / "cities.yaml"))
    assert len(calls) == n and "failed RuntimeError: net down" in out.output
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
    assert "missing explanation: ### berlin/cc_network_km" in bad.output
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


def test_auth_check_reports_failure_without_the_password(tmp_path, monkeypatch):
    import httpx

    from tests.test_geofabrik_auth import SECRET, _transport
    from velometer.sources import geofabrik_auth

    monkeypatch.setenv("VELOMETER_OSM_USER", "me")
    monkeypatch.setenv("VELOMETER_OSM_PASSWORD", SECRET)
    # the real login flow runs against a server that rejects the login (200 instead of 302)
    monkeypatch.setattr(
        geofabrik_auth,
        "new_auth_client",
        lambda: httpx.Client(transport=_transport([], login_status=200)),
    )
    result = CliRunner().invoke(app, ["auth", "check", "--data", str(tmp_path)])
    assert result.exit_code == 1
    assert "osm login" in result.output
    assert SECRET not in result.output


def test_cli_years_parse_and_reject(tmp_path, monkeypatch):
    from velometer import run as run_mod

    calls = []

    def fake_run_history(conn, city, years, **kw):
        calls.append((city.id, years, kw["boundary_kind"]))
        return [run_mod.RunOutcome(city.id, "done", 1, year=y) for y in years]

    monkeypatch.setattr(run_mod, "run_history", fake_run_history)
    db = str(tmp_path / "v.sqlite")
    base = ["run", "--cities", "berlin", "--db", db, "--data", str(tmp_path)]
    ok = CliRunner().invoke(app, [*base, "--years", "2018-2026"])
    assert ok.exit_code == 0, ok.output
    assert calls == [("berlin", range(2018, 2027), "lau")]
    assert "berlin 2018 done run=1" in ok.output and "berlin 2026 done" in ok.output
    calls.clear()
    for bad in ("2026-2018", "x", "2018", "2018-", "2018-20x6"):
        r = CliRunner().invoke(app, [*base, "--years", bad])
        assert r.exit_code == 2, (bad, r.output)
    assert calls == []
    one = CliRunner().invoke(app, [*base, "--years", "2020-2020"])
    assert one.exit_code == 0 and calls == [("berlin", range(2020, 2021), "lau")]


def test_cli_years_failed_outcome_exits_1(tmp_path, monkeypatch):
    from velometer import run as run_mod

    monkeypatch.setattr(
        run_mod,
        "run_history",
        lambda conn, city, years, **kw: [run_mod.RunOutcome(city.id, "failed", None, "boom")],
    )
    r = CliRunner().invoke(
        app,
        ["run", "--cities", "berlin", "--years", "2018-2019", "--db", str(tmp_path / "v.sqlite")],
    )
    assert r.exit_code == 1 and "boom" in r.output


def test_osm_fetch_history_prints_only_non_secret_fields(tmp_path, monkeypatch):
    from datetime import date

    from velometer import run as run_mod
    from velometer.sources.geofabrik import HistoryFile

    f = tmp_path / "h.osh.pbf"
    f.write_bytes(b"x" * 7)
    seen = []

    def fetch_history(region, data_dir, index, **kw):
        seen.append(region)
        return HistoryFile(region, f, "a" * 32, "published", date(2026, 10, 1))

    deps = run_mod.HistoryDeps(
        fetch_index=lambda d: type("S", (), {"path": tmp_path})(),
        load_index=lambda p: {"r/x": {"history": "http://h"}},
        fetch_history=fetch_history,
    )
    monkeypatch.setattr(run_mod, "HistoryDeps", lambda: deps)
    r = CliRunner().invoke(
        app, ["osm", "fetch-history", "--region", "r/x", "--data", str(tmp_path)]
    )
    assert r.exit_code == 0, r.output
    assert r.output.strip() == (f"region=r/x path={f} md5={'a' * 32} md5_source=published size=7")
    assert seen == ["r/x"]
    missing = CliRunner().invoke(app, ["osm", "fetch-history", "--region", "nope"])
    assert missing.exit_code == 2
    neither = CliRunner().invoke(app, ["osm", "fetch-history"])
    assert neither.exit_code == 2


def test_commands_on_a_v5_db_with_activity_rows_point_to_migrate(tmp_path):
    from tests.test_db import _make_v5_db_with_activity

    db = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(db, rows=2)
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    for args in (
        ["init"],
        ["results"],
        ["reconcile", "--report", str(report)],
        ["timeseries", "--report", str(report)],
    ):
        out = CliRunner().invoke(app, [*args, "--db", str(db)])
        assert out.exit_code == 1, (args, out.output)
        assert out.exception.__class__ is SystemExit, args
        assert "migrate --activity-sha" in out.output, args


def test_migrate_gives_a_v5_db_the_activity_sha(tmp_path):
    from tests.test_db import _make_v5_db_with_activity

    db = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(db, rows=2)
    out = CliRunner().invoke(app, ["migrate", "--activity-sha", "e" * 64, "--db", str(db)])
    assert out.exit_code == 0, out.output
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT DISTINCT activity_sha256 FROM activity").fetchall() == [
            ("e" * 64,)
        ]
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_migrate_without_activity_sha_on_empty_activity(tmp_path):
    from tests.test_db import _make_v5_db_with_activity

    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=0)
    r = CliRunner().invoke(app, ["migrate", "--db", str(path)])
    assert r.exit_code == 0, r.output
    assert f"schema v{SCHEMA_VERSION}" in r.output


def test_migrate_without_activity_sha_on_v5_rows_explains(tmp_path):
    from tests.test_db import _make_v5_db_with_activity

    path = tmp_path / "v5.sqlite"
    _make_v5_db_with_activity(path, rows=2)
    r = CliRunner().invoke(app, ["migrate", "--db", str(path)])
    assert r.exit_code == 1
    assert "--activity-sha" in r.output


def test_migrate_rejects_a_malformed_sha(tmp_path):
    db = tmp_path / "v5.sqlite"
    for bad in ("abc", "E" * 64, "g" * 64, "e" * 63):
        out = CliRunner().invoke(app, ["migrate", "--activity-sha", bad, "--db", str(db)])
        assert out.exit_code == 2, (bad, out.output)
    assert not db.exists()


def _report_cfg(tmp_path, classifier):
    """A config copy whose report.yaml names `classifier`."""
    import shutil

    from velometer.config import default_config_dir

    cfg = tmp_path / "cfg"
    shutil.copytree(default_config_dir(), cfg)
    rep = cfg / "report.yaml"
    rep.write_text(
        re.sub(r"report_classifier: \S+", f"report_classifier: {classifier}", rep.read_text())
    )
    return cfg


def _run_versions(db):
    with connect(db) as conn:
        return {r[0] for r in conn.execute("SELECT classifier_version FROM runs")}


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_run_defaults_to_the_report_classifier(tmp_path, monkeypatch, version):
    cfg = _report_cfg(tmp_path, version)
    _patched(monkeypatch, tmp_path)
    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--db", str(db), "--config-dir", str(cfg)]).exit_code == 0
    args = ["run", "--cities", "berlin", "--db", str(db), "--data", str(tmp_path)]
    out = runner.invoke(app, [*args, "--config-dir", str(cfg)])
    assert out.exit_code == 0, out.output
    assert _run_versions(db) == {version}
    other = "v2" if version == "v1" else "v1"
    out = runner.invoke(app, [*args, "--config-dir", str(cfg), "--classifier", other])
    assert out.exit_code == 0, out.output
    assert _run_versions(db) == {version, other}  # the explicit override still wins


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_results_and_reconcile_default_to_the_report_classifier(tmp_path, monkeypatch, version):
    other = "v2" if version == "v1" else "v1"
    cfg = _report_cfg(tmp_path, version)
    _patched(monkeypatch, tmp_path)
    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    assert runner.invoke(app, ["init", "--db", str(db), "--config-dir", str(cfg)]).exit_code == 0
    run = ["run", "--cities", "berlin", "--db", str(db), "--data", str(tmp_path)]
    run += ["--config-dir", str(cfg), "--classifier", version]
    assert runner.invoke(app, run).exit_code == 0
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    rargs = ["--db", str(db), "--config-dir", str(cfg)]
    rec = ["reconcile", "--city", "berlin", "--report", str(report), *rargs]
    res = runner.invoke(app, ["results", *rargs])
    assert re.search(r"^berlin\s", res.output, re.M), res.output
    assert "Provenance: run 1 " in runner.invoke(app, rec).output
    # report.yaml naming the other classifier: no run of it exists
    (cfg / "report.yaml").write_text(
        (cfg / "report.yaml")
        .read_text()
        .replace(f"report_classifier: {version}", f"report_classifier: {other}")
    )
    res = runner.invoke(app, ["results", *rargs])
    assert not re.search(r"^berlin\s", res.output, re.M), res.output
    assert "Provenance: run 1 " not in runner.invoke(app, rec).output
    # the explicit override still wins
    res = runner.invoke(app, ["results", *rargs, "--classifier", version])
    assert re.search(r"^berlin\s", res.output, re.M), res.output
    assert "Provenance: run 1 " in runner.invoke(app, [*rec, "--classifier", version]).output


def _only_de_trusted(report_db_with_trust):
    return report_db_with_trust(countries={"DE": {"status": "trusted", "basis": "t"}})


def test_reconcile_check_skips_untrusted_and_city_flag_refuses(report_db_with_trust, tmp_path):
    db, cfg = _only_de_trusted(report_db_with_trust)
    report = tmp_path / "r.md"
    report.write_text("<!-- reconcile:begin -->\n<!-- reconcile:end -->\n")
    base = ["--db", str(db), "--config-dir", str(cfg), "--report", str(report)]
    out = CliRunner().invoke(app, ["reconcile", *base])
    assert "paris" not in out.output
    refused = CliRunner().invoke(app, ["reconcile", "--city", "paris", *base])
    assert refused.exit_code == 2
    assert "paris is not trusted yet (country FR pending, see config/trust.yaml)" in refused.output
    ts = CliRunner().invoke(app, ["timeseries", "--city", "paris", *base[:4]])
    assert ts.exit_code == 2 and "not trusted yet" in ts.output
    csv = CliRunner().invoke(
        app, ["report", "csv", "--city", "paris", "--db", str(db), "--config-dir", str(cfg)]
    )
    assert csv.exit_code == 2 and "not trusted yet" in csv.output
    nope = CliRunner().invoke(app, ["reconcile", "--city", "atlantis", *base])
    assert nope.exit_code == 2 and "unknown city" in nope.output


@pytest.mark.parametrize("fr_status", ["pending", "trusted"])
def test_write_blocks_omit_the_cities_of_untrusted_countries(
    report_db_with_trust, tmp_path, fr_status
):
    # R7: reconcile --write and timeseries --write publish only trusted cities; with FR trusted
    # the same fixture shows paris, so its absence under "pending" is the trust filter's doing
    from tests.report_fixture import CLASSIFIER, PARIS
    from tests.test_run_history import _current_deps
    from velometer import reconcile as rc
    from velometer import run as R
    from velometer import timeseries as ts
    from velometer.db import open_db

    ok = {"status": "trusted", "basis": "t"}
    db, cfg = report_db_with_trust(countries={"DE": ok, "FR": {**ok, "status": fr_status}})
    with open_db(db) as conn:  # paris has history runs only: give it a current run too
        R.run_city(
            conn, PARIS, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER,
            deps=_current_deps(tmp_path),
        )  # fmt: skip
    base = ["--db", str(db), "--config-dir", str(cfg)]
    blocks = {}
    for cmd, mod in (("reconcile", rc), ("timeseries", ts)):
        report = tmp_path / f"{cmd}.md"
        report.write_text(f"{mod.BEGIN}\n{mod.END}\n")
        res = CliRunner().invoke(app, [cmd, *base, "--report", str(report), "--write"])
        assert res.exit_code == 0, res.output
        text = report.read_text()
        blocks[cmd] = text[text.index(mod.BEGIN) : text.index(mod.END)].lower()
    for cmd, block in blocks.items():
        assert "berlin" in block, cmd
        assert ("paris" in block) == (fr_status == "trusted"), (cmd, block)


def test_results_marks_untrusted(report_db_with_trust, tmp_path):
    from tests.report_fixture import CLASSIFIER, PARIS
    from tests.test_run_history import _current_deps
    from velometer import run as R
    from velometer.db import open_db

    db, cfg = _only_de_trusted(report_db_with_trust)
    with open_db(db) as conn:  # paris has history runs only: give it a current run too
        R.run_city(
            conn, PARIS, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER,
            deps=_current_deps(tmp_path),
        )  # fmt: skip
    out = CliRunner().invoke(app, ["results", "--db", str(db), "--config-dir", str(cfg)])
    assert out.exit_code == 0, out.output
    assert re.search(r"^berlin\s+\d{4}-", out.output, re.M), out.output
    paris = [ln for ln in out.output.splitlines() if ln.startswith("paris")]
    assert paris and "untrusted" in paris[0], out.output


def _subarea_cfg(tmp_path):
    import shutil

    import yaml

    cfg = tmp_path / "cfg"
    shutil.copytree(default_config_dir(), cfg)
    data = yaml.safe_load((cfg / "cities.yaml").read_text())
    berlin = next(c for c in data["cities"] if c["id"] == "berlin")
    berlin["subareas"] = {
        "source": "osm_admin",
        "admin_level": 9,
        "relations": [
            {"id": 9001, "name": "West", "slug": "west"},
            {"id": 9002, "name": "East", "slug": "east"},
        ],
    }
    (cfg / "cities.yaml").write_text(yaml.safe_dump(data))
    return cfg


def _write_geojson(path, geom_25833):
    import json

    import shapely

    from velometer.sources.boundaries import _to

    wgs = _to(geom_25833, 25833, 4326)
    feat = {"type": "Feature", "properties": {}, "geometry": json.loads(shapely.to_geojson(wgs))}
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [feat]}))


def _subarea_run(tmp_path, monkeypatch, east_right: float):
    from shapely.geometry import box

    from velometer import subareas as S

    cfg = _subarea_cfg(tmp_path)
    _patched(monkeypatch, tmp_path)
    (tmp_path / "boundaries").mkdir()
    x0, y0, side = 390_000.0, 5_820_000.0, 10_000.0
    _write_geojson(
        tmp_path / "boundaries" / "berlin_lau.geojson", box(x0, y0, x0 + side, y0 + side)
    )
    shapes = {
        9001: box(x0, y0, x0 + side / 2, y0 + side),
        9002: box(x0 + side / 2, y0, x0 + east_right, y0 + side),
    }

    def fake(src, relation_id, dst):
        _write_geojson(dst, shapes[relation_id])
        return dst

    monkeypatch.setattr(S, "relation_polygon", fake)
    db = tmp_path / "v.sqlite"
    out = CliRunner().invoke(
        app,
        ["boundaries", "fetch", "--city", "berlin", "--subareas", "--config-dir", str(cfg)]
        + ["--db", str(db), "--data", str(tmp_path)],
    )
    return out, db


def test_boundaries_fetch_subareas_stores_rows_and_prints_checks(tmp_path, monkeypatch):
    out, db = _subarea_run(tmp_path, monkeypatch, east_right=10_000.0)
    assert out.exit_code == 0, out.output
    assert "berlin west West relation=9001 area_km2=50.0" in out.output
    assert "berlin east East relation=9002 area_km2=50.0" in out.output
    assert "union_diff_pct=0.00 symdiff_pct=0.00 overlap_pct=0.000" in out.output
    rows = (
        sqlite3.connect(db)
        .execute("SELECT subarea_id, relation_id, source FROM subareas ORDER BY subarea_id")
        .fetchall()
    )
    assert rows == [("east", 9002, "OSM relation 9002"), ("west", 9001, "OSM relation 9001")]


def test_boundaries_fetch_subareas_that_leave_a_gap_exit_1_and_store_nothing(tmp_path, monkeypatch):
    out, db = _subarea_run(tmp_path, monkeypatch, east_right=9_800.0)
    assert out.exit_code == 1
    assert "union area differs from the LAU by 2.0 %" in out.output
    assert sqlite3.connect(db).execute("SELECT count(*) FROM subareas").fetchone() == (0,)


def test_boundaries_fetch_subareas_of_a_city_without_them_exits_1(tmp_path, monkeypatch):
    _patched(monkeypatch, tmp_path)
    out = CliRunner().invoke(
        app,
        ["boundaries", "fetch", "--city", "berlin", "--subareas"]
        + ["--db", str(tmp_path / "v.sqlite"), "--data", str(tmp_path)],
    )
    assert out.exit_code == 1
    assert "no subareas configured for berlin" in out.output


# --- subarea read surfaces (M6) ---


def _berlin_run_ids(db, kind="lau"):
    with sqlite3.connect(db) as conn:
        return [
            r[0]
            for r in conn.execute(
                "SELECT id FROM runs WHERE city_id='berlin' AND boundary_kind=? AND status='done'",
                (kind,),
            )
        ]


def test_results_subareas_prints_a_row_per_subarea(tmp_path):
    from tests.report_fixture import add_subareas, build_report_fixture

    db, cfg = build_report_fixture(tmp_path)
    add_subareas(db, cfg, _berlin_run_ids(db))
    out = CliRunner().invoke(
        app,
        ["results", "--city", "berlin", "--subareas", "--db", str(db), "--config-dir", str(cfg)],
    )
    assert out.exit_code == 0, out.output
    west = next(ln for ln in out.output.splitlines() if ln.startswith("West"))
    east = next(ln for ln in out.output.splitlines() if ln.startswith("East"))
    assert west.split()[1] == "4.0"  # (3 + 1) / 100 main_excl_motorway
    assert "A_km" in out.output and "a_of_ab_pct" in out.output
    assert west.split()[4:7] == ["3.0", "1.0", "0.0"] and west.split()[9] == "75.0"
    assert east.split()[4:6] == ["1.0", "3.0"] and east.split()[9] == "25.0"
    assert "per 100k: not available per subarea (no subarea population)" in out.output


def test_results_subareas_of_a_city_without_them_exits_1(tmp_path):
    from tests.report_fixture import build_report_fixture

    db, cfg = build_report_fixture(tmp_path)
    out = CliRunner().invoke(
        app,
        ["results", "--city", "berlin", "--subareas", "--db", str(db), "--config-dir", str(cfg)],
    )
    assert out.exit_code == 1
    assert "no subareas configured for berlin" in out.output


# --- report change ------------------------------------------------------------------------------

CHANGE_FIX = Path(__file__).parent / "fixtures" / "change"
needs_osmium = pytest.mark.skipif(
    __import__("shutil").which("osmium") is None, reason="osmium-tool not installed"
)


def _change_db(tmp_path):
    """berlin/lau: a 2024 history run on from.osm and a current run on to.osm (the M3 fakes),
    both snapshots placed where `snapshot_path_for_run` looks, and a config copy giving berlin
    two subareas (west/east) whose files sit in <data>/boundaries."""
    import json
    import shutil
    import subprocess

    import yaml

    from tests.report_fixture import CLASSIFIER
    from tests.test_run_history import CFG_DIR, CITY, Fakes, _current_deps
    from velometer import run as R
    from velometer.db import create_schema, fetch_run, open_db, upsert_cities

    db_path, data_dir = tmp_path / "v.sqlite", tmp_path / "data"
    fakes = Fakes(tmp_path)
    hdeps = fakes.deps(snapshot_at=lambda hist, ts, d: CHANGE_FIX / "from.osm")
    cur = _current_deps(tmp_path)
    cur = R.RunDeps(**{**cur.__dict__, "snapshot": lambda *a, **k: CHANGE_FIX / "to.osm"})
    with open_db(db_path) as conn:
        create_schema(conn)
        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        (h,) = R.run_history(conn, CITY, range(2024, 2025), data_dir=tmp_path,
                             config_dir=CFG_DIR, classifier=CLASSIFIER, deps=hdeps)  # fmt: skip
        c = R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR,
                       classifier=CLASSIFIER, deps=cur)  # fmt: skip
        assert (h.status, c.status) == ("done", "done")
        for run_id, src in ((h.run_id, "from.osm"), (c.run_id, "to.osm")):
            dst = R.run_snapshot_path(fetch_run(conn, run_id), data_dir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["osmium", "cat", str(CHANGE_FIX / src), "-o", str(dst)], check=True)

    def wgs_box(x0, y0, x1, y1):
        ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
        geom = {"type": "Polygon", "coordinates": [ring]}
        return {"type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": geom}]}  # fmt: skip

    # the run's boundary row points at tmp_path/b.geojson (the fakes); it holds every fixture way
    (tmp_path / "b.geojson").write_text(json.dumps(wgs_box(13.3, 52.45, 13.5, 52.55)))
    cfg = tmp_path / "config"
    shutil.copytree(CFG_DIR, cfg)
    doc = yaml.safe_load((cfg / "cities.yaml").read_text())
    berlin = next(x for x in doc["cities"] if x["id"] == "berlin")
    berlin["subareas"] = {
        "source": "osm_admin",
        "admin_level": 9,
        "relations": [
            {"id": 9_200_000_001, "name": "West", "slug": "west"},
            {"id": 9_200_000_002, "name": "East", "slug": "east"},
        ],
    }
    (cfg / "cities.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    (data_dir / "boundaries").mkdir(parents=True)
    for slug, (x0, x1) in (("west", (13.3, 13.4015)), ("east", (13.4015, 13.5))):
        path = data_dir / "boundaries" / f"berlin_sub_{slug}.geojson"
        path.write_text(json.dumps(wgs_box(x0, 52.45, x1, 52.55)))
    return db_path, cfg, data_dir, h.run_id, c.run_id


def _change_args(db_path, cfg, data_dir, out):
    return ["report", "change", "--city", "berlin", "--from", "2024-01-01", "--to", "current",
            "--out", str(out), "--data", str(data_dir), "--db", str(db_path),
            "--config-dir", str(cfg)]  # fmt: skip


@needs_osmium
def test_report_change_checks_totals_and_writes_md_geojson_png(tmp_path):
    db_path, cfg, data_dir, run_from, run_to = _change_db(tmp_path)
    out = tmp_path / "review"
    result = CliRunner().invoke(app, _change_args(db_path, cfg, data_dir, out))
    assert result.exit_code == 0, result.output
    assert f"run {run_from} -> run {run_to}: totals agree (A..E)" in result.output
    md = (out / "berlin_change_2024-01-01_current.md").read_text()
    assert "West" in md and "East" in md and "mapped km" in md
    assert (out / "berlin_change_2024-01-01_current.png").stat().st_size > 0
    assert (data_dir / "maps" / "berlin_change_2024-01-01_current.geojson").is_file()


@needs_osmium
def test_report_change_refuses_when_stored_totals_differ(tmp_path):
    db_path, cfg, data_dir, run_from, _ = _change_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.execute(
        "UPDATE tier_lengths SET length_km = length_km + 1 WHERE run_id=? AND tier='A' "
        "AND length_basis='per_side'",
        (run_from,),
    )
    c.commit()
    c.close()
    out = tmp_path / "review"
    result = CliRunner().invoke(app, _change_args(db_path, cfg, data_dir, out))
    assert result.exit_code == 1
    assert "tier A" in result.output
    assert not out.exists()
    assert not (data_dir / "maps").exists()


@needs_osmium
def test_report_change_refuses_a_boundary_other_than_the_runs(tmp_path):
    db_path, cfg, data_dir, *_ = _change_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.execute("UPDATE boundaries SET sha256=? WHERE city_id='berlin' AND kind='lau'", ("f" * 64,))
    c.commit()
    c.close()
    out = tmp_path / "review"
    result = CliRunner().invoke(app, _change_args(db_path, cfg, data_dir, out))
    assert result.exit_code == 1
    assert "refused:" in result.output
    assert "f" * 64 in result.output and "s" * 64 in result.output  # the row's and the runs' sha
    assert "totals agree" not in result.output
    assert not out.exists()


@needs_osmium
def test_report_change_without_a_run_at_the_date_fails(tmp_path):
    db_path, cfg, data_dir, *_ = _change_db(tmp_path)
    args = _change_args(db_path, cfg, data_dir, tmp_path / "review")
    args[args.index("2024-01-01")] = "2023-01-01"
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert "2023-01-01" in result.output
