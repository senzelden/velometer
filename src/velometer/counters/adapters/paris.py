"""Paris: opendata.paris.fr bike counts (ODbL), hourly per counter, summed per counting site.

Files, in load order: the yearly archives of `comptage-velo-historique-donnees-compteurs` (a zip
holding one CSV) and the CSV export of the rolling 13-month `comptage-velo-donnees-compteurs`
(labels as headers, UTC). Every file has the same labelled columns but its own dialect: UTF-8 or
cp1252, `;` or `,`, counts as `12`, `12.0` or `1 007` (non-breaking space), and times as naive
local wall clock (`2022-01-01T00:00:00`), with an offset (`2019-01-01T07:00:00+01:00`) or as
`2024-01-02 19:00:00.000 +0100`. Times with an offset are converted to the entry's timezone.

The site (`Identifiant du site de comptage`) is the unit: counter ids within a site are
renumbered between yearly files, so each hour is the sum of the site's counters in that file. A
site-hour is present only when every counter of the site in service that day reports it; a
counter is in service from its first to its last reported day in the file (in the real files a
counter missing a day inside that span is an outage: 26, 39 and 30 counter-days in 2023-2025;
none is missing outside it), so a day with a counter's hours missing is incomplete. A counter
that lists one hour twice in a file (the spring-forward placeholder row, written as a
second `03:00+02:00`) keeps the larger count. Rows without a site id (an all-counters total per
hour in the 2024 and 2025 archives) are skipped.
"""

import csv
import io
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from velometer.counters.adapters import _http_get, download
from velometer.counters.days import sum_counters
from velometer.counters.model import CounterEntry, CounterFormatError, HourCount, Site

COLUMNS = {
    "counter": "Identifiant du compteur",
    "site": "Identifiant du site de comptage",
    "name": "Nom du site de comptage",
    "count": "Comptage horaire",
    "time": "Date et heure de comptage",
    "coords": "Coordonnées géographiques",
}


def fetch(entry: CounterEntry, out_dir: Path, fetch=_http_get) -> list[Path]:
    return download(entry, out_dir, fetch)


def _members(path: Path):
    """(label, binary stream) of each CSV in `path` (a zip archive or a bare CSV)."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = [
                n
                for n in z.namelist()
                if n.lower().endswith(".csv") and not n.startswith("__MACOSX/")
            ]
            if not names:
                raise CounterFormatError(path, "zip archive without a CSV file")
            for n in names:
                with z.open(n) as f:
                    yield f"{path}!{n}", f
    else:
        with open(path, "rb") as f:
            yield str(path), f


def _open_text(raw) -> tuple[str, io.TextIOWrapper]:
    """The header line and the rest of `raw` as text: UTF-8 when the header decodes as UTF-8,
    else cp1252 (the 2025 archive)."""
    first = raw.readline()
    try:
        header = first.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        header = first.decode("cp1252")
        enc = "cp1252"
    return header.lstrip("\ufeff"), io.TextIOWrapper(raw, encoding=enc, newline="")


def _coords(v: str) -> tuple[float | None, float | None]:
    parts = [p.strip() for p in v.split(",")]
    if len(parts) != 2 or not all(parts):
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None


def _count(v: str, where: str, label: str) -> int | None:
    v = v.replace("\xa0", "").replace(" ", "").strip()
    if not v:
        return None
    try:
        f = float(v)
    except ValueError as e:
        raise CounterFormatError(label, f"{where}: not a count {v!r}") from e
    if f < 0 or f != int(f):
        raise CounterFormatError(label, f"{where}: not a count {v!r}")
    return int(f)


class _Times:
    """Timestamp text -> naive local hour (fold set), cached: every counter repeats them."""

    def __init__(self, tz: str):
        self.zone = ZoneInfo(tz)
        self.cache: dict[str, datetime] = {}

    def __call__(self, text: str, label: str, where: str) -> datetime:
        hit = self.cache.get(text)
        if hit is not None:
            return hit
        s = text.strip().replace(" +", "+").replace(" -", "-")
        try:
            t = datetime.fromisoformat(s)
        except ValueError as e:
            raise CounterFormatError(label, f"{where}: not a time {text!r}") from e
        if t.tzinfo is not None:
            t = t.astimezone(self.zone).replace(tzinfo=None)  # keeps fold
        self.cache[text] = t
        return t


def _parse_member(label, stream, times, sites, hours) -> None:
    header_line, f = _open_text(stream)
    delim = ";" if header_line.count(";") >= header_line.count(",") else ","
    header = [h.strip() for h in next(csv.reader([header_line], delimiter=delim))]
    idx = {}
    for key, name in COLUMNS.items():
        if name not in header:
            raise CounterFormatError(label, f"column {name!r} missing")
        idx[key] = header.index(name)
    width = max(idx.values()) + 1
    per_counter: dict[tuple[str, str, datetime, int], int] = {}
    for n, row in enumerate(csv.reader(f, delimiter=delim), start=2):
        if len(row) < width:
            if not any(row):
                continue
            raise CounterFormatError(label, f"line {n}: {len(row)} fields, need {width}")
        site = row[idx["site"]].strip()
        if not site:  # the 2024 and 2025 archives add an unlabelled all-counters total per hour
            continue
        count = _count(row[idx["count"]], f"line {n}", label)
        if count is None:
            continue
        t = times(row[idx["time"]], label, f"line {n}")
        key = (site, row[idx["counter"]].strip(), t, t.fold)
        if per_counter.get(key, -1) < count:
            per_counter[key] = count
        prev = sites.get(site)
        if prev is None or prev[0] != label or prev[1].lat is None:
            lat, lon = _coords(row[idx["coords"]])
            if lat is None and prev is not None:  # a file without coordinates keeps the last
                lat, lon = prev[1].lat, prev[1].lon
            sites[site] = (label, Site(site, row[idx["name"]].strip(), lat, lon))
    hours.extend(sum_counters(per_counter))


def parse(paths: list[Path], entry: CounterEntry) -> tuple[list[Site], list[HourCount]]:
    times = _Times(entry.timezone)
    # the site as described by the latest file that has it (coordinates: the latest given)
    sites: dict[str, tuple[str, Site]] = {}
    hours: list[HourCount] = []
    for path in paths:
        for label, stream in _members(Path(path)):
            _parse_member(label, stream, times, sites, hours)
    return [s for _, s in sites.values()], hours
