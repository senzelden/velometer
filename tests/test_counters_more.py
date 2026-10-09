"""M8 Task 7: the Helsinki, Madrid, Oslo and Barcelona counter adapters on fixtures cut from the
real portal files (tests/fixtures/counters/<city>/), the monthly index, the boundary filter and
the counter explainer.

Day totals below were summed by hand from the fixture rows (docs/review/m8-counters.md).
"""

import json
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

import openpyxl
import pytest
import yaml
from typer.testing import CliRunner

from velometer.cli import app
from velometer.content.check import causal_counter_wording
from velometer.content.loader import load_document
from velometer.counters.adapters import barcelona, helsinki, madrid, oslo
from velometer.counters.check import check_counters
from velometer.counters.days import to_days
from velometer.counters.index import MIN_SITES, chain_index_monthly
from velometer.counters.model import CounterFormatError, MonthValue, load_counters_config
from velometer.db import CounterMonth, create_schema, replace_counter_monthly

FIX = Path(__file__).parent / "fixtures" / "counters"
ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_counters_config(ROOT / "config" / "counters.yaml")

HEL = FIX / "helsinki"
HEL_FILES = [HEL / "Helsingin_pyorailijamaarat.xlsx", HEL / "pyoralaskentapisteiden_sijainnit.csv"]
MAD_FILES = [FIX / "madrid" / f"{y}.csv" for y in (2019, 2020, 2022, 2024)]
OSLO = FIX / "oslo"
OSLO_FILES = [OSLO / f for f in ("points.json", "70429B619257.json", "12703B2460285.json")]
OSLO_FILES.append(OSLO / "88224B442844.json")  # Snarøyveien, Bærum: outside Oslo
BCN = FIX / "barcelona"
BCN_FILES = [BCN / f"{y}_aforament_descripcio.csv" for y in (2019, 2024, 2025)] + [
    BCN / f"{y}_aforament_detall_valor.csv" for y in (2019, 2020, 2024)
]


def _days(sites_and_records, tz: str):
    _, records = sites_and_records
    return {(d.site_id, d.day): d for d in to_days(records, tz)}


# --- Helsinki -------------------------------------------------------------------------------


def test_helsinki_fixture_sites_and_day_totals():
    entry = CONFIG.entry("helsinki")
    sites, hours = helsinki.parse(HEL_FILES, entry)
    days = _days((sites, hours), entry.timezone)
    # the 03:00 placeholder row of the spring-forward day (3 at Baana) is not an hour
    assert (days["Baana", date(2019, 3, 31)].count, days["Baana", date(2019, 3, 31)].complete) == (
        671,
        True,
    )
    # fall-back day: 24 rows, the repeated hour once
    assert days["Baana", date(2019, 10, 27)].complete is False
    # fractional values are rounded per hour (41.447 -> 41, 24.868 -> 25, ...)
    assert days["Baana", date(2021, 3, 10)].count == 553
    # 2025 on: the spring-forward day has 23 rows
    assert days["Viikin Baana", date(2025, 3, 30)].count == 504
    assert days["Viikin Baana", date(2025, 3, 30)].complete
    assert ("Eteläesplanadi", date(2021, 3, 10)) not in days  # empty cells all day


def test_helsinki_bridge_sides_are_one_summed_site():
    entry = CONFIG.entry("helsinki")
    sites, hours = helsinki.parse(HEL_FILES, entry)
    by_id = {s.site_id: s for s in sites}
    assert "Kulosaaren silta et." not in by_id and "Kulosaaren silta po." not in by_id
    days = _days((sites, hours), entry.timezone)
    # 2016: the north column holds both sides (5,852), the south one 0
    assert days["Kulosaaren silta", date(2016, 6, 1)].count == 5852
    assert days["Kulosaaren silta", date(2016, 6, 1)].complete
    # 2022-03-15: the north side reports 19 of 24 hours, so the bridge's day is incomplete
    assert days["Kulosaaren silta", date(2022, 3, 15)].complete is False
    # the merged site sits between its two counting points (ETRS-GK25 -> WGS84)
    k = by_id["Kulosaaren silta"]
    assert k.lat == pytest.approx(60.1859, abs=1e-3) and k.lon == pytest.approx(24.9929, abs=1e-3)
    assert by_id["Baana"].lat == pytest.approx(60.1698, abs=1e-3)


