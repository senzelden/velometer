"""Geofabrik public extracts: resolve the dated file behind -latest, fetch it, read its time."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlparse

import httpx

from velometer.osmium import fileinfo_timestamp
from velometer.sources.download import DownloadError, fetch, is_transient, new_client

BASE = "https://download.geofabrik.de"


@dataclass(frozen=True)
class RegionFile:
    region: str
    path: Path
    url: str
    md5: str
    osm_timestamp: datetime


class _Glitch(Exception):
    """A mirror answer that is wrong but usually goes away on retry."""


def _with_retries[T](what: str, attempt_once: Callable[[], T], retries: int, backoff_s: float) -> T:
    """Call attempt_once, retrying transient HTTP errors and _Glitch; others raise at once."""
    for attempt in range(1, retries + 1):
        try:
            return attempt_once()
        except (httpx.HTTPError, _Glitch) as e:
            transient = isinstance(e, _Glitch) or is_transient(e)
            if attempt == retries or not transient:
                raise DownloadError(f"{what}: {e}") from e
            time.sleep(backoff_s * attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def resolve_dated(
    region: str, client: httpx.Client, *, retries: int = 4, backoff_s: float = 5.0
) -> str:
    latest = f"{BASE}/{region}-latest.osm.pbf"

    def once() -> str:
        resp = client.head(latest, follow_redirects=False)
        if resp.status_code in (301, 302, 307, 308):
            location = resp.headers.get("location")
            if not location:
                raise DownloadError(
                    f"{latest}: redirect {resp.status_code} without a location header"
                )
            # the mirror intermittently redirects to "<file>.osm.pbf/", which is no file
            if location.endswith("/"):
                raise _Glitch(f"redirect to {location!r} has a trailing slash")
            return urljoin(latest, location)
        resp.raise_for_status()
        return latest

    return _with_retries(latest, once, retries, backoff_s)


def fetch_region(
    region: str,
    data_dir: Path,
    client: httpx.Client | None = None,
    *,
    retries: int = 4,
    backoff_s: float = 5.0,
) -> RegionFile:
    own = client is None
    client = client or new_client()
    try:
        url = resolve_dated(region, client, retries=retries, backoff_s=backoff_s)

        def get_md5() -> str:
            resp = client.get(url + ".md5")
            resp.raise_for_status()
            return resp.text

        words = _with_retries(url + ".md5", get_md5, retries, backoff_s).split()
        if not words:
            raise DownloadError(f"{url}.md5: empty md5 file")
        md5 = words[0]
        dst = data_dir / "raw" / PurePosixPath(urlparse(url).path).name
        fetch(url, dst, md5=md5, client=client)
    finally:
        if own:
            client.close()
    ts = fileinfo_timestamp(dst)
    if ts is None:
        raise RuntimeError(f"{dst}: no osmosis_replication_timestamp in the PBF header")
    return RegionFile(region, dst, url, md5, ts)
