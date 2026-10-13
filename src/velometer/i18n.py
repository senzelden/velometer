"""Language core of the reader: the UI catalogue, `t()` and the en/de formatters.

The catalogue is `content/ui/{en,de}.yaml`, a flat mapping of keys to a string or a plural
`{one, other}`. German falls back to English with one warning per key. Number, sign, percent
and date formatting is our own code (no Babel); the German tables live here so that
`report/methodology.py` and the pages share one source.
"""

from __future__ import annotations

import functools
import logging
import re
import string
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

import yaml
from markupsafe import Markup

logger = logging.getLogger(__name__)

Lang = Literal["en", "de"]
LANGS: tuple[Lang, ...] = ("en", "de")
DEFAULT: Lang = "en"
LOCALE: dict[Lang, str] = {"en": "en-GB", "de": "de-DE"}
MINUS = "−"
NNBSP = " "

SHIPPED_CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
CATALOGUE_DIR = SHIPPED_CONTENT_DIR / "ui"

# Flipped by the task that ships complete German content; see `german_required`.
GERMAN_CONTENT_REQUIRED: bool = False

CONFIG = Path(__file__).resolve().parents[2] / "config"


# --- key families built from ids ----------------------------------------------------------
# A table in the code holds ids; the label key is composed at the call (`t(lang,
# f"city.tab.{id}")`). Each family names the live source of its ids, imported inside the
# callable (the modules import this one). tests/test_ui_strings.py checks that every composed
# prefix is a family here and that every id has its key.


def _countries() -> set[str]:
    from velometer.config import load_cities

    return {c.country_iso2 for c in load_cities(CONFIG / "cities.yaml")}


def _tiers() -> set[str]:
    from velometer.timeseries import TIERS

    return set(TIERS)


def _road_classes() -> set[str]:
    from velometer.report.data import ROAD_CLASS_TEXT

    return set(ROAD_CLASS_TEXT)


def _tabs() -> set[str]:
    from velometer.app.main import TABS

    return {tab for tab, _suffix in TABS}


def _compare(name: str) -> Callable[[], set[str]]:
    def ids() -> set[str]:
        from velometer.app import compare

        return set(getattr(compare, name))

    return ids


def _literal(module: str, model: str, field: str) -> Callable[[], set[str]]:
    def ids() -> set[str]:
        import importlib
        import typing

        cls = getattr(importlib.import_module(module), model)
        return set(typing.get_args(cls.model_fields[field].annotation))

    return ids


def _categories() -> set[str]:
    from velometer.report.change import CATEGORIES

    return set(CATEGORIES)


DYNAMIC_FAMILIES: dict[str, Callable[[], set[str]]] = {
    "country.": _countries,
    "tier.": _tiers,
    "road_class.": _road_classes,
    "city.tab.": _tabs,
    "compare.group.": _compare("QUICK_SETS"),
    "compare.metric.": _compare("METRIC_IDS"),
    "compare.view.": _compare("VIEW_IDS"),
    "org.kind.": _literal("velometer.content.models", "Organisation", "kind"),
    "plan.doc_type.": _literal("velometer.plans.models", "ReportRow", "doc_type"),
    "plan.status.": _literal("velometer.plans.models", "Plan", "status"),
    "change.category.": _categories,
    "js.tier.": _tiers,
}
# key prefixes of the JS strings that are not catalogue keys: `js_strings` writes them from
# MONTHS_SHORT / MONTHS, the one home of the month names
JS_INJECTED: tuple[str, ...] = ("js.month.short.", "js.month.long.")


def german_required(content_dir: Path) -> bool:
    """German content is mandatory only for the shipped tree, never for test trees."""
    return GERMAN_CONTENT_REQUIRED and content_dir.resolve() == SHIPPED_CONTENT_DIR.resolve()


# --- catalogue ----------------------------------------------------------------------------

Value = str | dict[str, str]
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[A-Za-z0-9_]+)*$")
_PLURAL = {"one", "other"}
_warned: set[tuple[str, str]] = set()


@functools.lru_cache(maxsize=32)
def _load(path: str, mtime_ns: int, size: int) -> dict[str, object]:
    del mtime_ns, size  # cache-key parts only: an edited file reads fresh
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: the catalogue must be a flat mapping")
    return {str(k): v for k, v in raw.items()}


