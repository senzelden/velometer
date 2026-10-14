"""The city page's Counts tab and the counter index of `/data/series.json` (M8 spec §5.5).

Counters are context, not outcome (spec §2.12): every label says "recorded at counter sites",
never "cycling in <city>", and no text links counts and km causally. The index is the stored
chain of spec §2.13 (`counter_index`); the A+B mapped-km index beside it is rebased to the same
base year (1 January snapshots of the city proper). 2020 is marked as the COVID year.

An index line needs at least `MIN_LINE_YEARS` years with a value: Madrid's index has 2020 only,
so it gets a note instead of a line, in the tab and in Compare (user ruling, Task 8).

`step_downs` in `config/counters.yaml` lists sites whose counts step down while they keep
counting (our reading of the daily data, never a sourced claim). They are used only for the
tab's note, which gives the index computed here without those sites from their `since` year on;
the stored index keeps them (user ruling, Task 8).
"""

import logging
from datetime import date
from pathlib import Path

from velometer import timeseries as ts
from velometer.config import ConfigError
from velometer.counters import index as counter_index
from velometer.counters.index import chain_index
from velometer.counters.model import (
    COUNTERS_FILE,
    COVID_YEAR,
    DEFAULT_BASE_YEAR,
    MIN_LINE_YEARS,
    CounterEntry,
    CountersConfig,
    DayCount,
    data_gaps,
    load_counters_config,
)
from velometer.i18n import Lang, month_year, t
from velometer.report.data import ReportData

log = logging.getLogger(__name__)


def series_label(series: str, lang: Lang = "en") -> str:
    """What a counter series records, in words."""
    if series == "counts":
        return t(lang, "counts.series.counts")
    if series == "avg_daily_intensity":
        return t(lang, "counts.series.avg_daily_intensity")
    return series


def series_short(series: str, lang: Lang = "en") -> str:
    """A line's short name: the chart's end label (city.js reads it off the chart mount) and the
    key under the chart, which gives each its full name."""
    if series == "counts":
        return t(lang, "counts.short.counts")
    if series == "avg_daily_intensity":
        return t(lang, "counts.short.avg_daily_intensity")
    return series


# the English forms under their M8 names (tests read them), and the keys they are read from
SERIES_SHORT = {s: series_short(s) for s in ("counts", "avg_daily_intensity")}
KM_SHORT = t("en", "counts.short.km")
LABEL_KEYS: tuple[str, ...] = (
    "counts.short.counts", "counts.short.avg_daily_intensity", "counts.short.km",
)  # fmt: skip


def counters_config(config_dir: Path) -> tuple[CountersConfig | None, str | None]:
    """(config, error) of config/counters.yaml: unreadable, (None, the logged reason), and each
    page that would use it says so (the no-data notes and step-downs cannot be read)."""
    try:
        return load_counters_config(Path(config_dir) / COUNTERS_FILE), None
    except ConfigError as e:
        log.error("counter configuration could not be read: %s", e)
        return None, str(e)


def _round(v: float | None) -> float | None:
    return None if v is None else round(v, 3)


def has_line(points: list[dict]) -> bool:
    return sum(p["idx"] is not None for p in points) >= MIN_LINE_YEARS


def no_data_notes(cfg: CountersConfig | None, lang: Lang = "en") -> dict[str, str]:
    """city -> the note of a city listed under `none:` in config/counters.yaml (spec §5.1): "no
    open counter data found", the portals checked and the config's note."""
    out = {}
    for n in cfg.none if cfg else []:
        note = n.note_in(lang)
        extra = f"; {note}" if note else ""
        portals = ", ".join(n.checked_in(lang))
        out[n.city] = t(lang, "counts.none_found", portals=portals, note=extra)
    return out


def attribution(
    entry: CounterEntry | None, sites, lang: Lang = "en"
) -> tuple[str | None, str | None]:
    """(publisher, licence) of a city's counter data: its config/counters.yaml entry (the German
    `source_de` on a German page), else the stored sites' (ADR 0008: every page that shows the
    data carries an attribution line)."""
    if entry is not None:
        return entry.source_in(lang), entry.licence
    return (sites[0].source, sites[0].licence) if sites else (None, None)


def _entry(cfg: CountersConfig | None, city_id: str) -> CounterEntry | None:
    return next((e for e in cfg.cities if e.city == city_id), None) if cfg else None


