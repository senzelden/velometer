import json

import pytest

from velometer.report.charts import (
    ATTRIBUTION,
    headline_over_time,
    rankings_flip,
    tier_composition,
    tiers_small_multiples,
    write_pngs,
)
from velometer.report.data import RankingRow

EXPECTED_KEYS = {
    ("Berlin", "lau", "2024"),
    ("Berlin", "lau", "2025"),
    ("Berlin", "lau", "2026"),
    ("Berlin", "lau", "now"),
    ("Berlin", "fua", "2024"),
    ("Berlin", "fua", "2025"),
    ("Berlin", "fua", "2026"),
    ("Berlin", "fua", "now"),
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
        tier_composition(data, "berlin"),
        tiers_small_multiples(data),
        rankings_flip(data),
    ]


def test_headline_spec_has_one_row_per_city_kind_label(fixture_data):
    rows = _data_rows(headline_over_time(fixture_data))
    assert {(r["city"], r["kind"], r["label"]) for r in rows} == EXPECTED_KEYS
    assert len(rows) == len(EXPECTED_KEYS)
    assert any(r["flagged"] for r in rows)
    flagged = [r for r in rows if r["flagged"]]
    assert {(r["city"], r["label"]) for r in flagged} == {("Berlin", "2025")}
    assert "activity_spike" in flagged[0]["flags"]
    assert all(not r["flagged"] for r in rows if r not in flagged)


def test_headline_spec_has_ring_layer_and_dashed_fua(fixture_data):
    text = json.dumps(headline_over_time(fixture_data))
    assert '"strokeDash"' in text
    assert '"flagged"' in text
    assert "now" in text


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
