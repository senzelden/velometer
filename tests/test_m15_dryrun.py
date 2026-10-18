"""M15: the deploy dry run's probes, Caddyfile extraction and driver (no server, no network)."""

import gzip
import json
from pathlib import Path

import pytest

from tests.helpers import load_script
from velometer.app.export import headers_text
from velometer.app.main import CSP, csp_meta

dr = load_script("tools/deploy_dryrun.py")

ORIGIN = "http://127.0.0.1:9"
RULES = dr.headers_rules(headers_text("/", csp_meta(CSP)))
WANT = dr.expected_headers(RULES, "/")


def resp(status=200, headers=None, body=b"x", url=ORIGIN + "/x"):
    return dr.Resp(status, {k.lower(): v for k, v in (headers or {}).items()}, body, url)


# --- _headers -----------------------------------------------------------------------------


def test_the_exported_headers_file_sets_four_headers_on_every_path():
    want = dr.expected_headers(RULES, "/city/berlin")
    assert set(want) == {
        "content-security-policy",
        "x-content-type-options",
        "referrer-policy",
        "cache-control",
    }
    assert want["content-security-policy"].endswith("frame-ancestors 'none'")


def test_a_rule_applies_only_to_paths_under_its_pattern():
    rules = dr.headers_rules(headers_text("/velometer/", "default-src 'self'"))
    assert dr.expected_headers(rules, "/velometer/compare")
    assert dr.expected_headers(rules, "/other") == {}


def test_a_header_line_before_any_path_is_an_error():
    with pytest.raises(dr.DryRunError):
        dr.headers_rules("  X-Frame-Options: DENY\n")


# --- single probes ------------------------------------------------------------------------


def test_headers_pass_when_all_are_sent_whatever_the_case_of_their_names():
    sent = {k.title(): v for k, v in WANT.items()}
    assert dr.check_headers("/", resp(headers=sent), WANT) == []


def test_a_missing_header_is_a_problem_naming_path_and_header():
    sent = {k: v for k, v in WANT.items() if k != "x-content-type-options"}
    (p,) = dr.check_headers("/de", resp(headers=sent), WANT)
    assert "/de" in p and "x-content-type-options" in p


def test_a_csp_without_frame_ancestors_is_a_wrong_value():
    sent = dict(WANT)
    sent["content-security-policy"] = sent["content-security-policy"].removesuffix(
        "; frame-ancestors 'none'"
    )
    (p,) = dr.check_headers("/", resp(headers=sent), WANT)
    assert "content-security-policy" in p


def test_the_404_page_passes_with_status_body_and_headers():
    assert dr.check_404("/nope", resp(404, WANT, b"<p>404</p>"), b"<p>404</p>", WANT) == []


def test_a_404_answered_200_is_a_problem():
    assert any("404" in p for p in dr.check_404("/nope", resp(200, WANT, b"a"), b"a", WANT))


def test_a_404_with_another_body_is_a_problem():
    assert dr.check_404("/nope", resp(404, WANT, b"index"), b"<p>404</p>", WANT)


def test_a_404_without_the_headers_is_a_problem():
    assert dr.check_404("/nope", resp(404, {}, b"a"), b"a", WANT)


def test_a_gzip_body_that_decodes_to_the_file_passes():
    r = resp(headers={"Content-Encoding": "gzip"}, body=gzip.compress(b"file"))
    assert dr.check_body("/f", r, b"file", require_gzip=True) == []


def test_a_gzip_body_that_decodes_to_other_bytes_is_a_problem():
    r = resp(headers={"Content-Encoding": "gzip"}, body=gzip.compress(b"stale"))
    (p,) = dr.check_body("/f", r, b"file", require_gzip=True)
    assert "/f" in p


def test_an_uncompressed_body_fails_only_where_gzip_is_required():
    r = resp(body=b"file")
    assert dr.check_body("/f", r, b"file", require_gzip=False) == []
    assert dr.check_body("/f", r, b"file", require_gzip=True)


