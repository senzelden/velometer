"""M14 task 3: `velometer app deploy-check`, the dry run on a finished export."""

import gzip
import json
import re
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.test_app_base import build_rich
from tests.test_export import _content, _files
from velometer.app import deploy_check, export
from velometer.app.repo_links import bare_repo_paths
from velometer.cli import app

COMPLETE = {
    "datalab": {"name": "Zählwerk Berlin Datalab", "url": "https://datalab.example.org/"},
    "impressum_url": "https://datalab.example.org/impressum",
    "privacy_url": "https://datalab.example.org/datenschutz",
    "repo": {
        "url": "https://forge.example.org/owner/velometer",
        "file_url": "https://forge.example.org/owner/velometer/blob/{commit}/{path}",
    },
}
REPO_SENTENCE = "\nThe code is MIT-licensed.<!-- repo: It is in the [repository]({repo_url}). -->\n"
# a public export needs a clean checkout (M16); the tests' tree may be mid-edit
CLEAN_COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture(scope="module")
def good(tmp_path_factory):
    """One public export with a complete site.yaml, made once: (export dir, config dir)."""
    tmp = tmp_path_factory.mktemp("m14-deploy-check")
    r = build_rich(tmp)
    db_path, cfg, maps, docs, plans = r
    (cfg / "site.yaml").write_text(yaml.safe_dump(COMPLETE, allow_unicode=True), encoding="utf-8")
    for name in ("methodology.md", "methodology.de.md"):  # the repo sentence (1.1c, R45 M5)
        page = docs / name
        text = page.read_text(encoding="utf-8") if page.is_file() else "# Methodology\n"
        page.write_text(text + REPO_SENTENCE, encoding="utf-8")
    out = tmp / "good"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(export, "public_commit", lambda: CLEAN_COMMIT)
        mp.setattr(export, "figures_drift", lambda conn, config_dir: [])  # synthetic figures
        export.run_export(
            out, "/", db_path, cfg, maps, docs, _content(r), plans, False, public=True,
            tiles_info=_sidecar(tmp),
        )  # fmt: skip
    return out, cfg


TILES_INFO = {"protomaps_build": "2026-08-11", "maxzoom": 13, "sha256": "ab" * 32}


def _sidecar(tmp: Path) -> Path:
    """The sidecar tools/tiles.py writes beside the extract."""
    path = tmp / "velometer.pmtiles.json"
    path.write_text(json.dumps({"file": "velometer.pmtiles", **TILES_INFO}), encoding="utf-8")
    return path


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


@pytest.mark.parametrize("page", ["methodology/index.html", "de/methodology/index.html"])
def test_a_public_export_whose_methodology_does_not_link_the_repo_is_refused(site, page):
    """Legal review 1.1c (R45 M5): each edition's methodology page links repo.url."""
    out, _ = site
    path = out / page
    repo = COMPLETE["repo"]["url"]
    text = path.read_text(encoding="utf-8")
    assert f'href="{repo}"' in text
    path.write_text(text.replace(f'href="{repo}"', 'href="https://elsewhere.example/"'))
    problems = deploy_check.deploy_problems(out, None)
    assert [p for p in problems if "does not link the repository" in p and page in p], problems
    path.unlink()
    problems = deploy_check.deploy_problems(out, None)
    assert [p for p in problems if f"{page} is missing" in p], problems


def test_good_export_is_ready(site):
    out, cfg = site
    assert deploy_check.deploy_problems(out, None) == []
    assert deploy_check.deploy_problems(out, "/") == []


def test_a_public_export_records_the_basemaps_build_and_its_maps_carry_the_date(site):
    """Spec §4.3, legal review 1.7: build.json `tiles`, and the maps' credit date from it."""
    out, _ = site
    build = json.loads((out / "build.json").read_text(encoding="utf-8"))
    assert build["tiles"] == TILES_INFO
    page = (out / "city" / "berlin" / "tiers" / "index.html").read_text(encoding="utf-8")
    assert '"tiles_build": "2026-08-11"' in page or '"tiles_build":"2026-08-11"' in page


