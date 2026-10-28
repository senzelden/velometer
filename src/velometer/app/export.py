"""`velometer app export`: the static edition (M9 spec decisions 1, 2, 4, 5, 8, 9).

The app renders every exported URL in-process (Starlette TestClient: no server, no network) and
the response bodies are written to files; there is no second renderer. The URL list comes from
the data (`export_urls`), a URL maps to a file by `url_to_path`, `static/` is copied, `404.html`
is the app's 404 response and `build.json` stamps the build. `scan_references` then proves every
reference in the written HTML, CSS and JS resolves (an export with one that does not fails,
listing each). The site is written to a staging directory next to `out` (never inside it) and
moved into place only when complete, so a failed export leaves `out` as it was. A dangerous
`out` (`/`, $HOME, a repo root, a directory holding an input, a symlink) and a base that is not
a plain path are refused before anything happens. The database is opened read-only, as the app
opens it.

M14: `write_gz` adds a `.gz` sibling to each large text file, `_headers` carries the security and
cache headers, and a file of 25 MiB or more (the Cloudflare Pages limit) fails the export.
"""

import gzip
import json
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI

from velometer.app.main import CSP, HERE, TABS, TILES_PATH, create_app, csp_meta
from velometer.app.urls import (
    DATA_ROOTS,
    LEGACY_DE,
    make_data_u,
    make_u,
    normalise_base,
    with_lang,
)
from velometer.config import ConfigError, load_site
from velometer.db import SchemaError
from velometer.reconcile import short_commit
from velometer.report.data import ReportData, open_readonly
from velometer.run import _git, git_commit

# Starlette's notice that its TestClient will move from httpx to httpx2 is for test suites; the
# export is a command, and the line would only be noise on every run. `httpx2` is a dev
# dependency only (M13), so an install without the dev group still takes this fallback.
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")
    from fastapi.testclient import TestClient

