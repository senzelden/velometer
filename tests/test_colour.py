import itertools

import pytest

from velometer.report import change, charts
from velometer.report.colour import ciede2000, contrast, delta, lab, simulate

LIGHT_BACKGROUNDS = ["#ffffff", "#fcfcfa"]  # --surface, --paper (light); Task 3 checks the tokens


def test_contrast_matches_wcag():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)
    assert contrast("#ffffff", "#767676") == contrast("#767676", "#ffffff")


@pytest.mark.parametrize(
    ("lab1", "lab2", "expected"),
    [  # Sharma, Wu & Dalal (2005), test pairs 1, 7, 17
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
        ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ],
)
def test_ciede2000_matches_the_reference_pairs(lab1, lab2, expected):
    assert ciede2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


def test_simulation_keeps_greys_and_merges_red_green():
    assert simulate("#808080", "deuteranopia") == "#808080"
    assert delta("#d62728", "#2ca02c", "deuteranopia") < delta("#d62728", "#2ca02c")


def test_the_tier_palette_follows_the_rule():
    tiers = charts.TIER_COLOURS
    assert len(tiers) == 5
    for c, bg in itertools.product(tiers, LIGHT_BACKGROUNDS):
        assert contrast(c, bg) >= 3.0, (c, bg)
    for vision in ("normal", "deuteranopia", "protanopia"):
        for a, b in itertools.combinations(tiers, 2):
            assert delta(a, b, vision) >= 20, (a, b, vision)
        for a, b in itertools.pairwise(tiers):
            assert delta(a, b, vision) >= 25, (a, b, vision)


@pytest.mark.parametrize("vision", ["normal", "deuteranopia", "protanopia"])
def test_the_series_palette_follows_the_rule(vision):
    series = charts.SERIES_COLOURS
    assert len(series) == 8
    for c, bg in itertools.product(series, LIGHT_BACKGROUNDS):
        assert contrast(c, bg) >= 3.0, (c, bg)
    for a, b in itertools.combinations(series, 2):
        assert delta(a, b, vision) >= 20, (a, b, vision)


def test_the_altair_charts_use_all_eight_series_colours():
    assert charts.CITY_COLOURS == charts.SERIES_COLOURS and len(charts.CITY_COLOURS) == 8


@pytest.mark.parametrize("vision", ["normal", "deuteranopia", "protanopia"])
def test_the_change_map_colours_follow_the_rule(vision):
    # the series rule, plus the pair a reader most needs to tell apart: gained versus lost
    colours = change.CATEGORY_COLOURS
    assert list(colours) == ["gained", "lost", "retiered", "redrawn"]
    for c, bg in itertools.product(colours.values(), LIGHT_BACKGROUNDS):
        assert contrast(c, bg) >= 3.0, (c, bg)
    for a, b in itertools.combinations(colours.values(), 2):
        assert delta(a, b, vision) >= 20, (a, b, vision)
    assert delta(colours["gained"], colours["lost"], vision) >= 25, vision
    assert "TIER_COLOURS" not in change.__dict__  # not the tier palette


def test_lab_puts_white_at_the_white_point():
    assert lab("#ffffff") == pytest.approx((100.0, 0.0, 0.0), abs=1e-6)
