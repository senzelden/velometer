"""FastAPI + Jinja app over the report query layer: index, city pages, methodology, maps, CSV.

Read-only: every request opens its own `mode=ro` connection (`open_readonly`) and closes it.
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
from velometer.db import SchemaError
from velometer.reconcile import short_commit
from velometer.report import charts
from velometer.report.csvexport import to_csv
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

    # async: the connection is made, used and closed on the event-loop thread (sqlite3
    # connections are bound to the thread that made them).
    async def report_data() -> AsyncIterator[ReportData]:
        try:
            conn = open_readonly(db_path)
        except FileNotFoundError as e:
            raise HTTPException(503, f"database not found: {db_path}") from e
        except SchemaError as e:
            raise HTTPException(503, str(e)) from e
        try:
            yield ReportData(conn, config_dir)
        finally:
            conn.close()

    Data = Annotated[ReportData, Depends(report_data)]

    def page(request: Request, name: str, **ctx) -> HTMLResponse:
        sel = report_selector(config_dir)  # config only: the footer needs no database
        footer = {"classifier": sel.version, "config": sel.short_sha}
        return templates.TemplateResponse(request, name, {"footer": footer, **ctx})

    def known(data: ReportData, city_id: str):
        city = next((c for c in data.cities() if c.id == city_id), None)
        if city is None:
            raise HTTPException(404, f"unknown city {city_id!r}")
        return city

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, data: Data):
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
        return page(
            request,
            "index.html",
            rows=rows,
            preset_label=data.preset_labels(),
            preset_unit=data.preset_units(),
            headline_unit=HEADLINE_UNIT,
            headline=charts.headline_over_time(data),
            rankings=charts.rankings_flip(data) if data.ranks() else None,
        )

    @app.get("/city/{city_id}", response_class=HTMLResponse)
    async def city(request: Request, city_id: str, data: Data):
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
        return page(
            request,
            "city.html",
            city=c,
            kinds=kinds,
            headline=charts.headline_city(data, city_id),
            reconcile=data.reconcile(city_id),
            preset_label=data.preset_labels(),
            preset_unit=data.preset_units(),
            headline_unit=HEADLINE_UNIT,
            tiers=ts.TIERS,
            tiermap=tiermap if map_kinds else None,
        )

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

    @app.get("/maps/{name}.png")
    async def map_png(name: str):
        path = maps_dir / f"{name}.png"
        if not MAP_NAME.fullmatch(name) or not path.is_file():
            raise HTTPException(404, "map not found")
        return FileResponse(path, media_type="image/png")

    @app.get("/maps/{name}.geojson")
    async def map_geojson(name: str):
        path = maps_dir / f"{name}.geojson"
        if not MAP_NAME.fullmatch(name) or not path.is_file():
            raise HTTPException(404, "map not found")
        return FileResponse(path, media_type="application/geo+json")

    def csv_response(data: ReportData, city_id: str | None) -> Response:
        try:
            text = to_csv(
                data.csv_rows(city_id),
                short_commit(git_commit()),
                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        except sqlite3.Error as e:
            raise HTTPException(503, f"database error: {e}") from e
        name = f"velometer-{city_id or 'all'}.csv"
        return Response(
            text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/data/all.csv")
    async def csv_all(data: Data):
        return csv_response(data, None)

    @app.get("/data/{city_id}.csv")
    async def csv_city(city_id: str, data: Data):
        known(data, city_id)
        return csv_response(data, city_id)

    return app