# The app answers loopback Host headers only (TrustedHostMiddleware), so the export asks as a
# browser on the served address does.
BASE_URL = "http://127.0.0.1:8000"
# The pages every export has; per-city pages, CSVs and maps are added from the data.
PAGES = [
    "/", "/cities", "/compare", "/stories", "/differences", "/organisations", "/sources",
    "/plans", "/methodology", "/methodology/de", "/data/series.json", "/data/search.json",
    "/data/all.csv",
]  # fmt: skip
# M12: every HTML page has a German twin under /de/ (the legacy /methodology/de is one already);
# the search index is the one data file written per language
GERMAN_DATA = ["/de/data/search.json"]
NOT_FOUND_PROBE = "/404"  # no route: the app's 404 response, written as 404.html
BUILD_FILE = "build.json"
BUILD_KEYS = (
    "commit", "commit_full", "dirty", "classifier_versions", "osm_timestamps", "base", "built_at"
)  # fmt: skip
STATIC_EXCLUDED = PurePosixPath("js/tests")  # the node tests of the JS modules, not the site
# The staging and set-aside directories, siblings of `out` (never inside it); .gitignore ignores
# the prefix, so an export killed mid-way leaves no untracked directory in the repo.
STAGING_PREFIX = ".velometer-staging-"
# The reference scan (decision 5). A *loaded* reference (src, srcset, <link href>, a form action,
# object data, poster, any other attribute holding a URL, CSS url() / @import in a file, a <style>
# or a style attribute, a script's import / url("…") / fetch("…") / new URL("…") and any other
# URL-shaped string literal, a JSON config string) must resolve to a file in the export, or be
# `data:`, or name the one file served beside the export (SERVED_BESIDE); no external host is
# loaded (LOADED_HOSTS is empty since M16, as the CSP allows none). A *link* (<a>/<area>
# href, a string under a JSON config's "links" key, which scripts put in an <a>) is followed by
# the reader, not loaded by the page: it may also point at any http(s) or mailto address (the
# attribution and source links). The scan fails closed: an inline <script> (the CSP runs none,
# and its code is not parsed) is reported as it is.
LOADED_HOSTS: frozenset[str] = frozenset()
# Paths under the base that pages load but the export never holds: the basemap extract (900 MB,
# uploaded apart from the releases). Pages work without it (their maps have no background).
SERVED_BESIDE = frozenset({TILES_PATH})
LINK_SCHEMES = frozenset({"http", "https", "mailto"})
LINK_TAGS = frozenset({"a", "area"})
# attributes whose value is a URL whatever it looks like; any other attribute is a reference when
# its value looks like one (URL_SHAPED)
URL_ATTRS = frozenset({"href", "src", "action", "data", "poster", "formaction", "cite"})
JSON_SCRIPT_TYPES = frozenset({"application/json", "application/ld+json"})
SCANNED_SUFFIXES = (".html", ".css", ".js")  # so `.gz` copies and `_headers` are never scanned
# M14: the compressed siblings, the host headers file and the per-file size limit
GZ_TYPES = (".html", ".css", ".js", ".json", ".geojson", ".csv", ".svg")
GZ_MIN_BYTES = 1024
MAX_FILE_BYTES = 26_214_400  # 25 MiB: Cloudflare Pages refuses a file of this size or more
HEADERS_FILE = "_headers"
# The images the vendored leaflet.css names that static/vendor/VERSIONS records as not vendored:
# the maps use neither the layers control nor the default marker icon (a test keeps that true).
UNVENDORED = frozenset(
    ("static/vendor/leaflet.css", ref)
    for ref in ("images/layers.png", "images/layers-2x.png", "images/marker-icon.png")
)
# XML namespace names in scripts (document.createElementNS): identifiers, never fetched
NAMESPACES = frozenset({"http://www.w3.org/2000/svg", "http://www.w3.org/1999/xhtml"})
# protomaps-leaflet parses its `url` option with `new URL(url, "http://example.com")` to read the
# path's suffix: a base for parsing, never fetched
NOT_FETCHED = frozenset({("static/vendor/protomaps-leaflet.js", "http://example.com")})
URL_SHAPED = re.compile(r"^\s*(/|[A-Za-z][A-Za-z0-9+.-]*://|javascript:|data:)", re.I)
CSS_URL = re.compile(r"""url\(\s*(["']?)([^"')]*?)\1\s*\)""", re.I)
CSS_IMPORT = re.compile(r"""@import\s+(["'])([^"']*)\1""", re.I)
CSS_QUOTED_URL = re.compile(r"""(["'])([A-Za-z][A-Za-z0-9+.-]*://[^"']*)\1""")
JS_IMPORT = re.compile(r"""\b(?:import|from)\s*\(?\s*(["'])([^"'\n]+)\1""")
# a string literal that is a URL: a root-relative path (`/` and a name character: not "/", "//"
# or "/${…}" string pieces), protocol-relative (`//` and a host) or with a scheme; group 1 is
# set when it is the argument of url()
JS_URL_LITERAL = re.compile(
    r"""(\burl\s*\(\s*)?(["'`])((?:/[A-Za-z0-9_.~-]|//[A-Za-z0-9]|[A-Za-z][A-Za-z0-9+.-]*://)[^"'`\s]*)\2"""
)
# a literal passed to fetch() / new URL() that JS_URL_LITERAL does not see (a relative path)
JS_CALL_LITERAL = re.compile(r"""\b(?:fetch|new\s+URL)\s*\(\s*(["'`])([^"'`\n]*)\1""")
# whole-line comments: `// …` lines and `/* … */` blocks that open a line (the JSDoc kind)
JS_COMMENTS = re.compile(r"^[ \t]*//[^\n]*$|^[ \t]*/\*.*?\*/", re.M | re.S)
SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")
# a base path is `/`-separated segments of these characters (no `..`, `//`, scheme, query, ...)
BASE_SEGMENT = re.compile(r"[A-Za-z0-9._~-]+")


class ExportError(Exception):
    """An export that cannot complete; the message names what and why."""


@dataclass(frozen=True, order=True)
class Unresolved:
    """A reference in an exported file (relative path) that resolves to no exported file, or a
    loaded resource on another host."""

    file: str
    ref: str


