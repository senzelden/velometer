"""M8 Task 10: the Counts tab and the counter index in Compare (spec §5.5)."""

import json
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from tests.test_app import (  # noqa: F401 - `setup` is a fixture
    CONTENT,
    _client,
    _text,
    setup,
)
from tests.test_app_m7 import CSP, INLINE_CODE, INLINE_SCRIPT
from velometer.app import compare
from velometer.app.counts import COVID_YEAR, data_gaps, step_down_note
from velometer.app.main import create_app
from velometer.counters.model import CounterEntry, DayCount, StepDown
from velometer.db import (
    CounterDay,
    CounterIndexYear,
    CounterSite,
    replace_counter_index,
    replace_counter_sites,
    upsert_counter_daily,
)

URL = "https://example.org/counters.csv"
ROOT = Path(__file__).parents[1]


def _site(city, sid, lat=52.5, lon=13.4):
    return CounterSite(city, sid, f"Site {sid}", lat, lon, "Senate", "dl-de-zero-2.0", URL,
                       "2026-10-07T13:12:12Z", "2019-01-01", "2025-12-31")  # fmt: skip


def _index(city, values: dict, base=2019, series="counts"):
    return [CounterIndexYear(city, y, v, 0 if v is None else 4, base, series)
            for y, v in values.items()]  # fmt: skip


def _seed(db_path, city="berlin", index=None, sites=None, days=(), base=2019, series="counts"):
    conn = sqlite3.connect(db_path)
    try:
        replace_counter_sites(
            conn, city, sites or [_site(city, "s1"), _site(city, "s2", None, None)]
        )
        upsert_counter_daily(conn, list(days))
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
    html = client.get("/city/berlin/counts").text
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
    assert '<script src="/static/countermap.js"></script>' in html
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
        html = c.get("/city/berlin/counts").text
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
    assert notes == [f"M: {compare.NO_COUNTER_LINE}", f"N: {compare.NO_COUNTERS}"]


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
    body = r.text[r.text.index("<tbody>", r.text.index('class="compare-table"')) :]
    row = body[body.index('<a href="/city/berlin">') :]
    row = row[: row.index("</tr>")]
    assert re.findall(r'<td class="num">([^<]+)', row) == [
        "101.3",
        "100.0",
        "114.6",
        "n/a",
        "102.0",
    ]


def test_js_counter_notes_equal_the_python_ones():
    js = (ROOT / "src/velometer/app/static/js/counter-model.js").read_text(encoding="utf-8")
    for name in ("NO_COUNTERS", "NO_COUNTER_LINE", "AVG_DAILY"):
        assert f'export const {name} = "{getattr(compare, name)}";' in js, name


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
    key = html[html.index('class="meta chart-key"') :].split("</p>")[0]
    text = _text(key)
    assert "Counts: index of counts recorded at counter sites" in text
    assert "Mapped km: index of A+B mapped km in the city proper, 1 January snapshots" in text
    assert 'class="key key-counter"' in key and 'class="key key-km"' in key
    from tests.test_app import _css_rules
    from tests.test_app_m7 import STATIC

    rules = _css_rules((STATIC / "app.css").read_text())
    colour = {s: d.get("background") for sels, d in rules for s in sels}
    palette = re.search(r"PALETTE = \[([^\]]*)\]", (STATIC / "js" / "data.js").read_text())
    first, second = re.findall(r'"(#[0-9a-f]{6})"', palette.group(1))[:2]
    assert colour[".key-counter"] == first and colour[".key-km"] == second


def test_counts_chart_key_for_average_daily_intensity(setup):  # noqa: F811
    _seed(setup[0], series="avg_daily_intensity")
    with _client(_app(setup)) as c:
        html = c.get("/city/berlin/counts").text
    key = _text(html[html.index('class="meta chart-key"') :].split("</p>")[0])
    assert "Intensity: index of average daily intensity recorded at counter sites" in key
    # no km for the base year (2019 is before the fixture's snapshots): no km line, no km key
    assert "Mapped km" not in key
