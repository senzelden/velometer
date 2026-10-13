import itertools
import re
from html.parser import HTMLParser
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
    subarea_setup,  # noqa: F401 - the fixture
)
from tests.test_app_m8 import _stylesheet
from velometer import i18n
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
def all_page_urls(page_site):
    """The HTML URLs of the export (both language trees); their bodies are `page_site.html`."""
    return list(page_site.html)


def test_every_map_png_sits_on_a_plate(all_page_urls, page_site):  # noqa: F811
    # light PNGs read as figures in the dark theme; the pages link them today, so this guards
    # any page that shows one inline
    assert all_page_urls
    for url in all_page_urls:
        html = page_site.html[url]
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
    # the counter markers (pane and icons) keep their own colours: no dark rule may touch them
    assert not any(
        "leaflet-marker-pane" in x or "leaflet-marker-icon" in x for s, _ in rules for x in s
    )
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


def test_map_tiles_carry_no_border():
    # the global `img` border would frame every 256px tile: a 2px seam grid across the map
    assert any(s == [".leaflet-container img"] and d.get("border") == "0" for s, d in _rules())
    assert any(s == [".map-png img"] and d.get("border") == "0" for s, d in _rules())


# ---------- phone tables stack into labelled cards (M10 decision 5) ----------

VOID = {"br", "img", "hr", "input", "meta", "link", "col", "wbr", "source", "area", "base"}


class _Tables(HTMLParser):
    """Every <table> outside a `.prose` ancestor: its classes, its header texts and, per body
    row, the (data-label, column index, tag) of every cell. A cell's column is where its
    colspan-aware position starts."""

    def __init__(self):
        super().__init__()
        self.tables: list[dict] = []
        self._open: list[tuple[str, bool]] = []  # (tag, carries the prose class)
        self._t = self._row = None
        self._in_body = self._in_th = False
        self._col = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in VOID:
            self._open.append((tag, "prose" in (a.get("class") or "").split()))
        if tag == "table":
            prose = any(p for _, p in self._open)
            self._t = {"cls": (a.get("class") or "").split(), "heads": [], "rows": []}
            if not prose:
                self.tables.append(self._t)
        elif self._t is None:
            return
        elif tag == "tbody":
            self._in_body = True
        elif tag == "tr" and self._in_body:
            self._row, self._col = [], 0
            self._t["rows"].append(self._row)
        elif tag == "th" and not self._in_body:
            self._in_th = True
            self._t["heads"].append("")
        elif tag in ("td", "th") and self._row is not None:
            self._row.append((a.get("data-label"), self._col, tag))
            self._col += int(a.get("colspan") or 1)

    def handle_endtag(self, tag):
        while tag not in VOID and self._open:  # unclosed <p>/<li> never occur in our templates
            if self._open.pop()[0] == tag:
                break
        if tag == "table":
            self._t = self._row = None
            self._in_body = False
        elif tag == "th":
            self._in_th = False
        elif tag == "tbody":
            self._in_body = False

    def handle_data(self, data):
        if self._in_th and self._t is not None:
            self._t["heads"][-1] += data


def _stack_violations(html: str) -> tuple[int, list]:
    p = _Tables()
    p.feed(html)
    bad = []
    for t in p.tables:
        heads = [" ".join(h.split()) for h in t["heads"]]
        if "stack" not in t["cls"]:
            bad.append(("not stacked", t["cls"], heads))
        for row in t["rows"]:
            for label, col, tag in row:
                if col >= len(heads) or label != heads[col]:
                    bad.append(("label", label, col, tag, heads))
    return len(p.tables), bad


def test_every_data_table_stacks_with_labels(all_page_urls, page_site):  # noqa: F811
    # spec decision 5: data tables outside prose stack; every body cell, row header included,
    # names its column with data-label equal to that column's header text
    seen = 0
    for url in all_page_urls:
        n, bad = _stack_violations(page_site.html[url])
        seen += n
        assert not bad, (url, bad[:3])
    assert seen > 10  # the parser found the tables at all


