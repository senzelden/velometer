"""M8 content: organisation profiles, plan and counter pages, coverage, and the new fact families
(spec §3.4, §4.5, §5.5). Each rule is checked by breaking one fixture file."""

import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from velometer.cli import app
from velometer.content.check import (
    causal_counter_wording,
    check_content_offline,
    misplaced_quotes,
)
from velometer.content.facts import FAMILIES, FactError, evaluate
from velometer.content.loader import (
    load_document,
    load_explainer,
    load_organisation_map,
    load_organisations,
    load_sources,
)
from velometer.content.models import ContentError, Explainer
from velometer.db import CounterIndexYear, OverlayRow, replace_counter_index, replace_plan_overlay

FIXTURE = Path(__file__).parent / "fixtures" / "content_m8"


@pytest.fixture
def m8(tmp_path) -> tuple[Path, Path]:
    """Writable copies of the M8 fixture (content dir, config dir)."""
    shutil.copytree(FIXTURE, tmp_path / "m8")
    return tmp_path / "m8" / "content", tmp_path / "m8" / "config"


def _problems(m8) -> list[str]:
    return check_content_offline(*m8)


def _edit(path: Path, mutate: Callable[[dict], None]) -> None:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _senmvku(m8) -> Path:
    return m8[0] / "organisations" / "senmvku.yaml"


# --- loaders -------------------------------------------------------------------------------


def test_the_fixture_is_clean(m8):
    assert _problems(m8) == []


def test_loaders_read_the_fixture(m8):
    content, config = m8
    orgs = load_organisations(content / "organisations")
    assert sorted(orgs) == ["abgeordnetenhaus", "senmvku"]
    dims = orgs["senmvku"].sections[1].dimensions
    assert dims["scope"] == "the planned network [@src]"
    assert dims["length"] == "not stated by the source"
    assert load_sources(content / "sources")["study"].kind == "research"
    assert load_document(content / "counters.yaml").title == "Bike counters"
    assert load_document(content / "absent.yaml") is None
    assert load_explainer is load_document
    assert [m.city for m in load_organisation_map(config / "organisations.yaml")][:2] == [
        "berlin",
        "*",
    ]


def test_profile_stem_must_equal_id_and_errors_are_collected(m8):
    path = _senmvku(m8)
    _edit(path, lambda d: d.__setitem__("id", "other"))
    with pytest.raises(ContentError, match="file stem must equal id"):
        load_organisations(path.parent)
    errors: dict[str, str] = {}
    assert sorted(load_organisations(path.parent, errors=errors)) == ["abgeordnetenhaus"]
    assert list(errors) == ["senmvku"]


def test_an_internal_profile_url_is_refused(m8):
    _edit(_senmvku(m8), lambda d: d.__setitem__("url", "http://127.0.0.1:8000/"))
    [problem] = [p for p in _problems(m8) if "external http(s) URL" in p]
    assert "organisation url must be" in problem and "source url" not in problem, problem


def test_an_internal_archive_url_is_named_as_the_archive_url():
    # M8-20: the archive_url error said "source url"
    from pydantic import ValidationError

    from velometer.content.models import Source

    base = {"id": "s", "publisher": "P", "title": "T", "url": "https://example.org/",
            "accessed": "2026-01-01", "language": "en", "kind": "press"}  # fmt: skip
    with pytest.raises(ValidationError, match="source archive_url must be an external") as e:
        Source(**base, archive_url="http://127.0.0.1/x")
    assert "source url must" not in str(e.value)
    with pytest.raises(ValidationError, match="source url must be an external"):
        Source(**(base | {"url": "http://localhost/"}))


# --- profile document rules ----------------------------------------------------------------


def test_profile_citing_an_unknown_source(m8):
    _edit(
        _senmvku(m8),
        lambda d: d["sections"][0]["paragraphs"].__setitem__(
            0, d["sections"][0]["paragraphs"][0] + " See [@nope]."
        ),
    )
    assert _problems(m8) == ["organisations/senmvku.yaml: unknown source nope"]


def test_profile_quote_that_does_not_match_an_excerpt(m8):
    _edit(_senmvku(m8), lambda d: d["quotes"].__setitem__(0, {"excerpt": "src/e9", "after": 0}))
    assert _problems(m8) == ["organisations/senmvku.yaml: unknown excerpt src/e9"]


def test_undeclared_number_in_a_profile(m8):
    _edit(_senmvku(m8), lambda d: d["sections"][1]["paragraphs"].__setitem__(0, "It is 9.4 km."))
    assert _problems(m8) == ["organisations/senmvku.yaml: undeclared number 9.4"]


