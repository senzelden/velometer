"""Why a published figure differs from our mapped km, along the six dimensions of
config/differences.yaml. One row per reconcile gap, then one per reported figure; each row
lists the dimensions on which the source's side is not ours."""

from dataclasses import dataclass
from datetime import date

from velometer import reconcile as rc
from velometer.config import DifferencesConfig
from velometer.db import fetch_external_figures
from velometer.models import ExternalFigure
from velometer.report.data import ROAD_CLASS_TEXT, ReportData

# Comparison tags that say the definition or scope of the source's figure is not ours.
_SCOPE_TAGS = frozenset({"definition_mismatch", "scope_mismatch"})


@dataclass(frozen=True)
class Driver:
    dimension: str
    ours: str
    theirs: str


@dataclass(frozen=True)
class DifferenceRow:
    source: str
    metric: str
    theirs: float
    unit: str
    ours: float | None
    ours_label: str | None
    gap_pct: float | None
    reference_date: date | None
    url: str | None
    drivers: list[Driver]


def _ours_label(data: ReportData, spec: dict | None) -> str | None:
    if not spec:
        return None
    if "preset" in spec:
        return data.preset_labels().get(spec["preset"], spec["preset"])
    if "road_class" in spec:
        return f"our km of {ROAD_CLASS_TEXT.get(spec['road_class'], spec['road_class'])}"
    tiers = "+".join(spec.get("tiers", []))
    return f"our tiers {tiers} km" if tiers else None


def _drivers(
    cfg: DifferencesConfig,
    *,
    source: str,
    metric: str,
    snapshot: date | None,
    reference_date: date | None,
    date_gap_days: int,
    length_basis: str | None,
    scope_differs: bool,
    boundary_differs: bool,
    date_differs: bool | None,
) -> list[Driver]:
    ours = cfg.ours
    out: list[Driver] = []
    label = cfg.labels.get(metric)
    if scope_differs and label:
        out.append(Driver("scope", ours["scope"], label))
    if metric in cfg.metric_kinds:
        out.append(Driver("kind", ours["kind"], cfg.metric_kinds[metric]))
    if length_basis is not None and cfg.length_bases[length_basis] != ours["length"]:
        out.append(Driver("length", ours["length"], cfg.length_bases[length_basis]))
    if date_differs is None:
        date_differs = (
            snapshot is not None
            and reference_date is not None
            and abs((snapshot - reference_date).days) > date_gap_days
        )
    if date_differs and reference_date is not None:
        out.append(
            Driver(
                "date",
                f"OSM snapshot of {snapshot.isoformat()}" if snapshot else "latest OSM snapshot",
                reference_date.isoformat(),
            )
        )
    area = cfg.areas.get(source) or (cfg.areas["default"] if boundary_differs else None)
    if area is not None and area != ours["area"]:
        out.append(Driver("area", ours["area"], area))
    method = cfg.source_methods.get(source)
    if method is not None and method != ours["method"]:
        out.append(Driver("method", ours["method"], method))
    return out


def _url(figures: list[ExternalFigure], source: str, metric: str, value: float) -> str | None:
    return next(
        (
            f.source_url
            for f in figures
            if (f.source, f.metric_name, f.value) == (source, metric, value)
        ),
        None,
    )


def difference_rows(data: ReportData, city_id: str, cfg: DifferencesConfig) -> list[DifferenceRow]:
    """Reconcile gaps first (ours, theirs and the gap as `Gap` has them), then every reported
    figure (`ours=None`); each with the drivers where its side differs from ours."""
    current = data.current(city_id, "lau")
    snapshot = date.fromisoformat(current.osm_timestamp[:10]) if current else None
    recon_cfg = rc.load_config(data.config_dir / "reconcile.yaml")
    date_gap_days = int(recon_cfg["date_gap_days"])
    comparisons = {c.id: c for c in rc.load_comparisons(data.config_dir / "reconcile.yaml")}
    figures = fetch_external_figures(data.conn, city_id)
    rows: list[DifferenceRow] = []
    report = data.reconcile(city_id)
    for g in report.gaps if report else []:
        comp = comparisons[g.comparison]
        rows.append(
            DifferenceRow(
                source=g.source,
                metric=comp.metric_name,
                theirs=g.theirs,
                unit=g.unit,
                ours=g.ours,
                ours_label=_ours_label(data, comp.ours),
                gap_pct=g.gap_pct,
                reference_date=g.reference_date,
                url=_url(figures, g.source, comp.metric_name, g.theirs),
                drivers=_drivers(
                    cfg,
                    source=g.source,
                    metric=comp.metric_name,
                    snapshot=snapshot,
                    reference_date=g.reference_date,
                    date_gap_days=date_gap_days,
                    length_basis=None,
                    scope_differs=bool(_SCOPE_TAGS & set(g.tags)),
                    boundary_differs="boundary_mismatch" in g.tags,
                    date_differs="date_gap" in g.tags,
                ),
            )
        )
    for f in data.reported_figures(city_id):
        rows.append(
            DifferenceRow(
                source=f.source,
                metric=f.metric_name,
                theirs=f.value,
                unit=f.unit,
                ours=None,
                ours_label=None,
                gap_pct=None,
                reference_date=f.reference_date,
                url=f.source_url,
                drivers=_drivers(
                    cfg,
                    source=f.source,
                    metric=f.metric_name,
                    snapshot=snapshot,
                    reference_date=f.reference_date,
                    date_gap_days=date_gap_days,
                    length_basis=f.length_basis,
                    scope_differs=True,
                    boundary_differs=False,
                    date_differs=None,
                ),
            )
        )
    return rows