def test_the_stack_check_catches_a_missing_or_wrong_label():
    ok = ('<table class="stack"><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr>'
          '<td data-label="A">1</td><td data-label="B">2</td></tr></tbody></table>')  # fmt: skip
    assert _stack_violations(ok) == (1, [])
    assert _stack_violations(ok.replace(' data-label="B"', ""))[1]
    assert _stack_violations(ok.replace('"B">2', '"A">2'))[1]
    assert _stack_violations(ok.replace('class="stack"', ""))[1]
    prose = f'<div class="prose">{ok.replace("stack", "x")}</div>'
    assert _stack_violations(prose) == (0, [])  # prose tables scroll instead


def test_a_colspan_cell_is_labelled_by_the_column_it_starts_in():
    html = ('<table class="stack"><thead><tr><th>A</th><th>B</th><th>C</th></tr></thead><tbody>'
            '<tr><td data-label="A">1</td><td colspan="2" data-label="B">n/a</td></tr>'
            "</tbody></table>")  # fmt: skip
    assert _stack_violations(html) == (1, [])


def test_the_markdown_change_table_stacks_with_labels(subarea_setup):  # noqa: F811
    # the Bezirk change table is rendered from markdown but is a data table (decision 5): it
    # stacks, outside any `.prose` box, each cell labelled with its column header
    from tests.test_app import CONTENT, _client, _latest_lau_run, _write_change
    from velometer.app.main import create_app

    db_path, cfg, maps, docs = subarea_setup
    _write_change(maps, docs, run_to=_latest_lau_run(db_path, cfg))
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        html = c.get("/city/berlin/bezirke").text
    section = html.split("<h3>Mapped change")[1]
    assert '<table class="stack">' in section and 'class="prose"' not in section
    assert "data-label=" in section.split("<tbody>")[1]
    n, bad = _stack_violations(html)
    assert n >= 3 and not bad


def _phone_rules():
    css = _css_outside_tokens(_stylesheet())
    blocks = re.findall(r"@media \(max-width: 600px\) \{(.*?)\n\}", css, re.S)
    return [r for b in blocks for r in _css_rules(b)]


def test_the_stack_pattern_is_one_phone_rule_set():
    rules = _phone_rules()
    sel = {s for ss, _ in rules for s in ss}

    def decl(selector):
        return {k: v for ss, d in rules if selector in ss for k, v in d.items()}

    # the header row stays for screen readers: visually hidden, not display:none
    head = decl("table.stack thead")
    assert head.get("display") != "none" and head.get("position") == "absolute"
    # each row is a bordered card, each cell a block that prints its column name first
    assert "border" in decl("table.stack tr") and "padding" in decl("table.stack tr")
    assert decl("table.stack td")["display"] == "block"
    assert decl("table.stack td::before")["content"] == "attr(data-label)"
    assert decl("table.stack td.num")["text-align"] == "right"  # numbers stay right-aligned
    # the per-table phone rules this pattern replaced are gone
    assert not {s for s in sel if s.startswith((".diffs", ".plans", ".plan-docs"))}


def test_the_compare_sort_buttons_stay_visible_on_phones():
    # the compare table's header holds focusable sort buttons: below 600 px it must not be
    # clipped like the label-only headers of the other stacking tables (WCAG 2.4.7)
    rules = _phone_rules()
    decl: dict[str, str] = {}
    for ss, d in rules:
        if ".compare-js .compare-table.stack thead" in ss:
            decl.update(d)
    assert decl, "no phone rule keeps the compare header on screen"
    assert decl["position"] == "static" and decl["overflow"] == "visible"
    assert decl["clip"] == "auto" and decl["width"] == "auto" and decl["height"] == "auto"
    assert decl["display"] == "block"  # a table-header-group would shrink to its 1px children
    row = {k: v for ss, d in rules if ".compare-js .compare-table.stack thead tr" in ss
           for k, v in d.items()}  # fmt: skip
    assert row["display"] == "flex" and row["flex-wrap"] == "wrap"
    assert row["overflow"] == "visible" and row["height"] == "auto" and row["width"] == "auto"
    cell = {k: v for ss, d in rules if ".compare-js .compare-table.stack thead th" in ss
            for k, v in d.items()}  # fmt: skip
    assert cell["overflow"] == "visible" and cell["width"] == "auto"


