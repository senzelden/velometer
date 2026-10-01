import pytest

from velometer.pipeline.tags import parts


@pytest.mark.parametrize(
    ("value", "want"),
    [
        (None, []),
        ("", []),
        ("yes", ["yes"]),
        (" yes ; no ", ["yes", "no"]),
        ("a;;b;", ["a", "b"]),
        (" ; ", []),
    ],
)
def test_parts_splits_strips_and_drops_empty(value, want):
    assert parts(value) == want
