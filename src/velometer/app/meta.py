"""The meta description of a page (M17 §4.2): plain text of at most `MAX` characters.

A city's story page takes its narrative dek, other city tabs a template sentence with the city's
headline figure (`meta.tab.<tab>`); without a dek (or with only the English one on a German
page) the story page takes `meta.city`, and without a current headline value each sentence
falls back to one without the figure. The other pages' sentences are `meta.<page>` in the UI
catalogue. Attribute text carries no markup, so a German description names no English term
that would need a `lang` mark.
"""

import html
import re

from velometer import i18n

MIN, MAX = 50, 160
OG_LOCALE = {"en": "en_GB", "de": "de_DE"}  # the editions' og:locale
# where a long dek may end early: the end of a clause, else of its main clause at a comma (never
# inside a number such as 1,279)
_STRONG = re.compile(r"[;:]\s|\.\s")
_COMMA = re.compile(r",\s")
_TAG = re.compile(r"<[^>]*>")


def plain(text: object) -> str:
    """`text` without tags or entities, its whitespace collapsed."""
    return " ".join(html.unescape(_TAG.sub("", str(text))).split())


def shorten(text: str, limit: int = MAX) -> str:
    """`text` as it is when it fits. Else it ends at the last clause end (`;`, `:` or a full
    stop) that fits and leaves at least `MIN` characters, or failing that at the first such
    comma (what follows a later comma may not stand without what it qualifies), with a full
    stop; failing both, at a word, with an ellipsis."""
    if len(text) <= limit:
        return text
    strong = [m.start() for m in _STRONG.finditer(text) if MIN - 1 <= m.start() < limit]
    comma = [m.start() for m in _COMMA.finditer(text) if MIN - 1 <= m.start() < limit]
    if strong or comma:
        return text[: strong[-1] if strong else comma[0]].rstrip() + "."
    head = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;: ")
    return head + "…"


def city_description(lang: str, tab: str, city: str, dek: object, value: str | None) -> str:
    """A city page's description: the dek on the story tab (an English fallback on a German page
    does not count), else the tab's sentence, with the headline figure `value` where there is
    one."""
    if tab == "story":
        if dek and not getattr(dek, "fallback", False) and plain(dek):
            return shorten(plain(dek))
        if value:
            return plain(i18n.t(lang, "meta.city", city=city, value=value))
        return plain(i18n.t(lang, "meta.city_plain", city=city))
    if value:
        return plain(i18n.t(lang, f"meta.tab.{tab}", city=city, value=value))
    label = plain(i18n.t(lang, f"city.tab.{tab}"))
    return plain(i18n.t(lang, "meta.tab_plain", city=city, tab=label))
