"""Hourly counts to daily totals (M8 spec §5.2).

`to_days` de-duplicates on (site, local hour, fold), keeping the last record seen, so files
that overlap (a yearly archive and a rolling window) count each hour once; pass them in load
order. A day is complete when it holds every local hour that exists on that date in the
timezone: 23 on the spring-forward day, 25 on the fall-back day (the repeated hour twice, the
second with fold=1), else 24. A record for an hour that does not exist (the skipped hour of a
spring-forward day, which some portals fill with a placeholder row) is ignored.

`sum_counters` turns the hours of several counters of one site into site-hours (Paris: the
counters of a counting site; Helsinki: the two sides of a bridge).
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from functools import cache
from zoneinfo import ZoneInfo

from velometer.counters.model import DayCount, HourCount

_HOUR = timedelta(hours=1)

HourKey = tuple[datetime, int]  # naive local hour with fold=0, fold


@cache
def local_hours(day: date, tz: str) -> frozenset[HourKey]:
    """Every local hour that exists on `day` in `tz`, as (naive hour, fold)."""
    z = ZoneInfo(tz)
    t = datetime.combine(day, time(), z).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(), z).astimezone(UTC)
    out = set()
    while t < end:
        loc = t.astimezone(z)
        out.add((loc.replace(tzinfo=None, fold=0), loc.fold))
        t += _HOUR
    return frozenset(out)


def to_days(hours: Iterable[HourCount], tz: str) -> list[DayCount]:
    latest: dict[str, dict[HourKey, int]] = defaultdict(dict)
    for h in hours:
        latest[h.site_id][(h.local_hour.replace(fold=0), h.local_hour.fold)] = h.count
    out = []
    for site_id, by_hour in latest.items():
        per_day: dict[date, dict[HourKey, int]] = defaultdict(dict)
        for key, count in by_hour.items():
            per_day[key[0].date()][key] = count
        for day in sorted(per_day):
            got = per_day[day]
            exist = local_hours(day, tz)
            kept = {k: c for k, c in got.items() if k in exist}
            if not kept:
                continue
            out.append(DayCount(site_id, day, sum(kept.values()), exist <= kept.keys()))
    return out


def zero_days_invalid(days: Iterable[DayCount]) -> list[DayCount]:
    """A site-day with nothing recorded is a counter outage (portals write 0 for a day not
    counted), not a valid day: kept with its count 0, marked incomplete."""
    return [DayCount(d.site_id, d.day, d.count, False) if d.count == 0 else d for d in days]


CounterHours = dict[tuple[str, str, datetime, int], int]  # (site, counter, local hour, fold)


def sum_counters(per_counter: CounterHours) -> list[HourCount]:
    """The site-hours of one file: the sum of the site's counters, kept only when every counter of
    the site in service that day reports the hour. A counter is in service on the days from its
    first to its last reported day in the file; a site-hour one of them lacks is left out, so
    to_days marks the day incomplete."""
    span: dict[tuple[str, str], tuple[date, date]] = {}
    for site, counter, t, _ in per_counter:
        d = t.date()
        lo, hi = span.get((site, counter), (d, d))
        span[site, counter] = (min(lo, d), max(hi, d))
    counters: dict[str, list[tuple[date, date]]] = defaultdict(list)
    for (site, _), lo_hi in span.items():
        counters[site].append(lo_hi)
    total: dict[tuple[str, datetime, int], int] = defaultdict(int)
    reporting: dict[tuple[str, datetime, int], int] = defaultdict(int)
    for (site, _, t, fold), count in per_counter.items():
        total[site, t, fold] += count
        reporting[site, t, fold] += 1
    in_service: dict[tuple[str, date], int] = {}
    out = []
    for (site, t, fold), count in total.items():
        d = t.date()
        if (site, d) not in in_service:
            in_service[site, d] = sum(lo <= d <= hi for lo, hi in counters[site])
        if reporting[site, t, fold] == in_service[site, d]:
            out.append(HourCount(site, t.replace(fold=fold), count))
    return out