def test_numbers_in_dimension_values_are_checked(m8):
    _edit(
        _senmvku(m8),
        lambda d: d["sections"][1]["dimensions"].__setitem__("date", "as of 31 [@src]"),
    )
    assert _problems(m8) == ["organisations/senmvku.yaml: undeclared number 31"]


def test_unknown_dimension_key_and_http_url(m8):
    def mutate(d):
        d["sections"][1]["dimensions"]["colour"] = "red"
        d["url"] = "http://example.org/senmvku"

    _edit(_senmvku(m8), mutate)
    assert _problems(m8) == [
        "organisations/senmvku.yaml: url is not https: http://example.org/senmvku",
        "organisations/senmvku.yaml: section 'How they measure': unknown dimension colour",
    ]


# --- causal counter wording ----------------------------------------------------------------


def test_causal_counter_wording():
    assert causal_counter_wording("Counts rose because of new lanes") == ["because of"]
    assert causal_counter_wording("Rents rose because of demand") == []
    assert causal_counter_wording("Counters rose because of new lanes") == ["because of"]
    assert causal_counter_wording("The counter shows growth that led to, and was due to, X") == [
        "led to",
        "due to",
    ]
    assert causal_counter_wording("Cyclists recorded rose thanks to the lanes") == ["thanks to"]


def test_the_verb_count_alone_is_not_a_counter_mention():
    # "count" the verb says nothing about counter data; a counter noun beside "due to" does
    assert causal_counter_wording("We count the km, due to the method.") == []
    assert causal_counter_wording("Counted trips drove demand.") == ["drove"]
    assert causal_counter_wording("The counts fell due to works.") == ["due to"]
    assert causal_counter_wording("We count the km at the counter, due to X.") == ["due to"]


def test_causal_wording_in_the_counters_page(m8):
    _edit(
        m8[0] / "counters.yaml",
        lambda d: d["sections"][0]["paragraphs"].__setitem__(0, "Counts rose because of lanes."),
    )
    assert _problems(m8) == ["counters.yaml: causal wording 'because of' about counts"]


def test_causal_wording_in_a_profile(m8):
    _edit(
        _senmvku(m8),
        lambda d: d["sections"][1]["paragraphs"].__setitem__(0, "Counted trips drove demand."),
    )
    assert _problems(m8) == ["organisations/senmvku.yaml: causal wording 'drove' about counts"]


def test_plan_page_follows_the_document_rules(m8):
    _edit(
        m8[0] / "plans" / "berlin.yaml",
        lambda d: d["sections"][0]["paragraphs"].__setitem__(0, "Berlin built 12.5 km [@x]."),
    )
    assert _problems(m8) == [
        "plans/berlin.yaml: unknown source x",
        "plans/berlin.yaml: undeclared number 12.5",
        "plans/berlin.yaml: construction verb 'built'",
    ]


def test_a_quote_follows_the_paragraph_citing_its_source():
    """`after` counts section paragraphs without the intro; an intro quote follows paragraph 0."""
    doc = Explainer.model_validate(
        {
            "title": "t",
            "intro": ["Intro [@a]."],
            "sections": [
                {"dimension": "x", "heading": "X", "paragraphs": ["One [@b].", "Two [@c]."]}
            ],
            "quotes": [
                {"excerpt": "a/e", "after": 0},
                {"excerpt": "b/e", "after": 0},
                {"excerpt": "c/e", "after": 1},
            ],
        }
    )
    assert misplaced_quotes(doc) == []
    late = doc.model_copy(
        update={"quotes": [doc.quotes[0].model_copy(update={"after": 1}), *doc.quotes[1:]]}
    )
    assert misplaced_quotes(late) == [
        "quote a/e follows paragraph 1, which does not cite a (not cited; paragraphs count from 0"
        " without the intro)"
    ]
    shifted = doc.model_copy(update={"quotes": [doc.quotes[1].model_copy(update={"after": 1})]})
    assert misplaced_quotes(shifted) == [
        "quote b/e follows paragraph 1, which does not cite b (cited in paragraph 0; paragraphs"
        " count from 0 without the intro)"
    ]
    wild = doc.model_copy(update={"quotes": [doc.quotes[2].model_copy(update={"after": 2})]})
    assert misplaced_quotes(wild) == ["quote c/e: after=2 must index one of 2"]


def test_plan_and_counter_pages_are_optional(m8):
    (m8[0] / "counters.yaml").unlink()
    shutil.rmtree(m8[0] / "plans")
    assert _problems(m8) == []


def test_a_broken_plan_page_is_one_problem(m8):
    (m8[0] / "counters.yaml").write_text("title: [unclosed\n", encoding="utf-8")
    [problem] = _problems(m8)
    assert "counters.yaml" in problem


