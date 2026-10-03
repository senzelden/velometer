"""The private read-only web app (`velometer serve`), on the shared report fixture DB."""

import gzip
import hashlib
import importlib.resources
import json
import re
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import altair as alt
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from velometer.app.main import create_app
from velometer.cli import app as cli_app
from velometer.report import charts

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


@pytest.fixture
def setup(fixture_db, tmp_path):
    db_path, cfg, _conn, _data = fixture_db
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
def client(setup):
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        yield c


@pytest.fixture
def fixture_db_path(setup):
    return setup[0]


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


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
    r = client.get("/city/paris")
    assert r.status_code == 200
    text = _text(r.text)
    assert "no run (LAU current)" in text  # headline, LAU vs FUA, comparison, map
    assert "no run (FUA history)" in text  # tier composition, flagged years
    assert "no run (LAU current) to compare" in text
    assert "map not generated" not in text  # no run, so no map to generate


def test_index_lists_cities_with_links_and_charts(client):
    html = client.get("/").text
    assert 'href="/city/berlin"' in html and 'href="/city/paris"' in html
    assert html.count("vegaEmbed('#") == 2  # headline over time, rankings flip
    row = re.search(r'<tr[^>]*>\s*<td[^>]*><a href="/city/paris">.*?</tr>', html, re.S)
    assert row and "no run" in row.group(0)


def test_city_page_sections_in_order(client):
    text = _text(client.get("/city/berlin").text)
    order = [
        "Headline and presets",
        "Tier composition",
        "LAU vs FUA",
        "Flagged years",
        "Comparison with published figures",
        "Tier map",
        "Provenance",
    ]
    positions = [text.find(h) for h in order]
    assert -1 not in positions, dict(zip(order, positions, strict=True))
    assert positions == sorted(positions)


