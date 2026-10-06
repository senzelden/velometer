"""M7 app foundation: navigation, CSP, the series endpoint, Overview and Cities (Task 10)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_app import (  # noqa: F401 - `setup`, `subarea_setup` are fixtures
    BASE_URL,
    EXPLANATION,
    ROUTES,
    _client,
    _text,
    setup,
    subarea_client,
    subarea_setup,
)
from velometer.app.cache import fingerprint
from velometer.app.main import create_app

CSP = (
    "default-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; "
    "style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'"
)
M7_ROUTES = ROUTES + ["/cities", "/data/series.json", "/compare", "/city/berlin/panel"]
# an inline <script> with a body; JSON data blocks are not executed and are allowed under the CSP
INLINE_SCRIPT = re.compile(
    r"<script(?![^>]*\bsrc=)(?![^>]*\btype=\"application/json\")[^>]*>\s*\S", re.I
)
STATIC = Path(__file__).parents[1] / "src" / "velometer" / "app" / "static"
TEMPLATES = STATIC.parent / "templates"


@pytest.fixture
def client(setup):  # noqa: F811 - the imported fixture
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        yield c


def _nav(html: str) -> str:
    return html[html.index('<nav class="site-nav"') : html.index("</nav>", html.index("site-nav"))]


def _current_items(html: str) -> list[str]:
    """The text of every nav element marked current."""
    nav = _nav(html)
    found = re.findall(
        r'<(a|summary)\b[^>]*aria-current="(?:page|true)"[^>]*>(.*?)</\1>', nav, re.S
    )
    return [_text(body).strip() for _tag, body in found]


@pytest.mark.parametrize("path", M7_ROUTES)
def test_every_route_is_200_with_the_csp_header(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    assert r.headers["content-security-policy"] == CSP


def test_errors_and_static_files_carry_the_csp_too(client):
    for path in ["/city/nowhere", "/static/app.css", "/static/js/chart.js"]:
        assert client.get(path).headers["content-security-policy"] == CSP, path
    refused = client.get("/", headers={"Host": "attacker.example"})
    assert refused.status_code == 400
    assert refused.headers["content-security-policy"] == CSP


def test_an_unhandled_exception_500_carries_the_csp_too(setup):  # noqa: F811
    db_path, cfg, maps, docs = setup
    app = create_app(db_path, cfg, maps, docs)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as c:
        r = c.get("/boom")
    assert r.status_code == 500
    assert r.headers["content-security-policy"] == CSP


@pytest.mark.parametrize("path", M7_ROUTES)
def test_no_inline_script_with_a_body(client, path):
    assert not INLINE_SCRIPT.search(client.get(path).text), path


def test_the_inline_script_pattern_catches_inline_code_and_spares_json():
    assert INLINE_SCRIPT.search("<script>alert(1)</script>")
    assert INLINE_SCRIPT.search('<script type="module">\n import x from "y"</script>')
    assert not INLINE_SCRIPT.search('<script type="module" src="/static/js/nav.js"></script>')
    assert not INLINE_SCRIPT.search('<script type="application/json" id="c">{"a": 1}</script>')


# what the CSP blocks in markup: style attributes, event-handler attributes, javascript: URLs
INLINE_CODE = re.compile(
    r"""\sstyle=|\son[a-z]+\s*=|(?:href|src|action)\s*=\s*["']?\s*javascript:""", re.I
)


@pytest.mark.parametrize("path", M7_ROUTES)
def test_no_rendered_page_has_inline_style_handlers_or_javascript_urls(client, path):
    assert not INLINE_CODE.search(client.get(path).text), path


def test_the_inline_code_pattern_catches_each_kind_and_spares_prose():
    for bad in [
        '<p style="color: red">',
        '<a onclick="x()">',
        "<img src=a onerror = x>",
        '<a href="javascript:alert(1)">',
    ]:
        assert INLINE_CODE.search(bad), bad
    assert not INLINE_CODE.search('<p class="once">on = 3, the front</p><a href="/online">')


def test_no_template_has_inline_style_attributes():
    """The source guard behind the rendered check: no template writes style=/on*= itself."""
    for path in TEMPLATES.rglob("*.html"):
        assert not INLINE_CODE.search(path.read_text()), path.name


