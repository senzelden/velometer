"""No English UI phrase on a German page (M12 spec decision 2): the visible text of every `/de/`
page, outside `lang="en"` subtrees, holds no English phrase of a phrase source. English content
shown for want of a German translation is inside `lang="en" data-fallback`, so it is no leak."""

import re
from pathlib import Path

from tests.test_a11y import all_page_urls  # noqa: F401
from tests.test_app import CONTENT, client, setup  # noqa: F401
from velometer import i18n
from velometer.app import urls
from velometer.config import reader_prose


def _config_phrases() -> list[str]:
    """The config's English reader prose with a German sibling, of four words or more."""
    return [en for _w, en, de in reader_prose(Path("config")) if len(en.split()) >= 4 and en != de]


def leak_sources():
    """Every phrase source: the name and a callable giving English phrases that must not show on
    a German page outside a lang="en" subtree. "config": the English reader prose of the config
    that has a German sibling (config.reader_prose), of four words or more."""
    return {
        "catalogue": i18n.leak_phrases,
        "content": lambda: i18n.content_phrases(CONTENT),
        "config": _config_phrases,
    }


def test_no_english_phrase_on_german_pages(client, all_page_urls):  # noqa: F811
    sources = {n: f() for n, f in leak_sources().items()}
    leaks = []
    for de in (u for u in all_page_urls if urls.lang_of(u) == "de"):
        body = i18n.visible_text(client.get(de).text)
        leaks += [f"{de} [{n}]: {p!r}" for n, ps in sources.items() for p in ps if p in body]
    assert leaks == []


def test_visible_text_skips_other_languages_and_scripts():
    html = ('<html lang="de"><head><title>The whole English title here</title></head><body>'
            '<p lang="en">An English paragraph <span>with a span</span> and more words</p>'
            '<a class="lang-switch" lang="en" href="/">English</a>'
            '<p>Deutscher Text <br> bleibt</p><script>var x = "Copied to the clipboard";</script>'
            '<button aria-label="Kopieren">x</button></body></html>')  # fmt: skip
    text = i18n.visible_text(html)
    assert "English" not in text and "Copied" not in text and "more words" not in text
    assert "Deutscher Text" in text and "bleibt" in text and "Kopieren" in text


def test_phrase_sources_are_real():
    """Each source gives phrases: a source that silently returned nothing would pass every page."""
    for name, source in leak_sources().items():
        assert len(source()) > 10, name


# --- runtime text: what Python builds at request time (provenance lines, flag details) is in no
# phrase source, so a sniff of English function words guards it, whatever the generators say ---

# common English words that are no German word: function words, and the vocabulary of
# provenance and activity notes in general (not today's generator output)
ENGLISH_WORDS = frozenset({
    "the", "and", "of", "with", "from", "for", "to", "is", "are", "were", "by", "not",
    "which", "this", "that", "needs", "limit", "retrieved", "edits", "share", "sources", "none",
    "boundary", "run", "runs", "classifier", "top", "mapper", "file", "history", "current",
    "population", "held", "constant",
})  # fmt: skip
# a word standing alone: identifiers (`activity_spike`, `legacy_km`) and ids with digits are code
WORD = re.compile(r"(?<![\w.+-])[A-Za-z]+(?![\w+-])")


def english_words(html: str) -> list[str]:
    """The English function words in the text a German reader sees outside lang="en"."""
    return sorted({w for w in WORD.findall(i18n.visible_text(html)) if w.lower() in ENGLISH_WORDS})


def test_no_english_words_on_german_city_pages(client, all_page_urls):  # noqa: F811
    """Every German city page has no English function word outside lang="en": the Over time
    tab's provenance lines and flag details are built at request time, and the Figures tab's
    source titles show our notes in German with the original title in its own language."""
    pages = [u for u in all_page_urls if u.startswith("/de/city/")]
    assert any(u.endswith("/time") for u in pages) and any(u.endswith("/figures") for u in pages)
    found = {u: w for u in pages if (w := english_words(client.get(u).text))}
    assert found == {}


def test_the_runtime_sniff_sees_the_over_time_generators(client):  # noqa: F811
    """The fixture's German Over time tab shows a flag detail and the comparison line, so the
    sniff above has generated text to read."""
    html = client.get("/de/city/berlin/time").text
    assert 'class="meta"' in html and i18n.t("de", "page.time.comparison") in html
    assert english_words("<p>retrieved the edits</p>") == ["edits", "retrieved", "the"]
    assert english_words("<p>activity_spike legacy_km <code>run</code></p>") == []
