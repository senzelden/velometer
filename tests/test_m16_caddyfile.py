"""M16 Task 7: `deploy/Caddyfile`, the production server's one Caddyfile (spec §4.2, §4.4, §4.6).

Two sites (the Datalab at the apex, velometer at `velometer.<domain>`) and a `www` redirect, the
host names from `{$DOMAIN}`. Headers equal each export's `_headers` plus HSTS, on the 404 page too
(the M14 deploy-doc test moved here). Every log masks client addresses and drops credentials
(legal review 5.3, fix F11); access logs roll at midnight and keep 14 days (5.4, fix F12). Every
site block imports the lock file, which holds either form of the lock (ruling P4). The behaviour
is proved against Caddy in tests/test_m15_dryrun_live.py; these tests hold the file's rules.
"""

import re
from pathlib import Path

import pytest

from velometer import datalab
from velometer.app.export import headers_text
from velometer.app.main import CSP, csp_meta

ROOT = Path(__file__).parents[1]
CADDYFILE = ROOT / "deploy" / "Caddyfile"
ENV_EXAMPLE = ROOT / "deploy" / "caddy.env.example"
DOC = ROOT / "docs" / "deploy.md"
HSTS = "max-age=31536000"
LOCK = "import /etc/caddy/lock.caddy"
APEX, VELOMETER, WWW = "{$DOMAIN}", "velometer.{$DOMAIN}", "www.{$DOMAIN}"
# every field of a log entry that carries the client's address, and the headers it must not keep:
# credentials, and what a client writes as it likes with no proxy to vouch for it (ruling R25)
MASKED = ("request>remote_ip", "request>client_ip")
DELETED = (
    "request>headers>Cookie", "request>headers>Authorization", "request>headers>X-Forwarded-For",
    "request>headers>Forwarded", "request>headers>X-Real-Ip",
)  # fmt: skip
# set by the site only where the lock file has not set it (ruling R26)
CONDITIONAL = "Cache-Control"


def _text() -> str:
    return CADDYFILE.read_text(encoding="utf-8")


def _lines(text: str) -> list[str]:
    """The file's lines without comments and blank lines, stripped."""
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if line:
            out.append(line)
    return out


def _blocks(text: str) -> dict[str, str]:
    """The top-level blocks by their opener (`{` for the global options), each block's body."""
    out: dict[str, str] = {}
    depth, opener, body = 0, None, []
    for line in _lines(text):
        if depth == 0:
            assert line.endswith("{"), f"a top-level line outside a block: {line!r}"
            opener, body = line[:-1].strip(), []
            depth = 1
            continue
        depth += line.count("{") - line.count("}")
        if depth == 0:
            assert opener not in out, f"two blocks named {opener!r}"
            out[opener] = "\n".join(body)
        else:
            body.append(line)
    assert depth == 0, "an unclosed block"
    return out


def _inner(body: str, opener: str) -> list[str]:
    """The bodies of every nested block in `body` whose line is exactly `opener {`."""
    lines = body.splitlines()
    found = []
    for i, line in enumerate(lines):
        if line == f"{opener} {{":
            depth, inner = 1, []
            for nxt in lines[i + 1 :]:
                depth += nxt.count("{") - nxt.count("}")
                if depth == 0:
                    break
                inner.append(nxt)
            found.append("\n".join(inner))
    return found


def _top_level(body: str) -> list[str]:
    """The lines of a block body at its own depth (nested blocks' contents left out)."""
    out, depth = [], 0
    for line in body.splitlines():
        if depth == 0:
            out.append(line)
        depth += line.count("{") - line.count("}")
    return out


def _header_lines(snippet: str) -> dict[str, str]:
    """The snippet's headers by name; a `?Name` line (set only if not set yet) counts as `Name`."""
    (inner,) = _inner(snippet, "header")
    out = {}
    for line in inner.splitlines():
        name, value = line.split(" ", 1)
        out[name.removeprefix("?")] = value.strip().removeprefix('"').removesuffix('"')
    return out


@pytest.mark.parametrize("snippet", ["(velometer_headers)", "(datalab_headers)"])
def test_only_cache_control_yields_to_the_lock(blocks, snippet):
    """While locked, the lock file's `no-store` (its header runs first) must survive the site's
    headers on every response, the 401 and the 404 page included (ruling R26)."""
    (inner,) = _inner(blocks[snippet], "header")
    conditional = [line.split()[0] for line in inner.splitlines() if line.startswith("?")]
    assert conditional == [f"?{CONDITIONAL}"]


