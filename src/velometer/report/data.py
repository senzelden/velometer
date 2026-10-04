"""The one read-only query layer every report surface shares (CSV, charts, app, methodology).

It never writes: `open_readonly` opens the database with `mode=ro`. "The current point", "the
series" and "the headline" are defined here once, by reusing `timeseries.build_city`,
`reconcile.reconcile_city` and `pipeline.measure.select_metric`.
"""

import sqlite3
from pathlib import Path
from string import Formatter

from pydantic import BaseModel, ConfigDict

from velometer import reconcile as rc
from velometer import timeseries as ts
from velometer.config import (
    ConfigError,
    ExternalRanking,
    ExternalRatioRanking,
    PresetRanking,
    load_activity,
    load_cities,
    load_history,
    load_report,
)
from velometer.db import (
    SCHEMA_VERSION,
    SchemaError,
    fetch_cities,
    fetch_external_figures,
    fetch_run,
    fetch_run_results,
    subarea_names,
    subarea_rows,
)
from velometer.models import City
from velometer.pipeline.measure import SubareaMeasure, compute_metrics, select_metric
from velometer.selection import report_selector, trusted_countries

KINDS = ("lau", "fua")
CSV_PRESETS = ("ours_headline", "ecf_qecio", "clean_cities_2025")
# What each road class (a preset's denominator) is, in words for the report surfaces.
ROAD_CLASS_TEXT = {
    "main_excl_motorway": "main roads (excl. motorways)",
    "main_incl_motorway": "main roads (incl. motorways)",
    "main_incl_motorway_raw": "main roads (incl. motorways, per carriageway)",
    "all_public": "all public roads",
}
HEADLINE_UNIT = f"A+B km per 100 km of {ROAD_CLASS_TEXT['main_excl_motorway']}"


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


class RankingRow(_Frozen):
    """One (ranking source, city) cell of the rankings, with or without a figure."""

    source_id: str
    source_label: str
    city_id: str
    value: float | None
    rank: int | None  # None: no figure from this source
    n_ranked: int  # cities with a value in this source


def open_readonly(db_path: Path) -> sqlite3.Connection:
    """The database opened read-only (`mode=ro`).

    FileNotFoundError when it does not exist; SchemaError when its schema is not this
    velometer's (`SCHEMA_VERSION`): an older one needs `velometer migrate`, which this read-only
    path never runs.
    """
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.Error:
        conn.close()
        raise
    if version != SCHEMA_VERSION:
        conn.close()
        hint = (
            "run `velometer migrate`"
            if version < SCHEMA_VERSION
            else "upgrade velometer to read it"
        )
        raise SchemaError(
            f"database {db_path} has schema v{version}, this velometer reads "
            f"v{SCHEMA_VERSION}: {hint}"
        )
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


class SubareaRow(_Frozen):
    """One subarea (Bezirk) of a city's current LAU run: headline, per-side tier km, A share."""

    subarea_id: str
    name: str
    headline: float | None  # ours_headline on the subarea's own road lengths
    tier_km: dict[str, float]  # per_side km of tiers A-E
    a_share_of_ab: float | None  # tier A's share of A+B in percent; None without A+B km


def _fmt(v: float | None) -> str:
    return "" if v is None else f"{v:.3f}"


