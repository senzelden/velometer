"""`velometer app export` (M9 spec decisions 1, 2, 4, 8, 9): the static edition is the app's own
responses written to files, for the URLs the data has; a build stamp; read-only on the DB; a
guarded `--clean`."""

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.test_app import CONTENT
from tests.test_app_base import BASE, rich  # noqa: F401  (`rich` is a fixture)
from velometer.app import export
from velometer.app.main import CSP, HERE, TABS, create_app, csp_meta
from velometer.cli import app as cli_app
from velometer.report.data import ReportData, open_readonly

BASE_URL = "http://127.0.0.1:8000"
FOOTER = "Static edition · build "
BUILD_KEYS = {
    "commit", "commit_full", "dirty", "classifier_versions", "osm_timestamps", "base", "built_at"
}  # fmt: skip

MAIN_OPEN = '<main id="main" tabindex="-1">'


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _content(rich) -> Path:  # noqa: F811
    """The shipped content with each link to a city the fixture DB lacks pointed at a fixture
    city: the reference scan fails an export that links to a page it does not have, and the
    shipped narratives link to all the real cities."""
    db_path, cfg, *_ = rich
    content = db_path.parent / "content-for-fixture"
    if not content.exists():
        cities = {c.id for c in _data(rich).cities()}
        assert "berlin" in cities
        city_link = re.compile(r"/city/([a-z_-]+)")

        def keep(m):
            return m.group(0) if m.group(1) in cities else "/city/berlin"

        for src in _files(CONTENT):
            dst = content / src.relative_to(CONTENT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(city_link.sub(keep, src.read_text()))
    return content


def _app(rich, base="/"):  # noqa: F811
    db_path, cfg, maps, docs, plans = rich
    content = _content(rich)
    return create_app(
        db_path, cfg, maps, docs, content_dir=content, plans_data_dir=plans, base_path=base
    )


def _data(rich):  # noqa: F811
    db_path, cfg, *_ = rich
    return ReportData(open_readonly(db_path), cfg)


def _export(rich, out: Path, base="/", clean=False):  # noqa: F811
    db_path, cfg, maps, docs, plans = rich
    content = _content(rich)
    return export.run_export(out, base, db_path, cfg, maps, docs, content, plans, clean)


def _files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in _files(root)}


def _staging(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.name.startswith(export.STAGING_PREFIX)]


# --- url_to_path (decision 2) ---


@pytest.mark.parametrize(
    ("url", "ctype", "path"),
    [
        ("/", "text/html; charset=utf-8", "index.html"),
        ("/city/berlin", "text/html; charset=utf-8", "city/berlin/index.html"),
        ("/city/berlin/panel", "text/html", "city/berlin/panel/index.html"),
        ("/data/series.json", "application/json", "data/series.json"),
        ("/data/berlin.csv", "text/csv; charset=utf-8", "data/berlin.csv"),
        ("/maps/x.png", "image/png", "maps/x.png"),
        ("/maps/x.geojson", "application/geo+json", "maps/x.geojson"),
    ],
)
def test_url_to_path(url, ctype, path):
    assert export.url_to_path(url, ctype) == PurePosixPath(path)


@pytest.mark.parametrize(
    "url", ["/compare?c=berlin", "/city/berlin#map", "city/berlin", "/city/../x", "/"]
)
def test_url_to_path_refuses_what_has_no_file(url):
    ctype = "image/png" if url == "/" else "text/html"  # a non-HTML `/` names no file
    with pytest.raises(ValueError):
        export.url_to_path(url, ctype)


# --- export_urls (decision 4) ---


def test_export_urls_are_what_the_app_serves(rich):  # noqa: F811
    app, data = _app(rich), _data(rich)
    found = export.export_urls(data, app)
    assert len(found) == len(set(found))
    with TestClient(app, base_url=BASE_URL) as c:
        responses = {url: c.get(url, follow_redirects=False) for url in found}
        for url, r in responses.items():
            assert r.status_code == 200, url
        cities = [city.id for city in data.cities()]
        assert cities
        for city in cities:
            assert f"/city/{city}" in found
            assert f"/city/{city}/panel" in found
            for _k, _l, suffix in TABS:
                url = f"/city/{city}{suffix}"
                # a tab is exported exactly when the app serves it for that city
                assert (url in found) == (c.get(url, follow_redirects=False).status_code == 200), (
                    url
                )
            for url in (f"/plans/{city}", f"/data/{city}.csv", f"/data/{city}_subareas.csv"):
                assert (url in found) == (c.get(url, follow_redirects=False).status_code == 200), (
                    url
                )
    # the fixture has a city without a tab (paris: no Bezirke), so absence is exercised
    assert any(f"/city/{c}/bezirke" not in found for c in cities)
    for url in ["/", "/compare", "/methodology/de", "/data/series.json", "/data/all.csv"]:
        assert url in found
    # every map an exported page references is exported
    maps = set()
    for r in responses.values():
        if r.headers["content-type"].startswith("text/html"):
            maps |= set(re.findall(r"/maps/[^\"'\s)<>]+", r.text))
    assert maps, "the fixture's pages reference maps"
    assert maps <= set(found)


