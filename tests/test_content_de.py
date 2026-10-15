import subprocess

import pytest

from tests.content_util import build_tree, fake_translate
from velometer.content import check as ck
from velometer.content import translate as tr


@pytest.mark.parametrize(
    "raw,canon",
    [("78,2", "78.2"), ("1.639,8", "1639.8"), ("−3,2", "3.2"), ("12,3 %", "12.3"),
     ("12,3 %", "12.3"), ("1 639", "1639"), ("2.500", "2500")],
)  # fmt: skip
def test_german_numbers_parse_the_german_way(raw, canon):
    assert ck.normalise_number_de(raw) == canon


def test_markers_and_citations_hold_no_numbers():
    p = "Der Anteil stieg auf 78,2 %[#share_2026] und um 12,3 Prozent [@src-2022]."
    assert ck.undeclared_numbers(p, {"78.2", "12.3"}, (), lang="de") == []


def test_english_decimal_point_in_german_is_reported():
    assert ck.undeclared_numbers("Der Wert lag bei 78.2 km.", {"78.2"}, (), lang="de") == ["78.2"]


def test_comma_is_never_a_thousands_separator_in_german():
    assert ck.undeclared_numbers("Rund 78,2 km.", {"782"}, (), lang="de") == ["78,2"]


def test_german_ordinals_in_date_context_and_years():
    p = "Am 1. Januar 2022 und zum 21. März 2026 lag der Stand im 3. Quartal vor."
    assert ck.undeclared_numbers(p, set(), (), lang="de") == []


def test_german_literal_is_accepted():
    assert ck.undeclared_numbers("rund 250 km Radwege", set(), ["rund 250 km"], lang="de") == []


def test_a_negative_english_fact_declares_its_german_form():
    assert ck.undeclared_numbers("Ein Minus von −3,2 km.", {"−3.2"}, (), lang="de") == []


@pytest.mark.parametrize(
    "family,text",
    [("verbs", "Die Stadt hat 20 km gebaut."), ("verbs", "Der Weg wurde zurückgebaut."),
     ("causal", "Mehr Zählstellen führte zu mehr Radverkehr."),
     ("number_words", "neun von zehn Wegen")],
)  # fmt: skip
def test_german_rule_families(family, text):
    assert ck.RULES["de"].find(family, text)


def test_completed_is_not_a_construction_verb_in_either_language():
    assert not ck.RULES["de"].find("verbs", "Der Abschnitt wurde fertiggestellt.")
    assert not ck.RULES["en"].find("verbs", "The section was completed.")


def test_german_index_rule_stated_as_literal_text_is_found():
    rules = {90.0: "counter.min_valid", 3.0: "counter.min_sites"}
    found = ck.literal_counter_rules(
        "Gezählt wird an neun von zehn Tagen, mit 3 Zählstellen.", rules, [], ck.RULES["de"]
    )
    assert any("neun von zehn" in f for f in found) and any(f.startswith("3 ") for f in found)


def test_whitespace_change_is_not_stale_but_a_real_edit_is():
    a = "Berlin has 12.5 km of tracks."
    assert tr.src_hash(a) == tr.src_hash("Berlin  has 12.5 km\nof tracks.")
    assert tr.src_hash(a) != tr.src_hash("Berlin has 12.5 km of lanes.")


class Tree:
    """A synthetic content tree with a German twin of its berlin narrative (no shipped prose)."""

    def __init__(self, fixture_db, tmp_path):
        self.root, self.data, self.tmp = build_tree(fixture_db, tmp_path)
        self.en = self.root / "narratives" / "berlin.yaml"
        self.de = self.root / "narratives" / "de" / "berlin.yaml"
        self.versions = []  # earlier English texts, newest first, as git would give them
        english = [*sorted((self.root / "narratives").glob("*.yaml")), self.root / "explainer.yaml"]
        for en in english:  # every English file gets its twin
            fake_translate(en, tr.twin_path(en))

    def edit(self, path, fn, *, german=False):
        target = self.de if german else self.en
        if not german:
            self.versions.insert(0, self.en.read_text(encoding="utf-8"))
        tr.edit_path(target, path, fn)  # a small helper in translate.py: load, change, dump

    def check(self, require_de=False):
        problems, notes = ck.check_content_all(
            self.root, self.data, self.tmp, require_de=require_de,
            history=lambda p: self.versions if p == self.en else [],
        )  # fmt: skip
        return problems, notes


@pytest.fixture
def tree(fixture_db, tmp_path):
    return Tree(fixture_db, tmp_path)


def test_a_clean_translation_has_no_problems(tree):
    assert tree.check(require_de=True) == ([], [])


