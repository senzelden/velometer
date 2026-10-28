"""The deploy dry run (M14): verify a finished static export and upload nothing."""

import gzip
import html
import json
import re
import zlib
from pathlib import Path

from markupsafe import escape

from velometer.app import export
from velometer.app.repo_links import bare_repo_paths
from velometer.app.urls import normalise_base

_META_CSP = re.compile(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)"')


def _build(out: Path) -> tuple[dict | None, str | None]:
    """build.json as a dict, or the problem with it."""
    path = out / export.BUILD_FILE
    if not path.is_file():
        return None, f"{export.BUILD_FILE} is missing (not an export, or not a finished one)"
    try:
        build = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return None, f"{export.BUILD_FILE} is not valid JSON: {e}"
    if not isinstance(build, dict) or not isinstance(build.get("base"), str):
        return None, f"{export.BUILD_FILE} has no base"
    return build, None


def _meta_csp(out: Path) -> str | None:
    index = out / "index.html"
    if not index.is_file():
        return None
    m = _META_CSP.search(index.read_text(encoding="utf-8"))
    return html.unescape(m.group(1)) if m else None


def _headers_problems(out: Path, base: str) -> list[str]:
    path = out / export.HEADERS_FILE
    if not path.is_file():
        return [f"{export.HEADERS_FILE} is missing"]
    meta = _meta_csp(out)
    if meta is None:
        return ["index.html has no Content-Security-Policy meta tag to compare _headers with"]
    text = path.read_text(encoding="utf-8")
    want = f"{meta}; frame-ancestors 'none'"
    lines = [ln.strip() for ln in text.splitlines()]
    csp = [ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("Content-Security-Policy:")]
    if csp != [want]:
        return [
            f"{export.HEADERS_FILE} Content-Security-Policy differs from the pages' meta policy "
            f"plus frame-ancestors 'none': have {csp}, want [{want!r}]"
        ]
    if text != export.headers_text(base, meta):
        return [f"{export.HEADERS_FILE} differs from what the export writes (re-export)"]
    return []


def _gz_problems(out: Path) -> list[str]:
    problems = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = path.relative_to(out).as_posix()
        if path.suffix == ".gz":
            origin = path.with_name(path.name.removesuffix(".gz"))
            if not origin.is_file():
                problems.append(f"stray {rel}: its file {origin.name} does not exist")
            continue
        if path.suffix not in export.GZ_TYPES or path.stat().st_size < export.GZ_MIN_BYTES:
            continue
        gz = path.with_name(path.name + ".gz")
        if not gz.is_file():
            problems.append(f"{rel}.gz is missing (the file is {path.stat().st_size} bytes)")
            continue
        try:
            same = gzip.decompress(gz.read_bytes()) == path.read_bytes()
        except (OSError, EOFError, zlib.error):
            problems.append(f"{rel}.gz is not a valid gzip file")
            continue
        if not same:
            problems.append(f"{rel}.gz differs from {rel} (edited since the export)")
    return problems


SITE_VALUES = (
    "datalab_name", "datalab_url", "impressum_url", "privacy_url", "repo_url", "repo_file_url",
)  # fmt: skip
FOOTER_LINKS = ("datalab_url", "impressum_url", "privacy_url")


def _bare_code_problems(out: Path) -> list[str]:
    """Every page that prints a repo path (`<code>docs/…</code>`, …) outside a link: a reader
    cannot open it (M16, R42; a public export links them to the repository)."""
    problems = []
    for page in sorted(out.rglob("*.html")):
        bare = bare_repo_paths(page.read_text(encoding="utf-8"))
        if bare:
            shown = ", ".join(bare[:3]) + (f" and {len(bare) - 3} more" if len(bare) > 3 else "")
            rel = page.relative_to(out).as_posix()
            problems.append(f"{rel}: {len(bare)} repo path(s) not linked to the repo: {shown}")
    return problems


_HREF = re.compile(r'href="([^"]*)"')


