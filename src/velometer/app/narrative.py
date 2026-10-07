"""Narratives and the explainer as HTML: paragraphs with numbered citations and pull-quotes.

The text is external content. Every paragraph, quote and caption is HTML-escaped first and only
then are `code` spans marked and the `[@source_id]` and `[#data_ref]` markers turned into links,
so nothing a content file contains reaches the page as markup. Citations are numbered in
first-use order over the whole document; a tab that shows part of it lists the sources and data
it cites under those same numbers. A marker or quote naming something the registry lacks renders
as a note, never an error.
"""

import re
from dataclasses import dataclass, field

from markupsafe import Markup, escape

from velometer.content.models import DataRef, Explainer, Narrative, Organisation, Quote, Source

SOURCE_MARK = re.compile(r"\[@([A-Za-z0-9._-]+)\]")
REF_MARK = re.compile(r"\[#([A-Za-z0-9._-]+)\]")
CODE_MARK = re.compile(r"`([^`\n]+)`")  # an OSM tag in backticks, as content/check reads it
MISSING = Markup('<span class="note">source missing</span>')
MISSING_REF = Markup('<span class="note">data reference missing</span>')


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

    def __init__(self, sources: dict[str, Source], refs: dict[str, DataRef], prefix: str = ""):
        self.registry, self.declared, self.prefix = sources, refs, prefix
        self.source_no: dict[str, int] = {}
        self.ref_no: dict[str, int] = {}
        self.used_sources: list[int] = []
        self.used_refs: list[int] = []

    def paragraph(self, text: str) -> Markup:
        return Markup(f"<p>{self.inline(text)}</p>")

    def inline(self, text: str) -> Markup:
        def source(m: re.Match) -> str:
            sid = m.group(1)
            if sid not in self.registry:
                return str(MISSING)
            n = self.source_no.setdefault(sid, len(self.source_no) + 1)
            self.used_sources.append(n)
            return f'<sup><a href="#{self.prefix}src-{n}">{n}</a></sup>'

        def ref(m: re.Match) -> str:
            rid = m.group(1)
            if rid not in self.declared:
                return str(MISSING_REF)
            n = self.ref_no.setdefault(rid, len(self.ref_no) + 1)
            self.used_refs.append(n)
            return f'<sup class="dref"><a href="#{self.prefix}ref-{n}">d{n}</a></sup>'

        body = str(escape(text))  # escaped first: the markers' characters are not escaped
        body = CODE_MARK.sub(r"<code>\1</code>", body)
        return Markup(REF_MARK.sub(ref, SOURCE_MARK.sub(source, body)))


def _date(source: Source) -> str:
    return source.published.isoformat() if source.published else ""


def pullquote(sources: dict[str, Source], excerpt_ref: str) -> Markup:
    """`<figure class="pullquote">` for a `<source_id>/<excerpt_id>` reference, or a note."""
    sid, _, eid = excerpt_ref.partition("/")
    source = sources.get(sid)
    excerpt = next((e for e in source.excerpts if e.id == eid), None) if source else None
    if source is None or excerpt is None:
        return Markup('<p class="note">source missing</p>')
    head = ", ".join(escape(p) for p in [source.publisher, source.title, _date(source)] if p)
    caption = [Markup(head)]
    if url := safe_url(source.url):
        caption.append(Markup(f'<a href="{escape(url)}" rel="noopener noreferrer">source</a>'))
    if excerpt.gloss_en and source.language != "en":
        caption.append(Markup(f'<span class="gloss">{escape(excerpt.gloss_en)}</span>'))
    return Markup(
        f'<figure class="pullquote"><blockquote lang="{escape(source.language)}">'
        f"{escape(excerpt.text)}</blockquote><figcaption>"
        + " · ".join(str(c) for c in caption)
        + "</figcaption></figure>"
    )


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
) -> tuple[list[Markup], list[RenderedSection], _Numbering]:
    """Render the intro and the (heading, role, paragraphs[, dimensions]) groups; a group's
    dimension values are rendered (and numbered) before its paragraphs. A quote follows the
    paragraph its `after` indexes (counted over the groups' paragraphs in order, the intro and
    dimension values excluded); one out of range goes to the end of the last group."""
    num = _Numbering(sources, {d.id: d for d in data_refs}, prefix)
    intro_html = [num.paragraph(p) for p in intro]
    total = sum(len(g[2]) for g in groups)
    after: dict[int, list[Quote]] = {}
    for q in quotes:
        after.setdefault(q.after if 0 <= q.after < total else total - 1, []).append(q)
    sections, index = [], 0
    for heading, role, paragraphs, *dims in groups:
        sec = RenderedSection(heading, role, [])
        for key, value in ((dims[0] if dims else None) or {}).items():
            sec.dimensions.append((key, _numbered(num, sec, num.inline, value)))
        for p in paragraphs:
            sec.items.append(_numbered(num, sec, num.paragraph, p))
            sec.items += [pullquote(sources, q.excerpt) for q in after.get(index, [])]
            index += 1
        sections.append(sec)
    return intro_html, sections, num


def render_narrative(n: Narrative, sources: dict[str, Source]) -> RenderedNarrative:
    groups = [(s.heading, s.role, s.paragraphs) for s in n.sections]
    _, sections, num = _build(groups, n.quotes, sources, n.data_refs)
    return _finish(n.title, n.dek, [], sections, num, sources, n.data_refs)


def render_explainer(e: Explainer, sources: dict[str, Source]) -> RenderedNarrative:
    groups = [(s.heading, s.dimension, s.paragraphs) for s in e.sections]
    intro, sections, num = _build(groups, e.quotes, sources, e.data_refs, intro=e.intro)
    return _finish(e.title, None, intro, sections, num, sources, e.data_refs)


def render_organisation(org: Organisation, sources: dict[str, Source]) -> RenderedNarrative:
    """A profile: its sections with their dimension values, citations anchored `<id>-src-<n>`
    (the organisations page shows every profile, each with its own source list)."""
    groups = [(s.heading, s.heading, s.paragraphs, s.dimensions) for s in org.sections]
    prefix = f"{org.id}-"
    _, sections, num = _build(groups, org.quotes, sources, org.data_refs, prefix=prefix)
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
