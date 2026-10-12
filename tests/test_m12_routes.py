"""M12 Task 2: German page routes under /de/, the language switch, head links, the bilingual
404, the German search index and language in the page-cache keys (spec decision 1)."""

import re

import pytest

from tests.test_a11y import all_page_urls  # noqa: F401  (fixture: HTML URLs of the export)
from tests.test_app import client, setup  # noqa: F401  (fixtures)
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


def test_every_page_has_a_german_twin_in_german(client, all_page_urls):  # noqa: F811
    english = english_pages(all_page_urls)
    assert english and all(urls.with_lang(u, "de") in all_page_urls for u in english)
    for url in english:
        en, de = client.get(url), client.get(urls.with_lang(url, "de"))
        assert de.status_code == 200, url
        assert _lang_of_document(en.text) == "en", url
        assert _lang_of_document(de.text) == "de", url


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
    """(href, exempt) for every root-relative URL in <a>/<link> markup and in JSON script
    blocks; the language switch and the alternate links are exempt."""
    out = []
    for tag in re.findall(r"<(?:a|link)\b[^>]*>", html):
        href = re.search(r'\bhref="(/[^"]*)"', tag)
        if href:
            exempt = 'class="lang-switch"' in tag or 'rel="alternate"' in tag
            out.append((href[1], exempt))
    for block in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S):
        out += [(u, False) for u in re.findall(r'"(/[^"\s]*)"', block)]
    return out


def test_german_pages_never_link_to_english_twins(client, all_page_urls):  # noqa: F811
    bad = []
    for de in (u for u in all_page_urls if urls.lang_of(u) == "de"):
        for href, exempt in _page_links(client.get(de).text):
            if exempt or href.startswith(("/data/", "/maps/", "/static/", "/de/data/")):
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


def test_german_search_index(client):  # noqa: F811
    assert client.get("/de/data/search.json").status_code == 200


@pytest.mark.parametrize("name", ["nav", "footer", "index", "cities", "search", "stories"])
def test_page_cache_keys_carry_the_language(client, monkeypatch, name):  # noqa: F811
    from velometer.app import cache

    seen = []
    real = cache.PageCache.get
    monkeypatch.setattr(
        cache.PageCache,
        "get",
        lambda self, n, fp, build: seen.append(n) or real(self, n, fp, build),
    )
    for path in ["/de/", "/de/cities", "/de/stories", "/de/data/search.json"]:
        client.get(path)
    assert any(s.startswith(f"{name}:") and s.endswith(":de") for s in seen), seen
