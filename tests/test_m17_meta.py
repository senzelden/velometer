"""M17 Task 5: meta descriptions and OpenGraph/Twitter tags on every indexable page."""

import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from tests.test_app_base import build_rich
from tests.test_export import _content
from tests.test_m17_crawl import ORIGIN, _export, _indexable
from tests.test_m17_datalab_crawl import _built
from velometer import datalab, i18n
from velometer.app import meta
from velometer.app.main import create_app
from velometer.app.urls import with_lang
from velometer.config import load_cities

REPO = Path(__file__).resolve().parents[1]
LOCALE = {"en": "en_GB", "de": "de_DE"}


class _Head(HTMLParser):
    """The `<meta>` tags (name or property -> every content given) and the canonical href of a
    page's head, attribute values decoded."""

    def __init__(self):
        super().__init__()
        self.meta: dict[str, list[str]] = {}
        self.canonical: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and ("name" in a or "property" in a):
            self.meta.setdefault(a.get("name") or a["property"], []).append(a.get("content", ""))
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a["href"]


def _head(html: str) -> _Head:
    h = _Head()
    h.feed(html.split("</head>", 1)[0])
    return h


def _one(h: _Head, key: str) -> str:
    values = h.meta.get(key, [])
    assert len(values) == 1, (key, values)
    return values[0]


def _page(out: Path, route: str) -> Path:
    return out / route.lstrip("/") / "index.html"