def _workbook(path: Path, header: list, rows: list) -> Path:
    wb = openpyxl.Workbook()
    wb.active.append(header)
    for r in rows:
        wb.active.append(r)
    wb.save(path)
    return path


def test_helsinki_missing_time_column_raises(tmp_path):
    path = _workbook(tmp_path / "h.xlsx", ["Aikaleima", "Baana"], [[datetime(2019, 1, 1), 1]])
    with pytest.raises(CounterFormatError, match="Päivämäärä_aika"):
        helsinki.parse([path], CONFIG.entry("helsinki"))


def test_helsinki_a_repeated_fall_back_hour_is_the_second_pass(tmp_path):
    t = datetime(2025, 10, 26)
    rows = [[t.replace(hour=h), 1] for h in range(4)] + [[t.replace(hour=3), 2]]
    rows += [[t.replace(hour=h), 1] for h in range(4, 24)]
    path = _workbook(tmp_path / "h.xlsx", ["Päivämäärä_aika", "Baana"], rows)
    entry = CONFIG.entry("helsinki")
    days = _days(helsinki.parse([path], entry), entry.timezone)
    assert (days["Baana", t.date()].count, days["Baana", t.date()].complete) == (26, True)
    bad = _workbook(tmp_path / "b.xlsx", ["Päivämäärä_aika", "Baana"], [[t], [t]])
    with pytest.raises(CounterFormatError, match="repeated"):
        helsinki.parse([bad], entry)


# --- Madrid ---------------------------------------------------------------------------------


def test_madrid_fixture_day_totals():
    entry = CONFIG.entry("madrid")
    days = _days(madrid.parse(MAD_FILES, entry), entry.timezone)

    def got(site, d):
        x = days[f"PERM_BICI{site}", d]
        return x.count, x.complete

    assert got("01_PM01", date(2019, 9, 1)) == (260, True)  # `fecha` without the time
    assert got("01_PM01", date(2019, 10, 27)) == (290, False)  # 2019-2021: fall-back in 24 rows
    assert got("01_PM01", date(2020, 3, 29)) == (29, True)  # placeholder 2:00 row (0) ignored
    assert got("16_PM01", date(2020, 10, 1)) == (78, True)  # listed twice, counted once
    assert got("16_PM01", date(2020, 10, 25)) == (151, False)
    assert got("01_PM01", date(2022, 10, 30)) == (253, True)  # 2:00 twice: 25 hours
    assert got("01_PM01", date(2024, 3, 31)) == (285, True)  # 23 rows
    assert got("22_PM01", date(2024, 3, 12)) == (86, False)  # empty counts: missing hours


def test_madrid_repairs_double_encoding_and_dotted_coordinates():
    sites, _ = madrid.parse([FIX / "madrid" / "2022.csv"], CONFIG.entry("madrid"))
    s = {x.site_id: x for x in sites}["PERM_BICI01_PM01"]
    assert s.name == "Calle Toledo 133, 28005 Madrid (Sentido Gta. Pirámides)"
    assert (s.lat, s.lon) == (pytest.approx(40.405472), pytest.approx(-3.711961))


