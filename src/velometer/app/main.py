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
from collections.abc import AsyncIterator, Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from functools import partial
from html import unescape
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import markdown
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.exceptions import HTTPException as StarletteHTTPException

from velometer import i18n
from velometer import timeseries as ts
from velometer.app import cite as cite_model
from velometer.app import compare as cmp
from velometer.app import counts as counts_model
from velometer.app import plans_pages, urls
from velometer.app import story as story_model
from velometer.app.cache import PageCache, fingerprint
from velometer.app.names import country_name
from velometer.app.narrative import (
    Fallback,
    bracketed,
    data_ref_label,
    fb,
    fb_text,
    lang_attr,
    render_explainer,
    render_narrative,
    safe_url,
    source_field,
)
from velometer.app.organisations import org_of_sources, organisations_context
from velometer.app.regions import name_scroll_regions
from velometer.app.search import search_index
from velometer.app.series import series_payload
from velometer.app.sources import GROUPS, group_name, overview_column, source_anchor, source_rows
from velometer.app.tokens import theme_tokens
from velometer.config import ConfigError, PresetRanking, load_differences, load_site
from velometer.content.loader import (
    load_document,
    load_narratives,
    load_organisation_map,
    load_organisations,
    load_sources,
)
from velometer.content.models import ContentError, Explainer
from velometer.content.translate import walk
from velometer.db import SchemaError, subarea_names
from velometer.i18n import LANGS, Lang
from velometer.plans.models import load_plans, load_report_notes_de
from velometer.reconcile import short_commit
from velometer.report import change as change_report
from velometer.report import charts
from velometer.report.csvexport import (
    SUBAREA_CSV_COLUMNS,
    csv_preamble,
    csv_table,
)
from velometer.report.data import KINDS, ReportData, headline_unit, open_readonly
from velometer.report.differences import difference_rows
from velometer.run import git_commit
from velometer.selection import report_selector

HERE = Path(__file__).parent
# a tier map: <city>_<kind>, its German image <city>_<kind>.de (PNG only)
MAP_NAME = re.compile(r"^[a-z0-9_]+_(lau|fua)(\.de)?$")
# a change map: <city>_change_<from>_<to>, each end a 1 January snapshot date or `current`
CHANGE_NAME = re.compile(
    r"^([a-z0-9_]+)_change_(\d{4}-\d{2}-\d{2}|current)_(\d{4}-\d{2}-\d{2}|current)$"
)
EXPLANATIONS = Path("review") / "m3_timeseries.md"
EXPLANATIONS_DE = ts.german_explanations(EXPLANATIONS)  # review/m3_timeseries.de.md
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
# The city page's tabs: key and path suffix; a tab's label is the catalogue's `city.tab.<key>`.
# Counts only for a city with counter data (ReportData.counter_cities), Bezirke only for a city
# with subareas.
TABS = [
    ("story", ""),
    ("time", "/time"),
    ("tiers", "/tiers"),
    ("figures", "/figures"),
    ("counts", "/counts"),
    ("bezirke", "/bezirke"),
]
COUNTERS_TEXT = "counters.yaml"  # content/: what the counters record, under the Counts tab
UNITS = {"pct": "%"}
CLAUSE_END = re.compile(r"[;:]|\.\s| [-–—] ")
log = logging.getLogger(__name__)
OURS_MARK = re.compile(r"^\s*ours:\s*|,\s*(our OSM data|unsere OSM-Daten)(?=\s*(,|$))", re.I)
# A 404 under these prefixes is not a page a reader opens: it stays FastAPI's JSON; any other 404
# is the HTML "page not found" page (the static edition's 404.html).
NOT_PAGE_PREFIXES = ("/data/", "/maps/", "/static/", "/de/data/")


def set_lang(lang: Lang):
    """The route dependency that gives a request its page language (M12 spec decision 1): the
    language comes from the route a page is registered at, never from reading the path (a base
    path such as `/velometer/` would shift it)."""

    def dependency(request: Request) -> None:
        request.state.lang = lang

    return dependency


def register_pages(app: FastAPI, path: str, endpoint, **kw) -> None:
    """A page at `path` (English) and at `/de` + `path` (German), the same handler: each route
    sets `request.state.lang` through its own dependency."""
    kw.setdefault("response_class", HTMLResponse)
    for lang in LANGS:
        prefix = "" if lang == "en" else urls.DE_PREFIX
        app.add_api_route(
            prefix + path, endpoint, methods=["GET"], dependencies=[Depends(set_lang(lang))], **kw
        )


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


def _num(v: float | int | None, spec: str = ",.1f", lang: Lang = "en") -> str:
    return i18n.fmt(v, spec, lang)


def _day(d: date | str | None, lang: Lang = "en") -> str:
    """A page date (a date or an ISO string): ISO in English, in words in German."""
    if d is None or d == "":
        return ""
    return i18n.iso_day(d, lang) if isinstance(d, str) else i18n.day(d, lang)


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


MD_HEADING = re.compile(r"^(#{2,3}) +(.+?) *#*$", re.M)  # the h2/h3 lines of a markdown file


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"


def heading_ids(text: str) -> list[tuple[str, str]]:
    """(level, id) of each h2/h3 heading of markdown `text`, in order: the heading's slug, made
    unique with `-2`, `-3`, …. Code blocks are skipped (a `## ` line in a fence is no heading)."""
    seen: dict[str, int] = {}
    out = []
    for m in MD_HEADING.finditer(re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)):
        slug = _slug(m.group(2))
        seen[slug] = seen.get(slug, 0) + 1
        out.append((m.group(1), slug if seen[slug] == 1 else f"{slug}-{seen[slug]}"))
    return out


class _HeadingIds(markdown.treeprocessors.Treeprocessor):
    def __init__(self, md, ids: list[str]):
        super().__init__(md)
        self.ids = ids

    def run(self, root):
        for el, slug in zip(
            (e for e in root.iter() if e.tag in ("h2", "h3")), self.ids, strict=False
        ):
            el.set("id", slug)


class _Ids(markdown.Extension):
    def __init__(self, ids: list[str]):
        super().__init__()
        self.ids = ids

    def extendMarkdown(self, md):
        md.treeprocessors.register(_HeadingIds(md, self.ids), "heading_ids", 5)


def methodology_html(text: str, english: str) -> Markup:
    """The methodology page body of `text`, its h2/h3 headings carrying the ids of the English
    file `english`'s headings at the same position, so a link `/methodology#id` lands on the
    same section in both editions (M13 Task 13b). Ids are set only when both files have the same
    heading outline (a test holds the shipped files to it)."""
    own, en = heading_ids(text), heading_ids(english)
    same = [lvl for lvl, _ in own] == [lvl for lvl, _ in en]
    return _md(text, ids=[slug for _, slug in en] if same else [])


