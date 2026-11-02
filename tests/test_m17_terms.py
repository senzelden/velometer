"""M17 Task 13 (spec §4.8): the terms registry, the methodology glossary and the first-use mark.

The wrapper marks the first occurrence of each registered short form in `<main>`, per scope
(always-visible text, each `<details>`, each `.phone-only` block), as a link to its glossary
entry around an `<abbr title>`; links, headings, code, SVG, `[lang]` marks and the glossary are
left alone."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from markupsafe import escape

from tests.test_app import CONTENT
from tests.test_app_base import rich  # noqa: F401  (`rich` is a fixture)
from velometer import i18n
from velometer.app import export, terms
from velometer.app.main import create_app
from velometer.content.models import ContentError
from velometer.report.data import ReportData, open_readonly

BASE_URL = "http://127.0.0.1:8000"
DOCS = Path(__file__).parents[1] / "docs"
BASE = "/velo/"
HREF = "/velo/methodology"
# the short forms spec §4.8 names; the registry may hold more, never fewer
SPEC_SHORT = ["A+B", "A+B+E", "LAU", "FUA", "OSM", "QECIO", "NUTS3", "COROP", "A", "B", "C", "D"]
SPEC_SHORT += ["E"]
MARK = re.compile(
    r'<a class="term" href="(?P<href>[^"]*)#term-(?P<id>[a-z0-9-]+)">'
    r'<abbr title="(?P<title>[^"]*)"(?: lang="(?P<lang>[^"]+)")?>(?P<text>[^<]*)</abbr></a>'
)


def _page(main: str, head: str = "<title>LAU</title>") -> str:
    return f"<!doctype html><html><head>{head}</head><body><main>{main}</main></body></html>"


def _marks(html: str) -> list[re.Match]:
    return list(MARK.finditer(html))


@pytest.fixture(scope="module")
def en():
    return terms.load("en", CONTENT)


@pytest.fixture(scope="module")
def de():
    return terms.load("de", CONTENT)


# --- the registry -------------------------------------------------------------------------


def test_registry_en_de_same_ids(en, de):
    assert [t.id for t in en] == [t.id for t in de]
    assert len({t.id for t in en}) == len(en)
    for t in en + de:
        assert t.short and t.expansion.strip() and t.explanation.strip(), t.id


def test_registry_refuses_a_term_missing_a_language(tmp_path):
    raw = yaml.safe_load((CONTENT / "terms.yaml").read_text(encoding="utf-8"))
    del raw["terms"][-1]["explanation"]["de"]
    (tmp_path / "terms.yaml").write_text(yaml.safe_dump(raw, allow_unicode=True))
    with pytest.raises(ContentError, match=raw["terms"][-1]["id"]):
        terms.load("de", tmp_path)


def test_registry_refuses_an_unknown_tier(tmp_path):
    raw = yaml.safe_load((CONTENT / "terms.yaml").read_text(encoding="utf-8"))
    raw["terms"][0]["tier"] = "Z"
    (tmp_path / "terms.yaml").write_text(yaml.safe_dump(raw, allow_unicode=True))
    with pytest.raises(ContentError, match="Z"):
        terms.load("en", tmp_path)


@pytest.mark.parametrize("lang", ["en", "de"])
def test_tier_expansions_are_the_tier_labels(lang):
    """A–E reuse the `tier.*` labels (one source): the expansion is the label without its
    letter."""
    by_short = {t.short: t for t in terms.load(lang, CONTENT) if t.tier}
    assert sorted(by_short) == ["A", "B", "C", "D", "E"]
    for letter, t in by_short.items():
        label = i18n.t(lang, f"tier.{letter}")
        assert label == f"{letter} {t.expansion}", letter


def _rule_pairs(match) -> set[tuple[str, str]]:
    """Every (key, value) a classifier rule's `match` names, through `any` lists and value lists."""
    out: set[tuple[str, str]] = set()
    if isinstance(match, list):
        for m in match:
            out |= _rule_pairs(m)
    elif isinstance(match, dict):
        for k, v in match.items():
            if k == "any":
                out |= _rule_pairs(v)
            elif isinstance(v, list):
                out |= {(k, str(x)) for x in v}
            elif isinstance(v, str):
                out.add((k, v))
    return out


@pytest.mark.parametrize("lang", ["en", "de"])
def test_tier_explanations_name_tags_of_their_own_tier(lang):
    """A tag a tier's explanation names (`key=value`) is matched by a rule of that tier in the
    report classifier: the glossary restates the classifier, not older prose."""
    from velometer.selection import report_selector

    config = Path(__file__).parents[1] / "config"
    version = report_selector(config).version
    rules = yaml.safe_load((config / "classifier" / f"{version}.yaml").read_text())["rules"]
    named = 0
    for t in terms.load(lang, CONTENT):
        if not t.tier:
            continue
        own = set().union(*(_rule_pairs(r["match"]) for r in rules if r["tier"] == t.tier))
        for key, value in re.findall(r"`([\w:]+)=([\w]+)`", t.explanation):
            assert (key, value) in own, (t.id, key, value)
            named += 1
    assert named >= 3