def test_series_json_has_the_spike_keys_and_ends_each_series_at_current(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    payload = client.get("/data/series.json").json()
    assert {"cities", "series", "bezirke", "presets", "explanations"} <= set(payload)
    labels = [p["label"] for p in payload["series"]["berlin/lau"]]
    assert labels[-1] == "current"
    assert labels[:-1] == sorted(labels[:-1])
    point = payload["series"]["berlin/lau"][-1]
    for key in ["label", "run_id", "osm", *"ABCDE", "ab_km", "headline", "ecf_qecio"]:
        assert key in point, key
    assert {"clean_cities", "flags"} <= set(point)
    assert point["osm"] == data.current("berlin", "lau").osm_timestamp[:10]
    assert point["ab_km"] == pytest.approx(data.current("berlin", "lau").ab_km, abs=1e-3)
    assert set(payload["cities"]) == {c.id for c in data.cities()}
    assert payload["cities"]["berlin"]["country_name"] == "Germany"
    assert payload["presets"] == data.preset_labels()


def test_series_json_explains_the_flagged_years(client):
    payload = client.get("/data/series.json").json()
    flagged = [p for p in payload["series"]["berlin/lau"] if p["flags"]]
    assert [p["label"] for p in flagged] == ["2025"]  # the fixture's one LAU flag
    assert "Fixture cause" in payload["explanations"]["timeseries"]["berlin/lau/2025"]
    assert "paris/lau/2020" not in payload["explanations"]["timeseries"]  # not a flag


def test_index_and_cities_link_every_trusted_city_and_mark_the_nav(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    for path, current in [("/", ["Overview"]), ("/cities", ["Cities ▾"])]:
        html = client.get(path).text
        main = html[html.index("<main") :]
        for c in data.cities():
            assert f'href="/city/{c.id}"' in main, (path, c.id)
        assert _current_items(html) == current, path
    assert _current_items(client.get("/methodology").text) == ["Methodology"]
    assert _current_items(client.get("/city/berlin").text) == ["Cities ▾"]


def test_nav_has_the_five_items_in_order(client):
    nav = _text(_nav(client.get("/").text))
    items = ["Overview", "Compare", "Cities ▾", "Stories", "Methodology"]
    positions = [nav.find(i) for i in items]
    assert -1 not in positions and positions == sorted(positions)


def test_cities_page_groups_by_country_name(client):
    html = client.get("/cities").text
    main = html[html.index("<main") :]
    groups = re.findall(r"<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|</main>)", main, re.S)
    by_country = {name: body for name, body in groups}
    assert set(by_country) == {"Germany", "France"}
    assert 'href="/city/berlin"' in by_country["Germany"]
    assert 'href="/city/paris"' in by_country["France"]
    assert "/city/paris" not in by_country["Germany"]


def test_no_response_references_vega(client):
    for path in M7_ROUTES + ["/static/js/overview.js", "/static/js/nav.js"]:
        assert "/static/vendor/vega" not in client.get(path).text, path
        assert "vegaEmbed" not in client.get(path).text, path
    assert not list((STATIC / "vendor").glob("vega*"))
    versions = (STATIC / "vendor" / "VERSIONS").read_text().splitlines()
    packages = [line.split()[0] for line in versions if line.strip() and not line.startswith("#")]
    assert packages == ["leaflet"]


def test_breadcrumbs_lead_back_to_the_overview(client):
    html = client.get("/city/berlin").text
    crumbs = re.search(r'<nav class="crumbs" aria-label="Breadcrumb">(.*?)</nav>', html, re.S)
    assert crumbs
    assert 'href="/"' in crumbs.group(1) and 'href="/cities"' in crumbs.group(1)
    assert 'aria-current="page"' in crumbs.group(1)


def test_overview_charts_have_a_server_side_table(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    html = client.get("/").text
    assert 'data-chart="overview-lines"' in html
    assert '<script type="module" src="/static/js/overview.js"></script>' in html
    ranking = html[html.index('id="ranking"') :]
    ranking = ranking[: ranking.index("</table>")]
    headline = next(p.value for p in data.current("berlin", "lau").presets
                    if p.preset == "ours_headline")  # fmt: skip
    assert f"{headline:,.1f}" in ranking


def test_fingerprint_follows_the_content_dir(setup, tmp_path):  # noqa: F811
    db_path, cfg, maps, docs = setup
    content = tmp_path / "content"
    (content / "narratives").mkdir(parents=True)
    narrative = content / "narratives" / "berlin.yaml"
    narrative.write_text("title: a\n")
    before = fingerprint(db_path, cfg, docs, maps, content)
    narrative.write_text("title: a changed title\n")
    assert fingerprint(db_path, cfg, docs, maps, content) != before
    before = fingerprint(db_path, cfg, docs, maps, content)
    (content / "sources").mkdir()
    (content / "sources" / "x.yaml").write_text("[]\n")
    assert fingerprint(db_path, cfg, docs, maps, content) != before


def test_create_app_takes_the_content_dir(setup, tmp_path):  # noqa: F811
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs, content_dir=tmp_path / "c")) as c:
        assert c.get("/").status_code == 200


def test_markdown_table_alignment_becomes_classes_not_inline_styles():
    """The tables extension writes style="text-align: ..."; the CSP blocks inline styles."""
    from velometer.app.main import _md

    html = str(_md("| a | b | c |\n|:--|--:|:-:|\n| x | 1.5 | y |\n"))
    assert "style=" not in html
    assert '<td class="num">1.5</td>' in html and '<th class="num">b</th>' in html
    assert '<td class="align-center">y</td>' in html and '<td class="align-left">x</td>' in html


def test_bezirk_change_table_has_no_inline_style(subarea_setup):  # noqa: F811
    from tests.test_app import _write_change

    db_path, cfg, maps, docs = subarea_setup
    _write_change(maps, docs)
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        html = c.get("/city/berlin/bezirke").text
    assert "Mapped change" in html and "<td>West</td>" in html
    assert not re.search(r"\sstyle=", html)


def test_a_city_without_a_headline_year_shows_na_not_a_zero_change(setup, monkeypatch):  # noqa: F811
    from dataclasses import replace

    from velometer.report.data import ReportData

    real = ReportData.series

    def only_current(self, city_id, kind):
        cs = real(self, city_id, kind)
        if cs is None:
            return None
        return replace(cs, points=[p for p in cs.points if p.label == "current"])

    monkeypatch.setattr(ReportData, "series", only_current)
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        html = c.get("/").text
    row = html[html.index('<table class="ranking"') :]
    row = row[row.index('href="/city/berlin"') :].split("</tr>")[0]
    assert "+0.0" not in row
    assert row.count("n/a") >= 2  # first year and change
    assert 'class="num up"' not in row and 'class="num down"' not in row


# ---------------------------------------------------------------------------------------------
# Task 11: city tabs, narratives, Figures, the explainer
# ---------------------------------------------------------------------------------------------
SOURCE_YAML = """\
sources:
- id: berlin-src
  publisher: Senat <i>Berlin</i>
  title: Fortschrittsbericht <u>2025</u>
  url: https://example.org/report
  published: '2026-05-20'
  accessed: '2026-10-06'
  language: de
  kind: official
  excerpts:
  - id: q1
    text: Insgesamt sind <b>78,2</b> km & mehr umgesetzt worden.
    gloss_en: In total <script>78.2</script> km have been implemented.
    locator: p. 1
- id: en-src
  publisher: Example NGO
  title: Index
  url: https://example.org/index
  accessed: '2026-10-06'
  language: 'en" onclick="x'
  kind: ngo
  excerpts:
  - id: e1
    text: Protected means separated.
    gloss_en: Gloss <em>x</em>
    locator: p. 2
"""
NARRATIVE_YAML = """\
city_id: berlin
title: "Berlin <b>story</b>"
dek: A dek.
sections:
  - heading: Since 2018
    paragraphs:
      - >-
        First paragraph [@berlin-src] and again [@berlin-src] with data [#ts]
        <script>alert(1)</script>.
      - Second paragraph [@en-src], an unknown [@nope] and an odd ref [#bad].
  - heading: Why the figures differ
    role: figures
    paragraphs:
      - Figures paragraph [@en-src].
quotes:
  - {excerpt: berlin-src/q1, after: 0}
  - {excerpt: berlin-src/missing, after: 1}
  - {excerpt: en-src/e1, after: 2}
data_refs:
  - id: ts
    label: velometer series
    file: docs/review/m3_timeseries.md
    route: /city/berlin/time
  - {id: bad, label: "bad route", route: "javascript:alert(1)"}
"""
EXPLAINER_YAML = (
    """\
title: Why the figures differ
intro:
  - Intro paragraph [@en-src].
sections:
"""
    + "".join(
        f"  - dimension: {d}\n    heading: Heading {d}\n    paragraphs:\n      - Text of {d}.\n"
        for d in ["scope", "kind", "length", "date", "area", "method"]
    )
    + """\
quotes:
  - {excerpt: en-src/e1, after: 2}
"""
)


@pytest.fixture
def content(tmp_path):
    root = tmp_path / "content"
    (root / "sources").mkdir(parents=True)
    (root / "narratives").mkdir()
    (root / "sources" / "x.yaml").write_text(SOURCE_YAML)
    (root / "narratives" / "berlin.yaml").write_text(NARRATIVE_YAML)
    return root


@pytest.fixture
def cclient(setup, content):  # noqa: F811
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs, content_dir=content)) as c:
        yield c


