"""The terms registry (`content/terms.yaml`), its glossary and the first-use mark (M17 spec §4.8).

`load(lang)` reads the registry in one language. `mark_first_use(html, terms, glossary_href)`
is a pure post-process on a rendered page: in `<main>` only, the first occurrence of each
registered short form becomes `<a class="term" href="<glossary_href>#term-<id>"><abbr
title="<expansion>">…</abbr></a>`. Each scope has its own first occurrence: the always-visible
content, each `<details>` and each `.phone-only` block (settled 4), so a reader who opens only
one of them still gets the link. Skipped, and not counted as an occurrence: links, headings,
code, SVG, scripts and styles, form controls, `<summary>`, hidden text, any element with a
`lang` (a foreign term or an English fallback), and the glossary itself (`#terms`). Nothing
outside the marked words changes, byte for byte, and a page without `<main>` (a fragment) is
returned as it is.

`glossary(terms, sources, lang)` is the methodology's `#terms` section model: each entry's
explanation rendered the way content text is (`code` and `<i lang>` marks), with its `cite`
sources numbered as the explainer numbers them.
"""

from __future__ import annotations

import functools
import re
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import yaml
from markupsafe import Markup, escape
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from velometer import i18n
from velometer.app.narrative import Numbering
from velometer.content.models import LANG_TAG, ContentError, Source
from velometer.i18n import LANGS, Lang

