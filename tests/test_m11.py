import csv
import io
import json
import re

from tests.test_app import client, client_21, setup, setup_21  # noqa: F401  (fixtures)

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


def test_long_city_lists_fold_into_a_disclosure(client_21, monkeypatch):  # noqa: F811
    import velometer.app.sources as sources

    real = sources.difference_rows

    def many(data, city_id, cfg):  # every fixture city quotes the sources it quotes in berlin
        return real(data, "berlin", cfg)

    monkeypatch.setattr(sources, "difference_rows", many)
    rows = dict(_rows(client_21.get("/sources").text))
    folded = 0
    for rid, body in rows.items():
        cell = body.split('data-label="Cities">', 1)[1].split("</td>", 1)[0]
        links = re.findall(r'href="/city/[\w-]+/figures"', cell)
        if len(links) > 3:
            folded += 1
            m = re.fullmatch(r"<details[^>]*><summary>(\d+) cities</summary>(.*)</details>", cell)
            assert m and int(m.group(1)) == len(links), rid
        else:
            assert "<details" not in cell, rid
    assert folded  # 21 cities: the ranking rows list more than three


def test_short_city_lists_stay_inline(client):  # noqa: F811
    for rid, body in _rows(client.get("/sources").text):
        cell = body.split('data-label="Cities">', 1)[1].split("</td>", 1)[0]
        if 0 < len(re.findall(r'href="/city/', cell)) <= 3:
            assert "<details" not in cell, rid


def test_recomputed_link_text_is_the_overview_column_label(client):  # noqa: F811
    overview = client.get("/").text
    rows = dict(_rows(client.get("/sources").text))
    seen = 0
    for rid, body in rows.items():
        for col, text in re.findall(r'href="/#(col-[\w-]+)">([^<]+)</a>', body):
            (th,) = re.findall(rf'<th[^>]*id="{col}"[^>]*>(.*?)</th>', overview, re.S)
            assert re.sub(r"<[^>]+>", "", th).strip() == text, rid
            seen += 1
    assert seen >= 3


# --- task 3: citation fields and formats -------------------------------------------------------


def test_python_citation_text_matches_the_shared_cases():
    from pathlib import Path

    from velometer.app.cite import CiteFields, cite_text

    shared = json.loads((Path(__file__).parent / "cite_cases.json").read_text(encoding="utf-8"))
    cases = shared["cases"]
    assert len(cases) >= 5
    for c in cases:
        assert cite_text(CiteFields(**c["fields"]), c["accessed"], c["url"]) == c["text"], c["name"]


def test_city_fields_come_from_the_run_and_build(fixture_db):
    from velometer.app.cite import fields_for_city

    data = fixture_db[3]
    f = fields_for_city(data, "berlin", "t", "/city/berlin")
    (row,) = [
        r
        for r in data.csv_rows("berlin")
        if r["boundary_kind"] == "lau" and r["label"] == "current"
    ]
    assert (f.osm_timestamp, f.run_id, f.classifier) == (
        row["osm_timestamp"],
        str(row["run_id"]),
        row["classifier_version"],
    )
    assert f.commit and f.path == "/city/berlin" and "ODbL 1.0" in f.attribution
    assert "built" not in f.title.lower()  # ADR 0006 wording


def test_multi_city_fields_have_a_snapshot_range_and_no_run(fixture_db):
    from velometer.app.cite import cite_text, fields_for_cities

    data = fixture_db[3]
    f = fields_for_cities(data, ["berlin", "paris"], "t", "/compare")
    assert f.run_id is None and f.osm_timestamp is None
    assert f.snapshot_note and f.snapshot_note.startswith("OSM snapshot")
    assert "run " not in cite_text(f)


class _StubData:
    """csv_rows(city) from {city: (timestamp, classifier)}; a city missing from it has no run."""

    def __init__(self, runs):
        self.runs = runs

    def csv_rows(self, city_id):
        if city_id not in self.runs:
            return []
        ts, clf = self.runs[city_id]
        return [
            {"boundary_kind": "lau", "label": "current", "osm_timestamp": ts,
             "classifier_version": clf, "run_id": 1},
        ]  # fmt: skip


