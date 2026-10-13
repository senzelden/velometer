"""The `/data/search.json` model (M11 Task 7): what the nav search can jump to. Every entry is
`{label, kind, url, terms}`; `url` is the path without the base (search.js adds it), `terms` the
words besides the label that find it. Display data only: the aliases are not classifier input."""

import logging
from pathlib import Path

from velometer.app.names import country_name
from velometer.content.loader import load_narratives, load_organisations
from velometer.i18n import Lang, t
from velometer.report.data import ReportData

log = logging.getLogger(__name__)


def pages(lang: Lang = "en") -> list[tuple[str, str]]:
    """The fixed pages the search finds: (label in `lang`, path)."""
    return [
        (t(lang, "nav.overview"), "/"), (t(lang, "nav.compare"), "/compare"),
        (t(lang, "nav.cities"), "/cities"), (t(lang, "nav.stories"), "/stories"),
        (t(lang, "nav.plans"), "/plans"), (t(lang, "nav.organisations"), "/organisations"),
        (t(lang, "nav.sources"), "/sources"), (t(lang, "nav.methodology"), "/methodology"),
        (t(lang, "search.methodology_de"), "/methodology/de"),
        (t(lang, "page.differences.title"), "/differences"),
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
        for label, url in pages(lang)
        if lang == "en" or url not in LEGACY_DE_ONLY
    ]
    cities = data.cities()
    countries: dict[str, str] = {}  # iso2 -> name
    for c in cities:
        country = country_name(c.country_iso2, lang)
        countries[c.country_iso2] = country
        # the edition's name first, then the id and every other form (config/cities.yaml: the
        # local name, the German exonym, the aliases), in both editions
        out.append(_entry(f"{c.name} ({country})", "city", f"/city/{c.id}", c.name, c.id, *c.names))
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
        out.append(
            _entry(t(lang, "search.story_combined"), "story", "/stories", "stories", "narrative")
        )
    for c in cities:
        if c.id in narratives:
            label = t(lang, "search.story_city", city=c.name)
            out.append(_entry(label, "story", f"/city/{c.id}", c.name, c.id))
    return out
