"""M7 app foundation: navigation, CSP, the series endpoint, Overview and Cities (Task 10)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_app import (  # noqa: F401 - `setup`, `subarea_setup` are fixtures
    BASE_URL,
    ROUTES,
    _client,
    _text,
    setup,
    subarea_setup,
)
from velometer.app.cache import fingerprint
from velometer.app.main import create_app

CSP = (
    "default-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; "
    "style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'"
)
M7_ROUTES = ROUTES + ["/cities", "/data/series.json"]
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
        html = c.get("/city/berlin").text
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
