"""Render the M2 results review: docs/review/m2_results.md and docs/review/m2_results.png.

Reads velometer.sqlite: the latest done LAU run per city of the config on disk. Clean Cities
figures are on the basis presets.yaml selects; the presets table lists both. Run after
`velometer run --cities all`:

    uv run python scripts/render_m2_results.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from velometer.config import (  # noqa: E402
    PresetsConfig,
    default_config_dir,
    load_classifier,
    load_presets,
)
from velometer.db import (  # noqa: E402
    DEFAULT_PARAMETERS,
    fetch_boundary,
    fetch_cities,
    fetch_run,
    fetch_run_results,
    latest_done_run,
    open_db,
)
from velometer.pipeline.measure import select_metric  # noqa: E402
from velometer.reconcile import short_commit  # noqa: E402
from velometer.run import config_sha256  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "velometer.sqlite"
OUT = ROOT / "docs" / "review"
BOUNDARY = "lau"
CLASSIFIER = "v1"  # with its default parameters: sensitivity runs never replace the chart
TIERS = "ABCDE"
PRESETS = ["ours_headline", "ecf_qecio", "clean_cities_2025"]
PRESET_LABEL = {
    "ours_headline": "ours_headline: A+B per side / main roads excl. motorways",
    "ecf_qecio": "ecf_qecio: A–D QECIO-weighted / main roads incl. motorways (raw)",
}
TIER_LABEL = {
    "A": "A separated track",
    "B": "B shared foot/cycle path",
    "C": "C physically protected lane",
    "D": "D painted lane",
    "E": "E cycle street / bus lane",
}
# Categorical slots 1-5 of the dataviz reference palette (light), fixed order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0"


def preset_label(preset: str, rows: list[dict]) -> str:
    """Legend text; the Clean Cities label names the basis the bar is on."""
    if preset == "clean_cities_2025":
        basis = rows[0]["metrics"][preset].length_basis
        return f"clean_cities_2025: A+B on {basis} / all public roads"
    return PRESET_LABEL[preset]


def load_config() -> tuple[str, PresetsConfig]:
    """sha256 of the config on disk and its presets: the runs the report is about."""
    config_dir = default_config_dir()
    classifier = config_dir / "classifier" / f"{CLASSIFIER}.yaml"
    presets_path = config_dir / "presets.yaml"
    return config_sha256(classifier, presets_path), load_presets(
        presets_path, load_classifier(classifier)
    )


def load(db: Path, sha: str, presets: PresetsConfig) -> list[dict]:
    rows = []
    with open_db(db) as conn:
        for c in fetch_cities(conn):
            run_id = latest_done_run(conn, c.id, BOUNDARY, CLASSIFIER, DEFAULT_PARAMETERS, sha)
            if run_id is None:
                continue
            r = fetch_run_results(conn, run_id)
            run = fetch_run(conn, run_id)
            boundary = fetch_boundary(conn, c.id, BOUNDARY)
            check_boundary(c.id, run, boundary)
            tier_km = {(b, t): 0.0 for b in ("per_side", "qecio_weighted") for t in TIERS}
            for t in r.tier_lengths:
                if t.tier in TIERS:
                    tier_km[(t.length_basis, t.tier)] += t.length_km
            rows.append(
                {
                    "city": c,
                    "run": run,
                    "metrics": {
                        p.id: m
                        for p in presets.presets
                        if (m := select_metric(r.metrics, p.id, presets)) is not None
                    },
                    "all_metrics": r.metrics,
                    "presets": presets,
                    "roads": {x.road_class: x.length_km for x in r.road_lengths},
                    "tier_km": tier_km,
                    "completeness": r.completeness,
                    "boundary": boundary,
                }
            )
    return rows


def check_boundary(city_id: str, run: dict, boundary) -> None:
    """The stored boundary row is mutable: refuse to describe a run with another boundary."""
    if boundary is None or boundary.sha256 != run["boundary_sha256"]:
        got = boundary.sha256[:12] if boundary else "none"
        raise SystemExit(
            f"{city_id}: run {run['id']} used boundary {run['boundary_sha256'][:12]}, the "
            f"stored {BOUNDARY} boundary is {got}; re-run the city or fetch its boundary"
        )


def population_cells(run: dict) -> tuple[str, str]:
    """Population as recorded on the run row (what its per-100k used), not the cities row."""
    if run.get("population_value") is None:
        return "n/a", "n/a"
    return f"{run['population_value']:,} ({run['population_year']})", run["population_source"]


def chart_title(rows: list[dict]) -> str:
    dates = sorted({r["run"]["osm_timestamp"][:10] for r in rows})
    versions = sorted({r["run"]["classifier_version"] for r in rows})
    sources = sorted({f"{r['boundary'].source_version}" for r in rows})
    return (
        f"velometer M2: {len(rows)} pilot cities ({', '.join(sources)}, "
        f"OSM {', '.join(dates)}, classifier {', '.join(versions)})"
    )


def fmt(v: float | None, nd: int = 1) -> str:
    return "n/a" if v is None else f"{v:,.{nd}f}"


def results_table(rows: list[dict]) -> list[str]:
    basis = rows[0]["presets"].parameters.clean_cities_basis if rows else "per_side"
    head = ["city", "osm_date", "headline %", "ecf_qecio %", f"clean_cities % ({basis})"]
    head += [f"{t} km" for t in TIERS] + ["main km", "headline km/100k"]
    out = ["| " + " | ".join(head) + " |", "|---|---|" + "---:|" * (len(head) - 2)]
    for r in rows:
        m = r["metrics"]
        cells = [r["city"].id, r["run"]["osm_timestamp"][:10]]
        cells += [fmt(m[p].value) if p in m else "n/a" for p in PRESETS]
        cells += [fmt(r["tier_km"][("per_side", t)]) for t in TIERS]
        cells += [fmt(r["roads"].get("main_excl_motorway"))]
        cells += [fmt(m["ours_headline"].per_100k) if "ours_headline" in m else "n/a"]
        out.append("| " + " | ".join(cells) + " |")
    return out


def markdown(rows: list[dict]) -> str:
    runs = {(r["run"]["classifier_version"], r["run"]["classifier_parameters"]) for r in rows}
    lines = [
        "# M2 results: five pilot cities",
        "",
        f"Generated by `scripts/render_m2_results.py` from `velometer.sqlite` (latest done "
        f"`{BOUNDARY}` run per city). OSM data: {ATTRIBUTION}; our tier lengths and metrics "
        "are derived data under ODbL 1.0 (ADR 0008). Lengths are OSM *mapped* km (ADR 0006), "
        "measured in each city's projected EPSG.",
        "",
        "![M2 results](m2_results.png)",
        "",
        "## Results",
        "",
        "Headline and preset values are percentages (numerator km / denominator km × 100); "
        "tier km are per side (each side of a road counts once). Per-100k is the headline "
        "numerator km per 100,000 residents. A per-side headline passes 100% when main roads "
        "have tracks on both sides, and can pass 200% because tracks along residential streets "
        "and standalone paths count in the numerator but not in the main-road denominator.",
        "",
        *results_table(rows),
        "",
        "## Presets",
        "",
        "Every basis is stored; a preset with a parameterised basis (`clean_cities_2025`, "
        "parameter `clean_cities_basis` in `config/presets.yaml`) lists one row per basis, the "
        "selected one marked.",
        "",
        "| city | preset | basis | selected | value % | numerator km | denominator km |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for r in rows:
        for p in PRESETS:
            for m in (m for m in r["all_metrics"] if m.preset == p):
                chosen = r["metrics"].get(p)
                mark = "yes" if chosen is not None and chosen.length_basis == m.length_basis else ""
                lines.append(
                    f"| {r['city'].id} | `{p}` | {m.length_basis} | {mark} | {fmt(m.value)} | "
                    f"{fmt(m.numerator_km)} | {fmt(m.denominator_km)} |"
                )
    lines += [
        "",
        "## Provenance",
        "",
        "Classifier: "
        + "; ".join(f"`{v}` with parameters `{p}`" for v, p in sorted(runs))
        + " (`config/classifier/`).",
        "",
        "| city | run | OSM timestamp | Geofabrik md5 | git commit | config sha | boundary "
        "| boundary sha | area km² | population | population source |",
        "|---|---:|---|---|---|---|---|---|---:|---:|---|",
    ]
    for r in rows:
        c, run, b = r["city"], r["run"], r["boundary"]
        pop, src = population_cells(run)
        lines.append(
            f"| {c.id} | {run['id']} | {run['osm_timestamp']} | `{run['region_md5'][:8]}` | "
            f"`{short_commit(run['git_commit'])}` | `{(run['config_sha256'] or 'n/a')[:12]}` | "
            f"{b.source}, {b.source_version} | `{run['boundary_sha256'][:12]}` | "
            f"{fmt(b.area_km2)} | {pop} | {src} |"
        )
    lines += [
        "",
        "## Completeness (share of tier km with the tag)",
        "",
        "Length-weighted per tier and side. `segregated` is meaningful only for tier B.",
        "",
        "| city | tier | width | surface | segregated |",
        "|---|---|---:|---:|---:|",
    ]
    for r in rows:
        for x in r["completeness"]:
            lines.append(
                f"| {r['city'].id} | {x.tier} | {x.share_with_width:.0%} | "
                f"{x.share_with_surface:.0%} | {x.share_with_segregated:.0%} |"
            )
    lines += [
        "",
        "## Attribution",
        "",
        f"Map data {ATTRIBUTION} (https://www.openstreetmap.org/copyright), via Geofabrik "
        "extracts. Boundaries: © EuroGeographics for the administrative boundaries "
        "(Eurostat GISCO LAU 2024). Population: Eurostat (GISCO LAU 2024 `POP_2024`; "
        "`demo_r_pjangrp3` where LAU has none).",
        "",
    ]
    return "\n".join(lines)


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart(rows: list[dict], path: Path) -> None:
    names = [r["city"].id.capitalize() for r in rows]
    x = range(len(rows))
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), facecolor=SURFACE)
    fig.subplots_adjust(hspace=0.38, top=0.925, bottom=0.07, left=0.09, right=0.97)
    fig.suptitle(
        chart_title(rows),
        color=INK,
        fontsize=13,
        fontweight="bold",
    )

    # (a) headline per city
    ax = axes[0]
    _style(ax)
    vals = [r["metrics"]["ours_headline"].value for r in rows]
    bars = ax.bar(x, vals, width=0.55, color=SERIES[0])
    for b, v in zip(bars, vals, strict=True):
        ax.annotate(
            f"{v:.0f}%",
            (b.get_x() + b.get_width() / 2, v),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            color=INK,
            fontsize=10,
        )
    ax.set_xticks(list(x), names, color=INK)
    ax.set_ylabel("% of main-road km", color=INK_2)
    ax.set_ylim(0, max(vals) * 1.15)
    ax.set_title(
        "(a) Headline: protected km (tiers A+B, per side) per km of main road excl. motorways",
        loc="left",
        color=INK,
        fontsize=11,
    )

    # (b) tier composition, per side km
    ax = axes[1]
    _style(ax)
    bottom = [0.0] * len(rows)
    for i, t in enumerate(TIERS):
        km = [r["tier_km"][("per_side", t)] for r in rows]
        ax.bar(
            x,
            km,
            width=0.55,
            bottom=bottom,
            color=SERIES[i],
            edgecolor=SURFACE,
            linewidth=1.5,
            label=TIER_LABEL[t],
        )
        bottom = [b + k for b, k in zip(bottom, km, strict=True)]
    for xi, total in zip(x, bottom, strict=True):
        ax.annotate(
            f"{total:,.0f} km",
            (xi, total),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            color=INK,
            fontsize=10,
        )
    ax.set_xticks(list(x), names, color=INK)
    ax.set_ylabel("km (per side)", color=INK_2)
    ax.set_ylim(0, max(bottom) * 1.15)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper right")
    ax.set_title("(b) Tier composition A–E, per side km", loc="left", color=INK, fontsize=11)

    # (c) presets side by side
    ax = axes[2]
    _style(ax)
    w = 0.26
    for i, p in enumerate(PRESETS):
        vals = [r["metrics"][p].value for r in rows]
        pos = [xi + (i - 1) * w for xi in x]
        ax.bar(
            pos,
            vals,
            width=w,
            color=SERIES[i],
            edgecolor=SURFACE,
            linewidth=1.5,
            label=preset_label(p, rows),
        )
        for px, v in zip(pos, vals, strict=True):
            ax.annotate(
                f"{v:.0f}",
                (px, v),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                color=INK_2,
                fontsize=8,
            )
    top = max(r["metrics"][p].value for r in rows for p in PRESETS)
    ax.set_ylim(0, top * 1.45)
    ax.set_xticks(list(x), names, color=INK)
    ax.set_ylabel("%", color=INK_2)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper right")
    ax.set_title(
        "(c) The three presets per city (%), Clean Cities basis as labelled",
        loc="left",
        color=INK,
        fontsize=11,
    )

    fig.text(
        0.09,
        0.015,
        f"Map data {ATTRIBUTION}. OSM mapped km, not built km (ADR 0006).",
        color=INK_2,
        fontsize=9,
    )
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    sha, presets = load_config()
    rows = load(DB, sha, presets)
    if not rows:
        raise SystemExit(f"no done {BOUNDARY!r} runs of the current config {sha[:12]} in {DB}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "m2_results.md").write_text(markdown(rows))
    chart(rows, OUT / "m2_results.png")
    print(f"wrote {OUT / 'm2_results.md'} and {OUT / 'm2_results.png'} ({len(rows)} cities)")


if __name__ == "__main__":
    main()