def test_an_unknown_content_encoding_is_a_problem_not_a_crash():
    r = resp(headers={"Content-Encoding": "br"}, body=b"\x00")
    assert dr.check_body("/f", r, b"file", require_gzip=False)


@pytest.mark.parametrize(
    ("suffix", "ctype", "ok"),
    [
        (".html", "text/html; charset=utf-8", True),
        (".geojson", "application/geo+json", True),
        (".geojson", "application/json", True),
        (".json", "application/json", True),
        (".csv", "text/csv; charset=utf-8", True),
        (".js", "text/javascript", True),
        (".js", "application/javascript", True),
        (".css", "text/plain", False),
        (".json", "application/octet-stream", False),
        (".html", None, False),
    ],
)
def test_content_types(suffix, ctype, ok):
    r = resp(headers={"Content-Type": ctype} if ctype else {})
    assert (dr.check_type("/p" + suffix, r, suffix) == []) is ok


def test_a_page_reached_off_site_is_a_problem():
    r = resp(body=b"page", url="http://elsewhere.example/city/berlin/")
    assert dr.check_page("/city/berlin/", r, b"page", ORIGIN)
    assert dr.check_page("/city/berlin/", resp(body=b"page"), b"page", ORIGIN) == []


def test_site_links_keep_only_paths_under_the_base_without_query_or_fragment():
    html = (
        '<a href="/city/berlin">b</a><link href="/static/app.css"><img src="/maps/x.png">'
        '<a href="//cdn.example/x">c</a><a href="https://osm.org/">o</a><a href="#top">t</a>'
        '<a href="/compare?c=berlin#v">q</a><a href="/city/berlin">again</a>'
    )
    assert dr.site_links(html, "/") == [
        "/city/berlin",
        "/compare",
        "/maps/x.png",
        "/static/app.css",
    ]


# --- Caddyfile from docs/deploy.md --------------------------------------------------------


def test_the_documented_caddyfile_is_extracted_with_only_its_site_address_replaced():
    doc = dr.DOC.read_text(encoding="utf-8")
    text = dr.caddyfile_from_doc(doc, ORIGIN)
    assert f"{ORIGIN} {{" in text and dr.SITE_ADDRESS not in text
    assert "handle_errors" in text and "precompressed gzip" in text
    assert text == dr.caddyfile_from_doc(doc, ORIGIN)  # deterministic
    assert text.replace(f"{ORIGIN} {{", f"{dr.SITE_ADDRESS} {{") in _dedented_blocks(doc)


def _dedented_blocks(doc):
    import re
    import textwrap

    return [textwrap.dedent(b) for b in re.findall(r"```\n(.*?)```", doc, re.S)]


def test_a_doc_without_the_caddyfile_fails():
    with pytest.raises(dr.DryRunError):
        dr.caddyfile_from_doc("# Deploy\n\n```\nrsync -a x y\n```\n", ORIGIN)


def test_a_caddyfile_without_the_site_address_fails():
    doc = "```\nexample.org {\n    handle_errors {\n    }\n}\n```\n"
    with pytest.raises(dr.DryRunError):
        dr.caddyfile_from_doc(doc, ORIGIN)


def test_two_caddyfiles_fail():
    one = "```\nvelometer.<domain> {\n    handle_errors {\n    }\n}\n```\n"
    with pytest.raises(dr.DryRunError):
        dr.caddyfile_from_doc(one + one, ORIGIN)


# --- the driver over a tiny site ----------------------------------------------------------

FAKE_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".geojson": "application/geo+json",
    ".css": "text/css",
    ".js": "text/javascript",
}


