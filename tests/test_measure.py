from pathlib import Path

import pytest
from shapely import MultiPolygon, Polygon

from velometer.config import Preset, default_config_dir, load_classifier, load_presets
from velometer.pipeline.geometry import Projector
from velometer.pipeline.measure import (
    SubareaMeasure,
    SubareaSumError,
    attribute_subareas,
    check_subarea_sums,
    compute_metrics,
    measure,
    road_length,
    select_metric,
)
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord
from velometer.subareas import SubareaPolygon

FIX = Path(__file__).parent / "fixtures" / "measure"
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
PRESETS_CONFIG = load_presets(default_config_dir() / "presets.yaml", CFG)
PRESETS = PRESETS_CONFIG.presets
PRESETS_BY_ID = {p.id: p for p in PRESETS}


@pytest.fixture(scope="module")
def result():
    return measure(read_ways(FIX / "mini_city.osm").ways, CFG, 25833)


def km(result, tier, basis, subtype=None):
    return sum(
        t.length_km
        for t in result.tier_lengths
        if t.tier == tier and t.length_basis == basis and (subtype is None or t.subtype == subtype)
    )


def test_per_side_counts_each_side_qecio_halves_unidirectional(result):
    unit = road_length(result, "main_excl_motorway") / 2  # 1 segment
    assert km(result, "A", "per_side") == pytest.approx(3 * unit, rel=0.01)
    assert km(result, "A", "qecio_weighted") == pytest.approx(1.5 * unit, rel=0.01)
    assert km(result, "B", "qecio_weighted") == pytest.approx(1 * unit, rel=0.01)


def test_road_classes_exclude_private_and_split_motorways(result):
    main = road_length(result, "main_excl_motorway")
    assert road_length(result, "main_incl_motorway") == pytest.approx(1.5 * main, rel=0.01)
    assert road_length(result, "main_incl_motorway_raw") == pytest.approx(1.5 * main, rel=0.01)
    assert road_length(result, "all_public") == pytest.approx(2 * main, rel=0.01)


def test_preset_metrics(result):
    metrics = compute_metrics(result, PRESETS)
    m = {p.id: select_metric(metrics, p.id, PRESETS_CONFIG).value for p in PRESETS}
    assert m["ours_headline"] == pytest.approx(200, rel=0.01)
    assert m["ecf_qecio"] == pytest.approx(100, rel=0.01)
    assert m["clean_cities_2025"] == pytest.approx(100, rel=0.01)


def test_parameterised_preset_is_computed_on_every_basis_and_fixed_ones_on_one(result):
    metrics = compute_metrics(result, PRESETS)
    bases = {p: sorted(m.length_basis for m in metrics if m.preset == p) for p in PRESETS_BY_ID}
    assert bases == {
        "ours_headline": ["per_side"],
        "ecf_qecio": ["qecio_weighted"],
        "clean_cities_2025": ["per_side", "qecio_weighted"],
    }
    by_basis = {m.length_basis: m for m in metrics if m.preset == "clean_cities_2025"}
    # the fixture has tracks on both sides of a road, so the two bases differ
    assert by_basis["per_side"].numerator_km != by_basis["qecio_weighted"].numerator_km
    assert by_basis["per_side"].denominator_km == by_basis["qecio_weighted"].denominator_km


def test_select_metric_follows_the_parameter_and_leaves_fixed_presets_alone(result):
    metrics = compute_metrics(result, PRESETS)
    for basis in ("per_side", "qecio_weighted"):
        config = PRESETS_CONFIG.with_parameters(clean_cities_basis=basis)
        assert select_metric(metrics, "clean_cities_2025", config).length_basis == basis
        assert select_metric(metrics, "ours_headline", config).length_basis == "per_side"
        assert select_metric(metrics, "ecf_qecio", config).length_basis == "qecio_weighted"
    assert select_metric([], "clean_cities_2025", PRESETS_CONFIG) is None


def test_empty_denominator_gives_none_not_error():
    ways = [WayRecord(1, {"highway": "cycleway"}, ((13.4, 52.5), (13.41, 52.5)))]
    m = compute_metrics(measure(ways, CFG, 25833), PRESETS)
    assert all(x.value is None and x.denominator_km == 0 for x in m)


