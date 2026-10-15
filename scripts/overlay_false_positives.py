"""Classify the way-side pieces one overlay version keeps and another drops (M8 overlay log).

Read-only against velometer.sqlite and the run's snapshot; writes nothing unless asked. For one
LAU run of Berlin, both versions' `plans.overlay._kept_pieces` are computed on each network class
and every piece kept by `--version` and dropped by `--base` is put in one class:

    uv run python scripts/overlay_false_positives.py --run 743 --version overlay_v3 \\
        --base overlay_v2 [--crops] [--detail beyond_network_end --seed 1]

Pieces are those of `_kept_pieces`: each A/B way-side, clipped to the LAU boundary, cut into equal
pieces of at most `min_part_m / 2` (10 m for v1-v4). Per piece (all lengths in EPSG:25833):

- a *matching* line is a network line of the piece's class within the piece's buffer
  (`buffer_m` for road-side tags, `buffer_separate_m` for separately mapped ways) whose direction
  over +-`MATCH_HALF_M` around its point nearest the piece's midpoint is within `max_angle_deg`
  of the piece (the parameters of `--version`; this is the overlay's own match test, before
  `clip_free_ends`);
- a matching line runs *alongside* the piece when the midpoint projects onto it more than
  `INSIDE_M` from either end, or lies at most `END_TOL_M` past the end it projects onto
  (measured along the line's outward direction over its last `MATCH_HALF_M`). Every end counts,
  free or not: a piece across a joint is alongside the next edge.

Classes, first that applies:

1. `beyond_network_end`: no matching line runs alongside, and no line of the other class runs
   alongside (within the same buffer and angle, projecting more than `INSIDE_M` inside it).
2. `class_boundary`: as 1, but a line of the other class runs alongside.
3. `junction_crossing`: the nearest line of the class (any distance) is more than `PARALLEL_DEG`
   from the piece (direction over +-`DIR_HALF_M`): it crosses that line, along another.
4. `parallel_or_crossing_street`: of the OSM carriageways (`road_classes.carriageway` of the
   report classifier, without `service`) within `ROAD_SEARCH_M` of the midpoint and within
   `PARALLEL_DEG` of the piece, the nearest is more than `PARALLEL_DEG` from the matched line (the
   nearest matching line), or its point nearest the midpoint is more than `NEAR_NET_M` from it.
5. `along`: the rest (the piece runs beside the road the network line follows, beside no
   carriageway, or along a network line that runs off-road).

`--checks` also prints: the km each version keeps on the two networks (summed over the classes) and
in both network classes; per class, the `class_boundary` pieces that the base keeps in the other
class, and those in neither class; and the pieces lying in a hole of a chain the base keeps (a
base-kept piece within `HOLE_PIECES` consecutive, end-to-start chained pieces on both sides), in all
and among the pieces whose midpoint lies past a *turn end* of a matching line (a free end under
overlay_v4's rule, 30°, that another line's end lies within 1 m of: the network turns there rather
than stops).

`--real-loss` prints, per network class, the dropped pieces that may lie along the network across
a turn (M13), in four disjoint parts: the pieces in a hole (as `--checks`, any class); outside
holes, the `along` class; the `class_boundary` pieces the base keeps in neither class; and the
`beyond_network_end` pieces at an *outer corner* (`outer_corner`: past the end of a line of the
class within the piece's buffer, at a joint of two edges turning more than `TURN_DEG`, on the
outer side of the turn). They are printed as turn-recoverable (holes past a turn end, plus outer
corners a visual check confirms), outer-corner candidates (mostly false positives: the far side of
a street continuing past the turn, M13 log) and the non-turn residual; their sum is an upper
bound, not the real loss.

`--crops` draws the six densest non-overlapping 800 m cells (1.2 km windows) to
data/maps/berlin_<version>_vs_<base>_crops.png; `--detail CLASS` (repeatable) draws 16 pieces of
the class drawn at random (numpy default_rng(`--seed`), 120 m windows) to
data/maps/berlin_<version>_vs_<base>_detail_<CLASS>.png; `--detail outer_corner` draws the outer
corners of `--real-loss` (each a `beyond_network_end` piece).
"""

import argparse
import json
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