def test_story_tab_shows_title_quote_citations_and_sources(cclient):
    html = cclient.get("/city/berlin").text
    assert '<h2 class="story-title">Berlin &lt;b&gt;story&lt;/b&gt;</h2>' in html
    assert (
        '<blockquote lang="de">Insgesamt sind &lt;b&gt;78,2&lt;/b&gt; km &amp; mehr '
        "umgesetzt worden.</blockquote>" in html
    )
    assert '<sup><a href="#src-1">1</a></sup>' in html
    assert (
        '<li id="src-1" value="1">Senat &lt;i&gt;Berlin&lt;/i&gt;, '
        "<cite>Fortschrittsbericht &lt;u&gt;2025&lt;/u&gt;</cite>" in html
    )
    assert 'href="https://example.org/report"' in html
    caption = re.search(r"<figcaption>(.*?)</figcaption>", html, re.S).group(1)
    assert "Senat &lt;i&gt;Berlin&lt;/i&gt;" in caption and "2026-05-20" in caption
    assert "In total &lt;script&gt;78.2&lt;/script&gt; km" in caption
    assert 'href="https://example.org/report"' in caption


def test_citations_are_numbered_in_first_use_order_with_a_separate_data_list(cclient):
    html = cclient.get("/city/berlin").text
    first = html.index("First paragraph")
    assert html.index('href="#src-1"', first) < html.index('href="#src-2"', first)
    assert html.count('href="#src-1"') == 2  # cited twice, numbered once
    assert '<li id="src-2" value="2">Example NGO' in html
    assert (
        '<a href="#ref-1">d1</a>' in html
        and '<li id="ref-1"><span class="dnum">d1</span> <a href="/city/berlin/time">' in html
    )


