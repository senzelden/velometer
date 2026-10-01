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


def test_classify_prints_tiers_roads_and_presets():
    fixture = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"
    result = CliRunner().invoke(app, ["classify", "--file", str(fixture), "--epsg", "25833"])
    assert result.exit_code == 0, result.output
    for needle in ("A", "main_excl_motorway", "ours_headline", "skipped ways: 0"):
        assert needle in result.output