def test_a_public_export_without_the_basemaps_build_is_refused(site):
    out, _ = site
    path = out / "build.json"
    build = json.loads(path.read_text(encoding="utf-8"))
    build["tiles"] = None
    path.write_text(json.dumps(build), encoding="utf-8")
    problems = deploy_check.deploy_problems(out, None)
    assert [p for p in problems if "records no tiles" in p], problems


def test_missing_build_json(site):
    out, cfg = site
    (out / "build.json").unlink()
    assert any("build.json" in p for p in deploy_check.deploy_problems(out, "/"))


def test_base_differs_from_build_json(site):
    out, cfg = site
    problems = deploy_check.deploy_problems(out, "/velometer/")
    assert any("build.json" in p and "base" in p for p in problems)


def test_missing_404(site):
    out, cfg = site
    (out / "404.html").unlink()
    assert any("404.html" in p for p in deploy_check.deploy_problems(out, None))


def test_missing_headers(site):
    out, cfg = site
    (out / "_headers").unlink()
    assert any("_headers" in p for p in deploy_check.deploy_problems(out, None))


def test_headers_csp_differs_from_the_meta_csp(site):
    out, cfg = site
    text = (out / "_headers").read_text()
    (out / "_headers").write_text(text.replace("frame-ancestors 'none'", "frame-ancestors *"))
    problems = deploy_check.deploy_problems(out, None)
    assert any("_headers" in p and "Content-Security-Policy" in p for p in problems)


def test_headers_csp_missing_frame_ancestors(site):
    out, cfg = site
    text = (out / "_headers").read_text()
    (out / "_headers").write_text(text.replace("; frame-ancestors 'none'", ""))
    assert any("_headers" in p for p in deploy_check.deploy_problems(out, None))


def test_missing_gz_for_an_eligible_file(site):
    out, cfg = site
    gz = _big_gz(out)
    gz.unlink()
    problems = deploy_check.deploy_problems(out, None)
    assert any(gz.name in p and "missing" in p for p in problems)


def test_gz_that_no_longer_matches_its_file(site):
    out, cfg = site
    gz = _big_gz(out)
    origin = gz.with_name(gz.name.removesuffix(".gz"))
    origin.write_bytes(origin.read_bytes() + b"\n<!-- edited by hand -->\n")
    problems = deploy_check.deploy_problems(out, None)
    assert any(origin.name in p and "differs" in p for p in problems)


def test_gz_that_is_not_gzip(site):
    out, cfg = site
    gz = _big_gz(out)
    gz.write_bytes(b"not gzip")
    assert any(gz.name in p for p in deploy_check.deploy_problems(out, None))


def test_stray_gz_without_its_file(site):
    out, cfg = site
    (out / "gone.json.gz").write_bytes(gzip.compress(b"{}"))
    problems = deploy_check.deploy_problems(out, None)
    assert any("gone.json.gz" in p and "stray" in p for p in problems)


def test_file_of_the_host_limit(site):
    out, cfg = site
    (out / "huge.bin").write_bytes(b"\0" * export.MAX_FILE_BYTES)
    assert any("huge.bin" in p for p in deploy_check.deploy_problems(out, None))
    (out / "huge.bin").write_bytes(b"\0" * (export.MAX_FILE_BYTES - 1))
    assert deploy_check.deploy_problems(out, None) == []


def test_unresolved_reference(site):
    out, cfg = site
    css = sorted((out / "static").rglob("*.css"))
    assert css
    css[0].unlink()
    assert any("unresolved" in p for p in deploy_check.deploy_problems(out, None))


def test_the_public_values_are_in_build_json(site):
    out, _cfg = site
    build = json.loads((out / "build.json").read_text())
    assert build["public"] is True
    assert build["site"] == {
        "datalab_name": COMPLETE["datalab"]["name"],
        "datalab_url": COMPLETE["datalab"]["url"],
        "impressum_url": COMPLETE["impressum_url"],
        "privacy_url": COMPLETE["privacy_url"],
        "repo_url": COMPLETE["repo"]["url"],
        "repo_file_url": COMPLETE["repo"]["file_url"],
    }


