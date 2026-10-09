"""`velometer app export`: the static edition (M9 spec decisions 1, 2, 4, 8, 9).

The app renders every exported URL in-process (Starlette TestClient: no server, no network) and
the response bodies are written to files; there is no second renderer. The URL list comes from
the data (`export_urls`), a URL maps to a file by `url_to_path`, `static/` is copied, `404.html`
is the app's 404 response and `build.json` stamps the build. The site is written to a staging
directory next to `out` and moved into place only when complete, so a failed export leaves `out`
as it was. The database is opened read-only, as the app opens it.
"""

import json
import re
import shutil
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
    with TestClient(app, base_url=BASE_URL) as client:
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
    with TestClient(app, base_url=BASE_URL) as client:
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


def _install(site: Path, out: Path) -> None:
    """The complete `site` in place of `out` (already checked by `_check_out`)."""
    if out.exists():
        shutil.rmtree(out)
    site.rename(out)


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
    out = Path(out)
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
    site = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    try:
        _write_site(site, app, urls, build)
        _install(site, out)
    except BaseException:
        shutil.rmtree(site, ignore_errors=True)
        raise
    files = [p for p in out.rglob("*") if p.is_file()]
    return ExportResult(len(files), sum(p.stat().st_size for p in files), build)
