"""Bike-counter context (M8 spec §5): portal adapters, hourly-to-daily totals, a chained index
per city and its check. `load_city` stores one fetched city into the `counter_*` tables.
"""

import calendar
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from velometer.counters.adapters import adapter, boundary_polygon, read_retrieved, sites_inside
from velometer.counters.days import to_days, zero_days_invalid
from velometer.counters.index import chain_index, chain_index_monthly
from velometer.counters.model import CounterEntry, DayCount, MonthValue, Site

SERIES = "counts"
MONTHLY_SERIES = "avg_daily_intensity"  # spec §2.14: Barcelona
MONTHLY_DAY_TYPE = "working_day"  # the day type a monthly series is indexed on


@dataclass(frozen=True)
class LoadResult:
    sites: int
    days: int  # stored rows: days, or (month, day type) values for a monthly portal
    complete_days: int  # complete days, or values of the indexed day type
    first_day: str | None
    last_day: str | None
    index: list[tuple[int, float | None, int]]
    unit: str = "days"


def city_dir(data_dir: Path, city: str) -> Path:
    return Path(data_dir) / "counters" / city


def _keep_inside(entry: CounterEntry, data_dir: Path, sites: list[Site], records: list):
    """The sites inside the entry's stored boundary and their records (all when the entry names
    no boundary)."""
    if entry.boundary is None:
        return sites, records
    keep = sites_inside(sites, boundary_polygon(entry, data_dir))
    return [s for s in sites if s.site_id in keep], [r for r in records if r.site_id in keep]


def load_city(conn, entry: CounterEntry, data_dir: Path) -> LoadResult:
    """Parse the city's fetched files (in `retrieved.json` order) and replace its daily totals
    (or monthly values), its sites (with first and last day) and its index.

    FileNotFoundError when the city was not fetched; CounterFormatError on a portal file the
    adapter cannot read (or a missing boundary file).
    """
    out_dir = city_dir(data_dir, entry.city)
    meta = read_retrieved(out_dir)
    paths = [out_dir / f["file"] for f in meta["files"]]
    retrieved_at = max(f["retrieved_at"] for f in meta["files"])
    sites, records = adapter(entry.adapter).parse(paths, entry)
    sites, records = _keep_inside(entry, data_dir, sites, records)
    if entry.grain == "monthly":
        return _load_monthly(conn, entry, sites, records, retrieved_at)
    days = to_days(records, entry.timezone) if entry.grain == "hourly" else records
    del records  # an hourly portal's history is millions of records
    days = zero_days_invalid(days)
    # the files hold the city's whole history, so its daily rows are replaced (rows the files
    # no longer give do not linger), in one transaction
    with conn:
        conn.execute("DELETE FROM counter_daily WHERE city_id=?", (entry.city,))
        conn.executemany(
            "INSERT INTO counter_daily (city_id, site_id, day, count, complete) VALUES (?,?,?,?,?)",
            [(entry.city, d.site_id, d.day.isoformat(), d.count, int(d.complete)) for d in days],
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
    _store_sites(conn, entry, sites, span, retrieved_at)
    index = chain_index(stored, entry.base_year)
    _store_index(conn, entry, index, SERIES)
    all_days = sorted(d.day for d in stored)
    return LoadResult(
        sites=len(sites),
        days=len(stored),
        complete_days=sum(d.complete for d in stored),
        first_day=all_days[0].isoformat() if all_days else None,
        last_day=all_days[-1].isoformat() if all_days else None,
        index=index,
    )


def _month_span(month: str) -> tuple[str, str]:
    y, m = int(month[:4]), int(month[5:7])
    return f"{month}-01", f"{month}-{calendar.monthrange(y, m)[1]:02d}"


def _load_monthly(conn, entry, sites: list[Site], months: list[MonthValue], retrieved_at: str):
    from velometer.db import CounterMonth, replace_counter_monthly

    replace_counter_monthly(
        conn,
        entry.city,
        [CounterMonth(entry.city, m.site_id, m.month, m.day_type, m.avg_daily) for m in months],
    )
    span: dict[str, tuple[str, str]] = {}
    for m in months:
        first, last = _month_span(m.month)
        lo, hi = span.get(m.site_id, (first, last))
        span[m.site_id] = (min(lo, first), max(hi, last))
    _store_sites(conn, entry, sites, span, retrieved_at)
    index = chain_index_monthly(months, entry.base_year, MONTHLY_DAY_TYPE)
    _store_index(conn, entry, index, MONTHLY_SERIES)
    bounds = sorted(x for lo_hi in span.values() for x in lo_hi)
    return LoadResult(
        sites=len(sites),
        days=len(months),
        complete_days=sum(m.day_type == MONTHLY_DAY_TYPE for m in months),
        first_day=bounds[0] if bounds else None,
        last_day=bounds[-1] if bounds else None,
        index=index,
        unit="monthly values",
    )


def _store_sites(conn, entry, sites: list[Site], span, retrieved_at: str) -> None:
    from velometer.db import CounterSite, replace_counter_sites

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


def _store_index(conn, entry, index, series: str) -> None:
    from velometer.db import CounterIndexYear, replace_counter_index

    replace_counter_index(
        conn,
        entry.city,
        [CounterIndexYear(entry.city, y, v, n, entry.base_year, series) for y, v, n in index],
    )