def counter_payload(data: ReportData) -> dict:
    """`counters` of series.json: the COVID year, per counter city its series kind, base year,
    whether it is drawn as a line, its yearly index (None: no value, a gap) and its attribution
    (`source`, `licence`), `none`: the note of each city without open counter data
    (`no_data_notes`), and `config_error`: whether config/counters.yaml was unreadable."""
    cfg, error = counters_config(data.config_dir)
    cities = {}
    for city_id in data.counter_cities():
        rows = data.counter_index(city_id)
        if not rows:
            continue
        points = [{"year": r.year, "idx": _round(r.index), "sites": r.sites} for r in rows]
        entry = _entry(cfg, city_id)
        source, licence = attribution(entry, data.counter_sites(city_id))
        german = {"source_de": entry.source_de} if entry and entry.source_de else {}
        cities[city_id] = {
            "series": rows[0].series,
            "base_year": rows[0].base_year,
            "line": has_line(points),
            "points": points,
            "source": source,
            "licence": licence,
            **german,
        }
    return {
        "covid_year": COVID_YEAR,
        "cities": cities,
        "none": no_data_notes(cfg),
        "config_error": error is not None,
    }


def km_index(points, base_year: int) -> dict[int, float | None]:
    """year -> A+B mapped km on 1 January of that year, base year = 100 (series points of the
    city proper; `current` is not a year). Empty when the base year has no km."""
    km = {int(p.label): p.ab_km for p in points if p.label != ts.CURRENT}
    base = km.get(base_year)
    if not base:
        return {}
    return {y: None if v is None else v / base * 100 for y, v in sorted(km.items())}


def step_down_note(
    entry: CounterEntry,
    days: list[DayCount],
    stored: dict[int, float | None],
    base_year: int,
    lang: Lang = "en",
):
    """The step-down sites (present in the data) and the index without them from their `since`
    year on (chained from `base_year`, the stored index's), for every year from the first
    `since` year with a value; None without step-downs."""
    present = {d.site_id for d in days}
    steps = [s for s in entry.step_downs if s.site in present]
    if not steps:
        return None
    since = {s.site: int(s.since[:4]) for s in steps}
    kept = [d for d in days if d.day.year < since.get(d.site_id, d.day.year + 1)]
    first = min(since.values())
    alt = [
        {"year": y, "idx": v, "sites": n, "stored": stored.get(y)}
        for y, v, n in chain_index(kept, base_year)
        if y >= first and v is not None
    ]
    return {
        "sites": [{"site": s.site, "since": month_year(s.since, lang, short=False)} for s in steps],
        "years": alt,
    }


def _days(data: ReportData, city_id: str) -> list[DayCount]:
    return [
        DayCount(d.site_id, date.fromisoformat(d.day), d.count, d.complete)
        for d in data.counter_days(city_id)
    ]


def counts_context(data: ReportData, city_id: str, entry: CounterEntry | None, km_points) -> dict:
    """The Counts tab: index rows (counter index, qualifying sites, km index per year), notes,
    sites (a map config for those with coordinates), attribution."""
    rows = data.counter_index(city_id)
    series = rows[0].series if rows else "counts"
    base = rows[0].base_year if rows else (entry.base_year if entry else DEFAULT_BASE_YEAR)
    points = [{"year": r.year, "idx": r.index, "sites": r.sites} for r in rows]
    line = has_line(points)
    km = km_index(km_points, base)
    valued = {r.year for r in rows if r.index is not None} | set(km)
    # every year from the first to the last with a value: a year between them without one is
    # a gap row (n/a), never left out
    years = range(min(valued), max(valued) + 1) if valued else []
    table = [
        {
            "year": y,
            "idx": next((r.index for r in rows if r.year == y), None),
            "sites": next((r.sites for r in rows if r.year == y), None),
            "km": km.get(y),
            "covid": y == COVID_YEAR,
        }
        for y in years
    ]
    # the daily rows are read only for a note that needs them (a no-line gap, a step-down)
    wanted = series == "counts" and (not line or (entry is not None and entry.step_downs))
    days = _days(data, city_id) if wanted else []
    stored = {r.year: r.index for r in rows}
    sites = data.counter_sites(city_id)
    mapped = [s for s in sites if s.lat is not None and s.lon is not None]
    retrieved = max((s.retrieved_at for s in sites), default=None)
    lang = data.lang
    source, licence = attribution(entry, sites, lang)
    return {
        "label": series_label(series, lang),
        "short": series_short(series, lang),
        "km_short": t(lang, "counts.short.km"),
        "series": series,
        "base_year": base,
        "line": line,
        "index_years": [r.year for r in rows if r.index is not None],
        "table": table,
        "km_base_missing": not km,
        "gaps": [] if line else data_gaps(days),
        "step_down": None if entry is None else step_down_note(entry, days, stored, base, lang),
        "sites": sites,
        "site_map": {
            "sites": [{"name": s.name, "lat": s.lat, "lon": s.lon} for s in mapped],
        }
        if mapped
        else None,
        "entry": entry,
        "source": source,
        "licence": licence,
        "retrieved": None if retrieved is None else retrieved[:10],
        "covid_year": COVID_YEAR,
        # the index rule (spec §2.13), read when the page renders: the text follows the constants
        "min_sites": counter_index.MIN_SITES,
        "min_valid_pct": round(counter_index.MIN_VALID * 100, 6),
    }
