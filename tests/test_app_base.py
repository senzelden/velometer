"""The base path in the rendered app (M9 spec decisions 3, 6, 8): built with a base, every page's
every internal reference carries it and resolves; built with `/`, the pages are what they were
apart from the two meta tags; every page carries the CSP and base meta tags."""

import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest
from starlette.routing import Match

from tests.test_app import (
    CHANGE_STEM,
    CONTENT,
    GEOJSON,
    PNG,
    _change_markdown,
    _client,
    _docs,
)
from tests.test_app_m8 import MEASURES, RETRIEVED
from tests.test_app_m8_counts import _seed
from velometer.app import urls
from velometer.app.main import CSP, TABS, create_app, csp_meta

BASE = "/velometer/"
# every page kind the app renders; the city tabs are added per city from TABS (those it serves)
PAGES = [
    "/", "/cities", "/compare", "/compare?c=berlin,paris&m=ab_km&view=table", "/stories",
    "/differences", "/organisations", "/plans", "/plans/berlin", "/methodology",
    "/methodology/de", "/city/berlin/panel",
]  # fmt: skip
CITIES = ["berlin", "paris"]
# the app's route prefixes: a JSON config string starting with one is an internal URL
ROUTE = re.compile(
    r"^/(city|compare|data|maps|static|plans|organisations|methodology|cities|stories|"
    r"differences)(?=[/?#.]|$)"
)
META_LINE = re.compile(
    r'^<meta (?:http-equiv="Content-Security-Policy"|name="velometer-base") [^\n]*\n', re.M
)
FOOTER_STAMP = "Static edition · build"


class _Refs(HTMLParser):
    """Every href / src / action, the velometer-base meta's content and the strings of every
    `<script type="application/json">` config."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str, str]] = []  # (tag, attribute, value)
        self.json_strings: list[str] = []
        self._in_json = False
        self._json = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for name in ("href", "src", "action"):
            if a.get(name) is not None:
                self.refs.append((tag, name, a[name]))
        if tag == "meta" and a.get("name") == "velometer-base":
            self.refs.append((tag, "content", a.get("content") or ""))
        if tag == "script" and a.get("type") == "application/json":
            self._in_json, self._json = True, ""

    def handle_data(self, data):
        if self._in_json:
            self._json += data

    def handle_endtag(self, tag):
        if tag == "script" and self._in_json:
            self._in_json = False
            self.json_strings += list(_strings(json.loads(self._json)))


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def _external(url: str) -> bool:
    return url.startswith("//") or bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", url))


@pytest.fixture
def rich(tmp_path):
    """The report fixture with every page part present: berlin's Bezirke and change map, its
    tier maps, counter data and the plan page's data."""
    from tests.report_fixture import build_report_fixture_subareas

    db_path, cfg = build_report_fixture_subareas(tmp_path)
    maps = tmp_path / "maps"
    maps.mkdir()
    (maps / "berlin_lau.png").write_bytes(PNG)
    (maps / "berlin_lau.geojson").write_bytes(GEOJSON)
    docs = _docs(tmp_path)
    (maps / f"{CHANGE_STEM}.geojson").write_bytes(GEOJSON)
    (docs / "review" / f"{CHANGE_STEM}.md").write_text(_change_markdown())
    _seed(db_path)
    plans = tmp_path / "plans-data"
    (plans / "berlin").mkdir(parents=True)
    (plans / "berlin" / "radverkehrsmassnahmen.geojson").write_text(json.dumps(MEASURES))
    (plans / "berlin" / "retrieved.json").write_text(json.dumps(RETRIEVED))
    return db_path, cfg, maps, docs, plans


def _app(rich, **kw):
    db_path, cfg, maps, docs, plans = rich
    return create_app(db_path, cfg, maps, docs, content_dir=CONTENT, plans_data_dir=plans, **kw)


