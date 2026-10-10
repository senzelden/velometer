import itertools
import re
from pathlib import Path

import pytest

from tests.test_app import (
    STATIC,
    _css_outside_tokens,
    _css_rules,
    _css_tokens,
    _dark_rules,
    _dark_tokens,
    client,  # noqa: F401 - the fixture
    setup,  # noqa: F401
)
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


def _rules():
    return _css_rules(_css_outside_tokens(_stylesheet()))


def _used(props, rules=None) -> set[str]:
    return {
        t
        for _, decls in (_rules() if rules is None else rules)
        for p, v in decls.items()
        if p in props
        for t in VAR.findall(v)
    }


def _backgrounds() -> set[str]:
    # the page and card grounds every text sits on, plus every background a rule sets. Marks
    # that hold no text (legend dots, key swatches, the story step bar) are drawn with `border`,
    # not `background`: they are graphics (3:1, the graphics test), not grounds for text. A
    # swatch drawn with `background` lands here, and every text token is then checked on it
    # --plate is the exception: it grounds the PNG map figures only (an image, no page text; the
    # caption sits outside the plate), so page text tokens are not read on it
    return (_used(BG_PROPS) - {"--plate"}) | {"--paper", "--surface", "--panel"}


# SVG text is painted with `fill`: a rule that targets chart text, by class name or because it
# sets a font, paints text with its fill, so that fill is a text colour (4.5:1)
SVG_TEXT = re.compile(
    r"(?:^|[\s.>])(?:text|tspan)\b|\.axis-t\b|\.ylab\b|\.el\b|\.mark-t\b|-label\b"
)


def _is_svg_text(sels, decls) -> bool:
    return any(SVG_TEXT.search(s) for s in sels) or any(p.startswith("font") for p in decls)


# rules whose `color` paints no text, by selector, each with the proof. An exempt selector must
# still exist and set a colour (test below), so the list cannot rot; the same token as `color`
# on any other rule is checked as text
TEXT_EXEMPT_RULES: dict[str, str] = {
    ".spark-mount": (
        '`color` only feeds currentColor: the mount (cities.html, `<span class="spark-mount" '
        'data-chart="sparkline">`) holds renderSparkline\'s SVG, a line and a dot drawn in '
        'currentColor (a graphic, 3:1), or emptyNote\'s `<p class="empty">`, whose own '
        "`.empty { color: var(--ink-2) }` wins (chart.js). No text is ever painted in it"
    ),
}


def _text_tokens() -> set[str]:
    rules = _rules()
    painted = [(sels, d) for sels, d in rules if not set(sels) <= TEXT_EXEMPT_RULES.keys()]
    svg_text = [(sels, d) for sels, d in rules if _is_svg_text(sels, d)]
    return _used(TEXT_PROPS, painted) | _used(("fill",), svg_text)


@pytest.mark.parametrize("theme", THEMES)
def test_every_text_token_reads_on_every_background(theme):
    tokens = _css_tokens(_stylesheet(), theme)
    bad = [
        (fg, bg, round(contrast(tokens[fg], tokens[bg]), 2))
        for fg, bg in itertools.product(sorted(_text_tokens()), sorted(_backgrounds()))
        if fg != bg and contrast(tokens[fg], tokens[bg]) < 4.5
    ]
    assert bad == []


def test_chart_text_painted_with_fill_is_text():
    # the axis labels are SVG text: their fill is held to 4.5:1, not the graphics 3:1
    assert {"--axis", "--ink-2", "--muted"} <= _text_tokens()
    assert _is_svg_text([".chart g.x"], {"font": "11px system-ui", "fill": "var(--x)"})
    assert _is_svg_text([".plan-svg .mapped-label"], {"fill": "var(--x)"})
    assert not _is_svg_text([".plan-svg .projects .bar"], {"fill": "var(--completed)"})


def test_text_exemptions_are_real_rules():
    for sel in TEXT_EXEMPT_RULES:
        assert any(sel in sels and "color" in d for sels, d in _rules()), sel


# where --panel is a ground. A new panel ground must be added here, and NOT_ON_PANEL re-argued
PANEL_GROUNDS = {"pre", ".tiermap", ".flag-item .rule", ".counts-table tr.covid th",
                 ".counts-table tr.covid td"}  # fmt: skip
# graphics that never sit on --panel. Of the grounds above, pre, the flag rule chip and the COVID
# rows hold text only; .tiermap is the Leaflet container, where tier lines, the boundary outline
# and the counter markers are drawn over the OSM tile layer that covers it (the panel shows only
# until the tiles load). Series and tier colours are drawn in chart cards (.panel, .sm-card,
# .chart: --surface) and on maps, never on a --panel ground
NOT_ON_PANEL = set(SERIES) | set(TIERS) | {"--outline", "--marker-fill"}


def test_the_panel_grounds_are_the_known_ones():
    found = {
        s
        for sels, d in _rules()
        for p, v in d.items()
        if p in BG_PROPS and "var(--panel)" in v
        for s in sels
    }
    assert found == PANEL_GROUNDS


