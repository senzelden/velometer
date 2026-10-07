"""Mapped A/B km on a plan network (`velometer plans overlay`, M8 spec §4.3, decision 10-11).

A way-side in tier A or B counts as on the network over the parts of its geometry (clipped to
the run's boundary) that lie within `buffer_m` of a network line whose local direction differs
by at most `max_angle_deg`; a part shorter than `min_part_m` is dropped. From overlay_v2 a
separately mapped way (`Side.separate`) gets its own buffer, `buffer_separate_m`: such a way runs
beside the road whose centreline the network follows, while a road-side tag sits on it.

The side is cut into equal pieces of at most `min_part_m / 2`; a piece is kept when a network
line lies within its buffer at a matching angle (measured at the network point nearest the piece's
midpoint), and consecutive kept pieces of one side merge into parts. Up to overlay_v2 the
`min_part_m` test applies to each such part (`merge_scope: side`); from overlay_v3
(`merge_scope: tier`) it applies to the extent of kept parts of one tier that touch across
way-sides, so a way split into short OSM ways still counts, while the two road sides of one short
way (the same extent) do not add up to a part. Either way a kept part counts its own km. From
overlay_v4 (`clip_free_ends`) a piece no longer matches a network line whose free end it lies
past (its midpoint beyond the end, along the line's direction there), so a match stops where the
network line stops instead of running on into the crossing or continuing street by up to the
buffer. An end is free unless another line of the class has an end within `_JOINT_M` of it and
leaves the joint within `max_angle_deg` of the line's own direction (the network is split into
edges at every junction; a joint into a turn of more than `max_angle_deg` is a free end). Lengths
are per_side km in the city EPSG (ADR 0006: mapped km, not km completed to any plan standard).
The parameters are data (`config/plans/overlay_vN.yaml`); a change is a new version.
"""

import math
import re
from pathlib import Path
from typing import Literal

import numpy as np
import shapely
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from shapely import LineString, STRtree
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import substring
from shapely.prepared import prep

from velometer.config import ConfigError

TIERS = ("A", "B")
GEOMETRIES = ("centreline", "separate")  # tags on a road centreline / separately mapped ways
CLASSES = {"Radvorrangnetz": "vorrangnetz", "Ergänzungsnetz": "ergaenzungsnetz"}
_LOCAL_M = 1.0  # half-length of the network stretch whose direction a piece is compared with
_EPS_M = 1e-6
_TOUCH_M = 1e-3  # kept parts of one tier closer than this touch (shared OSM nodes)
_JOINT_M = 1.0  # network line ends closer than this form a joint (overlay_v4)
_VERSION_FILE = re.compile(r"overlay_v(\d+)")


class OverlayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    buffer_m: float = Field(gt=0)  # way-sides tagged on a road centreline
    # separately mapped ways (`Side.separate`); None (v1): `buffer_m` for both
    buffer_separate_m: float | None = Field(default=None, gt=0)
    max_angle_deg: float = Field(ge=0, le=90)
    min_part_m: float = Field(gt=0)
    # what `min_part_m` is tested on: each way-side's kept parts (v1, v2), or kept parts of one
    # tier merged across touching way-sides (v3)
    merge_scope: Literal["side", "tier"] = "side"
    # a piece does not match a network line whose free end it lies past (v4)
    clip_free_ends: bool = False

    @property
    def separate_buffer_m(self) -> float:
        return self.buffer_m if self.buffer_separate_m is None else self.buffer_separate_m


def load_overlay_config(plans_dir: Path, version: str) -> OverlayConfig:
    """`<plans_dir>/<version>.yaml`; its `version` must equal the file name."""
    path = Path(plans_dir) / f"{version}.yaml"
    try:
        cfg = OverlayConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as e:
        raise ConfigError(f"{path}: {e}") from e
    if cfg.version != version:
        raise ConfigError(f"{path}: version {cfg.version!r} differs from the file name {version}")
    return cfg


