from dataclasses import replace
from pathlib import Path

import pytest
from shapely import box

from velometer.config import default_config_dir, load_activity, load_classifier
from velometer.pipeline.drift import drift_diagnostics
from velometer.pipeline.geometry import Projector
from velometer.pipeline.measure import measure
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import Classified, WayRecord, WaySide

CASES = Path(__file__).parent / "fixtures" / "cases"
CLS = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
ACT = load_activity(default_config_dir() / "activity.yaml")


def run(case: str, boundary=None):
    ways = read_ways(CASES / f"{case}.osm").ways
    result = measure(ways, CLS, 25833, boundary)
    return drift_diagnostics(result, ways, ACT), result


@pytest.mark.parametrize(
    "case", ["legacy_opposite_track", "legacy_opposite_lane", "legacy_sidewalk_designated"]
)
def test_legacy_cases_have_legacy_km(case):
    d, result = run(case)
    assert d["legacy_km"] > 0
    assert d["unrecognised_cycling_km"] == 0


def test_legacy_sidewalk_two_sides_count_each_side():
    d, result = run("legacy_sidewalk_yes")
    assert d["legacy_km"] == pytest.approx(2 * result.way_lengths[10])


def test_modern_track_is_not_legacy():
    d, _ = run("A_track_right_twoway")
    assert d["legacy_km"] == 0


def test_unknown_value_is_unrecognised_cycling():
    d, result = run("unknown_value")
    assert d["unrecognised_cycling_km"] == pytest.approx(result.way_lengths[10])
    assert d["legacy_km"] == 0


def test_km_outside_boundary_contribute_nothing():
    ways = read_ways(CASES / "legacy_opposite_track.osm").ways
    proj = Projector(25833)
    x, y = proj.line(ways[0].coords).coords[0]
    far = box(x + 50_000, y + 50_000, x + 51_000, y + 51_000)
    for case in ("legacy_opposite_track", "unknown_value"):
        d, _ = run(case, far)
        assert d == {"legacy_km": 0.0, "unrecognised_cycling_km": 0.0}


def test_way_lengths_are_clipped_km_per_way():
    _, full = run("legacy_opposite_track")
    assert full.way_lengths[10] == pytest.approx(1.0, rel=0.02)


COORDS = ((13.4, 52.5), (13.4147, 52.5))


def synthetic(
    tags: dict[str, str],
    tier: str | None,
    rule_id: str | None,
    kind: str = "road_side",
    attrs: dict | None = None,
):
    """A measured one-way city whose single classified side is replaced by the given one."""
    way = WayRecord(10, tags, COORDS)
    result = measure([way], CLS, 25833)
    side = WaySide(10, "right", kind, tags, COORDS)
    classified = [Classified(side, tier, None, rule_id, attrs or {})]
    return drift_diagnostics(replace(result, classified=classified), [way], ACT)


ROAD = {"highway": "residential"}


def test_legacy_prefix_is_matched_per_semicolon_part():
    d = synthetic({**ROAD, "cycleway": "lane;opposite_lane"}, "D", "D_lane")
    assert d["legacy_km"] > 0


def test_legacy_prefix_must_start_the_value():
    d = synthetic({**ROAD, "cycleway": "no_opposite"}, "D", "D_lane")
    assert d["legacy_km"] == 0


def test_legacy_tagged_side_without_tier_is_not_legacy():
    d = synthetic({**ROAD, "cycleway": "opposite_track"}, None, None)
    assert d["legacy_km"] == 0
    assert d["unrecognised_cycling_km"] > 0


def test_tier_none_side_without_cycling_tags_is_not_unrecognised():
    d = synthetic(ROAD, None, None)
    assert d == {"legacy_km": 0.0, "unrecognised_cycling_km": 0.0}


@pytest.mark.parametrize("highway", ["footway", "path", "track"])
def test_unmatched_standalone_with_bicycle_yes_is_not_unrecognised(highway):
    tags = {"highway": highway, "bicycle": "yes"}
    d = synthetic(tags, None, None, kind="standalone")
    assert d == {"legacy_km": 0.0, "unrecognised_cycling_km": 0.0}


def test_road_side_with_unknown_cycleway_value_is_unrecognised():
    tags = {**ROAD, "cycleway": "bogus"}
    d = synthetic(tags, None, None, attrs={"unknown_value": "bogus"})
    assert d["unrecognised_cycling_km"] > 0
    # the unknown_value clause alone suffices, whatever the tier
    d = synthetic(tags, "D", "D_lane", attrs={"unknown_value": "bogus"})
    assert d["unrecognised_cycling_km"] > 0


def _classified(kind, tier, attrs=None):
    return Classified(
        WaySide(1, "right", kind, {}, ((0.0, 0.0), (0.0, 1.0))), tier, None, None, attrs or {}
    )


def test_unmatched_road_side_is_untiered_or_unknown_value_on_a_road_only():
    from velometer.pipeline.drift import is_unmatched_road_side

    assert is_unmatched_road_side(_classified("road_side", None))
    assert is_unmatched_road_side(_classified("road_side", "A", {"unknown_value": "x"}))
    assert not is_unmatched_road_side(_classified("road_side", "A"))
    assert not is_unmatched_road_side(_classified("standalone", None))
    assert not is_unmatched_road_side(_classified("road_side", "excluded"))
