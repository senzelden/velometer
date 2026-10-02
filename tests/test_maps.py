import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from velometer.db import fetch_run
from velometer.pipeline.extract import snapshot_name
from velometer.report import maps

MINI = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"
needs_osmium = pytest.mark.skipif(
    shutil.which("osmium") is None, reason="osmium-tool not installed"
)


def _row(conn, data, city="berlin", kind="lau"):
    return fetch_run(conn, data.current(city, kind).run_id)


def _place_snapshot(conn, data, data_dir, boundary_dir):
    """The mini city as the current run's snapshot, plus the boundary file its row points at."""
    row = _row(conn, data)
    dst = maps.snapshot_path(row, data_dir)
    dst.parent.mkdir(parents=True)
    subprocess.run(["osmium", "cat", str(MINI), "-o", str(dst)], check=True)
    ring = [[13.39, 52.49], [13.43, 52.49], [13.43, 52.57], [13.39, 52.57], [13.39, 52.49]]
    poly = {"type": "Polygon", "coordinates": [ring]}
    feature = {"type": "Feature", "properties": {}, "geometry": poly}
    Path(
        conn.execute(
            "SELECT path FROM boundaries WHERE city_id='berlin' AND kind='lau'"
        ).fetchone()[0]
    ).write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
    return dst


@pytest.fixture
def placed(fixture_db, tmp_path):
    _, _, conn, data = fixture_db
    data_dir = tmp_path / "data"
    return conn, data, data_dir, tmp_path / "maps"


@needs_osmium
def test_build_map_writes_png_and_run_marker(placed, tmp_path):
    conn, data, data_dir, maps_dir = placed
    _place_snapshot(conn, data, data_dir, tmp_path)
    out = maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    assert out == maps_dir / "berlin_lau.png"
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert (maps_dir / "berlin_lau.run").read_text().strip() == str(
        data.current("berlin", "lau").run_id
    )


@needs_osmium
def test_build_map_skips_when_run_unchanged(placed, tmp_path, monkeypatch):
    conn, data, data_dir, maps_dir = placed
    _place_snapshot(conn, data, data_dir, tmp_path)
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    saves = []
    monkeypatch.setattr(maps.plt, "savefig", lambda *a, **k: saves.append(a))
    assert maps.build_map(data, "berlin", "lau", data_dir, maps_dir) == maps_dir / "berlin_lau.png"
    assert saves == []


@needs_osmium
def test_build_map_rebuilds_when_run_changes(placed, tmp_path):
    conn, data, data_dir, maps_dir = placed
    _place_snapshot(conn, data, data_dir, tmp_path)
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    (maps_dir / "berlin_lau.run").write_text("0")  # an older run's marker
    png = maps_dir / "berlin_lau.png"
    png.write_bytes(b"stale")
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    assert png.read_bytes()[:4] == b"\x89PNG"
    assert (maps_dir / "berlin_lau.run").read_text().strip() == str(
        data.current("berlin", "lau").run_id
    )


def test_build_map_returns_none_without_snapshot(placed):
    _, data, data_dir, maps_dir = placed
    assert maps.build_map(data, "berlin", "lau", data_dir, maps_dir) is None
    assert not maps_dir.exists() or not list(maps_dir.iterdir())


def test_build_map_returns_none_without_current_run(placed):
    _, data, data_dir, maps_dir = placed
    assert maps.build_map(data, "paris", "lau", data_dir, maps_dir) is None


def test_snapshot_name_is_shared_with_extract(placed):
    conn, data, data_dir, _ = placed
    row = _row(conn, data)
    ts = datetime.fromisoformat(row["osm_timestamp"]).astimezone(UTC)
    name = snapshot_name(row["city_id"], row["boundary_kind"], ts, row["region_md5"],
                         row["boundary_sha256"])  # fmt: skip
    assert maps.snapshot_path(row, data_dir) == data_dir / "snapshots" / name
    assert name == (
        f"berlin_lau_{ts:%Y%m%d}_{row['region_md5'][:8]}_{row['boundary_sha256'][:8]}.osm.pbf"
    )


@needs_osmium
def test_map_draws_only_tiered_sides(placed, tmp_path):
    conn, data, data_dir, _ = placed
    dst = _place_snapshot(conn, data, data_dir, tmp_path)
    sides = maps.tier_sides(dst, data.config_dir, data.selector.version, 25833)
    assert sides, "mini city has tiered sides"
    assert set(sides) <= set("ABCDE")
    assert all(not line.is_empty and line.bounds[0] > 1e5 for ls in sides.values() for line in ls)


@needs_osmium
def test_cli_report_maps_prints_one_line_per_map(fixture_db, tmp_path):
    from typer.testing import CliRunner

    from velometer.cli import app

    db_path, cfg, conn, data = fixture_db
    data_dir = tmp_path / "data"
    _place_snapshot(conn, data, data_dir, tmp_path)
    args = [
        "report",
        "maps",
        "--data",
        str(data_dir),
        "--db",
        str(db_path),
        "--config-dir",
        str(cfg),
    ]
    first = CliRunner().invoke(app, args)
    assert first.exit_code == 0, first.output
    out = first.output
    assert f"written: {data_dir / 'maps' / 'berlin_lau.png'}" in out
    assert "skipped: berlin fua (no snapshot)" in out
    assert "skipped: paris lau (no run)" in out
    again = CliRunner().invoke(app, args).output
    assert f"unchanged: {data_dir / 'maps' / 'berlin_lau.png'}" in again
    only = CliRunner().invoke(app, [*args, "--city", "paris", "--kind", "lau"]).output
    assert only.strip() == "skipped: paris lau (no run)"


def test_tier_sides_omits_excluded_and_untiered(fixture_db, monkeypatch):
    from types import SimpleNamespace

    from velometer.pipeline.types import Classified, WaySide

    _, cfg, _, _ = fixture_db
    coords = ((13.40, 52.50), (13.41, 52.50))

    def classified(tier):
        side = WaySide(1, "self", "standalone", {}, coords)
        return Classified(side, tier, None, None, {})

    monkeypatch.setattr(maps, "read_ways", lambda p: SimpleNamespace(ways=[]))
    monkeypatch.setattr(
        maps, "classify_ways", lambda ways, cfg: [classified(t) for t in ("A", "excluded", None)]
    )
    assert {t: len(v) for t, v in maps.tier_sides(Path("x"), cfg, "v2", 25833).items()} == {"A": 1}
