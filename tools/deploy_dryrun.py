"""Deploy dry run: serve finished exports with the server software of a documented route and
probe what a browser gets (M15 spec, docs/superpowers/specs/2026-10-18-velometer-m15-design.md;
M16 spec §4.2, §4.4, §4.6).

- `caddy`: the official Docker image (`CADDY_IMAGE`) with `deploy/Caddyfile`, the production
  file, its three site addresses made `http://…:<port>` and `DOMAIN` set to `localhost`: the
  Datalab (`--datalab`) answers at `localhost`, velometer (`--site`) at `velometer.localhost`,
  the redirect at `www.localhost`. The probes connect to 127.0.0.1 and name the site in the Host
  header; a browser reaches the same names directly (Chrome resolves `*.localhost` to loopback).
  With `--network host` the container also binds Caddy's admin endpoint on 127.0.0.1:2019, so
  stop any other Caddy (or a `--keep-running` dry run) first. `--tiles FILE` mounts a PMTiles
  extract where the server keeps it (`TILES_MOUNT`); probes ask it for a byte range and for a
  malformed one. `--lock` locks both sites the way the server is locked until go-live (a
  `basic_auth` block in /etc/caddy/lock.caddy, its bcrypt hash made by `caddy hash-password` in
  the container at run time, never stored), with the password from $VELOMETER_PREVIEW_PASSWORD
  (ruling R28), which keeps it off the command line: every path of every host must answer 401
  without the password, and the content probes send it. `--lock-default` serves the lock the server
  comes up with (`respond "locked" 401`, ruling P4), which no password opens. Either lock also
  sets `Cache-Control: no-store`, which every locked response must carry (ruling R26). Without
  either, the lock file is empty, as after go-live. The probes connect from `CLIENT_ADDR` with a
  forged X-Forwarded-For and a cookie; afterwards the access logs and Caddy's own output must
  hold neither address unmasked, nor the cookie, the password or its Authorization value, nor
  keep any of those headers (legal review 5.3, ruling R25). `--debug-log` raises Caddy's own
  log to DEBUG, so that the 404 and 401 error entries are written there too and checked.
- `wrangler`: `wrangler pages dev` (`WRANGLER`, fetched by npx at run time), Cloudflare Pages'
  local emulation, for `--site` only.

Nothing is uploaded. The probes are pure functions of a response; `run_probes` and its siblings
fetch the paths they need and collect their problems. The exit status is 1 when any probe fails.

    uv run python tools/deploy_dryrun.py --site DIR --server caddy --datalab DIR [--tiles FILE]
        [--lock | --lock-default] [--debug-log] [--keep-running]
    uv run python tools/deploy_dryrun.py --site DIR --server wrangler [--keep-running]
"""

import argparse
import base64
import contextlib
import functools
import gzip as gzip_
import http.client
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "deploy.md"
CADDYFILE = ROOT / "deploy" / "Caddyfile"
CADDY_IMAGE = "caddy:2.11.4-alpine"
# where the server keeps each site (deploy/Caddyfile, SITE_ROOT=/srv) and the maps' basemap,
# outside the site's directory; the path a page asks for it at (main.TILES_PATH under base /)
SITE_MOUNT = "/srv/velometer/current"
DATALAB_MOUNT = "/srv/datalab/current"
TILES_MOUNT = "/srv/tiles/velometer.pmtiles"
LOCK_MOUNT = "/etc/caddy/lock.caddy"
LOG_DIR = "/var/log/caddy"
ACCESS_LOGS = ("datalab.log", "velometer.log")
TILES_URL = "/tiles/velometer.pmtiles"
PMTILES_MAGIC = b"PMTiles"
# the dry run's DOMAIN: Chrome resolves every *.localhost name to loopback by itself
DOMAIN = "localhost"
HSTS = "max-age=31536000"
# the lock (spec §4.6): the user of the basic_auth block, and the file's form until setup writes
# that block (ruling P4). Both forms forbid caching (ruling R26): the header runs before the
# site's own headers, which set Cache-Control only where it is not set yet. docs/deploy.md
# records both texts for the server setup.
LOCK_USER = "preview"
NO_STORE = 'header Cache-Control "no-store"\n'
LOCK_DEFAULT = NO_STORE + 'respond "locked" 401\n'
PASSWORD_ENV = "VELOMETER_PREVIEW_PASSWORD"  # `--lock` with no value reads it (ruling R28)
BCRYPT = re.compile(r"\$2[aby]?\$\d\d\$[./A-Za-z0-9]{53}")
# The probes connect from this loopback address (not 127.0.0.1, which Caddy's own start-up lines
# name as an admin origin), with a forged X-Forwarded-For and a cookie: none may reach a log.
CLIENT_ADDR = "127.0.0.77"
FORGED_XFF = "203.0.113.7"
MASKED = ("127.0.0.0",)  # CLIENT_ADDR at /24
COOKIE = "velometer-dryrun=c00kie-marker-5e1f"
PROBE_HEADERS = {"X-Forwarded-For": FORGED_XFF, "Cookie": COOKIE}
# the only request headers a log entry may keep: what GoAccess reads (final review I4, R52); the
# credentials and what a client writes as it likes (R25) are among the rest
KEPT_HEADERS = frozenset({"User-Agent", "Referer"})
# entry fields no log may keep: the basic-auth user, the duration, the response headers, and
# (under `request`, beside the client port) the TLS details
DROPPED_FIELDS = ("user_id", "duration", "resp_headers")
DROPPED_REQUEST_FIELDS = ("tls",)
# a site address line of deploy/Caddyfile: the apex, velometer and www, all from {$DOMAIN}
SITE_LINE = re.compile(r"^((?:[a-z]+\.)?\{\$DOMAIN\}) \{$", re.M)
SITE_COUNT = 3
# Cloudflare's _headers docs cover static asset responses and are silent on 404s; wrangler pages
# dev sends no-store on its 404. An uncached not-found answer is harmless (rulings-m15).
NOT_FOUND_EXEMPT = ("cache-control",)
WRANGLER = "wrangler@4.147.0"
# accepted media types per suffix (parameters such as charset are ignored)
TYPES = {
    ".html": ("text/html",),
    ".json": ("application/json",),
    ".geojson": ("application/geo+json", "application/json"),
    ".csv": ("text/csv",),
    ".css": ("text/css",),
    ".js": ("text/javascript", "application/javascript"),
    ".svg": ("image/svg+xml",),
    ".woff2": ("font/woff2",),
}


