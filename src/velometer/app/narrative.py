"""Narratives and the explainer as HTML: paragraphs with numbered citations and pull-quotes.

The text is external content. Every paragraph, quote and caption is HTML-escaped first and only
then are `code` spans marked and the `[@source_id]` and `[#data_ref]` markers turned into links,
so nothing a content file contains reaches the page as markup. Citations are numbered in
first-use order over the whole document; a tab that shows part of it lists the sources and data
it cites under those same numbers. A marker or quote naming something the registry lacks renders
as a note, never an error.

On a German page (M12) the model is the English one merged with its translation; each string
that is still English (its walk path in `fallback`) renders inside `lang="en" data-fallback`:
the `<p>` of a paragraph, the heading tag (templates write `fb(heading)` into it), or a `<span>`
around an inline value.
"""

import re
from dataclasses import dataclass, field
from functools import partial

from markupsafe import Markup, escape

from velometer.content.models import (
    LANG_TAG,
    DataRef,
    Explainer,
    Narrative,
    Organisation,
    Quote,
    Source,
)
from velometer.i18n import Lang, t

SOURCE_MARK = re.compile(r"\[@([A-Za-z0-9._-]+)\]")
REF_MARK = re.compile(r"\[#([A-Za-z0-9._-]+)\]")
CODE_MARK = re.compile(r"`([^`\n]+)`")  # an OSM tag in backticks, as content/check reads it
# *a title* in italics, as markdown writes it; a lone `*` (an OSM wildcard, `highway=*`) is text
EM_MARK = re.compile(r"(?<![\w*])\*(?=[^\s*<>])([^*\n<>]*?[^\s*<>])\*(?![\w*])")


# the one markup content may write: a quotation in another language, `<q lang="de">…</q>` inside
# a paragraph or a paragraph that is wholly `<blockquote lang="de">…</blockquote>`. Matched on the
# escaped text, the language only ever a plain tag (LANG_TAG), nothing else is let through
def _open(tag: str) -> str:
    return f"&lt;{tag} lang=&#34;({LANG_TAG.pattern})&#34;&gt;"


QUOTE_MARK = re.compile(_open("q") + r"(.*?)&lt;/q&gt;", re.DOTALL)
BLOCKQUOTE_MARK = re.compile(
    _open("blockquote") + r"((?:(?!&lt;/?blockquote).)*?)&lt;/blockquote&gt;", re.DOTALL
)


FALLBACK_ATTRS = ' lang="en" data-fallback'


class Fallback(str):
    """A string shown in English on a German page: templates mark its element with `fb()`."""

    fallback = True


def fb(text: object) -> Markup:
    """The attributes of the element that shows `text`: `lang="en" data-fallback` when it is an
    English fallback (a `Fallback` string, or True), else nothing."""
    english = text is True or getattr(text, "fallback", False)
    return Markup(FALLBACK_ATTRS) if english else Markup("")


def fb_text(text: object, english: bool | None = None) -> object:
    """`text` as it shows inside other text: in a `lang="en" data-fallback` span when it is an
    English fallback (`english`, or a `Fallback` string), else unchanged."""
    if english is None:
        english = getattr(text, "fallback", False)
    return Markup('<span lang="en" data-fallback>{}</span>').format(text) if english else text


def data_ref_label(label: str, lang: Lang) -> object:
    """A data reference's label as a page shows it. Labels are never translated (spec §4.4):
    on a German page the English label sits in a `lang="en"` span. It is the design, not a
    fallback, so it carries no `data-fallback`."""
    return label if lang == "en" else Markup('<span lang="en">{}</span>').format(label)


def _text(text: str | None, english: bool) -> str | None:
    return Fallback(text) if english and text is not None else text


def _span(html: Markup, english: bool) -> Markup:
    return Markup(f"<span{FALLBACK_ATTRS}>{html}</span>") if english else html


def _note(lang: Lang, text: str, tag: str = "span") -> Markup:
    return Markup(f'<{tag} class="note">{{}}</{tag}>').format(text)


def missing(lang: Lang = "en") -> Markup:
    """The note a citation marker naming no registered source renders as."""
    return _note(lang, t(lang, "cite.missing_source"))


def missing_ref(lang: Lang = "en") -> Markup:
    """The note a data marker naming no declared data reference renders as."""
    return _note(lang, t(lang, "cite.missing_ref"))


