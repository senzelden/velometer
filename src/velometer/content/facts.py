"""The fact expression language: dot-separated paths into the report data.

A narrative declares every number it prints as a fact (an expression plus the printed value);
`evaluate` recomputes the expression from `ReportData`, `printed_matches` compares it to the
printed text at the printed precision.
"""

import math
import re
from collections.abc import Callable
from pathlib import Path

from velometer.report import change as change_report
from velometer.report.data import ReportData, rank_values

FIELDS = ("headline", "ab_km", "A", "B", "C", "D", "E")
TIER_FIELDS = ("A", "B", "C", "D", "E")
KINDS = ("lau", "fua")
CHANGE_CATEGORIES = ("gained", "lost", "retiered", "redrawn", "geometry")
GAP_FIELDS = ("ours", "theirs", "gap_pct")


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


def _points(expr: str, data: ReportData, city: str, kind: str) -> dict:
    _kind(expr, kind)
    series = data.series(city, kind)
    if series is None:
        raise _err(expr, f"no {kind} series for city {city!r}")
    return {p.label: p for p in series.points}


def _point(expr: str, points: dict, label: str):
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


def _first_label(pts: dict) -> str:
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


def _trusted_points(data: ReportData, kind: str, label: str) -> dict[str, object]:
    out = {}
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
    _arity(expr, args, 3, "<city>.<gap key>.<ours|theirs|gap_pct>")
    city, comparison, field = args
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
        raise _err(expr, f"{len(gaps)} gaps for comparison {comparison!r}: use a gap key")
    v = getattr(gaps[0], field)
    if v is None:
        raise _err(expr, f"{field} is missing")
    return float(v) * 100 if field == "gap_pct" else float(v)


def _figure(expr, args, data, docs_dir):
    _arity(expr, args, 4, "<city>.<source>.<metric_name>.<network_scope>")
    city, source, metric, scope = args
    found = [
        f
        for f in data.reported_figures(city)
        if (f.source, f.metric_name, f.network_scope) == (source, metric, scope)
    ]
    if not found:
        raise _err(expr, f"no reported figure {source}/{metric}/{scope} for {city!r}")
    if len(found) > 1:
        raise _err(expr, f"{len(found)} figures match: not unique")
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
}
FAMILIES: tuple[str, ...] = tuple(_HANDLERS)


def evaluate(expr: str, data: ReportData, docs_dir: Path) -> float:
    """The value of a fact expression; FactError (message starting with the expression) when
    it does not name one."""
    family, *args = expr.strip().split(".")
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