@dataclass(frozen=True)
class ExportResult:
    files: int
    bytes: int
    build: dict


def url_to_path(url: str, content_type: str) -> PurePosixPath:
    """The file (relative to the export root) a URL's response is written to: an HTML page
    `/x/y` to `x/y/index.html` (`/` to `index.html`), anything else to its URL path. A URL with
    a query or fragment, a relative or `..` path, or a non-HTML `/` has no file: ValueError."""
    if "?" in url or "#" in url:
        raise ValueError(f"a URL with a query or fragment has no file: {url!r}")
    if not url.startswith("/"):
        raise ValueError(f"not an absolute path: {url!r}")
    parts = [p for p in url.split("/") if p]
    if any(p in (".", "..") for p in parts):
        raise ValueError(f"a dot segment has no file: {url!r}")
    if content_type.split(";")[0].strip().lower() == "text/html":
        return PurePosixPath(*parts, "index.html")
    if not parts or url.endswith("/"):
        raise ValueError(f"a non-HTML response needs a file name: {url!r}")
    return PurePosixPath(*parts)


def validate_base(base: str) -> None:
    """Refuse a `--base` that is not a plain path: `..`/`.` segments, `//`, a scheme, a query, a
    fragment or any character outside `A-Z a-z 0-9 . _ ~ -` in a segment."""
    if "//" in base:
        raise ExportError(f"--base {base!r}: '//' is not a path (a scheme or an empty segment)")
    for segment in base.strip("/").split("/"):
        if not segment and base.strip("/") == "":
            return  # `/` or ""
        if segment in (".", ".."):
            raise ExportError(f"--base {base!r}: a '{segment}' segment is not allowed")
        if not BASE_SEGMENT.fullmatch(segment):
            raise ExportError(
                f"--base {base!r}: segment {segment!r} may hold only letters, digits and . _ ~ - "
                "(no scheme, query, fragment or space)"
            )


def _git_toplevel(cwd: Path) -> Path | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True
        )
    except OSError:
        return None
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else None


def _refuse_dangerous_out(out: Path, inputs: list[Path]) -> None:
    """Refuse an `out` that is `/`, $HOME, a git toplevel (of the cwd or of velometer's source),
    or a directory that holds an input (DB, config, maps, docs, content, plans data, the app's
    own static files), or a symlink: `--clean` would delete it."""
    if out.is_symlink():
        raise ExportError(f"refusing --out {out}: it is a symlink; name the directory itself")
    real = out.resolve()
    if real == Path(real.anchor):
        raise ExportError(f"refusing --out {out}: it is the filesystem root")
    if real == Path.home().resolve():
        raise ExportError(f"refusing --out {out}: it is the home directory")
    for where in (Path.cwd(), HERE):
        top = _git_toplevel(where)
        if top is not None and real == top:
            raise ExportError(f"refusing --out {out}: it is the root of the git repository {top}")
    for path in [*inputs, HERE]:
        if Path(path).resolve().is_relative_to(real):
            raise ExportError(f"refusing --out {out}: it contains the input {path}")


def _map_refs(html: str, base: str) -> set[str]:
    """The `/maps/…` routes a page references (written `<base>maps/…`, in an attribute or in a
    JSON config): the base taken off."""
    pattern = r"(?<=[\"'(=\s])" + re.escape(base) + r"maps/[A-Za-z0-9_.-]+"
    return {"/" + m.removeprefix(base) for m in re.findall(pattern, html)}


