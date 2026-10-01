"""Geofabrik public extracts: resolve the dated file behind -latest, fetch it, read its time."""

import functools
import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx
import shapely
from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

from velometer.osmium import fileinfo_timestamp
from velometer.sources.download import DownloadError, fetch, is_transient, md5_of, new_client
from velometer.sources.geofabrik_auth import Cookie, load_or_login, new_auth_client

BASE = "https://download.geofabrik.de"
INDEX_URL = "https://download.geofabrik.de/index-v1.json"


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
            words = resp.text.split()
            # an error page served with 200 is no md5: retry rather than report a mismatch
            if not words or not re.fullmatch(r"[0-9a-f]{32}", words[0]):
                raise _Glitch(f"not an md5 file: {resp.text[:60]!r}")
            return words[0]

        md5 = _with_retries(url + ".md5", get_md5, retries, backoff_s)
        dst = data_dir / "raw" / PurePosixPath(urlparse(url).path).name
        fetch(url, dst, md5=md5, client=client)
    finally:
        if own:
            client.close()
    ts = fileinfo_timestamp(dst)
    if ts is None:
        raise RuntimeError(f"{dst}: no osmosis_replication_timestamp in the PBF header")
    return RegionFile(region, dst, url, md5, ts)


def fetch_index(
    data_dir: Path, *, client: httpx.Client | None = None, today: date | None = None
) -> Path:
    """Snapshot Geofabrik's public region index under a dated name; an existing snapshot is kept."""
    today = today or date.today()
    dst = data_dir / "external" / "geofabrik" / f"index-v1-{today:%Y%m%d}.json"
    return fetch(INDEX_URL, dst, client=client)


def load_index(path: Path) -> dict[str, dict]:
    """Map region id to {"geometry": WGS84 geom, "parent": id or None, "history": url or None}."""
    out: dict[str, dict] = {}
    for f in json.loads(path.read_text())["features"]:
        p = f["properties"]
        out[p["id"]] = {
            "geometry": shape(f["geometry"]),
            "parent": p.get("parent"),
            "history": (p.get("urls") or {}).get("history"),
        }
    return out


def _project(geom: BaseGeometry, src: int, dst: int) -> BaseGeometry:
    tf = Transformer.from_crs(src, dst, always_xy=True)
    return transform(tf.transform, geom)


def regions_for(polygon_wgs84: BaseGeometry, index: dict[str, dict], *, buffer_m: float = 1000):
    """Ids of the fewest-ish leaf regions with history that cover polygon buffered by buffer_m.

    Leaves are regions no other region names as parent. Candidates intersecting the buffered
    polygon are dropped greedily, smallest intersection first, while the rest still cover it.
    Raises ValueError when the leaves cannot cover the buffered polygon at all.
    """
    target = _project(_project(polygon_wgs84, 4326, 3035).buffer(buffer_m), 3035, 4326)
    target = shapely.make_valid(target) if not target.is_valid else target
    parents = {v["parent"] for v in index.values()}
    chosen = [
        r
        for r, v in index.items()
        if r not in parents and v["history"] and v["geometry"].intersects(target)
    ]
    if not chosen or not unary_union([index[r]["geometry"] for r in chosen]).contains(target):
        raise ValueError(f"the index leaf regions with history do not cover the polygon: {chosen}")
    # ties (an aggregate like "dach" covers the polygon as fully as "berlin") drop the larger region
    chosen.sort(
        key=lambda r: (
            round(index[r]["geometry"].intersection(target).area / target.area, 6),
            -index[r]["geometry"].area,
        )
    )
    for r in list(chosen):
        rest = [index[o]["geometry"] for o in chosen if o != r]
        if rest and unary_union(rest).contains(target):
            chosen.remove(r)
    return sorted(chosen)


@dataclass(frozen=True)
class HistoryFile:
    region: str
    path: Path
    md5: str
    md5_source: Literal["published", "computed"]
    fetched_at: date


def history_set_md5(files: list[HistoryFile]) -> str:
    return hashlib.md5("\n".join(sorted(f"{f.region}:{f.md5}" for f in files)).encode()).hexdigest()


def _auth_refused(e: DownloadError) -> bool:
    cause = e.__cause__
    return isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code in (401, 403)


def _published_md5(url: str, client: httpx.Client, headers: dict[str, str]) -> str | None:
    def get() -> str | None:
        resp = client.get(url + ".md5", headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        words = resp.text.split()
        return words[0] if words and re.fullmatch(r"[0-9a-f]{32}", words[0]) else None

    return _with_retries(url + ".md5", get, 3, 5.0)


def fetch_history(
    region: str,
    data_dir: Path,
    index: dict[str, dict],
    *,
    client: httpx.Client | None = None,
    cookie_loader: Callable[..., Cookie] | None = None,
    today: date | None = None,
) -> HistoryFile:
    """Download a region's full-history PBF from Geofabrik's login-only server.

    cookie_loader(force=False) yields the auth cookie; a 401/403 asks it once for a fresh one
    (force=True) and retries once. The file is renamed to carry the first 8 hex of its md5.
    """
    today = today or date.today()
    url = index[region]["history"]
    slug = region.replace("/", "-")
    own_client = client is None
    client = client or new_client()
    auth_client = None
    if cookie_loader is None:
        auth_client = new_auth_client()
        cookie_loader = functools.partial(load_or_login, data_dir, client=auth_client)
    hist = data_dir / "history"
    try:
        cookie = cookie_loader(False)
        for relogin_left in (True, False):
            headers = {"Cookie": cookie.header()}
            try:
                published = _published_md5(url, client, headers)
                if published:
                    known = hist / f"{slug}_{today:%Y%m%d}_{published[:8]}.osh.pbf"
                    if known.exists() and md5_of(known) == published:
                        return HistoryFile(region, known, published, "published", today)
                interim = hist / f"{slug}_{today:%Y%m%d}.osh.pbf"
                fetch(url, interim, md5=published, client=client, headers=headers)
                break
            except DownloadError as e:
                if not (relogin_left and _auth_refused(e)):
                    raise
                cookie = cookie_loader(True)
    finally:
        if own_client:
            client.close()
        if auth_client is not None:
            auth_client.close()
    md5 = published or md5_of(interim)
    final = interim.with_name(f"{slug}_{today:%Y%m%d}_{md5[:8]}.osh.pbf")
    interim.replace(final)
    return HistoryFile(region, final, md5, "published" if published else "computed", today)
