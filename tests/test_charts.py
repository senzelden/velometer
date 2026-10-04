import json
import re

import pytest
import yaml

from velometer.report.charts import (
    ATTRIBUTION,
    GREY,
    PICK_COLOUR,
    headline_city,
    headline_over_time,
    rankings_flip,
    tier_composition,
    tiers_small_multiples,
    write_pngs,
)
from velometer.report.data import RankingRow, ReportData

EXPECTED_KEYS = {
    ("Berlin", "lau", "2024"),
    ("Berlin", "lau", "2025"),
    ("Berlin", "lau", "2026"),
    ("Berlin", "lau", "now"),
    ("Paris", "lau", "2024"),
    ("Paris", "lau", "2025"),
    ("Paris", "lau", "2026"),
}


@pytest.fixture
def fixture_data(fixture_db):
    return fixture_db[3]


def _data_rows(spec):
    """The inline rows of the spec's top-level data (or its first dataset)."""
    if "datasets" in spec:
        return next(iter(spec["datasets"].values()))
    return spec["data"]["values"]


def _keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _keys(v)


def _all_specs(data):
    return [
        headline_over_time(data),
        headline_city(data, "berlin"),
        tier_composition(data, "berlin"),
        tiers_small_multiples(data),
        rankings_flip(data),
    ]


def test_headline_is_lau_only(fixture_data):
    rows = _data_rows(headline_over_time(fixture_data))
    assert {r["kind"] for r in rows} == {"lau"}  # FUA moved to the city page


def test_headline_spec_has_one_row_per_city_kind_label(fixture_data):
    rows = _data_rows(headline_over_time(fixture_data))
    assert {(r["city"], r["kind"], r["label"]) for r in rows} == EXPECTED_KEYS
    assert len(rows) == len(EXPECTED_KEYS)
    assert any(r["flagged"] for r in rows)
    flagged = [r for r in rows if r["flagged"]]
    assert {(r["city"], r["label"]) for r in flagged} == {("Berlin", "2025")}
    assert "activity_spike" in flagged[0]["flags"]
    assert all(not r["flagged"] for r in rows if r not in flagged)


def test_headline_spec_has_ring_layer_and_now_labels(fixture_data):
    text = json.dumps(headline_over_time(fixture_data))
    assert '"flagged"' in text
    assert "now" in text
    assert '"strokeDash"' not in text


def test_headline_city_has_both_kinds_lau_solid_fua_dashed(fixture_data):
    spec = headline_city(fixture_data, "berlin")
    rows = _data_rows(spec)
    assert {(r["kind"], r["label"]) for r in rows} == {
        (k, y) for k in ("lau", "fua") for y in ("2024", "2025", "2026", "now")
    }
    assert {r["city"] for r in rows} == {"Berlin"}
    text = json.dumps(spec)
    assert '"strokeDash"' in text and '"flagged"' in text
    assert {r["label"] for r in rows if r["flagged"]} == {"2025"}
    assert "url" not in set(_keys(spec))


def test_tier_composition_has_five_tiers_per_label_in_m3_colours(fixture_data):
    spec = tier_composition(fixture_data, "berlin")
    rows = _data_rows(spec)
    assert {r["tier"] for r in rows} == set("ABCDE")
    assert {r["label"] for r in rows} == {"2024", "2025", "2026", "now"}
    assert len(rows) == 5 * 4
    colours = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    assert json.dumps(colours) in json.dumps(spec).replace(", ", ", ")


def test_tier_small_multiples_cover_every_city_lau(fixture_data):
    rows = _data_rows(tiers_small_multiples(fixture_data))
    assert {r["city"] for r in rows} == {"Berlin", "Paris"}


def test_small_multiples_shared_y_and_seven_columns(fixture_data):
    spec = tiers_small_multiples(fixture_data)
    assert spec["columns"] == 7
    assert spec["resolve"]["scale"]["y"] == "shared"
    assert spec["spec"]["width"] == 150 and spec["spec"]["height"] == 110
    assert spec["facet"]["sort"] == "ascending"  # the city name


