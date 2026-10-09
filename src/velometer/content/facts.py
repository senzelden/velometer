"""The fact expression language: dot-separated paths into the report data.

A narrative declares every number it prints as a fact (an expression plus the printed value);
`evaluate` recomputes the expression from `ReportData`, `printed_matches` compares it to the
printed text at the printed precision.

Families (`<family>.<args>`):

- `series|index.<city>.<kind>.<label>.<field>`, `delta|pct.<city>.<kind>.<from>.<to>.<field>`,
  `denominator.<city>.<kind>.<label>`, `rank.<city>.<kind>.<label>.headline`,
  `total.<kind>.<label>.ab_km`, `bezirk.<city>.<subarea>.<label>.<field>`,
  `gap.<city>.<gap key>.<ours|theirs|gap_pct>`,
  `figure.<city>.<source>.<metric>.<scope>[.<reference_date|value>]`, `population.<city>`,
  `change.<city>.<category>` (M7).
- `overlay.<city>.<class>.<YYYY-MM-DD>.<ab_km|network_km>`: A+B mapped km on that plan-network
  class at the LAU run whose OSM snapshot has that date, or the class's network km (M8, from
  `plan_overlay`; the latest overlay version of the city).
- `overlay_change.<city>.<class>.<from YYYY-MM-DD>.<to YYYY-MM-DD>`: the change of `ab_km`.
- `plan.<plan_id>.<item_id>.<year>.<quantity>[.<doc_id with / replaced by _>]`: the current
  reported value (latest document) or the named document's value, from
  `<config_dir>/plans/reports.csv`; needs `config_dir`.
- `counter.<city>.<year>`: the counter index; `counter_sites.<city>.<year>`: the number of
  qualifying sites of that year's link.
- `counter.min_valid` (the share of complete days a site needs in both years of a link, in
  percent), `counter.min_sites` (the qualifying sites a link needs), `counter.base_year.<city>`
  (the city's stored index base year): the index rule (spec §2.13), so prose that states it is
  checked against the constants and the data.
"""

import hashlib
import math
import re
from collections.abc import Callable
from pathlib import Path

from velometer.config import ConfigError
from velometer.counters import index as counter_index
from velometer.plans.models import (
    PLANS_FILE,
    REPORTS_FILE,
    Plan,
    ReportRow,
    current_and_revisions,
    load_plans,
)
from velometer.report import change as change_report
from velometer.report.data import ReportData, rank_values
from velometer.timeseries import YearPoint

FIELDS = ("headline", "ab_km", "A", "B", "C", "D", "E")
TIER_FIELDS = ("A", "B", "C", "D", "E")
KINDS = ("lau", "fua")
CHANGE_CATEGORIES = ("gained", "lost", "retiered", "redrawn", "geometry")
GAP_FIELDS = ("ours", "theirs", "gap_pct")
OVERLAY_FIELDS = ("ab_km", "network_km")
QUANTITIES = ("implemented_in_year", "implemented_cumulative", "under_construction", "in_planning")


class FactError(Exception):
    """An expression that does not name a value in the report data."""


def _err(expr: str, reason: str) -> FactError:
    return FactError(f"{expr}: {reason}")


def _arity(expr: str, args: list[str], n: int, shape: str) -> None:
    if len(args) != n:
        raise _err(expr, f"expected {shape}, got {len(args)} parts after the family")


def _kind(expr: str, kind: str) -> str:
    if kind not in KINDS:
        raise _err(expr, f"unknown kind {kind!r} (lau|fua)")
    return kind


def _field(expr: str, field: str, allowed: tuple[str, ...] = FIELDS) -> str:
    if field not in allowed:
        raise _err(expr, f"unknown field {field!r} ({'|'.join(allowed)})")
    return field


def _points(expr: str, data: ReportData, city: str, kind: str) -> dict[str, YearPoint]:
    _kind(expr, kind)
    series = data.series(city, kind)
    if series is None:
        raise _err(expr, f"no {kind} series for city {city!r}")
    return {p.label: p for p in series.points}


def _point(expr: str, points: dict[str, YearPoint], label: str) -> YearPoint:
    if label not in points:
        raise _err(expr, f"no point labelled {label!r} (have {', '.join(points)})")
    return points[label]


def _pick(expr: str, point, field: str) -> float:
    v = point.tiers_km.get(field) if field in TIER_FIELDS else getattr(point, field)
    if v is None:
        raise _err(expr, f"{field} is missing at {point.label}")
    return float(v)