def export_urls(data: ReportData, app: FastAPI, rendered: dict | None = None) -> list[str]:
    """Every URL the static edition has (decision 4): the fixed pages; per trusted city its page,
    each tab and plan page and CSV the app serves for it (a 404 is a page the city does not
    have, left out), its panel; every map an exported page references (a German page with
    maps is read too: it links the German tier map images). A per-city URL answered
    with anything but 200 or 404 is kept, so the export fails on it by name. Each response
    of a URL kept goes into `rendered` (URL -> response) when given, so `_write_site` need not
    render it again."""
    base = app.state.base_path
    probed = []
    for city in data.cities():
        probed += [f"/city/{city.id}{suffix}" for _k, suffix in TABS]
        probed += [f"/city/{city.id}/panel", f"/plans/{city.id}"]
        probed += [f"/data/{city.id}.csv", f"/data/{city.id}_subareas.csv"]
    found = list(PAGES)
    pages: list[str] = []  # the HTML URLs, each given its German twin
    maps: set[str] = set()
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        for url in PAGES + probed:
            r = client.get(url, follow_redirects=False)
            if r.status_code == 404 and url not in PAGES:
                continue
            if rendered is not None:
                rendered[url] = r
            if url not in PAGES:
                found.append(url)
            if r.headers.get("content-type", "").startswith("text/html") and url not in LEGACY_DE:
                pages.append(url)
            if r.status_code == 200 and r.headers["content-type"].startswith("text/html"):
                refs = _map_refs(r.text, base)
                if refs:  # its German twin links its own image (`<city>_<kind>.de.png`)
                    twin = with_lang(url, "de")
                    german = client.get(twin, follow_redirects=False)
                    if rendered is not None:
                        rendered[twin] = german
                    refs |= _map_refs(german.text, base)
                maps |= refs
    return found + [with_lang(url, "de") for url in pages] + GERMAN_DATA + sorted(maps)


def public_commit() -> str:
    """The checkout's commit as `git_commit` gives it ("<sha>", "<sha>-dirty", "unknown"), but
    dirty only for changes to tracked files: an untracked file is not in what the pages link
    (M16, R42), and stub files a sandbox shows must not block a public export."""
    try:
        sha = _git("rev-parse", "HEAD").strip()
        dirty = bool(_git("status", "--porcelain", "--untracked-files=no").strip())
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


