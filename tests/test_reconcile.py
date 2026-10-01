from datetime import date
from pathlib import Path

import pytest

from velometer import reconcile as RC
from velometer.db import RunResults
from velometer.models import ExternalFigure, Metric, RoadLength, TierLength

CFG = Path(__file__).resolve().parents[1] / "config" / "reconcile.yaml"


def _results():
    t = lambda tier, km, basis="per_side", sub=None: TierLength(  # noqa: E731
        tier=tier, subtype=sub, length_basis=basis, length_km=km, n_ways=1
    )
    return RunResults(
        run_id=1,
        city_id="berlin",
        osm_timestamp="2026-09-30T20:22:42Z",
        tier_lengths=[
            t("A", 600),
            t("B", 300),
            t("B", 100, sub="segregated"),
            t("A", 300, "qecio_weighted"),
            t("B", 100, "qecio_weighted", "segregated"),
            t("B", 150, "qecio_weighted"),
        ],
        road_lengths=[RoadLength(road_class="all_public", length_km=5000)],
        metrics=[
            Metric(
                preset="clean_cities_2025",
                length_basis="per_side",
                value=20.0,
                numerator_km=1000,
                denominator_km=5000,
            )
        ],
        completeness=[],
    )


def _fig(source, metric, value, scope="whole_network", ref=date(2025, 5, 14)):
    return ExternalFigure(
        city_id="berlin",
        source=source,
        metric_name=metric,
        value=value,
        unit="km",
        reference_date=ref,
        network_scope=scope,
        length_basis="unknown",
        source_url="u",
        retrieved_at=date(2026, 10, 1),
    )


def test_ours_value_sums_tiers_with_subtype_and_exclude():
    comps = {c.id: c for c in RC.load_comparisons(CFG)}
    r = _results()
    assert RC.ours_value(r, comps["cc_km"].ours) == 1000  # A 600 + B 300 + B/segregated 100
    assert RC.ours_value(r, comps["qecio_tracks_km"].ours) == 400  # A 300 + B/seg 100
    assert RC.ours_value(r, comps["qecio_shared_km"].ours) == 150  # B minus B/segregated
    assert RC.ours_value(r, comps["cc_ratio"].ours) == 20.0


def test_gaps_flag_over_threshold_and_tag_date_gap():
    comps = RC.load_comparisons(CFG)
    figs = [
        _fig("clean_cities_2025", "protected_km", 925),  # +8% -> not flagged
        _fig("clean_cities_2025", "network_km", 5350),  # -6.5%
        _fig("clean_cities_2025", "protected_share_pct", 17),  # +17.6%
        _fig("qecio_v2_10", "cycle_tracks_km", 679.471, "nuts3_DE300", date(2024, 1, 10)),
    ]
    gaps = {
        g.comparison: g
        for g in RC.gaps_for(_results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={})
    }
    assert not gaps["cc_km"].flagged
    assert gaps["qecio_tracks_km"].flagged  # 400 vs 679 = -41%
    assert "date_gap" in gaps["qecio_tracks_km"].tags
    assert gaps["cc_km"].gap_pct == pytest.approx((1000 - 925) / 925)


def test_informational_comparisons_are_never_flagged():
    comps = RC.load_comparisons(CFG)
    figs = [_fig("official", "new_cycle_infra_km", 21.2)]
    (g,) = RC.gaps_for(_results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={})
    assert g.informational and not g.flagged and g.ours is None


def test_write_report_replaces_only_generated_block_and_check_finds_missing(tmp_path):
    md = tmp_path / "reconciliation.md"
    md.write_text(
        "# R\n\nintro\n\n<!-- reconcile:begin -->\nold\n<!-- reconcile:end -->\n\n"
        "## Explanations\n\n### berlin/qecio_tracks_km\n\nBecause.\n"
    )
    comps = RC.load_comparisons(CFG)
    figs = [
        _fig("qecio_v2_10", "cycle_tracks_km", 679.471, "nuts3_DE300"),
        _fig("qecio_v2_10", "cycle_lanes_km", 10, "nuts3_DE300"),
        _fig("clean_cities_2025", "protected_km", 990),  # +1%: ok, needs no explanation
    ]
    gaps = RC.gaps_for(_results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={})
    RC.write_report(md, {"berlin": gaps})
    text = md.read_text()
    assert "old" not in text and "intro" in text and "Because." in text
    assert "qecio_tracks_km" in text.split("<!-- reconcile:end -->")[0]
    assert RC.missing_explanations(md, gaps) == ["berlin/qecio_lanes_km"]


def test_vienna_duplicate_rows_both_gap_and_scope_row_is_tagged():
    comps = RC.load_comparisons(CFG)
    figs = [
        _fig("clean_cities_2025", "protected_km", 384),
        _fig("clean_cities_2025", "protected_km", 625.1, "incl_traffic_calmed_restricted_access"),
    ]
    gaps = RC.gaps_for(_results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={})
    assert len(gaps) == 2
    pdf, web = gaps
    assert pdf.key == "berlin/cc_km" and "scope_mismatch" not in pdf.tags
    assert web.key == "berlin/cc_km@incl_traffic_calmed_restricted_access"
    assert "scope_mismatch" in web.tags and web.theirs == 625.1


def test_boundary_mismatch_tag_for_listed_city_and_source():
    comps = RC.load_comparisons(CFG)
    figs = [_fig("qecio_v2_10", "cycle_tracks_km", 679.471, "nuts3_DK011")]
    mm = {"qecio_v2_10": ["berlin"]}
    (g,) = RC.gaps_for(_results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch=mm)
    assert "boundary_mismatch" in g.tags
    cfg = RC.load_config(CFG)
    assert cfg["boundary_mismatch"] == {"qecio_v2_10": ["copenhagen"]}


def test_missing_ours_is_none_not_zero_and_never_flagged():
    comps = RC.load_comparisons(CFG)
    r = _results()
    r = RunResults(
        **{
            **r.__dict__,
            "metrics": [
                Metric(
                    preset="clean_cities_2025",
                    length_basis="per_side",
                    value=None,
                    numerator_km=0,
                    denominator_km=0,
                )
            ],
            "road_lengths": [],
            "tier_lengths": [],
        }
    )
    figs = [
        _fig("clean_cities_2025", "protected_share_pct", 17),
        _fig("clean_cities_2025", "network_km", 5350),
        _fig("clean_cities_2025", "protected_km", 925),
    ]
    gaps = RC.gaps_for(r, figs, comps, threshold=0.2, date_gap_days=365, mismatch={})
    assert len(gaps) == 3
    assert all(g.ours is None and g.gap_pct is None and not g.flagged for g in gaps)
    assert "n/a" in RC.render_block({"berlin": gaps})


def test_loaded_metric_names_exist_in_the_loaders():
    from velometer.sources.external import QECIO_COLUMNS

    comps = RC.load_comparisons(CFG)
    qecio = {c.metric_name for c in comps if c.sources == ("qecio_v2_10",)}
    assert qecio == set(QECIO_COLUMNS)
    csv = (CFG.parents[0] / "external" / "figures.csv").read_text()
    for c in comps:
        if "clean_cities_2025" in c.sources or "official" in c.sources:
            assert f",{c.metric_name}," in csv