import numpy as np
import shapely
from shapely import STRtree

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / "data" / "maps"
MATCH_HALF_M = 1.0  # the overlay's `_LOCAL_M`: direction window of the match test
DIR_HALF_M = 5.0  # direction window for "crosses" and road directions
PARALLEL_DEG = 30.0  # at most this far apart counts as parallel
INSIDE_M = 0.5  # a projection this far inside a line is not at its end
END_TOL_M = 1.0  # a midpoint at most this far past a line's end still runs alongside it
NEAR_NET_M = 15.0  # a parallel road this close to the network line is the network's road
ROAD_SEARCH_M = 30.0  # search radius for the road a piece runs beside
HOLE_PIECES = 3  # --checks: a base-kept piece this many chained pieces away closes a hole
TURN_DEG = 30.0  # --real-loss: a joint turning more than this is a turn (overlay_v4's angle)
CLASSES = ["along", "junction_crossing", "parallel_or_crossing_street", "class_boundary",
           "beyond_network_end"]  # fmt: skip
LABEL = {
    "along": "along the network line",
    "junction_crossing": "crosses a network line, along another",
    "parallel_or_crossing_street": "beside another parallel or crossing road",
    "class_boundary": "past its class's line end, on the other class",
    "beyond_network_end": "past the network line's end",
}


def piece_class(min_beyond_m: float, other_alongside: bool, angle_to_nearest_deg: float,
                road: tuple[float, float] | None) -> str:  # fmt: skip
    """The class of one piece. `min_beyond_m`: the least distance its midpoint lies past the end
    of a matching line (negative: alongside it); `angle_to_nearest_deg`: to the nearest line of
    its class; `road`: (angle to the matched line in degrees, distance from it in m) of the
    nearest parallel carriageway, or None."""
    if min_beyond_m > END_TOL_M:
        return "class_boundary" if other_alongside else "beyond_network_end"
    if angle_to_nearest_deg > PARALLEL_DEG:
        return "junction_crossing"
    if road is not None and (road[0] > PARALLEL_DEG or road[1] > NEAR_NET_M):
        return "parallel_or_crossing_street"
    return "along"


def direction(lines, pts, half: float) -> np.ndarray:
    """Unit direction of each line over +-`half` around its point nearest each point."""
    at = shapely.line_locate_point(lines, pts)
    length = shapely.length(lines)
    a = shapely.get_coordinates(
        shapely.line_interpolate_point(lines, np.clip(at - half, 0, length))
    )
    c = shapely.get_coordinates(
        shapely.line_interpolate_point(lines, np.clip(at + half, 0, length))
    )
    d = c - a
    n = np.hypot(d[:, 0], d[:, 1])
    n[n == 0] = 1
    return d / n[:, None]


def angle(u, v) -> np.ndarray:
    """Undirected angle in degrees between unit vectors, row by row."""
    return np.degrees(np.arccos(np.clip(np.abs((u * v).sum(axis=1)), 0, 1)))


def beyond_end(lines, mids) -> np.ndarray:
    """How far each midpoint lies past the end of its line it projects onto (m, along the line's
    outward direction over its last `MATCH_HALF_M`); -1 where it projects inside the line."""
    t = shapely.line_locate_point(lines, mids)
    ln = shapely.length(lines)
    at_start = t <= INSIDE_M
    e_pt = shapely.get_coordinates(shapely.line_interpolate_point(lines, np.where(at_start, 0, ln)))
    i_pt = shapely.get_coordinates(
        shapely.line_interpolate_point(
            lines,
            np.where(at_start, np.minimum(MATCH_HALF_M, ln), np.maximum(ln - MATCH_HALF_M, 0)),
        )
    )
    out = e_pt - i_pt
    out = out / np.maximum(np.hypot(out[:, 0], out[:, 1]), 1e-9)[:, None]
    past = ((shapely.get_coordinates(mids) - e_pt) * out).sum(axis=1)
    return np.where((t > INSIDE_M) & (t < ln - INSIDE_M), -1.0, past)


