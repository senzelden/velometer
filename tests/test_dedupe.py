import math
from dataclasses import replace
from pathlib import Path

import pytest

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.dedupe import flag_parallel_duplicates, pair_dual_carriageways
from velometer.pipeline.geometry import Projector
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

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
    flags = flag_parallel_duplicates(classified, PROJ)  # way 13 has zero length
    assert 13 in {c.side.way_id for c in classified}
    assert all(13 not in (f.standalone_way_id, f.road_way_id) for f in flags)


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
        w if w.id != 21 else replace(w, tags={**w.tags, "highway": "residential"})
        for w in read_ways(FIX / "dual.osm").ways
    ]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors[21] == 1.0


LAT0, LON0 = 52.5, 13.4
M_LAT = 111320.0
M_LON = 111320.0 * math.cos(math.radians(LAT0))


def _ll(east_m: float, north_m: float) -> tuple[float, float]:
    return (LON0 + east_m / M_LON, LAT0 + north_m / M_LAT)


def _arc(radius: float, a0: float, a1: float, step: float = 5.0):
    n = max(int(abs(a1 - a0) / step), 1)
    angles = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
    return tuple(
        _ll(radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a))) for a in angles
    )


def _way(wid: int, coords, **tags) -> WayRecord:
    return WayRecord(wid, {"highway": "primary", "oneway": "yes", "name": "X", **tags}, coords)


def _line(east0: float, east1: float, north: float):
    return (_ll(east0, north), _ll(east1, north))


def test_curved_dual_carriageway_with_split_opposite_halves_pairs():
    roads = [
        _way(1, _arc(300, 0, 150)),
        _way(2, _arc(325, 75, 0)),
        _way(3, _arc(325, 150, 75)),
    ]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors == {1: 0.5, 2: 0.5, 3: 0.5}


def test_long_way_against_three_short_opposite_pieces():
    roads = [_way(1, _line(0, 900, 0))] + [
        _way(2 + i, _line(300 * (i + 1), 300 * i, 28)) for i in range(3)
    ]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert set(factors.values()) == {0.5}


def test_oneway_minus_one_drawn_same_direction_is_opposite():
    roads = [_way(1, _line(0, 900, 0)), _way(2, _line(0, 900, 28), oneway="-1")]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors == {1: 0.5, 2: 0.5}


def test_closed_loop_is_not_halved_without_partner():
    roads = [_way(1, _arc(100, 0, 360))]
    factors, pairs = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors == {1: 1.0} and pairs == []


def test_multi_value_ref_pairs_with_single_ref():
    roads = [
        _way(1, _line(0, 900, 0), name="", ref="B 1;B 5"),
        _way(2, _line(900, 0, 28), name="", ref="B 1"),
    ]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors == {1: 0.5, 2: 0.5}


def test_multi_value_dual_carriageway_tag():
    roads = [_way(1, _line(0, 900, 0), name="", dual_carriageway="yes;no", oneway="no")]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors[1] == 0.5


def test_degenerate_way_next_to_real_pair_does_not_crash():
    p = _ll(450, 14)
    roads = [
        _way(1, _line(0, 900, 0)),
        _way(2, _line(900, 0, 28)),
        _way(3, (p, p)),
    ]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors == {1: 0.5, 2: 0.5, 3: 1.0}


def test_same_named_opposite_oneway_far_away_is_not_a_partner():
    roads = [
        _way(1, _line(0, 900, 0)),
        _way(2, _line(900, 0, 28)),
        _way(3, _line(900, 0, 2000)),  # same name, opposite bearing, 2 km north
    ]
    factors, pairs = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors == {1: 0.5, 2: 0.5, 3: 1.0}
    by_way = {p.way_id: p for p in pairs}
    assert by_way[1].partner_ids == (2,) and by_way[2].partner_ids == (1,)
    assert 3 not in by_way


def test_dual_pair_carries_per_partner_share_and_distance():
    # way 1 runs along two opposite halves; each partner covers about half of it
    roads = [
        _way(1, _line(0, 900, 0)),
        _way(2, _line(450, 0, 28)),
        _way(3, _line(900, 450, 28)),
    ]
    _, pairs = pair_dual_carriageways(roads, MAIN, PROJ)
    p1 = next(p for p in pairs if p.way_id == 1)
    assert p1.partner_ids == (2, 3)
    assert p1.overlap_share == pytest.approx(1.0, abs=0.01)
    assert all(s == pytest.approx(0.5, abs=0.07) for s in p1.partner_shares)
    assert all(d == pytest.approx(28, abs=1) for d in p1.partner_distances_m)


def _unfiltered_factors(roads, pairable, proj, max_dist_m=50.0, min_share=0.7, min_angle=150.0):
    """The pre-I8 pairing (no distance filter on candidates): the oracle for halving factors."""
    from collections import defaultdict

    from shapely import unary_union

    from velometer.pipeline import dedupe as D

    factors = {w.id: 1.0 for w in roads}
    for w in roads:
        if "yes" in D.parts(w.tags.get("dual_carriageway")):
            factors[w.id] = 0.5
    groups = defaultdict(list)
    for w in roads:
        if w.tags.get("highway") in pairable and D._is_oneway(w.tags):
            for key in D._group_keys(w.tags):
                groups[key].append(w)
    pairable_ids = {x.id for g in groups.values() for x in g}
    for w in roads:
        geom = proj.line(w.coords)
        if w.id not in pairable_ids or geom.length == 0:
            continue
        partners = {}
        for key in D._group_keys(w.tags):
            for o in groups.get(key, []):
                og = proj.line(o.coords)
                if o.id == w.id or o.id in partners or og.length == 0:
                    continue
                m = og.interpolate(0.5, normalized=True)
                bw = D._local_bearing(geom, geom.project(m), D._oneway_reversed(w.tags))
                bo = D._local_bearing(og, og.project(m), D._oneway_reversed(o.tags))
                if bw is not None and bo is not None and D._angle(bw, bo) >= min_angle:
                    partners[o.id] = og
        if partners:
            union = unary_union(list(partners.values()))
            if D._share_within(geom, union, max_dist_m) >= min_share:
                factors[w.id] = 0.5
    return factors


GOLDEN = Path(__file__).parent / "fixtures" / "berlin_golden.osm"
MINI = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"


@pytest.mark.parametrize("fixture", [FIX / "dual.osm", MINI, GOLDEN], ids=lambda p: p.name)
def test_distance_filter_leaves_halving_factors_unchanged(fixture):
    roads = read_ways(fixture).ways
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors == _unfiltered_factors(roads, MAIN, PROJ)


def test_distance_filter_leaves_synthetic_halving_factors_unchanged():
    p = _ll(450, 14)
    cases = [
        [_way(1, _arc(300, 0, 150)), _way(2, _arc(325, 75, 0)), _way(3, _arc(325, 150, 75))],
        [_way(1, _line(0, 900, 0))]
        + [_way(2 + i, _line(300 * (i + 1), 300 * i, 28)) for i in range(3)],
        [_way(1, _line(0, 900, 0)), _way(2, _line(0, 900, 28), oneway="-1")],
        [_way(1, _line(0, 900, 0)), _way(2, _line(900, 0, 28)), _way(3, (p, p))],
        [_way(1, _line(0, 900, 0)), _way(2, _line(900, 0, 28)), _way(3, _line(900, 0, 2000))],
    ]
    for roads in cases:
        assert pair_dual_carriageways(roads, MAIN, PROJ)[0] == _unfiltered_factors(
            roads, MAIN, PROJ
        )