def _series(expr, args, data, docs_dir):
    _arity(expr, args, 4, "<city>.<kind>.<label>.<field>")
    city, kind, label, field = args
    pts = _points(expr, data, city, kind)
    return _pick(expr, _point(expr, pts, label), _field(expr, field))


def _first_label(pts: dict[str, YearPoint]) -> str:
    return min(pts, key=lambda lab: (lab == "current", lab))


def _index(expr, args, data, docs_dir):
    _arity(expr, args, 4, "<city>.<kind>.<label>.<field>")
    city, kind, label, field = args
    pts = _points(expr, data, city, kind)
    _field(expr, field)
    value = _pick(expr, _point(expr, pts, label), field)
    base = _pick(expr, pts[_first_label(pts)], field)
    if base == 0:
        raise _err(expr, f"{field} is 0 at the first year {pts[_first_label(pts)].label}")
    return value / base * 100


def _two_points(expr, args, data):
    _arity(expr, args, 5, "<city>.<kind>.<from>.<to>.<field>")
    city, kind, frm, to, field = args
    pts = _points(expr, data, city, kind)
    _field(expr, field)
    return _pick(expr, _point(expr, pts, frm), field), _pick(expr, _point(expr, pts, to), field)


def _delta(expr, args, data, docs_dir):
    a, b = _two_points(expr, args, data)
    return b - a


def _pct(expr, args, data, docs_dir):
    a, b = _two_points(expr, args, data)
    if a == 0:
        raise _err(expr, "the from value is 0")
    return (b / a - 1) * 100


def _denominator(expr, args, data, docs_dir):
    _arity(expr, args, 3, "<city>.<kind>.<label>")
    city, kind, label = args
    p = _point(expr, _points(expr, data, city, kind), label)
    if not p.headline:
        raise _err(expr, f"headline is 0 or missing at {label}")
    return p.ab_km / p.headline * 100


def _trusted_points(data: ReportData, kind: str, label: str) -> dict[str, YearPoint]:
    out: dict[str, YearPoint] = {}
    for c in data.cities():
        s = data.series(c.id, kind)
        point = None if s is None else next((p for p in s.points if p.label == label), None)
        if point is not None:
            out[c.id] = point
    return out


def _rank(expr, args, data, docs_dir):
    _arity(expr, args, 4, "<city>.<kind>.<label>.headline")
    city, kind, label, field = args
    _kind(expr, kind)
    _field(expr, field, ("headline",))
    pts = _trusted_points(data, kind, label)
    if city not in pts:
        raise _err(expr, f"{city!r} is not a trusted city with a {kind} point at {label!r}")
    values = [(c, p.headline) for c, p in pts.items() if p.headline is not None]
    if city not in dict(values):
        raise _err(expr, f"headline is missing for {city!r} at {label!r}")
    return float(rank_values(values)[city])


def _total(expr, args, data, docs_dir):
    _arity(expr, args, 3, "<kind>.<label>.ab_km")
    kind, label, field = args
    _kind(expr, kind)
    _field(expr, field, ("ab_km",))
    pts = _trusted_points(data, kind, label)
    if not pts:
        raise _err(expr, f"no trusted city has a {kind} point at {label!r}")
    return sum(p.ab_km for p in pts.values())


def _bezirk(expr, args, data, docs_dir):
    _arity(expr, args, 4, "<city>.<subarea_id>.<label>.<field>")
    city, sid, label, field = args
    _field(expr, field, ("headline", *TIER_FIELDS))
    subareas = data.subarea_series(city)
    if sid not in subareas:
        raise _err(expr, f"no subarea {sid!r} in city {city!r} (have {', '.join(subareas)})")
    point = next((p for p in subareas[sid] if p.label == label), None)
    if point is None:
        raise _err(expr, f"subarea {sid!r} has no point labelled {label!r}")
    v = point.headline if field == "headline" else point.tier_km.get(field)
    if v is None:
        raise _err(expr, f"{field} is missing for {sid!r} at {label!r}")
    return float(v)