def test_content_is_escaped_never_raw_html(cclient):
    html = cclient.get("/city/berlin").text
    assert "<script>alert(1)</script>" not in html and "<b>story</b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_a_data_ref_with_a_non_path_route_is_not_a_link(cclient):
    html = cclient.get("/city/berlin").text
    assert "javascript:" not in html and "bad route" in html


def test_a_city_without_a_narrative_says_so(cclient):
    assert "no narrative yet" in _text(cclient.get("/city/paris").text)


def test_unknown_source_and_excerpt_render_as_source_missing_not_500(cclient):
    r = cclient.get("/city/berlin")
    assert r.status_code == 200
    # the unknown [@nope] marker and the unknown excerpt of the second quote
    assert r.text.count("source missing") == 2


def test_quotes_follow_their_paragraph_and_the_figures_quote_is_on_its_tab(cclient):
    story = cclient.get("/city/berlin").text
    assert story.count('<figure class="pullquote">') == 1  # q1 after the first paragraph
    assert story.index("Insgesamt") < story.index("Second paragraph")
    assert "Protected means separated." not in story
    assert "Figures paragraph" not in story  # the figures section is on its own tab
    figures = cclient.get("/city/berlin/figures").text
    assert figures.index("Figures paragraph") < figures.index("Protected means separated.")
    assert "Second paragraph" not in figures


def test_render_narrative_clamps_an_out_of_range_quote_to_the_end_of_the_document(content):
    """The model checks `after` for narratives, but the renderer must not rely on it."""
    from velometer.app.narrative import render_narrative
    from velometer.content.loader import load_narratives, load_sources
    from velometer.content.models import Quote

    n = load_narratives(content / "narratives")["berlin"]
    wild = [Quote(excerpt="en-src/e1", after=99), Quote(excerpt="en-src/e1", after=-3)]
    n = n.model_copy(update={"quotes": wild})  # model_copy skips the validator
    rendered = render_narrative(n, load_sources(content / "sources"))
    last = rendered.sections[-1].items
    assert ["pullquote" in str(i) for i in last] == [False, True, True]
    assert not any("pullquote" in str(i) for i in rendered.sections[0].items)


