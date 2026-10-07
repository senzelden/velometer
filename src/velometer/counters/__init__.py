"""Bike-counter context (M8 spec §5): portal adapters, hourly-to-daily totals, a chained index
per city and its check. `load_city` stores one fetched city into the `counter_*` tables.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from velometer.counters.adapters import adapter, read_retrieved
from velometer.counters.days import to_days, zero_days_invalid
from velometer.counters.index import chain_index
from velometer.counters.model import CounterEntry, DayCount

SERIES = "counts"


@dataclass(frozen=True)
class LoadResult:
    sites: int
    days: int
    complete_days: int
    first_day: str | None
    last_day: str | None
    index: list[tuple[int, float | None, int]]


def city_dir(data_dir: Path, city: str) -> Path:
    return Path(data_dir) / "counters" / city


def load_city(conn, entry: CounterEntry, data_dir: Path) -> LoadResult:
    """Parse the city's fetched files (in `retrieved.json` order) and replace its daily totals,
    its sites (with first and last day) and its index.

    FileNotFoundError when the city was not fetched; CounterFormatError on a portal file the
    adapter cannot read; ValueError for a grain this loader does not handle.
    """
    from velometer.db import (
        CounterDay,
        CounterIndexYear,
        CounterSite,
        replace_counter_index,
        replace_counter_sites,
        upsert_counter_daily,
    )

    if entry.grain not in ("hourly", "daily"):
        raise ValueError(f"{entry.city}: grain {entry.grain!r} is not loaded as daily counts")
    out_dir = city_dir(data_dir, entry.city)
    meta = read_retrieved(out_dir)
    paths = [out_dir / f["file"] for f in meta["files"]]
    retrieved_at = max(f["retrieved_at"] for f in meta["files"])
    sites, records = adapter(entry.adapter).parse(paths, entry)
    days = to_days(records, entry.timezone) if entry.grain == "hourly" else records
    del records  # an hourly portal's history is millions of records
    days = zero_days_invalid(days)
    # the files hold the city's whole history: rows they no longer give do not linger
    with conn:
        conn.execute("DELETE FROM counter_daily WHERE city_id=?", (entry.city,))
    upsert_counter_daily(
        conn,
        [CounterDay(entry.city, d.site_id, d.day.isoformat(), d.count, d.complete) for d in days],
    )
    stored = [
        DayCount(site, date.fromisoformat(day), count, bool(complete))
        for site, day, count, complete in conn.execute(
            "SELECT site_id, day, count, complete FROM counter_daily WHERE city_id=?",
            (entry.city,),
        )
    ]
    span: dict[str, tuple[str, str]] = {}
    for d in stored:
        day = d.day.isoformat()
        lo, hi = span.get(d.site_id, (day, day))
        span[d.site_id] = (min(lo, day), max(hi, day))
    replace_counter_sites(
        conn,
        entry.city,
        [
            CounterSite(
                entry.city,
                s.site_id,
                s.name,
                s.lat,
                s.lon,
                entry.source,
                entry.licence,
                entry.page,
                retrieved_at,
                *span.get(s.site_id, (None, None)),
            )
            for s in sorted(sites, key=lambda s: s.site_id)
        ],
    )
    index = chain_index(stored, entry.base_year)
    replace_counter_index(
        conn,
        entry.city,
        [CounterIndexYear(entry.city, y, v, n, entry.base_year, SERIES) for y, v, n in index],
    )
    all_days = sorted(d.day for d in stored)
    return LoadResult(
        sites=len(sites),
        days=len(stored),
        complete_days=sum(d.complete for d in stored),
        first_day=all_days[0].isoformat() if all_days else None,
        last_day=all_days[-1].isoformat() if all_days else None,
        index=index,
    )
