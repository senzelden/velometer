"""tools/review_rows.py (M12 Task 9): the rows of the German review page, on the synthetic content
tree with fake translations, a tmp catalogue and a tmp explanations pair."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
import yaml

from tests.content_util import build_tree, fake_translate
from velometer.config import reader_prose
from velometer.content import translate as tr
from velometer.timeseries import explanation, explanation_hash, stamp_explanations

TOOL = Path(__file__).resolve().parents[1] / "tools" / "review_rows.py"
_spec = importlib.util.spec_from_file_location("review_rows", TOOL)
review_rows = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review_rows)

GLOSSED = {
    "sources": [
        {
            "id": "oslo-src",
            "publisher": "Oslo kommune",
            "title": "Sykkelveier (answer of 20 May 2026)",
            "title_de": "Sykkelveier (Antwort vom 20. Mai 2026)",
            "url": "https://example.org/oslo",
            "accessed": "2026-10-01",
            "language": "nb",
            "kind": "official",
            "excerpts": [
                {
                    "id": "e1",
                    "text": "Nettet er 12 km.",
                    "gloss_en": "The network is 12 km.",
                    "gloss_de": "Das Netz ist 12 km lang.",
                    "locator": "p. 1",
                }
            ],
        },
        {
            "id": "en-src",
            "publisher": "City",
            "title": "Cycling",
            "url": "https://example.org/en",
            "accessed": "2026-10-01",
            "language": "en",
            "kind": "official",
            "excerpts": [
                {
                    "id": "e1",
                    "text": "The network is 12 km long.",
                    "gloss_de": "Das Netz ist 12 km lang.",
                    "locator": "p. 2",
                }
            ],
        },
    ]
}
# a German city name that sorts before "Berlin" only when folded ("Ä" read as "A")
PARIS_DE = "Ährenstadt"
BERLIN_CAVEAT = ("DE300 is not only the city (test)", "DE300 ist nicht nur die Stadt (Test)")
CATALOGUE_EN = {"same.key": "km", "page.a.title": "Figures", "n.cities": {"one": "{n} city",
                "other": "{n} cities"}}  # fmt: skip
CATALOGUE_DE = {"same.key": "km", "page.a.title": "Zahlen", "n.cities": {"one": "{n} Stadt",
                "other": "{n} Städte"}}  # fmt: skip
EXPLANATIONS_EN = """# Report

## Explanations

### berlin/lau/2022

Cause: **campaign**. A+B fell.

### berlin/fua/2022

Cause: **campaign**, the same.
"""
EXPLANATIONS_DE = """# Bericht

### berlin/lau/2022

Ursache: **Kampagne**. A+B fiel.

### berlin/fua/2022

