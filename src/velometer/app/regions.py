"""Sideways-scrolling regions reachable by keyboard (WCAG 2.1.1, axe scrollable-region-focusable).

Every element whose class list holds `scroll` gets `tabindex="0"`, `role="region"` and an
accessible name; every bare `<table>` outside such a wrapper (markdown tables of prose pages
scroll themselves) gets `tabindex="0"` and a name. A table inside a wrapper gets nothing of its
own: one tab stop per scroller, so a wrapper inside a wrapper gets nothing either. A name comes
from a caption or heading inside the region, else from the heading above it, else a fixed
fallback; never from a caption outside the region. Tags inside a script or a comment are not
the page's: they are not counted.
Attributes a template already sets are kept. Done once, on the rendered page, so no page needs
an edit of its own.
"""

from __future__ import annotations

import html
import re

from velometer.i18n import Lang, t

WRAPPER = re.compile(
    r"<(div|section)\b(?=[^>]*\bclass=([\"'])(?:(?!\2).)*?(?<![\w-])scroll(?![\w-])(?:(?!\2).)*\2)"
    r"([^>]*)>"
)
# a script's text and a comment hold no tags of the page: blanked (same length) before parsing
OPAQUE = re.compile(r"<!--.*?-->|<script\b[^>]*>.*?</script\s*>", re.S | re.I)
BARE_TABLE = re.compile(r"<table>")
TAG = re.compile(r"<(/?)(div|section)\b[^>]*>")
HEADING = re.compile(r"<h[1-6]\b([^>]*)>(.*?)</h[1-6]>", re.S)
CAPTION = re.compile(r"<caption\b([^>]*)>(.*?)</caption>", re.S)
LANG_ATTR = re.compile(r'\blang="([^"]*)"')


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def _usable(attrs: str, text: str, lang: Lang) -> bool:
    """A name source with text; on a German page also in German: a heading still in English
    there (lang="en" data-fallback) would give the region an English name outside lang="en".
    English pages name regions as they did before M12."""
    other = LANG_ATTR.search(attrs)
    return bool(text) and (lang == "en" or other is None or other.group(1) == lang)


def _first(pattern: re.Pattern, fragment: str, lang: Lang) -> str:
    for m in pattern.finditer(fragment):
        if _usable(m.group(1), _text(m.group(2)), lang):
            return _text(m.group(2))
    return ""


def _extent(page: str, m: re.Match) -> int:
    """Index just past the closing tag of the element `m` opens (end of page if unclosed)."""
    depth = 1
    for tag in TAG.finditer(page, m.end()):
        if tag.group(2) != m.group(1):
            continue
        depth += -1 if tag.group(1) else 1
        if not depth:
            return tag.end()
    return len(page)


def _name(page: str, start: int, inner: str, fallback: str, lang: Lang) -> str:
    name = _first(CAPTION, inner, lang) or _first(HEADING, inner, lang)
    if name:
        return name
    for attrs, h in reversed(HEADING.findall(page[:start])):
        if _usable(attrs, _text(h), lang):
            return _text(h)
    return fallback


def _attrs(attrs: str, wrapper: bool, name: str) -> str:
    add = []
    if "tabindex=" not in attrs:
        add.append('tabindex="0"')
    if wrapper and "role=" not in attrs:
        add.append('role="region"')
    if "aria-label" not in attrs:
        add.append(f'aria-label="{html.escape(name)}"')
    return (" " + " ".join(add)) if add else ""


def _blank(page: str) -> str:
    """`page` with each script's text and each comment as spaces, every index kept."""
    return OPAQUE.sub(lambda m: " " * len(m.group(0)), page)


def name_scroll_regions(page: str, lang: Lang = "en") -> str:
    """The page with every scrolling region and bare table named and focusable; the fixed
    fallback names are in `lang`."""
    seen = _blank(page)  # parsed; the edits go into `page` at the same indices
    wrappers: list[tuple[re.Match, int]] = []
    for m in WRAPPER.finditer(seen):
        if not any(w.start() < m.start() < end for w, end in wrappers):  # not nested
            wrappers.append((m, _extent(seen, m)))
    edits: list[tuple[int, int, str]] = []  # (start, end, replacement)
    for m, end in wrappers:
        name = _name(seen, m.start(), seen[m.end() : end], t(lang, "regions.scroll"), lang)
        tag = page[m.start() : m.end()]
        edits.append((m.start(), m.end(), tag[:-1] + _attrs(m.group(3), True, name) + ">"))
    for m in BARE_TABLE.finditer(seen):
        if any(w.start() < m.start() < end for w, end in wrappers):
            continue
        close = seen.find("</table>", m.end())
        inner = seen[m.end() : close if close >= 0 else len(seen)]
        name = _name(seen, m.start(), inner, t(lang, "regions.table"), lang)
        edits.append((m.start(), m.end(), "<table" + _attrs("", False, name) + ">"))
    out, last = [], 0
    for start, end, text in sorted(edits):
        out += [page[last:start], text]
        last = end
    out.append(page[last:])
    return "".join(out)