@dataclass
class RenderedSection:
    heading: str | None
    role: str  # "story" or "figures" (an explainer section: its dimension)
    items: list[Markup]  # paragraphs and pull-quotes, in order
    source_numbers: list[int] = field(default_factory=list)
    ref_numbers: list[int] = field(default_factory=list)
    # an organisation profile's "How they measure": (dimension id, rendered value), before items
    dimensions: list[tuple[str, Markup]] = field(default_factory=list)


@dataclass
class RenderedNarrative:
    title: str
    dek: str | None
    intro: list[Markup]
    sections: list[RenderedSection]
    sources: dict[int, Source]  # citation number -> source
    refs: dict[int, DataRef]  # data-reference number -> reference
    ref_links: dict[int, str | None]  # data-reference number -> its route link, if usable
    prefix: str = ""  # of the citation anchors (`<prefix>src-<n>`), for several documents a page

    def of_role(self, role: str) -> list[RenderedSection]:
        return [s for s in self.sections if s.role == role]

    def cited(self, sections: list[RenderedSection]) -> tuple[list, list]:
        """The (number, source) and (number, data ref) pairs the given sections cite, by number."""
        nums = sorted({n for s in sections for n in s.source_numbers})
        refs = sorted({n for s in sections for n in s.ref_numbers})
        return [(n, self.sources[n]) for n in nums], [(n, self.refs[n]) for n in refs]


class _Numbering:
    """First-use numbering of citations over one document. `prefix` starts every citation
    anchor, so documents rendered on one page keep their anchors apart."""

    def __init__(
        self,
        sources: dict[str, Source],
        refs: dict[str, DataRef],
        prefix: str = "",
        lang: Lang = "en",
    ):
        self.registry, self.declared, self.prefix, self.lang = sources, refs, prefix, lang
        self.source_no: dict[str, int] = {}
        self.ref_no: dict[str, int] = {}
        self.used_sources: list[int] = []
        self.used_refs: list[int] = []

    def paragraph(self, text: str, english: bool = False) -> Markup:
        """`<p>`, or a block quotation; `english`: an English fallback on a German page."""
        whole = BLOCKQUOTE_MARK.fullmatch(str(escape(text.strip())))
        if whole:  # a block quotation is a paragraph of its own, never inside a <p>
            inner = self.inline(self._unescape(whole.group(2)))
            return Markup(f'<blockquote lang="{whole.group(1)}"><p>{inner}</p></blockquote>')
        return Markup(f"<p{FALLBACK_ATTRS if english else ''}>{self.inline(text)}</p>")

    @staticmethod
    def _unescape(escaped: str) -> str:
        return str(Markup(escaped).unescape())

    def inline(self, text: str) -> Markup:
        def source(m: re.Match) -> str:
            sid = m.group(1)
            if sid not in self.registry:
                return str(missing(self.lang))
            n = self.source_no.setdefault(sid, len(self.source_no) + 1)
            self.used_sources.append(n)
            return f'<sup><a href="#{self.prefix}src-{n}">{n}</a></sup>'

        def ref(m: re.Match) -> str:
            rid = m.group(1)
            if rid not in self.declared:
                return str(missing_ref(self.lang))
            n = self.ref_no.setdefault(rid, len(self.ref_no) + 1)
            self.used_refs.append(n)
            return f'<sup class="dref"><a href="#{self.prefix}ref-{n}">d{n}</a></sup>'

        body = str(escape(text))  # escaped first: the markers' characters are not escaped
        body = QUOTE_MARK.sub(r'<q lang="\1">\2</q>', body)  # the only markup content may write
        # code spans first and kept whole: `*` inside one is text, and no *...* spans across one
        parts = CODE_MARK.split(body)  # text, code, text, code, ..., text
        body = "".join(
            f"<code>{part}</code>" if i % 2 else EM_MARK.sub(r"<em>\1</em>", part)
            for i, part in enumerate(parts)
        )
        return Markup(REF_MARK.sub(ref, SOURCE_MARK.sub(source, body)))


_TRIM = " (,;:–—-"


