import copy
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from velometer.cli import app
from velometer.config import DIFFERENCE_DIMENSIONS, default_config_dir, load_differences
from velometer.content.check import (
    _dimension_ids,
    _full,
    check_content,
    check_online,
    construction_verbs,
    undeclared_numbers,
)
from velometer.content.facts import evaluate
from velometer.content.loader import load_sources
from velometer.content.models import STORY_STEPS

EXPR = "series.berlin.lau.current.ab_km"

SOURCES = {
    "sources": [
        {
            "id": "src",
            "publisher": "Senat",
            "title": "Radverkehr",
            "url": "https://example.org/radverkehr",
            "accessed": "2026-10-01",
            "language": "de",
            "kind": "official",
            "excerpts": [
                {
                    "id": "e1",
                    "text": "Das Netz ist 78,2 km lang.",
                    "gloss_en": "The network is 78.2 km long.",
                    "locator": "p. 3",
                }
            ],
        }
    ]
}


def _write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")


def _berlin(value: float) -> dict:
    return {
        "city_id": "berlin",
        "title": "Berlin",
        "dek": "A dek.",
        "sections": [
            {"heading": "Story", "paragraphs": [f"Berlin has {value:.1f} km [#r1] [@src]."]},
            {"role": "figures", "paragraphs": ["Figures."]},
        ],
        "quotes": [{"excerpt": "src/e1", "after": 0}],
        "facts": [{"id": "ab", "expr": EXPR, "printed": f"{value:.1f}"}],
        "data_refs": [{"id": "r1", "label": "Report", "route": "/"}],
        "literals": ["5 m"],
    }


def _combined() -> dict:
    return {
        "city_id": "combined",
        "title": "All",
        "dek": "Dek.",
        "sections": [{"step": s, "paragraphs": [f"Step {s}."]} for s in STORY_STEPS],
    }


@pytest.fixture
def content(fixture_db, tmp_path):
    _db, _cfg, _conn, data = fixture_db
    value = evaluate(EXPR, data, tmp_path)
    root = tmp_path / "content"
    _write(root / "sources" / "all.yaml", SOURCES)
    _write(root / "narratives" / "berlin.yaml", _berlin(value))
    _write(root / "narratives" / "paris.yaml", {**_berlin(value), "city_id": "paris"})
    _write(root / "narratives" / "combined.yaml", _combined())
    _write(root / "explainer.yaml", {"title": "Explainer", "intro": ["Intro."], "sections": []})
    # these tests own their dimension list (the shipped one: test_shipped_dimensions_*)
    (_cfg / "differences.yaml").unlink(missing_ok=True)
    return root, data, tmp_path


def _problems(root, data, tmp):
    return check_content(root, data, tmp)


def test_valid_content_has_no_problems(content):
    root, data, tmp = content
    assert _problems(root, data, tmp) == []


def test_missing_city_narrative_is_one_problem(content):
    root, data, tmp = content
    (root / "narratives" / "paris.yaml").unlink()
    assert _problems(root, data, tmp) == ["narratives/paris.yaml: missing narrative: paris"]


