"""M17 Task 2b: every absolute URL M17 emits on the site's own origin names a file the static
server answers 200 for directly: a path ending in `/` is `<path>index.html`, any other path is
itself a file. A page exported as `<dir>/index.html` is never named without its slash (the
server would answer that with a redirect)."""

import json
import re
import zipfile
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import pytest

from tests.test_app_base import build_rich
from tests.test_m17_crawl import ORIGIN, _export
from tests.test_m17_datalab_crawl import _built
from velometer import dataset_bundle
from velometer.app.urls import absolute_url

DOI = "10.5281/zenodo.1234567"  # a test value, never committed config
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
LINK = re.compile(r"<link [^>]*>")
META = re.compile(r"<meta [^>]*>")
LD_URL_KEYS = ("url", "@id", "contentUrl")
DATALAB_ORIGIN = "https://example.org/"


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    rich = build_rich(tmp_path_factory.mktemp("slash-db"))
    with pytest.MonkeyPatch.context() as mp:
        yield _export(rich, tmp_path_factory.mktemp("slash-out"), mp, doi=DOI)


def _attr(tag: str, name: str) -> str | None:
    m = re.search(rf'{name}="([^"]*)"', tag)
    return unescape(m.group(1)) if m else None


def _ld_urls(obj) -> list[str]:
    """Every url-valued field (`url`, `@id`, `contentUrl`) of a JSON-LD object, nested ones too."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in LD_URL_KEYS and isinstance(v, str):
                found.append(v)
            else:
                found += _ld_urls(v)
    elif isinstance(obj, list):
        for v in obj:
            found += _ld_urls(v)
    return found


def _own_head_urls(html: str) -> list[str]:
    """The canonical, the hreflang alternates and og:url of a page's head: the page's own
    addresses, which are always on the site's origin."""
    head = html.split("</head>", 1)[0]
    urls = []
    for tag in LINK.findall(head):
        if _attr(tag, "rel") in ("canonical", "alternate"):
            urls.append(_attr(tag, "href"))
    for tag in META.findall(head):
        if _attr(tag, "property") == "og:url":
            urls.append(_attr(tag, "content"))
    return urls


def _head_urls(html: str) -> list[str]:
    """`_own_head_urls` and the JSON-LD urls of a page's head (which may name other sites)."""
    head = html.split("</head>", 1)[0]
    urls = _own_head_urls(html)
    for raw in LD.findall(head):
        urls += _ld_urls(json.loads(raw))
    return urls


def _sitemap_urls(site: Path) -> list[str]:
    root = ET.fromstring((site / "sitemap.xml").read_bytes())
    locs = [e.text or "" for e in root.findall("s:url/s:loc", NS)]
    return locs + [e.get("href") or "" for e in root.findall("s:url/x:link", NS)]


def _served_file(site: Path, origin: str, url: str) -> Path | None:
    """The file of `site` that answers `url` directly, or None if no file does (a redirect or a
    404 on the static server)."""
    parts = urlsplit(url)
    path = parts.path.removeprefix(urlsplit(origin).path)
    target = site / path / "index.html" if path.endswith("/") or not path else site / path
    return target if target.is_file() else None


def _assert_on_origin(origin: str, urls: list[str], where: str) -> None:
    """Every one of `urls` is on `origin`: `_assert_served` skips the others, so an address
    that should be the site's own is checked here first."""
    off = [u for u in urls if not u.startswith(origin)]
    assert not off, f"{where}: not on {origin}: {sorted(set(off))[:10]}"


def _assert_served(site: Path, origin: str, urls: list[str], where: str) -> int:
    own = [u for u in urls if u.startswith(origin)]
    bad = [u for u in own if _served_file(site, origin, u) is None]
    assert not bad, f"{where}: not answered 200 directly: {sorted(set(bad))[:10]}"
    return len(own)


