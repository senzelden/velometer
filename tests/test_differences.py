import csv
from dataclasses import replace
from datetime import date

import pytest

from tests.report_fixture import _figure
from velometer import reconcile as rc
from velometer.config import (
    DIFFERENCE_DIMENSIONS,
    ConfigError,
    default_config_dir,
    load_differences,
)
from velometer.db import open_db, replace_external_figures
from velometer.report.differences import Driver, difference_rows

CFG = default_config_dir()


def _cfg():
    return load_differences(CFG / "differences.yaml")


def _drivers(row):
    return {d.dimension: d for d in row.drivers}


def test_config_loads_with_the_six_dimensions():
    cfg = _cfg()
    assert tuple(d.id for d in cfg.dimensions) == DIFFERENCE_DIMENSIONS
    assert set(cfg.ours) <= set(DIFFERENCE_DIMENSIONS)


def test_wrong_dimensions_are_rejected(tmp_path):
    bad = tmp_path / "d.yaml"
    text = (CFG / "differences.yaml").read_text().replace("  - {id: date, label: When}\n", "")
    bad.write_text(text)
    with pytest.raises(ConfigError, match="dimension ids"):
        load_differences(bad)


def _shipped():
    with (CFG / "external" / "figures.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    comps = rc.load_comparisons(CFG / "reconcile.yaml")
    metrics = {r["metric_name"] for r in rows} | {c.metric_name for c in comps}
    sources = {r["source"] for r in rows} | {s for c in comps for s in c.sources}
    return metrics, sources, {r["length_basis"] for r in rows}


def missing_entries(cfg) -> list[str]:
    """Every shipped metric, source and length basis that cfg has no entry for."""
    metrics, sources, bases = _shipped()
    return (
        [f"label:{m}" for m in sorted(metrics - set(cfg.labels))]
        + [f"source:{s}" for s in sorted(sources - set(cfg.source_methods))]
        + [f"basis:{b}" for b in sorted(bases - set(cfg.length_bases))]
    )


def test_every_shipped_metric_source_and_basis_has_an_entry():
    cfg = _cfg()
    assert missing_entries(cfg) == []
    assert set(cfg.metric_kinds) <= _shipped()[0]
    assert "default" in cfg.areas


def test_coverage_check_fails_when_an_entry_is_missing():
    cfg = _cfg()
    labels = {k: v for k, v in cfg.labels.items() if k != "vorrangnetz_target_km"}
    methods = {k: v for k, v in cfg.source_methods.items() if k != "changing_cities"}
    broken = cfg.model_copy(update={"labels": labels, "source_methods": methods})
    assert missing_entries(broken) == ["label:vorrangnetz_target_km", "source:changing_cities"]


@pytest.fixture
def rows(fixture_db):
    db_path, _cfg_dir, _conn, data = fixture_db
    target = _figure("berlin", "official", "vorrangnetz_target_km", 870.0, "vorrangnetz")
    new = _figure("berlin", "changing_cities", "new_cycle_infra_km", 25.2)
    target = target.model_copy(update={"length_basis": "streckenlaenge"})
    with open_db(db_path) as w:
        replace_external_figures(w, "official", [target])
        replace_external_figures(w, "changing_cities", [new])
    return data, difference_rows(data, "berlin", _cfg())


def test_one_row_per_gap_plus_one_per_reported_figure(rows):
    data, out = rows
    gaps = data.reconcile("berlin").gaps
    reported = data.reported_figures("berlin")
    # the changing_cities gap (ours None) is the reported figure again: one row, not two
    dropped = [g for g in gaps if g.ours is None]
    assert len(dropped) == 1
    n_gaps = len(gaps) - len(dropped)
    assert len(out) == n_gaps + len(reported)
    assert all(r.ours is None for r in out[n_gaps:])
    assert {r.source for r in out[n_gaps:]} == {"official", "changing_cities"}


def test_streckenlaenge_gets_a_length_driver(rows):
    _, out = rows
    row = next(r for r in out if r.metric == "vorrangnetz_target_km")
    assert Driver("length", "per road side", "route length (Streckenlänge)") in row.drivers
    assert _drivers(row)["kind"].theirs == "planned network"


def test_unknown_basis_is_stated_as_not_stated(rows):
    _, out = rows
    # the last match: the reported figure, after the informational gap of the same figure
    row = [r for r in out if r.source == "changing_cities"][-1]
    assert _drivers(row)["length"].theirs == "basis not stated by the source"


def test_area_driver_only_for_boundary_mismatch_gaps(rows):
    data, out = rows
    gaps = {g.key: g for g in data.reconcile("berlin").gaps}
    q = [r for r in out if r.source == "qecio_v2_10"]
    assert q and all("boundary_mismatch" not in g.tags for g in gaps.values())  # berlin = NUTS3
    assert all("area" not in _drivers(r) for r in out)
    # a city whose NUTS3 differs (here: forced) gets the QECIO area
    forced = replace(
        next(g for g in gaps.values() if g.source == "qecio_v2_10"), tags=("boundary_mismatch",)
    )
    report = data.reconcile("berlin")
    data.reconcile = lambda _c: replace(report, gaps=[forced])
    (row,) = [r for r in difference_rows(data, "berlin", _cfg()) if r.source == "qecio_v2_10"]
    assert Driver("area", "city proper (LAU)", "NUTS3 region") in row.drivers


def test_no_gap_repeats_a_reported_figure(rows):
    data, out = rows
    keys = [(r.source, r.metric, r.theirs, r.reference_date) for r in out if r.ours is None]
    assert len(keys) == len(set(keys))
    assert keys.count(("changing_cities", "new_cycle_infra_km", 25.2, date(2025, 1, 1))) == 1


def test_variant_gaps_are_distinguishable(rows):
    _, out = rows
    cc = [r for r in out if r.source == "clean_cities_2025" and r.ours is not None]
    ids = [(r.metric, r.theirs, r.basis, r.ours_label) for r in cc]
    assert len(ids) == len(set(ids))
    assert {r.basis for r in cc} == {"per_side", "qecio_weighted"}
    w = next(r for r in out if r.metric == "cycle_tracks_km")
    assert w.basis == "qecio_weighted" and "length" not in _drivers(w)  # already QECIO's basis


def test_gap_on_another_basis_than_the_source_gets_a_length_driver(rows):
    data, _ = rows
    report = data.reconcile("berlin")
    g = next(g for g in report.gaps if g.comparison == "qecio_tracks_km")
    data.reconcile = lambda _c: replace(report, gaps=[replace(g, key=g.key + "~per_side")])
    (row,) = difference_rows(data, "berlin", _cfg())[:1]
    assert row.basis == "per_side"
    assert (
        Driver(
            "length",
            "per road side",
            "unidirectional cycling infrastructure counted at half length",
        )
        in row.drivers
    )


def test_date_driver_follows_the_gap_tag(rows):
    data, out = rows
    gaps = data.reconcile("berlin").gaps
    for row, gap in zip(out, gaps, strict=False):
        assert ("date" in _drivers(row)) == ("date_gap" in gap.tags)
    assert any("date_gap" in g.tags for g in gaps)  # the fixture's 2025-01-01 figures


def test_an_unmapped_length_basis_or_unknown_source_and_metric_never_raise(rows, fixture_db):
    data, _ = rows
    cfg = _cfg()
    thin = cfg.model_copy(
        update={"length_bases": {}, "source_methods": {}, "bases": {}, "areas": {"default": "x"}}
    )
    out = difference_rows(data, "berlin", thin)
    row = next(r for r in out if r.metric == "vorrangnetz_target_km")
    assert _drivers(row)["length"].theirs == "basis not stated by the source"
    assert row.scope == "vorrangnetz"


def test_reported_rows_carry_scope_and_note(rows):
    _, out = rows
    row = next(r for r in out if r.metric == "vorrangnetz_target_km")
    assert row.scope == "vorrangnetz" and row.note == ""