def _gap(expr, args, data, docs_dir):
    # The city is the first segment, the field the last; the middle is the gap key without its
    # `<city>/` prefix and may itself contain dots (`official_new_km#official:21.2`).
    if len(args) < 3:
        raise _err(expr, f"expected <city>.<gap key>.<ours|theirs|gap_pct>, got {len(args)} parts")
    city, comparison, field = args[0], ".".join(args[1:-1]), args[-1]
    _field(expr, field, GAP_FIELDS)
    report = data.reconcile(city)
    if report is None:
        raise _err(expr, f"no reconcile report for city {city!r}")
    # A comparison id can have several gaps (one per scope/weighting); the segment is the gap's
    # key without its city prefix, or a bare comparison id when that names a single gap.
    gaps = [g for g in report.gaps if g.key.removeprefix(f"{city}/") == comparison]
    if not gaps:
        gaps = [g for g in report.gaps if g.comparison == comparison]
    if not gaps:
        have = sorted({g.key.removeprefix(f"{city}/") for g in report.gaps})
        raise _err(expr, f"no comparison {comparison!r} for {city!r} (have {', '.join(have)})")
    if len(gaps) > 1:
        keys = ", ".join(sorted(g.key.removeprefix(f"{city}/") for g in gaps))
        raise _err(
            expr, f"{len(gaps)} gaps for comparison {comparison!r}: use a gap key (one of {keys})"
        )
    v = getattr(gaps[0], field)
    if v is None:
        raise _err(expr, f"{field} is missing")
    return float(v) * 100 if field == "gap_pct" else float(v)


def _figure(expr, args, data, docs_dir):
    # An optional last selector picks one of several matches: the figure's reference date
    # (ISO) or, when figures share a date, its value as `{value:g}` (as in gap keys, so it
    # may contain a dot).
    if len(args) < 4:
        raise _err(
            expr,
            "expected <city>.<source>.<metric_name>.<network_scope>[.<reference_date|value>], "
            f"got {len(args)} parts after the family",
        )
    city, source, metric, scope = args[:4]
    selector = ".".join(args[4:])
    found = [
        f
        for f in data.reported_figures(city)
        if (f.source, f.metric_name, f.network_scope) == (source, metric, scope)
    ]
    if not found:
        raise _err(expr, f"no reported figure {source}/{metric}/{scope} for {city!r}")
    have = ", ".join(
        f"{f.reference_date.isoformat() if f.reference_date else 'undated'} ({f.value:g})"
        for f in found
    )
    if selector:
        found = [
            f
            for f in found
            if selector in (f.reference_date and f.reference_date.isoformat(), f"{f.value:g}")
        ]
        if not found:
            raise _err(
                expr, f"no figure {source}/{metric}/{scope} matching {selector!r} (have {have})"
            )
    if len(found) > 1:
        raise _err(
            expr,
            f"{len(found)} figures match: not unique; add a reference date or value segment "
            f"(have {have})",
        )
    return float(found[0].value)


def _population(expr, args, data, docs_dir):
    _arity(expr, args, 1, "<city>")
    city = next((c for c in data.cities() if c.id == args[0]), None)
    if city is None:
        raise _err(expr, f"no trusted city {args[0]!r}")
    if city.population is None:
        raise _err(expr, f"city {args[0]!r} has no population")
    return float(city.population.value)


def _change(expr, args, data, docs_dir):
    _arity(expr, args, 2, "<city>.<category>")
    city, category = args
    if category not in CHANGE_CATEGORIES:
        raise _err(expr, f"unknown category {category!r} ({'|'.join(CHANGE_CATEGORIES)})")
    window = data.report_config.change_window
    label_to = window.to if isinstance(window.to, str) else window.to.isoformat()
    path = Path(docs_dir) / "review" / f"{city}_change_{window.from_.isoformat()}_{label_to}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise _err(expr, f"cannot read the change page {path}: {e}") from e
    table = change_report.bezirk_table(text)
    if table is None:
        raise _err(expr, f"{path.name} has no per-Bezirk table")
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in table.splitlines()]
    if len(rows) < 3:
        raise _err(expr, f"{path.name}: the Bezirk table has no city row")
    header, total = [h.strip() for h in rows[0]], rows[-1]
    if category not in header or len(total) != len(header):
        raise _err(expr, f"{path.name}: no {category!r} column in the Bezirk table")
    try:
        return float(total[header.index(category)].replace(",", ""))
    except ValueError as e:
        raise _err(expr, f"{path.name}: city row cell is not a number") from e


def version_key(version: str) -> tuple:
    """Sort key of a version id: `overlay_v10` after `overlay_v2`."""
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", version))