def test_madrid_duplicate_listing_with_other_counts_raises(tmp_path):
    lines = (FIX / "madrid" / "2020.csv").read_bytes().split(b"\r\n")
    i = next(n for n, ln in enumerate(lines) if b"01/10/2020 5:00;5:00;PERM_BICI16_PM01" in ln)
    parts = lines[i + 1].split(b";")
    assert parts[2] == b"PERM_BICI16_PM01" and b"5:00" in parts[0]
    parts[3] = str(int(parts[3]) + 7).encode()
    lines[i + 1] = b";".join(parts)
    bad = tmp_path / "2020.csv"
    bad.write_bytes(b"\r\n".join(lines))
    with pytest.raises(CounterFormatError, match="listed twice"):
        madrid.parse([bad], CONFIG.entry("madrid"))


# --- load via the CLI -----------------------------------------------------------------------


def _setup(tmp_path, city: str, files: list[Path], boundary: Path | None = None):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    entry = CONFIG.entry(city).model_dump()
    (cfg_dir / "counters.yaml").write_text(
        yaml.safe_dump({"cities": [entry], "none": []}, allow_unicode=True), encoding="utf-8"
    )
    data = tmp_path / "data"
    out = data / "counters" / city
    out.mkdir(parents=True)
    meta = []
    for i, f in enumerate(files):
        name = f"{i:02d}_{f.name}"
        shutil.copy(f, out / name)
        meta.append({"file": name, "url": f"https://example.org/{f.name}", "retrieved_at": "t"})
    (out / "retrieved.json").write_text(json.dumps({"files": meta}), encoding="utf-8")
    if boundary is not None:
        (data / "boundaries").mkdir()
        shutil.copy(boundary, data / "boundaries" / f"{city}_lau.geojson")
    db = tmp_path / "v.sqlite"
    args = ["--db", str(db), "--config-dir", str(cfg_dir)]
    res = CliRunner().invoke(app, ["counters", "load", city, "--data", str(data), *args])
    return res, sqlite3.connect(db)


def test_madrid_index_base_year_2020_is_100(tmp_path):
    assert CONFIG.entry("madrid").base_year == 2020
    res, conn = _setup(tmp_path, "madrid", MAD_FILES)
    assert res.exit_code == 0, res.output
    rows = conn.execute(
        "SELECT year, idx, sites, base_year FROM counter_index WHERE city_id='madrid'"
    )
    by_year = {y: (idx, n, base) for y, idx, n, base in rows}
    assert {base for _, _, base in by_year.values()} == {2020}
    idx, n, _ = by_year[2020]
    # 100 by definition, when the base year itself has MIN_SITES qualifying sites (spec §2.13)
    assert idx == (100.0 if n >= MIN_SITES else None)
    assert by_year[2019][0] is None  # four months of 2019: no link qualifies


@pytest.mark.parametrize(
    ("old", "new", "missing"),
    [(";NÚMERO;", ";PORTAL;", "número"), (";NOMBRE_VIAL;", ";VIA;", "nombre_vial")],
)
def test_madrid_address_header_without_its_pair_raises(tmp_path, old, new, missing):
    raw = (FIX / "madrid" / "2020.csv").read_bytes()
    assert old.encode() in raw
    path = tmp_path / "2020.csv"
    path.write_bytes(raw.replace(old.encode(), new.encode(), 1))
    with pytest.raises(CounterFormatError, match=f"column {missing!r} missing"):
        madrid.parse([path], CONFIG.entry("madrid"))


# --- Oslo -----------------------------------------------------------------------------------


def test_oslo_day_totals_and_coverage():
    entry = CONFIG.entry("oslo")
    _, days = oslo.parse(OSLO_FILES, entry)
    by = {(d.site_id, d.day): d for d in days}
    assert (
        by["70429B619257", date(2019, 10, 27)].count,
        by["70429B619257", date(2019, 10, 27)].complete,
    ) == (732, True)
    assert by["70429B619257", date(2015, 10, 26)].complete is False  # coverage 45.83 %
    assert ("70429B619257", date(2017, 5, 20)) not in by  # no volume (coverage 0)


