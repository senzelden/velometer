"""Oslo: Statens vegvesen's traffic-data GraphQL API (https://trafikkdata-api.atlas.vegvesen.no/,
public, no key; NLOD), bicycle registration points: state counters, not Oslo kommune's own.

`fetch` asks for every BICYCLE point of county 3 (Oslo), keeps those inside the stored Oslo LAU
boundary, and pages each kept point's `volume.byDay` (100 days per page) from its first data to
today. Files: `00_points.json` (the points answer as given) and `<nn>_<point id>.json` (the
point's days: `{"trafficRegistrationPointId", "from", "to", "days": [byDay nodes]}`), each with
the query in `retrieved.json`.

`byDay` is the API's own daily total, the sum of `byHour` (2019-10-27 at Frognerstranda: 25 hours
summing to 732, the day's total), with `coverage.percentage`, the share of the day the point
reported. A day is complete when coverage is 100; a day without a volume (coverage 0) is not
stored. The days are local (Europe/Oslo) dates, read from each node's `from`. The `boundary:
lau` key of the entry drops points outside Oslo at load as well.
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
from velometer.counters.model import CounterEntry, CounterFormatError, DayCount, Site

COUNTY = 3  # Oslo
POINTS_FILE = "00_points.json"
POINTS_SUFFIX = "points.json"  # parse reads the file whose name ends so
PAGE = 100  # the API's largest page

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


def fetch(entry: CounterEntry, out_dir: Path, post: Post = _graphql) -> list[Path]:
    url = entry.urls[0]
    zone = ZoneInfo(entry.timezone)
    points_data = post(url, POINTS_QUERY, {"county": [COUNTY]})
    at = _now()
    points = _points(points_data, url)
    inside = sites_inside(
        [_site(p) for p in points], boundary_polygon(entry, Path(out_dir).parents[1])
    )
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
        body = {"trafficRegistrationPointId": p["id"], "from": start, "to": end, "days": days}
        got.append(
            (
                f"{n + 1:02d}_{p['id']}.json",
                url,
                json.dumps(body, indent=1).encode(),
                _now(),
                {"query": DAYS_QUERY.strip(), "variables": {"id": p["id"], "from": start}},
            )
        )
    return write_retrieved(entry, out_dir, got)


def _days(path: Path) -> list[DayCount]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    try:
        sid, nodes = doc["trafficRegistrationPointId"], doc["days"]
    except KeyError as e:
        raise CounterFormatError(path, f"key {e} missing") from e
    out = []
    for node in nodes:
        total = node.get("total") or {}
        volume = (total.get("volumeNumbers") or {}).get("volume")
        if volume is None:
            continue
        if not isinstance(volume, int) or volume < 0:
            raise CounterFormatError(path, f"{node.get('from')}: not a count {volume!r}")
        coverage = (total.get("coverage") or {}).get("percentage")
        out.append(DayCount(sid, date.fromisoformat(node["from"][:10]), volume, coverage == 100))
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
        for d in _days(path):
            if d.site_id in sites:
                days[d.site_id, d.day] = d
    return list(sites.values()), [days[k] for k in sorted(days)]