def test_missing_combined_and_explainer(content):
    root, data, tmp = content
    (root / "narratives" / "combined.yaml").unlink()
    assert any("missing narrative: combined" in p for p in _problems(root, data, tmp))
    _write(root / "narratives" / "combined.yaml", _combined())
    (root / "explainer.yaml").unlink()
    assert _problems(root, data, tmp) == ["explainer.yaml: missing explainer"]


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (
            lambda n: n["quotes"].__setitem__(0, {"excerpt": "src/nope", "after": 0}),
            "unknown excerpt",
        ),
        (
            lambda n: n["sections"][0]["paragraphs"].__setitem__(0, "See [@ghost]."),
            "unknown source",
        ),
        (
            lambda n: n["sections"][0]["paragraphs"].__setitem__(0, "See [#ghost]."),
            "unknown data ref",
        ),
        (
            lambda n: n["sections"][0]["paragraphs"].__setitem__(0, "It was 77.7 km."),
            "undeclared number 77.7",
        ),
        (
            lambda n: n["sections"][0]["paragraphs"].__setitem__(0, "Berlin built paths."),
            "construction verb 'built'",
        ),
        (lambda n: n["facts"][0].__setitem__("printed", "1.0"), "printed 1.0"),
        (lambda n: n["facts"][0].__setitem__("expr", "series.berlin.lau.current.nope"), "fact ab:"),
        (
            lambda n: n["sections"].__setitem__(1, {"paragraphs": ["no figures role"]}),
            "no figures section",
        ),
    ],
)
def test_each_rule_reports(content, mutate, expected):
    root, data, tmp = content
    path = root / "narratives" / "berlin.yaml"
    n = yaml.safe_load(path.read_text())
    mutate(n)
    _write(path, n)
    problems = _problems(root, data, tmp)
    assert any(p.startswith("narratives/berlin.yaml: ") and expected in p for p in problems), (
        problems
    )


def test_combined_must_cover_each_step_once(content):
    root, data, tmp = content
    c = _combined()
    c["sections"][1]["step"] = "all"
    _write(root / "narratives" / "combined.yaml", c)
    problems = _problems(root, data, tmp)
    assert any("step all appears 2 times" in p for p in problems)
    assert any("step leaders appears 0 times" in p for p in problems)


def test_load_error_is_one_problem(content):
    root, data, tmp = content
    (root / "narratives" / "berlin.yaml").write_text("city_id: berlin\n")
    problems = _problems(root, data, tmp)
    assert len(problems) == 1 and "berlin.yaml" in problems[0]


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda n: n["sections"][0].__setitem__("heading", "Opened 40 km"), "construction verb"),
        (lambda n: n["sections"][0].__setitem__("heading", "Opened 40 km"), "undeclared number 40"),
        (lambda n: n.__setitem__("title", "Berlin built 41 km"), "construction verb 'built'"),
        (lambda n: n.__setitem__("title", "Berlin built 41 km"), "undeclared number 41"),
        (lambda n: n.__setitem__("dek", "Removed 42 km"), "undeclared number 42"),
        (lambda n: n["literals"].__setitem__(0, "6 m"), "undeclared number 5"),
    ],
)
def test_headings_titles_and_exact_literals(content, mutate, expected):
    root, data, tmp = content
    path = root / "narratives" / "berlin.yaml"
    n = yaml.safe_load(path.read_text())
    n["sections"][0]["paragraphs"].append("A lane of 5 m.")
    mutate(n)
    _write(path, n)
    assert any(expected in p for p in _problems(root, data, tmp)), _problems(root, data, tmp)


def test_explainer_title_and_headings_are_scanned(content):
    root, data, tmp = content
    cfg = data.config_dir
    (cfg / "differences.yaml").write_text(yaml.safe_dump({"dimensions": [{"id": "d1"}]}))
    ex = {
        "title": "Built 11 things",
        "intro": ["Intro."],
        "sections": [{"dimension": "d1", "heading": "Opened 12", "paragraphs": ["Fine."]}],
    }
    _write(root / "explainer.yaml", ex)
    problems = _problems(root, data, tmp)
    for expected in ("number 11", "'built'", "number 12", "'opened'"):
        assert any(expected in p for p in problems), problems


def test_fact_mismatch_prints_all_digits(content):
    root, data, tmp = content
    path = root / "narratives" / "berlin.yaml"
    n = yaml.safe_load(path.read_text())
    n["facts"][0]["printed"] = "1.0"
    _write(path, n)
    value = evaluate(EXPR, data, tmp)
    shown = f"{value:.6f}".rstrip("0").rstrip(".")
    assert any(f"is {shown}, printed 1.0" in p for p in _problems(root, data, tmp))
    assert _full(1234567.5) == "1234567.5"
    assert _full(1234567.0) == "1234567"
    assert _full(0.25) == "0.25"