def _headers_file(text: str) -> dict[str, str]:
    lines = text.splitlines()[1:]  # the first line is the path pattern
    return dict(line.strip().split(": ", 1) for line in lines if line.strip())


@pytest.fixture(scope="module")
def blocks() -> dict[str, str]:
    return _blocks(_text())


# --- sites and host names ----------------------------------------------------------------------


def test_the_sites_are_the_apex_velometer_and_www_named_only_by_the_domain_variable(blocks):
    sites = {k for k in blocks if k and not k.startswith("(")}
    assert sites == {APEX, VELOMETER, WWW}


def test_no_literal_domain_in_the_file():
    text = _text()
    assert "zaehlwerk" not in text.lower()
    hosts = re.findall(r"\b(?:[a-z0-9-]+\.)+(?:de|org|com|net|eu|io|test|localhost)\b", text)
    assert hosts == []


def test_site_roots_come_from_the_site_root_variable_with_srv_as_default(blocks):
    roots = {
        APEX: "{$SITE_ROOT:/srv}/datalab/current",
        VELOMETER: "{$SITE_ROOT:/srv}/velometer/current",
    }
    for site, root in roots.items():
        assert f"root * {root}" in _top_level(blocks[site])
        (errors,) = _inner(blocks[site], "handle_errors 404")
        # R16: an error under /tiles/ would look for the 404 page in the tiles' root
        assert f"root * {root}" in errors.splitlines()
        assert "rewrite * /404.html" in errors.splitlines()


def test_www_redirects_to_the_apex_permanently(blocks):
    assert "redir https://{$DOMAIN}{uri} 308" in _top_level(blocks[WWW])


# --- headers -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("snippet", "csp"),
    [("(velometer_headers)", csp_meta(CSP)), ("(datalab_headers)", datalab.meta_csp())],
)
def test_the_header_lines_equal_the_exported_headers_file_plus_hsts(blocks, snippet, csp):
    want = _headers_file(headers_text("/", csp)) | {"Strict-Transport-Security": HSTS}
    assert _header_lines(blocks[snippet]) == want


def test_hsts_is_one_year_without_subdomains_or_preload(blocks):
    for snippet in ("(velometer_headers)", "(datalab_headers)"):
        assert _header_lines(blocks[snippet])["Strict-Transport-Security"] == "max-age=31536000"


@pytest.mark.parametrize(
    ("site", "snippet"),
    [(APEX, "datalab_headers"), (VELOMETER, "velometer_headers"), (WWW, "datalab_headers")],
)
def test_each_site_sends_its_headers_on_every_response_and_on_the_404_page(blocks, site, snippet):
    assert f"import {snippet}" in _top_level(blocks[site])
    if site != WWW:
        (errors,) = _inner(blocks[site], "handle_errors 404")
        assert f"import {snippet}" in errors.splitlines()


def test_the_error_handler_serves_the_404_page_for_404_only(blocks):
    """A bare `handle_errors` would answer the lock's 401 with the 404 page: a page that leaks."""
    for site in (APEX, VELOMETER):
        lines = _top_level(blocks[site])
        assert "handle_errors 404 {" in lines
        assert not any(line.startswith("handle_errors") and line != "handle_errors 404 {"
                       for line in lines)  # fmt: skip


# --- the tiles ---------------------------------------------------------------------------------


def test_the_tiles_route_serves_byte_ranges_from_its_own_root_never_precompressed(blocks):
    (tiles,) = _inner(blocks[VELOMETER], "handle_path /tiles/*")
    assert tiles.splitlines() == ["root * {$SITE_ROOT:/srv}/tiles", "file_server"]
    assert "precompressed" not in tiles
    assert "/tiles/" not in blocks[APEX]


def test_precompressed_gzip_only_in_the_site_file_servers(blocks):
    for site in (APEX, VELOMETER):
        (fs,) = _inner(blocks[site], "file_server")
        assert fs.strip() == "precompressed gzip"
    assert sum("precompressed" in line for line in _lines(_text())) == 2


# --- the lock (spec §4.6, ruling P4) -----------------------------------------------------------


@pytest.mark.parametrize("site", [APEX, VELOMETER, WWW])
def test_every_site_block_imports_the_lock_file_first(blocks, site):
    lines = _top_level(blocks[site])
    assert lines[0] == LOCK