def test_export_urls_find_maps_under_a_base(rich):  # noqa: F811
    found = export.export_urls(_data(rich), _app(rich, BASE))
    assert "/maps/berlin_lau.geojson" in found  # referenced as /velometer/maps/…, kept as /maps/…


# --- run_export ---


def test_run_export_writes_the_static_edition(rich, tmp_path):  # noqa: F811
    db_path = rich[0]
    before = _md5(db_path)
    out = tmp_path / "dist"
    result = _export(rich, out, BASE)
    assert _md5(db_path) == before  # read-only

    app = _app(rich, BASE)
    data = _data(rich)
    found = export.export_urls(data, app)
    with TestClient(app, base_url=BASE_URL) as c:
        for url in found:
            r = c.get(url)
            path = out / export.url_to_path(url, r.headers["content-type"])
            assert path.is_file(), url
            if not r.headers["content-type"].startswith(("text/html", "text/csv")):
                assert path.read_bytes() == r.content, url  # a CSV's preamble has a timestamp
        missing = c.get("/no-such-page")
        assert missing.status_code == 404
        assert _without_footer((out / "404.html").read_text()) == missing.text

    static = HERE / "static"
    for src in _files(static):
        rel = src.relative_to(static)
        if rel.parts[:2] == ("js", "tests"):
            assert not (out / "static" / rel).exists(), rel
        else:
            assert (out / "static" / rel).read_bytes() == src.read_bytes(), rel
    assert not (out / "static" / "js" / "tests").exists()

    build = json.loads((out / "build.json").read_text())
    assert set(build) == BUILD_KEYS
    assert build["base"] == BASE
    assert isinstance(build["dirty"], bool)
    assert build["commit_full"].startswith(build["commit"].removesuffix("-dirty"))
    built = datetime.fromisoformat(build["built_at"])
    assert built.utcoffset().total_seconds() == 0
    assert abs((datetime.now(UTC) - built).total_seconds()) < 600
    rows = data.csv_rows()
    assert build["classifier_versions"] == sorted({r["classifier_version"] for r in rows})
    stamps: dict[str, set] = {}
    for r in rows:
        stamps.setdefault(r["city_id"], set()).add(r["osm_timestamp"])
    assert build["osm_timestamps"] == {k: sorted(v) for k, v in stamps.items()}
    assert result.build == build

    pages = [p for p in out.rglob("index.html") if p.parent.name != "panel"]
    assert len(pages) > 10
    for page in pages:
        assert page.read_text().count(FOOTER + build["commit"]) == 1, page
    files = _files(out)
    assert result.files == len(files)
    assert result.bytes == sum(p.stat().st_size for p in files)


