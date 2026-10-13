"""German content on German pages (M12 spec §4.4): translated text renders in German, every
string still English renders inside `lang="en" data-fallback`, and the shared data files carry
the German siblings the JS swaps in."""

import json
import re
import shutil
from pathlib import Path

import pytest

from tests.conftest import app_for, make_source
from tests.content_util import fake_translate
from tests.test_app import CONTENT, setup  # noqa: F401
from velometer.app import narrative

MARK = "Übersetzt: "  # fake_translate's prefix: German, and found nowhere else on a page
FALLBACK_P = re.compile(r'<(p|h[1-6]|span)\b[^>]*\blang="en"[^>]*\bdata-fallback')


def _content(tmp_path, drop=frozenset()):
    content = tmp_path / "content"
    shutil.copytree(CONTENT, content)
    en = content / "narratives" / "berlin.yaml"
    fake_translate(en, content / "narratives" / "de" / "berlin.yaml", drop=drop)
    return content


def _english_only(tmp_path):
    """A copy of the shipped content without any German translation file (every `de/`
    directory removed): the state of a tree nobody has translated yet."""
    content = tmp_path / "english_only"
    shutil.copytree(CONTENT, content)
    for de_dir in sorted(content.rglob("de"), reverse=True):
        if de_dir.is_dir():
            shutil.rmtree(de_dir)
    return content


def _berlin(setup, content):  # noqa: F811
    with app_for(setup, content=content) as c:
        r = c.get("/de/city/berlin")
    assert r.status_code == 200
    return r.text


def test_translated_paragraph_renders_german(setup, tmp_path):  # noqa: F811
    html = _berlin(setup, _content(tmp_path))
    assert MARK in html
    assert not re.search(r"<(?:p|h[1-6])\b[^>]*\bdata-fallback", html)  # glosses: Task 9


def test_missing_german_paragraph_falls_back_in_english(setup, tmp_path):  # noqa: F811
    html = _berlin(setup, _content(tmp_path, drop=frozenset({"sections.0.paragraphs.0"})))
    assert len(re.findall(r'<p\b[^>]*\blang="en"[^>]*\bdata-fallback', html)) == 1


def test_missing_german_heading_falls_back_in_english(setup, tmp_path):  # noqa: F811
    html = _berlin(setup, _content(tmp_path, drop=frozenset({"sections.0.heading"})))
    assert len(re.findall(r'<h[2-4]\b[^>]*\blang="en"[^>]*\bdata-fallback', html)) == 1


def test_missing_german_file_is_never_a_500(setup, tmp_path):  # noqa: F811
    content = _content(tmp_path)
    (content / "narratives" / "de" / "berlin.yaml").unlink()
    assert FALLBACK_P.search(_berlin(setup, content))


def test_broken_german_file_shows_the_english_and_no_note(setup, tmp_path):  # noqa: F811
    content = _content(tmp_path)
    (content / "narratives" / "de" / "berlin.yaml").write_text("title: [", encoding="utf-8")
    html = _berlin(setup, content)
    assert FALLBACK_P.search(html) and 'class="note"' not in html.split("story-layout")[1][:400]


def test_english_page_has_no_fallback_marks(setup, tmp_path):  # noqa: F811
    with app_for(setup, content=_content(tmp_path)) as c:
        html = c.get("/city/berlin").text
    assert "data-fallback" not in html and MARK not in html


def test_pullquote_shows_gloss_de_on_german_pages():
    html = str(narrative.pullquote({"s": make_source("pl", gloss_de="Glosse")}, "s/e", lang="de"))
    assert '<span class="gloss" lang="de">Glosse</span>' in html and ">Gloss<" not in html


def test_pullquote_falls_back_to_gloss_en_in_english():
    html = str(narrative.pullquote({"s": make_source("pl")}, "s/e", lang="de"))
    assert re.search(r'<span class="gloss" lang="en" data-fallback[^>]*>Gloss</span>', html)


def test_german_quote_has_no_gloss_on_german_pages():
    html = str(narrative.pullquote({"s": make_source("de")}, "s/e", lang="de"))
    assert 'class="gloss"' not in html


def test_missing_german_explanation_falls_back_in_english(setup):  # noqa: F811
    from tests.test_app import EXPLANATION
    from velometer import timeseries as ts

    _db, _cfg, _maps, docs = setup
    en, de = docs / "review" / "m3_timeseries.md", docs / "review" / "m3_timeseries.de.md"
    # a German file with paris/lau/2020 only: the fixture flag berlin/lau/2025 has no German
    de.write_text("# M3\n\n### paris/lau/2020\n\nKein Fixture-Flag.\n", encoding="utf-8")
    ts.stamp_explanations(en, de)
    with app_for(setup) as c:
        d = c.get("/data/series.json").json()
        html = c.get("/de/city/berlin/time").text
    assert set(d["explanations_de"]["timeseries"]) == set(d["explanations"]["timeseries"])
    assert "berlin/lau/2025" in d["explanations_de"]["fallback"]
    assert "paris/lau/2020" not in d["explanations_de"]["fallback"]
    assert re.search(r'lang="en"[^>]*data-fallback[^>]*>(?:(?!</).)*' + re.escape(EXPLANATION[:20]),
                     html, re.S)  # fmt: skip


