"""Madrid: "Aforos de bicicletas" from datos.madrid.es (dataset 300321-0-aforos-peatones-
bicicletas, CC BY 4.0), hourly per counter (`identificador`, one per direction: PERM_BICI01_PM01).

One `;`-separated CSV per year (2019 from September; the 2021 and 2024 files end in June).
Files: none from July 2021 to August 2022; portal: interruption August 2021 to September 2022,
when the detectors were replaced. Two
header schemas: 2019-2021 upper case (`FECHA;HORA;IDENTIFICADOR;BICICLETAS;...;NOMBRE_VIAL;
NÚMERO;...;OBSERVACIONES_DIRECCION;LATITUD;LONGITUD`, decimal commas), 2022-2024 lower case
(`fecha;hora;identificador;bicicletas;device_id;...;direccion;observaciones_direccion;latitude;
longitude`). The 2022 and 2023 files are UTF-8 encoded twice (`NÃºmero`); such text is repaired.
Their coordinates use dots as group separators (`40.405.472`): the first dot is the decimal
point. `fecha` is `dd/mm/yyyy` with or without the time; the hour is `hora` (`H:MM`), local wall
clock. An empty count is a missing hour.

A row repeating a counter's hour within a file is
- with another address, a duplicate listing (2020: PERM_BICI16_PM01/PM02 from October, listed
  under two street numbers with the same counts): counted once; differing counts raise;
- with the same address, the second pass of the fall-back hour (2022, 2023 write `2:00` twice
  on that day): fold=1. Anywhere else it raises.
Files from 2019 to 2021 give the fall-back day 24 rows (incomplete) and the spring-forward day a
placeholder `2:00` row (ignored); 2022 to 2024 give 25 and 23 rows.

The site's name and coordinates are those of its latest row.
"""

import csv
import io
import re
from datetime import date, datetime
from pathlib import Path

from velometer.counters.adapters import _http_get, download
from velometer.counters.days import local_hours
from velometer.counters.model import CounterEntry, CounterFormatError, HourCount, Site

_HOUR = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")
_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")
REQUIRED = ("fecha", "hora", "identificador", "bicicletas")
LAT = ("latitud", "latitude")
LON = ("longitud", "longitude")


def fetch(
    entry: CounterEntry, out_dir: Path, data_dir: Path | None = None, fetch=_http_get
) -> list[Path]:
    return download(entry, out_dir, fetch)


def repair(text: str) -> str:
    """Undo a second UTF-8 encoding (`PirÃ¡mides` -> `Pirámides`); other text is unchanged."""
    if "Ã" not in text and "Â" not in text:
        return text
    for enc in ("latin-1", "cp1252"):
        try:
            return text.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


def coordinate(v: str) -> float | None:
    """`40,40547173`, `40.405472` or `40.405.472` (dots grouping digits after the decimal dot)."""
    v = v.strip().replace(",", ".")
    if not v:
        return None
    head, dot, rest = v.partition(".")
    try:
        return float(head + dot + rest.replace(".", ""))
    except ValueError:
        return None


def _squash(v: str) -> str:
    return " ".join(repair(v).split())


def _column(header: list[str], names: tuple[str, ...]) -> int | None:
    for n in names:
        if n in header:
            return header.index(n)
    return None


def _parse_file(path: Path, tz: str, hours: list[HourCount], sites: dict[str, Site]) -> None:
    text = path.read_bytes().decode("utf-8-sig")
    rows = csv.reader(io.StringIO(text, newline=""), delimiter=";")
    header = [repair(h).strip().lower() for h in next(rows, [])]
    for col in REQUIRED:
        if col not in header:
            raise CounterFormatError(path, f"column {col!r} missing")
    fi, hi, ii, bi = (header.index(c) for c in REQUIRED)
    lat_i, lon_i = _column(header, LAT), _column(header, LON)
    addr_i = _column(header, ("direccion",))
    street_i, number_i = _column(header, ("nombre_vial",)), _column(header, ("número",))
    if addr_i is None:  # 2019-2021: the address is the pair nombre_vial + número
        if street_i is None:
            raise CounterFormatError(path, "column 'nombre_vial' missing (no 'direccion')")
        if number_i is None:
            raise CounterFormatError(path, "column 'número' missing (no 'direccion')")
    obs_i = _column(header, ("observaciones_direccion",))
    # (counter, local hour, fold) -> (count, address)
    got: dict[tuple[str, datetime, int], tuple[int | None, str]] = {}
    for n, row in enumerate(rows, start=2):
        if not any(c.strip() for c in row):
            continue
        if len(row) < len(header):
            raise CounterFormatError(path, f"line {n}: {len(row)} fields, need {len(header)}")
        sid = row[ii].strip()
        d, h = _DATE.match(row[fi].strip()), _HOUR.match(row[hi].strip())
        if not sid or d is None or h is None or h.group(2) != "00":
            raise CounterFormatError(path, f"line {n}: no counter, date or whole hour")
        t = datetime.combine(date(int(d[3]), int(d[2]), int(d[1])), datetime.min.time())
        t = t.replace(hour=int(h.group(1)))
        raw = row[bi].strip()
        if raw and not raw.isdigit():
            raise CounterFormatError(path, f"line {n}: not a count {raw!r}")
        count = int(raw) if raw else None
        if addr_i is not None:
            address = _squash(row[addr_i])
        elif street_i is not None and number_i is not None:  # checked at the header
            address = _squash(f"{row[street_i]} {row[number_i]}")
        else:
            address = ""
        prev = got.get((sid, t, 0))
        fold = 0
        if prev is not None:
            if prev[1] != address:  # a duplicate listing under another address
                if count is not None and prev[0] is not None and count != prev[0]:
                    raise CounterFormatError(
                        path, f"line {n}: {sid} {t} listed twice with {prev[0]} and {count}"
                    )
                if prev[0] is None:
                    got[sid, t, 0] = (count, prev[1])
                continue
            if (sid, t, 1) in got or (t, 1) not in local_hours(t.date(), tz):
                raise CounterFormatError(path, f"line {n}: {sid} {t} repeated")
            fold = 1
        got[sid, t, fold] = (count, address)
        obs = _squash(row[obs_i]) if obs_i is not None else ""
        name = f"{address} ({obs})" if obs else address
        lat = coordinate(row[lat_i]) if lat_i is not None else None
        lon = coordinate(row[lon_i]) if lon_i is not None else None
        sites[sid] = Site(sid, name or sid, lat, lon)
    for (sid, t, fold), (count, _) in got.items():
        if count is not None:
            hours.append(HourCount(sid, t.replace(fold=fold), count))


def parse(paths: list[Path], entry: CounterEntry) -> tuple[list[Site], list[HourCount]]:
    hours: list[HourCount] = []
    sites: dict[str, Site] = {}
    for path in paths:
        _parse_file(Path(path), entry.timezone, hours, sites)
    return list(sites.values()), hours