def test_oslo_day_under_full_coverage_is_complete_when_every_local_hour_has_a_volume():
    """§5.2: complete = all hours present. Coverage below 100 % is read from `byHour`."""
    _, days = oslo.parse(OSLO_FILES, CONFIG.entry("oslo"))
    by = {(d.site_id, d.day): d for d in days}
    # coverage 99.69 %: 24 hours, each with a volume (one hour partly covered)
    assert by["12703B2460285", date(2019, 10, 28)].complete is True
    # coverage 45.83 %: 12 hour rows, 11 with a volume
    assert by["70429B619257", date(2015, 10, 26)].complete is False
    # no coverage figure (2010): 24 hours, each with a volume
    assert by["70429B619257", date(2010, 5, 6)].complete is True


def test_oslo_day_under_full_coverage_is_incomplete_without_every_hour(tmp_path):
    doc = json.loads((OSLO / "12703B2460285.json").read_text(encoding="utf-8"))
    no_hours = dict(doc, hours={})
    one_missing = json.loads(json.dumps(doc))
    one_missing["hours"]["2019-10-28"][7]["total"]["volumeNumbers"] = None
    one_dropped = json.loads(json.dumps(doc))
    del one_dropped["hours"]["2019-10-28"][7]
    for name, variant in (("a", no_hours), ("b", one_missing), ("c", one_dropped)):
        path = tmp_path / f"{name}_12703B2460285.json"
        path.write_text(json.dumps(variant), encoding="utf-8")
        _, days = oslo.parse([OSLO / "points.json", path], CONFIG.entry("oslo"))
        by = {d.day: d for d in days}
        assert by[date(2019, 10, 28)].complete is False, name
        assert by[date(2019, 10, 27)].complete is True, name  # coverage 100


def test_oslo_load_drops_a_point_outside_the_boundary(tmp_path):
    assert CONFIG.entry("oslo").boundary == "lau"
    res, conn = _setup(tmp_path, "oslo", OSLO_FILES, OSLO / "oslo_lau.geojson")
    assert res.exit_code == 0, res.output
    sites = {r[0] for r in conn.execute("SELECT site_id FROM counter_sites")}
    assert sites == {"70429B619257", "12703B2460285"}
    (outside,) = conn.execute(
        "SELECT COUNT(*) FROM counter_daily WHERE site_id='88224B442844'"
    ).fetchone()
    assert outside == 0
    (source,) = conn.execute("SELECT DISTINCT source FROM counter_sites").fetchone()
    assert "state counters" in source


def test_oslo_load_without_the_stored_boundary_fails(tmp_path):
    res, _ = _setup(tmp_path, "oslo", OSLO_FILES)
    assert res.exit_code == 1
    assert "lau boundary not readable" in res.output


