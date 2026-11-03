"""The meta description of a page (M17 §4.2): plain text of at most `MAX` characters.

A city's story page takes its narrative's own `description` where it has one that fits, else
its dek verbatim; other city tabs a template sentence with the city's headline figure
(`meta.tab.<tab>`). Without either of `MIN` to `MAX` characters (an English one on a German
page does not count) the story page takes `meta.city`, never a cut text;
without a current headline value each sentence falls back to one without the figure. The other
pages' sentences are `meta.<page>` in the UI catalogue. Attribute text carries no markup, so a
German description names no English term that would need a `lang` mark.
"""

import html
import re

from velometer import i18n

MIN, MAX = 50, 160
OG_LOCALE = {"en": "en_GB", "de": "de_DE"}  # the editions' og:locale
_TAG = re.compile(r"<[^>]*>")


def plain(text: object) -> str:
    """`text` without tags or entities, its whitespace collapsed."""
    return " ".join(html.unescape(_TAG.sub("", str(text))).split())


def fits(text: str) -> bool:
    """Whether `text` is a description as it stands: `MIN` to `MAX` characters. A text outside
    is never cut (a cut can drop the clause that qualifies a figure, ADR 0006)."""
    return MIN <= len(text) <= MAX


def _own(text: object) -> str:
    """`text` as plain text, or "" when it is missing or an English fallback on a German page."""
    return "" if getattr(text, "fallback", False) else plain(text or "")


DATASET_MAX = 5000  # Google's Dataset `description`: 50 to 5000 characters


def dataset_description(dek: object, fallback: str) -> str:
    """A city `Dataset`'s description in its JSON-LD: the dek the story page shows, which the
    markup must match (Google's rule, spec §3), when it is its page's own and 50 to 5000
    characters; else `fallback`, the page's meta description."""
    text = _own(dek)
    return text if MIN <= len(text) <= DATASET_MAX else fallback


def city_description(
    lang: str, tab: str, city: str, dek: object, value: str | None, description: object = None
) -> str:
    """A city page's description: on the story tab the narrative's `description` when it fits,
    else the dek as it is when that fits (an English fallback on a German page counts for
    neither), else `meta.city`; on the other tabs the tab's sentence. Each names the headline
    figure `value` where there is one."""
    if tab == "story":
        for text in (_own(description), _own(dek)):
            if fits(text):
                return text
        if value:
            return plain(i18n.t(lang, "meta.city", city=city, value=value))
        return plain(i18n.t(lang, "meta.city_plain", city=city))
    if value:
        return plain(i18n.t(lang, f"meta.tab.{tab}", city=city, value=value))
    label = plain(i18n.t(lang, f"city.tab.{tab}"))
    return plain(i18n.t(lang, "meta.tab_plain", city=city, tab=label))