def test_cited_sources_exist(en):
    from velometer.content.loader import load_sources

    sources = load_sources(CONTENT / "sources")
    cited = {c for t in en for c in t.cite}
    assert {"qecio-methodology", "cbs-regionale-economie-2018-begrippen"} <= cited
    assert cited <= set(sources)


# --- the wrapper --------------------------------------------------------------------------


def test_first_use_wrapped_once_per_page(en):
    lau = next(t for t in en if t.id == "lau")
    html = _page("<p>The LAU is one, LAU two,</p><table><tr><td>LAU three</td></tr></table>")
    out = terms.mark_first_use(html, en, HREF)
    marks = _marks(out)
    assert [(m["href"], m["id"], m["text"]) for m in marks] == [(HREF, "lau", "LAU")]
    assert marks[0]["title"] == lau.expansion
    # the first one, the later two plain
    assert out.index(marks[0].group(0)) < out.index("LAU two") < out.index("LAU three")
    assert out.count("LAU") == html.count("LAU")


def test_first_use_marks_each_term_and_prefers_the_longest(en):
    html = _page("<p>tiers A+B+E km, then A+B and tier A, and NUTS-3 and NUTS3.</p>")
    out = terms.mark_first_use(html, en, HREF)
    assert [m["id"] for m in _marks(out)] == ["a-b-e", "a-b", "tier-a", "nuts3"]
    assert [m["text"] for m in _marks(out)] == ["A+B+E", "A+B", "A", "NUTS-3"]


def test_tier_letter_only_after_the_tier_word(en, de):
    out = terms.mark_first_use(_page("<p>A city. Plan B. Tiers A and B.</p>"), en, HREF)
    assert [(m["id"], m["text"]) for m in _marks(out)] == [("tier-a", "A")]
    out = terms.mark_first_use(_page("<p>A und B. Stufe B wuchs.</p>"), de, HREF)
    assert [(m["id"], m["text"]) for m in _marks(out)] == [("tier-b", "B")]


def test_wrapper_skips_links_headings_code_svg(en):
    skipped = (
        '<a href="/x">LAU</a><h2>LAU</h2><h3 id="h">FUA <span>LAU</span></h3><code>LAU</code>'
        "<pre>LAU</pre><svg><text>LAU</text><g><title>LAU</title></g></svg>"
        '<script type="application/json">{"a": "LAU"}</script><style>.LAU{}</style>'
        '<p><i lang="nl">LAU</i> <span lang="en">LAU</span></p><button>LAU</button>'
        '<details><summary>LAU</summary></details><span class="visually-hidden">LAU</span>'
        '<section id="terms"><p>LAU</p></section><abbr title="x">LAU</abbr>'
        '<p class="cite-text">velometer, LAU</p><cite>LAU</cite>'
    )
    out = terms.mark_first_use(_page(skipped + "<p>Then LAU.</p>"), en, HREF)
    marks = _marks(out)
    assert [m["id"] for m in marks] == ["lau"]
    assert out.index(marks[0].group(0)) > out.index("<p>Then ")
    # nothing outside the marked text changed
    assert out.replace(marks[0].group(0), "LAU") == _page(skipped + "<p>Then LAU.</p>")


def test_wrapper_scopes(en):
    """Always-visible text, each `<details>` and each `.phone-only` block are scopes of their
    own (spec §4.8 settled 4): each gets its first-use mark."""
    html = _page(
        "<p>LAU one</p>"
        "<details><summary>More</summary><p>LAU two</p><p>LAU three</p></details>"
        "<details><summary>Table</summary><table><tr><th>LAU four</th></tr></table></details>"
        '<div class="story phone-only"><p>LAU five <span>LAU six</span></p>'
        "<details><summary>x</summary>LAU seven</details></div>"
        "<p>LAU eight</p>"
    )
    out = terms.mark_first_use(html, en, HREF)
    marked = [m.end() for m in _marks(out)]
    after = [out[e : e + 6] for e in marked]
    assert after == [" one</", " two</", " four<", " five ", " seven"]


