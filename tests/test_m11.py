import csv
import io
import json
import re

from tests.test_app import client, client_21, setup, setup_21  # noqa: F401  (fixtures)
from tests.test_app_base import rich  # noqa: F401  (fixture)

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


def _ids(html):
    """Every element id of a page, parsed (not a substring match: `id="x"` is inside `id="x-y"`
    and `data-id="x"`)."""
    return set(re.findall(r'(?<![\w-])id="([^"]+)"', html))


def _text(fragment):
    return re.sub(r"<[^>]+>", "", fragment).strip()


def test_every_preset_and_published_header_links_to_its_sources_row(client):  # noqa: F811
    # the rule, from the config: each overview column of a ranking links to the Sources row of
    # the source it recomputes (a preset; none means our own approach) or publishes (external)
    from velometer.app.sources import source_anchor
    from velometer.config import default_config_dir, load_report

    rankings = load_report(default_config_dir() / "report.yaml").rankings
    heads = re.findall(r"<th[^>]*>(.*?)</th>", client.get("/").text, re.S)
    rows = _ids(client.get("/sources").text)
    assert rankings
    for r in rankings:
        want = source_anchor(r.recomputes if r.kind == "preset" else r.source)
        # the rankings table adds " (n=<ranked>)" to the label
        cells = [h for h in heads if re.fullmatch(rf"{re.escape(r.label)}( \(n=\d+\))?", _text(h))]
        assert cells, r.id  # every ranking is an overview column
        for h in cells:
            assert f'href="/sources#{want}"' in h, (r.id, h)
        assert want in rows, (r.id, want)


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
    page = _ids(client.get("/sources").text)
    assert anchors and anchors <= page, anchors - page


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
    from velometer.app.sources import source_anchor
    from velometer.config import default_config_dir
    from velometer.content.loader import load_organisation_map

    mapping = load_organisation_map(default_config_dir() / "organisations.yaml")
    ranking = {source_anchor(m.source) for m in mapping if m.city == "*"}
    ids = [i for i, _ in _rows(html)]
    assert ids[0] == "ours" and ranking
    n = len(ranking)
    assert set(ids[1 : 1 + n]) == ranking and not ranking & set(ids[1 + n :])


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
    marks = set(re.findall(r'<sup><a href="#([\w-]+)">', table))
    assert marks and marks <= _ids(html), marks - _ids(html)
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
    assert {c["lang"] for c in cases} == {"en", "de"}  # both editions share the cases (M12)
    for c in cases:
        got = cite_text(CiteFields(**c["fields"]), c["accessed"], c["url"], lang=c["lang"])
        assert got == c["text"], c["name"]


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


CHART_TAG = re.compile(r'<div[^>]+class="[^"]*\bchart\b[^"]*"[^>]*aria-describedby="([^"]+)"[^>]*>')


def _charts(html):
    """(start, end, tag, described id) of every chart container that names its data table."""
    return [(m.start(), m.end(), m.group(0), m.group(1)) for m in CHART_TAG.finditer(html)]


def test_every_chart_and_keynum_has_a_cite(all_page_urls, page_site):  # noqa: F811
    # each chart has its own Cite: after the data table its description names (where
    # download-ui.js looks for it), before the next chart's table
    seen = 0
    for url in all_page_urls:
        html = page_site.html[url]
        charts = _charts(html)
        seen += len(charts)
        tables = [html.find(f'id="{desc}"') for *_, desc in charts]
        assert all(t >= 0 for t in tables), url
        bounds = sorted(tables) + [len(html)]
        for (*_, desc), at in zip(charts, tables, strict=True):
            nxt = next(b for b in bounds if b > at)
            cite = html.find('<details class="cite"', at)
            assert 0 <= cite < nxt, (url, desc)
        if 'class="keynums"' in html:
            block = html.split('class="keynums"', 1)[1].split("</div>\n<nav", 1)[0]
            assert 'class="cite"' in block, url
    assert seen > 5


DOWNLOADABLE = re.compile(
    r'data-chart="(?!sparkline")|data-compare-chart\b|data-story-plot\b|data-plan-item="'
)


