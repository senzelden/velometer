"""`velometer content --check`: validate narratives, the explainer, organisation profiles and the
plan and counter pages against the source registry and the report data (M7 spec §4.4, M8 spec
§3.4, §4.5, §5.5), and the plan figures in `config/plans/`. Every problem is one
`"<file>: <message>"` string."""

import contextlib
import csv
import html
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import httpx
import yaml

from velometer.config import ConfigError
from velometer.content.facts import (
    BASE_YEAR,
    COUNTER_RULES,
    FactError,
    counter_rule,
    evaluate,
    parse_printed,
    printed_matches,
)
from velometer.content.loader import (
    load_document,
    load_narratives,
    load_organisation_map,
    load_organisations,
    load_sources,
)
from velometer.content.models import (
    STORY_STEPS,
    ContentError,
    DataRef,
    Explainer,
    Fact,
    Narrative,
    Organisation,
    Quote,
    Source,
)
from velometer.counters.model import COUNTERS_FILE, load_counters_config
from velometer.plans.models import Plan, ReportRow, load_plans
from velometer.report.data import ReportData

COMBINED = "combined"
_GROUP_SPACE = "[ \u202f\u00a0]"  # space, narrow no-break space, no-break space
_NUMBER_TOKEN = re.compile(
    rf"(?<!\w)[+−-]?(?:\d{{1,3}}(?:{_GROUP_SPACE}\d{{3}})+(?!\d)(?:\.\d+)?|\d[\d,]*(?:\.\d+)?)%?"
)
_ORDINAL = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
_SOURCE_REF = re.compile(r"\[@([^\]\s]+)\]")
_DATA_REF = re.compile(r"\[#([^\]\s]+)\]")
_STRIPPED = re.compile(r"\[@[^\]]*\]|\[#[^\]]*\]|`[^`]*`|\]\([^)]*\)")
_VERBS = re.compile(r"\b(built|constructed|opened|removed)\b", re.IGNORECASE)
_COUNTER_WORDS = re.compile(r"\b(counters?|counts?|counted|cyclists recorded)\b", re.IGNORECASE)
_CAUSAL = re.compile(
    r"\b(led to|lead to|leads to|because of|drove|driven by|thanks to|resulted in|caused|due to)\b",
    re.IGNORECASE,
)
COUNTER_PAGE = "counters.yaml"
PLAN_DOCUMENTS = ("plans/berlin.yaml", COUNTER_PAGE)
_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty",
)  # fmt: skip
_TENS = {"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
         "ninety": 90}  # fmt: skip
_NUMBER_WORDS = {w: i for i, w in enumerate(_ONES)} | _TENS
_WORD = re.compile(r"\b[A-Za-z]+\b")
_IN_TEN = re.compile(r"\b([A-Za-z]+)\s+(?:[A-Za-z]+\s+)?in\s+ten\b", re.IGNORECASE)  # 9 days in 10
BERLIN = "berlin"


def normalise_number(text: str) -> str:
    """A printed number at its printed precision, without sign prefix, commas or percent."""
    squeezed = re.sub(_GROUP_SPACE, "", text)  # "1 000" is the number 1000
    try:
        value, decimals = parse_printed(squeezed)
    except FactError:
        return text.strip()
    return f"{value:.{decimals}f}"


def _literal_pattern(literal: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in literal.split()]
    return re.compile(r"(?<!\w)" + r"[\s\u202f\u00a0]+".join(words) + r"(?!\w)")


def undeclared_numbers(
    paragraph: str, allowed: set[str], literals: Iterable[str] = ()
) -> list[str]:
    """Numbers in the prose that are neither declared (facts), inside a declared literal's exact
    text, nor a year or ordinal."""
    ok = {normalise_number(a) for a in allowed} | set(allowed)
    text = _STRIPPED.sub(" ", paragraph)
    for lit in sorted({x for x in literals if x.split()}, key=len, reverse=True):
        text = _literal_pattern(lit).sub(" ", text)
    text = _ORDINAL.sub(" ", text)
    found: list[str] = []
    for m in _NUMBER_TOKEN.finditer(text):
        raw = m.group(0).rstrip(",")
        norm = normalise_number(raw)
        if norm in ok or raw in ok:
            continue
        if re.fullmatch(r"20\d\d", norm):
            continue
        if raw not in found:
            found.append(raw)
    return found


