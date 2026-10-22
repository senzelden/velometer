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


# --- deploy/Caddyfile, made local for the dry run ----------------------------------------------

PROD = dr.CADDYFILE.read_text(encoding="utf-8")


def test_the_dry_run_serves_deploy_caddyfile_with_only_its_site_addresses_made_local():
    text = dr.dryrun_caddyfile(PROD, 8123)
    changed = [(a, b) for a, b in zip(PROD.splitlines(), text.splitlines(), strict=True) if a != b]
    assert changed == [
        ("{$DOMAIN} {", "http://{$DOMAIN}:8123 {"),
        ("velometer.{$DOMAIN} {", "http://velometer.{$DOMAIN}:8123 {"),
        ("www.{$DOMAIN} {", "http://www.{$DOMAIN}:8123 {"),
    ]
    assert text == dr.dryrun_caddyfile(PROD, 8123)  # deterministic


def test_the_debug_variant_only_raises_the_default_loggers_level():
    text = dr.dryrun_caddyfile(PROD, 8123, debug=True)
    extra = [line for line in text.splitlines() if line not in PROD.splitlines()]
    assert [x.strip() for x in extra if not x.startswith("http://")] == ["level DEBUG"]
    lines = text.splitlines()
    assert lines[lines.index("\t\toutput stderr") + 1] == "\t\tlevel DEBUG"


def test_a_caddyfile_without_the_three_sites_fails():
    with pytest.raises(dr.DryRunError, match="site"):
        dr.dryrun_caddyfile("{$DOMAIN} {\n\tfile_server\n}\n", 1)


def test_a_caddyfile_with_a_literal_site_address_fails():
    with pytest.raises(dr.DryRunError, match="site"):
        dr.dryrun_caddyfile(PROD.replace("www.{$DOMAIN} {", "www.example.org {"), 1)


def test_the_debug_variant_needs_the_default_logger():
    with pytest.raises(dr.DryRunError, match="output stderr"):
        dr.dryrun_caddyfile(PROD.replace("output stderr", "output stdout"), 1, debug=True)


# --- the lock file --------------------------------------------------------------------------


def test_the_lock_file_text_is_a_basic_auth_block_for_the_preview_user_with_no_store():
    h = "$2a$14$" + "x" * 53
    assert dr.lock_text(h) == f'header Cache-Control "no-store"\nbasic_auth {{\n\tpreview {h}\n}}\n'
    assert dr.LOCK_DEFAULT == 'header Cache-Control "no-store"\nrespond "locked" 401\n'


def test_the_guide_records_both_lock_file_texts_for_the_server_setup():
    doc = dr.DOC.read_text(encoding="utf-8")
    assert dr.LOCK_DEFAULT in _dedented_blocks(doc)
    assert dr.lock_text("$2a$14$" + "x" * 53).replace("$2a$14$" + "x" * 53, "<bcrypt hash>") in (
        _dedented_blocks(doc)
    )


def _dedented_blocks(doc):
    import re
    import textwrap

    fence = r"^[ \t]*```[a-z]*\n(.*?)^[ \t]*```[ \t]*$"
    return [textwrap.dedent(b) for b in re.findall(fence, doc, re.S | re.M)]


def test_a_hash_that_is_not_bcrypt_is_refused():
    with pytest.raises(dr.DryRunError):
        dr.lock_text("plaintext")


def test_the_password_reaches_caddy_on_stdin_never_on_its_command_line(monkeypatch):
    seen = {}

    class Done:
        returncode = 0
        stdout = b"$2a$14$" + b"y" * 53 + b"\n"
        stderr = b""

    def run(cmd, input=None, **kw):
        seen["cmd"], seen["input"] = cmd, input
        return Done()

    monkeypatch.setattr(dr.subprocess, "run", run)
    assert dr.hash_password("s3cret-pw") == "$2a$14$" + "y" * 53
    assert "s3cret-pw" not in " ".join(seen["cmd"])
    assert seen["input"] == b"s3cret-pw\n"
    assert seen["cmd"][:3] == ["docker", "run", "--rm"] and seen["cmd"][-2:] == [
        "caddy", "hash-password"]  # fmt: skip
    assert dr.CADDY_IMAGE in seen["cmd"]


