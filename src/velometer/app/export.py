"""`velometer app export`: the static edition (M9 spec decisions 1, 2, 4, 8, 9).

The app renders every exported URL in-process (Starlette TestClient: no server, no network) and
the response bodies are written to files; there is no second renderer. The URL list comes from
the data (`export_urls`), a URL maps to a file by `url_to_path`, `static/` is copied, `404.html`
is the app's 404 response and `build.json` stamps the build. The site is written to a staging
directory next to `out` (never inside it) and moved into place only when complete, so a failed
export leaves `out` as it was. A dangerous `out` (`/`, $HOME, a repo root, a directory holding
an input, a symlink) and a base that is not a plain path are refused before anything happens.
The database is opened read-only, as the app opens it.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from fastapi import FastAPI

from velometer.app.main import HERE, TABS, create_app
from velometer.app.urls import normalise_base
from velometer.db import SchemaError
from velometer.reconcile import short_commit
from velometer.report.data import ReportData, open_readonly
from velometer.run import git_commit

# Starlette's notice that its TestClient will move from httpx to httpx2 is for test suites; the
# export is a command, and the line would only be noise on every run.
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")
    from fastapi.testclient import TestClient

# The app answers loopback Host headers only (TrustedHostMiddleware), so the export asks as a
# browser on the served address does.
BASE_URL = "http://127.0.0.1:8000"
# The pages every export has; per-city pages, CSVs and maps are added from the data.
PAGES = [
    "/", "/cities", "/compare", "/stories", "/differences", "/organisations", "/plans",
    "/methodology", "/methodology/de", "/data/series.json", "/data/all.csv",
]  # fmt: skip
NOT_FOUND_PROBE = "/404"  # no route: the app's 404 response, written as 404.html
BUILD_FILE = "build.json"
BUILD_KEYS = (
    "commit", "commit_full", "dirty", "classifier_versions", "osm_timestamps", "base", "built_at"
)  # fmt: skip
STATIC_EXCLUDED = PurePosixPath("js/tests")  # the node tests of the JS modules, not the site
# The staging and set-aside directories, siblings of `out` (never inside it); .gitignore ignores
# the prefix, so an export killed mid-way leaves no untracked directory in the repo.
STAGING_PREFIX = ".velometer-staging-"
# a base path is `/`-separated segments of these characters (no `..`, `//`, scheme, query, ...)
BASE_SEGMENT = re.compile(r"^[A-Za-z0-9._~-]+$")


class ExportError(Exception):
    """An export that cannot complete; the message names what and why."""


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
        if not BASE_SEGMENT.match(segment):
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


def export_urls(data: ReportData, app: FastAPI) -> list[str]:
    """Every URL the static edition has (decision 4): the fixed pages; per trusted city its page,
    each tab and plan page and CSV the app serves for it (a 404 is a page the city does not
    have, left out), its panel; every map an exported page references. A per-city URL answered
    with anything but 200 or 404 is kept, so the export fails on it by name."""
    base = app.state.base_path
    probed = []
    for city in data.cities():
        probed += [f"/city/{city.id}{suffix}" for _k, _l, suffix in TABS]
        probed += [f"/city/{city.id}/panel", f"/plans/{city.id}"]
        probed += [f"/data/{city.id}.csv", f"/data/{city.id}_subareas.csv"]
    found = list(PAGES)
    maps: set[str] = set()
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        for url in PAGES + probed:
            r = client.get(url, follow_redirects=False)
            if r.status_code == 404 and url not in PAGES:
                continue
            if url not in PAGES:
                found.append(url)
            if r.status_code == 200 and r.headers["content-type"].startswith("text/html"):
                maps |= _map_refs(r.text, base)
    return found + sorted(maps)


def build_stamp(data: ReportData, base: str) -> dict:
    """`build.json` (decision 8): the git commit (local `git rev-parse`, no network), whether the
    tree was dirty, the classifier versions and per city the OSM snapshot timestamps of the
    exported runs (the rows of /data/all.csv), the base path and the build time (UTC)."""
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


def _write_site(site: Path, app: FastAPI, urls: list[str], build: dict) -> None:
    """Every URL's response to its file, `static/`, `404.html` and `build.json` into `site`."""
    written: dict[PurePosixPath, str] = {}
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as client:
        for url in urls:
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


def _install(site: Path, out: Path, clean: bool) -> None:
    """The complete `site` in place of `out`'s contents. The guard is checked again first (`out`
    may have changed during the render); `out`'s old entries are set aside in a sibling
    directory and deleted only once the new ones are in, else they are put back."""
    _check_out(out, clean)
    created = not out.exists()
    out.mkdir(exist_ok=True)
    old = Path(tempfile.mkdtemp(prefix=f"{STAGING_PREFIX}{out.name}-old-", dir=out.parent))
    moved_out: list[str] = []
    moved_in: list[str] = []
    try:
        for entry in list(out.iterdir()):
            entry.rename(old / entry.name)
            moved_out.append(entry.name)
        for entry in list(site.iterdir()):
            entry.rename(out / entry.name)
            moved_in.append(entry.name)
    except OSError:
        for name in moved_in:
            (out / name).rename(site / name)
        for name in moved_out:
            (old / name).rename(out / name)
        old.rmdir()
        if created:
            out.rmdir()
        raise
    shutil.rmtree(old)
    site.rmdir()


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
) -> ExportResult:
    """Write the static edition of the app built with `base` to `out` (module docstring)."""
    try:
        return _run_export(
            out, base, db, config_dir, maps, docs, content_dir, plans_data_dir, clean
        )
    except OSError as e:
        raise ExportError(f"export to {out} failed: {e}") from e


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
) -> ExportResult:
    validate_base(base)
    # absolute without following symlinks: `.` gets a real name, so staging is its sibling
    out = Path(os.path.abspath(out))
    _refuse_dangerous_out(out, [db, config_dir, maps, docs, content_dir, plans_data_dir])
    _check_out(out, clean)
    try:
        conn = open_readonly(Path(db))
    except (FileNotFoundError, SchemaError) as e:
        raise ExportError(str(e)) from e
    try:
        data = ReportData(conn, config_dir)
        build = build_stamp(data, normalise_base(base))
        app = create_app(
            db, config_dir, maps, docs, content_dir=content_dir, plans_data_dir=plans_data_dir,
            base_path=base, static_edition={"commit": build["commit"]},
        )  # fmt: skip
        urls = export_urls(data, app)
    finally:
        conn.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    site = Path(tempfile.mkdtemp(prefix=f"{STAGING_PREFIX}{out.name}-", dir=out.parent))
    try:
        _write_site(site, app, urls, build)
        _install(site, out, clean)
    except BaseException:
        shutil.rmtree(site, ignore_errors=True)
        raise
    files = [p for p in out.rglob("*") if p.is_file()]
    return ExportResult(len(files), sum(p.stat().st_size for p in files), build)
