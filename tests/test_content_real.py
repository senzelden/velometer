"""The shipped content/ passes every check that needs no database (final review, Important 1).

`content --check` needs velometer.sqlite, which a fresh checkout does not have; this runs the
rest of it on every gate. The broken copies below prove each rule is live on the real files.
"""

import re
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from markupsafe import escape

from velometer.app.narrative import render_explainer, render_organisation
from velometer.config import default_config_dir, load_cities
from velometer.content.check import check_content_offline
from velometer.content.loader import load_document, load_organisations, load_sources

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


EXPLAINER_SHAPED = ["explainer.yaml", "plans/berlin.yaml", "counters.yaml"]
# every organisation profile that places a quote (the organisations page renders them all)
PROFILES_WITH_QUOTES = [
    f"organisations/{p.name}"
    for p in sorted((REAL_CONTENT / "organisations").glob("*.yaml"))
    if yaml.safe_load(p.read_text(encoding="utf-8")).get("quotes")
]
QUOTED_PAGES = EXPLAINER_SHAPED + PROFILES_WITH_QUOTES


def _cites(paragraph: str) -> set[str]:
    return set(re.findall(r"\[@([^\]\s]+)\]", paragraph))


def _render(rel: str, sources):
    """(document, rendered) as the app renders the page or profile."""
    if rel.startswith("organisations/"):
        org = load_organisations(REAL_CONTENT / "organisations")[Path(rel).stem]
        return org, render_organisation(org, sources)
    doc = load_document(REAL_CONTENT / rel)
    return doc, render_explainer(doc, sources)


def test_the_profiles_with_quotes_are_found():
    assert PROFILES_WITH_QUOTES  # the parametrisation below is not silently empty


@pytest.mark.parametrize("rel", QUOTED_PAGES)
def test_each_quote_renders_after_a_paragraph_citing_its_source(rel):
    """Rendered as the app renders it, every pull-quote of a shipped explainer-shaped page or
    organisation profile follows a paragraph that cites the quote's source (a quote whose source
    the intro cites may follow the first paragraph). The Berlin plan page's `after` indices were
    once counted with the intro, which put every quote one paragraph late."""
    sources = load_sources(REAL_CONTENT / "sources")
    doc, rendered = _render(rel, sources)
    number = {s.id: n for n, s in rendered.sources.items()}
    href = {n: f'href="#{rendered.prefix}src-{n}"' for n in number.values()}
    intro_cites = {n for n in number.values() if any(href[n] in p for p in rendered.intro)}
    seen, previous, placed = 0, "", []
    for sec in rendered.sections:
        for item in sec.items:
            if "pullquote" not in item:
                seen, previous = seen + 1, item
                continue
            q = next(q for q in doc.quotes if _excerpt_text(sources, q.excerpt) in item)
            n = number[q.excerpt.partition("/")[0]]
            assert href[n] in previous or (seen == 1 and n in intro_cites), q.excerpt
            placed.append(q.excerpt)
    assert sorted(placed) == sorted(q.excerpt for q in doc.quotes)  # every quote was rendered


def _paragraph_not_citing(doc: dict, sid: str) -> int:
    """The first paragraph a quote of `sid` may not follow (counted as `after` counts)."""
    paragraphs = [p for s in doc["sections"] for p in s["paragraphs"]]
    intro = set().union(*(_cites(p) for p in doc.get("intro", [])))
    wrong = [
        i
        for i, p in enumerate(paragraphs)
        if sid not in _cites(p) and not (i == 0 and sid in intro)
    ]
    assert wrong, f"every paragraph may carry a quote of {sid}: no wrong place to move it to"
    return wrong[0]


def test_a_page_citing_the_source_everywhere_fails_with_a_message_not_stopiteration():
    doc = {"sections": [{"paragraphs": ["A [@s].", "B [@s]."]}]}
    assert _paragraph_not_citing({"sections": [{"paragraphs": ["A [@s].", "B."]}]}, "s") == 1
    with pytest.raises(AssertionError, match="every paragraph may carry a quote of s"):
        _paragraph_not_citing(doc, "s")


@pytest.mark.parametrize("rel", QUOTED_PAGES)
def test_a_quote_moved_off_its_paragraph_is_reported(broken, rel):
    """The offline check catches a quote moved to a paragraph that does not cite its source;
    the wrong index is derived from the file, so the break survives a rewrite of the page."""
    doc = yaml.safe_load((REAL_CONTENT / rel).read_text(encoding="utf-8"))
    q = doc["quotes"][0]
    wrong = _paragraph_not_citing(doc, q["excerpt"].partition("/")[0])

    def mutate(d: dict) -> None:
        d["quotes"][0]["after"] = wrong

    problems = offline_problems(broken(rel, mutate))
    assert f"{rel}: quote {q['excerpt']} follows paragraph {wrong}," in " ".join(problems), problems


def _excerpt_text(sources, ref: str) -> str:
    sid, _, eid = ref.partition("/")
    return str(escape(next(e.text for e in sources[sid].excerpts if e.id == eid)))


def test_plan_page_lines_fit_100_characters():
    # the plan pages are kept to the repo's line length (follow-up Task 7)
    pages = sorted((REAL_CONTENT / "plans").glob("*.yaml"))
    assert pages
    long = [
        f"{p.name}:{n}"
        for p in pages
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1)
        if len(line) > 100
    ]
    assert long == []