class DryRunError(Exception):
    """The dry run cannot go on (an unexpected Caddyfile, no server, an export it cannot read)."""


@dataclass
class Resp:
    status: int
    headers: dict[str, str]  # names lower-case; repeated headers joined with ", "
    body: bytes  # as sent: still compressed when Content-Encoding says so
    url: str  # the final URL, after redirects

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def decoded(self) -> bytes | None:
        """The body without its Content-Encoding; None for an encoding it cannot undo."""
        enc = (self.header("content-encoding") or "identity").strip().lower()
        if enc == "identity":
            return self.body
        if enc == "gzip":
            try:
                return gzip_.decompress(self.body)
            except (OSError, EOFError, zlib.error):
                return None
        return None


def dryrun_caddyfile(text: str, port: int, debug: bool = False) -> str:
    """deploy/Caddyfile served locally: each of its three site addresses (`{$DOMAIN}`,
    `velometer.{$DOMAIN}`, `www.{$DOMAIN}`) becomes `http://<address>:<port>`, plain HTTP on
    `port`; with `debug`, Caddy's own logger (`output stderr`) gets `level DEBUG`. Nothing else
    changes."""
    sites = SITE_LINE.findall(text)
    if len(sites) != SITE_COUNT or len(set(sites)) != SITE_COUNT:
        raise DryRunError(
            f"deploy/Caddyfile: expected {SITE_COUNT} site addresses built from {{$DOMAIN}}, "
            f"found {sites}"
        )
    out = SITE_LINE.sub(lambda m: f"http://{m.group(1)}:{port} {{", text)
    if debug:
        if out.count("\t\toutput stderr\n") != 1:
            raise DryRunError("deploy/Caddyfile: no single `output stderr` (the default logger)")
        out = out.replace("\t\toutput stderr\n", "\t\toutput stderr\n\t\tlevel DEBUG\n")
    return out


def lock_text(bcrypt_hash: str) -> str:
    """/etc/caddy/lock.caddy while the sites are locked: one user, `LOCK_USER`; nothing cached."""
    if not BCRYPT.fullmatch(bcrypt_hash):
        raise DryRunError("caddy hash-password gave no bcrypt hash")
    return NO_STORE + f"basic_auth {{\n\t{LOCK_USER} {bcrypt_hash}\n}}\n"


