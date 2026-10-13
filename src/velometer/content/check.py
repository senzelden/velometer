"""`velometer content --check`: validate narratives, the explainer, organisation profiles and the
plan and counter pages against the source registry and the report data (M7 spec §4.4, M8 spec
§3.4, §4.5, §5.5), and the plan figures in `config/plans/`. Every problem is one
`"<file>: <message>"` string."""

import contextlib
import csv
import html
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

from velometer import i18n
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
    LANG_TAG,
    STORY_STEPS,
    ContentError,
    DataRef,
    DocumentTr,
    Explainer,
    Fact,
    Narrative,
    NarrativeTr,
    Organisation,
    OrganisationTr,
    Quote,
    Source,
)
from velometer.content.translate import DE as DE_DIR
from velometer.content.translate import (
    English,
    History,
    Translation,
    english_path,
    git_history,
    load_english,
    load_translation,
    merge,
    old_english,
    src_hash,
    tr_strings,
    twin_path,
    walk,
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
# counter nouns and "counted" ("counted trips"); the verb "count" alone ("we count the km") says
# nothing about counter data
_COUNTER_WORDS = re.compile(r"\b(counters?|counts|counted|cyclists recorded)\b", re.IGNORECASE)
_CAUSAL = re.compile(
    r"\b(led to|lead to|leads to|because of|drove|driven by|thanks to|resulted in|caused|due to)\b",
    re.IGNORECASE,
)
_LANG_ATTR = re.compile(r"""\blang\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
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
# Threshold statements of the index rule (spec §2.13), read around a number equal to a rule value.
# A site count: the number, up to two words, then "sites" or "counters" ("3 such sites").
_SITES_AFTER = re.compile(r"\s+(?:[A-Za-z]+\s+){0,2}?(?:sites?|counters?)\b", re.IGNORECASE)
# A share of days: a percentage followed within three words by "days" ("90% of days").
_PER_CENT = re.compile(r"\s*(?:%|per\s?cent\b)", re.IGNORECASE)
_DAYS_AFTER = re.compile(r"\s+(?:[A-Za-z]+\s+){0,3}?days?\b", re.IGNORECASE)
# A base year: "2019 = 100", "2019 is the base (year)", "base year (is) 2019", "chained from
# 2019", "indexed/rebased to 2019", and a year in the parenthesis after one ("(Madrid: 2020)").
_BASE_AFTER = re.compile(
    r"\s*=\s*100\b|\s+(?:is\s+|as\s+)?(?:the\s+)?(?:index\s+)?base\b", re.IGNORECASE
)
_BASE_BEFORE = re.compile(
    r"(?:\bbase\s+year(?:\s+(?:is|of))?|\bchained\s+from|\b(?:indexed|rebased)\s+to)\s*:?\s*"
    r"(?:\d{4}\s*\([^()]*)?$",
    re.IGNORECASE,
)
BERLIN = "berlin"


def normalise_number(text: str) -> str:
    """A printed number at its printed precision, without sign prefix, commas or percent."""
    squeezed = re.sub(_GROUP_SPACE, "", text)  # "1 000" is the number 1000
    try:
        value, decimals = parse_printed(squeezed)
    except FactError:
        return text.strip()
    return f"{value:.{decimals}f}"


# --- German numbers (M12 spec §4.6) --------------------------------------------------------
# `.` and (narrow) no-break or plain spaces group thousands, `,` is the decimal comma, `−`/`-`
# the sign, `%` follows with or without a space.
_NUMBER_TOKEN_DE = re.compile(
    r"(?<![\w.,])[+−-]?(?:\d{1,3}(?:[.   ]\d{3})+(?!\d)|\d+)(?:,\d+)?"
    r"(?:[   ]?%)?"
)
# An English decimal point in German prose ("78.2") reads as a thousands group: always reported
# (a sentence-final one too: "bei 78.2."); "2.500" and "21.03.2026" are not English decimals
ENGLISH_DECIMAL_IN_DE = re.compile(r"(?<![\w.,])\d+\.\d{1,2}(?![\d,]|\.\d)")
_ORDINAL_WORDS_DE = sorted(
    {*i18n.MONTHS["de"], *i18n.MONTHS_SHORT["de"], "Quartal", "Quartals", "Jahrhundert",
     "Jahrhunderts"},
    key=len,
    reverse=True,
)  # fmt: skip
# "1. Januar", "21. März", "3. Quartal": an ordinal in date context
_ORDINAL_DE = re.compile(
    r"\b\d{1,2}\.[   ]?(?:" + "|".join(map(re.escape, _ORDINAL_WORDS_DE)) + r")(?!\w)"
)
# a quotation in another language than German: kept byte for byte from the English (parity),
# so it is checked there, not as German text
_FOREIGN_QUOTE = re.compile(
    r"""<(q|blockquote)\b[^>]*\blang\s*=\s*["'](?!de["'-])[^"']*["'][^>]*>.*?</\1>""",
    re.S | re.IGNORECASE,
)


def normalise_number_de(text: str) -> str:
    """A German printed number in `normalise_number`'s canonical form, without sign or percent:
    "1.639,8" -> "1639.8", "12,3 %" -> "12.3"."""
    s = text.strip().removesuffix("%").strip().lstrip("+−-")
    s = re.sub(r"[.   ]", "", s).replace(",", ".")
    return normalise_number(s)


def _literal_pattern(literal: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in literal.split()]
    return re.compile(r"(?<!\w)" + r"[\s\u202f\u00a0]+".join(words) + r"(?!\w)")


def undeclared_numbers(
    paragraph: str, allowed: set[str], literals: Iterable[str] = (), lang: str = "en"
) -> list[str]:
    """Numbers in the prose that are neither declared (facts), inside a declared literal's exact
    text, nor a year or ordinal. `allowed` holds the English printed values; German prose
    (`lang="de"`) is parsed the German way and may print them in German format."""
    ok = {normalise_number(a) for a in allowed} | set(allowed)
    text = _STRIPPED.sub(" ", paragraph)
    if lang == "de":
        text = _FOREIGN_QUOTE.sub(" ", text)
    for lit in sorted({x for x in literals if x.split()}, key=len, reverse=True):
        text = _literal_pattern(lit).sub(" ", text)
    if lang == "de":
        return _undeclared_de(text, ok)
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


def _undeclared_de(text: str, ok: set[str]) -> list[str]:
    found = list(dict.fromkeys(m.group(0) for m in ENGLISH_DECIMAL_IN_DE.finditer(text)))
    text = ENGLISH_DECIMAL_IN_DE.sub(" ", text)
    text = _ORDINAL_DE.sub(" ", text)
    unsigned = {x.lstrip("+\u2212-") for x in ok}
    for m in _NUMBER_TOKEN_DE.finditer(text):
        raw = m.group(0).strip()
        norm = normalise_number_de(raw)
        if norm in unsigned or raw in ok or re.fullmatch(r"20\d\d", norm):
            continue
        if raw not in found:
            found.append(raw)
    return found


def _full(value: float) -> str:
    """Every digit of a value (no exponent, no 6-significant-digit truncation)."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class RuleFamily:
    """The wording rules of one language, as data: construction verbs, counter words, causal
    phrases, number words and the index-rule threshold statements (M12 spec §4.6)."""

    verbs: re.Pattern[str]
    counter_words: re.Pattern[str]
    causal: re.Pattern[str]
    number_words: dict[str, int]
    word: re.Pattern[str]
    in_ten: re.Pattern[str]  # "nine days in ten": group 1 the number word
    sites_after: re.Pattern[str]
    per_cent: re.Pattern[str]
    days_after: re.Pattern[str]
    base_after: re.Pattern[str]
    base_before: re.Pattern[str]
    thresholds: re.Pattern[str]  # the threshold nouns the statements above look for
    number_token: re.Pattern[str]
    normalise: Callable[[str], str]

    def find(self, name: str, text: str) -> list[str]:
        """The matches of family `name` in `text`; for `number_words`, the number words."""
        if name == "number_words":
            return [w for w in self.word.findall(text) if w.lower() in self.number_words]
        return [m.group(0) for m in getattr(self, name).finditer(text)]


_LETTERS = r"[^\W\d_]+"
_ONES_DE = ("null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun",
            "zehn", "elf", "zwölf")  # fmt: skip
_TENS_DE = {"zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60,
            "siebzig": 70, "achtzig": 80, "neunzig": 90}  # fmt: skip
_I = re.IGNORECASE

RULES: dict[i18n.Lang, RuleFamily] = {
    "en": RuleFamily(
        verbs=_VERBS,
        counter_words=_COUNTER_WORDS,
        causal=_CAUSAL,
        number_words=_NUMBER_WORDS,
        word=_WORD,
        in_ten=_IN_TEN,
        sites_after=_SITES_AFTER,
        per_cent=_PER_CENT,
        days_after=_DAYS_AFTER,
        base_after=_BASE_AFTER,
        base_before=_BASE_BEFORE,
        thresholds=re.compile(r"\b(?:sites?|counters?|per\s?cent|days?|base\s+year)\b|%", _I),
        number_token=_NUMBER_TOKEN,
        normalise=normalise_number,
    ),
    # the twins of built/constructed/opened/removed only: "fertiggestellt" (completed) is not
    # flagged, and "entfernt" in the distance sense is, so prose avoids it
    "de": RuleFamily(
        verbs=re.compile(r"\b(gebaut|baute|bauten|errichtet|eröffnet|entfernt|zurückgebaut)\b", _I),
        counter_words=re.compile(r"\b(Zählstellen?|Zählwerte?|gezählt)\b", _I),
        causal=re.compile(
            r"\b(führte zu|führt zu|wegen|aufgrund|infolge|dank|verursacht|bewirkt)\b", _I
        ),
        number_words={w: i for i, w in enumerate(_ONES_DE)} | _TENS_DE,
        word=re.compile(rf"\b{_LETTERS}\b"),
        in_ten=re.compile(rf"\b({_LETTERS})\s+von\s+zehn\b", _I),  # "neun von zehn Tagen"
        sites_after=re.compile(
            rf"\s+(?:{_LETTERS}\s+){{0,2}}?(?:Zählstellen?|Messstellen?|Standorten?)\b", _I
        ),
        per_cent=re.compile(r"\s*(?:%|Prozent\b)", _I),
        days_after=re.compile(rf"\s+(?:{_LETTERS}\s+){{0,3}}?Tag(?:e|en)?\b", _I),
        base_after=re.compile(
            r"\s*=\s*100\b|\s+(?:ist\s+|als\s+)?(?:das\s+)?(?:Index-?\s*)?Basis(?:jahr)?\b", _I
        ),
        base_before=re.compile(
            r"(?:\bBasisjahr(?:\s+(?:ist|von))?|\bverkettet\s+ab|"
            r"\b(?:indexiert|umbasiert|bezogen)\s+auf)\s*:?\s*(?:\d{4}\s*\([^()]*)?$",
            _I,
        ),
        thresholds=re.compile(r"\b(?:Zählstellen?|Prozent|Tage[n]?|Basisjahr)\b|%", _I),
        number_token=_NUMBER_TOKEN_DE,
        normalise=normalise_number_de,
    ),
}


def construction_verbs(paragraph: str, rules: RuleFamily = RULES["en"]) -> list[str]:
    """Construction verbs in the prose (never allowed outside quotes for mapped km)."""
    found: list[str] = []
    for verb in rules.find("verbs", paragraph):
        if verb.lower() not in found:
            found.append(verb.lower())
    return found


def causal_counter_wording(paragraph: str, rules: RuleFamily = RULES["en"]) -> list[str]:
    """Causal wording in prose that mentions counters (counts are context, never an outcome of
    km: M8 spec §2.12, §5.5); [] when the paragraph does not mention counters."""
    if not rules.counter_words.search(paragraph):
        return []
    return rules.find("causal", paragraph)


def counter_rule_values(config_dir: Path) -> tuple[dict[float, str], str | None]:
    """(rules, error): the index rule's values (spec §2.13) -> the fact that prints each:
    `MIN_VALID` in percent, `MIN_SITES`, and each configured city's base year. No base years
    when config/counters.yaml is absent; when it is unreadable, also the reason, which the
    content check reports as a problem (the base-year rules would otherwise go unchecked)."""
    rules = {round(counter_rule(r), 6): f"counter.{r}" for r in COUNTER_RULES}
    path = Path(config_dir) / COUNTERS_FILE
    if not path.exists():
        return rules, None
    try:
        cfg = load_counters_config(path)
    except (ConfigError, OSError) as e:
        return rules, str(e)
    for e in cfg.cities:
        rules.setdefault(float(e.base_year), f"counter.{BASE_YEAR}.{e.city}")
    return rules, None


def _is_rule_fact(expr: str) -> bool:
    family, _, rest = expr.strip().partition(".")
    return family == "counter" and (rest in COUNTER_RULES or rest.startswith(f"{BASE_YEAR}."))


def _rule_kind(fact: str) -> str:
    """`min_valid`, `min_sites` or `base_year` for a rule fact name of `counter_rule_values`."""
    return fact.split(".")[1]


def _threshold(
    kind: str, text: str, start: int, end: int, percent: bool, family: RuleFamily
) -> bool:
    """Whether the number at `text[start:end]` states the index rule's `kind` threshold rather
    than another quantity of the same value ("three cities", "2020 was the COVID year")."""
    after = text[end:]
    if kind == "min_sites":
        return bool(family.sites_after.match(after))
    if kind == "min_valid":
        if not percent and (m := family.per_cent.match(after)):
            percent, after = True, after[m.end() :]
        return percent and bool(family.days_after.match(after))
    before = text[max(0, start - 80) : start]
    return bool(family.base_after.match(after) or family.base_before.search(before))


def literal_counter_rules(
    paragraph: str, rules: dict[float, str], facts: list[Fact], family: RuleFamily = RULES["en"]
) -> list[str]:
    """Index-rule values the counter prose states as literal text in a threshold statement (a
    site count before "sites", a percentage of days, a base year as "= 100", "base year" or
    "chained from"): a rule value spelled out in words ("three sites", "nine days in ten"), or a
    number equal to a rule value that no counter rule fact of the document (`counter.min_valid`,
    `counter.min_sites`, `counter.base_year.<city>`) prints. The same value elsewhere ("three
    cities", "2020 was the COVID year") is not the rule. Each is "<text> (<the fact to use>)"."""
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

    for m in family.in_ten.finditer(text):
        n = family.number_words.get(m.group(1).lower())
        fact = rules.get(float(n * 10)) if n is not None else None
        if fact is not None and _rule_kind(fact) == "min_valid":
            add(m.group(0), float(n * 10))
    for m in family.word.finditer(text):
        n = family.number_words.get(m.group(0).lower())
        if n is not None and float(n) in rules:
            kind = _rule_kind(rules[float(n)])
            if _threshold(kind, text, m.start(), m.end(), False, family):
                add(m.group(0), float(n))
    for m in family.number_token.finditer(text):
        raw = m.group(0).rstrip(",").strip()
        try:
            value = round(parse_printed(family.normalise(raw))[0], 6)
        except FactError:
            continue
        if value not in rules or value in declared:
            continue
        end = m.start() + len(raw)
        kind = _rule_kind(rules[value])
        if _threshold(kind, text, m.start(), end, raw.endswith("%"), family):
            add(raw, value)
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
    rules: RuleFamily = RULES["en"],
    lang: str = "en",
) -> list[str]:
    """The document's problems; without `data` the facts are not evaluated (their printed
    values still declare numbers). `rules` and `lang` are the prose's language."""
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
        for n in undeclared_numbers(p, allowed, literals, lang):
            add(f"undeclared number {n}")
        for v in construction_verbs(p, rules):
            add(f"construction verb {v!r}")
        for w in causal_counter_wording(p, rules):
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


_DIMENSION_ERRORS = (OSError, UnicodeDecodeError, yaml.YAMLError, KeyError, TypeError)


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
    try:
        dims = _read_dimensions(config_dir)
    except _DIMENSION_ERRORS as e:
        diff = Path(config_dir) / "differences.yaml"
        return problems + [f"{label}: cannot read dimensions from {diff}: {e}"]
    if dims is not None:
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


def _check_lang_attributes(content_dir: Path, german: bool = False) -> list[str]:
    """A problem per `lang="…"` in a content file whose value is not a BCP 47 language tag: the
    renderer writes it into the page for a quote (`<q lang>`, `<blockquote lang>`). The English
    files, or with `german` the translation files (those in a `de/` directory)."""
    problems = []
    for path in sorted(content_dir.rglob("*.yaml")):
        if (DE_DIR in path.relative_to(content_dir).parts[:-1]) != german:
            continue
        text = path.read_text(encoding="utf-8")
        for m in _LANG_ATTR.finditer(text):
            value = m.group(1) if m.group(1) is not None else m.group(2)
            if not LANG_TAG.fullmatch(value):
                problems.append(
                    f"{path.relative_to(content_dir).as_posix()}: lang attribute {value!r} "
                    "is not a BCP 47 language tag"
                )
    return problems


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
    problems: list[str] = list(load_errors.values()) + _check_lang_attributes(content_dir)
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
            rules, rules_error = counter_rule_values(config_dir)
            if rules_error is not None:
                problems.append(f"{rel}: cannot read config/{COUNTERS_FILE}: {rules_error}")
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
        problems += _check_source_rows(config_dir, orgs)
    return problems


# --- the German edition (M12 spec §4.6) ---------------------------------------------------

DE = "[de] "  # the prefix of every German problem and note
_MARKER = re.compile(r"\[[@#][^\]\s]+\]")
_NO_HISTORY = "(not found in history)"


def _foreign_quotes(text: str) -> list[str]:
    return [m.group(0) for m in _FOREIGN_QUOTE.finditer(text)]


def check_translation(
    en_rel: str,
    en_model: English,
    tr: Translation | None,
    data: ReportData | None,
    *,
    require_de: bool,
    history: History,
    content_dir: Path,
    sources: dict[str, Source],
) -> tuple[list[str], list[str]]:
    """(problems, notes) of one translation file (None: there is none) against its English
    file `en_rel` (relative to `content_dir`). Parity, staleness, orphans and the German content
    rules are problems; completeness (a missing file, string or stamp) is a note, or a problem
    when `require_de`. `history` gives the English file's earlier texts for a stale message."""
    de_rel = twin_path(Path(en_rel)).as_posix()
    problems: list[str] = []
    notes: list[str] = []

    def problem(msg: str) -> None:
        problems.append(f"{DE}{de_rel}{msg}")

    def incomplete(msg: str) -> None:
        (problems if require_de else notes).append(f"{DE}{de_rel}{msg}")

    if tr is None:
        incomplete(f": missing translation of {en_rel}")
        return problems, notes
    if isinstance(tr, NarrativeTr) and tr.city_id != en_model.city_id:
        problem(f": city_id {tr.city_id} is not the English file's {en_model.city_id}")
    if isinstance(tr, OrganisationTr) and tr.id != en_model.id:
        problem(f": id {tr.id} is not the English file's {en_model.id}")
    if isinstance(tr, DocumentTr) and len(tr.intro) != len(en_model.intro):
        problem(f" intro: paragraph count {len(tr.intro)}, English {len(en_model.intro)}")
    if len(tr.sections) != len(en_model.sections):
        problem(f": section count {len(tr.sections)}, English {len(en_model.sections)}")
    for i, (de_sec, en_sec) in enumerate(zip(tr.sections, en_model.sections, strict=False)):
        if len(de_sec.paragraphs) != len(en_sec.paragraphs):
            problem(
                f" sections.{i}: paragraph count {len(de_sec.paragraphs)}, "
                f"English {len(en_sec.paragraphs)}"
            )

    english = dict(walk(en_model))
    german = tr_strings(tr)
    versions: list[str] | None = None
    for path, en_text in english.items():
        de = german.get(path)
        if de is None:
            incomplete(f" {path}: missing German text")
            continue
        if de.src is None:
            incomplete(f" {path}: not stamped")
        elif de.src != src_hash(en_text):
            if versions is None:
                versions = history(Path(content_dir) / en_rel)
            was = old_english(versions, path, de.src) or _NO_HISTORY
            problem(f" {path}: stale (English changed)\n  was: {was}\n  now: {en_text}")
        en_markers, de_markers = (
            Counter(_MARKER.findall(en_text)),
            Counter(_MARKER.findall(de.text)),
        )
        if en_markers != de_markers:
            problem(
                f" {path}: markers differ from English (English {sorted(en_markers.elements())},"
                f" German {sorted(de_markers.elements())})"
            )
        if Counter(_foreign_quotes(en_text)) != Counter(_foreign_quotes(de.text)):
            problem(f" {path}: quotations differ from English (quotes are never translated)")
        not_stated = ".dimensions." in path and " ".join(en_text.split()) == NOT_STATED
        if not_stated and " ".join(de.text.split()) != NOT_STATED_DE:
            problem(f" {path}: {NOT_STATED!r} is {NOT_STATED_DE!r} in German")
    for path in german:
        if path not in english:
            problem(f" {path}: orphan (no English string at this path)")

    try:
        merged, fallback = merge(en_model, tr)
    except ValueError as e:  # pydantic's ValidationError too: a rule the German text breaks
        problem(f": the German text does not validate in the English structure: {e}")
        return problems, notes
    prose = [
        text
        for path, text in walk(merged)
        if path not in fallback and not path.startswith("data_refs.")
    ]
    config_dir = Path(data.config_dir) if data is not None else None
    problems += _check_document(
        f"{DE}{de_rel}",
        prose,
        [],
        en_model.facts,
        en_model.data_refs,
        list(tr.literals),
        sources,
        None,
        None,
        config_dir,
        rules=RULES["de"],
        lang="de",
    )
    if en_rel == COUNTER_PAGE and config_dir is not None:
        rules, _error = counter_rule_values(config_dir)  # an unreadable config: English reports it
        for p in prose:
            for lit in literal_counter_rules(p, rules, en_model.facts, RULES["de"]):
                problem(f": index rule stated as literal text: {lit}")
    return problems, notes


def _english_files(content_dir: Path) -> list[str]:
    """The English content files that have German twins, relative to `content_dir`."""
    rels = [f"narratives/{p.name}" for p in sorted((content_dir / "narratives").glob("*.yaml"))]
    rels += ["explainer.yaml", *PLAN_DOCUMENTS]
    rels += [
        f"organisations/{p.name}" for p in sorted((content_dir / "organisations").glob("*.yaml"))
    ]
    return [r for r in rels if (content_dir / r).is_file()]


def _relative(msg: str, content_dir: Path) -> str:
    return msg.replace(f"{content_dir}/", "")


def _check_german(
    content_dir: Path, data: ReportData | None, *, require_de: bool, history: History
) -> tuple[list[str], list[str]]:
    try:
        sources = load_sources(content_dir / "sources")
    except ContentError:
        return [], []  # the English check reports it
    problems: list[str] = [DE + p for p in _check_lang_attributes(content_dir, german=True)]
    notes: list[str] = []
    for rel in _english_files(content_dir):
        try:
            en_model = load_english(content_dir / rel)
        except ContentError:
            continue  # the English check reports it
        de_path = content_dir / twin_path(Path(rel))
        tr = None
        if de_path.is_file():
            try:
                tr = load_translation(de_path, en_model)
            except ContentError as e:
                problems.append(DE + _relative(str(e), content_dir))
                continue
        p, n = check_translation(
            rel, en_model, tr, data, require_de=require_de, history=history,
            content_dir=content_dir, sources=sources,
        )  # fmt: skip
        problems += p
        notes += n
    for de_dir in sorted({(content_dir / r).parent / DE_DIR for r in _english_files(content_dir)}):
        for de_path in sorted(de_dir.glob("*.yaml")):
            en = english_path(de_path)
            if not en.is_file():
                rel = de_path.relative_to(content_dir).as_posix()
                problems.append(f"{DE}{rel}: translation with no English file")
    for s in sources.values():
        if s.language.split("-")[0] == "de":
            continue
        for e in s.excerpts:
            if not e.gloss_de:
                msg = f"{DE}sources/{s.id}: excerpt {e.id} needs gloss_de (language {s.language})"
                (problems if require_de else notes).append(msg)
    return problems, notes


def check_content_all(
    content_dir: Path,
    data: ReportData,
    docs_dir: Path,
    *,
    require_de: bool | None = None,
    history: History = git_history,
) -> tuple[list[str], list[str]]:
    """(problems, notes) of both editions: the English problems exactly as `check_content`
    gives them, then the German ones, each prefixed "[de] ". Notes are German completeness
    gaps; they are problems when `require_de`, which defaults to `i18n.german_required` (the
    shipped tree once German content is required, never a test tree)."""
    content_dir = Path(content_dir)
    if require_de is None:
        require_de = i18n.german_required(content_dir)
    problems = check_content(content_dir, data, docs_dir)
    de_problems, notes = _check_german(content_dir, data, require_de=require_de, history=history)
    return problems + de_problems, notes


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
    except _DIMENSION_ERRORS as e:
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
    except (OSError, UnicodeDecodeError, csv.Error, KeyError) as e:
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
    except (OSError, UnicodeDecodeError, yaml.YAMLError, AttributeError, KeyError, TypeError) as e:
        raise ContentError(f"config/reconcile.yaml: cannot read comparison sources: {e!r}") from e


NOT_STATED = "not stated by the source"
NOT_STATED_DE = "von der Quelle nicht angegeben"


def _check_source_rows(config_dir: Path, orgs: dict[str, Organisation]) -> list[str]:
    """Every quoted figure source has its /sources row (M11 spec decision 1): the organisation
    behind each mapping entry whose (city, source) figures.csv or reconcile.yaml quotes has a
    "How they measure" section with all six dimensions, each cited or "not stated by the
    source". A missing profile or an unreadable file is `_check_coverage`'s problem."""
    try:
        mapping = load_organisation_map(Path(config_dir) / "organisations.yaml")
        dims = _read_dimensions(config_dir)
        pairs = _figure_pairs(config_dir)
        reconciled = set(_reconcile_sources(config_dir))
    except (ContentError, *_DIMENSION_ERRORS):
        return []
    if dims is None:
        return []
    problems: list[str] = []
    for m in mapping:
        quoted = m.source in reconciled or any(
            s == m.source and m.city in (c, "*") for c, s in pairs
        )
        org = orgs.get(m.organisation)
        if not quoted or org is None:
            continue
        label = f"organisations/{org.id}.yaml: How they measure"
        given = next((s.dimensions for s in org.sections if s.dimensions), None) or {}
        for d in dims:
            value = " ".join(str(given.get(d, "")).split())
            if not value:
                problems.append(f"{label} lacks {d} (figure source {m.source})")
            elif "[@" not in value and value != NOT_STATED:
                problems.append(f"{label}: {d} has no citation (figure source {m.source})")
    return list(dict.fromkeys(problems))


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
    from velometer.sources.download import user_agent

    resp = httpx.get(url, follow_redirects=True, timeout=30.0, headers={"User-Agent": user_agent()})
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
