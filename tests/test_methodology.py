import re
import sqlite3
from contextlib import closing
from importlib import resources
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.report_fixture import CLASSIFIER
from velometer.cli import app
from velometer.config import ConfigError, default_config_dir, load_classifier, load_trust
from velometer.report.data import ReportData, open_readonly
from velometer.report.methodology import (
    FILES,
    Limitation,
    _number,
    check,
    load_limitations,
    methodology_facts,
    render,
    write,
)

LANGS = ("en", "de")
SPEC_LIMITATIONS = [
    "mapped_km",
    "population_2024",
    "fua_no_per_100k",
    "no_width_surface",
    "classifier_gaps_excluded",
    "published_scope",
    "dirty_provenance_m3",
    "history_vs_current_date",
    "trust_gate",
    "population_national_statistics",
    "qecio_nuts3_not_city",
]
M5_LIMITATIONS = ["trust_gate", "population_national_statistics", "qecio_nuts3_not_city"]


@pytest.fixture
def facts(fixture_db):
    return methodology_facts(fixture_db[3])


def _timestamps(facts) -> set[str]:
    out = set()
    for c in facts.cities:
        for k in c.kinds:
            if k.current_osm_timestamp:
                out.add(k.current_osm_timestamp)
            out.update(k.history_osm_timestamps)
    return out


def test_both_languages_list_classifier_version_and_every_city_timestamp(facts):
    stamps = _timestamps(facts)
    # the fixture: berlin lau/fua current runs, and history 2024-2026 for berlin and paris
    assert "2026-09-30T00:00:00Z" in stamps
    assert {f"{y}-01-01T00:00:00Z" for y in (2024, 2025, 2026)} <= stamps
    assert facts.classifier_version == CLASSIFIER
    for lang in LANGS:
        text = render(facts, lang)
        assert re.search(rf"\b{CLASSIFIER}\b", text)
        for c in facts.cities:
            assert c.name in text
            for k in c.kinds:
                row = next(
                    line
                    for line in text.splitlines()
                    if line.startswith(f"| {c.name} | `{k.kind}` |")
                )
                for ts in [k.current_osm_timestamp, *k.history_osm_timestamps]:
                    if ts:
                        assert ts in row, (lang, c.id, k.kind, ts)