def test_unknown_values_are_counted():
    ways = [
        WayRecord(
            1,
            {"highway": "primary", "cycleway:both": "crossing"},
            ((13.4, 52.5), (13.41, 52.5)),
        )
    ]
    assert measure(ways, CFG, 25833).unknown_values == {"crossing": 2}


def test_dual_carriageway_halves_denominator_but_not_raw():
    a = WayRecord(
        1,
        {"highway": "primary", "oneway": "yes", "name": "X"},
        ((13.40, 52.5), (13.4147, 52.5)),
    )
    b = WayRecord(
        2,
        {"highway": "primary", "oneway": "yes", "name": "X"},
        ((13.4147, 52.50025), (13.40, 52.50025)),
    )
    r = measure([a, b], CFG, 25833)
    raw = road_length(r, "main_incl_motorway_raw")
    assert road_length(r, "main_excl_motorway") == pytest.approx(raw / 2, rel=0.01)
    assert len(r.dual_pairs) == 2


@pytest.mark.parametrize(
    "tags",
    [
        {"access": "private"},
        {"access": "yes;private"},
        {"access": "no"},
        {"access": "destination;no"},
        {"access": "no", "bicycle": "no"},
        {"area": "yes"},
        {"area": "no;yes"},
    ],
)
def test_private_or_area_roads_are_excluded_from_denominators_by_any_part(tags):
    way = WayRecord(1, {"highway": "primary", **tags}, ((13.4, 52.5), (13.4147, 52.5)))
    r = measure([way], CFG, 25833)
    assert road_length(r, "main_excl_motorway") == 0
    assert road_length(r, "all_public") == 0


@pytest.mark.parametrize("bicycle", ["yes", "designated", "permissive", "no;yes"])
def test_access_no_road_stays_in_denominators_when_bicycle_allowed(bicycle):
    tags = {"highway": "primary", "access": "no", "bicycle": bicycle}
    way = WayRecord(1, tags, ((13.4, 52.5), (13.4147, 52.5)))
    r = measure([way], CFG, 25833)
    assert road_length(r, "main_excl_motorway") == pytest.approx(1.0, rel=0.01)


def _preset(tiers: list[str]) -> Preset:
    return Preset(id="p", tiers=tiers, basis="per_side", denominator="main_excl_motorway")


SEG = ((13.4, 52.5), (13.4147, 52.5))  # ~1 km


@pytest.fixture(scope="module")
def mixed():
    ways = [
        # B/sidewalk on both sides of one main road (1 way, 2 sides) -> denominator 1 km
        WayRecord(1, {"highway": "primary", "sidewalk:both:bicycle": "designated"}, SEG),
        # B/segregated standalone
        WayRecord(2, {"highway": "footway", "bicycle": "designated", "segregated": "yes"}, SEG),
        # excluded sides (X_no) on another way
        WayRecord(3, {"highway": "residential", "cycleway:both": "no"}, SEG),
    ]
    return measure(ways, CFG, 25833)


def test_subtype_entry_selects_only_that_subtype(mixed):
    (only_sidewalk,) = compute_metrics(mixed, [_preset(["B/sidewalk"])])
    (only_seg,) = compute_metrics(mixed, [_preset(["B/segregated"])])
    (all_b,) = compute_metrics(mixed, [_preset(["B"])])
    assert only_sidewalk.numerator_km == pytest.approx(2.0, rel=0.01)
    assert only_seg.numerator_km == pytest.approx(1.0, rel=0.01)
    assert all_b.numerator_km == pytest.approx(3.0, rel=0.01)


def test_excluded_sides_are_never_selected(mixed):
    assert km(mixed, "excluded", "per_side") == pytest.approx(2.0, rel=0.01)
    (m,) = compute_metrics(mixed, [_preset(["A", "B", "C", "D", "E"])])
    assert m.numerator_km == pytest.approx(3.0, rel=0.01)
    # even an entry naming the excluded tier (rejected by load_presets) selects nothing
    (raw,) = compute_metrics(
        mixed, [Preset.model_construct(**{**_preset(["A"]).model_dump(), "tiers": ["excluded"]})]
    )
    assert raw.numerator_km == 0


