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


# --- Task 2: the Sources page ---------------------------------------------------------------

FIGURE_SOURCES = [
    "clean_cities_2025", "qecio_v2_10", "bikenetkit_v1", "official", "changing_cities",
    "mobilitaetsagentur_wien",
]  # fmt: skip


def _sources_table(html):
    from tests.test_a11y import _Tables  # the M10 table parser

    p = _Tables()
    p.feed(html)
    (t,) = [t for t in p.tables if "sources" in t["cls"]]
    return t


def _rows(html):
    """(id, inner html) of every row of the sources table that carries an id."""
    table = html.split('<table class="sources', 1)[1].split("</table>", 1)[0]
    return re.findall(r'<tr id="([\w-]+)">(.*?)</tr>', table, re.S)


def test_sources_page_has_ours_then_every_figure_source(client):  # noqa: F811
    html = client.get("/sources").text
    assert 'id="ours"' in html
    for sid in FIGURE_SOURCES:
        assert f'id="src-{sid}' in html, sid  # official has one row per organisation


def test_every_sources_row_has_six_cells_and_stacks(client):  # noqa: F811
    t = _sources_table(client.get("/sources").text)
    assert "stack" in t["cls"] and len(t["heads"]) == 1 + 6 + 2
    body = [r for r in t["rows"] if len(r) > 1]  # the group header rows span the table
    assert body and all(len(r) == len(t["heads"]) for r in body)
    assert all(label for r in body for label, _, tag in r if tag == "td")


def test_every_overview_header_anchor_exists_on_sources(client):  # noqa: F811
    anchors = set(re.findall(r'href="/sources#([\w-]+)"', client.get("/").text))
    page = client.get("/sources").text
    assert anchors and all(f'id="{a}"' in page for a in anchors)


def test_sources_is_in_the_nav_and_the_overview_links_differences(client):  # noqa: F811
    html = client.get("/").text
    assert 'href="/sources"' in html.split("</nav>", 1)[0]
    assert 'href="/differences"' in html.split("<main", 1)[1]


def test_sources_row_ids_are_unique(client):  # noqa: F811
    # a source behind two organisations (official: Berlin, Copenhagen) gets a row each
    ids = re.findall(r'\bid="([^"]+)"', client.get("/sources").text)
    assert len(ids) == len(set(ids))


def test_sources_groups_come_in_order_ours_rankings_cities(client):  # noqa: F811
    html = client.get("/sources").text
    heads = re.findall(r'<th colspan="9" scope="rowgroup"[^>]*>(.*?)</th>', html, re.S)
    assert heads == ["Our approach", "Cross-city rankings and datasets", "City sources"]
    ids = [i for i, _ in _rows(html)]
    assert ids[0] == "ours"
    ranking = {"src-clean_cities_2025", "src-qecio_v2_10", "src-bikenetkit_v1"}
    assert set(ids[1:4]) == ranking and not ranking & set(ids[4:])


def test_rankings_sort_by_title_and_city_sources_by_city_name():
    from velometer.app.sources import order_rows

    class R:
        def __init__(self, group, title, city):
            self.group, self.title, self.city_name = group, title, city

    rows = [R("city", "B", "Zagreb"), R("ranking", "Zeta", None), R("ours", "Our", None),
            R("city", "A", "Athens"), R("ranking", "alpha", None)]  # fmt: skip
    assert [(r.group, r.title) for r in order_rows(rows)] == [
        ("ours", "Our"), ("ranking", "alpha"), ("ranking", "Zeta"), ("city", "A"), ("city", "B"),
    ]  # fmt: skip


def test_every_citation_marker_on_sources_resolves_to_the_list(client):  # noqa: F811
    html = client.get("/sources").text
    table = html.split('<table class="sources', 1)[1].split("</table>", 1)[0]
    marks = re.findall(r'<sup><a href="#([\w-]+)">', table)
    assert marks and all(f'id="{m}"' in html for m in marks)
    assert '<ol class="citations">' in html


def test_ours_row_dates_the_osm_snapshot(client):  # noqa: F811
    (ours,) = [body for i, body in _rows(client.get("/sources").text) if i == "ours"]
    assert re.search(r"OSM snapshot of \d{4}-\d{2}-\d{2}<", ours)


def test_every_cities_link_opens_a_figures_tab_that_quotes_the_source(client):  # noqa: F811
    from velometer.config import default_config_dir, load_differences

    names = load_differences(default_config_dir() / "differences.yaml").source_names
    rows = _rows(client.get("/sources").text)
    linked = 0
    for rid, body in rows:
        if rid == "ours":
            continue
        sid = next(s for s in FIGURE_SOURCES if rid.startswith(f"src-{s}"))
        for city in re.findall(r'href="/city/([\w-]+)/figures"', body):
            linked += 1
            figures = client.get(f"/city/{city}/figures").text
            assert names[sid] in figures, (sid, city)
    assert linked


def test_recomputed_links_point_at_an_overview_column(client):  # noqa: F811
    overview = client.get("/").text
    rows = dict(_rows(client.get("/sources").text))
    for rid in ["ours", "src-qecio_v2_10", "src-clean_cities_2025"]:
        (col,) = re.findall(r'href="/#(col-[\w-]+)"', rows[rid])
        assert f'id="{col}"' in overview, rid
    assert not re.search(r'href="/#col-', rows["src-bikenetkit_v1"])


def test_recomputes_must_name_a_figure_source(tmp_path):
    import pytest

    from velometer.config import ConfigError, default_config_dir, load_report

    cfg = default_config_dir()
    for name in ["presets.yaml", "organisations.yaml"]:
        (tmp_path / name).write_text((cfg / name).read_text(encoding="utf-8"), encoding="utf-8")
    path = tmp_path / "report.yaml"
    body = "report_classifier: v4\nrankings:\n  - {{id: x, label: X, kind: preset, preset: " \
        "ecf_qecio, recomputes: {}}}\n"  # fmt: skip
    path.write_text(body.format("qecio_v2_10"))
    assert load_report(path).rankings[0].recomputes == "qecio_v2_10"
    path.write_text(body.format("no_such_source"))
    with pytest.raises(ConfigError, match="no_such_source"):
        load_report(path)


def test_figures_ours_column_drops_the_preset_suffix(client):  # noqa: F811
    from velometer.config import default_config_dir, load_report

    labels = [
        r.label
        for r in load_report(default_config_dir() / "report.yaml").rankings
        if r.kind == "preset" and r.label.endswith(", our OSM data")
    ]
    html = client.get("/city/berlin/figures").text
    ours = re.findall(r'<td data-label="Ours">(.*?)</td>', html, re.S)
    stems = [lbl.removesuffix(", our OSM data") for lbl in labels]
    preset_cells = [c for c in ours if any(s in c for s in stems)]
    assert preset_cells, "the fixture has a preset row on Berlin's Figures tab"
    assert not any("our OSM data" in c for c in preset_cells)


def test_sources_citations_are_numbered_in_reading_order(client):  # noqa: F811
    html = client.get("/sources").text
    table = html.split('<table class="sources', 1)[1].split("</table>", 1)[0]
    firsts = list(
        dict.fromkeys(int(n) for n in re.findall(r'<sup><a href="#[\w-]+">(\d+)<', table))
    )
    assert firsts and firsts == list(range(1, len(firsts) + 1))
