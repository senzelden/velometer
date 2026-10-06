"""The shipped content/ passes every check that needs no database (final review, Important 1).

`content --check` needs velometer.sqlite, which a fresh checkout does not have; this runs the
rest of it on every gate. The broken copies below prove each rule is live on the real files.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from velometer.config import default_config_dir, load_cities
from velometer.content.check import check_content_offline

REAL_CONTENT = Path(__file__).parents[1] / "content"
CONFIG = default_config_dir()


def offline_problems(content_dir: Path) -> list[str]:
    cities = [c.id for c in load_cities(CONFIG / "cities.yaml")]
    return check_content_offline(content_dir, CONFIG, city_ids=cities)


@pytest.fixture
def broken(tmp_path) -> Callable[[str, Callable[[dict], None]], Path]:
    """A copy of the real content/ with one file's YAML changed by `mutate`."""
    root = tmp_path / "content"
    shutil.copytree(REAL_CONTENT, root)

    def make(rel: str, mutate: Callable[[dict], None]) -> Path:
        path = root / rel
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        mutate(doc)
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), "utf-8")
        return root

    return make


def test_the_shipped_content_passes_every_check_that_needs_no_database():
    assert offline_problems(REAL_CONTENT) == []


def test_the_real_content_is_found_from_the_test_file_not_the_cwd():
    assert (REAL_CONTENT / "narratives" / "combined.yaml").is_file()
    assert (REAL_CONTENT / "explainer.yaml").is_file()


def _first_story_paragraph(doc: dict, text: str) -> None:
    doc["sections"][0]["paragraphs"][0] += text


def _drop_section(dimension: str) -> Callable[[dict], None]:
    def mutate(doc: dict) -> None:
        doc["sections"] = [s for s in doc["sections"] if s["dimension"] != dimension]

    return mutate


@pytest.mark.parametrize(
    "rel,mutate,expected",
    [
        (
            "narratives/berlin.yaml",
            lambda d: d["quotes"][0].__setitem__("after", 99),
            "after=99 must index one of",
        ),
        (
            "narratives/berlin.yaml",
            lambda d: d["quotes"][0].__setitem__("excerpt", "berlin-fortschrittsbericht-2025/x"),
            "narratives/berlin.yaml: unknown excerpt berlin-fortschrittsbericht-2025/x",
        ),
        (
            "narratives/warsaw.yaml",
            lambda d: _first_story_paragraph(d, " See [@no-such-source]."),
            "narratives/warsaw.yaml: unknown source no-such-source",
        ),
        (
            "narratives/warsaw.yaml",
            lambda d: _first_story_paragraph(d, " See [#no-such-ref]."),
            "narratives/warsaw.yaml: unknown data ref no-such-ref",
        ),
        (
            "narratives/budapest.yaml",
            lambda d: _first_story_paragraph(d, " The city opened a lane."),
            "narratives/budapest.yaml: construction verb 'opened'",
        ),
        (
            "narratives/budapest.yaml",
            lambda d: _first_story_paragraph(d, " It is 123.4 km."),
            "narratives/budapest.yaml: undeclared number 123.4",
        ),
        (
            "narratives/combined.yaml",
            lambda d: d["sections"][1].__setitem__("step", d["sections"][0]["step"]),
            "narratives/combined.yaml: step",
        ),
        ("explainer.yaml", _drop_section("length"), "explainer.yaml: dimension length has 0"),
        (
            "explainer.yaml",
            lambda d: _first_story_paragraph(d, " See [@no-such-source]."),
            "explainer.yaml: unknown source no-such-source",
        ),
    ],
)
def test_each_rule_catches_a_break_in_a_real_file(broken, rel, mutate, expected):
    problems = offline_problems(broken(rel, mutate))
    assert any(expected in p for p in problems), problems


def test_a_missing_city_narrative_and_a_yaml_typo_are_reported(broken):
    root = broken("narratives/paris.yaml", lambda d: None)
    (root / "narratives" / "paris.yaml").unlink()
    (root / "narratives" / "oslo.yaml").write_text("title: [unclosed\n", encoding="utf-8")
    (root / "narratives" / "lyon.yaml").write_text(
        (root / "narratives" / "lyon.yaml").read_text() + "\nsurprise: 1\n", encoding="utf-8"
    )
    problems = offline_problems(root)
    assert "narratives/paris.yaml: missing narrative: paris" in problems
    assert any("oslo.yaml" in p for p in problems)
    assert any("lyon.yaml" in p and "surprise" in p for p in problems)
    assert not any("missing narrative: oslo" in p for p in problems)  # reported once, as broken


def test_an_over_long_excerpt_in_the_registry_is_reported(broken):
    rel = next(
        p.relative_to(REAL_CONTENT) for p in sorted((REAL_CONTENT / "sources").glob("*.yaml"))
    )

    def mutate(doc: dict) -> None:
        doc["sources"][0]["excerpts"][0]["text"] = " ".join(["word"] * 61)

    problems = offline_problems(broken(str(rel), mutate))
    assert len(problems) == 1 and "more than 60 words" in problems[0], problems