def test_every_chart_page_offers_the_download_control(all_page_urls, page_site):  # noqa: F811
    # download-ui.js adds the control after each container its SELECTOR matches; a chart page
    # must load it, and each chart must match it and name a data table that exists (the CSV)
    seen = 0
    for url in all_page_urls:
        html = page_site.html[url]
        charts = _charts(html)
        if not charts:
            continue
        host = html if "<html" in html else page_site.html["/compare"]  # a panel's host page
        assert "/static/js/download-ui.js" in host, url
        ids = _ids(html)
        for _, _, tag, desc in charts:
            seen += 1
            assert DOWNLOADABLE.search(tag), (url, tag)
            assert desc in ids, (url, desc)
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


def test_german_pages_cite_in_german(client):  # noqa: F811
    # M12 spec 4.5: the German template, the German attribution, the /de/ address
    from velometer import i18n

    html = client.get("/de/city/berlin/time").text
    blobs = CITE_DATA.findall(html)
    assert blobs
    for blob in blobs:
        f = json.loads(blob)
        assert f["attribution"] == i18n.t("de", "cite.attribution")
        assert f["path"].startswith("de/city/berlin")
    texts = re.findall(r'<p class="cite-text">(.*?)</p>', html, re.S)
    assert texts and all("[Datensatz]" in x and "OpenStreetMap-Mitwirkende" in x for x in texts)
    assert all("Klassifikator" in x and "[Data set]" not in x for x in texts)
    english = client.get("/city/berlin/time").text
    assert all("[Data set]" in x for x in re.findall(r'<p class="cite-text">(.*?)</p>', english))


def test_figures_rows_each_carry_a_cite(client):  # noqa: F811
    html = client.get("/city/berlin/figures").text
    rows = re.findall(r"<tr[^>]*>.*?</tr>", html.split("<tbody", 1)[1], re.S)
    rows = [r for r in rows if "<td" in r and 'class="note-row"' not in r]
    assert rows and all('class="cite"' in r for r in rows)


def test_no_cite_title_says_built(all_page_urls, page_site):  # noqa: F811
    # ADR 0006: mapped km, never a construction verb
    titles = 0
    for url in all_page_urls:
        for blob in CITE_DATA.findall(page_site.html[url]):
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
    assert set(cfg["cite_runs"]) == {"lau", "fua"}
    assert set(cfg["cite_runs"]["lau"]) >= {"berlin"}
    assert set(cfg["cite_runs"]["lau"]["berlin"]) == {"osm_timestamp", "classifier"}


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
        got = cite.fields_for_cities(rows, c["ids"], c["title"], c["path"], lang=c["lang"])
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
    all_page_urls,  # noqa: F811
    page_site,
):
    # a citation is built from one run (LAU unless it says FUA): its title may name that
    # boundary only. A title naming both, or FUA with the LAU run, cites a run it does not name.
    data = page_site.data  # the run ids of the app that rendered the pages
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
        for blob in CITE_DATA.findall(page_site.html[url]):
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


def test_theme_tokens_cover_both_themes_and_dark_maps_unambiguously(client):  # noqa: F811
    from tests.test_app_m8 import _stylesheet
    from velometer.app.tokens import theme_tokens

    toks = theme_tokens(_stylesheet())
    assert toks["--ink"][0] != toks["--ink"][1]
    # every token lightOf maps, not a prefix subset: a later token must not corrupt the map
    drawable = list(toks)
    seen = {}
    for k in drawable:
        light, dark = toks[k]
        assert seen.setdefault(dark, light) == light, (k, dark)  # Review Focus 2


def test_theme_tokens_parse_both_blocks_and_keep_light_when_dark_is_silent():
    from velometer.app.tokens import theme_tokens

    css = (
        ":root { --a: #111111; --b: #222222; --font: system-ui; }"
        "@media (prefers-color-scheme: dark) { :root { --a: #eeeeee; } }"
    )
    assert theme_tokens(css) == {"--a": ["#111111", "#eeeeee"], "--b": ["#222222", "#222222"]}


