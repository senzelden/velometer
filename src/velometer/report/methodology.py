"""The generated methodology, in English and German (`docs/methodology.md`, `.de.md`).

The prose is hand-written in the Jinja templates (`templates/methodology.<lang>.md.j2`), once
per language. Every number and identifier comes from `MethodologyFacts`, gathered here from the
report classifier, presets, `activity.yaml`, `history.yaml`, `limitations.yaml`, `trust.yaml`
(with the golden fixtures it points to), `cities.yaml`, `counters.yaml`, the counter index
rule (`counters.index`), the runs `ReportData` selects and the stored `plan_overlay` and counter
tables.
`check` re-renders in memory and lists what is stale.
"""

import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined
from pydantic import BaseModel, ConfigDict

from velometer import credits, i18n
from velometer import timeseries as ts
from velometer.config import (
    CityConfig,
    Limitation,
    load_cities,
    load_classifier,
    load_limitations,
    load_trust,
)
from velometer.content.facts import latest_overlay
from velometer.counters import MONTHLY_SERIES, SERIES
from velometer.counters import index as counter_index
from velometer.counters.model import (
    COUNTERS_FILE,
    COVID_YEAR,
    DEFAULT_BASE_YEAR,
    CounterEntry,
    data_gaps,
    has_line,
    load_counters_config,
)
from velometer.credits import PopulationCredit
from velometer.db import fetch_boundary, fetch_run
from velometer.i18n import LANGS, Lang
from velometer.models import City
from velometer.plans.berlin import CITY as OVERLAY_CITY
from velometer.plans.models import MAPPED_BASELINE
from velometer.plans.overlay import load_overlay_config
from velometer.report.data import KINDS, ReportData
from velometer.sources.boundaries import OSM_ADMIN_VERSION
from velometer.trust import golden_paths

FILES: dict[str, str] = {"en": "methodology.md", "de": "methodology.de.md"}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class RuleRow(_Frozen):
    id: str
    tier: str
    subtype: str | None
    applies_to: str
    match: str  # a one-line summary of the match expression
    changed_from: str | None = None  # the previous version, when the rule id is new since it


class PresetRow(_Frozen):
    id: str
    numerator: str  # tiers, e.g. "A+B"
    denominator: str  # road class
    basis: str  # the reported length basis
    basis_parameter: str | None = None  # the presets parameter that picks it, if any


class KindFacts(_Frozen):
    kind: str
    current_osm_timestamp: str | None
    history_set: str | None  # md5 of the history set the series uses
    history_osm_timestamps: list[str]
    population_value: int | None
    population_year: int | None
    population_source: str | None  # the source string stored on the run row


class CityFacts(_Frozen):
    id: str
    name: str
    kinds: list[KindFacts]
    boundary_source: str | None  # of the admin (`lau`) boundary: GISCO LAU or OSM relation N
    population_source: str | None  # of the population the LAU runs carry
    nuts3_is_city: bool | None  # cities.yaml; False: QECIO's NUTS3 unit is not the city
    # cities.yaml population_override.source: a cited national-statistics population
    population_override: str | None = None


class CountryFact(_Frozen):
    iso2: str
    status: str
    basis: str
    basis_de: str  # the German wording; basis where trust.yaml has none
    classifier_reviewed: str | None
    signed_off: str | None  # ISO date
    n_golden_confirmed: int  # confirmed ways of the golden fixture; 0 of 0 without one
    n_golden: int
    golden_not_found: str | None = None  # the path trust.yaml names, when no file is there


class OverlayFacts(_Frozen):
    """The plan-network overlay version the Berlin plan page shows (the latest version stored in
    `plan_overlay`, as the page reads it) and its parameters (its config file)."""

    version: str
    buffer_m: float
    separate_buffer_m: float
    max_angle_deg: float
    min_part_m: float
    merge_scope: str
    clip_free_ends: bool


class StepDownFact(_Frozen):
    site: str
    since: str  # YYYY-MM


