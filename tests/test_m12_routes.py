"""M12 Task 2: German page routes under /de/, the language switch, head links, the bilingual
404, the German search index and language in the page-cache keys (spec decision 1)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_a11y import all_page_urls  # noqa: F401  (fixture: HTML URLs of the export)
from tests.test_app import client, setup  # noqa: F401  (fixtures)
from tests.test_app_base import rich  # noqa: F401  (fixture)
from velometer.app import urls

FIRST_TAG = re.compile(r"\s*<(?!!)([a-z]+)([^>]*)>")


def english_pages(all_urls):
    return [u for u in all_urls if urls.lang_of(u) == "en"]


def _lang_of_document(html):
    m = re.search(r"<html\b[^>]*\blang=\"([^\"]+)\"", html)
    if m:  # a full page
        return m[1]
    root = FIRST_TAG.match(html)  # a fragment: its root element carries the language
    lang = re.search(r'\blang="([^"]+)"', root[2]) if root else None
    return lang and lang[1]


def test_every_page_has_a_german_twin_in_german(all_page_urls, page_site):  # noqa: F811
    english = english_pages(all_page_urls)
    assert english and all(urls.with_lang(u, "de") in all_page_urls for u in english)
    for url in english:
        twin = urls.with_lang(url, "de")
        assert page_site.status[twin] == 200, url
        assert _lang_of_document(page_site.html[url]) == "en", url
        assert _lang_of_document(page_site.html[twin]) == "de", url


def test_head_links_and_switch(client):  # noqa: F811
    pairs = [("/", "/de/"), ("/city/berlin/time", "/de/city/berlin/time"),
             ("/methodology", "/methodology/de")]  # fmt: skip
    for en, de in pairs:
        de_twin = urls.with_lang(urls.strip_lang(de), "de")
        for path, lang in [(en, "en"), (de, "de")]:
            html = client.get(path).text
            assert f'<link rel="alternate" hreflang="en" href="{urls.strip_lang(en)}">' in html
            assert f'<link rel="alternate" hreflang="de" href="{de_twin}">' in html
            x_default = f'<link rel="alternate" hreflang="x-default" href="{urls.strip_lang(en)}">'
            assert x_default in html
            other = de_twin if lang == "en" else urls.strip_lang(en)
            assert re.search(rf'<a class="lang-switch"[^>]*\bhref="{re.escape(other)}"', html)


def _page_links(html):
    """(href, exempt) for every root-relative URL in <a>/<link> href, <form> action and JSON
    script blocks; the language switch and the alternate links are exempt."""
    out = []
    for tag in re.findall(r"<(?:a|link|form)\b[^>]*>", html):
        href = re.search(r'\b(?:href|action)="(/[^"]*)"', tag)
        if href:
            exempt = 'class="lang-switch"' in tag or 'rel="alternate"' in tag
            out.append((href[1], exempt))
    for block in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S):
        out += [(u, False) for u in re.findall(r'"(/[^"\s]*)"', block)]
    return out


def test_german_pages_never_link_to_english_twins(all_page_urls, page_site):  # noqa: F811
    bad = []
    for de in (u for u in all_page_urls if urls.lang_of(u) == "de"):
        for href, exempt in _page_links(page_site.html[de]):
            # data, maps, static files and the basemap file (M16) are the same in every language
            if exempt or href.startswith(("/data/", "/maps/", "/static/", "/de/data/", "/tiles/")):
                continue
            if not (href == "/de" or href.startswith(("/de/", "/de?", "/de#"))):
                bad.append(f"{de}: {href}")
    assert bad == []


def test_legacy_methodology_de_is_german_with_a_canonical_link(client):  # noqa: F811
    html = client.get("/methodology/de").text
    assert _lang_of_document(html) == "de"
    assert '<link rel="canonical" href="/de/methodology">' in html
    assert client.get("/de/methodology").status_code == 200


@pytest.mark.parametrize("path,first", [("/no-such-page", "en"), ("/de/no-such-page", "de"),
                                        ("/fr/cities", "en")])  # fmt: skip
def test_404_is_bilingual_and_takes_its_language_from_the_prefix(client, path, first):  # noqa: F811
    r = client.get(path)
    assert r.status_code == 404
    assert _lang_of_document(r.text) == first
    assert '<div lang="de"' in r.text or first == "de"
    assert '<div lang="en"' in r.text or first == "en"


def test_page_links_see_form_actions():
    html = '<form class="f" action="/compare" method="get"></form><a href="/de/x">x</a>'
    assert _page_links(html) == [("/compare", False), ("/de/x", False)]


def test_german_search_index(client):  # noqa: F811
    assert client.get("/de/data/search.json").status_code == 200


def test_the_legacy_german_methodology_is_only_in_the_english_index(client):  # noqa: F811
    # search.js puts the page's /de in front of every entry: /methodology/de would be a 404
    en = {e["url"] for e in client.get("/data/search.json").json()}
    de = {e["url"] for e in client.get("/de/data/search.json").json()}
    assert "/methodology/de" in en and "/methodology" in en
    assert "/methodology/de" not in de and "/methodology" in de


def test_german_routes_bind_german_data(setup, monkeypatch):  # noqa: F811
    # the page and the German search index read ReportData in their language (its display text
    # will be localised); an English route reads English data
    from tests.test_app import CONTENT, _client
    from velometer.app import main
    from velometer.report.data import ReportData

    seen: list[str] = []
    real_cities, real_index = ReportData.cities, main.search_index
    monkeypatch.setattr(
        ReportData, "cities", lambda self: seen.append(self.lang) or real_cities(self)
    )
    monkeypatch.setattr(
        main, "search_index", lambda data, *a: seen.append(data.lang) or real_index(data, *a)
    )
    for path, lang in [("/de/data/search.json", "de"), ("/data/search.json", "en"),
                       ("/de/cities", "de"), ("/cities", "en"), ("/de/city/berlin", "de"),
                       ("/methodology/de", "de"), ("/no-such-page", "en"),
                       ("/de/no-such-page", "de")]:  # fmt: skip
        seen.clear()
        with _client(main.create_app(*setup, content_dir=CONTENT)) as c:  # a cold page cache
            assert c.get(path).status_code in (200, 404), path
        assert seen and set(seen) == {lang}, (path, seen)


# Every page-cache key family of main.py: language-keyed (`…:{lang}`) unless listed here as
# language-free (numbers, raw content, CSV), which a later task moves when its content is localised
MAIN = (Path(__file__).parents[1] / "src" / "velometer" / "app" / "main.py").read_text()
CACHE_KEY = re.compile(r'cache\.get\(\s*f?"([^"]+)"')
LANGUAGE_FREE = {"series", "cite", "csv", "csv-subareas"}
KEYS = CACHE_KEY.findall(MAIN)
LANG_KEY = re.compile(r":(\{(request\.state\.)?lang\}|en|de)$")  # `…:{lang}`, or one per language
LANG_FAMILIES = sorted({k.split(":")[0] for k in KEYS if LANG_KEY.search(k)})
# a German page that builds each family (the fixture has Berlin's figures, Bezirke and plan)
GERMAN_PATHS = ["/de/", "/de/cities", "/de/stories", "/de/data/search.json", "/de/city/berlin",
                "/de/city/berlin/figures", "/de/city/berlin/counts", "/de/differences",
                "/de/organisations", "/de/sources", "/de/plans", "/de/plans/berlin"]  # fmt: skip


def test_every_cache_key_family_is_language_keyed_or_declared_free():
    families = {k.split(":")[0] for k in KEYS}
    assert len(LANG_FAMILIES) >= 10  # the scan sees the code
    assert families - set(LANG_FAMILIES) <= LANGUAGE_FREE, families - set(LANG_FAMILIES)


def test_page_cache_keys_carry_the_language(rich, monkeypatch):  # noqa: F811
    # every language-keyed family (derived from the code above) is built under `:de` by a
    # German page; `rich` has Berlin's counts, Bezirke and plan data
    from tests.test_app_base import _app
    from velometer.app import cache

    seen = []
    real = cache.PageCache.get
    monkeypatch.setattr(
        cache.PageCache,
        "get",
        lambda self, n, fp, build: seen.append(n) or real(self, n, fp, build),
    )
    with TestClient(_app(rich), base_url="http://127.0.0.1:8000") as c:
        for path in GERMAN_PATHS:
            assert c.get(path).status_code == 200, path
    missing = [f for f in LANG_FAMILIES if not any(s.startswith(f"{f}:") and s.endswith(":de")
                                                    for s in seen)]  # fmt: skip
    assert missing == [], seen


URL_ANYWHERE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://|\bwww\.|(?<![\w.])/[a-z]+/", re.I)


def test_ui_strings_block_has_no_url(client):  # noqa: F811
    # the M11 export-scan rule: a URL-shaped string in a page's JSON must resolve under the base;
    # the JS strings are text and hold none
    import json

    from velometer.app.export import URL_SHAPED

    def strings(v):
        return [v] if isinstance(v, str) else [s for x in v.values() for s in strings(x)]

    for path in ("/de/", "/", "/de/compare"):
        html = client.get(path).text
        block = re.search(
            r'<script type="application/json" id="ui-strings">(.*?)</script>', html, re.S
        )
        assert block, path
        data = json.loads(block[1])
        assert data and all(k.startswith("js.") for k in data), path
        assert [s for s in strings(data) if URL_SHAPED.match(s)] == [], path
        # nor anywhere inside a sentence: a scheme URL or a site path in text would dodge the scan
        assert [s for s in strings(data) if URL_ANYWHERE.search(s)] == [], path
