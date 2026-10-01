"""Yearly time series per city and boundary, rule-based flags and the explained-against check."""

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from velometer.config import ActivityConfig
from velometer.db import (
    fetch_activity,
    fetch_diagnostics,
    fetch_run,
    fetch_run_results,
    history_runs,
    latest_done_run,
    latest_history_set,
)
from velometer.models import ActivityYear
from velometer.pipeline.measure import select_metric
from velometer.reconcile import EXPLAINED_AGAINST, headings, ours_value

BEGIN, END = "<!-- timeseries:begin -->", "<!-- timeseries:end -->"
CURRENT = "current"
TIERS = "ABCDE"
_AB = {"tiers": ["A", "B"], "basis": "per_side"}


@dataclass(frozen=True)
class YearPoint:
    label: str  # "2018" ... "2026" or "current"
    run_id: int
    osm_timestamp: str
    headline: float | None  # ours_headline, in percent, on the selector's presets
    ab_km: float  # tiers A+B, per_side km
    tiers_km: dict[str, float]
    activity: ActivityYear | None
    legacy_km: float
    unrecognised_km: float


@dataclass(frozen=True)
class Flag:
    city_id: str
    kind: str
    label: str
    rules: tuple[str, ...]
    detail: str

    @property
    def key(self) -> str:
        return f"{self.city_id}/{self.kind}/{self.label}"


@dataclass(frozen=True)
class CitySeries:
    city_id: str
    kind: str
    set_md5: str
    points: list[YearPoint]
    current_fraction: float
    provenance: str
    notes: list[str] = field(default_factory=list)


def current_fraction(osm_timestamp: str) -> float:
    """Share of its year elapsed at the timestamp, clamped to (0, 1]."""
    ts = datetime.fromisoformat(osm_timestamp.replace("Z", "+00:00"))
    start = ts.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    days = 366 if ts.year % 4 == 0 and (ts.year % 100 != 0 or ts.year % 400 == 0) else 365
    return min(1.0, max((ts - start).total_seconds() / (days * 86400), 1e-9))


def _point(conn, run_id: int, label: str, selector, activity: ActivityYear | None) -> YearPoint:
    r = fetch_run_results(conn, run_id)
    metric = select_metric(r.metrics, "ours_headline", selector.presets)
    tiers: dict[str, float] = {
        t: sum(x.length_km for x in r.tier_lengths if x.tier == t and x.length_basis == "per_side")
        for t in TIERS
    }
    diag = fetch_diagnostics(conn, run_id)
    return YearPoint(
        label=label,
        run_id=run_id,
        osm_timestamp=r.osm_timestamp,
        headline=None if metric is None else metric.value,
        ab_km=ours_value(r, _AB, selector.presets) or 0.0,
        tiers_km=tiers,
        activity=activity,
        legacy_km=diag.get("legacy_km", 0.0),
        unrecognised_km=diag.get("unrecognised_cycling_km", 0.0),
    )


def series(conn, city_id: str, kind: str, selector, history_set_md5: str) -> list[YearPoint]:
    """Year points of one history set in label order, then the matching current run if any."""
    runs = history_runs(
        conn,
        city_id,
        kind,
        classifier_version=selector.version,
        classifier_parameters=selector.parameters,
        config_sha256=selector.config_sha256,
        history_set_md5=history_set_md5,
    )
    activity = {a.year: a for a in fetch_activity(conn, city_id, kind, history_set_md5)}
    points = [
        _point(conn, run_id, ts[:4], selector, activity.get(int(ts[:4])))
        for ts, run_id in sorted(runs.items())
    ]
    current = latest_done_run(
        conn, city_id, kind, selector.version, selector.parameters, selector.config_sha256
    )
    if points and current is not None:
        points.append(
            _point(conn, current, CURRENT, selector, activity.get(int(points[-1].label) + 1))
        )
    return points


def _drift(prev: float, cur: float, pct: float) -> bool:
    return prev > 0 and abs(cur - prev) / prev * 100 >= pct