def load(run_id: int, versions: tuple[str, str]):
    """(sides, LAU boundary, network lines by class, the two overlay configs, carriageway lines)
    for one Berlin LAU run."""
    from velometer.config import default_config_dir, load_cities, load_classifier
    from velometer.db import fetch_boundary, fetch_run
    from velometer.pipeline.geometry import Projector
    from velometer.pipeline.read import read_ways
    from velometer.plans import overlay as ov
    from velometer.plans.berlin import NETWORK_LAYER
    from velometer.report import change as ch
    from velometer.run import snapshot_path_for_run
    from velometer.selection import report_selector
    from velometer.sources.boundaries import load_boundary_polygon

    cfg_dir, data_dir = default_config_dir(), ROOT / "data"
    conn = sqlite3.connect(f"file:{ROOT / 'velometer.sqlite'}?mode=ro", uri=True)
    classifier = load_classifier(
        cfg_dir / "classifier" / f"{report_selector(cfg_dir).version}.yaml"
    )
    city = next(c for c in load_cities(cfg_dir / "cities.yaml") if c.id == "berlin")
    b = fetch_boundary(conn, "berlin", "lau")
    boundary = load_boundary_polygon(Path(b.path), city.epsg)
    if fetch_run(conn, run_id)["boundary_sha256"] != b.sha256:
        raise SystemExit(f"run {run_id} was measured on another boundary")
    ways = read_ways(snapshot_path_for_run(conn, run_id, data_dir)).ways
    conn.close()
    sides = ch.classified_sides(ways, classifier, city.epsg, boundary)
    net_path = data_dir / "plans" / "berlin" / f"{NETWORK_LAYER}.geojson"
    network = ov.network_lines(json.loads(net_path.read_text()))
    cfgs = [ov.load_overlay_config(cfg_dir / "plans", v) for v in versions]
    proj = Projector(city.epsg)
    carriageway = set(classifier.road_classes.carriageway) - {"service"}
    roads = [proj.line(w.coords) for w in ways
             if w.tags.get("highway") in carriageway and len(w.coords) >= 2]  # fmt: skip
    return sides, boundary, network, cfgs, np.asarray(roads, dtype=object)


def turn_ends(network) -> np.ndarray:
    """Bool (2n,) in `plans.overlay._end_directions` order: free ends (overlay_v4's rule) that
    another line's end lies within `_JOINT_M` of, i.e. where the network turns by more than
    `max_angle_deg` (30) rather than stops."""
    from velometer.plans import overlay as ov

    end, _ = ov._end_directions(network)
    owner = np.tile(np.arange(len(network)), 2)
    pts = shapely.points(end)
    a, b = STRtree(pts).query(pts, predicate="dwithin", distance=ov._JOINT_M)
    joined = np.zeros(len(end), bool)
    joined[a[owner[a] != owner[b]]] = True
    return joined & ov.free_ends(network, 30.0)


def past_turn_end(lines, qp, qn, mids, n_pieces) -> np.ndarray:
    """Per piece: its midpoint lies past a turn end (`turn_ends`) of one of its matching lines
    (pairs `qp`, `qn`), measured as overlay_v4 does."""
    from velometer.plans import overlay as ov

    end, out = ov._end_directions(lines)
    turn = turn_ends(lines)
    nets = np.asarray(lines, dtype=object)
    at = shapely.line_locate_point(nets[qn], mids[qp])
    length = shapely.length(nets[qn])
    at_end = at >= length - ov._EPS_M
    i = np.where(at_end, qn + len(lines), qn)
    beyond = ((shapely.get_coordinates(mids[qp]) - end[i]) * out[i]).sum(axis=1) > ov._EPS_M
    hit = ((at <= ov._EPS_M) | at_end) & beyond & turn[i]
    res = np.zeros(n_pieces, bool)
    res[qp[hit]] = True
    return res


class CornerParams(NamedTuple):
    buffer_m: float  # the piece's buffer (`buffer_m` or `buffer_separate_m`)
    max_angle_deg: float  # the overlay's match angle


_CORNER_INDEX: dict[int, tuple] = {}


def _corner_index(lines):
    """(lines, STRtree, end points, outward directions, owner, end tree) of `lines`, cached by
    identity (the list is kept, so its id stays valid)."""
    from velometer.plans import overlay as ov

    key = id(lines)
    if key not in _CORNER_INDEX:
        end, out = ov._end_directions(lines)
        _CORNER_INDEX[key] = (lines, STRtree(lines), end, out,
                              np.tile(np.arange(len(lines)), 2),
                              STRtree(shapely.points(end)))  # fmt: skip
    return _CORNER_INDEX[key]


