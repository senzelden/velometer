"""The methodology's QECIO-difference example names tag combinations and the tier each gets here.
Every such claim, in both languages, must match what the report classifier (the version the same
file names) actually does with those tags. The v1-v3 sentence ("a designated foot-and-cycle path
with `segregated=yes` is tier B") went stale when v4 moved that path to A (ADR 0002 amendment)."""

import re
from pathlib import Path

import pytest

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.types import WayRecord

DOCS = Path(__file__).resolve().parents[1] / "docs"
FILES = {"en": "methodology.md", "de": "methodology.de.md"}
PARAGRAPH_START = {"en": "The tiers derive from", "de": "Die Stufen leiten sich"}
# "(`k=v` with `k=v`) is tier C" / "(`k=v` mit `k=v`) als Stufe C"
CLAIM = {
    "en": re.compile(r"\(([^()]*`[^()]*)\)\s+is tier ([A-E])\b"),
    "de": re.compile(r"\(([^()]*`[^()]*)\)\s+als Stufe ([A-E])\b"),
}
TAG = re.compile(r"`([^`=\s]+)=([^`\s]+)`")
VERSION = re.compile(r"`config/classifier/(v\d+)\.yaml`")
# the stale shape: a sentence naming `segregated=yes` and a tier
SEGREGATED_TIER = {
    "en": re.compile(r"`segregated=yes`[^.]*?\btier ([A-E])\b"),
    "de": re.compile(r"`segregated=yes`[^.]*?\bStufe ([A-E])\b"),
}


def _text(lang: str) -> str:
    return (DOCS / FILES[lang]).read_text(encoding="utf-8")


def _paragraph(text: str, lang: str) -> str:
    start = text.index(PARAGRAPH_START[lang])
    end = text.find("\n\n", start)
    return text[start : end if end != -1 else None]


def _tier(tags: dict[str, str], version: str) -> str | None:
    """The tier the classifier gives the way side the tags describe. Road-side keys
    (`cycleway:<side>...`) are tested on a two-way main road; anything else is a standalone way."""
    cfg = load_classifier(default_config_dir() / "classifier" / f"{version}.yaml")
    side = next(
        (s for s in ("left", "right", "both") if any(k.startswith(f"cycleway:{s}") for k in tags)),
        None,
    )
    way_tags = {"highway": "primary", **tags} if side else tags
    sides = classify_ways([WayRecord(1, way_tags, ((0.0, 0.0), (0.001, 0.0)))], cfg)
    want = {"left", "right"} if side == "both" else {side or "self"}
    tiers = {c.tier for c in sides if c.side.side in want}
    assert len(tiers) == 1, (tags, tiers)
    return tiers.pop()


@pytest.mark.parametrize("lang", ["en", "de"])
def test_every_tier_claim_in_the_qecio_example_matches_the_classifier(lang):
    text = _text(lang)
    version = VERSION.search(text).group(1)
    claims = CLAIM[lang].findall(_paragraph(text, lang))
    assert claims, "the QECIO paragraph names no tag combination with a tier"
    for group, tier in claims:
        tags = dict(TAG.findall(group))
        assert tags, group
        assert _tier(tags, version) == tier, f"{lang}: {group!r} is not tier {tier} in {version}"


@pytest.mark.parametrize("lang", ["en", "de"])
def test_no_segregated_path_tier_claim_contradicts_the_classifier(lang):
    text = _text(lang)
    version = VERSION.search(text).group(1)
    actual = _tier({"highway": "path", "bicycle": "designated", "segregated": "yes"}, version)
    for claimed in SEGREGATED_TIER[lang].findall(_paragraph(text, lang)):
        assert claimed == actual, (
            f"{lang}: segregated path claimed {claimed}, {version} says {actual}"
        )


def test_german_class_names_every_lane_kind_the_english_does():
    """The English "all cycle lanes" covers painted advisory lanes too (tier D includes them),
    and German "Radfahrstreifen" alone does not: the German sentence on QECIO's one lane class names
    Schutzstreifen as well (the user's correction of 2026-11-02)."""
    en = _paragraph(_text("en"), "en")
    de = _paragraph(_text("de"), "de")
    assert "QECIO counts all cycle lanes as one class" in en
    one_class = re.search(r"zählt QECIO alle ([^.,]*?) als eine Klasse", de)
    assert one_class, de
    assert "Schutzstreifen" in one_class.group(1) and "Radfahr" in one_class.group(1)