@pytest.fixture(scope="module")
def public_out(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("meta")
    rich = build_rich(tmp)
    with pytest.MonkeyPatch.context() as mp:
        yield _export(rich, tmp, mp)


def _editions(out: Path) -> dict[str, list[str]]:
    en = _indexable(out)
    return {"en": en, "de": [with_lang(r, "de") for r in en]}


def test_every_indexable_page_has_description(public_out):
    """One description of 50–160 characters per page, plain text, and no two pages of an
    edition share one."""
    editions = _editions(public_out)
    assert len(editions["en"]) > 10
    for routes in editions.values():
        seen: dict[str, str] = {}
        for route in routes:
            desc = _one(_head(_page(public_out, route).read_text(encoding="utf-8")), "description")
            assert meta.MIN <= len(desc) <= meta.MAX, (route, len(desc), desc)
            assert not re.search(r"[<>{}]", desc), (route, desc)
            assert desc not in seen, (route, seen.get(desc), desc)
            seen[desc] = route


def test_og_and_twitter_tags(public_out):
    for lang, routes in _editions(public_out).items():
        other = "de" if lang == "en" else "en"
        for route in routes:
            h = _head(_page(public_out, route).read_text(encoding="utf-8"))
            assert _one(h, "og:title"), route
            assert _one(h, "og:description") == _one(h, "description"), route
            assert _one(h, "og:locale") == LOCALE[lang], route
            assert _one(h, "og:locale:alternate") == LOCALE[other], route
            assert _one(h, "og:site_name") == "velometer", route
            assert _one(h, "twitter:card") == "summary", route


def test_og_url_equals_canonical(public_out):
    """Every exported page with a canonical (the legacy `/methodology/de` too, whose canonical
    is the German edition's) has og:url equal to it; the 404 page has neither."""
    checked = 0
    for page in public_out.rglob("index.html"):
        h = _head(page.read_text(encoding="utf-8"))
        if h.canonical is None:  # a panel fragment: no head
            assert "og:url" not in h.meta, page
            continue
        og = _one(h, "og:url")
        assert og == h.canonical, page
        assert og.startswith(ORIGIN), (page, og)  # absolute, on the public origin
        checked += 1
    assert checked > 20
    h = _head((public_out / "404.html").read_text(encoding="utf-8"))
    assert h.canonical is None
    assert "og:url" not in h.meta and "description" not in h.meta


def _app_without_dek(tmp_path: Path):
    rich = build_rich(tmp_path)
    db_path, cfg, maps, docs, plans = rich
    content = tmp_path / "content-no-dek"
    shutil.copytree(_content(rich), content)
    path = content / "narratives" / "berlin.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["dek"] = ""
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return create_app(db_path, cfg, maps, docs, content_dir=content, plans_data_dir=plans)


def test_description_falls_back_without_dek(tmp_path):
    """A city whose dek is empty gets the `meta.city` sentence with its headline figure."""
    with TestClient(_app_without_dek(tmp_path), base_url="http://127.0.0.1:8000") as c:
        r = c.get("/city/berlin")
    assert r.status_code == 200
    desc = _one(_head(r.text), "description")
    pattern = re.escape(i18n.t("en", "meta.city", city="Berlin", value="\x00"))
    assert re.fullmatch(pattern.replace("\x00", r"[0-9][0-9,]*\.[0-9]"), desc), desc


CITY_NAMES = sorted({c.name for c in load_cities(REPO / "config" / "cities.yaml")}, key=len)


def test_city_names_include_the_extremes():
    """The bound test below runs over every shipped name, so the shortest and the longest."""
    assert len(CITY_NAMES) > 1 and len(CITY_NAMES[0]) < len(CITY_NAMES[-1])


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("tab", ["story", "time", "tiers", "figures", "counts", "bezirke"])
def test_description_without_value(lang, tab):
    """Without a current headline value a city page's sentence leaves the figure out; with
    one it names it. Each fits the bounds for every shipped city name (the shortest against
    MIN, the longest against MAX) and for a short and a long figure."""
    for city in CITY_NAMES:
        without = meta.city_description(lang, tab, city, "", None)
        assert without and not re.search(r"[0-9{}]", re.sub(r"\b100 km\b", "", without)), without
        assert city in without and "None" not in without
        assert meta.MIN <= len(without) <= meta.MAX, without
        for number in (0.5, 1234.5):
            value = i18n.number(number, lang)
            with_value = meta.city_description(lang, tab, city, "", value)
            assert value in with_value
            assert meta.MIN <= len(with_value) <= meta.MAX, with_value


def test_german_page_with_english_dek_takes_the_sentence():
    from velometer.app.narrative import Fallback

    dek = Fallback("Mapped A+B rose from 161 to 244 km between 2018 and October 2026.")
    assert meta.city_description("de", "story", "Berlin", dek, "1,0") == meta.plain(
        i18n.t("de", "meta.city", city="Berlin", value="1,0")
    )


def test_long_dek_falls_back_to_the_city_sentence():
    """A dek over `MAX` is never cut: the page takes exactly the `meta.city` sentence."""
    head = "Mapped A+B km per 100 km of main roads went from 113.7 in 2018 to 109.1 in 2026"
    dek = head + ": one step down in a 2022 re-mapping campaign, " + "a slow climb since " * 4
    assert len(dek) > meta.MAX
    for lang, value in (("en", "109.1"), ("de", "109,1")):
        desc = meta.city_description(lang, "story", "Berlin", dek, value)
        assert desc == meta.plain(i18n.t(lang, "meta.city", city="Berlin", value=value))
        assert not desc.startswith(head[:20])
    assert meta.city_description("en", "story", "Berlin", dek, None) == meta.plain(
        i18n.t("en", "meta.city_plain", city="Berlin")
    )
    assert meta.city_description("en", "story", "Berlin", "Too short.", "1.0") == meta.plain(
        i18n.t("en", "meta.city", city="Berlin", value="1.0")
    )


def test_dek_in_range_is_the_description_verbatim():
    dek = "The headline rose from 18.7 in 2018 to 29.6 in October 2026, while lanes tripled."
    assert meta.MIN <= len(dek) <= meta.MAX
    assert meta.city_description("en", "story", "Praha", dek, "29.6") == dek


def _deks() -> list[tuple[str, str]]:
    out = []
    for path in sorted((REPO / "content" / "narratives").glob("*.yaml")):
        out.append((path.stem, yaml.safe_load(path.read_text(encoding="utf-8"))["dek"]))
    for path in sorted((REPO / "content" / "narratives" / "de").glob("*.yaml")):
        out.append((f"de/{path.stem}", yaml.safe_load(path.read_text(encoding="utf-8"))["dek"]))
    return out


@pytest.mark.parametrize(("name", "dek"), _deks(), ids=[n for n, _ in _deks()])
def test_every_shipped_dek_makes_a_description(name, dek):
    """Each shipped story page, en and de, has a description within the bounds: its dek
    verbatim, or the city sentence (the fixture export holds only a few cities)."""
    text = dek["text"] if isinstance(dek, dict) else dek
    lang = "de" if name.startswith("de/") else "en"
    value = i18n.number(1234.5, lang)
    desc = meta.city_description(lang, "story", "København", text, value)
    assert meta.MIN <= len(desc) <= meta.MAX, (name, desc)
    city = meta.plain(i18n.t(lang, "meta.city", city="København", value=value))
    assert desc == (meta.plain(text) if meta.fits(meta.plain(text)) else city), name


def test_datalab_pages_have_description(tmp_path):
    out = _built(tmp_path)
    seen = set()
    og_urls = []
    for route in datalab.page_routes():
        h = _head((out / route.lstrip("/") / "index.html").read_text(encoding="utf-8"))
        desc = _one(h, "description")
        assert meta.MIN <= len(desc) <= meta.MAX, (route, desc)
        assert desc not in seen, route
        seen.add(desc)
        assert _one(h, "og:description") == desc
        assert _one(h, "og:title")
        assert _one(h, "og:url") == f"https://example.org{route}"
        og_urls.append(_one(h, "og:url"))
        assert _one(h, "og:locale") == "de_DE"
        assert "og:locale:alternate" not in h.meta
        assert _one(h, "og:site_name") == datalab.SITE_NAME
        assert _one(h, "twitter:card") == "summary"
    # each page's og:url is its sitemap entry, and every sitemap entry is a page's og:url
    locs = re.findall(r"<loc>([^<]+)</loc>", (out / "sitemap.xml").read_text(encoding="utf-8"))
    assert sorted(og_urls) == sorted(locs)
    h = _head((out / datalab.NOT_FOUND_PAGE).read_text(encoding="utf-8"))
    assert "description" not in h.meta and "og:url" not in h.meta