def test_a_public_export_links_its_repo_paths_at_its_commit(site):
    # M16 (R42): no page prints a repo path a reader cannot open; links pin the export's commit
    out, _cfg = site
    assert json.loads((out / "build.json").read_text())["commit_full"] == CLEAN_COMMIT
    pages = {p: p.read_text(encoding="utf-8") for p in sorted(out.rglob("*.html"))}
    assert all(bare_repo_paths(html) == [] for html in pages.values())
    blob = f"https://forge.example.org/owner/velometer/blob/{CLEAN_COMMIT}/"
    bezirke = pages[out / "city" / "berlin" / "bezirke" / "index.html"]
    assert f'<a href="{blob}docs/review"><code>docs/review</code></a>' in bezirke
    assert sum(html.count(blob) for html in pages.values()) > 0


def test_deploy_check_fails_a_public_export_with_a_bare_repo_path(site):
    # red-proof of the guard: the same export with the repo links taken out again
    out, _cfg = site
    link = re.compile(r'<a href="https://forge\.example\.org/[^"]*">(<code>[^<]*</code>)</a>')
    page = out / "city" / "berlin" / "bezirke" / "index.html"
    page.write_text(link.sub(r"\1", page.read_text(encoding="utf-8")), encoding="utf-8")
    problems = deploy_check.deploy_problems(out, None)
    assert any(
        "city/berlin/bezirke/index.html" in p
        and "not linked to the repo" in p
        and "docs/review" in p
        for p in problems
    ), problems


def test_a_public_export_is_judged_by_itself_not_todays_site_yaml(site):
    # final review M5: the export was made from a config that is not the repo's (empty) one
    out, _cfg = site
    assert deploy_check.deploy_problems(out, None) == []
    assert deploy_check.deploy_problems(out, None, public=True) == []


def test_a_public_export_without_its_site_values(site):
    out, _cfg = site
    build = json.loads((out / "build.json").read_text())
    del build["site"]["impressum_url"]
    (out / "build.json").write_text(json.dumps(build))
    problems = deploy_check.deploy_problems(out, None)
    assert any("build.json" in p and "impressum_url" in p for p in problems), problems


def test_a_public_export_whose_page_lost_its_footer_link(site):
    out, _cfg = site
    page = out / "cities" / "index.html"
    html = page.read_text(encoding="utf-8")
    page.write_text(html.replace(COMPLETE["impressum_url"], "https://elsewhere.example/"))
    gz = page.with_name(page.name + ".gz")  # kept matching: only the footer is at fault
    gz.write_bytes(gzip.compress(page.read_bytes(), mtime=0))
    problems = deploy_check.deploy_problems(out, None)
    assert any("cities/index.html" in p and "footer" in p for p in problems), problems


def test_non_public_export_needs_no_site_settings_but_fails_with_public(site):
    out, _cfg = site
    meta = json.loads((out / "build.json").read_text())
    meta["public"] = False
    del meta["site"]
    (out / "build.json").write_text(json.dumps(meta))
    assert deploy_check.deploy_problems(out, None) == []
    problems = deploy_check.deploy_problems(out, None, public=True)
    assert any("not a public export" in p for p in problems), problems


def test_cli_ok_and_broken(site):
    out, cfg = site
    runner = CliRunner()
    ok = runner.invoke(app, ["app", "deploy-check", str(out), "--public"])
    assert ok.exit_code == 0, ok.output
    assert ok.output.startswith("deploy-check ok: ")
    assert "base /, public True" in ok.output
    (out / "404.html").unlink()
    bad = runner.invoke(app, ["app", "deploy-check", str(out), "--public"])
    assert bad.exit_code == 1
    assert "404.html" in bad.output