def _graphics() -> set[str]:
    # gridlines, dividers and halos are decoration (WCAG 1.4.11 exempts them)
    # the change colours are exempt in light: they are fixed at their M9 values (decision 3) and
    # the key swatch beside each carries its text label; in dark they are held to 3:1 by
    # test_the_dark_change_colours_stand_apart_and_out
    return (
        _used(NONTEXT_PROPS) - {"--shadow", "--halo", "--grid", "--grid-2", *CHANGES}
        | set(SERIES) | set(TIERS)
        | {"--outline", "--focus", "--accent", "--flag", "--mapped", "--completed",
           "--control-border", "--marker-fill"}
    )  # fmt: skip


@pytest.mark.parametrize("theme", THEMES)
def test_graphics_stand_out_from_their_backgrounds(theme):
    tokens = _css_tokens(_stylesheet(), theme)
    bad = [
        (g, bg, round(contrast(tokens[g], tokens[bg]), 2))
        for g, bg in itertools.product(sorted(_graphics()), ("--paper", "--surface", "--panel"))
        if not (bg == "--panel" and g in NOT_ON_PANEL) and contrast(tokens[g], tokens[bg]) < 3.0
    ]
    assert bad == []


# form controls by selector: their boundary is what identifies them (WCAG 1.4.11), so it is a
# graphic at 3:1, never a decorative grid grey
CONTROL = re.compile(
    r"(?:^|[\s.>])(?:input|select|textarea|button)\b|\.chip\b|\.chip-link\b|-toggle\b"
    r"|\.city-filter\b|\.apply\b"
)
BORDER_PROPS = ("border", "border-color")


def test_form_control_borders_are_graphics():
    rules = [(sels, d) for sels, d in _rules() if any(CONTROL.search(s) for s in sels)]
    used = {t for _, d in rules for p, v in d.items() if p in BORDER_PROPS for t in VAR.findall(v)}
    assert used and used <= _graphics(), used - _graphics()
    for sel in (".city-filter", ".menu-toggle", ".compare-form select", ".filters-toggle",
                ".chip", ".chip-link", ".f-metric select"):  # fmt: skip
        border = [d["border"] for sels, d in rules if sel in sels and "border" in d]
        assert border and border[-1].endswith("var(--control-border)"), sel


@pytest.mark.parametrize("theme", THEMES)
def test_knock_outs_are_the_card_ground(theme):
    # the halo and the counter markers' rim cut marks out of the card they sit on
    t = _css_tokens(_stylesheet(), theme)
    assert t["--halo"] == t["--marker-stroke"] == t["--surface"]


def test_one_token_block_per_theme():
    css = re.sub(r"/\*.*?\*/", "", _stylesheet(), flags=re.S)
    assert len(re.findall(r"(?m)^:root\s*\{", css)) == 1
    # one dark token block; other dark media blocks hold rules (the tile filter), not tokens
    assert len(re.findall(r"prefers-color-scheme:\s*dark\)\s*\{\s*:root", css)) == 1
    assert len(re.findall(r":root\s*\{", css)) == 2


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


# ---------- colours the JS paints (static/js/theme.js reads the tokens) ----------

STATIC_DIR = Path(__file__).parents[1] / "src" / "velometer" / "app" / "static"
SVG_TEXT_EL = re.compile(r'svgEl\(\s*"(?:text|tspan)"\s*,\s*\{')
STYLE_TEXT = re.compile(r"\.style\.(?:color|fill)\s*=\s*([^;\n]+)")
JS_FILL = re.compile(r"(?<![\w-])fill:\s*([^,}]+)")
TOKEN_CALL = re.compile(r'^token\(\s*"(--[\w-]+)"\s*\)$')
JS_TOKEN = re.compile(r'token\(\s*"(--[\w-]+)"\s*\)')


def _js_sources() -> dict[str, str]:
    files = [*STATIC_DIR.glob("*.js"), *(STATIC_DIR / "js").glob("*.js")]
    return {f.name: f.read_text() for f in files}


def _braced(text: str, start: int) -> str:
    """The `{...}` object literal that opens at text[start - 1]."""
    depth, i = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[start : i - 1]


def _js_text_paints(text: str) -> list[str]:
    """Every expression the JS paints text with: the `fill` of an SVG text element it builds,
    and a colour it sets on an element's style. Text the JS builds without one is painted by
    the stylesheet, whose text colours the CSS tests above hold to 4.5:1."""
    paints = [m.group(1).strip() for m in STYLE_TEXT.finditer(text)]
    for m in SVG_TEXT_EL.finditer(text):
        paints += [f.group(1).strip() for f in JS_FILL.finditer(_braced(text, m.end()))]
    return paints


def test_js_paints_text_only_with_text_tokens():
    # the M7 carry: a series colour as end-label text read 3.1:1 on white. JS text is painted
    # by the stylesheet, or by one named token held to 4.5:1 on every ground in both themes; a
    # data-driven colour (a series, a tier) never paints text, it goes on a key mark beside it
    painted = {name: _js_text_paints(src) for name, src in _js_sources().items()}
    loose = {n: [p for p in ps if not TOKEN_CALL.match(p)] for n, ps in painted.items()}
    assert {n: ps for n, ps in loose.items() if ps} == {}
    used = {TOKEN_CALL.match(p).group(1) for ps in painted.values() for p in ps}
    for theme in THEMES:
        t = _css_tokens(_stylesheet(), theme)
        bad = [
            (fg, bg, round(contrast(t[fg], t[bg]), 2))
            for fg, bg in itertools.product(sorted(used), sorted(_backgrounds()))
            if contrast(t[fg], t[bg]) < 4.5
        ]
        assert bad == [], theme