class CounterCityFact(_Frozen):
    id: str
    name: str
    source: str
    source_de: str | None = None  # config/counters.yaml: only where `source` has our English words
    licence: str
    base_year: int
    series: Literal["counts", "avg_daily_intensity"]
    data_from: str | None = None  # YYYY-MM of the first stored day of any site
    index_years: list[int] = []  # stored years with an index value
    line: bool = True  # whether the index is drawn as a line (`MIN_LINE_YEARS` valued years)
    gaps: list[tuple[str, str]] = []  # (YYYY-MM, YYYY-MM) runs without counts, of a no-line city
    note: str | None = None  # config/counters.yaml: the clause after the gaps (M8-8)
    note_de: str | None = None
    step_downs: list[StepDownFact] = []  # config/counters.yaml: our reading of the daily data


class CounterMethodRow(_Frozen):
    """A link of a daily-count city whose ratio moved by at least METHOD_CHANGE_PCT between the
    stored v1 and v2 rows (M13 spec §4.2)."""

    city: str  # the city's name
    years: tuple[int, int]  # the link's earlier and later year
    v1: float  # the v1 link ratio (later index over earlier)
    v2: float  # the v2 link ratio
    change_pct: float  # (v2 / v1 - 1) * 100


class CounterFacts(_Frozen):
    cities: list[CounterCityFact]  # cities with an open counter portal, in config order
    n_no_data: int  # cities listed as checked without open counter data
    min_valid_pct: float  # complete days a site needs in both years of a link
    min_sites: int  # qualifying sites a link needs
    default_base_year: int  # the base year of a city whose entry names none
    covid_year: int
    method_changes: list[CounterMethodRow]  # links v2 moved by >= method_change_pct (M13)
    method_change_pct: float  # the threshold of `method_changes`, in percent


class MethodologyFacts(_Frozen):
    classifier_version: str
    classifier_parameters: dict[str, str]
    rules: list[RuleRow]
    previous_classifier: str | None = None  # the version the rules table is diffed against
    removed_rules: list[str] = []  # rule ids of the previous version that this one lacks
    value_separators: list[str]
    presets: list[PresetRow]
    countries: list[CountryFact]  # trusted countries only, by ISO2
    cities: list[CityFacts]
    snapshot_dates: list[str]
    flag_thresholds: dict[str, float]
    limitations: list[Limitation]
    overlay: OverlayFacts | None  # None: no overlay stored
    mapped_baseline: date  # "mapped on the network" counts from this day (spec §4.4)
    counters: CounterFacts
    # a city's own name -> its language, for each city whose name differs from its English form
    # (København): the English methodology shows it in a `<span lang>` (M14, spec §4.3)
    city_langs: dict[str, str] = {}


# The rules table is diffed against the previous version from v4 on, the rewrite that renamed
# and split tiers. Earlier versions keep the plain table.
RULES_DIFF_FROM = 4


def _version_number(version: str) -> int:
    return int(version.removeprefix("v"))  # the ordering `trust.expects_newer_classifier` uses


def previous_classifier(config_dir: Path, version: str) -> str | None:
    """The highest classifier version in `config_dir/classifier` below `version`, or None."""
    found = [p.stem for p in (config_dir / "classifier").glob("v*.yaml")]
    older = [v for v in found if _version_number(v) < _version_number(version)]
    return max(older, key=_version_number, default=None)


# --- facts --------------------------------------------------------------------------------


def _value(v: Any) -> str:
    if isinstance(v, bool):  # PyYAML 1.1 booleans are OSM "yes"/"no"
        return "yes" if v else "no"
    return str(v)


def summarise_match(expr: dict) -> str:
    """A one-line, table-safe summary of a classifier match expression."""
    parts = []
    for key, cond in expr.items():
        if key in ("all", "any"):
            joiner = " and " if key == "all" else " or "
            parts.append("(" + joiner.join(summarise_match(e) for e in cond) + ")")
        elif key == "not":
            parts.append(f"not ({summarise_match(cond)})")
        elif isinstance(cond, dict):
            if "absent" in cond:
                parts.append(f"{key} {'absent' if cond['absent'] else 'present'}")
            elif "not_in" in cond:
                parts.append(f"{key} not in [{', '.join(_value(v) for v in cond['not_in'])}]")
            else:
                parts.append(f"{key} in <{cond['in_list']}>")
        elif isinstance(cond, list):
            parts.append(f"{key} in [{', '.join(_value(v) for v in cond)}]")
        else:
            parts.append(f"{key}={_value(cond)}")
    return " and ".join(parts)