def latest_overlay_version(plans_dir: Path) -> str:
    """The highest-numbered `<plans_dir>/overlay_vN.yaml` (numeric order: v10 after v9)."""
    found = {
        int(m.group(1)): p.stem
        for p in Path(plans_dir).glob("overlay_v*.yaml")
        if (m := _VERSION_FILE.fullmatch(p.stem))
    }
    if not found:
        raise ConfigError(f"{plans_dir}: no overlay_vN.yaml file")
    return found[max(found)]


def _lines(geom: BaseGeometry) -> list[LineString]:
    """The non-empty, non-zero-length LineStrings of a (multi)line or collection."""
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom] if geom.length > 0 else []
    return [ln for g in getattr(geom, "geoms", []) for ln in _lines(g)]


def network_lines(
    geojson: dict, class_field: str = "ist_radvorrangnetz"
) -> dict[str, list[LineString]]:
    """Network class (`vorrangnetz` / `ergaenzungsnetz`) -> its 2D lines in the served EPSG;
    MultiLineStrings exploded, empty and zero-length parts dropped. A feature without geometry
    or with another class is a ValueError (nothing is dropped silently)."""
    out: dict[str, list[LineString]] = {}
    for i, f in enumerate(geojson.get("features", [])):
        value = (f.get("properties") or {}).get(class_field)
        if value not in CLASSES:
            raise ValueError(f"feature {i}: unknown {class_field} {value!r}")
        if not f.get("geometry"):
            raise ValueError(f"feature {i}: no geometry")
        geom = shapely.force_2d(shape(f["geometry"]))
        out.setdefault(CLASSES[value], []).extend(_lines(geom))
    return out


def network_km(lines: list[LineString]) -> float:
    return sum(ln.length for ln in lines) / 1000


def _undirected_deg(dx, dy, ex, ey):
    """Undirected angle between direction vectors (dx, dy) and (ex, ey), in [0, 90]."""
    a = np.degrees(np.abs(np.arctan2(dy, dx) - np.arctan2(ey, ex))) % 180.0
    return np.minimum(a, 180.0 - a)


def _end_directions(network: list[LineString]):
    """(end points, outward unit directions), shape (2n, 2): the n lines' starts, then their
    ends; the direction is taken over the last `_LOCAL_M` of the line."""
    lines = np.asarray(network, dtype=object)
    length = shapely.length(lines)
    at_end = np.repeat([False, True], len(lines))
    lines, length = np.tile(lines, 2), np.tile(length, 2)
    end = shapely.get_coordinates(
        shapely.line_interpolate_point(lines, np.where(at_end, length, 0.0))
    )
    inner = shapely.get_coordinates(
        shapely.line_interpolate_point(
            lines, np.where(at_end, np.maximum(length - _LOCAL_M, 0), np.minimum(_LOCAL_M, length))
        )
    )
    out = end - inner
    return end, out / np.hypot(out[:, 0], out[:, 1])[:, None]


def free_ends(network: list[LineString], max_angle_deg: float) -> np.ndarray:
    """Bool (2n,): the n lines' starts, then their ends, True where no other line has an end
    within `_JOINT_M` that leaves the joint within `max_angle_deg` of this line's outward
    direction (a continuation of the line)."""
    n = len(network)
    if n == 0:
        return np.zeros(0, bool)
    end, out = _end_directions(network)
    owner = np.tile(np.arange(n), 2)
    a, b = STRtree(shapely.points(end)).query(
        shapely.points(end), predicate="dwithin", distance=_JOINT_M
    )
    other = owner[a] != owner[b]
    a, b = a[other], b[other]
    # line b leaves the joint against its own outward direction
    cont = (out[a] * -out[b]).sum(axis=1) >= np.cos(np.radians(max_angle_deg)) - _EPS_M
    free = np.ones(2 * n, bool)
    free[a[cont]] = False
    return free


