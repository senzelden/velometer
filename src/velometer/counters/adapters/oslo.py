"""Oslo: Statens vegvesen's traffic-data GraphQL API (https://trafikkdata-api.atlas.vegvesen.no/,
public, no key; NLOD), bicycle registration points: state counters, not Oslo kommune's own.

`fetch` asks for every BICYCLE point of county 3 (Oslo), keeps those inside the stored Oslo LAU
boundary, and pages each kept point's `volume.byDay` (100 days per page) from its first data to
today. For each day with a volume whose coverage is below 100 % or missing, it also asks for
that day's `volume.byHour` (several days per request, one GraphQL alias each). Files:
`00_points.json` (the points answer as given) and `<nn>_<point id>.json` (`{
"trafficRegistrationPointId", "from", "to", "days": [byDay nodes], "hours": {date: [byHour
nodes]}}`), each with its queries in `retrieved.json`.

`byDay` is the API's own daily total, the sum of `byHour` (2019-10-27 at Frognerstranda: 25 hours
summing to 732, the day's total), with `coverage.percentage`, the share of the day's time the
point reported. A day is complete when all its local hours are present (§5.2), as for every other
city: an hour is present when `byHour` gives it a volume, however much of it is covered. A day at
coverage 100 is complete; any other day is complete when its `byHour` rows give a volume to every
local hour of the day (23, 24 or 25), and incomplete without them. A spot check of 51 days
(docs/review/m8-counters.md) found every 95-100 % day to be 24 hours with a volume and one to
nine partly covered hours (minutes missing), the days below 95 % to miss whole hours, and the
days without a coverage figure (2003-2015) to carry 24 hours with a volume and no coverage. A day
without a volume (coverage 0) is not stored. The days are local (Europe/Oslo) dates, read from
each node's `from`. The `boundary: lau` key of the entry drops points outside Oslo at load as
well.
"""

import json
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from velometer.counters.adapters import (
    TIMEOUT_S,
    _now,
    boundary_polygon,
    sites_inside,
    user_agent,
    write_retrieved,
)
from velometer.counters.days import local_hours
from velometer.counters.model import CounterEntry, CounterFormatError, DayCount, Site

COUNTY = 3  # Oslo
POINTS_FILE = "00_points.json"
POINTS_SUFFIX = "points.json"  # parse reads the file whose name ends so
PAGE = 100  # the API's largest page
HOUR_DAYS = 20  # days of byHour per request (one alias each, at most 25 hours per alias)

POINTS_QUERY = """
query Points($county: [PositiveInt!]) {
  trafficRegistrationPoints(searchQuery: {countyNumbers: $county, trafficType: BICYCLE}) {
    id name trafficRegistrationType
    location { municipality { name number } coordinates { latLon { lat lon } } }
    dataTimeSpan { firstData latestData { volumeByDay } }
  }
}
"""