def test_compare_js_builds_a_stacking_labelled_table_on_every_render():
    # the table is rebuilt by drawTable on each render, and a sort click re-renders: so the class
    # and the labelling must be in drawTable itself, labelling after the rows exist and before
    # the table goes into the page
    js = (STATIC / "js" / "compare.js").read_text()
    js = re.sub(r"/\*.*?\*/|//[^\n]*", "", js, flags=re.S)  # a comment must not satisfy it
    assert 'import { labelCells } from "./table.js"' in js
    body = js[js.index("function drawTable") :]
    body = body[: body.index("\nfunction ", 10)]
    assert 'el("table", { class: "compare-table stack" })' in body
    assert body.index("table.append(tbody)") < body.index("labelCells(table)")
    assert body.index("labelCells(table)") < body.index("out.table.replaceChildren(")
    render = js[js.index("function render(") :]
    assert "drawTable(" in render[: render.index("\n}\n")]  # render, which a sort click calls


def test_the_figures_cards_align_ours_with_theirs_and_gap():
    # in a card the three figures read as a column: Ours is right-aligned like Theirs and Gap
    rules = _phone_rules()
    ours = {k: v for ss, d in rules if "table.diffs td:nth-child(4)" in ss for k, v in d.items()}
    assert ours.get("text-align") == "right"
    assert any("table.diffs td:nth-child(4)::before" in ss for ss, _ in rules)
    assert _stack_violations(
        '<table class="diffs stack"><thead><tr><th>Source</th><th>Figure</th><th>Theirs</th>'
        '<th>Ours</th></tr></thead><tbody></tbody></table>'
    ) == (1, [])  # fmt: skip


# ---- Task 7: page structure ----


def _split_fragments(urls):
    """(pages, panels): the city panels are layout-less fragments, fetched by panel.js."""
    return [u for u in urls if not u.endswith("/panel")], [u for u in urls if u.endswith("/panel")]


def test_every_page_has_a_skip_link_main_and_live_region(all_page_urls, page_site):  # noqa: F811
    pages, _ = _split_fragments(all_page_urls)
    assert pages
    for url in pages:
        html = page_site.html[url]
        body = html.split("<body>", 1)[1]
        first = re.search(r"<(a|button|input|select|textarea)\b[^>]*>", body)
        assert first and 'class="skip"' in first.group(0) and 'href="#main"' in first.group(0), url
        assert '<main id="main"' in html, url
        assert 'id="live"' in html and 'aria-live="polite"' in html, url
        assert html.rfind('id="live"') > html.rfind("</main>"), url  # outside main, before </body>


def test_one_h1_and_no_skipped_levels(all_page_urls, page_site):  # noqa: F811
    pages, panels = _split_fragments(all_page_urls)
    assert panels
    for url in [*pages, *panels]:
        panel = url.endswith("/panel")
        levels = [int(n) for n in re.findall(r"<h([1-6])\b", page_site.html[url])]
        if not panel:
            assert levels.count(1) == 1, url
        prev = 1 if panel else 0  # a panel sits under compare's h2 title, so it starts at h2
        for lv in levels:
            assert lv <= prev + 1, (url, levels)
            prev = lv


def test_the_404_page_has_the_heading_block_of_other_pages(client):  # noqa: F811
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert 'class="crumbs"' in r.text
    assert re.search(r"<h1>[^<]+</h1>\s*<p class=\"dek\">", r.text)


def test_focus_is_always_visible():
    rules = _rules()
    focus = [d for s, d in rules if any(":focus-visible" in x for x in s)]
    assert any("var(--focus)" in d.get("outline", "") for d in focus)
    # no rule, for any element (compare's sort buttons included), removes the outline on focus
    assert not any(
        d.get("outline") in ("none", "0") or d.get("outline-style") == "none"
        for s, d in rules
        if any(":focus" in x for x in s)
    )
    assert not any(
        d.get("outline") in ("none", "0") for s, d in rules if any("button" in x for x in s)
    )