def _md(text: str, ids: list[str] | None = None) -> Markup:
    extensions = ["tables", "fenced_code", _EscapeHtml()] + ([_Ids(ids)] if ids else [])
    html = markdown.markdown(text, extensions=extensions)
    return Markup(
        ALIGN_STYLE.sub(
            lambda m: ' class="num"' if m.group(1) == "right" else f' class="align-{m.group(1)}"',
            html,
        )
    )


def _stack_table(html: Markup) -> Markup:
    """A rendered markdown table made a stacking table: class `stack`, and `data-label` on each
    body cell, equal to its column's header text (the same rule the templates follow)."""
    text = str(html)
    thead = re.search(r"<thead>.*?</thead>", text, re.S)
    heads = [
        " ".join(unescape(re.sub(r"<[^>]+>", "", h)).split())  # text, escaped once below
        for h in re.findall(r"<th\b[^>]*>(.*?)</th>", thead.group(0) if thead else "", re.S)
    ]

    def row(m: re.Match) -> str:
        cells = iter(heads + [""] * 64)
        return re.sub(
            r"<td\b",
            lambda _: f'<td data-label="{escape(next(cells))}"',
            m.group(0),
        )

    head, sep, body = text.partition("</thead>")
    body = re.sub(r"<tr>.*?</tr>", row, body, flags=re.S)
    return Markup((head + sep + body).replace("<table>", '<table class="stack">', 1))


def _host(url: str) -> str:
    host = urlparse(url).hostname or url
    return host.removeprefix("www.")


def _clause(note: str, limit: int = 90) -> str:
    """The first clause of a figure's note: what tells rows of one source apart."""
    first = CLAUSE_END.split(note.strip(), 1)[0].strip()
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


# The provenance prefix of an external figure's CSV note and how a reader is told it.
NOTE_PREFIX = re.compile(r"^\s*(primary-by-agency|primary|secondary)\b\s*(\([^)]*\))?\s*[;:]?\s*")


def _note_prefix(prefix: str, lang: Lang) -> str:
    if prefix == "primary":
        return i18n.t(lang, "note.prefix.primary")
    if prefix == "secondary":
        return i18n.t(lang, "note.prefix.secondary")
    return i18n.t(lang, "note.prefix.primary_by_agency")


def _note_clause(note: str, lang: Lang = "en") -> str:
    """A figure's note as the Figures tab shows it: the CSV provenance prefix (`primary`,
    `secondary`, `primary-by-agency`) in words, then the first clause of the rest."""
    m = NOTE_PREFIX.match(note or "")
    if not m:
        return _clause(note or "")
    head = _note_prefix(m.group(1), lang) + (f" {m.group(2)}" if m.group(2) else "")
    rest = note[m.end() :]
    return f"{head}: {_clause(rest)}" if rest.strip() else head


def _when(label: str, osm_timestamp: str | None = None, lang: Lang = "en") -> str:
    """A series label as the reader sees it: a year is "Jan <year>" (1 January snapshots), the
    current run its snapshot month ("Oct 2026")."""
    if label != ts.CURRENT:
        return i18n.january(int(label), lang)
    if osm_timestamp and re.match(r"^\d{4}-\d{2}", osm_timestamp):
        return i18n.month_year(osm_timestamp, lang)
    return i18n.t(lang, "time.current")