def test_rankings_spec_orders_sources_as_report_yaml(fixture_data):
    spec = rankings_flip(fixture_data)
    configured = [r.label for r in fixture_data.report_config.rankings]
    x_sort = spec["encoding"]["x"]["sort"] if "encoding" in spec else None
    assert [s.rsplit(" (n=", 1)[0] for s in x_sort] == configured
    assert all(s.endswith(")") for s in x_sort)


def test_rankings_missing_city_has_a_null_rank_not_a_zero(fixture_data):
    rows = _data_rows(rankings_flip(fixture_data))
    by_source = {}
    for r in rows:
        by_source.setdefault(r["source"], {})[r["city"]] = r["rank"]
    # paris has no current run (no preset value) and lacks cycle_lanes_km: a gap, not a zero
    assert by_source["Ours: headline (n=1)"] == {"Berlin": 1, "Paris": None}
    assert by_source["QECIO v2.10 (published) (n=1)"] == {"Berlin": 1, "Paris": None}
    assert by_source["Clean Cities 2025 (published) (n=2)"] == {"Berlin": 1, "Paris": 2}


def test_rankings_tie_shares_rank(fixture_data, monkeypatch):
    tied = [
        RankingRow(
            source_id="s",
            source_label="Ours: headline",
            city_id=c,
            value=5.0,
            rank=1,
            n_ranked=2,
        )
        for c in ("berlin", "paris")
    ]
    monkeypatch.setattr(fixture_data, "ranking_rows", lambda: tied)
    rows = _data_rows(rankings_flip(fixture_data))
    assert {(r["city"], r["rank"]) for r in rows} == {("Berlin", 1), ("Paris", 1)}


def test_every_spec_carries_the_attribution(fixture_data):
    assert "OpenStreetMap" in ATTRIBUTION and "ADR 0006" in ATTRIBUTION
    for spec in _all_specs(fixture_data):
        subtitle = spec["title"]["subtitle"]
        lines = subtitle if isinstance(subtitle, list) else [subtitle]
        assert lines[0] == ATTRIBUTION


def test_no_spec_has_a_url_key(fixture_data):
    for spec in _all_specs(fixture_data):
        assert "url" not in set(_keys(spec))


def test_write_pngs_writes_nonempty_pngs_and_specs(fixture_data, tmp_path):
    paths = write_pngs(fixture_data, tmp_path)
    assert {p.name for p in paths} >= {"m4_headline.png", "m4_tiers.png", "m4_rankings.png"}
    pngs = [p for p in paths if p.suffix == ".png"]
    assert len(pngs) == 3
    assert all(p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and p.stat().st_size > 1000 for p in pngs)
    for p in pngs:
        spec = json.loads(p.with_suffix(".vl.json").read_text())
        assert "url" not in set(_keys(spec))


def test_report_charts_cli_writes_into_out_dir(fixture_db, tmp_path):
    from typer.testing import CliRunner

    from velometer.cli import app

    db_path, cfg, _, _ = fixture_db
    out = tmp_path / "out"
    res = CliRunner().invoke(
        app, ["report", "charts", "--out", str(out), "--db", str(db_path), "--config-dir", str(cfg)]
    )
    assert res.exit_code == 0, res.output
    assert (out / "m4_rankings.png").stat().st_size > 1000
    missing = CliRunner().invoke(app, ["report", "charts", "--db", str(tmp_path / "no.sqlite")])
    assert missing.exit_code == 1


def test_tier_small_multiples_give_every_panel_its_own_x_axis(fixture_data):
    # wrapped facets share one x axis per column, drawn under the column's last row: with five
    # cities in three columns, Paris's year labels landed under the empty sixth cell
    spec = tiers_small_multiples(fixture_data)
    assert spec["resolve"]["axis"]["x"] == "independent"