def _overlay_at(expr: str, data: ReportData, city: str, cls: str, day: str) -> list:
    """The overlay rows (one per tier) of one class at the run snapshotted on `day`."""
    rows = data.plan_overlay(city)
    if not rows:
        raise _err(expr, f"no plan overlay for city {city!r}")
    version = max((r.overlay_version for r in rows), key=version_key)
    rows = [r for r in rows if r.overlay_version == version]
    classes = sorted({r.network_class for r in rows})
    rows = [r for r in rows if r.network_class == cls]
    if not rows:
        raise _err(expr, f"no network class {cls!r} (have {', '.join(classes)})")
    ids = sorted({r.run_id for r in rows})
    marks = ",".join("?" * len(ids))
    dates = {
        rid: ts[:10]
        for rid, ts in data.conn.execute(
            f"SELECT id, osm_timestamp FROM runs WHERE boundary_kind='lau' AND id IN ({marks})", ids
        )
    }
    at = [r for r in rows if dates.get(r.run_id) == day]
    if not at:
        have = ", ".join(sorted(set(dates.values())))
        raise _err(expr, f"no overlay at snapshot {day!r} (have {have})")
    if len({r.run_id for r in at}) > 1:
        raise _err(expr, f"several runs have an overlay at snapshot {day!r}")
    return at


def _ab_km(rows: list) -> float:
    return sum(r.mapped_km for r in rows if r.tier in ("A", "B"))


def _overlay(expr, args, data, docs_dir):
    _arity(expr, args, 4, "<city>.<class>.<YYYY-MM-DD>.<ab_km|network_km>")
    city, cls, day, field = args
    _field(expr, field, OVERLAY_FIELDS)
    rows = _overlay_at(expr, data, city, cls, day)
    return _ab_km(rows) if field == "ab_km" else float(rows[0].network_km)


def _overlay_change(expr, args, data, docs_dir):
    _arity(expr, args, 4, "<city>.<class>.<from YYYY-MM-DD>.<to YYYY-MM-DD>")
    city, cls, frm, to = args
    return _ab_km(_overlay_at(expr, data, city, cls, to)) - _ab_km(
        _overlay_at(expr, data, city, cls, frm)
    )


def _counter_year(expr: str, args: list[str], data: ReportData):
    _arity(expr, args, 2, "<city>.<year>")
    city, year = args
    rows = data.counter_index(city)
    if not rows:
        raise _err(expr, f"no counter index for city {city!r}")
    at = [r for r in rows if str(r.year) == year]
    if not at:
        have = ", ".join(sorted({str(r.year) for r in rows}))
        raise _err(expr, f"no counter index year {year!r} (have {have})")
    if len(at) > 1:
        raise _err(expr, f"{len(at)} counter series have year {year!r}")
    return at[0]


COUNTER_RULES = ("min_valid", "min_sites")
BASE_YEAR = "base_year"


def counter_rule(name: str) -> float:
    """The index rule's value `counter.<name>` prints: `min_valid` in percent, `min_sites`."""
    if name == "min_valid":
        return counter_index.MIN_VALID * 100
    return float(counter_index.MIN_SITES)


def _counter_base_year(expr: str, city: str, data: ReportData) -> float:
    rows = data.counter_index(city)
    if not rows:
        raise _err(expr, f"no counter index for city {city!r}")
    years = sorted({r.base_year for r in rows})
    if len(years) > 1:
        raise _err(expr, f"counter series of {city!r} have several base years ({years})")
    return float(years[0])


def _counter(expr, args, data, docs_dir):
    if len(args) == 1 and args[0] in COUNTER_RULES:
        return counter_rule(args[0])
    if args and args[0] == BASE_YEAR:
        _arity(expr, args, 2, "base_year.<city>")
        return _counter_base_year(expr, args[1], data)
    row = _counter_year(expr, args, data)
    if row.index is None:
        raise _err(expr, f"no index value in {row.year} ({row.sites} qualifying sites)")
    return float(row.index)


def _counter_sites(expr, args, data, docs_dir):
    return float(_counter_year(expr, args, data).sites)


def _years(series: dict) -> str:
    return ", ".join(str(k[4]) for k in sorted(series, key=lambda k: (k[4] is None, k[4] or 0)))


_PLANS_READ: dict[Path, tuple[bytes, tuple[list[Plan], list[ReportRow]]]] = {}


def _plans(plan_dir: Path) -> tuple[list[Plan], list[ReportRow]]:
    """`load_plans(plan_dir)`, parsed once while the files' bytes stay the same: a content check
    evaluates every plan fact against the same files."""
    digest = hashlib.sha256()
    for name in (PLANS_FILE, REPORTS_FILE):
        try:
            digest.update((plan_dir / name).read_bytes())
        except OSError:
            digest.update(b"\0missing")  # load_plans names the file
        digest.update(b"\0")
    key, stamp = plan_dir.resolve(), digest.digest()
    hit = _PLANS_READ.get(key)
    if hit is None or hit[0] != stamp:
        hit = _PLANS_READ[key] = (stamp, load_plans(plan_dir))
    return hit[1]