def _kind_facts(data: ReportData, city_id: str, kind: str) -> KindFacts:
    current = data.current(city_id, kind)
    series = data.series(city_id, kind)
    history = [] if series is None else [p for p in series.points if p.label != ts.CURRENT]
    run_id = current.run_id if current is not None else history[0].run_id if history else None
    run = None if run_id is None else fetch_run(data.conn, run_id)
    return KindFacts(
        kind=kind,
        current_osm_timestamp=None if current is None else current.osm_timestamp,
        history_set=None if series is None else series.set_md5,
        history_osm_timestamps=[p.osm_timestamp for p in history],
        population_value=None if run is None else run["population_value"],
        population_year=None if run is None else run["population_year"],
        population_source=None if run is None else run["population_source"],
    )


def _boundary_source(data: ReportData, city_id: str) -> str | None:
    """The stored source of the city's admin (`lau`) boundary: "OSM relation N" as stored (its
    `source_version` says it is an OSM relation), or the GISCO source with its version
    ("Eurostat GISCO LAU 2024 (1:1M)")."""
    b = fetch_boundary(data.conn, city_id, "lau")
    if b is None:
        return None
    return b.source if b.source_version == OSM_ADMIN_VERSION else f"{b.source} {b.source_version}"


def _city_facts(data: ReportData, city: City, cfg: CityConfig | None) -> CityFacts:
    kinds = [_kind_facts(data, city.id, k) for k in KINDS]
    lau = next(k for k in kinds if k.kind == "lau")
    population_source = lau.population_source or (city.population and city.population.source)
    return CityFacts(
        id=city.id,
        name=city.name,
        kinds=kinds,
        boundary_source=_boundary_source(data, city.id),
        population_source=population_source,
        nuts3_is_city=None if cfg is None else cfg.nuts3_is_city,
        population_override=(
            cfg.population_override.source if cfg and cfg.population_override else None
        ),
    )


def _golden_counts(paths: tuple[Path, Path] | None) -> tuple[int, int]:
    """(confirmed, total) ways of the golden yaml; (0, 0) when there is none to read."""
    if paths is None or not paths[0].is_file():
        return 0, 0
    ways = (yaml.safe_load(paths[0].read_text(encoding="utf-8")) or {}).get("ways") or []
    return sum(1 for w in ways if w.get("confirmed")), len(ways)


def _country_facts(config_dir: Path) -> list[CountryFact]:
    """The trusted countries of trust.yaml. Golden paths are relative to the repo root, the
    parent of the config directory."""
    out = []
    for cc, ct in sorted(load_trust(config_dir / "trust.yaml").countries.items()):
        if ct.status != "trusted":
            continue
        golden = golden_paths(cc, config_dir)
        confirmed, total = _golden_counts(golden)
        missing = golden is not None and not golden[0].is_file()
        out.append(
            CountryFact(
                iso2=cc,
                status=ct.status,
                basis=ct.basis,
                basis_de=ct.basis_de or ct.basis,
                classifier_reviewed=ct.classifier_reviewed,
                signed_off=None if ct.signed_off is None else ct.signed_off.isoformat(),
                n_golden_confirmed=confirmed,
                n_golden=total,
                golden_not_found=str(golden[0]) if missing else None,
            )
        )
    return out


def _overlay_facts(data: ReportData) -> OverlayFacts | None:
    """The latest overlay version stored for Berlin (numeric order, as the plan page picks it)
    with the parameters of its config file; None when no overlay is stored."""
    version, _ = latest_overlay(data.plan_overlay(OVERLAY_CITY))
    if version is None:
        return None
    cfg = load_overlay_config(data.config_dir / "plans", version)
    return OverlayFacts(
        version=cfg.version,
        buffer_m=cfg.buffer_m,
        separate_buffer_m=cfg.separate_buffer_m,
        max_angle_deg=cfg.max_angle_deg,
        min_part_m=cfg.min_part_m,
        merge_scope=cfg.merge_scope,
        clip_free_ends=cfg.clip_free_ends,
    )