def test_multi_city_snapshot_range_singular_and_natural_classifier_order():
    from velometer.app.cite import fields_for_cities

    data = _StubData(
        {
            "a": ("2026-10-05T01:00:00Z", "v10"),
            "b": ("2026-10-03T01:00:00Z", "v9"),
            "c": ("2026-10-04T01:00:00Z", "v9"),
        }
    )
    f = fields_for_cities(data, ["a", "b", "c"], "t", "/compare")
    assert f.snapshot_note == "OSM snapshots of 2026-10-03 to 2026-10-05"
    assert f.classifier == "v9/v10"
    same = fields_for_cities(data, ["b", "b"], "t", "/compare")
    assert same.snapshot_note == "OSM snapshot of 2026-10-03"
    assert same.classifier == "v9"


def test_missing_runs_give_none_never_an_error(fixture_db):
    from velometer.app.cite import fields_for_cities, fields_for_city

    data = _StubData({"a": ("2026-10-05T01:00:00Z", "v4")})
    assert fields_for_city(data, "nowhere", "t", "/x") is None
    assert fields_for_city(data, "a", "t", "/x", kind="fua") is None
    assert fields_for_cities(data, ["nowhere"], "t", "/compare") is None
    skipped = fields_for_cities(data, ["nowhere", "a"], "t", "/compare")
    assert skipped.snapshot_note == "OSM snapshot of 2026-10-05"
    assert fields_for_city(fixture_db[3], "no_such_city", "t", "/x") is None


def test_commit_is_resolved_once_per_process(monkeypatch):
    from velometer.app import cite

    calls = []
    cite._commit.cache_clear()
    monkeypatch.setattr(cite, "git_commit", lambda: calls.append(1) or "0123456789")
    data = _StubData({"a": ("2026-10-05T01:00:00Z", "v4")})
    for _ in range(3):
        cite.fields_for_city(data, "a", "t", "/x")
    cite._commit.cache_clear()
    assert len(calls) == 1


# ---- Task 4: cite this figure in the pages ----

from tests.test_a11y import all_page_urls  # noqa: E402,F401  (fixture)
from tests.test_app import STATIC  # noqa: E402

STATIC_JS = STATIC / "js"
CHART = re.compile(r'<div[^>]+class="[^"]*\bchart\b[^"]*"[^>]*aria-describedby=')
CITE_DATA = re.compile(r'class="cite-data">(.*?)</script>', re.S)


def test_every_chart_and_keynum_has_a_cite(client, all_page_urls):  # noqa: F811
    seen = 0
    for url in all_page_urls:
        html = client.get(url).text
        n_charts = len(CHART.findall(html))
        seen += n_charts
        assert html.count('<details class="cite"') >= n_charts, url
        if 'class="keynums"' in html:
            block = html.split('class="keynums"', 1)[1].split("</div>\n<nav", 1)[0]
            assert 'class="cite"' in block, url
    assert seen > 5


def test_cite_data_is_valid_json_with_the_attribution(client):  # noqa: F811
    html = client.get("/city/berlin/time").text
    blobs = CITE_DATA.findall(html)
    assert blobs
    for blob in blobs:
        f = json.loads(blob)
        assert f["attribution"].startswith("Map data © OpenStreetMap contributors")
        assert f["path"].startswith(
            "city/berlin"
        )  # no base and no leading slash: the browser adds both


def test_figures_rows_each_carry_a_cite(client):  # noqa: F811
    html = client.get("/city/berlin/figures").text
    rows = re.findall(r"<tr[^>]*>.*?</tr>", html.split("<tbody", 1)[1], re.S)
    rows = [r for r in rows if "<td" in r and 'class="note-row"' not in r]
    assert rows and all('class="cite"' in r for r in rows)


def test_no_cite_title_says_built(client, all_page_urls):  # noqa: F811
    # ADR 0006: mapped km, never a construction verb
    titles = 0
    for url in all_page_urls:
        for blob in CITE_DATA.findall(client.get(url).text):
            title = json.loads(blob)["title"]
            titles += 1
            assert not re.search(r"\bbuil[dt]|construct", title, re.I), (url, title)
    assert titles > 10


def test_a_city_without_a_run_gets_no_cite_and_no_error(client, monkeypatch):  # noqa: F811
    from velometer.app import cite

    monkeypatch.setattr(cite, "_current_row_of_kind", lambda *a, **k: None)
    for url in ("/city/berlin/time", "/", "/compare", "/city/berlin/figures"):
        r = client.get(url)
        assert r.status_code == 200, url
        assert '<details class="cite"' not in r.text, url


