"""Per-year mapping-activity aggregates from a city history file (M3 spec §2.12).

Privacy: mapper ids (uids) exist only inside `activity()`, in local per-year sets and counters.
They are never logged, stored in module state or returned; usernames are never read.
"""

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import osmium

from velometer.config import ActivityConfig
from velometer.models import ActivityYear


def cycling_tags(tags: Mapping[str, str], cfg: ActivityConfig) -> dict[str, str]:
    """The cycling-relevant subset of `tags`; `highway` counts only for the listed values."""
    keys = cfg.cycling_keys
    exact = set(keys.exact)
    prefixes = tuple(keys.prefixes)
    out: dict[str, str] = {}
    for k, v in tags.items():
        if k == "highway":
            if v in keys.highway_values:
                out[k] = v
        elif k in exact or k.startswith(prefixes):
            out[k] = v
    return out


class _Edits(osmium.SimpleHandler):
    """Collects (timestamp, changeset, uid, created, deleted) per counted way version."""

    def __init__(self, cfg: ActivityConfig) -> None:
        super().__init__()
        self._cfg = cfg
        self._prev: dict[int, dict[str, str]] = {}
        self.edits: list[tuple[datetime, int, int, bool, bool]] = []

    def way(self, w) -> None:
        cur = cycling_tags({t.k: t.v for t in w.tags}, self._cfg) if w.visible else {}
        prev = self._prev.get(w.id, {})
        self._prev[w.id] = cur
        if cur == prev:
            return
        ts = w.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        self.edits.append((ts, w.changeset, w.uid, not prev and bool(cur), bool(prev) and not cur))


def activity(
    city_history: Path,
    years: range,
    cfg: ActivityConfig,
    *,
    city_id: str,
    boundary_kind: str,
    history_set_md5: str,
) -> list[ActivityYear]:
    """One row per year; year Y covers edits in [Y-1-01-01, Y-01-01) UTC (zeros allowed)."""
    handler = _Edits(cfg)
    handler.apply_file(str(city_history))
    rows = []
    for year in years:
        start = datetime(year - 1, 1, 1, tzinfo=UTC)
        end = datetime(year, 1, 1, tzinfo=UTC)
        window = [e for e in handler.edits if start <= e[0] < end]
        per_mapper = Counter(e[2] for e in window)  # local to this call; dropped on return
        n = len(window)
        rows.append(
            ActivityYear(
                city_id=city_id,
                boundary_kind=boundary_kind,
                year=year,
                history_set_md5=history_set_md5,
                n_edits=n,
                n_changesets=len({e[1] for e in window}),
                n_mappers=len(per_mapper),
                top_mapper_share=max(per_mapper.values()) / n if n else 0.0,
                n_ways_created_cycling=sum(e[3] for e in window),
                n_ways_deleted_cycling=sum(e[4] for e in window),
            )
        )
    return rows
