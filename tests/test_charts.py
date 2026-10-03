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
    rings = [layer for layer in _layers(spec) if "flagged" in json.dumps(layer)]
    assert len(rings) == 1
    assert "other" in json.dumps(rings[0]["transform"])


def test_rankings_grey_lines_are_thin_without_points(fixture_db):
    data = _reconfigure(fixture_db, report={"highlight": ["berlin"], "comparison_set": []})
    spec = rankings_flip(data)
    assert _roles(_ranking_rows(spec)) == {"berlin": {"highlight"}, "paris": {"other"}}
    grey = next(layer for layer in _layers(spec) if "other" in json.dumps(layer["transform"]))
    assert grey["mark"]["strokeWidth"] == 1 and not grey["mark"].get("point")
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
    text = " ".join(subtitle)
    assert "QECIO v2.10 (published): NUTS3 region per city; † NUTS3 region is not the city" in text
    for name in ("Berlin", "Paris", "Vienna", "Copenhagen", "Wroclaw"):
        assert not re.search(rf"published\)?: .*{name}", text)
    for line in subtitle[1:]:
        assert not re.search(r"\b[A-Z]{2}\d{3}\b", line), line  # no NUTS3 code