def _full(value: float) -> str:
    """Every digit of a value (no exponent, no 6-significant-digit truncation)."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def construction_verbs(paragraph: str) -> list[str]:
    """Construction verbs in the prose (never allowed outside quotes for mapped km)."""
    found: list[str] = []
    for m in _VERBS.finditer(paragraph):
        verb = m.group(1).lower()
        if verb not in found:
            found.append(verb)
    return found


def causal_counter_wording(paragraph: str) -> list[str]:
    """Causal wording in prose that mentions counters (counts are context, never an outcome of
    km: M8 spec §2.12, §5.5); [] when the paragraph does not mention counters."""
    if not _COUNTER_WORDS.search(paragraph):
        return []
    return [m.group(1) for m in _CAUSAL.finditer(paragraph)]


def counter_rule_values(config_dir: Path) -> dict[float, str]:
    """The index rule's values (spec §2.13) -> the fact that prints each: `MIN_VALID` in percent,
    `MIN_SITES`, and each configured city's base year (none when config/counters.yaml is absent
    or unreadable; its own check reports that)."""
    rules = {round(counter_rule(r), 6): f"counter.{r}" for r in COUNTER_RULES}
    try:
        cfg = load_counters_config(Path(config_dir) / COUNTERS_FILE)
    except (ConfigError, OSError):
        return rules
    for e in cfg.cities:
        rules.setdefault(float(e.base_year), f"counter.{BASE_YEAR}.{e.city}")
    return rules


def _is_rule_fact(expr: str) -> bool:
    family, _, rest = expr.strip().partition(".")
    return family == "counter" and (rest in COUNTER_RULES or rest.startswith(f"{BASE_YEAR}."))


def literal_counter_rules(paragraph: str, rules: dict[float, str], facts: list[Fact]) -> list[str]:
    """Index-rule values the counter prose states as literal text: a rule value spelled out in
    words ("three sites", "nine days in ten"), or a number equal to a rule value that no
    counter rule fact of the document (`counter.min_valid`, `counter.min_sites`,
    `counter.base_year.<city>`) prints. Each is "<text> (<the fact to use>)"."""
    declared = set()
    for f in facts:
        if _is_rule_fact(f.expr):
            with contextlib.suppress(FactError):  # the fact's own check reports it
                declared.add(round(parse_printed(f.printed)[0], 6))
    text = _STRIPPED.sub(" ", paragraph)
    found: list[str] = []

    def add(literal: str, value: float) -> None:
        item = f"{literal} ({rules[value]})"
        if item not in found:
            found.append(item)

    for m in _IN_TEN.finditer(text):
        n = _NUMBER_WORDS.get(m.group(1).lower())
        if n is not None and float(n * 10) in rules:
            add(m.group(0), float(n * 10))
    for m in _WORD.finditer(text):
        n = _NUMBER_WORDS.get(m.group(0).lower())
        if n is not None and float(n) in rules:
            add(m.group(0), float(n))
    for m in _NUMBER_TOKEN.finditer(text):
        try:
            value = round(parse_printed(normalise_number(m.group(0).rstrip(",")))[0], 6)
        except FactError:
            continue
        if value in rules and value not in declared:
            add(m.group(0).rstrip(","), value)
    return found


def _check_document(
    label: str,
    prose: list[str],
    quotes: list[Quote],
    facts: list[Fact],
    data_refs: list[DataRef],
    literals: list[str],
    sources: dict[str, Source],
    data: ReportData | None,
    docs_dir: Path | None,
    config_dir: Path | None = None,
) -> list[str]:
    """The document's problems; without `data` the facts are not evaluated (their printed
    values still declare numbers)."""
    problems: list[str] = []

    def add(msg: str) -> None:
        problems.append(f"{label}: {msg}")

    excerpt_ids = {f"{s.id}/{e.id}" for s in sources.values() for e in s.excerpts}
    for q in quotes:
        if q.excerpt not in excerpt_ids:
            add(f"unknown excerpt {q.excerpt}")

    allowed: set[str] = set()
    for f in facts:
        if data is not None and docs_dir is not None:
            try:
                value = evaluate(f.expr, data, docs_dir, config_dir=config_dir)
                if not printed_matches(value, f.printed):
                    add(f"fact {f.id}: {f.expr} is {_full(value)}, printed {f.printed}")
            except FactError as e:
                add(f"fact {f.id}: {e}")
        allowed.add(normalise_number(f.printed))

    ref_ids = {d.id for d in data_refs}
    for p in prose:
        for sid in _SOURCE_REF.findall(p):
            if sid not in sources:
                add(f"unknown source {sid}")
        for rid in _DATA_REF.findall(p):
            if rid not in ref_ids:
                add(f"unknown data ref {rid}")
        for n in undeclared_numbers(p, allowed, literals):
            add(f"undeclared number {n}")
        for v in construction_verbs(p):
            add(f"construction verb {v!r}")
        for w in causal_counter_wording(p):
            add(f"causal wording {w!r} about counts")
    return problems


def _dimension_ids(path: Path) -> list[str]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    dims = doc.get("dimensions", doc) if isinstance(doc, dict) else doc
    if isinstance(dims, dict):
        return [str(k) for k in dims]
    return [str(d["id"]) for d in dims or []]


def _explainer_prose(doc: Explainer) -> list[str]:
    prose = [doc.title, *doc.intro]
    for sec in doc.sections:
        prose += [sec.heading, *sec.paragraphs]
    return prose


def misplaced_quotes(doc: Explainer | Organisation) -> list[str]:
    """Quotes of an explainer-shaped page or an organisation profile that do not follow a
    paragraph citing their source.

    `after` counts the sections' paragraphs, the intro (and a profile's dimension values)
    excluded, as the renderer does. A quote for the intro (its source cited there) follows the
    first paragraph."""
    paragraphs = [p for s in doc.sections for p in s.paragraphs]
    intro_cites = {sid for p in getattr(doc, "intro", []) for sid in _SOURCE_REF.findall(p)}
    out: list[str] = []
    for q in doc.quotes:
        sid = q.excerpt.partition("/")[0]
        if not 0 <= q.after < len(paragraphs):
            out.append(f"quote {q.excerpt}: after={q.after} must index one of {len(paragraphs)}")
            continue
        if sid in _SOURCE_REF.findall(paragraphs[q.after]):
            continue
        if q.after == 0 and sid in intro_cites:
            continue
        citing = [i for i, p in enumerate(paragraphs) if sid in _SOURCE_REF.findall(p)]
        where = f"cited in paragraph {', '.join(map(str, citing))}" if citing else "not cited"
        out.append(
            f"quote {q.excerpt} follows paragraph {q.after}, which does not cite {sid} ({where};"
            " paragraphs count from 0 without the intro)"
        )
    return out


def _check_explainer_shaped(
    label: str,
    doc: Explainer,
    sources: dict[str, Source],
    data: ReportData | None,
    docs_dir: Path | None,
    config_dir: Path,
) -> list[str]:
    return [f"{label}: {m}" for m in misplaced_quotes(doc)] + _check_document(
        label,
        _explainer_prose(doc),
        doc.quotes,
        doc.facts,
        doc.data_refs,
        doc.literals,
        sources,
        data,
        docs_dir,
        config_dir,
    )


def _read_dimensions(config_dir: Path) -> list[str] | None:
    """The differences.yaml dimension ids, None when the file is absent; raises on a bad file."""
    diff = Path(config_dir) / "differences.yaml"
    return _dimension_ids(diff) if diff.is_file() else None


def _check_explainer(
    explainer: Explainer,
    sources: dict[str, Source],
    data: ReportData | None,
    docs_dir: Path | None,
    config_dir: Path,
) -> list[str]:
    label = "explainer.yaml"
    problems = _check_explainer_shaped(label, explainer, sources, data, docs_dir, config_dir)
    diff = Path(config_dir) / "differences.yaml"
    if diff.is_file():
        try:
            dims = _dimension_ids(diff)
        except (OSError, yaml.YAMLError, KeyError, TypeError) as e:
            return problems + [f"{label}: cannot read dimensions from {diff}: {e}"]
        have = [s.dimension for s in explainer.sections]
        for d in dims:
            if have.count(d) != 1:
                problems.append(f"{label}: dimension {d} has {have.count(d)} sections, expected 1")
        for d in dict.fromkeys(have):
            if d not in dims:
                problems.append(f"{label}: section for unknown dimension {d}")
    return problems


def _check_combined_steps(narrative: Narrative) -> list[str]:
    steps = [s.step for s in narrative.sections if s.step is not None]
    return [
        f"narratives/{COMBINED}.yaml: step {step} appears {steps.count(step)} times, expected 1"
        for step in STORY_STEPS
        if steps.count(step) != 1
    ]


def _narrative_prose(n: Narrative) -> list[str]:
    out: list[str] = []
    for sec in n.sections:
        out += ([sec.heading] if sec.heading else []) + sec.paragraphs
    return out


def check_content(content_dir: Path, data: ReportData, docs_dir: Path) -> list[str]:
    """Every problem of the content directory, facts evaluated against the report data."""
    return _check(content_dir, Path(data.config_dir), data, docs_dir)


def check_content_offline(
    content_dir: Path, config_dir: Path, city_ids: Iterable[str] = ()
) -> list[str]:
    """Every problem that needs no database: schema, ids, quotes, references, steps,
    explainer dimensions, undeclared numbers and construction verbs, and a narrative for each
    of `city_ids`. Facts are not evaluated."""
    return _check(content_dir, Path(config_dir), None, None, city_ids)


def _check(
    content_dir: Path,
    config_dir: Path,
    data: ReportData | None,
    docs_dir: Path | None,
    city_ids: Iterable[str] = (),
) -> list[str]:
    content_dir = Path(content_dir)
    try:
        sources = load_sources(content_dir / "sources")
    except ContentError as e:
        return [str(e)]
    load_errors: dict[str, str] = {}
    narratives = load_narratives(content_dir / "narratives", errors=load_errors)
    problems: list[str] = list(load_errors.values())
    try:
        explainer = load_document(content_dir / "explainer.yaml")
    except ContentError as e:
        return problems + [str(e)]

    expected = [c.id for c in data.cities()] if data is not None else list(city_ids)
    for cid in expected:
        if cid not in narratives and cid not in load_errors:
            problems.append(f"narratives/{cid}.yaml: missing narrative: {cid}")
    if COMBINED not in narratives:
        if COMBINED not in load_errors:
            problems.append(f"narratives/{COMBINED}.yaml: missing narrative: {COMBINED}")
    elif explainer is None:
        problems.append("explainer.yaml: missing explainer")

    for cid, n in narratives.items():
        label = f"narratives/{cid}.yaml"
        problems += _check_document(
            label,
            [n.title, n.dek, *_narrative_prose(n)],
            n.quotes,
            n.facts,
            n.data_refs,
            n.literals,
            sources,
            data,
            docs_dir,
            config_dir,
        )
        if cid == COMBINED:
            problems += _check_combined_steps(n)
        elif not any(s.role == "figures" for s in n.sections):
            problems.append(f"{label}: no figures section")

    if explainer is not None:
        problems += _check_explainer(explainer, sources, data, docs_dir, config_dir)

    for rel in PLAN_DOCUMENTS:
        try:
            doc = load_document(content_dir / rel)
        except ContentError as e:
            problems.append(str(e))
            continue
        if doc is not None:
            problems += _check_explainer_shaped(rel, doc, sources, data, docs_dir, config_dir)
        if doc is not None and rel == COUNTER_PAGE:
            rules = counter_rule_values(config_dir)
            for p in _explainer_prose(doc):
                for lit in literal_counter_rules(p, rules, doc.facts):
                    problems.append(f"{rel}: index rule stated as literal text: {lit}")

    plans, rows, plan_problems = _plans(config_dir)
    problems += plan_problems
    org_dir = content_dir / "organisations"
    if org_dir.is_dir():
        org_errors: dict[str, str] = {}
        orgs = load_organisations(org_dir, errors=org_errors)
        problems += list(org_errors.values())
        for org in orgs.values():
            problems += _check_organisation(org, sources, data, docs_dir, config_dir)
        problems += _check_coverage(config_dir, set(orgs) | set(org_errors), plans, rows)
    return problems


def _https(url: str) -> bool:
    return url.startswith("https://")


def _plans(config_dir: Path) -> tuple[list[Plan], list[ReportRow], list[str]]:
    """The plans and report rows of `config/plans/` with their problems: unknown plan or item,
    non-https URLs, empty units. No directory, no plans."""
    plan_dir = Path(config_dir) / "plans"
    if not plan_dir.is_dir():
        return [], [], []
    try:
        plans, rows = load_plans(plan_dir)
    except ConfigError as e:
        return [], [], [str(e)]
    problems: list[str] = []
    items = {p.id: {i.id for i in p.items} for p in plans}
    for p in plans:
        label = f"config/plans/plans.yaml: plan {p.id}"
        if not _https(p.url):
            problems.append(f"{label}: url is not https: {p.url}")
        for i in p.items:
            if not i.unit.strip():
                problems.append(f"{label}: item {i.id} has no unit")
    seen: dict[tuple, int] = {}
    for n, r in enumerate(rows, start=2):
        label = f"config/plans/reports.csv:{n}"
        key = (r.plan_id, r.item_id, r.year, r.quantity, r.doc_id, r.cumulative_from)
        if key in seen:
            problems.append(f"{label}: duplicate of line {seen[key]} (same figure and document)")
        seen.setdefault(key, n)
        if r.plan_id not in items:
            problems.append(f"{label}: unknown plan {r.plan_id}")
        elif r.item_id not in items[r.plan_id]:
            problems.append(f"{label}: plan {r.plan_id} has no item {r.item_id}")
        if not _https(r.url):
            problems.append(f"{label}: url is not https: {r.url}")
        if not r.unit.strip():
            problems.append(f"{label}: no unit")
        if r.quantity == "implemented_cumulative" and r.cumulative_from is None:
            problems.append(f"{label}: cumulative figure without its start year")
        if r.cumulative_from is not None and r.quantity != "implemented_cumulative":
            problems.append(f"{label}: cumulative_from on a non-cumulative quantity")
        if r.suspect and not (r.note or "").strip():
            problems.append(f"{label}: suspect row without a note")
        if r.cumulative_from is not None and r.cumulative_from > r.year:
            problems.append(f"{label}: cumulative_from {r.cumulative_from} is after year {r.year}")
    return plans, rows, problems


def _check_organisation(
    org: Organisation,
    sources: dict[str, Source],
    data: ReportData | None,
    docs_dir: Path | None,
    config_dir: Path,
) -> list[str]:
    label = f"organisations/{org.id}.yaml"
    problems = [f"{label}: {m}" for m in misplaced_quotes(org)]
    problems += _check_document(
        label,
        org.prose,
        org.quotes,
        org.facts,
        org.data_refs,
        org.literals,
        sources,
        data,
        docs_dir,
        config_dir,
    )
    if not _https(org.url):
        problems.append(f"{label}: url is not https: {org.url}")
    try:
        dims = _read_dimensions(config_dir)
    except (OSError, yaml.YAMLError, KeyError, TypeError) as e:
        return problems + [f"{label}: cannot read dimensions: {e}"]
    if dims is not None:
        for sec in org.sections:
            for key in sec.dimensions or {}:
                if key not in dims:
                    problems.append(f"{label}: section {sec.heading!r}: unknown dimension {key}")
    return problems


def _figure_pairs(config_dir: Path) -> list[tuple[str, str]]:
    """The (city, source) pairs of figures.csv; ContentError naming the file when malformed."""
    path = Path(config_dir) / "external" / "figures.csv"
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", newline="") as f:
            return list(dict.fromkeys((r["city_id"], r["source"]) for r in csv.DictReader(f)))
    except (OSError, csv.Error, KeyError) as e:
        raise ContentError(
            f"config/external/figures.csv: cannot read (city_id, source): {e!r}"
        ) from e


def _reconcile_sources(config_dir: Path) -> list[str]:
    """The external source ids of reconcile.yaml; ContentError naming the file when malformed."""
    path = Path(config_dir) / "reconcile.yaml"
    if not path.is_file():
        return []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        out: list[str] = []
        for comp in doc.get("comparisons", []):
            src = comp["external"]["source"]
            out += [src] if isinstance(src, str) else list(src)
        return list(dict.fromkeys(out))
    except (OSError, yaml.YAMLError, AttributeError, KeyError, TypeError) as e:
        raise ContentError(f"config/reconcile.yaml: cannot read comparison sources: {e!r}") from e


def _check_coverage(
    config_dir: Path, profiles: set[str], plans: list[Plan], rows: list[ReportRow]
) -> list[str]:
    """Every figures.csv (city, source) pair and reconcile source maps to a profile, and every
    Berlin plan and report-row publisher is a profile (M8 spec §3.4)."""
    label = "config/organisations.yaml"
    try:
        mapping = load_organisation_map(Path(config_dir) / "organisations.yaml")
    except ContentError as e:
        return [str(e)]
    problems: list[str] = []
    for m in mapping:
        if m.organisation not in profiles:
            problems.append(
                f"{label}: {m.city}/{m.source} maps to {m.organisation}, which has no profile"
            )
    try:
        for city, source in _figure_pairs(config_dir):
            if not any(m.source == source and m.city in (city, "*") for m in mapping):
                problems.append(f"{label}: no organisation for figures.csv source {city}/{source}")
    except ContentError as e:
        problems.append(str(e))
    try:
        for source in _reconcile_sources(config_dir):
            if not any(m.source == source for m in mapping):
                problems.append(f"{label}: no organisation for reconcile source {source}")
    except ContentError as e:
        problems.append(str(e))
    berlin_plans = {p.id for p in plans if p.city == BERLIN}
    for p in plans:
        if p.city == BERLIN and p.publisher not in profiles:
            problems.append(
                f"config/plans/plans.yaml: plan {p.id}: publisher {p.publisher} has no profile"
            )
    for n, r in enumerate(rows, start=2):
        if r.plan_id in berlin_plans and r.publisher not in profiles:
            problems.append(f"config/plans/reports.csv:{n}: publisher {r.publisher} has no profile")
    return problems


def _http_get(url: str) -> str:
    resp = httpx.get(url, follow_redirects=True, timeout=30.0)
    resp.raise_for_status()
    return resp.text


def _squash(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def check_online(sources: dict[str, Source], fetch: Callable[[str], str] = _http_get) -> list[str]:
    """Fetch each source URL once and report excerpts whose text is not on the page
    (whitespace-normalised). Never archives anything."""
    problems: list[str] = []
    pages: dict[str, str | None] = {}
    for s in sources.values():
        if s.url not in pages:
            try:
                pages[s.url] = _squash(fetch(s.url))
            except Exception as e:  # noqa: BLE001 - any fetch failure is a reported problem
                pages[s.url] = None
                problems.append(f"sources/{s.id}: cannot fetch {s.url}: {e}")
        page = pages[s.url]
        if page is None:
            continue
        for e in s.excerpts:
            if _squash(e.text) not in page:
                problems.append(f"sources/{s.id}: excerpt not found online: {e.id}")
    return problems


def counts(content_dir: Path) -> tuple[int, int, int]:
    """(narratives, sources, excerpts) of the content directory."""
    content_dir = Path(content_dir)
    sources = load_sources(content_dir / "sources")
    narratives = load_narratives(content_dir / "narratives")
    return len(narratives), len(sources), sum(len(s.excerpts) for s in sources.values())