def test_stamped_german_explanation_renders_german(setup):  # noqa: F811
    from velometer import timeseries as ts

    _db, _cfg, _maps, docs = setup
    en, de = docs / "review" / "m3_timeseries.md", docs / "review" / "m3_timeseries.de.md"
    de.write_text("# M3\n\n### berlin/lau/2025\n\nDeutsche Erklärung.\n", encoding="utf-8")
    ts.stamp_explanations(en, de)
    with app_for(setup) as c:
        d = c.get("/data/series.json").json()
        html = c.get("/de/city/berlin/time").text
    assert d["explanations_de"]["timeseries"]["berlin/lau/2025"] == "Deutsche Erklärung."
    assert d["explanations_de"]["fallback"] == []
    assert "Deutsche Erklärung." in html and "data-fallback" not in html


def test_unstamped_german_explanation_falls_back_in_english(setup):  # noqa: F811
    """A German entry without its stamp is not known to translate today's English: English."""
    from tests.test_app import EXPLANATION

    _db, _cfg, _maps, docs = setup
    de = docs / "review" / "m3_timeseries.de.md"
    de.write_text("# M3\n\n### berlin/lau/2025\n\nUngestempelt.\n", encoding="utf-8")
    with app_for(setup) as c:
        d = c.get("/data/series.json").json()
        html = c.get("/de/city/berlin/time").text
    assert d["explanations_de"]["fallback"] == ["berlin/lau/2025"]
    assert "Ungestempelt." not in html and EXPLANATION[:20] in html


def test_series_json_has_every_de_field(setup):  # noqa: F811
    with app_for(setup, name_de={"berlin": "Berlin-Test"}) as c:
        d = c.get("/data/series.json").json()
    berlin = d["cities"]["berlin"]
    assert berlin["name"] == "Berlin" and berlin["name_de"] == "Berlin-Test"
    assert {"country_name_de"} <= set(berlin)
    assert {"headline_unit_de", "presets_de", "explanations_de"} <= set(d)
    assert "none_de" in d["counters"]


def test_series_json_de_fields_are_german(setup):  # noqa: F811
    from velometer.report.data import headline_unit

    with app_for(setup) as c:
        d = c.get("/data/series.json").json()
    assert d["headline_unit_de"] == headline_unit("de") != d["headline_unit"]
    assert d["cities"]["berlin"]["country_name_de"] == "Deutschland"
    assert set(d["presets_de"]) == set(d["presets"])
    assert d["presets_de"] != d["presets"]


def test_german_search_labels(setup):  # noqa: F811
    with app_for(setup, name_de={"berlin": "Berlin-Test"}) as c:
        de = c.get("/de/data/search.json").json()
    assert any(e["label"] == "Methodik" for e in de)
    assert any("Berlin-Test" in e["label"] for e in de if e["kind"] == "city")


def test_german_search_kinds_are_labelled_in_german(setup):  # noqa: F811
    """The result's kind ("city", "story") shows in the page's language: the German index names
    it from the catalogue; the English index keeps its M11 form, with no label field."""
    from velometer.i18n import t

    with app_for(setup) as c:
        de = c.get("/de/data/search.json").json()
        en = c.get("/data/search.json").json()
    assert {e["kind"] for e in de} >= {"page", "city", "country"}
    for e in de:
        assert e["kind_label"] == t("de", f"search.kind.{e['kind']}")
        assert e["kind_label"] != t("en", f"search.kind.{e['kind']}")
    assert all("kind_label" not in e for e in en)


def test_german_provenance_line_on_the_over_time_tab(setup):  # noqa: F811
    with app_for(setup) as c:
        de = c.get("/de/city/berlin/time").text
        en = c.get("/city/berlin/time").text
    assert "history runs" in en and "Läufe der Zeitreihe" in de
    assert "history runs" not in de and "held constant" not in de


def test_provenance_line_english_is_the_review_page_line(fixture_db):
    """The catalogue form gives the English line the review page has always had."""
    from velometer import timeseries as ts

    _db, _cfg, conn, data = fixture_db
    cs = data.series("berlin", "lau")
    line = ts.provenance_line(conn, data.selector, cs.set_md5, cs.points)
    sel = data.selector
    assert line.startswith("history runs ") and line == cs.provenance
    assert (
        f" · history set `{cs.set_md5[:8]}` · classifier {sel.version} `{sel.parameters}`" in line
    )
    assert f" · config `{sel.config_sha256[:12]}` · " in line