@pytest.fixture
def tiny(tmp_path):
    site = tmp_path / "site"
    files = {
        "index.html": '<a href="/city/berlin">B</a><link href="/static/app.css">',
        "city/berlin/index.html": "<h1>Berlin</h1>",
        "de/index.html": "<h1>Start</h1>",
        "data/series.json": "{}",
        "maps/berlin_lau.geojson": '{"type":"FeatureCollection","features":[]}',
        "static/app.css": "body{}",
        "404.html": "<p>404</p>",
        "_headers": headers_text("/", csp_meta(CSP)),
        "build.json": json.dumps({"base": "/"}),
    }
    for rel, text in files.items():
        (site / rel).parent.mkdir(parents=True, exist_ok=True)
        (site / rel).write_text(text, encoding="utf-8")
    return site


def fake_fetch(site: Path, *, drop=None, not_found=404):
    """A server over `site` that sends WANT on every response; `drop` names a path whose
    response lacks X-Content-Type-Options; `not_found` is the status for a missing file."""

    def fetch(url, gzip=False):
        path = url.removeprefix(ORIGIN)
        f = site / path.lstrip("/")
        if f.is_dir():
            f = f / "index.html"
        headers = dict(WANT)
        if path == drop:
            headers.pop("x-content-type-options")
        if not f.is_file():
            body = (site / "404.html").read_bytes()
            return dr.Resp(not_found, {**headers, "content-type": "text/html"}, body, url)
        headers["content-type"] = FAKE_TYPES[f.suffix]
        return dr.Resp(200, headers, f.read_bytes(), url)

    return fetch


def test_a_correct_server_passes_every_probe(tiny):
    n, problems = dr.run_probes(ORIGIN, tiny, "/", False, fetch=fake_fetch(tiny))
    assert problems == [] and n >= 10


def test_a_header_missing_on_one_path_is_reported_for_that_path(tiny):
    _, problems = dr.run_probes(ORIGIN, tiny, "/", False, fetch=fake_fetch(tiny, drop="/de"))
    assert problems and all("/de" in p for p in problems)


def test_a_404_served_as_200_is_reported(tiny):
    _, problems = dr.run_probes(ORIGIN, tiny, "/", False, fetch=fake_fetch(tiny, not_found=200))
    assert any("404" in p for p in problems)


def test_a_broken_link_on_the_home_page_is_reported(tiny):
    (tiny / "index.html").write_text('<a href="/gone">x</a>', encoding="utf-8")
    _, problems = dr.run_probes(ORIGIN, tiny, "/", False, fetch=fake_fetch(tiny))
    assert any("/gone" in p for p in problems)


def test_gzip_required_fails_on_a_server_that_never_compresses(tiny):
    big = tiny / "data" / "series.json"
    big.write_text("{" + '"k":1,' * 400 + '"z":0}', encoding="utf-8")
    (tiny / "data" / "series.json.gz").write_bytes(gzip.compress(big.read_bytes()))
    _, problems = dr.run_probes(ORIGIN, tiny, "/", True, fetch=fake_fetch(tiny))
    assert any("series.json" in p and "gzip" in p for p in problems)


def test_pick_paths_prefers_berlin_and_needs_a_tier_map(tiny):
    paths = dr.pick_paths(tiny, "/")
    assert paths["city"] == "/city/berlin" and paths["geojson"] == "/maps/berlin_lau.geojson"
    assert "csv" not in paths and "js" not in paths
    (tiny / "data" / "berlin.csv").write_text("a,b\n", encoding="utf-8")
    (tiny / "static" / "map.js").write_text("", encoding="utf-8")
    paths = dr.pick_paths(tiny, "/")
    assert paths["csv"] == "/data/berlin.csv" and paths["js"] == "/static/map.js"
    (tiny / "maps" / "berlin_lau.geojson").unlink()
    with pytest.raises(dr.DryRunError):
        dr.pick_paths(tiny, "/")


# --- fetch_url merges repeated headers ----------------------------------------------------