def build_stamp(
    data: ReportData,
    base: str,
    public: bool = False,
    site: dict | None = None,
    raw: str | None = None,
) -> dict:
    """`build.json` (decision 8): the git commit (local `git rev-parse`, no network), whether the
    tree was dirty, the classifier versions and per city the OSM snapshot timestamps of the
    exported runs (the rows of /data/all.csv), the base path and the build time (UTC). A public
    export also records `site`, the values its footer and repo links use
    (`SiteConfig.public_values`), which `deploy-check` checks the pages against. `raw` is the
    commit a public export already checked (read once), else `git_commit()` is asked."""
    if raw is None:
        raw = git_commit()  # "<sha>", "<sha>-dirty" or "unknown"
    stamps: dict[str, set[str]] = {}
    versions: set[str] = set()
    for row in data.csv_rows():
        versions.add(row["classifier_version"])
        stamps.setdefault(row["city_id"], set()).add(row["osm_timestamp"])
    return {
        "commit": short_commit(raw),
        "commit_full": raw.removesuffix("-dirty"),
        "dirty": raw.endswith("-dirty"),
        "classifier_versions": sorted(versions),
        "osm_timestamps": {city: sorted(ts) for city, ts in stamps.items()},
        "base": base,
        "public": public,
        **({"site": site} if public and site is not None else {}),
        "built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _check_out(out: Path, clean: bool) -> None:
    """Refuse a non-empty `out` without `clean`, and with it any directory that holds no
    `build.json` of a previous export (decision 9). Nothing is written or deleted here."""
    if out.is_symlink():
        raise ExportError(f"refusing --out {out}: it is a symlink; name the directory itself")
    if out.exists() and not out.is_dir():
        raise ExportError(f"{out} exists and is not a directory")
    if not out.exists() or not any(out.iterdir()):
        return
    if not clean:
        raise ExportError(f"{out} is not empty; pass --clean to replace a previous export")
    try:
        previous = json.loads((out / BUILD_FILE).read_text())
    except (OSError, ValueError) as e:
        raise ExportError(
            f"--clean replaces only a previous export: {out / BUILD_FILE} is missing or not one "
            f"({e})"
        ) from e
    if not isinstance(previous, dict) or not set(BUILD_KEYS) <= set(previous):
        raise ExportError(
            f"--clean replaces only a previous export: {out / BUILD_FILE} is not an export's"
        )


def _ignore_tests(static: Path):
    def ignore(directory: str, names: list[str]) -> set[str]:
        rel = PurePosixPath(Path(directory).relative_to(static).as_posix())
        return {n for n in names if rel / n == STATIC_EXCLUDED}

    return ignore


def _write_site(
    site: Path, app: FastAPI, urls: list[str], build: dict, rendered: dict | None = None
) -> None:
    """Every URL's response to its file, `static/`, `404.html` and `build.json` into `site`; a
    URL's response is taken from `rendered` when `export_urls` already had it."""
    written: dict[PurePosixPath, str] = {}
    rendered = {} if rendered is None else rendered
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        for url in urls:
            r = rendered.pop(url, None)
            if r is None:
                r = client.get(url, follow_redirects=False)
            if r.status_code != 200:
                raise ExportError(f"{url}: HTTP {r.status_code}")
            rel = url_to_path(url, r.headers["content-type"])
            if rel in written:
                raise ExportError(f"{url} and {written[rel]} both write {rel}")
            written[rel] = url
            path = site / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        missing = client.get(NOT_FOUND_PROBE, follow_redirects=False)
        if missing.status_code != 404:
            raise ExportError(f"{NOT_FOUND_PROBE}: HTTP {missing.status_code}, expected 404")
        (site / "404.html").write_bytes(missing.content)
    static = HERE / "static"
    shutil.copytree(static, site / "static", ignore=_ignore_tests(static))
    (site / BUILD_FILE).write_text(json.dumps(build, indent=2, sort_keys=True) + "\n")


def write_gz(site: Path) -> int:
    """A `<name>.gz` beside every file of a `GZ_TYPES` suffix and `GZ_MIN_BYTES` or more, byte
    for byte reproducible (mtime 0, no stored file name). Returns the number written."""
    count = 0
    for path in sorted(p for p in site.rglob("*") if p.is_file()):
        if path.suffix not in GZ_TYPES or path.stat().st_size < GZ_MIN_BYTES:
            continue
        with (
            path.with_name(path.name + ".gz").open("wb") as raw,
            gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw, mtime=0) as z,
        ):
            z.write(path.read_bytes())
        count += 1
    return count


def headers_text(base: str, csp: str) -> str:
    """The `_headers` file (Cloudflare Pages / Netlify format) for a site served under `base`:
    `csp` is the pages' meta policy, to which the header adds `frame-ancestors 'none'`."""
    return (
        f"{base}*\n"
        f"  Content-Security-Policy: {csp}; frame-ancestors 'none'\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Cache-Control: public, max-age=3600\n"
    )


def oversized(site: Path, limit: int = MAX_FILE_BYTES) -> list[str]:
    """The files (relative paths, sorted) of `limit` bytes or more."""
    return sorted(
        p.relative_to(site).as_posix()
        for p in site.rglob("*")
        if p.is_file() and p.stat().st_size >= limit
    )


