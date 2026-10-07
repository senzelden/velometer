"""The class decision of scripts/overlay_false_positives.py (the M8 overlay log's classes)."""

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "overlay_false_positives.py"
_spec = importlib.util.spec_from_file_location("overlay_false_positives", _PATH)
fp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fp)


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
