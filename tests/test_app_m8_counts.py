"""M8 Task 10: the Counts tab and the counter index in Compare (spec §5.5)."""

import json
import re
import shutil
import sqlite3
import subprocess
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import pytest
import yaml

from tests.test_app import (  # noqa: F401 - `setup` is a fixture
    CONTENT,
    _client,
    _css_rules,
    _css_tokens,
    _resolve,
    _text,
    nolabels,
    setup,
)
from tests.test_app_m7 import CSP, INLINE_CODE, INLINE_SCRIPT, STATIC
from velometer.app import compare
from velometer.app.counts import (
    COVID_YEAR,
    KM_SHORT,
    SERIES_SHORT,
    data_gaps,
    step_down_note,
)
from velometer.app.main import create_app
from velometer.counters import index as counter_index
from velometer.counters.model import INDEX_METHOD, CounterEntry, DayCount, StepDown
from velometer.db import (
    CounterDay,
    CounterIndexYear,
    CounterSite,
    replace_counter_daily,
    replace_counter_index,
    replace_counter_sites,
)

URL = "https://example.org/counters.csv"
ROOT = Path(__file__).parents[1]


def _site(city, sid, lat=52.5, lon=13.4):
    return CounterSite(city, sid, f"Site {sid}", lat, lon, "Senate", "dl-de-zero-2.0", URL,
                       "2026-10-07T13:12:12Z", "2019-01-01", "2025-12-31")  # fmt: skip


def _index(city, values: dict, base=2019, series="counts", method=INDEX_METHOD):
    return [CounterIndexYear(city, y, v, 0 if v is None else 4, base, series, method)
            for y, v in values.items()]  # fmt: skip


def _seed(db_path, city="berlin", index=None, sites=None, days=(), base=2019, series="counts"):
    conn = sqlite3.connect(db_path)
    try:
        replace_counter_sites(
            conn, city, sites or [_site(city, "s1"), _site(city, "s2", None, None)]
        )
        replace_counter_daily(conn, city, list(days))
        values = index or {2018: 101.3, 2019: 100.0, 2020: 114.6, 2021: None, 2022: 102.0}
        replace_counter_index(conn, city, _index(city, values, base, series))
    finally:
        conn.close()


def _app(setup):  # noqa: F811
    db_path, cfg, maps, docs = setup
    return create_app(db_path, cfg, maps, docs, content_dir=CONTENT)


@pytest.fixture
def client(setup):  # noqa: F811
    _seed(setup[0])
    with _client(_app(setup)) as c:
        yield c


# ---------- the tab ----------


def test_counts_tab_only_for_a_counter_city(client):
    berlin = client.get("/city/berlin")
    assert 'href="/city/berlin/counts"' in berlin.text
    paris = client.get("/city/paris")
    assert "/counts" not in paris.text
    assert client.get("/city/paris/counts").status_code == 404
    assert client.get("/city/nowhere/counts").status_code == 404


def test_counts_tab_renders_with_the_csp_and_no_inline_code(client):
    r = client.get("/city/berlin/counts")
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == CSP
    assert not INLINE_SCRIPT.search(r.text)
    assert not INLINE_CODE.search(r.text)
    ids = re.findall(r'\bid="([^"]+)"', r.text)
    assert len(ids) == len(set(ids))


def test_counts_tab_has_the_chart_table_attribution_and_the_counters_text(client):
    html = nolabels(client.get("/city/berlin/counts").text)
    text = _text(html)
    assert 'data-chart="city-counts"' in html
    assert "Index of counts recorded at counter sites, 2019 = 100" in text
    assert "cycling in Berlin" not in text
    # attribution: publisher (linked to its page), licence (linked), retrieval date
    doc = yaml.safe_load((ROOT / "config" / "counters.yaml").read_text(encoding="utf-8"))
    entry = next(e for e in doc["cities"] if e["city"] == "berlin")
    attribution = html[html.index("counts-attribution") :]
    attribution = attribution[: attribution.index("</p>")]
    assert entry["source"] in attribution and entry["licence"] in attribution
    assert f'href="{entry["licence_url"]}"' in attribution
    assert f'href="{entry["page"]}"' in attribution
    assert "retrieved 2026-10-07" in attribution
    # the stored index per year, a None year as n/a (not 0), the COVID year marked
    row = re.search(r"<tr class=\"covid\"><th scope=\"row\">2020 <span[^>]*>COVID year", html)
    assert row, "2020 row marked as the COVID year"
    assert re.search(r"<th scope=\"row\">2021</th><td class=\"num\">n/a</td>", html)
    # content/counters.yaml rendered below, with its sources
    assert "What the counters record" in text
    assert 'id="counters-breaks"' in html
    assert "<h3>Sources</h3>" in html


