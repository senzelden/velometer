"""M17 Task 2: absolute canonical and hreflang links in a public export; relative otherwise."""

import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from tests.test_app import CONTENT
from tests.test_app_base import rich  # noqa: F401  (`rich` is a fixture)
from velometer.app import export
from velometer.app.main import create_app
from velometer.report.data import ReportData, open_readonly

ORIGIN = "https://velometer.example.org/"
LEGACY = "/methodology/de"
BASE_URL = "http://127.0.0.1:8000"


def _head_links(html: str, rel: str) -> dict[str, str]:
    """hreflang (or "" for a canonical) -> href of the `<link rel=...>` tags of a page."""
    out = {}
    for tag in re.findall(r"<link [^>]*>", html):
        if f'rel="{rel}"' in tag:
            lang = re.search(r'hreflang="([^"]+)"', tag)
            out[lang.group(1) if lang else ""] = re.search(r'href="([^"]*)"', tag).group(1)
    return out


def _app(rich, url, public=True, base="/"):  # noqa: F811
    db_path, cfg, maps, docs, plans = rich
    # the fixture config may carry the shipped site.public.yaml: both files name the same origin
    for name in ("site.yaml", "site.public.yaml"):
        (Path(cfg) / name).write_text(f"url: {url or 'null'}\n", encoding="utf-8")
    return create_app(
        db_path, cfg, maps, docs, content_dir=CONTENT, plans_data_dir=plans,
        base_path=base, public=public,
    )  # fmt: skip


def _city(rich) -> str:  # noqa: F811
    conn = open_readonly(Path(rich[0]))
    try:
        return ReportData(conn, rich[1]).cities()[0].id
    finally:
        conn.close()


def test_public_alternates_absolute(rich):  # noqa: F811
    city = _city(rich)
    with TestClient(_app(rich, ORIGIN), base_url=BASE_URL) as c:
        alt = _head_links(c.get(f"/city/{city}").text, "alternate")
    assert alt["en"] == f"{ORIGIN}city/{city}/"
    assert alt["de"] == f"{ORIGIN}de/city/{city}/"
    assert alt["x-default"] == alt["en"]


def test_canonical_self(rich):  # noqa: F811
    """Every exported HTML page's canonical is its own absolute URL; the legacy page's is the
    German edition's."""
    app = _app(rich, ORIGIN)
    conn = open_readonly(Path(rich[0]))
    try:
        urls = export.export_urls(ReportData(conn, rich[1]), app)
    finally:
        conn.close()
    checked = 0
    with TestClient(app, base_url=BASE_URL) as c:
        for url in urls:
            r = c.get(url)
            if not r.headers["content-type"].startswith("text/html") or "<html" not in r.text:
                continue  # data files and the panel fragments have no head
            canon = _head_links(r.text, "canonical")[""]
            # every page is exported as `<dir>/index.html`: its URL ends in `/` (Task 2b)
            own = ORIGIN + (f"{url.strip('/')}/" if url.strip("/") else "")
            want = ORIGIN + "de/methodology/" if url == LEGACY else own
            assert canon == want, url
            checked += 1
    assert checked > 10


@pytest.mark.parametrize("path", ["/no-such-page", "/de/no-such-page"])
def test_not_found_page_has_no_canonical_and_no_alternates(rich, path):  # noqa: F811
    """The 404 page is no page of the site: no canonical, and no hreflang alternates, which
    would name pages that do not name it back (alternates are reciprocal)."""
    with TestClient(_app(rich, ORIGIN), base_url=BASE_URL) as c:
        r = c.get(path)
    assert r.status_code == 404
    head = r.text.split("</head>", 1)[0]
    assert _head_links(head, "canonical") == {}
    assert "hreflang" not in head


@pytest.mark.parametrize("public", [True, False])
def test_preview_alternates_relative(rich, public):  # noqa: F811
    """Without a url, or when the app is not a public export, every href starts with the base."""
    city = _city(rich)
    app = _app(rich, None if public else ORIGIN, public=public, base="/velo/")
    with TestClient(app, base_url=BASE_URL) as c:
        html = c.get(f"/city/{city}").text
    links = _head_links(html, "alternate") | _head_links(html, "canonical")
    assert links
    assert all(v.startswith("/velo/") for v in links.values()), links


def test_public_base_path_not_doubled(rich):  # noqa: F811
    app = _app(rich, ORIGIN, base="/velo/")
    with TestClient(app, base_url=BASE_URL) as c:
        alt = _head_links(c.get("/cities").text, "alternate")
    assert alt["en"] == f"{ORIGIN}cities/"


def test_public_export_writes_absolute_head_urls(rich, tmp_path, monkeypatch):  # noqa: F811
    """`export --public` builds its app as a public one; a plain export of the same config does
    not, though the config names a url."""
    from tests.test_export import _content

    db_path, cfg, maps, docs, plans = rich
    site = {
        "url": ORIGIN,
        "datalab": {"name": "Datalab", "url": "https://datalab.example.org/"},
        "impressum_url": "https://datalab.example.org/impressum",
        "privacy_url": "https://datalab.example.org/datenschutz",
        "accessibility_url": "https://datalab.example.org/barrierefreiheit",
        "repo": {
            "url": "https://forge.example.org/o/velometer",
            "file_url": "https://forge.example.org/o/velometer/blob/{commit}/{path}",
        },
    }
    (Path(cfg) / "site.yaml").write_text(yaml.safe_dump(site), encoding="utf-8")
    (Path(cfg) / "site.public.yaml").unlink(missing_ok=True)
    monkeypatch.setattr(export, "public_commit", lambda: "0123456789abcdef0123456789abcdef01234567")
    monkeypatch.setattr(export, "figures_drift", lambda conn, config_dir: [])
    monkeypatch.setattr(export, "config_drift", lambda config_dir: [])
    tiles = tmp_path / "t.json"
    tiles.write_text(
        '{"file":"t.pmtiles","protomaps_build":"2026-08-11","maxzoom":13,"sha256":"'
        + "ab" * 32
        + '"}'
    )
    content = _content(rich)
    heads = {}
    for public in (True, False):
        out = tmp_path / f"out-{public}"
        export.run_export(
            out, "/", db_path, cfg, maps, docs, content, plans, False, public=public,
            tiles_info=tiles,
        )  # fmt: skip
        heads[public] = _head_links((out / "cities" / "index.html").read_text(), "canonical")[""]
    assert heads[True] == f"{ORIGIN}cities/"
    assert heads[False] == "/cities"


def test_scan_follows_canonical_and_alternate_links_but_loads_no_stylesheet(tmp_path):
    """An absolute canonical or alternate link is a link (crawlers follow it); an external
    stylesheet, even one marked alternate, is still a load the scan refuses."""
    head = (
        '<link rel="canonical" href="https://a.example.org/">'
        '<link rel="alternate" hreflang="de" href="https://a.example.org/de/">'
    )
    (tmp_path / "index.html").write_text(f"<html><head>{head}</head></html>")
    assert export.scan_references(tmp_path, "/") == []
    css = '<link rel="alternate stylesheet" href="https://a.example.org/x.css">'
    (tmp_path / "index.html").write_text(f"<html><head>{css}</head></html>")
    assert [u.ref for u in export.scan_references(tmp_path, "/")] == ["https://a.example.org/x.css"]