def test_city_page_shows_current_numbers(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    point = data.current("berlin", "lau")
    text = _text(client.get("/city/berlin").text)
    section = text[text.find("Headline and presets") : text.find("Tier composition")]
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
    html = client.get("/city/berlin").text
    assert "berlin/lau/2025" in html
    assert "activity_spike" in html
    assert EXPLANATION in html
    assert "<code>config/activity.yaml</code>" in html  # rendered as markdown
    assert "Not a fixture flag." not in html


def test_flag_without_explanation_says_so(setup):
    db_path, cfg, maps, docs = setup
    (docs / "review" / "m3_timeseries.md").write_text("# empty\n")
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        r = c.get("/city/berlin")
    assert r.status_code == 200
    assert "no explanation" in _text(r.text)


def test_reconcile_rows_on_city_page(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    gaps = data.reconcile("berlin").gaps
    html = client.get("/city/berlin").text
    section = html[html.find("Comparison with published figures") : html.find("Tier map")]
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
    return html[html.index("<h2>Tier map</h2>") : html.index("<h2>Provenance</h2>")]


def _map_config(html: str) -> dict | None:
    m = re.search(r'<script type="application/json" id="tiermap-config">(.*?)</script>', html, re.S)
    return None if m is None else json.loads(m.group(1))


def test_city_page_interactive_map_with_png_link_and_hint(client):
    html = client.get("/city/berlin").text
    section = _map_section(html)
    assert '<div id="tiermap"' in section
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', section)
    assert scripts == ["/static/vendor/leaflet.js", "/static/map.js"]
    assert '<link rel="stylesheet" href="/static/vendor/leaflet.css">' in html.split("</head>")[0]
    for s in scripts + ["/static/vendor/leaflet.css"]:
        assert client.get(s).status_code == 200
    cfg = _map_config(section)
    assert cfg["kinds"] == [{"kind": "lau", "label": "LAU", "url": "/maps/berlin_lau.geojson"}]
    assert cfg["colours"] == dict(zip("ABCDE", charts.TIER_COLOURS, strict=True))
    assert cfg["labels"] == charts.TIER_LABEL
    for t, colour in zip("ABCDE", charts.TIER_COLOURS, strict=True):  # the tier checkboxes
        box = re.search(
            rf'<input type="checkbox" name="tier" value="{t}"[^>]*>'
            rf'\s*<span class="swatch" style="background: ([^"]+)">',
            section,
        )
        assert box and box.group(1) == colour, t
    assert re.findall(r'<input type="radio" name="kind" value="(\w+)"', section) == ["lau"]
    assert re.search(r'<a href="/maps/berlin_lau.png">[^<]*static image', section)
    assert '<a href="/maps/berlin_fua.png"' not in section  # no PNG either
    assert "<img" not in section
    # FUA has a current run but no GeoJSON: the existing hint
    assert "map not generated (<code>velometer report maps</code>)" in section


def test_city_page_without_any_geojson_loads_no_map(setup):
    db_path, cfg, maps, docs = setup
    (maps / "berlin_lau.geojson").unlink()
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        section = _map_section(c.get("/city/berlin").text)
    assert '<div id="tiermap"' not in section and "<script" not in section
    assert section.count("map not generated (<code>velometer report maps</code>)") == 2
    assert '<a href="/maps/berlin_lau.png">' in section  # the static image is still there


def _loaded_hosts(html: str) -> set[str]:
    """Hosts the page loads from: every absolute URL except anchors' hrefs and the map config's
    `links` (way pages and the copyright note are links a reader follows, not loads)."""
    html = re.sub(r'<a\s[^>]*href="[^"]*"', "<a", html)
    cfg = _map_config(html)
    if cfg is not None:
        cfg.pop("links")
        html = re.sub(r'(id="tiermap-config">).*?(</script>)', lambda m: m.group(1) +
                      json.dumps(cfg) + m.group(2), html, flags=re.S)  # fmt: skip
    return {urlparse(u).hostname for u in URL.findall(html)}


def test_pages_load_only_static_assets_and_osm_tiles(client):
    """The one external host a page loads from is the OSM tile server; scripts and CSS are ours."""
    for path in ["/", "/city/berlin", "/city/paris", "/methodology", "/methodology/de"]:
        html = client.get(path).text
        scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
        assert scripts and all(s.startswith("/static/") for s in scripts), path
        css = re.findall(r'<link[^>]+href="([^"]+)"', html)
        assert css and all(c.startswith("/static/") for c in css), path
        assert all(i.startswith("/") and not i.startswith("//")
                   for i in re.findall(r'<img[^>]+src="([^"]+)"', html)), path  # fmt: skip
        assert _loaded_hosts(html) <= {OSM_TILES}, path
    city = client.get("/city/berlin").text
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
    cfg = _map_config(client.get("/city/berlin").text)
    cls = cfg["tile_class"]
    assert cls and cls != "leaflet-tile-pane"
    rules = _css_rules((STATIC / "app.css").read_text())
    decls = [d for sels, d in rules if f".{cls}" in sels]
    assert decls, cls
    rule = {k: v for d in decls for k, v in d.items()}
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


def test_scripts_load_vega_then_lite_then_embed(client):
    html = client.get("/").text
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', html)
    assert srcs == [
        "/static/vendor/vega.min.js",
        "/static/vendor/vega-lite.min.js",
        "/static/vendor/vega-embed.min.js",
    ]
    for s in srcs:
        assert client.get(s).status_code == 200


def test_footer_on_every_page(client, fixture_db):
    _db, _cfg, _conn, data = fixture_db
    for path in ["/", "/city/berlin", "/city/paris", "/methodology", "/methodology/de"]:
        html = client.get(path).text
        footer = html[html.index("<footer") :]
        text = _text(footer)
        assert "© OpenStreetMap contributors, ODbL 1.0" in text
        assert "OSM mapped km, not built km (ADR 0006)" in text
        assert 'href="/methodology"' in footer
        assert data.selector.version in text and data.selector.short_sha in text


def test_methodology_rendered_with_tables_and_language_links(client):
    html = client.get("/methodology").text
    assert "<table>" in html and "separated track" in html
    assert "<pre><code>velometer run" in html  # fenced_code
    assert 'href="/methodology/de"' in html
    de = client.get("/methodology/de").text
    assert "Getrennter Radweg." in de and 'href="/methodology"' in de


def test_missing_methodology_is_a_note_not_an_error(setup):
    db_path, cfg, maps, docs = setup
    (docs / "methodology.md").unlink()
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        r = c.get("/methodology")
    assert r.status_code == 200
    assert "methodology not generated" in _text(r.text)


def test_missing_db_at_request_time_is_503_not_500(setup):
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path.with_name("gone.sqlite"), cfg, maps, docs)) as c:
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


