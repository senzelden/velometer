import pytest

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.explode import explode
from velometer.pipeline.types import WayRecord

RC = load_classifier(default_config_dir() / "classifier" / "v1.yaml").road_classes
LINE = ((13.40, 52.5), (13.41, 52.5))


def sides(tags: dict) -> dict:
    return {(s.side, s.kind): s for s in explode(WayRecord(1, tags, LINE), RC)}


def test_standalone_way_yields_self():
    out = sides({"highway": "cycleway", "foot": "designated"})
    assert list(out) == [("self", "standalone")]
    assert out[("self", "standalone")].tags["foot"] == "designated"


def test_no_highway_yields_nothing():
    assert sides({"building": "yes"}) == {}


def test_road_without_cycling_tags_yields_nothing():
    assert sides({"highway": "primary"}) == {}


def test_both_applies_to_each_side_and_carries_road_tags():
    out = sides({"highway": "primary", "cycleway:both": "lane", "name": "X", "access": "yes"})
    assert set(out) == {("left", "road_side"), ("right", "road_side")}
    right = out[("right", "road_side")].tags
    assert right["cycleway"] == "lane"
    assert right["road:highway"] == "primary" and right["road:name"] == "X"


def test_side_beats_both_beats_plain():
    out = sides(
        {
            "highway": "secondary",
            "cycleway": "lane",
            "cycleway:both": "track",
            "cycleway:left": "no",
        }
    )
    assert out[("left", "road_side")].tags["cycleway"] == "no"
    assert out[("right", "road_side")].tags["cycleway"] == "track"


def test_subkeys_resolve_per_level_and_join_values():
    out = sides(
        {
            "highway": "primary",
            "cycleway:right": "lane",
            "cycleway:right:separation:left": "kerb",
            "cycleway:right:separation:right": "bollard",
            "cycleway:both:lane": "exclusive",
            "cycleway:right:lane": "advisory",
        }
    )
    tags = out[("right", "road_side")].tags
    assert tags["cycleway:separation"] == "bollard;kerb"
    assert tags["cycleway:lane"] == "advisory"


def test_plain_cycleway_on_oneway_road_is_right_only():
    out = sides({"highway": "tertiary", "oneway": "yes", "cycleway": "lane"})
    assert set(out) == {("right", "road_side")}


@pytest.mark.parametrize("value", ["opposite_track", "opposite_lane"])
def test_legacy_opposite_goes_left_with_contraflow(value):
    out = sides({"highway": "residential", "oneway": "yes", "cycleway": value})
    assert set(out) == {("left", "road_side")}
    left = out[("left", "road_side")]
    assert left.contraflow is True
    assert left.tags["cycleway"] == value.removeprefix("opposite_")


def test_plain_opposite_yields_nothing():
    assert sides({"highway": "residential", "oneway": "yes", "cycleway": "opposite"}) == {}


def test_sidewalk_bicycle_legacy_side():
    out = sides({"highway": "primary", "sidewalk:right:bicycle": "designated"})
    assert set(out) == {("right", "road_side")}
    assert out[("right", "road_side")].tags["sidewalk_bicycle"] == "designated"


def test_bicycle_road_adds_self_side_plus_side_tags():
    out = sides({"highway": "residential", "bicycle_road": "yes", "cycleway:right": "lane"})
    assert set(out) == {("self", "standalone"), ("right", "road_side")}


def test_oneway_value_with_mixed_parts_is_oneway_if_any_part_yes():
    out = sides({"highway": "tertiary", "oneway": "yes;no", "cycleway": "lane"})
    assert set(out) == {("right", "road_side")}


def test_cycle_street_key_value_with_mixed_parts_creates_self_if_any_part_yes():
    out = sides(
        {"highway": "residential", "bicycle_road": "yes;designated", "cycleway:right": "lane"}
    )
    assert set(out) == {("self", "standalone"), ("right", "road_side")}


def test_plain_cycleway_applies_to_both_sides_on_non_oneway_road():
    out = sides({"highway": "secondary", "cycleway": "lane"})
    assert set(out) == {("left", "road_side"), ("right", "road_side")}
    assert out[("left", "road_side")].tags["cycleway"] == "lane"
    assert out[("right", "road_side")].tags["cycleway"] == "lane"


def test_traffic_side_separation_right_side_uses_left_directed_value():
    out = sides(
        {
            "highway": "primary",
            "cycleway:right": "lane",
            "cycleway:right:separation:left": "solid_line",
            "cycleway:right:separation:right": "parking_lane",
        }
    )
    tags = out[("right", "road_side")].tags
    assert tags["cycleway:separation:traffic"] == "solid_line"
    assert tags["cycleway:separation"] == "parking_lane;solid_line"


def test_traffic_side_separation_left_side_uses_right_directed_value_and_undirected():
    out = sides(
        {
            "highway": "primary",
            "cycleway:left": "lane",
            "cycleway:left:separation": "bollard",
            "cycleway:left:separation:right": "kerb",
            "cycleway:left:separation:left": "parking_lane",
        }
    )
    assert out[("left", "road_side")].tags["cycleway:separation:traffic"] == "bollard;kerb"


def test_curbside_only_separation_gives_no_traffic_separation():
    out = sides(
        {"highway": "primary", "cycleway:right": "lane", "cycleway:right:separation:right": "kerb"}
    )
    assert "cycleway:separation:traffic" not in out[("right", "road_side")].tags


def test_separately_mapped_sidewalk_does_not_emit_sidewalk_bicycle():
    out = sides(
        {
            "highway": "primary",
            "sidewalk:right": "separate",
            "sidewalk:right:bicycle": "designated",
        }
    )
    assert out == {}
