"""M17 Task 11: the Zenodo DOIs where they belong (spec §4.3).

The DOIs are configured once, in `config/site.public.yaml`. `CITATION.cff` and the README carry
the same ones; the Cite box, which cites a data set, carries the dataset DOI of the site config it
is rendered with (user ruling, fix round 1)."""

import json
import re
from html import unescape
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from tests.test_app_base import build_rich
from tests.test_export import _content
from tests.test_m17_crawl import _site_yaml
from velometer.app.cite import CiteFields, cite_text
from velometer.app.main import create_app
from velometer.config import SiteConfig, load_site

REPO = Path(__file__).resolve().parents[1]
DATASET_DOI = "10.5281/zenodo.7654321"  # test values, never committed config
SOFTWARE_DOI = "10.5281/zenodo.1111111"
FIELDS = {
    "title": "Berlin, headline",
    "path": "/city/berlin/time",
    "osm_timestamp": "2026-10-03T21:00:00Z",
    "snapshot_note": None,
    "classifier": "v4",
    "run_id": "12",
    "commit": "abc1234",
}


def _public_site() -> SiteConfig:
    """The committed public site values: `site.public.yaml` alone (a local `site.yaml` is not in
    a fresh checkout)."""
    raw = (REPO / "config" / "site.public.yaml").read_text(encoding="utf-8")
    return SiteConfig.model_validate(yaml.safe_load(raw))


def test_public_config_sets_both_dois():
    site = _public_site()
    assert site.dataset_doi and site.software_doi  # the model holds them to 10.5281/zenodo.<n>
    assert site.dataset_doi != site.software_doi


def test_citation_has_concept_doi():
    cff = yaml.safe_load((REPO / "CITATION.cff").read_text(encoding="utf-8"))
    dois = [i["value"] for i in cff.get("identifiers", []) if i.get("type") == "doi"]
    assert dois == [_public_site().software_doi]
    assert cff.get("doi") in (None, _public_site().software_doi)


def test_readme_badge_matches():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    head = readme.split("\n## ", 1)[0]  # the badges sit above the first section
    site = _public_site()
    for doi in (site.software_doi, site.dataset_doi):
        badge = re.compile(
            r"\[!\[[^\]]*\]\(https://zenodo\.org/badge/DOI/" + re.escape(doi) + r"\.svg\)\]"
            r"\(https://doi\.org/" + re.escape(doi) + r"\)"
        )
        assert badge.search(head), doi
    # every DOI the README names is a configured one
    named = set(re.findall(r"10\.5281/zenodo\.\d+", readme))
    assert named == {site.software_doi, site.dataset_doi}
    citation = readme.split("\n## Citation\n", 1)[1].split("\n## ", 1)[0]
    for doi in (site.software_doi, site.dataset_doi):
        assert f"https://doi.org/{doi}" in citation, doi


@pytest.mark.parametrize("lang", ["en", "de"])
def test_cite_text_has_doi(lang):
    with_doi = cite_text(CiteFields(**FIELDS, doi=DATASET_DOI), lang=lang)
    assert f"https://doi.org/{DATASET_DOI}" in with_doi
    url = "https://velometer.example/city/berlin/time"
    dated = cite_text(CiteFields(**FIELDS, doi=DATASET_DOI), "2026-10-11", url, lang=lang)
    assert dated.index(f"https://doi.org/{DATASET_DOI}") < dated.index(url)  # the page last
    without = cite_text(CiteFields(**FIELDS), lang=lang)
    assert "doi" not in without.lower()
    assert with_doi.startswith(without)  # the DOI adds to the citation, changes nothing in it


@pytest.fixture(scope="module")
def rich(tmp_path_factory):
    return build_rich(tmp_path_factory.mktemp("dois"))


@pytest.mark.parametrize("dataset_doi", [DATASET_DOI, None])
def test_cite_box_carries_the_configured_dataset_doi(rich, dataset_doi):
    db_path, cfg, maps, docs, plans = rich
    _site_yaml(cfg, doi=dataset_doi, software_doi=SOFTWARE_DOI)
    assert load_site(cfg).dataset_doi == dataset_doi
    app = create_app(db_path, cfg, maps, docs, content_dir=_content(rich), plans_data_dir=plans)
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        html = c.get("/city/berlin/time").text
    texts = [unescape(t) for t in re.findall(r'<p class="cite-text">(.*?)</p>', html, re.S)]
    data = re.findall(r'<script type="application/json" class="cite-data">(.*?)</script>', html)
    blobs = [json.loads(b) for b in data]
    assert texts and len(texts) == len(blobs)
    for text, blob in zip(texts, blobs, strict=True):
        assert blob["doi"] == dataset_doi
        assert (f"https://doi.org/{DATASET_DOI}" in text) == (dataset_doi is not None)
        assert SOFTWARE_DOI not in text  # the software's DOI is CITATION.cff's, not a figure's
    assert "doi.org/None" not in html


def test_cite_commit_is_the_public_commit_build_json_records(monkeypatch):
    """An untracked file (a sandbox's stub) does not make a Cite's commit `-dirty`: the Cite
    names the commit build.json names (`export.public_commit`), tracked changes still count."""
    from velometer import run
    from velometer.app import cite, export
    from velometer.reconcile import short_commit

    sha = "0123456789abcdef0123456789abcdef01234567"

    def fake_git(status):
        def git(*args):
            if args[0] == "rev-parse":
                return sha + "\n"
            if "--untracked-files=no" in args:
                return "\n".join(line for line in status if not line.startswith("??"))
            return "\n".join(status)

        return git

    for status, want in (
        (["?? .bashrc"], sha[:7]),
        ([" M x.py", "?? .bashrc"], sha[:7] + "-dirty"),
    ):
        monkeypatch.setattr(run, "_git", fake_git(status))
        monkeypatch.setattr(export, "_git", fake_git(status))
        cite._commit.cache_clear()
        try:
            assert cite._commit() == want == short_commit(export.public_commit())
        finally:
            cite._commit.cache_clear()