# --- the driver over a tiny site ----------------------------------------------------------

FAKE_TYPES = {
    ".svg": "image/svg+xml",
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


@pytest.fixture
def tiny_datalab(tmp_path):
    site = tmp_path / "datalab"
    files = {
        "index.html": '<a href="/impressum/">I</a><link href="/static/datalab.css">',
        "impressum/index.html": "<h1>Impressum</h1>",
        "datenschutz/index.html": "<h1>Datenschutz</h1>",
        "404.html": "<p>Seite nicht gefunden</p>",
        "static/datalab.css": "body{}",
        "static/favicon.svg": "<svg></svg>",
        "_headers": headers_text("/", "default-src 'self'"),
    }
    for rel, text in files.items():
        (site / rel).parent.mkdir(parents=True, exist_ok=True)
        (site / rel).write_text(text, encoding="utf-8")
    return site


def _caddy_args(tiny, tiny_datalab, *more):
    return ["--site", str(tiny), "--server", "caddy", "--datalab", str(tiny_datalab), *more]


def fake_fetch(site: Path, *, drop=None, not_found=404):
    """A server over `site` that sends WANT on every response; `drop` names a path whose
    response lacks X-Content-Type-Options; `not_found` is the status for a missing file."""

    def fetch(url, gzip=False, **kw):
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
    cmd = dr.caddy_command(
        tmp_path / "site", tmp_path / "datalab", tmp_path / "Caddyfile", tmp_path / "lock.caddy",
        "velometer-dryrun-1",
    )  # fmt: skip
    assert cmd[:3] == ["docker", "run", "--rm"]
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "host"
    assert f"{(tmp_path / 'site').resolve()}:/srv/velometer/current:ro" in cmd
    assert f"{(tmp_path / 'datalab').resolve()}:/srv/datalab/current:ro" in cmd
    assert f"{tmp_path / 'Caddyfile'}:/etc/caddy/Caddyfile:ro" in cmd
    assert f"{tmp_path / 'lock.caddy'}:/etc/caddy/lock.caddy:ro" in cmd
    assert cmd[cmd.index("-e") + 1] == "DOMAIN=localhost"
    assert not any(x.startswith("SITE_ROOT") for x in cmd)  # the Caddyfile's default, /srv
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
    monkeypatch.setattr(dr, "caddy_server", lambda *a, **k: pytest.fail("no server may start"))
    with pytest.raises(SystemExit) as e:
        dr.main(["--site", str(tiny), "--server", "caddy"])
    assert e.value.code == 2 and "--base /" in capsys.readouterr().err


def test_a_server_is_stopped_when_a_probe_crashes(tiny, tiny_datalab, monkeypatch):
    import contextlib

    stopped = []

    @contextlib.contextmanager
    def server(site, *a, **k):
        try:
            yield dr.Served("http://127.0.0.1:9", dict)
        finally:
            stopped.append(site)

    def boom(*a, **k):
        raise RuntimeError("probe crashed")

    monkeypatch.setattr(dr, "caddy_server", server)
    monkeypatch.setattr(dr, "run_caddy_probes", boom)
    with pytest.raises(RuntimeError):
        dr.main(_caddy_args(tiny, tiny_datalab))
    assert stopped == [tiny.resolve()]


def _served_with_logs(logs):
    import contextlib

    return lambda *a, **k: contextlib.nullcontext(dr.Served("http://127.0.0.1:9", lambda: logs))


CLEAN_LOGS = dict.fromkeys(
    ("caddy output", "datalab.log", "velometer.log"), "127.0.0.0 203.0.113.0"
)


def test_main_reports_problems_with_exit_1_and_none_with_exit_0(
    tiny, tiny_datalab, monkeypatch, capsys
):
    monkeypatch.setattr(dr, "caddy_server", _served_with_logs(CLEAN_LOGS))
    monkeypatch.setattr(dr, "run_caddy_probes", lambda *a, **k: (12, []))
    assert dr.main(_caddy_args(tiny, tiny_datalab)) == 0
    assert "13 checks, 0 problems" in capsys.readouterr().out  # the probes and the log check
    monkeypatch.setattr(dr, "run_caddy_probes", lambda *a, **k: (12, ["/de: missing header x"]))
    assert dr.main(_caddy_args(tiny, tiny_datalab)) == 1
    assert "/de: missing header x" in capsys.readouterr().out


def test_an_unmasked_address_in_a_log_fails_the_run(tiny, tiny_datalab, monkeypatch, capsys):
    leaky = CLEAN_LOGS | {"caddy output": '{"remote_ip":"127.0.0.77"}'}
    monkeypatch.setattr(dr, "caddy_server", _served_with_logs(leaky))
    monkeypatch.setattr(dr, "run_caddy_probes", lambda *a, **k: (12, []))
    assert dr.main(_caddy_args(tiny, tiny_datalab)) == 1
    assert "log caddy output: holds the client address" in capsys.readouterr().out


def test_the_password_and_its_header_are_secrets_the_logs_must_not_hold(
    tiny, tiny_datalab, monkeypatch, capsys
):
    import base64

    token = base64.b64encode(b"preview:hunter2-pw").decode()
    leaky = CLEAN_LOGS | {"velometer.log": CLEAN_LOGS["velometer.log"] + f" Basic {token}"}
    monkeypatch.setattr(dr, "caddy_server", _served_with_logs(leaky))
    monkeypatch.setattr(dr, "run_caddy_probes", lambda *a, **k: (12, []))
    monkeypatch.setattr(dr, "hash_password", lambda pw: "$2a$14$" + "z" * 53)
    assert dr.main(_caddy_args(tiny, tiny_datalab, "--lock", "hunter2-pw")) == 1
    out = capsys.readouterr().out
    assert "holds the Authorization value" in out and "hunter2-pw" not in out


def test_the_lock_options_reach_the_server_as_lock_file_text(tiny, tiny_datalab, monkeypatch):
    seen = []

    def server(site, datalab, tiles, lock, debug):
        seen.append((lock, debug))
        return _served_with_logs(CLEAN_LOGS)()

    monkeypatch.setattr(dr, "caddy_server", server)
    monkeypatch.setattr(dr, "run_caddy_probes", lambda *a, **k: (1, []))
    monkeypatch.setattr(dr, "hash_password", lambda pw: "$2a$14$" + "z" * 53)
    assert dr.main(_caddy_args(tiny, tiny_datalab)) == 0
    assert dr.main(_caddy_args(tiny, tiny_datalab, "--lock-default", "--debug-log")) == 0
    assert dr.main(_caddy_args(tiny, tiny_datalab, "--lock", "pw")) == 0
    assert seen == [
        ("", False),
        ('header Cache-Control "no-store"\nrespond "locked" 401\n', True),
        ('header Cache-Control "no-store"\nbasic_auth {\n\tpreview $2a$14$' + "z" * 53 + "\n}\n",
         False),
    ]  # fmt: skip


def test_lock_without_a_value_reads_the_password_from_the_environment(
    tiny, tiny_datalab, monkeypatch, capsys
):
    hashed = []
    monkeypatch.setattr(dr, "caddy_server", _served_with_logs(CLEAN_LOGS))
    monkeypatch.setattr(dr, "run_caddy_probes", lambda *a, **k: (1, []))
    monkeypatch.setattr(dr, "hash_password", lambda pw: hashed.append(pw) or "$2a$14$" + "z" * 53)
    monkeypatch.setenv("VELOMETER_PREVIEW_PASSWORD", "from-the-env")
    assert dr.main(_caddy_args(tiny, tiny_datalab, "--lock")) == 0
    assert hashed == ["from-the-env"]
    monkeypatch.delenv("VELOMETER_PREVIEW_PASSWORD")
    with pytest.raises(SystemExit) as e:
        dr.main(_caddy_args(tiny, tiny_datalab, "--lock"))
    assert e.value.code == 2 and "VELOMETER_PREVIEW_PASSWORD" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["--server", "caddy"],  # no --datalab
        ["--server", "wrangler", "--lock", "pw"],
        ["--server", "wrangler", "--datalab", "X"],
        ["--server", "caddy", "--datalab", "X", "--lock", "pw", "--lock-default"],
    ],
)
def test_options_that_do_not_fit_the_server_are_refused(tiny, tiny_datalab, args, capsys):
    args = [str(tiny_datalab) if x == "X" else x for x in args]
    with pytest.raises(SystemExit) as e:
        dr.main(["--site", str(tiny), *args])
    assert e.value.code == 2