# --- German organisation profiles, explainer and documents ---------------------------------


def _translate_all(content: Path, kind: str, drop=frozenset()) -> None:
    for en in sorted((content / kind).glob("*.yaml")):
        fake_translate(en, content / kind / "de" / en.name, drop=drop)


def test_organisation_profile_dimension_and_heading_fall_back(setup, tmp_path):  # noqa: F811
    content = tmp_path / "content"
    shutil.copytree(CONTENT, content)
    en = next((content / "organisations").glob("*.yaml"))
    from velometer.content import translate as tr

    model = tr.load_english(en)
    dim = next(p for p, _ in tr.walk(model) if ".dimensions." in p)
    drop = frozenset({dim, "sections.0.heading"})
    fake_translate(en, content / "organisations" / "de" / en.name, drop=drop)
    with app_for(setup, content=content) as c:
        html = c.get("/de/organisations").text
    org = html.split(f'id="{model.id}"', 1)[1].split('<section class="org"', 1)[0]
    assert MARK in org
    assert len(re.findall(r'<h3\b[^>]*lang="en"[^>]*data-fallback', org)) == 1
    assert len(re.findall(r'<dd><span lang="en" data-fallback>', org)) == 1


def test_explainer_intro_and_data_ref_label_fall_back(setup, tmp_path):  # noqa: F811
    content = tmp_path / "content"
    shutil.copytree(CONTENT, content)
    from velometer.content import translate as tr

    en = content / "explainer.yaml"
    model = tr.load_english(en)
    refs = [p for p, _ in tr.walk(model) if p.startswith("data_refs.")]
    drop = frozenset({"intro.0", "title", *refs[:1]})
    fake_translate(en, content / "de" / "explainer.yaml", drop=drop)
    with app_for(setup, content=content) as c:
        html = c.get("/de/differences").text
    assert MARK in html
    assert re.search(r'<h1 lang="en" data-fallback>', html)
    assert len(re.findall(r'<p lang="en" data-fallback>', html)) == 1
    if refs:
        assert '<span lang="en" data-fallback>' in html.split('class="citations drefs"')[1]


def test_untranslated_pages_mark_all_english_content(setup, tmp_path):  # noqa: F811
    """With no German files at all, every content string on a German page is a marked fallback:
    the narrative, the explainer, the profiles, the counters and plan texts."""
    with app_for(setup, content=_english_only(tmp_path)) as c:
        for url in ["/de/city/berlin", "/de/differences", "/de/organisations", "/de/stories",
                    "/de/plans/berlin"]:  # fmt: skip
            html = c.get(url).text
            assert FALLBACK_P.search(html), url


# --- notes without a German sibling ---------------------------------------------------------


def test_gap_note_without_german_falls_back_in_english(fixture_db, monkeypatch):
    """A figure note with a figures.csv `note_de` shows in German on a German Figures tab; any
    other (a loader's generated note) is the English one, marked as a fallback."""
    from velometer.config import load_differences
    from velometer.report.data import figure_notes_de
    from velometer.report.differences import difference_rows

    _db, cfg, _conn, data = fixture_db
    notes_de = figure_notes_de(cfg)
    de = data.with_lang("de")
    some = next(iter(notes_de))
    assert de.note_in_lang(some) == (notes_de[some], False)
    assert de.note_in_lang("QECIO v2.10 file md5 0123") == ("QECIO v2.10 file md5 0123", True)
    assert data.note_in_lang("QECIO v2.10 file md5 0123") == ("QECIO v2.10 file md5 0123", False)
    from velometer.report import data as report_data

    stored = report_data.fetch_external_figures

    def with_notes(conn, city_id):  # two reported figures: one note with a sibling, one without
        rows = stored(conn, city_id)
        extra = {"city_id": city_id, "source": "official", "metric_name": "network_km",
                 "value": 1.0, "unit": "km", "reference_date": None,
                 "network_scope": "whole_network", "length_basis": "unknown",
                 "source_url": "https://example.org/", "retrieved_at": "2026-10-01"}  # fmt: skip
        return rows + [
            report_data.ExternalFigure(**extra, note=some),
            report_data.ExternalFigure(**extra, note="a generated loader note"),
        ]

    monkeypatch.setattr(report_data, "fetch_external_figures", with_notes)
    diffs = load_differences(cfg / "differences.yaml")
    en_rows = difference_rows(data, "berlin", diffs, "en")
    de_rows = difference_rows(data, "berlin", diffs, "de")
    assert not any(r.note_fallback for r in en_rows)
    assert sum(r.note_fallback for r in de_rows) == 1
    for en, de_row in zip(en_rows, de_rows, strict=True):
        if en.note in notes_de:
            assert (de_row.note, de_row.note_fallback) == (notes_de[en.note], False)
        elif en.note:
            assert (de_row.note, de_row.note_fallback) == (en.note, True)


