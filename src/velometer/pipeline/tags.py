"""OSM tag-value semantics shared by every pipeline stage (spec global constraint)."""


def parts(value: str | None) -> list[str]:
    """Split a tag value on `;`, strip each part and drop empty ones; None or "" -> []."""
    if not value:
        return []
    return [p for p in (raw.strip() for raw in value.split(";")) if p]