def _counter_city(data: ReportData, c: CounterEntry, name: str) -> CounterCityFact:
    """One counter city: its config entry and what the stored data say (first day, index years,
    gaps of a city drawn without a line, as the Counts tab names them)."""
    series = MONTHLY_SERIES if c.grain == "monthly" else SERIES
    rows = data.counter_index(c.city)
    years = [r.year for r in rows if r.index is not None]
    line = has_line(r.index for r in rows)
    firsts = [s.first_day for s in data.counter_sites(c.city) if s.first_day]
    gaps: list[tuple[str, str]] = []
    # as the Counts tab: gaps of daily counts (the stored series), of a city without a line
    if rows and not line and rows[0].series == SERIES:
        gaps = [(a[:7], b[:7]) for a, b in data_gaps(data.counter_day_counts(c.city))]
    return CounterCityFact(
        id=c.city,
        name=name,
        source=c.source,
        source_de=c.source_de,
        licence=c.licence,
        base_year=c.base_year,
        series=series,
        data_from=min(firsts)[:7] if firsts else None,
        index_years=years,
        line=line,
        gaps=gaps,
        note=c.note,
        note_de=c.note_de,
        step_downs=[StepDownFact(site=s.site, since=s.since) for s in c.step_downs],
    )


METHOD_CHANGE_PCT = 0.5  # a link whose ratio moved by at least this much is listed (§4.2)


def _links(rows) -> dict[tuple[int, int], float]:
    """(earlier, later) -> ratio, for consecutive years that both have a value."""
    idx = {r.year: r.index for r in rows}
    return {
        (y - 1, y): idx[y] / idx[y - 1]
        for y in idx
        if idx[y] is not None and idx.get(y - 1) not in (None, 0)
    }


def _method_changes(data: ReportData, c: CounterEntry, name: str) -> list[CounterMethodRow]:
    """The links of a daily-count city whose ratio moved by at least METHOD_CHANGE_PCT from the
    stored v1 rows to the v2 rows; a link counts when both methods have it."""
    if c.grain == "monthly":
        return []
    v1, v2 = _links(data.counter_index(c.city, "v1")), _links(data.counter_index(c.city, "v2"))
    out = []
    for years in sorted(v1.keys() & v2.keys()):
        change = (v2[years] / v1[years] - 1) * 100
        if abs(change) >= METHOD_CHANGE_PCT:
            out.append(CounterMethodRow(city=name, years=years, v1=v1[years], v2=v2[years],
                                        change_pct=change))  # fmt: skip
    return out


def _counter_facts(data: ReportData, names: dict[str, str]) -> CounterFacts:
    """The counter portals of the reported cities (`names`: id -> name); a city the trust gate
    holds back appears in neither the table nor the no-data count. The index rule is read from
    `counters.index` when the facts are gathered."""
    cfg = load_counters_config(data.config_dir / COUNTERS_FILE)
    reported = [c for c in cfg.cities if c.city in names]
    return CounterFacts(
        cities=[_counter_city(data, c, names[c.city]) for c in reported],
        method_changes=[row for c in reported for row in _method_changes(data, c, names[c.city])],
        method_change_pct=METHOD_CHANGE_PCT,
        n_no_data=sum(1 for n in cfg.none if n.city in names),
        min_valid_pct=counter_index.MIN_VALID * 100,
        min_sites=counter_index.MIN_SITES,
        default_base_year=DEFAULT_BASE_YEAR,
        covid_year=COVID_YEAR,
    )


def methodology_facts(data: ReportData) -> MethodologyFacts:
    """Every generated fact of the methodology, on the report classifier and config on disk.

    Raises ConfigError when a config file (including limitations.yaml and trust.yaml) is
    invalid.
    """
    sel = data.selector
    cfg = load_classifier(data.config_dir / "classifier" / f"{sel.version}.yaml")
    presets = sel.presets
    preset_rows = []
    for p in presets.presets:
        preset_rows.append(
            PresetRow(
                id=p.id,
                numerator="+".join(p.tiers),
                denominator=p.denominator,
                basis=presets.parameters.resolve(p.basis),
                basis_parameter=p.basis.parameter if p.parameterised else None,
            )
        )
    prev_version = (
        previous_classifier(data.config_dir, cfg.version)
        if _version_number(cfg.version) >= RULES_DIFF_FROM
        else None
    )
    prev_ids: set[str] | None = None
    if prev_version is not None:
        prev = load_classifier(data.config_dir / "classifier" / f"{prev_version}.yaml")
        prev_ids = {r.id for r in prev.rules}
    current_ids = {r.id for r in cfg.rules}
    configured = {c.id: c for c in load_cities(data.config_dir / "cities.yaml")}
    return MethodologyFacts(
        classifier_version=cfg.version,
        classifier_parameters={k: str(v) for k, v in cfg.parameters.model_dump().items()},
        rules=[
            RuleRow(
                id=r.id,
                tier=r.tier,
                subtype=r.subtype,
                applies_to=r.applies_to,
                match=summarise_match(r.match),
                changed_from=prev_version
                if prev_ids is not None and r.id not in prev_ids
                else None,
            )
            for r in cfg.rules
        ],
        previous_classifier=prev_version,
        removed_rules=[] if prev_ids is None else sorted(prev_ids - current_ids),
        value_separators=list(cfg.value_separators),
        presets=preset_rows,
        countries=_country_facts(data.config_dir),
        cities=[_city_facts(data, c, configured.get(c.id)) for c in data.cities()],
        snapshot_dates=[f"{y}-01-01" for y in data.years],
        flag_thresholds=dict(data.activity.flags.model_dump()),
        limitations=load_limitations(data.config_dir / "limitations.yaml"),
        overlay=_overlay_facts(data),
        mapped_baseline=MAPPED_BASELINE,
        counters=_counter_facts(data, {c.id: c.name for c in data.cities()}),
        city_langs={
            cfg.name: cfg.lang
            for c in data.cities()
            if (cfg := configured.get(c.id)) is not None and cfg.name != cfg.english_name
        },
    )