def test_n_ways_counts_distinct_ways_not_sides(mixed):
    (t,) = [
        t
        for t in mixed.tier_lengths
        if (t.tier, t.subtype, t.length_basis) == ("B", "sidewalk", "per_side")
    ]
    assert t.n_ways == 1
    (x,) = [t for t in mixed.tier_lengths if (t.tier, t.length_basis) == ("excluded", "per_side")]
    assert x.n_ways == 1


def _oneway_track_road():
    # ~1 km tertiary oneway road with a plain cycleway=track
    tags = {"highway": "tertiary", "oneway": "yes", "cycleway": "track"}
    return WayRecord(1, tags, ((13.4, 52.5), (13.4147, 52.5)))


@pytest.mark.parametrize(
    ("mode", "sides", "delta_sign"), [("traffic_side", 1, 1), ("both_sides", 2, -1)]
)
def test_plain_oneway_mode_and_its_sensitivity_are_reported(mode, sides, delta_sign):
    cfg = CFG.with_parameters(plain_cycleway_on_oneway=mode)
    res = measure([_oneway_track_road()], cfg, 25833)
    length = res.plain_oneway.length_km
    assert length == pytest.approx(1.0, abs=0.01)
    assert res.plain_oneway.mode == mode
    assert res.plain_oneway.n_ways == 1
    assert km(res, "A", "per_side") == pytest.approx(sides * length, rel=1e-6)
    # switching mode would add (traffic_side) or remove (both_sides) exactly one side of tier A
    assert res.plain_oneway.delta_per_side_km == {"A": pytest.approx(delta_sign * length)}


def test_plain_oneway_report_is_empty_when_no_way_is_affected():
    tags = {"highway": "tertiary", "cycleway": "track"}
    res = measure([WayRecord(1, tags, ((13.4, 52.5), (13.41, 52.5)))], CFG, 25833)
    assert res.plain_oneway.n_ways == 0 and res.plain_oneway.delta_per_side_km == {}


def test_plain_oneway_delta_equals_actual_switch_including_tier_changes():
    line = ((13.4, 52.5), (13.41, 52.5))
    ways = [
        # left side becomes D (lane) instead of B (designated sidewalk) when switched
        WayRecord(
            1,
            {
                "highway": "tertiary",
                "oneway": "yes",
                "cycleway": "lane",
                "sidewalk:left:bicycle": "designated",
            },
            line,
        ),
        WayRecord(2, {"highway": "residential", "oneway": "-1", "cycleway": "track"}, line),
        WayRecord(3, {"highway": "primary", "junction": "roundabout", "cycleway": "lane"}, line),
        WayRecord(4, {"highway": "secondary", "cycleway": "track"}, line),  # two-way: unaffected
        WayRecord(5, {"highway": "tertiary", "oneway": "yes", "cycleway:right": "lane"}, line),
    ]
    for mode, other in (("traffic_side", "both_sides"), ("both_sides", "traffic_side")):
        cur = measure(ways, CFG.with_parameters(plain_cycleway_on_oneway=mode), 25833)
        alt = measure(ways, CFG.with_parameters(plain_cycleway_on_oneway=other), 25833)
        assert cur.plain_oneway.n_ways == 3
        for tier in "ABCDE":
            want = km(alt, tier, "per_side") - km(cur, tier, "per_side")
            got = cur.plain_oneway.delta_per_side_km.get(tier, 0.0)
            assert got == pytest.approx(want, abs=1e-9), (mode, tier)
        assert any(cur.plain_oneway.delta_per_side_km.values())  # not vacuous


def _proj_box(lon0, lat0, lon1, lat1, epsg=25833):
    p = Projector(epsg)
    ring = p.line(((lon0, lat0), (lon1, lat0), (lon1, lat1), (lon0, lat1), (lon0, lat0)))
    return Polygon(ring.coords)


TRACK = {"highway": "cycleway"}