def _original_parts(english: str, german: str) -> tuple[int, int, int]:
    """(prefix end, suffix start, suffix end) of the original-language text in a German
    publisher or title: the whole words it shares with the English field at its start and at
    its end, without the punctuation of our note around them. "Ranking 2025 (report)" /
    "Ranking 2025 (Bericht)": the prefix "Ranking 2025"; "(copy by the Ville de Mérignac)" /
    "(Kopie der Ville de Mérignac)": the suffix "Ville de Mérignac"."""
    n = 0
    for a, b in zip(english, german, strict=False):
        if a != b:
            break
        n += 1
    if n < len(german) and n and german[n - 1].isalnum() and german[n].isalnum():
        n = german.rfind(" ", 0, n) + 1  # diverged inside a word: drop the whole word
    m = 0
    for a, b in zip(reversed(english[n:]), reversed(german[n:]), strict=False):
        if a != b:
            break
        m += 1
    start, end = len(german) - m, len(german)
    if 0 < start < end and german[start - 1].isalnum() and german[start].isalnum():
        nxt = german.find(" ", start)
        start = end if nxt < 0 else nxt
    while start < end and german[start] in _TRIM:
        start += 1
    if german[start:end].endswith(")") and "(" not in german[start:end]:
        end -= 1  # the bracket closing our note
    if not any(c.isalpha() for c in german[start:end]):
        start = end = len(german)
    return len(german[:n].rstrip(_TRIM)), start, end


def source_field(source: Source, field: str, lang: Lang = "en") -> Markup:
    """A source's `publisher` or `title` as a page shows it, escaped. English pages: the field.
    German pages: its German sibling (our notes in German) or the field, with the original-
    language parts in `lang="<source language>"` unless that is German."""
    text = getattr(source, field)
    if lang != "de":
        return escape(text)
    german = getattr(source, f"{field}_de")
    shown = german or text
    if source.language.split("-")[0] == "de":
        return escape(shown)
    pre, start, end = (len(shown),) * 3 if german is None else _original_parts(text, german)

    def original(part: str) -> Markup:
        return Markup('<span lang="{}">{}</span>').format(source.language, part) if part else ""

    return Markup("{}{}{}{}").format(
        original(shown[:pre]), shown[pre:start], original(shown[start:end]), shown[end:]
    )


def _date(source: Source) -> str:
    return source.published.isoformat() if source.published else ""


def pullquote(sources: dict[str, Source], excerpt_ref: str, lang: Lang = "en") -> Markup:
    """`<figure class="pullquote">` for a `<source_id>/<excerpt_id>` reference, or a note."""
    sid, _, eid = excerpt_ref.partition("/")
    source = sources.get(sid)
    excerpt = next((e for e in source.excerpts if e.id == eid), None) if source else None
    if source is None or excerpt is None:
        return _note(lang, t(lang, "cite.missing_source"), "p")
    parts = [
        source_field(source, "publisher", lang) if source.publisher else "",
        source_field(source, "title", lang) if source.title else "",
        escape(_date(source)),
    ]
    head = ", ".join(p for p in parts if p)
    caption = [Markup(head)]
    if url := safe_url(source.url):
        caption.append(
            Markup('<a href="{}" rel="noopener noreferrer">{}</a>').format(
                url, t(lang, "cite.source")
            )
        )
    if gloss := _gloss(source, excerpt, lang):
        caption.append(gloss)
    return Markup(
        f'<figure class="pullquote"><blockquote lang="{escape(source.language)}">'
        f"{escape(excerpt.text)}</blockquote><figcaption>"
        + " · ".join(str(c) for c in caption)
        + "</figcaption></figure>"
    )


def _gloss(source: Source, excerpt, lang: Lang) -> Markup | None:
    """The translation under a quote: English on an English page (none for an English quote);
    on a German page `gloss_de` (none for a German quote), else `gloss_en` as an English
    fallback."""
    if lang == "de":
        if source.language == "de":
            return None
        if excerpt.gloss_de:
            return Markup('<span class="gloss" lang="de">{}</span>').format(excerpt.gloss_de)
        if excerpt.gloss_en and source.language != "en":
            return Markup('<span class="gloss" lang="en" data-fallback>{}</span>').format(
                excerpt.gloss_en
            )
        return None
    if excerpt.gloss_en and source.language != "en":
        return Markup(f'<span class="gloss" lang="en">{escape(excerpt.gloss_en)}</span>')
    return None


def safe_url(url: str | None) -> str | None:
    """The URL if it is http(s), else None: the renderer never emits any other scheme."""
    return url if url and url.lower().startswith(("http://", "https://")) else None


def _route(route: str | None) -> str | None:
    """A data reference's link: only a site-relative path, never a scheme or `//host`."""
    return route if route and route.startswith("/") and not route.startswith("//") else None


def _numbered(num: _Numbering, sec: RenderedSection, render, text: str) -> Markup:
    """`render(text)`, recording the citation numbers it used on the section."""
    before = (len(num.used_sources), len(num.used_refs))
    out = render(text)
    sec.source_numbers += num.used_sources[before[0] :]
    sec.ref_numbers += num.used_refs[before[1] :]
    return out


