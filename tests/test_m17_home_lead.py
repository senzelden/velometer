"""M17 Task 15 (spec §4.8, §4.2): the home lead, a short text for people above the ranking.

It says what velometer is, what it counts in plain words (before any letter code), that its km
are mapped km (ADR 0006), what a reader can do here, who maintains it, and it closes with the
home sentence: the current top and bottom city of the ranking the home table shows."""

import re
import shutil
import sqlite3
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.report_fixture import build_report_fixture, build_report_fixture_n
from tests.test_app import CONTENT, _docs
from velometer import i18n
from velometer.app.main import create_app
from velometer.config import load_site
from velometer.selection import report_selector, report_tiers

BASE_URL = "http://127.0.0.1"
HEADLINE = "ours_headline"
PREFIX = {"en": "", "de": "/de"}
MAPPED_KM = {"en": "mapped km", "de": "kartierte km"}  # ADR 0006's term in each edition


def _app(db_path: Path, cfg: Path, tmp: Path):
    maps = tmp / "maps"
    maps.mkdir(exist_ok=True)
    docs = tmp / "docs" if (tmp / "docs").is_dir() else _docs(tmp)
    return create_app(db_path, cfg, maps, docs, content_dir=CONTENT, public=True)


def _homes(db_path: Path, cfg: Path, tmp: Path) -> dict[str, str]:
    with TestClient(_app(db_path, cfg, tmp), base_url=BASE_URL) as c:
        return {lang: c.get(PREFIX[lang] + "/").text for lang in i18n.LANGS}


@pytest.fixture(scope="module")
def four(tmp_path_factory):
    """berlin, c03 and c04 with a current run, paris without one."""
    tmp = tmp_path_factory.mktemp("home-lead")
    db_path, cfg = build_report_fixture_n(tmp, 4)
    return db_path, cfg, tmp


@pytest.fixture(scope="module")
def homes(four):
    return _homes(*four)


def _main(html: str) -> str:
    m = re.search(r"<main\b.*?</main>", html, re.S)
    assert m
    return m.group(0)


def _lead(html: str) -> str:
    m = re.search(r'<section class="lead"[^>]*>.*?</section>', html, re.S)
    assert m, "no lead section"
    return m.group(0)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _words(text: str) -> int:
    """Words as a reader counts them: a punctuation mark left alone by a removed tag is none."""
    return sum(1 for w in text.split() if re.search(r"\w", w))


class _Links(HTMLParser):
    """Every `<a>`: its href and its text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._open: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._open.append([dict(attrs).get("href") or "", ""])

    def handle_data(self, data):
        for link in self._open:
            link[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._open:
            href, text = self._open.pop()
            self.links.append((href, re.sub(r"\s+", " ", text).strip()))


def _links(html: str) -> list[tuple[str, str]]:
    p = _Links()
    p.feed(html)
    return p.links


def _ranked_names(html: str) -> list[str]:
    """The city names of the home ranking table's rows that carry a rank, in table order."""
    m = re.search(r'<table class="ranking[^"]*".*?<tbody>(.*?)</tbody>', html, re.S)
    assert m
    names = []
    for row in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
        rank = re.search(r'<td class="num"[^>]*>\s*(\d*)\s*</td>', row)
        if rank and rank.group(1):
            names.append(_links(row)[0][1])
    return names


def test_home_lead_present_both_editions(homes):
    for lang, html in homes.items():
        main = _main(html)
        lead = main.find('<section class="lead"')
        ranking = main.find('<table class="ranking')
        assert 0 <= lead < ranking, f"{lang}: the lead does not precede the ranking table"
        words = _words(_text(_lead(main)))
        assert 100 <= words <= 200, f"{lang}: the lead has {words} words"


def test_home_lead_links(homes, four):
    site = load_site(four[1], public=True)
    for lang, html in homes.items():
        hrefs = {h for h, _ in _links(_lead(html))}
        p = PREFIX[lang]
        assert hrefs & {f"{p}/cities", "#ranking"}, lang
        for path in ("/stories", "/compare", "/methodology"):
            assert any(h == p + path or h.startswith(p + path + "#") for h in hrefs), (lang, path)
        assert str(site.datalab.url) in hrefs, lang
        assert str(site.repo.url) in hrefs, lang