def flags(
    points: list[YearPoint],
    cfg: ActivityConfig,
    *,
    current_fraction: float,
    city_id: str = "",
    kind: str = "",
) -> list[Flag]:
    """Spec §2.13. Only min_km and the spike threshold scale for the current point."""
    t = cfg.flags
    edits = [p.activity.n_edits for p in points if p.label != CURRENT and p.activity is not None]
    median = statistics.median(edits) if edits else None
    out = []
    for i, p in enumerate(points):
        scale = current_fraction if p.label == CURRENT else 1.0
        rules: dict[str, str] = {}
        jump = False
        if i > 0:
            prev = points[i - 1]
            delta = p.ab_km - prev.ab_km
            need = max(t.km_jump_pct / 100 * prev.ab_km, t.km_jump_min_km * scale)
            jump = abs(delta) >= need
            if jump:
                rules["km_jump"] = f"A+B km {prev.ab_km:.1f} -> {p.ab_km:.1f} (needs {need:.1f})"
            for name, a, b in (
                ("legacy_km", prev.legacy_km, p.legacy_km),
                ("unrecognised_km", prev.unrecognised_km, p.unrecognised_km),
            ):
                if _drift(a, b, t.tag_drift_pct):
                    rules.setdefault("tag_drift", f"{name} {a:.1f} -> {b:.1f}")
        spike = False
        if p.activity is not None and median:  # no median or 0: nothing to spike against
            limit = t.activity_spike_factor * median * scale
            spike = p.activity.n_edits >= limit
            if spike:
                rules["activity_spike"] = f"{p.activity.n_edits} edits (limit {limit:.1f})"
        if jump and spike:
            rules["campaign_suspected"] = "km_jump and activity_spike"
        if jump and p.activity is not None and p.activity.top_mapper_share >= t.single_mapper_share:
            rules["single_mapper"] = f"top mapper share {p.activity.top_mapper_share:.2f}"
        if rules:
            ordered = [
                r
                for r in ("km_jump", "activity_spike", "campaign_suspected", "single_mapper")
                if r in rules
            ] + (["tag_drift"] if "tag_drift" in rules else [])
            out.append(
                Flag(city_id, kind, p.label, tuple(ordered), "; ".join(rules[r] for r in ordered))
            )
    return out


def _n(v: float | None, spec: str = ",.1f") -> str:
    return "n/a" if v is None else format(v, spec)