# --- coverage -------------------------------------------------------------------------------


def _drop_mapping(config: Path, city: str, source: str) -> None:
    path = config / "organisations.yaml"
    doc = yaml.safe_load(path.read_text())
    doc = [m for m in doc if (m["city"], m["source"]) != (city, source)]
    path.write_text(yaml.safe_dump(doc))


def test_figures_pair_with_no_mapping(m8):
    _drop_mapping(m8[1], "berlin", "official")
    assert _problems(m8) == [
        "config/organisations.yaml: no organisation for figures.csv source berlin/official"
    ]


def test_reconcile_source_with_no_mapping(m8):
    _drop_mapping(m8[1], "*", "parliament_docs")
    assert _problems(m8) == [
        "config/organisations.yaml: no organisation for reconcile source parliament_docs"
    ]


def test_mapping_to_an_organisation_without_profile(m8):
    (m8[0] / "organisations" / "abgeordnetenhaus.yaml").unlink()
    problems = _problems(m8)
    assert (
        "config/organisations.yaml: */parliament_docs maps to abgeordnetenhaus, which has no "
        "profile" in problems
    )
    assert "config/plans/reports.csv:3: publisher abgeordnetenhaus has no profile" in problems


def test_berlin_publishers_must_be_profiles_others_need_not(m8):
    path = m8[1] / "plans" / "plans.yaml"
    path.write_text(path.read_text().replace("publisher: senmvku", "publisher: nobody"))
    # paris_plan_velo's publisher ville_de_paris has no profile and is not a problem
    assert _problems(m8) == [
        "config/plans/plans.yaml: plan berlin_rvp_2021: publisher nobody has no profile"
    ]


def test_coverage_waits_for_the_organisations_directory(m8):
    shutil.rmtree(m8[0] / "organisations")
    (m8[1] / "organisations.yaml").write_text("[]\n")
    assert _problems(m8) == []


# --- plan rules (always on) ------------------------------------------------------------------


def test_report_row_naming_an_unknown_item(m8):
    path = m8[1] / "plans" / "reports.csv"
    path.write_text(path.read_text().replace("paris_plan_velo,total", "paris_plan_velo,nope"))
    assert _problems(m8) == ["config/plans/reports.csv:4: plan paris_plan_velo has no item nope"]


def test_report_row_naming_an_unknown_plan(m8):
    path = m8[1] / "plans" / "reports.csv"
    path.write_text(path.read_text().replace("paris_plan_velo,total", "ghost,total"))
    assert _problems(m8) == ["config/plans/reports.csv:4: unknown plan ghost"]


def test_cumulative_figure_without_start_year(m8):
    path = m8[1] / "plans" / "reports.csv"
    path.write_text(path.read_text().replace(",,2020\n", ",,\n"))
    assert _problems(m8) == ["config/plans/reports.csv:4: cumulative figure without its start year"]


def test_cumulative_start_after_the_year(m8):
    path = m8[1] / "plans" / "reports.csv"
    path.write_text(path.read_text().replace(",,2020\n", ",,2030\n"))
    assert _problems(m8) == ["config/plans/reports.csv:4: cumulative_from 2030 is after year 2024"]


def test_http_plan_url(m8):
    path = m8[1] / "plans" / "plans.yaml"
    path.write_text(path.read_text().replace("https://example.org/rvp", "http://example.org/rvp"))
    assert _problems(m8) == [
        "config/plans/plans.yaml: plan berlin_rvp_2021: url is not https: http://example.org/rvp"
    ]


def test_http_report_url_and_empty_unit(m8):
    path = m8[1] / "plans" / "reports.csv"
    text = path.read_text().replace("https://example.org/paris", "http://example.org/paris")
    path.write_text(text.replace("1.0,km,implemented_cumulative", "1.0, ,implemented_cumulative"))
    assert _problems(m8) == [
        "config/plans/reports.csv:4: url is not https: http://example.org/paris",
        "config/plans/reports.csv:4: no unit",
    ]


def test_empty_item_unit(m8):
    path = m8[1] / "plans" / "plans.yaml"
    path.write_text(path.read_text().replace("target_kind: none}", "target_kind: none, unit: ''}"))
    assert _problems(m8) == [
        "config/plans/plans.yaml: plan paris_plan_velo: item total has no unit"
    ]


def test_duplicate_report_row_is_a_problem(m8):
    path = m8[1] / "plans" / "reports.csv"
    lines = path.read_text().splitlines()
    path.write_text("\n".join([*lines, lines[1].replace("10.8", "10.9")]) + "\n")
    assert _problems(m8) == [
        "config/plans/reports.csv:5: duplicate of line 2 (same figure and document)"
    ]