def _past_free_end(network, idx_net, mids, at, length, max_angle_deg) -> np.ndarray:
    """Per (piece, network line) pair: the piece's midpoint lies past a free end of the line
    (nearest the line at its end, and beyond the end along the line's outward direction)."""
    n = len(network)
    end, out = _end_directions(network)
    free = free_ends(network, max_angle_deg)
    at_start, at_end = at <= _EPS_M, at >= length - _EPS_M
    i = np.where(at_end, idx_net + n, idx_net)  # the end the midpoint is nearest to
    m = shapely.get_coordinates(mids)
    beyond = ((m - end[i]) * out[i]).sum(axis=1) > _EPS_M
    return (at_start | at_end) & free[i] & beyond


def _kept_pieces(sides: dict, network: list[LineString], boundary: BaseGeometry, cfg):
    """(pieces, tier, separate-way flag, length in m, kept mask) per piece of the A/B sides'
    clipped geometry; the mask already drops parts shorter than `min_part_m`. A piece's length
    is its share of the part's length (the piece itself is the chord between its ends)."""
    prepared = prep(boundary)
    step = cfg.min_part_m / 2
    coords, part_of, piece_len, part_tier, part_separate, parts = [], [], [], [], [], []
    for side in sides.values():
        if side.tier not in TIERS:
            continue
        line = side.line if prepared.contains(side.line) else side.line.intersection(boundary)
        for part in _lines(line):
            n = max(1, math.ceil(part.length / step - 1e-9))
            pts = shapely.get_coordinates(
                shapely.line_interpolate_point(part, np.linspace(0, part.length, n + 1))
            )
            coords.append(np.stack([pts[:-1], pts[1:]], axis=1))
            part_of.append(np.full(n, len(part_tier)))
            piece_len.append(np.full(n, part.length / n))
            part_tier.append(side.tier)
            part_separate.append(side.separate)
            parts.append(part)
    if not coords:
        empty = np.zeros(0, bool)
        return np.zeros(0, dtype=object), np.zeros(0, dtype=str), empty, np.zeros(0), empty
    seg = np.concatenate(coords)
    part_of, piece_len = np.concatenate(part_of), np.concatenate(piece_len)
    pieces = shapely.linestrings(seg)
    tiers = np.array(part_tier)[part_of]
    separate = np.array(part_separate)[part_of]
    if not network:
        return pieces, tiers, separate, piece_len, np.zeros(len(seg), bool)
    # distance: a network line within the piece's buffer
    tree = STRtree(network)
    buffers = np.where(separate, cfg.separate_buffer_m, cfg.buffer_m)
    idx_piece, idx_net = tree.query(pieces, predicate="dwithin", distance=buffers)
    # angle: the network's direction around its point nearest the piece's midpoint
    nets = np.asarray(network, dtype=object)[idx_net]
    mids = shapely.points((seg[idx_piece, 0] + seg[idx_piece, 1]) / 2)
    at = shapely.line_locate_point(nets, mids)
    length = shapely.length(nets)
    p0 = shapely.get_coordinates(
        shapely.line_interpolate_point(nets, np.clip(at - _LOCAL_M, 0, length))
    )
    p1 = shapely.get_coordinates(
        shapely.line_interpolate_point(nets, np.clip(at + _LOCAL_M, 0, length))
    )
    d = seg[idx_piece, 1] - seg[idx_piece, 0]
    e = p1 - p0
    ok = _undirected_deg(d[:, 0], d[:, 1], e[:, 0], e[:, 1]) <= cfg.max_angle_deg
    if cfg.clip_free_ends:
        ok &= ~_past_free_end(network, idx_net, mids, at, length, cfg.max_angle_deg)
    keep = np.zeros(len(seg), bool)
    keep[idx_piece[ok]] = True
    # merge consecutive kept pieces of one part; drop merged parts shorter than min_part_m
    prev_keep = np.concatenate([[False], keep[:-1]])
    prev_part = np.concatenate([[-1], part_of[:-1]])
    starts = keep & (~prev_keep | (part_of != prev_part))
    run = np.cumsum(starts) - 1
    run_m = np.bincount(run[keep], weights=piece_len[keep], minlength=int(starts.sum()))
    long_enough = run_m >= cfg.min_part_m - _EPS_M
    if cfg.merge_scope == "tier" and not long_enough.all():
        long_enough = _touching_extent_long_enough(
            seg, keep, run, run_m, long_enough, part_of, piece_len, parts, tiers, cfg
        )
    keep[keep] = long_enough[run[keep]]
    return pieces, tiers, separate, piece_len, keep