def _pages(client) -> dict[str, str]:
    """path -> HTML of every page kind, the city tabs each city has included."""
    paths = list(PAGES)
    for city in CITIES:
        paths += [f"/city/{city}{suffix}" for _k, _l, suffix in TABS]
    out = {}
    for path in paths:
        r = client.get(path)
        if r.status_code == 404 and path.startswith("/city/"):
            continue  # a tab the city does not have (Bezirke, Counts)
        assert r.status_code == 200, path
        out[path] = r.text
    tabs = {p for p in out if p.startswith("/city/berlin/") and not p.endswith("/panel")}
    assert len(tabs) == len(TABS) - 1  # the fixture exercises every tab (Story is /city/berlin)
    return out


def test_every_internal_reference_carries_the_base_and_resolves(rich):
    with _client(_app(rich, base_path=BASE)) as c:
        pages = _pages(c)
        targets: set[str] = set()
        for path, html in pages.items():
            parser = _Refs()
            parser.feed(html)
            internal = [r for r in parser.refs if not _external(r[2]) and not r[2].startswith("#")]
            assert internal, path
            for tag, attr, value in internal:
                assert value.startswith(BASE), f"{path}: <{tag} {attr}={value!r}>"
                targets.add(value)
            for s in parser.json_strings:
                assert not ROUTE.match(s), f"{path}: JSON config URL without the base: {s!r}"
                if s.startswith(BASE):
                    targets.add(s)
        # each reference, the base taken off, is one of the app's routes (the base is not doubled
        # or dropped); a static file is served. (The fixture DB lacks cities the shipped content
        # links to, so a city route is matched, not fetched.)
        for target in sorted(targets):
            path = "/" + urlsplit(target).path.removeprefix(BASE)
            scope = {"type": "http", "path": path, "method": "GET", "root_path": ""}
            assert any(r.matches(scope)[0] == Match.FULL for r in c.app.router.routes), target
            if path.startswith("/static/"):
                assert c.get(path).status_code == 200, target


def _without_meta(html: str) -> str:
    return META_LINE.sub("", html)


def test_base_root_renders_what_identity_urls_render(rich, monkeypatch):
    """With base `/` every page is byte-identical to the page rendered with `u` the identity,
    apart from the two meta tags: the live app's HTML does not change."""
    with _client(_app(rich)) as c:
        live = _pages(c)
    monkeypatch.setattr(urls, "make_u", lambda base: lambda path: path)
    with _client(_app(rich)) as c:
        identity = _pages(c)
    assert live.keys() == identity.keys()
    for path in live:
        assert _without_meta(live[path]) == _without_meta(identity[path]), path


@pytest.mark.parametrize("base", ["/", BASE])
def test_every_page_carries_the_csp_and_base_meta_tags(rich, base):
    csp_tag = f'<meta http-equiv="Content-Security-Policy" content="{csp_meta(CSP)}">'
    base_tag = f'<meta name="velometer-base" content="{base}">'
    with _client(_app(rich, base_path=base)) as c:
        for path, html in _pages(c).items():
            if path.endswith("/panel"):
                continue  # a fragment fetched into a page that has them
            head = html.split("</head>")[0]
            assert head.count(csp_tag) == 1, path
            assert head.count(base_tag) == 1, path
            # before anything the policy governs is loaded
            assert head.index(csp_tag) < head.index("<script"), path
        assert c.get("/").headers["content-security-policy"] == CSP  # the header is unchanged


def test_app_state_has_the_normalised_base(rich):
    assert _app(rich, base_path="velometer").state.base_path == BASE
    assert _app(rich).state.base_path == "/"


def test_static_edition_footer_only_when_built_for_it(rich):
    with _client(_app(rich, static_edition={"commit": "abc1234"})) as c:
        for path, html in _pages(c).items():
            if not path.endswith("/panel"):
                assert f"{FOOTER_STAMP} abc1234" in html, path
    with _client(_app(rich)) as c:
        assert all(FOOTER_STAMP not in html for html in _pages(c).values())