def test_home_lead_names_counted_types_before_letters(homes, four):
    """Each tier the headline counts is named in plain words, linked to its glossary entry (and
    its diagram), before the first `A+B` in `<main>`."""
    headline = report_tiers(four[1]).headline
    assert headline
    for lang, html in homes.items():
        lead_links = _links(_lead(html))
        main_text = _text(_main(html))
        first_code = main_text.find("A+B")
        assert first_code >= 0, lang
        for tier in sorted(headline):
            named = [t for h, t in lead_links if h.endswith(f"#term-tier-{tier.lower()}")]
            assert named, f"{lang}: tier {tier} is not linked from the lead"
            words = named[0]
            assert not re.search(r"\b[A-E]\b", words), f"{lang}: {words!r} uses a letter code"
            at = main_text.find(words)
            assert 0 <= at < first_code, f"{lang}: {words!r} comes after the first A+B"


def test_home_lead_says_mapped_km(homes):
    for lang, html in homes.items():
        assert MAPPED_KM[lang] in _text(_lead(html)), lang


def _home_sentence(html: str) -> str | None:
    m = re.search(r'<span id="home-sentence"[^>]*>(.*?)</span>\s*</p>\s*</section>', html, re.S)
    return None if m is None else _text(m.group(1))


def _with_headlines(src: tuple, tmp: Path, values: dict[str, float]) -> tuple[Path, Path, Path]:
    """A copy of the fixture database whose headline values are `values` (city id -> value),
    on every run of each city."""
    db_path, cfg, _ = src
    tmp.mkdir()
    db = tmp / "report.sqlite"
    shutil.copy(db_path, db)
    conn = sqlite3.connect(db)
    try:
        with conn:
            for city, v in values.items():
                conn.execute(
                    "UPDATE metrics SET value = ? WHERE city_id = ? AND preset = ?",
                    (v, city, HEADLINE),
                )
    finally:
        conn.close()
    return db, cfg, tmp


@pytest.mark.parametrize(
    "values",
    [
        {"berlin": 10.0, "c03": 30.0, "c04": 20.0},
        {"berlin": 30.0, "c03": 10.0, "c04": 20.0},
        {"berlin": 20.0, "c03": 20.0, "c04": 20.0},  # a tie: the table's order decides
    ],
)
def test_home_sentence_names_current_top_and_bottom(four, tmp_path, values):
    """The lead's last sentence names the first and the last ranked city of the home table,
    which ranks by the headline value; it is computed, so a changed ranking changes it."""
    assert report_selector(four[1]).presets.preset(HEADLINE)
    pages = _homes(*_with_headlines(four, tmp_path / "db", values))
    for lang, html in pages.items():
        ranked = _ranked_names(html)
        assert len(ranked) == len(values), lang
        if len(set(values.values())) > 1:  # the table itself follows the values
            top_id = max(values, key=values.get)
            bottom_id = min(values, key=values.get)
            assert ranked[0] != ranked[-1]
            assert (top_id == "berlin") == (ranked[0] == "Berlin"), lang
            assert (bottom_id == "berlin") == (ranked[-1] == "Berlin"), lang
        sentence = _home_sentence(_lead(html))
        assert sentence, f"{lang}: no home sentence closing the lead"
        top, bottom = ranked[0], ranked[-1]
        assert top in sentence and bottom in sentence, (lang, sentence)
        assert sentence.find(top) < sentence.find(bottom), (lang, sentence)
        for other in ranked[1:-1]:
            assert other not in sentence, (lang, sentence)


def test_home_sentence_omitted_below_two_ranked_cities(tmp_path):
    """berlin has a current run, paris none: one ranked city has no top and bottom."""
    db_path, cfg = build_report_fixture(tmp_path)
    for lang, html in _homes(db_path, cfg, tmp_path).items():
        assert len(_ranked_names(html)) == 1, lang
        lead = _lead(html)
        assert 'id="home-sentence"' not in lead, lang
        assert MAPPED_KM[lang] in _text(lead), lang  # the rest of the lead stays
