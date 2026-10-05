"""Yearly time series per city and boundary, rule-based flags and the explained-against check."""

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from velometer.config import REMAINDER_ID, ActivityConfig, CityConfig
from velometer.db import (
    fetch_activity,
    fetch_diagnostics,
    fetch_run,
    fetch_run_results,
    history_runs,
    latest_done_run,
    latest_history_set,
    subarea_rows,
)
from velometer.models import ActivityYear
from velometer.pipeline.measure import SubareaMeasure, compute_metrics, select_metric
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
    legacy_km: float | None  # None: the run recorded no drift diagnostics (current/M2 runs)
    unrecognised_km: float | None


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
    missing_years: tuple[int, ...] = ()  # series years (config/history.yaml) without a done run


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
        legacy_km=diag.get("legacy_km"),
        unrecognised_km=diag.get("unrecognised_cycling_km"),
    )


def _year(osm_timestamp: str) -> int:
    return int(osm_timestamp[:4])


def _series_runs(
    conn, city_id: str, kind: str, selector, history_set_md5: str
) -> list[tuple[str, int]]:
    """(label, run_id) of one history set in label order, then the matching current run if any.

    The current run follows only a last history year that is its own year (the 1 January
    before it).
    """
    runs = history_runs(
        conn,
        city_id,
        kind,
        classifier_version=selector.version,
        classifier_parameters=selector.parameters,
        config_sha256=selector.config_sha256,
        history_set_md5=history_set_md5,
    )
    out = [(ts[:4], run_id) for ts, run_id in sorted(runs.items())]
    current = latest_done_run(
        conn, city_id, kind, selector.version, selector.parameters, selector.config_sha256
    )
    if (
        out
        and current is not None
        and _year(fetch_run(conn, current)["osm_timestamp"]) == int(out[-1][0])
    ):
        out.append((CURRENT, current))
    return out


def series(conn, city_id: str, kind: str, selector, history_set_md5: str) -> list[YearPoint]:
    """Year points of one history set in label order, then the matching current run if any.

    The current point carries the activity of year last + 1, whose window ends at the history file.
    """
    activity = {
        a.year: a
        for a in fetch_activity(conn, city_id, kind, history_set_md5, selector.activity_sha256)
    }
    runs = _series_runs(conn, city_id, kind, selector, history_set_md5)
    return [
        _point(
            conn,
            run_id,
            label,
            selector,
            activity.get(
                int(runs[-2][0]) + 1 if label == CURRENT else int(label)  # current: last + 1
            ),
        )
        for label, run_id in runs
    ]


@dataclass(frozen=True)
class SubareaPoint:
    label: str  # as YearPoint.label
    run_id: int
    osm_timestamp: str
    headline: float | None  # ours_headline in percent, on the selector's presets
    tier_km: dict[str, float]  # per_side km of tiers A-E


def subarea_series(
    conn, city_id: str, selector, history_set_md5: str
) -> dict[str, list[SubareaPoint]]:
    """The yearly points of each subarea (LAU runs of the selector), by subarea_id.

    A run without subarea rows adds no point. No flags are computed per subarea. The derived
    remainder (outside every subarea) is no subarea: it has no series here.
    """
    out: dict[str, list[SubareaPoint]] = {}
    for label, run_id in _series_runs(conn, city_id, "lau", selector, history_set_md5):
        ts = fetch_run(conn, run_id)["osm_timestamp"]
        for sid, (tiers, roads) in subarea_rows(conn, run_id).items():
            if sid == REMAINDER_ID:
                continue
            metrics = compute_metrics(SubareaMeasure(tiers, roads), selector.presets.presets)
            metric = select_metric(metrics, "ours_headline", selector.presets)
            out.setdefault(sid, []).append(
                SubareaPoint(
                    label,
                    run_id,
                    ts,
                    None if metric is None else metric.value,
                    {
                        t: sum(
                            x.length_km
                            for x in tiers
                            if x.tier == t and x.length_basis == "per_side"
                        )
                        for t in TIERS
                    },
                )
            )
    return out


def missing_subarea_runs(conn, cities: list[CityConfig], selector) -> list[str]:
    """`<city>/<run_id>` of each report-classifier LAU run (the latest history set's runs and the
    latest current run) of a city with `subareas` that has no subarea rows. Remainder rows are
    not demanded (an empty remainder writes none) and do not count as subarea rows."""
    out = []
    for c in cities:
        if c.subareas is None:
            continue
        md5 = latest_history_set(
            conn,
            c.id,
            "lau",
            classifier_version=selector.version,
            classifier_parameters=selector.parameters,
            config_sha256=selector.config_sha256,
        )
        ids = [r for _, r in _series_runs(conn, c.id, "lau", selector, md5)] if md5 else []
        current = selector.latest(conn, c.id, "lau")
        if current is not None and current not in ids:
            ids.append(current)
        for run_id in sorted(ids):
            if not conn.execute(
                "SELECT 1 FROM subarea_tier_lengths WHERE run_id=? AND subarea_id!=? LIMIT 1",
                (run_id, REMAINDER_ID),
            ).fetchone():
                out.append(f"{c.id}/{run_id}")
    return out