def test_site_map_for_sites_with_coordinates_and_a_list_for_all(client):
    html = client.get("/city/berlin/counts").text
    cfg = json.loads(re.search(r'id="countermap-config">(.*?)</script>', html, re.S).group(1))
    assert [s["name"] for s in cfg["sites"]] == ["Site s1"]  # s2 has no coordinates
    assert cfg["tiles"].startswith("https://tile.openstreetmap.org/")
    assert '<script type="module" src="/static/countermap.js"></script>' in html
    assert "Site s2" in _text(html)  # in the site list


def test_sites_without_coordinates_get_a_list_and_no_map(setup):  # noqa: F811
    _seed(setup[0], sites=[_site("berlin", "v1", None, None)])
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
    assert "countermap" not in html
    assert "no coordinates for these sites" in _text(html)
    assert '<details class="table-details" open>' in html


def test_barcelona_style_series_is_labelled_average_daily_intensity(setup):  # noqa: F811
    _seed(setup[0], series="avg_daily_intensity")
    with _client(_app(setup)) as c:
        text = _text(c.get("/city/berlin/counts").text)
        payload = c.get("/data/series.json").json()
    assert "Index of average daily intensity recorded at counter sites" in text
    assert payload["counters"]["cities"]["berlin"]["series"] == "avg_daily_intensity"


def test_km_index_is_rebased_to_the_counter_base_year(setup):  # noqa: F811
    _seed(setup[0], index={2024: 100.0, 2025: 120.0}, base=2024)
    with _client(_app(setup)) as c:
        html = nolabels(c.get("/city/berlin/counts").text)
    # the fixture's A+B km on 1 January 2024 is the km index's 100
    assert re.search(r"<th scope=\"row\">2024</th><td class=\"num\">100.0</td><td class=\"num\">"
                     r"4</td><td class=\"num\">100.0</td>", html)  # fmt: skip
    assert "no mapped-km index" not in html


def test_index_with_one_year_has_no_line_and_names_the_gap(setup):  # noqa: F811
    days = [CounterDay("berlin", "s1", d, 10, True) for d in ("2021-06-30", "2022-09-01")]
    _seed(setup[0], index={2019: None, 2020: 100.0, 2021: None}, base=2020, days=days)
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
        payload = c.get("/data/series.json").json()
    assert 'data-chart="city-counts"' not in html
    note = _text(html[html.index('id="counts-no-line"') :].split("</p>")[0])
    assert "value for 2020 only" in note
    assert "no counts from 2021-07-01 to 2022-08-31" in note
    assert payload["counters"]["cities"]["berlin"]["line"] is False


# ---------- step-down note (Helsinki ruling) ----------


def _year(site, y, count, n=365):
    start = date(y, 1, 1)
    return [DayCount(site, start + timedelta(days=i), count, True) for i in range(n)]


def test_step_down_note_computes_the_index_without_the_sites_from_their_year_on():
    # three steady sites and one that halves in 2021: stored 2021 = (10+10+10+5)/(40) = 87.5
    days = [d for s in ("a", "b", "c") for y in (2019, 2020, 2021) for d in _year(s, y, 10)]
    days += _year("x", 2019, 10) + _year("x", 2020, 10) + _year("x", 2021, 5)
    entry = CounterEntry(city="t", adapter="t", source="s", licence="l", licence_url="u", page="p",
                         urls=["u"], timezone="UTC", grain="daily",
                         step_downs=[StepDown(site="x", since="2021-04"),
                                     StepDown(site="gone", since="2020-01")])  # fmt: skip
    note = step_down_note(entry, days, {2021: 87.5}, 2019)
    assert note["sites"] == [{"site": "x", "since": "April 2021"}]  # an unknown site is dropped
    assert note["years"] == [{"year": 2021, "idx": 100.0, "sites": 3, "stored": 87.5}]


