import re
from importlib import resources
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from velometer.cli import app
from velometer.config import ConfigError, default_config_dir, load_classifier
from velometer.report.data import ReportData
from velometer.report.methodology import (
    FILES,
    Limitation,
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
]


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
    assert facts.classifier_version == "v2"
    for lang in LANGS:
        text = render(facts, lang)
        assert re.search(r"\bv2\b", text)
        for c in facts.cities:
            assert c.name in text
            for k in c.kinds:
                row = next(
                    line for line in text.splitlines() if line.startswith(f"| {c.name} | {k.kind}")
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
    rules = load_classifier(cfg / "classifier" / "v2.yaml").rules
    assert [r.id for r in facts.rules] == [r.id for r in rules]
    for lang in LANGS:
        text = render(facts, lang)
        for r in rules:
            assert re.search(rf"^\| `{r.id}` \| {r.tier} \|", text, re.M), (lang, r.id)


def test_rules_follow_report_yaml(fixture_db):
    _, cfg, conn, _ = fixture_db
    report = cfg / "report.yaml"
    report.write_text(report.read_text().replace("report_classifier: v2", "report_classifier: v1"))
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
