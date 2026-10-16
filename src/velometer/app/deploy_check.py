"""The deploy dry run (M14): verify a finished static export and upload nothing."""

import gzip
import html
import json
import re
import zlib
from pathlib import Path

from velometer.app import export
from velometer.app.urls import normalise_base
from velometer.config import ConfigError, load_site

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


def deploy_problems(out: Path, base: str | None, config_dir: Path) -> list[str]:
    """What stops `out` from being uploaded as it is; an empty list means ready. `base` defaults
    to the one in build.json."""
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
        try:
            missing = load_site(config_dir).missing()
        except ConfigError as e:
            missing = [str(e)]
        if missing:
            problems.append("public export, but site.yaml has no: " + ", ".join(missing))
    return problems


def site_stats(out: Path) -> tuple[int, int]:
    """(file count, total bytes) under `out`."""
    sizes = [p.stat().st_size for p in Path(out).rglob("*") if p.is_file()]
    return len(sizes), sum(sizes)