def catalogue(lang: str, directory: Path | None = None) -> dict[str, Value]:
    path = (directory or CATALOGUE_DIR) / f"{lang}.yaml"
    st = path.stat()
    # validated by `check_catalogues`; `_load` is typed object because YAML can hold anything
    return _load(str(path), st.st_mtime_ns, st.st_size)  # type: ignore[return-value]


catalogue.cache_clear = _load.cache_clear  # type: ignore[attr-defined]


def _lookup(lang: str, key: str) -> Value:
    cat = catalogue(lang)
    if key in cat:
        return cat[key]
    if lang != DEFAULT:
        fallback = catalogue(DEFAULT)
        if key in fallback:
            if (lang, key) not in _warned:
                _warned.add((lang, key))
                logger.warning("ui string %s missing in %s", key, lang)
            return fallback[key]
    raise KeyError(key)


def _template(lang: str, key: str, vars: dict) -> str:
    value = _lookup(lang, key)
    if isinstance(value, dict):
        value = value["one"] if vars.get("count") == 1 else value["other"]
    return value


def t(lang: str, key: str, /, **vars) -> str:
    return _template(lang, key, vars).format(**vars)


def t_markup(lang: str, key: str, /, **vars) -> Markup:
    """The template is trusted markup; the values are escaped."""
    return Markup(_template(lang, key, vars)).format(**vars)


def js_strings(lang: str) -> dict:
    """The strings of the page's `#ui-strings` block (static/js/strings.js reads them): every
    `js.*` catalogue key in `lang`, English underneath, and the month names as
    `js.month.short.<1-12>` / `js.month.long.<1-12>` from MONTHS_SHORT / MONTHS."""
    merged: dict = {k: v for k, v in catalogue(DEFAULT).items() if k.startswith("js.")}
    if lang != DEFAULT:
        merged.update({k: v for k, v in catalogue(lang).items() if k.startswith("js.")})
    for prefix, names in zip(JS_INJECTED, (MONTHS_SHORT[lang], MONTHS[lang]), strict=True):
        merged.update({f"{prefix}{m}": name for m, name in enumerate(names, 1)})
    return merged


def _placeholders(form: object) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(str(form)) if name is not None}


def check_catalogues(directory: Path | None = None) -> list[str]:
    """Problems that make the catalogues disagree; empty when they are sound."""
    problems: list[str] = []
    cats: dict[str, dict[str, Value]] = {}
    for lang in LANGS:
        try:
            cats[lang] = catalogue(lang, directory)
        except (OSError, ValueError, yaml.YAMLError) as e:
            return [f"catalogue {lang}: {e}"]
    for lang, cat in cats.items():
        for key, value in cat.items():
            if not KEY_RE.match(key):
                problems.append(f"[{lang}] malformed key: {key}")
            if isinstance(value, dict) and set(value) != _PLURAL:
                problems.append(f"[{lang}] {key}: a plural needs exactly one and other")
            elif not isinstance(value, (str, dict)):
                problems.append(f"[{lang}] {key}: the value must be a string or a plural")
    en, de = cats["en"], cats["de"]
    for key in sorted(set(en) ^ set(de)):
        where = "en" if key in en else "de"
        problems.append(f"{key}: only in {where}.yaml")
    for key in sorted(set(en) & set(de)):
        if isinstance(en[key], dict) != isinstance(de[key], dict):
            problems.append(f"{key}: plural in one catalogue and not in the other")
        elif isinstance(en[key], dict):
            for form in sorted(_PLURAL & set(en[key]) & set(de[key])):
                if _placeholders(en[key][form]) != _placeholders(de[key][form]):
                    problems.append(f"{key}.{form}: placeholder sets differ")
        elif _placeholders(en[key]) != _placeholders(de[key]):
            problems.append(f"{key}: placeholder sets differ")
    return problems


# --- numbers ------------------------------------------------------------------------------


def _localise(text: str, lang: str) -> str:
    if text.startswith("-") and not any(c in "123456789" for c in text):
        text = text[1:]  # a value that rounds to zero carries no sign
    if lang != "de":
        return text
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return MINUS + text[1:] if text.startswith("-") else text


