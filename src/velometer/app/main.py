"""FastAPI + Jinja app over the report query layer: index, city pages, methodology, maps, CSV.

Read-only: a request that must build a page opens its own `mode=ro` connection (lazily) and
closes it; built pages are cached per DB/config/docs fingerprint (`app/cache.py`).
Missing data is a note on the page ("no run ...", "map not generated ..."), never a 500; an
unknown city is a 404. Charts are Vega-Lite specs with inline data, drawn by the vendored
vega / vega-lite / vega-embed bundles under /static. The city page's tier map is the vendored
Leaflet over the run's GeoJSON (`velometer report maps`); its background tiles come from the
public OSM tile server, the one external host a page loads from (the user's decision, 2026-10-02).
"""

import re
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import markdown
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from velometer import timeseries as ts
from velometer.app.cache import PageCache, fingerprint
from velometer.db import SchemaError
from velometer.reconcile import short_commit
from velometer.report import charts
from velometer.report.csvexport import csv_preamble, csv_table
from velometer.report.data import HEADLINE_UNIT, KINDS, ReportData, open_readonly
from velometer.run import git_commit
from velometer.selection import report_selector

HERE = Path(__file__).parent
MAP_NAME = re.compile(r"^[a-z0-9_]+_(lau|fua)$")
EXPLANATIONS = Path("review") / "m3_timeseries.md"
METHODOLOGY = {"en": "methodology.md", "de": "methodology.de.md"}
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


def _num(v: float | int | None, spec: str = ",.1f") -> str:
    return "n/a" if v is None else format(v, spec)


def _md(text: str) -> Markup:
    return Markup(markdown.markdown(text, extensions=["tables", "fenced_code"]))


def _embed(spec: dict) -> dict:
    """The spec as embedded: `$schema` (a remote URL, never fetched) is dropped; vega-embed is
    told the mode instead."""
    return {k: v for k, v in spec.items() if k != "$schema"}


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


def create_app(db_path: Path, config_dir: Path, maps_dir: Path, docs_dir: Path) -> FastAPI:
    db_path, config_dir = Path(db_path), Path(config_dir)
    maps_dir, docs_dir = Path(maps_dir), Path(docs_dir)
    app = FastAPI(title="velometer", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=GZIP_MIN_BYTES, compresslevel=GZIP_LEVEL)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)  # outermost
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters["num"] = _num
    templates.env.filters["md"] = _md
    templates.env.filters["embed"] = _embed

    cache = PageCache()

    def fp(request: Request) -> tuple:
        """The request's fingerprint, computed on first use and kept on `request.state`."""
        if not hasattr(request.state, "fingerprint"):
            request.state.fingerprint = fingerprint(db_path, config_dir, docs_dir, maps_dir)
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

    def page(request: Request, name: str, **ctx) -> HTMLResponse:
        def build_footer() -> dict:
            sel = report_selector(config_dir)  # config only: the footer needs no database
            return {"classifier": sel.version, "config": sel.short_sha}

        footer = cache.get("footer", fp(request), build_footer)
        return templates.TemplateResponse(request, name, {"footer": footer, **ctx})

    def known(data: ReportData, city_id: str):
        city = next((c for c in data.cities() if c.id == city_id), None)
        if city is None:
            raise HTTPException(404, f"unknown city {city_id!r}")
        return city

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, data: Data):
        def build() -> dict:
            rows = []
            for c in data.cities():
                point = data.current(c.id, "lau")
                presets = {} if point is None else {p.preset: p.value for p in point.presets}
                rows.append(
                    {
                        "city": c,
                        "point": point,
                        "presets": presets,
                        "flags": len(data.flags(c.id, "lau")),  # the table is the LAU run
                    }
                )
            return {
                "rows": rows,
                "preset_label": data.preset_labels(),
                "preset_unit": data.preset_units(),
                "headline_unit": HEADLINE_UNIT,
                "headline": charts.headline_over_time(data),
                "rankings": charts.rankings_flip(data) if data.ranks() else None,
            }

        return page(request, "index.html", **cache.get("index", fp(request), build))

    @app.get("/city/{city_id}", response_class=HTMLResponse)
    async def city(request: Request, city_id: str, data: Data):
        def build() -> dict:
            return city_context(data, city_id)

        return page(request, "city.html", **cache.get(f"city:{city_id}", fp(request), build))

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
                map_kinds.append({"kind": kind, "label": kind.upper(), "url": f"/maps/{geojson}"})
            kinds.append(
                {
                    "kind": kind,
                    "point": data.current(city_id, kind),
                    "series": series,
                    "tiers": None
                    if series is None
                    else charts.tier_composition(data, city_id, kind),
                    "flags": flags,
                    "map": map_name if (maps_dir / map_name).is_file() else None,
                    "geojson": (maps_dir / geojson).is_file(),
                }
            )
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
        return {
            "city": c,
            "kinds": kinds,
            "headline": charts.headline_city(data, city_id),
            "reconcile": data.reconcile(city_id),
            "preset_label": data.preset_labels(),
            "preset_unit": data.preset_units(),
            "headline_unit": HEADLINE_UNIT,
            "tiers": ts.TIERS,
            "tiermap": tiermap if map_kinds else None,
        }

    def methodology(request: Request, lang: str) -> HTMLResponse:
        path = docs_dir / METHODOLOGY[lang]
        try:
            body = _md(path.read_text(encoding="utf-8"))
        except OSError:
            body = None
        return page(request, "methodology.html", lang=lang, body=body, file=path.name)

    @app.get("/methodology", response_class=HTMLResponse)
    async def methodology_en(request: Request):
        return methodology(request, "en")

    @app.get("/methodology/de", response_class=HTMLResponse)
    async def methodology_de(request: Request):
        return methodology(request, "de")

    def map_file(data: ReportData, name: str, suffix: str) -> Path:
        """The map file of a trusted city's run, else 404 (the city page and CSV do the same)."""
        path = maps_dir / f"{name}.{suffix}"
        if not MAP_NAME.fullmatch(name):
            raise HTTPException(404, "map not found")
        city_id = name.rsplit("_", 1)[0]
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

    @app.get("/data/{city_id}.csv")
    async def csv_city(request: Request, city_id: str, data: Data):
        return csv_response(request, data, city_id)

    return app