def test_clip_counts_only_inside_part():
    way = WayRecord(1, TRACK, ((13.40, 52.5), (13.42, 52.5)))
    full = measure([way], CFG, 25833)
    half = measure([way], CFG, 25833, boundary=_proj_box(13.39, 52.49, 13.41, 52.51))
    assert km(half, "A", "per_side") == pytest.approx(km(full, "A", "per_side") / 2, rel=0.01)


def test_way_outside_boundary_contributes_zero():
    road = {"highway": "primary", "cycleway:both": "track"}
    ways = [WayRecord(1, road, ((13.50, 52.5), (13.52, 52.5)))]
    res = measure(ways, CFG, 25833, boundary=_proj_box(13.39, 52.49, 13.41, 52.51))
    assert km(res, "A", "per_side") == 0
    assert road_length(res, "main_excl_motorway") == 0


def test_clip_multipolygon_with_hole():
    outer = _proj_box(13.39, 52.49, 13.43, 52.51)
    hole = _proj_box(13.40, 52.495, 13.41, 52.505)
    other = _proj_box(13.44, 52.49, 13.45, 52.51)
    mp = MultiPolygon([Polygon(outer.exterior.coords, [hole.exterior.coords]), other])
    way = WayRecord(1, TRACK, ((13.38, 52.5), (13.46, 52.5)))  # crosses everything
    full_km = km(measure([way], CFG, 25833), "A", "per_side")
    res = measure([way], CFG, 25833, boundary=mp)
    # inside: 13.39-13.40 + 13.41-13.43 + 13.44-13.45 = 0.04 of 0.08 degrees of longitude
    assert km(res, "A", "per_side") == pytest.approx(full_km * 0.04 / 0.08, rel=0.01)


def test_completeness_shares_are_length_weighted():
    ways = [
        WayRecord(
            1,
            {"highway": "cycleway", "width": "2", "surface": "asphalt"},
            ((13.40, 52.5), (13.42, 52.5)),
        ),
        WayRecord(2, {"highway": "cycleway"}, ((13.40, 52.6), (13.41, 52.6))),
        WayRecord(
            3,
            {"highway": "primary", "cycleway:right": "track", "cycleway:right:width": "1.5"},
            ((13.40, 52.7), (13.41, 52.7)),
        ),
    ]
    res = measure(ways, CFG, 25833)
    a = next(c for c in res.completeness if c.tier == "A")
    # widths: way 1 (2 units) + way 3 (1 unit) of 4 units; surface: way 1 only
    assert a.share_with_width == pytest.approx(3 / 4, rel=0.02)
    assert a.share_with_surface == pytest.approx(2 / 4, rel=0.02)


def test_completeness_segregated_share_covers_both_key_forms():
    ways = [
        WayRecord(
            1,
            {"highway": "path", "bicycle": "designated", "segregated": "yes"},
            ((13.40, 52.5), (13.42, 52.5)),
        ),
        WayRecord(
            2,
            {
                "highway": "primary",
                "cycleway:right": "track",
                "cycleway:right:segregated": "no",
            },
            ((13.40, 52.6), (13.41, 52.6)),
        ),
        WayRecord(
            3,
            {"highway": "path", "bicycle": "designated"},
            ((13.40, 52.7), (13.41, 52.7)),
        ),
    ]
    res = measure(ways, CFG, 25833)
    b = next(c for c in res.completeness if c.tier == "B")
    # lengths 2 : 1 : 1 units; segregated tag present on ways 1 and 2
    assert b.share_with_segregated == pytest.approx(3 / 4, rel=0.02)


def test_completeness_weights_use_clipped_lengths():
    ways = [
        WayRecord(1, {"highway": "cycleway", "width": "2"}, ((13.40, 52.5), (13.42, 52.5))),
        WayRecord(2, {"highway": "cycleway"}, ((13.40, 52.6), (13.41, 52.6))),
    ]
    # cuts way 1 in half (0.01 of 0.02 degrees inside) and contains way 2 (0.01 degrees)
    boundary = _proj_box(13.39, 52.49, 13.41, 52.61)
    res = measure(ways, CFG, 25833, boundary=boundary)
    a = next(c for c in res.completeness if c.tier == "A")
    # clipped: 0.01 (width) of 0.02 -> 1/2; unclipped lengths would give 2/3
    assert a.share_with_width == pytest.approx(1 / 2, rel=0.02)


