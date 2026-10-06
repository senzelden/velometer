import math

import pytest

from tests.report_fixture import _figure, build_report_fixture_subareas
from velometer.content.facts import (
    FAMILIES,
    FactError,
    evaluate,
    parse_printed,
    printed_matches,
)
from velometer.db import open_db, replace_external_figures
from velometer.report.data import ReportData, open_readonly


@pytest.mark.parametrize(
    "printed,value,ok",
    [
        ("109.1", 109.1449, True),
        ("109.1", 109.16, False),
        ("1,551", 1550.7, True),
        ("+16%", 16.3, True),
        ("−4.6", -4.62, True),
        ("-4.6", -4.62, True),
        ("95", 95.4, True),
    ],
)
def test_printed_matches(printed, value, ok):
    assert printed_matches(value, printed) is ok


def test_parse_printed_decimals():
    assert parse_printed("1,234.56") == (1234.56, 2)


def test_parse_printed_rejects_text():
    with pytest.raises(FactError):
        parse_printed("about 5")


def test_series_and_derived_families(fixture_db, tmp_path):
    _db, _cfg, _conn, data = fixture_db
    pts = {p.label: p for p in data.series("berlin", "lau").points}
    first = min(pts, key=lambda lab: (lab == "current", lab))
    cur = pts["current"]
    assert evaluate("series.berlin.lau.current.ab_km", data, tmp_path) == cur.ab_km
    assert evaluate("series.berlin.lau.current.A", data, tmp_path) == cur.tiers_km["A"]
    assert math.isclose(
        evaluate("index.berlin.lau.current.ab_km", data, tmp_path),
        cur.ab_km / pts[first].ab_km * 100,
    )
    assert math.isclose(
        evaluate("denominator.berlin.lau.current", data, tmp_path),
        cur.ab_km / cur.headline * 100,
    )
    assert evaluate("rank.berlin.lau.2025.headline", data, tmp_path) in (1, 2)


def test_rank_is_by_headline_among_trusted(fixture_db, tmp_path):
    _db, _cfg, _conn, data = fixture_db
    vals = {}
    for c in data.cities():
        s = data.series(c.id, "lau")
        p = None if s is None else next((p for p in s.points if p.label == "2025"), None)
        if p is not None and p.headline is not None:
            vals[c.id] = p.headline
    assert len(vals) >= 2
    for city, v in vals.items():
        expected = 1 + sum(1 for o in vals.values() if o > v)
        assert evaluate(f"rank.{city}.lau.2025.headline", data, tmp_path) == expected


def test_delta_pct_total(fixture_db, tmp_path):
    _db, _cfg, _conn, data = fixture_db
    pts = {p.label: p for p in data.series("berlin", "lau").points}
    a, b = pts["2024"], pts["current"]
    assert math.isclose(
        evaluate("delta.berlin.lau.2024.current.ab_km", data, tmp_path), b.ab_km - a.ab_km
    )
    assert math.isclose(
        evaluate("pct.berlin.lau.2024.current.ab_km", data, tmp_path),
        (b.ab_km / a.ab_km - 1) * 100,
    )
    expected = sum(
        p.ab_km
        for c in data.cities()
        for s in [data.series(c.id, "lau")]
        if s is not None
        for p in s.points
        if p.label == "current"
    )
    assert math.isclose(evaluate("total.lau.current.ab_km", data, tmp_path), expected)


def test_gap_population_figure(fixture_db, tmp_path):
    db_path, _cfg, _conn, data = fixture_db
    gaps = data.reconcile("berlin").gaps
    gap = next(g for g in gaps if g.key == "berlin/cc_ratio@city_core~qecio_weighted")
    base = "gap.berlin.cc_ratio@city_core~qecio_weighted"
    assert evaluate(f"{base}.theirs", data, tmp_path) == gap.theirs
    assert math.isclose(evaluate(f"{base}.gap_pct", data, tmp_path), gap.gap_pct * 100)
    assert evaluate("gap.berlin.qecio_main_km.theirs", data, tmp_path) == 400.0
    assert evaluate("gap.berlin.cc_ratio.theirs", data, tmp_path) == 30.0  # the unscoped key
    berlin = next(c for c in data.cities() if c.id == "berlin")
    assert evaluate("population.berlin", data, tmp_path) == berlin.population.value
    with open_db(db_path) as w:
        replace_external_figures(
            w, "other_source", [_figure("berlin", "other_source", "km_total", 1234.5, "city")]
        )
    assert evaluate("figure.berlin.other_source.km_total.city", data, tmp_path) == 1234.5
    with pytest.raises(FactError, match="figure"):
        evaluate("figure.berlin.other_source.km_total.elsewhere", data, tmp_path)


def test_bezirk(tmp_path):
    db_path, cfg = build_report_fixture_subareas(tmp_path)
    conn = open_readonly(db_path)
    try:
        data = ReportData(conn, cfg)
        assert evaluate("bezirk.berlin.west.current.headline", data, tmp_path) == 4.0
        assert evaluate("bezirk.berlin.west.current.A", data, tmp_path) == 3.0
        with pytest.raises(FactError, match="bezirk"):
            evaluate("bezirk.berlin.nowhere.current.A", data, tmp_path)
    finally:
        conn.close()


def test_change_reads_the_city_row_of_the_window_page(fixture_db, tmp_path):
    _db, _cfg, _conn, data = fixture_db
    w = data.report_config.change_window
    to = w.to if isinstance(w.to, str) else w.to.isoformat()
    review = tmp_path / "review"
    review.mkdir()
    (review / f"berlin_change_{w.from_.isoformat()}_{to}.md").write_text(
        "# Change\n\n## Mapped km per category\n\n"
        "| | gained | lost | retiered | redrawn | geometry |\n|---|---:|---:|---:|---:|---:|\n"
        "| West | 1.250 | 0.000 | 0.000 | 0.000 | 0.000 |\n"
        "| **Berlin** | 1.250 | 0.500 | 2.000 | 0.250 | 0.125 |\n\n"
        "## gained: 1 way-side\n"
    )
    assert evaluate("change.berlin.gained", data, tmp_path) == 1.25
    assert evaluate("change.berlin.retiered", data, tmp_path) == 2.0
    assert evaluate("change.berlin.geometry", data, tmp_path) == 0.125
    with pytest.raises(FactError, match="change"):
        evaluate("change.paris.gained", data, tmp_path)


@pytest.mark.parametrize(
    "expr",
    [
        "series.berlin.lau.1999.headline",
        "series.nowhere.lau.current.headline",
        "series.berlin.lau.current.F",
        "bogus.berlin",
        "series.berlin",
        "series.berlin.xyz.current.headline",
        "rank.berlin.lau.1999.headline",
        "gap.berlin.nope.ours",
        "figure.berlin.nope.x.y",
        "population.nowhere",
        "change.berlin.bogus",
    ],
)
def test_unknown_paths_raise(fixture_db, tmp_path, expr):
    _db, _cfg, _conn, data = fixture_db
    with pytest.raises(FactError, match=expr.split(".")[0]):
        evaluate(expr, data, tmp_path)


def test_families_listed():
    assert "series" in FAMILIES and "change" in FAMILIES and len(FAMILIES) == 12
