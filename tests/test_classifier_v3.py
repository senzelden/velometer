"""Classifier v3: v2 plus two rules (user decision 2026-10-03, M5 Task 14).

`cycleway[:left|:right|:both]=soft_lane` (CZ) and `cycleway[:left|:right|:both]=advisory` (SK, NO)
are advisory lanes: tier D, subtype advisory, as v2 gives `cycleway=lane` +
`cycleway:lane=advisory`. Everything v2 recognised classifies the same.
"""

from pathlib import Path

import pytest
import yaml

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

FIX = Path(__file__).parent / "fixtures"
V2 = load_classifier(default_config_dir() / "classifier" / "v2.yaml")
V3 = load_classifier(default_config_dir() / "classifier" / "v3.yaml")
LINE = ((13.40, 52.52), (13.41, 52.52))

# side form -> the road sides it tags (two-way road, so plain `cycleway` means both sides)
SIDE_FORMS = {
    "cycleway": {"left", "right"},
    "cycleway:left": {"left"},
    "cycleway:right": {"right"},
    "cycleway:both": {"left", "right"},
}
NEW_RULES = {"soft_lane": "D_soft_lane", "advisory": "D_advisory"}


def sides(tags: dict, cfg) -> dict:
    way = WayRecord(1, {"highway": "secondary", **tags}, LINE)
    return {c.side.side: c for c in classify_ways([way], cfg) if c.side.side != "self"}


@pytest.mark.parametrize("form", sorted(SIDE_FORMS))
@pytest.mark.parametrize("value", sorted(NEW_RULES))
def test_v3_reads_the_value_as_an_advisory_lane_on_each_side_form(value, form):
    tagged = SIDE_FORMS[form]
    before = sides({form: value}, V2)
    assert all(before[s].tier is None for s in tagged)  # the v2 gap this rule closes
    got = sides({form: value}, V3)
    for s in tagged:
        c = got[s]
        assert (c.tier, c.rule_id, c.subtype) == ("D", NEW_RULES[value], "advisory"), (form, s)
        assert c.attrs.get("advisory") is True
        assert "unknown_value" not in c.attrs
    untagged_v2 = sides({form: value}, V2)
    for s in {"left", "right"} - tagged:
        # the untagged side is none of this rule's business: it gets exactly what v2 gives it
        assert (s in got) == (s in untagged_v2), (form, s)
        if s in got:
            assert (got[s].tier, got[s].subtype, got[s].rule_id) == (
                untagged_v2[s].tier,
                untagged_v2[s].subtype,
                untagged_v2[s].rule_id,
            ), (form, s)


def test_v3_gives_the_same_tier_and_subtype_as_v2_lane_advisory():
    ref = sides({"cycleway:right": "lane", "cycleway:right:lane": "advisory"}, V2)["right"]
    for value in NEW_RULES:
        got = sides({"cycleway:right": value}, V3)["right"]
        assert (got.tier, got.subtype) == (ref.tier, ref.subtype) == ("D", "advisory")


def test_shared_busway_stays_unrecognised_in_v3():
    got = sides({"cycleway:right": "shared_busway"}, V3).get("right")
    assert got is None or got.tier is None, f"shared_busway must stay unrecognised, got {got}"


V3_ONLY_RULES = set(NEW_RULES.values())


def _golden_sides(cfg_old, cfg_new):
    """Yield (file, key, tags, old, new) for every classified side of every golden fixture."""
    cases = yaml.safe_load((FIX / "expected.yaml").read_text())["cases"]
    files = [FIX / "cases" / f"{c}.osm" for c in cases] + [FIX / "berlin_golden.osm"]
    files += sorted((FIX / "golden").glob("*.osm"))
    for f in files:
        ways = read_ways(f).ways
        old = {(c.side.way_id, c.side.side): c for c in classify_ways(ways, cfg_old)}
        new = {(c.side.way_id, c.side.side): c for c in classify_ways(ways, cfg_new)}
        assert new.keys() == old.keys(), f.name
        tags = {w.id: w.tags for w in ways}
        for k in old:
            yield f.name, k, tags[k[0]], old[k], new[k]


def test_v3_changes_only_sides_v2_left_untiered_and_only_to_new_rules():
    for name, k, _, a, b in _golden_sides(V2, V3):
        if (b.tier, b.subtype, b.rule_id) == (a.tier, a.subtype, a.rule_id):
            continue
        assert a.tier is None, (name, k, "v2 had tiered it", a.rule_id)
        assert b.rule_id in V3_ONLY_RULES, (name, k, "changed by another rule", b.rule_id)


def test_v3_tiers_every_golden_soft_lane_or_advisory_side_as_advisory():
    checked = 0
    for name, k, tags, _, b in _golden_sides(V2, V3):
        for form, tagged in SIDE_FORMS.items():
            if tags.get(form) in NEW_RULES and k[1] in tagged:
                checked += 1
                assert (b.tier, b.subtype) == ("D", "advisory"), (name, k, form, b.rule_id)
    assert checked, "no golden side carries soft_lane/advisory; the fixtures no longer test this"


def test_v3_is_v2_plus_exactly_the_two_rules():
    v2 = {r.id: r for r in V2.rules}
    v3 = {r.id: r for r in V3.rules}
    assert set(v3) - set(v2) == V3_ONLY_RULES and set(v2) <= set(v3)
    assert all(v3[i] == v2[i] for i in v2)
    assert V3.version == "v3"