def test_skip_link_is_hidden_until_focused_and_visually_hidden_exists():
    rules = _rules()
    skip = {k: v for s, d in rules if ".skip" in s for k, v in d.items()}
    assert skip.get("position") in ("absolute", "fixed")
    shown = [d for s, d in rules if ".skip:focus" in s or ".skip:focus-visible" in s]
    assert shown
    assert any(s == [".visually-hidden"] or ".visually-hidden" in s for s, _ in rules)


class _Scrolls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []  # (tag, attrs) of every sideways-scrolling region
        self.depth_prose = 0
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag not in ("br", "img", "meta", "link", "input", "hr"):
            self._stack.append("prose" in classes)
            self.depth_prose += "prose" in classes
        if "scroll" in classes or (tag == "table" and self.depth_prose):
            self.found.append((tag, a))

    def handle_endtag(self, tag):
        if self._stack:
            self.depth_prose -= self._stack.pop()


def test_every_sideways_scrolling_region_is_focusable_and_named(all_page_urls, page_site):  # noqa: F811
    seen = 0
    for url in all_page_urls:  # panels included: they are in the export
        p = _Scrolls()
        p.feed(page_site.html[url])
        for tag, a in p.found:
            seen += 1
            assert a.get("tabindex") == "0", (url, tag, a)
            assert (a.get("aria-label") or "").strip() or a.get("aria-labelledby"), (url, tag, a)
            if tag == "div":
                assert a.get("role") == "region", (url, a)
    assert seen > 20


def test_prose_tables_are_scroll_regions_too(client):  # noqa: F811
    html = client.get("/methodology").text
    assert "<table" in html
    p = _Scrolls()
    p.feed(html)
    assert any(t == "table" for t, _ in p.found)


# ---- Task 7 fix round 1: the scroll-region post-process, and named groups ----

from velometer.app.regions import name_scroll_regions  # noqa: E402


def test_a_scroll_wrapper_is_matched_by_class_token_in_any_attribute_order():
    for tag in (
        '<div data-x="1" class="wide scroll">',
        '<div id="a" class="scroll" hidden>',
        '<div class="scroll wide">',
    ):
        out = name_scroll_regions(f"<h2>Heads</h2>{tag}<table></table></div>")
        assert 'tabindex="0"' in out.split("<table")[0], tag
        assert 'role="region"' in out and 'aria-label="Heads"' in out, tag
    assert "tabindex" not in name_scroll_regions('<div class="scrolled">x</div>')
    assert "tabindex" not in name_scroll_regions('<div class="no-scroll">x</div>')


def test_a_wrapper_is_never_named_by_a_caption_outside_it():
    page = (
        '<h2>Above</h2><div class="scroll"><p>no table here</p></div>'
        "<table><caption>Later table</caption></table>"
    )
    out = name_scroll_regions(page)
    assert 'aria-label="Above"' in out and 'Later table"' not in out.split("</div>")[0]
    bare = name_scroll_regions('<div class="scroll"><p>x</p></div>')  # no heading at all
    assert re.search(r'aria-label="[^"]+"', bare)
    inner = name_scroll_regions(
        '<h2>Above</h2><div class="scroll"><table><caption>Inside</caption></table></div>'
    )
    assert 'aria-label="Inside"' in inner


def test_a_table_inside_a_wrapper_gets_no_tab_stop_of_its_own():
    out = name_scroll_regions(
        '<h2>H</h2><div class="scroll"><table><caption>C</caption></table></div>'
        "<table><caption>Prose</caption></table>"
    )
    assert out.count('tabindex="0"') == 2  # the wrapper and the one table outside it
    inside = out.split("</div>")[0]
    assert inside.count('tabindex="0"') == 1
    nested = name_scroll_regions('<div class="scroll"><div>x</div><table></table></div>')
    assert nested.count('tabindex="0"') == 1  # a nested div does not end the wrapper early