def test_oslo_fetch_keeps_points_inside_pages_days_and_records_queries(tmp_path):
    points = json.loads((OSLO / "points.json").read_text(encoding="utf-8"))["data"]
    days = {
        p: json.loads((OSLO / f"{p}.json").read_text(encoding="utf-8"))["days"]
        for p in ("70429B619257", "12703B2460285", "88224B442844")
    }
    calls = []

    hours = {
        p: json.loads((OSLO / f"{p}.json").read_text(encoding="utf-8")).get("hours", {})
        for p in days
    }

    def post(url, query, variables):
        calls.append(variables)
        if "trafficRegistrationPoints" in query:
            return points
        if "byHour" in query:
            volume = {}
            for k, v in variables.items():
                if k.startswith("f"):
                    nodes = hours[variables["id"]][v[:10]]
                    edges = [{"node": n} for n in nodes]
                    volume[f"d{k[1:]}"] = {"edges": edges, "pageInfo": {"hasNextPage": False}}
            return {"trafficData": {"volume": volume}}
        nodes = days[variables["id"]]
        half = 0 if variables["after"] else 1  # two pages: the cursor is the split
        page = nodes[:2] if half else nodes[2:]
        info = {"hasNextPage": bool(half), "endCursor": "c2" if half else None}
        return {
            "trafficData": {
                "volume": {"byDay": {"edges": [{"node": n} for n in page], "pageInfo": info}}
            }
        }

    data = tmp_path / "data"
    (data / "boundaries").mkdir(parents=True)
    shutil.copy(OSLO / "oslo_lau.geojson", data / "boundaries" / "oslo_lau.geojson")
    out = tmp_path / "elsewhere" / "oslo"  # the data dir is a parameter, not out_dir's parent
    paths = oslo.fetch(CONFIG.entry("oslo"), out, data_dir=data, post=post)
    assert [p.name for p in paths] == [
        "00_points.json",
        "01_12703B2460285.json",
        "02_70429B619257.json",
    ]
    assert not any(c.get("id") == "88224B442844" for c in calls)
    got = json.loads(paths[2].read_text(encoding="utf-8"))
    assert [n["from"][:10] for n in got["days"]] == [n["from"][:10] for n in days["70429B619257"]]
    # byHour is asked only for days with a volume and coverage below 100 % (or none)
    assert sorted(got["hours"]) == ["2010-05-06", "2015-10-26"]
    assert got["hours"]["2015-10-26"] == hours["70429B619257"]["2015-10-26"]
    assert json.loads(paths[1].read_text(encoding="utf-8"))["hours"].keys() == {"2019-10-28"}
    meta = json.loads((out / "retrieved.json").read_text(encoding="utf-8"))
    assert meta["licence"] == "NLOD"
    assert all(f["url"] == "https://trafikkdata-api.atlas.vegvesen.no/" for f in meta["files"])
    assert all(f["query"] and f["retrieved_at"].endswith("Z") for f in meta["files"])


def test_counters_fetch_hands_the_data_dir_to_the_adapter(tmp_path, monkeypatch):
    import types

    from velometer.counters import adapters

    seen = {}

    def fetch(entry, out_dir, data_dir=None):
        seen.update(out_dir=out_dir, data_dir=data_dir)
        return []

    monkeypatch.setattr(adapters, "adapter", lambda name: types.SimpleNamespace(fetch=fetch))
    data = tmp_path / "somewhere"
    res = CliRunner().invoke(app, ["counters", "fetch", "oslo", "--data", str(data)])
    assert res.exit_code == 0, res.output
    assert seen == {"out_dir": data / "counters" / "oslo", "data_dir": data}


def test_oslo_fetch_without_a_data_dir_is_refused():
    with pytest.raises(ValueError, match="data directory"):
        oslo.fetch(CONFIG.entry("oslo"), Path("x"), post=lambda *a: pytest.fail("posted"))


def test_counter_downloads_and_the_oslo_api_send_the_shared_user_agent(agent_server):
    from velometer.counters import adapters
    from velometer.sources import download

    url, agents = agent_server
    assert adapters.user_agent is download.user_agent  # one user agent, not a copy
    adapters._http_get(url)
    oslo._graphql(url, "query { x }", {})
    assert agents == [download.user_agent(), download.user_agent()]


# --- Barcelona ------------------------------------------------------------------------------


def test_barcelona_bike_gauges_from_the_latest_descriptor():
    sites, months = barcelona.parse(BCN_FILES, CONFIG.entry("barcelona"))
    by_id = {s.site_id: s for s in sites}
    # the 2024 descriptor types the Glòries tunnel gauge 30001 `Bicis`, the 2025 one traffic
    assert set(by_id) == {"20012", "20013", "20015", "20037"}
    assert by_id["20012"].name == "DIPUTACIÓ-SARDENYA"  # 2025 descriptor
    assert by_id["20013"].name.startswith("CONSELL DE CENT - COMTE BORRELL")  # 2019 only
    values = {(m.site_id, m.month, m.day_type): m.avg_daily for m in months}
    assert values["20012", "2019-01", "working_day"] == 1635
    assert ("20037", "2020-04", "working_day") not in values  # "Mesura no disponible"
    assert {m.day_type for m in months} == {
        "monday",
        "working_day",
        "friday",
        "saturday",
        "sunday",
    }