def test_an_explainer_quote_out_of_range_renders_at_the_end_not_a_crash(setup, content):  # noqa: F811
    db_path, cfg, maps, docs = setup
    (content / "explainer.yaml").write_text(EXPLAINER_YAML.replace("after: 2", "after: 99"))
    with _client(create_app(db_path, cfg, maps, docs, content_dir=content)) as c:
        r = c.get("/differences")
    assert r.status_code == 200
    body = r.text
    assert body.rindex("Protected means separated.") > body.rindex("Text of method.")


def test_explainer_quote_counts_section_paragraphs_without_the_intro(content):
    import yaml

    from velometer.app.narrative import render_explainer
    from velometer.content.loader import load_sources
    from velometer.content.models import Explainer

    e = Explainer.model_validate(yaml.safe_load(EXPLAINER_YAML))
    rendered = render_explainer(e, load_sources(content / "sources"))
    flat = [i for s in rendered.sections for i in s.items]
    assert ["pullquote" in str(i) for i in flat] == [False, False, False, True, False, False, False]
    assert len(rendered.intro) == 1 and "pullquote" not in str(rendered.intro[0])


def test_tab_routes_and_the_current_tab_mark(subarea_client):  # noqa: F811 - the fixture
    for tab, label in [("", "Story"), ("/time", "Over time"), ("/tiers", "Tiers"),
                       ("/figures", "Figures"), ("/bezirke", "Bezirke")]:  # fmt: skip
        r = subarea_client.get(f"/city/berlin{tab}")
        assert r.status_code == 200, tab
        tabs = re.search(r'<nav class="tabs".*?</nav>', r.text, re.S).group(0)
        assert re.findall(r'<a [^>]*aria-current="page"[^>]*>(.*?)</a>', tabs) == [label]
        assert len(re.findall(r"<li><a ", tabs)) == 5
    assert subarea_client.get("/city/berlin/nope").status_code == 404
    assert subarea_client.get("/city/paris/bezirke").status_code == 404
    assert subarea_client.get("/city/nowhere/time").status_code == 404


def test_a_city_without_subareas_has_four_tabs(client):
    tabs = re.search(r'<nav class="tabs".*?</nav>', client.get("/city/berlin").text, re.S).group(0)
    assert re.findall(r"<li><a [^>]*>(.*?)</a>", tabs) == ["Story", "Over time", "Tiers", "Figures"]
    assert client.get("/city/berlin/bezirke").status_code == 404


def test_figures_tab_lists_a_length_driver_row_for_a_streckenlaenge_figure(setup):  # noqa: F811
    from tests.report_fixture import _figure
    from velometer.db import open_db, replace_external_figures

    db_path, cfg, maps, docs = setup
    fig = _figure("berlin", "official", "vorrangnetz_target_km", 870.0, "vorrangnetz")
    fig = fig.model_copy(update={"length_basis": "streckenlaenge"})
    with open_db(db_path) as w:
        replace_external_figures(w, "official", [fig])
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        html = c.get("/city/berlin/figures").text
    table = html[html.index('<table class="diffs">') :].split("</table>")[0]
    assert '<div data-dimension="length"><dt>How length is measured</dt>' in table
    assert "route length (Streckenlänge)" in table
    row = next(r for r in table.split("<tr>") if "vorrangnetz_target_km" in r)
    assert "reference date 2025-01-01" in row and 'href="https://example.invalid/fixture"' in row
    assert "Ours:" not in _text(table)  # preset labels read "Ours: ..."; the column says it


def test_figures_rows_of_one_source_are_told_apart_by_date_and_link(setup):  # noqa: F811
    from datetime import date

    from tests.report_fixture import _figure
    from velometer.db import open_db, replace_external_figures

    db_path, cfg, maps, docs = setup
    a = _figure("berlin", "official", "new_cycle_infra_km", 21.2)
    b = a.model_copy(update={"value": 20.5, "reference_date": date(2024, 12, 31),
                             "source_url": "https://example.org/other"})  # fmt: skip
    with open_db(db_path) as w:
        replace_external_figures(w, "official", [a, b])
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        html = c.get("/city/berlin/figures").text
    table = html[html.index('<table class="diffs">') :].split("</table>")[0]
    rows = [r for r in table.split("<tr>") if "new_cycle_infra_km" in r]
    assert len(rows) == 2
    assert {("2025-01-01" in r, "2024-12-31" in r) for r in rows} == {(True, False), (False, True)}
    assert any("https://example.org/other" in r for r in rows)


