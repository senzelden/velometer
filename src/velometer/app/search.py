"""The `/data/search.json` model (M11 Task 7): what the nav search can jump to. Every entry is
`{label, kind, url, terms}`; `url` is the path without the base (search.js adds it), `terms` the
words besides the label that find it. Display data only: the aliases are not classifier input."""

import logging
from pathlib import Path

from velometer.app.names import country_name
from velometer.config import ConfigError, load_cities
from velometer.content.loader import load_narratives, load_organisations
from velometer.i18n import Lang
from velometer.report.data import ReportData

log = logging.getLogger(__name__)

PAGES = [
    ("Overview", "/"), ("Compare", "/compare"), ("Cities", "/cities"), ("Stories", "/stories"),
    ("Plans", "/plans"), ("Organisations", "/organisations"), ("Sources", "/sources"),
    ("Methodology", "/methodology"), ("Methodology (Deutsch)", "/methodology/de"),
    ("Why the figures differ", "/differences"),
]  # fmt: skip


def _entry(label: str, kind: str, url: str, *terms: str) -> dict:
    return {"label": label, "kind": kind, "url": url, "terms": list(dict.fromkeys([label, *terms]))}


# the legacy German methodology URL: on a German page `/methodology` is already German, and
# search.js puts the page's `/de` in front of every entry
LEGACY_DE_ONLY = {"/methodology/de"}


def search_index(
    data: ReportData, config_dir: Path, content_dir: Path, lang: Lang = "en"
) -> list[dict]:
    """The index for the trusted cities of `data`, for pages in `lang` (`/de/data/search.json`).
    A broken or missing content file leaves its entries out, as the pages it feeds show a note
    instead."""
    out = [
        _entry(label, "page", url)
        for label, url in PAGES
        if lang == "en" or url not in LEGACY_DE_ONLY
    ]
    cities = data.cities()
    try:
        aliases = {c.id: c.aliases for c in load_cities(Path(config_dir) / "cities.yaml")}
    except (ConfigError, OSError) as e:
        log.error("search index: config/cities.yaml could not be read: %s", e)
        aliases = {}
    countries: dict[str, str] = {}  # iso2 -> name
    for c in cities:
        country = country_name(c.country_iso2)
        countries[c.country_iso2] = country
        out.append(
            _entry(
                f"{c.name} ({country})",
                "city",
                f"/city/{c.id}",
                c.name,
                c.id,
                *aliases.get(c.id, []),
            )
        )
    for iso2, name in sorted(countries.items(), key=lambda kv: kv[1]):
        out.append(_entry(name, "country", f"/cities#{iso2.lower()}", iso2))
    errors: dict[str, str] = {}
    try:
        orgs = load_organisations(Path(content_dir) / "organisations", errors=errors)
        narratives = load_narratives(Path(content_dir) / "narratives", errors=errors)
    except OSError as e:  # pragma: no cover - the loaders record per-file errors
        log.error("search index: content could not be read: %s", e)
        orgs, narratives = {}, {}
    for name, why in sorted(errors.items()):  # the pages show a note; the index says it here
        log.warning("search index: left out content %s: %s", name, why)
    for org in sorted(orgs.values(), key=lambda o: o.name.lower()):
        out.append(_entry(org.name, "organisation", f"/organisations#{org.id}", org.id))
    if "combined" in narratives:
        out.append(_entry("The story across cities", "story", "/stories", "stories", "narrative"))
    for c in cities:
        if c.id in narratives:
            out.append(_entry(f"The story of {c.name}", "story", f"/city/{c.id}", c.name, c.id))
    return out
