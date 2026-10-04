"""The generated methodology, in English and German (`docs/methodology.md`, `.de.md`).

The prose is hand-written in the Jinja templates (`templates/methodology.<lang>.md.j2`), once
per language. Every number and identifier comes from `MethodologyFacts`, gathered here from the
report classifier, presets, `activity.yaml`, `history.yaml`, `limitations.yaml`, `trust.yaml`
(with the golden fixtures it points to), `cities.yaml` and the runs `ReportData` selects.
`check` re-renders in memory and lists what is stale.
"""

from pathlib import Path
from typing import Any, Literal

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined
from pydantic import BaseModel, ConfigDict

from velometer import timeseries as ts
from velometer.config import (
    CityConfig,
    Limitation,
    load_cities,
    load_classifier,
    load_limitations,
    load_trust,
)
from velometer.db import fetch_boundary, fetch_run
from velometer.models import City
from velometer.report.data import KINDS, ReportData
from velometer.sources.boundaries import OSM_ADMIN_VERSION
from velometer.trust import golden_paths

Lang = Literal["en", "de"]
LANGS: tuple[Lang, ...] = ("en", "de")
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
    )


# --- rendering ----------------------------------------------------------------------------


def _number(v: float | int | None, lang: Lang) -> str:
    """Thousands and decimal separators of the language. At most two decimals (config
    thresholds such as 0.5 or 0.25), trailing zeros and a bare decimal point dropped."""
    if v is None:
        return ""
    text = f"{v:,.2f}".rstrip("0").rstrip(".")
    if lang == "de":
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


AND: dict[str, str] = {"en": "and", "de": "und"}


def _and_list(items: list[str], lang: Lang) -> str:
    """The items joined as "A", "A and B" or "A, B and C" in the language."""
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {AND[lang]} {items[-1]}"


def _environment(lang: Lang) -> Environment:
    env = Environment(
        loader=PackageLoader("velometer.report", "templates"),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,  # Markdown, not HTML
    )
    env.filters["num"] = lambda v: _number(v, lang)
    env.filters["and_list"] = lambda v: _and_list(v, lang)
    return env


def render(facts: MethodologyFacts, lang: Lang) -> str:
    """The methodology in one language, from its template and the facts."""
    template = _environment(lang).get_template(f"methodology.{lang}.md.j2")
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
