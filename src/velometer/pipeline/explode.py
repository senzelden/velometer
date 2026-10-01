"""Explode OSM ways into way-sides (ADR 0002: classification is per way-side)."""

from collections.abc import Mapping

from velometer.config import RoadClasses
from velometer.pipeline.types import WayRecord, WaySide

ONEWAY_YES = frozenset({"yes", "1", "true", "-1"})
SUBKEYS = ("lane", "oneway", "separation", "buffer", "segregated", "surface", "width")
ROAD_CARRY = ("highway", "access", "bicycle", "area", "oneway", "name", "ref", "dual_carriageway")
CYCLE_STREET_KEYS = ("bicycle_road", "cyclestreet", "cycle_street")


def _parts(value: str | None) -> set[str]:
    """Split tag value on `;` and strip, returning non-empty parts."""
    if value is None:
        return set()
    return {p.strip() for p in value.split(";") if p.strip()}


def _side_value(tags: Mapping[str, str], side: str, oneway: bool) -> str | None:
    for key in (f"cycleway:{side}", "cycleway:both"):
        if key in tags:
            return tags[key]
    plain = tags.get("cycleway")
    if plain is None:
        return None
    if plain.startswith("opposite"):
        return plain if side == "left" else None
    if oneway and side == "left":
        return None
    return plain


def _collect_sub(tags: Mapping[str, str], side: str, sub: str) -> str | None:
    for prefix in (f"cycleway:{side}", "cycleway:both", "cycleway"):
        base = f"{prefix}:{sub}"
        vals = [v for k, v in tags.items() if k == base or k.startswith(base + ":")]
        if vals:
            parts = {p.strip() for v in vals for p in v.split(";") if p.strip()}
            return ";".join(sorted(parts))
    return None


def _resolve_side(tags: Mapping[str, str], side: str) -> tuple[dict[str, str], bool] | None:
    oneway = any(p in {"yes", "1", "true"} for p in _parts(tags.get("oneway")))
    value = _side_value(tags, side, oneway)
    contraflow = False
    if value == "opposite":
        value = None
    elif value is not None and value.startswith("opposite_"):
        value, contraflow = value.removeprefix("opposite_"), True
    out: dict[str, str] = {}
    if value is not None:
        out["cycleway"] = value
        for sub in SUBKEYS:
            joined = _collect_sub(tags, side, sub)
            if joined is not None:
                out[f"cycleway:{sub}"] = joined
    sidewalk = tags.get(f"sidewalk:{side}:bicycle", tags.get("sidewalk:both:bicycle"))
    if sidewalk is not None:
        out["sidewalk_bicycle"] = sidewalk
    return (out, contraflow) if out else None


def explode(way: WayRecord, road_classes: RoadClasses) -> list[WaySide]:
    highway = way.tags.get("highway")
    if highway is None:
        return []
    if highway not in road_classes.carriageway:
        return [WaySide(way.id, "self", "standalone", dict(way.tags), way.coords)]
    result: list[WaySide] = []
    if any(any(p == "yes" for p in _parts(way.tags.get(k))) for k in CYCLE_STREET_KEYS):
        result.append(WaySide(way.id, "self", "standalone", dict(way.tags), way.coords))
    carried = {f"road:{k}": way.tags[k] for k in ROAD_CARRY if k in way.tags}
    for side in ("left", "right"):
        resolved = _resolve_side(way.tags, side)
        if resolved is None:
            continue
        tags, contraflow = resolved
        result.append(
            WaySide(way.id, side, "road_side", {**tags, **carried}, way.coords, contraflow)
        )
    return result
