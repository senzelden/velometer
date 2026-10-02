"""The generated methodology, in English and German (`docs/methodology.md`, `.de.md`).

The prose is hand-written in the Jinja templates (`templates/methodology.<lang>.md.j2`), once
per language. Every number and identifier comes from `MethodologyFacts`, gathered here from the
report classifier, presets, `activity.yaml`, `history.yaml`, `limitations.yaml` and the runs
`ReportData` selects. `check` re-renders in memory and lists what is stale.
"""

from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, PackageLoader, StrictUndefined
from pydantic import BaseModel, ConfigDict

from velometer import timeseries as ts
from velometer.config import Limitation, load_classifier, load_limitations
from velometer.db import fetch_run
from velometer.report.data import KINDS, ReportData

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


class CityFacts(_Frozen):
    id: str
    name: str
    kinds: list[KindFacts]


class MethodologyFacts(_Frozen):
    classifier_version: str
    classifier_parameters: dict[str, str]
    rules: list[RuleRow]
    value_separators: list[str]
    presets: list[PresetRow]
    cities: list[CityFacts]
    snapshot_dates: list[str]
    flag_thresholds: dict[str, float]
    limitations: list[Limitation]


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
    pop_value = pop_year = None
    if current is not None:
        pop_value, pop_year = current.population_value, current.population_year
    elif history:
        run = fetch_run(data.conn, history[0].run_id)
        pop_value, pop_year = run["population_value"], run["population_year"]
    return KindFacts(
        kind=kind,
        current_osm_timestamp=None if current is None else current.osm_timestamp,
        history_set=None if series is None else series.set_md5,
        history_osm_timestamps=[p.osm_timestamp for p in history],
        population_value=pop_value,
        population_year=pop_year,
    )


def methodology_facts(data: ReportData) -> MethodologyFacts:
    """Every generated fact of the methodology, on the report classifier and config on disk.

    Raises ConfigError when a config file (including limitations.yaml) is invalid.
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
            )
            for r in cfg.rules
        ],
        value_separators=list(cfg.value_separators),
        presets=preset_rows,
        cities=[
            CityFacts(id=c.id, name=c.name, kinds=[_kind_facts(data, c.id, k) for k in KINDS])
            for c in data.cities()
        ],
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
