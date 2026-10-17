"""No English UI phrase on a German page (M12 spec decision 2): the visible text of every `/de/`
page, outside `lang="en"` subtrees, holds no English phrase of a phrase source. English content
shown for want of a German translation is inside `lang="en" data-fallback`, so it is no leak."""

import re
from pathlib import Path

import pytest
from markupsafe import escape

from tests.test_a11y import all_page_urls  # noqa: F401
from tests.test_app import CONTENT, _client, client, setup  # noqa: F401
from velometer import i18n
from velometer import timeseries as ts
from velometer.app import urls
from velometer.app.main import create_app
from velometer.app.narrative import bracketed
from velometer.app.series import german_explanations
from velometer.config import reader_prose
from velometer.content.check import DE, check_content_all
from velometer.reconcile import headings


def _config_phrases() -> list[str]:
    """The config's English reader prose with a German sibling, of four words or more."""
    return [en for _w, en, de in reader_prose(Path("config")) if len(en.split()) >= 4 and en != de]


def _data_ref_labels() -> list[str]:
    """Every English data-reference label: German pages show them in English (spec §4.4), so
    each must sit inside lang="en"."""
    from velometer.content import translate as tr

    labels = set()
    for path in CONTENT.rglob("*.yaml"):
        rel = path.relative_to(CONTENT)
        if tr.DE in rel.parts or rel.parts[0] in ("sources", "ui"):
            continue
        labels |= {d.label for d in tr.load_english(path).data_refs}
    return sorted(labels)


def leak_sources():
    """Every phrase source: the name and a callable giving English phrases that must not show on
    a German page outside a lang="en" subtree. "config": the English reader prose of the config
    that has a German sibling (config.reader_prose), of four words or more. "data_refs": the
    data-reference labels, which German pages show in English inside lang="en"."""
    return {
        "catalogue": i18n.leak_phrases,
        "content": lambda: i18n.content_phrases(CONTENT),
        "config": _config_phrases,
        "data_refs": _data_ref_labels,
    }


def test_no_english_phrase_on_german_pages(client, all_page_urls):  # noqa: F811
    sources = {n: f() for n, f in leak_sources().items()}
    leaks = []
    for de in (u for u in all_page_urls if urls.lang_of(u) == "de"):
        body = i18n.visible_text(client.get(de).text)
        leaks += [f"{de} [{n}]: {p!r}" for n, ps in sources.items() for p in ps if p in body]
    assert leaks == []


def test_visible_text_skips_other_languages_and_scripts():
    html = ('<html lang="de"><head><title>The whole English title here</title></head><body>'
            '<p lang="en">An English paragraph <span>with a span</span> and more words</p>'
            '<a class="lang-switch" lang="en" href="/">English</a>'
            '<p>Deutscher Text <br> bleibt</p><script>var x = "Copied to the clipboard";</script>'
            '<button aria-label="Kopieren">x</button></body></html>')  # fmt: skip
    text = i18n.visible_text(html)
    assert "English" not in text and "Copied" not in text and "more words" not in text
    assert "Deutscher Text" in text and "bleibt" in text and "Kopieren" in text


def test_phrase_sources_are_real():
    """Each source gives phrases: a source that silently returned nothing would pass every page."""
    for name, source in leak_sources().items():
        assert len(source()) > 10, name


# --- runtime and config text: what Python builds at request time (provenance lines, flag
# details) and config text beside a name (an attribution) are in no phrase source, so a sniff of
# English words guards it (`i18n.english_words`, shared with the render pass) ---

english_words = i18n.english_words


def test_no_english_words_on_german_pages(client, all_page_urls):  # noqa: F811
    """No German page has a common English word outside lang="en" (M12 Task 11, the English-leak
    proof): runtime text such as the Over time tab's provenance lines and flag details, config
    text such as an attribution, and our notes beside a source title are in no phrase source, so
    the sniff is their net. Text in another language sits inside its lang attribute."""
    pages = [u for u in all_page_urls if urls.lang_of(u) == "de"]
    assert any(u.endswith("/time") for u in pages) and any(u.endswith("/figures") for u in pages)
    assert any(not u.startswith("/de/city/") for u in pages)
    found = {u: w for u in pages if (w := english_words(client.get(u).text))}
    assert found == {}


