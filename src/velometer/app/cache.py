"""A one-entry-per-page cache for the read-only app.

The data a page shows changes only when the database, the config, the docs it reads, the maps
directory or the content (narratives and sources) change, so the key is a fingerprint of those
files' mtimes and sizes. A page is rebuilt only when its fingerprint differs from the one it was
built under.
"""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

DOC_FILES = (
    "review/m3_timeseries.md",
    "review/m3_timeseries.de.md",  # the German flagged-year explanations (M12)
    "reconciliation.md",
    "methodology.md",
    "methodology.de.md",
)
MAP_GLOBS = ("*.png", "*.geojson")
CHANGE_DOCS = ("*_change_*.md",)  # docs/review: the change pages' per-Bezirk tables
PLANS_GLOBS = ("*.geojson", "*.json")  # data/plans/<city>: the datasets the plan pages read


def _stat(path: Path, rel: str) -> tuple:
    try:
        st = path.stat()
    except OSError:
        return (rel, None, None)
    return (rel, st.st_mtime_ns, st.st_size)


def _tree(root: Path, patterns: tuple[str, ...] = ("*",)) -> list[tuple]:
    files = {p for pat in patterns for p in root.rglob(pat) if p.is_file()}
    return [_stat(p, p.relative_to(root).as_posix()) for p in sorted(files)]


def fingerprint(
    db_path: Path,
    config_dir: Path,
    docs_dir: Path,
    maps_dir: Path,
    content_dir: Path = Path("content"),
    plans_data_dir: Path | None = None,
) -> tuple:
    """Everything a page reads: the DB, every config file, five docs files, the change pages,
    the map files, every content file and the plan datasets (GeoJSON and their retrieval
    records) when a plans data directory is given."""
    db_path, config_dir, docs_dir, maps_dir, content_dir = map(
        Path, (db_path, config_dir, docs_dir, maps_dir, content_dir)
    )
    plans = () if plans_data_dir is None else _tree(Path(plans_data_dir), PLANS_GLOBS)
    return (
        _stat(db_path, "db")[1:],
        ("config", *_tree(config_dir)),
        ("docs", *(_stat(docs_dir / rel, rel) for rel in DOC_FILES)),
        ("changes", *_tree(docs_dir / "review", CHANGE_DOCS)),
        ("maps", *_tree(maps_dir, MAP_GLOBS)),
        ("content", *_tree(content_dir)),
        ("plans_data", *plans),
    )


class PageCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[tuple, object]] = {}

    def get(self, name: str, fp: tuple, build: Callable[[], T]) -> T:
        with self._lock:
            hit = self._entries.get(name)
            if hit is not None and hit[0] == fp:
                return hit[1]  # type: ignore[return-value]
            value = build()
            self._entries[name] = (fp, value)
            return value
