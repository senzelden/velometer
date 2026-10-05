"""Fetch the Berlin golden way set from Overpass (network; run once, never in pytest).

Phase 1 picks way ids per group (lowest ids first, so the pick is deterministic for a given OSM
state). Groups are queried in GROUPS order and a way belongs to the first group that picks it
(first-group-wins dedup): a later group skips ids already taken and fills its cap from the rest.
Phase 2 downloads those ways with their nodes to tests/fixtures/berlin_golden.osm and the
classifier's current proposals are written to tests/fixtures/berlin_golden.yaml for human review.

An Overpass `remark` (timeout, memory exhaustion: HTTP 200 with truncated results) or a picked id
missing from the phase-2 download aborts the run instead of writing a short set.

The User-Agent carries no personal contact; set VELOMETER_CONTACT to append one.

`--reclassify` skips the network and only re-derives the proposals in berlin_golden.yaml for the
ways already in berlin_golden.osm (after a classifier change; keeps the original source stamp).
"""

import os
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
USER_AGENT_BASE = "velometer-golden-fetch/0.1 (Berlin golden set for tests)"
SLEEP_S = 2.0
RETRY_WAIT_S = 30.0
MAX_ATTEMPTS = 4
MIN_TOTAL = 40
FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

KMA = 'way["name"="Karl-Marx-Allee"]["highway"]'
UDE = 'way["name"="Unter den Eichen"]["highway"]'
SEPARATE_PATHS = 'way["highway"~"^(cycleway|path)$"]'


def _in_berlin(*filters: str) -> str:
    """Union of way filters restricted to the Berlin area (`.b`)."""
    return "(" + "".join(f"{f}(area.b);" for f in filters) + ");"


def _near(street: str, metres: int) -> str:
    """Separately mapped cycleways/paths within `metres` of the street group's ways."""
    return f"{street}(area.b)->.street;{SEPARATE_PATHS}(around.street:{metres});"


# group -> (Overpass statements leaving the group's ways in the default set, cap)
GROUPS: dict[str, tuple[str, int]] = {
    "kantstrasse": (_in_berlin('way["name"="Kantstraße"]["highway"]'), 8),
    "ollenhauerstrasse": (_in_berlin('way["name"="Ollenhauerstraße"]["highway"]'), 6),
    "unter_den_eichen": (_in_berlin(UDE), 6),
    "karl_marx_allee": (_in_berlin(KMA), 6),
    "fahrradstrasse": (_in_berlin('way["bicycle_road"="yes"]'), 4),
    "hochbord_shared": (
        _in_berlin('way["highway"="footway"]["footway"="sidewalk"]["bicycle"="designated"]'),
        4,
    ),
    "sidewalk_cycleway": (_in_berlin('way["highway"="cycleway"]["cycleway"="sidewalk"]'), 4),
    "protected_lane": (_in_berlin('way["cycleway:right:separation"]'), 4),
    "busway": (_in_berlin('way[~"^cycleway(:both|:right|:left)?$"~"share_busway"]'), 4),
    "separate": (_in_berlin('way["cycleway:both"="separate"]'), 4),
    # Ruling R17: groups that exercise the headline numerator (tiers A and B)
    "side_track": (
        _in_berlin('way["cycleway:right"="track"]', 'way["cycleway:both"="track"]'),
        4,
    ),
    "cycleway_no_foot": (_in_berlin('way["highway"="cycleway"][!"foot"]'), 4),
    "cycleway_foot_designated": (_in_berlin('way["highway"="cycleway"]["foot"="designated"]'), 4),
    "karl_marx_allee_paths": (_near(KMA, 30), 4),
    "unter_den_eichen_paths": (_near(UDE, 30), 4),
    "sidewalk_bicycle_designated": (
        _in_berlin(
            'way["sidewalk:right:bicycle"="designated"]',
            'way["sidewalk:both:bicycle"="designated"]',
        ),
        4,
    ),
}


