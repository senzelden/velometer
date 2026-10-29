"""M16 Task 5: the self-hosted vector basemap (spec §4.3, docs/review/m16-legal.md 1.7, 1.8, 5.9).

The three Leaflet maps draw a Protomaps extract served beside the site at TILES_PATH with the
vendored protomaps-leaflet; no page loads anything from another host (the CSP names none), the
export and deploy-check accept the one file served beside the export, `velometer serve --tiles`
serves it with byte ranges, and the old raster-tile CSS filters are gone (review focus 5).
"""

import hashlib
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.helpers import load_script
from tests.test_app import _client
from tests.test_app_base import BASE, _app, _config, rich  # noqa: F401  (`rich` is a fixture)
from tests.test_export import _export
from tests.test_m15_dryrun import ORIGIN, fake_fetch, tiny  # noqa: F401  (`tiny` is a fixture)
from tests.test_m15_dryrun import dr as dr15
from velometer import i18n
from velometer.app import deploy_check, export
from velometer.app.main import CSP, TILES_PATH, csp_meta
from velometer.cli import app as cli_app

ROOT = Path(__file__).parents[1]
STATIC = ROOT / "src" / "velometer" / "app" / "static"
VENDOR = STATIC / "vendor"
FIXTURE = ROOT / "tests" / "fixtures" / "tiles" / "berlin-z0-8.pmtiles"
OSM_TILE_HOST = "tile.openstreetmap.org"
MAP_PAGES = {  # page -> its map config block
    "/city/berlin/tiers": "tiermap-config",
    "/city/berlin/bezirke": "changemap-config",
    "/city/berlin/counts": "countermap-config",
}
MAP_TEMPLATES = ("city/tiers.html", "city/bezirke.html", "city/counts.html")


# --- the CSP and the export: no foreign host --------------------------------------------------


def test_the_csp_allows_no_host_but_the_own():
    assert OSM_TILE_HOST not in CSP
    assert "http:" not in CSP and "https:" not in CSP and "//" not in CSP
    directives = dict(d.strip().split(" ", 1) for d in CSP.split(";") if d.strip())
    assert directives["img-src"] == "'self' data:"
    assert directives["connect-src"] == "'self'"  # the byte-range requests for the tiles
    # protomaps-leaflet runs on the page itself: no worker, no blob: source
    assert "worker-src" not in directives and "blob:" not in CSP


def test_the_tiles_path_is_relative_to_the_base():
    assert TILES_PATH == "tiles/velometer.pmtiles"
    assert frozenset({TILES_PATH}) == export.SERVED_BESIDE
    assert frozenset() == export.LOADED_HOSTS


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    """The static export of the rich fixture under /velometer/ (every map page present)."""
    from tests.test_app_base import build_rich

    tmp = tmp_path_factory.mktemp("m16-basemap")
    out = tmp / "out"
    _export(build_rich(tmp), out, BASE)
    return out


def test_no_exported_file_names_the_osm_tile_server(exported):
    files = [p for p in exported.rglob("*") if p.is_file() and p.suffix != ".gz"]
    assert len(files) > 20
    hits = [
        p.relative_to(exported).as_posix()
        for p in files
        if OSM_TILE_HOST.encode() in p.read_bytes()
    ]
    assert hits == []
    headers = (exported / export.HEADERS_FILE).read_text(encoding="utf-8")
    assert f"Content-Security-Policy: {csp_meta(CSP)}; frame-ancestors 'none'" in headers


def test_the_export_ships_protomaps_leaflet_with_its_licence(exported):
    vendor = exported / "static" / "vendor"
    assert (vendor / "protomaps-leaflet.js").read_bytes() == (
        VENDOR / "protomaps-leaflet.js"
    ).read_bytes()
    assert (vendor / "protomaps-leaflet.LICENSE").is_file()
    assert (exported / "static" / "js" / "basemap.js").is_file()


# --- the map configs ------------------------------------------------------------------------


@pytest.mark.parametrize("base", ["/", BASE])
def test_every_map_config_names_the_tiles_under_the_base(rich, base):  # noqa: F811
    with _client(_app(rich, base_path=base)) as c:
        for page, block in MAP_PAGES.items():
            cfg = _config(c.get(page).text, block)
            assert cfg["tiles"] == base + TILES_PATH, page
            assert "tile_class" not in cfg, page  # no raster layer to mute any more
            assert cfg["links"]["copyright"] == "https://www.openstreetmap.org/copyright"


