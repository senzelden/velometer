"""No English UI phrase on a German page (M12 spec decision 2): the visible text of every `/de/`
page, outside `lang="en"` subtrees, holds no English phrase of a phrase source."""

from pathlib import Path

from tests.test_a11y import all_page_urls  # noqa: F401
from tests.test_app import CONTENT, client, setup  # noqa: F401
from velometer import i18n
from velometer.app import urls
from velometer.config import reader_prose

# Phrase sources that exist but are not yet enforced, with the task that enforces each. The test
# skips them; Task 7 removes "content" and deletes this constant and the skip.
LEAK_EXCLUDED = {"content": "Task 7: English content fallback is tagged lang=en"}


# While English content is untagged, a catalogue phrase that the English content also says
# cannot be told apart from content, so it is left to the content source. Exactly these;
# test_content_shared_phrases_are_the_named_ones fails on any other. Task 7 deletes this with
# the exclusion.
CONTENT_SHARED = {
    "per 100 km of main roads",  # the headline, in narratives and the explainer
    "per 100 km of main roads,",
    "A+B km per 100 km of main roads",  # the headline unit (js.unit.headline), in narratives
    "Why the figures differ",  # the explainer's title
}


# The same for the config's reader prose: English content (the explainer's headings, a profile)
# says these config phrases too. Exactly these; test_config_shared_phrases_are_the_named_ones
# fails on any other. Task 7 deletes this with the exclusion.
CONFIG_SHARED = {
    "What kind of km",  # a differences.yaml dimension label, an explainer heading
    "How length is measured",  # likewise
    "basis not stated by the source",  # length_bases.unknown, quoted by the explainer
    "completed in the year",  # metric_kinds, in the senmvku profile
}


def _config_phrases() -> list[str]:
    """The config's English reader prose with a German sibling, of four words or more, less,
    while content is excluded, the named phrases English content shares."""
    phrases = [
        en for _w, en, de in reader_prose(Path("config")) if len(en.split()) >= 4 and en != de
    ]
    if "content" not in LEAK_EXCLUDED:
        return phrases
    return [p for p in phrases if p not in CONFIG_SHARED]


def test_config_shared_phrases_are_the_named_ones():
    from velometer.content.loader import load_organisations

    said = i18n.content_phrases(CONTENT, min_words=1)
    orgs = load_organisations(CONTENT / "organisations", errors={}).values()
    said += [v for o in orgs for sec in o.sections for v in (sec.dimensions or {}).values()]
    phrases = {
        en for _w, en, de in reader_prose(Path("config")) if len(en.split()) >= 4 and en != de
    }
    assert {p for p in phrases if any(p in s for s in said)} == CONFIG_SHARED


def _content_shared() -> set[str]:
    """The catalogue phrases the English content also says."""
    said = i18n.content_phrases(CONTENT, min_words=1)
    return {p for p in i18n.leak_phrases() if any(p in s for s in said)}


def _catalogue_phrases():
    """The catalogue's phrases, less, while content is excluded, the named phrases English
    content shares."""
    phrases = i18n.leak_phrases()
    if "content" not in LEAK_EXCLUDED:
        return phrases
    return [p for p in phrases if p not in CONTENT_SHARED]


def test_content_shared_phrases_are_the_named_ones():
    """The content-shared filter cannot grow silently: a new catalogue phrase that the English
    content also says must be named in CONTENT_SHARED (or reworded)."""
    assert _content_shared() == CONTENT_SHARED


def leak_sources():
    """Every phrase source: the name and a callable giving English phrases that must not show on
    a German page outside a lang="en" subtree. "config": the English reader prose of the config
    that has a German sibling (config.reader_prose), of four words or more."""
    return {
        "catalogue": _catalogue_phrases,
        "content": lambda: i18n.content_phrases(CONTENT),
        "config": _config_phrases,
    }


def test_no_english_phrase_on_german_pages(client, all_page_urls):  # noqa: F811
    sources = {n: f() for n, f in leak_sources().items() if n not in LEAK_EXCLUDED}
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
