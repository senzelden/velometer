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
# Tier colours A-E, light theme; the light CSS tier tokens equal these. Chosen by rule (M10
# decision 3, tested in tests/test_colour.py): each >= 3:1 on the light backgrounds, every pair
# >= CIEDE2000 20 and adjacent tiers >= 25, in normal vision and simulated deuteranopia and
# protanopia. Hue families of the M3 palette: blue, orange, green, yellow-brown, pink-purple.
TIER_COLOURS = ["#2a78d6", "#9f3d0c", "#22a397", "#c68501", "#8d415b"]
TIER_LABEL = {
    "A": "A separated track",
    "B": "B shared foot/cycle path",
    "C": "C protected lane",
    "D": "D painted lane",
    "E": "E cycle street / bus lane",
}
OUTLINE = "#93928d"  # the tier maps' boundary outline (PNG and interactive), >= 3:1 on light
# Series colours, light theme: each >= 3:1 on the light backgrounds, every pair >= CIEDE2000 20
# in normal vision (tests/test_colour.py).
SERIES_COLOURS = [
    "#2a78d6", "#eb6834", "#35a186", "#bf8500", "#d96d98", "#8753cd", "#52514e", "#008300",
]  # fmt: skip
CITY_COLOURS = SERIES_COLOURS[:7]  # the Altair report charts
GREY = "#c9c8c3"  # the context ("other") cities
PICK_COLOUR = "#7a5bd1"  # a context city picked in the headline chart's select
HIGHLIGHT, COMPARISON, OTHER = "highlight", "comparison", "other"
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


def _roles(data: ReportData) -> dict[str, str]:
    """city id -> role, from report.yaml only; a city in neither list is "other"."""
    cfg = data.report_config
    roles = {c.id: OTHER for c in data.cities()}
    roles |= {i: COMPARISON for i in cfg.comparison_set if i in roles}
    roles |= {i: HIGHLIGHT for i in cfg.highlight if i in roles}
    return roles


def _focus_domain(data: ReportData) -> tuple[list[str], list[str]]:
    """City names and colours of the highlighted and comparison cities, in config order."""
    cfg = data.report_config
    roles = _roles(data)
    ids = [
        i for i in [*cfg.highlight, *cfg.comparison_set] if roles.get(i) in (HIGHLIGHT, COMPARISON)
    ]
    names = [_city_name(data, i) for i in ids]
    return names, [CITY_COLOURS[i % len(CITY_COLOURS)] for i in range(len(names))]


def _is_other(expr=alt.datum.role):
    return expr == OTHER


# --- headline over time ----------------------------------------------------------------------


def _headline_rows(data: ReportData, kinds: tuple[str, ...], city_ids=None) -> list[dict]:
    roles = _roles(data)
    rows = []
    for c in data.cities():
        if city_ids is not None and c.id not in city_ids:
            continue
        for kind in kinds:
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
                        "role": roles[c.id],
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


LABEL_GAP_PX = 13  # least vertical distance between two end labels (11 px text)


def _spread_labels(values: dict[str, float], gap: float, floor: float = 0.0) -> dict[str, float]:
    """Label positions (data units) at least `gap` apart that keep the order of the values.
    The highest label stays on its line end; each next one is pushed DOWN (smaller values) just
    far enough, so no label ever passes a higher-valued neighbour. A push below `floor` (the
    scale minimum) lifts the bottom of the stack back up to it, still in order and `gap` apart."""
    out: dict[str, float] = {}
    for k in sorted(values, key=lambda k: -values[k]):
        out[k] = min(values[k], min(out.values(), default=float("inf")) - gap)
    low = floor
    for k in sorted(out, key=out.get):
        out[k] = max(out[k], low)
        low = out[k] + gap
    return out


def _headline_tooltip() -> list[alt.Tooltip]:
    return [
        alt.Tooltip("city:N"),
        alt.Tooltip("kind:N"),
        alt.Tooltip("label:N"),
        alt.Tooltip("headline:Q", format=".2f", title="A+B km per 100 km main roads"),
        alt.Tooltip("ab_km:Q", format=".1f"),
        alt.Tooltip("flags:N"),
    ]


def _rings(x, y, tooltip) -> alt.Chart:
    return (
        alt.Chart()
        .transform_filter(alt.datum.flagged == True)  # noqa: E712 - a Vega expression
        .mark_point(shape="circle", size=260, filled=False, stroke=INK, strokeWidth=2)
        .encode(x=x, y=y, tooltip=tooltip)
    )


HEADLINE_HEIGHT = 320