def test_compare_carries_the_per_city_runs_for_its_citation(client):  # noqa: F811
    html = client.get("/compare?c=berlin").text
    cfg = json.loads(re.search(r'id="compare-config">(.*?)</script>', html, re.S).group(1))
    assert set(cfg["cite_runs"]) >= {"berlin"}
    assert set(cfg["cite_runs"]["berlin"]) == {"osm_timestamp", "classifier"}


def test_multi_fields_agree_with_the_shared_cases(monkeypatch):
    # the same cases tests multiFields in cite.test.mjs: one rule in Python and JS
    from dataclasses import asdict
    from pathlib import Path

    from velometer.app import cite

    multi = json.loads((Path(__file__).parent / "cite_cases.json").read_text("utf-8"))["multi"]
    assert len(multi) >= 3
    for c in multi:
        monkeypatch.setattr(cite, "_commit", lambda c=c: c["commit"])
        rows = cite.RunRows(
            {
                city: [
                    {
                        "boundary_kind": "lau",
                        "label": "current",
                        "osm_timestamp": r["osm_timestamp"],
                        "classifier_version": r["classifier"],
                        "run_id": r["run_id"],
                    }
                ]
                for city, r in c["runs"].items()
            }
        )
        got = cite.fields_for_cities(rows, c["ids"], c["title"], c["path"])
        assert (None if got is None else asdict(got)) == c["expected"], c["name"]


def test_run_rows_runs_give_the_lau_timestamp_and_classifier():
    from velometer.app.cite import RunRows

    def row(kind, ts, clf):
        return {"boundary_kind": kind, "label": "current", "osm_timestamp": ts,
                "classifier_version": clf, "run_id": 1}  # fmt: skip

    rows = RunRows(
        {
            "a": [
                row("fua", "2026-01-01T00:00:00Z", "v1"),
                row("lau", "2026-10-03T01:00:00Z", "v4"),
            ],
            "b": [row("fua", "2026-01-01T00:00:00Z", "v1")],
        }
    )
    assert rows.runs(["a", "b", "nowhere"]) == {
        "a": {"osm_timestamp": "2026-10-03T01:00:00Z", "classifier": "v4"}
    }


def test_the_keynums_cite_is_titled_for_the_run_it_cites(client):  # noqa: F811
    # it cites the LAU run only, so its title must not claim the metro area
    html = client.get("/city/berlin").text
    block = re.split(r'<nav class="tabs"', html.split('class="keynums"', 1)[1])[0]
    (blob,) = CITE_DATA.findall(block)
    title = json.loads(blob)["title"]
    assert "LAU" in title and "FUA" not in title


def test_cite_pre_blocks_are_not_scroll_regions():
    js = (STATIC_JS / "cite-ui.js").read_text(encoding="utf-8")
    assert "scroll" not in js


def test_a_cite_names_only_the_boundary_whose_run_it_cites(
    client,  # noqa: F811
    all_page_urls,  # noqa: F811
    fixture_db,
):
    # a citation is built from one run (LAU unless it says FUA): its title may name that
    # boundary only. A title naming both, or FUA with the LAU run, cites a run it does not name.
    data = fixture_db[3]
    runs = {
        (c.id, k): next(
            str(r["run_id"])
            for r in data.csv_rows(c.id)
            if r["boundary_kind"] == k and r["label"] == "current"
        )
        for c in data.cities()
        for k in ("lau", "fua")
        if any(r["boundary_kind"] == k and r["label"] == "current" for r in data.csv_rows(c.id))
    }
    seen_fua = 0
    for url in all_page_urls:
        for blob in CITE_DATA.findall(client.get(url).text):
            f = json.loads(blob)
            title = f["title"]
            names_lau, names_fua = "LAU" in title, bool(re.search(r"\bFUA\b", title))
            assert not (names_lau and names_fua), (url, title)
            if names_fua and f["run_id"] is not None:
                seen_fua += 1
                city = next(c for (c, k), rid in runs.items() if k == "fua" and rid == f["run_id"])
                assert f["run_id"] == runs[(city, "fua")] and f["run_id"] != runs.get(
                    (city, "lau")
                ), (url, title)
    assert seen_fua