class _HtmlRefs(HTMLParser):
    """A page's references as (value, loaded?), and what it cannot vouch for (`unsupported`): see
    the rule at LOADED_HOSTS."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, bool]] = []
        self.unsupported: list[str] = []
        self._block: tuple[str, str] | None = None  # ("json" | "style" | "script", text so far)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for name, value in attrs:
            if value is None:
                continue
            if name == "srcset":
                self.refs += [(c.split()[0], True) for c in value.split(",") if c.strip()]
            elif name == "style":
                self.refs += _css_refs(value)
            elif name in URL_ATTRS or URL_SHAPED.match(value):
                self.refs.append((value, not (name == "href" and tag in LINK_TAGS)))
        if tag == "meta" and a.get("name") == "velometer-base":
            self.refs.append((a.get("content") or "", True))
        if tag == "style":
            self._block = ("style", "")
        elif tag == "script":
            kind = "json" if (a.get("type") or "").lower() in JSON_SCRIPT_TYPES else "script"
            self._block = (kind, "")

    def handle_data(self, data):
        if self._block is not None:
            self._block = (self._block[0], self._block[1] + data)

    def handle_endtag(self, tag):
        if self._block is None or tag not in ("style", "script"):
            return
        kind, text = self._block
        self._block = None
        if kind == "json":
            self.refs += list(_json_refs(json.loads(text), link=False))
        elif kind == "style":
            self.refs += _css_refs(text)
        elif text.strip():
            snippet = " ".join(text.split())[:80]
            self.unsupported.append(f"inline <script> (not parsed; the CSP runs none): {snippet}")


def _json_refs(value, link: bool):
    """A JSON config's strings that are URLs: root-relative or http(s); under "links", links."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _json_refs(v, link or k == "links")
    elif isinstance(value, list):
        for v in value:
            yield from _json_refs(v, link)
    elif isinstance(value, str) and URL_SHAPED.match(value):
        yield value, not link


def _css_refs(text: str) -> list[tuple[str, bool]]:
    """Every url(…), @import "…" and quoted absolute URL of a stylesheet, all loaded."""
    found = [m.group(2) for m in CSS_URL.finditer(text)]
    found += [m.group(2) for m in CSS_IMPORT.finditer(text)]
    found += [m.group(2) for m in CSS_QUOTED_URL.finditer(text)]
    return [(ref, True) for ref in found]


def _js_refs(text: str, base: str) -> list[tuple[str, bool]]:
    """A script's references, loaded unless noted: import specifiers; every URL-shaped string
    literal (root-relative, `//host` or with a scheme; an argument of url() as url() resolves it
    under `base`; one written as an `href="…"` in markup is a link); the literal of a fetch() or
    new URL(). Whole-line comments are skipped. A built URL (`${…}`) passed to url() carries the
    base by construction and is not resolved; anywhere else it is checked as written. XML
    namespace names are not references.

    What it cannot do: resolve a URL a script builds at run time (`url(`/city/${id}/panel`)`,
    the Compare panel and city links). Those name a page per city, and the scan cannot know
    which ids a script will use. They rely on `export_urls` writing every city's page and panel
    instead, which `test_export_urls_are_what_the_app_serves` asserts for every city."""
    page_u, data_u = make_u(base), make_data_u(base)

    def u(path: str) -> str:  # url() of an English page: data paths shared, no prefix
        return data_u(path) if path.startswith(DATA_ROOTS) else page_u(path)

    code = JS_COMMENTS.sub("", text)
    refs = [(m.group(2), True) for m in JS_IMPORT.finditer(code)]
    for m in JS_URL_LITERAL.finditer(code):
        via_url, literal = m.group(1), m.group(3)
        if literal in NAMESPACES:
            continue
        if via_url:
            if "${" not in literal:
                refs.append((u(literal), True))
        else:  # the href of markup a script writes (`'<a href="…"'`) is a link
            refs.append((literal, not code.endswith("href=", 0, m.start())))
    refs += [(m.group(2), True) for m in JS_CALL_LITERAL.finditer(code)]
    return refs


def _resolves(out: Path, rel: str) -> bool:
    """`rel` (relative to `out`, no query) is an exported file or a page directory."""
    rel = posixpath.normpath(rel) if rel else "."
    if rel == ".." or rel.startswith("../") or rel.startswith("/"):
        return False
    target = out / rel
    return target.is_file() or (target / "index.html").is_file()


def _ok(ref: str, loaded: bool, file: str, out: Path, base: str) -> bool:
    if ref.startswith("#"):
        return True
    scheme = SCHEME.match(ref)
    if scheme or ref.startswith("//"):
        name = scheme.group(1).lower() if scheme else ""
        if name == "data":
            return loaded
        if not loaded and name in LINK_SCHEMES:
            return True
        return name == "https" and urlsplit(ref).hostname in LOADED_HOSTS
    path = unquote(urlsplit(ref).path)
    if path.startswith("/"):
        if not path.startswith(base):
            return False
        rel = path.removeprefix(base)
        return rel in SERVED_BESIDE or _resolves(out, rel)
    if file.endswith(".html") or not path:
        return False  # relative in a page: it depends on the URL the page is served at
    return _resolves(out, posixpath.join(posixpath.dirname(file), path))


