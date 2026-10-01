"""Geofabrik public extracts: resolve the dated file behind -latest, fetch it, read its time."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlparse

import httpx

from velometer.osmium import fileinfo_timestamp
from velometer.sources.download import fetch, new_client

BASE = "https://download.geofabrik.de"


@dataclass(frozen=True)
class RegionFile:
    region: str
    path: Path
    url: str
    md5: str
    osm_timestamp: datetime


def resolve_dated(region: str, client: httpx.Client) -> str:
    latest = f"{BASE}/{region}-latest.osm.pbf"
    resp = client.head(latest, follow_redirects=False)
    if resp.status_code in (301, 302, 307, 308):
        return urljoin(latest, resp.headers["location"])
    resp.raise_for_status()
    return latest


def fetch_region(region: str, data_dir: Path, client: httpx.Client | None = None) -> RegionFile:
    own = client is None
    client = client or new_client()
    try:
        url = resolve_dated(region, client)
        md5_resp = client.get(url + ".md5")
        md5_resp.raise_for_status()
        md5 = md5_resp.text.split()[0]
        dst = data_dir / "raw" / PurePosixPath(urlparse(url).path).name
        fetch(url, dst, md5=md5, client=client)
    finally:
        if own:
            client.close()
    ts = fileinfo_timestamp(dst)
    if ts is None:
        raise RuntimeError(f"{dst}: no osmosis_replication_timestamp in the PBF header")
    return RegionFile(region, dst, url, md5, ts)
