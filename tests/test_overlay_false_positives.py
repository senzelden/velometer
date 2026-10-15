"""The class decision of scripts/overlay_false_positives.py (the M8 overlay log's classes)."""

import pytest
from shapely import LineString

from tests.helpers import load_script

fp = load_script("scripts/overlay_false_positives.py")


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((1.5, False, 0.0, None), "beyond_network_end"),  # more than 1 m past every end
        ((1.5, True, 0.0, None), "class_boundary"),
        ((1.0, False, 0.0, None), "along"),  # at most 1 m past an end still runs alongside
        ((-1.0, False, 31.0, (0.0, 0.0)), "junction_crossing"),
        ((-1.0, False, 0.0, (31.0, 5.0)), "parallel_or_crossing_street"),
        ((-1.0, False, 0.0, (10.0, 15.5)), "parallel_or_crossing_street"),
        ((-1.0, False, 30.0, (30.0, 15.0)), "along"),  # the thresholds are inclusive
        ((-1.0, False, 0.0, None), "along"),  # beside no carriageway
    ],
)
def test_piece_class_applies_the_logged_classes_in_order(args, expected):
    assert fp.piece_class(*args) == expected


# An L-shaped network: one edge east to (100, 0), the next north from there (a joint of two edges
# turning 90 degrees); the way-side follows it 8 m outside the corner.
_L = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (100, 100)])]
_PARAMS = fp.CornerParams(buffer_m=12.0, max_angle_deg=30.0)


@pytest.mark.parametrize(
    ("lines", "piece", "expected"),
    [
        (_L, [(100, -8), (108, -8)], True),  # outer corner, 8 m off, 4 m past the first edge
        (_L, [(100, 8), (108, 8)], False),  # inside the turn: the crossing street's far side
        (_L[:1], [(100, -8), (108, -8)], False),  # the same piece past a straight line's end
        (_L[:1], [(135, -8), (145, -8)], False),  # 40 m past a straight line's end
        (_L, [(116, -8), (124, -8)], False),  # 20 m past the corner: beyond the distance bound
        (_L, [(104, -12), (104, -4)], True),  # the north edge's outer corner, running north
        (_L, [(101, -11), (107, -5)], False),  # at the outer corner, 45 degrees off both edges
    ],
)
def test_outer_corner_is_past_a_turn_on_its_outer_side(lines, piece, expected):
    assert fp.outer_corner(LineString(piece), lines, _PARAMS) is expected
