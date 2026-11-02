"""M17 Task 16 (spec §4.8): a city's story page reads as one scroll on phones.

Below the 62rem breakpoint the story page runs: the narrative, the headline chart (the aside box,
as on desktop), a "road types" block (the tier composition of the latest snapshot, then the tier
diagrams), the tier composition over time, and links to every other tab of that city. The blocks
after the headline chart are `.phone-only`: the stylesheet hides them at 62rem and wider, so the
desktop page looks as before. Their charts keep a table fallback, and the tier map stays on the
tiers tab (the scroll links to it, it never embeds it)."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.report_fixture import build_report_fixture_n
from tests.test_app import CONTENT, _docs
from tests.test_app_base import build_rich
from velometer.app.main import TABS, create_app
from velometer.selection import report_tiers

ROOT = Path(__file__).parents[1]
CSS = ROOT / "src/velometer/app/static/app.css"
BASE_URL = "http://127.0.0.1:8000"
PREFIX = {"en": "", "de": "/de"}
PHONE = "phone-only"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
        "track", "wbr", "path", "rect", "circle", "line", "stop", "use"}  # fmt: skip


# --- a small element tree of the page ------------------------------------------------------


class Node:
    def __init__(self, tag: str, attrs: dict, parent: "Node | None"):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: list[Node] = []
        self.text: list[str] = []

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def find_all(self, pred) -> list["Node"]:
        return [n for n in self.walk() if pred(n)]

    def ancestors(self):
        n = self.parent
        while n is not None:
            yield n
            n = n.parent

    def inside(self, pred) -> bool:
        return any(pred(a) for a in self.ancestors())

    def all_text(self) -> str:
        return " ".join(" ".join(n.text) for n in self.walk()).strip()


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text.append(data)


def tree(html: str) -> Node:
    p = _Tree()
    p.feed(html)
    p.close()
    main = p.root.find_all(lambda n: n.tag == "main")
    assert len(main) == 1
    return main[0]


def is_phone(n: Node) -> bool:
    return PHONE in n.classes


def charts(n: Node) -> list[Node]:
    return n.find_all(lambda x: "data-chart" in x.attrs)


def phone_blocks(main: Node) -> list[Node]:
    """The outermost `.phone-only` blocks, in document order."""
    return [n for n in main.find_all(is_phone) if not n.inside(is_phone)]


def tab_links(main: Node) -> list[str]:
    nav = main.find_all(lambda n: n.tag == "nav" and "tabs" in n.classes)
    assert len(nav) == 1
    return [a.attrs["href"] for a in nav[0].find_all(lambda n: n.tag == "a")]


def story_href(city: str, lang: str) -> str:
    return f"{PREFIX[lang]}/city/{city}"


# --- fixtures --------------------------------------------------------------------------------


def _pages(app, paths: list[str]) -> dict[str, str]:
    with TestClient(app, base_url=BASE_URL) as c:
        out = {}
        for p in paths:
            r = c.get(p)
            assert r.status_code == 200, p
            out[p] = r.text
        return out


@pytest.fixture(scope="module")
def rich_pages(tmp_path_factory):
    """berlin (Bezirke, counter data, tier maps) and paris (history, no current run)."""
    db, cfg, maps, docs, plans = build_rich(tmp_path_factory.mktemp("scroll-rich"))
    app = create_app(db, cfg, maps, docs, content_dir=CONTENT, plans_data_dir=plans)
    paths = [f"{PREFIX[lang]}/city/{c}" for lang in PREFIX for c in ("berlin", "paris")]
    paths += ["/city/berlin/tiers"]
    return _pages(app, paths) | {"_cfg": cfg}


@pytest.fixture(scope="module")
def plain_pages(tmp_path_factory):
    """c03: a current run and history, no Bezirke and no counter data."""
    tmp = tmp_path_factory.mktemp("scroll-plain")
    db, cfg = build_report_fixture_n(tmp, 3)
    maps = tmp / "maps"
    maps.mkdir()
    app = create_app(db, cfg, maps, _docs(tmp), content_dir=CONTENT)
    return _pages(app, [f"{PREFIX[lang]}/city/c03" for lang in PREFIX])


# --- the scroll ------------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "de"])
def test_story_page_has_phone_sections_in_order(rich_pages, lang):
    main = tree(rich_pages[story_href("berlin", lang)])
    order = list(main.walk())
    pos = order.index

    narrative = main.find_all(lambda n: n.tag == "article" and "narrative" in n.classes)
    headline = [c for c in charts(main) if c.attrs["data-chart"] == "city-headline"]
    assert len(narrative) == 1 and len(headline) == 1
    assert not headline[0].inside(is_phone)  # the aside box, shown on desktop as before

    blocks = phone_blocks(main)
    assert [b.attrs.get("id") for b in blocks] == ["phone-road-types", "phone-over-time",
                                                   "phone-tabs"]  # fmt: skip
    road, over, links = blocks
    assert pos(narrative[0]) < pos(headline[0]) < pos(road) < pos(over) < pos(links)

    # road types: the latest snapshot's tier composition (headline boundary), then the diagrams
    (now,) = charts(road)
    assert now.attrs["data-chart"] == "city-tiers" and now.attrs["data-kind"] == "lau"
    assert "data-latest" in now.attrs
    figures = road.find_all(lambda n: n.tag == "figure" and "tier-diagram" in n.classes)
    tiers = report_tiers(rich_pages["_cfg"]).tiers
    assert [f.attrs["data-tier"] for f in figures] == list(tiers)
    assert pos(now) < pos(figures[0])

    # over time: the tier composition over every snapshot
    (series,) = charts(over)
    assert series.attrs["data-chart"] == "city-tiers" and series.attrs["data-kind"] == "lau"
    assert "data-latest" not in series.attrs

    # the links: every other tab of the city, as the tab bar lists them
    hrefs = [a.attrs["href"] for a in links.find_all(lambda n: n.tag == "a")]
    others = [h for h in tab_links(main) if h != story_href("berlin", lang)]
    assert hrefs == others
    assert {f"{story_href('berlin', lang)}{s}" for k, s in TABS if k != "story"} == set(others)


def test_phone_ids_are_unique_on_the_page(rich_pages):
    ids = [n.attrs["id"] for n in tree(rich_pages["/city/berlin"]).walk() if "id" in n.attrs]
    assert len(ids) == len(set(ids)), sorted(i for i in ids if ids.count(i) > 1)


def test_tab_bar_stays_on_phones():
    """The tab bar is a link row on every width: no rule hides it."""
    for context, selectors, decls in css_rules(CSS.read_text(encoding="utf-8")):
        if any(s.startswith(".tabs") or s.startswith("nav.tabs") for s in selectors):
            assert decls.get("display") != "none", (context, selectors)


# --- CSS: hidden at 62rem and wider, only there ------------------------------------------------


def css_rules(css: str) -> list[tuple[str, list[str], dict[str, str]]]:
    """(at-rule context or "", selectors, declarations) of every style rule, nested one level."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out: list[tuple[str, list[str], dict[str, str]]] = []

    def scan(text: str, context: str) -> None:
        i = 0
        while i < len(text):
            open_ = text.find("{", i)
            if open_ < 0:
                return
            head = text[i:open_].strip()
            depth, j = 1, open_ + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            body = text[open_ + 1 : j - 1]
            if head.startswith("@"):
                scan(body, " ".join(head.split()))
            else:
                decls = {}
                for d in body.split(";"):
                    if ":" in d:
                        k, v = d.split(":", 1)
                        decls[k.strip()] = " ".join(v.split())
                out.append((context, [s.strip() for s in head.split(",")], decls))
            i = j

    scan(css, "")
    return out


