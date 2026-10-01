"""Ordered, data-driven rule engine over way-sides (rules: config/classifier/vN.yaml)."""

from collections.abc import Iterable

from velometer.config import ClassifierConfig
from velometer.pipeline.explode import ONEWAY_YES, explode
from velometer.pipeline.match import matches
from velometer.pipeline.tags import parts
from velometer.pipeline.types import Classified, WayRecord, WaySide

BIKE_ONEWAY_YES = frozenset({"yes", "1", "true", "-1"})


def is_bidirectional(side: WaySide) -> bool:
    """QECIO Methodology Table 3 directionality."""
    if side.kind == "standalone":
        oneway = set(parts(side.tags.get("oneway")))
        bike_oneway = set(parts(side.tags.get("oneway:bicycle")))
        return not (oneway & ONEWAY_YES or bike_oneway & BIKE_ONEWAY_YES)
    return side.tags.get("cycleway:oneway") == "no"


def _generic_attrs(side: WaySide) -> dict[str, bool | str]:
    attrs: dict[str, bool | str] = {
        "bidirectional": is_bidirectional(side),
        "contraflow": side.contraflow,
    }
    seg = side.tags.get("segregated" if side.kind == "standalone" else "cycleway:segregated")
    if seg is not None:
        attrs["segregated"] = seg
    return attrs


def classify(side: WaySide, cfg: ClassifierConfig) -> Classified:
    attrs = _generic_attrs(side)
    for rule in cfg.rules:
        if rule.applies_to not in ("any", side.kind):
            continue
        if matches(rule.match, side.tags, cfg.value_lists):
            return Classified(side, rule.tier, rule.subtype, rule.id, {**attrs, **rule.attrs})
    if side.kind == "road_side" and "cycleway" in side.tags:
        attrs["unknown_value"] = side.tags["cycleway"]
    return Classified(side, None, None, None, attrs)


def classify_ways(ways: Iterable[WayRecord], cfg: ClassifierConfig) -> list[Classified]:
    mode = cfg.parameters.plain_cycleway_on_oneway
    return [classify(s, cfg) for w in ways for s in explode(w, cfg.road_classes, mode)]
