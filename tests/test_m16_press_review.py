"""M16 Task 3: the press-law candidate sentences (`tools/press_review.py`), on a fixture."""

from pathlib import Path

from tests.helpers import ROOT, load_script

pr = load_script("tools/press_review.py")

FIXTURE = ROOT / "tests" / "fixtures" / "press" / "sample.yaml"
PERSONS = ("Erika Mustermann",)


def found(paths=(FIXTURE,), persons=PERSONS) -> dict[str, tuple[str, ...]]:
    return {c.sentence: c.reasons for c in pr.candidates(list(paths), persons=persons)}


def test_an_administration_that_rolled_back_is_named_and_causal():
    got = found()["Die Senatsverwaltung hat Radwege zurückgebaut."]
    assert set(got) == {"names-administration", "causal-claim"}


def test_an_organisation_judged_not_reproducible():
    got = found()["Clean Cities is not reproducible."]
    assert set(got) == {"names-organisation", "judgement"}


def test_a_neutral_sentence_is_no_candidate():
    assert "The tiers do not consider width or surface." not in found()


def test_a_person_a_party_and_a_cause():
    got = found()["Erika Mustermann (SPD) opened the lane because the census asked for it."]
    assert set(got) == {"names-person", "names-party", "causal-claim"}


def test_a_person_is_only_found_when_listed():
    got = found(persons=())
    assert (
        "names-person"
        not in got["Erika Mustermann (SPD) opened the lane because the census asked for it."]
    )


def test_organisation_names_come_from_the_profiled_organisations():
    # "Changing Cities e.V." and "Mobilitätsagentur Wien" are not spelled out in the tool: they
    # are config/organisations.yaml ids with names in content/organisations/
    assert found()["Changing Cities e.V. counts km per street."] == ("names-organisation",)
    names = pr.load_names()
    assert names["Mobilitätsagentur Wien"] == "names-administration"
    assert names["Changing Cities"] == "names-organisation"


def test_a_judgement_next_to_a_named_actor_is_a_candidate_a_lone_cause_is_not():
    got = found()
    assert set(got["That figure is misleading."]) == {"judgement"}
    assert "The fall came because mappers redrew ways." not in got


def test_sentences_split_without_breaking_abbreviations_or_german_dates():
    s = "Fahrradstraßen o. Ä. kamen am 2. Oktober hinzu, sagt die Mobilitätsagentur Wien."
    assert found()[s] == ("names-administration",)
    text = (
        "Not the city's. Ein Satz. Siehe z. B. Wien. Am 2. Oktober kam es. E.g. this one. "
        "Nr. 4 folgt."
    )
    assert pr.split_sentences(text) == [
        "Not the city's.",
        "Ein Satz.",
        "Siehe z. B. Wien.",
        "Am 2. Oktober kam es.",
        "E.g. this one.",
        "Nr. 4 folgt.",
    ]


def test_language_key_and_file_of_a_candidate():
    by = {c.sentence: c for c in pr.candidates([FIXTURE], persons=PERSONS)}
    de = by["Die Senatsverwaltung hat Radwege zurückgebaut."]
    assert (de.lang, de.key) == ("de", "sections.0.paragraphs_de.0")
    assert by["Clean Cities is not reproducible."].lang == "en"
    assert de.file == "tests/fixtures/press/sample.yaml"


def test_facts_and_other_non_prose_keys_are_skipped():
    assert not any("wrong" in s for s in found())


def test_german_twin_files_and_keys_are_detected(tmp_path):
    (tmp_path / "de").mkdir()
    en, de = tmp_path / "x.yaml", tmp_path / "de" / "x.yaml"
    en.write_text("sections:\n  - paragraphs:\n      - The Senate cut lanes.\n", encoding="utf-8")
    de.write_text(
        "sections:\n- paragraphs:\n  - text: Der Senat hat Radwege gestrichen.\n    src: abc\n",
        encoding="utf-8",
    )
    got = pr.candidates([de, en], persons=())
    assert [(c.lang, c.key) for c in got] == [
        ("en", "sections.0.paragraphs.0"),
        ("de", "sections.0.paragraphs.0"),
    ]  # twins adjacent, English first, `.text` dropped from the German key


def test_cli_writes_the_candidate_table(tmp_path):
    out = tmp_path / "press.md"
    assert pr.main(["--out", str(out), str(FIXTURE)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "Clean Cities is not reproducible." in text
    assert "width or surface" not in text
    assert text.count("| open |") == len(pr.candidates([FIXTURE]))


def test_the_default_sources_reach_both_editions_and_config_prose():
    paths = pr.default_paths()
    rel = {Path(p).relative_to(ROOT).as_posix() for p in paths}
    assert "content/narratives/berlin.yaml" in rel
    assert "content/narratives/de/berlin.yaml" in rel
    assert "content/ui/de.yaml" in rel
    assert "config" in rel  # the config dir: its reader prose (velometer.config.reader_prose)
    assert "config/limitations.yaml" in rel
    assert not any(r.startswith("content/sources/") for r in rel)  # quotations, see the doc


def test_an_osm_tag_is_not_a_word(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text(
        "p:\n  - Way 1 went from railway=abandoned to highway=cycleway.\n"
        "  - Die ersten sieben halten dieselben Plätze.\n",
        encoding="utf-8",
    )
    assert pr.candidates([path], persons=()) == []


def test_a_coalition_by_colour_and_an_office_holder():
    got = pr.reasons(
        "The red-green city government created it, and the city's cycling commissioner led it."
    )
    assert {"names-party", "names-person"} <= set(got)
    got = pr.reasons(
        "Die rot-grüne Stadtregierung gründete sie; der Radverkehrsbeauftragte leitete sie."
    )
    assert {"names-party", "names-person"} <= set(got)


def test_cli_never_overwrites_an_existing_file_without_force(tmp_path, capsys):
    out = tmp_path / "m16-press.md"
    out.write_bytes(b"# reviewed table\n| 1 | ... | reviewed |\n")
    before = out.read_bytes()
    assert pr.main(["--out", str(out), str(FIXTURE)]) == 2
    assert out.read_bytes() == before
    assert "--force" in capsys.readouterr().err
    assert pr.main(["--out", str(out), "--force", str(FIXTURE)]) == 0
    assert "Clean Cities is not reproducible." in out.read_text(encoding="utf-8")
