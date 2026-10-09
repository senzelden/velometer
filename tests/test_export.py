"""`velometer app export` (M9 spec decisions 1, 2, 4, 8, 9): the static edition is the app's own
responses written to files, for the URLs the data has; a build stamp; read-only on the DB; a
guarded `--clean`."""

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.test_app import CONTENT
from tests.test_app_base import BASE, rich  # noqa: F401  (`rich` is a fixture)
from velometer.app import export
from velometer.app.main import HERE, TABS, create_app
from velometer.cli import app as cli_app
from velometer.report.data import ReportData, open_readonly

BASE_URL = "http://127.0.0.1:8000"
FOOTER = "Static edition · build "
BUILD_KEYS = {
    "commit", "commit_full", "dirty", "classifier_versions", "osm_timestamps", "base", "built_at"
}  # fmt: skip


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _app(rich, base="/"):  # noqa: F811
    db_path, cfg, maps, docs, plans = rich
    return create_app(
        db_path, cfg, maps, docs, content_dir=CONTENT, plans_data_dir=plans, base_path=base
    )


def _data(rich):  # noqa: F811
    db_path, cfg, *_ = rich
    return ReportData(open_readonly(db_path), cfg)


def _export(rich, out: Path, base="/", clean=False):  # noqa: F811
    db_path, cfg, maps, docs, plans = rich
    return export.run_export(out, base, db_path, cfg, maps, docs, CONTENT, plans, clean)


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
        assert (out / "404.html").read_bytes() == missing.content

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
    args += ["--content", str(CONTENT)]
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
