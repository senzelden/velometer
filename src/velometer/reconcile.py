"""Compare our latest run per city with external figures (config/reconcile.yaml)."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from velometer.db import (
    DEFAULT_PARAMETERS,
    RunResults,
    fetch_external_figures,
    fetch_run_results,
    latest_done_run,
)
from velometer.models import ExternalFigure

_LIKE_FOR_LIKE_SCOPES = ("whole_network", "bikenetkit_bike_network")
BEGIN, END = "<!-- reconcile:begin -->", "<!-- reconcile:end -->"


@dataclass(frozen=True)
class Comparison:
    id: str
    sources: tuple[str, ...]
    metric_name: str
    ours: dict | None
    informational: bool
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Gap:
    city_id: str
    comparison: str
    key: str
    ours: float | None
    theirs: float
    unit: str
    gap_pct: float | None
    flagged: bool
    informational: bool
    tags: tuple[str, ...]
    source: str
    reference_date: date | None
    note: str


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def load_comparisons(path: Path) -> list[Comparison]:
    out = []
    for c in load_config(path)["comparisons"]:
        src = c["external"]["source"]
        out.append(
            Comparison(
                id=c["id"],
                sources=tuple(src if isinstance(src, list) else [src]),
                metric_name=c["external"]["metric_name"],
                ours=c.get("ours"),
                informational=bool(c.get("informational", False)),
                tags=tuple(c.get("tags", [])),
            )
        )
    return out


def _matches(t, entries) -> bool:
    for e in entries:
        tier, _, sub = e.partition("/")
        if t.tier == tier and (not sub or t.subtype == sub):
            return True
    return False


def ours_value(r: RunResults, spec: dict | None) -> float | None:
    if spec is None:
        return None
    if "preset" in spec:
        return next((m.value for m in r.metrics if m.preset == spec["preset"]), None)
    if "road_class" in spec:
        return next(
            (x.length_km for x in r.road_lengths if x.road_class == spec["road_class"]), None
        )
    on_basis = [t for t in r.tier_lengths if t.length_basis == spec["basis"]]
    # measure() writes no row for a tier with no length inside the boundary, so no rows on a
    # done run's basis is a real 0 km, not n/a.
    return sum(
        t.length_km
        for t in on_basis
        if t.tier != "excluded"
        and _matches(t, spec["tiers"])
        and not _matches(t, spec.get("exclude", []))
    )


def gaps_for(
    r: RunResults,
    figures: list[ExternalFigure],
    comparisons: list[Comparison],
    *,
    threshold: float,
    date_gap_days: int,
    mismatch: dict,
) -> list[Gap]:
    ours_date = datetime.fromisoformat(r.osm_timestamp.replace("Z", "+00:00")).date()
    out = []
    for comp in comparisons:
        figs = [
            f for f in figures if f.source in comp.sources and f.metric_name == comp.metric_name
        ]
        for f in figs:
            ours = None if comp.informational else ours_value(r, comp.ours)
            gap = (ours - f.value) / f.value if ours is not None and f.value else None
            tags = list(comp.tags)
            if f.reference_date and abs((ours_date - f.reference_date).days) > date_gap_days:
                tags.append("date_gap")
            if r.city_id in mismatch.get(f.source, []):
                tags.append("boundary_mismatch")
            key = f"{r.city_id}/{comp.id}"
            if f.network_scope not in _LIKE_FOR_LIKE_SCOPES and not f.network_scope.startswith(
                "nuts3_"
            ):
                # e.g. Vienna's web-correction row: its own key (never overwrites the PDF row)
                # and tagged, since its scope is not like-for-like with ours.
                key += f"@{f.network_scope}"
                tags.append("scope_mismatch")
            if len(comp.sources) > 1:
                key += f"#{f.source}:{f.value:g}"
            out.append(
                Gap(
                    city_id=r.city_id,
                    comparison=comp.id,
                    key=key,
                    ours=ours,
                    theirs=f.value,
                    unit=f.unit,
                    gap_pct=gap,
                    flagged=(not comp.informational and gap is not None and abs(gap) > threshold),
                    informational=comp.informational,
                    tags=tuple(dict.fromkeys(tags)),
                    source=f.source,
                    reference_date=f.reference_date,
                    note=f.note,
                )
            )
    return out


def reconcile_city(
    conn,
    city_id: str,
    config_path: Path,
    boundary_kind: str = "lau",
    *,
    classifier_version: str = "v1",
    classifier_parameters: str = DEFAULT_PARAMETERS,
) -> list[Gap]:
    cfg = load_config(config_path)
    run_id = latest_done_run(
        conn, city_id, boundary_kind, classifier_version, classifier_parameters
    )
    if run_id is None:
        return []
    return gaps_for(
        fetch_run_results(conn, run_id),
        fetch_external_figures(conn, city_id),
        load_comparisons(config_path),
        threshold=cfg["threshold"],
        date_gap_days=cfg["date_gap_days"],
        mismatch=cfg.get("boundary_mismatch", {}),
    )


def _fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:+.1f}%" if pct else f"{v:,.1f}"


def render_block(gaps_by_city: dict[str, list[Gap]]) -> str:
    lines = [BEGIN, ""]
    for city, gaps in sorted(gaps_by_city.items()):
        lines += [
            f"#### {city}",
            "",
            "| key | ours | theirs | gap | flag | tags | source (date) |",
            "|---|---:|---:|---:|---|---|---|",
        ]
        for g in gaps:
            flag = "info" if g.informational else ("**>20%**" if g.flagged else "ok")
            lines.append(
                f"| `{g.key}` | {_fmt(g.ours)} | {_fmt(g.theirs)} | {_fmt(g.gap_pct, True)} "
                f"| {flag} | {', '.join(g.tags)} | {g.source} ({g.reference_date or '?'}) |"
            )
        lines.append("")
    lines.append(END)
    return "\n".join(lines)


def write_report(path: Path, gaps_by_city: dict[str, list[Gap]]) -> None:
    text = path.read_text()
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"{path}: markers {BEGIN} / {END} not found")
    path.write_text(pattern.sub(lambda m: render_block(gaps_by_city), text, count=1))


def missing_explanations(path: Path, gaps: list[Gap]) -> list[str]:
    text = path.read_text()
    headings = set(re.findall(r"^### (\S+)\s*$", text, re.M))
    return [g.key for g in gaps if g.flagged and g.key not in headings]
