from datetime import date
from pathlib import Path

import pytest

from velometer import reconcile as RC
from velometer.config import load_classifier, load_presets
from velometer.db import RunResults
from velometer.models import ExternalFigure, Metric, RoadLength, TierLength

CFG = Path(__file__).resolve().parents[1] / "config" / "reconcile.yaml"
PRESETS = load_presets(
    CFG.parent / "presets.yaml", load_classifier(CFG.parent / "classifier" / "v1.yaml")
)


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


def _rep(gaps, run_id=1, city="berlin"):
    return RC.CityReport(city, run_id, f"run {run_id}", gaps)


def test_ours_value_sums_tiers_with_subtype_and_exclude():
    comps = {c.id: c for c in RC.load_comparisons(CFG)}
    r = _results()
    assert (
        RC.ours_value(r, comps["cc_km"].ours, PRESETS) == 1000
    )  # A 600 + B 300 + B/segregated 100
    assert RC.ours_value(r, comps["qecio_tracks_km"].ours, PRESETS) == 400  # A 300 + B/seg 100
    assert RC.ours_value(r, comps["qecio_shared_km"].ours, PRESETS) == 150  # B minus B/segregated
    assert RC.ours_value(r, comps["cc_ratio"].ours, PRESETS) == 20.0


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
        for g in RC.gaps_for(
            _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
        )
        if "~" not in g.key  # the informational other-basis rows have their own tests
    }
    assert not gaps["cc_km"].flagged
    assert gaps["qecio_tracks_km"].flagged  # 400 vs 679 = -41%
    assert "date_gap" in gaps["qecio_tracks_km"].tags
    assert gaps["cc_km"].gap_pct == pytest.approx((1000 - 925) / 925)


def test_informational_comparisons_are_never_flagged():
    comps = RC.load_comparisons(CFG)
    figs = [_fig("official", "new_cycle_infra_km", 21.2)]
    (g,) = RC.gaps_for(
        _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
    )
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
    gaps = RC.gaps_for(
        _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
    )
    RC.write_report(md, {"berlin": _rep(gaps)})
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
    gaps = RC.gaps_for(
        _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
    )
    pdf, web = (g for g in gaps if "~" not in g.key)
    assert len(gaps) == 4  # each also has its informational other-basis row
    assert pdf.key == "berlin/cc_km" and "scope_mismatch" not in pdf.tags
    assert web.key == "berlin/cc_km@incl_traffic_calmed_restricted_access"
    assert "scope_mismatch" in web.tags and web.theirs == 625.1


def test_boundary_mismatch_tag_for_listed_city_and_source():
    comps = RC.load_comparisons(CFG)
    figs = [_fig("qecio_v2_10", "cycle_tracks_km", 679.471, "nuts3_DK011")]
    mm = {"qecio_v2_10": ["berlin"]}
    (g,) = RC.gaps_for(
        _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch=mm, presets=PRESETS
    )
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
    gaps = RC.gaps_for(
        r, figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
    )
    by = {g.comparison: g for g in gaps if "~" not in g.key}
    assert len(by) == 3
    # a done run with no tier rows is a real 0 km: flagged at -100%, not n/a
    assert by["cc_km"].ours == 0.0 and by["cc_km"].flagged
    assert by["cc_km"].gap_pct == pytest.approx(-1.0)
    # missing preset value / road class stay n/a and are never flagged
    for k in ("cc_ratio", "cc_network_km"):
        assert by[k].ours is None and by[k].gap_pct is None and not by[k].flagged
    assert "n/a" in RC.render_block({"berlin": _rep(gaps)})


def test_loaded_metric_names_exist_in_the_loaders():
    from velometer.sources.external import QECIO_COLUMNS

    comps = RC.load_comparisons(CFG)
    qecio = {c.metric_name for c in comps if c.sources == ("qecio_v2_10",)}
    assert qecio == set(QECIO_COLUMNS)
    csv = (CFG.parents[0] / "external" / "figures.csv").read_text()
    for c in comps:
        if "clean_cities_2025" in c.sources or "official" in c.sources:
            assert f",{c.metric_name}," in csv


