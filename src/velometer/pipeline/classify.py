"""Ordered, data-driven rule engine over way-sides (rules: config/classifier/vN.yaml)."""

from collections.abc import Iterable

from velometer.config import ClassifierConfig
from velometer.pipeline.explode import ONEWAY_YES, explode
from velometer.pipeline.match import matches
from velometer.pipeline.types import Classified, WayRecord, WaySide


def is_bidirectional(side: WaySide) -> bool:
    """QECIO Methodology Table 3 directionality."""
    if side.kind == "standalone":
        return (
            side.tags.get("oneway", "no") not in ONEWAY_YES
            and side.tags.get("oneway:bicycle") != "yes"
        )
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
    return [classify(s, cfg) for w in ways for s in explode(w, cfg.road_classes)]
