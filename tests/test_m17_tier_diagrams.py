"""M17 Task 14 (spec §4.8): one drawn street cross-section per tier, in the methodology glossary.

The tier set is the current classifier version's (config/report.yaml names it), so a tier without
a diagram, or a diagram without a tier, fails here. Each diagram is a `<figure>` holding an inline
`<svg role="img">` named by its caption, drawn only with colour tokens, and its caption says
whether the tier counts in the headline, read from the headline preset in config/presets.yaml."""

import re
import shutil
from functools import partial
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader

from tests.test_app import CONTENT, STATIC
from tests.test_app_base import build_rich
from tests.test_app_m8 import _colour_literal
from velometer import i18n
from velometer.app.main import create_app
from velometer.config import load_classifier, load_report
from velometer.selection import report_selector

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "config"
DOCS = ROOT / "docs"
TEMPLATES = ROOT / "src/velometer/app/templates"
BASE_URL = "http://127.0.0.1:8000"
HEADLINE = "ours_headline"  # the headline's preset, as report/data.py selects it
PAINT_ATTRS = {"fill", "stroke", "color", "stop-color", "flood-color", "lighting-color"}
TOKEN_OR_CURRENT = re.compile(r"^(?:var\(--[\w-]+\)|currentColor|none)$")


def classifier_tiers(config_dir: Path) -> set[str]:
    """The tiers the report classifier's rules produce (its `excluded` is no tier)."""
    report = load_report(config_dir / "report.yaml", config_dir / "presets.yaml")
    cfg = load_classifier(config_dir / "classifier" / f"{report.report_classifier}.yaml")
    return {r.tier for r in cfg.rules} - {"excluded"}


def headline_tiers(config_dir: Path) -> set[str]:
    """The tiers the headline counts whole (an `X/sub` entry counts only part of X)."""
    preset = report_selector(config_dir).presets.preset(HEADLINE)
    return {e for e in preset.tiers if "/" not in e}


def _module(lang: str, tier_set: dict):
    """The diagram template's module in `lang`, outside the app: its macros and DRAWN."""
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals.update(t=partial(i18n.t_markup, lang), u=lambda p: "/velo" + p, lang=lang)
    return env.get_template("_tier_diagram.html").make_module({"tier_set": tier_set})


def _tier_set(config_dir: Path = CONFIG) -> dict:
    return {
        "tiers": sorted(classifier_tiers(config_dir)),
        "headline": sorted(headline_tiers(config_dir)),
    }