class _Groups(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.names, self.groups = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if "grp-name" in (a.get("class") or "").split():
            self.names.append(a.get("id"))
        if a.get("role") == "group" and a.get("aria-labelledby"):
            self.groups.append(a["aria-labelledby"])


def test_every_group_label_labels_a_group_and_ids_are_unique(all_page_urls, page_site):  # noqa: F811
    seen = 0
    for url in all_page_urls:
        p = _Groups()
        p.feed(page_site.html[url])
        assert len(p.ids) == len(set(p.ids)), url
        for name_id in p.names:
            seen += 1
            assert name_id and name_id in p.groups, (url, name_id)
    assert seen > 5


# --- content semantics (M10 spec decision 6): a table behind every chart, not colour alone ---
class _Charts(HTMLParser):
    """Every element with the class token `chart`, and the ids that name a table: the table's
    own, an ancestor's (a details block), or the id of its summary or caption."""

    def __init__(self):
        super().__init__()
        self.charts: list[dict] = []
        self.table_ids: set[str] = set()
        self._open: list[list] = []  # [tag, ids, holds a table]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "chart" in (a.get("class") or "").split():
            self.charts.append(a)
        if tag in VOID:
            return
        ids = {a["id"]} if a.get("id") else set()
        if tag in ("summary", "caption") and self._open:
            self._open[-1][1] |= ids  # the id of a summary or caption names its parent
        self._open.append([tag, ids, tag == "table"])

    def handle_endtag(self, tag):
        while tag not in VOID and self._open:
            t, ids, has_table = self._open.pop()
            if has_table:
                self.table_ids |= ids
                if self._open:
                    self._open[-1][2] = True
            if t == tag:
                break


def _chart_gaps(html: str) -> tuple[int, list]:
    p = _Charts()
    p.feed(html)
    bad = []
    for a in p.charts:
        ref = a.get("aria-describedby")
        if not ref:
            bad.append(("no aria-describedby", a))
        elif ref not in p.table_ids:
            bad.append(("describedby names no table", ref, a))
    return len(p.charts), bad


def test_every_chart_has_its_data_in_the_page(all_page_urls, page_site):  # noqa: F811
    seen = 0
    for url in all_page_urls:
        n, bad = _chart_gaps(page_site.html[url])
        seen += n
        assert not bad, (url, bad[:2])
    assert seen > 8  # the parser found the charts at all


def test_the_chart_check_catches_a_chart_without_its_table():
    ok = ('<div class="chart" aria-describedby="t"></div>'
          '<details id="t"><table><tr><td>1</td></tr></table></details>')  # fmt: skip
    assert _chart_gaps(ok) == (1, [])
    summed = (
        '<div class="chart" aria-describedby="s"></div><details><summary id="s">T</summary>'
        "<div><table></table></div></details>"
    )
    assert _chart_gaps(summed) == (1, [])
    assert _chart_gaps(summed.replace("<table></table>", ""))[1]  # a summary of nothing
    captioned = (
        '<div class="chart" aria-describedby="c"></div><table><caption id="c">T</caption></table>'
    )
    assert _chart_gaps(captioned) == (1, [])
    assert _chart_gaps(ok.replace(' aria-describedby="t"', ""))[1]  # no link
    assert _chart_gaps(ok.replace("<table>", "<ul>").replace("</table>", "</ul>"))[1]  # no table
    assert _chart_gaps(ok.replace('id="t"', 'id="u"'))[1]  # the link points nowhere
    assert _chart_gaps(
        '<div class="chart plan-chart" aria-describedby="t"></div><table id="t"></table>'
    ) == (1, [])  # a table with the id, any other class on the chart
    assert _chart_gaps('<span class="spark-mount" data-chart="sparkline"></span>') == (0, [])


FLAG_WORDS = "|".join(
    re.escape(text)
    for lang in ("en", "de")
    for text in (
        i18n.t(lang, "table.flagged"),
        f'data-label="{i18n.t(lang, "table.flagged_col")}"',
        i18n.t(lang, "page.plans.suspect"),
    )
)


def test_flagged_rows_carry_the_flag_mark_not_only_the_colour(all_page_urls, page_site):  # noqa: F811
    rows = 0
    for url in all_page_urls:
        html = page_site.html[url]
        for row in re.findall(r'<tr class="[^"]*\bflagged\b[^"]*"[^>]*>(.*?)</tr>', html, re.S):
            rows += 1
            assert 'class="flagmark"' in row and "⚑" in row, (url, row[:120])
            # and said to a screen reader: in words, or by a cell headed "Flagged" / a status, in
            # the page's language
            assert re.search(FLAG_WORDS, row), (url, row[:120])
    assert rows  # the fixtures have flagged rows


def test_every_up_and_down_value_carries_a_sign(all_page_urls, page_site):  # noqa: F811
    seen = 0
    for url in all_page_urls:
        html = page_site.html[url]
        for m in re.finditer(r'class="[^"]*\b(?:up|down)\b[^"]*"[^>]*>\s*([^<\s][^<]*)<', html):
            seen += 1
            assert m.group(1).strip()[0] in "+−-" or m.group(1).strip() == "n/a", (url, m[0])
    assert seen


def test_a_flagged_year_in_the_overview_chart_table_has_the_mark(client):  # noqa: F811
    html = client.get("/").text
    block = html[html.index('data-chart="overview-lines"') :]
    table = block[block.index("<table") : block.index("</table>")]
    assert "⚑" in table and "stack" in table and 'data-label="' in table


def test_the_tier_chart_names_every_tier_in_a_visible_key():
    # chart.js renderTiers draws a legend chip per tier layer; the node test proves it renders
    src = (STATIC / "js" / "chart.js").read_text()
    assert 'legend.className = "legend"' in src and "layer.name" in src


def test_the_tier_map_popup_names_the_tier_of_the_side():
    # the side's tier opens the popup, by its full name ("A separated track"), not a colour
    src = (STATIC / "map.js").read_text()
    popup = src[src.index("function popup(p)") : src.index("function checked")]
    head = "\n".join(
        ln for ln in popup[: popup.index("var dl")].splitlines() if not ln.strip().startswith("//")
    )
    assert "cfg.labels[p.tier]" in head and "tiermap-popup-tier" in head


def test_the_tier_names_are_the_popup_labels(client):  # noqa: F811
    import json

    html = client.get("/city/berlin/tiers").text
    cfg = json.loads(re.search(r'id="tiermap-config">(.*?)</script>', html, re.S).group(1))
    assert all(re.match(rf"{t} \w", cfg["labels"][t]) for t in "ABCDE")


def test_the_story_aside_table_is_compact_and_wraps_so_it_never_scrolls_sideways():
    # decision 5: only prose tables scroll sideways. The aside box is 18rem wide, so its table
    # is set small, full width, with cells that may wrap (render pass: no overflow at 1280/390/320)
    rules = {k: v for sels, d in _rules() if ".story-aside table" in sels for k, v in d.items()}
    assert rules.get("width") == "100%" and float(rules["font-size"].removesuffix("rem")) <= 0.8
    cells = {k: v for sels, d in _rules() if ".story-aside td.num" in sels for k, v in d.items()}
    assert cells.get("white-space") == "normal" and cells.get("min-width") == "0"


def test_stack_table_labels_are_escaped_exactly_once():
    from velometer.app.main import _md, _stack_table

    out = str(_stack_table(_md("| A & B | C < D |\n|---|---|\n| 1 | 2 |\n")))
    assert 'data-label="A &amp; B"' in out and 'data-label="C &lt; D"' in out
    assert "&amp;amp;" not in out and "&amp;lt;" not in out


def test_the_compare_sort_bar_has_a_visible_caption_tied_to_the_table():
    js = re.sub(r"/\*.*?\*/|//[^\n]*", "", (STATIC / "js" / "compare.js").read_text(), flags=re.S)
    body = js[js.index("function drawTable") :]
    body = body[: body.index("\nfunction ", 10)]
    assert 't("js.compare.sort_by")' in body and 'class: "sort-caption"' in body
    assert "describeSort(table)" in body  # described by it only where it is on screen
    assert "out.table.replaceChildren(caption, table)" in body  # the caption sits with the table
    rules = _css_rules(_stylesheet())
    plain = {k: v for s, d in rules if s == [".sort-caption"] for k, v in d.items()}
    assert plain.get("display") == "none"  # wide screens show the real header instead
    phone = {k: v for s, d in rules if s == [".compare-js .sort-caption"] for k, v in d.items()}
    assert phone.get("display") == "block"  # not visually hidden: sighted readers need it
    assert "clip" not in phone and "width" not in phone


def test_column_heads_may_wrap_so_a_wide_table_fits_its_box():
    # a long head ("Ours: Clean Cities method (n=21)") must not set its column's width: with
    # nowrap heads the ranks, presets and story tables spilled out of their box at 1280 px
    rules = _css_rules(_stylesheet())
    wrap = {s for s, d in rules if d.get("white-space") == "normal" for s in s}
    assert "thead th" in wrap and "thead th.num" in wrap  # the .num rule is more specific


def test_sorting_a_compare_column_puts_focus_back_on_its_button():
    # drawTable rebuilds the table, so the pressed header is a new element: the click handler
    # must refocus the one with the same key (found by the keyboard pass: focus fell to <body>)
    js = re.sub(r"/\*.*?\*/|//[^\n]*", "", (STATIC / "js" / "compare.js").read_text(), flags=re.S)
    body = js[js.index("function drawTable") :]
    body = body[: body.index("\nfunction ", 10)]
    assert '"data-key": key' in body
    handler = body[body.index('addEventListener("click"') :]
    assert handler.index("render()") < handler.index("button.sort")
    assert ".focus()" in handler[handler.index("button.sort") :][:200]


def test_the_sort_caption_describes_the_table_only_where_it_is_visible():
    js = re.sub(r"/\*.*?\*/|//[^\n]*", "", (STATIC / "js" / "compare.js").read_text(), flags=re.S)
    fn = js[js.index("function describeSort") :]
    fn = fn[: fn.index("\n}\n")]
    # set under the phone query that shows the caption, removed otherwise, and kept in step
    assert 'matchMedia("(max-width: 600px)")' in js and "PHONE.matches" in fn
    assert 'setAttribute("aria-describedby"' in fn and 'removeAttribute("aria-describedby")' in fn
    assert 'PHONE.addEventListener("change"' in js
    # the query is the one that shows the caption (the stack breakpoint in the stylesheet)
    css = _stylesheet()
    assert re.search(r"@media \(max-width: 600px\) \{[^@]*?\.compare-js \.sort-caption", css, re.S)


def test_the_rebuilt_compare_table_keeps_the_caption_the_chart_points_at():
    # the chart is described by #compare-caption (compare.html); drawTable replaces the server
    # table, so the JS caption must carry the same id or the chart's description dangles
    html = (STATIC.parent / "templates" / "compare.html").read_text()
    m = re.search(r'data-compare-chart aria-describedby="([^"]+)"', html)
    assert m
    js = re.sub(r"/\*.*?\*/|//[^\n]*", "", (STATIC / "js" / "compare.js").read_text(), flags=re.S)
    body = js[js.index("function drawTable") :]
    body = body[: body.index("\nfunction ", 10)]
    assert f'id: "{m.group(1)}"' in body


def test_a_plan_item_without_yearly_rows_gets_no_chart_without_a_table(client, monkeypatch):  # noqa: F811
    from velometer.app import plans_pages

    real = plans_pages.berlin_context

    def no_yearly_for_the_first_item(*a, **k):
        ctx = real(*a, **k)
        ctx["items"][0]["yearly"] = []
        return ctx

    monkeypatch.setattr(plans_pages, "berlin_context", no_yearly_for_the_first_item)
    html = client.get("/plans/berlin").text
    first, second, *_ = re.finditer(r'<section class="plan-item" id="item-([^"]+)"', html)
    bare = html[first.end() : second.start()]
    assert "data-plan-item" not in bare and "plan-years" not in bare  # no chart, no table
    assert "no chart" in bare  # and it says so
    assert "data-plan-item" in html[second.end() :]  # the others keep theirs


def test_an_empty_card_cell_keeps_its_label_and_says_there_is_no_value():
    rules = _css_rules(_stylesheet())
    hidden = [s for s, d in rules if d.get("display") == "none" for s in s if "td" in s]
    assert not any("empty" in s for s in hidden)  # an empty cell is not hidden with its label
    marked = {k: v for s, d in rules if any("td:empty" in x and "::after" in x for x in s)
              for k, v in d.items()}  # fmt: skip
    assert "no value" in marked.get("content", "")  # a visible dash with a spoken alternative