def scan_references(out: Path, base: str) -> list[Unresolved]:
    """Every reference of every exported HTML, CSS and JS file under `out` that does not resolve
    (the rule at LOADED_HOSTS): an internal one must carry `base` and name an exported file or
    page directory (a relative one in CSS/JS resolves against its file) or a path served beside
    the export; nothing external may be loaded; a link may also leave the site. Sorted, without
    duplicates."""
    base = normalise_base(base)
    found: set[Unresolved] = set()
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        file = path.relative_to(out).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".html":
            parser = _HtmlRefs()
            parser.feed(text)
            parser.close()
            refs = parser.refs
            found |= {Unresolved(file, what) for what in parser.unsupported}
        elif path.suffix == ".css":
            refs = _css_refs(text)
        else:
            refs = _js_refs(text, base)
        for ref, loaded in refs:
            if (file, ref) in UNVENDORED or (file, ref) in NOT_FETCHED:
                continue
            if not _ok(ref.strip(), loaded, file, out, base):
                found.add(Unresolved(file, ref))
    return sorted(found)


def _install(site: Path, out: Path, clean: bool) -> None:
    """The complete `site` in place of `out`'s contents. The guard is checked again first (`out`
    may have changed during the render); `out`'s old entries are set aside in a sibling
    directory and deleted only once the new ones are in. Anything that stops the swap, an
    interrupt (Ctrl-C) included, puts them back and is raised again; when putting them back
    fails too, the ExportError names the directory that still holds them."""
    _check_out(out, clean)
    created = not out.exists()
    old: Path | None = None
    moved_out: list[str] = []
    moved_in: list[str] = []
    try:
        out.mkdir(exist_ok=True)
        old = Path(tempfile.mkdtemp(prefix=f"{STAGING_PREFIX}{out.name}-old-", dir=out.parent))
        # each name is noted before its move: an interrupt between the two is undone too
        for entry in list(out.iterdir()):
            moved_out.append(entry.name)
            entry.rename(old / entry.name)
        for entry in list(site.iterdir()):
            moved_in.append(entry.name)
            entry.rename(out / entry.name)
    except BaseException as failure:
        _roll_back(site, out, old, moved_in, moved_out, created, failure)
        raise
    shutil.rmtree(old)
    site.rmdir()


def _roll_back(
    site: Path,
    out: Path,
    old: Path | None,
    moved_in: list[str],
    moved_out: list[str],
    created: bool,
    failure: BaseException,
) -> None:
    """Undo a partial swap: the new entries back into `site`, the old ones back into `out`, the
    set-aside directory and a newly made `out` removed. A noted name whose move had not happened
    yet is skipped. When that fails, an interrupt included, ExportError naming the set-aside
    directory while it still exists (the previous export is in it)."""

    def back(src: Path, dst: Path) -> None:
        if os.path.lexists(src):
            src.rename(dst)

    try:
        for name in reversed(moved_in):
            back(out / name, site / name)
        if old is not None:
            for name in reversed(moved_out):
                back(old / name, out / name)
            old.rmdir()
        if created and out.exists():
            out.rmdir()
    except BaseException as e:
        kept = old is not None and old.exists()
        where = f"; the previous export's entries are in {old}" if kept else ""
        raise ExportError(
            f"export to {out} failed ({failure!r}) and putting {out} back failed too ({e}){where}"
        ) from failure


def run_export(
    out: Path,
    base: str,
    db: Path,
    config_dir: Path,
    maps: Path,
    docs: Path,
    content_dir: Path,
    plans_data_dir: Path,
    clean: bool,
    public: bool = False,
) -> ExportResult:
    """Write the static edition of the app built with `base` to `out` (module docstring)."""
    try:
        return _run_export(
            out, base, db, config_dir, maps, docs, content_dir, plans_data_dir, clean, public
        )
    except OSError as e:
        raise ExportError(f"export to {out} failed: {e}") from e


