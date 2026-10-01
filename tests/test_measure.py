from pathlib import Path

import pytest

from velometer.config import default_config_dir, load_classifier, load_presets
from velometer.pipeline.measure import compute_metrics, measure, road_length
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

FIX = Path(__file__).parent / "fixtures" / "measure"
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
PRESETS = load_presets(default_config_dir() / "presets.yaml")


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
    m = {x.preset: x.value for x in compute_metrics(result, PRESETS)}
    assert m["ours_headline"] == pytest.approx(200, rel=0.01)
    assert m["ecf_qecio"] == pytest.approx(100, rel=0.01)
    assert m["clean_cities_2025"] == pytest.approx(100, rel=0.01)


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
        {"area": "yes"},
        {"area": "no;yes"},
    ],
)
def test_private_or_area_roads_are_excluded_from_denominators_by_any_part(tags):
    way = WayRecord(1, {"highway": "primary", **tags}, ((13.4, 52.5), (13.4147, 52.5)))
    r = measure([way], CFG, 25833)
    assert road_length(r, "main_excl_motorway") == 0
    assert road_length(r, "all_public") == 0
