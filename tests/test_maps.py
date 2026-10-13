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
LABELS = {t: f"{t} label" for t in "ABCDE"}
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


def test_legend_and_footer_stay_inside_the_figure(tmp_path, monkeypatch):
    # the legend sat right of the axes and its longest label ran off the PNG's right edge
    from shapely.geometry import LineString

    figs = []
    monkeypatch.setattr(maps.plt, "close", figs.append)
    sides = {t: [LineString([(0, 0), (1000, 1000)])] for t in maps.TIERS}
    maps._draw(
        sides, None, "Berlin (LAU): protected cycling tiers", "footer", tmp_path / "m.png", LABELS
    )
    (fig,) = figs
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = fig.bbox
    legend = fig.axes[0].get_legend().get_window_extent(renderer)
    assert box.x0 <= legend.x0 and legend.x1 <= box.x1 and legend.y1 <= box.y1
    for text in fig.texts:
        ext = text.get_window_extent(renderer)
        assert box.x0 <= ext.x0 and ext.x1 <= box.x1


def test_outline_draws_interior_rings(tmp_path, monkeypatch):
    # a city boundary with an enclave (København around Frederiksberg) must show the hole's
    # edge, or the enclave reads as part of the city with no infrastructure in it
    from shapely.geometry import Polygon

    figs = []
    monkeypatch.setattr(maps.plt, "close", figs.append)
    hole = [(4, 4), (6, 4), (6, 6), (4, 6)]
    outline = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [hole])
    maps._draw({}, outline, "title", "footer", tmp_path / "m.png", LABELS)
    (fig,) = figs
    drawn = [set(zip(*line.get_data(), strict=True)) for line in fig.axes[0].get_lines()]
    assert any({(float(x), float(y)) for x, y in hole} <= d for d in drawn)


def test_map_footer_carries_odbl_and_mapped_km(placed, monkeypatch):
    """Every chart, the tier map included, says OSM mapped km, not built km (ADR 0006)."""
    conn, data, data_dir, maps_dir = placed
    snap = maps.snapshot_path(_row(conn, data), data_dir)
    snap.parent.mkdir(parents=True)
    snap.write_bytes(b"")  # never read: the classification is stubbed
    monkeypatch.setattr(maps, "tiered", lambda *a, **k: ([], {}))
    drawn = []
    monkeypatch.setattr(
        maps, "_draw", lambda sides, outline, title, footer, out, labels: drawn.append(footer)
    )
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    assert len(drawn) == 1
    assert "© OpenStreetMap contributors, ODbL 1.0" in drawn[0]
    assert "OSM mapped km, not built km" in drawn[0]


def test_map_texts_english_are_the_constants_and_german_is_german(fixture_db):
    from velometer.report.charts import TIER_LABEL

    _, _, _, data = fixture_db
    point = data.current("berlin", "lau")
    title, footer, labels = maps.map_texts(point, "Berlin", "lau", "en")
    assert title == "Berlin (LAU): protected cycling tiers" and labels == TIER_LABEL
    assert footer == (f"{maps.ODBL} · {maps.MAPPED_KM}\nOSM {point.osm_timestamp}, "
                      f"classifier {point.classifier_version}")  # fmt: skip
    title, footer, labels = maps.map_texts(point, "Krakau", "lau", "de")
    assert title.startswith("Krakau (LAU): ") and labels["A"] == "A baulich getrennter Radweg"
    assert footer == (
        "Kartendaten © OpenStreetMap-Mitwirkende, ODbL 1.0 · kartierte km, nicht gebaute km\n"
        f"OSM-Stand {point.osm_timestamp}, Klassifikator {point.classifier_version}"
    )


@needs_osmium
def test_german_map_is_its_own_file_and_leaves_the_english_alone(placed, tmp_path):
    conn, data, data_dir, maps_dir = placed
    _place_snapshot(conn, data, data_dir, tmp_path)
    run_id = data.current("berlin", "lau").run_id
    en = maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    geojson = maps_dir / "berlin_lau.geojson"
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (en, geojson)}
    assert not maps.up_to_date(maps_dir, "berlin", "lau", run_id, "de")
    de = maps.build_map(data, "berlin", "lau", data_dir, maps_dir, "de")
    assert de == maps_dir / "berlin_lau.de.png" and de.read_bytes()[:4] == b"\x89PNG"
    assert de.read_bytes() != en.read_bytes()
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (en, geojson)} == before
    assert maps.up_to_date(maps_dir, "berlin", "lau", run_id, "de")
    assert maps.up_to_date(maps_dir, "berlin", "lau", run_id, "en")


