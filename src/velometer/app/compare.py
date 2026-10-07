"""The Compare page's state and its server-rendered Table view (spec §3.3).

`parse_compare` mirrors `static/js/state.js: parseState` case for case (both suites read
`tests/compare_cases.json`); `QUICK_SETS` mirrors the JS constant (a test asserts they are equal).
The Table view is rendered here from the `/data/series.json` payload so the page works without
JavaScript; compare.js draws the charts and re-renders the table from the same payload.
"""

from collections.abc import Iterable, Sequence
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
    "counter_index",
)  # fmt: skip
# The counter index (`series.json: counters`): calendar years, already an index (never rebased),
# the same for both boundaries (the counter sites of the city).
COUNTER_METRIC = "counter_index"
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
    "counter_index": "Counter index",
}
VIEW_LABELS = {"lines": "Lines", "small": "Small multiples", "rank": "Rank", "table": "Table"}
NO_INDEX = "no index: first year is 0 or missing"
FUA_NOTE = (
    "A+B km per 100k residents exists for the city proper (LAU) only; "
    "showing the headline for the metro area (FUA)."
)
NO_COUNTERS = "no open counter data"
NO_COUNTER_LINE = "no counter index line (an index value for one year only; see its Counts tab)"
AVG_DAILY = "index of average daily intensity (monthly values), not of counts"
COUNTER_UNIT = (
    "index of counts recorded at counter sites (or of their average daily intensity), "
    "2019 = 100; 2020 is the COVID year"
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


def per_100k_unit(population_years: Iterable[int] = ()) -> str:
    """The per-100k unit, naming the population it divides by: each city's one configured
    population (of the years given), held for every year of the series."""
    years = sorted(set(population_years))
    span = "" if not years else f"{years[0]} " if len(years) == 1 else f"{years[0]}–{years[-1]} "
    return (
        f"A+B mapped km per 100,000 residents (each city's {span}population, held for every year)"
    )


def metric_info(
    headline_unit: str, preset_units: dict[str, str], population_years: Iterable[int] = ()
) -> dict[str, dict[str, str]]:
    """Label and unit text per metric (the Table and chart subtitles, and compare.js's config).
    `population_years`: the years of the populations the per-100k metric divides by."""
    unit = {
        "headline": headline_unit,
        "ab_km": "A+B mapped km, per side",
        **{t: f"mapped km of tier {t}, per side" for t in ts.TIERS},
        "ecf_qecio": preset_units.get("ecf_qecio", ""),
        "clean_cities": preset_units.get("clean_cities_2025", ""),
        "ab_per_100k": per_100k_unit(population_years),
        "counter_index": COUNTER_UNIT,
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


def counter_lines(payload: dict, ids: Sequence[str]) -> tuple[list[str], dict, list[str]]:
    """(labels, values, notes) of the counter index for `ids`: labels are the calendar years from
    the first to the last with a value for any drawn city; values[id] one per label (None: a
    gap, never 0). A city without counter data, or whose index is not drawn as a line, gets no
    values and a note (compare-model.js: counterLines)."""
    counters = payload.get("counters", {}).get("cities", {})
    names = payload["cities"]
    drawn = {i: counters[i] for i in ids if i in counters and counters[i]["line"]}
    years = [p["year"] for c in drawn.values() for p in c["points"] if p["idx"] is not None]
    labels = [str(y) for y in range(min(years), max(years) + 1)] if years else []
    values, notes = {}, []
    for i in ids:
        c = counters.get(i)
        if c is None:
            notes.append(f"{names[i]['name']}: {NO_COUNTERS}")
        elif not c["line"]:
            notes.append(f"{names[i]['name']}: {NO_COUNTER_LINE}")
        elif c["series"] == "avg_daily_intensity":
            notes.append(f"{names[i]['name']}: {AVG_DAILY}")
        by_year = {str(p["year"]): p["idx"] for p in c["points"]} if i in drawn else {}
        values[i] = [by_year.get(lbl) for lbl in labels]
    return labels, values, notes


def _counter_table(payload: dict, ids: list[str]) -> dict:
    labels, values, notes = counter_lines(payload, ids)
    covid = str(payload.get("counters", {}).get("covid_year", ""))
    names = payload["cities"]
    return {
        "columns": [
            {"label": lbl, "text": f"{lbl} (COVID year)" if lbl == covid else lbl} for lbl in labels
        ],
        "rows": [
            {"id": i, "name": names[i]["name"], "values": values[i], "flagged": []} for i in ids
        ],
        "notes": notes,
        "index_base": None,
    }


def table_model(payload: dict, state: CompareState) -> dict:
    """The Table view: a row per selected city, a column per series label, the state's metric
    (indexed to the first year = 100 in `index` mode), plus the notes the page must show. The
    counter index has a column per calendar year and is never rebased."""
    cities = payload["cities"]
    if state.m == COUNTER_METRIC:
        return _counter_table(payload, [i for i in state.c if i in cities])
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
