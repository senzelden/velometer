"""Classifier v2: the M3 classifier gaps are recognised; everything v1 recognised is unchanged."""

from pathlib import Path

import pytest
import yaml

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

FIX = Path(__file__).parent / "fixtures"
V1 = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
V2 = load_classifier(default_config_dir() / "classifier" / "v2.yaml")
LINE = ((13.40, 52.52), (13.41, 52.52))


def right_side(cycleway_right: str, cfg):
    way = WayRecord(1, {"highway": "secondary", "cycleway:right": cycleway_right}, LINE)
    (side,) = [c for c in classify_ways([way], cfg) if c.side.side == "right"]
    return side


@pytest.mark.parametrize(
    ("value", "rule", "subtype"),
    [
        ("use_sidepath", "X_use_sidepath", "use_sidepath"),
        ("shoulder", "X_shoulder", "shoulder"),
        ("crossing", "X_crossing", "crossing"),
        ("yes", "X_untyped", "untyped"),
    ],
)
def test_v2_recognises_each_gap_as_excluded(value, rule, subtype):
    assert right_side(value, V1).tier is None  # the v1 gap this rule closes
    got = right_side(value, V2)
    assert (got.tier, got.rule_id, got.subtype) == ("excluded", rule, subtype)
    assert "unknown_value" not in got.attrs


def test_v2_splits_comma_multi_values_and_keeps_rule_order():
    assert right_side("share_busway,track", V1).tier is None
    got = right_side("share_busway,track", V2)
    assert (got.tier, got.rule_id) == ("A", "A_track_side")  # track outranks the bus lane


def test_v1_still_splits_on_semicolon_only():
    assert V1.value_separators == [";"]
    assert right_side("share_busway;track", V1).rule_id == "A_track_side"


V2_ONLY_RULES = {"X_use_sidepath", "X_shoulder", "X_crossing", "X_untyped"}


def test_v2_changes_only_sides_v1_left_untiered_and_only_to_new_rules():
    cases = yaml.safe_load((FIX / "expected.yaml").read_text())["cases"]
    files = [FIX / "cases" / f"{c}.osm" for c in cases] + [FIX / "berlin_golden.osm"]
    changed = 0
    for f in files:
        ways = read_ways(f).ways
        old = {(c.side.way_id, c.side.side): c for c in classify_ways(ways, V1)}
        new = {(c.side.way_id, c.side.side): c for c in classify_ways(ways, V2)}
        assert new.keys() == old.keys(), f.name
        for k, a in old.items():
            b = new[k]
            if (b.tier, b.subtype, b.rule_id) == (a.tier, a.subtype, a.rule_id):
                continue
            assert a.tier is None and b.rule_id in V2_ONLY_RULES, (f.name, k, a.rule_id, b.rule_id)
            changed += 1
    assert changed == 1  # tests/fixtures/cases/unknown_value.osm uses cycleway:right=crossing


def test_v2_keeps_v1_rule_ids_used_as_legacy_markers():
    ids = {r.id for r in V2.rules}
    assert {"B_sidewalk_designated", "X_sidewalk_bicycle_permitted"} <= ids
    assert V2.version == "v2"
