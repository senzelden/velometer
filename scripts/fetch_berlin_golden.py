"""Fetch the Berlin golden way set from Overpass (network; run once, never in pytest).

Phase 1 picks way ids per group (lowest ids first, so the pick is deterministic for a given OSM
state). Phase 2 downloads those ways with their nodes to tests/fixtures/berlin_golden.osm and the
classifier's current proposals are written to tests/fixtures/berlin_golden.yaml for human review.
"""

import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways

URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "velometer-golden-fetch/0.1 (Berlin golden set for tests)"
SLEEP_S = 2.0
RETRY_WAIT_S = 30.0
MAX_ATTEMPTS = 4
MIN_TOTAL = 40
FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# group -> (way filter, cap)
GROUPS: dict[str, tuple[str, int]] = {
    "kantstrasse": ('way["name"="Kantstraße"]["highway"]', 8),
    "ollenhauerstrasse": ('way["name"="Ollenhauerstraße"]["highway"]', 6),
    "unter_den_eichen": ('way["name"="Unter den Eichen"]["highway"]', 6),
    "karl_marx_allee": ('way["name"="Karl-Marx-Allee"]["highway"]', 6),
    "fahrradstrasse": ('way["bicycle_road"="yes"]', 4),
    "hochbord_shared": (
        'way["highway"="footway"]["footway"="sidewalk"]["bicycle"="designated"]',
        4,
    ),
    "sidewalk_cycleway": ('way["highway"="cycleway"]["cycleway"="sidewalk"]', 4),
    "protected_lane": ('way["cycleway:right:separation"]', 4),
    "busway": ('way[~"^cycleway(:both|:right|:left)?$"~"share_busway"]', 4),
    "separate": ('way["cycleway:both"="separate"]', 4),
}


def overpass(client: httpx.Client, query: str) -> httpx.Response:
    """POST a query, politely; retry on 429/504 (the public instance is often overloaded)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        time.sleep(SLEEP_S)
        resp = client.post(URL, data={"data": query})
        if resp.status_code in (429, 504) and attempt < MAX_ATTEMPTS:
            print(f"  HTTP {resp.status_code}, retry {attempt}/{MAX_ATTEMPTS - 1}", flush=True)
            time.sleep(RETRY_WAIT_S)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError("unreachable")


def phase1(client: httpx.Client) -> dict[str, list[int]]:
    picked: dict[str, list[int]] = {}
    seen: set[int] = set()
    for group, (flt, cap) in GROUPS.items():
        q = (
            '[out:json][timeout:90];area["name"="Berlin"]["admin_level"="4"]->.b;'
            f"{flt}(area.b);out ids;"
        )
        ids = sorted(e["id"] for e in overpass(client, q).json()["elements"])
        fresh = [i for i in ids if i not in seen][:cap]  # a way belongs to its first group only
        seen.update(fresh)
        picked[group] = fresh
        print(group, len(ids), "found", flush=True)
    return picked


def phase2(client: httpx.Client, ids: list[int], stamp: str) -> None:
    q = f"[timeout:180];way(id:{','.join(map(str, ids))});(._;>;);out meta;"
    xml = overpass(client, q).text
    comment = f"<!-- Overpass API, fetched {stamp}; (c) OpenStreetMap contributors, ODbL 1.0 -->"
    xml = re.sub(r"(<\?xml[^>]*\?>)", lambda m: f"{m.group(1)}\n{comment}", xml, count=1)
    (FIX / "berlin_golden.osm").write_text(xml, encoding="utf-8")


def write_yaml(picked: dict[str, list[int]], stamp: str) -> None:
    cfg = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
    ways = {w.id: w for w in read_ways(FIX / "berlin_golden.osm").ways}
    proposed: dict[int, list[dict]] = {}
    for c in classify_ways(ways.values(), cfg):
        if c.tier is not None:
            proposed.setdefault(c.side.way_id, []).append(
                {
                    "side": c.side.side,
                    "tier": c.tier,
                    "rule": c.rule_id,
                    "subtype": c.subtype,
                }
            )
    entries = []
    for group, ids in picked.items():
        for wid in ids:
            if wid not in ways:
                continue
            tags = ways[wid].tags
            entries.append(
                {
                    "way_id": wid,
                    "group": group,
                    "name": tags.get("name", ""),
                    "highway": tags.get("highway", ""),
                    "proposed": proposed.get(wid, []),
                    "confirmed": False,
                    "note": "",
                }
            )
    doc = {
        "source": f"Overpass API, fetched {stamp}; © OpenStreetMap contributors, ODbL 1.0",
        "classifier_version": "v1",
        "ways": entries,
    }
    (FIX / "berlin_golden.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    for group in GROUPS:
        print(f"{group:20s} {sum(1 for e in entries if e['group'] == group)}")
    print(f"{'TOTAL':20s} {len(entries)}")
    if len(entries) < MIN_TOTAL:
        sys.exit(f"only {len(entries)} ways, need >= {MIN_TOTAL}")


def main() -> None:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=240) as client:
        picked = phase1(client)
        ids = sorted({i for v in picked.values() for i in v})
        print({g: len(v) for g, v in picked.items()})
        phase2(client, ids, stamp)
    write_yaml(picked, stamp)


if __name__ == "__main__":
    main()