def outer_corner(piece, lines, params: CornerParams) -> bool:
    """The piece lies at the outer corner of a turning network line: its midpoint lies within
    `params.buffer_m` of a line of `lines` (one network class), past one of its ends, at most
    `END_TOL_M` + the buffer from it, and the piece runs within `params.max_angle_deg` of the
    line's outward direction there; at that end exactly one other line of the class has an end
    within `_JOINT_M` (a joint of two edges) and leaves it turning more than `TURN_DEG`; and the
    midpoint lies on the outer side of that turn (the side of the line opposite the way the
    network turns). A way-side following the network round the corner has such pieces; so has,
    within the buffer, the far side of a street continuing straight past the turn, which this
    test cannot tell apart."""
    from velometer.plans import overlay as ov

    lines, tree, end, out, owner, end_tree = _corner_index(lines)
    a, b = np.asarray(piece.coords)[[0, -1]]
    d = (b - a) / max(float(np.hypot(*(b - a))), 1e-9)
    m = (a + b) / 2
    mid = shapely.Point(m)
    n = len(lines)
    cos_turn = np.cos(np.radians(TURN_DEG))
    for i in tree.query(mid, predicate="dwithin", distance=params.buffer_m).tolist():
        line = lines[i]
        t = line.project(mid)
        if INSIDE_M < t < line.length - INSIDE_M:
            continue  # alongside the line, not past an end
        e = i + n if t > line.length / 2 else i
        rel = m - end[e]
        past = float(rel @ out[e])
        if past <= 0 or np.hypot(*rel) > END_TOL_M + params.buffer_m:
            continue
        if float(angle(d[None], out[e][None])[0]) > params.max_angle_deg:
            continue
        near = end_tree.query(shapely.Point(end[e]), predicate="dwithin", distance=ov._JOINT_M)
        joined = [j for j in near.tolist() if owner[j] != i]
        if len(joined) != 1:
            continue  # a free end, or a junction of three or more edges
        leave = -out[joined[0]]  # the other line leaves the joint against its outward direction
        if float(out[e] @ leave) >= cos_turn:
            continue  # a continuation, not a turn
        turn_side = out[e][0] * leave[1] - out[e][1] * leave[0]
        piece_side = out[e][0] * rel[1] - out[e][1] * rel[0]
        if turn_side * piece_side < 0:
            return True
    return False


def in_hole(seg_all, keep_base, only, reach: int = HOLE_PIECES) -> np.ndarray:
    """Per piece in `only`: within `reach` consecutive pieces before and after it (pieces that
    chain end to start, i.e. one way-side part, or touching ways in input order) there is a
    piece kept by the base version on both sides: a hole in a chain the base keeps."""
    n = len(seg_all)
    chained = np.zeros(n, bool)  # piece i's end is piece i+1's start
    chained[:-1] = np.all(np.isclose(seg_all[:-1, 1], seg_all[1:, 0], atol=1e-6), axis=1)
    res = np.zeros(len(only), bool)
    for k, j in enumerate(only.tolist()):
        before = after = False
        for step in range(1, reach + 1):
            if j - step < 0 or not chained[j - step]:
                break
            if keep_base[j - step]:
                before = True
                break
        for step in range(1, reach + 1):
            if j + step >= n or not chained[j + step - 1]:
                break
            if keep_base[j + step]:
                after = True
                break
        res[k] = before and after
    return res


