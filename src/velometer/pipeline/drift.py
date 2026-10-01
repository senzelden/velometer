"""Per-run tag-drift diagnostics: km on legacy tagging and km of cycling-tagged road
sides that no rule recognised. Both are per_side km, clipped to the run's boundary (from
`way_lengths`)."""

from velometer.config import ActivityConfig
from velometer.pipeline.activity import cycling_tags
from velometer.pipeline.measure import MeasureResult
from velometer.pipeline.tags import parts
from velometer.pipeline.types import WayRecord


def drift_diagnostics(
    result: MeasureResult, ways: list[WayRecord], cfg: ActivityConfig
) -> dict[str, float]:
    """`legacy_km`: sides with a tier that match a legacy rule or legacy value prefix.
    `unrecognised_cycling_km` (spec §14): ROAD sides only (standalone footways, paths and tracks
    are not counted) with no tier or an unknown cycleway value, whose way carries cycling tags."""
    tags_by_way = {w.id: w.tags for w in ways}
    legacy_rules = set(cfg.legacy.rules)
    legacy_prefixes = cfg.legacy.value_prefixes
    legacy = unrecognised = 0.0
    for c in result.classified:
        way_id = c.side.way_id
        tags = tags_by_way[way_id]
        length = result.way_lengths[way_id]
        if c.side.kind == "road_side" and (c.tier is None or "unknown_value" in c.attrs):
            if cycling_tags(tags, cfg):
                unrecognised += length
        elif c.tier is None:
            continue
        elif c.rule_id in legacy_rules or any(
            part.startswith(prefix)
            for k, prefix in legacy_prefixes.items()
            for part in parts(tags.get(k))
        ):
            legacy += length
    return {"legacy_km": legacy, "unrecognised_cycling_km": unrecognised}
