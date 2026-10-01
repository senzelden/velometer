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