def test_stale_message_shows_old_and_new_english(tree):
    tree.edit("sections.0.paragraphs.0", lambda s: s.replace("Berlin has", "Berlin now has"))
    problems, _ = tree.check()
    stale = [p for p in problems if p.startswith("[de] ") and "stale" in p]
    assert len(stale) == 1
    assert "was: Berlin has" in stale[0] and "now: Berlin now has" in stale[0]


def test_stale_message_without_history_says_so(tree):
    tree.edit("title", lambda s: s + " x")
    tree.versions.clear()
    (stale,) = [p for p in tree.check()[0] if "stale" in p]
    assert "was: (not found in history)" in stale


def test_parity_of_markers_is_enforced(tree):
    tree.edit("sections.0.paragraphs.0", lambda s: s.replace("[@src]", ""), german=True)
    assert any(p.startswith("[de] ") and "markers" in p for p in tree.check()[0])


def test_parity_of_foreign_quotations_is_enforced(tree):
    tree.edit("sections.0.paragraphs.0", lambda s: s + ' <q lang="pl">Tak.</q>')
    fake_translate(tree.en, tree.de)
    assert tree.check()[0] == []
    tree.edit("sections.0.paragraphs.0", lambda s: s.replace("Tak.", "Ja."), german=True)
    assert any(p.startswith("[de] ") and "quotations" in p for p in tree.check()[0])


def test_parity_of_original_terms_is_enforced(tree):
    """An original term in another language is kept byte for byte, like a quotation: the German
    edition shows the same `<i lang="da">cykelsti</i>`, only its bracketed translation differs."""
    tree.edit("sections.0.paragraphs.0", lambda s: s + ' <i lang="da">cykelsti</i> (x)')
    fake_translate(tree.en, tree.de)
    assert tree.check()[0] == []
    tree.edit(
        "sections.0.paragraphs.0",
        lambda s: s.replace('lang="da">cykelsti', 'lang="da">Radweg'),
        german=True,
    )
    assert any(p.startswith("[de] ") and "original terms" in p for p in tree.check()[0])


def test_section_and_paragraph_counts_must_match(tree):
    tree.edit("sections.1.paragraphs", lambda ps: ps + ["Übersetzt: extra"], german=True)
    assert any("paragraph count" in p for p in tree.check()[0])


def test_completeness_is_a_note_unless_required(tree):
    tree.de.unlink()
    problems, notes = tree.check(require_de=False)
    assert problems == [] and any(n.startswith("[de] ") and "missing" in n for n in notes)
    problems, _ = tree.check(require_de=True)
    assert any(p.startswith("[de] ") and "missing" in p for p in problems)


def test_a_missing_string_and_a_missing_stamp_are_completeness(tree):
    fake_translate(tree.en, tree.de, drop=frozenset({"sections.0.paragraphs.0", "dek"}))
    doc = tr.yaml.safe_load(tree.de.read_text(encoding="utf-8"))
    del doc["title"]["src"]
    tr.dump(tree.de, doc)
    problems, notes = tree.check(require_de=False)
    assert problems == []  # the English fallback paragraph is not checked as German
    assert sorted(n.rsplit(": ", 1)[1] for n in notes) == [
        "missing German text", "missing German text", "not stamped"
    ]  # fmt: skip
    assert len(tree.check(require_de=True)[0]) == 3


def test_a_german_string_without_english_twin_is_an_orphan_problem(tree):
    tree.edit("sections.1.paragraphs", lambda ps: [*ps, "Übersetzt: Geist"], german=True)
    assert any("sections.1.paragraphs.1" in p and "orphan" in p for p in tree.check()[0])
    (tree.root / "narratives" / "de" / "lisbon.yaml").write_text("city_id: lisbon\n")
    assert any("lisbon.yaml" in p and "no English" in p for p in tree.check()[0])


def test_data_reference_labels_are_not_translatable(tree):
    """A data reference's label comes only from the English file (spec §4.4): walk yields no
    data_refs path, so no German label is asked for, merged or stamped."""
    en = tr.load_english(tree.en)
    assert en.data_refs  # the fixture narrative has a data reference
    assert not [p for p, _ in tr.walk(en) if p.startswith("data_refs")]
    german = tr.load_translation(tree.de, en)
    merged, _fallback = tr.merge(en, german)
    assert merged.data_refs == en.data_refs


def test_a_german_data_refs_copy_is_a_problem(tree):
    """A German file that still carries data_refs is reported, so a stale copy can't linger."""
    doc = tr.yaml.safe_load(tree.de.read_text(encoding="utf-8"))
    doc["data_refs"] = {"r1": {"text": "Bericht"}}
    tr.dump(tree.de, doc)
    problems = tree.check()[0]
    assert any(p.startswith("[de] ") and "berlin.yaml" in p and "data_refs" in p for p in problems)


