from datetime import date
from pathlib import Path

import pytest
import yaml

from velometer.content.loader import load_explainer, load_narratives, load_sources
from velometer.content.models import ContentError, Narrative, Source

SRC = {
    "id": "berlin-drs-19-25987",
    "publisher": "Abgeordnetenhaus Berlin",
    "title": "Schriftliche Anfrage 19/25987",
    "url": "https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf",
    "published": "2026-05-20",
    "accessed": "2026-10-06",
    "language": "de",
    "kind": "parliament",
    "excerpts": [
        {
            "id": "vorrangnetz-total",
            "text": "Insgesamt sind 78,2 km des Radvorrangnetzes umgesetzt worden.",
            "gloss_en": "In total, 78.2 km of the priority network have been implemented.",
            "locator": "Antwort zu 18",
        }
    ],
}


def _write(d: Path, name: str, doc: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(yaml.safe_dump(doc, allow_unicode=True))


def test_sources_load_and_merge_across_files(tmp_path):
    _write(tmp_path / "s", "de.yaml", {"sources": [SRC]})
    other = {**SRC, "id": "other", "excerpts": []}
    _write(tmp_path / "s", "fr.yaml", {"sources": [other]})
    got = load_sources(tmp_path / "s")
    assert set(got) == {"berlin-drs-19-25987", "other"}
    assert got["berlin-drs-19-25987"].published == date(2026, 5, 20)


def test_duplicate_source_id_across_files_is_an_error(tmp_path):
    _write(tmp_path / "s", "a.yaml", {"sources": [SRC]})
    _write(tmp_path / "s", "b.yaml", {"sources": [SRC]})
    with pytest.raises(ContentError, match="b.yaml.*berlin-drs-19-25987"):
        load_sources(tmp_path / "s")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/city/berlin",
        "file:///home/x/docs/reconciliation.md",
        "docs/reconciliation.md",
        "https://localhost/methodology",
    ],
)
def test_internal_or_non_http_source_url_is_refused(url):
    with pytest.raises(ValueError, match="external"):
        Source.model_validate({**SRC, "url": url})


def test_excerpt_over_60_words_is_refused():
    long = " ".join(["Wort"] * 61)
    bad = {**SRC, "excerpts": [{"id": "x", "text": long, "locator": "p. 1"}]}
    with pytest.raises(ValueError, match="60 words"):
        Source.model_validate(bad)


def test_non_english_excerpt_needs_a_gloss():
    bad = {**SRC, "excerpts": [{"id": "x", "text": "Kurz.", "locator": "p. 1"}]}
    with pytest.raises(ValueError, match="gloss_en"):
        Source.model_validate(bad)


NARR = {
    "city_id": "berlin",
    "title": "Berlin",
    "dek": "One line.",
    "sections": [
        {"paragraphs": ["First 109.1 [#series]."]},
        {"role": "figures", "heading": "Figures", "paragraphs": ["Second [@berlin-drs-19-25987]."]},
    ],
    "quotes": [{"excerpt": "berlin-drs-19-25987/vorrangnetz-total", "after": 1}],
    "facts": [{"id": "h", "expr": "series.berlin.lau.current.headline", "printed": "109.1"}],
    "data_refs": [{"id": "series", "label": "velometer v4 run set", "route": "/city/berlin/time"}],
}


def test_narratives_load_by_file_stem(tmp_path):
    _write(tmp_path / "n", "berlin.yaml", NARR)
    got = load_narratives(tmp_path / "n")
    assert list(got) == ["berlin"] and got["berlin"].paragraphs[1].startswith("Second")


def test_narrative_file_stem_must_match_city_id(tmp_path):
    _write(tmp_path / "n", "paris.yaml", NARR)
    with pytest.raises(ContentError, match="paris.yaml.*berlin"):
        load_narratives(tmp_path / "n")


def test_quote_after_must_index_a_paragraph():
    with pytest.raises(ValueError, match="after"):
        Narrative.model_validate({**NARR, "quotes": [{"excerpt": "a/b", "after": 2}]})


def test_unknown_step_is_refused():
    bad = {**NARR, "sections": [{"step": "nope", "paragraphs": ["x"]}]}
    with pytest.raises(ValueError, match="step"):
        Narrative.model_validate(bad)


def test_missing_explainer_is_none(tmp_path):
    assert load_explainer(tmp_path / "explainer.yaml") is None