def test_repeated_headers_are_joined_so_a_doubled_header_is_seen():
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        r = dr.fetch_url(f"http://127.0.0.1:{srv.server_port}/")
    finally:
        srv.shutdown()
        srv.server_close()
    assert r.header("cache-control") == "public, max-age=3600, no-store"
    assert dr.check_headers("/", r, {"cache-control": "public, max-age=3600"})


# --- servers and CLI (no Docker, no npx) --------------------------------------------------


def test_the_caddy_command_pins_the_image_and_mounts_read_only_on_the_host_network(tmp_path):
    cmd = dr.caddy_command(tmp_path / "site", tmp_path / "Caddyfile", "velometer-dryrun-1")
    assert cmd[:3] == ["docker", "run", "--rm"]
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "host"
    assert f"{(tmp_path / 'site').resolve()}:/srv/velometer:ro" in cmd
    assert f"{tmp_path / 'Caddyfile'}:/etc/caddy/Caddyfile:ro" in cmd
    import re

    assert re.fullmatch(r"caddy:\d+\.\d+\.\d+-alpine", cmd[-1])


def test_the_wrangler_command_pins_its_version_and_binds_loopback(tmp_path):
    import re

    cmd = dr.wrangler_command(tmp_path, 8788, 9230)
    assert cmd[:2] == ["npx", "--yes"] and re.fullmatch(r"wrangler@\d+\.\d+\.\d+", cmd[2])
    assert cmd[3:5] == ["pages", "dev"]
    assert cmd[cmd.index("--ip") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--port") + 1] == "8788"


def test_wait_http_gives_up_with_an_error_naming_the_url():
    import socket

    with socket.socket() as s:  # a port nobody listens on
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(dr.DryRunError, match=str(port)):
        dr.wait_http(f"http://127.0.0.1:{port}/", timeout=1)


def test_an_export_without_build_json_is_refused(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        dr.main(["--site", str(tmp_path), "--server", "caddy"])
    assert e.value.code == 2 and "build.json" in capsys.readouterr().err


def test_an_export_for_another_base_is_refused_before_any_server_starts(tiny, monkeypatch, capsys):
    (tiny / "build.json").write_text(json.dumps({"base": "/velometer/"}), encoding="utf-8")
    monkeypatch.setattr(dr, "caddy_server", lambda site: pytest.fail("no server may start"))
    with pytest.raises(SystemExit) as e:
        dr.main(["--site", str(tiny), "--server", "caddy"])
    assert e.value.code == 2 and "--base /" in capsys.readouterr().err


def test_a_server_is_stopped_when_a_probe_crashes(tiny, monkeypatch):
    import contextlib

    stopped = []

    @contextlib.contextmanager
    def server(site):
        try:
            yield "http://127.0.0.1:9"
        finally:
            stopped.append(site)

    def boom(*a, **k):
        raise RuntimeError("probe crashed")

    monkeypatch.setattr(dr, "caddy_server", server)
    monkeypatch.setattr(dr, "run_probes", boom)
    with pytest.raises(RuntimeError):
        dr.main(["--site", str(tiny), "--server", "caddy"])
    assert stopped == [tiny.resolve()]


def test_main_reports_problems_with_exit_1_and_none_with_exit_0(tiny, monkeypatch, capsys):
    import contextlib

    monkeypatch.setattr(
        dr, "caddy_server", lambda site: contextlib.nullcontext("http://127.0.0.1:9")
    )
    monkeypatch.setattr(dr, "run_probes", lambda *a, **k: (12, []))
    assert dr.main(["--site", str(tiny), "--server", "caddy"]) == 0
    assert "12 checks, 0 problems" in capsys.readouterr().out
    monkeypatch.setattr(dr, "run_probes", lambda *a, **k: (12, ["/de: missing header x"]))
    assert dr.main(["--site", str(tiny), "--server", "caddy"]) == 1
    assert "/de: missing header x" in capsys.readouterr().out
