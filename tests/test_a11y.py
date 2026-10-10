import itertools
import re

import pytest

from tests.test_app import _css_outside_tokens, _css_rules, _css_tokens, _dark_tokens
from tests.test_app_m8 import _stylesheet
from velometer.report import change, charts
from velometer.report.colour import contrast, delta

THEMES = ("light", "dark")
VISIONS = ("normal", "deuteranopia", "protanopia")
TEXT_PROPS = ("color",)
BG_PROPS = ("background", "background-color")
NONTEXT_PROPS = ("border", "border-color", "border-top", "border-bottom", "border-left",
                 "border-right", "outline", "outline-color", "stroke", "fill",
                 "box-shadow")  # fmt: skip
VAR = re.compile(r"var\((--[\w-]+)\)")
TIERS = [f"--tier-{t}" for t in "abcde"]
SERIES = [f"--series-{i}" for i in range(1, 9)]
CHANGES = [f"--change-{k}" for k in change.CATEGORY_COLOURS]


def _used(props) -> set[str]:
    return {
        t
        for _, decls in _css_rules(_css_outside_tokens(_stylesheet()))
        for p, v in decls.items()
        if p in props
        for t in VAR.findall(v)
    }


def _backgrounds() -> set[str]:
    # the page and card grounds every text sits on, plus every background a rule sets
    return _used(BG_PROPS) | {"--paper", "--surface", "--panel"}


@pytest.mark.parametrize("theme", THEMES)
def test_every_text_token_reads_on_every_background(theme):
    tokens = _css_tokens(_stylesheet(), theme)
    bad = [
        (fg, bg, round(contrast(tokens[fg], tokens[bg]), 2))
        for fg, bg in itertools.product(sorted(_used(TEXT_PROPS)), sorted(_backgrounds()))
        if fg != bg and contrast(tokens[fg], tokens[bg]) < 4.5 and (fg, bg) not in TEXT_EXEMPT
    ]
    assert bad == []


# (text token, background token) pairs that never meet in a rendered page, each with its reason.
# A pair listed here must still exist in the stylesheet (the test below), so the list cannot rot.
_SPARK = (
    "`.spark-mount` sets `color` only for currentColor: the mount (cities.html, "
    '`<span class="spark-mount" data-chart="sparkline">`) holds renderSparkline\'s SVG, a line and '
    'a dot drawn in currentColor (a graphic, 3:1), or emptyNote\'s `<p class="empty">`, whose '
    "own `.empty { color: var(--ink-2) }` wins (chart.js). No text is ever painted in it"
)
TEXT_EXEMPT: dict[tuple[str, str], str] = {
    ("--series-1", bg): _SPARK for bg in ("--paper", "--surface", "--panel", "--accent-bg")
}


def test_text_exemptions_name_real_tokens():
    tokens = _css_tokens(_stylesheet())
    assert all(fg in tokens and bg in tokens for fg, bg in TEXT_EXEMPT)
    # an exemption whose token no longer sets a text colour is stale
    assert {fg for fg, _ in TEXT_EXEMPT} <= _used(TEXT_PROPS)


@pytest.mark.parametrize("theme", THEMES)
def test_graphics_stand_out_from_their_backgrounds(theme):
    tokens = _css_tokens(_stylesheet(), theme)
    graphics = (
        _used(NONTEXT_PROPS) - {"--shadow", "--halo", "--grid", "--grid-2"}
        | set(SERIES) | set(TIERS)
        | {"--outline", "--focus", "--accent", "--flag", "--mapped", "--completed"}
    )  # fmt: skip
    # gridlines and halos are decoration (WCAG 1.4.11 exempts them)
    bad = [
        (g, bg, round(contrast(tokens[g], tokens[bg]), 2))
        for g, bg in itertools.product(sorted(graphics), ("--paper", "--surface"))
        if contrast(tokens[g], tokens[bg]) < 3.0
    ]
    assert bad == []


def test_the_light_tokens_are_the_python_palettes():
    t = _css_tokens(_stylesheet(), "light")
    assert [t[x] for x in TIERS] == charts.TIER_COLOURS
    assert [t[x] for x in SERIES] == charts.SERIES_COLOURS
    assert t["--outline"] == charts.OUTLINE
    assert {k: t[f"--change-{k}"] for k in change.CATEGORY_COLOURS} == change.CATEGORY_COLOURS


def test_the_dark_tier_palette_follows_the_rule():
    # spec decision 3 on the dark grounds: the light rule, with the dark tokens (light ones are
    # tests/test_colour.py's). 3:1 is the graphics test above
    t = _css_tokens(_stylesheet(), "dark")
    tiers = [t[x] for x in TIERS]
    for vision in VISIONS:
        for a, b in itertools.combinations(tiers, 2):
            assert delta(a, b, vision) >= 20, (a, b, vision)
        for a, b in itertools.pairwise(tiers):
            assert delta(a, b, vision) >= 25, (a, b, vision)


def test_the_dark_series_palette_follows_the_rule():
    t = _css_tokens(_stylesheet(), "dark")
    for a, b in itertools.combinations([t[x] for x in SERIES], 2):
        assert delta(a, b) >= 20, (a, b)


def test_the_dark_change_colours_stand_apart_and_out():
    # the light change colours are fixed at their M9 values (decision 3); the dark ones are
    # free, so they follow the series rule: 3:1 on the dark grounds, pairwise >= Delta E 20
    t = _css_tokens(_stylesheet(), "dark")
    for c, bg in itertools.product(CHANGES, ("--paper", "--surface")):
        assert contrast(t[c], t[bg]) >= 3.0, (c, bg)
    for a, b in itertools.combinations(CHANGES, 2):
        assert delta(t[a], t[b]) >= 20, (a, b)


def test_every_colour_token_has_a_dark_value():
    light, dark = _css_tokens(_stylesheet(), "light"), _dark_tokens(_stylesheet())
    colours = {k for k in light if k.startswith("--") and not k.startswith(("--serif", "--mono"))}
    assert sorted(colours - dark.keys()) == []


def test_the_page_declares_both_schemes():
    # the first :root rule is the light token block (the dark block's :root comes later)
    root = next(d for s, d in _css_rules(_stylesheet()) if s == [":root"])
    assert root.get("color-scheme") == "light dark"