def test_german_map_writes_only_its_png_and_marker(placed, monkeypatch):
    conn, data, data_dir, maps_dir = placed
    snap = maps.snapshot_path(_row(conn, data), data_dir)
    snap.parent.mkdir(parents=True)
    snap.write_bytes(b"")  # never read: the classification is stubbed
    monkeypatch.setattr(maps, "tiered", lambda *a, **k: ([], {}))
    drawn = []

    def draw(sides, outline, title, footer, out, labels):
        drawn.append((title, footer, labels, out))
        out.write_bytes(b"png")

    monkeypatch.setattr(maps, "_draw", draw)
    run_id = data.current("berlin", "lau").run_id
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir, "de")
    assert sorted(p.name for p in maps_dir.iterdir()) == ["berlin_lau.de.png", "berlin_lau.de.run"]
    ((title, footer, labels, out),) = drawn
    assert out.name == "berlin_lau.de.png" and "Kartendaten" in footer
    assert labels["A"] == "A baulich getrennter Radweg" and "protected" not in title
    assert maps.up_to_date(maps_dir, "berlin", "lau", run_id, "de")
    assert not maps.up_to_date(maps_dir, "berlin", "lau", run_id, "en")


# --- GeoJSON for the interactive map -----------------------------------------------------------


def _side(way_id, tier, side="right", coords=((13.123456789, 52.5), (13.13, 52.5000049))):
    from velometer.pipeline.types import Classified, WaySide

    ws = WaySide(way_id, side, "road_side", {"cycleway:right": "track"}, coords)
    return Classified(ws, tier, "sub" if tier else None, f"R{way_id}" if tier else None, {})


WAY_TAGS = {
    "highway": "primary",
    "cycleway": "track",
    "cycleway:right": "track",
    "cycleway:left:width": "2",
    "sidewalk:bicycle": "yes",
    "sidewalk:left:bicycle": "designated",
    "bicycle": "use_sidepath",
    "foot": "yes",
    "segregated": "yes",
    "oneway": "yes",
    "oneway:bicycle": "no",
    "bicycle_road": "yes",
    "cyclestreet": "yes",
    # not in the subset
    "name": "Unter den Linden",
    "surface": "asphalt",
    "maxspeed": "50",
    "sidewalk": "both",
    "sidewalk:left:surface": "paving_stones",
    "road:highway": "primary",
}
KEPT = set(WAY_TAGS) - {
    "name", "surface", "maxspeed", "sidewalk", "sidewalk:left:surface", "road:highway",
}  # fmt: skip


def test_side_features_only_tiers_rounded_with_listed_properties():
    from velometer.pipeline.geometry import Projector

    classified = [_side(1, t) for t in ("A", "B", "C", "D", "E")]
    classified += [_side(2, "excluded"), _side(3, None)]
    feats = maps.side_features(classified, {1: WAY_TAGS}, Projector(25833), None)
    assert [f["properties"]["tier"] for f in feats] == list("ABCDE")
    f = feats[0]
    assert f["type"] == "Feature" and f["geometry"]["type"] == "LineString"
    assert f["geometry"]["coordinates"] == [[13.12346, 52.5], [13.13, 52.5]]
    assert set(f["properties"]) == {"way_id", "side", "tier", "subtype", "rule_id", "km", "tags"}
    assert f["properties"]["way_id"] == 1 and f["properties"]["side"] == "right"
    assert f["properties"]["subtype"] == "sub" and f["properties"]["rule_id"] == "R1"
    assert set(f["properties"]["tags"]) == KEPT


def test_side_features_km_is_projected_and_clipped_like_measure():
    from shapely.geometry import box
    from shapely.prepared import prep

    from velometer.pipeline.geometry import Projector, length_km
    from velometer.pipeline.measure import clipped_length_km

    proj = Projector(25833)
    coords = ((13.40, 52.50), (13.43, 52.52))
    line = proj.line(coords)
    whole = maps.side_features([_side(1, "A", coords=coords)], {}, proj, None)
    assert whole[0]["properties"]["km"] == round(length_km(line), 3)
    x0, y0, x1, y1 = line.bounds
    half = box(x0 - 10, y0 - 10, (x0 + x1) / 2, y1 + 10)
    clipped = maps.side_features([_side(1, "A", coords=coords)], {}, proj, half)
    expected = round(clipped_length_km(line, prep(half), half), 3)
    assert clipped[0]["properties"]["km"] == expected
    assert 0 < expected < whole[0]["properties"]["km"]