class _Figures(HTMLParser):
    """Every `<figure class="tier-diagram">`: its tier, svg attributes, every paint attribute
    inside the svg, the svg's raw text, the caption's text and every element id with its text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.figures: list[dict] = []
        self.ids: dict[str, list[str]] = {}
        self.id_list: list[str] = []
        self._fig: dict | None = None
        self._depth = 0
        self._in_svg = self._in_cap = 0
        self._open_ids: list[tuple[str, int]] = []
        self._level = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._level += 1
        if a.get("id"):
            self.id_list.append(a["id"])
            self.ids.setdefault(a["id"], [])
            self._open_ids.append((a["id"], self._level))
        if tag == "figure" and "tier-diagram" in (a.get("class") or "").split():
            self._fig = {"tier": a.get("data-tier"), "svg": [], "paint": [], "svg_text": [],
                         "caption": [], "styles": []}  # fmt: skip
            self._depth = self._level
        if self._fig is None:
            return
        if tag == "svg":
            self._in_svg += 1
            self._fig["svg"].append(a)
        if self._in_svg:
            self._fig["paint"] += [(k, v) for k, v in a.items() if k in PAINT_ATTRS]
            self._fig["styles"] += [v for k, v in a.items() if k == "style"]
        if tag == "figcaption":
            self._in_cap += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self._fig is not None:
            if tag == "svg":
                self._in_svg -= 1
            if tag == "figcaption":
                self._in_cap -= 1
            if tag == "figure" and self._level == self._depth:
                self.figures.append(self._fig)
                self._fig = None
        while self._open_ids and self._open_ids[-1][1] >= self._level:
            self._open_ids.pop()
        self._level -= 1

    def handle_data(self, data):
        for i, _ in self._open_ids:
            self.ids[i].append(data)
        if self._fig is not None:
            if self._in_svg:
                self._fig["svg_text"].append(data)
            if self._in_cap:
                self._fig["caption"].append(data)


def _parse(html: str) -> _Figures:
    p = _Figures()
    p.feed(html)
    p.close()
    return p


def _figures(html: str) -> tuple[list[dict], dict[str, str]]:
    p = _parse(html)
    return p.figures, {k: " ".join("".join(v).split()) for k, v in p.ids.items()}


def _caption(fig: dict) -> str:
    return " ".join("".join(fig["caption"]).split())


def _plain(lang: str, key: str) -> str:
    return " ".join(i18n.t(lang, key).split())


# --- the template ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", i18n.LANGS)
def test_diagram_for_every_tier_and_no_extra(lang):
    tiers = classifier_tiers(CONFIG)
    assert tiers  # the classifier produces tiers at all
    module = _module(lang, _tier_set())
    assert set(module.DRAWN) == tiers
    for tier in sorted(tiers):
        figs, _ = _figures(str(module.tier_diagram(tier)))
        assert [f["tier"] for f in figs] == [tier]  # one figure per tier, E's two panels included
        assert len(figs[0]["svg"]) == 1
    figs, _ = _figures(str(module.tier_diagrams()))
    assert sorted(f["tier"] for f in figs) == sorted(tiers)


def test_every_tier_has_its_caption_and_name_keys():
    # the caption and name keys are a declared family of the classifier's tiers: one per tier
    for prefix in ("tier.caption.", "tier.diagram_name."):
        assert prefix in i18n.DYNAMIC_FAMILIES
        assert i18n.DYNAMIC_FAMILIES[prefix]() >= classifier_tiers(CONFIG)


@pytest.mark.parametrize(
    ("tier", "hedge"),
    [("A", {"en": "typically by", "de": "meist durch"}), ("C", {"en": "such as", "de": "etwa"})],
)
def test_caption_names_separations_as_examples(tier, hedge):
    """A and C are drawn with one kind of separation each, but the tier has more (the user's
    call of 2026-11-02): their captions name the drawn kinds as typical or as examples."""
    for lang in ("en", "de"):
        caption = i18n.t(lang, f"tier.caption.{tier}")
        assert re.search(rf"\b{hedge[lang]}\b", caption), (lang, caption)


def test_one_viewbox_for_every_diagram():
    module = _module("en", _tier_set())
    boxes = {
        f["svg"][0].get("viewbox")
        for tier in sorted(classifier_tiers(CONFIG))
        for f in _figures(str(module.tier_diagram(tier)))[0]
    }
    assert len(boxes) == 1 and None not in boxes


# --- on the methodology page ----------------------------------------------------------------


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    return build_rich(tmp_path_factory.mktemp("tier-diagrams"))


def _app(site, cfg=None):
    db_path, fixture_cfg, maps, _, plans = site
    return create_app(
        db_path, cfg or fixture_cfg, maps, DOCS, content_dir=CONTENT, plans_data_dir=plans,
        base_path="/velo/",
    )  # fmt: skip


@pytest.fixture(scope="module")
def pages(site):
    with TestClient(_app(site), base_url=BASE_URL) as c:
        return {lang: c.get(f"/{'' if lang == 'en' else 'de/'}methodology").text
                for lang in i18n.LANGS}  # fmt: skip


def _glossary(html: str) -> str:
    m = re.search(r'<section [^>]*id="terms".*?</section>', html, re.S)
    assert m
    return m.group(0)


def test_glossary_shows_one_diagram_per_tier_with_its_term(pages, site):
    tiers = classifier_tiers(site[1])
    for lang, html in pages.items():
        glossary = _glossary(html)
        figs, _ = _figures(glossary)
        assert sorted(f["tier"] for f in figs) == sorted(tiers), lang
        for tier in tiers:  # each sits in its tier's glossary entry
            entry = re.search(rf'<dt id="term-tier-{tier.lower()}">.*?</dd>', glossary, re.S)
            assert entry and f'data-tier="{tier}"' in entry.group(0), (lang, tier)


def test_diagram_has_accessible_name_and_caption_en_de(pages):
    names: dict[str, dict[str, str]] = {}
    for lang, html in pages.items():
        figs, ids = _figures(html)
        assert figs, lang
        id_list = _parse(html).id_list
        assert len(id_list) == len(set(id_list)), lang
        for fig in figs:
            (svg,) = fig["svg"]
            assert svg.get("role") == "img", (lang, fig["tier"])
            label = svg.get("aria-labelledby")
            assert label and label in ids, (lang, fig["tier"])
            name = ids[label]
            assert name == _plain(lang, f"tier.diagram_name.{fig['tier']}"), (lang, fig["tier"])
            caption = _caption(fig)
            assert name in caption  # the name is visible: the caption starts with it
            assert _plain(lang, f"tier.caption.{fig['tier']}") in caption, (lang, fig["tier"])
            names.setdefault(fig["tier"], {})[lang] = name + caption
    for tier, by_lang in names.items():  # translated, not copied
        assert by_lang["en"] != by_lang["de"], tier


def test_diagram_svg_uses_tokens_not_literal_colours(pages):
    for lang, html in pages.items():
        figs = _figures(html)[0]
        assert figs, lang
        for fig in figs:
            where = (lang, fig["tier"])
            assert not "".join(fig["svg_text"]).strip(), where  # no text inside the drawing
            for attr, value in fig["paint"]:
                assert TOKEN_OR_CURRENT.match(value.strip()), (*where, attr, value)
            assert fig["styles"] == [], where  # CSP style-src 'self': no inline style
        svgs = re.findall(r"<svg[^>]*\bclass=\"td-svg\".*?</svg>", html, re.S)
        assert len(svgs) == len(figs), lang
        for svg in svgs:
            assert not _colour_literal(svg), lang


def test_each_tier_is_drawn_in_its_tier_colour():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    for tier in sorted(classifier_tiers(CONFIG)):
        rule = re.search(
            rf'\.tier-diagram\[data-tier="{tier}"\] \.td-tier \{{\s*fill: var\(([\w-]+)\);', css
        )
        assert rule and rule.group(1) == f"--tier-{tier.lower()}", tier


def test_caption_states_headline_membership(pages, site):
    tiers, headline = classifier_tiers(site[1]), headline_tiers(site[1])
    assert headline and tiers - headline  # both kinds exist, so both sentences are tested
    for lang, html in pages.items():
        counts, measured = (
            _plain(lang, "tier.diagram_counts"),
            _plain(lang, "tier.diagram_measured"),
        )
        for fig in _figures(_glossary(html))[0]:
            caption = _caption(fig)
            if fig["tier"] in headline:
                assert counts in caption and measured not in caption, (lang, fig["tier"])
            else:
                assert measured in caption and counts not in caption, (lang, fig["tier"])


def test_caption_follows_the_headline_preset_not_the_letters(site, tmp_path):
    # a headline that counted one more tier: that tier's caption says it counts
    cfg = tmp_path / "config"
    shutil.copytree(site[1], cfg)
    raw = yaml.safe_load((cfg / "presets.yaml").read_text(encoding="utf-8"))
    preset = next(p for p in raw["presets"] if p["id"] == HEADLINE)
    extra = sorted(classifier_tiers(cfg) - headline_tiers(cfg))[0]
    preset["tiers"] = [*preset["tiers"], extra]
    (cfg / "presets.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with TestClient(_app(site, cfg), base_url=BASE_URL) as c:
        html = c.get("/methodology").text
    (fig,) = [f for f in _figures(_glossary(html))[0] if f["tier"] == extra]
    assert _plain("en", "tier.diagram_counts") in _caption(fig)


def test_glossary_says_once_that_the_rules_decide(pages):
    for lang, html in pages.items():
        glossary = _glossary(html)
        assert glossary.count('class="tier-diagram-rules"') == 1, lang
        assert re.search(r'class="tier-diagram-rules"[^>]*>.*?href="/velo/', glossary, re.S)
