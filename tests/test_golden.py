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


def test_confirmed_ways_match_classifier():
    confirmed = [w for w in GOLDEN["ways"] if w["confirmed"]]
    if not confirmed:
        pytest.skip(f"0/{len(GOLDEN['ways'])} golden ways confirmed yet (awaiting review)")
    obs = _observed()
    for w in confirmed:
        want = {(p["side"], p["tier"], p["rule"]) for p in w["proposed"]}
        assert obs[w["way_id"]] == want, (w["way_id"], w["name"])
