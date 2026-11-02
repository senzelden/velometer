"""M17 Task 3: robots.txt, sitemap.xml and llms.txt of an export, and deploy-check on them."""

import os
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import yaml

from tests.test_app_base import rich  # noqa: F401  (`rich` is a fixture)
from tests.test_export import _content
from velometer.app import crawl, export
from velometer.app.deploy_check import deploy_problems
from velometer.app.urls import with_lang
from velometer.config import ConfigError

ORIGIN = "https://velometer.example.org/"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}
REPO = Path(__file__).resolve().parents[1]


def _site_yaml(cfg: Path, doi: str | None = None) -> None:
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
    if doi:
        site["dataset_doi"] = doi
    (Path(cfg) / "site.yaml").write_text(yaml.safe_dump(site), encoding="utf-8")
    (Path(cfg) / "site.public.yaml").unlink(missing_ok=True)


def _export(rich, tmp_path, monkeypatch, name="out", public=True, doi=None):  # noqa: F811
    db_path, cfg, maps, docs, plans = rich
    _site_yaml(cfg, doi)
    monkeypatch.setattr(export, "public_commit", lambda: "0123456789abcdef0123456789abcdef01234567")
    monkeypatch.setattr(export, "figures_drift", lambda conn, config_dir: [])
    monkeypatch.setattr(export, "config_drift", lambda config_dir: [])
    tiles = tmp_path / "t.json"
    tiles.write_text(
        '{"file":"t.pmtiles","protomaps_build":"2026-08-11","maxzoom":13,"sha256":"'
        + "ab" * 32
        + '"}'
    )
    out = tmp_path / name
    export.run_export(
        out, "/", db_path, cfg, maps, docs, _content(rich), plans, False, public=public,
        tiles_info=tiles,
    )  # fmt: skip
    return out


@pytest.fixture
def public_out(rich, tmp_path, monkeypatch):  # noqa: F811
    return _export(rich, tmp_path, monkeypatch)


def _routes(out: Path) -> list[str]:
    """The routes of the HTML pages written under `out` (the 404 page and fragments aside)."""
    routes = []
    for page in sorted(out.rglob("index.html")):
        rel = page.parent.relative_to(out).as_posix()
        routes.append("/" if rel == "." else f"/{rel}")
    return routes


def _abs(route: str) -> str:
    """A page route's absolute URL in the form the static server answers 200 for: every page is
    a `<dir>/index.html`, so it ends in `/` (Task 2b)."""
    inner = route.strip("/")
    return ORIGIN + (f"{inner}/" if inner else "")


def _indexable(out: Path) -> list[str]:
    return crawl.indexable(_routes(out))


def _sitemap(out: Path) -> ET.Element:
    return ET.fromstring((out / "sitemap.xml").read_bytes())


def test_indexable_rule():
    urls = [
        "/", "/cities", "/methodology", "/methodology/de", "/city/berlin", "/city/berlin/time",
        "/city/berlin/panel", "/data/series.json", "/maps/x.png", "/tiles/a", "/build.json",
        "/de/", "/de/cities", "/de/city/berlin/panel", "/de/data/search.json", "/plans/berlin",
    ]  # fmt: skip
    assert crawl.indexable(urls) == [
        "/", "/cities", "/city/berlin", "/city/berlin/time", "/methodology", "/plans/berlin",
    ]  # fmt: skip


def test_robots_rules(public_out):
    text = (public_out / "robots.txt").read_text()
    lines = text.splitlines()
    assert lines.count("User-agent: *") == 1
    assert sum(ln.lower().startswith("user-agent:") for ln in lines) == 1  # no per-bot group
    assert "Allow: /" in lines
    disallow = [ln.removeprefix("Disallow: ") for ln in lines if ln.startswith("Disallow:")]
    assert disallow == crawl.DISALLOW
    for path in ("/data/", "/maps/", "/tiles/", "/build.json", "/city/*/panel"):
        assert path in disallow
        assert "/de" + path in disallow
    assert lines[-1] == f"Sitemap: {ORIGIN}sitemap.xml"


def test_robots_text_is_exactly_the_rules():
    text = crawl.robots_txt(ORIGIN, ["/a/", "/b"])
    assert text.endswith("Disallow: /a/\nDisallow: /b\n\nSitemap: " + ORIGIN + "sitemap.xml\n")
    assert "Allow: /\n" in text


def test_sitemap_lists_every_indexable_page_once(public_out):
    locs = [e.text for e in _sitemap(public_out).findall("s:url/s:loc", NS)]
    want = {_abs(p) for p in _indexable(public_out)} | {
        _abs(with_lang(p, "de")) for p in _indexable(public_out)
    }
    assert len(locs) == len(set(locs))
    assert set(locs) == want
    assert len(locs) > 20
    for bad in ("/panel", "/data/", "/maps/", "/tiles/", "build.json", "/methodology/de"):
        assert not any(bad in loc for loc in locs), bad


