"""The data credits downloads and pages carry (ADR 0008; docs/review/m16-legal.md 1.1b-1.3).

- `OSM_NOTICE`: the one OSM notice of every download file, with the copyright page's and the
  licence's URIs (ODbL 1.0 §4.2 b). `OSM_PRINTED` is the same notice printed on an image or put
  in a page's strings: without a scheme, so no page names a host it does not load from.
- `BOUNDARY_CREDIT`: the notice GISCO prescribes for its LAU and FUA boundaries, word for word
  (the German one is `credit.boundaries` of the German catalogue).
- `population_credit`: the credit each statistics office asks for, chosen from the source string
  a run stores (`runs.population_source`); `population_lines` turns a file's sources into its
  preamble lines, with the disclaimer Eurostat asks for on derived figures.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from velometer import i18n

OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
ODBL_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
OSM_NOTICE = f"Map data © OpenStreetMap contributors ({OSM_COPYRIGHT_URL}), ODbL 1.0 ({ODBL_URL})"
OSM_PRINTED = (
    "Map data © OpenStreetMap contributors (openstreetmap.org/copyright), "
    "ODbL 1.0 (opendatacommons.org/licenses/odbl/1-0/)"
)
GISCO_TERMS_URL = "https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units"
BOUNDARY_CREDIT = "© EuroGeographics for the administrative boundaries"
BOUNDARY_NOTE = (
    f"The `boundary` member is Eurostat GISCO data, {BOUNDARY_CREDIT}, used under GISCO's terms "
    f"({GISCO_TERMS_URL}), not under ODbL."
)

EUROSTAT, INSEE, INE = "Eurostat", "INSEE", "INE"
# body -> (the credit it asks for, the credit's language)
CREDITS = {
    EUROSTAT: ("Eurostat", "en"),
    INSEE: ("Source : Insee", "fr"),
    INE: ("Elaboración propia con datos extraídos del sitio web del INE: www.ine.es", "es"),
}
BODIES = tuple(CREDITS)  # the order credits are listed in
_URL_SUFFIX = re.compile(r"\s*\(https?://[^)]*\)\s*$")


def is_gisco(source: str | None) -> bool:
    """True for a boundary stored from Eurostat GISCO (`boundaries.source`)."""
    return bool(source) and source.startswith("Eurostat GISCO")


@dataclass(frozen=True)
class PopulationCredit:
    body: str  # Eurostat, INSEE, INE; or the recorded source itself when it is none of them
    text: str  # the credit the body asks for
    lang: str  # the language of `text`
    detail: str  # the recorded statistic, its URL and the body's name dropped


def population_credit(source: str | None) -> PopulationCredit | None:
    """The credit for a recorded population source; None without one. A source of no known
    body is named as recorded."""
    if not source or not source.strip():
        return None
    name = _URL_SUFFIX.sub("", source).strip()
    for body, prefixes in (
        (EUROSTAT, ("GISCO", "Eurostat")),
        (INSEE, ("INSEE",)),
        (INE, ("INE ",)),
    ):
        if name.startswith(prefixes):
            text, lang = CREDITS[body]
            return PopulationCredit(body, text, lang, name.removeprefix(body).strip())
    return PopulationCredit(name, name, "en", "")


def group_credits(sources: Iterable[str | None]) -> list[tuple[PopulationCredit, list[str]]]:
    """Each body's credit once, with the distinct details of its sources, in `BODIES` order and
    then the unknown sources alphabetically."""
    details: dict[str, list[str]] = {}
    first: dict[str, PopulationCredit] = {}
    for source in sources:
        c = population_credit(source)
        if c is None:
            continue
        first.setdefault(c.body, c)
        found = details.setdefault(c.body, [])
        if c.detail and c.detail not in found:
            found.append(c.detail)
    order = [b for b in BODIES if b in first] + sorted(b for b in first if b not in BODIES)
    return [(first[b], details[b]) for b in order]


def disclaimer(bodies: list[str], lang: str = "en") -> str | None:
    """Eurostat's non-responsibility line for figures we derive (per capita), naming the known
    bodies among `bodies`, in `lang`; None when there is none."""
    known = [b for b in BODIES if b in bodies]
    if not known:
        return None
    names = i18n.and_list(known, lang)
    if lang == "de":
        verb = "trägt" if len(known) == 1 else "tragen"
        return f"Die Pro-Kopf-Werte berechnet velometer; {names} {verb} dafür keine Verantwortung."
    verb = "bears" if len(known) == 1 else "bear"
    return (
        f"Per-capita figures are computed by velometer; {names} {verb} no responsibility for them."
    )


def population_lines(sources: Iterable[str | None]) -> list[str]:
    """The population credit line and the disclaimer for a file whose rows used `sources`;
    [] when no row has a population."""
    groups = group_credits(sources)
    if not groups:
        return []
    parts = [f"{c.text} ({'; '.join(d)})" if d else c.text for c, d in groups]
    lines = ["Population: " + "; ".join(parts)]
    note = disclaimer([c.body for c, _ in groups])
    return lines + ([note] if note else [])
