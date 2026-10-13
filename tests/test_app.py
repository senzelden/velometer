"""The private read-only web app (`velometer serve`), on the shared report fixture DB."""

import gzip
import hashlib
import importlib.resources
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.report_fixture import CLASSIFIER
from velometer import i18n
from velometer.app.cache import PageCache, fingerprint
from velometer.app.main import create_app
from velometer.cli import app as cli_app
from velometer.report import charts
from velometer.report.data import ReportData, open_readonly

VENDOR = Path(__file__).parents[1] / "src" / "velometer" / "app" / "static" / "vendor"
EXPLANATION = "Fixture cause: a spike of 50 edits in the fixture activity rows."
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


# a tier-map GeoJSON as `velometer report maps` writes it; big enough to be worth compressing
def _side(i: int) -> dict:
    props = {"way_id": 1000 + i, "side": "right", "tier": "ABCDE"[i % 5], "subtype": None}
    props |= {"rule_id": "R1", "km": 0.5, "tags": {"highway": "primary"}}
    line = {"type": "LineString", "coordinates": [[13.4, 52.5 + i / 1e4], [13.41, 52.5]]}
    return {"type": "Feature", "geometry": line, "properties": props}


RUN = {"run_id": 1, "osm_timestamp": "2026-09-30T00:00:00+00:00", "classifier": "v2"}
GEOJSON = json.dumps(
    {"type": "FeatureCollection", "properties": RUN, "boundary": None,
     "features": [_side(i) for i in range(40)]}
).encode()  # fmt: skip
ROUTES = ["/", "/city/berlin", "/city/paris", "/methodology", "/methodology/de"]
ROUTES += ["/data/all.csv", "/data/berlin.csv", "/maps/berlin_lau.png", "/maps/berlin_lau.geojson"]
OSM_TILES = "tile.openstreetmap.org"
# absolute (http/https) or protocol-relative (`//host`, after a quote, `(`, `=` or space) URLs
URL = re.compile(r"""(?:https?:|(?<=["'(=\s]))//[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+[^\s"'<>\\)]*""")
STATIC = VENDOR.parent
# Absolute URLs the vendored Leaflet names that are not loads: the attribution prefix's link
# (leafletjs.com) and the SVG namespace identifier (www.w3.org/2000/svg).
LEAFLET_NON_LOAD_HOSTS = {"leafletjs.com", "www.w3.org"}


# The app answers loopback Host headers only (DNS rebinding, see ALLOWED_HOSTS), so tests talk
# to it as a browser on the served address does, instead of TestClient's default `testserver`.
BASE_URL = "http://127.0.0.1"
# the shipped narratives, found from this file (never the cwd-relative default of create_app)
CONTENT = Path(__file__).parents[1] / "content"


def _client(app) -> TestClient:
    return TestClient(app, base_url=BASE_URL)