def test_same_document_from_two_start_years_is_not_a_duplicate(m8):
    path = m8[1] / "plans" / "reports.csv"
    lines = path.read_text().splitlines()
    assert lines[3].endswith(",,2020")
    path.write_text("\n".join([*lines, lines[3].replace(",,2020", ",,2015")]) + "\n")
    assert _problems(m8) == []


def test_start_year_on_a_non_cumulative_quantity(m8):
    path = m8[1] / "plans" / "reports.csv"
    lines = path.read_text().splitlines()
    lines[1] = lines[1] + "2020"
    path.write_text("\n".join(lines) + "\n")
    assert _problems(m8) == [
        "config/plans/reports.csv:2: cumulative_from on a non-cumulative quantity"
    ]


def test_suspect_row_needs_a_note(m8):
    path = m8[1] / "plans" / "reports.csv"
    lines = path.read_text().splitlines()
    lines[1] = lines[1][:-1] + "true,"  # no note on this row
    lines[2] = lines[2][:-1] + "true,"  # has a note
    path.write_text("\n".join(lines) + "\n")
    assert _problems(m8) == ["config/plans/reports.csv:2: suspect row without a note"]


def test_malformed_figures_csv_is_a_problem(m8):
    path = m8[1] / "external" / "figures.csv"
    path.write_text(path.read_text().replace("city_id,source,", "city,source,", 1))
    [problem] = _problems(m8)
    assert problem.startswith("config/external/figures.csv: cannot read")


def test_an_undecodable_figures_csv_is_a_problem_not_a_crash(m8):
    path = m8[1] / "external" / "figures.csv"
    path.write_bytes(path.read_bytes() + "berlin,caf\xe9\n".encode("latin-1"))
    [problem] = _problems(m8)
    assert problem.startswith("config/external/figures.csv: cannot read"), problem


def test_an_undecodable_reconcile_yaml_is_a_problem_not_a_crash(m8):
    path = m8[1] / "reconcile.yaml"
    path.write_bytes(path.read_bytes() + "# caf\xe9\n".encode("latin-1"))
    [problem] = _problems(m8)
    assert problem.startswith("config/reconcile.yaml: cannot read"), problem


def test_an_undecodable_dimension_list_is_a_problem_for_each_reader(m8):
    # the explainer and the profiles read differences.yaml through one function
    path = m8[1] / "differences.yaml"
    path.write_bytes(path.read_bytes() + "# caf\xe9\n".encode("latin-1"))
    problems = _problems(m8)
    assert any(p.startswith("explainer.yaml: cannot read dimensions from") for p in problems)
    assert sum(": cannot read dimensions: " in p for p in problems) == 2, problems  # 2 profiles


def test_malformed_reconcile_yaml_is_a_problem(m8):
    (m8[1] / "reconcile.yaml").write_text("comparisons:\n  - id: x\n")
    [problem] = _problems(m8)
    assert problem.startswith("config/reconcile.yaml: cannot read")


def test_an_unreadable_plan_file_is_one_problem(m8):
    path = m8[1] / "plans" / "reports.csv"
    path.write_text(path.read_text().replace("rote_nummer", "memo"))
    [problem] = _problems(m8)
    assert "reports.csv:2" in problem


# --- facts ----------------------------------------------------------------------------------

PLAN_EXPR = "plan.berlin_rvp_2021.vorrangnetz.2025.implemented_in_year"


def test_new_families_are_listed():
    assert {"overlay", "overlay_change", "plan", "counter", "counter_sites"} <= set(FAMILIES)


def test_plan_fact_current_value_and_named_document(fixture_db, tmp_path):
    data = fixture_db[3]
    cfg = FIXTURE / "config"
    assert evaluate(PLAN_EXPR, data, tmp_path, config_dir=cfg) == 8.6
    assert evaluate(f"{PLAN_EXPR}.TEST_0001", data, tmp_path, config_dir=cfg) == 10.8
    assert evaluate(f"{PLAN_EXPR}.TEST_0002", data, tmp_path, config_dir=cfg) == 8.6


@pytest.mark.parametrize(
    "expr,match",
    [
        (f"{PLAN_EXPR}.TEST_0003", "no document 'TEST_0003'"),
        ("plan.ghost.vorrangnetz.2025.implemented_in_year", "no plan 'ghost'"),
        ("plan.berlin_rvp_2021.nope.2025.implemented_in_year", "has no item 'nope'"),
        ("plan.berlin_rvp_2021.vorrangnetz.2024.implemented_in_year", "no reported"),
        ("plan.berlin_rvp_2021.vorrangnetz.2025.built", "unknown quantity"),
        ("plan.berlin_rvp_2021.vorrangnetz", "expected <plan_id>"),
    ],
)
def test_plan_fact_errors(fixture_db, tmp_path, expr, match):
    with pytest.raises(FactError, match=match):
        evaluate(expr, fixture_db[3], tmp_path, config_dir=FIXTURE / "config")