def classify(sides, boundary, network, cfg, base, roads):
    """Per network class: (segments (n, 2, 2), class names, lengths m) of the pieces kept by
    `cfg` and dropped by `base`; every piece kept by `cfg` (for drawing); and per class the
    masks and flags `checks` reads."""
    from velometer.plans import overlay as ov

    road_tree = STRtree(roads)
    out, kept_all, meta = {}, [], {}
    for cls, lines in sorted(network.items(), reverse=True):
        pieces, _, sep, plen, keep = ov._kept_pieces(sides, lines, boundary, cfg)
        keep_base = ov._kept_pieces(sides, lines, boundary, base)[4]
        kept_all.append(pieces[keep])
        only = np.flatnonzero(keep & ~keep_base)
        nets = np.asarray(lines, dtype=object)
        seg = shapely.get_coordinates(pieces[only]).reshape(-1, 2, 2)
        d = seg[:, 1] - seg[:, 0]
        d = d / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
        mids = shapely.points(seg.mean(axis=1))
        inet = STRtree(nets).query_nearest(mids, all_matches=False)[1]
        a_near = angle(d, direction(nets[inet], mids, DIR_HALF_M))
        buf = np.where(sep[only], cfg.separate_buffer_m, cfg.buffer_m)
        qp, qn = STRtree(nets).query(pieces[only], predicate="dwithin", distance=buf)
        ok = angle(d[qp], direction(nets[qn], mids[qp], MATCH_HALF_M)) <= cfg.max_angle_deg
        qp, qn = qp[ok], qn[ok]
        match, md = np.full(len(only), -1), np.full(len(only), np.inf)
        for p_, n_, dd in zip(qp, qn, shapely.distance(pieces[only][qp], nets[qn]), strict=True):
            if dd < md[p_]:
                match[p_], md[p_] = n_, dd
        if (match < 0).any():
            raise SystemExit(f"{cls}: {(match < 0).sum()} pieces without a matching line")
        min_beyond = np.full(len(only), np.inf)
        np.minimum.at(min_beyond, qp, beyond_end(nets[qn], mids[qp]))
        other = np.asarray(next(v for k, v in network.items() if k != cls), dtype=object)
        op, on = STRtree(other).query(pieces[only], predicate="dwithin", distance=buf)
        ook = angle(d[op], direction(other[on], mids[op], MATCH_HALF_M)) <= cfg.max_angle_deg
        ot = shapely.line_locate_point(other[on], mids[op])
        ook &= (ot > INSIDE_M) & (ot < shapely.length(other[on]) - INSIDE_M)
        other_alongside = np.zeros(len(only), bool)
        other_alongside[op[ook]] = True
        matched = nets[match]
        mdir = direction(matched, mids, DIR_HALF_M)
        ip, ir = road_tree.query(mids, predicate="dwithin", distance=ROAD_SEARCH_M)
        par = angle(d[ip], direction(roads[ir], mids[ip], DIR_HALF_M)) <= PARALLEL_DEG
        ip, ir = ip[par], ir[par]
        best: dict[int, tuple[int, float]] = {}
        for p_, r_, dd in zip(ip, ir, shapely.distance(mids[ip], roads[ir]), strict=True):
            if p_ not in best or dd < best[p_][1]:
                best[p_] = (r_, dd)
        names = []
        for k in range(len(only)):
            road = None
            if k in best:
                r = roads[best[k][0]]
                road_pt = shapely.line_interpolate_point(r, shapely.line_locate_point(r, mids[k]))
                r_dir = direction(np.array([r]), np.array([mids[k]]), DIR_HALF_M)
                road = (float(angle(r_dir, mdir[k : k + 1])[0]),
                        float(shapely.distance(road_pt, matched[k])))  # fmt: skip
            names.append(piece_class(min_beyond[k], other_alongside[k], a_near[k], road))
        out[cls] = (seg, np.array(names, dtype=object), plen[only])
        meta[cls] = {
            "keep": keep, "keep_base": keep_base, "plen": plen, "only": only,
            "turn": past_turn_end(lines, qp, qn, mids, len(only)),
            "hole": in_hole(shapely.get_coordinates(pieces).reshape(-1, 2, 2), keep_base, only),
            "pieces": pieces[only], "buffer": buf,
        }  # fmt: skip
    return out, np.concatenate(kept_all), road_tree, meta


def checks(out, meta, version: str, base: str) -> None:
    """Cross-class and chain checks of the pieces kept by `version`, dropped by `base`."""
    a, b = sorted(meta)
    km = lambda mask, cls: float(meta[cls]["plen"][mask].sum()) / 1000  # noqa: E731
    for v, key in ((version, "keep"), (base, "keep_base")):
        per = {cls: km(meta[cls][key], cls) for cls in (a, b)}
        print(f"  kept by {v}: {sum(per.values()):.2f} km on the two networks ("
              + ", ".join(f"{cls} {k:.2f}" for cls, k in per.items()) + ")")  # fmt: skip
    for v, key in ((version, "keep"), (base, "keep_base")):
        both = meta[a][key] & meta[b][key]
        print(f"  kept by {v} in both classes: {km(both, a):.2f} km")
    for cls in (a, b):
        other = b if cls == a else a
        m, names = meta[cls], out[cls][1]
        cb = m["only"][names == "class_boundary"]
        kept_other = meta[other]["keep_base"][cb]
        print(f"  {cls} class_boundary: {km(cb[kept_other], cls):.2f} km kept by {base} in "
              f"{other}, {km(cb[~kept_other], cls):.2f} km in neither class")  # fmt: skip
    for cls in (a, b):
        m, names = meta[cls], out[cls][1]
        for label, sel in (("past a turn end", m["turn"]), ("all", np.ones(len(names), bool))):
            hole = sel & m["hole"]
            by = {c: km(m["only"][hole & (names == c)], cls) for c in CLASSES}
            print(f"  {cls} {label}: {km(m['only'][sel], cls):.2f} km, of which in a hole of a "
                  f"chain {base} keeps {km(m['only'][hole], cls):.2f} km ("
                  + ", ".join(f"{c} {v:.2f}" for c, v in by.items() if v) + ")")  # fmt: skip


