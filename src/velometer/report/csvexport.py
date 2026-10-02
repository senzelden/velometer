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
ATTRIBUTION = "# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km, not built km"


def to_csv(rows: list[dict[str, str]], commit: str, generated_at: str) -> str:
    out = io.StringIO()
    out.write(f"{ATTRIBUTION}\n# velometer {commit} generated {generated_at}\n")
    writer = csv.DictWriter(out, CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
