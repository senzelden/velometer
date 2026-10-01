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


LOCAL_SPAN_M = 10.0


def _parts(value: str | None) -> set[str]:
    if not value:
        return set()
    return {p.strip() for p in value.split(";") if p.strip()}


def _oneway_reversed(tags: dict[str, str]) -> bool:
    parts = _parts(tags.get("oneway"))
    return "-1" in parts and not parts & {"yes", "1", "true"}


def _is_oneway(tags: dict[str, str]) -> bool:
    return bool(_parts(tags.get("oneway")) & ONEWAY_YES)


def _local_bearing(line, dist: float, reverse: bool) -> float | None:
    """Direction of travel around `dist` along `line`; None if the span has no extent."""
    a = line.interpolate(max(dist - LOCAL_SPAN_M, 0.0))
    b = line.interpolate(min(dist + LOCAL_SPAN_M, line.length))
    if a.equals(b):
        return None
    x0, y0, x1, y1 = (b.x, b.y, a.x, a.y) if reverse else (a.x, a.y, b.x, b.y)
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


def _angle(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def _group_keys(tags: dict[str, str]) -> list[tuple[str, str]]:
    return [(k, v.casefold()) for k in ("name", "ref") for v in sorted(_parts(tags.get(k)))]


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
        if "yes" in _parts(w.tags.get("dual_carriageway")):
            factors[w.id] = 0.5
    groups: dict[tuple[str, str], list[WayRecord]] = defaultdict(list)
    for w in roads:
        if w.tags.get("highway") not in pairable_highways or not _is_oneway(w.tags):
            continue
        for key in _group_keys(w.tags):
            groups[key].append(w)
    pairable_ids = {x.id for g in groups.values() for x in g}
    pairs: list[DualPair] = []
    for w in roads:
        if w.id not in pairable_ids:  # never halve two-way or non-main roads by pairing
            continue
        geom = proj.line(w.coords)
        if geom.length == 0:
            continue
        w_rev = _oneway_reversed(w.tags)
        partners: dict[int, WayRecord] = {}
        for key in _group_keys(w.tags):
            for o in groups.get(key, []):
                if o.id == w.id or o.id in partners:
                    continue
                og = proj.line(o.coords)
                if og.length == 0:
                    continue
                m = og.interpolate(0.5, normalized=True)
                bw = _local_bearing(geom, geom.project(m), w_rev)
                bo = _local_bearing(og, og.project(m), _oneway_reversed(o.tags))
                if bw is None or bo is None:
                    continue
                if _angle(bw, bo) >= min_angle_deg:
                    partners[o.id] = o
        if not partners:
            continue
        union = unary_union([proj.line(o.coords) for o in partners.values()])
        share = _share_within(geom, union, max_dist_m)
        if share >= min_share:
            factors[w.id] = 0.5
            pairs.append(DualPair(w.id, tuple(sorted(partners)), round(share, 4)))
    return factors, pairs