def test_way_outside_boundary_is_not_counted_in_n_ways():
    inside = WayRecord(1, TRACK, ((13.395, 52.5), (13.405, 52.5)))
    outside = WayRecord(2, TRACK, ((13.50, 52.5), (13.52, 52.5)))
    res = measure([inside, outside], CFG, 25833, boundary=_proj_box(13.39, 52.49, 13.41, 52.51))
    rows = [t for t in res.tier_lengths if t.tier == "A"]
    assert rows and all(t.n_ways == 1 for t in rows)
    only_out = measure([outside], CFG, 25833, boundary=_proj_box(13.39, 52.49, 13.41, 52.51))
    assert only_out.tier_lengths == []  # an all-outside tier gets no row, not 0 km with ways


# --- per-subarea attribution (M6) ---

CITY_BOX = (13.39, 52.49, 13.43, 52.51)


def _sub(slug, box):
    return SubareaPolygon(slug, slug.upper(), 1, _proj_box(*box), "0" * 64)


NORTH_SOUTH = [
    _sub("n", (13.38, 52.50, 13.44, 52.52)),  # overhangs the city: clipped to it
    _sub("s", (13.38, 52.48, 13.44, 52.50)),
]


def _attribute(ways, subareas, city_box=CITY_BOX):
    city = _proj_box(*city_box)
    result = measure(ways, CFG, 25833, boundary=city)
    return result, attribute_subareas(ways, result, CFG, 25833, city, subareas)


def _tier_map(rows):
    return {(t.tier, t.subtype, t.length_basis): t for t in rows}


def test_subareas_sum_to_the_city():
    ways = [
        WayRecord(1, TRACK, ((13.40, 52.495), (13.40, 52.505))),  # crosses the split
        WayRecord(
            2, {"highway": "primary", "cycleway:both": "track"}, ((13.41, 52.505), (13.42, 52.505))
        ),
        WayRecord(
            3,
            {"highway": "secondary", "cycleway:right": "lane"},
            ((13.41, 52.495), (13.42, 52.495)),
        ),
        WayRecord(4, {"highway": "residential"}, ((13.395, 52.492), (13.425, 52.508))),
        WayRecord(5, {"highway": "motorway"}, ((13.385, 52.497), (13.435, 52.497))),
    ]
    result, parts = _attribute(ways, NORTH_SOUTH)
    assert set(parts) == {"n", "s"}
    city_tiers = _tier_map(result.tier_lengths)
    assert {k[0] for k in city_tiers} >= {"A", "D"}  # not vacuous
    for key, row in city_tiers.items():
        total = sum(
            t.length_km
            for p in parts.values()
            for t in p.tier_lengths
            if t.tier == key[0] and t.subtype == key[1] and t.length_basis == key[2]
        )
        assert total == pytest.approx(row.length_km, abs=1e-9), key
    for r in result.road_lengths:
        total = sum(road_length(p, r.road_class) for p in parts.values())
        assert r.length_km > 0
        assert total == pytest.approx(r.length_km, abs=1e-9), r.road_class
    # the crossing way 1 counts in both subareas; way 2 (tier A) only in n
    n_ways = {
        s: _tier_map(p.tier_lengths)[("A", None, "per_side")].n_ways for s, p in parts.items()
    }
    assert n_ways == {"n": 2, "s": 1}
    check_subarea_sums(result, parts)
    assert compute_metrics(parts["n"], PRESETS)  # SubareaMeasure works as a MeasureResult


def test_dual_carriageway_halving_carries_into_subareas():
    a = WayRecord(
        1,
        {"highway": "primary", "oneway": "yes", "name": "X"},
        ((13.40, 52.505), (13.4147, 52.505)),
    )
    b = WayRecord(
        2,
        {"highway": "primary", "oneway": "yes", "name": "X"},
        ((13.4147, 52.50525), (13.40, 52.50525)),
    )
    result, parts = _attribute([a, b], NORTH_SOUTH)
    city = road_length(result, "main_excl_motorway")
    assert city == pytest.approx(road_length(result, "main_incl_motorway_raw") / 2, rel=1e-9)
    assert road_length(parts["n"], "main_excl_motorway") == pytest.approx(city, rel=1e-9)
    assert road_length(parts["n"], "main_incl_motorway_raw") == pytest.approx(2 * city, rel=1e-9)
    assert road_length(parts["s"], "main_excl_motorway") == 0