def test_helsinki_entry_lists_the_ruled_step_down_sites():
    cfg = yaml.safe_load((ROOT / "config" / "counters.yaml").read_text(encoding="utf-8"))
    helsinki = next(e for e in cfg["cities"] if e["city"] == "helsinki")
    assert {s["site"]: str(s["since"]) for s in helsinki["step_downs"]} == {
        "Kaivokatu": "2024-04",
        "Pitkäsilta länsipuoli": "2025-05",
    }


def test_counts_tab_shows_the_computed_step_down_index(setup):  # noqa: F811
    db_path, cfg_dir, _, _ = setup
    doc = yaml.safe_load((cfg_dir / "counters.yaml").read_text())
    entry = next(e for e in doc["cities"] if e["city"] == "berlin")
    entry["step_downs"] = [{"site": "x", "since": "2021-04"}]
    (cfg_dir / "counters.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True))
    days = [CounterDay("berlin", d.site_id, d.day.isoformat(), d.count, True)
            for s in ("a", "b", "c") for y in (2020, 2021) for d in _year(s, y, 10)]  # fmt: skip
    days += [CounterDay("berlin", "x", d.day.isoformat(), d.count, True)
             for d in _year("x", 2020, 10) + _year("x", 2021, 5)]  # fmt: skip
    _seed(db_path, index={2020: 100.0, 2021: 87.5}, base=2020, days=days)
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
    note = _text(html[html.index('id="counts-step-down"') :].split("</p>")[0])
    assert "In our reading of the daily counts" in note
    assert "the counts of x (from April 2021) step down" in note
    assert "the index is 100.0 in 2021 (3 sites; above: 87.5)" in note
    assert "config/counters.yaml" in note


def test_data_gaps_name_runs_longer_than_a_month_only():
    d = [DayCount("a", date(2021, 1, 1), 1, True), DayCount("a", date(2021, 1, 20), 1, True),
         DayCount("a", date(2021, 6, 1), 1, True)]  # fmt: skip
    assert data_gaps(d) == [("2021-01-21", "2021-05-31")]


# ---------- series.json and Compare ----------


def test_series_json_carries_the_counter_index_with_gaps_as_null(client):
    payload = client.get("/data/series.json").json()
    c = payload["counters"]
    assert c["covid_year"] == COVID_YEAR == 2020
    assert set(c["cities"]) == {"berlin"}
    by_year = {p["year"]: p["idx"] for p in c["cities"]["berlin"]["points"]}
    assert by_year[2021] is None and by_year[2020] == 114.6
    assert c["cities"]["berlin"]["line"] is True


def test_compare_parses_counter_index():
    s = compare.parse_compare("m=counter_index&b=fua", ["berlin"], compare.METRICS)
    assert (s.m, s.b) == ("counter_index", "fua")


def test_counter_lines_gap_is_none_and_cities_without_data_are_notes():
    payload = {
        "cities": {"a": {"name": "A"}, "m": {"name": "M"}, "n": {"name": "N"}},
        "counters": {"covid_year": 2020, "cities": {
            "a": {"series": "counts", "base_year": 2019, "line": True, "points": [
                {"year": 2018, "idx": 90.0}, {"year": 2019, "idx": 100.0},
                {"year": 2020, "idx": None}, {"year": 2021, "idx": 0.0}]},
            "m": {"series": "counts", "base_year": 2020, "line": False,
                  "points": [{"year": 2020, "idx": 100.0}]},
        }},
    }  # fmt: skip
    labels, values, notes = compare.counter_lines(payload, ["a", "m", "n"])
    assert labels == ["2018", "2019", "2020", "2021"]
    assert values == {"a": [90.0, 100.0, None, 0.0], "m": [None] * 4, "n": [None] * 4}
    assert notes == [
        f"M: {compare.NO_COUNTER_LINE}",
        f"N: {compare.NO_COUNTERS}",
        "Counter data, A: source not recorded, licence not recorded",
    ]


def test_compare_table_without_js_shows_the_counter_index(client):
    r = client.get("/compare?c=berlin,paris&m=counter_index&mode=index")
    assert r.status_code == 200
    text = _text(r.text)
    assert "Counter index · counter sites" in text
    assert "Paris: no open counter data" in text
    head = r.text[r.text.index("<thead>", r.text.index("compare-table")) :]
    head = head[: head.index("</thead>")]
    assert re.findall(r'class="num">([^<]+)</th>', head) == [
        "2018", "2019", "2020 (COVID year)", "2021", "2022",
    ]  # fmt: skip
    # not rebased in index mode; 2021 is a gap
    page = nolabels(r.text)
    body = page[page.index("<tbody>", page.index('class="compare-table stack"')) :]
    row = body[body.index('<a href="/city/berlin">') :]
    row = row[: row.index("</tr>")]
    assert re.findall(r'<td class="num">([^<]+)', row) == [
        "101.3",
        "100.0",
        "114.6",
        "n/a",
        "102.0",
    ]


def test_compare_counter_index_names_the_publisher_and_licence_of_every_drawn_city(setup):  # noqa: F811
    # ADR 0008 (M8 note): every page that shows the counter data carries an attribution line
    db_path = setup[0]
    _seed(db_path)
    _seed(db_path, "paris", sites=[_site("paris", "p1", 48.86, 2.35)])
    doc = yaml.safe_load((ROOT / "config" / "counters.yaml").read_text(encoding="utf-8"))
    entries = {e["city"]: e for e in doc["cities"]}
    with _client(_app(setup)) as c:
        payload = c.get("/data/series.json").json()
        text = _text(c.get("/compare?c=berlin,paris&m=counter_index").text)
    drawn = [i for i, v in payload["counters"]["cities"].items() if v["line"]]
    assert sorted(drawn) == ["berlin", "paris"]
    for city in drawn:
        entry = entries[city]
        got = payload["counters"]["cities"][city]
        assert (got["source"], got["licence"]) == (entry["source"], entry["licence"])
        name = payload["cities"][city]["name"]
        line = f"Counter data, {name}: {entry['source']}, licence {entry['licence']}"
        assert line in text, line
    # a city whose index is not drawn (one year only) shows no data, so no attribution
    _seed(db_path, "paris", index={2019: 100.0}, sites=[_site("paris", "p1", 48.86, 2.35)])
    with _client(_app(setup)) as c:
        text = _text(c.get("/compare?c=berlin,paris&m=counter_index").text)
    assert f"Counter data, {payload['cities']['berlin']['name']}:" in text
    assert f"Counter data, {payload['cities']['paris']['name']}:" not in text


def test_counter_lines_attribution_falls_back_to_unrecorded():
    payload = {
        "cities": {"a": {"name": "A"}},
        "counters": {"cities": {"a": {"series": "counts", "base_year": 2019, "line": True,
                                      "points": [{"year": 2019, "idx": 100.0},
                                                 {"year": 2020, "idx": 99.0}]}}},
    }  # fmt: skip
    _, _, notes = compare.counter_lines(payload, ["a"])
    assert notes == ["Counter data, A: source not recorded, licence not recorded"]


COUNTER_CASES = json.loads((ROOT / "tests" / "counter_cases.json").read_text(encoding="utf-8"))
COUNTER_JS = (ROOT / "src/velometer/app/static/js/counter-model.js").as_uri()
COMPARE_JS = (ROOT / "src/velometer/app/static/js/compare-model.js").as_uri()


def _node(script: str):
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _case_payload(case: dict) -> dict:
    """The shared payload with the case's `counters` keys in place of the payload's."""
    payload = COUNTER_CASES["payload"]
    return {**payload, "counters": {**payload["counters"], **case.get("counters", {})}}


@pytest.mark.parametrize("case", COUNTER_CASES["cases"], ids=lambda c: c["name"])
def test_counter_lines_and_unit_match_the_shared_cases(case):
    # counter-model.test.mjs runs counterLines over the same cases
    payload = _case_payload(case)
    labels, values, notes = compare.counter_lines(payload, case["ids"])
    unit = compare.counter_unit(payload, case["ids"])
    assert {"labels": labels, "values": values, "notes": notes, "unit": unit} == case["expect"]


STRINGS_JS = (ROOT / "src/velometer/app/static/js/strings.js").as_uri()
JS_STRINGS = (ROOT / "tests" / "ui_js_strings.json").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to run counter-model.js")
@pytest.mark.parametrize("lang", ["en", "de"])
def test_js_counter_title_footnote_unit_and_notes_equal_the_python_ones(lang):
    # the no-JS page and compare.js show the same title, footnote, unit and notes, in the page's
    # language: the JS reads the `js.counts.*` strings of tests/ui_js_strings.json, as a page does
    cases = [(_case_payload(c), c["ids"]) for c in COUNTER_CASES["cases"]]
    script = (
        f"Promise.all([import('{STRINGS_JS}'), import('{COUNTER_JS}'), import('{COMPARE_JS}')])"
        f".then(([s, c, m]) => {{ const S = {JS_STRINGS}; s.setStrings(S['{lang}'], S.en); "
        f"console.log(JSON.stringify({{"
        f"lines: {json.dumps(cases)}.map(([payload, ids]) => {{ const r = c.counterLines("
        f"payload, ids); return [r.notes, r.unit]; }}), "
        f"title: c.counterTitle('Counter index'), "
        f"foot: ['counter_index', 'headline', 'ab_km'].map(k => m.footnote(k, 'HU'))}})) }})"
    )
    js = _node(script)
    assert js["lines"] == [
        [compare.counter_lines(payload, ids, lang)[2], compare.counter_unit(payload, ids, lang)]
        for payload, ids in cases
    ]
    assert js["title"] == compare.counter_title("Counter index", lang)
    feet = [compare.footnote(k, "HU", lang) for k in ("counter_index", "headline", "ab_km")]
    assert js["foot"] == feet


def _foot(html: str) -> str:
    tag = "data-compare-foot>"
    return unescape(_text(html[html.index(tag) + len(tag) :].split("</p>")[0]))


def test_compare_footnote_is_metric_aware(client):
    # the headline footnote (flag mark, headline unit) is about the mapped-km metrics; the
    # counter index has no flagged years and is not the headline: its own footnote
    counter = _foot(client.get("/compare?c=berlin&m=counter_index").text)
    assert "flagged year" not in counter and "Headline:" not in counter
    assert counter == compare.COUNTER_FOOT
    assert "base year = 100" in counter and "recorded at counter sites" in counter
    for m in ("headline", "ab_km"):
        foot = _foot(client.get(f"/compare?c=berlin&m={m}").text)
        assert "flagged year" in foot and "Headline:" in foot, m


def test_compare_counter_unit_names_the_base_year_of_each_drawn_city(setup):  # noqa: F811
    # the unit's "<year> = 100" comes from the drawn cities' base years, not a constant
    db_path = setup[0]
    _seed(db_path)  # base 2019
    _seed(db_path, "paris", index={2020: 100.0, 2021: 104.0}, base=2020,
          sites=[_site("paris", "p1", 48.86, 2.35)])  # fmt: skip
    with _client(_app(setup)) as c:
        berlin = _text(c.get("/compare?c=berlin&m=counter_index").text)
        paris = _text(c.get("/compare?c=paris&m=counter_index").text)
        both = _text(c.get("/compare?c=berlin,paris&m=counter_index").text)
    assert "counter sites (or of their average daily intensity), 2019 = 100;" in berlin
    assert "2020 = 100" not in berlin
    assert "counter sites (or of their average daily intensity), 2020 = 100;" in paris
    assert "2019 = 100" not in paris
    assert "2019 = 100 (2020 = 100 for Paris);" in both


# ---------- cities without open counter data (spec §5.1) ----------


def test_city_without_counter_data_shows_the_portals_checked_on_figures_and_compare(setup):  # noqa: F811
    db_path, cfg_dir, _, _ = setup
    _seed(db_path)
    doc = yaml.safe_load((cfg_dir / "counters.yaml").read_text(encoding="utf-8"))
    listed = next(n for n in doc["none"] if n.get("note"))  # a real entry, moved to paris
    doc["cities"] = [e for e in doc["cities"] if e["city"] != "paris"]
    doc["none"] = [n for n in doc["none"] if n is not listed] + [{**listed, "city": "paris"}]
    (cfg_dir / "counters.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True))
    with _client(_app(setup)) as c:
        figures = _text(c.get("/city/paris/figures").text)
        berlin = c.get("/city/berlin/figures").text
        compare_page = _text(c.get("/compare?c=berlin,paris&m=counter_index").text)
        payload = c.get("/data/series.json").json()
    checked = ", ".join(listed["checked"])
    assert f"No open counter data found (portals checked: {checked}; {listed['note']})." in figures
    assert 'id="counter-data"' not in berlin  # a counter city has its Counts tab instead
    note = f"Paris: no open counter data found (portals checked: {checked}; {listed['note']})"
    assert note in compare_page
    assert payload["counters"]["none"]["paris"].startswith("no open counter data found")


def test_compare_summary_for_the_counter_index_names_counter_sites_and_no_mode(client):
    html = client.get("/compare?c=berlin,paris&m=counter_index&b=fua&mode=index").text
    summary = re.search(r"data-filters-summary>([^<]*)<", html).group(1)
    assert summary == "Counter index · counter sites · 2 cities"


def test_counts_chart_key_names_the_short_end_labels_in_full(setup):  # noqa: F811
    # the chart's end labels are short at most widths ("Counts", "Mapped km"; counter-model.js):
    # the key under the chart gives each line its full name, in the line's colour. Base 2024:
    # the fixture has A+B km on 1 January 2024, so both lines are drawn
    _seed(setup[0], index={2024: 100.0, 2025: 120.0}, base=2024)
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
    key = _chart_key(html)
    text = _text(key)
    assert "Counts: index of counts recorded at counter sites" in text
    assert "Mapped km: index of A+B mapped km in the city proper, 1 January snapshots" in text
    assert 'class="key key-counter"' in key and 'class="key key-km"' in key

    css = (STATIC / "app.css").read_text()
    rules = _css_rules(css)
    # the chart draws the counter index in series slot 0 and the km index in slot 1 (city.js),
    # which theme.js resolves to --series-1 and --series-2
    city_js = (STATIC / "js" / "city.js").read_text()
    assert "series: model.series.map((s, i) => ({ ...s, slot: i }))" in city_js
    # the swatch is a 3 px top border on a box of no height: its visible colour is the
    # border-top colour the cascade gives a `.key.key-counter` inside `.chart-key`
    tokens = _css_tokens(css)
    first, second = tokens["--series-1"], tokens["--series-2"]
    assert _resolve(_key_line_colour(rules, "key-counter"), tokens) == first
    assert _resolve(_key_line_colour(rules, "key-km"), tokens) == second


def _chart_key(html: str) -> str:
    """The Counts tab's chart key: a list, one item per line of the chart."""
    start = html.index('class="meta chart-key"')
    return html[start : html.index("</ul>", start)]


def test_counts_chart_key_items_are_list_items_without_a_typed_separator(setup):  # noqa: F811
    # render check: at 390 px the key wrapped after " · ", starting its second line with "·".
    # Items in a list wrap whole; the spacing between them is the stylesheet's
    _seed(setup[0], index={2024: 100.0, 2025: 120.0}, base=2024)
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
    key = _chart_key(html)
    assert re.search(r'<ul class="meta chart-key"', html)
    items = re.findall(r"<li\b[^>]*>(.*?)</li>", key, re.S)
    assert len(items) == 2
    assert "·" not in re.sub(r"<li\b[^>]*>.*?</li>", "", key, flags=re.S)
    assert all(
        not _text(i).strip().startswith("·") and not _text(i).strip().endswith("·") for i in items
    )


@pytest.mark.parametrize(
    ("series", "short"), [("counts", "Counts"), ("avg_daily_intensity", "Intensity")]
)
def test_counter_short_names_come_from_one_place(setup, series, short):  # noqa: F811
    # the chart's end labels (city.js) and the key under it name the lines alike: the server
    # puts the short names on the chart mount and city.js reads them, typing none of its own

    _seed(setup[0], index={2024: 100.0, 2025: 120.0}, base=2024, series=series)
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
    mount = re.search(r'<div class="chart" data-chart="city-counts"[^>]*>', html).group(0)
    assert f'data-counter-short="{SERIES_SHORT[series]}"' in mount and SERIES_SHORT[series] == short
    assert f'data-km-short="{KM_SHORT}"' in mount
    key = _text(_chart_key(html))
    assert f"{SERIES_SHORT[series]}: index of" in key and f"{KM_SHORT}: index of" in key
    js = (ROOT / "src" / "velometer" / "app" / "static" / "js" / "city.js").read_text()
    for name in (*SERIES_SHORT.values(), KM_SHORT):
        assert f'"{name}"' not in js, f"city.js types {name!r}"
    assert "dataset.counterShort" in js and "dataset.kmShort" in js


def _key_line_colour(rules, cls: str) -> str:
    """The border-top colour of `<p class="chart-key"><span class="key {cls}">`: the matching
    rule of highest specificity wins, a later one on ties; a shorthand without a colour resets
    it to currentColor."""
    matching = {".key", f".{cls}", ".chart-key .key", f".chart-key .{cls}", f".key.{cls}"}
    best = (-1, "currentColor")
    for sels, decls in rules:
        for sel in (s for s in sels if s in matching):
            for prop, value in decls.items():
                if prop in ("border", "border-top"):
                    found = re.findall(r"#[0-9a-f]{3,6}\b|var\(--[\w-]+\)", value)
                    colour = found[0] if found else "currentColor"
                elif prop in ("border-color", "border-top-color"):
                    colour = value
                else:
                    continue
                if sel.count(".") >= best[0]:
                    best = (sel.count("."), colour)
    return best[1]


def test_counts_chart_key_for_average_daily_intensity(setup):  # noqa: F811
    _seed(setup[0], series="avg_daily_intensity")
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
    key = _text(_chart_key(html))
    assert "Intensity: index of average daily intensity recorded at counter sites" in key
    # no km for the base year (2019 is before the fixture's snapshots): no km line, no km key
    assert "Mapped km" not in key


def test_counts_tables_fit_a_phone_width():
    # Task 11 render check: at 390 px the counts table (four columns, headers kept on one line)
    # was 626 px wide in a 358 px column, and a site name like "Hesperian puisto/Ooppera"
    # pushed the sites table past it. At phone width the headers wrap and site names break

    css = (STATIC / "app.css").read_text()
    start = css.index("/* counts tables at phone width */")
    block = css[start : css.index("\n}\n", start)]
    assert "@media (max-width: 600px)" in block
    rules = _css_rules(block.split("{", 1)[1])
    decl: dict[str, dict] = {}
    for sels, d in rules:
        for s in sels:
            decl.setdefault(s, {}).update(d)
    assert decl[".counts-table th"]["white-space"] == "normal"
    assert decl[".counter-sites td"]["overflow-wrap"] == "anywhere"
    assert decl[".counts-table .covid-mark"]["white-space"] == "nowrap"  # "COVID year" stays whole


# ---------- an unreadable config/counters.yaml (M8 follow-ups, Task 2) ----------


def _page_text(html: str) -> str:
    """The page's text without its scripts: every page carries the JS strings (`#ui-strings`),
    the counter notes among them."""
    return _text(re.sub(r"<script\b.*?</script>", " ", html, flags=re.S))


def test_an_unreadable_counter_configuration_is_a_note_on_figures_compare_and_counts(setup, caplog):  # noqa: F811
    db_path, cfg_dir, _, _ = setup
    _seed(db_path)
    note = "counter configuration unreadable"
    with _client(_app(setup)) as c:  # readable: no note anywhere
        assert note not in _page_text(c.get("/city/paris/figures").text).lower()
        assert note not in _page_text(c.get("/compare?c=berlin,paris&m=counter_index").text)
        assert c.get("/data/series.json").json()["counters"]["config_error"] is False
    (cfg_dir / "counters.yaml").write_text("cities: [unclosed\n")
    with _client(_app(setup)) as c:
        figures = c.get("/city/paris/figures").text
        compare_page = _page_text(c.get("/compare?c=berlin,paris&m=counter_index").text)
        counts = _page_text(c.get("/city/berlin/counts").text)
        payload = c.get("/data/series.json").json()
    assert note in _page_text(_section_of(figures, "counter-data")).lower()
    assert compare.COUNTER_CONFIG_ERROR in compare_page
    assert note in counts.lower()
    assert payload["counters"]["config_error"] is True
    assert "counters.yaml" in caplog.text  # the detail goes to the log


def _section_of(html: str, anchor: str) -> str:
    start = html.index(f'id="{anchor}"')
    return html[start : html.index("</section>", start)]


def test_the_counts_tab_states_the_index_rule_from_its_constants(setup, monkeypatch):  # noqa: F811
    """MIN_SITES and MIN_VALID are printed from `counters.index`, not spelled out by hand: moving
    the constants moves the text (follow-up Task 3)."""

    _seed(setup[0], index={2019: 100.0, 2020: None})  # one year with a value: the no-line note
    monkeypatch.setattr(counter_index, "MIN_SITES", 7)
    monkeypatch.setattr(counter_index, "MIN_VALID", 0.8)
    with _client(_app(setup)) as c:
        text = _text(c.get("/city/berlin/counts").text)
    assert "links to a neighbouring one with 7 sites complete on at least 80% of days." in text
    assert "fewer than 7 sites complete on at least 80% of days in both years of a link" in text
    assert "nine days in ten" not in text and "three sites" not in text
