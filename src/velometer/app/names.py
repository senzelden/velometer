"""Display names shared by the navigation, the Cities page and the series payload."""

from velometer.i18n import Lang, t


def country_name(iso2: str, lang: Lang = "en") -> str:
    """A country's name in `lang` (`country.<ISO2>` of the UI catalogue); a country the
    catalogue does not name shows its code."""
    try:
        return t(lang, f"country.{iso2}")
    except KeyError:
        return iso2
