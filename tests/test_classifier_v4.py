"""Classifier v4: the unified facility rule for standalone ways and the MTB exclusion
(user decisions 2026-10-04, M6 spec §2 decisions 3, 4, 9 and 10; §3)."""

import hashlib
import itertools
from pathlib import Path

import pytest
import yaml

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

FIX = Path(__file__).parent / "fixtures"
CLS = default_config_dir() / "classifier"
V3 = load_classifier(CLS / "v3.yaml")
V4 = load_classifier(CLS / "v4.yaml")
LINE = ((13.40, 52.52), (13.41, 52.52))

# sha256 of the released classifier files (ADR 0005: a released version never changes)
RELEASED = {
    "v1": "fb93883535f1cce6161ff32061f1400c8959456db302e7119302ce9738647e00",
    "v2": "01d47c9a4c7b5c6e17cbc2ca6aec8300e3fde4069c930aa69f1ba2b06621d292",
    "v3": "a0e50457415ff65a6902f8f5025f2d5097d4ad2fcc6b396b7bed1d5a3ad46ac3",
}

CASES = [
    # tags, v4 (tier, rule), v3 tier
    ({"highway": "cycleway"}, ("A", "A_cycle_only"), "A"),
    ({"highway": "cycleway", "foot": "no"}, ("A", "A_cycle_only"), "A"),
    ({"highway": "cycleway", "foot": "yes"}, ("B", "B_shared"), "A"),
    ({"highway": "cycleway", "foot": "permissive"}, ("B", "B_shared"), "A"),
    ({"highway": "cycleway", "foot": "designated"}, ("B", "B_shared"), "B"),
    (
        {"highway": "cycleway", "foot": "designated", "segregated": "yes"},
        ("A", "A_segregated"),
        "A",
    ),
    ({"highway": "cycleway", "foot": "yes", "segregated": "yes"}, ("A", "A_segregated"), "A"),
    ({"highway": "path", "bicycle": "designated"}, ("B", "B_shared"), "B"),
    ({"highway": "path", "bicycle": "designated", "segregated": "yes"}, ("A", "A_segregated"), "B"),
    (
        {"highway": "footway", "bicycle": "designated", "segregated": "yes"},
        ("A", "A_segregated"),
        "B",
    ),
    ({"highway": "path", "bicycle": "designated", "foot": "no"}, ("A", "A_cycle_only"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "designated"}, ("B", "B_shared"), "B"),
    ({"highway": "pedestrian", "bicycle": "designated"}, ("B", "B_shared"), "B"),
    (
        {"highway": "footway", "footway": "crossing", "bicycle": "designated", "segregated": "yes"},
        ("B", "B_crossing"),
        "B",
    ),
    (
        {"highway": "path", "bicycle": "designated", "foot": "no", "mtb:scale": "1"},
        ("excluded", "X_mtb_trail"),
        "A",
    ),
    (
        {"highway": "path", "bicycle": "designated", "foot": "no", "mtb:scale:imba": "2"},
        ("excluded", "X_mtb_trail"),
        "A",
    ),
    (
        {"highway": "path", "bicycle": "designated", "foot": "no", "mtb": "designated"},
        ("excluded", "X_mtb_trail"),
        "A",
    ),
    (
        {"highway": "path", "bicycle": "designated", "foot": "no", "mtb:type": "downhill"},
        ("excluded", "X_mtb_trail"),
        "A",
    ),
    (
        {"highway": "path", "bicycle": "designated", "foot": "no", "cycling": "mtb"},
        ("excluded", "X_mtb_trail"),
        "A",
    ),
    (
        {"highway": "path", "bicycle": "designated", "foot": "no", "mtb": "no"},
        ("A", "A_cycle_only"),
        "A",
    ),
    (
        {"highway": "path", "bicycle": "designated", "foot": "no", "surface": "dirt"},
        ("A", "A_cycle_only"),
        "A",
    ),
    # multi-valued tags
    ({"highway": "cycleway", "foot": "yes,designated"}, ("B", "B_shared"), "B"),
    ({"highway": "cycleway", "mtb": "yes"}, ("excluded", "X_mtb_trail"), "A"),
    ({"highway": "cycleway", "mtb": "permissive"}, ("excluded", "X_mtb_trail"), "A"),
    (
        {"highway": "path", "bicycle": "designated", "mtb:scale": "1", "mtb": "no"},
        ("excluded", "X_mtb_trail"),
        "B",
    ),
    # X_mtb_trail is limited to path/cycleway/footway (spec §3.3)
    (
        {"highway": "pedestrian", "bicycle": "designated", "mtb:scale": "1"},
        ("B", "B_shared"),
        "B",
    ),
    # v3 gave a foot=no footway B (A_path_cycle_only covered `path` only)
    ({"highway": "footway", "bicycle": "designated", "foot": "no"}, ("A", "A_cycle_only"), "B"),
    ({"highway": "cycleway", "segregated": "no"}, ("A", "A_cycle_only"), "A"),
    ({"highway": "cycleway", "foot": "yes;designated"}, ("B", "B_shared"), "B"),
    (
        {"highway": "path", "bicycle": "designated", "segregated": "yes;no"},
        ("A", "A_segregated"),
        "B",
    ),
]