def test_rankings_footnote_states_each_published_columns_scope(fixture_data):
    # M4 spec 4.2: each ranking column's footnote states its scope (config/report.yaml `note`)
    notes = [(r.label, getattr(r, "note", None)) for r in fixture_data.report_config.rankings]
    notes = [(label, note) for label, note in notes if note]
    assert notes, "the fixture config must carry ranking notes for this test to bite"
    subtitle = rankings_flip(fixture_data)["title"]["subtitle"]
    for label, note in notes:
        assert f"{label}: {note}" in subtitle


def _titles(spec) -> list[str]:
    """Every axis and tooltip title in a spec (nested layers and encodings included)."""
    out = []
    if isinstance(spec, dict):
        for k, v in spec.items():
            if k == "title" and isinstance(v, str):
                out.append(v)
            out += _titles(v)
    elif isinstance(spec, list):
        for v in spec:
            out += _titles(v)
    return out


def test_headline_axis_is_km_per_100_km_main_roads_not_a_share(fixture_data):
    """ADR 0003: the headline is A+B km per 100 km of main roads (excl. motorways), which can
    exceed 100; it is not a share or a percent."""
    headline = headline_over_time(fixture_data)
    assert "A+B km per 100 km of main roads (excl. motorways)" in _titles(headline)
    for spec in (headline, rankings_flip(fixture_data)):
        for t in _titles(spec):
            assert "share" not in t.lower() and "%" not in t, t


def test_rankings_line_breaks_at_a_missing_source(fixture_data):
    spec = rankings_flip(fixture_data)
    values = _data_rows(spec)
    assert any(v["city"] == "Paris" and v["rank"] is None for v in values)
    mark = spec["layer"][0]["mark"] if "layer" in spec else spec["mark"]
    assert mark["invalid"] == "break-paths-filter-domains"
    assert any("(n=1)" in v["source"] for v in values)
    assert any(v["value_text"] == "not published" for v in values)


def _reconfigure(fixture_db, *, report=None, cities=None):
    """A ReportData over the fixture whose config copy has `report` keys set and `cities`
    (id -> fields) merged into cities.yaml."""
    _db, cfg, conn, _ = fixture_db
    if report:
        path = cfg / "report.yaml"
        doc = yaml.safe_load(path.read_text()) | report
        path.write_text(yaml.safe_dump(doc, sort_keys=False))
    if cities:
        path = cfg / "cities.yaml"
        doc = yaml.safe_load(path.read_text())
        for c in doc["cities"]:
            c.update(cities.get(c["id"], {}))
        path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return ReportData(conn, cfg)


def _roles(rows):
    out = {}
    for r in rows:
        out.setdefault(r["city_id"], set()).add(r["role"])
    return out


def test_headline_roles_follow_config(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["paris"], "comparison_set": []})
    rows = _data_rows(headline_over_time(data))
    assert _roles(rows) == {"paris": {"highlight"}, "berlin": {"other"}}


def test_a_city_in_neither_list_is_other_and_comparison_is_comparison(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": [], "comparison_set": ["paris"]})
    assert _roles(_data_rows(headline_over_time(data))) == {
        "paris": {"comparison"},
        "berlin": {"other"},
    }


def _layers(spec):
    return spec["layer"]


FLAGGED = "(datum.flagged === true)"
NOT_OTHER = "(datum.role !== 'other')"


def _filters(layer):
    """The Vega filter expressions of a layer's transform, in order."""
    return [t["filter"] for t in layer.get("transform", []) if "filter" in t]


def test_headline_has_a_bound_picker_on_the_grey_layer(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["berlin"], "comparison_set": []})
    spec = headline_over_time(data)
    # altair hoists a layer's selection param to the top level, scoped to that layer by `views`
    params = [*spec.get("params", []), *(p for lay in _layers(spec) for p in lay.get("params", []))]
    pick = next(p for p in params if p["name"] == "pick")
    assert pick["bind"]["input"] == "select"
    assert pick["bind"]["options"] == [None, "Paris"]
    assert pick["bind"]["labels"] == ["—", "Paris"]
    assert pick["bind"]["name"] == "Highlight a city "
    grey = next(layer for layer in _layers(spec) if "pick" in json.dumps(layer["encoding"]))
    assert "other" in json.dumps(grey["transform"])
    colour = grey["encoding"]["color"]["condition"]
    assert colour["value"] == PICK_COLOUR and grey["encoding"]["color"]["value"] == GREY
    assert grey["encoding"]["strokeWidth"]["condition"]["param"] == "pick"


