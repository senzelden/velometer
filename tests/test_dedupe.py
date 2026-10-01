from pathlib import Path

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.dedupe import flag_parallel_duplicates, pair_dual_carriageways
from velometer.pipeline.geometry import Projector
from velometer.pipeline.read import read_ways

FIX = Path(__file__).parent / "fixtures" / "dedupe"
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
PROJ = Projector(25833)
MAIN = set(CFG.road_classes.main) | set(CFG.road_classes.motorway)


def test_parallel_cycleway_next_to_tagged_track_is_flagged_not_removed():
    classified = classify_ways(read_ways(FIX / "parallel.osm").ways, CFG)
    flags = flag_parallel_duplicates(classified, PROJ)
    assert [(f.standalone_way_id, f.road_way_id, f.road_side) for f in flags] == [(11, 10, "right")]
    assert flags[0].overlap_share >= 0.8 and flags[0].distance_m < 15
    assert {c.side.way_id for c in classified} >= {10, 11, 12}  # nothing removed


def test_degenerate_geometry_does_not_crash():
    classified = classify_ways(read_ways(FIX / "parallel.osm").ways, CFG)
    flag_parallel_duplicates(classified, PROJ)  # way 13 has zero length


def test_dual_carriageway_by_pairing_and_by_tag():
    roads = read_ways(FIX / "dual.osm").ways
    factors, pairs = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors[20] == 0.5 and factors[21] == 0.5 and factors[24] == 0.5
    assert factors[22] == 1.0
    assert factors[23] == 0.5  # dual_carriageway=yes
    by_way = {p.way_id: set(p.partner_ids) for p in pairs}
    assert 24 not in by_way[20]  # same direction never pairs
    assert by_way[20] == {21}


def test_pairing_ignores_non_main_highways():
    roads = [
        w if w.id != 21 else type(w)(w.id, {**w.tags, "highway": "residential"}, w.coords)
        for w in read_ways(FIX / "dual.osm").ways
    ]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors[21] == 1.0
