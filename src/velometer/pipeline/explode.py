"""Explode OSM ways into way-sides (ADR 0002: classification is per way-side)."""

from collections.abc import Mapping

from velometer.config import RoadClasses
from velometer.pipeline.tags import parts
from velometer.pipeline.types import WayRecord, WaySide

ONEWAY_YES = frozenset({"yes", "1", "true", "-1"})
SUBKEYS = ("lane", "oneway", "separation", "buffer", "segregated", "surface", "width")
ROAD_CARRY = (
    "highway",
    "access",
    "bicycle",
    "area",
    "oneway",
    "name",
    "ref",
    "dual_carriageway",
    "construction",
    "proposed",
)
FORWARD = frozenset({"yes", "1", "true"})
CYCLE_STREET_KEYS = ("bicycle_road", "cyclestreet", "cycle_street")


def plain_cycleway_sides(tags: Mapping[str, str]) -> frozenset[str]:
    """Sides a plain `cycleway=<v>` applies to (Ruling R18, provisional; right-hand traffic).

    `oneway=yes|1|true` -> right only; `oneway=-1` -> left only (traffic's right);
    `junction=roundabout` with no oneway tag -> right only; otherwise (incl. `oneway=no`) both.
    """
    oneway = set(parts(tags.get("oneway")))
    if oneway & FORWARD:
        return frozenset({"right"})
    if "-1" in oneway:
        return frozenset({"left"})
    if not oneway and "roundabout" in parts(tags.get("junction")):
        return frozenset({"right"})
    return frozenset({"left", "right"})


def _side_value(tags: Mapping[str, str], side: str) -> str | None:
    for key in (f"cycleway:{side}", "cycleway:both"):
        if key in tags:
            return tags[key]
    plain = tags.get("cycleway")
    if plain is None:
        return None
    if plain.startswith("opposite"):
        return plain if side == "left" else None
    return plain if side in plain_cycleway_sides(tags) else None


def _collect_sub(tags: Mapping[str, str], side: str, sub: str) -> str | None:
    for prefix in (f"cycleway:{side}", "cycleway:both", "cycleway"):
        base = f"{prefix}:{sub}"
        vals = [v for k, v in tags.items() if k == base or k.startswith(base + ":")]
        if vals:
            joined = {p for v in vals for p in parts(v)}
            return ";".join(sorted(joined))
    return None


def _collect_traffic_separation(tags: Mapping[str, str], side: str) -> str | None:
    """Separation on the traffic side of the lane (undirected + `:left` for a right-side lane)."""
    traffic = "left" if side == "right" else "right"
    for prefix in (f"cycleway:{side}", "cycleway:both", "cycleway"):
        base = f"{prefix}:separation"
        if not any(k == base or k.startswith(base + ":") for k in tags):
            continue
        found = set(parts(tags.get(base))) | set(parts(tags.get(f"{base}:{traffic}")))
        return ";".join(sorted(found)) or None
    return None


def _sidewalk_is_separate(tags: Mapping[str, str], side: str) -> bool:
    keys = (f"sidewalk:{side}", "sidewalk:both", "sidewalk")
    return any("separate" in parts(tags.get(k)) for k in keys)


def _resolve_side(tags: Mapping[str, str], side: str) -> tuple[dict[str, str], bool] | None:
    value = _side_value(tags, side)
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
        traffic_sep = _collect_traffic_separation(tags, side)
        if traffic_sep is not None:
            out["cycleway:separation:traffic"] = traffic_sep
    sidewalk = tags.get(f"sidewalk:{side}:bicycle", tags.get("sidewalk:both:bicycle"))
    if sidewalk is not None and not _sidewalk_is_separate(tags, side):
        out["sidewalk_bicycle"] = sidewalk
    return (out, contraflow) if out else None


def explode(way: WayRecord, road_classes: RoadClasses) -> list[WaySide]:
    highway = way.tags.get("highway")
    if highway is None:
        return []
    if highway not in road_classes.carriageway:
        return [WaySide(way.id, "self", "standalone", dict(way.tags), way.coords)]
    result: list[WaySide] = []
    if any("yes" in parts(way.tags.get(k)) for k in CYCLE_STREET_KEYS):
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