def test_the_lock_runs_before_redir_tiles_and_files_whichever_form_it_holds(blocks):
    """Both lock forms (`basic_auth { … }` and `respond "locked" 401`) must run before `redir`
    (www) and `handle_path` (tiles): by Caddy's default order they would come after."""
    glob = _top_level(blocks[""])
    assert "order basic_auth before redir" in glob
    assert "order respond after basic_auth" in glob
    # nothing else may be answered by `respond`, which the order moves ahead of everything
    assert not any(line.startswith("respond") for line in _lines(_text()))


def test_no_secret_in_the_deploy_files():
    for f in sorted((ROOT / "deploy").iterdir()):
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"\$2[aby]?\$\d\d\$", text), f.name  # a bcrypt hash
        assert "basic_auth {" not in text, f.name  # the credentials live only on the server


# --- logs (legal review 5.3, 5.4: fixes F11, F12) ----------------------------------------------


def _log_blocks(text: str) -> list[str]:
    """Every `log` block (the global default logger's and each site's), however opened."""
    lines, out = _lines(text), []
    for i, line in enumerate(lines):
        if re.fullmatch(r"log( \S+)? \{", line):
            depth, inner = 1, []
            for nxt in lines[i + 1 :]:
                depth += nxt.count("{") - nxt.count("}")
                if depth == 0:
                    break
                inner.append(nxt)
            out.append("\n".join(inner))
    return out


def test_every_log_masks_client_addresses_and_drops_credentials():
    logs = _log_blocks(_text())
    assert len(logs) == 2  # the default logger and the sites' access log snippet
    for log in logs:
        (fmt,) = _inner(log, "format filter")
        assert "wrap json" in fmt.splitlines()
        fields = fmt.splitlines()
        for field in MASKED:
            assert f"{field} ip_mask 24 48" in fields, field
        for field in DELETED:
            assert f"{field} delete" in fields, field


def test_no_log_writes_without_the_filter():
    text = _text()
    assert text.count("format filter") == len(_log_blocks(text))
    assert not re.search(r"^\s*format (?!filter)", text, re.M)


def test_the_default_logger_writes_no_access_line_and_no_stdlib_line(blocks):
    (default,) = _inner(blocks[""], "log default")
    excluded = next(line for line in _top_level(default) if line.startswith("exclude "))
    # http.stdlib's messages carry `TLS handshake error from <ip>:<port>` in the text, which no
    # field filter reaches (seen with Caddy 2.11.4 at DEBUG)
    assert set(excluded.split()[1:]) == {"http.log.access", "http.stdlib"}
    assert "output stderr" in _top_level(default)
    assert not any(line.startswith("level") for line in default.splitlines())


def test_each_file_serving_site_writes_its_own_access_log(blocks):
    assert "import access_log datalab" in _top_level(blocks[APEX])
    assert "import access_log velometer" in _top_level(blocks[VELOMETER])
    (log,) = _inner(blocks["(access_log)"], "log")
    assert "output file /var/log/caddy/{args[0]}.log {" in log.splitlines()


def test_access_logs_roll_at_midnight_and_keep_14_days_by_time(blocks):
    """Retention is time-based (ruling R27): rolled files go once 14 days old. Size and count
    must not prune first: Caddy 2.11.4 rolls at 100 MiB by default and keeps 10 files by default,
    also for `roll_keep 0` (seen live), so both are set far above a day's log."""
    (log,) = _inner(blocks["(access_log)"], "log")
    (out,) = _inner(log, "output file /var/log/caddy/{args[0]}.log")
    opts = dict(line.split(" ", 1) for line in out.splitlines())
    assert opts == {
        "roll_at": "00:00", "roll_size": "1GiB", "roll_keep": "1000", "roll_keep_for": "336h",
    }  # fmt: skip
    # 14 daily rolls plus a size roll for every GiB: 1000 files outlast 14 days of any day here
    assert int(opts["roll_keep"]) >= 14 * 2


def test_no_log_masks_x_forwarded_for_instead_of_dropping_it():
    assert "X-Forwarded-For ip_mask" not in _text()


# --- the env example and the guide -------------------------------------------------------------


def test_the_env_example_names_both_variables_without_a_secret():
    pairs = dict(
        line.split("=", 1)
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )
    assert set(pairs) == {"DOMAIN", "SITE_ROOT"}
    assert pairs["SITE_ROOT"] == "/srv"


def test_the_guide_points_to_the_file_and_carries_no_copy():
    doc = DOC.read_text(encoding="utf-8")
    assert "deploy/Caddyfile" in doc
    assert not any("handle_errors" in b for b in re.findall(r"```\n(.*?)```", doc, re.S))
    assert "test_m14_deploy_doc" not in doc