# --- rendering ----------------------------------------------------------------------------


_number = i18n.number_trimmed
_and_list = i18n.and_list


def _month(v: str, lang: Lang) -> str:
    """A month (YYYY-MM or an ISO day) in words: "September 2019"."""
    return i18n.month_year(v, lang, short=False)


GAP: dict[str, str] = {"en": "from {} to {}", "de": "von {} bis {}"}
# a count of sites in words: English after "of", German in the genitive ("die Zählwerte zweier
# Zählstellen"); a larger count in figures
SITES: dict[str, tuple[str, ...]] = {
    "en": ("no sites", "one site", "two sites", "three sites", "four sites"),
    "de": ("keiner Zählstelle", "einer Zählstelle", "zweier Zählstellen", "dreier Zählstellen"),
}
SITES_MANY: dict[str, str] = {"en": "{} sites", "de": "von {} Zählstellen"}


def _gaps(gaps: list[tuple[str, str]], lang: Lang) -> str:
    """Runs of months without counts: "from July 2021 to August 2022 and from ..."."""
    return _and_list([GAP[lang].format(_month(a, lang), _month(b, lang)) for a, b in gaps], lang)


def _sites(n: int, lang: Lang) -> str:
    words = SITES[lang]
    return words[n] if n < len(words) else SITES_MANY[lang].format(n)


def _day(v: date, lang: Lang) -> str:
    """A day in words: "1 January 2022", "1. Januar 2022"."""
    return i18n.long_day(v, lang)


# our own words in the stored boundary and population provenance (sources/boundaries.py), in
# German: the stored strings are run identity in the database and stay as written
_PROVENANCE_DE = (
    (re.compile(r", union of (\d+) LAU\b"), r", Vereinigung von \1 LAU"),
    (re.compile(r"\(sum of (\d+) LAU\)"), r"(Summe von \1 LAU)"),
)


def _provenance(v: str | None, lang: Lang) -> str | None:
    """A stored provenance string as the page's language shows it: German replaces our own
    English words ("union of 17 LAU"); a source's name stays as written."""
    if v is None or lang == "en":
        return v
    for pattern, german in _PROVENANCE_DE:
        v = pattern.sub(german, v)
    return v


def _signed_pct(v: float, lang: Lang) -> str:
    """A signed percentage to one decimal, spaced as the page's other percentages: "+1.8 %",
    "−1.0 %" (a true minus in both languages), "+1,8 %" with a narrow space in German."""
    text = i18n.signed(v, lang, 1)
    text = i18n.MINUS + text[1:] if text.startswith("-") else text
    return f"{text}{i18n.NNBSP if lang == 'de' else ' '}%"


def _city(name: str, langs: dict[str, str], lang: Lang) -> str:
    """A city's name as the methodology shows it: on the English page, a name that differs from
    its English form in a `<span lang>` of its language, as the app's `city_name` does."""
    own = langs.get(name) if lang == "en" else None
    return f'<span lang="{own}">{name}</span>' if own else name