def test_headline_coloured_layers_follow_config_order_and_label_now(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["berlin"], "comparison_set": ["paris"]})
    spec = headline_over_time(data)
    text = json.dumps(spec)
    assert '"domain": ["Berlin", "Paris"]' in text
    assert any(layer["mark"]["type"] == "text" for layer in _layers(spec))
    # flag rings are drawn for the coloured layer only
    rings = [layer for layer in _layers(spec) if FLAGGED in _filters(layer)]
    assert len(rings) == 1
    assert NOT_OTHER in _filters(rings[0])


def test_rankings_grey_lines_are_thin(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["berlin"], "comparison_set": []})
    spec = rankings_flip(data)
    assert _roles(_ranking_rows(spec)) == {"berlin": {"highlight"}, "paris": {"other"}}
    grey = next(layer for layer in _layers(spec) if "other" in json.dumps(layer["transform"]))
    assert grey["mark"]["strokeWidth"] == 1
    assert grey["mark"]["invalid"] == "break-paths-filter-domains"


def _ranking_rows(spec):
    rows = _data_rows(spec)
    return [{"city_id": r["city_id"], "role": r["role"]} for r in rows]


def test_qecio_column_marks_cities_whose_nuts3_is_not_the_city(fixture_db):
    data = _reconfigure(fixture_db, cities={"paris": {"nuts3_is_city": False}})
    rows = _data_rows(rankings_flip(data))
    by = {(r["source"].split(" (n=")[0], r["city"]): r["city_label"] for r in rows}
    assert by[("QECIO v2.10 (published)", "Paris")] == "Paris †"
    assert by[("QECIO v2.10 (published)", "Berlin")] == "Berlin"
    # only the NUTS3 column carries the marker
    assert by[("Clean Cities 2025 (published)", "Paris")] == "Paris"
    assert by[("Ours: headline", "Paris")] == "Paris"


def test_qecio_marker_follows_the_flag(fixture_db):
    data = _reconfigure(fixture_db, cities={"paris": {"nuts3_is_city": True}})
    labels = {r["city_label"] for r in _data_rows(rankings_flip(data))}
    assert not any("†" in label for label in labels)


def test_ranking_notes_are_generic_and_name_no_city(fixture_db):
    subtitle = rankings_flip(fixture_db[3])["title"]["subtitle"]
    # the config notes; the "(gap in the line)" lines name the cities a source lacks, by design
    text = " ".join(s for s in subtitle if "(gap in the line)" not in s)
    assert "QECIO v2.10 (published): NUTS3 region per city; † NUTS3 region is not the city" in text
    for name in ("Berlin", "Paris", "Vienna", "Copenhagen", "Wroclaw"):
        assert not re.search(rf"published\)?: .*{name}", text)
    for line in subtitle[1:]:
        assert not re.search(r"\b[A-Z]{2}\d{3}\b", line), line  # no NUTS3 code


def _label_layer(spec):
    return next(
        lay
        for lay in _layers(spec)
        if lay["mark"]["type"] == "text" and "now" in json.dumps(lay["transform"])
    )


def test_headline_legend_does_not_sit_where_the_end_labels_are(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["berlin"], "comparison_set": ["paris"]})
    spec = headline_over_time(data)
    colour = next(
        lay["encoding"]["color"]
        for lay in _layers(spec)
        if lay["mark"]["type"] == "line"
        and "legend" in lay["encoding"].get("color", {})
        and lay["encoding"]["color"]["legend"] is not None
    )
    legend = colour["legend"]
    assert legend.get("orient") not in (None, "right", "top-right", "top")  # default is right
    assert _label_layer(spec)  # the labels exist, so the legend is a duplicate at best


