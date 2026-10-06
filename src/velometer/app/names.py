"""Display names shared by the navigation, the Cities page and the series payload."""

# English country names for the ISO codes in config/cities.yaml (navigation and the Cities page)
COUNTRY_NAMES = {
    "AT": "Austria",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "HU": "Hungary",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
}


def country_name(iso2: str) -> str:
    return COUNTRY_NAMES.get(iso2, iso2)