def test_sitemap_alternates_reciprocal(public_out):
    alt = {}
    for url in _sitemap(public_out).findall("s:url", NS):
        loc = url.find("s:loc", NS).text
        links = {link.get("hreflang"): link.get("href") for link in url.findall("x:link", NS)}
        assert set(links) == {"en", "de", "x-default"}, loc
        assert links["x-default"] == links["en"]
        assert loc in (links["en"], links["de"])
        alt[loc] = links
    for loc, links in alt.items():
        for other in (links["en"], links["de"]):
            assert other in alt, f"{loc} names {other}, which is not listed"
            assert alt[other] == links, f"{loc} and {other} do not list each other alike"


def test_sitemap_lastmod_stable(rich, tmp_path, monkeypatch):  # noqa: F811
    first = _export(rich, tmp_path, monkeypatch, "one")
    second = _export(rich, tmp_path, monkeypatch, "two")
    assert (first / "sitemap.xml").read_bytes() == (second / "sitemap.xml").read_bytes()
    for lastmod in _sitemap(first).findall("s:url/s:lastmod", NS):
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", lastmod.text)


def test_lastmod_of_a_city_page_is_its_latest_osm_snapshot(tmp_path):
    build = {"osm_timestamps": {"x": ["2025-01-01T00:00:00Z", "2026-03-04T10:00:00Z"]}}
    assert crawl.lastmod_for("/city/x/time", build, tmp_path) == "2026-03-04"


def _git(repo: Path, *args: str, date: str | None = None) -> None:
    env = {
        **os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org",
    }  # fmt: skip
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00+00:00"
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def _commit(repo: Path, rel: str, text: str, date: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text)
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"change {rel}", date=date)


def _source_repo(tmp_path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo, crawl.SOURCES_FOR("/cities")[0]


def test_lastmod_follows_the_last_commit_of_the_pages_sources(tmp_path):
    repo, source = _source_repo(tmp_path)
    _commit(repo, source, "v1", "2026-01-10")
    assert crawl.lastmod_for("/cities", {}, repo) == "2026-01-10"
    _commit(repo, "unrelated.txt", "x", "2026-03-01")  # another file: the page did not change
    assert crawl.lastmod_for("/cities", {}, repo) == "2026-01-10"
    _commit(repo, source, "v2", "2026-02-05")
    assert crawl.lastmod_for("/cities", {}, repo) == "2026-02-05"


def test_lastmod_of_a_shallow_clone_is_an_error(tmp_path):
    repo, source = _source_repo(tmp_path)
    _commit(repo, source, "v1", "2026-01-10")
    _commit(repo, source, "v2", "2026-02-05")
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow))
    with pytest.raises(ConfigError, match="shallow"):
        crawl.lastmod_for("/cities", {}, shallow)


def test_lastmod_without_history_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="git"):  # no repository at all
        crawl.lastmod_for("/cities", {}, tmp_path)
    repo, _ = _source_repo(tmp_path)
    _commit(repo, "unrelated.txt", "x", "2026-03-01")  # a repository, no commit on the sources
    with pytest.raises(ConfigError, match="no commit"):
        crawl.lastmod_for("/cities", {}, repo)


def test_lastmod_of_a_city_without_a_snapshot_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="snapshot"):
        crawl.lastmod_for("/city/x", {"osm_timestamps": {}}, tmp_path)


def test_every_source_of_a_page_exists():
    """SOURCES_FOR names files of this checkout (a renamed template would silently lose its
    date otherwise)."""
    for route in ("/", "/cities", "/compare", "/stories", "/differences", "/organisations",
                  "/sources", "/plans", "/plans/berlin", "/methodology"):  # fmt: skip
        sources = crawl.SOURCES_FOR(route)
        assert sources, route
        for source in sources:
            assert (REPO / source).exists(), (route, source)


def test_sitemap_city_without_subareas(rich, public_out):  # noqa: F811
    cfg_cities = [p.name for p in (public_out / "city").iterdir()]
    assert cfg_cities
    locs = [e.text for e in _sitemap(public_out).findall("s:url/s:loc", NS)]
    assert not any("_subareas" in loc for loc in locs)
    # the fixture has cities with and without subareas; each gets its page either way
    for city in cfg_cities:
        assert _abs(f"/city/{city}") in locs
    without = [c for c in cfg_cities if not (public_out / "data" / f"{c}_subareas.csv").exists()]
    assert without, "the fixture should have a city without _subareas.csv"


def test_preview_export_has_no_crawl_files(rich, tmp_path, monkeypatch):  # noqa: F811
    out = _export(rich, tmp_path, monkeypatch, "preview", public=False)
    assert (out / "robots.txt").read_text() == "User-agent: *\nDisallow: /\n"
    assert not (out / "sitemap.xml").exists()
    assert not (out / "llms.txt").exists()


