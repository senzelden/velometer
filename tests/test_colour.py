import itertools

import pytest

from velometer.report import change, charts
from velometer.report.colour import ciede2000, contrast, delta, simulate

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


def test_the_series_palette_follows_the_rule():
    series = charts.SERIES_COLOURS
    assert len(series) == 8
    for c, bg in itertools.product(series, LIGHT_BACKGROUNDS):
        assert contrast(c, bg) >= 3.0, (c, bg)
    for a, b in itertools.combinations(series, 2):
        assert delta(a, b) >= 20, (a, b)


def test_change_map_colours_do_not_follow_the_tier_palette():
    # spec decision 3: fixed at their M9 values, so the change PNGs need no re-render
    assert change.CATEGORY_COLOURS == {
        "gained": "#1baf7a",
        "lost": "#eb6834",
        "retiered": "#eda100",
        "redrawn": "#2a78d6",
    }
    assert "TIER_COLOURS" not in change.__dict__