def outer_flags(out, meta, network, cfg) -> dict:
    """Per network class: bool per dropped piece, True for a `beyond_network_end` piece outside a
    hole that `outer_corner` finds at an outer corner (`cfg`'s buffers and angle)."""
    res = {}
    for cls, (_, names, _) in out.items():
        m = meta[cls]
        flags = np.zeros(len(names), bool)
        for k in np.flatnonzero((names == "beyond_network_end") & ~m["hole"]).tolist():
            params = CornerParams(float(m["buffer"][k]), cfg.max_angle_deg)
            flags[k] = outer_corner(m["pieces"][k], network[cls], params)
        res[cls] = flags
    return res


def real_loss(out, meta, network, cfg, base: str) -> None:
    """The dropped pieces that may lie along the network across a turn, per class, in four
    disjoint parts: the pieces in a hole of a chain the base keeps (any class); then, outside
    holes, the `along` class, the `class_boundary` pieces the base keeps in neither class, and the
    `beyond_network_end` pieces at an outer corner (`outer_corner`, with `cfg`'s buffers and
    angle). Printed as what a turn rule could recover (holes past a turn end; outer corners only
    where a visual check confirms them, which this script does not do), the outer-corner
    candidates (mostly the continuing street's far side, M13 log), and the non-turn residual.
    The four parts' sum is an upper bound, not the real loss."""
    a, b = sorted(meta)
    outer_by = outer_flags(out, meta, network, cfg)
    km = lambda cls, mask: float(meta[cls]["plen"][meta[cls]["only"][mask]].sum()) / 1000  # noqa: E731
    totals: dict[str, float] = defaultdict(float)
    for cls in (a, b):
        other = b if cls == a else a
        m, names = meta[cls], out[cls][1]
        hole, outer = m["hole"], outer_by[cls]
        parts = {
            "holes past a turn end": hole & m["turn"],
            "outer-corner candidates": outer,
            "holes elsewhere": hole & ~m["turn"],
            "along": (names == "along") & ~hole,
            "class boundary in neither class": (names == "class_boundary")
            & ~meta[other]["keep_base"][m["only"]]
            & ~hole,
        }
        k = {name: km(cls, mask) for name, mask in parts.items()}
        for name, v in k.items():
            totals[name] += v
        beyond = km(cls, (names == "beyond_network_end") & ~hole)
        residual = k["holes elsewhere"] + k["along"] + k["class boundary in neither class"]
        print(f"  {cls}: turn-recoverable (holes past turn ends + verified corners): holes past "
              f"turn ends {k['holes past a turn end']:.2f} km + verified corners (a visual "
              "check; not computed)")  # fmt: skip
        print(f"  {cls}: outer-corner candidates (mostly false positives): "
              f"{k['outer-corner candidates']:.2f} km of {beyond:.2f} km beyond_network_end "
              "outside holes")  # fmt: skip
        print(f"  {cls}: non-turn residual: {residual:.2f} km (holes elsewhere "
              f"{k['holes elsewhere']:.2f}, along {k['along']:.2f}, class boundary in neither "
              f"class {k['class boundary in neither class']:.2f})")  # fmt: skip
    print("  both classes: " + ", ".join(f"{n} {v:.2f}" for n, v in totals.items())
          + f"; the four parts sum to {sum(totals.values()):.2f} km, an upper bound, not the "
          f"real loss (pieces kept by {cfg.version}, dropped by {base})")  # fmt: skip


def report(out, version: str, base: str, run_id: int) -> None:
    total = sum(float(v[2].sum()) for v in out.values()) / 1000
    print(f"run {run_id}: pieces kept by {version}, dropped by {base}: {total:.2f} km")
    for cls, (_, _, lens) in out.items():
        print(f"  {cls}: {lens.sum() / 1000:.2f} km")
    for c in CLASSES:
        by = {cls: float(lens[names == c].sum()) / 1000 for cls, (_, names, lens) in out.items()}
        km = sum(by.values())
        share = 100 * km / total if total else 0.0
        print(
            f"  {c:28s} {km:6.2f} km {share:5.1f} %  ("
            + " / ".join(f"{cls} {v:.2f}" for cls, v in by.items())
            + ")"
        )