def test_every_page_ships_tokens_and_commit(client):  # noqa: F811
    html = client.get("/").text
    assert 'id="theme-tokens"' in html and 'name="velometer-commit"' in html
    assert "download-ui.js" in html


def test_server_csv_guards_formula_cells_and_keeps_numbers():
    from velometer.report.csvexport import SUBAREA_CSV_COLUMNS, csv_table, safe_cell

    for bad in ["=1+1", "+cmd", "@SUM(A1)", "\tx", "\rx", "-cmd|' /C calc'!A0", "-1+1", "--", "- "]:
        assert safe_cell(bad) == "'" + bad, bad
    for ok in ["-3.2", "-1,639.8", "12", "abc", "a=b", "", "2018"]:
        assert safe_cell(ok) == ok, ok
    for mark in ["-", "\u2013", "\u2014", "\u2212"]:  # a lone dash is a no-data mark
        assert safe_cell(mark) == mark, repr(mark)
    row = {c: "" for c in SUBAREA_CSV_COLUMNS} | {
        "name": '=HYPERLINK("http://x")',
        "length_km": "-3.2",
    }
    body = list(csv.DictReader(io.StringIO(csv_table([row], SUBAREA_CSV_COLUMNS))))[0]
    assert body["name"] == '\'=HYPERLINK("http://x")'
    assert body["length_km"] == "-3.2"


# ---- Task 6: permalinks and "Copy link" ----

COPY_LINK = re.compile(r'<button type="button" class="copy-link">Copy link</button>')
PERMALINK_BOX = re.compile(r'<div class="permalink"([^>]*)>')


def test_stateful_pages_render_a_hidden_copy_link_button(client):  # noqa: F811
    for url in ["/city/berlin/tiers", "/city/berlin", "/stories", "/compare"]:
        html = client.get(url).text
        assert len(COPY_LINK.findall(html)) == 1, url
        assert "permalink-ui.js" in html, url


def test_without_javascript_the_copy_link_box_takes_no_space(all_page_urls, page_site):  # noqa: F811
    # the box itself is hidden until permalink-ui.js reveals it: no margin gap without JS
    seen = 0
    for url in all_page_urls:
        for attrs in PERMALINK_BOX.findall(page_site.html[url]):
            seen += 1
            assert re.search(r"(?<![\w-])hidden\b", attrs), (url, attrs)
    assert seen


def test_permalink_js_reveals_the_button_and_copies_through_copytext():
    ui = (STATIC_JS / "permalink-ui.js").read_text(encoding="utf-8")
    assert "copyText" in ui and "currentAddress" in ui and ".copy-link" in ui
    assert "hidden = false" in ui
    for name in ["map.js", "js/story.js", "js/panel.js", "js/compare.js"]:
        src = (STATIC_JS.parent / name).read_text(encoding="utf-8")
        assert "replaceState" in src, name
    for name in ["map.js", "js/story.js", "js/panel.js"]:
        assert "permalink.js" in (STATIC_JS.parent / name).read_text(encoding="utf-8"), name


def test_permalink_code_never_writes_url_values_with_innerhtml():
    for name in ["map.js", "js/story.js", "js/panel.js", "js/compare.js", "js/permalink.js",
                 "js/permalink-ui.js"]:  # fmt: skip
        src = (STATIC_JS.parent / name).read_text(encoding="utf-8")
        assert not re.search(
            r"\.(innerHTML|outerHTML)\s*\+?=|insertAdjacentHTML|document\.write", src
        ), name


# ---- Task 7: search and jump ----


def test_search_index_covers_every_city_country_org_story_and_page(client, fixture_db):  # noqa: F811
    idx = client.get("/data/search.json").json()
    urls = {e["url"] for e in idx}
    for c in fixture_db[3].cities():
        assert f"/city/{c.id}" in urls
    for p in ["/", "/compare", "/cities", "/stories", "/plans", "/organisations", "/sources",
              "/methodology", "/methodology/de", "/differences"]:  # fmt: skip
        assert p in urls, p
    assert all(client.get(u.split("#")[0]).status_code == 200 for u in urls)
    assert {e["kind"] for e in idx} == {"city", "country", "organisation", "story", "page"}
    for e in idx:
        assert set(e) == {"label", "kind", "url", "terms"} and e["url"].startswith("/")


