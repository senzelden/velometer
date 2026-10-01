from pathlib import Path

import pytest
import yaml

from velometer.config import ClassifierConfig, default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

FIX = Path(__file__).parent / "fixtures"
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
EXPECTED = yaml.safe_load((FIX / "expected.yaml").read_text())["cases"]


def run_case(case: str, cfg: ClassifierConfig = CFG) -> list:
    return classify_ways(read_ways(FIX / "cases" / f"{case}.osm").ways, cfg)


def observed(case: str, cfg: ClassifierConfig = CFG) -> set[tuple]:
    return {(c.side.way_id, c.side.side, c.tier, c.rule_id) for c in run_case(case, cfg)}


def test_every_case_file_has_an_expectation_and_vice_versa():
    files = {p.stem for p in (FIX / "cases").glob("*.osm")}
    assert files == set(EXPECTED)
    assert len(files) >= 34


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_case_sides_tiers_and_rules(case):
    want = {(s["way"], s["side"], s["tier"], s["rule"]) for s in EXPECTED[case]["sides"]}
    got = observed(case)
    # sides with tier None are only compared when the expectation lists them
    got = {g for g in got if g[2] is not None or g in want}
    assert got == want


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_case_attrs(case):
    by_key = {(c.side.way_id, c.side.side): c for c in run_case(case)}
    for s in EXPECTED[case]["sides"]:
        attrs = by_key[(s["way"], s["side"])].attrs
        for k, v in s.get("attrs", {}).items():
            assert attrs.get(k) == v, (case, s["side"], k)


def _without(rule_id: str) -> ClassifierConfig:
    rules = [r for r in CFG.rules if r.id != rule_id]
    assert len(rules) == len(CFG.rules) - 1, rule_id
    return CFG.model_copy(update={"rules": rules})


# Red-proofing: each core rule is load-bearing for at least the named fixture.
@pytest.mark.parametrize(
    ("rule_id", "case"),
    [
        ("A_cycleway", "A_cycleway_basic"),
        ("A_track_side", "A_track_both"),
        ("B_path_segregated", "B_footway_segregated"),
        ("B_cycleway_foot", "B_cycleway_foot_shared"),
        ("C_lane_physical", "C_lane_kerb"),
        ("D_lane_advisory", "D_lane_advisory"),
        ("E_bus", "E_bus"),
        ("E_cycle_street", "E_bicycle_road"),
        ("X_separate", "X_separate"),
        ("X_private", "X_private_cycleway"),
        ("X_road_private", "road_private"),
        ("B_sidewalk_designated", "legacy_sidewalk_designated"),
    ],
)
def test_rule_is_load_bearing(rule_id, case):
    assert observed(case, _without(rule_id)) != observed(case)


def test_rule_order_matters_track_before_sidewalk():
    # a road side with both a track and a designated sidewalk is a track (tier A)
    way = WayRecord(
        10,
        {"highway": "primary", "cycleway:right": "track", "sidewalk:right:bicycle": "designated"},
        ((13.4, 52.5), (13.41, 52.5)),
    )
    (c,) = classify_ways([way], CFG)
    assert (c.tier, c.rule_id) == ("A", "A_track_side")