def _drift(prev: float | None, cur: float | None, pct: float, min_km: float) -> bool:
    """A change of at least `pct` percent and at least `min_km` km. An unknown side (no
    diagnostics recorded) is never drift: unknown is not 0 km."""
    if prev is None or cur is None:
        return False
    change = abs(cur - prev)
    return prev > 0 and change / prev * 100 >= pct and change >= min_km


def _consecutive(prev: YearPoint, p: YearPoint) -> bool:
    """Adjacent years, or the current point after the 1 January of its own year."""
    if prev.label == CURRENT:
        return False
    if p.label == CURRENT:
        return int(prev.label) == _year(p.osm_timestamp)
    return int(p.label) == int(prev.label) + 1


def flags(
    points: list[YearPoint],
    cfg: ActivityConfig,
    *,
    current_fraction: float,
    city_id: str = "",
    kind: str = "",
) -> list[Flag]:
    """Spec §2.13. Only the km floors and the spike threshold scale for the current point.

    Change rules (km_jump, tag_drift) compare consecutive points only: never across a gap.
    """
    t = cfg.flags
    edits = [p.activity.n_edits for p in points if p.label != CURRENT and p.activity is not None]
    median = statistics.median(edits) if edits else None
    out = []
    for i, p in enumerate(points):
        scale = current_fraction if p.label == CURRENT else 1.0
        rules: dict[str, str] = {}
        jump = False
        if i > 0 and _consecutive(points[i - 1], p):
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
                if _drift(a, b, t.tag_drift_pct, t.tag_drift_min_km * scale):
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
    population = (
        "no population (per-100k n/a)" if pop is None else f"population {pop} held constant"
    )
    runs = ", ".join(f"{p.label}={p.run_id}" for p in years)
    return (
        f"history runs {runs}"
        + (f" · current run {cur.run_id} (OSM {cur.osm_timestamp})" if cur else " · no current run")
        + f" · history set `{set_md5[:8]}` · classifier {selector.version} "
        f"`{selector.parameters}` · config `{selector.config_sha256[:12]}`"
        f" · {population}"
    )


def build_city(
    conn, city_id: str, kind: str, selector, years: range | None = None
) -> CitySeries | None:
    """The city's series for the latest history set of this config, or None without history.

    `years` (config/history.yaml) are the years the series must hold; each one without a done
    run is listed in missing_years and noted.
    """
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
    labels = {p.label for p in points}
    missing = tuple(y for y in (years or ()) if str(y) not in labels)
    for y in missing:
        notes.append(
            f"{city_id}/{kind}/{y} has no done history run: no point, and no change rule "
            "compares across the gap"
        )
    fraction = 1.0
    if points and points[-1].label == CURRENT:
        fraction = current_fraction(points[-1].osm_timestamp)
    else:
        current = latest_done_run(
            conn, city_id, kind, selector.version, selector.parameters, selector.config_sha256
        )
        if current is None:
            notes.append(f"{city_id}/{kind} has no current run of this config: no current point")
        else:
            ts = fetch_run(conn, current)["osm_timestamp"]
            last = next((p.label for p in reversed(points)), "none")
            notes.append(
                f"{city_id}/{kind} current run {current} (OSM {ts}) does not follow the last "
                f"history year {last}: no current point"
            )
    return CitySeries(
        city_id,
        kind,
        set_md5,
        points,
        fraction,
        provenance_line(conn, selector, set_md5, points),
        notes,
        missing,
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
    path: Path, flag_list: list[Flag], shown: set[tuple[str, str]] | None = None
) -> list[str]:
    """`### city/kind/label` headings (of these (city, kind) pairs) that match no current flag."""
    current = {f.key for f in flag_list}
    return sorted(
        h
        for h in headings(path.read_text())
        if h.count("/") == 2
        and (shown is None or tuple(h.rsplit("/", 1)[0].split("/")) in shown)
        and h not in current
    )


_HEADING = re.compile(r"^#{1,3} ", re.M)


def explanation(path: Path, key: str) -> str | None:
    """The text under the `### city/kind/label` heading `key`, up to the next `#`-`###` heading.

    None when the file is unreadable, the heading is absent (as `headings` parses them) or it has
    no text under it.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    if key not in headings(text):
        return None
    m = re.search(rf"^### {re.escape(key)}\s*$", text, re.M)
    body = text[m.end() :]
    nxt = _HEADING.search(body)
    body = (body if nxt is None else body[: nxt.start()]).strip()
    return body or None


# Markers written before schema v6 carry an `activity=<sha>` item; activity.yaml is part of the run
# identity now, so it is ignored.
IGNORED_MARKER_KEYS = ("activity",)


def _marker_items(path: Path) -> dict[str, str]:
    m = EXPLAINED_AGAINST.search(path.read_text())
    if m is None:
        return {}
    out = {}
    for item in m.group("body").split():
        key, _, value = item.partition("=")
        if key in IGNORED_MARKER_KEYS and value:
            continue
        if not value or "/" not in key:
            raise ValueError(f"{path}: bad explained-against entry {item!r}")
        out[key] = value
    return out


def explained_against(path: Path) -> dict[str, str]:
    """`city/kind` -> history_set_md5[:8] from the marker ({} if there is none)."""
    return _marker_items(path)


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
