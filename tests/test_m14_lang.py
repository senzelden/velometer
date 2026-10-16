"""M14 Task 5: `lang` on data. Every city has a language; an English page shows a city's own name
(København) in a `<span lang>` of that language where it differs from the English form
(Copenhagen); the Vienna and Lyon plan titles and Oslo's counter source carry the language of
their lead and of their English bracket."""

import re
from html.parser import HTMLParser

import pytest
import yaml
from pydantic import ValidationError

from tests.report_fixture import build_report_fixture
from velometer.app import export
from velometer.config import ConfigError, default_config_dir, load_cities
from velometer.content.models import LANG_TAG, name_lang
from velometer.counters.model import load_counters_config
from velometer.db import open_db
from velometer.plans.models import load_plans
from velometer.report.data import ReportData, open_readonly

CONFIG = default_config_dir()
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
SKIPPED = {"script", "style", "title"}


def test_every_city_has_a_language():
    cities = load_cities(CONFIG / "cities.yaml")
    assert len(cities) >= 21
    for c in cities:
        assert name_lang(c.lang, c.id) == c.lang and LANG_TAG.fullmatch(c.lang), c.id


def test_a_city_without_a_language_fails_loading(tmp_path):
    doc = yaml.safe_load((CONFIG / "cities.yaml").read_text(encoding="utf-8"))
    del doc["cities"][0]["lang"]
    path = tmp_path / "cities.yaml"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="lang"):
        load_cities(path)


class _Occurrences(HTMLParser):
    """Each text node containing `name`: the nearest `lang` above it, its element, its text."""

    def __init__(self, name: str):
        super().__init__(convert_charrefs=True)
        # the name as a word: not `Københavns Kommune`, an organisation
        self.word = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)")
        self.stack, self.found = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            a = dict(attrs)
            self.stack.append((tag, a.get("lang"), a.get("class")))

    @staticmethod
    def _skipped(frame) -> bool:
        # a citation is plain text that is copied whole (M14 Task 4), so it carries no mark
        return frame[0] in SKIPPED or (frame[0] == "details" and frame[2] == "cite")

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if not self.word.search(data) or any(self._skipped(f) for f in self.stack):
            return
        lang = next((f[1] for f in reversed(self.stack) if f[1]), None)
        self.found.append((lang, self.stack[-1][0] if self.stack else "", data.strip()[:90]))


@pytest.fixture(scope="module")
def copenhagen_site(tmp_path_factory):
    """The report fixture whose second city is Copenhagen as config/cities.yaml has it (name,
    German name, aliases, language): a city whose name differs from its English form."""
    from tests.test_app import CONTENT, _client, app_inputs
    from velometer.app.main import create_app

    real = next(c for c in load_cities(CONFIG / "cities.yaml") if c.id == "copenhagen")
    tmp = tmp_path_factory.mktemp("m14_lang")
    db_path, cfg = build_report_fixture(tmp)
    doc = yaml.safe_load((cfg / "cities.yaml").read_text(encoding="utf-8"))
    paris = next(c for c in doc["cities"] if c["id"] == "paris")
    paris.update(name=real.name, name_de=real.name_de, aliases=real.aliases, lang=real.lang)
    (cfg / "cities.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    with open_db(db_path) as conn:
        conn.execute("UPDATE cities SET name = ? WHERE id = 'paris'", (real.name,))
        conn.commit()
    inputs = app_inputs(db_path, cfg, tmp)
    conn = open_readonly(db_path)
    data = ReportData(conn, cfg)
    with _client(create_app(*inputs, content_dir=CONTENT)) as c:
        html = {}
        for url in export.export_urls(data, c.app):
            r = c.get(url)
            if r.headers["content-type"].startswith("text/html"):
                html[url] = r.text
    yield real, html
    conn.close()


def test_a_city_name_differing_from_its_english_form_carries_its_language(copenhagen_site):
    real, html = copenhagen_site
    english = real.aliases[0] if real.aliases else real.name
    assert real.name != english  # the fixture covers a name that differs
    pages = {u: h for u, h in html.items() if not u.startswith("/de")}
    assert any(real.name in h for h in pages.values())
    wrong = {}
    for url, page in pages.items():
        p = _Occurrences(real.name)
        p.feed(page)
        bad = [f for f in p.found if f[0] != real.lang]
        if bad:
            wrong[url] = bad
    assert not wrong, "\n".join(f"{u}: {w}" for u, w in wrong.items())


def test_the_german_edition_shows_the_german_name(copenhagen_site):
    real, html = copenhagen_site
    de = html[next(u for u in html if u.startswith("/de/city/paris"))]
    assert real.name_de in de


def test_the_plan_titles_and_oslos_source_carry_their_languages():
    plans, _rows = load_plans(CONFIG / "plans")
    by_id = {p.id: p for p in plans}
    for pid in ("vienna_radwegoffensive", "lyon_plan_velo_2024"):
        p = by_id[pid]
        assert re.fullmatch(r".+ \([^()]+\)", p.title), pid  # a lead and a bracket
        assert p.title_lang and p.title_bracket_lang, pid
        assert p.title_lang != p.title_bracket_lang, pid
    assert (
        by_id["vienna_radwegoffensive"].title_lang,
        by_id["vienna_radwegoffensive"].title_bracket_lang,
    ) == ("de", "en")
    assert (
        by_id["lyon_plan_velo_2024"].title_lang,
        by_id["lyon_plan_velo_2024"].title_bracket_lang,
    ) == ("fr", "en")
    # the German title is ours, in the page's language: no `lang` on it
    de = by_id["vienna_radwegoffensive"].localised("de")
    assert de.title_lang is None and de.title_bracket_lang is None
    oslo = load_counters_config(CONFIG / "counters.yaml").entry("oslo")
    assert (oslo.source_lang, oslo.source_bracket_lang) == ("nb", "en")


def test_a_title_bracket_language_needs_a_bracket():
    from velometer.plans.models import Plan

    base = dict(id="x", city="x", title="Title", adopted=None, url="https://example.org/x",
                status="current", publisher="P", items=[])  # fmt: skip
    with pytest.raises(ValidationError, match="title_bracket_lang"):
        Plan(**base, title_bracket_lang="en")