def test_a_datalab_without_its_404_page_is_refused(tiny, tiny_datalab, capsys):
    (tiny_datalab / "404.html").unlink()
    with pytest.raises(SystemExit) as e:
        dr.main(_caddy_args(tiny, tiny_datalab))
    assert e.value.code == 2 and "404.html" in capsys.readouterr().err


# --- a server that never comes up; missing binaries; process-group cleanup -----------------


class _Proc:
    """A stand-in for subprocess.Popen: writes one line to the log it is given, never serves."""

    pid = 4242

    def __init__(self, cmd, stdout=None, **kw):
        self.cmd = cmd
        stdout.write(b"boom: the server log line\n")

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def _no_answer(url, timeout):
    raise dr.DryRunError(f"no answer from {url} within {timeout:g} s")


@pytest.mark.parametrize("server", ["caddy", "wrangler"])
def test_a_server_that_never_answers_exits_1_naming_it_with_its_log_tail(
    tiny, tiny_datalab, monkeypatch, capsys, server
):
    monkeypatch.setattr(dr.subprocess, "Popen", _Proc)
    monkeypatch.setattr(dr.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(dr.os, "killpg", lambda *a: None)
    monkeypatch.setattr(dr, "wait_http", _no_answer)
    more = ["--datalab", str(tiny_datalab)] if server == "caddy" else []
    assert dr.main(["--site", str(tiny), "--server", server, *more]) == 1
    err = capsys.readouterr().err
    assert f"error: {server}: no answer" in err and "boom: the server log line" in err


def test_an_export_without_a_headers_file_is_refused(tiny, capsys):
    (tiny / "_headers").unlink()
    with pytest.raises(SystemExit) as e:
        dr.main(["--site", str(tiny), "--server", "caddy"])
    assert e.value.code == 2 and "_headers" in capsys.readouterr().err


@pytest.mark.parametrize(("server", "program"), [("caddy", "docker"), ("wrangler", "npx")])
def test_a_missing_program_is_a_clean_error_and_leaves_no_temp_dir(
    tiny, tiny_datalab, tmp_path, monkeypatch, capsys, server, program
):
    made = []

    def mkdtemp(prefix=""):
        d = tmp_path / f"{prefix}x"
        d.mkdir()
        made.append(d)
        return str(d)

    def popen(*a, **k):
        raise FileNotFoundError(program)

    monkeypatch.setattr(dr.tempfile, "mkdtemp", mkdtemp)
    monkeypatch.setattr(dr.subprocess, "Popen", popen)
    monkeypatch.setattr(dr.subprocess, "run", lambda *a, **k: None)
    more = ["--datalab", str(tiny_datalab)] if server == "caddy" else []
    assert dr.main(["--site", str(tiny), "--server", server, *more]) == 1
    err = capsys.readouterr().err
    assert f"{server}: {program} not found" in err
    assert made and not any(d.exists() for d in made)


def test_a_failing_caddyfile_rewrite_leaves_no_temp_dir(tiny, tiny_datalab, tmp_path, monkeypatch):
    made = []

    def mkdtemp(prefix=""):
        d = tmp_path / f"{prefix}y"
        d.mkdir()
        made.append(d)
        return str(d)

    def broken(*a, **k):
        raise dr.DryRunError("deploy/Caddyfile: no site addresses")

    monkeypatch.setattr(dr.tempfile, "mkdtemp", mkdtemp)
    monkeypatch.setattr(dr, "dryrun_caddyfile", broken)
    assert dr.main(_caddy_args(tiny, tiny_datalab)) == 1
    assert made and not any(d.exists() for d in made)


def test_wrangler_cleanup_kills_the_whole_group_after_terminating_it(tiny, monkeypatch):
    import signal

    calls = []
    monkeypatch.setattr(dr.subprocess, "Popen", _Proc)
    monkeypatch.setattr(dr, "wait_http", lambda url, timeout: None)
    monkeypatch.setattr(dr.os, "killpg", lambda pid, sig: calls.append((pid, sig)))
    with dr.wrangler_server(tiny):
        pass
    assert calls == [(4242, signal.SIGTERM), (4242, signal.SIGKILL)]


def test_the_doc_names_the_caddy_version_the_tool_pins_and_warns_about_2_10_2():
    import re

    version = re.fullmatch(r"caddy:(\d+\.\d+\.\d+)-alpine", dr.CADDY_IMAGE)
    assert version, dr.CADDY_IMAGE
    doc = dr.DOC.read_text(encoding="utf-8")
    assert f"Caddy {version.group(1)} or later" in doc
    assert "2.10.2" in doc


def test_the_doc_names_the_wrangler_version_the_tool_pins():
    import re

    version = re.fullmatch(r"wrangler@(\d+\.\d+\.\d+)", dr.WRANGLER)
    assert version, dr.WRANGLER
    assert version.group(1) in dr.DOC.read_text(encoding="utf-8")


# --- the 404 page's Cache-Control (wrangler sends no-store on a 404) -----------------------


def test_a_404_with_no_store_cache_control_passes_the_other_headers():
    sent = {**WANT, "cache-control": "no-store"}
    assert dr.check_404("/nope", resp(404, sent, b"<p>404</p>"), b"<p>404</p>", WANT) == []


def test_a_404_without_cache_control_passes_the_other_headers():
    sent = {k: v for k, v in WANT.items() if k != "cache-control"}
    assert dr.check_404("/nope", resp(404, sent, b"<p>404</p>"), b"<p>404</p>", WANT) == []


def test_a_404_without_csp_is_still_a_problem_when_its_cache_control_is_exempt():
    sent = {k: v for k, v in WANT.items() if k != "content-security-policy"}
    (p,) = dr.check_404("/nope", resp(404, sent, b"<p>404</p>"), b"<p>404</p>", WANT)
    assert "content-security-policy" in p


# --- M16: the lock, www, Range and the logs (deploy/Caddyfile; legal review 5.3) ----------------


NS = {"Cache-Control": "no-store"}


def test_a_locked_answer_is_401_with_nothing_of_the_site_and_nothing_to_cache():
    assert dr.check_locked("velometer /", resp(401, NS, b"")) == []
    assert dr.check_locked("velometer /", resp(401, NS, b"locked")) == []
    assert dr.check_locked("velometer /", resp(200, NS, b"<!doctype html>"))
    # a 401 that carries the 404 page (a bare handle_errors) or the tile file leaks
    (p,) = dr.check_locked("velometer /x", resp(401, NS, b"<p>404</p>"))
    assert "body" in p
    assert dr.check_locked("velometer /t", resp(401, NS, b"PMTiles\x03"))
    # a 401 a shared cache may keep (ruling R26)
    (p,) = dr.check_locked("datalab /", resp(401, {"Cache-Control": "public, max-age=3600"}, b""))
    assert p == "datalab /: Cache-Control 'public, max-age=3600' while locked"
    assert dr.check_locked("datalab /", resp(401, {}, b""))


def test_www_must_redirect_permanently_to_the_apex():
    ok = resp(308, {"Location": "https://localhost/impressum/"}, b"")
    assert dr.check_redirect("www", ok, "https://localhost/impressum/") == []
    assert dr.check_redirect(
        "www", resp(301, {"Location": "https://localhost/"}), "https://localhost/"
    )
    assert dr.check_redirect(
        "www", resp(308, {"Location": "https://www.localhost/"}), "https://localhost/"
    )


def test_a_malformed_range_must_be_refused_without_the_file():
    assert dr.check_bad_range("/t", resp(416, body=b"invalid range")) == []
    assert dr.check_bad_range("/t", resp(200, body=b"PMTiles\x03..."))
    assert dr.check_bad_range("/t", resp(206, body=b"ab"))  # a range answered, not refused
    assert dr.check_bad_range("/t", resp(416, body=b"PMTiles\x03"))


def test_the_log_check_finds_each_unmasked_address_and_secret():
    clean = "127.0.0.0"
    assert dr.check_logs({"a.log": clean}, {"the cookie": "c00k"}, ["a.log"]) == []
    for leak, what in (
        ("127.0.0.77", "the client address"),
        ("203.0.113.7", "the forged X-Forwarded-For"),
        ("c00k", "the cookie"),
    ):
        (p,) = dr.check_logs({"a.log": clean + " " + leak}, {"the cookie": "c00k"}, ["a.log"])
        assert p == f"log a.log: holds {what} unmasked"
    # a JSON entry that keeps the Cookie or Authorization header, even redacted
    line = '{"request":{"remote_ip":"127.0.0.0","headers":{"Cookie":["REDACTED"]}}}'
    (p,) = dr.check_logs({"a.log": clean + "\n" + line}, {}, ["a.log"])
    assert p == "log a.log: keeps the Cookie header"
    line = '{"request":{"headers":{"Authorization":["REDACTED"],"User-Agent":["x"]}}}'
    assert dr.check_logs({"b.log": line}, {}, []) == ["log b.log: keeps the Authorization header"]
    # X-Forwarded-For is dropped, even masked (ruling R25)
    line = '{"request":{"headers":{"X-Forwarded-For":["203.0.113.0"]}}}'
    assert dr.check_logs({"c.log": line}, {}, []) == ["log c.log: keeps the X-Forwarded-For header"]
    # a log that should show the probes but holds no masked address logged nothing
    (p,) = dr.check_logs({"a.log": ""}, {}, ["a.log"])
    assert "nothing logged" in p
    assert dr.check_logs({"b.log": ""}, {}, []) == []


def test_fetch_sends_host_auth_and_headers_from_the_given_address_and_can_stop_at_a_redirect():
    import http.server
    import threading

    seen = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.client_address[0], dict(self.headers)))
            self.send_response(308)
            self.send_header("Location", "https://elsewhere.invalid/")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        r = dr.fetch_url(
            f"http://127.0.0.1:{srv.server_port}/x",
            host="www.localhost:1",
            auth=("preview", "pw"),
            source=dr.CLIENT_ADDR,
            headers=dr.PROBE_HEADERS,
            follow=False,
        )
    finally:
        srv.shutdown()
        srv.server_close()
    assert r.status == 308 and r.header("location") == "https://elsewhere.invalid/"
    ((addr, headers),) = seen
    assert addr == dr.CLIENT_ADDR
    assert headers["Host"] == "www.localhost:1"
    assert headers["Authorization"] == "Basic cHJldmlldzpwdw=="
    assert headers["X-Forwarded-For"] == dr.FORGED_XFF and headers["Cookie"] == dr.COOKIE