def test_the_js_text_rule_sees_a_series_colour_as_text():
    src = 'g.appendChild(svgEl("text", { class: "el", x: 1, fill: it.s.colour ?? null }, "Aa"));'
    assert _js_text_paints(src) == ["it.s.colour ?? null"]
    assert _js_text_paints('svgEl("text", { class: "el", "fill-opacity": 1 }, "Aa")') == []
    assert _js_text_paints('svgEl("path", { fill: s.colour })') == []
    assert _js_text_paints("lab.style.color = colours[i];") == ["colours[i]"]
    assert _js_text_paints('svgEl("text", { fill: token("--ink") })') == ['token("--ink")']


def test_every_token_the_js_reads_is_defined_in_both_themes():
    # a missing token falls back to grey with a console error at run time (theme.js); this
    # catches it before: every token the JS names, and the families theme.js builds by number
    names = {n for src in _js_sources().values() for n in JS_TOKEN.findall(src)}
    names |= set(SERIES) | set(TIERS) | set(CHANGES)
    assert "--ctx" in names and "--outline" in names  # the scan sees the call sites
    for theme in THEMES:
        assert sorted(names - _css_tokens(_stylesheet(), theme).keys()) == [], theme


# --- maps in the dark (M10 decisions 3 and 4) ---


@pytest.fixture
def all_page_urls(client, fixture_db):  # noqa: F811
    from velometer.app import export

    urls = export.export_urls(fixture_db[3], client.app)
    return [u for u in urls if client.get(u).headers["content-type"].startswith("text/html")]


def test_every_map_png_sits_on_a_plate(client, all_page_urls):  # noqa: F811
    # light PNGs read as figures in the dark theme; the pages link them today, so this guards
    # any page that shows one inline
    assert all_page_urls
    for url in all_page_urls:
        html = client.get(url).text
        for img in re.finditer(r'<img[^>]+src="[^"]*/maps/[^"]+\.png"', html):
            before = html[: img.start()]
            assert before.rfind('<figure class="map-png') > before.rfind("</figure>"), url


def test_the_map_png_plate_is_a_light_ground_with_a_border():
    rule = {k: v for s, d in _rules() if "figure.map-png" in s or ".map-png" in s
            for k, v in d.items()}  # fmt: skip
    assert rule["background"] == "var(--plate)"
    assert "var(--grid-2)" in rule["border"]
    for theme in THEMES:  # the plate is light in both themes: the PNGs are drawn for white
        assert contrast(_css_tokens(_stylesheet(), theme)["--plate"], "#000000") > 12, theme


def test_the_dark_theme_darkens_the_tiles_only():
    rules = _dark_rules(_stylesheet())
    tiles = [d for s, d in rules if any("tiermap-tiles" in x for x in s)]
    assert tiles and "invert" in tiles[0].get("filter", "")
    assert not any("leaflet-overlay-pane" in x or "canvas" in x for s, _ in rules for x in s)
    assert not any("img" in x for s, _ in rules for x in s if "tiermap-tiles" in x)  # no seams


def test_every_map_tile_layer_uses_the_dark_filtered_class():
    static = STATIC
    for js in ("map.js", "changemap.js", "countermap.js"):
        assert "className: cfg.tile_class" in (static / js).read_text(), js


def test_key_swatches_have_a_css_fill_without_js():
    # the swatch <rect>s carry no fill until JS sets the attribute: black without it. The
    # fallback applies only while the attribute is absent, so JS (or an inline style) wins
    rules = [(s, d) for s, d in _rules() if any("swatch" in x for x in s)]
    css = _stylesheet()
    keys = {
        "A": "--tier-a", "B": "--tier-b", "C": "--tier-c", "D": "--tier-d", "E": "--tier-e",
        **{k: f"--change-{k}" for k in change.CATEGORY_COLOURS},
    }  # fmt: skip
    for key, token in keys.items():
        sel = f'.swatch[data-key="{key}"] rect:not([fill])'
        found = [d for s, d in rules if sel in s]
        assert found and found[0]["fill"] == f"var({token})", key
    assert any(".swatch rect:not([fill])" in s for s, _ in rules)
    assert ".swatch rect {" not in css  # an unconditional rule would beat the fill attribute
    for token in TIERS:  # the tier fills are held to 3:1 by the graphics test (change: see there)
        assert token in _graphics(), token


def test_map_tiles_carry_no_border():
    # the global `img` border would frame every 256px tile: a 2px seam grid across the map
    assert any(s == [".leaflet-container img"] and d.get("border") == "0" for s, d in _rules())
    assert any(s == [".map-png img"] and d.get("border") == "0" for s, d in _rules())
