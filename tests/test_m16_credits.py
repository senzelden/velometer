"""M16 Task 2: the data credits the legal review requires (docs/review/m16-legal.md, F1-F8, F15).

F1 one OSM notice with both URIs in every download; F2 the GISCO boundary notice in its
prescribed wording; F3 the population credit of each statistics office and the per-capita
disclaimer; F4 the counter credit says the index is ours; F5-F8, F15 the ADR 0008 entries.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from tests.test_app import client, setup  # noqa: F401  (fixtures)
from tests.test_app_base import build_rich
from tests.test_change import _golden_outputs
from tests.test_export import _export
from tests.test_maps import _row, placed  # noqa: F401  (`placed` is a fixture)
from velometer import credits, i18n
from velometer.report import charts, maps
from velometer.report.csvexport import csv_preamble
from velometer.report.methodology import methodology_facts, render

ROOT = Path(__file__).parents[1]
OSM_URIS = (
    "https://www.openstreetmap.org/copyright",
    "https://opendatacommons.org/licenses/odbl/1-0/",
)
PRINTED_URIS = ("openstreetmap.org/copyright", "opendatacommons.org/licenses/odbl/1-0/")
GISCO = {
    "en": "© EuroGeographics for the administrative boundaries",
    "de": "© EuroGeographics bezüglich der Verwaltungsgrenzen",
}
COMPUTED = {
    "en": "; index and totals computed by velometer",
    "de": "; Index und Summen von velometer berechnet",
}
INSEE = "INSEE populations de référence 2023, population municipale (https://www.insee.fr/x)"
INE = "INE Revisión del Padrón Municipal 2025 (1 Jan 2025) (https://www.ine.es/jaxiT3/x)"
GISCO_POP = "GISCO LAU 2024 POP_2024"
EUROSTAT_POP = "Eurostat demo_r_pjangrp3 FR101 2024"


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    """The static export of the rich fixture (every page part present)."""
    tmp = tmp_path_factory.mktemp("m16-credits")
    rich = build_rich(tmp)
    out = tmp / "out"
    _export(rich, out)
    return out


def _lang(html: str) -> str:
    """The page's language (/methodology/de is German outside /de/)."""
    return re.search(r'<html lang="(\w+)"', html).group(1)


# --- F1: one OSM notice with both URIs ------------------------------------------------------


def test_osm_notice_names_both_uris():
    for uri in OSM_URIS:
        assert uri in credits.OSM_NOTICE
    for uri in PRINTED_URIS:
        assert uri in credits.OSM_PRINTED


def test_csv_preamble_carries_both_osm_uris():
    first = csv_preamble("abc", "2026-10-21T00:00:00Z").splitlines()[0]
    for uri in OSM_URIS:
        assert uri in first
    assert "mapped km, not built km" in first  # ADR 0006 stays


def test_every_exported_csv_carries_the_notices(exported):
    files = sorted((exported / "data").glob("*.csv"))
    assert files
    for path in files:
        head = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("#")]
        text = "\n".join(head)
        for uri in OSM_URIS:
            assert uri in text, path
        assert GISCO["en"] in text, path


def test_series_json_carries_the_osm_notice(exported):
    doc = json.loads((exported / "data" / "series.json").read_text(encoding="utf-8"))
    assert doc["attribution"] == credits.OSM_NOTICE


def test_change_map_geojson_has_a_top_level_osm_notice(tmp_path):
    _, raw = _golden_outputs(tmp_path)
    assert json.loads(raw)["attribution"] == credits.OSM_NOTICE


def test_tier_map_png_footer_prints_the_copyright_and_licence(fixture_db):
    point = fixture_db[3].current("berlin", "lau")
    for lang in i18n.LANGS:
        _, footer, _ = maps.map_texts(point, "Berlin", "lau", lang)
        for uri in PRINTED_URIS:
            assert uri in footer, lang


def test_chart_images_print_the_copyright_and_licence():
    for lang in i18n.LANGS:
        for uri in PRINTED_URIS:
            assert uri in i18n.t(lang, "js.download.attribution"), lang
    for uri in PRINTED_URIS:
        assert uri in charts.ATTRIBUTION


# --- F1 + F2: the tier-map GeoJSON ----------------------------------------------------------


