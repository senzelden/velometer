import csv
import io
import json
import re

from tests.test_app import client, setup  # noqa: F401  (fixtures)

M10_CSV_COLUMNS = [
    "city_id", "boundary_kind", "label", "run_id", "osm_timestamp", "classifier_version",
    "config_sha256", "tier_A_km", "tier_B_km", "tier_C_km", "tier_D_km", "tier_E_km", "ab_km",
    "ours_headline", "ecf_qecio", "clean_cities_2025", "population_value", "population_year",
    "flags",
]  # fmt: skip


def _header(text):
    rows = [r for r in text.splitlines() if not r.startswith("#")]
    return next(csv.reader(io.StringIO(rows[0])))


def test_csv_and_series_ids_are_unchanged(client):  # noqa: F811
    # spec decision 2: only display labels change; scripts keep working
    assert _header(client.get("/data/all.csv").text) == M10_CSV_COLUMNS
    series = client.get("/data/series.json").json()
    assert {"ours_headline", "ecf_qecio", "clean_cities_2025"} <= set(json.dumps(series).split('"'))


def test_no_label_says_ours_colon(client):  # noqa: F811
    html = client.get("/").text
    assert "Ours:" not in html
    assert "our OSM data" in html and "velometer headline" in html


def test_every_preset_and_published_header_links_to_its_sources_row(client):  # noqa: F811
    html = client.get("/").text
    heads = re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)
    linked = [
        h for h in heads if "our OSM data" in h or "velometer headline" in h or "(published)" in h
    ]
    assert len(linked) == 8  # 3 presets in each of two tables, plus 2 published columns
    assert all(re.search(r'href="/sources#(ours|src-[a-z0-9_]+)"', h) for h in linked)


def test_source_anchor_rule():
    from velometer.app.sources import source_anchor

    assert source_anchor(None) == "ours"
    assert source_anchor("qecio_v2_10") == "src-qecio_v2_10"


def test_preset_sources_map_recomputed_figures(client):  # noqa: F811
    from velometer.app.sources import source_anchor

    html = client.get("/").text
    assert 'href="/sources#ours"' in html
    assert f'href="/sources#{source_anchor("qecio_v2_10")}"' in html
    assert f'href="/sources#{source_anchor("clean_cities_2025")}"' in html
