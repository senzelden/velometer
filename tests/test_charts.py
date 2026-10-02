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
from velometer.report.data import RankEntry

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
    labels = [r.label for r in fixture_data.report_config.rankings]
    order = json.dumps(spec)
    positions = [order.index(json.dumps(label)) for label in labels]
    assert positions == sorted(positions)
    x_sort = spec["encoding"]["x"]["sort"] if "encoding" in spec else None
    assert x_sort == labels


def test_rankings_missing_city_is_absent(fixture_data):
    rows = _data_rows(rankings_flip(fixture_data))
    by_source = {}
    for r in rows:
        by_source.setdefault(r["source"], {})[r["city"]] = r["rank"]
    # paris has no current run (no preset value) and lacks cycle_lanes_km: no row, not a zero
    assert by_source["Ours: headline"] == {"Berlin": 1}
    assert by_source["QECIO v2.10 (published)"] == {"Berlin": 1}
    assert by_source["Clean Cities 2025 (published)"] == {"Berlin": 1, "Paris": 2}


def test_rankings_tie_shares_rank(fixture_data, monkeypatch):
    tied = [
        RankEntry(source_id="s", source_label="Ours: headline", city_id=c, value=5.0, rank=1)
        for c in ("berlin", "paris")
    ]
    monkeypatch.setattr(fixture_data, "ranks", lambda: tied)
    rows = _data_rows(rankings_flip(fixture_data))
    assert {(r["city"], r["rank"]) for r in rows} == {("Berlin", 1), ("Paris", 1)}


def test_every_spec_carries_the_attribution(fixture_data):
    assert "OpenStreetMap" in ATTRIBUTION and "ADR 0006" in ATTRIBUTION
    for spec in _all_specs(fixture_data):
        assert spec["title"]["subtitle"] == ATTRIBUTION


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
