"""Compare page state (Task 12): parse_compare against the cases table state.js shares."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from velometer.app import compare

CASES = json.loads((Path(__file__).parent / "compare_cases.json").read_text())
JS = Path(__file__).parents[1] / "src" / "velometer" / "app" / "static" / "js"


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["name"])
def test_parse_compare_matches_the_shared_cases(case):
    k = CASES["known"]
    state = compare.parse_compare(case["query"], k["cities"], k["metrics"])
    assert state.as_dict() == case["expect"]
    assert state.dropped_metric == case["dropped_metric"]


def test_the_shared_cases_know_the_pages_metrics():
    assert CASES["known"]["metrics"] == list(compare.METRICS)


def test_the_default_metric_falls_back_to_the_first_known_one():
    s = compare.parse_compare("m=nope", ["berlin"], ["ab_km", "A"])
    assert s.m == "ab_km"


def test_parse_never_shares_the_default_city_list():
    s = compare.parse_compare("", ["berlin"], compare.METRICS)
    s.c.append("x")
    assert compare.PILOT5 == ["berlin", "paris", "vienna", "copenhagen", "wroclaw"]


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["name"])
def test_serialize_round_trips_through_parse(case):
    k = CASES["known"]
    state = compare.parse_compare(case["query"], k["cities"], k["metrics"])
    again = compare.parse_compare(compare.serialize(state), k["cities"], k["metrics"])
    assert again.as_dict() == state.as_dict()


def test_serialize_omits_defaults_and_keeps_the_key_order():
    state = compare.parse_compare("mode=index&m=ab_km", ["berlin"], compare.METRICS)
    assert compare.serialize(state) == "m=ab_km&mode=index"
    assert compare.serialize(state, c=["oslo", "berlin"]) == "c=oslo,berlin&m=ab_km&mode=index"


def test_quick_sets_are_the_briefs_and_all_is_every_known_city():
    assert compare.QUICK_SETS["pilot5"] == compare.PILOT5
    assert compare.QUICK_SETS["dach"] == ["berlin", "vienna"]
    assert compare.quick_set_ids("all", ["a", "b"]) == ["a", "b"]
    assert compare.quick_set_ids("nordic", ["oslo", "x"]) == ["oslo"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to read state.js")
def test_quick_sets_and_metrics_equal_the_js_constants():
    script = (
        f"import('{(JS / 'state.js').as_uri()}').then(m => "
        "console.log(JSON.stringify({q: m.QUICK_SETS, m: m.METRICS, p: m.PILOT5})))"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    assert js["q"] == compare.QUICK_SETS
    assert js["m"] == list(compare.METRICS)
    assert js["p"] == compare.PILOT5


def _payload(cities, series):
    return {
        "cities": {i: {"name": i.title(), "population": pop} for i, pop in cities.items()},
        "series": series,
    }


def _pt(label, **kw):
    return {"label": label, "osm": f"{label}-01-01" if label != "current" else "2026-10-03",
            "flags": "", **kw}  # fmt: skip


def test_table_model_index_notes_a_zero_or_missing_first_year():
    payload = _payload(
        {"a": 1000, "b": 1000, "c": 1000},
        {
            "a/lau": [_pt("2018", headline=10.0), _pt("2019", headline=20.0, flags="x")],
            "b/lau": [_pt("2018", headline=0.0), _pt("2019", headline=5.0)],
            "c/lau": [_pt("2019", headline=5.0)],
        },
    )
    state = compare.parse_compare("c=a,b,c&mode=index", ["a", "b", "c"], compare.METRICS)
    t = compare.table_model(payload, state)
    assert [r["values"] for r in t["rows"]] == [[100.0, 200.0], [None, None], [None, None]]
    assert t["rows"][0]["flagged"] == ["2019"]
    assert t["notes"] == [f"B: {compare.NO_INDEX}", f"C: {compare.NO_INDEX}"]
    assert t["index_base"] == "2018"


def test_table_model_ab_per_100k_uses_the_residents():
    payload = _payload(
        {"a": 200000}, {"a/lau": [_pt("2018", ab_km=50.0), _pt("current", ab_km=100.0)]}
    )
    state = compare.parse_compare("c=a&m=ab_per_100k", ["a"], compare.METRICS)
    t = compare.table_model(payload, state)
    assert t["rows"][0]["values"] == [25.0, 50.0]
    assert [c["text"] for c in t["columns"]] == ["Jan 2018", "Oct 2026"]