def _decimals(x: float) -> int:
    s = repr(x)
    return len(s.split(".")[1]) if "." in s else 0


@needs_osmium
def test_geojson_matches_the_run_measure_on_mini_city(placed, tmp_path):
    from velometer.config import load_classifier
    from velometer.pipeline.measure import measure
    from velometer.pipeline.read import read_ways
    from velometer.sources.boundaries import load_boundary_polygon

    conn, data, data_dir, maps_dir = placed
    snap = _place_snapshot(conn, data, data_dir, tmp_path)
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    fc = json.loads((maps_dir / "berlin_lau.geojson").read_text())
    point = data.current("berlin", "lau")
    assert fc["type"] == "FeatureCollection"
    assert fc["properties"] == {
        "run_id": point.run_id,
        "osm_timestamp": point.osm_timestamp,
        "classifier": point.classifier_version,
    }
    assert fc["boundary"]["type"] == "Feature"
    assert fc["boundary"]["geometry"]["type"] in ("Polygon", "MultiPolygon")
    feats = fc["features"]
    assert feats and {f["properties"]["tier"] for f in feats} <= set("ABCDE")
    for f in feats:
        assert all(_decimals(v) <= 5 for xy in f["geometry"]["coordinates"] for v in xy)
    cfg = load_classifier(data.config_dir / "classifier" / f"{point.classifier_version}.yaml")
    boundary_path = conn.execute(
        "SELECT path FROM boundaries WHERE city_id='berlin' AND kind='lau'"
    ).fetchone()[0]
    outline = load_boundary_polygon(Path(boundary_path), 25833)
    text = (maps_dir / "berlin_lau.geojson").read_text()
    for key in ("user", "uid", "changeset", "timestamp", "version"):  # no OSM editor metadata
        assert f'"{key}":' not in text, key
    ways = read_ways(snap).ways
    lengths = measure(ways, cfg, 25833, boundary=outline).way_lengths
    tags = {w.id: w.tags for w in ways}
    for f in feats:
        p = f["properties"]
        assert p["km"] == round(lengths[p["way_id"]], 3)
        assert p["tags"] == {k: v for k, v in tags[p["way_id"]].items() if maps.keep_tag(k)}


@needs_osmium
def test_build_map_classifies_once_for_png_and_geojson(placed, tmp_path, monkeypatch):
    conn, data, data_dir, maps_dir = placed
    _place_snapshot(conn, data, data_dir, tmp_path)
    calls = []
    real = maps.classify_ways
    monkeypatch.setattr(maps, "classify_ways", lambda *a, **k: calls.append(1) or real(*a, **k))
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    assert calls == [1]
    assert (maps_dir / "berlin_lau.png").is_file() and (maps_dir / "berlin_lau.geojson").is_file()


@needs_osmium
def test_missing_geojson_with_matching_marker_rebuilds(placed, tmp_path):
    conn, data, data_dir, maps_dir = placed
    _place_snapshot(conn, data, data_dir, tmp_path)
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    run_id = data.current("berlin", "lau").run_id
    assert maps.up_to_date(maps_dir, "berlin", "lau", run_id)
    (maps_dir / "berlin_lau.geojson").unlink()
    assert not maps.up_to_date(maps_dir, "berlin", "lau", run_id)
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    assert json.loads((maps_dir / "berlin_lau.geojson").read_text())["features"]


@needs_osmium
def test_matching_marker_leaves_geojson_alone(placed, tmp_path, monkeypatch):
    conn, data, data_dir, maps_dir = placed
    _place_snapshot(conn, data, data_dir, tmp_path)
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    writes = []
    monkeypatch.setattr(maps, "write_atomic", lambda *a: writes.append(a))
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    assert writes == []


