"""Berlin: the Senate's `gesamtdatei-stundenwerte.xlsx` (dl-de-zero-2.0), hourly per direction.

Sheets read: `Legende` (the fill of its `0` cell marks "no or implausible data"), `Standortdaten`
(one row per direction: id, description, latitude, longitude) and every `Jahresdatei <year>`
(column A the local wall-clock hour, one column per direction headed `<id> <install date>`).
A cell is a count when it holds a number and does not carry the implausible-data fill; an empty
cell, `''` or a flagged cell is a missing hour. Reconstructed values (another fill) are counts.
Header ids renumbered between years map to their `Standortdaten` id via `site_aliases`. The
`2012` sheet also holds 2013; the `2013` sheet, read later, wins on those hours.
"""

import re
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from velometer.counters.adapters import _http_get, download
from velometer.counters.model import CounterEntry, CounterFormatError, HourCount, Site

LEGEND = "Legende"
SITES = "Standortdaten"
YEAR_SHEET = re.compile(r"^Jahresdatei (\d{4})$")
SITE_COLUMNS = {
    "id": "Zählstelle",
    "name": "Beschreibung - Fahrtrichtung",
    "lat": "Breitengrad",
    "lon": "Längengrad",
}


def fetch(entry: CounterEntry, out_dir: Path, fetch=_http_get) -> list[Path]:
    return download(entry, out_dir, fetch)


def _fill(cell) -> str | None:
    f = cell.fill
    if f is None or f.patternType != "solid":
        return None
    rgb = f.fgColor.rgb
    return rgb if isinstance(rgb, str) else None


def _invalid_fill(wb, path: Path) -> str:
    for row in wb[LEGEND].iter_rows():
        for c in row:
            if c.value == 0 and not isinstance(c.value, bool):
                fill = _fill(c)
                if fill:
                    return fill
    raise CounterFormatError(path, f"sheet {LEGEND!r}: no filled legend cell for 0 (no data)")


def _sites(wb, path: Path) -> dict[str, Site]:
    rows = wb[SITES].iter_rows(values_only=True)
    header = [str(v).strip() if v is not None else "" for v in next(rows, ())]
    idx = {}
    for key, label in SITE_COLUMNS.items():
        if label not in header:
            raise CounterFormatError(path, f"sheet {SITES!r}: column {label!r} missing")
        idx[key] = header.index(label)
    out = {}
    for r in rows:
        sid = r[idx["id"]]
        if sid is None or str(sid).strip() == "":
            continue
        sid = str(sid).strip()
        lat, lon = r[idx["lat"]], r[idx["lon"]]
        out[sid] = Site(
            sid,
            str(r[idx["name"]]).strip(),
            float(lat) if lat is not None else None,
            float(lon) if lon is not None else None,
        )
    return out


def _count(cell, invalid: str) -> int | None:
    """The cell's count; None for a missing or flagged hour; ValueError for anything else."""
    v = cell.value
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    if isinstance(v, bool) or not isinstance(v, int | float) or v < 0 or v != int(v):
        raise ValueError(f"not a count: {v!r}")
    if _fill(cell) == invalid:
        return None
    return int(v)


def _year_sheet(ws, sites, aliases, invalid, path: Path, hours: list[HourCount]) -> None:
    rows = ws.iter_rows()
    header = next(rows, ())
    columns: dict[int, str] = {}
    for i, c in enumerate(header[1:], start=1):
        if c.value is None or str(c.value).strip() == "":
            continue
        raw_id = str(c.value).split()[0]
        sid = aliases.get(raw_id, raw_id)
        if sid not in sites:
            raise CounterFormatError(
                path, f"sheet {ws.title!r}: column {raw_id!r} is not a site of {SITES!r}"
            )
        if sid in columns.values():
            raise CounterFormatError(path, f"sheet {ws.title!r}: site {sid!r} in two columns")
        columns[i] = sid
    if not columns:
        raise CounterFormatError(path, f"sheet {ws.title!r}: no counter columns")
    for row in rows:
        t = row[0].value
        if t is None:
            continue
        if not isinstance(t, datetime):
            raise CounterFormatError(path, f"sheet {ws.title!r} row {row[0].row}: not a time")
        for i, sid in columns.items():
            if i >= len(row):
                continue
            try:
                n = _count(row[i], invalid)
            except ValueError as e:
                cell = f"{get_column_letter(i + 1)}{row[0].row}"
                raise CounterFormatError(path, f"sheet {ws.title!r} cell {cell}: {e}") from e
            if n is not None:
                hours.append(HourCount(sid, t, n))


def parse(paths: list[Path], entry: CounterEntry) -> tuple[list[Site], list[HourCount]]:
    sites: dict[str, Site] = {}
    hours: list[HourCount] = []
    for path in paths:
        wb = openpyxl.load_workbook(path, read_only=True)
        try:
            for name in (LEGEND, SITES):
                if name not in wb.sheetnames:
                    raise CounterFormatError(path, f"sheet {name!r} missing")
            year_sheets = sorted(
                (int(m.group(1)), n) for n in wb.sheetnames if (m := YEAR_SHEET.match(n))
            )
            if not year_sheets:
                raise CounterFormatError(path, "no 'Jahresdatei <year>' sheet")
            invalid = _invalid_fill(wb, path)
            file_sites = _sites(wb, path)
            for _, name in year_sheets:
                _year_sheet(wb[name], file_sites, entry.site_aliases, invalid, path, hours)
            sites.update(file_sites)
        finally:
            wb.close()
    return list(sites.values()), hours
