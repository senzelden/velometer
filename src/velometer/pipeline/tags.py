"""OSM tag-value semantics shared by every pipeline stage (spec global constraint)."""

from collections.abc import Sequence


def parts(value: str | None, separators: Sequence[str] = (";",)) -> list[str]:
    """Split a tag value on each separator (`;` by default), strip each part and drop empty
    ones; None or "" -> []."""
    if not value:
        return []
    pieces = [value]
    for sep in separators:
        pieces = [q for piece in pieces for q in piece.split(sep)]
    return [p for p in (raw.strip() for raw in pieces) if p]