DAYS_QUERY = """
query Days($id: String!, $from: ZonedDateTime!, $to: ZonedDateTime!, $after: String) {
  trafficData(trafficRegistrationPointId: $id) {
    volume {
      byDay(from: $from, to: $to, first: 100, after: $after) {
        edges { node { from to total { volumeNumbers { volume } coverage { percentage } } } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""

HOURS_FIELDS = (
    "edges { node { from to total { volumeNumbers { volume } coverage { percentage } } } }"
)


def hours_query(n: int) -> str:
    """byHour for `n` days of one point, day `i` as alias `d<i>` from `$f<i>` to `$t<i>`."""
    params = "".join(f", $f{i}: ZonedDateTime!, $t{i}: ZonedDateTime!" for i in range(n))
    fields = " ".join(
        f"d{i}: byHour(from: $f{i}, to: $t{i}, first: {PAGE}) "
        f"{{ {HOURS_FIELDS} pageInfo {{ hasNextPage }} }}"
        for i in range(n)
    )
    return (
        f"query Hours($id: String!{params}) {{\n"
        f"  trafficData(trafficRegistrationPointId: $id) {{ volume {{ {fields} }} }}\n}}"
    )


Post = Callable[[str, str, dict], dict]


def _graphql(url: str, query: str, variables: dict) -> dict:
    r = httpx.post(
        url,
        json={"query": query, "variables": variables},
        timeout=TIMEOUT_S,
        headers={"User-Agent": user_agent()},
    )
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise CounterFormatError(url, f"GraphQL errors: {body['errors']}")
    return body["data"]


def _points(data: dict, label) -> list[dict]:
    try:
        return data["trafficRegistrationPoints"]
    except (KeyError, TypeError) as e:
        raise CounterFormatError(label, "no trafficRegistrationPoints") from e


def _site(p: dict) -> Site:
    ll = ((p.get("location") or {}).get("coordinates") or {}).get("latLon") or {}
    return Site(p["id"], p["name"].strip(), ll.get("lat"), ll.get("lon"))


def _volume(node: dict):
    return ((node.get("total") or {}).get("volumeNumbers") or {}).get("volume")


def _coverage(node: dict):
    return ((node.get("total") or {}).get("coverage") or {}).get("percentage")


def _fetch_hours(url: str, pid: str, days: list[dict], post: Post) -> dict[str, list[dict]]:
    """byHour for the days with a volume but coverage below 100 % (or none)."""
    want = [d for d in days if _volume(d) is not None and _coverage(d) != 100]
    out = {}
    for i in range(0, len(want), HOUR_DAYS):
        batch = want[i : i + HOUR_DAYS]
        variables = {"id": pid}
        for j, d in enumerate(batch):
            variables[f"f{j}"], variables[f"t{j}"] = d["from"], d["to"]
        volume = post(url, hours_query(len(batch)), variables)["trafficData"]["volume"]
        for j, d in enumerate(batch):
            got = volume[f"d{j}"]
            if got["pageInfo"]["hasNextPage"]:
                raise CounterFormatError(url, f"{pid} {d['from']}: more than {PAGE} hours")
            out[d["from"][:10]] = [e["node"] for e in got["edges"]]
    return out


def fetch(
    entry: CounterEntry, out_dir: Path, data_dir: Path | None = None, post: Post = _graphql
) -> list[Path]:
    """The points, then each kept point's days (and hours); `data_dir` holds the stored Oslo
    boundary (`<data_dir>/boundaries/`) the points are kept inside, and is required."""
    if data_dir is None:
        raise ValueError("oslo fetch needs the data directory (its stored boundary)")
    url = entry.urls[0]
    zone = ZoneInfo(entry.timezone)
    points_data = post(url, POINTS_QUERY, {"county": [COUNTY]})
    at = _now()
    points = _points(points_data, url)
    inside = sites_inside([_site(p) for p in points], boundary_polygon(entry, data_dir))
    got = [
        (
            POINTS_FILE,
            url,
            json.dumps({"data": points_data}, ensure_ascii=False, indent=1).encode(),
            at,
            {"query": POINTS_QUERY.strip(), "variables": {"county": [COUNTY]}},
        )
    ]
    end = datetime.combine(date.today() + timedelta(days=1), time(), zone).isoformat()
    for n, p in enumerate(sorted((p for p in points if p["id"] in inside), key=lambda p: p["id"])):
        first = (p.get("dataTimeSpan") or {}).get("firstData")
        if not first:
            continue
        start = datetime.combine(date.fromisoformat(first[:10]), time(), zone).isoformat()
        days, after = [], None
        while True:
            variables = {"id": p["id"], "from": start, "to": end, "after": after}
            page = post(url, DAYS_QUERY, variables)["trafficData"]["volume"]["byDay"]
            days += [e["node"] for e in page["edges"]]
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
        hours = _fetch_hours(url, p["id"], days, post)
        body = {
            "trafficRegistrationPointId": p["id"],
            "from": start,
            "to": end,
            "days": days,
            "hours": hours,
        }
        got.append(
            (
                f"{n + 1:02d}_{p['id']}.json",
                url,
                json.dumps(body, indent=1).encode(),
                _now(),
                {
                    "query": DAYS_QUERY.strip(),
                    "variables": {"id": p["id"], "from": start},
                    "hours_query": hours_query(1),
                    "hours_days": len(hours),
                },
            )
        )
    return write_retrieved(entry, out_dir, got)


def _all_hours(nodes: list[dict], day: date, zone: ZoneInfo, tz: str) -> bool:
    """Every local hour of `day` has a byHour row with a volume."""
    got = set()
    for n in nodes:
        if _volume(n) is None:
            continue
        loc = datetime.fromisoformat(n["from"]).astimezone(zone)
        got.add((loc.replace(tzinfo=None, fold=0), loc.fold))
    return got >= local_hours(day, tz)


def _days(path: Path, tz: str) -> list[DayCount]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    try:
        sid, nodes = doc["trafficRegistrationPointId"], doc["days"]
    except KeyError as e:
        raise CounterFormatError(path, f"key {e} missing") from e
    hours = doc.get("hours") or {}
    zone = ZoneInfo(tz)
    out = []
    for node in nodes:
        volume = _volume(node)
        if volume is None:
            continue
        if not isinstance(volume, int) or volume < 0:
            raise CounterFormatError(path, f"{node.get('from')}: not a count {volume!r}")
        day = date.fromisoformat(node["from"][:10])
        complete = _coverage(node) == 100 or _all_hours(hours.get(str(day), []), day, zone, tz)
        out.append(DayCount(sid, day, volume, complete))
    return out


def parse(paths: list[Path], entry: CounterEntry) -> tuple[list[Site], list[DayCount]]:
    points = [Path(p) for p in paths if Path(p).name.endswith(POINTS_SUFFIX)]
    if not points:
        raise CounterFormatError(paths[0] if paths else "oslo", f"no {POINTS_FILE}")
    data = json.loads(points[-1].read_text(encoding="utf-8")).get("data")
    sites = {
        p["id"]: _site(p)
        for p in _points(data, points[-1])
        if p.get("trafficRegistrationType") == "BICYCLE"
    }
    days: dict[tuple[str, date], DayCount] = {}
    for path in (Path(p) for p in paths):
        if path.name.endswith(POINTS_SUFFIX):
            continue
        for d in _days(path, entry.timezone):
            if d.site_id in sites:
                days[d.site_id, d.day] = d
    return list(sites.values()), [days[k] for k in sorted(days)]