def test_suspect_note_lookup_falls_back_in_english():
    from velometer.app.plans_pages import note_in

    notes = {"stored as printed": "wie gedruckt"}
    assert note_in("stored as printed", "de", notes) == ("wie gedruckt", False)
    assert note_in("other note", "de", notes) == ("other note", True)
    assert note_in("stored as printed", "en", notes) == ("stored as printed", False)


def test_suspect_note_without_german_is_marked_on_german_plan_pages(setup):  # noqa: F811
    with app_for(setup) as c:
        de = c.get("/de/plans/berlin").text
        en = c.get("/plans/berlin").text
    notes = re.findall(r'<span class="meta suspect-note"([^>]*)>', de)
    assert notes and all('lang="en" data-fallback' in a for a in notes)
    assert all(a == "" for a in re.findall(r'<span class="meta suspect-note"([^>]*)>', en))


def test_every_report_note_without_german_is_marked_on_the_german_plan_page(setup):  # noqa: F811
    """Not only the suspect notes: the note row under each figure of the Berlin plan's series
    is English on a German page until reports_notes_de.yaml has its sibling."""
    with app_for(setup) as c:
        de = c.get("/de/plans/berlin").text
        en = c.get("/plans/berlin").text
    rows = re.findall(r'<tr class="note-row"><td ([^>]*)>', de)
    assert rows and all('lang="en" data-fallback' in a for a in rows)
    assert all("lang=" not in a for a in re.findall(r'<tr class="note-row"><td ([^>]*)>', en))


def test_a_region_is_never_named_after_a_fallback_heading_on_a_german_page():
    from velometer.app.regions import name_scroll_regions

    page = (
        '<h2>Deutsche Überschrift</h2><h2 lang="en" data-fallback>English heading</h2>'
        '<div class="scroll"><table></table></div>'
    )
    assert 'aria-label="Deutsche Überschrift"' in name_scroll_regions(page, "de")
    assert 'aria-label="English heading"' in name_scroll_regions(page, "en")
    inner = '<div class="scroll"><h3 lang="en" data-fallback>Only English</h3><table></table></div>'
    assert "Only English" not in name_scroll_regions(inner, "de").split(">", 1)[0]


def test_report_notes_de_must_name_a_reports_csv_note(tmp_path):
    from velometer.config import ConfigError
    from velometer.plans.models import REPORT_NOTES_DE_FILE, load_plans, load_report_notes_de

    plans = tmp_path / "plans"
    shutil.copytree(Path("config/plans"), plans)
    _p, rows = load_plans(plans)
    note = next(r.note for r in rows if r.suspect and r.note)
    (plans / REPORT_NOTES_DE_FILE).write_text(json.dumps({note: "Deutsch."}), encoding="utf-8")
    assert load_report_notes_de(plans, rows) == {note: "Deutsch."}
    (plans / REPORT_NOTES_DE_FILE).write_text(json.dumps({"no such note": "x"}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_report_notes_de(plans, rows)


# --- tier map images ---------------------------------------------------------------------


def test_german_tiers_tab_links_the_german_image(setup):  # noqa: F811
    _db, _cfg, maps, _docs = setup
    (maps / "berlin_lau.de.png").write_bytes((maps / "berlin_lau.png").read_bytes())
    with app_for(setup) as c:
        de = c.get("/de/city/berlin/tiers").text
        en = c.get("/city/berlin/tiers").text
        png = c.get("/maps/berlin_lau.de.png")
        geo = c.get("/maps/berlin_lau.de.geojson")
    assert "/maps/berlin_lau.de.png" in de and "/maps/berlin_lau.png" not in de
    assert "/maps/berlin_lau.png" in en and ".de.png" not in en
    assert png.status_code == 200 and geo.status_code == 404


def test_city_names_fixture_is_cities_yaml():
    """tests/city_names.json (the node search test reads it) is every city's name forms."""
    from velometer.config import load_cities

    names = json.loads(Path("tests/city_names.json").read_text(encoding="utf-8"))
    assert names == {c.id: list(c.names) for c in load_cities(Path("config/cities.yaml"))}


def test_sources_dimension_cells_fall_back_and_translate(setup, tmp_path):  # noqa: F811
    content = _english_only(tmp_path)
    with app_for(setup, content=content) as c:
        before = c.get("/de/sources").text
    assert '<td data-label="' in before and '<span lang="en" data-fallback>' in before
    _translate_all(content, "organisations")
    with app_for(setup, content=content) as c:
        after = c.get("/de/sources").text
        english = c.get("/sources").text
    table = after.split("<tbody>", 1)[1].split("</table>", 1)[0]
    assert MARK in table and "data-fallback" not in table
    assert MARK not in english and "data-fallback" not in english
