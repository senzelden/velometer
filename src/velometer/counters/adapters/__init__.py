"""Counter portal adapters (M8 spec §5.1).

Each adapter module has
- `fetch(entry, out_dir, data_dir=None, fetch=_http_get) -> list[Path]`: download every URL of
  the entry into `out_dir` and record URL, licence and retrieval time per file in
  `retrieved.json` (`data_dir` is the data directory, for an adapter that reads the stored
  boundary while fetching: Oslo);
- `parse(paths, entry) -> (sites, records)`: `HourCount` records for an hourly portal,
  `DayCount` for a daily one; `CounterFormatError` on a missing sheet or column.

`download` is the shared `fetch`: files are named `<nn>_<last URL path segment>` in the order of
`entry.urls`, which is the order `parse` reads them in (later files win on overlapping hours).
Nothing is written unless every URL arrived. An adapter whose portal is an API (Oslo) writes its
own files and records them with `write_retrieved`.

`boundary_polygon` and `sites_inside` drop sites outside a city's stored boundary (an entry's
`boundary` key).
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

import httpx
import shapely

from velometer.counters.model import CounterEntry, CounterFormatError, Site
from velometer.sources.download import user_agent  # Open Data BCN answers httpx's own with 502

TIMEOUT_S = 300.0
RETRIEVED_FILE = "retrieved.json"

Fetch = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    r = httpx.get(
        url, timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": user_agent()}
    )
    r.raise_for_status()
    return r.content


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_name(index: int, url: str) -> str:
    segment = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1] or "download"
    return f"{index:02d}_{re.sub(r'[^A-Za-z0-9._-]', '_', segment)}"


def download(entry: CounterEntry, out_dir: Path, fetch: Fetch = _http_get) -> list[Path]:
    got = []
    for i, url in enumerate(entry.urls):
        got.append((file_name(i, url), url, fetch(url), _now()))
    return write_retrieved(entry, out_dir, got)


def write_retrieved(entry: CounterEntry, out_dir: Path, got: list[tuple]) -> list[Path]:
    """Write each `(name, url, body, retrieved_at[, extra])` file into `out_dir` and record them
    in `retrieved.json` (URL, licence, retrieval time, size; `extra` is merged into the file's
    record, e.g. the API query)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths, files = [], []
    for name, url, body, at, *extra in got:
        (out_dir / name).write_bytes(body)
        paths.append(out_dir / name)
        record = {"file": name, "url": url, "retrieved_at": at, "bytes": len(body)}
        for e in extra:
            record.update(e)
        files.append(record)
    meta = {
        "city": entry.city,
        "source": entry.source,
        "licence": entry.licence,
        "licence_url": entry.licence_url,
        "page": entry.page,
        "files": files,
    }
    (out_dir / RETRIEVED_FILE).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return paths


def read_retrieved(out_dir: Path) -> dict:
    """`retrieved.json` of a fetched city; FileNotFoundError when the city was not fetched."""
    path = Path(out_dir) / RETRIEVED_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def boundary_polygon(entry: CounterEntry, data_dir: Path):
    """The city's stored boundary named by `entry.boundary` (EPSG:4326), from
    `<data_dir>/boundaries/<city>_<kind>.geojson`; CounterFormatError when it is missing."""
    path = Path(data_dir) / "boundaries" / f"{entry.city}_{entry.boundary}.geojson"
    try:
        feats = json.loads(path.read_text(encoding="utf-8"))["features"]
    except (OSError, ValueError, KeyError) as e:
        raise CounterFormatError(path, f"stored {entry.boundary} boundary not readable: {e}") from e
    return shapely.union_all([shapely.from_geojson(json.dumps(f["geometry"])) for f in feats])


def sites_inside(sites: list[Site], polygon) -> set[str]:
    """Ids of the sites whose point lies inside `polygon` (a site without coordinates cannot be
    placed and is not inside)."""
    return {
        s.site_id
        for s in sites
        if s.lat is not None and s.lon is not None and polygon.covers(shapely.Point(s.lon, s.lat))
    }


def adapter(name: str) -> ModuleType:
    from velometer.counters.adapters import (
        barcelona,
        berlin,
        helsinki,
        madrid,
        oslo,
        paris,
        vienna,
    )

    modules = {
        "barcelona": barcelona,
        "berlin": berlin,
        "helsinki": helsinki,
        "madrid": madrid,
        "oslo": oslo,
        "paris": paris,
        "vienna": vienna,
    }
    if name not in modules:
        raise KeyError(f"no counter adapter {name!r} (have {', '.join(sorted(modules))})")
    return modules[name]
