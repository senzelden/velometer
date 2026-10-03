"""Vega-Lite chart specs for the report surfaces (headline over time, tier composition,
rankings flip) and their PNG export.

Every spec embeds its data inline (no `url` key anywhere), so a spec is self-contained and
renders offline. Charts are built from `ReportData`, the same query layer as the CSV.
"""

import json
from pathlib import Path

import altair as alt
import vl_convert as vlc

from velometer import timeseries as ts
from velometer.report.data import HEADLINE_UNIT, ReportData

ATTRIBUTION = (
    "Map data © OpenStreetMap contributors, ODbL 1.0 · OSM mapped km, not built km (ADR 0006)"
)
# The M3 chart's tier colours (dataviz categorical slots 1-5), A-E.
TIER_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
TIER_LABEL = {
    "A": "A separated track",
    "B": "B shared foot/cycle path",
    "C": "C protected lane",
    "D": "D painted lane",
    "E": "E cycle street / bus lane",
}
OUTLINE = "#9a9994"  # the boundary outline on the tier maps (PNG and interactive)
CITY_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#7a5bd1", "#52514e"]
NOW = "now"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

alt.data_transformers.disable_max_rows()


def _label(label: str) -> str:
    return NOW if label == ts.CURRENT else label


def _title(text: str, notes: list[str] | None = None) -> alt.TitleParams:
    """Title with the attribution as subtitle; `notes` become further subtitle lines."""
    subtitle = [ATTRIBUTION, *notes] if notes else ATTRIBUTION
    return alt.TitleParams(text, subtitle=subtitle, anchor="start", fontSize=16)


def _config(chart):
    return (
        chart.configure_axis(labelColor=INK_2, titleColor=INK_2, gridColor=GRID, domainColor=GRID)
        .configure_legend(labelColor=INK, titleColor=INK_2, labelLimit=260)
        .configure_title(color=INK, subtitleColor=INK_2, subtitleFontSize=11)
        .configure_view(stroke=None)
    )


def _x_labels(data: ReportData) -> list[str]:
    return [str(y) for y in data.years] + [NOW]


def _city_name(data: ReportData, city_id: str) -> str:
    return next((c.name for c in data.cities() if c.id == city_id), city_id)


def _city_domain(data: ReportData) -> tuple[list[str], list[str]]:
    names = [c.name for c in data.cities()]
    return names, [CITY_COLOURS[i % len(CITY_COLOURS)] for i in range(len(names))]


# --- headline over time ----------------------------------------------------------------------


def _headline_rows(data: ReportData) -> list[dict]:
    rows = []
    for c in data.cities():
        for kind in ("lau", "fua"):
            cs = data.series(c.id, kind)
            if cs is None:
                continue
            flagged = {f.label: f for f in data.flags(c.id, kind)}
            for p in cs.points:
                f = flagged.get(p.label)
                rows.append(
                    {
                        "city": c.name,
                        "city_id": c.id,
                        "kind": kind,
                        "series": f"{c.name} ({kind.upper()})",
                        "label": _label(p.label),
                        "headline": p.headline,
                        "ab_km": round(p.ab_km, 3),
                        "flagged": f is not None,
                        "flags": ", ".join(f.rules) if f else "",
                    }
                )
    return rows


def headline_over_time(data: ReportData) -> dict:
    """One line per city on LAU, dashed lines for the FUA series; flagged points are ringed."""
    rows = _headline_rows(data)
    names, colours = _city_domain(data)
    x = alt.X("label:O", sort=_x_labels(data), title=None, axis=alt.Axis(labelAngle=0))
    y = alt.Y("headline:Q", title=HEADLINE_UNIT, scale=alt.Scale(zero=True))
    colour = alt.Color(
        "city:N", scale=alt.Scale(domain=names, range=colours), title="City", legend=alt.Legend()
    )
    tooltip = [
        alt.Tooltip("city:N"),
        alt.Tooltip("kind:N"),
        alt.Tooltip("label:N"),
        alt.Tooltip("headline:Q", format=".2f", title="A+B km per 100 km main roads"),
        alt.Tooltip("ab_km:Q", format=".1f"),
        alt.Tooltip("flags:N"),
    ]
    base = alt.Chart().encode(x=x, y=y, color=colour, tooltip=tooltip)
    lines = base.transform_filter(alt.datum.kind == "lau").mark_line(point=True, strokeWidth=2)
    fua = (
        base.encode(
            strokeDash=alt.StrokeDash(
                "kind:N",
                scale=alt.Scale(domain=["lau", "fua"], range=[[1, 0], [5, 4]]),
                title="Boundary",
            )
        )
        .transform_filter(alt.datum.kind == "fua")
        .mark_line(strokeWidth=1.5, opacity=0.8)
    )
    rings = (
        alt.Chart()
        .transform_filter(alt.datum.flagged == True)  # noqa: E712 - a Vega expression
        .mark_point(shape="circle", size=260, filled=False, stroke=INK, strokeWidth=2)
        .encode(x=x, y=y, tooltip=tooltip)
    )
    chart = alt.layer(lines, fua, rings, data=alt.Data(values=rows)).properties(
        width=560, height=320, title=_title("Protected cycling infrastructure over time")
    )
    return _config(chart).to_dict()


# --- tier composition ------------------------------------------------------------------------