def test_plan_fact_doc_suffix_matching_two_documents_is_ambiguous(fixture_db, tmp_path):
    cfg = tmp_path / "cfg"
    shutil.copytree(FIXTURE / "config", cfg)
    path = cfg / "plans" / "reports.csv"
    path.write_text(path.read_text().replace("TEST/0001", "TEST_0002"))  # TEST/0002 also maps
    with pytest.raises(FactError, match="ambiguous: documents TEST/0002, TEST_0002"):
        evaluate(f"{PLAN_EXPR}.TEST_0002", fixture_db[3], tmp_path, config_dir=cfg)


def test_plan_fact_with_several_start_years_names_them(fixture_db, tmp_path):
    cfg = tmp_path / "cfg"
    shutil.copytree(FIXTURE / "config", cfg)
    path = cfg / "plans" / "reports.csv"
    lines = path.read_text().splitlines()
    paris = lines[3]
    assert "implemented_cumulative" in paris
    path.write_text("\n".join([*lines, paris.replace(",,2020", ",,2015")]) + "\n")
    expr = "plan.paris_plan_velo.total.2024.implemented_cumulative"
    with pytest.raises(FactError, match=r"start years \(2015, 2020\)"):
        evaluate(expr, fixture_db[3], tmp_path, config_dir=cfg)


def test_plan_fact_doc_suffix_printing_two_start_years_is_refused(fixture_db, tmp_path):
    cfg = tmp_path / "cfg"
    shutil.copytree(FIXTURE / "config", cfg)
    path = cfg / "plans" / "reports.csv"
    lines = path.read_text().splitlines()
    extra = [lines[3].replace(",,2020", f",,{y}") for y in (2015, 2015)]
    path.write_text("\n".join([*lines, *extra]) + "\n")
    expr = "plan.paris_plan_velo.total.2024.implemented_cumulative"
    with pytest.raises(FactError, match=r"start years \(2015, 2020\)"):
        evaluate(f"{expr}.PARIS-1", fixture_db[3], tmp_path, config_dir=cfg)


def test_the_plan_files_are_read_once_for_many_plan_facts(fixture_db, tmp_path, monkeypatch):
    from velometer.content import facts

    cfg = tmp_path / "cfg"
    shutil.copytree(FIXTURE / "config", cfg)
    calls: list[Path] = []
    real = facts.load_plans

    def counting(path):
        calls.append(Path(path))
        return real(path)

    monkeypatch.setattr(facts, "load_plans", counting)
    for doc in ("", ".TEST_0001", ".TEST_0002"):
        evaluate(f"{PLAN_EXPR}{doc}", fixture_db[3], tmp_path, config_dir=cfg)
    assert calls == [cfg / "plans"]
    path = cfg / "plans" / "reports.csv"  # an edited file is read again, not served stale
    path.write_text(path.read_text().replace(",8.6,", ",8.7,"))
    assert evaluate(PLAN_EXPR, fixture_db[3], tmp_path, config_dir=cfg) == 8.7
    assert len(calls) == 2


def test_plan_fact_needs_the_config_dir(fixture_db, tmp_path):
    with pytest.raises(FactError, match="need the config directory"):
        evaluate(PLAN_EXPR, fixture_db[3], tmp_path)


def _berlin_lau_runs(db_path: Path, kind: str = "lau") -> list[tuple[int, str]]:
    with sqlite3.connect(db_path) as c:
        rows = c.execute(
            "SELECT id, osm_timestamp FROM runs WHERE city_id='berlin' AND boundary_kind=? "
            "ORDER BY osm_timestamp",
            (kind,),
        ).fetchall()
    return [(rid, ts[:10]) for rid, ts in rows]


def _write(db_path: Path, fn) -> None:
    c = sqlite3.connect(db_path)
    try:
        fn(c)
    finally:
        c.close()