def test_write_report_is_idempotent(tmp_path):
    md = tmp_path / "r.md"
    md.write_text("# R\n\n<!-- reconcile:begin -->\nold\n<!-- reconcile:end -->\n\n## E\n")
    comps = RC.load_comparisons(CFG)
    figs = [_fig("clean_cities_2025", "protected_km", 925)]
    gaps = RC.gaps_for(
        _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
    )
    RC.write_report(md, {"berlin": _rep(gaps)})
    once = md.read_text()
    RC.write_report(md, {"berlin": _rep(gaps)})
    assert md.read_text() == once


RUN = {
    "id": 6,
    "osm_timestamp": "2026-09-30T20:22:42Z",
    "classifier_version": "v1",
    "classifier_parameters": '{"plain_cycleway_on_oneway":"traffic_side"}',
    "config_sha256": "ab" * 32,
    "git_commit": "0123456789abcdef-dirty",
    "boundary_kind": "lau",
    "boundary_sha256": "cd" * 32,
}


def test_provenance_line_names_run_inputs_and_source_retrieval():
    q = _fig("qecio_v2_10", "main_roads_km", 2149.6, "nuts3_DE300")
    q = q.model_copy(update={"note": "NUTS3 DE300; file md5 " + "e" * 32})
    line = RC.provenance_line(RUN, [_fig("clean_cities_2025", "protected_km", 925), q])
    for part in (
        "run 6",
        "OSM 2026-09-30T20:22:42Z",
        "classifier v1",
        "traffic_side",
        "abababababab",
        "0123456-dirty",  # a dirty tree is never shown as a clean commit
        "lau `cdcdcdcdcdcd`",
        "clean_cities_2025 retrieved 2026-10-01",
        "qecio_v2_10 retrieved 2026-10-01, file md5 " + "e" * 32,
    ):
        assert part in line, part
    block = RC.render_block({"berlin": RC.CityReport("berlin", 6, line, [])})
    assert f"Provenance: {line}" in block


def test_explained_against_marker_must_name_the_latest_run(tmp_path):
    md = tmp_path / "r.md"
    reports = {"berlin": _rep([], 6), "paris": _rep([], 7, "paris")}
    md.write_text("## Explanations\n")
    assert len(RC.unexplained_runs(md, reports)) == 2  # no marker at all
    md.write_text("## Explanations\n\n" + RC.explained_against_marker(reports) + "\n")
    assert RC.explained_against(md) == {"berlin": 6, "paris": 7}
    assert RC.unexplained_runs(md, reports) == []
    newer = {**reports, "paris": _rep([], 9, "paris")}
    assert RC.unexplained_runs(md, newer) == [
        "paris: explanations written against run 7, latest is 9"
    ]


def test_stale_explanation_headings_are_reported_per_checked_city(tmp_path):
    md = tmp_path / "r.md"
    md.write_text("### berlin/cc_km\n\nx\n\n### berlin/old_key\n\ny\n\n### paris/cc_km\n")
    comps = RC.load_comparisons(CFG)
    figs = [_fig("clean_cities_2025", "protected_km", 500)]  # 1000 vs 500: flagged
    gaps = RC.gaps_for(
        _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
    )
    assert RC.stale_explanations(md, gaps, {"berlin"}) == ["berlin/old_key"]


def test_required_comparisons_without_an_external_row_are_missing():
    comps = RC.load_comparisons(CFG)
    required = {c.id for c in comps if c.required}
    assert required == {"cc_ratio", "qecio_main_km", "bnk_network_km"}
    figs = [_fig("clean_cities_2025", "protected_share_pct", 17)]
    gaps = RC.gaps_for(
        _results(), figs, comps, threshold=0.2, date_gap_days=365, mismatch={}, presets=PRESETS
    )
    assert RC.missing_required({"berlin": _rep(gaps)}, comps) == [
        "berlin/qecio_main_km",
        "berlin/bnk_network_km",
    ]


