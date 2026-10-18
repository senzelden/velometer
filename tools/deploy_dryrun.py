"""Deploy dry run: serve a finished export with the server software of a documented route and
probe what a browser gets (M15 spec, docs/superpowers/specs/2026-10-18-velometer-m15-design.md).

- `caddy`: the official Docker image (`CADDY_IMAGE`) with the Caddyfile from docs/deploy.md,
  its site address replaced by `http://127.0.0.1:<port>`;
- `wrangler`: `wrangler pages dev` (`WRANGLER`, fetched by npx at run time), Cloudflare Pages'
  local emulation.

Nothing is uploaded. The probes are pure functions of a response; `run_probes` fetches the paths
they need and collects their problems. The exit status is 1 when any probe fails.

    uv run python tools/deploy_dryrun.py --site DIR --server caddy|wrangler [--keep-running]
"""

import argparse
import contextlib
import gzip as gzip_
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
import textwrap
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
SITE_ADDRESS = "velometer.<domain>"  # the Caddyfile's site address in docs/deploy.md
CADDY_IMAGE = "caddy:2.10.2-alpine"
WRANGLER = "wrangler@4.147.0"
# accepted media types per suffix (parameters such as charset are ignored)
TYPES = {
    ".html": ("text/html",),
    ".json": ("application/json",),
    ".geojson": ("application/geo+json", "application/json"),
    ".csv": ("text/csv",),
    ".css": ("text/css",),
    ".js": ("text/javascript", "application/javascript"),
}


class DryRunError(Exception):
    """The dry run cannot go on (no Caddyfile in the doc, no server, an export it cannot read)."""


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


def caddyfile_from_doc(doc: str, address: str) -> str:
    """The one Caddyfile in docs/deploy.md (the fenced block holding `handle_errors`), dedented,
    with its site address `velometer.<domain>` replaced by `address`."""
    blocks = [
        textwrap.dedent(b) for b in re.findall(r"```\n(.*?)```", doc, re.S) if "handle_errors" in b
    ]
    if len(blocks) != 1:
        raise DryRunError(f"docs/deploy.md: expected one Caddyfile block, found {len(blocks)}")
    opener = f"{SITE_ADDRESS} {{"
    if blocks[0].count(opener) != 1:
        raise DryRunError(f"docs/deploy.md: the Caddyfile has no single `{opener}` site block")
    return blocks[0].replace(opener, f"{address} {{")


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
    return problems + check_headers(path, r, expected)


def check_page(path: str, r: Resp, page: bytes, origin: str) -> list[str]:
    """`path` ends, after any redirects, on this site with `page` as its body."""
    problems = check_status(path, r)
    if not r.url.startswith(origin + "/"):
        problems.append(f"{path}: ended off the site, at {r.url}")
    if r.decoded() != page:
        problems.append(f"{path}: the body is not the page's index.html")
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