def test_german_excerpt_numbers_in_registry_are_not_checked(content):
    root, data, tmp = content
    assert "78,2" in load_sources(root / "sources")["src"].excerpts[0].text
    assert _problems(root, data, tmp) == []


def test_explainer_rules_and_dimensions(content):
    root, data, tmp = content
    cfg = data.config_dir
    (cfg / "differences.yaml").write_text(
        yaml.safe_dump({"dimensions": [{"id": "d1"}, {"id": "d2"}]})
    )
    ex = {
        "title": "Explainer",
        "intro": ["It was 77.7 km."],
        "sections": [{"dimension": "d1", "heading": "H", "paragraphs": ["Opened it."]}],
    }
    _write(root / "explainer.yaml", ex)
    problems = _problems(root, data, tmp)
    assert "explainer.yaml: undeclared number 77.7" in problems
    assert "explainer.yaml: construction verb 'opened'" in problems
    assert "explainer.yaml: dimension d2 has 0 sections, expected 1" in problems


def test_years_ordinals_literals_and_declared_pass():
    allowed = {"109.1"}
    assert (
        undeclared_numbers(
            "In 2024-2026 the 3rd, +109.1 and 109.1% 5 m [@a1] `42` [x](http://a/9)",
            allowed,
            ["5 m"],
        )
        == []
    )
    assert undeclared_numbers("About 1,551 and −4.6%.", {"1,551"}) == ["−4.6%"]
    assert undeclared_numbers("In 1999 and 2100.", set()) == ["1999", "2100"]


def test_literal_allows_only_its_exact_text():
    assert undeclared_numbers("A 5 m lane, then 5 more.", set(), ["5 m"]) == ["5"]
    assert undeclared_numbers("A 5 m lane and a 45 m one.", set(), ["5 m"]) == ["45"]
    assert undeclared_numbers("A 5\u00a0m lane.", set(), ["5 m"]) == []


@pytest.mark.parametrize("sep", [" ", "\u202f", "\u00a0"])
def test_space_grouped_thousands_are_one_number(sep):
    assert undeclared_numbers(f"About 1{sep}551 km.", {"1,551"}) == []
    assert undeclared_numbers(f"About 1{sep}551 km.", set()) == [f"1{sep}551"]
    assert undeclared_numbers("Counts 12 and 345.", set()) == ["12", "345"]


def test_construction_verbs():
    assert construction_verbs("Opened, then REMOVED; unbuilt stays. Built built.") == [
        "opened",
        "removed",
        "built",
    ]


def test_check_online_with_fake_fetch():
    src = load_sources_from(SOURCES)
    calls: list[str] = []

    def without(url):
        calls.append(url)
        return "<p>other   text</p>"

    out = check_online(src, fetch=without)
    assert out == ["sources/src: excerpt not found online: e1"]
    assert calls == ["https://example.org/radverkehr"]
    assert check_online(src, fetch=lambda u: "<p>Das  Netz\nist 78,2 km   lang.</p>") == []

    def boom(url):
        raise OSError("down")

    assert "cannot fetch" in check_online(src, fetch=boom)[0]


def load_sources_from(doc):
    from velometer.content.models import Source

    return {s["id"]: Source.model_validate(copy.deepcopy(s)) for s in doc["sources"]}


def test_cli_check_ok_and_failing(content, fixture_db):
    root, _data, tmp = content
    db, cfg, _conn, _d = fixture_db
    args = [
        "content",
        "--check",
        "--content",
        str(root),
        "--db",
        str(db),
        "--config-dir",
        str(cfg),
        "--docs",
        str(tmp),
    ]
    ok = CliRunner().invoke(app, args)
    assert ok.exit_code == 0 and ok.output.strip() == "ok"
    (root / "narratives" / "paris.yaml").unlink()
    bad = CliRunner().invoke(app, args)
    assert bad.exit_code == 1
    assert "missing narrative: paris" in bad.stderr


