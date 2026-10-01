import warnings
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

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


def check_golden(ways: list[dict], observed: dict[int, set[tuple]]) -> None:
    """Assert confirmed ways; skip if none is confirmed, else warn with the unconfirmed count."""
    confirmed = [w for w in ways if w["confirmed"]]
    unconfirmed = len(ways) - len(confirmed)
    if not confirmed:
        pytest.skip(f"0/{len(ways)} golden ways confirmed yet (awaiting review)")
    if unconfirmed:
        warnings.warn(
            f"{unconfirmed}/{len(ways)} golden ways unconfirmed (skipped)",
            UserWarning,
            stacklevel=2,
        )
    for w in confirmed:
        want = {(p["side"], p["tier"], p["rule"]) for p in w["proposed"]}
        assert observed[w["way_id"]] == want, (w["way_id"], w["name"])


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
