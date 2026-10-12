"""Sideways-scrolling regions reachable by keyboard (WCAG 2.1.1, axe scrollable-region-focusable).

Every element whose class list holds `scroll` gets `tabindex="0"`, `role="region"` and an
accessible name; every bare `<table>` outside such a wrapper (markdown tables of prose pages
scroll themselves) gets `tabindex="0"` and a name. A table inside a wrapper gets nothing of its
own: one tab stop per scroller. A name comes from a caption or heading inside the region, else
from the heading above it, else a fixed fallback; never from a caption outside the region.
Attributes a template already sets are kept. Done once, on the rendered page, so no page needs
an edit of its own.
"""

from __future__ import annotations

import html
import re

from velometer.i18n import Lang, t

WRAPPER = re.compile(
    r'<(div|section)\b(?=[^>]*\bclass="[^"]*(?<![\w-])scroll(?![\w-])[^"]*")([^>]*)>'
)
BARE_TABLE = re.compile(r"<table>")
TAG = re.compile(r"<(/?)(div|section)\b[^>]*>")
HEADING = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", re.S)
CAPTION = re.compile(r"<caption\b[^>]*>(.*?)</caption>", re.S)


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def _first(pattern: re.Pattern, fragment: str) -> str:
    for m in pattern.finditer(fragment):
        if _text(m.group(1)):
            return _text(m.group(1))
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


def _name(page: str, start: int, inner: str, fallback: str) -> str:
    name = _first(CAPTION, inner) or _first(HEADING, inner)
    if name:
        return name
    for h in reversed(HEADING.findall(page[:start])):
        if _text(h):
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


def name_scroll_regions(page: str, lang: Lang = "en") -> str:
    """The page with every scrolling region and bare table named and focusable; the fixed
    fallback names are in `lang`."""
    wrappers = [(m, _extent(page, m)) for m in WRAPPER.finditer(page)]
    edits: list[tuple[int, int, str]] = []  # (start, end, replacement)
    for m, end in wrappers:
        name = _name(page, m.start(), page[m.end() : end], t(lang, "regions.scroll"))
        edits.append((m.start(), m.end(), m.group(0)[:-1] + _attrs(m.group(2), True, name) + ">"))
    for m in BARE_TABLE.finditer(page):
        if any(w.start() < m.start() < end for w, end in wrappers):
            continue
        close = page.find("</table>", m.end())
        inner = page[m.end() : close if close >= 0 else len(page)]
        name = _name(page, m.start(), inner, t(lang, "regions.table"))
        edits.append((m.start(), m.end(), "<table" + _attrs("", False, name) + ">"))
    out, last = [], 0
    for start, end, text in sorted(edits):
        out += [page[last:start], text]
        last = end
    out.append(page[last:])
    return "".join(out)
