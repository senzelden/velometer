"""Sideways-scrolling regions reachable by keyboard (WCAG 2.1.1, axe scrollable-region-focusable).

Every `.scroll` wrapper and every bare `<table>` (the markdown tables of prose pages scroll
themselves) gets `tabindex="0"` and an accessible name: the table's caption when it has one,
else the nearest heading above it. A wrapper becomes `role="region"` so the name is announced.
Attributes a template already sets are kept. Done once, on the rendered page, so no page
needs an edit of its own.
"""

from __future__ import annotations

import html
import re

SCROLL = re.compile(r'<div class="scroll"([^>]*)>')
BARE_TABLE = re.compile(r"<table>")
HEADING = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", re.S)
CAPTION = re.compile(r"<caption\b[^>]*>(.*?)</caption>", re.S)
FALLBACK = "Table"


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def _name(page: str, start: int, end: int) -> str:
    """The label for a region starting at `start`: its table's caption, else the last heading."""
    table = re.search(r"</table>", page[end:])
    caption = CAPTION.search(page[end : end + table.end()] if table else page[end:end])
    if caption and _text(caption.group(1)):
        return _text(caption.group(1))
    headings = HEADING.findall(page[:start])
    for h in reversed(headings):
        if _text(h):
            return _text(h)
    return FALLBACK


def name_scroll_regions(page: str) -> str:
    out: list[str] = []
    last = 0
    for m in sorted([*SCROLL.finditer(page), *BARE_TABLE.finditer(page)], key=lambda m: m.start()):
        out.append(page[last : m.start()])
        last = m.end()
        wrapper = m.re is SCROLL
        attrs = m.group(1) if wrapper else ""
        add = []
        if "tabindex=" not in attrs:
            add.append('tabindex="0"')
        if wrapper and "role=" not in attrs:
            add.append('role="region"')
        if "aria-label" not in attrs:
            add.append(f'aria-label="{html.escape(_name(page, m.start(), m.end()))}"')
        extra = (" " + " ".join(add)) if add else ""
        if wrapper:
            out.append(f'<div class="scroll"{attrs}{extra}>')
        else:
            out.append(f"<table{extra}>")
    out.append(page[last:])
    return "".join(out)