def test_overlay_facts(fixture_db, tmp_path):
    db_path, _cfg, _conn, data = fixture_db
    (r1, d1), (r2, d2) = _berlin_lau_runs(db_path)[:2]
    assert d1 != d2

    def row(run, tier, km, version="v1"):
        return OverlayRow(run, "berlin", "vorrangnetz", tier, km, 150.0, version, "2026-10-07")

    rows = [row(r1, "A", 10.0), row(r1, "B", 2.5), row(r1, "C", 99.0)]
    rows += [row(r2, "A", 11.0), row(r2, "B", 4.0)]
    rows += [row(r2, "A", 500.0, "v0")]  # an older overlay version is ignored
    (f1, fd1), *_ = _berlin_lau_runs(db_path, "fua")
    assert fd1 == d1
    rows += [row(f1, "A", 700.0)]  # an FUA run on the same snapshot is not an LAU overlay
    for v in ("v0", "v1"):
        mine = [r for r in rows if r.overlay_version == v]
        _write(db_path, lambda c, v=v, mine=mine: replace_plan_overlay(c, "berlin", v, mine))

    assert evaluate(f"overlay.berlin.vorrangnetz.{d1}.ab_km", data, tmp_path) == 12.5
    assert evaluate(f"overlay.berlin.vorrangnetz.{d2}.ab_km", data, tmp_path) == 15.0
    assert evaluate(f"overlay.berlin.vorrangnetz.{d1}.network_km", data, tmp_path) == 150.0
    assert evaluate(f"overlay_change.berlin.vorrangnetz.{d1}.{d2}", data, tmp_path) == 2.5
    with pytest.raises(FactError, match="no network class 'ergaenzung'"):
        evaluate(f"overlay.berlin.ergaenzung.{d1}.ab_km", data, tmp_path)
    with pytest.raises(FactError, match="no overlay at snapshot '1999-01-01'"):
        evaluate("overlay.berlin.vorrangnetz.1999-01-01.ab_km", data, tmp_path)
    with pytest.raises(FactError, match="no plan overlay for city 'paris'"):
        evaluate(f"overlay.paris.vorrangnetz.{d1}.ab_km", data, tmp_path)


def test_a_reader_opened_before_a_write_sees_the_write(fixture_db, tmp_path):
    """M8-5: the fixture's read-only connection is opened before the test writes. It reads
    each statement afresh (rollback journal, no transaction held between statements), so an
    overlay evaluated before and after a write gives the written value, never a stale one."""
    db_path, _cfg, conn, data = fixture_db
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    (r1, d1), *_ = _berlin_lau_runs(db_path)
    expr = f"overlay.berlin.vorrangnetz.{d1}.ab_km"
    with pytest.raises(FactError, match="no plan overlay"):
        evaluate(expr, data, tmp_path)
    for km in (10.0, 12.5):
        row = OverlayRow(r1, "berlin", "vorrangnetz", "A", km, 150.0, "v1", "2026-10-07")
        _write(db_path, lambda c, row=row: replace_plan_overlay(c, "berlin", "v1", [row]))
        assert evaluate(expr, data, tmp_path) == km


def test_counter_facts(fixture_db, tmp_path):
    db_path, _cfg, _conn, data = fixture_db
    rows = [
        CounterIndexYear("berlin", 2019, 100.0, 12, 2019, "counts", "v2"),
        CounterIndexYear("berlin", 2020, 87.25, 11, 2019, "counts", "v2"),
        CounterIndexYear("berlin", 2021, None, 2, 2019, "counts", "v2"),
    ]
    _write(db_path, lambda c: replace_counter_index(c, "berlin", rows))
    assert evaluate("counter.berlin.2020", data, tmp_path) == 87.25
    assert evaluate("counter_sites.berlin.2020", data, tmp_path) == 11.0
    assert evaluate("counter_sites.berlin.2021", data, tmp_path) == 2.0
    with pytest.raises(FactError, match="no index value in 2021"):
        evaluate("counter.berlin.2021", data, tmp_path)
    with pytest.raises(FactError, match="no counter index year '2018'"):
        evaluate("counter.berlin.2018", data, tmp_path)
    with pytest.raises(FactError, match="no counter index for city 'paris'"):
        evaluate("counter.paris.2020", data, tmp_path)


# --- CLI -----------------------------------------------------------------------------------


def _clean_cli_setup(fixture_db, m8) -> list[str]:
    """`content --check` arguments for the M8 fixture beside the report fixture's database,
    clean before any edit: the fixture's organisation, plan and reconcile config over the
    report fixture's config copy, and a narrative for each of its cities."""
    db_path, cfg, _conn, _data = fixture_db  # cfg: a copy of the real config
    content, config = m8
    for rel in ("organisations.yaml", "reconcile.yaml", "differences.yaml"):
        shutil.copy(config / rel, cfg / rel)
    shutil.copy(config / "external" / "figures.csv", cfg / "external" / "figures.csv")
    shutil.rmtree(cfg / "plans")
    shutil.copytree(config / "plans", cfg / "plans")
    for city in ("berlin", "paris"):
        doc = {"city_id": city, "title": city, "dek": "Dek.", "sections": [
            {"role": "figures", "paragraphs": ["Figures."]}
        ]}  # fmt: skip
        (content / "narratives" / f"{city}.yaml").write_text(yaml.safe_dump(doc))
    args = ["content", "--check", "--content", str(content), "--db", str(db_path)]
    return [*args, "--config-dir", str(cfg), "--docs", str(db_path.parent)]


