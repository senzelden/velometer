"""Why a published figure differs from our mapped km, along the six dimensions of
config/differences.yaml. One row per reconcile gap, then one per reported figure; each row
lists the dimensions on which the source's side is not ours."""

from dataclasses import dataclass
from datetime import date

from velometer import reconcile as rc
from velometer.config import BasisRef, DifferencesConfig
from velometer.db import fetch_external_figures
from velometer.i18n import Lang, t
from velometer.models import ExternalFigure
from velometer.report.data import ROAD_CLASS_TEXT, ReportData

NOT_STATED = "basis not stated by the source"
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
    basis: str | None = None  # our length basis of a gap row ("per_side", "qecio_weighted", ...)
    scope: str | None = None  # a reported figure's network scope ("whole_network", "vorrangnetz")
    note: str = ""  # the figure's own note (reported) or the comparison's (gap)


def _ours_label(data: ReportData, spec: dict | None, lang: Lang = "en") -> str | None:
    if not spec:
        return None
    if "preset" in spec:
        return data.with_lang(lang).preset_labels().get(spec["preset"], spec["preset"])
    if "road_class" in spec:
        rc = spec["road_class"]
        text = t(lang, f"road_class.{rc}") if rc in ROAD_CLASS_TEXT else rc
        return t(lang, "page.figures.ours_road_class", road_class=text)
    tiers = "+".join(spec.get("tiers", []))
    return t(lang, "page.figures.ours_tiers", tiers=tiers) if tiers else None


def _basis(data: ReportData, spec: dict | None, key: str) -> str | None:
    """Our length basis of a gap row: the `~<basis>` variant of its key, else the selected one."""
    if "~" in key:
        return key.rsplit("~", 1)[1]
    if not spec:
        return None
    presets = data.selector.presets
    basis = presets.preset(spec["preset"]).basis if "preset" in spec else spec.get("basis")
    if isinstance(basis, dict):
        basis = BasisRef.model_validate(basis)
    if isinstance(basis, BasisRef):
        return getattr(presets.parameters, basis.parameter)
    if isinstance(basis, str):
        return basis
    return "road_class" if "road_class" in spec else None


def _drivers(
    cfg: DifferencesConfig,
    *,
    lang: Lang = "en",
    source: str,
    metric: str,
    snapshot: date | None,
    reference_date: date | None,
    date_gap_days: int,
    length_basis: str | None,
    our_basis: str | None = None,
    scope_differs: bool,
    boundary_differs: bool,
    date_differs: bool | None,
) -> list[Driver]:
    # each comparison reads the English config; the shown words are the `lang` ones
    loc = cfg.localised(lang)
    ours, shown = cfg.ours, loc.ours
    out: list[Driver] = []
    if scope_differs and metric in cfg.labels:
        out.append(Driver("scope", shown["scope"], loc.labels[metric]))
    if metric in cfg.metric_kinds:
        out.append(Driver("kind", shown["kind"], loc.metric_kinds[metric]))
    if length_basis is not None:
        theirs = cfg.length_bases.get(length_basis, NOT_STATED)
        if theirs != ours["length"]:
            # an unlisted basis id is one the source does not state
            words = loc.length_bases.get(length_basis) or loc.length_bases.get("unknown", theirs)
            out.append(Driver("length", shown["length"], words))
    source_length = cfg.source_length_bases.get(f"{source}/{metric}")
    if source_length is not None and our_basis not in source_length.matches:
        ours_length = loc.bases.get(our_basis, shown["length"]) if our_basis else shown["length"]
        out.append(
            Driver("length", ours_length, loc.source_length_bases[f"{source}/{metric}"].theirs)
        )
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
                t(lang, "sources.snapshot", date=snapshot.isoformat())
                if snapshot
                else t(lang, "page.figures.latest_snapshot"),
                reference_date.isoformat(),
            )
        )
    if boundary_differs:
        out.append(Driver("area", shown["area"], loc.areas.get(source, loc.areas["default"])))
    method = cfg.source_methods.get(source)
    if method is not None and method != ours["method"]:
        out.append(Driver("method", shown["method"], loc.source_methods[source]))
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


def difference_rows(
    data: ReportData, city_id: str, cfg: DifferencesConfig, lang: Lang = "en"
) -> list[DifferenceRow]:
    """Reconcile gaps first (ours, theirs and the gap as `Gap` has them), then every reported
    figure (`ours=None`); each with the drivers where its side differs from ours, the words in
    `lang` (the reported figures' notes too)."""
    data = data.with_lang(lang)
    current = data.current(city_id, "lau")
    snapshot = date.fromisoformat(current.osm_timestamp[:10]) if current else None
    recon_cfg = rc.load_config(data.config_dir / "reconcile.yaml")
    date_gap_days = int(recon_cfg["date_gap_days"])
    comparisons = {c.id: c for c in rc.load_comparisons(data.config_dir / "reconcile.yaml")}
    figures = fetch_external_figures(data.conn, city_id)
    rows: list[DifferenceRow] = []
    report = data.reconcile(city_id)
    reported = data.reported_figures(city_id)
    shown = {(f.source, f.metric_name, f.value, f.reference_date) for f in reported}
    for g in report.gaps if report else []:
        comp = comparisons[g.comparison]
        # an informational gap without our value is the reported figure again: keep that row
        if g.ours is None and (g.source, comp.metric_name, g.theirs, g.reference_date) in shown:
            continue
        basis = _basis(data, comp.ours, g.key)
        label = _ours_label(data, comp.ours, lang)
        if label and basis in ("per_side", "qecio_weighted"):
            label = f"{label}, {cfg.localised(lang).bases.get(basis, basis)}"
        rows.append(
            DifferenceRow(
                source=g.source,
                metric=comp.metric_name,
                theirs=g.theirs,
                unit=g.unit,
                ours=g.ours,
                ours_label=label,
                gap_pct=g.gap_pct,
                reference_date=g.reference_date,
                url=_url(figures, g.source, comp.metric_name, g.theirs),
                basis=basis,
                note=g.note,
                drivers=_drivers(
                    cfg,
                    lang=lang,
                    source=g.source,
                    metric=comp.metric_name,
                    snapshot=snapshot,
                    reference_date=g.reference_date,
                    date_gap_days=date_gap_days,
                    length_basis=None,
                    our_basis=basis,
                    scope_differs=bool(_SCOPE_TAGS & set(g.tags)),
                    boundary_differs="boundary_mismatch" in g.tags,
                    date_differs="date_gap" in g.tags,
                ),
            )
        )
    for f in reported:
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
                scope=f.network_scope,
                note=f.note,
                drivers=_drivers(
                    cfg,
                    lang=lang,
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