Ursache: **Kampagne**, dieselbe.
"""


@pytest.fixture
def tree(fixture_db, tmp_path):
    root, _data, docs = build_tree(fixture_db, tmp_path)
    config = fixture_db[1]
    shutil.copy(Path("config") / "differences.yaml", config / "differences.yaml")
    for rel in ("narratives/berlin.yaml", "narratives/paris.yaml", "narratives/combined.yaml",
                "explainer.yaml"):  # fmt: skip
        fake_translate(root / rel, root / tr.twin_path(Path(rel)))
    cities = yaml.safe_load((config / "cities.yaml").read_text(encoding="utf-8"))
    for c in cities["cities"]:
        if c["id"] == "paris":
            c["name_de"] = PARIS_DE
        if c["id"] == "berlin":
            c["nuts3_note"], c["nuts3_note_de"] = BERLIN_CAVEAT
    (config / "cities.yaml").write_text(yaml.safe_dump(cities, allow_unicode=True), "utf-8")
    (root / "sources" / "glossed.yaml").write_text(
        yaml.safe_dump(GLOSSED, allow_unicode=True), encoding="utf-8"
    )
    ui = root / "ui"
    ui.mkdir()
    for lang, doc in (("en", CATALOGUE_EN), ("de", CATALOGUE_DE)):
        (ui / f"{lang}.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), "utf-8")
    review = docs / "review"
    review.mkdir(parents=True, exist_ok=True)
    (review / "m3_timeseries.md").write_text(EXPLANATIONS_EN, encoding="utf-8")
    (review / "m3_timeseries.de.md").write_text(EXPLANATIONS_DE, encoding="utf-8")
    stamp_explanations(review / "m3_timeseries.md", review / "m3_timeseries.de.md")
    rows = review_rows.build_rows(root, config, docs, root=tmp_path)
    return rows, root, config, docs


def _by_id(rows):
    return {r["id"]: r for r in rows}


def test_each_translated_string_is_one_row_with_its_current_texts(tree):
    rows, root, _config, _docs = tree
    by_id = _by_id(rows)
    n = 0
    for rel in ("narratives/berlin.yaml", "narratives/paris.yaml", "narratives/combined.yaml",
                "explainer.yaml"):  # fmt: skip
        en = tr.load_english(root / rel)
        de_path = root / tr.twin_path(Path(rel))
        german = tr.tr_strings(tr.load_translation(de_path, en))
        file = de_path.relative_to(root.parent).as_posix()
        for path, text in tr.walk(en):
            row = by_id.pop(f"{file}#{path}")
            assert (row["en"], row["de"], row["src"]) == (
                text,
                german[path].text,
                tr.src_hash(text),
            )
            n += 1
    assert n > 10
    # no other row from a translation file
    assert not [r for r in by_id.values() if "/de/" in r["file"]]


def test_a_gloss_row_shows_the_quote_and_both_glosses(tree):
    rows, *_ = tree
    row = _by_id(rows)["content/sources/glossed.yaml#oslo-src.e1.gloss_de"]
    assert (row["kind"], row["group"], row["quote"], row["en"], row["de"]) == (
        "gloss",
        "Glosses",
        "Nettet er 12 km.",
        "The network is 12 km.",
        "Das Netz ist 12 km lang.",
    )
    title = _by_id(rows)["content/sources/glossed.yaml#oslo-src.title_de"]
    assert (title["kind"], title["en"], title["de"]) == (
        "title",
        GLOSSED["sources"][0]["title"],
        GLOSSED["sources"][0]["title_de"],
    )
    # a German-language source's quotation needs no gloss: no row
    assert not [r for r in rows if r["path"].startswith("src.")]


def test_config_rows_come_from_reader_prose(tree):
    rows, _root, config, _docs = tree
    got = {(r["file"], r["en"]): r["de"] for r in rows if r["kind"] == "config"}
    want = reader_prose(config)
    assert want and len(got) <= len(want)
    for where, en, de in want:
        assert got[(f"config/{where.split(' ')[0]}", en)] == (de or None), where
    assert any("_de" not in r["path"] and r["de"] for r in rows if r["kind"] == "config")


def test_one_explanation_row_per_german_heading(tree):
    rows, _root, _config, docs = tree
    en = docs / "review" / "m3_timeseries.md"
    got = [r for r in rows if r["kind"] == "explanation"]
    assert [r["path"] for r in got] == ["berlin/lau/2022", "berlin/fua/2022"]
    assert got[0]["de"] == "Ursache: **Kampagne**. A+B fiel."
    assert got[0]["en"] == explanation(en, "berlin/lau/2022")
    assert got[0]["src"] == explanation_hash(en, "berlin/lau/2022")
    assert {r["group"] for r in got} == {"Flagged years"}


def test_a_ui_row_for_each_key_whose_german_differs(tree):
    rows, *_ = tree
    got = {r["path"]: r for r in rows if r["kind"] == "ui"}
    assert set(got) == {"page.a.title", "n.cities"}
    assert (got["page.a.title"]["en"], got["page.a.title"]["de"]) == ("Figures", "Zahlen")
    assert got["n.cities"]["de"] == "one: {n} Stadt | other: {n} Städte"


def test_ids_are_unique_and_rows_ordered_by_group(tree):
    rows, *_ = tree
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert all(r["id"] == f"{r['file']}#{r['path']}" for r in rows)
    assert all(r["kind"] in review_rows.KINDS for r in rows)
    order = [review_rows._group_rank(r) for r in rows]
    assert order == sorted(order)
    groups = list(dict.fromkeys(r["group"] for r in rows))
    # city groups by their German name, folded: "Ährenstadt" (Paris) before "Berlin"
    assert groups == ["Overview", "Stories", PARIS_DE, "Berlin", "Glosses", "UI", "Config",
                      "Flagged years"]  # fmt: skip


def test_the_cli_writes_the_rows(tree, tmp_path):
    rows, root, config, docs = tree
    out = tmp_path / "out" / "rows.json"
    argv = ["--out", str(out), "--content", str(root), "--config", str(config), "--docs",
            str(docs), "--root", str(tmp_path)]  # fmt: skip
    assert review_rows.main(argv) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == rows


def test_an_english_quotation_is_the_english_of_its_gloss_row(tree):
    rows, *_ = tree
    row = _by_id(rows)["content/sources/glossed.yaml#en-src.e1.gloss_de"]
    assert (row["en"], row["quote"], row["de"]) == (
        "The network is 12 km long.",
        "The network is 12 km long.",
        "Das Netz ist 12 km lang.",
    )


def test_the_german_config_siblings_of_task_9_are_rows(tree):
    """The QECIO caveats (cities.yaml nuts3_note_de) and the German reports.csv notes."""
    from velometer.plans.models import load_plans, load_report_notes_de

    rows, _root, config, _docs = tree
    by_id = _by_id(rows)
    caveat = by_id["config/cities.yaml#berlin.nuts3_note"]
    assert (caveat["kind"], caveat["en"], caveat["de"]) == ("config", *BERLIN_CAVEAT)
    _plans, report_rows = load_plans(config / "plans")
    notes = load_report_notes_de(config / "plans", report_rows)
    assert notes
    for en, de in notes.items():
        row = by_id[f"config/plans/reports_notes_de.yaml#notes.{tr.src_hash(en)}"]
        assert (row["en"], row["de"]) == (en, de)