def _pinned_problems(out: Path, build: dict) -> list[str]:
    """Every page (and data JSON, where Compare's flag notes get their links) whose repo file
    link (an address starting as `repo_file_url` does before `{commit}`) does not carry
    `build.json` `commit_full`: a link to another commit than the export's (M16, R42)."""
    pattern, commit = build["site"]["repo_file_url"], build.get("commit_full")
    prefix = pattern.split("{commit}", 1)[0]
    if not isinstance(commit, str) or not commit or commit == "unknown":
        return [f"public export, but {export.BUILD_FILE} records no commit_full for its repo links"]
    in_json = re.compile('"(' + re.escape(prefix) + '[^"]*)"')
    problems = []
    pages = sorted([*out.rglob("*.html"), *(out / "data").rglob("*.json")])
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if page.suffix == ".json":
            hrefs = in_json.findall(text)
        else:
            hrefs = [html.unescape(h) for h in _HREF.findall(text)]
        wrong = [h for h in hrefs if h.startswith(prefix) and commit not in h]
        if wrong:
            rel = page.relative_to(out).as_posix()
            problems.append(
                f"{rel}: {len(wrong)} repo link(s) not at the export's commit {commit[:7]}: "
                + wrong[0]
            )
    return problems


def _public_problems(out: Path, build: dict) -> list[str]:
    """A public export's footer, judged from the export itself: build.json records the site
    values, and every page with the site's footer (the home page always) names the Datalab and
    links it, its Impressum and its privacy page; no page prints a repo path unlinked."""
    site = build.get("site")
    site = site if isinstance(site, dict) else {}
    missing = [k for k in SITE_VALUES if not isinstance(site.get(k), str) or not site[k]]
    if missing:
        return [f"public export, but {export.BUILD_FILE} records no: " + ", ".join(missing)]
    links = [f'href="{escape(site[k])}"' for k in FOOTER_LINKS]
    name = str(escape(site["datalab_name"]))
    footless = []
    for page in sorted(out.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(out).as_posix()
        if "<footer>" not in text and rel != "index.html":
            continue  # a fragment (a city's /panel), not a page with the site's footer
        footer = text.rpartition("<footer>")[2]
        if name not in footer or not all(link in footer for link in links):
            footless.append(rel)
    problems = []
    if footless:
        n = len(footless)
        shown = ", ".join(footless[:5]) + (f" and {n - 5} more" if n > 5 else "")
        problems.append(
            f"public export, but {n} page(s) lack the Datalab, Impressum or privacy "
            f"link of {export.BUILD_FILE} in the footer: {shown}"
        )
    return problems + _bare_code_problems(out) + _pinned_problems(out, build)


def deploy_problems(out: Path, base: str | None, public: bool = False) -> list[str]:
    """What stops `out` from being uploaded as it is; an empty list means ready. `base` defaults
    to the one in build.json. A public export is checked against its own build.json and footers,
    not today's site.yaml; `public` also refuses an export that is not public."""
    out = Path(out)
    if not out.is_dir():
        return [f"{out} is not a directory"]
    problems = []
    build, error = _build(out)
    if error:
        problems.append(error)
    stamped = build["base"] if build else None
    use = normalise_base(base) if base is not None else (stamped or "/")
    if build and stamped != use:
        problems.append(f"{export.BUILD_FILE} base {stamped!r} differs from base {use!r}")
    if not (out / "404.html").is_file():
        problems.append("404.html is missing")
    problems += _headers_problems(out, use)
    problems += _gz_problems(out)
    big = export.oversized(out, export.MAX_FILE_BYTES)
    problems += [
        f"{name} is {export.MAX_FILE_BYTES} bytes (25 MiB) or more: the host refuses it"
        for name in big
    ]
    problems += [
        f"unresolved reference in {u.file}: {u.ref}" for u in export.scan_references(out, use)
    ]
    if build and build.get("public") is True:
        problems += _public_problems(out, build)
    elif build and public:
        problems.append("not a public export (exported without --public): no Impressum")
    return problems


def site_stats(out: Path) -> tuple[int, int]:
    """(file count, total bytes) under `out`."""
    sizes = [p.stat().st_size for p in Path(out).rglob("*") if p.is_file()]
    return len(sizes), sum(sizes)
