from pathlib import Path

from velometer.pipeline.read import read_ways

FIX = Path(__file__).parent / "fixtures"


def test_reads_tags_and_lonlat_coords():
    res = read_ways(FIX / "read_missing_node.osm")
    way = next(w for w in res.ways if w.id == 100)
    assert dict(way.tags) == {"highway": "cycleway"}
    assert way.coords == ((13.4, 52.5), (13.41, 52.5), (13.42, 52.5))


def test_unresolvable_ways_are_skipped_and_reported_not_raised():
    res = read_ways(FIX / "read_missing_node.osm")
    assert res.skipped == [101]
    # 102 keeps its 2 resolvable nodes; partial ways are kept, dropped nodes don't crash
    assert [w.coords for w in res.ways if w.id == 102] == [((13.41, 52.5), (13.42, 52.5))]


def test_untagged_ways_are_ignored():
    res = read_ways(FIX / "read_missing_node.osm")
    assert 103 not in {w.id for w in res.ways}


def test_only_highway_ways_are_read(tmp_path):
    osm = tmp_path / "x.osm"
    osm.write_text(
        '<?xml version="1.0"?><osm version="0.6">'
        '<node id="1" lat="52.5" lon="13.4"/><node id="2" lat="52.5" lon="13.41"/>'
        '<way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="cycleway"/></way>'
        '<way id="2"><nd ref="1"/><nd ref="2"/><tag k="building" v="yes"/></way>'
        "</osm>"
    )
    assert [w.id for w in read_ways(osm).ways] == [1]
