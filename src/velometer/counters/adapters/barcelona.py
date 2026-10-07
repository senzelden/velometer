"""Barcelona: Open Data BCN "aforaments" (CC BY 4.0), monthly average daily intensity per
gauge and day type: not counts (spec §2.14).

Two kinds of file, one per year, `,`-separated with quoted text, UTF-8 (some with a BOM):
- `<year>_aforament_descripcio.csv` (dataset aforaments-descriptiu): one row per gauge,
  `Id_aforament`, `Desc_aforament`, `Codi_tipus_aforament` (2 = `Bicis`), `Longitud`, `Latitud`;
- `<year>_aforament_detall_valor.csv` (aforaments-detall): `Any`, `Id_aforament`, `Mes`,
  `Codi_tipus_dia`, `Valor_IMD`, one row per gauge, month and day type (1 Monday, 2 working
  days, 3 Friday, 4 Saturday, 5 Sunday).

A gauge is a bike gauge when the latest descriptor listing it types it `Bicis` (the 2022-2024
descriptors type three Glòries tunnel gauges `Bicis`, the 2025 one traffic); its name and
coordinates are the latest descriptor's; a bike gauge without any value is not listed.
Descriptor rows with a field count other than the
header's are skipped (the 2017 file merges two gauges into one broken row with Valencia's
coordinates; both are described in later years). `Mesura no disponible` is a missing month, and
so is 0 (as a zero day elsewhere: a gauge not measuring). Files are read in `entry.urls` order;
a later value wins on the same gauge, month and day type.
"""

import csv
import io
from pathlib import Path

from velometer.counters.adapters import _http_get, download
from velometer.counters.model import CounterEntry, CounterFormatError, MonthValue, Site

BIKE_TYPE = "2"
NOT_AVAILABLE = "Mesura no disponible"
DAY_TYPES = {"1": "monday", "2": "working_day", "3": "friday", "4": "saturday", "5": "sunday"}
DESCRIPTOR = ("Id_aforament", "Desc_aforament", "Codi_tipus_aforament", "Longitud", "Latitud")
DETAIL = ("Any", "Id_aforament", "Mes", "Codi_tipus_dia", "Valor_IMD")


def fetch(entry: CounterEntry, out_dir: Path, fetch=_http_get) -> list[Path]:
    return download(entry, out_dir, fetch)


def _rows(path: Path, required: tuple[str, ...]):
    text = path.read_bytes().decode("utf-8-sig")
    rows = csv.reader(io.StringIO(text, newline=""))
    header = [h.strip() for h in next(rows, [])]
    for col in required:
        if col not in header:
            raise CounterFormatError(path, f"column {col!r} missing")
    return header, rows


def _float(v: str) -> float | None:
    try:
        return float(v.strip())
    except ValueError:
        return None


def _descriptor(path: Path, gauges: dict[str, tuple[bool, Site]]) -> None:
    header, rows = _rows(path, DESCRIPTOR)
    i = {c: header.index(c) for c in DESCRIPTOR}
    for row in rows:
        if len(row) != len(header):  # a broken row (2017); no row of another width is read
            continue
        gid = row[i["Id_aforament"]].strip()
        if not gid:
            continue
        lat, lon = _float(row[i["Latitud"]]), _float(row[i["Longitud"]])
        site = Site(gid, " ".join(row[i["Desc_aforament"]].split()) or gid, lat, lon)
        gauges[gid] = (row[i["Codi_tipus_aforament"]].strip() == BIKE_TYPE, site)


def _detail(path: Path, values: dict[tuple[str, str, str], float]) -> None:
    header, rows = _rows(path, DETAIL)
    i = {c: header.index(c) for c in DETAIL}
    for n, row in enumerate(rows, start=2):
        if not any(c.strip() for c in row):
            continue
        if len(row) != len(header):
            raise CounterFormatError(path, f"line {n}: {len(row)} fields, need {len(header)}")
        year, month = row[i["Any"]].strip(), row[i["Mes"]].strip()
        day_type = DAY_TYPES.get(row[i["Codi_tipus_dia"]].strip())
        if not (year.isdigit() and month.isdigit() and 1 <= int(month) <= 12) or day_type is None:
            raise CounterFormatError(path, f"line {n}: no year, month or known day type")
        raw = row[i["Valor_IMD"]].strip()
        if raw == NOT_AVAILABLE:
            continue
        value = _float(raw)
        if value is None or value < 0:
            raise CounterFormatError(path, f"line {n}: not an average daily value {raw!r}")
        key = (row[i["Id_aforament"]].strip(), f"{int(year):04d}-{int(month):02d}", day_type)
        if value == 0:
            values.pop(key, None)
            continue
        values[key] = value


def parse(paths: list[Path], entry: CounterEntry) -> tuple[list[Site], list[MonthValue]]:
    gauges: dict[str, tuple[bool, Site]] = {}
    values: dict[tuple[str, str, str], float] = {}
    for path in (Path(p) for p in paths):
        header = path.read_bytes()[:400].decode("utf-8-sig", errors="replace")
        if "Codi_tipus_aforament" in header:
            _descriptor(path, gauges)
        elif "Valor_IMD" in header:
            _detail(path, values)
        else:
            raise CounterFormatError(path, "neither a descriptor nor a detail file")
    bikes = {gid: site for gid, (is_bike, site) in gauges.items() if is_bike}
    months = [
        MonthValue(gid, month, day_type, v)
        for (gid, month, day_type), v in sorted(values.items())
        if gid in bikes
    ]
    with_values = {m.site_id for m in months}
    return [s for gid, s in bikes.items() if gid in with_values], months