def test_search_index_anchors_exist_on_their_pages(client):  # noqa: F811
    for e in client.get("/data/search.json").json():
        if "#" not in e["url"]:
            continue
        path, anchor = e["url"].split("#")
        assert anchor in _ids(client.get(path).text), e["url"]


def test_search_index_city_entries_carry_name_id_aliases_and_country(client):  # noqa: F811
    idx = {e["url"]: e for e in client.get("/data/search.json").json() if e["kind"] == "city"}
    berlin = idx["/city/berlin"]
    assert berlin["label"] == "Berlin (Germany)"
    assert {"Berlin", "berlin"} <= set(berlin["terms"])


def test_aliases_validate_and_reach_the_index():
    from pathlib import Path

    from velometer.config import load_cities

    cities = load_cities(Path("config/cities.yaml"))
    assert any(c.aliases for c in cities)
    assert all(isinstance(a, str) and a.strip() for c in cities for a in c.aliases)
    by_id = {c.id: c.aliases for c in cities}
    assert by_id["vienna"] == ["Vienna"] and by_id["krakow"] == ["Cracow"]
    assert by_id["copenhagen"] == ["Copenhagen"]
    assert by_id["prague"] == ["Prague"] and by_id["warsaw"] == ["Warsaw"]


def test_a_blank_alias_is_refused():
    import pytest
    from pydantic import ValidationError

    from velometer.config import CityConfig

    with pytest.raises(ValidationError):
        CityConfig(
            id="x", name="X", aliases=[" "], country_iso2="DE", epsg=25832, geofabrik_region="r",
            osm_relation_id=1,
        )  # fmt: skip


def test_the_js_fold_makes_every_real_city_name_ascii():
    # Wrocław, København, Kraków must be typeable on an ASCII keyboard (ł and ø do not decompose)
    import shutil
    import subprocess
    from pathlib import Path

    from velometer.config import load_cities

    names = [c.name for c in load_cities(Path("config/cities.yaml"))]
    script = (
        f"import {{fold}} from {json.dumps((STATIC_JS / 'search.js').resolve().as_uri())};"
        f"console.log(JSON.stringify({json.dumps(names)}.map(fold)));"
    )
    node = shutil.which("node")
    assert node
    out = subprocess.run(
        [node, "--input-type=module", "-e", script], capture_output=True, text=True, check=True
    ).stdout
    folded = json.loads(out)
    assert all(re.fullmatch(r"[a-z0-9 -]+", f) for f in folded), folded
    assert {"wroclaw", "kobenhavn", "krakow"} <= set(folded)


def test_nav_search_is_a_hidden_combobox_with_a_working_fallback_link(client):  # noqa: F811
    html = client.get("/").text
    assert re.search(r'<a class="search-fallback" href="/cities">Find a city</a>', html)
    assert re.search(r'<div class="search" hidden>', html)
    assert 'role="combobox"' in html and 'aria-expanded="false"' in html
    assert 'aria-controls="site-search-list"' in html and 'role="listbox"' in html
    assert re.search(r'<label for="site-search" class="visually-hidden">', html)


def test_search_js_follows_the_rules():
    src = (STATIC_JS / "search.js").read_text(encoding="utf-8")
    assert not re.search(r"\.(innerHTML|outerHTML)\s*\+?=|insertAdjacentHTML", src)
    assert 'url("/data/search.json")' in src or "url('/data/search.json')" in src
    assert "announce" in src and "aria-activedescendant" in src
    assert "https://" not in src


# ---- final review: a FUA figure cites the FUA run ----


def _two_runs(kind_dates):
    """RunRows where a city's LAU and FUA runs differ: {city: {kind: (timestamp, classifier)}}."""
    from velometer.app.cite import RunRows

    return RunRows(
        {
            city: [
                {
                    "boundary_kind": k,
                    "label": "current",
                    "osm_timestamp": ts,
                    "classifier_version": clf,
                    "run_id": i,
                }  # fmt: skip
                for i, (k, (ts, clf)) in enumerate(kinds.items())
            ]
            for city, kinds in kind_dates.items()
        }
    )


