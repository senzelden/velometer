"""M17 Task 6: schema.org JSON-LD of the public pages, and the DOI that fails closed."""

import json
import re
from html import unescape
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from tests.test_app_base import build_rich
from tests.test_export import _content
from tests.test_m17_crawl import ORIGIN, _export, _site_yaml
from tests.test_m17_datalab_crawl import _built
from velometer.app import deploy_check, jsonld
from velometer.app.main import create_app
from velometer.config import ConfigError, load_site

REPO = Path(__file__).resolve().parents[1]
DOI = "10.5281/zenodo.1234567"  # a test value, never committed config
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ODBL = "https://opendatacommons.org/licenses/odbl/1-0/"


def _ld(html: str) -> list[dict]:
    """Every JSON-LD object of the page's head, parsed."""
    head = html.split("</head>", 1)[0]
    return [json.loads(raw) for raw in LD.findall(head)]


def _of(html: str, kind: str) -> dict:
    found = [o for o in _ld(html) if o["@type"] == kind]
    assert len(found) == 1, (kind, [o["@type"] for o in _ld(html)])
    return found[0]


def _text(html: str) -> str:
    body = html.split("</head>", 1)[1]
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", body)).split())


def _read(out: Path, route: str) -> str:
    return (out / route.strip("/") / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rich(tmp_path_factory):
    return build_rich(tmp_path_factory.mktemp("jsonld"))


@pytest.fixture(scope="module")
def out_doi(rich, tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp:
        yield _export(rich, tmp_path_factory.mktemp("doi"), mp, doi=DOI)


@pytest.fixture(scope="module")
def out_no_doi(rich, tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp:
        yield _export(rich, tmp_path_factory.mktemp("nodoi"), mp, doi=None)


@pytest.mark.parametrize("route", ["/", "/de/"])
def test_collection_required_fields(out_doi, route):
    html = _read(out_doi, route)
    obj = _of(html, "Dataset")
    assert obj["@context"] == "https://schema.org"
    assert obj["name"]
    assert 50 <= len(obj["description"]) <= 5000
    assert obj["license"] == ODBL
    assert obj["isAccessibleForFree"] is True
    assert obj["creator"] == {"@type": "Person", "name": "Dennis Senzel"}
    assert obj["url"].startswith(ORIGIN)
    assert obj["identifier"] == f"https://doi.org/{DOI}"
    first, last = obj["temporalCoverage"].split("/")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", first) and first <= last
    (dist,) = obj["distribution"]
    assert dist["@type"] == "DataDownload" and dist["encodingFormat"] == "text/csv"
    assert dist["contentUrl"].startswith(ORIGIN)  # absolute
    assert (out_doi / dist["contentUrl"].removeprefix(ORIGIN)).is_file()  # and in the export
    assert obj["isBasedOn"] and all(s["url"].startswith("https://") for s in obj["isBasedOn"])
    names = {s["name"] for s in obj["isBasedOn"]}
    assert {"OpenStreetMap", "Eurostat GISCO", "Eurostat"} <= names


@pytest.mark.parametrize("route", ["/", "/de/"])
def test_jsonld_matches_visible_text(out_doi, route):
    """Every place the Dataset names is on the page, and hasPart is the city pages the visible
    ranking links, in the ranking's order (the order the home sentence reads its ends from)."""
    html = _read(out_doi, route)
    obj = _of(html, "Dataset")
    text = _text(html)
    names = [p["name"] for p in obj["spatialCoverage"]]
    assert names
    for name in names:
        assert name in text, name
    table = html.split('<table class="ranking', 1)[1].split("</table>", 1)[0]
    linked = re.findall(r'<td data-label="[^"]*"><a href="([^"]*/city/[a-z0-9_-]+)"', table)
    ids = [u.rsplit("/", 1)[1] for u in linked]
    parts = [p["url"].rstrip("/").rsplit("/", 1)[1] for p in obj["hasPart"]]
    assert ids and parts == ids
    assert len(names) == len(ids)
    sentence = re.search(r'<span id="home-sentence">(.*?)</span>', html, re.S)
    if sentence:  # the ends the sentence names are the ends of the Dataset's own order
        said = _text(sentence.group(1))
        assert names[0] in said


def test_city_dataset_is_part_of_the_collection(out_doi):
    html = _read(out_doi, "/city/berlin")
    city = _of(html, "Dataset")
    home = _of(_read(out_doi, "/"), "Dataset")
    assert city["isPartOf"]["@id"] == home["@id"]
    assert city["url"] in {p["url"] for p in home["hasPart"]}
    assert "Berlin" in _text(html) and city["spatialCoverage"]["name"] == "Berlin"
    assert 50 <= len(city["description"]) <= 5000
    assert city["license"] == ODBL
    assert (out_doi / city["distribution"][0]["contentUrl"].removeprefix(ORIGIN)).is_file()
    assert "identifier" not in city  # the DOI is the collection's
    assert _of(_read(out_doi, "/de/city/berlin"), "Dataset")["inLanguage"] == "de"


def test_website_and_methodology_article(out_doi):
    home = _of(_read(out_doi, "/"), "WebSite")
    assert home["name"] == "velometer" and home["url"] == ORIGIN
    art = _of(_read(out_doi, "/methodology"), "TechArticle")
    assert art["url"] == ORIGIN + "methodology"
    assert art["author"]["name"] == "Dennis Senzel" and art["description"]
    de = _of(_read(out_doi, "/de/methodology"), "TechArticle")
    assert de["url"] == ORIGIN + "de/methodology" and de["inLanguage"] == "de"
    legacy = _of(_read(out_doi, "/methodology/de"), "TechArticle")
    assert legacy["url"] == de["url"]  # the legacy page is the German edition


def test_pages_without_structured_data(out_doi):
    for route in ("/cities", "/city/berlin/time"):
        assert _ld(_read(out_doi, route)) == [], route


def test_no_doi_leaves_out_the_identifier(out_no_doi):
    obj = _of(_read(out_no_doi, "/"), "Dataset")
    assert "identifier" not in obj
    assert "None" not in _read(out_no_doi, "/") or "doi.org/None" not in _read(out_no_doi, "/")


def test_public_check_requires_dataset_doi(out_doi, out_no_doi):
    """Without a dataset DOI the export builds but `deploy-check --public` reports exactly the
    one problem; with one it is clean."""
    problems = deploy_check.deploy_problems(out_no_doi, None, public=True)
    assert [p for p in problems if "JSON-LD" in p] == ["JSON-LD identifier: no dataset DOI"]
    clean = deploy_check.deploy_problems(out_doi, None, public=True)
    assert not [p for p in clean if "JSON-LD" in p], clean


def test_public_check_refuses_a_home_page_without_the_dataset(out_doi, tmp_path):
    """The check reads the page, not the config: a home page whose Dataset has lost its
    identifier (or the whole JSON-LD) fails."""
    import shutil

    copy = tmp_path / "copy"
    shutil.copytree(out_doi, copy)
    home = copy / "index.html"
    text = home.read_text(encoding="utf-8")
    home.write_text(LD.sub("", text), encoding="utf-8")
    for gz in copy.rglob("*.gz"):
        gz.unlink()
    problems = deploy_check.deploy_problems(copy, None, public=True)
    assert "JSON-LD identifier: no dataset DOI" in problems


def test_preview_has_no_jsonld(rich):
    """A local preview (not a public export) has no public origin to name: no structured data."""
    db_path, cfg, maps, docs, plans = rich
    app = create_app(db_path, cfg, maps, docs, content_dir=_content(rich), plans_data_dir=plans)
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        assert "ld+json" not in c.get("/").text


def test_script_escapes_script_close():
    obj = {"@type": "Dataset", "description": "a </script><script>alert(1)</script> b </ c"}
    el = str(jsonld.script(obj))
    assert el.count("</script>") == 1 and el.endswith("</script>")
    inner = LD.search(el).group(1)
    assert "</" not in inner
    assert json.loads(inner)["description"] == obj["description"]  # the same string
    assert "Zählwerk" in str(jsonld.script({"name": "Zählwerk"}))  # not ASCII-escaped


def test_jsonld_escapes_script_close_in_a_page(rich, tmp_path):
    """A dek quoting `</script` (no closing `>`, so it is no tag the description strips) reaches
    the city Dataset: the page still has one parseable JSON-LD element and its own `</script>`s
    stay the page's."""
    db_path, cfg, maps, docs, plans = rich
    _site_yaml(cfg, DOI)
    content = tmp_path / "content"
    import shutil

    shutil.copytree(_content(rich), content)
    path = content / "narratives" / "berlin.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["dek"] = (
        "Berlin maps 12.3 km of protected tracks per 100 km of main roads </script and rising."
    )
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    app = create_app(
        db_path, cfg, maps, docs, content_dir=content, plans_data_dir=plans, public=True
    )
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        html = c.get("/city/berlin").text
    head = html.split("</head>", 1)[0]
    (raw,) = LD.findall(head)
    assert "</script and" in json.loads(raw)["description"]
    assert "</script and" not in head


def test_dois_are_zenodo_dois(tmp_path):
    for bad in ("10.1234/zenodo.1", "https://doi.org/10.5281/zenodo.1", "10.5281/zenodo.x"):
        (tmp_path / "site.yaml").write_text(yaml.safe_dump({"dataset_doi": bad}))
        with pytest.raises(ConfigError):
            load_site(tmp_path)
    (tmp_path / "site.yaml").write_text(
        yaml.safe_dump({"dataset_doi": DOI, "software_doi": "10.5281/zenodo.7"})
    )
    assert load_site(tmp_path).dataset_doi == DOI


def test_shipped_public_config_has_no_dois_yet():
    """Until Task 11 the committed public values carry no DOI (never a made-up one): the keys
    exist and are null, or are real Zenodo DOIs."""
    raw = yaml.safe_load((REPO / "config" / "site.public.yaml").read_text(encoding="utf-8"))
    for key in ("dataset_doi", "software_doi"):
        assert key in raw
        assert raw[key] is None or re.fullmatch(r"10\.5281/zenodo\.\d+", raw[key])


def test_datalab_home_names_velometer_as_its_project(tmp_path):
    out = _built(tmp_path)
    obj = _ld((out / "index.html").read_text(encoding="utf-8"))
    (org,) = obj
    assert org["@type"] == "Organization" and org["name"] == "Zählwerk Berlin Datalab"
    assert org["owns"]["name"] == "velometer" and org["owns"]["url"].startswith(
        "https://velometer."
    )
    assert org["name"] in _text((out / "index.html").read_text(encoding="utf-8"))
    assert _ld((out / "impressum" / "index.html").read_text(encoding="utf-8")) == []
