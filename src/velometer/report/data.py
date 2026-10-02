"""The one read-only query layer every report surface shares (CSV, charts, app, methodology).

It never writes: `open_readonly` opens the database with `mode=ro`. "The current point", "the
series" and "the headline" are defined here once, by reusing `timeseries.build_city`,
`reconcile.reconcile_city` and `pipeline.measure.select_metric`.
"""

import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from velometer import reconcile as rc
from velometer import timeseries as ts
from velometer.config import (
    ExternalRanking,
    ExternalRatioRanking,
    PresetRanking,
    load_activity,
    load_history,
    load_report,
)
from velometer.db import (
    fetch_cities,
    fetch_external_figures,
    fetch_run,
    fetch_run_results,
)
from velometer.models import City
from velometer.pipeline.measure import select_metric
from velometer.selection import report_selector

KINDS = ("lau", "fua")
CSV_PRESETS = ("ours_headline", "ecf_qecio", "clean_cities_2025")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class PresetValue(_Frozen):
    preset: str
    value: float | None  # percent, on the preset's reported basis
    per_100k: float | None


class CurrentPoint(_Frozen):
    city_id: str
    city_name: str
    kind: str  # "lau" | "fua"
    run_id: int
    osm_timestamp: str
    classifier_version: str
    config_sha256: str
    ab_km: float
    tiers_km: dict[str, float]  # "A".."E", per side
    presets: list[PresetValue]
    population_value: int | None
    population_year: int | None


class RankEntry(_Frozen):
    source_id: str
    source_label: str
    city_id: str
    value: float
    rank: int  # 1 = highest; ties share the lower rank number