def _tier_geojson(placed, monkeypatch, source: str) -> dict:  # noqa: F811
    conn, data, data_dir, maps_dir = placed
    snap = maps.snapshot_path(_row(conn, data), data_dir)
    snap.parent.mkdir(parents=True)
    snap.write_bytes(b"")  # never read: the classification is stubbed
    monkeypatch.setattr(maps, "tiered", lambda *a, **k: ([], {}))
    monkeypatch.setattr(maps, "_draw", lambda *a, **k: None)
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    ring = [[13.39, 52.49], [13.43, 52.49], [13.43, 52.57], [13.39, 52.57], [13.39, 52.49]]
    feature = {"type": "Feature", "properties": {},
               "geometry": {"type": "Polygon", "coordinates": [ring]}}  # fmt: skip
    with sqlite3.connect(db_path) as rw:  # the fixture's own copy, never velometer.sqlite
        path = rw.execute(
            "SELECT path FROM boundaries WHERE city_id='berlin' AND kind='lau'"
        ).fetchone()[0]
        rw.execute(
            "UPDATE boundaries SET source=? WHERE city_id='berlin' AND kind='lau'", (source,)
        )
    rw.close()
    Path(path).write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
    maps.build_map(data, "berlin", "lau", data_dir, maps_dir)
    return json.loads((maps_dir / "berlin_lau.geojson").read_text(encoding="utf-8"))


def test_tier_map_geojson_credits_osm_and_eurogeographics(placed, monkeypatch):  # noqa: F811
    doc = _tier_geojson(placed, monkeypatch, "Eurostat GISCO")
    for uri in OSM_URIS:
        assert uri in doc["attribution"]
    assert GISCO["en"] in doc["attribution"]
    note = doc["boundary_note"]
    assert "`boundary`" in note and "GISCO" in note and "not under ODbL" in note
    assert doc["boundary"] is not None


def test_tier_map_geojson_of_an_osm_boundary_names_no_gisco(placed, monkeypatch):  # noqa: F811
    doc = _tier_geojson(placed, monkeypatch, "OSM relation 62422")
    assert doc["attribution"] == credits.OSM_NOTICE
    assert "boundary_note" not in doc


def test_a_credit_change_redraws_the_tier_maps(monkeypatch):
    before = maps.palette_hash()
    monkeypatch.setattr(credits, "OSM_NOTICE", credits.OSM_NOTICE + " changed")
    assert maps.palette_hash() != before


# --- F2: the EuroGeographics notice ---------------------------------------------------------


def test_boundary_credit_is_the_gisco_wording_in_both_languages():
    assert GISCO["en"] == credits.BOUNDARY_CREDIT
    for lang, text in GISCO.items():
        assert i18n.t(lang, "credit.boundaries") == text
        assert i18n.t(lang, "js.map.boundaries") == text
    assert "für die Verwaltungsgrenzen" not in (ROOT / "content/ui/de.yaml").read_text()


def test_tier_map_adds_the_boundary_credit_beside_the_tile_layer():
    """Ruling P1: the credit is the map's own attribution, independent of the tile layer."""
    js = (ROOT / "src/velometer/app/static/map.js").read_text(encoding="utf-8")
    assert re.search(r'map\.attributionControl\.addAttribution\(t\("js\.map\.boundaries"\)\)', js)


def test_every_exported_page_footer_carries_the_boundary_credit(exported):
    # every full page; a panel fragment (`city/<id>/panel`) is shown inside one
    pages = [p for p in sorted(exported.rglob("*.html")) if p.parent.name != "panel"]
    assert len(pages) > 20
    for page in pages:
        html = page.read_text(encoding="utf-8")
        footer = html[html.index("<footer>") :]
        assert GISCO[_lang(html)] in footer, page


def test_tier_map_page_ships_the_boundary_string(exported):
    for prefix, lang in (("", "en"), ("de/", "de")):
        html = (exported / f"{prefix}city/berlin/tiers/index.html").read_text(encoding="utf-8")
        assert 'id="tiermap-config"' in html
        m = re.search(r'id="ui-strings">(.*?)</script>', html, re.S)
        assert json.loads(m.group(1))["js.map.boundaries"] == GISCO[lang]


def test_tier_map_png_footer_carries_the_boundary_credit(fixture_db):
    point = fixture_db[3].current("berlin", "lau")
    for lang, text in GISCO.items():
        _, footer, _ = maps.map_texts(point, "Berlin", "lau", lang)
        assert text in footer


def test_methodology_credits_gisco_with_its_terms(fixture_db):
    facts = methodology_facts(fixture_db[3])
    en, de = render(facts, "en"), render(facts, "de")
    assert GISCO["en"] in en and GISCO["de"] in de
    assert credits.GISCO_TERMS_URL in en and credits.GISCO_TERMS_URL in de
    assert "commercial" in en and "kommerziell" in de
    for uri in OSM_URIS:
        assert uri in en and uri in de


# --- F3: population credits -----------------------------------------------------------------


def test_population_credit_per_source():
    assert credits.population_credit(GISCO_POP).body == "Eurostat"
    assert credits.population_credit(EUROSTAT_POP).body == "Eurostat"
    fr = credits.population_credit(INSEE)
    assert (fr.body, fr.text, fr.lang) == ("INSEE", "Source : Insee", "fr")
    es = credits.population_credit(INE)
    assert es.body == "INE" and es.lang == "es"
    assert es.text == "Elaboración propia con datos extraídos del sitio web del INE: www.ine.es"
    assert "https://" not in fr.detail + es.detail
    assert credits.population_credit(None) is None
    other = credits.population_credit("Statistik Austria 2025")
    assert other.body == other.text == "Statistik Austria 2025"


