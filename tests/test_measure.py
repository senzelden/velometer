from pathlib import Path

import pytest
from shapely import MultiPolygon, Polygon

from velometer.config import Preset, default_config_dir, load_classifier, load_presets
from velometer.pipeline.geometry import Projector
from velometer.pipeline.measure import compute_metrics, measure, road_length, select_metric
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

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