def draw_crops(out, kept_all, road_tree, network, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    cell = 800.0
    segs = np.concatenate([v[0] for v in out.values()])
    cats = np.concatenate([v[1] for v in out.values()])
    lens = np.concatenate([v[2] for v in out.values()])
    cell_km: dict[tuple[int, int], float] = defaultdict(float)
    for c, length in zip(map(tuple, np.floor(segs.mean(axis=1) / cell).astype(int)), lens,
                         strict=True):  # fmt: skip
        cell_km[c] += length / 1000
    chosen: list[tuple[int, int]] = []
    for c, _ in sorted(cell_km.items(), key=lambda kv: -kv[1]):
        if all(max(abs(c[0] - o[0]), abs(c[1] - o[1])) > 1 for o in chosen):
            chosen.append(c)
        if len(chosen) == 6:
            break
    col = {"along": "#c2185b", "junction_crossing": "#ff9800",
           "parallel_or_crossing_street": "#7b1fa2", "class_boundary": "#00a0c0",
           "beyond_network_end": "#000000"}  # fmt: skip
    netcol = {"vorrangnetz": "#1f6fb5", "ergaenzungsnetz": "#2ca05a"}
    kt = STRtree(kept_all)
    fig, axes = plt.subplots(2, 3, figsize=(19, 13.5), dpi=100)
    for ax, (i, j) in zip(axes.ravel(), chosen, strict=False):
        x0, y0 = (i - 0.25) * cell, (j - 0.25) * cell
        x1, y1 = x0 + 1.5 * cell, y0 + 1.5 * cell
        window = shapely.box(x0, y0, x1, y1)
        for g in road_tree.geometries.take(road_tree.query(window)):
            ax.plot(*g.xy, color="#d0d0d0", lw=0.7, zorder=1)
        for cls, lines in network.items():
            t = STRtree(lines)
            for g in t.geometries.take(t.query(window)):
                ax.plot(*g.xy, color=netcol[cls], lw=2.2, alpha=0.55, zorder=2)
        for g in kt.geometries.take(kt.query(window)):
            ax.plot(*g.xy, color="#555555", lw=1.0, zorder=3)
        inside = ((segs[:, :, 0].min(1) < x1) & (segs[:, :, 0].max(1) > x0)
                  & (segs[:, :, 1].min(1) < y1) & (segs[:, :, 1].max(1) > y0))  # fmt: skip
        for s, c in zip(segs[inside], cats[inside], strict=True):
            ax.plot(s[:, 0], s[:, 1], color=col[c], lw=3.2, zorder=5, solid_capstyle="butt")
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"EPSG:25833 x {x0:.0f}, y {y0:.0f} (1.2 km); {cell_km[(i, j)]:.2f} km in "
                     "the centre cell", fontsize=10, loc="left")  # fmt: skip
    km = {c: float(lens[cats == c].sum()) / 1000 for c in CLASSES}
    handles = [Line2D([], [], color=netcol[c], lw=3, alpha=0.6, label=f"network: {c}")
               for c in netcol]  # fmt: skip
    handles.append(Line2D([], [], color="#555555", lw=1.5, label="A/B side piece kept"))
    handles += [Line2D([], [], color=col[c], lw=3.5, label=f"{LABEL[c]} ({km[c]:.1f} km)")
                for c in CLASSES]  # fmt: skip
    handles.append(Line2D([], [], color="#d0d0d0", lw=1.5, label="carriageway (OSM)"))
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=11,
               bbox_to_anchor=(0.5, 0.02))  # fmt: skip
    fig.suptitle(title, fontsize=15, x=0.02, ha="left")
    fig.text(0.02, 0.005, "Network: Senatsverwaltung Berlin, Radverkehrsnetz (dl-de-zero-2.0). "
             "Way-sides and roads: © OpenStreetMap contributors, ODbL 1.0. Mapped km (ADR 0006).",
             fontsize=9, color="#555555")  # fmt: skip
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.12, wspace=0.03, hspace=0.12)
    fig.savefig(path)
    print(f"wrote {path}")


