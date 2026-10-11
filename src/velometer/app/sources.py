"""The /sources page: one row per figure source, plus the row for our own figures."""


def source_anchor(source_id: str | None) -> str:
    """The /sources fragment of a source row; `ours` is the row for our own figures."""
    return "ours" if source_id is None else f"src-{source_id}"