def test_deploy_check_flags_stale_sitemap(public_out):
    assert [p for p in deploy_problems(public_out, None, public=True) if "sitemap" in p] == []
    gone = _indexable(public_out)[-1]
    page = public_out / gone.lstrip("/") / "index.html"
    page.unlink()
    problems = deploy_problems(public_out, None, public=True)
    assert any("sitemap.xml" in p and _abs(gone) in p for p in problems), problems


def test_deploy_check_flags_page_missing_from_sitemap(public_out):
    extra = public_out / "extra-page"
    extra.mkdir()
    (extra / "index.html").write_text("<html></html>")
    problems = deploy_problems(public_out, None, public=True)
    assert any("sitemap.xml" in p and _abs("/extra-page") in p for p in problems), problems


def test_deploy_check_flags_missing_crawl_files(public_out):
    (public_out / "sitemap.xml").unlink()
    (public_out / "robots.txt").unlink()
    problems = deploy_problems(public_out, None, public=True)
    assert any("sitemap.xml is missing" in p for p in problems)
    assert any("robots.txt is missing" in p for p in problems)


def test_deploy_check_flags_robots_without_sitemap_line(public_out):
    (public_out / "robots.txt").write_text("User-agent: *\nAllow: /\n")
    problems = deploy_problems(public_out, None, public=True)
    assert any("robots.txt" in p and "Sitemap" in p for p in problems), problems


def test_llms_txt_shape(public_out):
    text = (public_out / "llms.txt").read_text()
    lines = text.splitlines()
    assert lines[0].startswith("# ") and not lines[0].startswith("## ")
    first_block = next(i for i, ln in enumerate(lines) if ln.strip())
    assert first_block == 0
    quote = next(i for i, ln in enumerate(lines) if ln.startswith(">"))
    assert quote < next(i for i, ln in enumerate(lines) if ln.startswith("## "))
    assert sum(ln.startswith("# ") for ln in lines) == 1
    sitemap = {e.text for e in _sitemap(public_out).findall("s:url/s:loc", NS)}
    site = {
        "https://forge.example.org/o/velometer", "https://datalab.example.org/",
        crawl.ODBL_URL,
    }  # fmt: skip
    links = re.findall(r"\]\(([^)]+)\)", text)
    assert len(links) > 5
    for link in links:
        assert link.startswith("https://"), link
        if link in sitemap or link in site:
            continue
        # a downloadable file of the export (not a page)
        assert link.startswith(ORIGIN), link
        assert (public_out / link.removeprefix(ORIGIN)).is_file(), link
    assert f"]({ORIGIN}de/)" in text


def test_llms_txt_omits_doi_lines_without_dois_and_lists_them_with():
    cities = [("Berlin", "/city/berlin")]
    without = crawl.llms_txt(ORIGIN, cities, {})
    assert "doi.org" not in without
    with_doi = crawl.llms_txt(ORIGIN, cities, {"data": "10.5281/zenodo.1"})
    assert "https://doi.org/10.5281/zenodo.1" in with_doi


def test_llms_txt_without_cities_has_no_empty_cities_section():
    """A heading whose section is left empty is dropped; the other sections stay."""
    empty = crawl.llms_txt(ORIGIN, [], {})
    assert "## Cities" not in empty
    assert "## Method and data" in empty and "## Citation" in empty  # "Cite the page…" stays
    filled = [line for line in empty.splitlines() if line.strip()]
    for line, following in zip(filled, [*filled[1:], None], strict=True):
        if line.startswith("## "):  # every heading left has a line before the next one
            assert following is not None and not following.startswith("## "), line
    assert "## Cities" in crawl.llms_txt(ORIGIN, [("Berlin", "/city/berlin")], {})


def test_sitemap_prefixes_hold_without_a_fresh_registration():
    """The namespaces are registered once at import: a sitemap built later still writes the
    default namespace and the `xhtml` prefix."""
    xml = crawl.sitemap_xml(ORIGIN, ["/"], {})
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<urlset ')
    assert f'xmlns="{crawl.SITEMAP_NS}"' in xml and f'xmlns:xhtml="{crawl.XHTML_NS}"' in xml
    assert "<xhtml:link " in xml and xml.endswith("</urlset>\n")


def test_llms_txt_years_are_the_history_years():
    """llms.txt says the CSV holds one snapshot per year since the history's first year, plus
    the current state: every "since <year>" in it is the first year of `config/history.yaml`,
    the yearly series every city's history runs cover."""
    first = int(yaml.safe_load((REPO / "config" / "history.yaml").read_text())["years"][:4])
    text = (REPO / "content" / "llms.md").read_text(encoding="utf-8")
    assert "(one per year since" in text and "plus the current state)" in text
    years = [int(y) for y in re.findall(r"\bsince (\d{4})\b", text)]
    assert len(years) >= 1 and set(years) == {first}, years
