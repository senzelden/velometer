import csv

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


def _shipped_metrics_and_sources():
    with (CFG / "external" / "figures.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    comps = rc.load_comparisons(CFG / "reconcile.yaml")
    metrics = {r["metric_name"] for r in rows} | {c.metric_name for c in comps}
    sources = {r["source"] for r in rows} | {s for c in comps for s in c.sources}
    return metrics, sources, {r["length_basis"] for r in rows}


def test_every_shipped_metric_source_and_basis_has_an_entry():
    cfg = _cfg()
    metrics, sources, bases = _shipped_metrics_and_sources()
    assert metrics <= set(cfg.labels), sorted(metrics - set(cfg.labels))
    assert sources <= set(cfg.source_methods), sorted(sources - set(cfg.source_methods))
    assert bases <= set(cfg.length_bases)
    assert set(cfg.metric_kinds) <= metrics
    assert "default" in cfg.areas


def test_coverage_check_fails_when_an_entry_is_missing():
    cfg = _cfg()
    metrics, sources, _ = _shipped_metrics_and_sources()
    labels = {k: v for k, v in cfg.labels.items() if k != "vorrangnetz_target_km"}
    methods = {k: v for k, v in cfg.source_methods.items() if k != "changing_cities"}
    assert not metrics <= set(labels)
    assert not sources <= set(methods)


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
    assert len(out) == len(data.reconcile("berlin").gaps) + len(data.reported_figures("berlin"))
    n_gaps = len(data.reconcile("berlin").gaps)
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


def test_qecio_gap_gets_an_area_driver_and_a_clean_cities_gap_does_not(rows):
    _, out = rows
    q = next(r for r in out if r.source == "qecio_v2_10")
    assert Driver("area", "city proper (LAU)", "NUTS3 region") in q.drivers
    cc = next(r for r in out if r.source == "clean_cities_2025")
    assert "area" not in _drivers(cc)


def test_a_dimension_equal_to_ours_has_no_driver():
    cfg = _cfg()
    same = cfg.model_copy(
        update={"length_bases": {**cfg.length_bases, "unknown": cfg.ours["length"]}}
    )
    from velometer.report.differences import _drivers as drivers

    kwargs = dict(
        source="official",
        metric="new_cycle_infra_km",
        snapshot=None,
        reference_date=None,
        date_gap_days=365,
        length_basis="unknown",
        scope_differs=False,
        boundary_differs=False,
        date_differs=False,
    )
    assert "length" not in {d.dimension for d in drivers(same, **kwargs)}
    assert "length" in {d.dimension for d in drivers(cfg, **kwargs)}


def test_date_driver_follows_the_gap_tag(rows):
    data, out = rows
    gaps = data.reconcile("berlin").gaps
    for row, gap in zip(out, gaps, strict=False):
        assert ("date" in _drivers(row)) == ("date_gap" in gap.tags)
    assert any("date_gap" in g.tags for g in gaps)  # the fixture's 2025-01-01 figures