TERMS_FILE = "terms.yaml"
GLOSSARY_ID = "terms"
ANCHOR_PREFIX = "term-"
CITE_PREFIX = "terms-"  # the glossary's citation anchors (`terms-src-<n>`)
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class Term(BaseModel):
    """One registry entry in one language. `forms` are the spellings that count as it, `short`
    first; `context` the words one of which must stand right before it (a tier letter counts
    only after the word for tier)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    short: str
    also: tuple[str, ...] = ()
    expansion: str
    expansion_lang: str | None = None
    explanation: str
    cite: tuple[str, ...] = ()
    tier: str | None = None
    context: tuple[str, ...] = ()

    @property
    def forms(self) -> tuple[str, ...]:
        return (self.short, *self.also)

    @property
    def anchor(self) -> str:
        return ANCHOR_PREFIX + self.id


class _Raw(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    short: str
    forms: dict[str, list[str]] = Field(default_factory=dict)
    tier: str | None = None
    expansion: dict[str, str] | None = None
    expansion_lang: dict[str, str] = Field(default_factory=dict)
    explanation: dict[str, str]
    cite: list[str] = Field(default_factory=list)


class _RawFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier_words: dict[str, list[str]]
    terms: list[_Raw]


def load(lang: Lang, content_dir: Path = i18n.SHIPPED_CONTENT_DIR) -> list[Term]:
    """The registry in `lang`, in file order; [] without a registry file. ContentError, naming
    the term, for an invalid one: a language missing, an unknown tier, a duplicate id or form."""
    path = Path(content_dir) / TERMS_FILE
    try:
        stamp = path.stat().st_mtime_ns
    except FileNotFoundError:
        return []
    return list(_load(lang, path, stamp))


@functools.lru_cache(maxsize=16)
def _load(lang: Lang, path: Path, _stamp: int) -> tuple[Term, ...]:
    try:
        raw = _RawFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError) as e:
        raise ContentError(f"{path}: {e}") from e
    from velometer.timeseries import TIERS

    missing_words = [w for w in LANGS if not raw.tier_words.get(w)]
    if missing_words:
        raise ContentError(f"{path}: tier_words has no {', '.join(missing_words)}")
    out: list[Term] = []
    seen_forms: dict[str, str] = {}
    for r in raw.terms:
        where = f"{path}: term {r.id!r}"
        if not ID.fullmatch(r.id) or any(t.id == r.id for t in out):
            raise ContentError(f"{where}: the id is not a unique lower-case slug")
        gaps = [f"explanation.{w}" for w in LANGS if not (r.explanation.get(w) or "").strip()]
        if r.tier is not None:
            if r.tier not in TIERS or r.short != r.tier:
                raise ContentError(f"{where}: tier {r.tier!r} is not one of {TIERS} or its short")
            if r.expansion is not None:
                raise ContentError(f"{where}: a tier's expansion is its label tier.{r.tier}")
        else:
            gaps += [f"expansion.{w}" for w in LANGS if not (r.expansion or {}).get(w, "").strip()]
        if gaps:
            raise ContentError(f"{where}: missing {', '.join(gaps)}")
        bad_lang = [v for v in r.expansion_lang.values() if not LANG_TAG.fullmatch(v)]
        if bad_lang or set(r.expansion_lang) - set(LANGS):
            raise ContentError(f"{where}: expansion_lang {r.expansion_lang!r}")
        also = tuple(r.forms.get(lang, ()))
        for form in (r.short, *also):
            if form in seen_forms:
                raise ContentError(f"{where}: form {form!r} is also {seen_forms[form]!r}'s")
            seen_forms[form] = r.id
        out.append(
            Term(
                id=r.id,
                short=r.short,
                also=also,
                expansion=_tier_expansion(lang, r.tier, where) if r.tier else r.expansion[lang],
                expansion_lang=r.expansion_lang.get(lang),
                explanation=" ".join(r.explanation[lang].split()),
                cite=tuple(r.cite),
                tier=r.tier,
                context=tuple(raw.tier_words[lang]) if r.tier else (),
            )
        )
    return tuple(out)


def _tier_expansion(lang: Lang, tier: str, where: str) -> str:
    """The tier label `tier.<X>` ("A separated track") without its letter: one source."""
    label = i18n.t(lang, f"tier.{tier}")
    if not label.startswith(f"{tier} "):
        raise ContentError(f"{where}: label tier.{tier} {label!r} does not start with {tier!r}")
    return label[len(tier) + 1 :]


# --- the first-use mark -------------------------------------------------------------------

# neither marked nor counted: their text is a link, a heading, code, a picture, a control, or not
# shown as page text
SKIP_TAGS = frozenset({
    "a", "abbr", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "kbd", "samp", "svg", "math",
    "script", "style", "template", "noscript", "button", "summary", "label", "select", "option",
    "textarea", "title", "cite",
})  # fmt: skip
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track",
    "wbr",
})  # fmt: skip
# hidden text, and a citation to copy (the Cite box's text), which stays as it is cited
SKIP_CLASSES = frozenset({"visually-hidden", "cite-text"})
SCOPE_CLASS = "phone-only"
EDGE_BEFORE = r"(?<![\w+])"  # a form is a whole token: `A+B` is not inside `A+B+E`
EDGE_AFTER = r"(?![\w+])"


@functools.lru_cache(maxsize=16)
def _matchers(terms: tuple[Term, ...]) -> tuple[re.Pattern | None, tuple[re.Pattern, ...]]:
    """(any form anywhere, for a quick no; one pattern per term whose group `t` is the form)."""
    patterns = []
    for t in terms:
        forms = "|".join(re.escape(f) for f in sorted(t.forms, key=len, reverse=True))
        form = f"(?P<t>{forms}){EDGE_AFTER}"
        if t.context:
            words = "|".join(re.escape(w) for w in t.context)
            patterns.append(re.compile(rf"{EDGE_BEFORE}(?:{words})\s+{form}"))
        else:
            patterns.append(re.compile(EDGE_BEFORE + form))
    every = sorted({f for t in terms for f in t.forms}, key=len, reverse=True)
    quick = re.compile("|".join(re.escape(f) for f in every)) if every else None
    return quick, tuple(patterns)


def _mark(term: Term, text: str, href: str) -> str:
    lang = f' lang="{term.expansion_lang}"' if term.expansion_lang else ""
    return (
        f'<a class="term" href="{escape(href)}#{term.anchor}">'
        f'<abbr title="{escape(term.expansion)}"{lang}>{text}</abbr></a>'
    )


class _Marker(HTMLParser):
    """Collects the edits (start, end, replacement) of one `<main>`, offsets into its text. The
    data is read raw (`convert_charrefs=False`), so an offset in a text run is one in the page."""

    def __init__(self, source: str, terms: tuple[Term, ...], href: str):
        super().__init__(convert_charrefs=False)
        self.terms, self.href = terms, href
        self.patterns = _matchers(terms)[1]
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", source)]
        self.stack: list[tuple[str, bool, bool]] = []  # (tag, skipped, scope)
        self.skipping = 0
        self.scopes: list[set[str]] = [set()]
        self.edits: list[tuple[int, int, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        skipped = (
            tag in SKIP_TAGS
            or "lang" in a
            or "hidden" in a
            or a.get("aria-hidden") == "true"
            or a.get("id") == GLOSSARY_ID
            or bool(SKIP_CLASSES & set(classes))
        )
        scope = tag == "details" or SCOPE_CLASS in classes
        self.stack.append((tag, skipped, scope))
        self.skipping += skipped
        if scope:
            self.scopes.append(set())

    def handle_startendtag(self, tag, attrs):
        pass  # `<x/>` opens nothing

    def handle_endtag(self, tag):
        at = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i][0] == tag), None)
        if at is None:
            return  # a stray end tag closes nothing
        while len(self.stack) > at:
            _tag, skipped, scope = self.stack.pop()
            self.skipping -= skipped
            if scope:
                self.scopes.pop()

    def handle_data(self, data):
        if self.skipping:
            return
        line, col = self.getpos()
        base = self.line_starts[line - 1] + col
        used = self.scopes[-1]
        found = []  # (start, end, term) of every occurrence, marked or not
        for term, pattern in zip(self.terms, self.patterns, strict=True):
            found += [(m.start("t"), m.end("t"), term) for m in pattern.finditer(data)]
        # the longest form at a place wins, and an occurrence inside another is none
        found.sort(key=lambda f: (f[0], f[0] - f[1]))
        end = 0
        for start, stop, term in found:
            if start < end:
                continue
            end = stop
            if term.id not in used:
                used.add(term.id)
                mark = _mark(term, data[start:stop], self.href)
                self.edits.append((base + start, base + stop, mark))


def mark_first_use(html: str, terms: list[Term] | tuple[Term, ...], glossary_href: str) -> str:
    """`html` with the first occurrence of each term in each scope of its `<main>` marked as a
    link to `glossary_href#term-<id>` around an `<abbr>`; see the module docstring. Pure."""
    start = re.search(r"<main\b", html)
    stop = html.rfind("</main>")
    if start is None or stop < start.start() or not terms:
        return html
    main = html[start.start() : stop]
    terms = tuple(terms)
    quick, _ = _matchers(terms)
    if quick is None or not quick.search(main):
        return html
    marker = _Marker(main, terms, glossary_href)
    marker.feed(main)
    marker.close()
    if not marker.edits:
        return html
    parts, at = [], 0
    for begin, end, text in marker.edits:
        parts += [main[at:begin], text]
        at = end
    parts.append(main[at:])
    return html[: start.start()] + "".join(parts) + html[stop:]


MARKED = re.compile(
    r'<a class="term" href="[^"]*"><abbr title="[^"]*"(?: lang="[^"]*")?>([^<]*)</abbr></a>'
)


def unmark(html: str) -> str:
    """`html` without the marks `mark_first_use` added: for reading a page's text as written."""
    return MARKED.sub(r"\1", html)