def test_german_content_rules_run_on_the_german_text(tree):
    tree.edit("sections.0.paragraphs.0", lambda s: s + " Es wurde 2 km gebaut.", german=True)
    problems = tree.check()[0]
    assert any(p.startswith("[de] ") and "construction verb 'gebaut'" in p for p in problems)
    assert any(p.startswith("[de] ") and "undeclared number 2" in p for p in problems)


def test_gloss_de_is_required_only_when_german_is_required(tree):
    # SOURCES' excerpt is German: no gloss_de needed even when required
    assert tree.check(require_de=True)[0] == []
    src = tree.root / "sources" / "all.yaml"
    tr.edit_path(src, "sources.0.language", lambda _: "pl")
    assert not any("gloss_de" in p for p in tree.check(require_de=False)[0])
    assert any("gloss_de" in p for p in tree.check(require_de=True)[0])


def test_gloss_de_is_not_a_model_rule():
    from tests.conftest import make_source

    make_source("pl")  # a synthetic Source without gloss_de stays valid


def test_require_de_defaults_to_the_shipped_tree_rule(tree, monkeypatch):
    from velometer import i18n

    tree.de.unlink()
    monkeypatch.setattr(i18n, "GERMAN_CONTENT_REQUIRED", True)
    problems, _ = ck.check_content_all(tree.root, tree.data, tree.tmp, history=lambda p: [])
    assert problems == []  # a tmp tree is never the shipped one
    monkeypatch.setattr(i18n, "SHIPPED_CONTENT_DIR", tree.root)
    problems, _ = ck.check_content_all(tree.root, tree.data, tree.tmp, history=lambda p: [])
    assert any("missing" in p for p in problems)


def test_stamp_writes_hashes_only_for_the_given_file(tree):
    other = tree.root / "narratives" / "de" / "paris.yaml"
    before = other.read_bytes()
    tree.edit("title", lambda s: s + " x")
    tr.stamp(tree.de, tr.load_english(tree.en))
    assert other.read_bytes() == before
    assert not any("stale" in p for p in tree.check()[0])


def test_english_problems_keep_their_exact_text(tree):
    (tree.root / "narratives" / "paris.yaml").unlink()
    problems, _ = tree.check()
    assert "narratives/paris.yaml: missing narrative: paris" in problems


def test_merge_gives_german_text_and_the_fallback_paths(tree):
    fake_translate(tree.en, tree.de, drop=frozenset({"sections.0.paragraphs.0"}))
    en = tr.load_english(tree.en)
    merged, fallback = tr.merge(en, tr.load_translation(tree.de, en))
    assert merged.title == "Übersetzt: Berlin"
    assert merged.sections[0].paragraphs[0] == en.sections[0].paragraphs[0]
    assert fallback == frozenset({"sections.0.paragraphs.0"})
    assert merged.facts == en.facts and merged.quotes == en.quotes


def test_loader_by_language(tree):
    from velometer.content.loader import load_document, load_narratives

    fake_translate(tree.en, tree.de, drop=frozenset({"dek"}))
    assert load_narratives(tree.root / "narratives")["berlin"].title == "Berlin"
    narratives, fallback = load_narratives(tree.root / "narratives", lang="de")
    assert narratives["berlin"].title == "Übersetzt: Berlin"
    assert fallback["berlin"] == frozenset({"dek"}) and fallback["paris"] == frozenset()
    (tree.root / "narratives" / "de" / "paris.yaml").unlink()
    _, fallback = load_narratives(tree.root / "narratives", lang="de")
    assert "title" in fallback["paris"]
    doc, fb = load_document(tree.root / "explainer.yaml", lang="de")
    assert doc.title == "Übersetzt: Explainer" and fb == {"explainer": frozenset()}


def test_dump_folds_long_strings_and_round_trips(tmp_path):
    long = "Ein sehr langer Satz, der weit über achtzig Zeichen hinausgeht, damit er gefaltet wird."
    doc = {"z": {"text": long, "src": "0" * 12}, "a": "kurz"}
    path = tmp_path / "x.yaml"
    tr.dump(path, doc)
    text = path.read_text(encoding="utf-8")
    assert "text: >" in text and text.index("z:") < text.index("a:")
    assert tr.yaml.safe_load(text) == doc


def test_git_history_reads_earlier_versions_newest_first(tmp_path):
    def git(*args):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
            cwd=tmp_path, check=True, capture_output=True,
        )  # fmt: skip

    git("init", "-q")
    f = tmp_path / "sub" / "a.yaml"
    f.parent.mkdir()
    for text in ("one\n", "two\n"):
        f.write_text(text)
        git("add", "sub/a.yaml")
        git("commit", "-q", "-m", text.strip())
    assert tr.git_history(f) == ["two\n", "one\n"]
    assert tr.git_history(tmp_path.parent / "elsewhere.yaml") == []