def test_each_map_page_loads_protomaps_leaflet_between_leaflet_and_its_module(rich):  # noqa: F811
    with _client(_app(rich)) as c:
        for page in MAP_PAGES:
            srcs = re.findall(r'<script[^>]+src="([^"]+)"', c.get(page).text)
            leaflet = srcs.index("/static/vendor/leaflet.js")
            assert srcs[leaflet + 1] == "/static/vendor/protomaps-leaflet.js", page
            assert srcs[leaflet + 2].removeprefix("/static/") in (
                "map.js",
                "changemap.js",
                "countermap.js",
            ), page


# --- deploy-check: the file served beside the export ----------------------------------------


def test_deploy_check_accepts_the_tiles_served_beside_and_nothing_else(exported, tmp_path):
    assert not (exported / TILES_PATH).exists()
    refs = [
        f
        for f in exported.rglob("*.html")
        if f'"tiles": "{BASE}{TILES_PATH}"' in f.read_text(encoding="utf-8")
    ]
    assert len(refs) >= 3  # the tier, change and counter map pages reference it
    assert deploy_check.deploy_problems(exported, None) == []
    # any other missing reference still fails, also one in the tiles directory
    page = refs[0]
    original = page.read_text(encoding="utf-8")
    try:
        for missing in (f"{BASE}tiles/other.pmtiles", f"{BASE}static/nowhere.js"):
            planted = original.replace("</body>", f'<script src="{missing}"></script></body>')
            page.write_text(planted, encoding="utf-8")
            problems = deploy_check.deploy_problems(exported, None)
            rel = page.relative_to(exported).as_posix()
            unresolved = [p for p in problems if p.startswith("unresolved")]  # (and the stale .gz)
            assert unresolved == [f"unresolved reference in {rel}: {missing}"], missing
    finally:
        page.write_text(original, encoding="utf-8")


def test_the_scan_takes_the_tiles_path_only_under_the_base(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(
        '<!doctype html><html><head></head><body><script type="application/json">'
        f'{{"tiles": "/velometer/{TILES_PATH}", "bad": "/{TILES_PATH}"}}</script></body></html>',
        encoding="utf-8",
    )
    assert export.scan_references(site, "/velometer/") == [
        export.Unresolved("index.html", f"/{TILES_PATH}")
    ]


# --- the stylesheet: no raster-tile filter --------------------------------------------------


def test_the_stylesheet_has_no_tile_filter():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "tiermap-tiles" not in css
    assert "invert(" not in css and "hue-rotate(" not in css
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "leaflet" in selector or "tiermap" in selector:
            assert "filter" not in body, selector


def test_a_map_without_its_basemap_shows_the_themed_ground():
    """leaflet.css paints `.leaflet-container` #ddd; a map whose tile file is missing must show
    the theme's own ground instead (review focus 2), so a more specific rule overrides it."""
    css = re.sub(r"/\*.*?\*/", "", (STATIC / "app.css").read_text(encoding="utf-8"), flags=re.S)
    rules = dict((sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css))
    assert "background: var(--panel)" in rules[".tiermap.leaflet-container"]
    leaflet = (VENDOR / "leaflet.css").read_text(encoding="utf-8")
    assert re.search(r"\.leaflet-container\s*\{[^}]*background:\s*#ddd", leaflet)


# --- velometer serve --tiles ----------------------------------------------------------------


def _served_app(monkeypatch, args):
    """The app `velometer serve` would run with `args` (uvicorn.run captured, not started)."""
    import uvicorn

    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app, **kw))
    result = CliRunner().invoke(cli_app, ["serve", *args])
    return result, seen.get("app")