def test_content_check_reports_profile_problems(fixture_db, m8):
    args = _clean_cli_setup(fixture_db, m8)
    ok = CliRunner().invoke(app, args)
    assert ok.exit_code == 0 and ok.output.strip() == "ok", ok.output
    _edit(_senmvku(m8), lambda d: d["sections"][0]["paragraphs"].append("See [@nope]."))
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 1
    assert res.stderr.strip().splitlines() == ["organisations/senmvku.yaml: unknown source nope"]


def test_an_unreadable_counters_config_fails_the_content_check(fixture_db, m8):
    # the base-year rules come from config/counters.yaml: a check that cannot read it must say
    # so and fail, not print "ok" with those rules silently dropped
    args = _clean_cli_setup(fixture_db, m8)
    cfg = Path(args[args.index("--config-dir") + 1])
    assert (cfg / "counters.yaml").is_file(), "the report fixture's config has the counters"
    assert CliRunner().invoke(app, args).exit_code == 0
    (cfg / "counters.yaml").write_text("cities: [unclosed\n", encoding="utf-8")
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 1
    assert res.stderr.startswith("counters.yaml: cannot read config/counters.yaml: "), res.stderr


# --- the counter index rule in prose (follow-up Task 3) --------------------------------------


def test_counter_rule_facts_follow_the_constants_and_the_stored_base_year(
    fixture_db, tmp_path, monkeypatch
):
    from velometer.counters import index

    db_path, _cfg, _conn, data = fixture_db
    rows = [CounterIndexYear("berlin", y, 100.0, 12, 2020, "counts", "v2") for y in (2020, 2021)]
    _write(db_path, lambda c: replace_counter_index(c, "berlin", rows))
    assert evaluate("counter.min_valid", data, tmp_path) == pytest.approx(index.MIN_VALID * 100)
    assert evaluate("counter.min_sites", data, tmp_path) == index.MIN_SITES
    assert evaluate("counter.base_year.berlin", data, tmp_path) == 2020
    monkeypatch.setattr(index, "MIN_SITES", 5)
    monkeypatch.setattr(index, "MIN_VALID", 0.75)
    assert evaluate("counter.min_sites", data, tmp_path) == 5
    assert evaluate("counter.min_valid", data, tmp_path) == 75
    with pytest.raises(FactError, match="no counter index for city 'paris'"):
        evaluate("counter.base_year.paris", data, tmp_path)
    with pytest.raises(FactError, match="expected base_year.<city>"):
        evaluate("counter.base_year", data, tmp_path)


def _counter_prose(m8, paragraph: str, facts: list[dict] = ()) -> list[str]:
    """The problems of the fixture's counters.yaml with `paragraph` added, beside the real
    config/counters.yaml (whose base years are rule values)."""
    shutil.copy(Path(__file__).parents[1] / "config" / "counters.yaml", m8[1] / "counters.yaml")

    def edit(d):
        d["sections"][0]["paragraphs"].append(paragraph)
        d["facts"] = [*d.get("facts", []), *facts]

    _edit(m8[0] / "counters.yaml", edit)
    return _problems(m8)


RULE = "counters.yaml: index rule stated as literal text: "


def test_counter_prose_may_not_spell_out_the_index_rule(m8):
    problems = _counter_prose(
        m8,
        "Sites complete on nine days in ten are compared, chained from 2019. A year with fewer "
        "than three such sites has no value.",
    )
    assert problems == [
        f"{RULE}nine days in ten (counter.min_valid)",
        f"{RULE}three (counter.min_sites)",
        f"{RULE}2019 (counter.base_year.berlin)",
    ]


def test_counter_prose_states_the_index_rule_through_its_facts(m8):
    paragraph = "Sites complete on at least 90% of days, from 2019: fewer than 3 have no value."
    facts = [
        {"id": "v", "expr": "counter.min_valid", "printed": "90%"},
        {"id": "s", "expr": "counter.min_sites", "printed": "3"},
        {"id": "b", "expr": "counter.base_year.berlin", "printed": "2019"},
    ]
    assert _counter_prose(m8, paragraph, facts) == []


