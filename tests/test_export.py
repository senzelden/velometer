"""`velometer app export` (M9 spec decisions 1, 2, 4, 8, 9): the static edition is the app's own
responses written to files, for the URLs the data has; a build stamp; read-only on the DB; a
guarded `--clean`."""

import hashlib
import json
import re
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
                assert (url in found) == (c.get(url).status_code == 200), url
            for url in (f"/plans/{city}", f"/data/{city}.csv", f"/data/{city}_subareas.csv"):
                assert (url in found) == (c.get(url).status_code == 200), url
    # the fixture has a city without a tab (paris: no Bezirke), so absence is exercised
    assert any(f"/city/{c}/bezirke" not in found for c in cities)
    for url in ["/", "/compare", "/methodology/de", "/data/series.json", "/data/all.csv"]:
        assert url in found
    # every map an exported page references is exported
    maps = set()
    for r in responses.values():
        if r.headers["content-type"].startswith("text/html"):
            maps |= set(re.findall(r"(?<=[\"'(=\s])/maps/[A-Za-z0-9_.-]+", r.text))
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
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".dist")]  # no staging left


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
