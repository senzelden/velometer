"""`velometer counters --check` (M8 spec §5.4): every configured city has sites and at least one
index year; no site appears under two cities; daily counts (and monthly values) are non-negative;
the index base year equals 100.

"An index year" is a year with a value carried by at least `MIN_SITES` qualifying sites: the
base year is 100 by definition, so it counts only when enough sites qualify in it.
"""

import sqlite3
from collections import defaultdict

from velometer.counters.index import MIN_SITES
from velometer.counters.model import CountersConfig


def check_counters(conn: sqlite3.Connection, cfg: CountersConfig) -> list[str]:
    problems = []
    for entry in cfg.cities:
        city = entry.city
        (n_sites,) = conn.execute(
            "SELECT COUNT(*) FROM counter_sites WHERE city_id=?", (city,)
        ).fetchone()
        if not n_sites:
            problems.append(f"{city}: no counter sites")
        rows = conn.execute(
            "SELECT year, idx, sites, base_year FROM counter_index WHERE city_id=?", (city,)
        ).fetchall()
        if not any(idx is not None and sites >= MIN_SITES for _, idx, sites, _ in rows):
            problems.append(f"{city}: no index year")
        for year, idx, _, base in rows:
            if base != entry.base_year:
                problems.append(f"{city}: index base year {base}, config says {entry.base_year}")
            elif year == base and idx != 100.0:
                problems.append(f"{city}: index base year {base} is {idx}, not 100")
    owners = defaultdict(set)
    for city, site in conn.execute("SELECT city_id, site_id FROM counter_sites"):
        owners[site].add(city)
    for site, cities in sorted(owners.items()):
        if len(cities) > 1:
            problems.append(f"site {site!r} under more than one city: {', '.join(sorted(cities))}")
    places = defaultdict(set)
    for city, _site, lat, lon in conn.execute(
        "SELECT city_id, site_id, lat, lon FROM counter_sites WHERE lat IS NOT NULL"
    ):
        places[lat, lon].add(city)
    for (lat, lon), cities in sorted(places.items()):
        if len(cities) > 1:
            problems.append(
                f"a site at {lat}, {lon} under more than one city: {', '.join(sorted(cities))}"
            )
    for city, n in conn.execute(
        "SELECT city_id, COUNT(*) FROM counter_daily WHERE count < 0 GROUP BY city_id"
    ):
        problems.append(f"{city}: {n} negative daily counts")
    for city, n in conn.execute(
        "SELECT city_id, COUNT(*) FROM counter_monthly WHERE avg_daily < 0 GROUP BY city_id"
    ):
        problems.append(f"{city}: {n} negative monthly values")
    return problems
