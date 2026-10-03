"""Geofabrik public extracts: resolve the dated file behind -latest, fetch it, read its time."""

import functools
import hashlib
import json
import logging
import re
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx
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


@dataclass(frozen=True)
class IndexSnapshot:
    path: Path
    sha256: str


def fetch_index(
    data_dir: Path, *, client: httpx.Client | None = None, today: date | None = None
) -> IndexSnapshot:
    """Snapshot Geofabrik's public region index under a dated name; an existing one is kept.

    The sha256 of the snapshot file is returned for provenance.
    """
    today = today or date.today()
    dst = data_dir / "external" / "geofabrik" / f"index-v1-{today:%Y%m%d}.json"
    path = fetch(INDEX_URL, dst, client=client)
    return IndexSnapshot(path, hashlib.sha256(path.read_bytes()).hexdigest())


def load_index(path: Path) -> dict[str, dict]:
    """Map region id to {"geometry": WGS84 geom, "parent": id or None, "history": url or None,
    "pbf": url or None}."""
    out: dict[str, dict] = {}
    for f in json.loads(path.read_text())["features"]:
        p = f["properties"]
        urls = p.get("urls") or {}
        out[p["id"]] = {
            "geometry": shape(f["geometry"]),
            "parent": p.get("parent"),
            "history": urls.get("history"),
            "pbf": urls.get("pbf"),
        }
    return out


def region_geometry(index: dict[str, dict], region: str) -> BaseGeometry:
    """WGS84 geometry of a download path such as `europe/germany/berlin`, found by its pbf URL."""
    url = f"{BASE}/{region}-latest.osm.pbf"
    for v in index.values():
        if v.get("pbf") == url:
            return v["geometry"]
    raise ValueError(f"region {region} is not in the Geofabrik index")


def _project(geom: BaseGeometry, src: int, dst: int) -> BaseGeometry:
    tf = Transformer.from_crs(src, dst, always_xy=True)
    return transform(tf.transform, geom)


def to_3035(geom_wgs84: BaseGeometry) -> BaseGeometry:
    return _project(geom_wgs84, 4326, 3035)


def tolerance_m2(
    target_3035: BaseGeometry, *, tolerance_frac: float = 0.001, tolerance_km2: float = 1.0
) -> float:
    """Uncovered area accepted as covered: max(tolerance_frac of the target, tolerance_km2)."""
    return max(tolerance_frac * target_3035.area, tolerance_km2 * 1e6)


def uncovered_m2(target_3035: BaseGeometry, geoms_3035: list[BaseGeometry]) -> float:
    """Area of the target outside the union of geoms (all EPSG:3035)."""
    if not geoms_3035:
        return target_3035.area
    return target_3035.difference(unary_union(geoms_3035)).area


@dataclass(frozen=True)
class RegionSelection:
    regions: list[str]
    uncovered_km2: float


def regions_for(
    polygon_wgs84: BaseGeometry,
    index: dict[str, dict],
    *,
    buffer_m: float = 0,
    tolerance_frac: float = 0.001,
    tolerance_km2: float = 1.0,
) -> RegionSelection:
    """Leaf regions with history that cover polygon (buffered by buffer_m), within tolerance.

    Covered means the uncovered area is at most max(tolerance_frac * polygon area, tolerance_km2),
    measured in EPSG:3035. Leaves are regions no other region names as parent. A single leaf that
    covers is preferred (smallest area wins). Otherwise the intersecting leaves are dropped
    greedily, largest first, while the rest still cover, so specific regions beat aggregates.
    Raises ValueError when the leaves cannot cover the polygon within tolerance.
    """
    target = to_3035(polygon_wgs84)
    if buffer_m:
        target = target.buffer(buffer_m)
    near = _project(target, 3035, 4326)
    tol_m2 = tolerance_m2(target, tolerance_frac=tolerance_frac, tolerance_km2=tolerance_km2)
    parents = {v["parent"] for v in index.values()}
    leaves = {
        r: to_3035(v["geometry"])
        for r, v in index.items()
        if r not in parents and v["history"] and v["geometry"].intersects(near)
    }

    def uncovered(ids: list[str]) -> float:
        return uncovered_m2(target, [leaves[r] for r in ids])

    def selection(ids: list[str]) -> RegionSelection:
        return RegionSelection(sorted(ids), uncovered(ids) / 1e6)

    if not leaves:
        raise ValueError("no index leaf region with history intersects the polygon")
    singles = [r for r in leaves if uncovered([r]) <= tol_m2]
    if singles:
        return selection([min(singles, key=lambda r: leaves[r].area)])
    chosen = [r for r in leaves if leaves[r].intersects(target)]
    if uncovered(chosen) > tol_m2:
        raise ValueError(
            f"the index leaf regions with history do not cover the polygon: {sorted(chosen)}"
        )
    for r in sorted(chosen, key=lambda r: -leaves[r].area):
        rest = [o for o in chosen if o != r]
        if rest and uncovered(rest) <= tol_m2:
            chosen = rest
    return selection(chosen)