def _build(
    groups: list[tuple[str | None, str, list[str]]]
    | list[tuple[str | None, str, list[str], dict[str, str] | None]],
    quotes: list[Quote],
    sources: dict[str, Source],
    data_refs: list[DataRef],
    intro: list[str] = (),
    prefix: str = "",
    lang: Lang = "en",
    fallback: frozenset[str] = frozenset(),
) -> tuple[list[Markup], list[RenderedSection], _Numbering]:
    """Render the intro and the (heading, role, paragraphs[, dimensions]) groups; a group's
    dimension values are rendered (and numbered) before its paragraphs. A quote follows the
    paragraph its `after` indexes (counted over the groups' paragraphs in order, the intro and
    dimension values excluded); one out of range goes to the end of the last group. Group `i` is
    the model's `sections.<i>`: a string whose walk path is in `fallback` renders as English."""
    num = _Numbering(sources, {d.id: d for d in data_refs}, prefix, lang)
    intro_html = [num.paragraph(p, f"intro.{i}" in fallback) for i, p in enumerate(intro)]
    total = sum(len(g[2]) for g in groups)
    after: dict[int, list[Quote]] = {}
    for q in quotes:
        after.setdefault(q.after if 0 <= q.after < total else total - 1, []).append(q)
    sections, index = [], 0
    for i, (heading, role, paragraphs, *dims) in enumerate(groups):
        path = f"sections.{i}"
        sec = RenderedSection(_text(heading, f"{path}.heading" in fallback), role, [])
        for key, value in ((dims[0] if dims else None) or {}).items():
            html = _numbered(num, sec, num.inline, value)
            sec.dimensions.append((key, _span(html, f"{path}.dimensions.{key}" in fallback)))
        for j, p in enumerate(paragraphs):
            english = f"{path}.paragraphs.{j}" in fallback
            sec.items.append(_numbered(num, sec, partial(num.paragraph, english=english), p))
            sec.items += [pullquote(sources, q.excerpt, lang) for q in after.get(index, [])]
            index += 1
        sections.append(sec)
    return intro_html, sections, num


def render_narrative(
    n: Narrative,
    sources: dict[str, Source],
    lang: Lang = "en",
    fallback: frozenset[str] = frozenset(),
) -> RenderedNarrative:
    """A narrative; `fallback` the walk paths still English on a German page (loader)."""
    groups = [(s.heading, s.role, s.paragraphs) for s in n.sections]
    _, sections, num = _build(groups, n.quotes, sources, n.data_refs, lang=lang, fallback=fallback)
    return _finish(
        _text(n.title, "title" in fallback), _text(n.dek, "dek" in fallback), [], sections, num,
        sources, n.data_refs,
    )  # fmt: skip


def render_explainer(
    e: Explainer,
    sources: dict[str, Source],
    lang: Lang = "en",
    fallback: frozenset[str] = frozenset(),
) -> RenderedNarrative:
    groups = [(s.heading, s.dimension, s.paragraphs) for s in e.sections]
    intro, sections, num = _build(
        groups, e.quotes, sources, e.data_refs, intro=e.intro, lang=lang, fallback=fallback
    )
    title = _text(e.title, "title" in fallback)
    return _finish(title, None, intro, sections, num, sources, e.data_refs)


def render_organisation(
    org: Organisation,
    sources: dict[str, Source],
    lang: Lang = "en",
    fallback: frozenset[str] = frozenset(),
) -> RenderedNarrative:
    """A profile: its sections with their dimension values, citations anchored `<id>-src-<n>`
    (the organisations page shows every profile, each with its own source list)."""
    groups = [(s.heading, s.heading, s.paragraphs, s.dimensions) for s in org.sections]
    prefix = f"{org.id}-"
    _, sections, num = _build(
        groups, org.quotes, sources, org.data_refs, prefix=prefix, lang=lang, fallback=fallback
    )
    return _finish(org.name, None, [], sections, num, sources, org.data_refs, prefix)


def _finish(title, dek, intro, sections, num, sources, data_refs, prefix="") -> RenderedNarrative:
    by_ref = {d.id: d for d in data_refs}
    return RenderedNarrative(
        title=title,
        dek=dek,
        intro=intro,
        sections=sections,
        sources={n: sources[sid] for sid, n in num.source_no.items()},
        refs={n: by_ref[rid] for rid, n in num.ref_no.items()},
        ref_links={n: _route(by_ref[rid].route) for rid, n in num.ref_no.items()},
        prefix=prefix,
    )