def test_a_non_200_fails_the_export_naming_url_and_status(rich, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(export, "export_urls", lambda data, app: ["/", "/city/nowhere"])
    out = tmp_path / "dist"
    with pytest.raises(export.ExportError, match=r"/city/nowhere.*404"):
        _export(rich, out)
    assert not out.exists()
    assert not _staging(tmp_path)


# --- the guard (decision 9) ---


def test_a_non_empty_out_needs_clean(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    with pytest.raises(export.ExportError, match="--clean"):
        _export(rich, out)
    assert _files(out) == [out / "keep.txt"]


@pytest.mark.parametrize("build_json", [None, "not ours", "{}", '["commit"]'])
def test_clean_refuses_a_directory_no_export_wrote(rich, tmp_path, build_json):  # noqa: F811
    out = tmp_path / "dist"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    if build_json is not None:
        (out / "build.json").write_text(build_json)
    with pytest.raises(export.ExportError, match="build.json"):
        _export(rich, out, clean=True)
    names = ["keep.txt"] + ([] if build_json is None else ["build.json"])
    assert sorted(p.name for p in out.iterdir()) == sorted(names)


def test_clean_replaces_a_previous_export(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    _export(rich, out)
    (out / "stale.txt").write_text("from before")
    _export(rich, out, clean=True)
    assert not (out / "stale.txt").exists()
    assert (out / "index.html").is_file()
    assert set(json.loads((out / "build.json").read_text())) == BUILD_KEYS


def test_an_empty_out_needs_no_clean(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    out.mkdir()
    _export(rich, out)
    assert (out / "build.json").is_file()


# --- the CLI ---


def test_cli_app_export(rich, tmp_path, monkeypatch):  # noqa: F811
    db_path, cfg, maps, docs, _plans = rich
    monkeypatch.chdir(tmp_path)  # the default data/plans is absent: the plan page notes it
    out = tmp_path / "site"
    args = ["app", "export", "--out", str(out), "--base", "/velometer", "--db", str(db_path)]
    args += ["--config", str(cfg), "--maps", str(maps), "--docs", str(docs)]
    args += ["--content", str(_content(rich))]
    r = CliRunner().invoke(cli_app, args)
    assert r.exit_code == 0, r.output
    assert json.loads((out / "build.json").read_text())["base"] == BASE
    assert str(out) in r.output
    again = CliRunner().invoke(cli_app, args)  # non-empty, no --clean
    assert again.exit_code == 1
    assert "--clean" in again.output
    assert CliRunner().invoke(cli_app, [*args, "--clean"]).exit_code == 0


# --- deletion safety (review fix round 1) ---


def test_out_dot_exports_into_the_cwd(rich, tmp_path, monkeypatch):  # noqa: F811
    """`--out .`: staging is a sibling of the cwd, never inside it (I-1)."""
    site = tmp_path / "site"
    site.mkdir()
    monkeypatch.chdir(site)
    _export(rich, Path("."))
    assert (site / "index.html").is_file()
    assert Path.cwd() == site and site.is_dir()
    (site / "stale.txt").write_text("from before")
    _export(rich, Path("."), clean=True)
    assert not (site / "stale.txt").exists()
    assert (site / "build.json").is_file()
    assert not _staging(site) and not _staging(tmp_path)


def test_a_failed_export_leaves_out_dot_as_it_was(rich, tmp_path, monkeypatch):  # noqa: F811
    site = tmp_path / "site"
    site.mkdir()
    monkeypatch.chdir(site)
    _export(rich, Path("."))
    before = _snapshot(site)
    monkeypatch.setattr(export, "export_urls", lambda data, app: ["/", "/city/nowhere"])
    with pytest.raises(export.ExportError, match="/city/nowhere"):
        _export(rich, Path("."), clean=True)
    assert _snapshot(site) == before
    assert not _staging(tmp_path)


def test_a_symlinked_out_is_refused(rich, tmp_path):  # noqa: F811
    target = tmp_path / "real"
    _export(rich, target)
    before = _snapshot(target)
    link = tmp_path / "dist"
    link.symlink_to(target)
    with pytest.raises(export.ExportError, match="symlink"):
        _export(rich, link, clean=True)
    assert _snapshot(target) == before
    dangling = tmp_path / "gone"
    dangling.symlink_to(tmp_path / "nowhere")
    with pytest.raises(export.ExportError, match="symlink"):
        _export(rich, dangling)


def test_a_route_exception_names_its_url(rich, tmp_path, monkeypatch):  # noqa: F811
    real = export.create_app

    def with_boom(*args, **kw):
        app = real(*args, **kw)

        @app.get("/boom")
        def boom():
            raise RuntimeError("route failed")

        return app

    monkeypatch.setattr(export, "create_app", with_boom)
    monkeypatch.setattr(export, "export_urls", lambda data, app: ["/", "/boom"])
    out = tmp_path / "dist"
    with pytest.raises(export.ExportError, match="/boom: HTTP 500"):
        _export(rich, out)
    assert not out.exists() and not _staging(tmp_path)


def test_a_missing_database_is_an_export_error(rich, tmp_path):  # noqa: F811
    """Spec §5: a missing DB fails with the app's message, not a traceback, and writes nothing."""
    db_path, cfg, maps, docs, plans = rich
    out = tmp_path / "dist"
    with pytest.raises(export.ExportError, match="database not found"):
        export.run_export(
            out, "/", db_path.with_name("nope.sqlite"), cfg, maps, docs, _content(rich), plans,
            False,
        )  # fmt: skip
    assert not out.exists() and not _staging(tmp_path)


def test_an_os_error_is_an_export_error(rich, tmp_path):  # noqa: F811
    parent = tmp_path / "locked"
    parent.mkdir()
    parent.chmod(0o555)
    try:
        with pytest.raises(export.ExportError, match="locked"):
            _export(rich, parent / "dist")
    finally:
        parent.chmod(0o755)


def _git_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


@pytest.mark.parametrize("clean", [False, True])
@pytest.mark.parametrize("which", ["root", "home", "cwd-git-toplevel", "velometer-repo", *range(5)])
def test_a_dangerous_out_is_refused(rich, tmp_path, monkeypatch, which, clean):  # noqa: F811
    """`/`, $HOME, a git toplevel and any directory holding an input (db, config, maps, docs,
    plans data) are refused before anything happens, with or without --clean (M-2)."""
    if which == "root":
        out = Path("/")
    elif which == "home":
        out = tmp_path / "home"
        out.mkdir()
        monkeypatch.setenv("HOME", str(out))
    elif which == "cwd-git-toplevel":
        out = _git_repo(tmp_path / "repo")
        monkeypatch.chdir(out / ".")
        out = Path(".")
    elif which == "velometer-repo":
        out = Path(__file__).resolve().parents[1]
    else:
        given = Path(rich[which])
        out = given.parent if given.is_file() else given
    # each would pass the build.json guard, so only the path rule refuses it
    if out != Path("/") and which != "velometer-repo":
        (out / "build.json").write_text(json.dumps(dict.fromkeys(BUILD_KEYS, "x")))
    _content(rich)  # made before the snapshot (it lives beside the fixture's inputs)
    before = _snapshot(out) if which not in ("root", "velometer-repo") else None
    calls = []
    monkeypatch.setattr(export, "open_readonly", lambda *a: calls.append(a))
    with pytest.raises(export.ExportError, match="refus"):
        _export(rich, out, clean=clean)
    assert calls == []  # refused before the database is opened
    if before is not None:
        assert _snapshot(out) == before


def test_clean_rechecks_the_guard_before_deleting(rich, tmp_path, monkeypatch):  # noqa: F811
    """Between the first check and the swap `out` stops being an export: nothing is deleted
    (M-3)."""
    out = tmp_path / "dist"
    _export(rich, out)
    real = export._write_site

    def write_then_tamper(site, *args):
        real(site, *args)
        (out / "build.json").unlink()

    monkeypatch.setattr(export, "_write_site", write_then_tamper)
    before = _snapshot(out)
    with pytest.raises(export.ExportError, match="build.json"):
        _export(rich, out, clean=True)
    del before["build.json"]  # the tampering, and nothing else
    assert _snapshot(out) == before
    assert not _staging(tmp_path)


def test_the_staging_directory_is_git_ignored(rich, tmp_path, monkeypatch):  # noqa: F811
    """`--out dist` in the repo puts staging next to it: the repo ignores that name (M-4)."""
    seen = []
    real = export._write_site
    monkeypatch.setattr(export, "_write_site", lambda site, *a: (seen.append(site), real(site, *a)))
    _export(rich, tmp_path / "dist")
    repo = Path(__file__).resolve().parents[1]
    probe = repo / seen[0].name / "index.html"
    r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", str(probe)])
    assert r.returncode == 0, probe


@pytest.mark.parametrize(
    "base", ["/a/../b", "..", "//cdn.example", "/a//b", "https://x.org/", "/a?b=1", "/a#top",
             "/a b/", '/a"b/']
)  # fmt: skip
def test_a_bad_base_is_refused(rich, tmp_path, base):  # noqa: F811
    with pytest.raises(export.ExportError, match="--base"):
        _export(rich, tmp_path / "dist", base)
    assert not (tmp_path / "dist").exists()


@pytest.mark.parametrize("base", ["/", "", "/velometer", "velometer/", "/a/b-c_d.e~/"])
def test_a_good_base_is_accepted(base):
    export.validate_base(base)


def test_cli_reports_a_bad_base(rich, tmp_path):  # noqa: F811
    args = ["app", "export", "--out", str(tmp_path / "x"), "--base", "/a/../b"]
    r = CliRunner().invoke(cli_app, [*args, "--db", str(rich[0])])
    assert r.exit_code == 1
    assert "--base" in r.output


# --- the reference scan (decision 5) ---

# a tiny site, base /velometer/: every reference form points at its own file, so deleting a file
# leaves exactly the reference of that form unresolved
SCAN_SITE = {
    "index.html": (
        "<!doctype html><html><head>"
        '<link rel="stylesheet" href="/velometer/static/a.css">'
        '<script type="module" src="/velometer/static/m.js"></script></head><body>'
        '<a href="/velometer/page?x=1#top">page</a>'
        '<form action="/velometer/search" method="get"></form>'
        '<div data-src="/velometer/data/d.json"></div>'
        '<script type="application/json" id="cfg">{"k": [{"url": "/velometer/maps/m.geojson"}],'
        ' "links": {"copyright": "https://www.openstreetmap.org/copyright"},'
        ' "tiles": "https://tile.openstreetmap.org/{z}/{x}/{y}.png"}</script>'
        '<img src="data:image/png;base64,AAAA" alt="">'
        '<a href="https://www.openstreetmap.org/copyright">OSM</a> <a href="#x">here</a>'
        "</body></html>"
    ),
    "about/index.html": (
        '<!doctype html><html><head><meta name="velometer-base" content="/velometer/">'
        "</head><body></body></html>"
    ),
    "page/index.html": "<!doctype html><html><head></head><body></body></html>",
    "search/index.html": "<!doctype html><html><head></head><body></body></html>",
    "data/d.json": "{}",
    "maps/m.geojson": "{}",
    "static/a.css": "a { background: url(img/bg.png); } b { background: url('data:x'); }",
    "static/img/bg.png": "png",
    "static/m.js": (
        'import { x } from "./dep.js";\n'
        'const series = fetch(url("/data/series.json"));\n'
        'fetch("/velometer/data/raw.csv");\n'
        '// a comment naming url("/nowhere") is not a reference\n'
        "const dynamic = url(`/city/${id}`);\n"
    ),
    "static/dep.js": "export const x = 1;\n",
    "data/series.json": "{}",
    "data/raw.csv": "a\n",
}
# file deleted -> (file holding the reference, the reference as written resolved to a URL)
SCAN_FORMS = {
    "index.html": ("about/index.html", "/velometer/"),  # the velometer-base meta
    "static/a.css": ("index.html", "/velometer/static/a.css"),  # <link href>
    "static/m.js": ("index.html", "/velometer/static/m.js"),  # <script src>
    "page/index.html": ("index.html", "/velometer/page?x=1#top"),  # <a href>
    "search/index.html": ("index.html", "/velometer/search"),  # <form action>
    "data/d.json": ("index.html", "/velometer/data/d.json"),  # a data-* attribute
    "maps/m.geojson": ("index.html", "/velometer/maps/m.geojson"),  # a JSON config string
    "static/img/bg.png": ("static/a.css", "img/bg.png"),  # CSS url(), relative to the CSS
    "static/dep.js": ("static/m.js", "./dep.js"),  # a JS import
    "data/series.json": ("static/m.js", "/velometer/data/series.json"),  # url("/…")
    "data/raw.csv": ("static/m.js", "/velometer/data/raw.csv"),  # fetch("…")
}


def _scan_site(root: Path) -> Path:
    for rel, text in SCAN_SITE.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root


def test_the_scan_of_a_complete_site_finds_nothing(tmp_path):
    assert export.scan_references(_scan_site(tmp_path), BASE) == []


@pytest.mark.parametrize("deleted", sorted(SCAN_FORMS))
def test_the_scan_finds_each_reference_form(tmp_path, deleted):
    site = _scan_site(tmp_path)
    (site / deleted).unlink()
    file, ref = SCAN_FORMS[deleted]
    found = export.scan_references(site, BASE)
    assert found == [export.Unresolved(file, ref)]


@pytest.mark.parametrize(
    ("planted", "ref"),
    [
        ('<a href="/velometer/nowhere">x</a>', "/velometer/nowhere"),
        ('<a href="/nowhere">x</a>', "/nowhere"),  # internal without the base
        ('<a href="nowhere">x</a>', "nowhere"),  # relative in a page: no fixed file
        ('<script src="https://cdn.example/x.js"></script>', "https://cdn.example/x.js"),
        ('<img src="//cdn.example/x.png" alt="">', "//cdn.example/x.png"),
        ('<link rel="stylesheet" href="https://cdn.example/x.css">', "https://cdn.example/x.css"),
        ('<form action="https://forms.example/x"></form>', "https://forms.example/x"),
        ('<a href="javascript:alert(1)">x</a>', "javascript:alert(1)"),
        (
            '<script type="application/json">{"url": "https://cdn.example/t.json"}</script>',
            "https://cdn.example/t.json",
        ),
    ],
)
def test_the_scan_reports_dangling_and_foreign_references(tmp_path, planted, ref):
    site = _scan_site(tmp_path)
    page = site / "page" / "index.html"
    page.write_text(page.read_text().replace("<body>", "<body>" + planted))
    assert export.scan_references(site, BASE) == [export.Unresolved("page/index.html", ref)]


@pytest.mark.parametrize(
    "allowed",
    [
        '<a href="https://www.openstreetmap.org/copyright">OSM</a>',  # a link, not a load
        '<a href="mailto:x@example.org">mail</a>',
        '<img src="https://tile.openstreetmap.org/1/0/0.png" alt="">',  # the one loaded host
        '<script type="application/json">{"links": {"w": "https://example.org/w/"}}</script>',
    ],
)
def test_the_scan_allows_links_and_the_tile_host(tmp_path, allowed):
    site = _scan_site(tmp_path)
    page = site / "page" / "index.html"
    page.write_text(page.read_text().replace("<body>", "<body>" + allowed))
    assert export.scan_references(site, BASE) == []


def test_the_scan_of_a_real_export_finds_the_planted_breaks_only(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    _export(rich, out, BASE)
    assert export.scan_references(out, BASE) == []
    page = out / "cities" / "index.html"
    planted = (
        '<a href="/velometer/nowhere">x</a><script src="https://cdn.example/x.js"></script>'
        '<a href="https://www.openstreetmap.org/copyright">OSM</a>'
    )
    page.write_text(page.read_text().replace(MAIN_OPEN, MAIN_OPEN + planted, 1))
    assert export.scan_references(out, BASE) == [
        export.Unresolved("cities/index.html", "/velometer/nowhere"),
        export.Unresolved("cities/index.html", "https://cdn.example/x.js"),
    ]


# (file, text planted, the reference reported contains): each reference form the scan must not
# pass silently, with a dangling internal and a foreign target where the form takes both
PLANTS = [
    (
        "cities/index.html",
        '<img srcset="https://cdn.example/a.png 1x" alt="">',
        "cdn.example/a.png",
    ),
    (
        "cities/index.html",
        '<img srcset="/velometer/static/favicon.svg 1x, /velometer/nowhere-2x.png 2x" alt="">',
        "/velometer/nowhere-2x.png",
    ),
    (
        "cities/index.html",
        '<div style="background:url(https://cdn.example/b.png)"></div>',
        "cdn.example/b.png",
    ),
    (
        "cities/index.html",
        '<div style="background:url(/velometer/nowhere-b.png)"></div>',
        "/velometer/nowhere-b.png",
    ),
    (
        "cities/index.html",
        "<style>body{background:url(https://cdn.example/s.png)}</style>",
        "cdn.example/s.png",
    ),
    (
        "cities/index.html",
        "<style>body{background:url(/velometer/nowhere.png)}</style>",
        "/velometer/nowhere.png",
    ),
    (
        "cities/index.html",
        "<style>@import 'https://cdn.example/i.css';</style>",
        "cdn.example/i.css",
    ),
    ("cities/index.html", '<script>fetch("https://cdn.example/h")</script>', "inline <script>"),
    ("cities/index.html", '<script>fetch("/velometer/nowhere-h")</script>', "inline <script>"),
    (
        "cities/index.html",
        '<object data="https://cdn.example/o.svg"></object>',
        "cdn.example/o.svg",
    ),
    (
        "cities/index.html",
        '<object data="/velometer/nowhere-o.svg"></object>',
        "/velometer/nowhere-o.svg",
    ),
    (
        "cities/index.html",
        '<video poster="https://cdn.example/p.png"></video>',
        "cdn.example/p.png",
    ),
    (
        "cities/index.html",
        '<video poster="/velometer/nowhere-p.png"></video>',
        "/velometer/nowhere-p.png",
    ),
    (
        "cities/index.html",
        '<div data-src="https://cdn.example/d.json"></div>',
        "cdn.example/d.json",
    ),
    (
        "cities/index.html",
        '<div data-src="/velometer/nowhere-d.json"></div>',
        "/velometer/nowhere-d.json",
    ),
    # the CSP allows the tile server over https only
    (
        "cities/index.html",
        '<img src="http://tile.openstreetmap.org/1/0/0.png" alt="">',
        "http://tile",
    ),
    ("cities/index.html", '<img src="//tile.openstreetmap.org/1/0/0.png" alt="">', "//tile"),
    ("static/app.css", '@import "https://cdn.example/j.css";', "cdn.example/j.css"),
    ("static/app.css", '@import "/velometer/nowhere-j.css";', "/velometer/nowhere-j.css"),
    ("static/app.css", '@import "nowhere-j2.css";', "nowhere-j2.css"),
    ("static/js/data.js", 's.src = "https://cdn.example/k.js";', "cdn.example/k.js"),
    ("static/js/data.js", 's.src = "/velometer/nowhere-k.js";', "/velometer/nowhere-k.js"),
    (
        "static/js/data.js",
        'new URL("/velometer/nowhere-u", location.href);',
        "/velometer/nowhere-u",
    ),
    ("static/js/data.js", 'new URL("https://cdn.example/u");', "cdn.example/u"),
    ("static/js/data.js", 'fetch ("https://cdn.example/f");', "cdn.example/f"),
    ("static/js/data.js", 'fetch ("/velometer/nowhere-f");', "/velometer/nowhere-f"),
    ("static/js/data.js", 'const z = 2\n  *fetch("/velometer/nowhere-z");', "/velometer/nowhere-z"),
]


def test_the_scan_fails_closed_on_every_reference_form(rich, tmp_path):  # noqa: F811
    """Each form planted into a copy of a fixture export is reported with its file; the export
    as made (its JSON configs' based URLs included) scans clean."""
    out = tmp_path / "dist"
    _export(rich, out, BASE)
    assert export.scan_references(out, BASE) == []
    missed = []
    for i, (rel, planted, expected) in enumerate(PLANTS):
        copy = tmp_path / f"plant-{i}"
        shutil.copytree(out, copy)
        target = copy / rel
        text = target.read_text()
        if rel.endswith(".html"):
            text = text.replace(MAIN_OPEN, MAIN_OPEN + planted, 1)
        else:
            text += "\n" + planted + "\n"
        target.write_text(text)
        found = export.scan_references(copy, BASE)
        if [u.file for u in found] != [rel] or expected not in found[0].ref:
            missed.append((planted, found))
        shutil.rmtree(copy)
    assert missed == []


def test_an_unresolved_reference_fails_the_export_listing_each(rich, tmp_path, monkeypatch):  # noqa: F811
    out = tmp_path / "dist"
    _export(rich, out, BASE)
    before = _snapshot(out)
    real = export._write_site

    def write_then_break(site, *args):
        real(site, *args)
        for rel in ("cities/index.html", "stories/index.html"):
            page = site / rel
            page.write_text(
                page.read_text().replace(MAIN_OPEN, MAIN_OPEN + '<a href="/velometer/x">', 1)
            )
        (site / "static" / "app.css").unlink()

    monkeypatch.setattr(export, "_write_site", write_then_break)
    with pytest.raises(export.ExportError) as e:
        _export(rich, out, BASE, clean=True)
    msg = str(e.value)
    assert "cities/index.html: /velometer/x" in msg
    assert "stories/index.html: /velometer/x" in msg
    assert "index.html: /velometer/static/app.css" in msg
    assert _snapshot(out) == before
    assert not _staging(tmp_path)


def test_the_unvendored_leaflet_images_are_unused():
    """The scan allows only the leaflet.css images VERSIONS records as not vendored, because the
    maps use neither the layers control nor the default marker icon; this keeps that true."""
    static = HERE / "static"
    assert "not vendored" in (static / "vendor" / "VERSIONS").read_text()
    for allowed_file, ref in export.UNVENDORED:
        assert allowed_file == "static/vendor/leaflet.css"
        assert ref in (static / "vendor" / "leaflet.css").read_text()
        assert not (static / "vendor" / ref).exists()
    uses = re.compile(r"\bL\.(marker|icon|Icon|control)\b")
    for js in [*static.glob("*.js"), *static.glob("js/*.js")]:
        assert not uses.search(js.read_text()), js


# --- the whole export: base rule, equality, CSP, the static compare note ---

ROOT_REF = {
    # an attribute value or a JSON config string that is a root-relative path
    ".html": re.compile(r'(?:=|": )"(/(?!/)[^"]*)"'),
    ".css": re.compile(r"url\(\s*['\"]?(/(?!/)[^'\")]*)"),
    # a root-relative string literal anywhere in a script (url() adds the base at run time)
    ".js": re.compile(r"""(\burl\(\s*)?(["'`])(/(?![/*])[A-Za-z][^"'`\s]*)\2"""),
}


def test_every_internal_reference_of_an_export_carries_the_base(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    _export(rich, out, BASE)
    seen = 0
    for path in _files(out):
        text = path.read_text(errors="replace")
        if path.suffix in (".html", ".css"):
            for ref in ROOT_REF[path.suffix].findall(text):
                seen += 1
                assert ref.startswith(BASE), f"{path.relative_to(out)}: {ref}"
        elif path.suffix == ".js":
            for via_url, _quote, ref in ROOT_REF[".js"].findall(text):
                seen += 1
                assert via_url, f"{path.relative_to(out)}: {ref} not through url()"
    assert seen > 100
    assert export.scan_references(out, BASE) == []


def _without_footer(html: str) -> str:
    lines = html.split("\n")
    stamps = [i for i, line in enumerate(lines) if FOOTER in line]
    assert len(stamps) == 1
    assert lines[stamps[0]].strip().startswith("<p>" + FOOTER)
    return "\n".join(lines[: stamps[0]] + lines[stamps[0] + 1 :])


STATIC_NOTE = "Without JavaScript this static edition shows the default selection"


def test_exported_pages_are_the_live_apps_pages(rich, tmp_path):  # noqa: F811
    """Equality: every exported HTML file is the live app's response for its URL (base `/`, no
    static edition) apart from the footer stamp, and on Compare the lede's static note."""
    out = tmp_path / "dist"
    _export(rich, out)
    pages = [p for p in _files(out) if p.suffix == ".html"]
    assert len(pages) > 10
    with TestClient(_app(rich), base_url=BASE_URL) as c:
        for page in pages:
            rel = page.relative_to(out).as_posix()
            url = "/404" if rel == "404.html" else "/" + rel.removesuffix("index.html").rstrip("/")
            r = c.get(url)
            assert r.status_code == (404 if rel == "404.html" else 200), rel
            text = page.read_text()
            if rel.endswith("panel/index.html"):
                assert text == r.text, rel  # a fragment: no footer
                continue
            text = _without_footer(text)
            if rel == "compare/index.html":
                static, live = text.split("\n"), r.text.split("\n")
                differ = [i for i, (a, b) in enumerate(zip(static, live, strict=True)) if a != b]
                assert len(differ) == 1, differ
                assert STATIC_NOTE in static[differ[0]]
                assert static[differ[0]].startswith('<p class="lede">')
                assert STATIC_NOTE not in r.text
            else:
                assert text == r.text, rel


def test_every_exported_page_carries_the_csp_meta_tag(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    _export(rich, out, BASE)
    tag = f'<meta http-equiv="Content-Security-Policy" content="{csp_meta(CSP)}">'
    documents = 0
    for page in (p for p in _files(out) if p.suffix == ".html"):
        text = page.read_text()
        if "<html" not in text:
            assert page.parent.name == "panel", page  # only the panels are fragments
            continue
        documents += 1
        assert text.split("</head>")[0].count(tag) == 1, page
    assert documents > 10


def test_the_static_compare_says_it_shows_the_default(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    _export(rich, out, BASE)
    lede = [
        line
        for line in (out / "compare" / "index.html").read_text().split("\n")
        if line.startswith('<p class="lede">')
    ]
    assert len(lede) == 1 and STATIC_NOTE in lede[0]
    with TestClient(_app(rich), base_url=BASE_URL) as c:
        assert STATIC_NOTE not in c.get("/compare").text


# --- the HTML 404 page (controller ruling) ---


@pytest.mark.parametrize("base", ["/", BASE])
def test_an_unknown_page_is_an_html_404_with_the_layout(rich, base):  # noqa: F811
    with TestClient(_app(rich, base), base_url=BASE_URL) as c:
        for url in ("/no-such-page", "/city/nowhere", "/city/berlin/nope"):
            r = c.get(url)
            assert r.status_code == 404, url
            assert r.headers["content-type"].startswith("text/html"), url
            assert r.headers["content-security-policy"] == CSP
            assert "Page not found" in r.text
            main = r.text.split(MAIN_OPEN, 1)[1].split("</main>", 1)[0]
            assert f'<a href="{base}">Go to the overview</a>' in main  # its own way home, u()
            assert 'id="site-nav"' in r.text  # the layout's navigation
            assert "openstreetmap.org/copyright" in r.text  # the footer and its attribution
        for url in ("/data/nope.csv", "/maps/nope.png", "/static/nope.js"):
            r = c.get(url)
            assert r.status_code == 404, url
            assert r.headers["content-type"].startswith("application/json"), url
            assert "detail" in r.json()


def test_the_exported_404_is_the_html_page_and_resolves(rich, tmp_path):  # noqa: F811
    out = tmp_path / "dist"
    _export(rich, out, BASE)
    text = (out / "404.html").read_text()
    assert text.startswith("<!doctype html>") and "Page not found" in text
    assert 'href="/velometer/"' in text
    assert [u for u in export.scan_references(out, BASE) if u.file == "404.html"] == []