def render_block(
    points_by_city_kind: dict[tuple[str, str], list[YearPoint]],
    flag_list: list[Flag],
    provenance: dict[tuple[str, str], str] | None = None,
) -> str:
    provenance = provenance or {}
    lines = [BEGIN, ""]
    for (city, kind), points in sorted(points_by_city_kind.items()):
        by_label = {f.label: f for f in flag_list if (f.city_id, f.kind) == (city, kind)}
        lines += [f"#### {city}/{kind}", ""]
        if (city, kind) in provenance:
            lines += [f"Provenance: {provenance[(city, kind)]}", ""]
        lines += [
            "| year | headline % | A+B km | A | B | C | D | E | edits | mappers "
            "| top mapper | legacy km | unrecognised km | flags |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for p in points:
            a = p.activity
            f = by_label.get(p.label)
            lines.append(
                f"| {p.label} | {_n(p.headline)} | {_n(p.ab_km)} "
                + " ".join(f"| {_n(p.tiers_km[t])}" for t in TIERS)
                + f" | {_n(a and a.n_edits, ',d')} | {_n(a and a.n_mappers, ',d')} "
                f"| {_n(a and a.top_mapper_share, '.2f')} | {_n(p.legacy_km)} "
                f"| {_n(p.unrecognised_km)} | {', '.join(f.rules) if f else ''} |"
            )
        lines.append("")
    lines.append(END)
    return "\n".join(lines)


def provenance_line(conn, selector, set_md5: str, points: list[YearPoint]) -> str:
    years = [p for p in points if p.label != CURRENT]
    cur = next((p for p in points if p.label == CURRENT), None)
    pop = fetch_run(conn, years[0].run_id).get("population_year") if years else None
    runs = ", ".join(f"{p.label}={p.run_id}" for p in years)
    return (
        f"history runs {runs}"
        + (f" · current run {cur.run_id} (OSM {cur.osm_timestamp})" if cur else " · no current run")
        + f" · history set `{set_md5[:8]}` · classifier {selector.version} "
        f"`{selector.parameters}` · config `{selector.config_sha256[:12]}`"
        f" · population {pop} held constant"
    )


def build_city(conn, city_id: str, kind: str, selector) -> CitySeries | None:
    """The city's series for the latest history set of this config, or None without history."""
    set_md5 = latest_history_set(
        conn,
        city_id,
        kind,
        classifier_version=selector.version,
        classifier_parameters=selector.parameters,
        config_sha256=selector.config_sha256,
    )
    if set_md5 is None:
        return None
    points = series(conn, city_id, kind, selector, set_md5)
    notes = []
    fraction = 1.0
    if points and points[-1].label == CURRENT:
        fraction = current_fraction(points[-1].osm_timestamp)
    else:
        notes.append(f"{city_id}/{kind} has no current run of this config: no current point")
    return CitySeries(
        city_id,
        kind,
        set_md5,
        points,
        fraction,
        provenance_line(conn, selector, set_md5, points),
        notes,
    )


def city_flags(cs: CitySeries, cfg: ActivityConfig) -> list[Flag]:
    return flags(
        cs.points, cfg, current_fraction=cs.current_fraction, city_id=cs.city_id, kind=cs.kind
    )


def check_markers(path: Path) -> None:
    """Raise ValueError (OSError if unreadable) unless the generated-block markers are present."""
    text = path.read_text()
    if BEGIN not in text or END not in text:
        raise ValueError(f"{path}: markers {BEGIN} / {END} not found")


def write_report(path: Path, block: str) -> None:
    text = path.read_text()
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"{path}: markers {BEGIN} / {END} not found")
    path.write_text(pattern.sub(lambda _: block, text, count=1))


def missing_explanations(path: Path, flag_list: list[Flag]) -> list[str]:
    found = headings(path.read_text())
    return [f.key for f in flag_list if f.key not in found]


def stale_explanations(
    path: Path, flag_list: list[Flag], cities: set[str] | None = None
) -> list[str]:
    """`### city/kind/label` headings (of these cities) that match no current flag."""
    current = {f.key for f in flag_list}
    return sorted(
        h
        for h in headings(path.read_text())
        if h.count("/") == 2 and (cities is None or h.split("/")[0] in cities) and h not in current
    )


def explained_against(path: Path) -> dict[str, str]:
    """`city/kind` -> history_set_md5[:8] from the marker ({} if there is none)."""
    m = EXPLAINED_AGAINST.search(path.read_text())
    if m is None:
        return {}
    out = {}
    for item in m.group("body").split():
        key, _, md5 = item.partition("=")
        if not md5 or "/" not in key:
            raise ValueError(f"{path}: bad explained-against entry {item!r}")
        out[key] = md5
    return out


def explained_against_marker(sets: dict[tuple[str, str], str]) -> str:
    body = " ".join(f"{c}/{k}={md5[:8]}" for (c, k), md5 in sorted(sets.items()))
    return f"<!-- explained-against: {body} -->"


def unexplained_sets(path: Path, sets: dict[tuple[str, str], str]) -> list[str]:
    """`city/kind` entries whose current history set is not the one the explanations name."""
    marker = explained_against(path)
    return [
        f"{c}/{k}: explanations written against history set {marker.get(f'{c}/{k}', 'none')}, "
        f"current is {md5[:8]}"
        for (c, k), md5 in sorted(sets.items())
        if marker.get(f"{c}/{k}") != md5[:8]
    ]