def test_write_atomic_keeps_the_old_file_when_the_write_fails(tmp_path, monkeypatch):
    path = tmp_path / "berlin_lau.geojson"
    path.write_text("old")

    def fail(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(maps.os, "replace", fail)
    with pytest.raises(OSError):
        maps.write_atomic(path, b"new")
    assert path.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["berlin_lau.geojson"]
    monkeypatch.undo()
    maps.write_atomic(path, b"new")
    assert path.read_text() == "new"


def test_tiered_keeps_tags_of_tiered_ways_only(monkeypatch):
    # memory: a FUA snapshot has ~10x more ways than tiered sides; their tags must not be kept
    from types import SimpleNamespace

    from velometer.pipeline.types import WayRecord

    coords = ((13.40, 52.50), (13.41, 52.50))
    ways = [WayRecord(i, {"highway": "primary", "name": f"w{i}"}, coords) for i in (1, 2, 3)]
    tiers = {1: "A", 2: "excluded", 3: None}
    monkeypatch.setattr(maps, "load_classifier", lambda p: None)
    monkeypatch.setattr(maps, "read_ways", lambda p: SimpleNamespace(ways=ways))
    monkeypatch.setattr(
        maps, "classify_ways", lambda ws, cfg: [_side(w.id, tiers[w.id]) for w in ws]
    )
    sides, tags = maps.tiered(Path("x"), Path("cfg"), "v2")
    assert [c.side.way_id for c in sides] == [1]
    assert tags == {1: {"highway": "primary"}}  # only the kept subset of the tiered way


def test_a_way_crossing_the_boundary_is_drawn_only_inside():
    from shapely.geometry import LineString, box

    boundary = box(13.40, 52.52, 13.41, 52.53)
    line = LineString([(13.405, 52.525), (13.42, 52.525)])
    clipped = maps.clip_feature(line, boundary)
    assert clipped is not None
    assert clipped.bounds[2] <= 13.41 + 1e-9
    assert maps.clip_feature(LineString([(13.5, 52.6), (13.6, 52.6)]), boundary) is None


def test_geojson_geometry_is_clipped_and_a_side_outside_is_dropped():
    from shapely.geometry import box

    from velometer.pipeline.geometry import Projector

    proj = Projector(25833)
    boundary = box(13.40, 52.50, 13.41, 52.51)
    crossing = _side(1, "A", coords=((13.405, 52.505), (13.42, 52.505)))
    outside = _side(2, "A", coords=((13.50, 52.60), (13.51, 52.60)))
    feats = maps.side_features([crossing, outside], {}, proj, None, boundary)
    assert [f["properties"]["way_id"] for f in feats] == [1]
    xs = [x for x, _ in feats[0]["geometry"]["coordinates"]]
    assert max(xs) <= 13.41 + 1e-9


def test_drawn_and_counted_tier_a_km_agree_on_the_measure_fixture():
    from shapely.geometry import box

    from velometer.config import default_config_dir, load_classifier
    from velometer.pipeline.geometry import Projector, length_km
    from velometer.pipeline.measure import measure
    from velometer.pipeline.read import read_ways

    cfg_dir = default_config_dir()
    ways = read_ways(MINI).ways
    proj = Projector(25833)
    cfg = load_classifier(cfg_dir / "classifier" / "v1.yaml")
    sides, _ = maps.tiered(MINI, cfg_dir, "v1")
    x0, y0, x1, y1 = [
        f(g.bounds[i] for g in maps._by_tier(sides, proj)["A"])
        for i, f in ((0, min), (1, min), (2, max), (3, max))
    ]
    # a boundary that cuts through the tier-A ways: drawn and counted both lose the outer part
    outline = box(x0 - 10, y0 - 10, (x0 + x1) / 2, y1 + 10)
    counted = measure(ways, cfg, 25833, boundary=outline)
    counted_a = sum(
        t.length_km for t in counted.tier_lengths if t.tier == "A" and t.length_basis == "per_side"
    )
    drawn_a = sum(length_km(g) for g in maps._by_tier(sides, proj, outline)["A"])
    whole_a = sum(length_km(g) for g in maps._by_tier(sides, proj)["A"])
    assert 0 < counted_a < whole_a
    assert drawn_a == pytest.approx(counted_a, rel=1e-6)


def test_map_name_accepts_the_german_image_only():
    from velometer.app.main import MAP_NAME

    assert MAP_NAME.fullmatch("berlin_lau") and MAP_NAME.fullmatch("berlin_lau.de")
    assert not MAP_NAME.fullmatch("berlin_lau.fr") and not MAP_NAME.fullmatch("berlin_lau.de.de")