def test_a_rule_value_printed_by_another_fact_is_still_a_literal(m8):
    # "3" declared by a counter_sites fact is not the rule: the check names the rule fact
    facts = [{"id": "n", "expr": "counter_sites.berlin.2020", "printed": "3"}]
    assert _counter_prose(m8, "A link needs 3 sites.", facts) == [f"{RULE}3 (counter.min_sites)"]


def test_the_literal_rule_check_follows_the_constants(m8, monkeypatch):
    from velometer.counters import index

    monkeypatch.setattr(index, "MIN_SITES", 4)
    assert _counter_prose(m8, "A year with fewer than four sites has no value.") == [
        f"{RULE}four (counter.min_sites)"
    ]


RULES = {90.0: "counter.min_valid", 3.0: "counter.min_sites"} | {
    2019.0: "counter.base_year.berlin",
    2020.0: "counter.base_year.madrid",
}


@pytest.mark.parametrize(
    "sentence",
    [
        "Three cities publish hourly counts.",
        "2020 was the COVID year.",
        "Counts fell in 2020 and rose in 2019 terms.",
        "The network grew by 90 km; 3 portals were checked.",
        "Nine of the sites are in three districts.",
        "In 2019 the city opened its portal (Madrid: 2020).",
    ],
)
def test_a_rule_value_outside_a_threshold_statement_is_not_a_literal_rule(sentence):
    from velometer.content.check import literal_counter_rules

    assert literal_counter_rules(sentence, RULES, []) == []


@pytest.mark.parametrize(
    ("sentence", "found"),
    [
        ("A link needs 3 sites.", "3 (counter.min_sites)"),
        ("A year with fewer than three such sites has no value.", "three (counter.min_sites)"),
        ("Fewer than three counter sites give no value.", "three (counter.min_sites)"),
        ("Sites complete on 90% of days count.", "90% (counter.min_valid)"),
        ("Sites complete on 90 per cent of their days count.", "90 (counter.min_valid)"),
        ("Sites complete on nine days in ten count.", "nine days in ten (counter.min_valid)"),
        ("The index sets 2019 = 100.", "2019 (counter.base_year.berlin)"),
        ("Its base year is 2020.", "2020 (counter.base_year.madrid)"),
        ("Chained from 2019 (Madrid: 2020).", "2020 (counter.base_year.madrid)"),
    ],
)
def test_a_rule_value_in_a_threshold_statement_is_a_literal_rule(sentence, found):
    from velometer.content.check import literal_counter_rules

    assert found in literal_counter_rules(sentence, RULES, [])


@pytest.mark.parametrize(
    ("lang", "sentence"),
    [("en", "The index sets 2019 (= 100) for most cities."),
     ("de", "Der Index setzt 2019 (= 100) für die meisten Städte.")],
)  # fmt: skip
def test_a_base_year_with_a_bracketed_equals_100_is_a_literal_rule(lang, sentence):
    # M8-20: "2019 (= 100)" slipped past the "2019 = 100" pattern
    from velometer.content.check import RULES as FAMILIES
    from velometer.content.check import literal_counter_rules

    found = literal_counter_rules(sentence, RULES, [], FAMILIES[lang])
    assert "2019 (counter.base_year.berlin)" in found


def test_the_shipped_counter_page_states_the_rule_through_its_facts():
    # the follow-up Task 3 wording ("90% of days", "chained from 2019 (Madrid: 2020)", "fewer
    # than 3 such sites") passes because the rule facts print those numbers, and only then.
    # M8-25: the rule values are config's and the constants' (counter_rule_values), not typed here
    from velometer.content.check import _is_rule_fact, counter_rule_values, literal_counter_rules

    root = Path(__file__).parents[1]
    rules, error = counter_rule_values(root / "config")
    assert error is None
    doc = load_document(root / "content" / "counters.yaml")
    prose = [p for s in doc.sections for p in s.paragraphs]
    assert [x for p in prose for x in literal_counter_rules(p, rules, doc.facts)] == []
    # without its rule facts, every rule value the page prints is a literal of its rule
    declared = {f.expr.strip() for f in doc.facts if _is_rule_fact(f.expr)}
    others = [f for f in doc.facts if not _is_rule_fact(f.expr)]
    found = {
        x.rsplit(" (", 1)[1].rstrip(")")
        for p in prose
        for x in literal_counter_rules(p, rules, others)
    }
    assert declared and found == declared


def test_the_online_check_fetches_with_the_shared_user_agent(agent_server):
    # Open Data BCN answers httpx's default User-Agent with 502
    from velometer.content import check as ck
    from velometer.sources.download import user_agent

    url, agents = agent_server
    ck._http_get(url)
    assert agents == [user_agent()]
