"""Render the M3 time-series chart: docs/review/m3_timeseries.png.

Reads velometer.sqlite through `velometer.timeseries` (the same series and flags as
`velometer timeseries`): per city and boundary, the latest history set of the config on disk plus
the current run. Run after `velometer run --years 2018-2026` and the current runs:

    uv run python scripts/render_m3_timeseries.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from velometer.cli import Selector, run_selector  # noqa: E402
from velometer.config import default_config_dir, load_activity, load_history  # noqa: E402
from velometer.db import fetch_run, open_db  # noqa: E402
from velometer.timeseries import CURRENT, TIERS, build_city, city_flags  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "velometer.sqlite"
OUT = ROOT / "docs" / "review" / "m3_timeseries.png"
FUA_CITIES = ("berlin", "paris")
SPARSE = ("2018", "2022")  # year ticks shown on the small multiples
TIER_LABEL = {
    "A": "A separated track",
    "B": "B shared foot/cycle path",
    "C": "C protected lane",
    "D": "D painted lane",
    "E": "E cycle street / bus lane",
}
# Categorical slots 1-5 of the dataviz reference palette (light), fixed order (as M2).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0"


def series_years() -> range:
    return load_history(default_config_dir() / "history.yaml").year_range()


def x_of(label: str, years: range) -> int:
    """x position of a point: its year's slot on the shared axis, `current` one past the last."""
    return len(years) if label == CURRENT else int(label) - years.start


def load(db: Path) -> tuple[dict, dict, dict, Selector]:
    """(city, kind) -> CitySeries, (city, kind) -> {label: Flag}, run_id -> run row."""
    history = load_history(default_config_dir() / "history.yaml")
    # the runs `velometer timeseries` shows: its default classifier, default parameters
    sel = run_selector(default_config_dir(), history.report_classifier)
    activity = load_activity(default_config_dir() / "activity.yaml")
    built, flagged, runs = {}, {}, {}
    with open_db(db) as conn:
        cities = [r[0] for r in conn.execute("SELECT id FROM cities ORDER BY id")]
        for c in cities:
            for kind in ("lau", "fua"):
                cs = build_city(conn, c, kind, sel, series_years())
                if cs is None or not cs.points:
                    continue
                built[(c, kind)] = cs
                flagged[(c, kind)] = {f.label: f for f in city_flags(cs, activity)}
                for p in cs.points:
                    runs[p.run_id] = fetch_run(conn, p.run_id)
    return built, flagged, runs, sel


def tick_label(p) -> str:
    return f"now\n{p.osm_timestamp[:7]}" if p.label == CURRENT else p.label


def _slots(series_points: list[list], years: range) -> list[tuple[int, str]]:
    """(x, tick label) for every year, plus `now` when any series has a current point."""
    slots = [(x_of(str(y), years), str(y)) for y in years]
    current = next((p for pts in series_points for p in pts if p.label == CURRENT), None)
    if current is not None:
        slots.append((x_of(CURRENT, years), tick_label(current)))
    return slots


def chart_title(built: dict, runs: dict, sel: Selector) -> str:
    years = sorted({p.label for cs in built.values() for p in cs.points if p.label != CURRENT})
    current = sorted(
        {p.osm_timestamp[:10] for cs in built.values() for p in cs.points if p.label == CURRENT}
    )
    n_cities = len({c for c, _ in built})
    n_runs = len(runs)
    span = f"{years[0]}–{years[-1]}" if years else "no years"
    cur = f", current OSM {', '.join(current)}" if current else ""
    return (
        f"velometer M3: {n_cities} pilot cities, 1 January {span}{cur} "
        f"({n_runs} runs, classifier {sel.version})"
    )


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, length=0, labelsize=8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _xticks(ax, slots: list[tuple[int, str]]) -> None:
    ax.set_xticks([x for x, _ in slots], [t for _, t in slots], color=INK_2)


def _headline_lines(ax, series: list[tuple[str, list, dict, str, str]], years: range) -> None:
    """(label, points, flags-by-label, color, linestyle); points sit at their year's x, so a
    gap stays a gap; flagged points get a ring. End labels are nudged apart vertically so close
    lines stay readable."""
    ends = []
    for label, points, flags, color, ls in series:
        shown = [p for p in points if p.headline is not None]
        xs = [x_of(p.label, years) for p in shown]
        ys = [p.headline for p in shown]
        ax.plot(xs, ys, color=color, linewidth=2, linestyle=ls, marker="o", markersize=4)
        fx = [x_of(p.label, years) for p in shown if p.label in flags]
        fy = [p.headline for p in shown if p.label in flags]
        ax.scatter(fx, fy, s=110, facecolors="none", edgecolors=color, linewidths=1.6, zorder=3)
        if xs:
            ends.append([ys[-1], xs[-1], label, color])
    top = max((p.headline or 0) for _, pts, *_ in series for p in pts)
    gap = 0.06 * top
    ends.sort()
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
    for y, x, label, color in ends:
        ax.annotate(
            label,
            (x, y),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            color=color,
            fontsize=9,
            fontweight="bold",
        )


def _spread_labels(ax, n_points: int) -> None:
    ax.set_xlim(-0.4, n_points - 1 + 1.6)  # room for end-of-line labels


