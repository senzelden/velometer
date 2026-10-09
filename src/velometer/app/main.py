"""FastAPI + Jinja app over the report query layer: overview, cities, city pages, methodology,
maps, CSV and the chart data.

Read-only: a request that must build a page opens its own `mode=ro` connection (lazily) and
closes it; built pages are cached per DB/config/docs/maps/content fingerprint (`app/cache.py`).
Missing data is a note on the page ("no run ...", "map not generated ..."), never a 500; an
unknown city is a 404. Every page is server-rendered and readable without JavaScript (tables);
charts are drawn by our own ES modules under /static/js from `/data/series.json`. The city page's
tier map is the vendored Leaflet over the run's GeoJSON (`velometer report maps`); its background
tiles come from the public OSM tile server, the one external host a page loads from (the user's
decision, 2026-10-02). Every response carries a Content-Security-Policy that allows exactly that.
"""

import logging
import re
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import markdown
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from velometer import timeseries as ts
from velometer.app import compare as cmp
from velometer.app import counts as counts_model
from velometer.app import plans_pages, urls
from velometer.app import story as story_model
from velometer.app.cache import PageCache, fingerprint
from velometer.app.names import country_name
from velometer.app.narrative import render_explainer, render_narrative, safe_url
from velometer.app.organisations import org_of_sources, organisations_context
from velometer.app.series import series_payload
from velometer.config import ConfigError, load_differences
from velometer.content.loader import (
    load_document,
    load_explainer,
    load_narratives,
    load_organisation_map,
    load_organisations,
    load_sources,
)
from velometer.content.models import ContentError
from velometer.db import SchemaError, subarea_names
from velometer.plans.models import load_plans
from velometer.reconcile import short_commit
from velometer.report import change as change_report
from velometer.report import charts
from velometer.report.csvexport import (
    SUBAREA_CSV_COLUMNS,
    csv_preamble,
    csv_table,
)
from velometer.report.data import HEADLINE_UNIT, KINDS, ReportData, open_readonly
from velometer.report.differences import difference_rows
from velometer.run import git_commit
from velometer.selection import report_selector

HERE = Path(__file__).parent
MAP_NAME = re.compile(r"^[a-z0-9_]+_(lau|fua)$")
# a change map: <city>_change_<from>_<to>, each end a 1 January snapshot date or `current`
CHANGE_NAME = re.compile(
    r"^([a-z0-9_]+)_change_(\d{4}-\d{2}-\d{2}|current)_(\d{4}-\d{2}-\d{2}|current)$"
)
EXPLANATIONS = Path("review") / "m3_timeseries.md"
METHODOLOGY = {"en": "methodology.md", "de": "methodology.de.md"}
# The docs file opens with a maintainer note (a blockquote: "generated, do not edit", a link to
# the other language's .md file). The page has its own language switch and drops it.
GENERATED_NOTE = re.compile(r"\A(?:>[^\n]*\n)+\s*")
# The Host headers the app answers: the loopback names `velometer serve` binds to. Any other
# Host (a DNS-rebinding page pointing its own name at 127.0.0.1) gets a 400.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
GZIP_MIN_BYTES = 1024  # below this a gzip frame saves too little to be worth it
GZIP_LEVEL = 5  # ~3x less CPU than 9 on the 15-20 MB FUA GeoJSON, ~5 % more bytes
# The tile layer's class (app.css mutes it: OSM's orange/red roads clash with tiers B and D)
TILE_CLASS = "tiermap-tiles"
LINE_WEIGHT = 3  # px: tier lines stay readable over the tiles at zoom 16
# The tier map's background and the links its attribution and popups point at.
OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_LINKS = {
    "copyright": "https://www.openstreetmap.org/copyright",
    "way": "https://www.openstreetmap.org/way/",
}
# The Stories page: what each chart step shows. `c` and `hl` are selection rules (story.pick;
# `hl: "c"` highlights every selected city), `m` and `mode` the Compare metric and scale; `href`
# is a fixed destination (the Bezirk tab). The Explore link and the sticky chart both come from it.
STORY_CITY = "berlin"
STEP_COMPARE = {
    "all": {"c": "all", "hl": "leaders"},
    "leaders": {"c": "leaders"},
    "tail": {"c": "tail"},
    "growth": {"c": "all", "hl": "growth", "m": "ab_km", "mode": "index"},
    "jumps": {"c": "flagged", "m": "ab_km", "view": "small", "table": "jumps", "ring": "km_jump"},
    "bezirke": {"href": f"/city/{STORY_CITY}/bezirke"},
}
# No inline script or style, no third-party host except the OSM tiles (images), no framing.
CSP = (
    "default-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; "
    "style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'"
)
# Directives a browser ignores in a <meta http-equiv> policy: the header keeps them; a page served
# without our headers (the static edition) goes without them.
HEADER_ONLY_DIRECTIVES = {"frame-ancestors", "report-uri", "report-to", "sandbox"}
# The city page's tabs: key, label, path suffix. Counts only for a city with counter data
# (ReportData.counter_cities), Bezirke only for a city with subareas.
TABS = [
    ("story", "Story", ""),
    ("time", "Over time", "/time"),
    ("tiers", "Tiers", "/tiers"),
    ("figures", "Figures", "/figures"),
    ("counts", "Counts", "/counts"),
    ("bezirke", "Bezirke", "/bezirke"),
]
COUNTERS_TEXT = "counters.yaml"  # content/: what the counters record, under the Counts tab
UNITS = {"pct": "%"}
CLAUSE_END = re.compile(r"[;:]|\.\s| [-–—] ")
log = logging.getLogger(__name__)
OURS_PREFIX = re.compile(r"^\s*ours:\s*", re.I)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def csp_meta(csp: str) -> str:
    """The policy as a `<meta http-equiv>` tag can carry it: `csp` without the header-only
    directives, the others verbatim and in order."""
    kept = [d.strip() for d in csp.split(";") if d.strip()]
    return "; ".join(d for d in kept if d.split()[0].lower() not in HEADER_ONLY_DIRECTIVES)