TWO_RUNS = {
    "berlin": {"lau": ("2026-10-03T01:00:00Z", "v4"), "fua": ("2026-09-01T01:00:00Z", "v3")},
    "paris": {"lau": ("2026-10-04T01:00:00Z", "v4"), "fua": ("2026-09-02T01:00:00Z", "v3")},
}


def test_multi_city_fields_and_runs_follow_the_boundary_kind():
    from velometer.app.cite import fields_for_cities

    rows = _two_runs(TWO_RUNS)
    fua = fields_for_cities(rows, ["berlin", "paris"], "t", "/compare", kind="fua")
    assert (
        fua.snapshot_note == "OSM snapshots of 2026-09-01 to 2026-09-02" and fua.classifier == "v3"
    )
    lau = fields_for_cities(rows, ["berlin", "paris"], "t", "/compare")
    assert lau.snapshot_note == "OSM snapshots of 2026-10-03 to 2026-10-04"
    assert rows.runs(["berlin"], "fua") == {
        "berlin": {"osm_timestamp": "2026-09-01T01:00:00Z", "classifier": "v3"}
    }


def test_compare_on_the_metro_area_cites_the_fua_runs(client, monkeypatch):  # noqa: F811
    from velometer.app import cite

    monkeypatch.setattr(cite.RunRows, "of", classmethod(lambda cls, data: _two_runs(TWO_RUNS)))
    html = client.get("/compare?c=berlin,paris&b=fua").text
    (blob,) = CITE_DATA.findall(html.split('class="compare-out"', 1)[1])
    f = json.loads(blob)
    assert "FUA" in f["title"]
    assert f["snapshot_note"] == "OSM snapshots of 2026-09-01 to 2026-09-02", f
    assert f["classifier"] == "v3"
    # the browser rebuilds the Cite when the boundary changes: it gets both kinds' runs
    cfg = json.loads(re.search(r'id="compare-config">(.*?)</script>', html, re.S).group(1))
    assert cfg["cite_runs"]["fua"]["berlin"]["osm_timestamp"] == "2026-09-01T01:00:00Z"
    assert cfg["cite_runs"]["lau"]["berlin"]["osm_timestamp"] == "2026-10-03T01:00:00Z"


def test_search_index_logs_the_content_it_leaves_out(fixture_db, tmp_path, caplog):
    import logging
    import shutil
    from pathlib import Path

    from velometer.app.search import search_index

    content = tmp_path / "content"
    shutil.copytree(Path("content"), content)
    broken = sorted((content / "organisations").glob("*.yaml"))[0]
    broken.write_text("id: [not, closed\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="velometer.app.search"):
        idx = search_index(fixture_db[3], fixture_db[1], content)
    assert all(e["url"] != f"/organisations#{broken.stem}" for e in idx)
    logged = [r.getMessage() for r in caplog.records if r.name == "velometer.app.search"]
    assert any(broken.stem in m for m in logged), logged


def test_every_exported_search_url_resolves_to_an_exported_page_and_anchor(rich, tmp_path):  # noqa: F811
    # the static edition under a base: search.js prefixes each url with the base, and the file
    # and the fragment it lands on must be in the export
    from tests.test_app_base import BASE
    from tests.test_export import _export

    out = tmp_path / "site"
    _export(rich, out, BASE)
    idx = json.loads((out / "data" / "search.json").read_text(encoding="utf-8"))
    assert idx and BASE != "/"
    anchors = 0
    for e in idx:
        path, _, anchor = e["url"].partition("#")
        assert path.startswith("/") and not path.startswith(BASE), e["url"]  # the base is added
        page = out / path.strip("/") / "index.html"
        assert page.is_file(), e["url"]
        if anchor:
            anchors += 1
            assert anchor in _ids(page.read_text(encoding="utf-8")), e["url"]
    assert anchors