def chart(built: dict, flagged: dict, runs: dict, sel: Selector, path: Path, years: range) -> None:
    lau = {c: cs for (c, k), cs in built.items() if k == "lau"}
    cities = sorted(lau)
    color = {c: SERIES[i % len(SERIES)] for i, c in enumerate(cities)}
    fig = plt.figure(figsize=(13, 15), facecolor=SURFACE)
    grid = fig.add_gridspec(
        3, len(cities), height_ratios=[1.15, 1.0, 1.0], hspace=0.55, wspace=0.28
    )
    fig.subplots_adjust(top=0.93, bottom=0.07, left=0.06, right=0.97)
    fig.suptitle(chart_title(built, runs, sel), color=INK, fontsize=13, fontweight="bold")

    # (a) headline % per city on LAU, flagged points ringed
    ax = fig.add_subplot(grid[0, :])
    _style(ax)
    slots = _slots([cs.points for cs in lau.values()], years)
    _headline_lines(
        ax,
        [(c.capitalize(), lau[c].points, flagged[(c, "lau")], color[c], "-") for c in cities],
        years,
    )
    _xticks(ax, slots)
    _spread_labels(ax, len(slots))
    ax.set_ylim(0, None)
    ax.set_ylabel("% of main-road km", color=INK_2)
    ax.set_title(
        "(a) Headline on LAU: tiers A+B per side / main roads excl. motorways "
        "(ringed: flagged year, see the explanations)",
        loc="left",
        color=INK,
        fontsize=11,
    )

    # (b) small multiples: stacked A-E per side km per year
    top = max(sum(p.tiers_km[t] for t in TIERS) for cs in lau.values() for p in cs.points)
    for j, c in enumerate(cities):
        ax = fig.add_subplot(grid[1, j])
        _style(ax)
        points = lau[c].points
        xs = [x_of(p.label, years) for p in points]
        bottom = [0.0] * len(points)
        for i, t in enumerate(TIERS):
            km = [p.tiers_km[t] for p in points]
            ax.bar(
                xs,
                km,
                width=0.7,
                bottom=bottom,
                color=SERIES[i],
                edgecolor=SURFACE,
                linewidth=0.6,
                label=TIER_LABEL[t],
            )
            bottom = [b + k for b, k in zip(bottom, km, strict=True)]
        ax.set_xticks(
            xs,
            [
                "now" if p.label == CURRENT else (p.label if p.label in SPARSE else "")
                for p in points
            ],
            color=INK_2,
            fontsize=7,
        )
        ax.set_ylim(0, top * 1.05)
        ax.set_title(c.capitalize(), color=INK, fontsize=10, loc="left")
        if j == 0:
            ax.set_ylabel("km (per side)", color=INK_2)
            ax.text(
                0,
                1.14,
                "(b) Tier composition A–E per year on LAU, per side km (shared y axis)",
                transform=ax.transAxes,
                color=INK,
                fontsize=11,
            )
        else:
            ax.tick_params(labelleft=False)
    handles, labels = fig.axes[1].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="center",
        bbox_to_anchor=(0.515, 0.355),
        ncol=5,
        frameon=False,
        fontsize=9,
        labelcolor=INK,
    )

    # (c) LAU vs FUA headline, Berlin and Paris
    fua_cities = [c for c in FUA_CITIES if (c, "lau") in built and (c, "fua") in built]
    bottom_row = grid[2, :].subgridspec(1, 2, wspace=0.18)
    spans = [bottom_row[0, 0], bottom_row[0, 1]]
    for k, (c, spec) in enumerate(zip(fua_cities, spans, strict=False)):
        ax = fig.add_subplot(spec)
        _style(ax)
        pts = {kind: built[(c, kind)].points for kind in ("lau", "fua")}
        slots = _slots(list(pts.values()), years)
        _headline_lines(
            ax,
            [
                ("LAU (city)", pts["lau"], flagged[(c, "lau")], color[c], "-"),
                ("FUA (metro)", pts["fua"], flagged[(c, "fua")], INK_2, "--"),
            ],
            years,
        )
        _xticks(ax, slots)
        ax.tick_params(axis="x", labelsize=7)
        _spread_labels(ax, len(slots) + 1)
        ax.set_ylim(0, None)
        ax.set_title(c.capitalize(), color=INK, fontsize=10, loc="left")
        if k == 0:
            ax.set_ylabel("headline %", color=INK_2)
            ax.text(
                0,
                1.16,
                "(c) Headline on the city (LAU) vs its functional urban area (FUA); "
                "a series without a current run has no 'now' point",
                transform=ax.transAxes,
                color=INK,
                fontsize=11,
            )
    if not fua_cities:
        fig.text(0.06, 0.2, "(c) no FUA history runs yet", color=INK_2, fontsize=11)

    fig.text(
        0.06,
        0.015,
        f"Map data {ATTRIBUTION}. OSM mapped km, not built km (ADR 0006); LAU population 2024 "
        "held constant (FUA: no population, no per-100k).\nSnapshots at 1 January 00:00 UTC "
        "from Geofabrik full history (ADR 0005); "
        "'now' is the current run.",
        color=INK_2,
        fontsize=9,
    )
    fig.savefig(path, dpi=120, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    built, flagged, runs, sel = load(DB)
    if not any(k == "lau" for _, k in built):
        raise SystemExit(f"no LAU history runs of the current config {sel.short_sha} in {DB}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    chart(built, flagged, runs, sel, OUT, series_years())
    print(f"wrote {OUT} ({len(built)} series, {len(runs)} runs)")


if __name__ == "__main__":
    main()