class CSPMiddleware:
    """Adds the Content-Security-Policy header to every HTTP response, errors included."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def with_csp(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() != b"content-security-policy"]  # fmt: skip
                headers.append((b"content-security-policy", CSP.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, with_csp)


class VelometerApp(FastAPI):
    """FastAPI with the CSP wrapped around the whole stack, ServerErrorMiddleware included, so
    the 500 of an unhandled exception carries the policy as well."""

    def build_middleware_stack(self):
        return CSPMiddleware(super().build_middleware_stack())


def _num(v: float | int | None, spec: str = ",.1f") -> str:
    return "n/a" if v is None else format(v, spec)


# the tables extension aligns columns with style="text-align: ..."; the CSP allows no inline
# style, so alignment becomes a class (app.css: .num right-aligns, .align-* the others)
ALIGN_STYLE = re.compile(r' style="text-align: (left|right|center);"')


HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


class _DropComments(markdown.preprocessors.Preprocessor):
    def run(self, lines):
        return HTML_COMMENT.sub("", "\n".join(lines)).split("\n")


class _EscapeHtml(markdown.Extension):
    """Markdown with raw HTML turned off: `<b>` in the source is shown as text, never emitted.
    HTML comments (the `<!-- generated:... -->` markers of docs/methodology*.md) are dropped."""

    def extendMarkdown(self, md):
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")
        md.preprocessors.register(_DropComments(md), "drop_comments", 30)


def _md(text: str) -> Markup:
    html = markdown.markdown(text, extensions=["tables", "fenced_code", _EscapeHtml()])
    return Markup(
        ALIGN_STYLE.sub(
            lambda m: ' class="num"' if m.group(1) == "right" else f' class="align-{m.group(1)}"',
            html,
        )
    )


def _host(url: str) -> str:
    host = urlparse(url).hostname or url
    return host.removeprefix("www.")


def _clause(note: str, limit: int = 90) -> str:
    """The first clause of a figure's note: what tells rows of one source apart."""
    first = CLAUSE_END.split(note.strip(), 1)[0].strip()
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


# The provenance prefix of an external figure's CSV note and how a reader is told it.
NOTE_PREFIX = re.compile(r"^\s*(primary-by-agency|primary|secondary)\b\s*(\([^)]*\))?\s*[;:]?\s*")
NOTE_PREFIX_TEXT = {
    "primary": "primary source",
    "secondary": "secondary source",
    "primary-by-agency": "primary source, published by the agency",
}


def _note_clause(note: str) -> str:
    """A figure's note as the Figures tab shows it: the CSV provenance prefix (`primary`,
    `secondary`, `primary-by-agency`) in words, then the first clause of the rest."""
    m = NOTE_PREFIX.match(note or "")
    if not m:
        return _clause(note or "")
    head = NOTE_PREFIX_TEXT[m.group(1)] + (f" {m.group(2)}" if m.group(2) else "")
    rest = note[m.end() :]
    return f"{head}: {_clause(rest)}" if rest.strip() else head


def _when(label: str, osm_timestamp: str | None = None) -> str:
    """A series label as the reader sees it: a year is "Jan <year>" (1 January snapshots), the
    current run its snapshot month ("Oct 2026")."""
    if label != ts.CURRENT:
        return f"Jan {label}"
    if osm_timestamp and re.match(r"^\d{4}-\d{2}", osm_timestamp):
        return f"{MONTHS[int(osm_timestamp[5:7]) - 1]} {osm_timestamp[:4]}"
    return "current"


class LazyData:
    """The per-request ReportData, opened on first attribute access: a page-cache hit never
    touches the database. A missing database or a schema mismatch is a 503 at that access."""

    def __init__(self, db_path: Path, config_dir: Path):
        self._db_path, self._config_dir = db_path, config_dir
        self._conn: sqlite3.Connection | None = None
        self._data: ReportData | None = None

    def __getattr__(self, name: str):
        if name.startswith("_"):  # private names (and dunder probes) are not ReportData's API
            raise AttributeError(name)
        if self._data is None:
            try:
                self._conn = open_readonly(self._db_path)
            except FileNotFoundError as e:
                raise HTTPException(503, f"database not found: {self._db_path}") from e
            except SchemaError as e:
                raise HTTPException(503, str(e)) from e
            self._data = ReportData(self._conn, self._config_dir)
        if name not in ReportData.__dict__ and name not in vars(self._data):
            raise AttributeError(f"ReportData has no attribute {name!r}")
        return getattr(self._data, name)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()


def population_years(data: ReportData) -> list[int]:
    """The years of the city populations the per-100k metric divides by."""
    return [c.population.year for c in data.cities() if c.population]


