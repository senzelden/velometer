"""M17 Task 7: `velometer dataset bundle`, the zip and the Zenodo sheet."""

import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.test_app_base import build_rich
from tests.test_m17_crawl import _export
from velometer import dataset_bundle as db
from velometer.cli import app
from velometer.report import csvexport


@pytest.fixture(scope="module")
def public(tmp_path_factory):
    rich = build_rich(tmp_path_factory.mktemp("bundle-db"))
    with pytest.MonkeyPatch.context() as mp:
        return _export(rich, tmp_path_factory.mktemp("bundle-out"), mp)


@pytest.fixture
def made(public, tmp_path):
    zpath, mpath = db.bundle(public, tmp_path / "o")
    return zpath, mpath


def test_bundle_contains_all_csvs(public, made):
    names = {p.name for p in (public / "data").glob("*.csv")}
    assert names
    with zipfile.ZipFile(made[0]) as z:
        members = z.namelist()
    assert {Path(m).name for m in members if m.endswith(".csv")} == names
    assert not [m for m in members if m.endswith(".gz")]
    assert "README.md" in members
    assert made[0].name == "velometer-data-0123456.zip"


def _readme(zpath):
    with zipfile.ZipFile(zpath) as z:
        return z.read("README.md").decode("utf-8")


def test_bundle_readme_has_notices(public, tmp_path):
    """Every notice line the CSV preamble writer produces, population credits and the
    per-capita disclaimer included, is in the README verbatim; the writer is the source."""
    site = tmp_path / "s"
    (site / "data").mkdir(parents=True)
    sources = ["Eurostat GISCO (x)", "INSEE y (z)", "INE 2024 (w)"]
    pre = csvexport.csv_preamble("c", "t", sources)
    (site / "data" / "all.csv").write_text(pre + "a\n1\n", encoding="utf-8")
    (site / "build.json").write_bytes((public / "build.json").read_bytes())
    readme = _readme(db.bundle(site, tmp_path / "o")[0])
    lines = [x[2:] for x in pre.splitlines() if not x.startswith("# velometer ")]
    assert len(lines) >= 4
    for line in lines:
        assert line in readme, line
    assert csvexport.ATTRIBUTION[2:] in readme and csvexport.BOUNDARIES[2:] in readme
    # and every notice of the real fixture's files
    real = _readme(db.bundle(public, tmp_path / "o2")[0])
    for csv in (public / "data").glob("*.csv"):
        for line in csv.read_text(encoding="utf-8").splitlines():
            if line.startswith("# ") and not line.startswith("# velometer "):
                assert line[2:] in real, (csv.name, line)


def test_bundle_readme_names_provenance(public, made):
    readme = _readme(made[0])
    build = json.loads((public / "build.json").read_text())
    assert build["commit"] in readme
    for v in build["classifier_versions"]:
        assert v in readme
    for stamps in build["osm_timestamps"].values():
        for s in stamps:
            assert s in readme
    assert build["site"]["repo_url"] in readme


def test_bundle_has_no_geometry(made):
    with zipfile.ZipFile(made[0]) as z:
        for name in z.namelist():
            assert not name.endswith((".geojson", ".json", ".gz"))
            assert "boundary" not in name
        assert b'"boundary"' not in b"".join(z.read(n) for n in z.namelist())


def test_bundle_reproducible(public, tmp_path):
    a = db.bundle(public, tmp_path / "a")[0].read_bytes()
    b = db.bundle(public, tmp_path / "b")[0].read_bytes()
    assert a == b
    with zipfile.ZipFile(tmp_path / "a" / "velometer-data-0123456.zip") as z:
        assert z.namelist() == sorted(z.namelist())
        assert {i.date_time for i in z.infolist()} == {db.FIXED_TIME}


def test_zenodo_sheet(public, made):
    text = made[1].read_text(encoding="utf-8")
    build = json.loads((public / "build.json").read_text())
    assert "License: odbl-1.0" in text
    assert "Creators: Dennis Senzel" in text
    assert f"Version: {build['commit']}" in text
    assert f"isSupplementTo {build['site']['repo_url']}" in text
    assert "Keywords:" in text and "Title:" in text and "Description:" in text
    assert "gmail" not in text.lower() and "@" not in text


@pytest.mark.parametrize(
    "patch", [{"commit": None}, {"commit": "unknown"}, {"dirty": True}, {"public": False}]
)
def test_bundle_refuses_an_unfit_export(public, tmp_path, patch):
    site = tmp_path / "s"
    (site / "data").mkdir(parents=True)
    (site / "data" / "all.csv").write_text("# x\na\n")
    build = json.loads((public / "build.json").read_text()) | patch
    if build["commit"] is None:
        del build["commit"]
    (site / "build.json").write_text(json.dumps(build))
    with pytest.raises(db.BundleError):
        db.bundle(site, tmp_path / "o")


def test_cli(public, tmp_path):
    res = CliRunner().invoke(
        app, ["dataset", "bundle", "--site", str(public), "--out", str(tmp_path)]
    )
    assert res.exit_code == 0, res.output
    assert (tmp_path / "zenodo-metadata.txt").is_file()


def test_bundle_refuses_csvs_without_the_osm_notice(public, tmp_path):
    site = tmp_path / "s"
    (site / "data").mkdir(parents=True)
    (site / "data" / "all.csv").write_text("a,b\n1,2\n")
    (site / "build.json").write_bytes((public / "build.json").read_bytes())
    with pytest.raises(db.BundleError, match="OSM notice"):
        db.bundle(site, tmp_path / "o")