def fetch_url(url: str, gzip: bool = False) -> Resp:
    """GET `url` (following redirects); repeated response headers are joined with ", "."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": "gzip" if gzip else "identity",
            "User-Agent": "velometer-dryrun",
        },
    )

    def merged(msg) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in msg.items():
            k = k.lower()
            out[k] = f"{out[k]}, {v}" if k in out else v
        return out

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return Resp(r.status, merged(r.headers), r.read(), r.geturl())
    except urllib.error.HTTPError as e:
        with e:
            return Resp(e.code, merged(e.headers), e.read(), e.geturl())


def run_probes(
    origin: str,
    site: Path,
    base: str,
    require_gzip: bool,
    fetch: Callable[..., Resp] = fetch_url,
) -> tuple[int, list[str]]:
    """Probe the server at `origin` serving `site` under `base`: (checks run, problems)."""
    rules = headers_rules((site / "_headers").read_text(encoding="utf-8"))
    paths = pick_paths(site, base)
    problems: list[str] = []
    n = 0
    for path in paths.values():
        f = _file(site, base, path)
        r = fetch(origin + path, gzip=True)
        gz = require_gzip and f.with_name(f.name + ".gz").is_file()
        for found in (
            check_status(path, r),
            check_headers(path, r, expected_headers(rules, path)),
            check_type(path, r, f.suffix),
            check_body(path, r, f.read_bytes(), gz),
        ):
            n += 1
            problems += found
    # the city page in its other form (with or without the trailing slash) reaches the same page
    city = paths["city"]
    other = city[:-1] if city.endswith("/") else city + "/"
    n += 1
    problems += check_page(
        other, fetch(origin + other), _file(site, base, city).read_bytes(), origin
    )
    # an unknown path
    nope = f"{base}nope-{secrets.token_hex(4)}"
    n += 1
    problems += check_404(
        nope,
        fetch(origin + nope),
        (site / "404.html").read_bytes(),
        expected_headers(rules, nope),
    )
    # every path the home page links or loads
    home = fetch(origin + base).decoded() or b""
    for link in site_links(home.decode("utf-8", "replace"), base):
        n += 1
        r = fetch(origin + link)
        if not 200 <= r.status < 300:
            problems.append(f"{link}: linked from {base}, status {r.status}")
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


def caddy_command(site: Path, caddyfile: Path, name: str, image: str = CADDY_IMAGE) -> list[str]:
    # host networking: the site address 127.0.0.1:<port> is the host's loopback
    return [
        "docker", "run", "--rm", "--name", name, "--network", "host",
        "-v", f"{site.resolve()}:/srv/velometer:ro",
        "-v", f"{caddyfile}:/etc/caddy/Caddyfile:ro",
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


@contextlib.contextmanager
def caddy_server(site: Path):
    """Caddy in Docker with the documented Caddyfile; yields the origin, removes the container."""
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    work = Path(tempfile.mkdtemp(prefix="deploy-dryrun-caddy-"))
    caddyfile = work / "Caddyfile"
    caddyfile.write_text(caddyfile_from_doc(DOC.read_text(encoding="utf-8"), origin))
    name = f"velometer-dryrun-{port}"
    log = work / "server.log"
    with log.open("wb") as out:
        proc = subprocess.Popen(
            caddy_command(site, caddyfile, name), stdout=out, stderr=subprocess.STDOUT
        )
    try:
        try:
            wait_http(origin + "/", 120)
        except DryRunError as e:
            raise DryRunError(f"caddy: {e}\n{_log_tail(log)}") from None
        yield origin
    finally:
        subprocess.run(["docker", "stop", "-t", "5", name], capture_output=True)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        shutil.rmtree(work, ignore_errors=True)


@contextlib.contextmanager
def wrangler_server(site: Path):
    """`wrangler pages dev` in its own process group; yields the origin, stops the group."""
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    work = Path(tempfile.mkdtemp(prefix="deploy-dryrun-wrangler-"))  # wrangler's .wrangler/
    env = {**os.environ, "WRANGLER_SEND_METRICS": "false", "CI": "1"}
    log = work / "server.log"
    with log.open("wb") as out:
        proc = subprocess.Popen(
            wrangler_command(site, port, free_port()),
            cwd=work,
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        try:
            wait_http(origin + "/", 300)
        except DryRunError as e:
            raise DryRunError(f"wrangler: {e}\n{_log_tail(log)}") from None
        yield origin
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--site", type=Path, required=True, help="a finished export (--base /)")
    ap.add_argument("--server", choices=("caddy", "wrangler"), required=True)
    ap.add_argument(
        "--keep-running",
        action="store_true",
        help="after the probes, keep serving until Ctrl-C (for render_pass.py --url)",
    )
    a = ap.parse_args(argv)
    site = a.site.resolve()
    try:
        base = json.loads((site / "build.json").read_text(encoding="utf-8"))["base"]
    except (OSError, ValueError, KeyError):
        ap.error(f"{site} has no readable build.json; export the static edition first")
    if base != "/":
        ap.error(f"both routes serve an export made with --base /; this one has base {base}")
    if not (site / "_headers").is_file():
        ap.error(f"{site} has no _headers file")
    server = caddy_server(site) if a.server == "caddy" else wrangler_server(site)
    try:
        with server as origin:
            print(f"{a.server} serving {site} at {origin}{base}", flush=True)
            n, problems = run_probes(origin, site, base, require_gzip=a.server == "caddy")
            for p in problems:
                print(f"  problem: {p}")
            print(f"{n} checks, {len(problems)} problems", flush=True)
            if a.keep_running:
                print(f"serving {origin}{base} until Ctrl-C", flush=True)
                with contextlib.suppress(KeyboardInterrupt):
                    while True:
                        time.sleep(3600)
    except DryRunError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
