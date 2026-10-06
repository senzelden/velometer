"""The Compare page's state and its server-rendered Table view (spec §3.3).

`parse_compare` mirrors `static/js/state.js: parseState` case for case (both suites read
`tests/compare_cases.json`); `QUICK_SETS` mirrors the JS constant (a test asserts they are equal).
The Table view is rendered here from the `/data/series.json` payload so the page works without
JavaScript; compare.js draws the charts and re-renders the table from the same payload.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote

from velometer import timeseries as ts

PILOT5 = ["berlin", "paris", "vienna", "copenhagen", "wroclaw"]
MAX_HIGHLIGHTED = 8
BOUNDARIES = ("lau", "fua")
MODES = ("abs", "index")
VIEWS = ("lines", "small", "rank", "table")
METRICS = (
    "headline", "ab_km", "A", "B", "C", "D", "E", "ecf_qecio", "clean_cities", "ab_per_100k",
)  # fmt: skip
DEFAULT_METRIC = "headline"
LAU_ONLY_METRIC = "ab_per_100k"  # needs the city proper's residents; dropped for the metro area
# `all` (None) is every known city
QUICK_SETS: dict[str, list[str] | None] = {
    "all": None,
    "pilot5": PILOT5,
    "nordic": ["copenhagen", "stockholm", "oslo", "helsinki"],
    "dach": ["berlin", "vienna"],
    "west": [
        "paris", "lyon", "strasbourg", "bordeaux", "madrid", "barcelona", "amsterdam", "utrecht",
    ],
    "central": ["wroclaw", "warsaw", "krakow", "prague", "bratislava", "budapest", "ljubljana"],
}  # fmt: skip
QUICK_LABELS = {
    "all": "All",
    "pilot5": "Pilot 5",
    "nordic": "Nordic",
    "dach": "DACH",
    "west": "West & South",
    "central": "Central & East",
}
METRIC_LABELS = {
    "headline": "Headline",
    "ab_km": "A+B km",
    **{t: f"Tier {t} km" for t in ts.TIERS},
    "ecf_qecio": "QECIO method",
    "clean_cities": "Clean Cities method",
    "ab_per_100k": "A+B km per 100k residents",
}
VIEW_LABELS = {"lines": "Lines", "small": "Small multiples", "rank": "Rank", "table": "Table"}
NO_INDEX = "no index: first year is 0 or missing"
FUA_NOTE = (
    "A+B km per 100k residents exists for the city proper (LAU) only; "
    "showing the headline for the metro area (FUA)."
)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class CompareState:
    c: list[str]
    m: str = DEFAULT_METRIC
    b: str = "lau"
    mode: str = "abs"
    view: str = "lines"
    hl: list[str] = field(default_factory=list)
    dropped_metric: str | None = None  # the LAU-only metric asked for with b=fua

    def as_dict(self) -> dict:
        """The six URL parameters (what state.js's parseState returns)."""
        return {k: getattr(self, k) for k in ("c", "m", "b", "mode", "view", "hl")}


def _values(params: dict[str, list[str]], key: str) -> list[str]:
    """Repeated and comma-separated values merged, in order, empties dropped."""
    return [v for raw in params.get(key, []) for v in raw.split(",") if v]


def _first(params: dict[str, list[str]], key: str) -> str | None:
    return params[key][0] if params.get(key) else None


def _one_of(value: str | None, allowed: Sequence[str], default: str) -> str:
    return value if value in allowed else default


def parse_compare(query: str, cities: Sequence[str], metrics: Sequence[str]) -> CompareState:
    """The page state of a query string, with state.js's defaults and validation: unknown cities
    are dropped (none left: the Pilot 5), an unknown metric or boundary/mode/view falls back to
    the default (the headline, or the first known metric), `hl` is a de-duplicated subset of `c`
    of at most 8, and the LAU-only metric becomes the headline for `b=fua`."""
    params = parse_qs(query.lstrip("?"), keep_blank_values=True)
    c = [i for i in dict.fromkeys(_values(params, "c")) if i in cities]
    if not c:
        c = list(PILOT5)
    b = _one_of(_first(params, "b"), BOUNDARIES, "lau")
    wanted = _first(params, "m")
    dropped = wanted == LAU_ONLY_METRIC and b == "fua"
    if wanted in metrics and not dropped:
        m = wanted
    else:
        m = DEFAULT_METRIC if DEFAULT_METRIC in metrics else (metrics[0] if metrics else "")
    hl = [i for i in dict.fromkeys(_values(params, "hl")) if i in c][:MAX_HIGHLIGHTED]
    return CompareState(
        c=c,
        m=m,
        b=b,
        mode=_one_of(_first(params, "mode"), MODES, "abs"),
        view=_one_of(_first(params, "view"), VIEWS, "lines"),
        hl=hl,
        dropped_metric=LAU_ONLY_METRIC if dropped else None,
    )


def serialize(state: CompareState, **changes) -> str:
    """The query string (no "?") of the state with `changes` applied, defaults omitted, in
    state.js's serializeState key order; the links of the no-JS page are built with it."""
    s = {**state.as_dict(), **changes}
    parts = []
    if s["c"] != PILOT5:
        parts.append("c=" + ",".join(quote(i, safe="") for i in s["c"]))
    for key, default in (("m", DEFAULT_METRIC), ("b", "lau"), ("mode", "abs"), ("view", "lines")):
        if s[key] != default:
            parts.append(f"{key}={quote(s[key], safe='')}")
    if s["hl"]:
        parts.append("hl=" + ",".join(quote(i, safe="") for i in s["hl"]))
    return "&".join(parts)


def quick_set_ids(key: str, known: Sequence[str]) -> list[str]:
    """The known cities of a quick set (`all`: every known city)."""
    ids = QUICK_SETS[key]
    return list(known) if ids is None else [i for i in ids if i in known]


def metric_info(headline_unit: str, preset_units: dict[str, str]) -> dict[str, dict[str, str]]:
    """Label and unit text per metric (the Table and chart subtitles, and compare.js's config)."""
    unit = {
        "headline": headline_unit,
        "ab_km": "A+B mapped km, per side",
        **{t: f"mapped km of tier {t}, per side" for t in ts.TIERS},
        "ecf_qecio": preset_units.get("ecf_qecio", ""),
        "clean_cities": preset_units.get("clean_cities_2025", ""),
        "ab_per_100k": "A+B mapped km per 100,000 residents",
    }
    return {m: {"label": METRIC_LABELS[m], "unit": unit[m]} for m in METRICS}


def metric_value(point: dict, metric: str, population: float | None) -> float | None:
    """One point's value of a metric (None where it is missing)."""
    if metric == LAU_ONLY_METRIC:
        km = point.get("ab_km")
        return None if km is None or not population else km / population * 100_000
    return point.get(metric)


def column_label(label: str, osm: str | None) -> str:
    """A series label as a column heading: "Jan 2018" for a year, "Oct 2026" for the current run."""
    if label != ts.CURRENT:
        return f"Jan {label}"
    if osm and len(osm) >= 7 and osm[4] == "-":
        return f"{MONTHS[int(osm[5:7]) - 1]} {osm[:4]}"
    return "current"


def table_model(payload: dict, state: CompareState) -> dict:
    """The Table view: a row per selected city, a column per series label, the state's metric
    (indexed to the first year = 100 in `index` mode), plus the notes the page must show."""
    cities = payload["cities"]
    ids = [i for i in state.c if i in cities]
    lists = {i: payload["series"].get(f"{i}/{state.b}", []) for i in ids}
    labels = sorted({p["label"] for pts in lists.values() for p in pts} - {ts.CURRENT})
    has_current = any(p["label"] == ts.CURRENT for pts in lists.values() for p in pts)
    if has_current:
        labels.append(ts.CURRENT)
    osm = {p["label"]: p["osm"] for pts in lists.values() for p in pts}
    years = [lbl for lbl in labels if lbl != ts.CURRENT]
    base = years[0] if years else None
    notes: list[str] = []
    if state.dropped_metric:
        notes.append(FUA_NOTE)
    rows = []
    for i in ids:
        by_label = {p["label"]: p for p in lists[i]}
        pop = cities[i]["population"]
        values = [
            metric_value(by_label[lbl], state.m, pop) if lbl in by_label else None for lbl in labels
        ]
        flagged = [lbl for lbl in labels if by_label.get(lbl, {}).get("flags")]
        if state.mode == "index":
            start = values[labels.index(base)] if base else None
            if not start:  # None or 0
                notes.append(f"{cities[i]['name']}: {NO_INDEX}")
                values = [None] * len(labels)
            else:
                values = [None if v is None else v / start * 100 for v in values]
        rows.append({"id": i, "name": cities[i]["name"], "values": values, "flagged": flagged})
    return {
        "columns": [{"label": lbl, "text": column_label(lbl, osm.get(lbl))} for lbl in labels],
        "rows": rows,
        "notes": notes,
        "index_base": base if state.mode == "index" else None,
    }