def test_barcelona_index_needs_twelve_months_in_both_years():
    _, months = barcelona.parse(BCN_FILES, CONFIG.entry("barcelona"))
    index = {y: (v, n) for y, v, n in chain_index_monthly(months, 2019, "working_day")}
    assert index[2019] == (100.0, 4)
    # 20037 lacks April 2020: the link rests on 20012, 20013 and 20015, their yearly means
    # summed: (21632 + 19301 + 8811) / 12 over (24449 + 23959 + 9441) / 12
    assert index[2020][1] == 3
    assert index[2020][0] == pytest.approx(100 * 49744 / 57849)


def test_barcelona_load_stores_monthly_values_and_their_series(tmp_path):
    res, conn = _setup(tmp_path, "barcelona", BCN_FILES)
    assert res.exit_code == 0, res.output
    assert "monthly values" in res.output
    (n,) = conn.execute("SELECT COUNT(*) FROM counter_monthly WHERE city_id='barcelona'").fetchone()
    assert n > 0
    assert conn.execute("SELECT COUNT(*) FROM counter_daily").fetchone() == (0,)
    series = {r[0] for r in conn.execute("SELECT series FROM counter_index")}
    assert series == {"avg_daily_intensity"}
    span = conn.execute(
        "SELECT first_day, last_day FROM counter_sites WHERE site_id='20012'"
    ).fetchone()
    assert span == ("2019-01-01", "2024-12-31")


def test_monthly_index_with_a_gap_in_the_base_year():
    months = [
        MonthValue(s, f"{y}-{m:02d}", "working_day", 10.0)
        for s in "abc"
        for y in (2019, 2020)
        for m in range(1, 13)
    ]
    complete = {y: (v, n) for y, v, n in chain_index_monthly(months, 2019, "working_day")}
    assert complete[2019] == (100.0, 3)
    months = [x for x in months if not (x.site_id == "a" and x.month == "2019-05")]
    index = {y: (v, n) for y, v, n in chain_index_monthly(months, 2019, "working_day")}
    assert index[2019] == (None, 2)  # two gauges valid in the base year: below three (§2.13)
    assert index[2020] == (None, 2)  # two sites valid in both years: below three


# --- config, check, explainer ---------------------------------------------------------------


def test_seven_cities_configured_with_their_adapters():
    adapters = {c.city: c.adapter for c in CONFIG.cities}
    assert adapters == {
        c: c for c in ("berlin", "paris", "vienna", "helsinki", "madrid", "oslo", "barcelona")
    }
    assert CONFIG.entry("barcelona").grain == "monthly"
    assert CONFIG.entry("oslo").source.endswith("(state counters)")
    assert len(CONFIG.none) == 14


def test_check_flags_a_negative_monthly_value(tmp_path):
    conn = sqlite3.connect(tmp_path / "c.sqlite")
    create_schema(conn)
    replace_counter_monthly(
        conn, "barcelona", [CounterMonth("barcelona", "20012", "2019-01", "working_day", -1.0)]
    )
    problems = check_counters(conn, CONFIG)
    assert "barcelona: 1 negative monthly values" in problems


def test_counter_explainer_length_wording_and_facts():
    doc = load_document(ROOT / "content" / "counters.yaml")
    prose = [*doc.intro, *(p for s in doc.sections for p in s.paragraphs)]
    words = sum(len(p.split()) for p in prose)
    assert 150 <= words <= 300, words
    assert not any(causal_counter_wording(p) for p in prose)
    assert all(f.expr.startswith(("counter.", "counter_sites.")) for f in doc.facts)
    assert doc.quotes