def test_facts_per_city_kind(facts):
    by = {(c.id, k.kind): k for c in facts.cities for k in c.kinds}
    assert by[("berlin", "lau")].population_value == 100000
    assert by[("berlin", "lau")].population_year == 2024
    assert by[("berlin", "fua")].population_value is None
    assert by[("paris", "lau")].current_osm_timestamp is None
    assert by[("paris", "lau")].history_osm_timestamps == [
        "2024-01-01T00:00:00Z",
        "2025-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]
    assert by[("paris", "lau")].population_value == 100000  # from the history runs
    assert by[("paris", "fua")].history_set is None
    assert by[("berlin", "lau")].history_set
    assert facts.snapshot_dates == ["2024-01-01", "2025-01-01", "2026-01-01"]
    assert facts.flag_thresholds["tag_drift_min_km"] == 5
    assert [p.id for p in facts.presets] == ["ours_headline", "ecf_qecio", "clean_cities_2025"]
    assert facts.presets[0].numerator == "A+B"
    assert facts.presets[0].denominator == "main_excl_motorway"


def test_check_passes_after_write_and_fails_after_hand_edit(facts, tmp_path):
    paths = write(tmp_path, facts)
    assert [p.name for p in paths] == ["methodology.md", "methodology.de.md"]
    assert check(tmp_path, facts) == []
    p = tmp_path / "methodology.de.md"
    p.write_text(p.read_text().replace("v2", "v9", 1))
    problems = check(tmp_path, facts)
    assert any("methodology.de.md" in m for m in problems)
    assert not any("methodology.md " in m or m.startswith("methodology.md") for m in problems)


def test_check_reports_a_missing_file(facts, tmp_path):
    write(tmp_path, facts)
    (tmp_path / "methodology.md").unlink()
    problems = check(tmp_path, facts)
    assert len(problems) == 1 and "methodology.md" in problems[0] and "missing" in problems[0]


def test_check_fails_when_a_generated_fact_changes(facts, tmp_path):
    write(tmp_path, facts)
    changed = facts.model_copy(
        update={"flag_thresholds": {**facts.flag_thresholds, "km_jump_min_km": 30.0}}
    )
    problems = check(tmp_path, changed)
    assert any("methodology.md" in m for m in problems)
    assert any("methodology.de.md" in m for m in problems)


def test_check_reports_a_limitation_without_a_language(facts, tmp_path):
    write(tmp_path, facts)
    bad = Limitation.model_construct(id="mapped_km", en="Mapped km.", de="  ")
    problems = check(tmp_path, facts.model_copy(update={"limitations": [bad]}))
    assert any("mapped_km" in m and "de" in m for m in problems)


def test_limitation_missing_a_language_fails_load(tmp_path):
    p = tmp_path / "limitations.yaml"
    p.write_text(yaml.safe_dump({"limitations": [{"id": "x", "en": "Only English."}]}))
    with pytest.raises(ConfigError, match="limitations.yaml"):
        load_limitations(p)
    p.write_text(yaml.safe_dump({"limitations": [{"id": "x", "en": "English.", "de": " "}]}))
    with pytest.raises(ConfigError):
        load_limitations(p)
    p.write_text(yaml.safe_dump({"limitations": [{"id": "x", "en": "English.", "de": "Deutsch."}]}))
    assert load_limitations(p)[0].de == "Deutsch."


def test_limitations_yaml_covers_the_spec_list():
    lims = load_limitations(default_config_dir() / "limitations.yaml")
    assert [x.id for x in lims] == SPEC_LIMITATIONS


def test_limitations_render_in_the_language_of_the_file(facts):
    en, de = render(facts, "en"), render(facts, "de")
    for lim in facts.limitations:
        assert lim.en in en and lim.en not in de
        assert lim.de in de and lim.de not in en


def test_rules_table_lists_every_rule_of_the_report_classifier(facts, fixture_db):
    cfg = fixture_db[1]
    rules = load_classifier(cfg / "classifier" / f"{CLASSIFIER}.yaml").rules
    assert [r.id for r in facts.rules] == [r.id for r in rules]
    for lang in LANGS:
        text = render(facts, lang)
        for r in rules:
            assert re.search(rf"^\| `{r.id}` \| `{r.tier}` \|", text, re.M), (lang, r.id)


def test_rules_follow_report_yaml(fixture_db):
    _, cfg, conn, _ = fixture_db
    report = cfg / "report.yaml"
    report.write_text(
        report.read_text().replace(f"report_classifier: {CLASSIFIER}", "report_classifier: v1")
    )
    facts = methodology_facts(ReportData(conn, cfg))
    v1 = load_classifier(cfg / "classifier" / "v1.yaml")
    assert facts.classifier_version == "v1"
    assert [r.id for r in facts.rules] == [r.id for r in v1.rules]


def test_files_open_with_generated_notice_and_link_the_other_language(facts):
    en, de = render(facts, "en"), render(facts, "de")
    assert "velometer report methodology" in en.splitlines()[0]
    assert "(methodology.de.md)" in en.splitlines()[0]
    assert "velometer report methodology" in de.splitlines()[0]
    assert "(methodology.md)" in de.splitlines()[0]
    assert FILES == {"en": "methodology.md", "de": "methodology.de.md"}


def test_generated_sections_are_wrapped_in_markers(facts):
    names = ["classifier", "rules", "presets", "cities", "snapshots", "flags", "limitations"]
    for lang in LANGS:
        text = render(facts, lang)
        for n in names:
            start, end = f"<!-- generated:{n} -->", f"<!-- /generated:{n} -->"
            assert text.count(start) == 1 and text.count(end) == 1, (lang, n)
            assert text.index(start) < text.index(end)


def test_numbers_use_the_language_convention(facts):
    assert "100,000" in render(facts, "en")
    assert "100.000" in render(facts, "de")
    assert "0,5" in render(facts, "de")  # single_mapper_share


def test_templates_load_through_the_package():
    root = resources.files("velometer.report") / "templates"
    for lang in LANGS:
        assert (root / f"methodology.{lang}.md.j2").is_file()


def _cli(*args):
    return CliRunner().invoke(app, ["report", "methodology", *args])


def test_cli_report_methodology_check_exit_codes(fixture_db, tmp_path):
    db_path, cfg, _, _ = fixture_db
    docs = tmp_path / "docs"
    common = ["--docs", str(docs), "--db", str(db_path), "--config-dir", str(cfg)]
    stale = _cli("--check", *common)
    assert stale.exit_code == 1 and "methodology.md" in stale.output  # not written yet
    res = _cli(*common)
    assert res.exit_code == 0, res.output
    assert (docs / "methodology.md").is_file() and (docs / "methodology.de.md").is_file()
    assert _cli("--check", *common).exit_code == 0
    p = docs / "methodology.de.md"
    p.write_text(p.read_text() + "hand edit\n")
    edited = _cli("--check", *common)
    assert edited.exit_code == 1 and "methodology.de.md" in edited.output
    missing = _cli("--check", "--docs", str(docs), "--db", str(tmp_path / "no.sqlite"))
    assert missing.exit_code == 1


def test_cli_check_fails_when_a_limitation_lacks_a_language(fixture_db, tmp_path):
    db_path, cfg, _, _ = fixture_db
    docs = tmp_path / "docs"
    common = ["--docs", str(docs), "--db", str(db_path), "--config-dir", str(cfg)]
    assert _cli(*common).exit_code == 0
    lim = cfg / "limitations.yaml"
    data = yaml.safe_load(lim.read_text())
    del data["limitations"][0]["de"]
    lim.write_text(yaml.safe_dump(data, allow_unicode=True))
    res = _cli("--check", *common)
    assert res.exit_code == 1 and "limitations.yaml" in res.output


def test_write_writes_each_language_render(facts, tmp_path):
    write(tmp_path / "new", facts)  # creates the directory
    assert Path(tmp_path / "new" / "methodology.md").read_text() == render(facts, "en")
    assert Path(tmp_path / "new" / "methodology.de.md").read_text() == render(facts, "de")


@pytest.mark.parametrize(
    ("value", "lang", "expected"),
    [
        (1.001, "en", "1"),  # rounds to 1.00: no bare "1." left behind
        (1.001, "de", "1"),
        (10.0, "en", "10"),
        (0.5, "de", "0,5"),
        (0.25, "en", "0.25"),
        (100000, "en", "100,000"),
        (1234.5, "de", "1.234,5"),
        (None, "en", ""),
    ],
)
def test_number_has_no_trailing_decimal_point(value, lang, expected):
    assert _number(value, lang) == expected


def test_files_are_utf8_with_unix_newlines(facts, tmp_path):
    write(tmp_path, facts)
    raw = (tmp_path / "methodology.de.md").read_bytes()
    assert b"\r\n" not in raw
    text = raw.decode("utf-8")  # umlauts and sharp s survive as UTF-8
    assert "Straßen" in text and "Prüfhinweise" in text


def test_german_tier_b_names_both_footway_kinds(facts):
    de = render(facts, "de")
    assert "| B | Geh- und Radweg (gemeinsam oder getrennt) |" in de
    assert "(getrennter Geh- und Radweg) hier als Stufe B" in de
    assert "gemeinsamer Geh- und Radweg" not in de  # Zeichen 240 is the unsegregated kind


# --- M5: trust gate, boundary and population sources, NUTS3 caveat ---------------------------


def _facts_of(db_path, cfg):
    with closing(open_readonly(db_path)) as conn:
        return methodology_facts(ReportData(conn, cfg))


def _row(text: str, prefix: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(prefix))


def test_trusted_countries_are_listed_with_their_golden_counts(report_db_with_trust):
    nl = {
        "status": "trusted",
        "basis": "golden sample",
        "basis_de": "Referenzstichprobe",
        "golden": "tests/fixtures/golden/nl",
        "classifier_reviewed": "v2",
        "signed_off": "2026-10-03",
    }
    db, cfg = report_db_with_trust(
        countries={
            "DE": {"status": "trusted", "basis": "Berlin golden set (M1)"},
            "FR": {"status": "pending", "basis": "not yet"},
            "NL": nl,
        }
    )
    golden = cfg.parent / "tests" / "fixtures" / "golden" / "nl.yaml"  # relative to the repo root
    golden.parent.mkdir(parents=True)
    ways = [{"way_id": i, "confirmed": i != 3} for i in (1, 2, 3)]
    golden.write_text(yaml.safe_dump({"status": "signed_off", "ways": ways}))
    facts = _facts_of(db, cfg)
    by = {c.iso2: c for c in facts.countries}
    assert list(by) == ["DE", "NL"]  # trusted only, sorted
    assert (by["NL"].n_golden_confirmed, by["NL"].n_golden) == (2, 3)
    assert (by["DE"].n_golden_confirmed, by["DE"].n_golden) == (0, 0)  # no golden file
    assert by["NL"].classifier_reviewed == "v2" and by["NL"].signed_off == "2026-10-03"
    en, de = render(facts, "en"), render(facts, "de")
    assert _row(en, "| DE |") == "| DE | trusted | Berlin golden set (M1) | – | – | none |"
    assert _row(en, "| NL |") == "| NL | trusted | golden sample | v2 | 2026-10-03 | 2 of 3 |"
    assert _row(de, "| DE |") == "| DE | freigegeben | Berlin golden set (M1) | – | – | keine |"
    assert _row(de, "| NL |") == (
        "| NL | freigegeben | Referenzstichprobe | v2 | 2026-10-03 | 2 von 3 |"
    )  # basis_de in German; DE above has none and falls back to basis
    for text in (en, de):
        assert not any(line.startswith("| FR |") for line in text.splitlines())
        start, end = "<!-- generated:trust -->", "<!-- /generated:trust -->"
        assert text.count(start) == 1 and text.index(start) < text.index("| DE |") < text.index(end)


def test_each_city_lists_its_boundary_and_population_source(fixture_db):
    db_path, cfg, _, _ = fixture_db
    with closing(sqlite3.connect(db_path)) as w, w:
        w.execute(
            "UPDATE boundaries SET source='OSM relation 123', source_version='OSM admin relation' "
            "WHERE city_id='berlin' AND kind='lau'"
        )
        w.execute(
            "UPDATE boundaries SET source='Eurostat GISCO', source_version='LAU 2024 (1:1M)' "
            "WHERE city_id='paris' AND kind='lau'"
        )
        w.execute(
            "UPDATE runs SET population_source='GISCO LAU 2024 POP_2024' WHERE city_id='berlin'"
        )
        w.execute(
            "UPDATE runs SET population_source='Eurostat urb_cpop1 XX001C 2023' "
            "WHERE city_id='paris'"
        )
    facts = _facts_of(db_path, cfg)
    by = {c.id: c for c in facts.cities}
    assert by["berlin"].boundary_source == "OSM relation 123"
    assert by["paris"].boundary_source == "Eurostat GISCO LAU 2024 (1:1M)"
    assert by["berlin"].population_source == "GISCO LAU 2024 POP_2024"
    assert by["paris"].population_source == "Eurostat urb_cpop1 XX001C 2023"
    for lang in LANGS:
        text = render(facts, lang)
        assert "| Berlin | OSM relation 123 | GISCO LAU 2024 POP_2024 |" in text, lang
        assert "| Paris | Eurostat GISCO LAU 2024 (1:1M) | Eurostat urb_cpop1 XX001C 2023 |" in text
        start, end = "<!-- generated:sources -->", "<!-- /generated:sources -->"
        assert text.count(start) == 1
        assert text.index(start) < text.index("| Berlin | OSM relation 123 |") < text.index(end)


def _nuts3_item(text: str, lim) -> str:
    """The rendered list item of the qecio_nuts3_not_city limitation, after the YAML text."""
    line = next(x for x in text.splitlines() if x.startswith(f"- {lim}"))
    return line[len(f"- {lim}") :]


def test_qecio_nuts3_city_list_follows_cities_yaml(fixture_db):
    db_path, cfg, _, data = fixture_db
    facts = methodology_facts(data)  # config/cities.yaml: berlin and paris are their NUTS3 unit
    lim = next(x for x in facts.limitations if x.id == "qecio_nuts3_not_city")
    assert "Paris" not in lim.en + lim.de and "Berlin" not in lim.en + lim.de
    assert _nuts3_item(render(facts, "en"), lim.en) == ""  # no list sentence at all
    assert _nuts3_item(render(facts, "de"), lim.de) == ""
    cities = cfg / "cities.yaml"
    doc = yaml.safe_load(cities.read_text())
    for c in doc["cities"]:
        if c["id"] in ("paris", "berlin"):
            c["nuts3_is_city"] = False
    cities.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    flipped = _facts_of(db_path, cfg)
    assert _nuts3_item(render(flipped, "en"), lim.en) == " This applies to Berlin and Paris."
    assert _nuts3_item(render(flipped, "de"), lim.de) == " Das betrifft Berlin und Paris."
    for c in doc["cities"]:
        if c["id"] == "berlin":
            c["nuts3_is_city"] = True
    cities.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    one = _facts_of(db_path, cfg)
    assert _nuts3_item(render(one, "en"), lim.en) == " This applies to Paris."
    assert _nuts3_item(render(one, "de"), lim.de) == " Das betrifft Paris."


def test_population_override_city_list_follows_cities_yaml(fixture_db):
    """The national-statistics limitation names the cities with a cited population_override in
    cities.yaml, with their source; no city is named in limitations.yaml itself."""
    db_path, cfg, _, data = fixture_db
    facts = methodology_facts(data)  # config/cities.yaml of the fixture: no override
    lim = next(x for x in facts.limitations if x.id == "population_national_statistics")
    for name in ("Paris", "Berlin", "Lyon", "Madrid"):
        assert name not in lim.en + lim.de
    assert _nuts3_item(render(facts, "en"), lim.en) == ""
    assert _nuts3_item(render(facts, "de"), lim.de) == ""
    cities = cfg / "cities.yaml"
    doc = yaml.safe_load(cities.read_text())
    for c in doc["cities"]:
        if c["id"] == "paris":
            c.pop("population_nuts3", None)
            c["population_override"] = {
                "value": 2_100_000,
                "year": 2023,
                "source": "INSEE populations de référence 2023",
                "source_url": "https://www.insee.fr/fr/statistiques/8643952?geo=COM-75056",
            }
    cities.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    with_override = _facts_of(db_path, cfg)
    assert {c.id: c.population_override for c in with_override.cities} == {
        "berlin": None,
        "paris": "INSEE populations de référence 2023",
    }
    expected = "Paris (INSEE populations de référence 2023)."
    assert _nuts3_item(render(with_override, "en"), lim.en) == f" This applies to {expected}"
    assert _nuts3_item(render(with_override, "de"), lim.de) == f" Das betrifft {expected}"


@pytest.mark.parametrize("lim_id", M5_LIMITATIONS)
def test_cli_check_fails_when_a_new_limitation_lacks_german(fixture_db, tmp_path, lim_id):
    db_path, cfg, _, _ = fixture_db
    docs = tmp_path / "docs"
    common = ["--docs", str(docs), "--db", str(db_path), "--config-dir", str(cfg)]
    assert _cli(*common).exit_code == 0
    assert _cli("--check", *common).exit_code == 0
    lim = cfg / "limitations.yaml"
    data = yaml.safe_load(lim.read_text())
    del next(x for x in data["limitations"] if x["id"] == lim_id)["de"]
    lim.write_text(yaml.safe_dump(data, allow_unicode=True))
    res = _cli("--check", *common)
    assert res.exit_code == 1 and "limitations.yaml" in res.output


def test_committed_trusted_countries_have_a_german_basis():
    trust = load_trust(default_config_dir() / "trust.yaml")
    trusted = {cc: t for cc, t in trust.countries.items() if t.status == "trusted"}
    assert trusted and all(t.basis_de for t in trusted.values())


TRUST_CHECK_CONDITIONS = {
    # each failure condition of `velometer trust check` (cli.trust_check, trust.py)
    "en": [
        "still the placeholder 1.0",  # placeholder_problems
        "has no diagnostics file",  # missing <cc>.json
        "leave out one of its cities",  # a configured city missing from <cc>.json
        "no longer the city's current LAU run",  # stale_problems
        "without a note in the country's review file",  # breach_problems
        "unconfirmed",  # golden_problems
        "no longer match the report classifier",  # golden_problems
        "reviewed on a classifier other than the report classifier",  # classifier_reviewed
    ],
    "de": [
        "noch auf dem Platzhalter 1,0",
        "keine Diagnosedatei",
        "eine seiner Städte auslässt",
        "nicht mehr der aktuelle LAU-Lauf",
        "ohne Begründung in der Prüfdatei",
        "unbestätigt",
        "anders einstuft",
        "mit einem anderen Klassifikator geprüft",
    ],
}


@pytest.mark.parametrize("lang", LANGS)
def test_trust_check_conditions_are_all_described(facts, lang):
    text = render(facts, lang)
    section = text[text.index("velometer trust check") : text.index("<!-- generated:trust -->")]
    for phrase in TRUST_CHECK_CONDITIONS[lang]:
        assert phrase in section, (lang, phrase)
    # classifier_reviewed is checked for every trusted country, not only golden-sample ones
    (line,) = [x for x in section.splitlines() if TRUST_CHECK_CONDITIONS[lang][-1] in x]
    assert "golden" not in line and "Referenzstichprobe" not in line, line
    assert "drei Fällen" not in section


TEMPLATES = resources.files("velometer.report") / "templates"
PUBLISHED_SOURCES = {
    "en": [TEMPLATES / "methodology.en.md.j2"],
    "de": [TEMPLATES / "methodology.de.md.j2"],
}


def _published(lang: str) -> str:
    """The hand-written text of the published methodology in `lang`: its template plus the
    limitations in that language."""
    lims = yaml.safe_load((default_config_dir() / "limitations.yaml").read_text())["limitations"]
    parts = [p.read_text() for p in PUBLISHED_SOURCES[lang]]
    return "\n".join(parts + [x[lang] for x in lims])


@pytest.mark.parametrize("lang", LANGS)
def test_published_text_cites_no_task_id_and_no_superseded_decision(lang):
    text = _published(lang)
    assert not re.search(r"\bTask \d+[a-z]?\b", text)  # internal ids mean nothing to a reader
    # spec decision 9 (urb_cpop1) was superseded by the user decision of 2026-10-03
    assert not re.search(r"(decision|Entscheidung) 9\b", text)


def test_the_urban_audit_fallback_is_described_as_unused_and_is_unused():
    from velometer.config import load_cities

    cities = load_cities(default_config_dir() / "cities.yaml")
    assert not any(c.population_urau for c in cities)
    for lang, unused in (("en", "no configured city uses it"), ("de", "keine konfigurierte Stadt")):
        text = _published(lang)
        (para,) = [p for p in text.split("\n\n") if "urb_cpop1" in p]
        assert unused in para, (lang, para)


GERMAN_SLIPS = {
    # wrong or awkward German in published text, with the fix
    "den keine Regel erkennt": "die keine Regel erkennt (the km, not the share, go unrecognised)",
    "je neuem Land": "für jedes neue Land",
    "Ihre Vergleichszeilen": "Die QECIO-Vergleichszeilen der Stadt (unclear antecedent)",
}


def test_published_german_has_none_of_the_known_slips():
    text = _published("de")
    for slip, fix in GERMAN_SLIPS.items():
        assert slip not in text, f"{slip!r}: use {fix!r}"


def test_english_qecio_rows_name_their_city():
    assert "Its comparison rows" not in _published("en")
    assert "The city's QECIO comparison rows" in _published("en")


def test_the_english_qecio_note_is_glossed_in_german():
    text = _published("de")
    for para in text.split("\n"):
        if "NUTS3 unit is not the city" in para:
            assert "(NUTS-3-Einheit ist nicht die Stadt)" in para, para


@pytest.mark.parametrize("lang", LANGS)
def test_trust_gate_bullets_are_parallel(lang):
    # each check before trust is a bold term with a full stop, then sentences
    text = _published(lang)
    section = text[text.index("## Country trust gate" if lang == "en" else "## Freigabe je Land") :]
    bullets = section.split("\n\n")[2].splitlines()
    assert len(bullets) == 2
    for b in bullets:
        assert re.match(r"- \*\*[^*]+\.\*\* [A-ZÄÖÜ]", b), b