def fmt(v: float | int | None, spec: str, lang: str) -> str:
    if v is None:
        return t(lang, "fmt.na")
    return _localise(format(v, spec), lang)


def number(v: float | int | None, lang: str, decimals: int = 1) -> str:
    return fmt(v, f",.{decimals}f", lang)


def signed(v: float | int | None, lang: str, decimals: int = 1) -> str:
    if v is None:
        return t(lang, "fmt.na")
    return _localise(f"{v:+.{decimals}f}", lang)


# `percent` has a `signed` flag that shadows the function inside it; this alias reaches it.
_signed = signed


def percent(v: float | int | None, lang: str, decimals: int = 1, signed: bool = False) -> str:
    if v is None:
        return t(lang, "fmt.na")
    n = _signed(v, lang, decimals) if signed else number(v, lang, decimals)
    return f"{n}{NNBSP}%" if lang == "de" else f"{n}%"


def number_trimmed(v: float | int | None, lang: str) -> str:
    """Thousands and decimal separators of the language. At most two decimals (config
    thresholds such as 0.5 or 0.25), trailing zeros and a bare decimal point dropped."""
    if v is None:
        return ""
    text = f"{v:,.2f}".rstrip("0").rstrip(".")
    if lang == "de":
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


# --- months, days, lists ------------------------------------------------------------------

AND: dict[str, str] = {"en": "and", "de": "und"}
MONTHS: dict[str, tuple[str, ...]] = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"),
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
           "Oktober", "November", "Dezember"),
}  # fmt: skip
MONTHS_SHORT: dict[str, tuple[str, ...]] = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "de": ("Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.",
           "Nov.", "Dez."),
}  # fmt: skip


def month_year(iso: str, lang: str, short: bool = True) -> str:
    """A month (YYYY-MM or an ISO timestamp) with its year: "Oct 2026" / "Okt. 2026", or in
    words with `short=False`: "September 2019"."""
    names = MONTHS_SHORT if short else MONTHS
    return f"{names[lang][int(iso[5:7]) - 1]} {iso[:4]}"


def january(year: int, lang: str) -> str:
    return f"{MONTHS_SHORT[lang][0]} {year}"


def long_day(d: date, lang: str) -> str:
    """A day in words: "1 January 2022", "1. Januar 2022"."""
    sep = ". " if lang == "de" else " "
    return f"{d.day}{sep}{MONTHS[lang][d.month - 1]} {d.year}"


def day(d: date, lang: str) -> str:
    """A page date: ISO in English, in words in German."""
    return long_day(d, lang) if lang == "de" else d.isoformat()


def iso_day(iso: str, lang: str) -> str:
    return day(date.fromisoformat(iso[:10]), lang)


def and_list(items: list[str], lang: str) -> str:
    """The items joined as "A", "A and B" or "A, B and C" in the language."""
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} {AND[lang]} {items[-1]}"


# --- what a reader sees (the leak test and the Chrome step) -------------------------------

SKIPPED_TAGS = {"head", "script", "style", "template", "code", "pre"}
VOID_TAGS = {"br", "img", "input", "meta", "link", "hr", "source", "wbr"}
SEEN_ATTRS = ("aria-label", "title", "alt", "placeholder")
# a tag that starts a new line of text: its edges separate words
BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "dl", "dt", "dd", "td", "th", "tr", "table", "caption",
    "section", "article", "aside", "nav", "header", "footer", "main", "figure", "figcaption",
    "blockquote", "details", "summary", "h1", "h2", "h3", "h4", "h5", "h6", "label", "legend",
    "fieldset", "option", "select", "button", "form", "body", "br",
}  # fmt: skip


def _squash(text: str) -> str:
    return " ".join(text.split())


