from pathlib import Path

import pytest
from shapely import box

from velometer.config import default_config_dir, load_activity, load_classifier
from velometer.pipeline.drift import drift_diagnostics
from velometer.pipeline.geometry import Projector
from velometer.pipeline.measure import measure
from velometer.pipeline.read import read_ways

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