def test_old_english_finds_the_version_that_was_translated():
    v1 = "title: Old title\n"
    v2 = "title: Newer title\n"
    assert tr.old_english([v2, v1], "title", tr.src_hash("Old title")) == "Old title"
    assert tr.old_english([v2, v1], "title", tr.src_hash("Never")) is None


def test_a_sentence_final_english_decimal_is_reported_once():
    found = ck.undeclared_numbers("Der Wert lag bei 78.2.", {"78", "78.2"}, (), lang="de")
    assert found == ["78.2"]
    # a numeric date and German thousands are not English decimals (the date's day is reported
    # by the plain number rule)
    p = "Am 21.03.2026 lagen 2.500 km vor."
    assert ck.undeclared_numbers(p, {"2500"}, (), lang="de") == ["21"]


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_a_blank_german_text_is_missing_and_falls_back(tree, blank):
    tree.edit("dek", lambda s: blank, german=True)
    problems, notes = tree.check(require_de=False)
    assert problems == [] and any("dek: missing German text" in n for n in notes)
    assert any("dek: missing German text" in p for p in tree.check(require_de=True)[0])
    en = tr.load_english(tree.en)
    merged, fallback = tr.merge(en, tr.load_translation(tree.de, en))
    assert merged.dek == en.dek and "dek" in fallback


def test_a_merge_the_english_model_rejects_is_a_problem_not_a_traceback(tree, monkeypatch):
    from velometer.content.models import Narrative

    real = Narrative.model_validate.__func__

    def strict(cls, doc, *a, **k):
        if str(doc.get("title", "")).startswith("Übersetzt"):
            raise ValueError("a text rule")
        return real(cls, doc, *a, **k)

    monkeypatch.setattr(Narrative, "model_validate", classmethod(strict))
    from velometer.content.loader import load_narratives

    errors: dict[str, str] = {}
    narratives, fallback = load_narratives(tree.root / "narratives", errors, lang="de")
    assert "a text rule" in errors["de/berlin"] and narratives["berlin"].title == "Berlin"
    assert "title" in fallback["berlin"]
    problems = tree.check()[0]
    assert any(
        p.startswith("[de] narratives/de/berlin.yaml: ") and "a text rule" in p for p in problems
    )


# --- the M8 fixture tree: organisations, the explainer and the counter page ---------------


@pytest.fixture
def m8(tmp_path):
    import shutil
    from pathlib import Path
    from types import SimpleNamespace

    root = tmp_path / "m8"
    shutil.copytree(Path(__file__).parent / "fixtures" / "content_m8", root)
    content, config = root / "content", root / "config"
    english = [*content.glob("narratives/*.yaml"), *content.glob("organisations/*.yaml"),
               content / "explainer.yaml", content / "counters.yaml",
               content / "plans" / "berlin.yaml"]  # fmt: skip
    for en in english:
        if en.is_file():
            fake_translate(en, tr.twin_path(en))

    def german(require_de=True):
        problems, notes = ck._check_german(
            content, SimpleNamespace(config_dir=config), require_de=require_de,
            history=lambda p: [],
        )  # fmt: skip
        return [p for p in problems if "gloss_de" not in p], notes

    return content, config, german


def test_an_organisation_twin_is_checked_end_to_end(m8):
    content, _config, german = m8
    assert german() == ([], [])
    de = content / "organisations" / "de" / "senmvku.yaml"
    raw = tr.yaml.safe_load(de.read_text(encoding="utf-8"))
    assert raw["sections"][1]["dimensions"]["length"]["text"] == ck.NOT_STATED_DE
    tr.edit_path(de, "sections.1.dimensions.length", lambda s: "nicht angegeben")
    assert any(
        "organisations/de/senmvku.yaml sections.1.dimensions.length" in p and ck.NOT_STATED_DE in p
        for p in german()[0]
    )
    tr.edit_path(de, "sections.1.dimensions", lambda d: {k: v for k, v in d.items() if k != "area"})
    problems, notes = german(require_de=False)
    assert any("sections.1.dimensions.area: missing German text" in n for n in notes)


def test_the_explainer_intro_count_must_match(m8):
    content, _config, german = m8
    tr.edit_path(content / "de" / "explainer.yaml", "intro", lambda ps: ps + ["Übersetzt: mehr"])
    assert any("[de] de/explainer.yaml intro: paragraph count" in p for p in german()[0])


def test_the_counter_page_index_rule_runs_on_the_german_text(m8):
    content, config, german = m8
    rules, _ = ck.counter_rule_values(config)
    sites = next(int(v) for v, fact in rules.items() if fact == "counter.min_sites")
    de = content / "de" / "counters.yaml"
    tr.edit_path(de, "sections.0.paragraphs.0", lambda s: s + f" Es braucht {sites} Zählstellen.")
    assert any(
        p.startswith("[de] de/counters.yaml: index rule stated as literal text: ")
        for p in german()[0]
    )
