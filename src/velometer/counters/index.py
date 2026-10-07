"""Chained counter index per city (M8 spec §2.13, §5.3).

Each year-on-year link uses only the sites with at least `min_valid` complete days (of the
year's 365 or 366 calendar days) in both years; the link ratio is the sum of those sites'
counts over their complete days in the later year over the earlier one. Links are chained from
`base_year` = 100.0, forwards and backwards. A link with fewer than `min_sites` sites breaks the
chain: that year and every year beyond it (further from the base) have no value; the chain is
never re-based. The base year is 100.0 by definition; its site count is the number of sites
with `min_valid` complete days in it.
"""

import calendar
from collections import defaultdict
from collections.abc import Iterable

from velometer.counters.model import DayCount

IndexYear = tuple[int, float | None, int]  # year, index, qualifying sites

MIN_VALID = 0.9  # share of complete days a site needs in both years of a link
MIN_SITES = 3  # sites a link needs


def _year_stats(days: Iterable[DayCount]) -> dict[int, dict[str, tuple[int, int]]]:
    """year -> site -> (complete days, count summed over complete days)."""
    acc: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for d in days:
        if d.complete:
            s = acc[d.day.year][d.site_id]
            s[0] += 1
            s[1] += d.count
    return {y: {site: (n, c) for site, (n, c) in sites.items()} for y, sites in acc.items()}


def _valid_sites(stats, year: int, min_valid: float) -> set[str]:
    n_days = 366 if calendar.isleap(year) else 365
    return {s for s, (n, _) in stats.get(year, {}).items() if n / n_days >= min_valid}


def chain_index(
    days: list[DayCount],
    base_year: int,
    min_valid: float = MIN_VALID,
    min_sites: int = MIN_SITES,
) -> list[IndexYear]:
    years = {d.day.year for d in days}
    if not years:
        return []
    first, last = min(years | {base_year}), max(years | {base_year})
    stats = _year_stats(days)
    valid = {y: _valid_sites(stats, y, min_valid) for y in range(first, last + 1)}

    def link(earlier: int, later: int) -> tuple[float | None, int]:
        sites = valid[earlier] & valid[later]
        before = sum(stats[earlier][s][1] for s in sites)
        after = sum(stats[later][s][1] for s in sites)
        if len(sites) < min_sites or before == 0:
            return None, len(sites)
        return after / before, len(sites)

    out: dict[int, IndexYear] = {}
    out[base_year] = (base_year, 100.0, len(valid[base_year]))
    for step, years_out in (
        (1, range(base_year + 1, last + 1)),
        (-1, range(base_year - 1, first - 1, -1)),
    ):
        prev = out[base_year][1]
        for y in years_out:
            ratio, n = link(y - 1, y) if step == 1 else link(y, y + 1)
            if prev is None or ratio is None:
                prev = None
            else:
                prev = prev * ratio if step == 1 else prev / ratio
            out[y] = (y, prev, n)
    return [out[y] for y in sorted(out)]
