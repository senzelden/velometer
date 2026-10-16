"""M14 Task 6: data tables outside prose are named, and the Sources links have unique names."""

from html.parser import HTMLParser

from tests.test_app import subarea_setup  # noqa: F401
from velometer import i18n

VOID = {"br", "img", "hr", "input", "meta", "link", "wbr", "col"}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def text(self, skip_hidden=False):
        out = []
        for k in self.kids:
            if isinstance(k, str):
                out.append(k)
            elif not (skip_hidden and "visually-hidden" in k.classes()):
                out.append(k.text(skip_hidden))
        return "".join(out)

    def walk(self):
        yield self
        for k in self.kids:
            if isinstance(k, Node):
                yield from k.walk()

    def inside(self, cls):
        n = self.parent
        while n is not None:
            if cls in n.classes():
                return True
            n = n.parent
        return False


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = self.cur = Node("#root", [], None)

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def parse(html):
    t = _Tree()
    t.feed(html)
    return t.root


def _words(s):
    return " ".join(s.split())


def _unnamed_tables(root):
    ids = {n.attrs["id"]: n for n in root.walk() if "id" in n.attrs}
    bad = []
    for tbl in (n for n in root.walk() if n.tag == "table" and not n.inside("prose")):
        caps = [k for k in tbl.kids if isinstance(k, Node) and k.tag == "caption"]
        if any(_words(c.text()) for c in caps):
            continue
        refs = (tbl.attrs.get("aria-labelledby") or "").split()
        if any(r in ids and _words(ids[r].text()) for r in refs):
            continue
        bad.append(tbl.attrs.get("class") or "table")
    return bad


def test_every_data_table_outside_prose_is_named(page_site):
    assert page_site.html
    bad = {}
    for url, html in page_site.html.items():
        found = _unnamed_tables(parse(html))
        if found:
            bad[url] = found
    assert not bad, f"{sum(map(len, bad.values()))} unnamed tables: {bad}"


def test_the_checker_flags_an_unnamed_table():
    assert _unnamed_tables(parse("<table><tr><td>1</td></tr></table>")) == ["table"]
    assert not _unnamed_tables(parse("<table><caption>x</caption><tr><td>1</td></tr></table>"))
    assert not _unnamed_tables(parse('<div class="prose"><table></table></div>'))


def test_sources_links_have_unique_names_and_the_same_look(page_site):
    checked = 0
    for url, html in page_site.html.items():
        if not url.rstrip("/").endswith("/sources"):
            continue
        lang = "de" if url.startswith("/de/") else "en"
        word = i18n.t(lang, "cite.source")
        links = [
            a
            for a in parse(html).walk()
            if a.tag == "a" and _words(a.text(skip_hidden=True)) == word
        ]
        assert links, url
        names = [_words(a.text()) for a in links]
        assert len(set(names)) == len(names), f"{url}: duplicate link names {names}"
        assert all(n.startswith(word + ":") for n in names), names
        checked += 1
    assert checked == 2, [u for u in page_site.html if "source" in u]


def test_the_bezirke_change_table_is_named_and_marks_its_remainder(subarea_setup):  # noqa: F811
    # the fixture app has no change data, so the whole-site test above cannot see this table
    # (final review I2): Berlin's Bezirke tab with a change page whose table has a remainder row
    from tests.test_app import CONTENT, _client, _latest_lau_run, _write_change
    from velometer.app.main import create_app

    db_path, cfg, maps, docs = subarea_setup
    _write_change(maps, docs, run_to=_latest_lau_run(db_path, cfg), remainder=True)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        pages = {u: c.get(u).text for u in ("/city/berlin/bezirke", "/de/city/berlin/bezirke")}
    for url, html in pages.items():
        root = parse(html)
        tables = [n for n in root.walk() if n.tag == "table"]
        assert len(tables) >= 3, url  # the Bezirk table, its values and the change table
        assert not _unnamed_tables(root), (url, _unnamed_tables(root))
    # the change table's remainder row: the original term marked where the term is foreign
    change = parse(pages["/city/berlin/bezirke"].split('id="bezirke-change-h"')[1])
    rows = [n for n in change.walk() if n.tag == "tr" and "Outside the" in n.text()]
    assert rows and all(
        any(i.tag == "i" and i.attrs.get("lang") == "de" and i.text() == "Bezirke"
            for i in r.walk())
        for r in rows
    ), [r.text() for r in rows]  # fmt: skip