def _touching_extent_long_enough(seg, keep, run, run_m, long_enough, part_of, piece_len, parts,
                                 tiers, cfg):  # fmt: skip
    """`long_enough` per kept run (consecutive kept pieces of one part), widened to every run
    that touches, through runs of its tier, a run of at least `min_part_m` or a group whose
    extent (the length of the union of its runs) is at least `min_part_m`. Touch is tested on
    the runs' chords; extent on their exact geometry."""
    n_runs = len(run_m)
    kept = np.flatnonzero(keep)
    first = np.full(n_runs, len(seg))
    np.minimum.at(first, run[kept], kept)
    last = np.zeros(n_runs, int)
    np.maximum.at(last, run[kept], kept)
    # chord polyline per run: its first piece's start, then each kept piece's end
    with_start = np.stack([kept == first[run[kept]], np.ones(len(kept), bool)], axis=1)
    pts = seg[kept].reshape(-1, 2)[with_start.ravel()]
    chords = shapely.linestrings(pts, indices=np.repeat(run[kept], with_start.sum(axis=1)))
    run_tier = tiers[first]
    short = np.flatnonzero(~long_enough)
    i_short, j = STRtree(chords).query(chords[short], predicate="dwithin", distance=_TOUCH_M)
    i = short[i_short]
    same = (run_tier[i] == run_tier[j]) & (i != j)
    parent = list(range(n_runs))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in zip(i[same].tolist(), j[same].tolist(), strict=True):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    with_long = {find(b) for b in j[same].tolist() if long_enough[b]}
    groups: dict[int, list[int]] = {}
    for r in short.tolist():
        groups.setdefault(find(r), []).append(r)
    out = long_enough.copy()
    part_start = np.searchsorted(part_of, np.arange(len(parts)))
    for root, members in groups.items():
        if root in with_long:
            out[members] = True
            continue
        if len(members) < 2:
            continue
        geoms = []
        for r in members:
            p = int(part_of[first[r]])
            step = piece_len[first[r]]
            start = (first[r] - part_start[p]) * step
            end = (last[r] + 1 - part_start[p]) * step
            geoms.append(substring(parts[p], start, end))
        if shapely.union_all(geoms).length >= cfg.min_part_m - _EPS_M:
            out[members] = True
    return out


def on_network_km_by_geometry(
    sides: dict, network: list[LineString], boundary: BaseGeometry, cfg: OverlayConfig
) -> dict[tuple[str, str], float]:
    """(tier, `centreline` | `separate`) -> per_side km of the sides' parts on `network`, as
    `on_network_km`, split by tags on a road centreline and separately mapped ways."""
    _, tiers, separate, piece_len, keep = _kept_pieces(sides, network, boundary, cfg)
    return {
        (t, g): float(piece_len[keep & (tiers == t) & (separate == (g == "separate"))].sum()) / 1000
        for t in TIERS
        for g in GEOMETRIES
    }


def on_network_km(
    sides: dict, network: list[LineString], boundary: BaseGeometry, cfg: OverlayConfig
) -> dict[str, float]:
    """Tier (A, B) -> per_side km of the sides' parts on `network` (lines in the sides' EPSG),
    clipped to `boundary`. `sides` maps (way id, side) to `report.change.Side`; C-E are ignored."""
    by = on_network_km_by_geometry(sides, network, boundary, cfg)
    return {t: sum(by[t, g] for g in GEOMETRIES) for t in TIERS}
