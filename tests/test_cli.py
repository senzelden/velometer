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