def test_figures_tab_keeps_the_reconciliation_and_reported_tables(cclient):
    text = _text(cclient.get("/city/berlin/figures").text)
    for h in ["Why the figures differ", "Comparison with published figures",
              "Official and reported figures"]:  # fmt: skip
        assert h in text


def test_differences_page_has_one_section_per_dimension(setup, content):  # noqa: F811
    db_path, cfg, maps, docs = setup
    (content / "explainer.yaml").write_text(EXPLAINER_YAML)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=content)) as c:
        html = c.get("/differences").text
    ids = re.findall(r'<section class="narrative prose" id="dim-(\w+)">', html)
    assert ids == ["scope", "kind", "length", "date", "area", "method"]
    assert "Intro paragraph" in html and "Protected means separated." in html
    assert '<a href="/city/berlin/figures">Berlin</a>' in html


def test_differences_page_without_an_explainer_is_a_note(cclient):
    r = cclient.get("/differences")
    assert r.status_code == 200 and "no explainer yet" in _text(r.text)


def test_unreadable_content_is_a_note_not_a_500(setup, content):  # noqa: F811
    db_path, cfg, maps, docs = setup
    (content / "narratives" / "berlin.yaml").write_text("title: [unclosed\n")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=content)) as c:
        for path in ["/city/berlin", "/city/berlin/figures", "/differences"]:
            assert c.get(path).status_code == 200, path
        for path in ["/city/berlin", "/city/berlin/figures"]:
            text = _text(c.get(path).text)
            assert "narratives could not be loaded" in text and "no narrative yet" not in text


def test_over_time_tab_has_the_yearly_table_and_flag_explanations_without_js(client):
    html = client.get("/city/berlin/time").text
    assert '<table class="yearly">' in html and "⚑" in html
    assert EXPLANATION in html


@pytest.mark.parametrize("tab", ["", "/time", "/tiers", "/figures"])
def test_every_tab_has_the_compare_form_that_works_without_js(client, tab):
    html = client.get(f"/city/berlin{tab}").text
    form = re.search(r'<form class="compare-form" action="/compare"[^>]*>(.*?)</form>', html, re.S)
    assert form and 'method="get"' in form.group(0)
    body = form.group(1)
    assert '<input type="hidden" name="c" value="berlin">' in body
    assert re.search(r'<select [^>]*name="c"[^>]* multiple', body)
    assert '<option value="paris">Paris</option>' in body
    assert '<option value="berlin">' not in body  # not itself
    assert '<button type="submit">' in body


def test_header_key_numbers_sit_in_one_scrolling_row(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    html = client.get("/city/berlin").text
    assert html.count('class="keynums"') == 1
    row = html[html.index('class="keynums"') :].split("</div>\n<nav")[0]
    assert row.count('class="kn"') == 5
    headline = next(p.value for p in data.current("berlin", "lau").presets
                    if p.preset == "ours_headline")  # fmt: skip
    assert f"{headline:,.1f}" in row
    from tests.test_app import _css_rules

    rules = _css_rules((STATIC / "app.css").read_text())
    decl = {k: v for sels, d in rules if ".keynums" in sels for k, v in d.items()}
    assert decl.get("overflow-x") == "auto" and decl.get("display") == "flex"
    css = (STATIC / "app.css").read_text()
    assert "@media (max-width: 480px)" in css  # the row scrolls, the page does not


def test_unreadable_content_is_logged(setup, content, caplog):  # noqa: F811
    db_path, cfg, maps, docs = setup
    (content / "narratives" / "berlin.yaml").write_text("title: [unclosed\n")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=content)) as c:
        c.get("/city/berlin")
    assert "content could not be loaded" in caplog.text


def test_pull_quote_language_attribute_is_escaped(setup, content):  # noqa: F811
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs, content_dir=content)) as c:
        html = c.get("/city/berlin/figures").text
    assert '<blockquote lang="en&#34; onclick=&#34;x">' in html
    assert "Gloss &lt;em&gt;x&lt;/em&gt;" in html and "<em>x</em>" not in html


def test_renderer_emits_only_http_urls(content):
    from velometer.app.narrative import pullquote, safe_url
    from velometer.content.loader import load_sources

    assert safe_url("javascript:alert(1)") is None and safe_url("//evil.example/x") is None
    assert safe_url("HTTPS://example.org/a") == "HTTPS://example.org/a"
    src = load_sources(content / "sources")
    bad = {**src, "berlin-src": src["berlin-src"].model_copy(update={"url": "javascript:alert(1)"})}
    assert "javascript:" not in pullquote(bad, "berlin-src/q1")


