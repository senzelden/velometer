"""CSV text of the report rows: the data credits and provenance comments, then the table."""

import csv
import io
import re
from collections.abc import Iterable

from velometer import credits

CSV_COLUMNS = [
    "city_id",
    "boundary_kind",
    "label",
    "run_id",
    "osm_timestamp",
    "classifier_version",
    "config_sha256",
    "tier_A_km",
    "tier_B_km",
    "tier_C_km",
    "tier_D_km",
    "tier_E_km",
    "ab_km",
    "ours_headline",
    "ecf_qecio",
    "clean_cities_2025",
    "population_value",
    "population_year",
    "flags",
]
SUBAREA_CSV_COLUMNS = [
    "city_id",
    "subarea_id",
    "name",
    "run_id",
    "osm_timestamp",
    "classifier_version",
    "git_commit",
    "config_sha256",
    "boundary_sha256",
    "subarea_sha",
    "tier",
    "length_basis",
    "length_km",
]
ATTRIBUTION = f"# {credits.OSM_NOTICE} — OSM mapped km, not built km"
BOUNDARIES = f"# Boundaries: Eurostat GISCO, {credits.BOUNDARY_CREDIT}"


_NUMBER = re.compile(r"-\d[\d,]*(\.\d+)?")
_NO_DATA = frozenset({"-", "\u2013", "\u2014", "\u2212"})  # a lone dash: hyphen, en, em, minus


def safe_cell(value: str) -> str:
    """A cell a spreadsheet would run as a formula (OWASP CSV injection) gets a leading quote:
    `=`, `+`, `@`, tab and CR always, `-` unless the whole cell is a number or a lone dash (a
    no-data mark, which runs nothing). The same rule is `safeCell` in `static/js/download.js`."""
    if value in _NO_DATA:
        return value
    if value.startswith(("=", "+", "@", "\t", "\r")):
        return "'" + value
    if value.startswith("-") and not _NUMBER.fullmatch(value):
        return "'" + value
    return value


def csv_preamble(
    commit: str, generated_at: str, population_sources: Iterable[str | None] = ()
) -> str:
    """The comment lines: the OSM notice, the boundary notice, the population credit of the
    sources the rows used (`runs.population_source`) with the per-capita disclaimer (none when
    no row has a population), then the commit and time of this export."""
    lines = [ATTRIBUTION, BOUNDARIES]
    lines += [f"# {line}" for line in credits.population_lines(population_sources)]
    lines.append(f"# velometer {commit} generated {generated_at}")
    return "\n".join(lines) + "\n"


def csv_table(rows: list[dict[str, str]], columns: list[str] = CSV_COLUMNS) -> str:
    """The header and the rows (what stays the same while the data does)."""
    out = io.StringIO()
    writer = csv.DictWriter(out, columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        {k: safe_cell(v) if isinstance(v, str) else v for k, v in r.items()} for r in rows
    )
    return out.getvalue()


def to_csv(
    rows: list[dict[str, str]],
    commit: str,
    generated_at: str,
    population_sources: Iterable[str | None] = (),
) -> str:
    return csv_preamble(commit, generated_at, population_sources) + csv_table(rows)
