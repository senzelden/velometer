"""M12 Task 5: German siblings of the config's reader prose, German city names on the pages."""

import csv
import html
import re
import sqlite3
from pathlib import Path

import pytest
import yaml

from tests.conftest import app_for
from tests.test_app import setup  # noqa: F401
from velometer import i18n
from velometer.config import ConfigError, load_cities, load_differences, reader_prose
from velometer.db import replace_external_figures
from velometer.report.data import COMPARISON_SOURCES, figure_notes_de
from velometer.sources.external import load_figures_csv

GERMAN = {
    "vienna": "Wien",
    "prague": "Prag",
    "warsaw": "Warschau",
    "copenhagen": "Kopenhagen",
    "krakow": "Krakau",
}  # fmt: skip  (spec §4.3's list; a pre-flight ruling accepts it)
ENGLISH_FUNCTION_WORDS = {"the", "of", "and", "with", "from", "not", "is", "are", "which"}


def test_name_de_is_set_exactly_for_the_exonyms():
    cities = {c.id: c for c in load_cities(Path("config/cities.yaml"))}
    assert {i: c.name_de for i, c in cities.items() if c.name_de} == GERMAN


def test_a_missing_differences_sibling_is_refused(tmp_path):
    raw = yaml.safe_load(Path("config/differences.yaml").read_text(encoding="utf-8"))
    raw["dimensions"][0].pop("label_de")
    p = tmp_path / "differences.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="label_de"):
        load_differences(p)


def test_a_german_map_must_mirror_its_english_map(tmp_path):
    raw = yaml.safe_load(Path("config/differences.yaml").read_text(encoding="utf-8"))
    raw["labels_de"].pop(next(iter(raw["labels_de"])))
    p = tmp_path / "differences.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="labels_de must mirror labels"):
        load_differences(p)


def test_every_figure_note_has_one_german_note():
    by_note = {}
    text = Path("config/external/figures.csv").read_text(encoding="utf-8")
    for row in csv.DictReader(text.splitlines()):
        if row["note"]:
            assert row["note_de"], row
            by_note.setdefault(row["note"], set()).add(row["note_de"])
    assert all(len(v) == 1 for v in by_note.values())


