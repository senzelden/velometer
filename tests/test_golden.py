from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from tests.golden_util import check_country_golden, check_golden
from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways

FIX = Path(__file__).parent / "fixtures"
GOLDEN = yaml.safe_load((FIX / "berlin_golden.yaml").read_text())
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")


def _observed() -> dict[int, set[tuple]]:
    out: dict[int, set[tuple]] = defaultdict(set)
    for c in classify_ways(read_ways(FIX / "berlin_golden.osm").ways, CFG):
        if c.tier is not None:
            out[c.side.way_id].add((c.side.side, c.tier, c.rule_id))
    return out


def test_golden_set_is_large_enough_and_covers_named_streets():
    groups = {w["group"] for w in GOLDEN["ways"]}
    assert len(GOLDEN["ways"]) >= 40
    assert {
        "kantstrasse",
        "ollenhauerstrasse",
        "unter_den_eichen",
        "karl_marx_allee",
        "fahrradstrasse",
        "hochbord_shared",
    } <= groups


def test_every_golden_way_is_in_the_osm_fixture():
    ids = {w.id for w in read_ways(FIX / "berlin_golden.osm").ways}
    assert {w["way_id"] for w in GOLDEN["ways"]} <= ids


def test_confirmed_ways_match_classifier():
    check_golden(GOLDEN["ways"], _observed())


def test_partial_signoff_reports_unconfirmed_count():
    prop = [{"side": "self", "tier": "A", "rule": "A_cycleway"}]
    ways = [
        {"way_id": 1, "name": "x", "proposed": prop, "confirmed": True},
        {"way_id": 2, "name": "y", "proposed": prop, "confirmed": False},
        {"way_id": 3, "name": "z", "proposed": prop, "confirmed": False},
    ]
    with pytest.warns(UserWarning, match="2/3 golden ways unconfirmed"):
        check_golden(ways, {1: {("self", "A", "A_cycleway")}})


def _ways_with_a_v3_verdict():
    a = [{"side": "self", "tier": "A", "rule": "A_cycleway"}]
    d = [{"side": "right", "tier": "D", "rule": "D_soft_lane"}]
    return [
        {"way_id": 1, "name": "x", "proposed": a, "confirmed": True},
        {"way_id": 2, "name": "y", "proposed": d, "confirmed": True, "min_classifier": "v3"},
    ]


def test_a_way_expecting_a_newer_classifier_is_skipped_by_name_not_failed():
    with pytest.raises(pytest.skip.Exception, match=r"XX: way\(s\) 2 expect classifier v3"):
        check_country_golden(
            "XX", _ways_with_a_v3_verdict(), {1: {("self", "A", "A_cycleway")}}, "v2"
        )


def test_the_other_ways_are_still_asserted_before_the_skip():
    with pytest.raises(AssertionError):
        check_country_golden("XX", _ways_with_a_v3_verdict(), {1: {("self", "E", "E_bus")}}, "v2")


def test_a_way_is_asserted_once_the_classifier_reaches_its_min_classifier():
    observed = {1: {("self", "A", "A_cycleway")}, 2: set()}
    with pytest.raises(AssertionError):
        check_country_golden("XX", _ways_with_a_v3_verdict(), observed, "v3")
    observed[2] = {("right", "D", "D_soft_lane")}
    check_country_golden("XX", _ways_with_a_v3_verdict(), observed, "v3")