def _population_credits(cities: list[CityFacts]) -> list[tuple[PopulationCredit, list[str]]]:
    """Each population credit once with the names of the cities whose LAU population it gives:
    the national offices first (`credits.BODIES` order), sources of no known body next, and
    Eurostat last (the page says "every other city" for it)."""
    found: dict[str, tuple[PopulationCredit, list[str]]] = {}
    for c in cities:
        credit = credits.population_credit(c.population_source)
        if credit is not None:
            found.setdefault(credit.body, (credit, []))[1].append(c.name)
    known = [b for b in credits.BODIES if b in found and b != credits.EUROSTAT]
    other = sorted(b for b in found if b not in credits.BODIES)
    last = [credits.EUROSTAT] if credits.EUROSTAT in found else []
    return [found[b] for b in known + other + last]


def _credit(c: PopulationCredit, lang: Lang) -> str:
    """A credit's text, in a `<span lang>` where its language is not the page's."""
    return c.text if c.lang in (lang, "en") else f'<span lang="{c.lang}">{c.text}</span>'


def _environment(lang: Lang, city_langs: dict[str, str] | None = None) -> Environment:
    env = Environment(
        loader=PackageLoader("velometer.report", "templates"),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,  # Markdown, not HTML
    )
    env.filters["num"] = lambda v: _number(v, lang)
    env.filters["pct"] = lambda v: (
        f"{_number(v, lang)}{i18n.NNBSP}%" if lang == "de" else f"{_number(v, lang)}%"
    )
    env.filters["signed_pct"] = lambda v: _signed_pct(v, lang)
    env.filters["and_list"] = lambda v: _and_list(v, lang)
    env.filters["month"] = lambda v: _month(v, lang)
    env.filters["day"] = lambda v: _day(v, lang)
    env.filters["gaps"] = lambda v: _gaps(v, lang)
    env.filters["sites"] = lambda v: _sites(v, lang)
    env.filters["provenance"] = lambda v: _provenance(v, lang)
    env.filters["city"] = lambda v: _city(v, city_langs or {}, lang)
    env.globals["tab"] = lambda key: i18n.t(lang, f"city.tab.{key}")  # the site's tab label
    env.globals["population_credits"] = _population_credits
    env.globals["disclaimer"] = lambda groups: credits.disclaimer([c.body for c, _ in groups], lang)
    env.globals["gisco_terms"] = credits.GISCO_TERMS_URL
    env.globals["osm_copyright"] = credits.OSM_COPYRIGHT_URL
    env.globals["odbl_url"] = credits.ODBL_URL
    env.filters["credit"] = lambda c: _credit(c, lang)
    env.globals["boundary_credit"] = i18n.t(lang, "credit.boundaries")
    return env


def render(facts: MethodologyFacts, lang: Lang) -> str:
    """The methodology in one language, from its template and the facts."""
    template = _environment(lang, facts.city_langs).get_template(f"methodology.{lang}.md.j2")
    return template.render(f=facts, files=FILES)


def write(docs_dir: Path, facts: MethodologyFacts) -> list[Path]:
    """Write methodology.md (en) and methodology.de.md (de) into docs_dir."""
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for lang in LANGS:
        path = docs_dir / FILES[lang]
        path.write_text(render(facts, lang), encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def _first_difference(a: str, b: str) -> int:
    al, bl = a.splitlines(), b.splitlines()
    for i, (x, y) in enumerate(zip(al, bl, strict=False), start=1):
        if x != y:
            return i
    return min(len(al), len(bl)) + 1


def check(docs_dir: Path, facts: MethodologyFacts) -> list[str]:
    """Problems that make the committed methodology stale; empty when both files are current."""
    problems = []
    for lim in facts.limitations:
        for lang in LANGS:
            if not str(getattr(lim, lang, "") or "").strip():
                problems.append(f"limitations.yaml: limitation {lim.id!r} has no {lang!r} text")
    for lang in LANGS:
        path = Path(docs_dir) / FILES[lang]
        if not path.is_file():
            problems.append(
                f"{FILES[lang]}: missing at {path} (run `velometer report methodology`)"
            )
            continue
        expected, actual = render(facts, lang), path.read_text(encoding="utf-8")
        if actual != expected:
            line = _first_difference(actual, expected)
            problems.append(
                f"{FILES[lang]}: differs from the render (first difference at line {line}; "
                "run `velometer report methodology`)"
            )
    return problems