def phone_only_rules(css: str) -> list[tuple[str, list[str], dict[str, str]]]:
    return [r for r in css_rules(css) if any(re.search(r"\.phone-only\b", s) for s in r[1])]


WIDE = "@media (min-width: 62rem)"


def test_phone_sections_hidden_on_desktop_css():
    css = CSS.read_text(encoding="utf-8")
    rules = phone_only_rules(css)
    assert rules, "no .phone-only rule"
    # one rule, at the story layout's own breakpoint, and it hides the block
    assert [(c, s, d.get("display")) for c, s, d in rules] == [(WIDE, [".phone-only"], "none")]
    story = [c for c, s, d in css_rules(css) if ".story-layout" in s and "grid-template-columns"
             in d and c]  # fmt: skip
    assert story == [WIDE]


def test_the_css_rule_check_bites():
    css = CSS.read_text(encoding="utf-8")
    without = re.sub(r"@media \(min-width: 62rem\) \{ \.phone-only \{[^}]*\} \}", "", css)
    assert without != css
    assert not phone_only_rules(without)
    narrow = css + "\n@media (max-width: 40rem) { .phone-only { display: none; } }\n"
    assert len(phone_only_rules(narrow)) == 2


# --- charts and their tables ---------------------------------------------------------------


@pytest.mark.parametrize("path", ["/city/berlin", "/de/city/berlin", "/city/paris"])
def test_every_phone_chart_has_table_fallback(rich_pages, path):
    main = tree(rich_pages[path])
    ids = {n.attrs["id"]: n for n in main.walk() if "id" in n.attrs}
    phone_charts = [c for b in phone_blocks(main) for c in charts(b)]
    if path != "/city/paris":
        assert len(phone_charts) == 2
    for chart in phone_charts:
        block = next(a for a in chart.ancestors() if is_phone(a))
        summary = ids[chart.attrs["aria-describedby"]]
        assert summary.tag == "summary"
        details = summary.parent
        assert details.tag == "details" and "table-details" in details.classes
        assert next(a for a in details.ancestors() if is_phone(a)) is block
        (table,) = details.find_all(lambda n: n.tag == "table")
        rows = table.find_all(lambda n: n.tag == "tr" and n.parent.tag == "tbody")
        assert rows
        if "data-latest" in chart.attrs:
            assert len(rows) == 1  # the latest snapshot only, as the chart
        else:
            assert len(rows) > 1


