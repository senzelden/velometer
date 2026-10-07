"""Vienna: `radverkehrszaehlungen.csv` from data.gv.at (CC BY 4.0), daily per counter.

One `;`-separated row per day (`Datum` as YYYYMMDD), one column per counter, headed by the
counter's name. A number is that day's count (a `.` groups thousands: `1.121` is 1121); an empty
cell is a day not reported. Columns named in `exclude_columns` aggregate others (`Opernring` is
`Opernring Innen` + `Opernring Außen` on every row) and are left out. The file has no
coordinates, so sites carry none.
"""

import csv
import re
from datetime import date
from pathlib import Path

from velometer.counters.adapters import _http_get, download
from velometer.counters.model import CounterEntry, CounterFormatError, DayCount, Site

DATE_COLUMN = "Datum"
_COUNT = re.compile(r"^\d{1,3}(\.\d{3})+$|^\d+$")


def fetch(entry: CounterEntry, out_dir: Path, fetch=_http_get) -> list[Path]:
    return download(entry, out_dir, fetch)


def _parse_file(path: Path, exclude: list[str], days: list[DayCount], sites: dict) -> None:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = csv.reader(f, delimiter=";")
        header = [h.strip() for h in next(rows, [])]
        if DATE_COLUMN not in header:
            raise CounterFormatError(path, f"column {DATE_COLUMN!r} missing")
        for col in exclude:
            if col not in header:
                raise CounterFormatError(path, f"excluded column {col!r} missing")
        di = header.index(DATE_COLUMN)
        columns = {
            i: name for i, name in enumerate(header) if i != di and name and name not in exclude
        }
        for name in columns.values():
            sites.setdefault(name, Site(name, name, None, None))
        for n, row in enumerate(rows, start=2):
            if not row or not row[di].strip():
                continue
            raw = row[di].strip()
            if not re.fullmatch(r"\d{8}", raw):
                raise CounterFormatError(path, f"line {n}: {DATE_COLUMN} {raw!r} is not YYYYMMDD")
            day = date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
            for i, name in columns.items():
                v = row[i].strip() if i < len(row) else ""
                if not v:
                    continue
                if not _COUNT.match(v):
                    raise CounterFormatError(path, f"line {n} column {name!r}: not a count {v!r}")
                days.append(DayCount(name, day, int(v.replace(".", "")), True))


def parse(paths: list[Path], entry: CounterEntry) -> tuple[list[Site], list[DayCount]]:
    days: list[DayCount] = []
    sites: dict[str, Site] = {}
    for path in paths:
        _parse_file(Path(path), entry.exclude_columns, days, sites)
    latest = {(d.site_id, d.day): d for d in days}  # a later file wins on a repeated day
    return list(sites.values()), [latest[k] for k in sorted(latest)]