class _Visible(HTMLParser):
    """The text and labelled attributes of a page outside skipped subtrees. A subtree is skipped
    from the element that opens it (attributes included) to its matching end tag, counted by
    tag name, so an unclosed element inside it cannot end it early or late."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.attrs: list[str] = []
        self.skip_tag: str | None = None
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.skip_tag is not None:
            if tag == self.skip_tag and tag not in VOID_TAGS:
                self.skip_depth += 1
            return
        lang = dict(attrs).get("lang")
        if tag in SKIPPED_TAGS or (lang is not None and not lang.lower().startswith("de")):
            if tag not in VOID_TAGS:
                self.skip_tag, self.skip_depth = tag, 1
            return
        self.attrs += [_squash(v) for k, v in attrs if k in SEEN_ATTRS and v]
        if tag in BLOCK_TAGS:
            self.text.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.skip_tag is None:
            lang = dict(attrs).get("lang")
            if lang is None or lang.lower().startswith("de"):
                self.attrs += [_squash(v) for k, v in attrs if k in SEEN_ATTRS and v]

    def handle_endtag(self, tag: str) -> None:
        if self.skip_tag is not None:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if not self.skip_depth:
                    self.skip_tag = None
            return
        if tag in BLOCK_TAGS:
            self.text.append(" ")

    def handle_data(self, data: str) -> None:
        if self.skip_tag is None:
            self.text.append(data)


def visible_text(html: str) -> str:
    """The text a reader of a German page sees in German: the page's text, then the
    `aria-label`, `title`, `alt` and `placeholder` values, one per line. Skips `head`, `script`,
    `style`, `template`, `code` and `pre`, and every subtree in another language (a `lang` that
    does not start with `de`). Whitespace is squashed to single spaces."""
    parser = _Visible()
    parser.feed(html)
    parser.close()
    return "\n".join([_squash("".join(parser.text)), *parser.attrs])


_TAG = re.compile(r"<[^>]*>|<[^>]*$")


def _phrase(text: str) -> str:
    """A catalogue value as a reader sees its fixed start: up to the first placeholder, without
    markup, whitespace squashed."""
    return _squash(_TAG.sub(" ", text.split("{", 1)[0]))


def leak_phrases(min_words: int = 4) -> list[str]:
    """Every English catalogue value (each plural form) whose German differs, cut at the first
    placeholder, of at least `min_words` words: none may show on a German page outside a
    `lang="en"` subtree."""
    en, de = catalogue("en"), catalogue("de")
    out: set[str] = set()
    for key, value in en.items():
        forms = value if isinstance(value, dict) else {"": value}
        other = de.get(key)
        theirs = other if isinstance(other, dict) else {"": other}
        for form, text in forms.items():
            if theirs.get(form) == text:
                continue
            phrase = _phrase(str(text))
            if len(phrase.split()) >= min_words:
                out.add(phrase)
    return sorted(out)


# a quotation in another language, a citation or data marker, a code span: none of it is
# English running text, and each splits the text around it
_NOT_PROSE = re.compile(r"<(q|blockquote)\b[^>]*>.*?</\1>|\[[@#][^\]]*\]|`[^`]*`", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+")


def _sentences(text: str, min_words: int) -> list[str]:
    out = []
    for part in _NOT_PROSE.split(text):
        if part is None or part in ("q", "blockquote"):
            continue
        for sentence in _SENTENCE_END.split(part.replace("*", "")):
            sentence = _squash(sentence).strip(" ,;:—–-")
            if len(sentence.split()) >= min_words:
                out.append(sentence)
    return out


def content_phrases(content_dir: Path, min_words: int = 8) -> list[str]:
    """Every English sentence (or the stretch of one between markers, quotations and code
    spans) of `min_words` or more words in the paragraphs, headings, titles and deks of the
    English content: narratives, the explainer, the counters and plan documents, the
    organisation profiles."""
    from velometer.content.loader import load_document, load_narratives, load_organisations

    texts: list[str] = []
    for n in load_narratives(content_dir / "narratives", errors={}).values():
        texts += [n.title, n.dek or ""]
        texts += [t for s in n.sections for t in (s.heading or "", *s.paragraphs)]
    for name in ("explainer.yaml", "counters.yaml", "plans/berlin.yaml"):
        doc = load_document(content_dir / name)
        if doc is not None:
            texts += [doc.title, *doc.intro]
            texts += [t for s in doc.sections for t in (s.heading, *s.paragraphs)]
    for org in load_organisations(content_dir / "organisations", errors={}).values():
        texts += [t for s in org.sections for t in (s.heading, *s.paragraphs)]
    return sorted({p for text in texts for p in _sentences(text, min_words)})