def test_spread_labels_keeps_a_minimum_gap_and_order():
    from velometer.report.charts import _spread_labels

    out = _spread_labels({"a": 238.0, "b": 237.0, "c": 100.0, "d": 99.5, "e": 99.0}, gap=5.0)
    ys = sorted(out.values())
    assert all(b - a >= 5.0 - 1e-9 for a, b in zip(ys, ys[1:], strict=False))
    assert out["c"] > out["d"] > out["e"] and out["a"] > out["b"]  # order is kept
    assert _spread_labels({"x": 1.0, "y": 50.0}, gap=5.0) == {"x": 1.0, "y": 50.0}


def test_headline_end_labels_use_the_spread_position(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["berlin"], "comparison_set": ["paris"]})
    spec = headline_over_time(data)
    assert _label_layer(spec)["encoding"]["y"]["field"] == "label_y"
    now = [r for r in _data_rows(spec) if r["label"] == "now" and r["role"] != "other"]
    assert all("label_y" in r for r in now)


def test_small_multiples_show_at_most_four_year_labels(fixture_db):
    spec = tiers_small_multiples(fixture_db[3])
    axis = spec["spec"]["encoding"]["x"]["axis"]
    assert 1 <= len(axis["values"]) <= 4
    assert axis["values"][-1] == "now"


def test_qecio_dagger_sits_on_its_own_point_to_the_right(fixture_db):
    data = _reconfigure(fixture_db, cities={"paris": {"nuts3_is_city": False}})
    spec = rankings_flip(data)
    dagger = next(lay for lay in _layers(spec) if lay["mark"].get("text") == "†")
    point = next(
        lay
        for lay in _layers(spec)
        if lay["mark"]["type"] == "line" and lay["mark"].get("strokeWidth") != 1
    )
    # y comes from the shared top-level encoding unless a layer overrides it: same field for both
    y_of = lambda lay: lay.get("encoding", {}).get("y", spec["encoding"]["y"])["field"]  # noqa: E731
    assert y_of(dagger) == y_of(point) == "rank"
    assert dagger["mark"].get("dy", 0) == 0
    assert dagger["mark"]["dx"] > 0
    assert dagger["mark"]["baseline"] == "middle" and dagger["mark"]["align"] == "left"


def test_spread_labels_never_swap_order_and_stay_near_their_own_line():
    from velometer.report.charts import _spread_labels

    gap = 10.7
    values = {"berlin": 110.0, "wien": 91.0, "paris": 62.0, "far": 240.0, "close": 108.0}
    out = _spread_labels(values, gap)
    assert sorted(out, key=out.get) == sorted(values, key=values.get)  # same vertical order
    assert all(out[k] <= values[k] + 1e-9 for k in values)  # pushed down only, never up
    assert all(values[k] - out[k] <= gap * (len(values) - 1) for k in values)
    # wien is 19 below berlin: more than the gap, so it stays on its own line end
    assert _spread_labels({"berlin": 110.0, "wien": 91.0, "paris": 62.0}, gap) == {
        "berlin": 110.0,
        "wien": 91.0,
        "paris": 62.0,
    }


def _vega_filter(expr: str):
    """A Python predicate for the simple Vega filter expressions the charts use."""
    py = re.sub(r"datum\.(\w+)", r"r.get('\1')", expr)
    for a, b in (("===", "=="), ("!==", "!="), ("&&", " and "), ("||", " or ")):
        py = py.replace(a, b)
    py = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", py))
    return lambda r: eval(py, {}, {"r": r})  # noqa: S307 - test-only, expressions from our spec


def _draws_points(layer) -> bool:
    mark = layer["mark"]
    return mark["type"] in ("point", "circle") or (
        mark["type"] == "line" and bool(mark.get("point"))
    )


def _rows_of(layer, rows):
    preds = [_vega_filter(t["filter"]) for t in layer.get("transform", []) if "filter" in t]
    return [r for r in rows if all(p(r) for p in preds)]