def test_the_runtime_sniff_sees_the_over_time_generators(client):  # noqa: F811
    """The fixture's German Over time tab shows a flag detail and the comparison line, so the
    sniff above has generated text to read."""
    html = client.get("/de/city/berlin/time").text
    assert 'class="meta"' in html and i18n.t("de", "page.time.comparison") in html
    assert english_words("<p>retrieved the edits</p>") == ["edits", "retrieved", "the"]
    assert english_words("<p>activity_spike legacy_km <code>run</code></p>") == []


def test_the_sniff_reads_prose_not_codes_paths_or_names():
    """Capitals are codes (AT, NO), a slash or underscore makes an id, a name in its own form
    is no English prose; lower-case and capitalised English words are."""
    assert english_words("<p>Österreich AT, Norwegen NO, CAN RABIA</p>") == []
    assert english_words("<p>d1 · vienna/lau/current · cycle_street</p>") == []
    assert english_words("<p>Statens vegvesen (state counters)</p>") == ["counters", "state"]
    assert english_words("<p>The data of</p>") == ["The", "of"]
    name = i18n.PROPER_NAMES[0]
    assert english_words(f"<p>{name}</p>") == []
    assert english_words(f'<p lang="en">{name} and the rest</p>') == []


def _squashed(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_every_proper_name_of_the_sniff_is_shipped():
    """A name the sniff passes over is one the shipped config, content or German methodology
    holds: a name no page can show any more must leave the list, not linger as a hole."""
    root = Path(__file__).resolve().parents[1]
    files = [*root.glob("config/**/*.yaml"), *root.glob("content/**/*.yaml")]
    texts = [_squashed(f) for f in [*files, root / "docs" / "methodology.de.md"]]
    stale = [n for n in i18n.PROPER_NAMES if not any(n in text for text in texts)]
    assert stale == []


# --- German content is required (M12 Task 9): the shipped edition is complete ---

SHIPPED_DOCS = Path(__file__).resolve().parents[1] / "docs"


@pytest.fixture
def shipped_client(setup):  # noqa: F811
    """The fixture app on the shipped content and the shipped docs (the flagged-year
    explanations and their German twin), read-only."""
    db_path, cfg, maps, _docs = setup
    with _client(create_app(db_path, cfg, maps, SHIPPED_DOCS, content_dir=CONTENT)) as c:
        yield c


def test_no_fallback_on_german_pages(shipped_client, all_page_urls):  # noqa: F811
    """No German page shows English for want of German (`data-fallback`), and every flagged-year
    explanation has its stamped German entry."""
    pages = [u for u in all_page_urls if urls.lang_of(u) == "de"]
    assert len(pages) > 20
    fallback = [u for u in pages if "data-fallback" in shipped_client.get(u).text]
    assert fallback == []
    assert shipped_client.get("/data/series.json").json()["explanations_de"]["fallback"] == []
    # the fixture's flags are not the shipped ones: every shipped explanation, as series.json
    # would carry it for the real flags
    report = SHIPPED_DOCS / "review" / "m3_timeseries.md"
    notes = {k: ts.explanation(report, k) for k in headings(report.read_text(encoding="utf-8"))}
    assert len(notes) > 50
    assert german_explanations(notes, report)["fallback"] == []


def test_shipped_german_content_is_complete(fixture_db):
    """With its default `require_de`, the content check requires German for the shipped tree:
    no German problem and no note (a gap would be a note while German was optional). The English
    facts are evaluated against the fixture database here, so only the German problems count."""
    assert i18n.german_required(CONTENT)
    problems, notes = check_content_all(CONTENT, fixture_db[3], SHIPPED_DOCS)
    assert [p for p in problems if p.startswith(DE)] == []
    assert notes == []


# --- config text beside a name: our English words in an attribution, a portal list or a
# publisher have a German sibling (M12 Task 11; Oslo's "Statens vegvesen (state counters)") ---

CONFIG = Path(__file__).resolve().parents[1] / "config"


def test_counter_attributions_and_portals_have_no_english_words_in_german():
    from velometer.app.counts import attribution, counters_config, no_data_notes

    cfg, error = counters_config(CONFIG)
    assert error is None and cfg.cities and cfg.none
    for e in cfg.cities:
        assert english_words(f"<p>{attribution(e, [], 'de')[0]}</p>") == [], e.city
        assert attribution(e, [], "en")[0] == e.source  # English shows the config as written
    notes = no_data_notes(cfg, "de")
    assert {c: w for c, n in notes.items() if (w := english_words(f"<p>{n}</p>"))} == {}


def test_plan_publishers_have_no_english_words_in_german():
    from velometer.plans.models import load_plans

    plans, _rows = load_plans(CONFIG / "plans")
    found = {
        p.id: w for p in plans if (w := english_words(f"<p>{p.localised('de').publisher}</p>"))
    }
    assert found == {}
    assert all(p.localised("en").publisher == p.publisher for p in plans)


def test_german_compare_counter_notes_read_the_german_siblings():
    from velometer.app.compare import counter_lines

    payload = {
        "cities": {"oslo": {"name": "Oslo"}, "warsaw": {"name": "Warschau"}},
        "counters": {
            "cities": {
                "oslo": {"line": True, "series": "counts", "source": "Statens vegvesen (state "
                         "counters)", "source_de": "Statens vegvesen (staatliche Zählstellen)",
                         "licence": "NLOD", "points": [{"year": 2019, "idx": 100.0}]},
            },
            "none": {"warsaw": "no open counter data found"},
            "none_de": {"warsaw": "keine offenen Zähldaten gefunden"},
        },
    }  # fmt: skip
    _labels, _values, de = counter_lines(payload, ["oslo", "warsaw"], "de")
    assert any("staatliche Zählstellen" in n for n in de) and not any("state" in n for n in de)
    assert "Warschau: keine offenen Zähldaten gefunden" in de
    _labels, _values, en = counter_lines(payload, ["oslo", "warsaw"], "en")
    assert any("(state counters)" in n for n in en)


def test_shipped_german_methodology_has_no_english_words(shipped_client):
    """The German methodology renders the stored provenance with our words in German ("union
    of 17 LAU" is "Vereinigung von 17 LAU") and the counter attributions in German."""
    assert english_words(shipped_client.get("/de/methodology").text) == []


def test_german_figure_citations_name_an_unlabelled_metric_by_its_id(client):  # noqa: F811
    """A figure's Cite title on a German page names a metric without a label by its id (as the
    table's code cell), never the de-underscored id, which reads as English words; English
    keeps its form."""
    de, en = (client.get(f"{p}/city/berlin/figures").text for p in ("/de", ""))
    ids = {i for i in re.findall(r"<code>([a-z0-9_@~]+)</code>", de) if "_" in i}
    assert ids  # the fixture's figures table shows unlabelled metric ids
    spaced = {i: i.replace("_", " ") for i in ids}
    assert [i for i, s in spaced.items() if f", {s} (" in de] == []
    assert any(f", {s} (" in en for s in spaced.values())


def test_german_methodology_sets_a_narrow_space_before_percent():
    """The German edition writes 5 %, with U+202F, never a plain space, before a percent sign."""
    text = (SHIPPED_DOCS / "methodology.de.md").read_text(encoding="utf-8")
    assert "\u202f%" in text  # the page has percentages, so the rule has something to read
    assert re.findall(r"\d %", text) == []


def test_tab_names_in_the_german_methodology_are_the_german_tab_labels():
    """Every tab the German methodology names (Reiter „…“) is named by its German label
    (`city.tab.*`), never by the English one ("Figures", "Counts")."""
    text = (SHIPPED_DOCS / "methodology.de.md").read_text(encoding="utf-8")
    quoted = re.findall(r"Reiter „([^“]+)“", text)
    assert quoted  # the page names tabs, so the rule has something to read
    labels = {v for k, v in i18n.catalogue("de").items() if k.startswith("city.tab.")}
    assert [q for q in quoted if q not in labels] == []


def test_content_phrases_split_at_an_original_term_as_at_a_quotation():
    # M13: an original term (`<i lang="da">…</i>`, Task 7) is no English, and its markup is not
    # on the page: a phrase holding it could never be found, so it never caught a leak
    text = (
        'Our Copenhagen figure, 401 km of <i lang="da">cykelsti</i> in 2025, comes from the '
        'city\'s own mobility report of the year, as we read it. Then <i\n lang="nb">'
        "kommunale veger</i> follow."
    )
    parts = i18n._sentences(text, 3)
    assert parts == [
        "Our Copenhagen figure, 401 km of",
        "in 2025, comes from the city's own mobility report of the year, as we read it.",
    ]
    assert not [p for p in i18n.content_phrases(CONTENT) if "<" in p]


# --- M12-1: names in their own language carry it, so the sniff needs no list for them ---


def test_names_with_a_language_are_written_in_it_on_german_pages(client):  # noqa: F811
    from velometer.content.loader import load_organisations
    from velometer.plans.models import load_plans

    orgs = load_organisations(CONTENT / "organisations", errors={})
    assert orgs and all(o.lang for o in orgs.values())  # every shipped profile names its language
    html = client.get("/de/organisations").text
    for o in orgs.values():
        name = bracketed(o.name, o.bracket_lang)  # a bracket in another language: its own span
        assert f'<h2 lang="{o.lang}">{name}</h2>' in html, o.id
    plans, _rows = load_plans(CONFIG / "plans")
    oslo = next(p for p in plans if p.id == "oslo_sykkelveinettet_2018")
    assert oslo.title_lang == "nb" and oslo.localised("de").title_lang == "nb"
    vienna = next(p for p in plans if p.title_de)  # our German title is not the document's
    assert vienna.localised("de").title_lang is None
    plans_html = client.get("/de/plans").text
    shown = [p.localised("de") for p in plans if str(escape(p.localised("de").title)) in plans_html]
    assert any(p.title_lang for p in shown)
    for p in shown:
        title = re.escape(str(escape(p.title)))
        assert re.search(rf'(?:lang="{p.title_lang}")?>{title}<', plans_html), p.id
        if p.title_lang:
            assert re.search(rf'lang="{p.title_lang}">{title}<', plans_html), p.id
    name = "Plan for sykkelveinettet i Oslo"
    assert name not in i18n.PROPER_NAMES
    assert english_words(f"<p>{name}</p>")  # untagged, the sniff would see its English
    assert english_words(f'<p lang="nb">{name}</p>') == []
    # Copenhagen's English bracket: test_copenhagens_english_bracket_is_english_on_every_page


def test_a_counter_publisher_is_written_in_its_language_unless_ours_is_shown():
    from velometer.app.counts import counters_config

    cfg, error = counters_config(CONFIG)
    assert error is None
    by_city = {e.city: e for e in cfg.cities}
    assert by_city["berlin"].source_lang_in("de") == "de"
    assert by_city["helsinki"].source_lang_in("en") == "en"
    oslo = by_city["oslo"]  # "Statens vegvesen (state counters)": our words beside the name
    assert oslo.source_lang_in("en") == "nb" and oslo.source_bracket_lang_in("en") == "en"
    assert oslo.source_lang_in("de") is None  # our German attribution is in the page's language
    assert oslo.source_bracket_lang_in("de") is None


@pytest.mark.parametrize("bad", ["d a", "DE", "deutsch-", ""])
def test_a_name_language_must_be_a_language_tag(bad):
    from velometer.content.models import name_lang

    with pytest.raises(ValueError, match="BCP 47"):
        name_lang(bad, "lang")
    assert name_lang(None, "lang") is None and name_lang("pt-BR", "lang") == "pt-BR"


# --- M13 fix round (review 10, I1): a bracket in another language than the name's lead ---

COPENHAGEN_DE = 'Københavns Kommune (<span lang="en">City of Copenhagen</span>)'


def test_a_bracket_in_another_language_than_the_lead_is_marked_in_it():
    assert bracketed("Københavns Kommune (City of Copenhagen)", "en") == COPENHAGEN_DE
    assert bracketed("A & B (C)", None) == "A &amp; B (C)"  # no bracket language: the name
    assert bracketed("A (B) & C", "en") == "A (B) &amp; C"  # no closing bracket: the name
    assert bracketed("<x> (<y>)", "en") == '&lt;x&gt; (<span lang="en">&lt;y&gt;</span>)'


def test_a_bracket_language_needs_a_bracket():
    from velometer.content.models import Organisation

    base = {"id": "x", "name": "Plain Name", "lang": "da", "kind": "official",
            "url": "https://example.org/", "sections": []}  # fmt: skip
    with pytest.raises(ValueError, match="no bracketed form"):
        Organisation(**base, bracket_lang="en")
    with pytest.raises(ValueError, match="BCP 47"):
        Organisation(**{**base, "name": "A (B)"}, bracket_lang="E N")
    assert Organisation(**{**base, "name": "A (B)"}, bracket_lang="en").bracket_lang == "en"


def test_copenhagens_english_bracket_is_english_on_every_page_that_names_it(client):  # noqa: F811
    from velometer.content.loader import load_organisations

    kk = load_organisations(CONTENT / "organisations", errors={})["copenhagen_kommune"]
    assert (kk.lang, kk.bracket_lang) == ("da", "en")
    for path in ("/de/organisations", "/organisations"):
        html = client.get(path).text
        assert f'<h2 lang="da">{COPENHAGEN_DE}</h2>' in html, path
        assert '<h2 lang="da">Københavns Kommune (City of Copenhagen)' not in html, path
    # the sniff: tagged this way the English words are no leak, so no PROPER_NAMES entry
    assert english_words(f'<p lang="da">{COPENHAGEN_DE}</p>') == []
    assert "City of Copenhagen" not in " ".join(i18n.PROPER_NAMES)


def test_helsinkis_finnish_bracket_is_finnish_in_the_counts_attribution(setup):  # noqa: F811
    import yaml

    from tests.test_app_m8_counts import _seed
    from velometer.app.counts import counters_config

    cfg_all, _ = counters_config(CONFIG)
    hel = next(e for e in cfg_all.cities if e.city == "helsinki")
    assert (hel.source_lang, hel.source_bracket_lang) == ("en", "fi")
    assert hel.source_bracket_lang_in("de") == "fi"
    # Berlin's fixture attribution, given Helsinki's form (the fixture has no Helsinki)
    db_path, cfg = setup[0], setup[1]
    assert cfg.resolve() != CONFIG.resolve(), "never edit the real config"
    doc = yaml.safe_load((cfg / "counters.yaml").read_text(encoding="utf-8"))
    berlin = next(e for e in doc["cities"] if e["city"] == "berlin")
    berlin.pop("source_de", None)
    berlin.update(source=hel.source, source_lang="en", source_bracket_lang="fi")
    (cfg / "counters.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    _seed(db_path)
    with _client(create_app(*setup, content_dir=CONTENT)) as c:
        html = c.get("/de/city/berlin/counts").text
    want = ('lang="en">City of Helsinki, Urban Environment Division '
            '(<span lang="fi">Helsingin kaupunkiympäristön toimiala</span>)</a>')  # fmt: skip
    assert want in html


def test_search_names_an_organisations_language_and_its_brackets(client):  # noqa: F811
    from velometer.content.loader import load_organisations

    orgs = load_organisations(CONTENT / "organisations", errors={})
    for path in ("/data/search.json", "/de/data/search.json"):
        entries = {e["url"]: e for e in client.get(path).json() if e["kind"] == "organisation"}
        assert entries
        for o in orgs.values():
            e = entries[f"/organisations#{o.id}"]
            assert e["lang"] == o.lang, (path, o.id)
            assert e.get("bracket_lang") == o.bracket_lang, (path, o.id)
    city = next(e for e in client.get("/data/search.json").json() if e["kind"] == "city")
    assert "lang" not in city  # a city's label is in the page's language


# --- M13 fix round (review 10, M3): a plan title without a link still carries its language ---


def test_a_plan_title_without_a_web_link_is_a_span_in_its_language(setup):  # noqa: F811
    import yaml

    cfg = setup[1]
    assert cfg.resolve() != CONFIG.resolve(), "never edit the real config"
    path = cfg / "plans" / "plans.yaml"
    plans = yaml.safe_load(path.read_text(encoding="utf-8"))
    rvp = next(p for p in plans if p["id"] == "berlin_rvp_2021")
    rvp.update(url="ftp://example.org/rvp.pdf", title="Radverkehrsplan", title_lang="de")
    path.write_text(yaml.safe_dump(plans, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with _client(create_app(*setup, content_dir=CONTENT)) as c:
        for page in ("/plans", "/plans/berlin", "/de/plans", "/de/plans/berlin"):
            html = c.get(page).text
            assert '<span lang="de">Radverkehrsplan</span>' in html, page
            assert "ftp://example.org" not in html, page