def figures_drift(conn, config_dir: Path) -> list[str]:
    """The curated external figures where the database differs from the config's
    `external/figures.csv` (Task 9: a CSV edit without `external load` sent the German figures
    page back to English)."""
    from velometer.sources.external import curated_drift

    return curated_drift(conn, config_dir / "external" / "figures.csv")


def _run_export(
    out: Path,
    base: str,
    db: Path,
    config_dir: Path,
    maps: Path,
    docs: Path,
    content_dir: Path,
    plans_data_dir: Path,
    clean: bool,
    public: bool = False,
) -> ExportResult:
    validate_base(base)
    site_values, raw = None, None
    if public:
        try:
            site_cfg = load_site(config_dir)
        except ConfigError as e:
            raise ExportError(str(e)) from e
        if not site_cfg.complete:
            raise ExportError(
                "--public needs config/site.yaml to set: " + ", ".join(site_cfg.missing())
            )
        site_values = site_cfg.public_values()
        # the pages link repo files at the export's commit (M16, R42): a commit that lacks the
        # tree's changes, or no commit at all, would link the wrong text
        raw = public_commit()
        if raw == "unknown" or raw.endswith("-dirty"):
            raise ExportError(
                "--public needs a clean git checkout (the pages link the repository at the "
                f"export's commit); git says {raw!r}: commit or stash the changes first"
            )
    # absolute without following symlinks: `.` gets a real name, so staging is its sibling
    out = Path(os.path.abspath(out))
    _refuse_dangerous_out(out, [db, config_dir, maps, docs, content_dir, plans_data_dir])
    _check_out(out, clean)
    try:
        conn = open_readonly(Path(db))
    except (FileNotFoundError, SchemaError) as e:
        raise ExportError(str(e)) from e
    try:
        if public:
            drift = figures_drift(conn, Path(config_dir))
            if drift:
                from velometer.sources.external import LOAD_COMMAND

                lines = "\n".join(f"  {d}" for d in drift)
                raise ExportError(
                    f"--public: the database's external figures differ from "
                    f"{Path(config_dir) / 'external' / 'figures.csv'} in {len(drift)} row(s):\n"
                    f"{lines}\nreload them with `{LOAD_COMMAND}` (writes velometer.sqlite)"
                )
        data = ReportData(conn, config_dir)
        build = build_stamp(data, normalise_base(base), public, site_values, raw)
        app = create_app(
            db, config_dir, maps, docs, content_dir=content_dir, plans_data_dir=plans_data_dir,
            base_path=base,
            static_edition={"commit": build["commit"], "commit_full": build["commit_full"]},
        )  # fmt: skip
        rendered: dict = {}  # each page is rendered once: listing it and writing it
        urls = export_urls(data, app, rendered)
    finally:
        conn.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    site = Path(tempfile.mkdtemp(prefix=f"{STAGING_PREFIX}{out.name}-", dir=out.parent))
    try:
        _write_site(site, app, urls, build, rendered)
        (site / HEADERS_FILE).write_text(headers_text(build["base"], csp_meta(CSP)))
        write_gz(site)
        big = oversized(site, MAX_FILE_BYTES)
        if big:
            lines = "\n".join(f"  {name}" for name in big)
            raise ExportError(
                f"{len(big)} file(s) of {MAX_FILE_BYTES} bytes or more (the host's limit):\n{lines}"
            )
        unresolved = scan_references(site, build["base"])
        if unresolved:
            lines = "\n".join(f"  {x.file}: {x.ref}" for x in unresolved)
            raise ExportError(f"{len(unresolved)} reference(s) do not resolve:\n{lines}")
        _install(site, out, clean)
    except BaseException:
        shutil.rmtree(site, ignore_errors=True)
        raise
    files = [p for p in out.rglob("*") if p.is_file()]
    return ExportResult(len(files), sum(p.stat().st_size for p in files), build)
