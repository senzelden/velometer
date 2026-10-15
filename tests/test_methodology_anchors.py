"""M13 Task 13b (user review, open-small b): methodology headings carry stable ids, the same id in
both editions, and an in-site link into the methodology page lands on one of them."""

import re
import shutil
from pathlib import Path

import pytest

from tests.report_fixture import build_report_fixture
from tests.test_app import CONTENT, _client, app_inputs
from velometer.app import export
from velometer.app.main import create_app
from velometer.report.data import ReportData, open_readonly

ROOT = Path(__file__).parents[1]
DOCS = {"en": ROOT / "docs/methodology.md", "de": ROOT / "docs/methodology.de.md"}
HEADING = re.compile(r"^(#{2,3}) ", re.M)
METHODOLOGY_LINK = re.compile(r'href="(/(?:de/)?methodology)#([^"]+)"')


def test_both_editions_have_the_same_heading_outline():
    # the German page takes its heading ids from the English heading at the same position
    en, de = (HEADING.findall(p.read_text(encoding="utf-8")) for p in DOCS.values())
    assert en and en == de


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Every HTML page of the export, with the real methodology files as the docs."""
    tmp = tmp_path_factory.mktemp("anchors")
    db_path, cfg = build_report_fixture(tmp)
    inputs = app_inputs(db_path, cfg, tmp)
    for p in DOCS.values():
        shutil.copy(p, inputs[3] / p.name)
    conn = open_readonly(db_path)
    with _client(create_app(*inputs, content_dir=CONTENT)) as c:
        pages = {}
        for url in export.export_urls(ReportData(conn, cfg), c.app):
            r = c.get(url)
            if r.headers["content-type"].startswith("text/html"):
                pages[url] = r.text
    conn.close()
    return pages


def _ids(html: str) -> list[str]:
    return re.findall(r'<h[23] id="([^"]+)"', html)


def test_methodology_headings_carry_the_same_ids_in_both_editions(site):
    en, de = _ids(site["/methodology"]), _ids(site["/de/methodology"])
    assert len(en) == len(HEADING.findall(DOCS["en"].read_text(encoding="utf-8")))
    assert en == de and len(set(en)) == len(en)
    assert "headline-and-presets" in en  # a slug of the English heading


def test_every_link_into_the_methodology_lands_on_an_id(site):
    found = {"en": 0, "de": 0}
    for url, html in site.items():
        for path, fragment in METHODOLOGY_LINK.findall(html):
            lang = "de" if path.startswith("/de/") else "en"
            target = site["/de/methodology" if lang == "de" else "/methodology"]
            assert f'id="{fragment}"' in target, (url, fragment)
            found[lang] += 1
    assert found["en"] and found["de"]  # the G7 pointer [#main-roads] on the organisation page