@pytest.mark.parametrize(
    "report",
    [
        {"highlight": ["berlin"], "comparison_set": []},
        {"highlight": [], "comparison_set": []},
        {"highlight": ["paris"], "comparison_set": ["berlin"]},
    ],
)
def test_rankings_every_ranked_row_is_drawn_as_a_point(fixture_db, report):
    # a line mark draws nothing for an isolated point (a city whose figure gap sits beside it):
    # every ranked row needs a layer that renders points, whatever its role
    spec = rankings_flip(_reconfigure(fixture_db, report=report))
    rows = _data_rows(spec)
    drawn = {
        (r["source"], r["city_id"])
        for lay in _layers(spec)
        if _draws_points(lay)
        for r in _rows_of(lay, rows)
    }
    ranked = {(r["source"], r["city_id"]) for r in rows if r["rank"] is not None}
    assert ranked and ranked <= drawn


def test_rankings_grey_points_are_small_and_grey(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["berlin"], "comparison_set": []})
    spec = rankings_flip(data)
    grey = next(layer for layer in _layers(spec) if "other" in json.dumps(layer["transform"]))
    point = grey["mark"]["point"]
    assert point["color"] == GREY and point["size"] <= 30


def test_rankings_name_every_city_a_source_has_no_figure_for(fixture_data):
    spec = rankings_flip(fixture_data)
    subtitle = spec["title"]["subtitle"]
    by_label = {r.label: r.kind for r in fixture_data.report_config.rankings}
    gaps = [r for r in _data_rows(spec) if r["rank"] is None]
    assert gaps  # the fixture's paris has no QECIO figure and no current run
    for r in gaps:
        label = r["source"].rsplit(" (n=", 1)[0]
        line = next((s for s in subtitle if s.startswith(label) and r["city"] in s), None)
        assert line is not None, (label, r["city"], subtitle)
        if by_label[label] != "preset":
            assert "not publish" in line
    # a source with no gap gets no line
    full = {r["source"].rsplit(" (n=", 1)[0] for r in _data_rows(spec)} - {
        r["source"].rsplit(" (n=", 1)[0] for r in gaps
    }
    assert full and not any(
        s.startswith(f"{lab} ") and "gap" in s for s in subtitle for lab in full
    )


def test_spread_labels_never_go_below_the_floor_and_keep_order_and_gap():
    from velometer.report.charts import _spread_labels

    values = {"a": 2.0, "b": 1.5, "c": 1.0, "d": 0.2}
    out = _spread_labels(values, gap=5.0)
    assert min(out.values()) >= 0.0
    assert sorted(out, key=out.get) == sorted(values, key=values.get)
    ys = sorted(out.values())
    assert all(b - a >= 5.0 - 1e-9 for a, b in zip(ys, ys[1:], strict=False))
    assert out["d"] == 0.0  # the lowest label sits on the floor, not above it


def test_headline_subareas_is_one_facet_per_subarea_on_a_shared_y(tmp_path):
    from tests.report_fixture import build_report_fixture_subareas
    from velometer.report.charts import headline_subareas
    from velometer.report.data import open_readonly

    db_path, cfg = build_report_fixture_subareas(tmp_path)
    conn = open_readonly(db_path)
    try:
        spec = headline_subareas(ReportData(conn, cfg), "berlin")
    finally:
        conn.close()
    rows = _data_rows(spec)
    assert {r["name"] for r in rows} == {"West", "East"}
    assert {(r["name"], r["label"]) for r in rows} == {
        (n, y) for n in ("West", "East") for y in ("2024", "2025", "2026", "now")
    }
    assert {r["headline"] for r in rows if r["name"] == "West"} == {4.0}
    assert spec["facet"]["field"] == "name"
    assert spec["resolve"]["scale"]["y"] == "shared"
    labels = spec["spec"]["encoding"]["x"]["axis"]["values"]
    assert len(labels) <= 4  # R32: at most four year labels per panel
    assert ATTRIBUTION in json.dumps(spec, ensure_ascii=False)
    assert "url" not in set(_keys(spec))