def _plan(expr: str, args: list[str], config_dir: Path | None) -> float:
    if config_dir is None:
        raise _err(expr, "plan facts need the config directory")
    if len(args) < 4:
        raise _err(
            expr,
            "expected <plan_id>.<item_id>.<year>.<quantity>[.<doc_id>], "
            f"got {len(args)} parts after the family",
        )
    plan_id, item_id, year, quantity = args[:4]
    doc = ".".join(args[4:])
    try:
        plans, rows = _plans(Path(config_dir) / "plans")
    except ConfigError as e:
        raise _err(expr, str(e)) from e
    plan = next((p for p in plans if p.id == plan_id), None)
    if plan is None:
        raise _err(expr, f"no plan {plan_id!r}")
    if not any(i.id == item_id for i in plan.items):
        raise _err(expr, f"plan {plan_id!r} has no item {item_id!r}")
    if quantity not in QUANTITIES:
        raise _err(expr, f"unknown quantity {quantity!r} ({'|'.join(QUANTITIES)})")
    if not year.isdigit():
        raise _err(expr, f"year {year!r} is not a year")
    series = {
        k: v
        for k, v in current_and_revisions(rows).items()
        if k[:4] == (plan_id, item_id, int(year), quantity)
    }
    if not series:
        raise _err(expr, f"no reported {quantity} for {plan_id}/{item_id} in {year}")
    if not doc:
        if len(series) > 1:
            raise _err(
                expr, f"counted from several start years ({_years(series)}); name a document"
            )
        ((current, _),) = series.values()
        return current.value
    every: list[ReportRow] = [r for cur, revs in series.values() for r in (cur, *revs)]
    named = [r for r in every if r.doc_id.replace("/", "_") == doc]
    if not named:
        have = ", ".join(sorted({r.doc_id.replace("/", "_") for r in every}))
        raise _err(expr, f"no document {doc!r} for this figure (have {have})")
    distinct = sorted({r.doc_id for r in named})
    if len(distinct) > 1:
        raise _err(expr, f"{doc!r} is ambiguous: documents {', '.join(distinct)}")
    if len({r.cumulative_from for r in named}) > 1:
        starts = ", ".join(str(y) for y in sorted({r.cumulative_from for r in named}))
        raise _err(expr, f"{doc!r} prints this figure from several start years ({starts})")
    return named[0].value


_HANDLERS: dict[str, Callable[[str, list[str], ReportData, Path], float]] = {
    "series": _series,
    "index": _index,
    "delta": _delta,
    "pct": _pct,
    "denominator": _denominator,
    "rank": _rank,
    "total": _total,
    "bezirk": _bezirk,
    "gap": _gap,
    "figure": _figure,
    "population": _population,
    "change": _change,
    "overlay": _overlay,
    "overlay_change": _overlay_change,
    "counter": _counter,
    "counter_sites": _counter_sites,
}
FAMILIES: tuple[str, ...] = (*_HANDLERS, "plan")


def evaluate(
    expr: str, data: ReportData, docs_dir: Path, *, config_dir: Path | None = None
) -> float:
    """The value of a fact expression; FactError (message starting with the expression) when
    it does not name one. `plan.*` facts read `config_dir` and fail without it."""
    family, *args = expr.strip().split(".")
    if family == "plan":
        return _plan(expr.strip(), args, config_dir)
    handler = _HANDLERS.get(family)
    if handler is None:
        raise _err(expr, f"unknown family {family!r} (one of {', '.join(FAMILIES)})")
    return handler(expr.strip(), args, data, Path(docs_dir))


_NUMBER = re.compile(r"-?\d+(\.\d+)?")


def parse_printed(printed: str) -> tuple[float, int]:
    """The number a printed string shows and its decimals ('+16%' -> 16.0, 0)."""
    s = printed.strip().replace("−", "-").replace(",", "")
    s = s.removeprefix("+").removesuffix("%").strip()
    if not _NUMBER.fullmatch(s):
        raise FactError(f"{printed!r}: not a printed number")
    return float(s), len(s.partition(".")[2])


def printed_matches(value: float, printed: str) -> bool:
    """Whether `printed` is `value` rounded to the printed decimals."""
    parsed, decimals = parse_printed(printed)
    return math.isclose(round(value, decimals), parsed, abs_tol=10 ** -(decimals + 3))
