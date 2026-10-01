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