def test_wrapper_keeps_html_valid():
    odd = terms.Term(
        id="x-y", short="X&Y", expansion='Tom & "Jerry" <b>', explanation="-", cite=(), tier=None
    )
    plain = terms.Term(id="lau", short="LAU", expansion="a 'unit'", explanation="-")
    html = _page('<p>Tom &amp; X&amp;Y &lt;LAU&gt; <a href="/a">LAU</a> LAU.</p>')
    out = terms.mark_first_use(html, [odd, plain], HREF)
    # the escaped `X&amp;Y` in the source is not the short form's raw text: only LAU matched
    marks = _marks(out)
    assert [m["id"] for m in marks] == ["lau"]
    assert marks[0]["title"] == "a &#39;unit&#39;"
    assert "&lt;" in out and "Tom &amp; X&amp;Y" in out
    # a title with markup characters is escaped
    out = terms.mark_first_use(_page("<p>X-Y and LAU</p>"), [odd.model_copy(
        update={"short": "X-Y"})], HREF)  # fmt: skip
    assert 'title="Tom &amp; &#34;Jerry&#34; &lt;b&gt;"' in out
    _assert_well_formed(out)


def test_wrapper_leaves_pages_without_main_and_the_head_alone(en):
    fragment = "<section><p>LAU and FUA</p></section>"
    assert terms.mark_first_use(fragment, en, HREF) == fragment
    head = '<title>LAU</title><script type="application/ld+json">{"name": "LAU"}</script>'
    html = _page("<p>LAU</p>", head=head)
    out = terms.mark_first_use(html, en, HREF)
    assert out.split("<main>")[0] == html.split("<main>")[0]
    assert out.split("</main>")[1] == html.split("</main>")[1]
    assert len(_marks(out)) == 1


class _Nesting(HTMLParser):
    VOID = {"br", "img", "input", "meta", "link", "hr", "source", "wbr", "col", "area"}

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.nested_a = False

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        if tag == "a" and "a" in self.stack:
            self.nested_a = True
        self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1] == tag, (self.stack, tag)
        self.stack.pop()


def _assert_well_formed(html: str) -> None:
    p = _Nesting()
    p.feed(html)
    p.close()
    assert not p.nested_a
    assert p.stack == []


# --- the pages ----------------------------------------------------------------------------


def _app(rich, base=BASE, docs=None):  # noqa: F811
    """The fixture app; `docs` the repo's own docs (the real methodology) when given."""
    db_path, cfg, maps, fixture_docs, plans = rich
    docs = docs or fixture_docs
    return create_app(
        db_path, cfg, maps, docs, content_dir=CONTENT, plans_data_dir=plans, base_path=base
    )


def _urls(rich, app) -> list[str]:  # noqa: F811
    conn = open_readonly(Path(rich[0]))
    try:
        return export.export_urls(ReportData(conn, rich[1]), app)
    finally:
        conn.close()