def test_uncovered_sliver_beyond_tolerance_fails():
    # subareas cover 13.39-13.4292 of the city's 13.39-13.43: 98 % of its area
    covering = [_sub("w", (13.38, 52.48, 13.4292, 52.52))]
    ways = [
        WayRecord(1, TRACK, ((13.40, 52.49), (13.40, 52.51))),
        WayRecord(2, TRACK, ((13.4296, 52.49), (13.4296, 52.51))),  # in the gap
    ]
    result, parts = _attribute(ways, covering)
    city_a = _tier_map(result.tier_lengths)[("A", None, "per_side")].length_km
    part_a = _tier_map(parts["w"].tier_lengths)[("A", None, "per_side")].length_km
    with pytest.raises(SubareaSumError) as exc:
        check_subarea_sums(result, parts)
    msg = str(exc.value)
    assert "'A'" in msg and f"{part_a:.3f}" in msg and f"{city_a:.3f}" in msg


def test_a_way_wholly_outside_every_subarea_counts_no_n_ways():
    covering = [_sub("w", (13.38, 52.48, 13.41, 52.52))]
    inside = WayRecord(1, TRACK, ((13.40, 52.495), (13.40, 52.505)))
    outside = WayRecord(2, TRACK, ((13.42, 52.495), (13.42, 52.505)))  # in the city, no subarea
    result, parts = _attribute([inside, outside], covering)
    assert all(t.n_ways == 2 for t in result.tier_lengths if t.tier == "A")
    rows = [t for t in parts["w"].tier_lengths if t.tier == "A"]
    assert rows and all(t.n_ways == 1 for t in rows)
    _, only_out = _attribute([outside], covering)
    assert only_out["w"].tier_lengths == []


def test_a_way_on_a_shared_edge_is_split_not_double_counted():
    on_edge = WayRecord(1, TRACK, ((13.41, 52.495), (13.41, 52.505)))
    (x0, y0), (x1, y1) = Projector(25833).line(on_edge.coords).coords
    # the shared edge is the way itself (exact in projected space), one side each
    west = SubareaPolygon(
        "w", "W", 1, Polygon([(x0, y0), (x1, y1), (x1 - 500, y1), (x0 - 500, y0)]), "0" * 64
    )
    east = SubareaPolygon(
        "e", "E", 1, Polygon([(x0, y0), (x1, y1), (x1 + 500, y1), (x0 + 500, y0)]), "0" * 64
    )
    result, parts = _attribute([on_edge], [west, east], city_box=(13.39, 52.49, 13.43, 52.51))
    city = _tier_map(result.tier_lengths)[("A", None, "per_side")].length_km
    assert city > 0
    halves = [_tier_map(p.tier_lengths)[("A", None, "per_side")].length_km for p in parts.values()]
    assert halves == [pytest.approx(city / 2, rel=1e-9)] * 2
    check_subarea_sums(result, parts)


def _scaled(result, parts, factor):
    """`parts` with every length multiplied by `factor` (a controlled deviation from the city)."""
    return {
        k: SubareaMeasure(
            [t.model_copy(update={"length_km": t.length_km * factor}) for t in p.tier_lengths],
            [r.model_copy(update={"length_km": r.length_km * factor}) for r in p.road_lengths],
        )
        for k, p in parts.items()
    }


def test_sum_check_tolerance_is_half_a_percent():
    ways = [WayRecord(1, TRACK, ((13.40, 52.495), (13.40, 52.505)))]
    result, parts = _attribute(ways, NORTH_SOUTH)
    check_subarea_sums(result, _scaled(result, parts, 0.997))  # 0.3 % short: passes
    check_subarea_sums(result, _scaled(result, parts, 1.003))
    for factor in (0.993, 1.007):  # 0.7 % off: fails
        with pytest.raises(SubareaSumError):
            check_subarea_sums(result, _scaled(result, parts, factor))