def test_latest_table_is_the_series_last_snapshot(rich_pages):
    """The road-types table shows the last point of the LAU series the over-time table shows."""
    main = tree(rich_pages["/city/berlin"])
    road, over, _links = phone_blocks(main)

    def body_rows(block):
        return [r.all_text() for r in block.find_all(lambda n: n.tag == "tr")
                if r.parent.tag == "tbody"]  # fmt: skip

    assert body_rows(road) == body_rows(over)[-1:]


def test_phone_scroll_links_tier_map_not_embeds(rich_pages):
    tiers_tab = rich_pages["/city/berlin/tiers"]
    # what an embedded map brings, as the tiers tab shows it (the fixture's berlin has a map)
    markers = ('id="tiermap"', 'id="tiermap-config"', "/vendor/leaflet", "/static/map.js")
    assert all(m in tiers_tab for m in markers)
    for lang in PREFIX:
        html = rich_pages[story_href("berlin", lang)]
        for marker in markers:
            assert marker not in html, (lang, marker)
        road = phone_blocks(tree(html))[0]
        hrefs = [a.attrs["href"] for a in road.find_all(lambda n: n.tag == "a")]
        assert f"{story_href('berlin', lang)}/tiers" in hrefs


def test_city_without_subareas_or_counts(plain_pages, rich_pages):
    for lang in PREFIX:
        main = tree(plain_pages[story_href("c03", lang)])
        links = phone_blocks(main)[-1]
        hrefs = [a.attrs["href"] for a in links.find_all(lambda n: n.tag == "a")]
        others = [h for h in tab_links(main) if h != story_href("c03", lang)]
        assert hrefs == others
        assert not any(h.endswith(("/bezirke", "/counts")) for h in hrefs), hrefs
        assert len(charts(phone_blocks(main)[0])) == 1
    # and the rich berlin links both, so the check above is not empty by construction
    rich = phone_blocks(tree(rich_pages["/city/berlin"]))[-1]
    rich_hrefs = [a.attrs["href"] for a in rich.find_all(lambda n: n.tag == "a")]
    assert "/city/berlin/bezirke" in rich_hrefs and "/city/berlin/counts" in rich_hrefs


def test_phone_charts_are_lazy_in_the_script():
    """city.js hands the phone blocks' charts to the lazy path (drawn once visible)."""
    js = (ROOT / "src/velometer/app/static/js/city.js").read_text(encoding="utf-8")
    assert re.search(r"drawAll\([^;]*lazy:\s*\"\.phone-only\"", js, re.S)