def test_cli_summary(content):
    root, _data, _tmp = content
    res = CliRunner().invoke(app, ["content", "--content", str(root)])
    assert res.exit_code == 0
    assert res.output.strip() == "3 narratives, 1 sources, 1 excerpts"


def _check_args(content, fixture_db, *extra):
    root, _data, tmp = content
    db, cfg, _conn, _d = fixture_db
    return [
        "content",
        "--check",
        *extra,
        "--content",
        str(root),
        "--db",
        str(db),
        "--config-dir",
        str(cfg),
        "--docs",
        str(tmp),
    ]


def test_cli_online_uses_fetcher_only_when_offline_clean(content, fixture_db, monkeypatch):
    import velometer.content.check as ck

    root = content[0]
    calls: list[str] = []

    def fake(url):
        calls.append(url)
        return "<p>unrelated</p>"

    real = ck.check_online
    monkeypatch.setattr(ck, "check_online", lambda sources: real(sources, fetch=fake))
    res = CliRunner().invoke(app, _check_args(content, fixture_db, "--online"))
    assert res.exit_code == 1
    assert "sources/src: excerpt not found online: e1" in res.stderr
    assert calls == ["https://example.org/radverkehr"]

    monkeypatch.setattr(
        ck,
        "check_online",
        lambda sources: real(sources, fetch=lambda u: "Das Netz ist 78,2 km lang."),
    )
    ok = CliRunner().invoke(app, _check_args(content, fixture_db, "--online"))
    assert ok.exit_code == 0 and ok.output.strip() == "ok"

    calls.clear()
    monkeypatch.setattr(ck, "check_online", lambda sources: real(sources, fetch=fake))
    (root / "narratives" / "paris.yaml").unlink()
    bad = CliRunner().invoke(app, _check_args(content, fixture_db, "--online"))
    assert bad.exit_code == 1 and calls == []  # offline problems stop before any fetch


def test_cli_online_alone_implies_check(content, fixture_db, monkeypatch):
    import velometer.content.check as ck

    calls: list[str] = []
    real = ck.check_online
    monkeypatch.setattr(
        ck, "check_online", lambda sources: real(sources, fetch=lambda u: calls.append(u) or "")
    )
    args = _check_args(content, fixture_db, "--online")
    args.remove("--check")
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 1 and "excerpt not found online: e1" in res.stderr
    assert calls == ["https://example.org/radverkehr"]
    assert "Implies --check" in CliRunner().invoke(app, ["content", "--help"]).output


def test_cli_check_missing_db(content, fixture_db, tmp_path):
    args = _check_args(content, fixture_db)
    args[args.index("--db") + 1] = str(tmp_path / "absent.sqlite")
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 1
    assert res.stderr.startswith("error:")


def _explainer(dims) -> dict:
    return {
        "title": "Explainer",
        "intro": ["Intro."],
        "sections": [{"dimension": d, "heading": d.title(), "paragraphs": ["Text."]} for d in dims],
    }


def test_shipped_dimensions_match_the_config_model(content):
    _root, data, _tmp = content
    shipped = default_config_dir() / "differences.yaml"
    assert tuple(_dimension_ids(shipped)) == DIFFERENCE_DIMENSIONS
    assert [d.id for d in load_differences(shipped).dimensions] == list(DIFFERENCE_DIMENSIONS)


def test_explainer_needs_one_section_per_shipped_dimension(content):
    root, data, tmp = content
    shipped = default_config_dir() / "differences.yaml"
    (data.config_dir / "differences.yaml").write_text(shipped.read_text(encoding="utf-8"))
    _write(root / "explainer.yaml", _explainer(DIFFERENCE_DIMENSIONS))
    assert _problems(root, data, tmp) == []
    _write(root / "explainer.yaml", _explainer(DIFFERENCE_DIMENSIONS[:-1]))
    assert _problems(root, data, tmp) == [
        f"explainer.yaml: dimension {DIFFERENCE_DIMENSIONS[-1]} has 0 sections, expected 1"
    ]