def standalone(tags: dict, cfg):
    (c,) = classify_ways([WayRecord(1, tags, LINE)], cfg)
    return c


@pytest.mark.parametrize(("tags", "v4", "v3"), CASES)
def test_v4_standalone_way(tags, v4, v3):
    got = standalone(tags, V4)
    assert (got.tier, got.rule_id) == v4
    assert standalone(tags, V3).tier == v3


def test_retagging_cycleway_to_path_keeps_the_tier():
    for foot, seg in itertools.product((None, "no", "yes", "designated"), (None, "yes", "no")):
        extra = {k: v for k, v in (("foot", foot), ("segregated", seg)) if v}
        cyc = standalone({"highway": "cycleway", "bicycle": "designated", **extra}, V4).tier
        path = standalone({"highway": "path", "bicycle": "designated", **extra}, V4).tier
        if foot is None and seg != "yes":
            # decision 9: no foot tag means pedestrians may use a path, but a cycleway is A
            assert (cyc, path) == ("A", "B"), (foot, seg)
        else:
            assert cyc == path, (foot, seg, cyc, path)


def test_every_v3_road_side_rule_classifies_the_same():
    cases = yaml.safe_load((FIX / "expected.yaml").read_text())["cases"]
    files = [FIX / "cases" / f"{c}.osm" for c in cases] + [FIX / "berlin_golden.osm"]
    files += sorted((FIX / "golden").glob("*.osm"))
    checked = 0
    for f in files:
        ways = read_ways(f).ways
        old = {(c.side.way_id, c.side.side): c for c in classify_ways(ways, V3)}
        new = {(c.side.way_id, c.side.side): c for c in classify_ways(ways, V4)}
        assert new.keys() == old.keys(), f.name
        for k, a in old.items():
            if a.side.side == "self":
                continue
            checked += 1
            b = new[k]
            assert (b.side.side, b.tier, b.subtype) == (a.side.side, a.tier, a.subtype), (f.name, k)
    assert checked, "no road-side fixture was compared"


def test_v4_road_side_rules_are_v3s():
    v3 = {r.id: r for r in V3.rules if r.applies_to == "road_side"}
    v4 = {r.id: r for r in V4.rules if r.applies_to == "road_side"}
    assert v4 == v3
    assert [r.id for r in V4.rules if r.applies_to == "road_side"] == list(v3)
    assert V4.version == "v4"


def test_v1_to_v3_unchanged():
    for version, digest in RELEASED.items():
        assert hashlib.sha256((CLS / f"{version}.yaml").read_bytes()).hexdigest() == digest