def _host_fetch(by_host):
    """A server answering per Host header: `by_host[name](path, auth)` gives (status, body)."""
    calls = []

    def fetch(url, gzip=False, byte_range=None, *, host=None, auth=None, follow=True, **kw):
        path = url.removeprefix(ORIGIN)
        calls.append((host, path, auth, kw))
        status, body = by_host[host.split(":")[0]](path, auth)
        return dr.Resp(status, {"cache-control": "no-store"}, body, url)

    return fetch, calls


def test_the_lock_probes_ask_every_host_for_every_path_and_report_a_leak():
    locked = lambda path, auth: (401, b"")  # noqa: E731
    # (the fake sends Cache-Control: no-store on every answer)
    leaky = lambda path, auth: (200, b"PMTiles") if path.startswith("/tiles/") else (401, b"")  # noqa: E731
    fetch, calls = _host_fetch({"localhost": locked, "velometer.localhost": leaky,
                                "www.localhost": locked})  # fmt: skip
    n, problems = dr.run_lock_probes(ORIGIN, fetch)
    assert n == 3 * len(dr.lock_paths()) == len(calls)
    assert {h for h, *_ in calls} == {"localhost:9", "velometer.localhost:9", "www.localhost:9"}
    assert all(auth is None for _, _, auth, _ in calls)
    assert problems and all(p.startswith("velometer /tiles/") for p in problems)
    # the lock no password opens: each path is asked again with one
    fetch, calls = _host_fetch(dict.fromkeys(("localhost", "velometer.localhost",
                                              "www.localhost"), locked))  # fmt: skip
    n, problems = dr.run_lock_probes(ORIGIN, fetch, auth=("preview", "guess"))
    assert problems == [] and n == 2 * 3 * len(dr.lock_paths())