# --- the glossary -------------------------------------------------------------------------

# the one markup an explanation may write besides content's own (`<i lang>`, `code`): a name in
# another language, upright; the language is a plain tag
SPAN_MARK = re.compile(r'<span lang="(' + LANG_TAG.pattern + r')">(.*?)</span>', re.S)


def glossary(terms: list[Term], sources: dict[str, Source], lang: Lang) -> SimpleNamespace:
    """The `#terms` section: `entries` [(term, explanation Markup)], `cited` [(n, source)] for
    `city/_cited.html`, and its anchor `prefix`. A cited id the source registry lacks renders as
    the content's "missing" note."""
    num = Numbering(sources, {}, prefix=CITE_PREFIX, lang=lang)

    def explained(text: str) -> Markup:
        # a name in another language, `<span lang="en">…</span>`, stays upright: each part is
        # rendered as content text is, and the span is written around its part
        parts = SPAN_MARK.split(text)  # text, lang, inner, text, lang, inner, ..., text
        out = Markup("")
        for i in range(0, len(parts), 3):
            out += num.inline(parts[i]) if parts[i] else Markup("")
            if i + 2 < len(parts):
                inner = num.inline(parts[i + 2])
                out += Markup('<span lang="{}">{}</span>').format(parts[i + 1], inner)
        return out

    entries = []
    for t in terms:
        marks = "".join(f"[@{c}]" for c in t.cite)
        entries.append((t, explained(t.explanation + marks)))
    cited = [(n, sources[sid]) for sid, n in sorted(num.source_no.items(), key=lambda kv: kv[1])]
    return SimpleNamespace(entries=entries, cited=cited, prefix=CITE_PREFIX, ref_links={})
