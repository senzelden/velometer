"""M17 Task 4: the Datalab's robots.txt, sitemap.xml and llms.txt, and `--checked` per build."""

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from tests.helpers import load_script
from tests.test_m16_datalab import SITE_YAML, _cfg, _export
from velometer import datalab
from velometer.cli import app
from velometer.datalab import build, load_config

srv = load_script("tools/server.py")
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
CRAWL = ("robots.txt", "sitemap.xml", "llms.txt")


def _built(tmp_path: Path, **over) -> Path:
    out = tmp_path / "out"
    build(_cfg(**over), _export(tmp_path), out)
    return out


def _cli(tmp_path: Path, *extra: str):
    out = tmp_path / "out"
    r = CliRunner().invoke(
        app,
        ["datalab", "build", "--velometer-export", str(_export(tmp_path)), "--out", str(out),
         "--config", str(SITE_YAML), *extra],
    )  # fmt: skip
    return r, out


def test_datalab_sitemap_pages(tmp_path):
    """The pages are the PAGES outputs minus the 404 page, as absolute URLs on the domain."""
    out = _built(tmp_path)
    root = ET.fromstring((out / "sitemap.xml").read_text(encoding="utf-8"))
    locs = [e.text for e in root.findall("s:url/s:loc", NS)]
    expected = []
    for rel in datalab.PAGES.values():
        if rel == datalab.NOT_FOUND_PAGE:
            continue
        route = "/" + rel.removesuffix("index.html")
        expected.append(f"https://example.org{route}")
    assert sorted(locs) == sorted(expected)
    assert len(locs) == len(set(locs)) == len(datalab.PAGES) - 1
    assert not any("404" in loc for loc in locs)


def test_datalab_sitemap_has_no_lastmod_and_no_alternates(tmp_path):
    text = (_built(tmp_path) / "sitemap.xml").read_text(encoding="utf-8")
    assert "lastmod" not in text
    assert "hreflang" not in text


def test_datalab_robots_points_to_sitemap(tmp_path):
    text = (_built(tmp_path) / "robots.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert "User-agent: *" in lines and "Allow: /" in lines
    assert "Sitemap: https://example.org/sitemap.xml" in lines
    assert not any(line.startswith("Disallow") for line in lines)


def test_datalab_llms_txt_is_facts_from_the_site(tmp_path):
    out = _built(tmp_path, contact_email="hallo@example.org")
    text = (out / "llms.txt").read_text(encoding="utf-8")
    assert text.startswith("# ")
    for url in (
        "https://velometer.example.org/",
        "https://example.org/impressum/",
        "https://example.org/datenschutz/",
        "https://example.org/barrierefreiheit/",
    ):
        assert url in text
    assert "{" not in text and "@" not in text and "gmail" not in text.lower()


def test_datalab_crawl_files_are_in_the_written_list(tmp_path):
    out = tmp_path / "out"
    written = build(_cfg(), _export(tmp_path), out)
    assert set(CRAWL) <= set(written)


def test_datalab_checked_override(tmp_path):
    before = SITE_YAML.read_bytes()
    r, out = _cli(tmp_path, "--checked", "2026-11-05")
    assert r.exit_code == 0, r.output
    page = (out / "barrierefreiheit" / "index.html").read_text(encoding="utf-8")
    assert "5. November 2026" in page
    assert "29. Oktober 2026" not in page
    assert SITE_YAML.read_bytes() == before
    assert json.loads((out / "build.json").read_text(encoding="utf-8"))["checked"] == "2026-11-05"


def test_datalab_build_without_checked_uses_the_site_yaml_date(tmp_path):
    r, out = _cli(tmp_path)
    assert r.exit_code == 0, r.output
    day = load_config(SITE_YAML).accessibility.checked
    assert day is not None
    assert datalab.i18n.long_day(day, "de") in (out / "barrierefreiheit/index.html").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "bad", ["2026-13-01", "5.11.2026", "2026-11-5", "20261105", "2026-W45-4", "tomorrow", ""]
)
def test_datalab_checked_rejects_a_bad_date(tmp_path, bad):
    r, out = _cli(tmp_path, "--checked", bad)
    assert r.exit_code != 0
    assert "--checked" in r.output and "YYYY-MM-DD" in r.output
    assert not out.exists()


def test_datalab_checked_format_takes_ascii_digits_only():
    """`\\d` would also take other scripts' digits (Arabic-Indic here); the format is ASCII."""
    assert datalab.CHECKED_FORMAT.fullmatch("2026-10-29")
    arabic_indic = "\u0662\u0660\u0662\u0666-\u0661\u0660-\u0662\u0669"  # 2026-10-29
    assert datalab.CHECKED_FORMAT.fullmatch(arabic_indic) is None


def test_datalab_checked_override_keeps_the_inputs_stamp(tmp_path):
    """The stamp is of the committed settings, so the deploy check still accepts the build."""
    r, out = _cli(tmp_path, "--checked", "2026-11-05")
    assert r.exit_code == 0, r.output
    assert datalab.read_stamp(out) == datalab.inputs_stamp(load_config(SITE_YAML))


@pytest.mark.parametrize("missing", CRAWL)
def test_check_datalab_build_requires_the_crawl_files(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(srv.DEPS, "git_dirty", lambda: False)
    out = tmp_path / "out"
    build(load_config(SITE_YAML), _export(tmp_path), out)
    srv.check_datalab_build(out)  # a complete build passes
    (out / missing).unlink()
    with pytest.raises(srv.ServerError, match=re.escape(missing)):
        srv.check_datalab_build(out)
