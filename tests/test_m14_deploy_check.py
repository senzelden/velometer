"""M14 task 3: `velometer app deploy-check`, the dry run on a finished export."""

import gzip
import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.test_app_base import rich  # noqa: F401  (`rich._get_wrapped_function`)
from tests.test_export import _content, _files
from velometer.app import deploy_check, export
from velometer.cli import app

COMPLETE = {
    "datalab": {"name": "Zählwerk Berlin Datalab", "url": "https://datalab.example.org/"},
    "impressum_url": "https://datalab.example.org/impressum",
    "privacy_url": "https://datalab.example.org/datenschutz",
}


@pytest.fixture(scope="module")
def good(tmp_path_factory):
    """One public export with a complete site.yaml, made once: (export dir, config dir)."""
    tmp = tmp_path_factory.mktemp("m14-deploy-check")
    r = rich._get_wrapped_function()(tmp)
    db_path, cfg, maps, docs, plans = r
    (cfg / "site.yaml").write_text(yaml.safe_dump(COMPLETE, allow_unicode=True), encoding="utf-8")
    out = tmp / "good"
    export.run_export(out, "/", db_path, cfg, maps, docs, _content(r), plans, False, public=True)
    return out, cfg


@pytest.fixture
def site(good, tmp_path):
    """A fresh copy of the good export to break, with the config dir."""
    out = tmp_path / "site"
    shutil.copytree(good[0], out)
    return out, good[1]


def _big_gz(out: Path) -> Path:
    gzs = sorted(p for p in _files(out) if p.suffix == ".gz")
    assert gzs
    return gzs[0]


def test_good_export_is_ready(site):
    out, cfg = site
    assert deploy_check.deploy_problems(out, None, cfg) == []
    assert deploy_check.deploy_problems(out, "/", cfg) == []


def test_missing_build_json(site):
    out, cfg = site
    (out / "build.json").unlink()
    assert any("build.json" in p for p in deploy_check.deploy_problems(out, "/", cfg))


def test_base_differs_from_build_json(site):
    out, cfg = site
    problems = deploy_check.deploy_problems(out, "/velometer/", cfg)
    assert any("build.json" in p and "base" in p for p in problems)


def test_missing_404(site):
    out, cfg = site
    (out / "404.html").unlink()
    assert any("404.html" in p for p in deploy_check.deploy_problems(out, None, cfg))


def test_missing_headers(site):
    out, cfg = site
    (out / "_headers").unlink()
    assert any("_headers" in p for p in deploy_check.deploy_problems(out, None, cfg))


def test_headers_csp_differs_from_the_meta_csp(site):
    out, cfg = site
    text = (out / "_headers").read_text()
    (out / "_headers").write_text(text.replace("frame-ancestors 'none'", "frame-ancestors *"))
    problems = deploy_check.deploy_problems(out, None, cfg)
    assert any("_headers" in p and "Content-Security-Policy" in p for p in problems)


def test_headers_csp_missing_frame_ancestors(site):
    out, cfg = site
    text = (out / "_headers").read_text()
    (out / "_headers").write_text(text.replace("; frame-ancestors 'none'", ""))
    assert any("_headers" in p for p in deploy_check.deploy_problems(out, None, cfg))


def test_missing_gz_for_an_eligible_file(site):
    out, cfg = site
    gz = _big_gz(out)
    gz.unlink()
    problems = deploy_check.deploy_problems(out, None, cfg)
    assert any(gz.name in p and "missing" in p for p in problems)


def test_gz_that_no_longer_matches_its_file(site):
    out, cfg = site
    gz = _big_gz(out)
    origin = gz.with_name(gz.name.removesuffix(".gz"))
    origin.write_bytes(origin.read_bytes() + b"\n<!-- edited by hand -->\n")
    problems = deploy_check.deploy_problems(out, None, cfg)
    assert any(origin.name in p and "differs" in p for p in problems)


def test_gz_that_is_not_gzip(site):
    out, cfg = site
    gz = _big_gz(out)
    gz.write_bytes(b"not gzip")
    assert any(gz.name in p for p in deploy_check.deploy_problems(out, None, cfg))


def test_stray_gz_without_its_file(site):
    out, cfg = site
    (out / "gone.json.gz").write_bytes(gzip.compress(b"{}"))
    problems = deploy_check.deploy_problems(out, None, cfg)
    assert any("gone.json.gz" in p and "stray" in p for p in problems)


def test_file_of_the_host_limit(site):
    out, cfg = site
    (out / "huge.bin").write_bytes(b"\0" * export.MAX_FILE_BYTES)
    assert any("huge.bin" in p for p in deploy_check.deploy_problems(out, None, cfg))
    (out / "huge.bin").write_bytes(b"\0" * (export.MAX_FILE_BYTES - 1))
    assert deploy_check.deploy_problems(out, None, cfg) == []


def test_unresolved_reference(site):
    out, cfg = site
    css = sorted((out / "static").rglob("*.css"))
    assert css
    css[0].unlink()
    assert any("unresolved" in p for p in deploy_check.deploy_problems(out, None, cfg))


def test_public_export_with_incomplete_site_settings(site, tmp_path):
    out, _cfg = site
    assert json.loads((out / "build.json").read_text())["public"] is True
    empty = tmp_path / "empty-config"
    empty.mkdir()
    problems = deploy_check.deploy_problems(out, None, empty)
    assert any("site.yaml" in p and "datalab.name" in p for p in problems)


def test_non_public_export_needs_no_site_settings(site, tmp_path):
    out, _cfg = site
    meta = json.loads((out / "build.json").read_text())
    meta["public"] = False
    (out / "build.json").write_text(json.dumps(meta))
    empty = tmp_path / "empty-config"
    empty.mkdir()
    assert deploy_check.deploy_problems(out, None, empty) == []


def test_cli_ok_and_broken(site):
    out, cfg = site
    runner = CliRunner()
    ok = runner.invoke(app, ["app", "deploy-check", str(out), "--config", str(cfg)])
    assert ok.exit_code == 0, ok.output
    assert ok.output.startswith("deploy-check ok: ")
    assert "base /, public True" in ok.output
    (out / "404.html").unlink()
    bad = runner.invoke(app, ["app", "deploy-check", str(out), "--config", str(cfg)])
    assert bad.exit_code == 1
    assert "404.html" in bad.output