def test_page_heads_name_served_files(out):
    """Canonical, hreflang alternates, og:url and JSON-LD url fields of every exported page."""
    checked = 0
    for page in sorted(out.rglob("*.html")):
        rel = page.relative_to(out).as_posix()
        html = page.read_text(encoding="utf-8")
        _assert_on_origin(ORIGIN, _own_head_urls(html), rel)
        checked += _assert_served(out, ORIGIN, _head_urls(html), rel)
    assert checked > 50


def test_jsonld_names_city_pages_and_csvs(out):
    """The home's collection lists city pages (`hasPart`) and CSVs (`contentUrl`): both kinds
    are checked, so the rule is exercised for pages and files alike."""
    urls = _head_urls((out / "index.html").read_text(encoding="utf-8"))
    assert any("/city/" in u for u in urls)
    assert any(u.endswith(".csv") for u in urls)


def test_sitemap_names_served_files(out):
    _assert_on_origin(ORIGIN, _sitemap_urls(out), "sitemap.xml")
    assert _assert_served(out, ORIGIN, _sitemap_urls(out), "sitemap.xml") > 10


def test_on_origin_check_refuses_another_origin(out):
    """Red-proof of `_assert_on_origin`: the same addresses, checked against a wrong origin."""
    with pytest.raises(AssertionError, match="not on"):
        _assert_on_origin("https://wrong.example/", _sitemap_urls(out), "sitemap.xml")
    html = (out / "index.html").read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match="not on"):
        _assert_on_origin("https://wrong.example/", _own_head_urls(html), "index.html")


def test_llms_txt_links_name_served_files(out):
    text = (out / "llms.txt").read_text(encoding="utf-8")
    links = re.findall(r"\]\((\S+?)\)", text)
    assert _assert_served(out, ORIGIN, links, "llms.txt") >= 4


def test_dataset_readme_methodology_link_is_served(out, tmp_path):
    zpath, _ = dataset_bundle.bundle(out, tmp_path / "bundle")
    with zipfile.ZipFile(zpath) as z:
        readme = z.read("README.md").decode("utf-8")
    # a link that ends a sentence is followed by its punctuation, which is not part of the URL
    links = [u.rstrip(".,;:") for u in re.findall(r"https?://[^\s)>\]]+", readme)]
    assert _assert_served(out, ORIGIN, links, "README.md") >= 1


def test_datalab_sitemap_and_og_url_name_served_files(tmp_path):
    site = _built(tmp_path)
    _assert_on_origin(DATALAB_ORIGIN, _sitemap_urls(site), "datalab sitemap")
    assert _assert_served(site, DATALAB_ORIGIN, _sitemap_urls(site), "datalab sitemap") >= 4
    checked = 0
    for page in sorted(site.rglob("*.html")):
        html, rel = page.read_text(encoding="utf-8"), page.relative_to(site).as_posix()
        _assert_on_origin(DATALAB_ORIGIN, _own_head_urls(html), rel)
        checked += _assert_served(site, DATALAB_ORIGIN, _head_urls(html), rel)
    assert checked >= 4


@pytest.mark.parametrize(
    ("rel", "want"),
    [
        ("/", "https://h.example/"),
        ("/de/", "https://h.example/de/"),
        ("/de", "https://h.example/de/"),
        ("/methodology", "https://h.example/methodology/"),
        ("/city/berlin", "https://h.example/city/berlin/"),
        ("/city/berlin#dataset", "https://h.example/city/berlin/#dataset"),
        ("/impressum/", "https://h.example/impressum/"),
        ("/data/all.csv", "https://h.example/data/all.csv"),
        ("/build.json", "https://h.example/build.json"),
        ("/sitemap.xml", "https://h.example/sitemap.xml"),
        ("/sub/city/berlin", "https://h.example/city/berlin/"),
    ],
)
def test_absolute_url_rule(rel, want):
    base = "/sub/" if rel.startswith("/sub/") else "/"
    assert absolute_url("https://h.example/", rel, base) == want
