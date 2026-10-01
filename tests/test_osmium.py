import json
import shutil
from datetime import UTC, datetime

import osmium as pyosmium
import pytest

from velometer.osmium import OsmiumError, extract, fileinfo_timestamp, relation_polygon
from velometer.pipeline.extract import snapshot
from velometer.pipeline.read import read_ways

needs_osmium = pytest.mark.skipif(
    shutil.which("osmium") is None, reason="osmium-tool not installed"
)
TS = "2026-09-30T20:22:42Z"


def _pbf(path):
    """Two ways: way 1 inside lon 13.40-13.41, way 2 at lon 13.50-13.51."""
    header = pyosmium.io.Header()
    header.set("osmosis_replication_timestamp", TS)
    with pyosmium.SimpleWriter(str(path), header=header) as w:
        for nid, lon in ((1, 13.40), (2, 13.41), (3, 13.50), (4, 13.51)):
            w.add_node(pyosmium.osm.mutable.Node(id=nid, location=(lon, 52.5), version=1))
        for wid, nodes in ((1, [1, 2]), (2, [3, 4])):
            w.add_way(
                pyosmium.osm.mutable.Way(
                    id=wid, nodes=nodes, tags={"highway": "cycleway"}, version=1
                )
            )
    return path


def _poly(path):
    ring = [[13.39, 52.49], [13.42, 52.49], [13.42, 52.51], [13.39, 52.51], [13.39, 52.49]]
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {"type": "Polygon", "coordinates": [ring]},
                    }
                ],
            }
        )
    )
    return path


@needs_osmium
def test_fileinfo_timestamp_reads_header(tmp_path):
    assert fileinfo_timestamp(_pbf(tmp_path / "r.osm.pbf")) == datetime(
        2026, 9, 30, 20, 22, 42, tzinfo=UTC
    )


@needs_osmium
def test_extract_keeps_only_ways_inside(tmp_path):
    out = extract(
        _pbf(tmp_path / "r.osm.pbf"), _poly(tmp_path / "b.geojson"), tmp_path / "o.osm.pbf"
    )
    assert [w.id for w in read_ways(out).ways] == [1]


@needs_osmium
def test_snapshot_is_cached_by_region_and_boundary(tmp_path):
    src, poly = _pbf(tmp_path / "r.osm.pbf"), _poly(tmp_path / "b.geojson")
    ts = datetime(2026, 9, 30, tzinfo=UTC)
    a = snapshot(src, "md5aaaaaaaa", ts, "berlin", "lau", poly, "sha1111111", tmp_path)
    mtime = a.stat().st_mtime_ns
    b = snapshot(src, "md5aaaaaaaa", ts, "berlin", "lau", poly, "sha1111111", tmp_path)
    assert a == b and b.stat().st_mtime_ns == mtime
    assert [w.id for w in read_ways(a).ways] == [1]
    c = snapshot(src, "md5aaaaaaaa", ts, "berlin", "lau", poly, "sha2222222", tmp_path)
    assert c != a
    assert not list((tmp_path / "snapshots").glob("*.part*"))


@needs_osmium
def test_osmium_failure_raises_with_stderr(tmp_path):
    with pytest.raises(OsmiumError, match="osmium"):
        extract(tmp_path / "missing.osm.pbf", _poly(tmp_path / "b.geojson"), tmp_path / "o.osm.pbf")


@needs_osmium
def test_relation_polygon_writes_only_areas(tmp_path):
    # a closed boundary relation around way 1's square
    path = tmp_path / "rel.osm.pbf"
    with pyosmium.SimpleWriter(str(path)) as w:
        pts = [(10, 13.39, 52.49), (11, 13.42, 52.49), (12, 13.42, 52.51), (13, 13.39, 52.51)]
        for nid, lon, lat in pts:
            w.add_node(pyosmium.osm.mutable.Node(id=nid, location=(lon, lat), version=1))
        w.add_way(pyosmium.osm.mutable.Way(id=20, nodes=[10, 11, 12, 13, 10], version=1))
        w.add_relation(
            pyosmium.osm.mutable.Relation(
                id=30,
                members=[("w", 20, "outer")],
                tags={"type": "boundary", "boundary": "administrative"},
                version=1,
            )
        )
    out = relation_polygon(path, 30, tmp_path / "rel.geojson")
    feats = json.loads(out.read_text())["features"]
    assert feats and {f["geometry"]["type"] for f in feats} <= {"Polygon", "MultiPolygon"}


@needs_osmium
def test_fileinfo_timestamp_none_without_header_option(tmp_path):
    path = tmp_path / "plain.osm.pbf"
    with pyosmium.SimpleWriter(str(path)) as w:
        w.add_node(pyosmium.osm.mutable.Node(id=1, location=(13.4, 52.5), version=1))
    assert fileinfo_timestamp(path) is None


@needs_osmium
def test_relation_polygon_failure_leaves_no_stray_files(tmp_path):
    path = tmp_path / "open.osm.pbf"
    with pyosmium.SimpleWriter(str(path)) as w:
        for nid, lon, lat in [(10, 13.39, 52.49), (11, 13.42, 52.49), (12, 13.42, 52.51)]:
            w.add_node(pyosmium.osm.mutable.Node(id=nid, location=(lon, lat), version=1))
        w.add_way(pyosmium.osm.mutable.Way(id=20, nodes=[10, 11, 12], version=1))
        w.add_relation(
            pyosmium.osm.mutable.Relation(
                id=30,
                members=[("w", 20, "outer")],
                tags={"type": "boundary", "boundary": "administrative"},
                version=1,
            )
        )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with pytest.raises(OsmiumError, match="did not assemble"):
        relation_polygon(path, 30, out_dir / "rel.geojson")
    assert list(out_dir.iterdir()) == []