def test_the_lock_paths_cover_pages_tiles_the_404_page_and_robots():
    paths = dr.lock_paths()
    for want in ("/", dr.TILES_URL, "/404.html", "/robots.txt"):
        assert want in paths
    assert any(p.startswith("/tiles/nope-") for p in paths)
    assert any(p.startswith("/nope-") for p in paths)


def test_the_datalab_probes_visit_its_pages_files_and_404(tiny_datalab):
    assert dr.datalab_paths(tiny_datalab) == [
        "/", "/datenschutz/", "/impressum/", "/static/datalab.css", "/static/favicon.svg",
    ]  # fmt: skip
    want = dr.expected_headers(dr.headers_rules(headers_text("/", "default-src 'self'")), "/")

    def fetch(url, gzip=False, **kw):
        path = url.removeprefix(ORIGIN)
        f = tiny_datalab / path.lstrip("/")
        if f.is_dir():
            f = f / "index.html"
        headers = want | {"strict-transport-security": dr.HSTS}
        if not f.is_file():
            return dr.Resp(404, headers, (tiny_datalab / "404.html").read_bytes(), url)
        return dr.Resp(200, headers | {"content-type": FAKE_TYPES[f.suffix]}, f.read_bytes(), url)

    hsts = {"strict-transport-security": dr.HSTS}
    n, problems = dr.run_datalab_probes(ORIGIN, tiny_datalab, False, fetch, hsts)
    assert problems == [] and n >= 5 * 4 + 2
    # a server without HSTS fails on every response
    no_hsts = lambda url, gzip=False, **kw: dr.Resp(  # noqa: E731
        fetch(url).status, {k: v for k, v in fetch(url).headers.items() if "strict" not in k},
        fetch(url).body, url,
    )  # fmt: skip
    _, problems = dr.run_datalab_probes(ORIGIN, tiny_datalab, False, no_hsts, hsts)
    for path in ("/", "/impressum/", "/static/datalab.css"):  # pages and files, not only 404s
        assert (
            f"{path}: missing header strict-transport-security (expected 'max-age=31536000')"
            in problems
        )


def test_the_caddy_probes_send_every_request_from_the_client_address_with_the_forged_headers(
    tiny, tiny_datalab
):
    sent = []

    def fetch(url, gzip=False, byte_range=None, **kw):
        sent.append(kw)
        return dr.Resp(401, {}, b"", url)

    dr.run_caddy_probes(ORIGIN, tiny, tiny_datalab, True, "pw", fetch=fetch)
    assert sent and all(k["source"] == dr.CLIENT_ADDR for k in sent)
    assert all(k["headers"] == dr.PROBE_HEADERS for k in sent)
    hosts = {k["host"].split(":")[0] for k in sent}
    assert hosts == {"localhost", "velometer.localhost", "www.localhost"}
    # the content probes carry the password; the lock probes go without it
    assert {k["auth"] for k in sent} == {("preview", "pw"), None}
    sent.clear()
    dr.run_caddy_probes(ORIGIN, tiny, tiny_datalab, False, None, lock_default=True, fetch=fetch)
    assert {k["auth"] for k in sent} == {None, ("preview", "a-guess")}
