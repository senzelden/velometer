"""Aggregate classified way-sides into tier lengths, road lengths and preset metrics."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from velometer.config import ClassifierConfig, Preset
from velometer.models import Metric, RoadLength, TierLength
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.dedupe import flag_parallel_duplicates, pair_dual_carriageways
from velometer.pipeline.geometry import Projector, length_km
from velometer.pipeline.tags import parts
from velometer.pipeline.types import Classified, DualPair, DuplicateFlag, WayRecord


@dataclass(frozen=True)
class MeasureResult:
    tier_lengths: list[TierLength]
    road_lengths: list[RoadLength]
    duplicates: list[DuplicateFlag]
    dual_pairs: list[DualPair]
    classified: list[Classified]
    unknown_values: dict[str, int]


def _closed_to_public(tags, bicycle_allowed: set[str]) -> bool:
    """access=private always; access=no unless bicycle is allowed (mirrors X_road_private, R22)."""
    access = set(parts(tags.get("access")))
    if "private" in access:
        return True
    return "no" in access and not set(parts(tags.get("bicycle"))) & bicycle_allowed


def _public_roads(ways: list[WayRecord], cfg: ClassifierConfig) -> list[WayRecord]:
    rc = cfg.road_classes
    classes = set(rc.main) | set(rc.motorway) | set(rc.local)
    bicycle_allowed = set(cfg.value_lists["bicycle_allowed"])
    return [
        w
        for w in ways
        if w.tags.get("highway") in classes
        and not _closed_to_public(w.tags, bicycle_allowed)
        and "yes" not in parts(w.tags.get("area"))
    ]


def measure(ways: list[WayRecord], cfg: ClassifierConfig, epsg: int) -> MeasureResult:
    proj = Projector(epsg)
    lengths = {w.id: length_km(proj.line(w.coords)) for w in ways}
    classified = classify_ways(ways, cfg)

    km: dict[tuple, float] = defaultdict(float)
    way_ids: dict[tuple, set[int]] = defaultdict(set)
    unknown: Counter[str] = Counter()
    for c in classified:
        if c.tier is None:
            if "unknown_value" in c.attrs:
                unknown[str(c.attrs["unknown_value"])] += 1
            continue
        length = lengths[c.side.way_id]
        weight = 1.0 if c.attrs["bidirectional"] else 0.5
        for basis, value in (("per_side", length), ("qecio_weighted", length * weight)):
            key = (c.tier, c.subtype, basis)
            km[key] += value
            way_ids[key].add(c.side.way_id)
    tier_lengths = [
        TierLength(tier=t, subtype=s, length_basis=b, length_km=v, n_ways=len(way_ids[(t, s, b)]))
        for (t, s, b), v in sorted(km.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2]))
    ]

    rc = cfg.road_classes
    main, motorway = set(rc.main), set(rc.motorway)
    public = _public_roads(ways, cfg)
    factors, pairs = pair_dual_carriageways(public, main | motorway, proj)

    def total(highways: set[str], dedupe: bool) -> float:
        return sum(
            lengths[w.id] * (factors[w.id] if dedupe else 1.0)
            for w in public
            if w.tags["highway"] in highways
        )

    everything = main | motorway | set(rc.local)
    road_lengths = [
        RoadLength(road_class="main_excl_motorway", length_km=total(main, True)),
        RoadLength(road_class="main_incl_motorway", length_km=total(main | motorway, True)),
        RoadLength(road_class="main_incl_motorway_raw", length_km=total(main | motorway, False)),
        RoadLength(road_class="all_public", length_km=total(everything, True)),
    ]
    return MeasureResult(
        tier_lengths=tier_lengths,
        road_lengths=road_lengths,
        duplicates=flag_parallel_duplicates(classified, proj),
        dual_pairs=pairs,
        classified=classified,
        unknown_values=dict(unknown),
    )


def road_length(result: MeasureResult, road_class: str) -> float:
    return next(r.length_km for r in result.road_lengths if r.road_class == road_class)


def _selected(t: TierLength, entries: list[str]) -> bool:
    if t.tier == "excluded":
        return False
    for e in entries:
        tier, _, sub = e.partition("/")
        if t.tier == tier and (not sub or t.subtype == sub):
            return True
    return False


def compute_metrics(result: MeasureResult, presets: list[Preset]) -> list[Metric]:
    out = []
    for p in presets:
        num = sum(
            t.length_km
            for t in result.tier_lengths
            if t.length_basis == p.basis and _selected(t, p.tiers)
        )
        den = road_length(result, p.denominator)
        out.append(
            Metric(
                preset=p.id,
                length_basis=p.basis,
                value=(100 * num / den) if den else None,
                numerator_km=num,
                denominator_km=den,
            )
        )
    return out