def test_figure_notes_de_refuses_a_note_without_german(tmp_path):
    (tmp_path / "external").mkdir()
    (tmp_path / "external" / "figures.csv").write_text(
        "city_id,note,note_de\nberlin,an English note,\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="row 2: note_de is required"):
        figure_notes_de(tmp_path)


def test_a_counter_city_note_needs_its_german_clause():
    # M8-8: the Madrid gap clause is reader prose in both editions
    from pydantic import ValidationError

    from velometer.counters.model import CounterEntry

    entry = {
        "city": "x", "adapter": "x", "source": "S", "licence": "L", "licence_url": "u",
        "page": "p", "urls": ["u"], "timezone": "Europe/Madrid", "grain": "hourly",
        "note": "while the detectors were changed",
    }  # fmt: skip
    with pytest.raises(ValidationError, match="note_de is required beside note"):
        CounterEntry(**entry)
    assert CounterEntry(**entry, note_de="während").note_de == "während"
    assert any(
        w == "counters.yaml cities.madrid.note" for w, _en, _de in reader_prose(Path("config"))
    )


def test_german_config_prose_has_no_english_sentences():
    # the sniff's scope is config-derived text only: the _de values themselves
    bad = []
    for where, _en, de in reader_prose(Path("config")):
        words = re.findall(r"[a-zäöüß]+", de.lower())
        runs = [words[i : i + 4] for i in range(max(len(words) - 3, 0))]
        if any(len(ENGLISH_FUNCTION_WORDS & set(r)) >= 2 for r in runs):
            bad.append(f"{where}: {de!r}")
    assert bad == []


@pytest.mark.parametrize(
    "path", ["/city/berlin/time", "/city/berlin/tiers", "/city/berlin/figures", "/cities",
             "/compare?cities=berlin,paris", "/stories", "/city/berlin/panel"],
)  # fmt: skip
def test_german_pages_use_name_de_everywhere(setup, path):  # noqa: F811
    with app_for(setup, name_de={"berlin": "Berlin-Test"}) as c:
        de, en = c.get("/de" + path).text, c.get(path).text
    assert "Berlin-Test" in de and "Berlin-Test" not in en
    if path == "/city/berlin/time":
        assert re.search(r"<h1[^>]*>[^<]*Berlin-Test", de)
        assert re.search(r'<p class="cite-text">[^<]*Berlin-Test', de)
        assert re.search(r'<script type="application/json" class="cite-data">[^<]*Berlin-Test', de)


def test_german_tables_built_from_the_series_use_name_de(setup):  # noqa: F811
    """The Compare table and the overview chart table come from the English series.json: the
    German page names its cities in German there too, not only in the nav."""
    with app_for(setup, name_de={"berlin": "Berlin-Test"}) as c:
        compare = c.get("/de/compare?cities=berlin,paris").text
        overview = c.get("/de/").text
    for page in (compare, overview):
        assert re.search(r'<th scope="row"[^>]*>(<a [^>]*>)?Berlin-Test', page)


def test_search_terms_hold_every_name_form_in_both_editions(setup):  # noqa: F811
    with app_for(setup, name_de={"berlin": "Berlin-Test"}) as c:
        for path in ("/data/search.json", "/de/data/search.json"):
            entry = next(e for e in c.get(path).json() if e["kind"] == "city" and
                         e["url"].endswith("city/berlin"))  # fmt: skip
            assert "Berlin-Test" in entry["terms"] and "Berlin" in entry["terms"]
            assert entry["label"].startswith("Berlin-Test" if path.startswith("/de") else "Berlin ")


def test_the_series_file_stays_english_after_a_german_page(setup):  # noqa: F811
    """series.json is one shared English file: a German page that builds it first must not
    leave German names in it."""
    with app_for(setup, name_de={"berlin": "Berlin-Test"}) as c:
        c.get("/de/compare?cities=berlin,paris")
        series = c.get("/data/series.json").json()
    assert series["cities"]["berlin"]["name"] == "Berlin"
    assert "velometer headline" in series["presets"].values()


def _with_curated_figures(paths, city_id: str) -> None:
    """Store the curated figures.csv rows of `city_id` in the fixture's own database copy."""
    db_path = paths[0]
    figures = [f for f in load_figures_csv(Path("config/external/figures.csv"))
               if f.city_id == city_id]  # fmt: skip
    conn = sqlite3.connect(db_path)
    try:
        for source in sorted({f.source for f in figures}):
            replace_external_figures(conn, source, [f for f in figures if f.source == source])
    finally:
        conn.close()


def test_german_figures_tab_shows_the_german_config_text(setup):  # noqa: F811
    _with_curated_figures(setup, "berlin")
    notes = figure_notes_de(Path("config"))
    rows = [f for f in load_figures_csv(Path("config/external/figures.csv"))
            if f.city_id == "berlin" and f.source not in COMPARISON_SOURCES]  # fmt: skip
    assert rows, "the fixture needs berlin's reported figures"
    with app_for(setup) as c:
        de = i18n.visible_text(c.get("/de/city/berlin/figures").text)
        en = i18n.plain(html.unescape(c.get("/city/berlin/figures").text))
    for f in rows:
        assert notes[f.note] in de and f.note not in de
        assert f.note in en
    assert i18n.t("de", "figure.scope.vorrangnetz") in de
    assert i18n.t("de", "figure.basis.streckenlaenge") in de
    # both editions show the glossed label (M13: the original term, then its translation)
    assert i18n.t("en", "figure.scope.vorrangnetz") in en
    assert i18n.t("en", "figure.basis.streckenlaenge") in en
    leaks = [en_ for _w, en_, de_ in reader_prose(Path("config"))
             if len(en_.split()) >= 4 and en_ != de_ and en_ in de]  # fmt: skip
    assert leaks == []


def test_german_dimension_list_keeps_its_nouns_capitalised(setup):  # noqa: F811
    """The Figures tab lists the dimensions in running text: only the first letter is lowered,
    so German nouns keep their capital ("welche Art von km")."""
    with app_for(setup) as c:
        de = c.get("/de/city/berlin/figures").text
        en = c.get("/city/berlin/figures").text
    assert "welche Art von km" in de and "wie die Länge gemessen wird" in de
    assert "what kind of km, how length is measured" in en


# a unit that reads the same in both languages
NEUTRAL_UNITS = {"km", "%"}


def test_every_reported_unit_has_a_german_form():
    """A reported figure on a German plans page shows its unit in German: every unit of
    reports.csv has a `plan.unit.*` form, German unless it is language-neutral."""
    from velometer.app.plans_pages import row_view
    from velometer.plans.models import load_plans

    _plans, rows = load_plans(Path("config/plans"))
    bad = []
    for r in rows:
        de, en = row_view(r, True, {}, "de")["unit"], row_view(r, True, {}, "en")["unit"]
        assert en == r.unit  # English shows the unit as stored
        if de == r.unit and r.unit not in NEUTRAL_UNITS:
            bad.append(f"{r.plan_id}/{r.item_id}/{r.year}: {r.unit!r}")
    assert bad == []


def test_german_name_falls_back_to_the_english_display_name(setup):  # noqa: F811
    """A city without name_de is named on German pages exactly as on English ones (the same
    source: the database name), even when the config's name differs."""
    db_path, cfg = setup[0], setup[1]
    doc = yaml.safe_load((cfg / "cities.yaml").read_text(encoding="utf-8"))
    for city in doc["cities"]:
        if city["id"] == "paris":
            city["name"] = "Paris-Config"  # the database keeps "Paris"
    (cfg / "cities.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    from velometer.report.data import ReportData, open_readonly

    conn = open_readonly(db_path)
    try:
        en = {c.id: c.name for c in ReportData(conn, cfg).cities()}
        de = {c.id: c.name for c in ReportData(conn, cfg, "de").cities()}
    finally:
        conn.close()
    assert de["paris"] == en["paris"] == "Paris"


def test_figure_notes_de_is_read_once_until_the_file_changes(tmp_path, monkeypatch):
    import velometer.report.data as data

    (tmp_path / "external").mkdir()
    csv_path = tmp_path / "external" / "figures.csv"
    csv_path.write_text("city_id,note,note_de\nberlin,a note,eine Notiz\n", encoding="utf-8")
    data._figure_notes_de.cache_clear()
    reads = []
    real_open = Path.open

    def counting_open(self, mode="r", *a, **k):
        if mode == "r":  # reads only: write_text opens the file for writing
            reads.append(self)
        return real_open(self, mode, *a, **k)

    monkeypatch.setattr(Path, "open", counting_open)
    assert figure_notes_de(tmp_path) == {"a note": "eine Notiz"}
    assert figure_notes_de(tmp_path) == {"a note": "eine Notiz"}
    assert len(reads) == 1
    csv_path.write_text("city_id,note,note_de\nberlin,a note,eine andere Notiz\n", encoding="utf-8")
    assert figure_notes_de(tmp_path) == {"a note": "eine andere Notiz"}
    assert len(reads) == 2
