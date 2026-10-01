"""Flag (never delete) double-mapped infrastructure; detect dual carriageways (ADR 0003)."""

import math
from collections import defaultdict

from shapely import STRtree, unary_union

from velometer.pipeline.explode import ONEWAY_YES
from velometer.pipeline.geometry import Projector
from velometer.pipeline.types import Classified, DualPair, DuplicateFlag, WayRecord

ROAD_TIERS = {"A", "B", "C", "D"}
STANDALONE_TIERS = {"A", "B"}


def _share_within(line, other, dist_m: float) -> float:
    if line.length == 0:
        return 0.0
    return line.intersection(other.buffer(dist_m)).length / line.length


def flag_parallel_duplicates(
    classified: list[Classified],
    proj: Projector,
    max_dist_m: float = 15.0,
    min_share: float = 0.8,
) -> list[DuplicateFlag]:
    roads = [c for c in classified if c.side.kind == "road_side" and c.tier in ROAD_TIERS]
    stands = [c for c in classified if c.side.kind == "standalone" and c.tier in STANDALONE_TIERS]
    if not roads or not stands:
        return []
    road_geoms = [proj.line(r.side.coords) for r in roads]
    tree = STRtree(road_geoms)
    flags: list[DuplicateFlag] = []
    for s in stands:
        geom = proj.line(s.side.coords)
        if geom.length == 0:
            continue
        for idx in tree.query(geom.buffer(max_dist_m)):
            share = _share_within(geom, road_geoms[idx], max_dist_m)
            if share >= min_share:
                r = roads[idx]
                mid = geom.interpolate(0.5, normalized=True)
                flags.append(
                    DuplicateFlag(
                        s.side.way_id,
                        r.side.way_id,
                        r.side.side,
                        round(share, 4),
                        round(road_geoms[idx].distance(mid), 2),
                    )
                )
    return sorted(flags, key=lambda f: (f.standalone_way_id, f.road_way_id, f.road_side))


def _bearing(line, reverse: bool) -> float:
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    if reverse:
        x0, y0, x1, y1 = x1, y1, x0, y0
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


def _angle(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def pair_dual_carriageways(
    roads: list[WayRecord],
    pairable_highways: set[str],
    proj: Projector,
    max_dist_m: float = 50.0,
    min_share: float = 0.7,
    min_angle_deg: float = 150.0,
) -> tuple[dict[int, float], list[DualPair]]:
    factors = {w.id: 1.0 for w in roads}
    for w in roads:
        if w.tags.get("dual_carriageway") == "yes":
            factors[w.id] = 0.5
    groups: dict[tuple[str, str], list[WayRecord]] = defaultdict(list)
    for w in roads:
        if w.tags.get("highway") not in pairable_highways:
            continue
        if w.tags.get("oneway") not in ONEWAY_YES:
            continue
        for key in ("name", "ref"):
            if w.tags.get(key):
                groups[(key, w.tags[key].strip().casefold())].append(w)
    pairable_ids = {x.id for g in groups.values() for x in g}
    pairs: list[DualPair] = []
    for w in roads:
        if w.id not in pairable_ids:  # never halve two-way or non-main roads by pairing
            continue
        partners: dict[int, WayRecord] = {}
        geom = proj.line(w.coords)
        if geom.length == 0:
            continue
        bw = _bearing(geom, w.tags.get("oneway") == "-1")
        for key in ("name", "ref"):
            value = w.tags.get(key)
            if not value:
                continue
            for o in groups.get((key, value.strip().casefold()), []):
                if o.id == w.id or o.id in partners:
                    continue
                og = proj.line(o.coords)
                if og.length == 0:
                    continue
                if _angle(bw, _bearing(og, o.tags.get("oneway") == "-1")) >= min_angle_deg:
                    partners[o.id] = o
        if not partners:
            continue
        union = unary_union([proj.line(o.coords) for o in partners.values()])
        share = _share_within(geom, union, max_dist_m)
        if share >= min_share:
            factors[w.id] = 0.5
            pairs.append(DualPair(w.id, tuple(sorted(partners)), round(share, 4)))
    return factors, pairs
