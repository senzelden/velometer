"""The private read-only web app (`velometer serve`), on the shared report fixture DB."""

import hashlib
import importlib.resources
import re
from pathlib import Path

import altair as alt
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from velometer.app.main import create_app
from velometer.cli import app as cli_app

VENDOR = Path(__file__).parents[1] / "src" / "velometer" / "app" / "static" / "vendor"
EXPLANATION = "Fixture cause: a spike of 50 edits in the fixture activity rows."
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
ROUTES = ["/", "/city/berlin", "/city/paris", "/methodology", "/methodology/de"]
ROUTES += ["/data/all.csv", "/data/berlin.csv", "/maps/berlin_lau.png"]


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
    for name in ["Berlin_lau.png", "berlin_xyz.png"]:  # present, but not valid map names
        (maps / name).write_bytes(PNG)
    (tmp_path / "secret.png").write_bytes(PNG)
    docs = _docs(tmp_path)
    return db_path, cfg, maps, docs


@pytest.fixture
def client(setup):
    db_path, cfg, maps, docs = setup
    with TestClient(create_app(db_path, cfg, maps, docs)) as c:
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
    assert f"Headline (ours) {headline.value:,.1f} {headline.per_100k:,.1f}" in section
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
    with TestClient(create_app(db_path, cfg, maps, docs)) as c:
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


def test_city_page_map_image_or_note(client):
    html = client.get("/city/berlin").text
    assert '<img src="/maps/berlin_lau.png"' in html
    assert '<img src="/maps/berlin_fua.png"' not in html
    assert "map not generated (<code>velometer report maps</code>)" in html


def test_pages_reference_only_local_scripts(client):
    for path in ["/", "/city/berlin", "/city/paris", "/methodology"]:
        html = client.get(path).text
        assert re.findall(r'<script[^>]+src="([^"]+)"', html)
        assert all(s.startswith("/static/") for s in re.findall(r'<script[^>]+src="([^"]+)"', html))
        assert "http://" not in html.split("<footer")[0]
        assert "https://" not in html.split("<footer")[0]
        css = re.findall(r'<link[^>]+href="([^"]+)"', html)
        assert css == ["/static/app.css"]


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
    with TestClient(create_app(db_path, cfg, maps, docs)) as c:
        r = c.get("/methodology")
    assert r.status_code == 200
    assert "methodology not generated" in _text(r.text)


def test_missing_db_at_request_time_is_503_not_500(setup):
    db_path, cfg, maps, docs = setup
    with TestClient(create_app(db_path.with_name("gone.sqlite"), cfg, maps, docs)) as c:
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
    for pkg in ["vega", "vega-lite", "vega-embed"]:
        assert (root / "static" / "vendor" / f"{pkg}.min.js").is_file()
        assert (root / "static" / "vendor" / f"{pkg}.LICENSE").is_file()


def test_vendor_versions_match_altair():
    expected = {
        "vega": alt.VEGA_VERSION,
        "vega-lite": alt.VEGALITE_VERSION,
        "vega-embed": alt.VEGAEMBED_VERSION,
    }
    rows = [
        line.split()
        for line in (VENDOR / "VERSIONS").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
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
    with TestClient(app) as c:
        assert c.get("/city/berlin").status_code == 200


def test_serve_missing_db_exits_1(tmp_path, monkeypatch):
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: pytest.fail("uvicorn.run called"))
    result = CliRunner().invoke(cli_app, ["serve", "--db", str(tmp_path / "none.sqlite")])
    assert result.exit_code == 1
    assert "not found" in result.output