def test_serve_tiles_answers_a_byte_range(monkeypatch, rich):  # noqa: F811
    db, cfg, maps, docs, plans = rich
    common = ["--db", str(db), "--config-dir", str(cfg), "--maps", str(maps), "--docs", str(docs)]
    result, app_ = _served_app(monkeypatch, [*common, "--tiles", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    data = FIXTURE.read_bytes()
    with _client(app_) as c:
        r = c.get("/" + TILES_PATH, headers={"Range": "bytes=0-15"})
        assert r.status_code == 206
        assert r.content == data[:16] and r.content.startswith(b"PMTiles")
        assert r.headers["content-range"] == f"bytes 0-15/{len(data)}"
        # a large range is sent as stored: gzip would break the byte offsets a reader asks for
        r = c.get("/" + TILES_PATH, headers={"Range": "bytes=0-16383", "Accept-Encoding": "gzip"})
        assert r.status_code == 206 and r.content == data[:16384]
        assert r.headers.get("content-encoding", "identity") == "identity"
        assert c.head("/" + TILES_PATH).status_code == 200
    # without --tiles the path is not served
    result, app_ = _served_app(monkeypatch, common)
    with _client(app_) as c:
        assert c.get("/" + TILES_PATH, headers={"Range": "bytes=0-15"}).status_code == 404


def test_serve_refuses_a_missing_tiles_file(monkeypatch, rich, tmp_path):  # noqa: F811
    db, cfg, maps, docs, _plans = rich
    result, app_ = _served_app(
        monkeypatch,
        ["--db", str(db), "--config-dir", str(cfg), "--tiles", str(tmp_path / "none.pmtiles")],
    )
    assert result.exit_code != 0 and app_ is None
    assert "none.pmtiles" in result.output


# --- the vendored library -------------------------------------------------------------------


def _version_row(package: str) -> list[str]:
    for line in (VENDOR / "VERSIONS").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and line.split()[0] == package:
            return line.split()
    raise AssertionError(f"no VERSIONS row for {package}")


def test_protomaps_leaflet_is_the_recorded_release_with_its_checksum():
    _pkg, requested, resolved = _version_row("protomaps-leaflet")
    assert requested == resolved and re.fullmatch(r"\d+\.\d+\.\d+", resolved)  # an exact pin
    versions = (VENDOR / "VERSIONS").read_text(encoding="utf-8")
    url = f"https://cdn.jsdelivr.net/npm/protomaps-leaflet@{resolved}/dist/protomaps-leaflet.js"
    assert url in versions
    digest = hashlib.sha256((VENDOR / "protomaps-leaflet.js").read_bytes()).hexdigest()
    assert f"sha256 {digest}" in versions
    assert "BSD-3-Clause" in versions
    js = (VENDOR / "protomaps-leaflet.js").read_text(encoding="utf-8")
    assert js.startswith('"use strict";var protomapsL=')  # the browser bundle (a global)


def test_the_protomaps_leaflet_licence_and_its_bundled_packages():
    text = (VENDOR / "protomaps-leaflet.LICENSE").read_text(encoding="utf-8")
    assert text.startswith("Copyright 2021-2024 Protomaps LLC")
    assert "Redistributions in binary form must reproduce" in text
    # the bundle carries its dependencies: each one's notice is reproduced
    for package in ("pmtiles", "@protomaps/basemaps", "@mapbox/vector-tile", "pbf", "rbush",
                    "color2k", "potpack", "quickselect", "@mapbox/point-geometry"):  # fmt: skip
        assert f"\n{package} " in text, package


def test_the_adr_and_the_basemap_credit_agree():
    adr = (ROOT / "docs/adr/0008-licences.md").read_text(encoding="utf-8")
    basemap = (STATIC / "js" / "basemap.js").read_text(encoding="utf-8")
    assert 't("js.map.basemap_credit")' in basemap and 't("js.map.osm_contributors")' in basemap
    for lang in i18n.LANGS:  # the names stay as they are in German
        assert i18n.t(lang, "js.map.basemap_credit") == "Protomaps, ESA WorldCover (CC BY 4.0)"
    entry = next(line for line in adr.splitlines() if "M16 basemap" in line)
    assert "ESA WorldCover (CC BY 4.0)" in entry and "not drawn" in entry
    assert "protomaps-leaflet.LICENSE" in adr


# --- the tools: render pass and dry run ------------------------------------------------------


def test_the_render_pass_allows_only_the_loopback_host():
    rp = load_script("tools/render_pass.py")
    assert {"127.0.0.1"} == rp.ALLOWED_HOSTS
    r = {"errors": [], "axe": [], "overflow": [], "console": [], "csp": []}
    assert rp.failures(r | {"hosts": ["127.0.0.1"]}) == []
    assert rp.failures(r | {"hosts": ["127.0.0.1", OSM_TILE_HOST]}) == [f"hosts {OSM_TILE_HOST}"]


def test_the_dry_run_mounts_the_tiles_beside_the_site(tmp_path):
    dr = load_script("tools/deploy_dryrun.py")
    tiles = tmp_path / "t.pmtiles"
    paths = (tmp_path / "site", tmp_path / "datalab", tmp_path / "Caddyfile", tmp_path / "lock")
    cmd = dr.caddy_command(*paths, "n", tiles=tiles)
    assert f"{tiles.resolve()}:/srv/tiles/velometer.pmtiles:ro" in cmd
    assert not any("/srv/tiles" in x for x in dr.caddy_command(*paths, "n"))
    caddyfile = dr.dryrun_caddyfile(dr.CADDYFILE.read_text(encoding="utf-8"), 1)
    assert "/tiles/*" in caddyfile and "{$SITE_ROOT:/srv}/tiles" in caddyfile


def test_the_dry_run_probes_a_byte_range_on_the_tiles():
    dr = load_script("tools/deploy_dryrun.py")
    head = FIXTURE.read_bytes()[:16]
    ok = dr.Resp(206, {"content-range": "bytes 0-15/99"}, head, "u")
    assert dr.check_tiles("/tiles/velometer.pmtiles", ok) == []
    full = dr.Resp(200, {}, FIXTURE.read_bytes(), "u")
    assert dr.check_tiles("/tiles/velometer.pmtiles", full)  # no range support
    gz = dr.Resp(206, {"content-encoding": "gzip"}, head, "u")
    assert dr.check_tiles("/tiles/velometer.pmtiles", gz)
    other = dr.Resp(206, {}, b"<!doctype html>x", "u")
    assert dr.check_tiles("/tiles/velometer.pmtiles", other)


def test_the_map_scripts_draw_the_basemap_and_name_no_host():
    for js in ("map.js", "changemap.js", "countermap.js"):
        text = (STATIC / js).read_text(encoding="utf-8")
        assert "L.tileLayer" not in text and "tile_class" not in text, js
        assert "addBasemap(map, cfg)" in text, js
        assert not re.search(r"https?://", text), js
    for name in MAP_TEMPLATES:
        tpl = (ROOT / "src/velometer/app/templates" / name).read_text(encoding="utf-8")
        assert "/static/vendor/protomaps-leaflet.js" in tpl, name


def test_the_dry_run_reports_an_empty_404_under_the_tiles_route(tiny):  # noqa: F811
    """Caddy's handle_errors kept /srv/tiles as its root and sent an empty 404 body under
    /tiles/ (found in the Task 5 dry run); the probe now asks there too."""
    good = fake_fetch(tiny)

    def empty_under_tiles(url, gzip=False, byte_range=None):
        r = good(url, gzip)
        return dr15.Resp(404, r.headers, b"", url) if "/tiles/" in url else r

    assert dr15.run_probes(ORIGIN, tiny, "/", False, fetch=good)[1] == []
    _, problems = dr15.run_probes(ORIGIN, tiny, "/", False, fetch=empty_under_tiles)
    assert problems and all("/tiles/nope-" in p for p in problems)


# --- the Protomaps build in the credit (final review I3) ----------------------------------------


def test_the_dated_credit_strings_name_the_build(tmp_path):
    """Reader-facing (R8): the exact strings, en and de, with the date filled from data."""
    from velometer import i18n

    assert i18n.t("en", "js.map.basemap_credit_build", build="2026-08-11") == (
        "Protomaps (build 2026-08-11), ESA WorldCover (CC BY 4.0)"
    )
    assert i18n.t("de", "js.map.basemap_credit_build", build="2026-08-11") == (
        "Protomaps (Stand 2026-08-11), ESA WorldCover (CC BY 4.0)"
    )


def test_the_tile_sidecar_loads_or_refuses(tmp_path):
    import json

    from velometer.app.main import load_tiles_info

    path = tmp_path / "velometer.pmtiles.json"
    assert load_tiles_info(None) is None and load_tiles_info(path) is None
    good = {"file": "velometer.pmtiles", "protomaps_build": "2026-08-11", "maxzoom": 13,
            "sha256": "0f" * 32}  # fmt: skip
    path.write_text(json.dumps(good), encoding="utf-8")
    assert load_tiles_info(path) == {k: good[k] for k in ("protomaps_build", "maxzoom", "sha256")}
    for bad in ({**good, "protomaps_build": "20260811"}, {**good, "sha256": "x"}, [1], "{"):
        path.write_text(bad if isinstance(bad, str) else json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            load_tiles_info(path)