def user_agent() -> str:
    contact = os.environ.get("VELOMETER_CONTACT", "").strip()
    return f"{USER_AGENT_BASE}; {contact}" if contact else USER_AGENT_BASE


def check_json(payload: dict, group: str) -> list[dict]:
    """Return the elements; raise if Overpass flagged a partial result with a `remark`."""
    if "remark" in payload:
        raise RuntimeError(f"Overpass remark for group {group!r}: {payload['remark']}")
    return payload["elements"]


def check_xml(xml: str, ids: list[int]) -> None:
    """Raise on an Overpass `<remark>` or if any picked way id is missing from the download."""
    remark = re.search(r"<remark>(.*?)</remark>", xml, re.S)
    if remark:
        raise RuntimeError(f"Overpass remark in phase 2: {remark.group(1).strip()}")
    got = {int(i) for i in re.findall(r'<way id="(\d+)"', xml)}
    missing = sorted(set(ids) - got)
    if missing:
        raise RuntimeError(f"phase 2 download lacks picked way ids {missing}")


EDITOR_ATTRS = re.compile(r' (?:changeset|uid|user)="[^"]*"')


def strip_editor_metadata(xml: str) -> str:
    """The download without the mapper's user name, uid and changeset (never kept in the repo)."""
    return EDITOR_ATTRS.sub("", xml)


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
    for group, (body, cap) in GROUPS.items():
        q = f'[out:json][timeout:90];area["name"="Berlin"]["admin_level"="4"]->.b;{body}out ids;'
        ids = sorted(e["id"] for e in check_json(overpass(client, q).json(), group))
        fresh = [i for i in ids if i not in seen][:cap]  # a way belongs to its first group only
        seen.update(fresh)
        picked[group] = fresh
        print(group, len(ids), "found", flush=True)
    return picked


def phase2(client: httpx.Client, ids: list[int], stamp: str) -> None:
    q = f"[timeout:180];way(id:{','.join(map(str, ids))});(._;>;);out meta;"
    xml = strip_editor_metadata(overpass(client, q).text)
    check_xml(xml, ids)
    comment = f"<!-- Overpass API, fetched {stamp}; (c) OpenStreetMap contributors, ODbL 1.0 -->"
    xml = re.sub(r"(<\?xml[^>]*\?>)", lambda m: f"{m.group(1)}\n{comment}", xml, count=1)
    (FIX / "berlin_golden.osm").write_text(xml, encoding="utf-8")


def write_yaml(picked: dict[str, list[int]], source: str) -> None:
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
                    "bidirectional": c.attrs["bidirectional"],
                }
            )
    entries = []
    for group, ids in picked.items():
        for wid in ids:
            if wid not in ways:
                raise RuntimeError(f"picked way {wid} ({group}) not readable from the download")
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
        "source": source,
        "classifier_version": "v1",
        "ways": entries,
    }
    (FIX / "berlin_golden.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    for group in picked:
        print(f"{group:20s} {sum(1 for e in entries if e['group'] == group)}")
    print(f"{'TOTAL':20s} {len(entries)}")
    if len(entries) < MIN_TOTAL:
        sys.exit(f"only {len(entries)} ways, need >= {MIN_TOTAL}")


def reclassify() -> None:
    """Offline: re-derive proposals for the already-downloaded ways (no network)."""
    old = yaml.safe_load((FIX / "berlin_golden.yaml").read_text())
    picked: dict[str, list[int]] = {}
    for w in old["ways"]:
        picked.setdefault(w["group"], []).append(w["way_id"])
    write_yaml(picked, old["source"])


def main() -> None:
    if sys.argv[1:] == ["--reclassify"]:
        reclassify()
        return
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with httpx.Client(headers={"User-Agent": user_agent()}, timeout=240) as client:
        picked = phase1(client)
        ids = sorted({i for v in picked.values() for i in v})
        print({g: len(v) for g, v in picked.items()})
        phase2(client, ids, stamp)
    write_yaml(picked, f"Overpass API, fetched {stamp}; © OpenStreetMap contributors, ODbL 1.0")


if __name__ == "__main__":
    main()