class _MainText(HTMLParser):
    """The text of `<main>` outside script, style, svg, code and pre: what a reader reads."""

    SKIP = {"script", "style", "svg", "code", "pre", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = self.skip = 0
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.depth += tag == "main"
        self.skip += self.depth > 0 and tag in self.SKIP

    def handle_endtag(self, tag):
        self.skip -= self.depth > 0 and tag in self.SKIP
        self.depth -= tag == "main"

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.text.append(data)


def _main_text(html: str) -> str:
    p = _MainText()
    p.feed(html)
    p.close()
    return " ".join(p.text)


# the shapes of a term in page text: a tier sum, a tier letter after the word for tier, the NUTS
# levels, and the upper-case codes spec §4.8 lists
SHAPES = [
    re.compile(r"(?<![\w+])[A-E](?:\+[A-E])+(?![\w+])"),
    re.compile(r"\b(?:[Tt]iers?|Stufen?)\s+([A-E])(?![\w+])"),
    re.compile(r"\bNUTS[ -]?\d\b"),
    re.compile(r"\b(?:LAU|FUA|OSM|QECIO|COROP)\b"),
]


def test_every_listed_short_form_is_registered(rich):  # noqa: F811
    app = _app(rich)
    found: dict[str, set[str]] = {}
    with TestClient(app, base_url=BASE_URL) as c:
        for url in _urls(rich, app):
            r = c.get(url)
            if not r.headers["content-type"].startswith("text/html"):
                continue
            text = _main_text(r.text)
            for shape in SHAPES:
                for m in shape.finditer(text):
                    found.setdefault(m.group(m.lastindex or 0), set()).add(url)
    for lang in ("en", "de"):
        forms = {f for t in terms.load(lang, CONTENT) for f in t.forms}
        assert set(SPEC_SHORT) <= forms
        missing = {tok: sorted(urls)[:3] for tok, urls in found.items() if tok not in forms}
        assert missing == {}, lang
    assert {"A+B", "LAU", "OSM"} <= set(found)  # the fixture export shows terms at all


def test_pages_mark_terms_and_link_the_glossary_in_their_edition(rich):  # noqa: F811
    app = _app(rich)
    with TestClient(app, base_url=BASE_URL) as c:
        for prefix in ("", "de/"):
            html = c.get(f"/{prefix}city/berlin").text
            marks = _marks(html)
            assert marks, prefix
            assert {m["href"] for m in marks} == {f"{BASE}{prefix}methodology"}
            ids = [m["id"] for m in marks]
            assert "a-b" in ids
            _assert_well_formed("<main" + html.split("<main", 1)[1].split("</main>")[0] + "</main>")
            # the panel fragment has no <main>: untouched
            assert not _marks(c.get(f"/{prefix}city/berlin/panel").text)


@pytest.mark.parametrize("prefix,lang", [("", "en"), ("de/", "de")])
def test_glossary_lists_every_term_both_editions(rich, prefix, lang):  # noqa: F811
    with TestClient(_app(rich, docs=DOCS), base_url=BASE_URL) as c:
        html = c.get(f"/{prefix}methodology").text
    section = re.search(r'<section [^>]*id="terms".*?</section>', html, re.S)
    assert section, lang
    glossary = section.group(0)
    for t in terms.load(lang, CONTENT):
        entry = re.search(rf'<dt id="term-{t.id}">(.*?)</dd>', glossary, re.S)
        assert entry, t.id
        assert f">{t.short}</abbr>" in entry.group(1)
    # the glossary itself carries no first-use mark; the methodology text before it does
    assert not _marks(glossary)
    assert _marks(html.split(glossary)[0])
    # its citations are listed under their numbers
    assert 'id="terms-src-1"' in glossary


def test_de_glossary_marks_original_terms(rich):  # noqa: F811
    """On the German page, an expansion in another language (`expansion_lang`) sits in its
    `lang`, as does every English expansion the German glossary shows (the original-terms
    rule): none of them is in the page's German visible text."""
    en_terms = {t.id: t for t in terms.load("en", CONTENT)}
    de_terms = terms.load("de", CONTENT)
    foreign = [t for t in de_terms if t.expansion_lang]
    assert foreign  # QECIO's title is English
    with TestClient(_app(rich, docs=DOCS), base_url=BASE_URL) as c:
        html = c.get("/de/methodology").text
        city = c.get("/de/city/berlin").text
    glossary = re.search(r'<section [^>]*id="terms".*?</section>', html, re.S).group(0)
    visible = i18n.visible_text(glossary)
    for t in foreign:
        assert re.search(
            rf'<abbr title="{re.escape(str(escape(t.expansion)))}" lang="{t.expansion_lang}">',
            glossary,
        ), t.id
        assert t.expansion not in visible, t.id
    shown_english = [
        en_terms[t.id].expansion.split(",")[0]
        for t in de_terms
        if en_terms[t.id].expansion != t.expansion
    ]
    shown_english = [e for e in shown_english if e in glossary]
    # every name or term a German explanation marks in another language renders in that language
    lang_mark = re.compile(r'<(?:i|span) lang="en">(.*?)</(?:i|span)>', re.S)
    marked = [m.group(1) for t in de_terms for m in lang_mark.finditer(t.explanation)]
    assert "European Cyclists' Federation" in marked
    for inner in marked:
        shown = re.escape(str(escape(inner)))
        assert re.search(rf'<(i|span) lang="en">{shown}</\1>', glossary), inner
        assert inner not in visible, inner
    assert shown_english  # LAU's and FUA's English names are shown
    assert [e for e in shown_english if e in visible] == []
    # a first-use mark on a German page carries the expansion's language too
    for m in _marks(city):
        t = next(t for t in de_terms if t.id == m["id"])
        assert m["lang"] == t.expansion_lang, t.id


def test_every_exported_page_with_main_passes_through_the_wrapper(rich):  # noqa: F811
    """Each exported page with a `<main>` is exactly the wrapper's output on its own unmarked
    text, in its edition: no page type bypasses the hook, and none is marked twice."""
    app = _app(rich, docs=DOCS)
    checked: dict[str, int] = {}
    registry = {lang: terms.load(lang, CONTENT) for lang in ("en", "de")}
    with TestClient(app, base_url=BASE_URL) as c:
        for url in _urls(rich, app):
            r = c.get(url)
            if not r.headers["content-type"].startswith("text/html") or "<main" not in r.text:
                continue
            lang = "de" if url.startswith("/de/") or url == "/methodology/de" else "en"
            href = f"{BASE}{'de/' if lang == 'de' else ''}methodology"
            want = terms.mark_first_use(terms.unmark(r.text), registry[lang], href)
            assert r.text == want, url
            if _marks(r.text):
                kind = url.removeprefix("/de").split("/")[1] or "home"
                checked[kind] = checked.get(kind, 0) + 1
    # the check bites: marked pages of every main page type, both editions included
    assert {"home", "city", "cities", "compare", "methodology", "sources"} <= set(checked), checked