def headline_over_time(data: ReportData) -> dict:
    """LAU headline of every city: the highlighted and comparison cities coloured and labelled,
    every other city a thin grey line a select can pick out; flagged points are ringed."""
    rows = _headline_rows(data, ("lau",))
    names, colours = _focus_domain(data)
    other_names = sorted({r["city"] for r in rows if r["role"] == OTHER})
    x = alt.X("label:O", sort=_x_labels(data), title=None, axis=alt.Axis(labelAngle=0))
    y = alt.Y("headline:Q", title=HEADLINE_UNIT, scale=alt.Scale(zero=True))
    city_scale = alt.Scale(domain=names, range=colours)
    # the legend sits below the plot: on the right it ran into the end labels
    colour = alt.Color(
        "city:N",
        scale=city_scale,
        title="City",
        legend=alt.Legend(orient="bottom", direction="horizontal"),
    )
    tooltip = _headline_tooltip()
    # only the labelled (coloured) cities are spread: the grey ones carry no end label
    now = {
        r["city"]: r["headline"]
        for r in rows
        if r["label"] == NOW and r["kind"] == "lau" and r["role"] != OTHER
    }
    top = max([r["headline"] for r in rows if r["headline"] is not None] + [1.0])
    gap = LABEL_GAP_PX / HEADLINE_HEIGHT * top
    spread = _spread_labels({c: v for c, v in now.items() if v is not None}, gap)
    for r in rows:
        r["label_y"] = spread.get(r["city"], r["headline"]) if r["label"] == NOW else r["headline"]
    pick = alt.selection_point(
        name="pick",
        fields=["city"],
        empty=False,
        bind=alt.binding_select(
            options=[None, *other_names], labels=["—", *other_names], name="Highlight a city "
        ),
    )
    focus = alt.datum.role != OTHER
    grey = (
        alt.Chart()
        .transform_filter(_is_other())
        .mark_line()
        .encode(
            x=x,
            y=y,
            detail="city:N",
            color=alt.condition(pick, alt.value(PICK_COLOUR), alt.value(GREY)),
            strokeWidth=alt.condition(pick, alt.value(2.5), alt.value(1)),
            tooltip=tooltip,
        )
        .add_params(pick)
    )
    lines = (
        alt.Chart()
        .transform_filter(focus)
        .mark_line(point=True)
        .encode(
            x=x,
            y=y,
            color=colour,
            strokeWidth=alt.condition(alt.datum.role == HIGHLIGHT, alt.value(2.5), alt.value(1.8)),
            tooltip=tooltip,
        )
    )
    labels = (
        alt.Chart()
        .transform_filter(focus & (alt.datum.label == NOW))
        .mark_text(align="left", dx=8, fontSize=11)
        .encode(
            x=x,
            y=alt.Y("label_y:Q", title=HEADLINE_UNIT, scale=alt.Scale(zero=True)),
            text="city:N",
            color=alt.Color("city:N", scale=city_scale, legend=None),
        )
    )
    rings = _rings(x, y, tooltip).transform_filter(focus)
    chart = alt.layer(grey, lines, labels, rings, data=alt.Data(values=rows)).properties(
        width=560,
        height=HEADLINE_HEIGHT,
        padding={"left": 5, "top": 5, "right": 110, "bottom": 5},  # room for the "now" labels
        title=_title("Protected cycling infrastructure over time"),
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


def _sparse_years(data: ReportData) -> list[str]:
    """First, middle and last label: nine labels do not fit under a 150 px panel."""
    labels = _x_labels(data)
    return list(dict.fromkeys([labels[0], labels[(len(labels) - 1) // 2], labels[-1]]))


def _tier_chart(
    data: ReportData, rows: list[dict], *, width: int, height: int, sparse: bool = False
) -> alt.Chart:
    axis = alt.Axis(labelAngle=0, values=_sparse_years(data)) if sparse else alt.Axis(labelAngle=0)
    return (
        alt.Chart(alt.Data(values=rows))
        .mark_bar()
        .encode(
            x=alt.X("label:O", sort=_x_labels(data), title=None, axis=axis),
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


def tiers_small_multiples(data: ReportData) -> dict:
    """Every city's LAU tier composition as small multiples sharing one legend and one y scale."""
    rows = [r for c in data.cities() for r in _tier_rows(data, c.id, "lau")]
    base = _tier_chart(data, rows, width=150, height=110, sparse=True)
    chart = (
        base.facet(facet=alt.Facet("city:N", title=None, sort="ascending"), columns=7)
        .properties(title=_title("Tier composition per city (LAU)"))
        .resolve_scale(y="shared")
        # one x axis per panel: a wrapped facet otherwise draws a column's axis under its last
        # row, which for a short last row is an empty cell
        .resolve_axis(x="independent")
    )
    return _config(chart).to_dict()


# --- rankings flip ---------------------------------------------------------------------------


def _nuts3_columns(data: ReportData) -> set[str]:
    """Ids of the ranking sources whose scope is each city's NUTS3 region."""
    return {
        r.id
        for r in data.report_config.rankings
        if r.kind == "external_ratio" and r.scope.startswith("nuts3_")
    }


def _gap_lines(data: ReportData, rows: list[dict]) -> list[str]:
    """One subtitle line per source that has no figure for some cities: a null rank breaks the
    line and draws no mark, so the chart itself cannot carry its "not published" tooltip."""
    out = []
    for r in data.report_config.rankings:
        missing = sorted({x["city"] for x in rows if x["rank"] is None and x["source_id"] == r.id})
        if missing:
            what = "has no value" if r.kind == "preset" else "does not publish a figure"
            out.append(f"{r.label} {what} for {', '.join(missing)} (gap in the line)")
    return out


def rankings_flip(data: ReportData) -> dict:
    """Slope chart: x = ranking source (report.yaml order), y = rank (1 on top); the highlighted
    and comparison cities are coloured, every other city a thin grey line."""
    names = {c.id: c.name for c in data.cities()}
    roles = _roles(data)
    nuts3 = _nuts3_columns(data)
    # a city whose NUTS3 region is not the city: its QECIO figure is a region's, marked with †
    region_only = {i for i, f in data.city_fields().items() if f.get("nuts3_is_city") is False}
    ranking_rows = data.ranking_rows()
    # each column says how many cities it ranks (n differs per source: a missing figure is a gap)
    column = {r.source_id: f"{r.source_label} (n={r.n_ranked})" for r in ranking_rows}
    labels = [column[r.id] for r in data.report_config.rankings if r.id in column]
    rows = []
    for e in ranking_rows:
        city = names.get(e.city_id, e.city_id)
        dagger = e.source_id in nuts3 and e.city_id in region_only
        rows.append(
            {
                "source": column[e.source_id],
                "source_id": e.source_id,
                "city": city,
                "city_id": e.city_id,
                "city_label": f"{city} †" if dagger else city,
                "dagger": dagger,
                "role": roles.get(e.city_id, OTHER),
                "rank": e.rank,
                "value": None if e.value is None else round(e.value, 3),
                "value_text": "not published" if e.value is None else f"{e.value:.2f}",
            }
        )
    domain, colours = _focus_domain(data)
    top = max([r["rank"] for r in rows if r["rank"] is not None] + [1])
    x = alt.X("source:O", sort=labels, title=None, axis=alt.Axis(labelAngle=-25, labelLimit=220))
    y = alt.Y(
        "rank:Q",
        title="Rank (1 = highest)",
        scale=alt.Scale(reverse=True, domain=[1, top], nice=False),
        axis=alt.Axis(values=list(range(1, top + 1)), format="d"),
    )
    tooltip = [
        alt.Tooltip("source:N"),
        alt.Tooltip("city_label:N", title="city"),
        alt.Tooltip("rank:Q"),
        # each source has its own unit and denominator (report.yaml notes, methodology)
        alt.Tooltip("value_text:N", title="value"),
    ]
    invalid = "break-paths-filter-domains"  # a null rank breaks the line
    # small grey points: a city whose line breaks beside a column (a gap in the next or previous
    # source) is a lone point there, which a line mark alone would not draw
    grey = (
        alt.Chart()
        .transform_filter(_is_other())
        .mark_line(
            strokeWidth=1,
            color=GREY,
            invalid=invalid,
            point=alt.OverlayMarkDef(size=18, filled=True, color=GREY),
        )
        .encode(detail="city:N", tooltip=tooltip)
    )
    focus = (
        alt.Chart()
        .transform_filter(alt.datum.role != OTHER)
        .mark_line(point=alt.OverlayMarkDef(size=90, filled=True), invalid=invalid)
        .encode(
            color=alt.Color("city:N", scale=alt.Scale(domain=domain, range=colours), title="City"),
            strokeWidth=alt.condition(alt.datum.role == HIGHLIGHT, alt.value(2.5), alt.value(1.8)),
            tooltip=tooltip,
        )
    )
    daggers = (
        alt.Chart()
        .transform_filter(alt.datum.dagger == True)  # noqa: E712 - a Vega expression
        .mark_text(text="†", dx=9, dy=0, align="left", baseline="middle", fontSize=14, color=INK)
        .encode(tooltip=tooltip)
    )
    chart = (
        alt.layer(grey, focus, daggers, data=alt.Data(values=rows))
        .encode(x=x, y=y)
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
                ]
                + _gap_lines(data, rows),
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