def hash_password(password: str, image: str = CADDY_IMAGE) -> str:
    """The bcrypt hash of `password` from `caddy hash-password` in the pinned image; the password
    goes in on stdin, never on a command line."""
    try:
        r = subprocess.run(
            ["docker", "run", "--rm", "-i", image, "caddy", "hash-password"],
            input=password.encode() + b"\n",
            capture_output=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DryRunError(f"caddy hash-password: docker not runnable ({e})") from None
    if r.returncode != 0:
        raise DryRunError(f"caddy hash-password failed: {r.stderr.decode(errors='replace')}")
    return r.stdout.decode().strip().splitlines()[-1] if r.stdout.strip() else ""


def headers_rules(text: str) -> list[tuple[str, dict[str, str]]]:
    """The rules of a `_headers` file: (path pattern, {lower-case name: value}) in file order."""
    rules: list[tuple[str, dict[str, str]]] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            rules.append((line.strip(), {}))
            continue
        if not rules:
            raise DryRunError(f"_headers: a header line before any path: {line!r}")
        name, sep, value = line.strip().partition(":")
        if not sep:
            raise DryRunError(f"_headers: not `Name: value`: {line!r}")
        rules[-1][1][name.strip().lower()] = value.strip()
    return rules


def expected_headers(rules: list[tuple[str, dict[str, str]]], path: str) -> dict[str, str]:
    """The headers the rules set for `path` (a pattern ending in `*` matches by prefix)."""
    out: dict[str, str] = {}
    for pattern, headers in rules:
        if pattern == path or (pattern.endswith("*") and path.startswith(pattern[:-1])):
            out.update(headers)
    return out


def check_status(path: str, r: Resp, want: int = 200) -> list[str]:
    return [] if r.status == want else [f"{path}: status {r.status}, expected {want}"]


def check_headers(path: str, r: Resp, expected: dict[str, str]) -> list[str]:
    problems = []
    for name, want in expected.items():
        got = r.header(name)
        if got is None:
            problems.append(f"{path}: missing header {name} (expected {want!r})")
        elif got.strip() != want:
            problems.append(f"{path}: header {name} is {got!r}, expected {want!r}")
    return problems


def check_body(path: str, r: Resp, original: bytes, require_gzip: bool) -> list[str]:
    """The body decodes to `original`; with `require_gzip` it must come gzip-encoded."""
    problems = []
    enc = (r.header("content-encoding") or "identity").strip().lower()
    if require_gzip and enc != "gzip":
        problems.append(f"{path}: not gzip-encoded (Content-Encoding {enc}) though a .gz exists")
    body = r.decoded()
    if body is None:
        problems.append(f"{path}: cannot decode Content-Encoding {enc}")
    elif body != original:
        problems.append(f"{path}: body ({len(body)} bytes) differs from the file ({len(original)})")
    return problems


def check_type(path: str, r: Resp, suffix: str) -> list[str]:
    ctype = r.header("content-type")
    mime = (ctype or "").split(";")[0].strip().lower()
    if mime in TYPES[suffix]:
        return []
    return [f"{path}: Content-Type {ctype!r}, expected one of {', '.join(TYPES[suffix])}"]


def check_404(path: str, r: Resp, page: bytes, expected: dict[str, str]) -> list[str]:
    problems = check_status(path, r, 404)
    if r.decoded() != page:
        problems.append(f"{path}: the body is not 404.html")
    kept = {name: v for name, v in expected.items() if name not in NOT_FOUND_EXEMPT}
    return problems + check_headers(path, r, kept)


def check_tiles(path: str, r: Resp) -> list[str]:
    """`Range: bytes=0-15` on the tile file: 206 with exactly those 16 bytes, unencoded (the
    reader asks for byte offsets of the file as stored)."""
    problems = []
    if r.status != 206:
        problems.append(f"{path}: a byte range answered {r.status}, not 206 (no Range support?)")
    enc = (r.header("content-encoding") or "identity").strip().lower()
    if enc != "identity":
        problems.append(f"{path}: a byte range sent with Content-Encoding {enc}")
    if len(r.body) != 16 or not r.body.startswith(PMTILES_MAGIC):
        problems.append(f"{path}: the first 16 bytes are not a PMTiles header ({r.body[:16]!r})")
    return problems


def check_page(path: str, r: Resp, page: bytes, origin: str) -> list[str]:
    """`path` ends, after any redirects, on this site with `page` as its body."""
    problems = check_status(path, r)
    if not r.url.startswith(origin + "/"):
        problems.append(f"{path}: ended off the site, at {r.url}")
    if r.decoded() != page:
        problems.append(f"{path}: the body is not the page's index.html")
    return problems


def check_bad_range(path: str, r: Resp) -> list[str]:
    """A malformed `Range` on the tile file: 416, and none of the file's bytes."""
    problems = check_status(path, r, 416)
    if PMTILES_MAGIC in r.body:
        problems.append(f"{path}: a malformed byte range was answered with the file")
    return problems


def check_no_store(label: str, r: Resp) -> list[str]:
    """While locked, no response may be stored by any cache (ruling R26)."""
    got = r.header("cache-control")
    return [] if got == "no-store" else [f"{label}: Cache-Control {got!r} while locked"]


def check_locked(label: str, r: Resp) -> list[str]:
    """A request without the password: 401, nothing of the site (no page, no file), and
    nothing a cache may keep."""
    problems = check_status(label, r, 401) + check_no_store(label, r)
    if b"<" in r.body or PMTILES_MAGIC in r.body or len(r.body) > 64:
        problems.append(f"{label}: the 401 carries a body of {len(r.body)} bytes ({r.body[:40]!r})")
    return problems


def check_redirect(label: str, r: Resp, location: str) -> list[str]:
    """`www.` sends the reader to the apex: 308 to `location`."""
    problems = check_status(label, r, 308)
    if r.header("location") != location:
        problems.append(f"{label}: redirects to {r.header('location')!r}, not {location!r}")
    return problems


def check_logs(logs: dict[str, str], secrets: dict[str, str], masked_in: list[str]) -> list[str]:
    """No log (`name: text`) holds the probes' address, the forged X-Forwarded-For or a secret
    (`what: value`), and no JSON entry keeps a request header outside `KEPT_HEADERS` (Caddy
    itself only redacts the credentials' values), the client port or a `DROPPED_FIELDS` field;
    each log in `masked_in` shows the probes' address masked to /24, so it did log the probes."""
    problems = []
    forbidden = {"the client address": CLIENT_ADDR, "the forged X-Forwarded-For": FORGED_XFF}
    for name, text in logs.items():
        for what, value in (forbidden | secrets).items():
            if value and value in text:
                problems.append(f"log {name}: holds {what} unmasked")
    for name, text in logs.items():
        kept, port, fields = set(), False, set()
        for line in text.splitlines():
            with contextlib.suppress(ValueError, AttributeError):
                entry = json.loads(line)
                request = entry.get("request", {})
                kept |= set(request.get("headers", {})) - KEPT_HEADERS
                port = port or "remote_port" in request
                fields |= {f for f in DROPPED_FIELDS if f in entry}
                fields |= {f"request>{f}" for f in DROPPED_REQUEST_FIELDS if f in request}
        problems += [f"log {name}: keeps the {h} header" for h in sorted(kept)]
        if port:
            problems.append(f"log {name}: keeps the client port (request>remote_port)")
        problems += [f"log {name}: keeps {f}" for f in sorted(fields)]
    for name in masked_in:
        text = logs.get(name, "")
        missing = [m for m in MASKED if m not in text]
        if missing:
            problems.append(f"log {name}: no masked address {', '.join(missing)} (nothing logged?)")
    return problems


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.found += [v for k, v in attrs if k in ("href", "src") and v]


def site_links(html: str, base: str) -> list[str]:
    """The distinct paths under `base` that `html` links or loads, without query or fragment."""
    p = _Links()
    p.feed(html)
    out = set()
    for v in p.found:
        if v.startswith(base) and not v.startswith("//"):
            path = v.split("#", 1)[0].split("?", 1)[0]
            if path:
                out.add(path)
    return sorted(out)


def pick_paths(site: Path, base: str) -> dict[str, str]:
    """The paths the probes visit: home, a city page (Berlin if exported), the German home,
    series.json, the first tier map and app.css."""
    cities = sorted(p.parent.name for p in (site / "city").glob("*/index.html"))
    if not cities:
        raise DryRunError(f"{site}: no city page")
    city = "berlin" if "berlin" in cities else cities[0]
    maps = sorted((site / "maps").glob("*.geojson"))
    if not maps:
        raise DryRunError(f"{site}: no tier-map GeoJSON in maps/")
    paths = {
        "home": base,
        "city": f"{base}city/{city}",
        "de": f"{base}de",
        "json": f"{base}data/series.json",
        "geojson": f"{base}maps/{maps[0].name}",
        "css": f"{base}static/app.css",
    }
    # a CSV and a script too, where the export has them (the spec's content types)
    for key, pattern in (("csv", "data/*.csv"), ("js", "static/*.js")):
        found = sorted(site.glob(pattern))
        if found:
            paths[key] = base + found[0].relative_to(site).as_posix()
    return paths


def _file(site: Path, base: str, path: str) -> Path:
    f = site / path.removeprefix(base)
    return f / "index.html" if f.is_dir() else f


class _FromHandler(urllib.request.HTTPHandler):
    """Connects from `source`, a local address (the probes' `CLIENT_ADDR`)."""

    def __init__(self, source: str):
        super().__init__()
        self.source = source

    def http_open(self, req):
        conn = functools.partial(http.client.HTTPConnection, source_address=(self.source, 0))
        return self.do_open(conn, req)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # the redirect itself is the answer


def basic_auth(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def fetch_url(
    url: str,
    gzip: bool = False,
    byte_range: str | None = None,
    *,
    host: str | None = None,
    auth: tuple[str, str] | None = None,
    source: str | None = None,
    headers: dict[str, str] | None = None,
    follow: bool = True,
) -> Resp:
    """GET `url` (following redirects unless `follow` is False); repeated response headers are
    joined with ", ". `host` is sent as the Host header, `auth` as basic auth, from the local
    address `source`, with `headers` added."""
    sent = {"Accept-Encoding": "gzip" if gzip else "identity", "User-Agent": "velometer-dryrun"}
    if byte_range:
        sent["Range"] = f"bytes={byte_range}"
    if host:
        sent["Host"] = host
    if auth:
        sent["Authorization"] = basic_auth(*auth)
    sent |= headers or {}
    req = urllib.request.Request(url, headers=sent)
    handlers: list[urllib.request.BaseHandler] = []
    if source:
        handlers.append(_FromHandler(source))
    if not follow:
        handlers.append(_NoRedirect())
    opener = urllib.request.build_opener(*handlers)

    def merged(msg) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in msg.items():
            k = k.lower()
            out[k] = f"{out[k]}, {v}" if k in out else v
        return out

    try:
        with opener.open(req, timeout=30) as r:
            return Resp(r.status, merged(r.headers), r.read(), r.geturl())
    except urllib.error.HTTPError as e:
        with e:
            return Resp(e.code, merged(e.headers), e.read(), e.geturl())


def _probe_files(
    origin: str,
    site: Path,
    base: str,
    paths: list[str],
    rules: list[tuple[str, dict[str, str]]],
    require_gzip: bool,
    fetch: Callable[..., Resp],
    extra: dict[str, str],
) -> tuple[int, list[str]]:
    """Each path: status 200, its headers (the rules', plus `extra`), type and body."""
    problems: list[str] = []
    n = 0
    for path in paths:
        f = _file(site, base, path)
        r = fetch(origin + path, gzip=True)
        gz = require_gzip and f.with_name(f.name + ".gz").is_file()
        for found in (
            check_status(path, r),
            check_headers(path, r, expected_headers(rules, path) | extra),
            check_type(path, r, f.suffix),
            check_body(path, r, f.read_bytes(), gz),
        ):
            n += 1
            problems += found
    return n, problems


def _probe_404s(origin, site, base, nopes, rules, fetch, extra) -> tuple[int, list[str]]:
    problems: list[str] = []
    for nope in nopes:
        problems += check_404(
            nope,
            fetch(origin + nope),
            (site / "404.html").read_bytes(),
            expected_headers(rules, nope) | extra,
        )
    return len(nopes), problems


def _probe_links(origin: str, base: str, fetch: Callable[..., Resp]) -> tuple[int, list[str]]:
    """Every path the home page links or loads answers 2xx."""
    problems: list[str] = []
    home = fetch(origin + base).decoded() or b""
    links = site_links(home.decode("utf-8", "replace"), base)
    for link in links:
        r = fetch(origin + link)
        if not 200 <= r.status < 300:
            problems.append(f"{link}: linked from {base}, status {r.status}")
    return len(links), problems


def run_probes(
    origin: str,
    site: Path,
    base: str,
    require_gzip: bool,
    fetch: Callable[..., Resp] = fetch_url,
    tiles: bool = False,
    extra: dict[str, str] | None = None,
) -> tuple[int, list[str]]:
    """Probe the server at `origin` serving `site` under `base`: (checks run, problems); with
    `tiles`, also a byte range of the basemap file served beside the site. `extra` names headers
    the server sends beyond the `_headers` file (HSTS)."""
    extra = extra or {}
    rules = headers_rules((site / "_headers").read_text(encoding="utf-8"))
    paths = pick_paths(site, base)
    n, problems = _probe_files(
        origin, site, base, list(paths.values()), rules, require_gzip, fetch, extra
    )
    # the city page in its other form (with or without the trailing slash) reaches the same page
    city = paths["city"]
    other = city[:-1] if city.endswith("/") else city + "/"
    n += 1
    problems += check_page(
        other, fetch(origin + other), _file(site, base, city).read_bytes(), origin
    )
    # an unknown path, at the top and under the tiles route (served from another root)
    nopes = [f"{base}nope-{secrets.token_hex(4)}", f"{base}tiles/nope-{secrets.token_hex(4)}"]
    k, found = _probe_404s(origin, site, base, nopes, rules, fetch, extra)
    n, problems = n + k, problems + found
    if tiles:
        n += 2
        # gzip offered: a byte range must still come back as stored
        problems += check_tiles(TILES_URL, fetch(origin + TILES_URL, gzip=True, byte_range="0-15"))
        problems += check_bad_range(TILES_URL, fetch(origin + TILES_URL, byte_range="0-x"))
    k, found = _probe_links(origin, base, fetch)
    return n + k, problems + found


def datalab_paths(site: Path) -> list[str]:
    """The Datalab paths the probes visit: its pages, its stylesheet, script, a font and the
    favicon, whichever of these the build has."""
    paths = []
    for page in sorted(site.rglob("index.html")):
        rel = page.parent.relative_to(site).as_posix()
        paths.append("/" if rel == "." else f"/{rel}/")
    paths.sort()
    for pattern in ("static/*.css", "static/*.js", "static/*.svg", "static/fonts/*.woff2"):
        found = sorted(site.glob(pattern))
        if found:
            paths.append("/" + found[0].relative_to(site).as_posix())
    if "/" not in paths:
        raise DryRunError(f"{site}: no index.html")
    return paths


def run_datalab_probes(
    origin: str,
    site: Path,
    require_gzip: bool,
    fetch: Callable[..., Resp] = fetch_url,
    extra: dict[str, str] | None = None,
) -> tuple[int, list[str]]:
    """Probe the Datalab at `origin`: its pages and files, its 404 page and its home's links."""
    extra = extra or {}
    rules = headers_rules((site / "_headers").read_text(encoding="utf-8"))
    n, problems = _probe_files(
        origin, site, "/", datalab_paths(site), rules, require_gzip, fetch, extra
    )
    nopes = [f"/nope-{secrets.token_hex(4)}", f"/impressum/nope-{secrets.token_hex(4)}"]
    k, found = _probe_404s(origin, site, "/", nopes, rules, fetch, extra)
    n, problems = n + k, problems + found
    k, found = _probe_links(origin, "/", fetch)
    return n + k, problems + found


def lock_paths() -> list[str]:
    """What the lock probes ask every host for: pages, files and their `.gz` siblings (which
    `precompressed` serves), the tile file, the 404 page, an unknown path at the top and under
    the tiles route, robots.txt."""
    nope = secrets.token_hex(4)
    return [
        "/", "/de", "/city/berlin/", "/impressum/", "/data/series.json", "/static/app.css",
        "/static/app.css.gz", "/data/series.json.gz", "/404.html", f"/nope-{nope}", TILES_URL,
        f"/tiles/nope-{nope}", "/robots.txt",
    ]  # fmt: skip


def hosts(port: int, domain: str = DOMAIN) -> dict[str, str]:
    """The Host header of each site, as a browser sends it (with the port)."""
    return {
        "datalab": f"{domain}:{port}",
        "velometer": f"velometer.{domain}:{port}",
        "www": f"www.{domain}:{port}",
    }


def run_lock_probes(
    origin: str, fetch: Callable[..., Resp] = fetch_url, auth: tuple[str, str] | None = None
) -> tuple[int, list[str]]:
    """Every path of every host answers 401 with nothing of the site, without credentials (and,
    with `auth`, also with those: the lock that no password opens). Each asks with gzip offered,
    and the tile file is asked once more for a byte range."""
    port = int(origin.rsplit(":", 1)[1])
    problems: list[str] = []
    n = 0
    for name, host in hosts(port).items():
        for path in lock_paths():
            for creds in (None, auth) if auth else (None,):
                n += 1
                label = f"{name} {path}" + (" (with a password)" if creds else "")
                r = fetch(origin + path, gzip=True, host=host, auth=creds, follow=False)
                problems += check_locked(label, r)
        n += 1
        r = fetch(origin + TILES_URL, byte_range="0-15", host=host, auth=None, follow=False)
        problems += check_locked(f"{name} {TILES_URL} (Range bytes=0-15)", r)
    return n, problems


def run_caddy_probes(
    origin: str,
    site: Path,
    datalab: Path,
    tiles: bool,
    password: str | None,
    lock_default: bool = False,
    fetch: Callable[..., Resp] = fetch_url,
) -> tuple[int, list[str]]:
    """Both sites and the redirect behind deploy/Caddyfile, from `CLIENT_ADDR` with
    `PROBE_HEADERS`: with `lock_default` only the lock (no password opens it); otherwise the
    content probes (with the password, if locked), www's redirect and, if locked, the lock."""
    port = int(origin.rsplit(":", 1)[1])
    host = hosts(port)
    base = functools.partial(fetch, source=CLIENT_ADDR, headers=PROBE_HEADERS)
    if lock_default:
        return run_lock_probes(origin, base, auth=(LOCK_USER, "a-guess"))
    auth = (LOCK_USER, password) if password else None
    hsts = {"strict-transport-security": HSTS}
    if password:  # the password opens the sites, not the caches (ruling R26)
        hsts["cache-control"] = "no-store"
    n, problems = run_probes(
        origin, site, "/", True, functools.partial(base, host=host["velometer"], auth=auth),
        tiles=tiles, extra=hsts,
    )  # fmt: skip
    k, found = run_datalab_probes(
        origin, datalab, True, functools.partial(base, host=host["datalab"], auth=auth), hsts
    )
    n, problems = n + k, problems + found
    if password:  # check_404 leaves Cache-Control out (rulings-m15); the lock does not
        for name in ("velometer", "datalab"):
            n += 1
            nope = f"/nope-{secrets.token_hex(4)}"
            r = base(origin + nope, host=host[name], auth=auth)
            problems += check_status(f"{name} {nope}", r, 404) + check_no_store(f"{name} {nope}", r)
    for path in ("/", "/impressum/", "/city/berlin?x=1"):
        n += 1
        r = base(origin + path, host=host["www"], auth=auth, follow=False)
        problems += check_redirect(f"www {path}", r, f"https://{DOMAIN}{path}")
        if password:
            problems += check_no_store(f"www {path}", r)
    if password:
        k, found = run_lock_probes(origin, base)
        n, problems = n + k, problems + found
    return n, problems


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float) -> None:
    """Return once anything answers at `url` (any HTTP status); DryRunError after `timeout`."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except urllib.error.HTTPError as e:
            e.close()
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise DryRunError(f"no answer from {url} within {timeout:g} s")


def caddy_command(
    site: Path,
    datalab: Path,
    caddyfile: Path,
    lock: Path,
    name: str,
    image: str = CADDY_IMAGE,
    tiles: Path | None = None,
) -> list[str]:
    # host networking: the site addresses' port is the host's; DOMAIN fills {$DOMAIN}, and
    # SITE_ROOT is left to the Caddyfile's default (/srv)
    mount_tiles = ["-v", f"{tiles.resolve()}:{TILES_MOUNT}:ro"] if tiles else []
    return [
        "docker", "run", "--rm", "--name", name, "--network", "host",
        "-e", f"DOMAIN={DOMAIN}",
        "-v", f"{site.resolve()}:{SITE_MOUNT}:ro",
        "-v", f"{datalab.resolve()}:{DATALAB_MOUNT}:ro",
        *mount_tiles,
        "-v", f"{caddyfile}:/etc/caddy/Caddyfile:ro",
        "-v", f"{lock}:{LOCK_MOUNT}:ro",
        image,
    ]  # fmt: skip


def wrangler_command(site: Path, port: int, inspector_port: int) -> list[str]:
    return [
        "npx", "--yes", WRANGLER, "pages", "dev", str(site.resolve()),
        "--ip", "127.0.0.1", "--port", str(port), "--inspector-port", str(inspector_port),
    ]  # fmt: skip


def _log_tail(log: Path, lines: int = 30) -> str:
    try:
        return "\n".join(log.read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no server log)"


@dataclass
class Served:
    origin: str
    logs: Callable[[], dict[str, str]]  # each log the server wrote so far, by name


def _no_logs() -> dict[str, str]:
    return {}


@contextlib.contextmanager
def caddy_server(
    site: Path,
    datalab: Path,
    tiles: Path | None = None,
    lock: str = "",
    debug: bool = False,
):
    """Caddy in Docker with deploy/Caddyfile serving `site` and `datalab` (and the tile file, if
    given), `lock` as /etc/caddy/lock.caddy (empty: unlocked); yields a `Served` whose `logs`
    are Caddy's output and the access log files; removes the container."""
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    name = f"velometer-dryrun-{port}"
    work = Path(tempfile.mkdtemp(prefix="deploy-dryrun-caddy-"))
    log = work / "server.log"
    proc = None

    def logs() -> dict[str, str]:
        out = {"caddy output": log.read_text(errors="replace")}
        for f in ACCESS_LOGS:
            r = subprocess.run(
                ["docker", "exec", name, "cat", f"{LOG_DIR}/{f}"], capture_output=True
            )
            out[f] = r.stdout.decode(errors="replace") if r.returncode == 0 else ""
        return out

    try:
        caddyfile = work / "Caddyfile"
        caddyfile.write_text(
            dryrun_caddyfile(CADDYFILE.read_text(encoding="utf-8"), port, debug), encoding="utf-8"
        )
        lockfile = work / "lock.caddy"
        lockfile.write_text(lock, encoding="utf-8")
        try:
            with log.open("wb") as out:
                proc = subprocess.Popen(
                    caddy_command(site, datalab, caddyfile, lockfile, name, tiles=tiles),
                    stdout=out,
                    stderr=subprocess.STDOUT,
                )
        except OSError as e:
            raise DryRunError(f"caddy: docker not found or not runnable ({e})") from None
        try:
            wait_http(origin + "/", 120)
        except DryRunError as e:
            raise DryRunError(f"caddy: {e}\n{_log_tail(log)}") from None
        yield Served(origin, logs)
    finally:
        if proc is not None:
            subprocess.run(["docker", "stop", "-t", "5", name], capture_output=True)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        shutil.rmtree(work, ignore_errors=True)


@contextlib.contextmanager
def wrangler_server(site: Path):
    """`wrangler pages dev` in its own process group; yields a `Served`, stops the group."""
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    work = Path(tempfile.mkdtemp(prefix="deploy-dryrun-wrangler-"))  # wrangler's .wrangler/
    env = {**os.environ, "WRANGLER_SEND_METRICS": "false", "CI": "1"}
    log = work / "server.log"
    proc = None
    try:
        try:
            with log.open("wb") as out:
                proc = subprocess.Popen(
                    wrangler_command(site, port, free_port()),
                    cwd=work,
                    env=env,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except OSError as e:
            raise DryRunError(f"wrangler: npx not found or not runnable ({e})") from None
        try:
            wait_http(origin + "/", 300)
        except DryRunError as e:
            raise DryRunError(f"wrangler: {e}\n{_log_tail(log)}") from None
        yield Served(origin, _no_logs)
    finally:
        if proc is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=15)
            # npx may exit while workerd, its child, ignores SIGTERM: end the whole group
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        shutil.rmtree(work, ignore_errors=True)


def _site_error(path: Path, what: str) -> str | None:
    """Why `path` cannot be served as an export made with --base / (None: it can)."""
    try:
        base = json.loads((path / "build.json").read_text(encoding="utf-8"))["base"]
    except (OSError, ValueError, KeyError):
        return f"{path} has no readable build.json; export the {what} first"
    if base != "/":
        return f"both routes serve an export made with --base /; this one has base {base}"
    if not (path / "_headers").is_file():
        return f"{path} has no _headers file"
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--site", type=Path, required=True, help="a finished export (--base /)")
    ap.add_argument("--server", choices=("caddy", "wrangler"), required=True)
    ap.add_argument(
        "--datalab",
        type=Path,
        help="a finished Datalab build (velometer datalab build), served at the apex (caddy only, "
        "required there)",
    )
    ap.add_argument(
        "--tiles",
        type=Path,
        help="a PMTiles extract to serve beside the site at /tiles/velometer.pmtiles (caddy only)",
    )
    lock = ap.add_mutually_exclusive_group()
    lock.add_argument(
        "--lock",
        metavar="PASSWORD",
        nargs="?",
        const="",
        help=f"lock both sites with basic auth, user {LOCK_USER} (caddy only); with no value, "
        f"the password is read from ${PASSWORD_ENV} and stays off the command line",
    )
    lock.add_argument(
        "--lock-default",
        action="store_true",
        help='serve the lock the server comes up with, `respond "locked" 401` (caddy only)',
    )
    ap.add_argument(
        "--debug-log",
        action="store_true",
        help="raise Caddy's own log to DEBUG, so its error entries are written and checked too",
    )
    ap.add_argument(
        "--keep-running",
        action="store_true",
        help="after the probes, keep serving until Ctrl-C (for render_pass.py --url)",
    )
    a = ap.parse_args(argv)
    site = a.site.resolve()
    if err := _site_error(site, "static edition"):
        ap.error(err)
    caddy = a.server == "caddy"
    if not caddy and (a.datalab or a.tiles or a.lock or a.lock_default or a.debug_log):
        ap.error("--datalab, --tiles, --lock, --lock-default and --debug-log need --server caddy")
    if a.tiles is not None and not a.tiles.is_file():
        ap.error(f"--tiles needs an existing file, not {a.tiles}")
    datalab = None
    if caddy:
        if a.datalab is None:
            ap.error("--server caddy serves both sites: name the Datalab build with --datalab")
        datalab = a.datalab.resolve()
        if not (datalab / "_headers").is_file() or not (datalab / "404.html").is_file():
            ap.error(f"{datalab} is no Datalab build (no _headers or 404.html)")
    if a.lock == "":
        a.lock = os.environ.get(PASSWORD_ENV, "")
        if not a.lock:
            ap.error(f"--lock with no value reads ${PASSWORD_ENV}, which is not set")
    try:
        if caddy:
            lock = LOCK_DEFAULT if a.lock_default else ""
            if a.lock:
                lock = lock_text(hash_password(a.lock))
            server = caddy_server(site, datalab, a.tiles, lock, a.debug_log)
        else:
            server = wrangler_server(site)
        with server as served:
            origin = served.origin
            if caddy:
                port = origin.rsplit(":", 1)[1]
                print(
                    f"caddy serving {site} at http://velometer.{DOMAIN}:{port}/ and {datalab} "
                    f"at http://{DOMAIN}:{port}/"
                    + (f" (locked, user {LOCK_USER})" if a.lock else "")
                    + (" (locked for everyone)" if a.lock_default else ""),
                    flush=True,
                )
                n, problems = run_caddy_probes(
                    origin, site, datalab, a.tiles is not None, a.lock, a.lock_default
                )
                n += 1
                secrets_ = {"the cookie": COOKIE.split("=", 1)[1]}
                if a.lock:
                    secrets_ |= {
                        "the password": a.lock,
                        "the Authorization value": basic_auth(LOCK_USER, a.lock).split()[1],
                    }
                masked_in = list(ACCESS_LOGS) + (["caddy output"] if a.debug_log else [])
                problems += check_logs(served.logs(), secrets_, masked_in)
            else:
                print(f"wrangler serving {site} at {origin}/", flush=True)
                n, problems = run_probes(origin, site, "/", require_gzip=False)
            for p in problems:
                print(f"  problem: {p}")
            print(f"{n} checks, {len(problems)} problems", flush=True)
            if a.keep_running:
                print("serving until Ctrl-C", flush=True)
                with contextlib.suppress(KeyboardInterrupt):
                    while True:
                        time.sleep(3600)
    except DryRunError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
