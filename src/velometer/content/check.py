"""`velometer content --check`: validate narratives and the explainer against the source
registry and the report data (spec §4.4). Every problem is one `"<file>: <message>"` string."""

import html
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import httpx
import yaml

from velometer.content.facts import FactError, evaluate, parse_printed, printed_matches
from velometer.content.loader import load_explainer, load_narratives, load_sources
from velometer.content.models import (
    STORY_STEPS,
    ContentError,
    DataRef,
    Explainer,
    Fact,
    Narrative,
    Quote,
    Source,
)
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


def _check_document(
    label: str,
    prose: list[str],
    quotes: list[Quote],
    facts: list[Fact],
    data_refs: list[DataRef],
    literals: list[str],
    sources: dict[str, Source],
    data: ReportData,
    docs_dir: Path,
) -> list[str]:
    problems: list[str] = []

    def add(msg: str) -> None:
        problems.append(f"{label}: {msg}")

    excerpt_ids = {f"{s.id}/{e.id}" for s in sources.values() for e in s.excerpts}
    for q in quotes:
        if q.excerpt not in excerpt_ids:
            add(f"unknown excerpt {q.excerpt}")

    allowed: set[str] = set()
    for f in facts:
        try:
            value = evaluate(f.expr, data, docs_dir)
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
    return problems


def _dimension_ids(path: Path) -> list[str]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    dims = doc.get("dimensions", doc) if isinstance(doc, dict) else doc
    if isinstance(dims, dict):
        return [str(k) for k in dims]
    return [str(d["id"]) for d in dims or []]


def _check_explainer(
    explainer: Explainer, sources: dict[str, Source], data: ReportData, docs_dir: Path
) -> list[str]:
    label = "explainer.yaml"
    prose = [explainer.title, *explainer.intro]
    for sec in explainer.sections:
        prose += [sec.heading, *sec.paragraphs]
    problems = _check_document(
        label,
        prose,
        explainer.quotes,
        explainer.facts,
        explainer.data_refs,
        explainer.literals,
        sources,
        data,
        docs_dir,
    )
    diff = Path(data.config_dir) / "differences.yaml"
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
    """Every problem of the content directory; a load error is one problem and stops."""
    content_dir = Path(content_dir)
    try:
        sources = load_sources(content_dir / "sources")
        narratives = load_narratives(content_dir / "narratives")
        explainer = load_explainer(content_dir / "explainer.yaml")
    except ContentError as e:
        return [str(e)]

    problems: list[str] = []
    for city in data.cities():
        if city.id not in narratives:
            problems.append(f"narratives/{city.id}.yaml: missing narrative: {city.id}")
    if COMBINED not in narratives:
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
        )
        if cid == COMBINED:
            problems += _check_combined_steps(n)
        elif not any(s.role == "figures" for s in n.sections):
            problems.append(f"{label}: no figures section")

    if explainer is not None:
        problems += _check_explainer(explainer, sources, data, docs_dir)
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