def draw_detail(out, road_tree, network, sides, cls_name: str, seed: int, path: Path,
                title: str) -> None:  # fmt: skip
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    segs = np.concatenate([v[0] for v in out.values()])
    cats = np.concatenate([v[1] for v in out.values()])
    idx = np.flatnonzero(cats == cls_name)
    pick = np.random.default_rng(seed).choice(idx, size=min(16, len(idx)), replace=False)
    netcol = {"vorrangnetz": "#1f6fb5", "ergaenzungsnetz": "#2ca05a"}
    all_nets = [(c, ln) for c, ls in network.items() for ln in ls]
    ntree = STRtree([ln for _, ln in all_nets])
    ab = [s.line for s in sides.values() if s.tier in ("A", "B")]
    stree = STRtree(ab)
    fig, axes = plt.subplots(4, 4, figsize=(18, 18), dpi=90)
    for ax, q in zip(axes.ravel(), pick, strict=False):
        c = segs[q].mean(axis=0)
        window = shapely.box(c[0] - 60, c[1] - 60, c[0] + 60, c[1] + 60)
        for g in road_tree.geometries.take(road_tree.query(window)):
            ax.plot(*g.xy, color="#bbbbbb", lw=3, zorder=1)
        for j in ntree.query(window):
            ax.plot(*all_nets[j][1].xy, color=netcol[all_nets[j][0]], lw=2, alpha=0.7, zorder=2)
        for g in stree.geometries.take(stree.query(window)):
            ax.plot(*g.xy, color="#555555", lw=1, zorder=3)
        ax.plot(segs[q][:, 0], segs[q][:, 1], color="#ff0000", lw=4, zorder=5)
        ax.set_xlim(c[0] - 60, c[0] + 60)
        ax.set_ylim(c[1] - 60, c[1] + 60)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(title, fontsize=13)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.text(
        0.01,
        0.005,
        "Network: Senatsverwaltung Berlin, Radverkehrsnetz (dl-de-zero-2.0). "
        "Way-sides and roads: © OpenStreetMap contributors, ODbL 1.0.",
        fontsize=9,
    )
    fig.savefig(path)
    print(f"wrote {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--run", type=int, required=True, help="a Berlin LAU run id, e.g. 743")
    ap.add_argument("--version", required=True, help="the version whose extra pieces to classify")
    ap.add_argument("--base", default="overlay_v2", help="the version they are compared with")
    ap.add_argument("--crops", action="store_true", help="write the crops PNG to data/maps/")
    ap.add_argument(
        "--checks", action="store_true",
        help="print cross-class counts and pieces in holes of chains the base keeps",
    )  # fmt: skip
    ap.add_argument(
        "--detail", choices=[*CLASSES, "outer_corner"], action="append", default=[],
        help="write 16 pieces of a class (or the outer corners of --real-loss) to data/maps/ "
        "(repeatable)",
    )  # fmt: skip
    ap.add_argument(
        "--real-loss", action="store_true",
        help="print the dropped km along the network across a turn, in four parts per class",
    )  # fmt: skip
    ap.add_argument("--seed", type=int, default=1, help="random seed of --detail (default 1)")
    args = ap.parse_args()
    t0 = time.monotonic()
    sides, boundary, network, (cfg, base), roads = load(args.run, (args.version, args.base))
    out, kept_all, road_tree, meta = classify(sides, boundary, network, cfg, base, roads)
    report(out, args.version, args.base, args.run)
    if args.checks:
        checks(out, meta, args.version, args.base)
    if args.real_loss:
        real_loss(out, meta, network, cfg, args.base)
    what = f"pieces kept by {args.version}, dropped by {args.base}, run {args.run}"
    stem = f"berlin_{args.version}_vs_{args.base}"
    if args.crops or args.detail:
        MAPS.mkdir(parents=True, exist_ok=True)
    if args.crops:
        draw_crops(out, kept_all, road_tree, network, MAPS / f"{stem}_crops.png",
                   f"{what}: the six densest areas")  # fmt: skip
    if "outer_corner" in args.detail:  # relabel the outer corners for drawing
        flags = outer_flags(out, meta, network, cfg)
        out = {cls: (seg, np.where(flags[cls], "outer_corner", names), lens)
               for cls, (seg, names, lens) in out.items()}  # fmt: skip
    for name in args.detail:
        draw_detail(out, road_tree, network, sides, name, args.seed,
                    MAPS / f"{stem}_detail_{name}.png",
                    f"{what}: 16 classed {name} (red, seed {args.seed}), 120 m windows; "
                    "grey: carriageways; dark: A/B sides; blue/green: network")  # fmt: skip
    print(f"done in {time.monotonic() - t0:.0f} s")


if __name__ == "__main__":
    main()
