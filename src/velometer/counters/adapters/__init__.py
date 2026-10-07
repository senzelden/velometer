"""Counter portal adapters (M8 spec §5.1).

Each adapter module has
- `fetch(entry, out_dir, fetch=_http_get) -> list[Path]`: download every URL of the entry into
  `out_dir` and record URL, licence and retrieval time per file in `retrieved.json`;
- `parse(paths, entry) -> (sites, records)`: `HourCount` records for an hourly portal,
  `DayCount` for a daily one; `CounterFormatError` on a missing sheet or column.

`download` is the shared `fetch`: files are named `<nn>_<last URL path segment>` in the order of
`entry.urls`, which is the order `parse` reads them in (later files win on overlapping hours).
Nothing is written unless every URL arrived.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

import httpx

from velometer.counters.model import CounterEntry

TIMEOUT_S = 300.0
RETRIEVED_FILE = "retrieved.json"

Fetch = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    r = httpx.get(url, timeout=TIMEOUT_S, follow_redirects=True)
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
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths, files = [], []
    for name, url, body, at in got:
        (out_dir / name).write_bytes(body)
        paths.append(out_dir / name)
        files.append({"file": name, "url": url, "retrieved_at": at, "bytes": len(body)})
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


def adapter(name: str) -> ModuleType:
    from velometer.counters.adapters import berlin, paris, vienna

    modules = {"berlin": berlin, "paris": paris, "vienna": vienna}
    if name not in modules:
        raise KeyError(f"no counter adapter {name!r} (have {', '.join(sorted(modules))})")
    return modules[name]
