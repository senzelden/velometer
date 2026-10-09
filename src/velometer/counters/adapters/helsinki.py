"""Helsinki: `Helsingin_pyorailijamaarat.xlsx` and `pyoralaskentapisteiden_sijainnit.csv` from
hel.fi via HRI (CC BY 4.0), hourly per counting point.

The workbook has one sheet: column `Päivämäärä_aika` is the local wall-clock hour (`Päivämäärä`
and `Aika` repeat it and are not read), every other headed column is a counting point named in
the header. A number is that hour's count; an empty cell or `''` is a missing hour. A few values
are fractional (33 cells in the 2026-08 file, e.g. 41.447 at Baana on 2021-03-10 09:00; the
file does not say why) and are rounded to the nearest integer. Up to 2024 the spring-forward day
carries a placeholder 03:00 row (ignored by `to_days`); from 2025 it has 23 rows. The fall-back
day has 24 rows (the repeated hour once), so it is incomplete. A time repeated in the file is
read as the second pass of the fall-back hour (fold=1) when that hour exists, else it is a
`CounterFormatError`.

Columns mapped to one site by `site_aliases` are summed (`days.sum_counters`): an hour counts
only when every mapped column in service that day reports it (a column is in service from its
first to its last reported day). The config maps the two sides of three bridges this way: the
file moves counts between their columns (publisher note: in 2016 both sides of the Kulosaari
bridge are in one column; docs/review/m8-counters.md).

The CSV gives each point's coordinates in ETRS-GK25 (EPSG:3879; "indicative" per the
publisher), `;`-separated with decimal commas, ISO-8859-1; a site of several columns gets the
mean of their points. A point without a coordinate row has none.
"""

import csv
import io
from datetime import datetime
from pathlib import Path

import openpyxl
from pyproj import Transformer

from velometer.counters.adapters import _http_get, download
from velometer.counters.days import CounterHours, local_hours, sum_counters
from velometer.counters.model import CounterEntry, CounterFormatError, HourCount, Site

TIME_COLUMN = "Päivämäärä_aika"
NOT_COUNTERS = {TIME_COLUMN, "Päivämäärä", "Aika"}
POINT_COLUMNS = ("piste", "x", "y")
POINT_EPSG = 3879  # ETRS-GK25


def fetch(
    entry: CounterEntry, out_dir: Path, data_dir: Path | None = None, fetch=_http_get
) -> list[Path]:
    return download(entry, out_dir, fetch)


def _points(path: Path) -> dict[str, tuple[float, float]]:
    """Point name -> (lat, lon) in EPSG:4326."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    rows = csv.reader(io.StringIO(text, newline=""), delimiter=";")
    header = [h.strip().lower() for h in next(rows, [])]
    for col in POINT_COLUMNS:
        if col not in header:
            raise CounterFormatError(path, f"column {col!r} missing")
    i_name, i_x, i_y = (header.index(c) for c in POINT_COLUMNS)
    to_wgs = Transformer.from_crs(POINT_EPSG, 4326, always_xy=True)
    out = {}
    for n, row in enumerate(rows, start=2):
        if not any(c.strip() for c in row):
            continue
        try:
            x = float(row[i_x].strip().replace(",", "."))
            y = float(row[i_y].strip().replace(",", "."))
        except (IndexError, ValueError) as e:
            raise CounterFormatError(path, f"line {n}: not a coordinate pair") from e
        lon, lat = to_wgs.transform(x, y)
        out[row[i_name].strip()] = (lat, lon)
    return out


def _count(v, where: str, path: Path) -> int | None:
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    if isinstance(v, bool) or not isinstance(v, int | float) or v < 0:
        raise CounterFormatError(path, f"{where}: not a count {v!r}")
    return round(v)


def _hours(path: Path, entry: CounterEntry, hours: list[HourCount], merged: CounterHours):
    """Read the workbook: hours of unaliased columns into `hours`, aliased ones into `merged`.
    Returns the column names read."""
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        rows = wb.worksheets[0].iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(rows, ())]
        if TIME_COLUMN not in header:
            raise CounterFormatError(path, f"column {TIME_COLUMN!r} missing")
        ti = header.index(TIME_COLUMN)
        columns = {i: h for i, h in enumerate(header) if h and h not in NOT_COUNTERS}
        if not columns:
            raise CounterFormatError(path, "no counter columns")
        aliases = entry.site_aliases
        seen: set[tuple[datetime, int]] = set()
        for n, row in enumerate(rows, start=2):
            t = row[ti] if ti < len(row) else None
            if t is None:
                continue
            if not isinstance(t, datetime):
                raise CounterFormatError(path, f"row {n}: {TIME_COLUMN} {t!r} is not a time")
            fold = 0
            if (t, 0) in seen:
                if (t, 1) in seen or (t, 1) not in local_hours(t.date(), entry.timezone):
                    raise CounterFormatError(path, f"row {n}: hour {t} repeated")
                fold = 1
            seen.add((t, fold))
            t = t.replace(fold=fold)
            for i, name in columns.items():
                count = _count(row[i] if i < len(row) else None, f"row {n} {name!r}", path)
                if count is None:
                    continue
                if name in aliases:
                    merged[aliases[name], name, t, fold] = count
                else:
                    hours.append(HourCount(name, t, count))
        return list(columns.values())
    finally:
        wb.close()


def parse(paths: list[Path], entry: CounterEntry) -> tuple[list[Site], list[HourCount]]:
    points: dict[str, tuple[float, float]] = {}
    hours: list[HourCount] = []
    names: list[str] = []
    workbooks = [Path(p) for p in paths if Path(p).suffix.lower() == ".xlsx"]
    if not workbooks:
        raise CounterFormatError(paths[0] if paths else "helsinki", "no .xlsx file")
    for path in (Path(p) for p in paths):
        if path.suffix.lower() == ".csv":
            points.update(_points(path))
    for path in workbooks:
        merged: CounterHours = {}
        names += _hours(path, entry, hours, merged)
        hours.extend(sum_counters(merged))
    members: dict[str, list[str]] = {}
    for name in dict.fromkeys(names):
        members.setdefault(entry.site_aliases.get(name, name), []).append(name)
    sites = []
    for site_id, cols in members.items():
        located = [points[c] for c in cols if c in points]
        if located and len(located) == len(cols):
            lat = sum(p[0] for p in located) / len(located)
            lon = sum(p[1] for p in located) / len(located)
        else:
            lat = lon = None
        sites.append(Site(site_id, site_id, lat, lon))
    return sites, hours