def test_data_citations_read_d_numbers_and_sources_plain_numbers(cclient):
    html = cclient.get("/city/berlin").text
    assert '<sup><a href="#src-1">1</a></sup>' in html
    assert '<sup class="dref"><a href="#ref-1">d1</a></sup>' in html


def test_data_list_shows_the_label_and_a_file_line_only_without_a_route(setup, content):  # noqa: F811
    db_path, cfg, maps, docs = setup

    def ref_item(yaml_text: str) -> str:
        (content / "narratives" / "berlin.yaml").write_text(yaml_text)
        with _client(create_app(db_path, cfg, maps, docs, content_dir=content)) as c:
            html = c.get("/city/berlin").text
        return html[html.index('<li id="ref-1">') :].split("</li>")[0]

    routed = ref_item(NARRATIVE_YAML)
    assert "docs/review" not in routed and 'href="/city/berlin/time">velometer series' in routed
    plain = ref_item(
        NARRATIVE_YAML.replace("    route: /city/berlin/time", "    locator: '#### berlin/lau'")
    )
    assert "<code>docs/review/m3_timeseries.md</code>" in plain and "· berlin/lau" in plain
    assert "####" not in plain and "<a " not in plain


def test_compare_picker_is_tall_and_drops_a_group_that_would_be_empty(client):
    html = client.get("/city/paris").text
    form = html[html.index('class="compare-form"') :].split("</form>")[0]
    assert 'size="8"' in form
    assert '<optgroup label="France">' not in form  # Paris is France's only fixture city
    assert '<optgroup label="Germany">' in form


def test_figures_rows_with_one_source_metric_and_date_differ_in_visible_text(setup):  # noqa: F811
    from tests.report_fixture import _figure
    from velometer.db import open_db, replace_external_figures

    db_path, cfg, maps, docs = setup
    base = _figure("berlin", "official", "new_cycle_infra_km", 21.2)
    rows = [
        base.model_copy(update={"source_url": "https://www.nordkurier.de/a",
                                "note": "Senate; final"}),
        base.model_copy(update={"value": 9.8, "network_scope": "vorrangnetz", "unit": "pct",
                                "source_url": "https://parlament-berlin.de/b",
                                "note": "Drucksache 19/25987: Vorrangnetz only"}),
    ]  # fmt: skip
    with open_db(db_path) as w:
        replace_external_figures(w, "official", rows)
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        html = c.get("/city/berlin/figures").text
    table = html[html.index('<table class="diffs">') :].split("</table>")[0]
    cells = [
        re.sub(r"<(?:dl|div|dt|dd)\b.*", "", r.split("</td>")[0], flags=re.S)
        for r in table.split("<tr>")
        if "new_cycle_infra_km" in r
    ]
    texts = [_text(c) for c in cells]
    assert len(texts) == 2 and texts[0] != texts[1]
    assert "nordkurier.de" in texts[0] and "scope: whole network" in texts[0]
    assert "Senate" in texts[0] and "final" not in texts[0]  # the first clause only
    assert "parlament-berlin.de" in texts[1] and "scope: vorrangnetz" in texts[1]
    assert "Official / press figures" in texts[0] and "official" not in texts[0].replace(
        "Official", ""
    )
    assert "9.8 %" in _text(table) and "9.8 pct" not in _text(table)


# --- Compare and the slide-over (Task 12) ----------------------------------------------------


def _table(html: str) -> str:
    return html[html.index('<table class="compare-table"') : html.index("</table>")]


def _rows(html: str) -> list[str]:
    return re.findall(r'<th scope="row"><a href="/city/([^"]+)"', _table(html))


def test_default_compare_lists_the_pilot_cities_of_the_data_in_the_table(client):
    r = client.get("/compare")
    assert r.status_code == 200
    assert _rows(r.text) == ["berlin", "paris"]  # the Pilot 5 that the fixture has
    assert 'aria-current="page">Compare</a>' in _nav(r.text)


def test_compare_keeps_only_known_cities(client):
    assert _rows(client.get("/compare?c=berlin,atlantis").text) == ["berlin"]


def test_compare_takes_repeated_c_from_the_no_js_city_form(client):
    assert _rows(client.get("/compare?c=paris&c=berlin").text) == ["paris", "berlin"]
    assert _rows(client.get("/compare?c=paris,berlin&c=berlin").text) == ["paris", "berlin"]