def _tier_rows(data: ReportData, city_id: str, kind: str) -> list[dict]:
    cs = data.series(city_id, kind)
    if cs is None:
        return []
    return [
        {
            "city": _city_name(data, city_id),
            "kind": kind,
            "label": _label(p.label),
            "tier": t,
            "tier_label": TIER_LABEL[t],
            "km": round(p.tiers_km[t], 3),
        }
        for p in cs.points
        for t in ts.TIERS
    ]


def _tier_chart(data: ReportData, rows: list[dict], *, width: int, height: int) -> alt.Chart:
    return (
        alt.Chart(alt.Data(values=rows))
        .mark_bar()
        .encode(
            x=alt.X("label:O", sort=_x_labels(data), title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("km:Q", title="Mapped km (per side)", stack="zero"),
            color=alt.Color(
                "tier_label:N",
                scale=alt.Scale(domain=list(TIER_LABEL.values()), range=TIER_COLOURS),
                title="Tier",
            ),
            order=alt.Order("tier:N"),
            tooltip=[
                alt.Tooltip("city:N"),
                alt.Tooltip("label:N"),
                alt.Tooltip("tier_label:N", title="tier"),
                alt.Tooltip("km:Q", format=".1f"),
            ],
        )
        .properties(width=width, height=height)
    )


def tier_composition(data: ReportData, city_id: str, kind: str = "lau") -> dict:
    """Stacked bars of the A-E per-side km of one city's boundary, per label."""
    rows = _tier_rows(data, city_id, kind)
    name = _city_name(data, city_id)
    chart = _tier_chart(data, rows, width=480, height=300).properties(
        title=_title(f"Tier composition, {name} ({kind.upper()})")
    )
    return _config(chart).to_dict()


def tiers_small_multiples(data: ReportData) -> dict:
    """Every city's LAU tier composition as small multiples sharing one legend."""
    rows = [r for c in data.cities() for r in _tier_rows(data, c.id, "lau")]
    base = _tier_chart(data, rows, width=260, height=200)
    chart = (
        base.facet(facet=alt.Facet("city:N", title=None), columns=3)
        .properties(title=_title("Tier composition per city (LAU)"))
        .resolve_scale(y="independent")
        # one x axis per panel: a wrapped facet otherwise draws a column's axis under its last
        # row, which for a short last row is an empty cell
        .resolve_axis(x="independent")
    )
    return _config(chart).to_dict()


# --- rankings flip ---------------------------------------------------------------------------


def rankings_flip(data: ReportData) -> dict:
    """Slope chart: x = ranking source (report.yaml order), y = rank (1 on top), colour = city."""
    names = {c.id: c.name for c in data.cities()}
    ranking_rows = data.ranking_rows()
    # each column says how many cities it ranks (n differs per source: a missing figure is a gap)
    column = {r.source_id: f"{r.source_label} (n={r.n_ranked})" for r in ranking_rows}
    labels = [column[r.id] for r in data.report_config.rankings if r.id in column]
    rows = [
        {
            "source": column[e.source_id],
            "city": names.get(e.city_id, e.city_id),
            "rank": e.rank,
            "value": None if e.value is None else round(e.value, 3),
            "value_text": "not published" if e.value is None else f"{e.value:.2f}",
        }
        for e in ranking_rows
    ]
    domain, colours = _city_domain(data)
    top = max([r["rank"] for r in rows if r["rank"] is not None] + [1])
    chart = (
        alt.Chart(alt.Data(values=rows))
        .mark_line(
            point=alt.OverlayMarkDef(size=90, filled=True),
            strokeWidth=2.5,
            invalid="break-paths-filter-domains",  # a null rank breaks the line
        )
        .encode(
            x=alt.X(
                "source:O", sort=labels, title=None, axis=alt.Axis(labelAngle=-25, labelLimit=220)
            ),
            y=alt.Y(
                "rank:Q",
                title="Rank (1 = highest)",
                scale=alt.Scale(reverse=True, domain=[1, top], nice=False),
                axis=alt.Axis(values=list(range(1, top + 1)), format="d"),
            ),
            color=alt.Color("city:N", scale=alt.Scale(domain=domain, range=colours), title="City"),
            tooltip=[
                alt.Tooltip("source:N"),
                alt.Tooltip("city:N"),
                alt.Tooltip("rank:Q"),
                # each source has its own unit and denominator (report.yaml notes, methodology)
                alt.Tooltip("value_text:N", title="value"),
            ],
        )
        .properties(
            width=560,
            height=320,
            # each column's scope (M4 spec 4.2), from the `note` of its config/report.yaml entry
            title=_title(
                "City rankings by source",
                [
                    f"{r.label}: {n}"
                    for r in data.report_config.rankings
                    if (n := getattr(r, "note", None))
                ],
            ),
        )
    )
    return _config(chart).to_dict()


# --- PNG export ------------------------------------------------------------------------------


def write_pngs(data: ReportData, out_dir: Path) -> list[Path]:
    """Write m4_headline / m4_tiers / m4_rankings as PNG plus the .vl.json spec of each."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = {
        "m4_headline": headline_over_time(data),
        "m4_tiers": tiers_small_multiples(data),
        "m4_rankings": rankings_flip(data),
    }
    paths = []
    for stem, spec in specs.items():
        png = out_dir / f"{stem}.png"
        png.write_bytes(vlc.vegalite_to_png(spec, scale=2))
        vl = out_dir / f"{stem}.vl.json"
        vl.write_text(json.dumps(spec, indent=2) + "\n")
        paths += [png, vl]
    return paths