def create_app(
    db_path: Path,
    config_dir: Path,
    maps_dir: Path,
    docs_dir: Path,
    content_dir: Path = Path("content"),
    plans_data_dir: Path = Path("data") / "plans",
    base_path: str = "/",
    static_edition: dict | None = None,
) -> FastAPI:
    """The app. `base_path` is the path the site is served under (M9: every URL a page emits
    carries it, the routes stay at `/…`); `static_edition` ({"commit": <short>}) marks pages built
    for the static export (a footer line), None for the live app."""
    db_path, config_dir = Path(db_path), Path(config_dir)
    maps_dir, docs_dir, content_dir = Path(maps_dir), Path(docs_dir), Path(content_dir)
    plans_data_dir = Path(plans_data_dir)
    app = VelometerApp(title="velometer", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=GZIP_MIN_BYTES, compresslevel=GZIP_LEVEL)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.state.base_path = urls.normalise_base(base_path)
    # Every URL that leaves the app goes through `u`: templates call it on each internal href,
    # src and action at the point they write it; values a script reads from a JSON config (map
    # URLs, the Stories steps' links) get it here, since the script uses them as they are.
    u = urls.make_u(app.state.base_path)
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.globals["u"] = u
    templates.env.globals["base_path"] = app.state.base_path
    # inside a double-quoted attribute the policy's single quotes need no escaping
    templates.env.globals["csp_meta"] = Markup(str(escape(csp_meta(CSP))).replace("&#39;", "'"))
    templates.env.globals["static_edition"] = static_edition
    templates.env.filters["num"] = _num
    templates.env.filters["md"] = _md
    templates.env.filters["when"] = _when
    templates.env.filters["http_url"] = safe_url
    templates.env.filters["host"] = _host
    templates.env.filters["clause"] = _note_clause
    templates.env.filters["unit"] = lambda u: UNITS.get(u, u)
    # a preset's report.yaml label starts "Ours: "; a Figures row's "Ours" column says it already
    templates.env.filters["strip_ours"] = lambda v: OURS_PREFIX.sub("", v or "")

    cache = PageCache()

    def fp(request: Request) -> tuple:
        """The request's fingerprint, computed on first use and kept on `request.state`."""
        if not hasattr(request.state, "fingerprint"):
            request.state.fingerprint = fingerprint(
                db_path, config_dir, docs_dir, maps_dir, content_dir, plans_data_dir
            )
        return request.state.fingerprint

    # async: the connection is made, used and closed on the event-loop thread (sqlite3
    # connections are bound to the thread that made them).
    async def report_data() -> AsyncIterator[LazyData]:
        lazy = LazyData(db_path, config_dir)
        try:
            yield lazy
        finally:
            lazy.close()

    Data = Annotated[ReportData, Depends(report_data)]

    def by_country(data: ReportData) -> list[dict]:
        """The trusted cities grouped by country name, both sorted by name."""
        groups: dict[str, list] = {}
        for c in data.cities():
            groups.setdefault(country_name(c.country_iso2), []).append(c)
        return [
            {
                "country": name,
                "iso2": cs[0].country_iso2,
                "cities": sorted(cs, key=lambda c: c.name),
            }
            for name, cs in sorted(groups.items())
        ]

    def page(
        request: Request, name: str, active: str, data: ReportData | None = None, **ctx
    ) -> HTMLResponse:
        def build_footer() -> dict:
            sel = report_selector(config_dir)  # config only: the footer needs no database
            return {"classifier": sel.version, "config": sel.short_sha}

        footer = cache.get("footer", fp(request), build_footer)
        nav = None  # the Cities menu; a page without a database still renders, linking /cities
        if data is not None:
            try:
                nav = cache.get("nav", fp(request), lambda: by_country(data))
            except HTTPException:
                nav = None
        return templates.TemplateResponse(
            request, name, {"footer": footer, "nav_groups": nav, "active": active, **ctx}
        )

    def known(data: ReportData, city_id: str):
        city = next((c for c in data.cities() if c.id == city_id), None)
        if city is None:
            raise HTTPException(404, f"unknown city {city_id!r}")
        return city

    def headline_of(point) -> float | None:
        return (
            None
            if point is None
            else {p.preset: p.value for p in point.presets}.get("ours_headline")
        )

    def city_summary(data: ReportData, c) -> dict:
        """A city's LAU headline now and at the first series year (Overview, Cities)."""
        point = data.current(c.id, "lau")
        cs = data.series(c.id, "lau")
        first = (
            next((p for p in cs.points if p.headline is not None and p.label != ts.CURRENT), None)
            if cs
            else None
        )
        now = headline_of(point)
        return {
            "city": c,
            "country": country_name(c.country_iso2),
            "point": point,
            "now": now,
            "now_label": _when(ts.CURRENT, point.osm_timestamp) if point else None,
            "first": None if first is None else first.headline,
            "first_label": None if first is None else _when(first.label, first.osm_timestamp),
            "change": None if now is None or first is None else now - first.headline,
        }

    def rankings_table(data: ReportData) -> dict | None:
        """The rankings by source as one table: a row per city, a column per source (report.yaml
        order), each cell the rank and value or "not published"."""
        rows = data.ranking_rows()
        if not data.ranks():
            return None
        nuts3 = {
            r.id
            for r in data.report_config.rankings
            if r.kind == "external_ratio" and r.scope.startswith("nuts3_")
        }
        region_only = {i for i, f in data.city_fields().items() if f.get("nuts3_is_city") is False}
        columns = {}
        for r in rows:
            columns.setdefault(r.source_id, f"{r.source_label} (n={r.n_ranked})")
        cells: dict[str, dict] = {}
        for r in rows:
            cells.setdefault(r.city_id, {})[r.source_id] = {
                "rank": r.rank,
                "value": r.value,
                "dagger": r.source_id in nuts3 and r.city_id in region_only,
            }
        names = {c.id: c.name for c in data.cities()}
        first = next(iter(columns))
        order = sorted(cells, key=lambda i: (cells[i].get(first, {}).get("rank") or 10**6, i))
        return {
            "columns": columns,
            "rows": [{"id": i, "name": names.get(i, i), "cells": cells[i]} for i in order],
            "notes": [
                f"{r.label}: {n}"
                for r in data.report_config.rankings
                if (n := getattr(r, "note", None))
            ],
            "dagger": any(c["dagger"] for row in cells.values() for c in row.values()),
        }

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, data: Data):
        def build() -> dict:
            rows, summaries = [], []
            for c in data.cities():
                summary = city_summary(data, c)
                summaries.append(summary)
                point = summary["point"]
                presets = {} if point is None else {p.preset: p.value for p in point.presets}
                rows.append(
                    {
                        "city": c,
                        "point": point,
                        "presets": presets,
                        "flags": len(data.flags(c.id, "lau")),  # the table is the LAU run
                    }
                )
            ranked = sorted(
                summaries, key=lambda s: (s["now"] is None, -(s["now"] or 0), s["city"].name)
            )
            values = [v for s in summaries for v in (s["now"], s["first"]) if v is not None]
            top = max(values, default=0.0)
            return {
                "rows": rows,
                "ranking": ranked,
                "scale_max": (int(top // 50) + 1) * 50 if top else 1,
                "countries": len({c.country_iso2 for c in data.cities()}),
                "years": data.years,
                "preset_label": data.preset_labels(),
                "preset_unit": data.preset_units(),
                "headline_unit": HEADLINE_UNIT,
                "rankings": rankings_table(data),
            }

        ctx = cache.get("index", fp(request), build)
        return page(request, "index.html", "overview", data, **ctx)

    @app.get("/cities", response_class=HTMLResponse)
    async def cities(request: Request, data: Data):
        def build() -> dict:
            summaries = {c.id: city_summary(data, c) for c in data.cities()}
            groups = [
                {**g, "cities": [summaries[c.id] for c in g["cities"]]} for g in by_country(data)
            ]
            ranked = sorted((s for s in summaries.values() if s["now"] is not None),
                            key=lambda s: -s["now"])  # fmt: skip
            rank = {s["city"].id: i + 1 for i, s in enumerate(ranked)}
            return {"groups": groups, "rank": rank, "n": len(summaries),
                    "headline_unit": HEADLINE_UNIT}  # fmt: skip

        ctx = cache.get("cities", fp(request), build)
        return page(request, "cities.html", "cities", data, **ctx)

    @app.get("/data/series.json")
    async def series_json(request: Request, data: Data):
        payload = cache.get(
            "series", fp(request), lambda: series_payload(data, docs_dir / EXPLANATIONS)
        )
        return JSONResponse(payload)

    def content():
        """(narratives, sources, explainer, errors) of the content dir. `errors` maps what could
        not be read to its message: "*" for the source registry (nothing renders without it),
        "explainer", or a narrative's file stem. Each is logged and shown as a note, never a 500;
        one broken narrative leaves the others readable."""

        def build():
            try:
                sources = load_sources(content_dir / "sources")
            except ContentError as e:
                log.error("content could not be loaded: %s", e)
                return {}, {}, None, {"*": str(e)}
            errors: dict[str, str] = {}
            narratives = load_narratives(content_dir / "narratives", errors=errors)
            try:
                explainer = load_explainer(content_dir / "explainer.yaml")
            except ContentError as e:
                explainer, errors["explainer"] = None, str(e)
            for msg in errors.values():
                log.error("content could not be loaded: %s", msg)
            return narratives, sources, explainer, errors

        return build

    def content_error(errors: dict[str, str], key: str) -> str | None:
        """The load error that blanks `key` (a narrative stem or "explainer"), if any."""
        return errors.get("*") or errors.get(key)

    def narrative_of(request: Request, city_id: str):
        """The city's rendered narrative (None without one) and a note about unreadable content."""
        narratives, sources, _, errors = cache.get("content", fp(request), content())

        def build():
            n = narratives.get(city_id)
            return None if n is None else render_narrative(n, sources)

        return cache.get(f"narrative:{city_id}", fp(request), build), content_error(errors, city_id)

    def organisations(request: Request) -> tuple[dict, dict[str, str]]:
        """(profiles, errors) of content/organisations; a broken profile is a note, not a 500."""

        def build():
            errors: dict[str, str] = {}
            try:
                orgs = load_organisations(content_dir / "organisations", errors=errors)
            except ContentError as e:  # pragma: no cover - the loader records per file
                orgs, errors["*"] = {}, str(e)
            for msg in errors.values():
                log.error("organisation profile could not be loaded: %s", msg)
            return orgs, errors

        return cache.get("organisations-raw", fp(request), build)

    def org_mapping() -> list:
        try:
            return load_organisation_map(config_dir / "organisations.yaml")
        except ContentError as e:
            log.error("config/organisations.yaml could not be read: %s", e)
            return []

    def plans_config():
        """(plans, report rows, error) of config/plans; an unreadable file is a note."""
        try:
            plans, rows = load_plans(config_dir / "plans")
        except ConfigError as e:
            log.error("plans could not be loaded: %s", e)
            return [], [], str(e)
        return plans, rows, None

    def figures_context(data: ReportData, city_id: str, profiles: set[str]) -> dict:
        try:
            cfg = load_differences(config_dir / "differences.yaml")
            rows = difference_rows(data, city_id, cfg)
        except (ConfigError, OSError, KeyError) as e:
            log.error("figures for %s could not be built: %r", city_id, e)
            return {
                "differences": None,
                "dimensions": [],
                "dimension_labels": {},
                "metric_labels": {},
                "source_names": {},
                "org_of": {},
            }
        return {
            "differences": rows,
            "dimensions": cfg.dimensions,
            "dimension_labels": {d.id: d.label for d in cfg.dimensions},
            "metric_labels": cfg.labels,
            "source_names": cfg.source_names,
            "org_of": org_of_sources(org_mapping(), city_id, profiles),
        }

    def counts_context(request: Request, data: ReportData, city_id: str) -> dict:
        """The Counts tab: the counter index beside the mapped-km index, the sites, the
        attribution and content/counters.yaml (a broken text is a note, not a 500)."""
        _, sources, _, errors = cache.get("content", fp(request), content())

        def build() -> dict:
            cfg, cfg_error = counts_model.counters_config(config_dir)
            entry = next((e for e in cfg.cities if e.city == city_id), None) if cfg else None
            lau = data.series(city_id, "lau")
            ctx = counts_model.counts_context(data, city_id, entry, lau.points if lau else [])
            try:
                text, text_error = load_document(content_dir / COUNTERS_TEXT), None
            except ContentError as e:
                log.error("counters text could not be loaded: %s", e)
                text, text_error = None, str(e)
            doc = None if text is None or errors.get("*") else render_explainer(text, sources)
            ctx["site_map"] = (
                None
                if ctx["site_map"] is None
                else ctx["site_map"]
                | {"tiles": OSM_TILES, "tile_class": TILE_CLASS, "links": OSM_LINKS}
            )
            return ctx | {"doc": doc, "text_error": text_error, "config_error": cfg_error}

        return cache.get(f"counts:{city_id}", fp(request), build)

    def city_page(request: Request, city_id: str, tab: str, data: ReportData) -> HTMLResponse:
        ctx = cache.get(f"city:{city_id}", fp(request), lambda: city_context(data, city_id))
        if tab == "bezirke" and not ctx["bezirke"]:
            raise HTTPException(404, f"{city_id!r} has no Bezirke")
        if tab == "counts" and not ctx["has_counts"]:
            raise HTTPException(404, f"{city_id!r} has no counter data")
        extra: dict = {}
        if tab == "figures":
            profiles = set(organisations(request)[0])
            extra = cache.get(
                f"figures:{city_id}", fp(request), lambda: figures_context(data, city_id, profiles)
            )
        nar, note = narrative_of(request, city_id)
        role = {"story": "story", "figures": "figures"}.get(tab)
        cited_sources, cited_refs = nar.cited(nar.of_role(role)) if nar and role else ([], [])
        if tab == "counts":
            extra = {"counts": counts_context(request, data, city_id)}
            nar = extra["counts"]["doc"]  # the tab cites the counters text's sources
            cited_sources = [] if nar is None else sorted(nar.sources.items())
            cited_refs = [] if nar is None else sorted(nar.refs.items())
        label = next(t[1] for t in TABS if t[0] == tab)
        tabs = [
            {"key": k, "label": lbl, "href": f"/city/{city_id}{suffix}"}
            for k, lbl, suffix in TABS
            if (k != "bezirke" or ctx["bezirke"]) and (k != "counts" or ctx["has_counts"])
        ]
        return page(
            request, f"city/{tab}.html", "city", data, **ctx, **extra, tab=tab, tab_label=label,
            tabs=tabs, nar=nar, content_error=note, cited_sources=cited_sources,
            cited_refs=cited_refs,
        )  # fmt: skip

    @app.get("/compare", response_class=HTMLResponse)
    async def compare(request: Request, data: Data):
        payload = cache.get(
            "series", fp(request), lambda: series_payload(data, docs_dir / EXPLANATIONS)
        )
        known_ids = list(payload["cities"])
        state = cmp.parse_compare(request.url.query, known_ids, cmp.METRICS)
        table = cmp.table_model(payload, state)
        quick = [
            {"key": k, "label": label, "ids": cmp.quick_set_ids(k, known_ids)}
            for k, label in cmp.QUICK_LABELS.items()
        ]
        info = cmp.metric_info(HEADLINE_UNIT, data.preset_units(), population_years(data))
        config = {
            "cities": known_ids,
            "metric_order": list(cmp.METRICS),  # tojson sorts the keys of `metrics`
            "metrics": info,
            "quick": cmp.QUICK_SETS,
            "views": cmp.VIEW_LABELS,
            "headline_unit": HEADLINE_UNIT,
        }
        return page(
            request, "compare.html", "compare", data, state=state, table=table, quick=quick,
            groups=by_country(data), metrics=info, views=cmp.VIEW_LABELS, config=config,
            href=lambda **changes: "/compare?" + cmp.serialize(state, **changes),
            foot=cmp.footnote(state.m, HEADLINE_UNIT),
            counter={"title": cmp.counter_title, "context": cmp.COUNTER_CONTEXT},
        )  # fmt: skip

    @app.get("/city/{city_id}/panel", response_class=HTMLResponse)
    async def city_panel(request: Request, city_id: str, data: Data):
        """The Compare slide-over: a fragment (no layout), fetched by panel.js. A direct visit
        shows the same fragment; the full page is /city/<id>."""
        ctx = cache.get(f"city:{city_id}", fp(request), lambda: city_context(data, city_id))
        # a copy: TemplateResponse adds `request` to the dict it is given, and this one is cached
        # (a tab page spreads it next to its own `request=`)
        return templates.TemplateResponse(request, "city/panel.html", {**ctx})

    @app.get("/city/{city_id}", response_class=HTMLResponse)
    async def city(request: Request, city_id: str, data: Data):
        return city_page(request, city_id, "story", data)

    @app.get("/city/{city_id}/{tab}", response_class=HTMLResponse)
    async def city_tab(request: Request, city_id: str, tab: str, data: Data):
        if tab not in {k for k, _, suffix in TABS if suffix}:
            raise HTTPException(404, f"unknown tab {tab!r}")
        return city_page(request, city_id, tab, data)

    def story_context(data: ReportData, payload: dict, n, sources) -> dict:
        """The Stories page: the combined narrative's sections with the chart step each names."""
        nar = render_narrative(n, sources)
        metrics = cmp.metric_info(HEADLINE_UNIT, data.preset_units(), population_years(data))
        steps = {}
        for step, spec in STEP_COMPARE.items():
            built = (
                story_model.bezirke_step(payload, STORY_CITY, spec["href"])
                if "href" in spec
                else story_model.lines_step(payload, spec, metrics)
            )
            if built:
                steps[step] = built
        story, figures = [], []
        for raw, sec in zip(n.sections, nar.sections, strict=True):
            if sec.role == "figures":
                figures.append(sec)
            else:
                story.append({"step": raw.step, "sec": sec})
        order = [s["step"] for s in story if s["step"] in steps]
        config = {
            step: {k: v for k, v in built.items() if k != "table"}
            | {
                "href": u(built["href"]),  # story.js sets it as the Explore link
                # a step section may have no heading: the eyebrow then names the chart
                "heading": next(s["sec"].heading for s in story if s["step"] == step)
                or built.get("title")
                or "",
                "n": order.index(step) + 1,
                "of": len(order),
            }
            for step, built in steps.items()
            if step in order
        }
        sources_cited, refs_cited = nar.cited(nar.sections)
        return {
            "nar": nar, "story": story, "figures": figures, "steps": steps, "config": config,
            "cited_sources": sources_cited, "cited_refs": refs_cited,
        }  # fmt: skip

    @app.get("/stories", response_class=HTMLResponse)
    async def stories(request: Request, data: Data):
        payload = cache.get(
            "series", fp(request), lambda: series_payload(data, docs_dir / EXPLANATIONS)
        )
        narratives, sources, _, errors = cache.get("content", fp(request), content())
        error = content_error(errors, "combined")

        def build():
            n = narratives.get("combined")
            return None if n is None else story_context(data, payload, n, sources)

        ctx = cache.get("stories", fp(request), build) or {}
        return page(request, "stories.html", "stories", data, content_error=error, **ctx)

    @app.get("/differences", response_class=HTMLResponse)
    async def differences(request: Request, data: Data):
        _, sources, explainer, errors = cache.get("content", fp(request), content())
        error = content_error(errors, "explainer")

        def build():
            return None if explainer is None else render_explainer(explainer, sources)

        doc = cache.get("differences", fp(request), build)
        try:
            cfg = load_differences(config_dir / "differences.yaml")
            labels = {d.id: d.label for d in cfg.dimensions}
        except (ConfigError, OSError):
            labels = {}
        sources = [] if doc is None else sorted(doc.sources.items())
        refs = [] if doc is None else sorted(doc.refs.items())
        cities = [c for g in by_country(data) for c in g["cities"]]
        return page(
            request, "differences.html", "differences", data, doc=doc, content_error=error,
            cited_sources=sources, cited_refs=refs, nar=doc, dimension_labels=labels,
            cities=cities,
        )  # fmt: skip

    @app.get("/organisations", response_class=HTMLResponse)
    async def organisations_page(request: Request, data: Data):
        _, sources, _, errors = cache.get("content", fp(request), content())
        orgs, org_errors = organisations(request)

        def build() -> dict:
            plans, rows, _ = plans_config()
            try:
                diffs = load_differences(config_dir / "differences.yaml")
                labels, source_names = {d.id: d.label for d in diffs.dimensions}, diffs.source_names
            except (ConfigError, OSError):
                labels, source_names = {}, {}
            names = {c.id: c.name for c in data.cities()}
            return {
                "profiles": organisations_context(
                    orgs, sources, org_mapping(), plans, rows, names, source_names
                ),
                "dimension_labels": labels,
            }

        ctx = cache.get("organisations", fp(request), build)
        return page(
            request, "organisations.html", "organisations", data, **ctx,
            content_error=errors.get("*"), broken=sorted(org_errors),
        )  # fmt: skip

    @app.get("/plans", response_class=HTMLResponse)
    async def plans_index(request: Request, data: Data):
        orgs, _ = organisations(request)

        def build() -> dict:
            plans, rows, error = plans_config()
            cities = sorted(((c.id, c.name) for c in data.cities()), key=lambda c: c[1])
            return {"table": plans_pages.plans_table(plans, rows, cities, orgs), "error": error}

        ctx = cache.get("plans", fp(request), build)
        return page(request, "plans.html", "plans", data, **ctx)

    @app.get("/plans/{city_id}", response_class=HTMLResponse)
    async def plan_page(request: Request, city_id: str, data: Data):
        if city_id != plans_pages.DETAIL_CITY:
            raise HTTPException(404, f"no plan page for {city_id!r}")
        _, sources, _, errors = cache.get("content", fp(request), content())
        orgs, _ = organisations(request)

        def build() -> dict:
            plans, rows, error = plans_config()
            plan = next((p for p in plans if p.city == city_id), None)
            try:
                text = load_document(content_dir / "plans" / f"{city_id}.yaml")
                text_error = None
            except ContentError as e:
                log.error("plan page text could not be loaded: %s", e)
                text, text_error = None, str(e)
            doc = None if text is None or errors.get("*") else render_explainer(text, sources)
            if plan is None:
                return {"plan": None, "error": error, "doc": doc, "text_error": text_error}
            overlay = data.plan_overlay(city_id)
            dates = plans_pages.run_dates(data.conn, {r.run_id for r in overlay})
            projects = plans_pages.completed_projects(plans_data_dir / plans_pages.MEASURES_FILE)
            ctx = plans_pages.berlin_context(plan, rows, orgs, overlay, dates, projects)
            measures, record_error = plans_pages.measures_retrieved(plans_data_dir)
            if record_error:
                log.error("plan data source record could not be read: %s", record_error)
            return ctx | {
                "error": error,
                "doc": doc,
                "text_error": text_error,
                "measures": measures,
                "network_licence": plans_pages.network_licence(measures),
                "record_error": record_error,
            }

        ctx = cache.get(f"plan:{city_id}", fp(request), build)
        doc = ctx["doc"]
        return page(
            request, "plans_berlin.html", "plans", data, **ctx, nar=doc,
            content_error=errors.get("*"),
            cited_sources=[] if doc is None else sorted(doc.sources.items()),
            cited_refs=[] if doc is None else sorted(doc.refs.items()),
        )  # fmt: skip

    def keynums(summary: dict, fua, fua_now: float | None, flagged: int) -> list[dict]:
        """The five numbers of the city header's `.keynums` row (LAU unless it says FUA)."""
        point, change = summary["point"], summary["change"]
        return [
            {"label": f"Headline, {summary['now_label'] or 'now'}", "value": _num(summary["now"]),
             "sub": "per 100 km of main roads"},
            {"label": f"Since {summary['first_label'] or 'the first year'}",
             "value": "n/a" if change is None else f"{change:+.1f}".replace("-", "\u2212"),
             "tone": None if change is None else ("up" if change >= 0 else "down"),
             "sub": "n/a" if summary["first"] is None else f"from {_num(summary['first'])}"},
            {"label": "A+B mapped km",
             "value": "n/a" if point is None else _num(point.ab_km, ",.0f"),
             "sub": "per side" + (f", {summary['now_label']}" if point else "")},
            {"label": "Metro area (FUA)", "value": _num(fua_now),
             "sub": "headline" + (f", {_when(ts.CURRENT, fua.osm_timestamp)}" if fua else "")},
            {"label": "Flagged years", "value": str(flagged),
             "sub": "LAU, with explanations" if flagged else "LAU, none flagged"},
        ]  # fmt: skip

    def city_context(data: ReportData, city_id: str) -> dict:
        c = known(data, city_id)
        explanations = docs_dir / EXPLANATIONS
        kinds, map_kinds = [], []
        for kind in KINDS:
            series = data.series(city_id, kind)
            flags = [
                {"flag": f, "explanation": ts.explanation(explanations, f.key)}
                for f in data.flags(city_id, kind)
            ]
            map_name = f"{city_id}_{kind}.png"
            geojson = f"{city_id}_{kind}.geojson"
            if (maps_dir / geojson).is_file():
                map_kinds.append(
                    {"kind": kind, "label": kind.upper(), "url": u(f"/maps/{geojson}")}
                )
            kinds.append(
                {
                    "kind": kind,
                    "point": data.current(city_id, kind),
                    "series": series,
                    "flagged": {f["flag"].label: f["flag"] for f in flags},
                    "flags": flags,
                    "map": map_name if (maps_dir / map_name).is_file() else None,
                    "geojson": (maps_dir / geojson).is_file(),
                }
            )
        # the yearly headline table under the chart: one row per label of either boundary
        by_label: dict[str, dict] = {}
        for k in kinds:
            for p in k["series"].points if k["series"] else []:
                row = by_label.setdefault(p.label, {"label": p.label, "osm": p.osm_timestamp})
                row[k["kind"]] = p
        years = sorted((r for r in by_label.values() if r["label"] != ts.CURRENT),
                       key=lambda r: r["label"])  # fmt: skip
        yearly = years + ([by_label[ts.CURRENT]] if ts.CURRENT in by_label else [])
        colours = dict(zip("ABCDE", charts.TIER_COLOURS, strict=True))
        tiermap = {
            "tiles": OSM_TILES,
            "tile_class": TILE_CLASS,
            "weight": LINE_WEIGHT,
            "links": OSM_LINKS,
            "colours": colours,
            "labels": charts.TIER_LABEL,
            "outline": charts.OUTLINE,
            "kinds": map_kinds,
        }
        summary = city_summary(data, c)
        counters_cfg, counters_error = counts_model.counters_config(config_dir)
        lau = summary["point"]
        fua = data.current(city_id, "fua")
        return {
            "city": c,
            "country": country_name(c.country_iso2),
            "residents": lau.population_value if lau else None,
            "keynums": keynums(
                summary,
                fua,
                headline_of(fua),
                len(next(k for k in kinds if k["kind"] == "lau")["flags"]),
            ),
            "compare_groups": [
                {**g, "cities": others}
                for g in by_country(data)
                if (others := [o for o in g["cities"] if o.id != city_id])
            ],
            "bezirke": bezirke_context(data, city_id),
            "has_counts": city_id in data.counter_cities(),
            # spec §5.1: a city without open counter data says so, with the portals checked; an
            # unreadable config/counters.yaml says that instead of dropping the note
            "no_counters": counts_model.no_data_notes(counters_cfg).get(city_id),
            "counters_error": None if counters_error is None else cmp.COUNTER_CONFIG_ERROR,
            "kinds": kinds,
            "yearly": yearly,
            "reconcile": data.reconcile(city_id),
            "reported": data.reported_figures(city_id),
            "preset_label": data.preset_labels(),
            "preset_unit": data.preset_units(),
            "headline_unit": HEADLINE_UNIT,
            "tiers": ts.TIERS,
            "tiermap": tiermap if map_kinds else None,
            "plan_href": f"/plans/{city_id}"
            if city_id == plans_pages.DETAIL_CITY
            else f"/plans#{city_id}",
        }

    def bezirk_series(data: ReportData, city_id: str) -> dict:
        """Each subarea's headline per series label, the table under the small multiples."""
        series = data.subarea_series(city_id)
        names = subarea_names(data.conn, city_id)
        labels: list[str] = []
        for points in series.values():
            labels += [p.label for p in points if p.label not in labels]
        years = sorted(lbl for lbl in labels if lbl != ts.CURRENT)
        labels = years + ([ts.CURRENT] if ts.CURRENT in labels else [])
        osm = {p.label: p.osm_timestamp for points in series.values() for p in points}
        rows = [
            {"name": names.get(sid, sid), "values": {p.label: p.headline for p in points}}
            for sid, points in series.items()
        ]
        return {
            "labels": [{"label": lbl, "text": _when(lbl, osm.get(lbl))} for lbl in labels],
            "rows": sorted(rows, key=lambda r: r["name"]),
        }

    def bezirke_context(data: ReportData, city_id: str) -> dict | None:
        """The Bezirk section: current table, small multiples, and the change map with the
        per-Bezirk table of its markdown. None for a city without (trusted) subareas."""
        rows = data.subareas(city_id)
        if rows is None:
            return None
        window = data.report_config.change_window
        label_from = window.from_.isoformat()
        label_to = window.to if isinstance(window.to, str) else window.to.isoformat()
        stem = f"{city_id}_change_{label_from}_{label_to}"
        md_path = docs_dir / "review" / f"{stem}.md"
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            text = None
        table = None if text is None else change_report.bezirk_table(text)
        if table is not None:  # never raw HTML from the page into the `md` filter
            table = table.replace("<", "&lt;").replace(">", "&gt;")
        runs = None if text is None else change_report.change_runs(text)
        has_map = (maps_dir / f"{stem}.geojson").is_file()
        colours = change_report.CATEGORY_COLOURS
        latest = data.selector.latest(data.conn, city_id, "lau")
        return {
            "rows": rows,
            "series": bezirk_series(data, city_id),
            "window": f"{label_from} to {label_to}",
            "change_runs": runs,
            # the change page does not end at the run the Bezirk table above shows
            "change_stale": (has_map or table is not None) and (runs is None or runs[1] != latest),
            "latest_run": latest,
            "change_table": table,
            "change_map": {
                "url": u(f"/maps/{stem}.geojson"),
                "tiles": OSM_TILES,
                "tile_class": TILE_CLASS,
                "weight": LINE_WEIGHT,
                "links": OSM_LINKS,
                "colours": colours,
                "labels": {c: f"mapped {c}" for c in colours},
            }
            if has_map
            else None,
        }

    def methodology(request: Request, data: ReportData, lang: str) -> HTMLResponse:
        path = docs_dir / METHODOLOGY[lang]
        try:
            body = _md(GENERATED_NOTE.sub("", path.read_text(encoding="utf-8")))
        except OSError:
            body = None
        return page(
            request, "methodology.html", "methodology", data, lang=lang, body=body, file=path.name
        )

    @app.get("/methodology", response_class=HTMLResponse)
    async def methodology_en(request: Request, data: Data):
        return methodology(request, data, "en")

    @app.get("/methodology/de", response_class=HTMLResponse)
    async def methodology_de(request: Request, data: Data):
        return methodology(request, data, "de")

    def map_file(data: ReportData, name: str, suffix: str) -> Path:
        """The map file of a trusted city's run, else 404 (the city page and CSV do the same)."""
        path = maps_dir / f"{name}.{suffix}"
        change = CHANGE_NAME.fullmatch(name) if suffix == "geojson" else None
        if change is None and not MAP_NAME.fullmatch(name):
            raise HTTPException(404, "map not found")
        city_id = change.group(1) if change else name.rsplit("_", 1)[0]
        if city_id not in {c.id for c in data.cities()} or not path.is_file():
            raise HTTPException(404, "map not found")
        return path

    @app.get("/maps/{name}.png")
    async def map_png(name: str, data: Data):
        return FileResponse(map_file(data, name, "png"), media_type="image/png")

    @app.get("/maps/{name}.geojson")
    async def map_geojson(name: str, data: Data):
        return FileResponse(map_file(data, name, "geojson"), media_type="application/geo+json")

    def csv_response(request: Request, data: ReportData, city_id: str | None) -> Response:
        def build() -> str:
            if city_id is not None:
                known(data, city_id)
            try:
                return csv_table(data.csv_rows(city_id))
            except sqlite3.Error as e:
                raise HTTPException(503, f"database error: {e}") from e

        # the table is cached; the commit and the generated time are of this request
        table = cache.get(f"csv:{city_id or 'all'}", fp(request), build)
        text = (
            csv_preamble(
                short_commit(git_commit()), datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            + table
        )
        name = f"velometer-{city_id or 'all'}.csv"
        return Response(
            text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/data/all.csv")
    async def csv_all(request: Request, data: Data):
        return csv_response(request, data, None)

    @app.get("/data/{city_id}_subareas.csv")
    async def csv_subareas(request: Request, city_id: str, data: Data):
        def build() -> str:
            known(data, city_id)
            try:
                rows = data.subarea_csv_rows(city_id)
            except sqlite3.Error as e:
                raise HTTPException(503, f"database error: {e}") from e
            if not rows:
                raise HTTPException(404, f"no subareas for {city_id!r}")
            return csv_table(rows, SUBAREA_CSV_COLUMNS)

        table = cache.get(f"csv-subareas:{city_id}", fp(request), build)
        text = (
            csv_preamble(
                short_commit(git_commit()), datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            + table
        )
        return Response(
            text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="velometer-{city_id}-subareas.csv"'
            },
        )

    @app.get("/data/{city_id}.csv")
    async def csv_city(request: Request, city_id: str, data: Data):
        return csv_response(request, data, city_id)

    return app