def test_charts_are_inline_specs_without_remote_urls(client):
    html = client.get("/city/berlin").text
    specs = re.findall(r"vegaEmbed\('#(c\d+)', (\{.*?\}), \{actions", html, re.S)
    assert specs
    for div_id, spec in specs:
        assert f'<div id="{div_id}"' in html
        assert '"url"' not in spec and "$schema" not in spec


def test_templates_and_static_ship_in_the_package():
    root = importlib.resources.files("velometer.app")
    for name in ["base.html", "index.html", "city.html", "methodology.html"]:
        assert (root / "templates" / name).is_file()
    assert (root / "static" / "app.css").is_file()
    assert (root / "static" / "map.js").is_file()
    for pkg in ["vega", "vega-lite", "vega-embed"]:
        assert (root / "static" / "vendor" / f"{pkg}.min.js").is_file()
        assert (root / "static" / "vendor" / f"{pkg}.LICENSE").is_file()
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


def test_vendor_versions_match_altair():
    expected = {
        "vega": alt.VEGA_VERSION,
        "vega-lite": alt.VEGALITE_VERSION,
        "vega-embed": alt.VEGAEMBED_VERSION,
    }
    rows = [r for pkg, r in _versions().items() if pkg != "leaflet"]  # leaflet is not altair's
    assert {r[0]: r[1] for r in rows} == expected
    for pkg, _constant, resolved in rows:
        assert resolved.split(".")[0] == expected[pkg].split(".")[0]
        assert resolved.startswith(expected[pkg])
        bundle = (VENDOR / f"{pkg}.min.js").read_text()
        assert f'"{resolved}"' in bundle  # the bundle is the resolved release
        assert "cdn.jsdelivr" not in bundle and "unpkg.com" not in bundle
        assert (
            "BSD" in (VENDOR / f"{pkg}.LICENSE").read_text()
            or "Redistribution" in (VENDOR / f"{pkg}.LICENSE").read_text()
        )


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
        assert label.startswith("Ours") and label in headers
    assert all(h.startswith("Ours") for h in headers if "QECIO" in h or "Clean Cities" in h)
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
    path.write_text(path.read_text().replace("Ours: QECIO method", "Ours: QECIO test label"))
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        assert "Ours: QECIO test label" in _headers(c.get("/").text)
        assert "Ours: QECIO test label" in _text(c.get("/city/berlin").text)


def test_app_follows_report_classifier_of_the_config(setup):
    """Spec section 5: the app defaults to config/report.yaml, red-proofed in a copied config."""
    db_path, cfg, maps, docs = setup
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        before = c.get("/city/berlin").text
    assert "Classifier v2" in _text(before)
    assert "no run (LAU current)" not in _text(before)
    path = cfg / "report.yaml"
    path.write_text(path.read_text().replace("report_classifier: v2", "report_classifier: v1"))
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        after = _text(c.get("/city/berlin").text)
    assert "Classifier v1" in after and "Classifier v2" not in after
    assert "no run (LAU current)" in after  # the fixture's runs are on v2 only


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
    with _client(create_app(old, cfg, maps, docs)) as c:
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
    with _client(create_app(db_path, cfg, maps, docs)) as c:
        r = c.get("/city/berlin")
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
    with _client(create_app(db_path, cfg, maps, _docs(tmp_path / "d2"))) as c:
        assert c.get("/city/berlin").status_code == 200
        assert c.get("/city/paris").status_code == 404
        assert "/city/paris" not in c.get("/").text
        assert "/city/berlin" in c.get("/").text