class ReportData:
    """Read-only report queries over an open connection and the config directory."""

    def __init__(self, conn: sqlite3.Connection, config_dir: Path):
        self.conn = conn
        self.config_dir = Path(config_dir)
        self.selector = report_selector(self.config_dir)
        self.report_config = load_report(
            self.config_dir / "report.yaml",
            self.config_dir / "presets.yaml",
            self.config_dir / "cities.yaml",
        )
        self.activity = load_activity(self.config_dir / "activity.yaml")
        self.years = load_history(self.config_dir / "history.yaml").year_range()
        self._cities: list[City] | None = None
        self._all_cities: list[City] | None = None
        self._city_config: dict[str, dict] | None = None
        self._series: dict[tuple[str, str], ts.CitySeries | None] = {}

    def preset_labels(self) -> dict[str, str]:
        """Each preset's label, from its `kind: preset` ranking in report.yaml ("Ours: ..."):
        these are our values on a publisher's method, never the published figure. A preset
        without a ranking falls back to "Ours: <id>"."""
        labels = {
            r.preset: r.label for r in self.report_config.rankings if isinstance(r, PresetRanking)
        }
        return {p.id: labels.get(p.id, f"Ours: {p.id}") for p in self.selector.presets.presets}

    def preset_units(self) -> dict[str, str]:
        """What each preset's value measures: its tiers' km per 100 km of its own denominator."""
        return {
            p.id: f"{'+'.join(p.tiers)} km per 100 km of {ROAD_CLASS_TEXT[p.denominator]}"
            for p in self.selector.presets.presets
        }

    def all_cities(self) -> list[City]:
        """Every city in the database, trusted or not (only `results` shows the difference)."""
        if self._all_cities is None:
            self._all_cities = fetch_cities(self.conn)
        return self._all_cities

    def cities(self) -> list[City]:
        """The cities of trusted countries: the one filter every report surface goes through."""
        if self._cities is None:
            trusted = trusted_countries(self.config_dir)
            self._cities = [c for c in self.all_cities() if c.country_iso2 in trusted]
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

    def city_fields(self) -> dict[str, dict]:
        """city id -> its config/cities.yaml fields (the scope patterns format over these)."""
        if self._city_config is None:
            self._city_config = {
                c.id: c.model_dump() for c in load_cities(self.config_dir / "cities.yaml")
            }
        return self._city_config

    def _ranking_values(self, ranking) -> dict[str, float]:
        out: dict[str, float] = {}
        for c in self.cities():
            v = self._ranking_value(ranking, c.id)
            if v is not None:
                out[c.id] = v
        return out

    def _ratio_scope(self, ranking, city_id: str) -> str | None:
        """The ratio ranking's scope for this city; None when a field it names has no value."""
        fields = self.city_fields().get(city_id, {})
        try:
            scope = ranking.scope.format_map(fields)
        except KeyError as e:
            raise ConfigError(
                f"ranking {ranking.id!r}: scope {ranking.scope!r} names unknown city field {e}"
            ) from e
        if any(
            fields.get(name) is None for _, name, _, _ in Formatter().parse(ranking.scope) if name
        ):
            return None
        return scope

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
        scope = self._ratio_scope(ranking, city_id)
        if scope is None:
            return None
        by_metric: dict[str, float] = {}
        for f in figures:
            if f.source == ranking.source and f.network_scope == scope:
                if f.metric_name in by_metric:
                    raise ConfigError(
                        f"{city_id}: {ranking.source} {f.metric_name}: 2 figures with scope {scope}"
                    )
                by_metric[f.metric_name] = f.value
        needed = [*ranking.numerator, ranking.denominator]
        if any(m not in by_metric for m in needed) or not by_metric[ranking.denominator]:
            return None  # a missing component drops the city from this source
        return sum(by_metric[m] for m in ranking.numerator) / by_metric[ranking.denominator] * 100

    def ranking_rows(self) -> list[RankingRow]:
        """One row per (source, city), report.yaml order; ranked cities first (highest first),
        then the cities without a figure (rank and value None)."""
        out = []
        ids = [c.id for c in self.cities()]
        for ranking in self.report_config.rankings:
            values = self._ranking_values(ranking)
            ranked = rank_values(list(values.items()))
            n = len(values)
            for city_id in sorted(values, key=lambda k: (ranked[k], k)):
                out.append(self._ranking_row(ranking, city_id, values[city_id], ranked[city_id], n))
            out += [
                self._ranking_row(ranking, i, None, None, n) for i in sorted(ids) if i not in values
            ]
        return out

    @staticmethod
    def _ranking_row(ranking, city_id, value, rank, n) -> RankingRow:
        return RankingRow(
            source_id=ranking.id,
            source_label=ranking.label,
            city_id=city_id,
            value=value,
            rank=rank,
            n_ranked=n,
        )

    def ranks(self) -> list[RankEntry]:
        """The ranked cells of `ranking_rows()` (rank 1 = highest)."""
        return [
            RankEntry(
                source_id=r.source_id,
                source_label=r.source_label,
                city_id=r.city_id,
                value=r.value,
                rank=r.rank,
            )
            for r in self.ranking_rows()
            if r.rank is not None and r.value is not None
        ]

    # --- subareas (Bezirke) ---------------------------------------------------------------

    def _has_subareas(self, city_id: str) -> bool:
        """A trusted city whose config lists subareas (the one gate of every subarea surface)."""
        if city_id not in {c.id for c in self.cities()}:
            return False
        return bool(self.city_fields().get(city_id, {}).get("subareas"))

    def _headline(self, tiers, roads) -> float | None:
        metrics = compute_metrics(SubareaMeasure(tiers, roads), self.selector.presets.presets)
        metric = select_metric(metrics, "ours_headline", self.selector.presets)
        return None if metric is None else metric.value

    def subareas(self, city_id: str) -> list[SubareaRow] | None:
        """The latest current LAU run's subarea rows by name; None for a city without subareas,
        an untrusted city, or a run without subarea rows."""
        if not self._has_subareas(city_id):
            return None
        run_id = self.selector.latest(self.conn, city_id, "lau")
        parts = {} if run_id is None else subarea_rows(self.conn, run_id)
        if not parts:
            return None
        names = subarea_names(self.conn, city_id)
        rows = []
        for sid, (tiers, roads) in parts.items():
            km = {
                t: sum(x.length_km for x in tiers if x.tier == t and x.length_basis == "per_side")
                for t in ts.TIERS
            }
            ab = km["A"] + km["B"]
            rows.append(
                SubareaRow(
                    subarea_id=sid,
                    name=names.get(sid, sid),
                    headline=self._headline(tiers, roads),
                    tier_km=km,
                    a_share_of_ab=100 * km["A"] / ab if ab else None,
                )
            )
        return sorted(rows, key=lambda r: (r.name, r.subarea_id))

    def subarea_series(self, city_id: str) -> dict[str, list[ts.SubareaPoint]]:
        """The yearly headline and tier km of each subarea, by subarea_id ({} where `subareas`
        is None, or the city has no history set)."""
        if not self._has_subareas(city_id):
            return {}
        cs = self.series(city_id, "lau")
        if cs is None:
            return {}
        return ts.subarea_series(self.conn, city_id, self.selector, cs.set_md5)

    def subarea_csv_rows(self, city_id: str) -> list[dict[str, str]]:
        """One row per (run, subarea, tier, length basis) over the series runs and the latest
        current run: tier km summed over subtypes, with each run's own provenance."""
        run_ids = {p.run_id for pts in self.subarea_series(city_id).values() for p in pts}
        if not self._has_subareas(city_id):
            return []
        current = self.selector.latest(self.conn, city_id, "lau")
        if current is not None:
            run_ids.add(current)
        names = subarea_names(self.conn, city_id)
        out = []
        for run_id in sorted(run_ids):
            run = fetch_run(self.conn, run_id)
            for sid, (tiers, _roads) in sorted(subarea_rows(self.conn, run_id).items()):
                km: dict[tuple[str, str], float] = {}
                for t in tiers:
                    key = (t.tier, t.length_basis)
                    km[key] = km.get(key, 0.0) + t.length_km
                for (tier, basis), length in sorted(km.items()):
                    out.append(
                        {
                            "city_id": city_id,
                            "subarea_id": sid,
                            "name": names.get(sid, sid),
                            "run_id": str(run_id),
                            "osm_timestamp": run["osm_timestamp"],
                            "classifier_version": run["classifier_version"],
                            "git_commit": run["git_commit"],
                            "config_sha256": run["config_sha256"] or "",
                            "boundary_sha256": run["boundary_sha256"],
                            "subarea_sha": run["subarea_sha"] or "",
                            "tier": tier,
                            "length_basis": basis,
                            "length_km": _fmt(length),
                        }
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