def _berlin_like_results():
    """Berlin's reconciliation numbers: per_side A+B 1,557.9 km, qecio_weighted 918.3 km."""
    t = lambda tier, km, basis: TierLength(  # noqa: E731
        tier=tier, subtype=None, length_basis=basis, length_km=km, n_ways=1
    )
    m = lambda basis, num: Metric(  # noqa: E731
        preset="clean_cities_2025",
        length_basis=basis,
        value=100 * num / 5350,
        numerator_km=num,
        denominator_km=5350,
    )
    return RunResults(
        run_id=1,
        city_id="berlin",
        osm_timestamp="2026-09-30T20:22:42Z",
        tier_lengths=[t("A", 1557.9, "per_side"), t("A", 918.3, "qecio_weighted")],
        road_lengths=[],
        metrics=[m("per_side", 1557.9), m("qecio_weighted", 918.3)],
        completeness=[],
    )


def _cc_gaps(basis):
    figs = [
        _fig("clean_cities_2025", "protected_km", 925),
        _fig("clean_cities_2025", "protected_share_pct", 17),
    ]
    return {
        g.key: g
        for g in RC.gaps_for(
            _berlin_like_results(),
            figs,
            RC.load_comparisons(CFG),
            presets=PRESETS.with_parameters(clean_cities_basis=basis),
            threshold=0.2,
            date_gap_days=365,
            mismatch={},
        )
    }


def test_selecting_qecio_weighted_flips_the_cc_flags_and_lists_the_other_basis_as_info():
    per_side = _cc_gaps("per_side")
    assert per_side["berlin/cc_km"].flagged and per_side["berlin/cc_km"].ours == 1557.9
    other = per_side["berlin/cc_km~qecio_weighted"]
    assert other.informational and not other.flagged and other.ours == 918.3
    assert other.gap_pct == pytest.approx((918.3 - 925) / 925)

    weighted = _cc_gaps("qecio_weighted")
    assert not weighted["berlin/cc_km"].flagged and weighted["berlin/cc_km"].ours == 918.3
    back = weighted["berlin/cc_km~per_side"]
    assert back.informational and not back.flagged and back.ours == 1557.9
    # the preset-valued comparison follows the parameter too
    assert per_side["berlin/cc_ratio"].ours == pytest.approx(100 * 1557.9 / 5350)
    assert weighted["berlin/cc_ratio"].ours == pytest.approx(100 * 918.3 / 5350)
    assert "berlin/cc_ratio~per_side" in weighted
    # a comparison on a fixed basis gets no other-basis row
    assert not [k for k in per_side if k.startswith("berlin/qecio_tracks_km")]


def test_info_rows_are_never_demanded_as_explanations(tmp_path):
    md = tmp_path / "r.md"
    md.write_text("## Explanations\n\n### berlin/cc_km\n\nx\n\n### berlin/cc_ratio\n\ny\n")
    gaps = list(_cc_gaps("per_side").values())
    assert RC.missing_explanations(md, gaps) == []  # flagged keys explained; ~ rows are info
    assert RC.stale_explanations(md, gaps, {"berlin"}) == []


def test_provenance_line_states_the_clean_cities_basis():
    from velometer.config import PresetParameters

    line = RC.provenance_line(RUN, [], PresetParameters(clean_cities_basis="qecio_weighted"))
    assert "clean_cities_basis=qecio_weighted" in line
    assert "clean_cities_basis" not in RC.provenance_line(RUN, [])


def test_the_shipped_report_has_exactly_one_parseable_explained_against_marker():
    report = Path(__file__).resolve().parents[1] / "docs" / "reconciliation.md"
    assert len(RC.EXPLAINED_AGAINST.findall(report.read_text())) == 1  # prose must not mimic it
    assert RC.explained_against(report)  # parses, and names at least one city