def test_csv_population_line_names_each_recorded_source():
    text = csv_preamble("abc", "t", [GISCO_POP, EUROSTAT_POP, INSEE, INE, INE, None])
    pop = next(ln for ln in text.splitlines() if ln.startswith("# Population:"))
    assert "Eurostat (GISCO LAU 2024 POP_2024; demo_r_pjangrp3 FR101 2024)" in pop
    assert "Source : Insee (populations de référence 2023, population municipale)" in pop
    assert (
        pop.count("Elaboración propia con datos extraídos del sitio web del INE: www.ine.es") == 1
    )
    assert "https://" not in pop
    assert (
        "# Per-capita figures are computed by velometer; Eurostat, INSEE and INE bear no "
        "responsibility for them." in text
    )


def test_csv_of_one_city_names_only_its_own_population_source():
    text = csv_preamble("abc", "t", [INSEE])
    pop = next(ln for ln in text.splitlines() if ln.startswith("# Population:"))
    assert (
        pop == "# Population: Source : Insee (populations de référence 2023, population municipale)"
    )
    assert "# Per-capita figures are computed by velometer; INSEE bears no responsibility" in text


def test_csv_without_population_has_no_population_lines():
    text = csv_preamble("abc", "t", [])
    assert "Population" not in text and "Per-capita" not in text
    assert GISCO["en"] in text  # the boundary credit is there all the same


def test_csv_route_reads_the_population_source_of_its_runs(client, fixture_db):  # noqa: F811
    db_path = fixture_db[0]
    with sqlite3.connect(db_path) as rw:  # the fixture's own copy, never velometer.sqlite
        rw.execute("UPDATE runs SET population_source=? WHERE city_id='paris'", (INSEE,))
    rw.close()
    paris = client.get("/data/paris.csv").text
    berlin = client.get("/data/berlin.csv").text
    every = client.get("/data/all.csv").text
    assert "Source : Insee" in paris and "Source : Insee" not in berlin
    assert "Source : Insee" in every


def test_methodology_credits_each_population_source(fixture_db):
    facts = methodology_facts(fixture_db[3])
    sources = {"berlin": GISCO_POP, "paris": INSEE}
    cities = [c.model_copy(update={"population_source": sources[c.id]}) for c in facts.cities]
    facts = facts.model_copy(update={"cities": cities})
    en, de = render(facts, "en"), render(facts, "de")
    assert '<span lang="fr">Source : Insee</span>' in en
    assert '<span lang="fr">Source : Insee</span>' in de
    assert (
        "Per-capita figures are computed by velometer; Eurostat and INSEE bear no "
        "responsibility for them." in en
    )
    assert "Eurostat und INSEE" in de


# --- F4: the counter credit says the index is ours ------------------------------------------


def test_counter_credit_says_index_and_totals_are_computed():
    for lang, tail in COMPUTED.items():
        for key in ("counts.attribution", "js.counts.attribution"):
            text = i18n.t(lang, key, city="C", source="S", licence="L")
            assert text.endswith(tail), (lang, key)
        assert i18n.t(lang, "page.counts.computed") == tail


def test_counts_page_credit_says_index_and_totals_are_computed(exported):
    for prefix, lang in (("", "en"), ("de/", "de")):
        html = (exported / f"{prefix}city/berlin/counts/index.html").read_text(encoding="utf-8")
        m = re.search(r'<p class="meta counts-attribution">(.*?)</p>', html, re.S)
        assert COMPUTED[lang] + "." in m.group(1), lang


# --- F5-F8, F15: ADR 0008 -------------------------------------------------------------------


def test_adr_0008_names_every_source_and_library():
    adr = (ROOT / "docs/adr/0008-licences.md").read_text(encoding="utf-8")
    for needle in (
        "GISCO", GISCO["en"], GISCO["de"], "commercial",  # F2
        "Eurostat", "INSEE", "Source : Insee", "INE", "CC BY 4.0", "Licence Ouverte",  # F3
        "BikeNetKit (Zenodo 22271229) states no licence",  # F5
        "Protomaps", "Produced Work", "ESA WorldCover",  # F6
        "Leaflet", "BSD-2-Clause", "protomaps-leaflet", "BSD-3-Clause",  # F7
        "Martian Mono", "Public Sans", "OFL",  # F8
        "DB-IP",  # F15
    ):  # fmt: skip
        assert needle in adr, needle
    assert "BikeNetKit (Zenodo 22271229) is also ODbL" not in adr