def test_an_unknown_metric_falls_back_to_the_headline(client):
    html = client.get("/compare?m=nope").text
    assert re.search(r'<option value="headline" selected>', html)
    assert "<h2>Headline · City proper (LAU)</h2>" in html


def test_the_filter_sheet_is_a_real_get_form_with_the_cities_and_quick_sets(client):
    html = client.get("/compare").text
    assert re.search(r'<form class="filters-sheet"[^>]*action="/compare" method="get"', html)
    assert 'name="c" value="berlin" checked' in html
    assert 'name="c" value="paris" checked' in html
    for key in ("all", "pilot5", "nordic", "dach", "west", "central"):
        assert f'data-quick="{key}"' in html
    assert 'href="/compare?c=berlin,vienna"' not in html  # only known cities in a set
    assert 'data-quick="dach" href="/compare?c=berlin"' in html


def test_index_mode_notes_a_city_whose_first_year_is_zero(client):
    html = client.get("/compare?mode=index&m=C&c=berlin").text  # tier C is 0 in berlin
    assert "Berlin: no index: first year is 0 or missing" in html
    assert "no index" not in client.get("/compare?mode=index&c=berlin").text


def test_index_mode_rebases_the_first_year_to_100(client):
    cells = re.findall(
        r'<td class="num">([^<]*)', _table(client.get("/compare?mode=index&c=berlin").text)
    )
    assert [c.strip() for c in cells[:3]] == ["100.0", "100.0", "100.0"]


def test_the_lau_only_metric_is_dropped_for_the_metro_area_with_a_visible_note(client):
    html = client.get("/compare?b=fua&m=ab_per_100k&c=berlin").text
    assert "exists for the city proper (LAU) only" in html
    assert "<h2>Headline · Metro area (FUA)</h2>" in html
    assert "exists for the city proper" not in client.get("/compare?m=ab_per_100k&c=berlin").text


def test_the_table_marks_flagged_years(client):
    assert "flagged" in _table(client.get("/compare?c=berlin").text)  # berlin 2025 is flagged


def test_compare_never_echoes_query_text(client):
    html = client.get(
        "/compare?c=%3Cscript%3Ex%3C/script%3E&m=%3Cb%3E&view=%3Ci%3E&hl=%3Cu%3E"
    ).text
    assert "<script>x" not in html and "<b>" not in html and "<i>" not in html


def test_compare_config_block_is_json_and_the_only_script_besides_the_modules(client):
    import json

    html = client.get("/compare").text
    block = re.search(
        r'<script type="application/json" id="compare-config">(.*?)</script>', html, re.S
    )
    cfg = json.loads(block.group(1))
    assert cfg["cities"] == ["berlin", "paris"]
    assert cfg["metric_order"] == list(
        ["headline", "ab_km", "A", "B", "C", "D", "E", "ecf_qecio", "clean_cities", "ab_per_100k"]
    )
    assert cfg["quick"]["all"] is None
    assert '<script type="module" src="/static/js/compare.js">' in html


def test_the_panel_is_a_fragment_that_links_to_the_city(client):
    r = client.get("/city/berlin/panel")
    assert r.status_code == 200
    assert "<nav" not in r.text and "<html" not in r.text and "<body" not in r.text
    assert 'href="/city/berlin"' in r.text
    assert "Berlin" in r.text and 'data-chart="city-tiers"' in r.text
    assert r.headers["content-security-policy"] == CSP


def test_the_panel_lists_flagged_years_with_their_explanations(client):
    text = _text(client.get("/city/berlin/panel").text)
    assert "Flagged years" in text and "activity_spike" in text
    assert EXPLANATION.split(".")[0] in text


def test_the_panel_of_a_city_without_flags_says_so_and_unknown_is_404(client):
    assert "no flagged years" in client.get("/city/paris/panel").text
    assert client.get("/city/nowhere/panel").status_code == 404


def test_the_panel_escapes_city_names(setup, monkeypatch):  # noqa: F811
    from velometer.report.data import ReportData

    real = ReportData.cities

    def cities(self):
        return [
            c.model_copy(update={"name": "<b>Evil</b>"}) if c.id == "berlin" else c
            for c in real(self)
        ]

    monkeypatch.setattr(ReportData, "cities", cities)
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        html = c.get("/city/berlin/panel").text
    assert "<b>Evil</b>" not in html and "&lt;b&gt;Evil&lt;/b&gt;" in html