def open_readonly(db_path: Path) -> sqlite3.Connection:
    """The database opened read-only (`mode=ro`); FileNotFoundError when it does not exist."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rank_values(values: list[tuple[str, float]]) -> dict[str, int]:
    """Descending ranks: equal values (rounded to 6 places) share the first one's rank number,
    the next distinct value takes its 1-based position."""
    ordered = sorted(values, key=lambda kv: -round(kv[1], 6))
    out: dict[str, int] = {}
    prev: float | None = None
    rank = 0
    for i, (key, v) in enumerate(ordered, start=1):
        r = round(v, 6)
        if r != prev:
            rank, prev = i, r
        out[key] = rank
    return out


def _fmt(v: float | None) -> str:
    return "" if v is None else f"{v:.3f}"


class ReportData:
    """Read-only report queries over an open connection and the config directory."""

    def __init__(self, conn: sqlite3.Connection, config_dir: Path):
        self.conn = conn
        self.config_dir = Path(config_dir)
        self.selector = report_selector(self.config_dir)
        self.report_config = load_report(
            self.config_dir / "report.yaml", self.config_dir / "presets.yaml"
        )
        self.activity = load_activity(self.config_dir / "activity.yaml")
        self.years = load_history(self.config_dir / "history.yaml").year_range()
        self._cities: list[City] | None = None
        self._series: dict[tuple[str, str], ts.CitySeries | None] = {}

    def cities(self) -> list[City]:
        if self._cities is None:
            self._cities = fetch_cities(self.conn)
        return self._cities

    def _city_name(self, city_id: str) -> str:
        return next((c.name for c in self.cities() if c.id == city_id), city_id)

    def _preset_values(self, results) -> list[PresetValue]:
        out = []
        for p in self.selector.presets.presets:
            m = select_metric(results.metrics, p.id, self.selector.presets)
            out.append(PresetValue(preset=p.id, value=m and m.value, per_100k=m and m.per_100k))
        return out

    def current(self, city_id: str, kind: str) -> CurrentPoint | None:
        """The city's latest done current run of the report config, or None without one."""
        run_id = self.selector.latest(self.conn, city_id, kind)
        if run_id is None:
            return None
        run = fetch_run(self.conn, run_id)
        results = fetch_run_results(self.conn, run_id)
        point = ts._point(self.conn, run_id, ts.CURRENT, self.selector, None)
        return CurrentPoint(
            city_id=city_id,
            city_name=self._city_name(city_id),
            kind=kind,
            run_id=run_id,
            osm_timestamp=results.osm_timestamp,
            classifier_version=run["classifier_version"],
            config_sha256=run["config_sha256"],
            ab_km=point.ab_km,
            tiers_km=point.tiers_km,
            presets=self._preset_values(results),
            population_value=run["population_value"],
            population_year=run["population_year"],
        )

    def series(self, city_id: str, kind: str) -> ts.CitySeries | None:
        key = (city_id, kind)
        if key not in self._series:
            self._series[key] = ts.build_city(self.conn, city_id, kind, self.selector, self.years)
        return self._series[key]

    def flags(self, city_id: str, kind: str) -> list[ts.Flag]:
        cs = self.series(city_id, kind)
        return [] if cs is None else ts.city_flags(cs, self.activity)

    def reconcile(self, city_id: str) -> rc.CityReport | None:
        sel = self.selector
        return rc.reconcile_city(
            self.conn,
            city_id,
            self.config_dir / "reconcile.yaml",
            "lau",
            classifier_version=sel.version,
            classifier_parameters=sel.parameters,
            config_sha256=sel.config_sha256,
            presets=sel.presets,
        )

    # --- rankings -----------------------------------------------------------------------

    def _ranking_values(self, ranking) -> dict[str, float]:
        out: dict[str, float] = {}
        for c in self.cities():
            v = self._ranking_value(ranking, c.id)
            if v is not None:
                out[c.id] = v
        return out

    def _ranking_value(self, ranking, city_id: str) -> float | None:
        if isinstance(ranking, PresetRanking):
            run_id = self.selector.latest(self.conn, city_id, "lau")
            if run_id is None:
                return None
            m = select_metric(
                fetch_run_results(self.conn, run_id).metrics, ranking.preset, self.selector.presets
            )
            return None if m is None else m.value
        figures = fetch_external_figures(self.conn, city_id)
        if isinstance(ranking, ExternalRanking):
            return next(
                (
                    f.value
                    for f in figures
                    if f.source == ranking.source
                    and f.metric_name == ranking.metric
                    and f.network_scope == ranking.scope
                ),
                None,
            )
        assert isinstance(ranking, ExternalRatioRanking)
        by_metric: dict[str, float] = {}
        for f in figures:
            if f.source == ranking.source:
                by_metric.setdefault(f.metric_name, f.value)
        needed = [*ranking.numerator, ranking.denominator]
        if any(m not in by_metric for m in needed) or not by_metric[ranking.denominator]:
            return None  # a missing component drops the city from this source
        return sum(by_metric[m] for m in ranking.numerator) / by_metric[ranking.denominator] * 100

    def ranks(self) -> list[RankEntry]:
        """Every configured ranking source, cities ranked highest first (rank 1 = highest)."""
        out = []
        for ranking in self.report_config.rankings:
            values = self._ranking_values(ranking)
            ranked = rank_values(list(values.items()))
            for city_id, v in sorted(values.items(), key=lambda kv: (ranked[kv[0]], kv[0])):
                out.append(
                    RankEntry(
                        source_id=ranking.id,
                        source_label=ranking.label,
                        city_id=city_id,
                        value=v,
                        rank=ranked[city_id],
                    )
                )
        return out

    # --- CSV ------------------------------------------------------------------------------

    def csv_rows(self, city_id: str | None = None) -> list[dict[str, str]]:
        """One row per (city, boundary kind, label); a label is a year or `current`."""
        rows = []
        for c in self.cities():
            if city_id is not None and c.id != city_id:
                continue
            for kind in KINDS:
                rows += self._kind_rows(c.id, kind)
        return rows

    def _kind_rows(self, city_id: str, kind: str) -> list[dict[str, str]]:
        cs = self.series(city_id, kind)
        points = [] if cs is None else cs.points
        by_label = {f.label: f for f in self.flags(city_id, kind)}
        rows = [self._row(city_id, kind, p, by_label.get(p.label)) for p in points]
        if not any(p.label == ts.CURRENT for p in points):
            run_id = self.selector.latest(self.conn, city_id, kind)
            if run_id is not None:  # a current run without a series (or not following it)
                p = ts._point(self.conn, run_id, ts.CURRENT, self.selector, None)
                rows.append(self._row(city_id, kind, p, None))
        return rows

    def _row(self, city_id: str, kind: str, p: ts.YearPoint, flag: ts.Flag | None):
        run = fetch_run(self.conn, p.run_id)
        results = fetch_run_results(self.conn, p.run_id)
        values = {pv.preset: pv.value for pv in self._preset_values(results)}
        row = {
            "city_id": city_id,
            "boundary_kind": kind,
            "label": p.label,
            "run_id": str(p.run_id),
            "osm_timestamp": p.osm_timestamp,
            "classifier_version": run["classifier_version"],
            "config_sha256": run["config_sha256"] or "",
        }
        row.update({f"tier_{t}_km": _fmt(p.tiers_km[t]) for t in ts.TIERS})
        row["ab_km"] = _fmt(p.ab_km)
        row.update({name: _fmt(values.get(name)) for name in CSV_PRESETS})
        row["population_value"] = (
            "" if run["population_value"] is None else str(run["population_value"])
        )
        row["population_year"] = (
            "" if run["population_year"] is None else str(run["population_year"])
        )
        row["flags"] = ";".join(flag.rules) if flag else ""
        return row