def _docs(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    (docs / "review").mkdir(parents=True)
    (docs / "methodology.md").write_text(
        "# Methodology\n\n| term | meaning |\n|---|---|\n| A | separated track |\n\n"
        "```\nvelometer run\n```\n"
    )
    (docs / "methodology.de.md").write_text("# Methodik\n\nGetrennter Radweg.\n")
    (docs / "review" / "m3_timeseries.md").write_text(
        "# M3 time series\n\n## Explanations\n\n"
        f"### berlin/lau/2025\n\n{EXPLANATION} See `config/activity.yaml`.\n\n"
        "### paris/lau/2020\n\nNot a fixture flag.\n"
    )
    return docs


def app_inputs(db_path: Path, cfg: Path, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """(db, config, maps, docs) of the `client` app: the maps and docs it reads, in `tmp_path`.
    Shared with the session-wide rendered pages (conftest `page_site`), so both are one app."""
    maps = tmp_path / "maps"
    maps.mkdir()
    (maps / "berlin_lau.png").write_bytes(PNG)  # berlin_fua.png is deliberately missing
    (maps / "berlin_lau.geojson").write_bytes(GEOJSON)  # and so is berlin_fua.geojson
    for name in ["Berlin_lau", "berlin_xyz"]:  # present, but not valid map names
        (maps / f"{name}.png").write_bytes(PNG)
        (maps / f"{name}.geojson").write_bytes(GEOJSON)
    (tmp_path / "secret.png").write_bytes(PNG)
    (tmp_path / "secret_lau.geojson").write_bytes(GEOJSON)
    docs = _docs(tmp_path)
    return db_path, cfg, maps, docs


@pytest.fixture
def setup(fixture_db, tmp_path):
    db_path, cfg, _conn, _data = fixture_db
    return app_inputs(db_path, cfg, tmp_path)


@pytest.fixture
def client(setup):
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        yield c


@pytest.fixture
def fixture_db_path(setup):
    return setup[0]


def nolabels(html: str) -> str:
    """The page without the stacking labels (data-label), for tests that match cell markup."""
    return re.sub(r' data-label="[^"]*"', "", html)


UI_STRINGS = re.compile(r'<script type="application/json" id="ui-strings">.*?</script>', re.S)


def without_ui_strings(html: str) -> str:
    """The page without its JS strings block: every page carries the whole `js.*` catalogue,
    so a "this note is absent" assertion must not read it."""
    return UI_STRINGS.sub(" ", html)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", without_ui_strings(html)))


@pytest.mark.parametrize(
    "path", ["/", "/city/berlin", "/methodology", "/methodology/de", "/data/all.csv",
             "/data/berlin.csv"],
)  # fmt: skip
def test_routes_render(client, path):
    assert client.get(path).status_code == 200


def test_unknown_city_is_404(client):
    assert client.get("/city/nowhere").status_code == 404
    assert client.get("/data/nowhere.csv").status_code == 404


def test_city_without_current_run_renders_no_run(client):
    # paris has history but no current run (LAU) and nothing at all for FUA
    pages = [client.get(f"/city/paris/{tab}") for tab in ("time", "tiers", "figures")]
    assert [r.status_code for r in pages] == [200, 200, 200]
    assert client.get("/city/paris").status_code == 200
    text = _text(" ".join(r.text for r in pages))
    assert "no run (LAU current)" in text  # headline, LAU vs FUA, comparison, map
    assert "no run (FUA history)" in text  # tier composition, flagged years
    assert "no run (LAU current) to compare" in text
    assert "map not generated" not in text  # no run, so no map to generate


def test_index_lists_cities_with_links_and_charts(client):
    html = client.get("/").text
    assert 'href="/city/berlin"' in html and 'href="/city/paris"' in html
    assert html.count('data-chart="overview-lines"') == 1  # drawn by /static/js/overview.js
    assert "<h2" in html and "Rankings by source" in html  # the old flip chart, as a table
    row = re.search(r'<tr[^>]*>\s*<td[^>]*><a href="/city/paris">.*?</tr>', html, re.S)
    assert row and "no run" in row.group(0)


def test_city_tabs_have_their_sections_in_order(client):
    tabs = {
        "time": ["Over time", "Flagged years", "Headline and presets", "Provenance"],
        "tiers": ["Tier composition", "LAU vs FUA", "Tier map"],
        "figures": ["Why the figures differ", "Comparison with published figures",
                    "Official and reported figures"],
    }  # fmt: skip
    for tab, order in tabs.items():
        text = _text(client.get(f"/city/berlin/{tab}").text)
        positions = [text.find(h) for h in order]
        assert -1 not in positions, (tab, dict(zip(order, positions, strict=True)))
        assert positions == sorted(positions), tab


def test_city_page_mounts_the_headline_with_lau_and_fua_and_tabulates_it(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    html = nolabels(client.get("/city/berlin/time").text)
    tiers_html = nolabels(client.get("/city/berlin/tiers").text)
    mount = '<div class="chart" data-chart="city-headline" data-city="berlin"'
    assert mount in html
    assert 'data-chart="city-tiers"' not in html  # the tier charts are on the Tiers tab
    assert re.findall(
        r'data-chart="city-tiers" data-city="berlin" data-kind="(\w+)"', tiers_html
    ) == [
        "lau",
        "fua",
    ]
    table = html[html.index('<table class="yearly stack">') :]
    table = table[: table.index("</table>")]
    assert _headers(table)[1:] == ["LAU headline", "LAU A+B km", "FUA headline", "FUA A+B km"]
    lau = data.series("berlin", "lau").points
    rows = re.findall(r"<tr>\s*<td>(.*?)</td>", table.split("<tbody>")[1])
    labels = {
        p.label for k in ("lau", "fua") if (cs := data.series("berlin", k)) for p in cs.points
    }
    assert len(rows) == len(labels) and rows[-1].startswith(("Jan", "Feb", "Mar", "Apr", "May",
        "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))  # fmt: skip
    assert f"{lau[0].headline:,.1f}" in table and "⚑" in table  # the 2025 LAU flag


def test_city_page_shows_current_numbers(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    point = data.current("berlin", "lau")
    text = _text(client.get("/city/berlin/time").text)
    section = text[text.find("Headline and presets") : text.find("Provenance")]
    headline = next(p for p in point.presets if p.preset == "ours_headline")
    label = data.preset_labels()["ours_headline"]
    unit = data.preset_units()["ours_headline"]
    assert f"{label} {headline.value:,.1f} {unit} {headline.per_100k:,.1f}" in section
    assert f"A+B km {point.ab_km:,.1f}" in section
    assert point.osm_timestamp in section
    provenance = text[text.find("Provenance") :]
    assert f"run {point.run_id}" in provenance
    assert point.config_sha256[:12] in provenance


def test_flag_explanation_text_on_city_page(client):
    html = client.get("/city/berlin/time").text
    assert "berlin/lau/2025" in html
    assert "activity_spike" in html
    assert EXPLANATION in html
    assert "<code>config/activity.yaml</code>" in html  # rendered as markdown
    assert "Not a fixture flag." not in html


def test_flag_without_explanation_says_so(setup):
    db_path, cfg, maps, docs = setup
    (docs / "review" / "m3_timeseries.md").write_text("# empty\n")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        r = c.get("/city/berlin/time")
    assert r.status_code == 200
    assert "no explanation" in _text(r.text)


def test_reconcile_rows_on_city_page(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    gaps = data.reconcile("berlin").gaps
    html = client.get("/city/berlin/figures").text
    section = html[
        html.find("Comparison with published figures") : html.find("Official and reported figures")
    ]
    flagged = next(g for g in gaps if g.flagged)
    assert flagged.key.split("/", 1)[1] in section
    assert f"{flagged.gap_pct * 100:+.1f}%" in section
    assert section.count("<tr") == len(gaps) + 1  # + header row


def test_map_route_blocks_traversal_and_missing(client):
    assert client.get("/maps/..%2Fsecret.png").status_code == 404
    assert client.get("/maps/berlin_lau.png").status_code in (200, 404)
    assert client.get("/maps/berlin_fua.png").status_code == 404  # missing file
    assert client.get("/maps/Berlin_lau.png").status_code == 404
    assert client.get("/maps/berlin_xyz.png").status_code == 404
    assert client.get("/maps/..%2F..%2Fsecret_lau.png").status_code == 404


def test_map_route_serves_png(client):
    r = client.get("/maps/berlin_lau.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == PNG


def _map_section(html: str) -> str:
    return html[html.index("<h2>Tier map</h2>") : html.index("</main>")]


def _map_config(html: str) -> dict | None:
    m = re.search(r'<script type="application/json" id="tiermap-config">(.*?)</script>', html, re.S)
    return None if m is None else json.loads(m.group(1))


def test_city_page_interactive_map_with_png_link_and_hint(client):
    html = client.get("/city/berlin/tiers").text
    section = _map_section(html)
    assert '<div id="tiermap"' in section
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', section)
    assert scripts == ["/static/vendor/leaflet.js", "/static/map.js"]
    assert '<link rel="stylesheet" href="/static/vendor/leaflet.css">' in html.split("</head>")[0]
    for s in scripts + ["/static/vendor/leaflet.css"]:
        assert client.get(s).status_code == 200
    cfg = _map_config(section)
    assert cfg["kinds"] == [{"kind": "lau", "label": "LAU", "url": "/maps/berlin_lau.geojson"}]
    # the colours live in the stylesheet's tokens (both themes), not in the config: map.js
    # reads them when it draws and again when the OS theme changes
    assert "colours" not in cfg and "outline" not in cfg
    assert cfg["labels"] == charts.TIER_LABEL
    for t in "ABCDE":  # the tier checkboxes: a key swatch map.js paints from --tier-x
        box = re.search(
            rf'<input type="checkbox" name="tier" value="{t}"[^>]*>'
            rf'\s*<svg class="swatch" data-key="{t}"[^>]*><rect ([^>]*)>',
            section,
        )
        assert box and "fill=" not in box.group(1), t
    assert not HEX_COLOUR.search(section)
    assert re.findall(r'<input type="radio" name="kind" value="(\w+)"', section) == ["lau"]
    assert re.search(r'<a href="/maps/berlin_lau.png">[^<]*static image', section)
    assert '<a href="/maps/berlin_fua.png"' not in section  # no PNG either
    assert "<img" not in section
    # FUA has a current run but no GeoJSON: the existing hint
    assert "map not generated (<code>velometer report maps</code>)" in section


def test_city_page_without_any_geojson_loads_no_map(setup):
    db_path, cfg, maps, docs = setup
    (maps / "berlin_lau.geojson").unlink()
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        section = _map_section(c.get("/city/berlin/tiers").text)
    assert '<div id="tiermap"' not in section and "<script" not in section
    assert section.count("map not generated (<code>velometer report maps</code>)") == 2
    assert '<a href="/maps/berlin_lau.png">' in section  # the static image is still there


def _loaded_hosts(html: str) -> set[str]:
    """Hosts the page loads from: every absolute URL except anchors' hrefs and the map config's
    `links` (way pages and the copyright note are links a reader follows, not loads) and the CSP
    meta tag (a policy naming hosts, as the header does, not a load)."""
    html = re.sub(r'<a\s[^>]*href="[^"]*"', "<a", html)
    html = re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', "", html)
    cfg = _map_config(html)
    if cfg is not None:
        cfg.pop("links")
        html = re.sub(r'(id="tiermap-config">).*?(</script>)', lambda m: m.group(1) +
                      json.dumps(cfg) + m.group(2), html, flags=re.S)  # fmt: skip
    return {urlparse(u).hostname for u in URL.findall(html)}


def test_pages_load_only_static_assets_and_osm_tiles(client):
    """The one external host a page loads from is the OSM tile server; scripts and CSS are ours."""
    for path in [
        "/",
        "/city/berlin",
        "/city/berlin/time",
        "/city/berlin/figures",
        "/city/paris",
        "/methodology",
        "/methodology/de",
    ]:
        html = client.get(path).text
        scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
        assert scripts and all(s.startswith("/static/") for s in scripts), path
        # what a page loads: the head's alternate and canonical links are not fetched
        css = re.findall(r'<link (?!rel="(?:alternate|canonical)")[^>]*href="([^"]+)"', html)
        assert css and all(c.startswith("/static/") for c in css), path
        assert all(i.startswith("/") and not i.startswith("//")
                   for i in re.findall(r'<img[^>]+src="([^"]+)"', html)), path  # fmt: skip
        assert _loaded_hosts(html) <= {OSM_TILES}, path
    city = client.get("/city/berlin/tiers").text
    assert _loaded_hosts(city) == {OSM_TILES}
    cfg = _map_config(city)
    assert urlparse(cfg["tiles"]).hostname == OSM_TILES
    assert {urlparse(u).hostname for u in cfg["links"].values()} == {"www.openstreetmap.org"}
    # map.js takes every URL from that config: it names no host of its own
    assert not URL.findall(client.get("/static/map.js").text)


def test_static_files_load_nothing_external():
    """The network rule covers our own and the vendored static files, not only the HTML."""
    for css in [*STATIC.glob("*.css"), *VENDOR.glob("*.css")]:
        text = css.read_text()
        refs = re.findall(r"url\(\s*['\"]?([^'\")]+)", text)
        refs += re.findall(r"@import\s+(?:url\()?\s*['\"]?([^'\");\s]+)", text)
        for ref in refs:
            ok = ref.startswith(("#", "data:")) or not (
                urlparse(ref).scheme or ref.startswith("//")
            )
            assert ok, (css.name, ref)
    leaflet = {urlparse(u).hostname for u in URL.findall((VENDOR / "leaflet.js").read_text())}
    assert leaflet == LEAFLET_NON_LOAD_HOSTS
    assert "www.w3.org/2000/svg" in (VENDOR / "leaflet.js").read_text()
    assert not URL.findall((STATIC / "map.js").read_text())


def test_protocol_relative_urls_count_as_loads():
    assert _loaded_hosts('<div style="background:url(//evil.example.com/x.png)"></div>') == {
        "evil.example.com"
    }
    assert _loaded_hosts('<a href="//www.openstreetmap.org/copyright">x</a>') == set()


def test_osm_tiles_are_muted_and_tier_lines_readable(client):
    """Standard OSM draws main roads orange/red, clashing with tiers B and D: the tile layer
    (only it, not the vector canvas) is greyed and faded; the tier lines stay ~3 px."""
    cfg = _map_config(client.get("/city/berlin/tiers").text)
    cls = cfg["tile_class"]
    assert cls and cls != "leaflet-tile-pane"
    rules = _css_rules((STATIC / "app.css").read_text())
    decls = [d for sels, d in rules if f".{cls}" in sels]
    assert decls, cls
    rule = decls[0]  # the light rule; the dark-theme filter is checked in test_a11y
    assert "grayscale(1)" in rule["filter"]
    assert float(rule.get("opacity", "1")) <= 0.8 or "contrast(" in rule["filter"]
    assert not any(".leaflet-overlay-pane" in s or "canvas" in s for sels, d in rules
                   if "filter" in d for s in sels)  # fmt: skip
    assert 2.5 <= cfg["weight"] <= 4
    js = (STATIC / "map.js").read_text()
    assert "className: cfg.tile_class" in js and "weight: cfg.weight" in js


def test_geojson_route_serves_geo_json(client):
    r = client.get("/maps/berlin_lau.geojson")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/geo+json"
    assert r.content == GEOJSON


def test_geojson_route_blocks_bad_names_and_missing(client):
    for name in [
        "berlin_fua",
        "Berlin_lau",
        "berlin_xyz",
        "..%2Fsecret_lau",
        "..%2F..%2Fsecret_lau",
    ]:
        assert client.get(f"/maps/{name}.geojson").status_code == 404, name


def test_responses_are_gzipped_when_the_client_accepts_it(client):
    r = client.get("/maps/berlin_lau.geojson", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip"
    assert r.content == GEOJSON  # httpx decodes it
    assert int(r.headers["content-length"]) < len(GEOJSON)
    plain = client.get("/maps/berlin_lau.geojson", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers and plain.content == GEOJSON
    assert gzip.decompress(gzip.compress(GEOJSON)) == GEOJSON


def test_pages_load_our_chart_modules(client):
    base = [
        "/static/js/nav.js",
        "/static/js/search.js",
        "/static/js/cite-ui.js",
        "/static/js/download-ui.js",
        "/static/js/permalink-ui.js",
        "/static/js/lang-switch.js",
    ]
    pages = {
        "/": [*base, "/static/js/overview.js"],
        "/cities": [*base, "/static/js/overview.js"],
        "/city/berlin": [*base, "/static/js/city.js"],
        "/city/berlin/time": [*base, "/static/js/city.js"],
        "/city/berlin/tiers": [*base, "/static/js/city.js", "/static/vendor/leaflet.js",
                               "/static/map.js"],
        "/city/berlin/figures": base,
        "/differences": base,
        "/methodology": base,
    }  # fmt: skip
    for path, expected in pages.items():
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', client.get(path).text)
        assert srcs == expected, path
        for s in srcs:
            assert client.get(s).status_code == 200
    # the modules import only our own files, by relative path (the map modules beside js/ too)
    for js in [*(STATIC / "js").glob("*.js"), *STATIC.glob("*.js")]:
        for spec in re.findall(r'^import .*? from "([^"]+)"', js.read_text(), re.M):
            assert spec.startswith("./") and (js.parent / spec).is_file(), (js.name, spec)


HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
JS_COLOUR = re.compile(rf"{HEX_COLOUR.pattern}|(?<![\w-])(?:rgba?|hsla?)\(", re.I)


def _js_colour_literals(text: str) -> list[str]:
    return JS_COLOUR.findall(text)


def test_no_js_file_holds_a_colour_literal():
    # charts and maps draw from the stylesheet's tokens (static/js/theme.js), so a theme
    # changes every colour in one place. The one literal is theme.js's MISSING grey, the
    # fallback for a token that is not defined (it logs a console error, which fails the render
    # pass). Our own scripts, not the vendored ones or the node tests
    found = {}
    for js in [*STATIC.glob("*.js"), *(STATIC / "js").glob("*.js")]:
        text = js.read_text()
        if js.name == "theme.js":
            text = text.replace('export const MISSING = "#808080";', "", 1)
        if hits := _js_colour_literals(text):
            found[js.name] = hits
    assert found == {}


def test_the_js_literal_rule_sees_each_kind():
    for lit in ['"#2a78d6"', "'#fff'", "rgb(0 0 0)", "rgba(0,0,0,.1)", "hsl(10 50% 50%)"]:
        assert _js_colour_literals(f"const c = {lit};"), lit
    for ok in ['"#tiermap-config"', "`#${t}`", '"transparent"', '"currentColor"', "#hash"]:
        assert not _js_colour_literals(f"const c = {ok};"), ok


# the ODbL attribution (a licence requirement) and the mapped-km line, in each language
FOOTER_TEXT = {
    "en": ("Map data © OpenStreetMap contributors, ODbL 1.0",
           "OSM mapped km, not built km (ADR 0006)"),
    "de": ("Kartendaten © OpenStreetMap-Mitwirkende, ODbL 1.0",
           "kartierte km, nicht gebaute km (ADR 0006)"),
}  # fmt: skip


def test_footer_on_every_page(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    pages = [("/", "en"), ("/city/berlin", "en"), ("/city/paris", "en"), ("/methodology", "en"),
             ("/methodology/de", "de"), ("/de/", "de")]  # fmt: skip
    for path, lang in pages:
        html = client.get(path).text
        footer = html[html.index("<footer") :]
        text = _text(footer)
        # the licence and ADR 0006 wording itself, then the catalogue the page renders from
        assert FOOTER_TEXT[lang][0] in text and FOOTER_TEXT[lang][1] in text, path
        assert _text(i18n.t(lang, "site.footer.attribution", osm="")).strip() in text, path
        assert i18n.t(lang, "site.footer.mapped_km") in text, path
        methodology = "/methodology" if lang == "en" else "/de/methodology"
        assert f'href="{methodology}"' in footer, path
        assert data.selector.version in text and data.selector.short_sha in text


def test_methodology_rendered_with_tables_and_language_links(client):
    html = client.get("/methodology").text
    assert "<table" in html and "separated track" in html
    assert "<pre><code>velometer run" in html  # fenced_code
    # the nav's language switch leads to the twin in the other language
    assert re.search(r'<a class="lang-switch"[^>]*\bhref="/de/methodology"', html)
    de = client.get("/methodology/de").text
    assert "Getrennter Radweg." in de
    assert re.search(r'<a class="lang-switch"[^>]*\bhref="/methodology"', de)


def test_missing_methodology_is_a_note_not_an_error(setup):
    db_path, cfg, maps, docs = setup
    (docs / "methodology.md").unlink()
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        r = c.get("/methodology")
    assert r.status_code == 200
    assert "methodology not generated" in _text(r.text)


def test_missing_db_at_request_time_is_503_not_500(setup):
    db_path, cfg, maps, docs = setup
    with _client(
        create_app(db_path.with_name("gone.sqlite"), cfg, maps, docs, content_dir=CONTENT)
    ) as c:
        assert c.get("/").status_code == 503
        assert c.get("/city/berlin").status_code == 503


def _digest(p: Path) -> tuple[str, int]:
    return hashlib.md5(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns


def test_app_never_writes_the_db(client, fixture_db_path):
    before = _digest(fixture_db_path)
    siblings = set(fixture_db_path.parent.iterdir())
    for path in ROUTES + ["/city/nowhere", "/maps/berlin_fua.png", "/data/paris.csv"]:
        client.get(path)
    assert _digest(fixture_db_path) == before
    assert set(fixture_db_path.parent.iterdir()) == siblings  # no -wal / -journal files


def test_csv_route_is_attachment_with_attribution(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    r = client.get("/data/berlin.csv")
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"].startswith("attachment")
    assert "berlin" in r.headers["content-disposition"]
    lines = r.text.splitlines()
    assert lines[0].startswith("# Map data © OpenStreetMap contributors, ODbL 1.0")
    assert lines[1].startswith("# velometer ")
    body = lines[3:]
    assert len(body) == len(data.csv_rows("berlin")) and all(b.startswith("berlin,") for b in body)
    every = client.get("/data/all.csv").text.splitlines()[3:]
    assert len(every) == len(data.csv_rows())


def test_templates_and_static_ship_in_the_package():
    root = importlib.resources.files("velometer.app")
    for name in ["base.html", "_nav.html", "index.html", "cities.html", "differences.html",
                 "methodology.html", "city/_page.html", "city/_header.html",
                 "city/story.html", "city/time.html", "city/tiers.html", "city/figures.html",
                 "city/bezirke.html"]:  # fmt: skip
        assert (root / "templates" / name).is_file()
    assert (root / "static" / "app.css").is_file()
    assert (root / "static" / "map.js").is_file()
    for name in ["chart.js", "chart-core.js", "state.js", "data.js", "nav.js", "overview.js",
                 "city.js"]:  # fmt: skip
        assert (root / "static" / "js" / name).is_file()
    for name in ["leaflet.js", "leaflet.css", "leaflet.LICENSE"]:
        assert (root / "static" / "vendor" / name).is_file()


def _versions() -> dict[str, list[str]]:
    rows = [
        line.split()
        for line in (VENDOR / "VERSIONS").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return {r[0]: r for r in rows}


def test_vendor_leaflet_is_the_recorded_1_9_release():
    _pkg, constant, resolved = _versions()["leaflet"]
    assert constant == "1.9" and resolved.startswith("1.9.")
    js = (VENDOR / "leaflet.js").read_text()
    assert f"Leaflet {resolved}," in js and f'version="{resolved}"' in js
    assert (
        f"Leaflet {resolved}" in (VENDOR / "leaflet.css").read_text()
        or ".leaflet-pane" in (VENDOR / "leaflet.css").read_text()
    )
    assert "BSD 2-Clause" in (VENDOR / "leaflet.LICENSE").read_text()
    assert "cdn.jsdelivr" not in js and "unpkg.com" not in js


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "example.com", "::", "127.0.0.2"])
def test_serve_refuses_non_loopback_host(fixture_db_path, monkeypatch, host):
    import uvicorn

    def boom(*a, **k):
        raise AssertionError("uvicorn.run must not be called")

    monkeypatch.setattr(uvicorn, "run", boom)
    result = CliRunner().invoke(cli_app, ["serve", "--host", host, "--db", str(fixture_db_path)])
    assert result.exit_code == 2, result.output
    assert "loopback" in result.output


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_serve_runs_uvicorn_on_loopback(setup, monkeypatch, host):
    import uvicorn

    db_path, cfg, maps, docs = setup
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append((app, kw)))
    args = ["serve", "--host", host, "--port", "8123", "--db", str(db_path)]
    args += ["--config-dir", str(cfg), "--maps", str(maps), "--docs", str(docs)]
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    app, kw = calls[0]
    assert kw == {"host": host, "port": 8123}
    with _client(app) as c:
        assert c.get("/city/berlin").status_code == 200


def test_serve_missing_db_exits_1(tmp_path, monkeypatch):
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: pytest.fail("uvicorn.run called"))
    result = CliRunner().invoke(cli_app, ["serve", "--db", str(tmp_path / "none.sqlite")])
    assert result.exit_code == 1
    assert "not found" in result.output


def _headers(html: str) -> list[str]:
    return [_text(h).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)]


def test_index_preset_columns_are_labelled_ours(client, fixture_db):
    """Our preset values never sit under a publisher's name or a "%"/"share" heading."""
    _db, _cfg, _conn, data = fixture_db
    headers = _headers(client.get("/").text)
    for preset in ("ecf_qecio", "clean_cities_2025"):
        label = data.preset_labels()[preset]
        assert label.endswith("our OSM data") and label in headers
    # a publisher's name heads only our values ("<method>, our OSM data") or its own ranking
    named = [h for h in headers if "QECIO" in h or "Clean Cities" in h]
    assert all("our OSM data" in h or "(published)" in h for h in named)
    assert any("(published)" in h for h in named)  # the rankings-by-source table
    for path in ["/", "/city/berlin"]:
        for h in _headers(client.get(path).text):
            assert "%" not in h and "share" not in h.lower(), (path, h)


def test_index_lede_names_the_headline_unit_and_own_denominators(client):
    text = _text(client.get("/").text)
    assert "A+B km per 100 km of main roads (excl. motorways)" in text
    assert "own denominator" in text
    assert "percent of main roads" not in text
    assert "A+B km per 100 km of all public roads" in text  # clean_cities_2025's denominator


def test_preset_labels_follow_report_yaml(setup):
    db_path, cfg, maps, docs = setup
    path = cfg / "report.yaml"
    path.write_text(
        path.read_text().replace("QECIO method, our OSM data", "QECIO test label, our OSM data")
    )
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        assert "QECIO test label, our OSM data" in _headers(c.get("/").text)
        assert "QECIO test label, our OSM data" in _text(c.get("/city/berlin/time").text)


def test_app_follows_report_classifier_of_the_config(setup):
    """Spec section 5: the app defaults to config/report.yaml, red-proofed in a copied config."""
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        before = c.get("/city/berlin/time").text
    assert f"Classifier {CLASSIFIER}" in _text(before)
    assert "no run (LAU current)" not in _text(before)
    path = cfg / "report.yaml"
    path.write_text(
        path.read_text().replace(f"report_classifier: {CLASSIFIER}", "report_classifier: v1")
    )
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        after = _text(c.get("/city/berlin/time").text)
    assert "Classifier v1" in after and f"Classifier {CLASSIFIER}" not in after
    assert "no run (LAU current)" in after  # the fixture's runs are on CLASSIFIER only


@pytest.mark.parametrize("host", ["attacker.example", "192.168.1.10", "127.0.0.1.nip.io"])
def test_foreign_host_header_is_refused(client, host):
    """DNS rebinding: a page that points its own name at 127.0.0.1 gets no data."""
    for path in ["/", "/data/all.csv", "/city/berlin"]:
        r = client.get(path, headers={"Host": host})
        assert r.status_code == 400, (path, host)
        assert "berlin" not in r.text


@pytest.mark.parametrize("host", ["127.0.0.1:8766", "localhost:8000", "[::1]:8000", "localhost"])
def test_loopback_host_headers_are_served(client, host):
    assert client.get("/data/all.csv", headers={"Host": host}).status_code == 200


def test_db_on_another_schema_version_is_503(setup, tmp_path):
    db_path, cfg, maps, docs = setup
    old = tmp_path / "v5.sqlite"
    shutil.copy(db_path, old)
    with sqlite3.connect(old) as c:
        c.execute("PRAGMA user_version = 5")
    with _client(create_app(old, cfg, maps, docs, content_dir=CONTENT)) as c:
        for path in ["/", "/city/berlin", "/data/all.csv"]:
            r = c.get(path)
            assert r.status_code == 503, path
            assert "velometer migrate" in r.text


def test_index_flagged_years_count_lau_only(client, monkeypatch):
    from velometer.report.data import ReportData

    real = ReportData.flags
    monkeypatch.setattr(
        ReportData,
        "flags",
        lambda self, city_id, kind: (
            # seven FUA flags (copies of the real LAU one; only the count matters here)
            real(self, city_id, "lau") * 7 if kind == "fua" else real(self, city_id, kind)
        ),
    )
    html = client.get("/").text
    assert "Flagged years (LAU)" in _headers(html)
    row = re.search(r'<tr[^>]*>\s*<td[^>]*><a href="/city/berlin">.*?</tr>', html, re.S).group(0)
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
    assert cells[-1].strip() == "1"  # the fixture's one LAU flag (2025); FUA's 7 not counted


def test_city_with_current_run_but_no_history(setup):
    """Review Focus 2, reverse case: berlin/fua keeps its current run, its history fails."""
    db_path, cfg, maps, docs = setup
    with sqlite3.connect(db_path) as c:
        c.execute(
            "UPDATE runs SET status='failed' WHERE city_id='berlin' AND boundary_kind='fua' "
            "AND source='history'"
        )
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        r = c.get("/city/berlin/tiers")
        assert r.status_code == 200
        text = _text(r.text)
        assert "no run (FUA history)" in text
        assert "no run (FUA current)" not in text
        csv = c.get("/data/berlin.csv").text.splitlines()
    assert any(line.startswith("berlin,fua,current,") for line in csv)
    assert not any(line.startswith("berlin,fua,20") for line in csv)


def _css_rules(css: str) -> list[tuple[list[str], dict[str, str]]]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decls = dict(
            (k.strip(), v.strip())
            for k, _, v in (d.partition(":") for d in body.split(";") if ":" in d)
        )
        rules.append(([s.strip() for s in sel.split(",")], decls))
    return rules


_ROOT = re.compile(r"(?m)^:root\s*\{([^{}]*)\}")
_DARK = re.compile(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^{}]*)\}\s*\}")


def _pairs(body: str) -> dict[str, str]:
    pairs = (d.partition(":") for d in body.split(";") if ":" in d)
    return {k.strip(): v.strip() for k, _, v in pairs}


def _dark_tokens(css: str) -> dict[str, str]:
    """The custom properties the `prefers-color-scheme: dark` `:root` block redefines."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found = _DARK.findall(css)
    assert len(found) == 1, f"{len(found)} dark :root blocks; the theme is one block"
    return _pairs(found[0])


def _dark_rules(css: str) -> list[tuple[list[str], dict[str, str]]]:
    """The (selectors, declarations) of the rules inside `prefers-color-scheme: dark` media
    blocks, the `:root` token block excluded."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = []
    for m in re.finditer(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{", css):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        rules += [r for r in _css_rules(css[m.end() : i - 1]) if r[0] != [":root"]]
    return rules


def _css_tokens(css: str, theme: str = "light") -> dict[str, str]:
    """The custom properties of the stylesheet's `:root`; for dark, updated with the dark block."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found = _ROOT.findall(css)
    assert len(found) == 1, f"{len(found)} light :root blocks; the tokens are one block"
    light = _pairs(found[0])
    if theme == "light":
        return light
    assert theme == "dark", theme
    return {**light, **_dark_tokens(css)}


def _css_outside_tokens(css: str) -> str:
    """The stylesheet without comments and its two token blocks (light `:root`, dark media)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    _css_tokens(css, "dark")  # exactly one block of each, or a second one could hide literals
    return _ROOT.sub("", _DARK.sub("", css))


def _resolve(value: str, tokens: dict[str, str]) -> str:
    """`var(--x)` -> the token's value (one level, as the stylesheet uses them)."""
    m = re.fullmatch(r"var\((--[\w-]+)\)", value.strip())
    return tokens[m.group(1)] if m else value


def test_table_cells_never_break_inside_words():
    """A table must overflow into its .scroll box, not shrink letter by letter: no inherited
    `overflow-wrap: anywhere` reaches a cell, headers do not wrap, and code in cells stays whole."""
    rules = _css_rules((VENDOR.parent / "app.css").read_text())

    def decl(selector, prop):
        found = [d[prop] for sels, d in rules if selector in sels and prop in d]
        return found[-1] if found else None

    for ancestor in ["html", "body", "*", "main", "table", "tr", "thead", "tbody"]:
        assert decl(ancestor, "overflow-wrap") in (None, "normal"), ancestor
    for cell in ["th", "td", "th *", "td *"]:
        assert decl(cell, "overflow-wrap") == "normal", cell
    assert decl("th", "white-space") == "nowrap"
    assert decl("td code", "white-space") == "nowrap"


def test_untrusted_city_page_is_404(report_db_with_trust, tmp_path):
    db_path, cfg = report_db_with_trust(countries={"DE": {"status": "trusted", "basis": "t"}})
    maps = tmp_path / "maps2"
    maps.mkdir()
    with _client(create_app(db_path, cfg, maps, _docs(tmp_path / "d2"), content_dir=CONTENT)) as c:
        assert c.get("/city/berlin").status_code == 200
        assert c.get("/city/paris").status_code == 404
        assert "/city/paris" not in c.get("/").text
        assert "/city/berlin" in c.get("/").text


# --- page cache (Task 10) and the 21-city fixture ---------------------------------------------


@pytest.fixture
def setup_21(report_db_21, tmp_path):
    db_path, cfg = report_db_21
    maps = tmp_path / "maps"
    maps.mkdir()
    return db_path, cfg, maps, _docs(tmp_path)


@pytest.fixture
def client_21(setup_21):
    with _client(create_app(*setup_21, content_dir=CONTENT)) as c:
        yield c


@pytest.fixture
def cities_calls(monkeypatch):
    calls = Counter()
    real = ReportData.cities
    monkeypatch.setattr(ReportData, "cities", lambda self: calls.update(["q"]) or real(self))
    return calls


def test_second_request_does_not_query(client_21, cities_calls):
    client_21.get("/")
    first = cities_calls["q"]
    client_21.get("/")
    assert first > 0 and cities_calls["q"] == first


def test_cache_hit_never_opens_the_database(client_21, setup_21, monkeypatch):
    for path in ["/", "/city/c21", "/data/all.csv", "/data/c21.csv"]:
        client_21.get(path)

    def boom(*a, **k):
        raise AssertionError("a cache hit opened the database")

    monkeypatch.setattr("velometer.app.main.open_readonly", boom)
    for path in ["/", "/city/c21", "/data/all.csv", "/data/c21.csv"]:
        assert client_21.get(path).status_code == 200


def test_db_change_invalidates(client_21, setup_21, cities_calls):
    client_21.get("/")
    first = cities_calls["q"]
    os.utime(setup_21[0], ns=(time.time_ns(), time.time_ns() + 10**9))
    client_21.get("/")
    assert cities_calls["q"] > first


def test_config_change_invalidates(client_21, setup_21, cities_calls):
    client_21.get("/")
    first = cities_calls["q"]
    report = setup_21[1] / "report.yaml"
    os.utime(report, ns=(time.time_ns(), time.time_ns() + 10**9))
    client_21.get("/")
    assert cities_calls["q"] > first


def test_docs_and_maps_change_invalidates(client_21, setup_21, cities_calls):
    _db, _cfg, maps, docs = setup_21
    client_21.get("/city/berlin/tiers")
    first = cities_calls["q"]
    (maps / "berlin_lau.geojson").write_bytes(GEOJSON)  # a new map file
    assert "/maps/berlin_lau.geojson" in client_21.get("/city/berlin/tiers").text
    assert cities_calls["q"] > first
    second = cities_calls["q"]
    (docs / "review" / "m3_timeseries.md").write_text("# changed\n")
    client_21.get("/city/berlin/tiers")
    assert cities_calls["q"] > second


def test_unknown_city_is_not_cached_and_stays_404(client_21):
    assert client_21.get("/city/nowhere").status_code == 404
    assert client_21.get("/city/nowhere").status_code == 404
    assert client_21.get("/data/nowhere.csv").status_code == 404


def test_missing_db_is_503_even_after_a_cached_page(client_21, setup_21):
    assert client_21.get("/").status_code == 200
    setup_21[0].unlink()
    assert client_21.get("/").status_code == 503


def test_fingerprint_covers_every_file_the_pages_read(setup_21):
    db, cfg, maps, docs = setup_21
    fp = lambda: fingerprint(db, cfg, docs, maps)  # noqa: E731
    base = fp()
    assert ("reconciliation.md", None, None) in base[2]  # missing: contributes None
    (docs / "reconciliation.md").write_text("x")
    assert fp() != base
    before = fp()
    (cfg / "classifier").mkdir(exist_ok=True)
    (cfg / "classifier" / "extra.yaml").write_text("a: 1\n")  # config is recursive
    assert fp() != before
    before = fp()
    (maps / "y.txt").write_text("ignored")  # only png / geojson count
    assert fp() == before
    (maps / "y.png").write_bytes(PNG)
    assert fp() != before


def test_page_cache_rebuilds_only_when_fingerprint_differs():
    cache, calls = PageCache(), Counter()

    def build():
        calls.update(["b"])
        return calls["b"]

    assert [cache.get("a", (1,), build), cache.get("a", (1,), build)] == [1, 1]
    assert cache.get("a", (2,), build) == 2
    assert cache.get("b", (2,), build) == 3  # one entry per name


def test_page_cache_builds_once_under_concurrent_gets():
    cache, builds = PageCache(), Counter()
    start = threading.Barrier(8)

    def build():
        builds.update(["n"])
        time.sleep(0.05)  # long enough for every other thread to arrive while this one builds
        return builds["n"]

    results = []

    def worker():
        start.wait()
        results.append(cache.get("page", (1,), build))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert builds["n"] == 1 and results == [1] * 8


def test_csv_commit_and_generated_line_are_of_the_request_not_the_cache(client, monkeypatch):
    from velometer.app import main

    monkeypatch.setattr(main, "git_commit", lambda: "aaaaaaaa" * 5)
    first = client.get("/data/berlin.csv").text.splitlines()
    monkeypatch.setattr(main, "git_commit", lambda: "bbbbbbbb" * 5)
    second = client.get("/data/berlin.csv").text.splitlines()
    assert first[0] == second[0] and first[0].startswith("# Map data ©")
    assert first[1] != second[1]  # the provenance line follows git_commit()
    assert "aaaaaaa" in first[1] and "bbbbbbb" in second[1]
    assert first[2:] == second[2:]  # the table is the cached part


def test_lazy_data_forwards_only_public_report_data_attributes(fixture_db):
    from velometer.app.main import LazyData

    db_path, cfg, _conn, _data = fixture_db
    lazy = LazyData(db_path, cfg)
    try:
        assert [c.id for c in lazy.cities()] == ["berlin", "paris"]  # a public method
        assert lazy.config_dir == cfg and lazy.report_config.highlight  # public attributes
        for name in ("_series", "_cities", "no_such_attribute", "__deepcopy__"):
            with pytest.raises(AttributeError):
                getattr(lazy, name)
        assert not hasattr(lazy, "conn_typo")
    finally:
        lazy.close()


def test_the_fingerprint_is_computed_once_per_request(setup, monkeypatch):
    from velometer.app import main

    db_path, cfg, maps, docs = setup
    calls = []

    def counting(*args):
        calls.append(args)
        return fingerprint(*args)

    monkeypatch.setattr(main, "fingerprint", counting)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        for path in ["/", "/city/berlin", "/data/berlin.csv", "/methodology"]:
            calls.clear()
            assert c.get(path).status_code == 200
            assert len(calls) == 1, path


def test_every_route_200_at_21_cities(client_21):
    for path in ["/", "/city/berlin", "/city/c21", "/data/all.csv", "/methodology"]:
        assert client_21.get(path).status_code == 200


def test_png_export_at_21_cities(report_db_21, tmp_path):
    db_path, cfg = report_db_21
    conn = open_readonly(db_path)
    try:
        paths = charts.write_pngs(ReportData(conn, cfg), tmp_path / "png")
    finally:
        conn.close()
    pngs = [p for p in paths if p.suffix == ".png"]
    assert len(pngs) == 3 and all(p.stat().st_size > 0 for p in pngs)


def test_warm_page_times_are_reported(client_21, capsys):
    rows = []
    for path in ["/", "/city/berlin", "/city/c21", "/data/all.csv", "/methodology"]:
        t0 = time.perf_counter()
        client_21.get(path)
        cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        client_21.get(path)
        rows.append((path, cold * 1000, (time.perf_counter() - t0) * 1000))
    with capsys.disabled():
        print(f"\n{'route':<16} {'cold ms':>10} {'warm ms':>10}")
        for path, cold, warm in rows:
            print(f"{path:<16} {cold:>10.0f} {warm:>10.0f}")


def test_maps_of_an_untrusted_city_are_404(report_db_with_trust, tmp_path):
    db_path, cfg = report_db_with_trust(countries={"DE": {"status": "trusted", "basis": "t"}})
    maps = tmp_path / "maps3"
    maps.mkdir()
    for city in ("berlin", "paris"):  # both have files; only Berlin's country is trusted
        (maps / f"{city}_lau.png").write_bytes(PNG)
        (maps / f"{city}_lau.geojson").write_bytes(GEOJSON)
    with _client(create_app(db_path, cfg, maps, _docs(tmp_path / "d3"), content_dir=CONTENT)) as c:
        assert c.get("/maps/berlin_lau.png").status_code == 200
        assert c.get("/maps/berlin_lau.geojson").status_code == 200
        assert c.get("/maps/paris_lau.png").status_code == 404
        assert c.get("/maps/paris_lau.geojson").status_code == 404


# --- Bezirke: subarea table, small multiples, change map and subarea CSV (M6 Task 10) ----------

CHANGE_STEM = "berlin_change_2023-01-01_current"  # the shipped report.yaml change_window


def _change_markdown(run_to: int = 2, west: str = "West") -> str:
    from velometer.report import change as ch

    rows = [
        ch.ChangeRow("gained", None, 7, "right", None, "A", 1.25, {"west": 1.25}),
        ch.ChangeRow("lost", 8, None, "left", "B", None, 0.5, {"east": 0.5}),
    ]
    result = ch.ChangeResult(rows, {"A": 1.0}, {"A": 2.0})
    run = {"id": 1, "osm_timestamp": "2023-01-01T00:00:00Z", "classifier_version": "v4",
           "boundary_sha256": "b" * 64}  # fmt: skip
    md = ch.render_markdown(
        result, "Berlin", run, {**run, "id": run_to}, {"west": west, "east": "East"}
    )
    return md + "\nMARKER-BEYOND-THE-TABLE\n"


def _latest_lau_run(db_path, cfg) -> int:
    from velometer.db import open_db
    from velometer.selection import report_selector

    with open_db(db_path) as conn:
        return report_selector(cfg).latest(conn, "berlin", "lau")


@pytest.fixture
def subarea_setup(tmp_path):
    from tests.report_fixture import build_report_fixture_subareas

    db_path, cfg = build_report_fixture_subareas(tmp_path)
    maps = tmp_path / "maps"
    maps.mkdir()
    return db_path, cfg, maps, _docs(tmp_path)


@pytest.fixture
def subarea_client(subarea_setup):
    with _client(create_app(*subarea_setup, content_dir=CONTENT)) as c:
        yield c


def _write_change(maps: Path, docs: Path, stem: str = CHANGE_STEM, **kw) -> None:
    (maps / f"{stem}.geojson").write_bytes(GEOJSON)
    (docs / "review" / f"{stem}.md").write_text(_change_markdown(**kw))


def test_city_page_has_the_bezirke_table_and_small_multiples(subarea_client):
    html = nolabels(subarea_client.get("/city/berlin/bezirke").text)
    assert "<h2>Bezirke</h2>" in html
    bezirke = html.split("<h2>Bezirke</h2>")[1].split("<h2>")[0]
    assert "<td>West</td>" in bezirke and "<td>East</td>" in bezirke
    assert "4.0" in bezirke  # West's headline, 4 %
    assert '<div class="chart" data-chart="bezirke" data-city="berlin"' in bezirke
    # the small multiples' values, without JavaScript: a row per Bezirk, a column per snapshot
    table = bezirke.split("Table: headline per Bezirk")[1].split("</table>")[0]
    assert re.findall(r"<tr><td>(\w+)</td>", table) == ["East", "West"]


def test_bezirke_table_ends_with_the_remainder_row_and_its_note(subarea_client):
    html = nolabels(subarea_client.get("/city/berlin/bezirke").text)
    bezirke = html.split("<h2>Bezirke</h2>")[1].split("<h3>")[0]
    body = bezirke.split("<tbody>")[1].split("</tbody>")[0]
    rows = body.split("<tr")[1:]
    assert ["<td>East</td>" in rows[0], "<td>West</td>" in rows[1]] == [True, True]
    assert len(rows) == 3 and 'class="remainder"' in rows[2]
    assert "<td>Outside the 2 Bezirke (LAU edge)</td>" in rows[2]
    assert 'class="remainder"' not in "".join(rows[:2])
    note = bezirke.split("</table>")[1]
    assert (
        "Road and path km inside the city's LAU boundary but outside every Bezirk polygon; "
        "the LAU is generalised at 1:1M (ADR 0004)." in note
    )


def test_city_without_subareas_has_no_bezirke(client):
    html = client.get("/city/berlin").text  # the plain fixture: no subareas in config
    assert "Bezirke</a></li>" not in html and "_subareas.csv" not in html  # no tab, no CSV
    assert client.get("/city/berlin/bezirke").status_code == 404


def test_other_city_of_a_subarea_config_has_no_bezirke(subarea_client):
    assert "Bezirke</a></li>" not in subarea_client.get("/city/paris").text
    assert subarea_client.get("/city/paris/bezirke").status_code == 404


def test_bezirke_without_a_change_file_says_so_and_loads_no_change_map(subarea_client):
    html = subarea_client.get("/city/berlin/bezirke").text
    assert "No change map generated yet" in html
    assert "changemap" not in html.replace("No change map", "")


def test_bezirke_with_change_files_show_the_map_and_the_per_bezirk_table(subarea_setup):
    db_path, cfg, maps, docs = subarea_setup
    _write_change(maps, docs)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        html = nolabels(c.get("/city/berlin/bezirke").text)
        assert "No change map generated yet" not in html
        assert f"/maps/{CHANGE_STEM}.geojson" in html
        assert "/static/changemap.js" in html and "/static/vendor/leaflet.js" in html
        table = html.split("<h3>Mapped change")[1].split("</table>")[0]
        assert "<td>West</td>" in table and "<td>East</td>" in table and "1.250" in table
        assert "MARKER-BEYOND-THE-TABLE" not in html  # only the generated table, not the page
        assert c.get(f"/maps/{CHANGE_STEM}.geojson").status_code == 200


def test_change_section_names_its_runs_and_is_not_stale_on_the_latest_run(subarea_setup):
    db_path, cfg, maps, docs = subarea_setup
    latest = _latest_lau_run(db_path, cfg)
    _write_change(maps, docs, run_to=latest)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        section = c.get("/city/berlin/bezirke").text.split("<h3>Mapped change")[1]
    assert f"Run 1 → run {latest}" in section
    assert "older than" not in section and "Regenerate it" not in section


def test_change_section_says_when_the_change_map_is_older_than_the_figures(subarea_setup):
    db_path, cfg, maps, docs = subarea_setup
    latest = _latest_lau_run(db_path, cfg)
    _write_change(maps, docs, run_to=latest - 1)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        section = c.get("/city/berlin/bezirke").text.split("<h3>Mapped change")[1]
    assert f"Run 1 → run {latest - 1}" in section
    assert f"ends at run {latest - 1}, not at the run {latest} of the figures above" in section
    assert "<code>velometer report change --city berlin</code>" in section


def test_change_table_never_passes_raw_html(subarea_setup):
    db_path, cfg, maps, docs = subarea_setup
    stem = CHANGE_STEM
    _write_change(maps, docs, run_to=_latest_lau_run(db_path, cfg), west="<b>West</b>")
    md = docs / "review" / f"{stem}.md"
    assert "&lt;b&gt;West&lt;/b&gt;" in md.read_text()  # render_markdown escapes the name
    # a hand-edited page with raw HTML in the table is escaped by the app too
    md.write_text(md.read_text().replace("| East |", "| <i>East</i> |"))
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        section = (
            c.get("/city/berlin/bezirke").text.split("<h3>Mapped change")[1].split("</table>")[0]
        )
    assert "<b>" not in section and "<i>" not in section
    assert "&lt;b&gt;West&lt;/b&gt;" in section and "&lt;i&gt;East&lt;/i&gt;" in section


def test_change_geojson_route_refuses_unknown_and_missing_files(subarea_setup):
    db_path, cfg, maps, docs = subarea_setup
    _write_change(maps, docs)
    (maps / "paris_change_2023-01-01_current.geojson").write_bytes(GEOJSON)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        assert c.get("/maps/berlin_change_2022-01-01_current.geojson").status_code == 404
        assert c.get("/maps/berlin_change_x_y.geojson").status_code == 404
        assert c.get("/maps/nowhere_change_2023-01-01_current.geojson").status_code == 404


def test_subarea_csv_has_provenance_columns_the_odbl_line_and_a_row_per_tier(subarea_client):
    import csv
    import io

    text = subarea_client.get("/data/berlin_subareas.csv").text
    lines = text.splitlines()
    assert lines[0].startswith("# Map data © OpenStreetMap contributors, ODbL 1.0")
    assert lines[1].startswith("# velometer ")
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[2:]))))
    assert list(rows[0]) == [
        "city_id", "subarea_id", "name", "run_id", "osm_timestamp", "classifier_version",
        "git_commit", "config_sha256", "boundary_sha256", "subarea_sha", "tier", "length_basis",
        "length_km",
    ]  # fmt: skip
    assert {r["subarea_id"] for r in rows} == {"west", "east", "remainder"}
    west_a = [r for r in rows if r["subarea_id"] == "west" and r["tier"] == "A"]
    assert {r["length_basis"] for r in west_a} == {"per_side", "qecio_weighted"}
    assert {r["length_km"] for r in west_a} == {"3.000"}
    assert all(r["git_commit"] for r in rows)
    assert {(r["subarea_id"], r["name"]) for r in rows} == {
        ("west", "West"),
        ("east", "East"),
        ("remainder", "Outside the 2 Bezirke (LAU edge)"),
    }
    for run_id in {r["run_id"] for r in rows}:  # the remainder's rows close each run's block
        ids = [r["subarea_id"] for r in rows if r["run_id"] == run_id]
        assert ids[-2:] == ["remainder"] * 2 and "remainder" not in ids[:-2]
    assert (
        "attachment"
        in subarea_client.get("/data/berlin_subareas.csv").headers["content-disposition"]
    )


def test_subarea_csv_commit_and_generated_line_are_of_the_request(subarea_client, monkeypatch):
    from velometer.app import main

    monkeypatch.setattr(main, "git_commit", lambda: "aaaaaaaa" * 5)
    first = subarea_client.get("/data/berlin_subareas.csv").text.splitlines()
    monkeypatch.setattr(main, "git_commit", lambda: "bbbbbbbb" * 5)
    second = subarea_client.get("/data/berlin_subareas.csv").text.splitlines()
    assert "aaaaaaa" in first[1] and "bbbbbbb" in second[1]
    assert first[2:] == second[2:]


def test_subarea_csv_of_a_city_without_subareas_is_404(subarea_client):
    assert subarea_client.get("/data/paris_subareas.csv").status_code == 404
    assert subarea_client.get("/data/nowhere_subareas.csv").status_code == 404


def test_pending_country_hides_bezirke_csv_and_change_geojson(subarea_setup):
    import yaml

    db_path, cfg, maps, docs = subarea_setup
    _write_change(maps, docs)
    with _client(
        create_app(db_path, cfg, maps, docs, content_dir=CONTENT)
    ) as c:  # control: DE is trusted
        assert c.get("/city/berlin").status_code == 200
        assert c.get("/data/berlin_subareas.csv").status_code == 200
        assert c.get(f"/maps/{CHANGE_STEM}.geojson").status_code == 200
    trust = yaml.safe_load((cfg / "trust.yaml").read_text())
    trust["countries"] = {k: v for k, v in trust["countries"].items() if k != "DE"}
    trust["countries"]["FR"] = {"status": "trusted", "basis": "t"}
    (cfg / "trust.yaml").write_text(yaml.safe_dump(trust))
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        assert c.get("/city/berlin").status_code == 404
        assert c.get("/data/berlin_subareas.csv").status_code == 404
        assert c.get(f"/maps/{CHANGE_STEM}.geojson").status_code == 404


def test_fingerprint_follows_the_change_page(subarea_setup):
    db_path, cfg, maps, docs = subarea_setup
    before = fingerprint(db_path, cfg, docs, maps)
    (docs / "review" / f"{CHANGE_STEM}.md").write_text(_change_markdown())
    assert fingerprint(db_path, cfg, docs, maps) != before


def _add_reported(db_path, **overrides):
    from tests.report_fixture import _figure
    from velometer.db import open_db, replace_external_figures

    base = _figure("berlin", "official", "new_cycle_infra_km", 21.2)
    rows = [
        base.model_copy(update={"network_scope": "vorrangnetz", "value": 17.3, **overrides}),
        base.model_copy(update={"source_url": "", "value": 20.5, "reference_date": None}),
    ]
    with open_db(db_path) as conn:
        replace_external_figures(conn, "official", rows)


def test_reported_figures_skip_the_comparison_layers_and_sort_by_date(fixture_db_path, setup):
    from datetime import date

    _add_reported(fixture_db_path, reference_date=date(2024, 12, 31), length_basis="streckenlaenge")
    conn = open_readonly(fixture_db_path)
    try:
        figs = ReportData(conn, setup[1]).reported_figures("berlin")
    finally:
        conn.close()
    assert {f.source for f in figs} == {"official"}  # fixture also holds clean_cities, qecio
    assert [f.value for f in figs] == [17.3, 20.5]  # dated first, undated last
    assert (figs[0].network_scope, figs[0].length_basis) == ("vorrangnetz", "streckenlaenge")


def test_city_page_lists_reported_figures_with_link_or_no_url_note(setup):
    db_path, cfg, maps, docs = setup
    _add_reported(db_path, length_basis="unknown")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        html = c.get("/city/berlin/figures").text
        other = c.get("/city/paris/figures").text
    section = html.split("<h2>Official and reported figures</h2>")[1].split("</section>")[0]
    assert (
        section.count("<td>new_cycle_infra_km") == 0
        and section.count("<code>new_cycle_infra_km</code>") == 2
    )
    assert 'href="https://example.invalid/fixture"' in section
    assert 'href=""' not in section
    assert section.count("no source URL recorded") == 1
    text = _text(section)
    assert "17.3" in text and "20.5" in text and "vorrangnetz" in text and "unknown" in text
    assert "clean_cities_2025" not in section and "qecio" not in section
    assert "no official or reported figures for Paris" in _text(other)


def test_fingerprint_follows_the_external_figures_csv(setup):
    db, cfg, maps, docs = setup
    before = fingerprint(db, cfg, docs, maps)
    (cfg / "external").mkdir(exist_ok=True)
    (cfg / "external" / "figures.csv").write_text("city_id\n")
    assert fingerprint(db, cfg, docs, maps) != before


def test_non_http_source_url_is_never_a_link(setup):
    db_path, cfg, maps, docs = setup
    _add_reported(db_path, source_url="javascript:alert(1)")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        html = c.get("/city/berlin/figures").text
    section = html.split("<h2>Official and reported figures</h2>")[1].split("</section>")[0]
    assert 'href="javascript:' not in html and "javascript:" not in section
    assert section.count("no source URL recorded") == 2  # the bad scheme and the blank one


def test_an_upper_case_http_scheme_is_a_link(setup):
    db_path, cfg, maps, docs = setup
    _add_reported(db_path, source_url="HTTPS://example.org/report")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        html = c.get("/city/berlin/figures").text
    section = html.split("<h2>Official and reported figures</h2>")[1].split("</section>")[0]
    assert 'href="HTTPS://example.org/report"' in section


def test_reported_figure_note_gets_its_own_full_width_row(setup):
    # A long source note in the link cell squeezed that column to a word per line (M6 render).
    db_path, cfg, maps, docs = setup
    _add_reported(db_path, note="primary: Drucksache 19/25987, table Vorrangnetz")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        html = nolabels(c.get("/city/berlin/figures").text)
    section = html.split("<h2>Official and reported figures</h2>")[1].split("</section>")[0]
    link_cell = section.split('rel="noopener noreferrer">source</a>')[1].split("</td>")[0]
    assert "Drucksache" not in link_cell
    assert '<td colspan="8" class="meta">primary: Drucksache 19/25987' in section
