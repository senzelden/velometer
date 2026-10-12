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

# Key families built from ids at run time (`prefix` -> live ids), declared where they are used.
DYNAMIC_FAMILIES: dict[str, Callable[[], set[str]]] = {}


def german_required(content_dir: Path) -> bool:
    """German content is mandatory only for the shipped tree, never for test trees."""
    return GERMAN_CONTENT_REQUIRED and content_dir.resolve() == SHIPPED_CONTENT_DIR.resolve()


# --- catalogue ----------------------------------------------------------------------------

Value = str | dict[str, str]
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[A-Za-z0-9_]+)*$")
_PLURAL = {"one", "other"}
_warned: set[tuple[str, str]] = set()


@functools.cache
def _load(path: str, mtime_ns: int, size: int) -> dict[str, Value]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: the catalogue must be a flat mapping")
    return {str(k): v for k, v in raw.items()}


def catalogue(lang: str, directory: Path | None = None) -> dict[str, Value]:
    path = (directory or CATALOGUE_DIR) / f"{lang}.yaml"
    st = path.stat()
    return _load(str(path), st.st_mtime_ns, st.st_size)


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
    """The `js.*` strings for the client, English underneath the language."""
    merged: dict = {k: v for k, v in catalogue(DEFAULT).items() if k.startswith("js.")}
    if lang != DEFAULT:
        merged.update({k: v for k, v in catalogue(lang).items() if k.startswith("js.")})
    return merged


def _placeholders(value: Value) -> set[str]:
    forms = value.values() if isinstance(value, dict) else [value]
    return {
        name
        for form in forms
        for _, name, _, _ in string.Formatter().parse(str(form))
        if name is not None
    }


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
        elif _placeholders(en[key]) != _placeholders(de[key]):
            problems.append(f"{key}: placeholder sets differ")
    return problems


# --- numbers ------------------------------------------------------------------------------


def _localise(text: str, lang: str) -> str:
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
