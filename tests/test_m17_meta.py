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
from tests.test_m17_crawl import _export, _indexable
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
        assert _one(h, "og:url") == h.canonical, page
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


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("tab", ["story", "time", "tiers", "figures", "counts", "bezirke"])
def test_description_without_value(lang, tab):
    """Without a current headline value a city page's sentence leaves the figure out; with
    one it names it. Each fits the bounds for the longest shipped city name."""
    city = max((c.name for c in load_cities(REPO / "config" / "cities.yaml")), key=len)
    value = i18n.number(1234.5, lang)
    with_value = meta.city_description(lang, tab, city, "", value)
    without = meta.city_description(lang, tab, city, "", None)
    assert value in with_value
    assert without and not re.search(r"[0-9{}]", re.sub(r"\b100 km\b", "", without)), without
    assert city in without and "None" not in without
    for desc in (with_value, without):
        assert meta.MIN <= len(desc) <= meta.MAX, desc


def test_german_page_with_english_dek_takes_the_sentence():
    from velometer.app.narrative import Fallback

    dek = Fallback("Mapped A+B rose from 161 to 244 km between 2018 and October 2026.")
    assert meta.city_description("de", "story", "Berlin", dek, "1,0") == meta.plain(
        i18n.t("de", "meta.city", city="Berlin", value="1,0")
    )


def test_long_text_is_shortened_at_a_clause():
    """A long text ends at its last clause end that fits, else at its first comma that leaves
    enough, else at a word."""
    head = "A" * 70 + " went from 1,279 to 1,292 km in 2026"
    assert meta.shorten(head + ", c d; " + "b " * 60) == head + ", c d."
    assert meta.shorten(head + ", c d, e f, " + "b " * 60) == head + "."
    words = "word " * 50
    out = meta.shorten(words)
    assert len(out) <= meta.MAX and out.endswith("word…")


def _deks() -> list[tuple[str, str]]:
    out = []
    for path in sorted((REPO / "content" / "narratives").glob("*.yaml")):
        out.append((path.stem, yaml.safe_load(path.read_text(encoding="utf-8"))["dek"]))
    for path in sorted((REPO / "content" / "narratives" / "de").glob("*.yaml")):
        out.append((f"de/{path.stem}", yaml.safe_load(path.read_text(encoding="utf-8"))["dek"]))
    return out


@pytest.mark.parametrize(("name", "dek"), _deks(), ids=[n for n, _ in _deks()])
def test_every_shipped_dek_makes_a_description(name, dek):
    """Each shipped dek, en and de, gives a description within the bounds (the fixture export
    holds only a few cities)."""
    text = dek["text"] if isinstance(dek, dict) else dek
    desc = meta.shorten(meta.plain(text))
    assert meta.MIN <= len(desc) <= meta.MAX, (name, desc)


def test_datalab_pages_have_description(tmp_path):
    out = _built(tmp_path)
    seen = set()
    for route in datalab.page_routes():
        h = _head((out / route.lstrip("/") / "index.html").read_text(encoding="utf-8"))
        desc = _one(h, "description")
        assert meta.MIN <= len(desc) <= meta.MAX, (route, desc)
        assert desc not in seen, route
        seen.add(desc)
        assert _one(h, "og:description") == desc
        assert _one(h, "og:title")
        assert _one(h, "og:url") == f"https://example.org{route}"
        assert _one(h, "og:locale") == "de_DE"
        assert "og:locale:alternate" not in h.meta
        assert _one(h, "og:site_name") == "Zählwerk Berlin Datalab"
        assert _one(h, "twitter:card") == "summary"
    h = _head((out / datalab.NOT_FOUND_PAGE).read_text(encoding="utf-8"))
    assert "description" not in h.meta and "og:url" not in h.meta
