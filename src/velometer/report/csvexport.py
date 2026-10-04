"""CSV text of the report rows: ODbL attribution and provenance comments, then the table."""

import csv
import io

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
ATTRIBUTION = "# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km, not built km"


def csv_preamble(commit: str, generated_at: str) -> str:
    """The two comment lines: attribution, then the commit and time of this export."""
    return f"{ATTRIBUTION}\n# velometer {commit} generated {generated_at}\n"


def csv_table(rows: list[dict[str, str]], columns: list[str] = CSV_COLUMNS) -> str:
    """The header and the rows (what stays the same while the data does)."""
    out = io.StringIO()
    writer = csv.DictWriter(out, columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def to_csv(rows: list[dict[str, str]], commit: str, generated_at: str) -> str:
    return csv_preamble(commit, generated_at) + csv_table(rows)