class LazyData:
    """The per-request ReportData, opened on first attribute access: a page-cache hit never
    touches the database. A missing database or a schema mismatch is a 503 at that access."""

    def __init__(self, db_path: Path, config_dir: Path, lang: Lang = "en"):
        self._db_path, self._config_dir = db_path, config_dir
        self._conn: sqlite3.Connection | None = None
        self._data: ReportData | None = None
        self._lang: Lang = lang

    def with_lang(self, lang: Lang) -> "LazyData | ReportData":
        """The data in `lang`: itself when it is in `lang`, else a ReportData copy sharing its
        connection (opened now). Never changes this object: the request keeps its language."""
        if lang == self._lang:
            return self
        return self._open().with_lang(lang)

    def __getattr__(self, name: str):
        if name.startswith("_"):  # private names (and dunder probes) are not ReportData's API
            raise AttributeError(name)
        data = self._open()
        if name not in ReportData.__dict__ and name not in vars(data):
            raise AttributeError(f"ReportData has no attribute {name!r}")
        return getattr(data, name)

    def _open(self) -> ReportData:
        if self._data is None:
            try:
                self._conn = open_readonly(self._db_path)
            except FileNotFoundError as e:
                raise HTTPException(503, f"database not found: {self._db_path}") from e
            except SchemaError as e:
                raise HTTPException(503, str(e)) from e
            self._data = ReportData(self._conn, self._config_dir, self._lang)
        return self._data

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
    # Every page URL that leaves the app goes through `u`, bound to the page's language (`us`),
    # and every data, map and static URL through `data_u`: templates call them on each internal
    # href, src and action at the point they write it; values a script reads from a JSON config
    # (map URLs, the Stories steps' links) get them here, since the script uses them as they are.
    us: dict[Lang, Callable[[str], str]] = {
        lang: urls.make_u(app.state.base_path, lang) for lang in LANGS
    }
    data_u = urls.make_data_u(app.state.base_path)
    tokens = theme_tokens((HERE / "static" / "app.css").read_text(encoding="utf-8"))
    app.state.site = load_site(config_dir)
    commit = static_edition["commit"] if static_edition else short_commit(git_commit())

    def _templates(lang: Lang) -> Jinja2Templates:
        """The templates of one page language: its `u` and `t`, the shared globals and filters."""
        templates = Jinja2Templates(directory=HERE / "templates")
        env = templates.env
        env.globals["lang"] = lang
        env.globals["u"] = us[lang]
        env.globals["u_in"] = lambda other, path: us[other](path)
        env.globals["data_u"] = data_u
        env.globals["t"] = partial(i18n.t_markup, lang)
        env.globals["t_in"] = i18n.t_markup
        env.globals["base_path"] = app.state.base_path
        # inside a double-quoted attribute the policy's single quotes need no escaping
        env.globals["csp_meta"] = Markup(str(escape(csp_meta(CSP))).replace("&#39;", "'"))
        env.globals["static_edition"] = static_edition
        env.globals["site"] = app.state.site
        env.globals["cite_text"] = partial(cite_model.cite_text, lang=lang)
        # the `#ui-strings` block static/js/strings.js reads: the `js.*` strings and month names
        env.globals["js_strings"] = i18n.js_strings
        # an English fallback on a German page: `fb(x)` marks the element showing x, `fb_text(x)`
        # wraps x where it sits inside other text
        env.globals["fb"] = fb
        env.globals["fb_text"] = fb_text
        # a name in its own language (an organisation, a counter publisher, a plan title)
        env.globals["lang_attr"] = lang_attr
        # its bracketed form in another language, in its own `lang` (review 10, I1)
        env.globals["bracketed"] = bracketed
        # a data reference's label: always the English one, in `lang="en"` on a German page
        env.globals["data_ref_label"] = partial(data_ref_label, lang=lang)
        # a source's publisher or title: on a German page its German sibling, original in `lang`
        env.globals["source_field"] = partial(source_field, lang=lang)
        # chart downloads (M11): the light/dark colour tokens, so a dark page can be drawn light,
        # and the commit the source line names (the export's build commit, else the checkout's)
        env.globals["theme_tokens"] = tokens
        env.globals["build_commit"] = commit
        env.filters["cite_json"] = cite_model.json_fields
        env.filters["num"] = lambda v, spec=",.1f": _num(v, spec, lang)
        env.filters["signed"] = lambda v, decimals=1: i18n.signed(v, lang, decimals)
        env.filters["tone"] = i18n.tone
        env.filters["pct"] = lambda v, decimals=1, signed=False: i18n.percent(
            v, lang, decimals, signed
        )
        # not `trim`: Jinja's own trim (whitespace) is in use
        env.filters["trimmed"] = lambda v: i18n.number_trimmed(v, lang)
        env.filters["day"] = lambda d: _day(d, lang)
        env.filters["md"] = _md
        env.filters["stack_table"] = _stack_table
        env.filters["when"] = lambda label, osm=None: _when(label, osm, lang)
        env.filters["http_url"] = safe_url
        env.filters["host"] = _host
        # an English fallback note (German page) is cut in English: `note | clause('en')`
        env.filters["clause"] = lambda note, in_lang=None: _note_clause(note, in_lang or lang)
        env.filters["unit"] = lambda unit: UNITS.get(unit, unit)
        # a preset label says ", our OSM data" (a gap row's basis may follow it); a Figures row's
        # "Ours" column says it already
        env.filters["strip_ours"] = lambda v: OURS_MARK.sub("", v or "")
        _respond = templates.TemplateResponse

        def respond(*args, **kwargs):
            """Every rendered page, with its sideways-scrolling regions keyboard-reachable."""
            resp = _respond(*args, **kwargs)
            resp.body = name_scroll_regions(resp.body.decode(), lang).encode()
            resp.headers["content-length"] = str(len(resp.body))
            return resp

        templates.TemplateResponse = respond  # type: ignore[method-assign]
        return templates

    TEMPLATES = {lang: _templates(lang) for lang in LANGS}

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
    async def report_data(request: Request) -> AsyncIterator[LazyData]:
        # a page route set the language; a data route has none and is English
        lazy = LazyData(db_path, config_dir, getattr(request.state, "lang", "en"))
        try:
            yield lazy
        finally:
            lazy.close()

    Data = Annotated[ReportData, Depends(report_data)]

    def by_country(data: ReportData) -> list[dict]:
        """The trusted cities grouped by country name, both sorted by name."""
        groups: dict[str, list] = {}
        for c in data.cities():
            groups.setdefault(country_name(c.country_iso2, data.lang), []).append(c)
        return [
            {
                "country": name,
                "iso2": cs[0].country_iso2,
                "cities": sorted(cs, key=lambda c: c.name),
            }
            for name, cs in sorted(groups.items())
        ]

    def named(payload: dict, data: ReportData) -> dict:
        """The series payload (English, one shared file) with the city names of `data`'s
        language, for the tables and steps a page builds from it."""
        if data.lang == "en":
            return payload
        names = {c.id: c.name for c in data.cities()}
        cities = {i: {**c, "name": names.get(i, c["name"])} for i, c in payload["cities"].items()}
        return {**payload, "cities": cities}

    def cite_rows(request: Request, data: ReportData) -> cite_model.RunRows | None:
        """The run rows citations read, built once per fingerprint (None without a database)."""
        try:
            return cache.get("cite:rows", fp(request), lambda: cite_model.RunRows.of(data))
        except HTTPException:
            return None

    def cite_for(request: Request, data: ReportData | None, path: str | None = None):
        """`cite_for(title, city=…, kind=…)` / `cite_for(title, cities=[…])` for a template:
        the CiteFields of that figure in the page's language, None without a run (the template
        then shows no Cite). `path` is the page's path without the base path (the browser adds
        the base)."""
        rows = None if data is None else cite_rows(request, data)
        where = request.url.path if path is None else path
        lang = request.state.lang

        shared: dict = {}  # a page's figures share one run: built once, the title varies

        def make(title, city=None, cities=None, kind="lau", path=None, both=None):
            """`both`: the title of a city figure drawn from its LAU and FUA runs; with both
            runs present it cites both under that title, else the `kind` run under `title`."""
            if rows is None:
                return None
            key = (city, kind, None if cities is None else tuple(cities))
            if both is not None and city is not None:
                if ("both", city) not in shared:
                    shared[("both", city)] = cite_model.fields_for_city_runs(
                        rows, city, "", where, lang=lang
                    )
                if shared[("both", city)] is not None:
                    key, title = ("both", city), both
            if key not in shared:
                if city is not None:
                    shared[key] = cite_model.fields_for_city(rows, city, "", where, kind, lang)
                else:
                    ids = cities if cities is not None else rows.city_ids()
                    shared[key] = cite_model.fields_for_cities(
                        rows, list(ids), "", where, kind, lang
                    )
            base = shared[key]
            # a title built with `t()` in a template is Markup: the citation wants its plain text
            title = str(title.unescape()) if isinstance(title, Markup) else title
            return None if base is None else replace(base, title=title, path=path or where)

        return make

    def page(
        request: Request,
        name: str,
        active: str,
        data: ReportData | None = None,
        status_code: int = 200,
        **ctx,
    ) -> HTMLResponse:
        def build_footer() -> dict:
            sel = report_selector(config_dir)  # config only: the footer needs no database
            return {"classifier": sel.version, "config": sel.short_sha}

        lang = request.state.lang
        footer = cache.get(f"footer:{lang}", fp(request), build_footer)
        nav = None  # the Cities menu; a page without a database still renders, linking /cities
        if data is not None:
            try:
                nav = cache.get(f"nav:{lang}", fp(request), lambda: by_country(data))
            except HTTPException:
                nav = None
        return TEMPLATES[lang].TemplateResponse(
            request,
            name,
            {
                "footer": footer,
                "nav_groups": nav,
                "active": active,
                "cite_for": cite_for(request, data),
                # the page's route path without the language: its twins and the switch use it
                "here": urls.strip_lang(request.url.path),
                **ctx,
            },
            status_code=status_code,
        )

    @app.exception_handler(StarletteHTTPException)
    async def not_found_page(request: Request, exc: StarletteHTTPException) -> Response:
        """A 404 for a page path is the HTML "page not found" page (layout, nav, a way home);
        any other error, and a 404 for data, maps or static files, is FastAPI's JSON."""
        if exc.status_code != 404 or request.url.path.startswith(NOT_PAGE_PREFIXES):
            return await http_exception_handler(request, exc)
        # no route ran: the language is the `/de` prefix's (the page shows both anyway)
        request.state.lang = "de" if request.url.path.split("/")[1:2] == ["de"] else "en"
        lazy = LazyData(db_path, config_dir, request.state.lang)
        try:
            return page(request, "404.html", "", lazy, status_code=404, here="/")
        finally:
            lazy.close()

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
            "country": country_name(c.country_iso2, data.lang),
            "point": point,
            "now": now,
            "now_label": _when(ts.CURRENT, point.osm_timestamp, data.lang) if point else None,
            "first": None if first is None else first.headline,
            "first_label": (
                None if first is None else _when(first.label, first.osm_timestamp, data.lang)
            ),
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
        anchors = {
            r.id: source_anchor(r.recomputes if isinstance(r, PresetRanking) else r.source)
            for r in data.report_config.rankings
        }
        return {
            "columns": columns,
            "anchors": anchors,
            "rows": [{"id": i, "name": names.get(i, i), "cells": cells[i]} for i in order],
            "notes": [
                f"{r.label_in(data.lang)}: {n}"
                for r in data.report_config.rankings
                if (n := r.note_in(data.lang))
            ],
            "dagger": any(c["dagger"] for row in cells.values() for c in row.values()),
        }

    async def index(request: Request, data: Data):
        payload = cache.get(
            "series", fp(request), lambda: series_payload(data, docs_dir / EXPLANATIONS)
        )

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
                "preset_anchor": {p: source_anchor(s) for p, s in data.preset_sources().items()},
                "preset_column": {p: overview_column(p) for p in data.preset_sources()},
                "preset_unit": data.preset_units(),
                "headline_unit": headline_unit(data.lang),
                "rankings": rankings_table(data),
                # the values the all-cities chart draws: headline per city and snapshot, LAU
                "chart_table": cmp.table_model(
                    named(payload, data),
                    cmp.CompareState(c=list(payload["cities"]), b="lau"),
                    data.lang,
                ),
            }

        ctx = cache.get(f"index:{request.state.lang}", fp(request), build)
        return page(request, "index.html", "overview", data, **ctx)

    register_pages(app, "/", index)

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
                    "headline_unit": headline_unit(data.lang)}  # fmt: skip

        ctx = cache.get(f"cities:{request.state.lang}", fp(request), build)
        return page(request, "cities.html", "cities", data, **ctx)

    register_pages(app, "/cities", cities)

    @app.get("/data/series.json")
    async def series_json(request: Request, data: Data):
        payload = cache.get(
            "series", fp(request), lambda: series_payload(data, docs_dir / EXPLANATIONS)
        )
        return JSONResponse(payload)

    @app.get("/data/search.json")
    async def search_json(request: Request, data: Data):
        payload = cache.get(
            "search:en", fp(request), lambda: search_index(data, config_dir, content_dir)
        )
        return JSONResponse(payload)

    @app.get("/de/data/search.json", dependencies=[Depends(set_lang("de"))])
    async def search_json_de(request: Request, data: Data):
        """The one per-language data file: the German pages' search index."""
        payload = cache.get(
            "search:de", fp(request), lambda: search_index(data, config_dir, content_dir, "de")
        )
        return JSONResponse(payload)

    def document(path: Path, lang: Lang) -> tuple[Explainer | None, frozenset[str]]:
        """An explainer-shaped page in `lang` and its walk paths still English. ContentError for
        the English file; a broken German translation is logged and the English page shown."""
        doc = load_document(path)
        if lang != "de" or doc is None:
            return doc, frozenset()
        try:
            merged, fallback = load_document(path, "de")
        except ContentError as e:
            log.error("German content could not be loaded, shown in English: %s", e)
            return doc, frozenset(p for p, _ in walk(doc))
        return merged, fallback.get(path.stem, frozenset())

    def log_fallback(lang: Lang, fallback: dict[str, frozenset[str]]) -> None:
        for stem, paths in sorted(fallback.items()):
            if paths:
                i18n.warn_once(lang, f"content:{stem}", "content %s: %d strings shown in English"
                               " on %s pages", stem, len(paths), lang)  # fmt: skip

    def content(lang: Lang = "en"):
        """(narratives, sources, explainer, errors, fallback) of the content dir, the
        narratives and the explainer in `lang`. `errors` maps what could not be read to its
        message: "*" for the source registry (nothing renders without it), "explainer", or a
        narrative's file stem (a German file's under "de/<stem>": its English is shown). Each is
        logged and shown as a note, never a 500; one broken narrative leaves the others readable.
        `fallback` maps a narrative's stem (and "explainer") to its walk paths still English."""

        def build():
            try:
                sources = load_sources(content_dir / "sources")
            except ContentError as e:
                log.error("content could not be loaded: %s", e)
                return {}, {}, None, {"*": str(e)}, {}
            errors: dict[str, str] = {}
            fallback: dict[str, frozenset[str]] = {}
            if lang == "de":
                narratives, fallback = load_narratives(
                    content_dir / "narratives", errors=errors, lang="de"
                )
            else:
                narratives = load_narratives(content_dir / "narratives", errors=errors)
            try:
                explainer, fallback["explainer"] = document(content_dir / "explainer.yaml", lang)
            except ContentError as e:
                explainer, errors["explainer"] = None, str(e)
            for msg in errors.values():
                log.error("content could not be loaded: %s", msg)
            log_fallback(lang, fallback)
            return narratives, sources, explainer, errors, fallback

        return build

    def content_of(request: Request):
        """The content in the request's page language, built once per fingerprint."""
        lang = request.state.lang
        return cache.get(f"content:{lang}", fp(request), content(lang))

    def content_error(errors: dict[str, str], key: str) -> str | None:
        """The load error that blanks `key` (a narrative stem or "explainer"), if any."""
        return errors.get("*") or errors.get(key)

    def narrative_of(request: Request, city_id: str):
        """The city's rendered narrative (None without one) and a note about unreadable content."""
        narratives, sources, _, errors, fallback = content_of(request)

        def build():
            n = narratives.get(city_id)
            if n is None:
                return None
            lang = request.state.lang
            return render_narrative(n, sources, lang, fallback.get(city_id, frozenset()))

        return cache.get(
            f"narrative:{city_id}:{request.state.lang}", fp(request), build
        ), content_error(errors, city_id)

    def organisations(request: Request) -> tuple[dict, dict[str, str], dict[str, frozenset]]:
        """(profiles, errors, fallback) of content/organisations in the page language; a broken
        profile is a note, not a 500. `fallback`: per profile id its walk paths still English."""

        lang = request.state.lang

        def build():
            errors: dict[str, str] = {}
            fallback: dict[str, frozenset[str]] = {}
            try:
                if lang == "de":
                    orgs, fallback = load_organisations(
                        content_dir / "organisations", errors=errors, lang="de"
                    )
                else:
                    orgs = load_organisations(content_dir / "organisations", errors=errors)
            except ContentError as e:  # pragma: no cover - the loader records per file
                orgs, errors["*"] = {}, str(e)
            for msg in errors.values():
                log.error("organisation profile could not be loaded: %s", msg)
            log_fallback(lang, fallback)
            # a broken German profile ("de/<id>") shows its English: not a broken profile
            broken = {k: v for k, v in errors.items() if not k.startswith("de/")}
            return orgs, broken, fallback

        return cache.get(f"organisations-raw:{lang}", fp(request), build)

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

    def report_notes_de(rows) -> dict[str, str]:
        """The German report-row notes; an unreadable file leaves every note English."""
        try:
            return load_report_notes_de(config_dir / "plans", rows)
        except ConfigError as e:
            log.error("German report notes could not be loaded: %s", e)
            return {}

    def figures_context(data: ReportData, city_id: str, profiles: set[str]) -> dict:
        try:
            cfg = load_differences(config_dir / "differences.yaml")
            rows = difference_rows(data, city_id, cfg, data.lang)
            cfg = cfg.localised(data.lang)
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
        _, sources, _, errors, _ = content_of(request)

        def build() -> dict:
            cfg, cfg_error = counts_model.counters_config(config_dir)
            entry = next((e for e in cfg.cities if e.city == city_id), None) if cfg else None
            lau = data.series(city_id, "lau")
            ctx = counts_model.counts_context(data, city_id, entry, lau.points if lau else [])
            try:
                (text, english), text_error = document(content_dir / COUNTERS_TEXT, data.lang), None
            except ContentError as e:
                log.error("counters text could not be loaded: %s", e)
                text, english, text_error = None, frozenset(), str(e)
            doc = (
                None
                if text is None or errors.get("*")
                else render_explainer(text, sources, data.lang, english)
            )
            ctx["site_map"] = (
                None
                if ctx["site_map"] is None
                else ctx["site_map"]
                | {"tiles": OSM_TILES, "tile_class": TILE_CLASS, "links": OSM_LINKS}
            )
            return ctx | {"doc": doc, "text_error": text_error, "config_error": cfg_error}

        return cache.get(f"counts:{city_id}:{request.state.lang}", fp(request), build)

    def city_page(request: Request, city_id: str, tab: str, data: ReportData) -> HTMLResponse:
        ctx = cache.get(
            f"city:{city_id}:{request.state.lang}", fp(request), lambda: city_context(data, city_id)
        )
        if tab == "bezirke" and not ctx["bezirke"]:
            raise HTTPException(404, f"{city_id!r} has no Bezirke")
        if tab == "counts" and not ctx["has_counts"]:
            raise HTTPException(404, f"{city_id!r} has no counter data")
        extra: dict = {}
        if tab == "figures":
            profiles = set(organisations(request)[0])
            extra = cache.get(
                f"figures:{city_id}:{request.state.lang}",
                fp(request),
                lambda: figures_context(data, city_id, profiles),
            )
        nar, note = narrative_of(request, city_id)
        role = {"story": "story", "figures": "figures"}.get(tab)
        cited_sources, cited_refs = nar.cited(nar.of_role(role)) if nar and role else ([], [])
        if tab == "counts":
            extra = {"counts": counts_context(request, data, city_id)}
            nar = extra["counts"]["doc"]  # the tab cites the counters text's sources
            cited_sources = [] if nar is None else sorted(nar.sources.items())
            cited_refs = [] if nar is None else sorted(nar.refs.items())
        lang = request.state.lang
        label = i18n.t(lang, f"city.tab.{tab}")  # plain: the <title>
        label_html = i18n.t_markup(lang, f"city.tab.{tab}")  # the crumb and the tab links: marks
        tabs = [
            {
                "key": k,
                "label_html": i18n.t_markup(lang, f"city.tab.{k}"),
                "href": f"/city/{city_id}{suffix}",
            }
            for k, suffix in TABS
            if (k != "bezirke" or ctx["bezirke"]) and (k != "counts" or ctx["has_counts"])
        ]
        return page(
            request, f"city/{tab}.html", "city", data, **ctx, **extra, tab=tab, tab_label=label,
            tabs=tabs, tab_label_html=label_html, nar=nar, content_error=note,
            cited_sources=cited_sources, cited_refs=cited_refs,
        )  # fmt: skip

    async def compare(request: Request, data: Data):
        payload = cache.get(
            "series", fp(request), lambda: series_payload(data, docs_dir / EXPLANATIONS)
        )
        known_ids = list(payload["cities"])
        state = cmp.parse_compare(request.url.query, known_ids, cmp.METRICS)
        lang = request.state.lang
        table = cmp.table_model(named(payload, data), state, lang)
        quick = [
            {"key": k, "label": i18n.t(lang, f"compare.group.{k}"),
             "ids": cmp.quick_set_ids(k, known_ids)}
            for k in cmp.QUICK_SETS
        ]  # fmt: skip
        unit = headline_unit(lang)
        info = cmp.metric_info(unit, data.preset_units(), population_years(data), lang)
        views = {v: i18n.t(lang, f"compare.view.{v}") for v in cmp.VIEW_IDS}
        config = {
            "cities": known_ids,
            "metric_order": list(cmp.METRICS),  # tojson sorts the keys of `metrics`
            "metrics": info,
            "quick": cmp.QUICK_SETS,
            "views": views,
            "headline_unit": unit,
        }
        rows = cite_rows(request, data)
        # per boundary kind: the browser rebuilds the Cite when the boundary changes
        config["cite_runs"] = {
            kind: {} if rows is None else rows.runs(known_ids, kind) for kind in ("lau", "fua")
        }
        names = [r["name"] for r in table["rows"]]
        heading = (
            cmp.counter_title(info[state.m]["label"], lang)
            if state.m == cmp.COUNTER_METRIC
            else f"{info[state.m]['label']} \u00b7 "
            + i18n.t(lang, "unit.lau" if state.b == "lau" else "unit.fua")
            + (f" \u00b7 {i18n.t(lang, 'compare.index_heading')}" if state.mode == "index" else "")
        )
        return page(
            request, "compare.html", "compare", data, state=state, table=table, quick=quick,
            compare_cite=cite_for(request, data)(
                i18n.t(lang, "cite.title.compare", heading=heading, cities=", ".join(names)),
                cities=[r["id"] for r in table["rows"]],
                kind=state.b, path=urls.with_lang("/compare", lang),
            ),
            groups=by_country(data), metrics=info, views=views, config=config,
            href=lambda **changes: "/compare?" + cmp.serialize(state, **changes),
            foot=cmp.footnote(state.m, unit, lang),
            counter={"title": partial(cmp.counter_title, lang=lang),
                     "context": i18n.t(lang, "counts.context")},
        )  # fmt: skip

    register_pages(app, "/compare", compare)

    async def city_panel(request: Request, city_id: str, data: Data):
        """The Compare slide-over: a fragment (no layout), fetched by panel.js. A direct visit
        shows the same fragment; the full page is /city/<id>."""
        ctx = cache.get(
            f"city:{city_id}:{request.state.lang}", fp(request), lambda: city_context(data, city_id)
        )
        # a copy: TemplateResponse adds `request` to the dict it is given, and this one is cached
        # (a tab page spreads it next to its own `request=`)
        lang = request.state.lang
        return TEMPLATES[lang].TemplateResponse(
            request,
            "city/panel.html",
            {**ctx, "cite_for": cite_for(request, data, urls.with_lang(f"/city/{city_id}", lang))},
        )

    register_pages(app, "/city/{city_id}/panel", city_panel)

    async def city(request: Request, city_id: str, data: Data):
        return city_page(request, city_id, "story", data)

    register_pages(app, "/city/{city_id}", city)

    async def city_tab(request: Request, city_id: str, tab: str, data: Data):
        if tab not in {k for k, suffix in TABS if suffix}:
            raise HTTPException(404, f"unknown tab {tab!r}")
        return city_page(request, city_id, tab, data)

    register_pages(app, "/city/{city_id}/{tab}", city_tab)

    def story_context(
        data: ReportData, payload: dict, n, sources, lang: Lang, fallback=frozenset()
    ) -> dict:
        """The Stories page: the combined narrative's sections with the chart step each names
        (`fallback`: its walk paths still English)."""
        nar = render_narrative(n, sources, lang, fallback)
        metrics = cmp.metric_info(
            headline_unit(lang), data.preset_units(), population_years(data), lang
        )
        steps = {}
        for step, spec in STEP_COMPARE.items():
            built = (
                story_model.bezirke_step(payload, STORY_CITY, spec["href"], lang)
                if "href" in spec
                else story_model.lines_step(payload, spec, metrics, lang)
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

        def heading_of(step: str):
            return next(s["sec"].heading for s in story if s["step"] == step)

        config = {
            step: {k: v for k, v in built.items() if k != "table"}
            | {
                "href": us[lang](built["href"]),  # story.js sets it as the Explore link
                # a step section may have no heading: the eyebrow then names the chart
                "heading": heading_of(step) or built.get("title") or "",
                "n": order.index(step) + 1,
                "of": len(order),
            }
            # an English fallback heading (German page): story.js marks it lang="en"
            | ({"heading_fallback": True} if isinstance(heading_of(step), Fallback) else {})
            for step, built in steps.items()
            if step in order
        }
        sources_cited, refs_cited = nar.cited(nar.sections)
        return {
            "nar": nar, "story": story, "figures": figures, "steps": steps, "config": config,
            "first_step": order[0] if order else None,  # the chart's table until a step is read
            "cited_sources": sources_cited, "cited_refs": refs_cited,
        }  # fmt: skip

    async def stories(request: Request, data: Data):
        payload = cache.get(
            "series", fp(request), lambda: series_payload(data, docs_dir / EXPLANATIONS)
        )
        narratives, sources, _, errors, fallback = content_of(request)
        error = content_error(errors, "combined")

        def build():
            n = narratives.get("combined")
            if n is None:
                return None
            english = fallback.get("combined", frozenset())
            return story_context(data, named(payload, data), n, sources, request.state.lang,
                                 english)  # fmt: skip

        ctx = cache.get(f"stories:{request.state.lang}", fp(request), build) or {}
        return page(request, "stories.html", "stories", data, content_error=error, **ctx)

    register_pages(app, "/stories", stories)

    async def differences(request: Request, data: Data):
        _, sources, explainer, errors, fallback = content_of(request)
        error = content_error(errors, "explainer")

        def build():
            english = fallback.get("explainer", frozenset())
            return (
                None
                if explainer is None
                else render_explainer(explainer, sources, request.state.lang, english)
            )

        doc = cache.get(f"differences:{request.state.lang}", fp(request), build)
        try:
            cfg = load_differences(config_dir / "differences.yaml").localised(request.state.lang)
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

    register_pages(app, "/differences", differences)

    async def organisations_page(request: Request, data: Data):
        _, sources, _, errors, _ = content_of(request)
        orgs, org_errors, org_fallback = organisations(request)

        def build() -> dict:
            plans, rows, _ = plans_config()
            try:
                diffs = load_differences(config_dir / "differences.yaml").localised(
                    request.state.lang
                )
                labels, source_names = {d.id: d.label for d in diffs.dimensions}, diffs.source_names
            except (ConfigError, OSError):
                labels, source_names = {}, {}
            names = {c.id: c.name for c in data.cities()}
            return {
                "profiles": organisations_context(
                    orgs,
                    sources,
                    org_mapping(),
                    plans,
                    rows,
                    names,
                    source_names,
                    request.state.lang,
                    org_fallback,
                ),
                "dimension_labels": labels,
            }

        ctx = cache.get(f"organisations:{request.state.lang}", fp(request), build)
        return page(
            request, "organisations.html", "organisations", data, **ctx,
            content_error=errors.get("*"), broken=sorted(org_errors),
        )  # fmt: skip

    register_pages(app, "/organisations", organisations_page)

    async def sources_page(request: Request, data: Data):
        def build() -> dict:
            try:
                rows, cited = source_rows(data, config_dir, content_dir, request.state.lang)
                diffs = load_differences(config_dir / "differences.yaml")
                dims = diffs.localised(request.state.lang).dimensions
            except (ConfigError, ContentError, OSError) as e:
                log.error("the sources table could not be built: %s", e)
                return {"rows": [], "cited": None, "dimensions": [], "error": str(e)}
            return {"rows": rows, "cited": cited, "dimensions": dims, "error": None}

        ctx = cache.get(f"sources:{request.state.lang}", fp(request), build)
        groups = [
            (group_name(g, request.state.lang), [r for r in ctx["rows"] if r.group == g])
            for g in GROUPS
        ]
        return page(
            request, "sources.html", "sources", data, groups=[(n, rs) for n, rs in groups if rs],
            cited=ctx["cited"], dimensions=ctx["dimensions"], content_error=ctx["error"],
        )  # fmt: skip

    register_pages(app, "/sources", sources_page)

    async def plans_index(request: Request, data: Data):
        orgs, _, _ = organisations(request)

        def build() -> dict:
            plans, rows, error = plans_config()
            cities = sorted(((c.id, c.name) for c in data.cities()), key=lambda c: c[1])
            lang = request.state.lang
            notes = report_notes_de(rows) if lang == "de" else None
            table = plans_pages.plans_table(plans, rows, cities, orgs, lang, notes)
            return {"table": table, "error": error}

        ctx = cache.get(f"plans:{request.state.lang}", fp(request), build)
        return page(request, "plans.html", "plans", data, **ctx)

    register_pages(app, "/plans", plans_index)

    async def plan_page(request: Request, city_id: str, data: Data):
        if city_id != plans_pages.DETAIL_CITY:
            raise HTTPException(404, f"no plan page for {city_id!r}")
        _, sources, _, errors, _ = content_of(request)
        orgs, _, _ = organisations(request)

        def build() -> dict:
            plans, rows, error = plans_config()
            plan = next((p for p in plans if p.city == city_id), None)
            lang = request.state.lang
            try:
                text, english = document(content_dir / "plans" / f"{city_id}.yaml", lang)
                text_error = None
            except ContentError as e:
                log.error("plan page text could not be loaded: %s", e)
                text, english, text_error = None, frozenset(), str(e)
            doc = (
                None
                if text is None or errors.get("*")
                else render_explainer(text, sources, lang, english)
            )
            if plan is None:
                return {"plan": None, "error": error, "doc": doc, "text_error": text_error}
            overlay = data.plan_overlay(city_id)
            dates = plans_pages.run_dates(data.conn, {r.run_id for r in overlay})
            projects = plans_pages.completed_projects(plans_data_dir / plans_pages.MEASURES_FILE)
            notes = report_notes_de(rows) if lang == "de" else None
            ctx = plans_pages.berlin_context(
                plan, rows, orgs, overlay, dates, projects, lang, notes
            )
            measures, record_error = plans_pages.measures_retrieved(plans_data_dir)
            if record_error:
                log.error("plan data source record could not be read: %s", record_error)
            return ctx | {
                "error": error,
                "doc": doc,
                "text_error": text_error,
                "measures": measures,
                "network_licence": plans_pages.network_licence(measures),
                "measures_licence": plans_pages.layer_licence(measures, plans_pages.MEASURES_LAYER),
                "record_error": record_error,
            }

        ctx = cache.get(f"plan:{city_id}:{request.state.lang}", fp(request), build)
        doc = ctx["doc"]
        return page(
            request, "plans_berlin.html", "plans", data, **ctx, nar=doc,
            content_error=errors.get("*"),
            cited_sources=[] if doc is None else sorted(doc.sources.items()),
            cited_refs=[] if doc is None else sorted(doc.refs.items()),
        )  # fmt: skip

    register_pages(app, "/plans/{city_id}", plan_page)

    def keynums(
        summary: dict, fua, fua_now: float | None, flagged: int, lang: Lang = "en"
    ) -> list[dict]:
        """The five numbers of the city header's `.keynums` row (LAU unless it says FUA)."""
        point, change = summary["point"], summary["change"]
        na = i18n.t(lang, "fmt.na")
        now_label = summary["now_label"]
        return [
            {"label": i18n.t(lang, "city.keynum.headline",
                             when=now_label or i18n.t(lang, "city.keynum.now")),
             "value": _num(summary["now"], lang=lang),
             "sub": i18n.t(lang, "city.keynum.headline_sub")},
            {"label": i18n.t(lang, "city.keynum.since",
                             when=summary["first_label"] or i18n.t(lang, "city.keynum.first_year")),
             "value": na if change is None else i18n.signed(change, lang).replace("-", i18n.MINUS),
             "tone": i18n.tone(change),
             "sub": na if summary["first"] is None
             else i18n.t(lang, "city.keynum.from", value=_num(summary["first"], lang=lang))},
            {"label": i18n.t(lang, "city.keynum.ab_km"),
             "value": na if point is None else _num(point.ab_km, ",.0f", lang),
             "sub": i18n.t(lang, "city.keynum.per_side")
             + (f", {now_label}" if point else "")},
            {"label": i18n.t(lang, "unit.fua"), "value": _num(fua_now, lang=lang),
             "sub": i18n.t(lang, "city.keynum.fua_sub")
             + (f", {_when(ts.CURRENT, fua.osm_timestamp, lang)}" if fua else "")},
            {"label": i18n.t(lang, "city.keynum.flagged"), "value": str(flagged),
             "sub": i18n.t(lang, "city.keynum.flagged_sub") if flagged
             else i18n.t(lang, "city.keynum.none_flagged")},
        ]  # fmt: skip

    def city_context(data: ReportData, city_id: str) -> dict:
        c = known(data, city_id)
        lang = data.lang
        kinds, map_kinds = [], []
        for kind in KINDS:
            series = data.series(city_id, kind)
            flags = [
                {"flag": f, "explanation": explanation_in(f.key, lang)}
                for f in data.flags(city_id, kind)
            ]
            # the static image in the page's language (`<city>_<kind>.de.png` on German pages)
            map_name = f"{city_id}_{kind}{'.de' if lang == 'de' else ''}.png"
            geojson = f"{city_id}_{kind}.geojson"
            if (maps_dir / geojson).is_file():
                map_kinds.append(
                    {"kind": kind, "label": kind.upper(), "url": data_u(f"/maps/{geojson}")}
                )
            kinds.append(
                {
                    "kind": kind,
                    "point": data.current(city_id, kind),
                    "series": series,
                    "provenance": None if series is None else provenance_in(data, series),
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
        # no colours: the tier and outline colours are stylesheet tokens map.js reads (both themes)
        tiermap = {
            "tiles": OSM_TILES,
            "tile_class": TILE_CLASS,
            "weight": LINE_WEIGHT,
            "links": OSM_LINKS,
            "labels": {tier: i18n.t(lang, f"tier.{tier}") for tier in charts.TIER_LABEL},
            "kinds": map_kinds,
        }
        summary = city_summary(data, c)
        counters_cfg, counters_error = counts_model.counters_config(config_dir)
        lau = summary["point"]
        fua = data.current(city_id, "fua")
        return {
            "city": c,
            "country": country_name(c.country_iso2, data.lang),
            "residents": lau.population_value if lau else None,
            "keynums": keynums(
                summary,
                fua,
                headline_of(fua),
                len(next(k for k in kinds if k["kind"] == "lau")["flags"]),
                data.lang,
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
            "no_counters": counts_model.no_data_notes(counters_cfg, data.lang).get(city_id),
            "counters_error": (
                None if counters_error is None else i18n.t(lang, "counts.config_error")
            ),
            "kinds": kinds,
            "yearly": yearly,
            "reconcile": data.reconcile(city_id),
            "reported": data.reported_figures(city_id),
            # the reported figures' notes still English on a German page (no German sibling)
            "english_notes": english_notes(data, city_id),
            "preset_label": data.preset_labels(),
            "preset_unit": data.preset_units(),
            "headline_unit": headline_unit(data.lang),
            "tiers": ts.TIERS,
            "tiermap": tiermap if map_kinds else None,
            "plan_href": f"/plans/{city_id}"
            if city_id == plans_pages.DETAIL_CITY
            else f"/plans#{city_id}",
        }

    def explanation_in(key: str, lang: Lang) -> str | None:
        """A flagged year's explanation in `lang`: on a German page the stamped German entry,
        else the English one as a `Fallback` (a stale stamp still shows the German)."""
        text = ts.explanation(docs_dir / EXPLANATIONS, key)
        if lang != "de" or text is None:
            return text
        german, stamp = ts.stamped_explanation(docs_dir / EXPLANATIONS_DE, key)
        return Fallback(text) if german is None or stamp is None else german

    def provenance_in(data: ReportData, series: ts.CitySeries) -> str:
        """The series' provenance line in the page's language."""
        if data.lang == "en":
            return series.provenance
        return ts.provenance_line(
            data.conn, data.selector, series.set_md5, series.points, data.lang
        )

    def english_notes(data: ReportData, city_id: str) -> set[str]:
        """The reported figures' notes a German page shows in English (none has a German
        sibling in figures.csv); empty on an English page."""
        if data.lang == "en":
            return set()
        return {
            f.note
            for f in data.with_lang("en").reported_figures(city_id)
            if f.note and data.note_in_lang(f.note)[1]
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
            "labels": [
                {"label": lbl, "text": _when(lbl, osm.get(lbl), data.lang)} for lbl in labels
            ],
            "rows": sorted(rows, key=lambda r: r["name"]),
        }

    def bezirke_context(data: ReportData, city_id: str) -> dict | None:
        """The Bezirk section: current table, small multiples, and the change map with the
        per-Bezirk table of its markdown. None for a city without (trusted) subareas."""
        rows = data.subareas(city_id)
        if rows is None:
            return None
        window = data.report_config.change_window
        lang = data.lang
        label_from = window.from_.isoformat()
        label_to = window.to if isinstance(window.to, str) else window.to.isoformat()
        stem = f"{city_id}_change_{label_from}_{label_to}"
        md_path = docs_dir / "review" / f"{stem}.md"
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            text = None
        table = None if text is None else change_report.bezirk_table(text, data.lang)
        if table is not None:  # never raw HTML from the page into the `md` filter
            table = table.replace("<", "&lt;").replace(">", "&gt;")
        runs = None if text is None else change_report.change_runs(text)
        has_map = (maps_dir / f"{stem}.geojson").is_file()
        latest = data.selector.latest(data.conn, city_id, "lau")
        return {
            "rows": rows,
            # the remainder row's name as HTML text, the original term marked (the plain label
            # is for the CSV and the change report)
            "remainder_html": i18n.t_markup(
                lang,
                "subarea.remainder",
                n=len(data.city_fields()[city_id]["subareas"]["relations"]),
            ),
            "series": bezirk_series(data, city_id),
            "window": i18n.t(
                lang,
                "page.bezirke.window",
                start=label_from,
                # report.yaml's `to: current`: the latest current run, named in the page's language
                end=i18n.t(lang, "page.bezirke.window_current")
                if window.to == "current"
                else label_to,
            ),
            "change_runs": runs,
            # the change page does not end at the run the Bezirk table above shows
            "change_stale": (has_map or table is not None) and (runs is None or runs[1] != latest),
            "latest_run": latest,
            "change_table": table,
            "change_map": {
                "url": data_u(f"/maps/{stem}.geojson"),
                "tiles": OSM_TILES,
                "tile_class": TILE_CLASS,
                "weight": LINE_WEIGHT,
                "links": OSM_LINKS,
                # the drawn categories, in key order; their colours are the --change-<category>
                # tokens changemap.js reads (both themes)
                "labels": {
                    c: i18n.t(lang, "change.mapped", category=i18n.t(lang, f"change.category.{c}"))
                    for c in change_report.CATEGORY_COLOURS
                },  # fmt: skip
            }
            if has_map
            else None,
        }

    def methodology_page(request: Request, data: ReportData, **ctx) -> HTMLResponse:
        path = docs_dir / METHODOLOGY[request.state.lang]
        try:
            text = GENERATED_NOTE.sub("", path.read_text(encoding="utf-8"))
            english = docs_dir / METHODOLOGY["en"]
            body = methodology_html(text, english.read_text(encoding="utf-8"))
        except OSError:
            body = None
        return page(
            request, "methodology.html", "methodology", data, body=body, file=path.name, **ctx
        )

    async def methodology(request: Request, data: Data):
        return methodology_page(request, data)

    register_pages(app, "/methodology", methodology)

    async def methodology_legacy_de(request: Request, data: Data):
        """The German methodology's URL before M12: the same German page, pointing search engines
        at /de/methodology (a static site cannot redirect)."""
        return methodology_page(request, data, canonical=us["de"]("/methodology"))

    app.add_api_route(
        "/methodology/de", methodology_legacy_de, methods=["GET"],
        response_class=HTMLResponse, dependencies=[Depends(set_lang("de"))],
    )  # fmt: skip

    def map_file(data: ReportData, name: str, suffix: str) -> Path:
        """The map file of a trusted city's run, else 404 (the city page and CSV do the same).
        A German image (`<city>_<kind>.de`) is a PNG only."""
        path = maps_dir / f"{name}.{suffix}"
        change = CHANGE_NAME.fullmatch(name) if suffix == "geojson" else None
        if change is None and not MAP_NAME.fullmatch(name):
            raise HTTPException(404, "map not found")
        if suffix != "png" and name.endswith(".de"):
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