@dataclass(frozen=True)
class HistoryFile:
    region: str
    path: Path
    md5: str
    md5_source: Literal["published", "computed"]
    fetched_at: date


def set_md5(pairs: list[tuple[str, str]]) -> str:
    """md5 over the sorted `region:md5` lines of a region set (order independent)."""
    return hashlib.md5("\n".join(sorted(f"{r}:{m}" for r, m in pairs)).encode()).hexdigest()


def history_set_md5(files: list[HistoryFile]) -> str:
    return set_md5([(f.region, f.md5) for f in files])


def _auth_refused(e: DownloadError) -> bool:
    cause = e.__cause__
    return isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code in (401, 403)


log = logging.getLogger(__name__)

_EMPTY_MD5 = hashlib.md5(b"").hexdigest()


def _published_md5(url: str, client: httpx.Client) -> str | None:
    def get() -> str | None:
        resp = client.get(url + ".md5")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        words = resp.text.split()
        if words and words[0] == _EMPTY_MD5:
            # the md5 of zero bytes: a broken sidecar, never a PBF's
            log.warning(
                "%s: published md5 is the md5 of empty input; using the computed md5",
                url.rsplit("/", 1)[-1],
            )
            return None
        if not words or not re.fullmatch(r"[0-9a-f]{32}", words[0]):
            return None
        return words[0]

    return _with_retries(url + ".md5", get, 3, 5.0)


def _cached_history(hist: Path, slug: str, published: str) -> tuple[Path, date] | None:
    """A cached file of the region whose md5 is the published one, whatever day it was fetched.

    Newest first; the date in its name is when it was fetched.
    """
    pattern = f"{slug}_{'[0-9]' * 8}_{published[:8]}.osh.pbf"
    for known in sorted(hist.glob(pattern), reverse=True):
        if md5_of(known) == published:
            day = known.name.removeprefix(f"{slug}_")[:8]
            return known, datetime.strptime(day, "%Y%m%d").date()
    return None


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

    cookie_loader is called with the keyword `force` (cookie_loader(force=False) first); a
    401/403 asks it once for a fresh cookie (force=True) and retries once. None means
    load_or_login on data_dir. The cookie travels in the client's cookie jar, scoped to the
    history host, so same-host redirects keep it and foreign hosts never see it. With a published
    md5, a cached file of the region with that md5 is reused whatever day it was fetched (its
    fetched_at is that day); without one, only today's file is reused. The file is renamed to
    carry the first 8 hex of its md5.
    """
    today = today or date.today()
    url = index[region]["history"]
    host = urlparse(url).hostname
    slug = region.replace("/", "-")
    stem = f"{slug}_{today:%Y%m%d}"
    own_client = client is None
    client = client or new_client()
    auth_client = None
    if cookie_loader is None:
        auth_client = new_auth_client()
        cookie_loader = functools.partial(load_or_login, data_dir, client=auth_client)
    hist = data_dir / "history"
    cookie_name = None
    try:
        cookie = cookie_loader(force=False)
        for relogin_left in (True, False):
            cookie_name = cookie.name
            client.cookies.set(cookie.name, cookie.value, domain=host)
            try:
                published = _published_md5(url, client)
                if published:
                    cached = _cached_history(hist, slug, published)
                    if cached is not None:
                        path, fetched_at = cached
                        return HistoryFile(region, path, published, "published", fetched_at)
                else:
                    for known in sorted(hist.glob(f"{stem}_{'?' * 8}.osh.pbf")):
                        md5 = md5_of(known)
                        if known.name == f"{stem}_{md5[:8]}.osh.pbf":
                            return HistoryFile(region, known, md5, "computed", today)
                interim = hist / f"{stem}.osh.pbf"
                fetch(url, interim, md5=published, verify_length=published is None, client=client)
                break
            except DownloadError as e:
                if not (relogin_left and _auth_refused(e)):
                    raise
                cookie = cookie_loader(force=True)
    finally:
        if cookie_name:
            with suppress(KeyError):
                client.cookies.delete(cookie_name, domain=host)
        if own_client:
            client.close()
        if auth_client is not None:
            auth_client.close()
    md5 = published or md5_of(interim)
    final = interim.with_name(f"{stem}_{md5[:8]}.osh.pbf")
    interim.replace(final)
    return HistoryFile(region, final, md5, "published" if published else "computed", today)
