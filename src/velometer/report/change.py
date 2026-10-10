"""Change map between two done runs of a city (`velometer report change`, M6 spec §4.4).

Recomputed, never stored (decision 14): both runs' cached snapshots are re-read and classified with
the report classifier; way-sides in tiers A-E match on (way id, side). Lengths are per_side km in
the city EPSG, clipped to the run's boundary exactly as `pipeline.measure` clips them, so the
recomputed tier totals must equal the stored run totals before anything is written.

Categories (all mapped km, ADR 0006: a gain is a way newly mapped, not a construction):

- `gained`: a way-side in A-E only in `to` (new, or from untiered/excluded), not a redraw;
- `lost`: a way-side in A-E only in `from`, not redrawn;
- `retiered`: the same way-side in A-E on both sides, in another tier;
- `redrawn`: a `to`-only side of the same tier lying within 15 m of `from`-only sides for at
  least 80 % of its length, where those `to` sides together also cover 80 % of each `from` side
  they replace (decision 15: redrawing sidepaths as new ways is not churn); or a side of a new
  way id split off a way-side of the same tier whose id persists and whose length fell, lying
  within 15 m of that side's `from` geometry for at least 80 % of its length (an OSM split
  keeps the old id on one piece; the split-off pieces together absorb at most the length the
  persisting side lost, plus a slack);
- `geometry`: the same way-side and tier, its clipped length changed by more than 1 m.
"""

import html
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import matplotlib

matplotlib.use("Agg")  # before pyplot: no display needed

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from shapely import STRtree, unary_union  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402
from shapely.prepared import prep  # noqa: E402

from velometer.config import REMAINDER_ID, ClassifierConfig, remainder_label  # noqa: E402
from velometer.db import fetch_run  # noqa: E402
from velometer.pipeline.classify import classify_ways  # noqa: E402
from velometer.pipeline.dedupe import share_within  # noqa: E402
from velometer.pipeline.geometry import Projector  # noqa: E402
from velometer.pipeline.measure import clipped_length_km, remainder_polygon  # noqa: E402
from velometer.pipeline.types import Classified, WayRecord  # noqa: E402
from velometer.report.charts import INK_2  # noqa: E402
from velometer.report.maps import (  # noqa: E402
    DPI,
    ODBL,
    _geojson_geometry,
    clip_feature,
    write_atomic,
)

Category = Literal["gained", "lost", "retiered", "redrawn", "geometry"]
CATEGORIES: tuple[Category, ...] = ("gained", "lost", "retiered", "redrawn", "geometry")
TIERS = ("A", "B", "C", "D", "E")
GEOMETRY_MIN_KM = 0.001  # a same-tier side whose length changed by more than 1 m
# what the split-off pieces of a shrunk side may add up to beyond its lost length: a piece
# redrawn on split is rarely exactly as long as the part it replaces
SPLIT_SLACK_SHARE = 0.2
SPLIT_SLACK_KM = 0.015
TOP_N = 20
# four map colours (geometry changes are listed, not drawn), fixed at their M9 values and
# independent of the tier palette (M10 decision 3), so the change maps need no re-render
CATEGORY_COLOURS = {
    "gained": "#1baf7a",
    "lost": "#eb6834",
    "retiered": "#eda100",
    "redrawn": "#2a78d6",
}
BEZIRK_OUTLINE = "#d6d5d0"  # light grey
MAPPED_KM_LINE = (
    "All figures are mapped km (ADR 0006): a gain is a way newly mapped as cycling "
    "infrastructure, not a construction."
)
OSM_WAY = "https://www.openstreetmap.org/way/{}"
BEZIRK_HEADING = "## Mapped km per category"  # the per-Bezirk table's section in the markdown


@dataclass(frozen=True)
class ChangeRow:
    category: Category
    way_id_from: int | None
    way_id_to: int | None
    side: str
    tier_from: str | None  # None/"excluded" on the from side of a gain
    # way_id_from on a gain (way_id_to on a loss) is set only where that way-side is mapped
    # there, untiered or excluded; None where it is not mapped at all
    tier_to: str | None
    km: float  # per_side, clipped to the boundary; redrawn: the to-side km; geometry: to - from
    km_by_subarea: dict[str, float]
    tags_changed: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)


@dataclass(frozen=True)
class ChangeResult:
    rows: list[ChangeRow]
    totals_from: dict[str, float]  # tier -> per_side km, recomputed
    totals_to: dict[str, float]


class ChangeRefused(ValueError):
    """The two runs cannot be compared, or the recomputation disagrees with the stored runs."""


@dataclass(frozen=True)
class Side:
    """A way-side in tiers A-E of one snapshot."""

    tier: str
    line: BaseGeometry  # city EPSG, unclipped
    km: float  # per_side, clipped to the boundary
    km_by_subarea: dict[str, float] = field(default_factory=dict)  # empty without subareas
    # a separately mapped way (side `self` of a highway outside the carriageway classes), not a
    # tag on a road centreline (left/right sides, cycle streets)
    separate: bool = False


class _Clip:
    """Clipped lengths in the city EPSG: the boundary (as `measure`), each subarea ∩ boundary
    and the remainder outside every subarea, scaled on a shared edge (as
    `measure.attribute_subareas`)."""

    def __init__(self, boundary: BaseGeometry, subareas) -> None:
        self.boundary, self.prepared = boundary, prep(boundary)
        self.areas = []
        for s in subareas:
            area = s.polygon.intersection(boundary)
            self.areas.append((s.subarea_id, area, prep(area)))
        if subareas:
            rest = remainder_polygon(boundary, list(subareas))
            if not rest.is_empty:
                self.areas.append((REMAINDER_ID, rest, prep(rest)))

    def km(self, line) -> float:
        return clipped_length_km(line, self.prepared, self.boundary)

    def inside(self, line):
        """The part of `line` inside the boundary."""
        return line if self.prepared.contains(line) else line.intersection(self.boundary)

    def by_subarea(self, line, city_km: float) -> dict[str, float]:
        parts = {sid: clipped_length_km(line, p, area) for sid, area, p in self.areas}
        total = sum(parts.values())
        if total > city_km + 1e-9:  # on the shared edge of two closed subareas
            parts = {sid: v * city_km / total for sid, v in parts.items()}
        return {sid: v for sid, v in parts.items() if v > 0}


def _sides(
    classified: list[Classified], proj: Projector, clip: _Clip, carriageway: Iterable[str]
) -> dict[tuple[int, str], Side]:
    """Sides in A-E with a non-zero clipped length, keyed by (way id, side)."""
    out = {}
    carriageway = frozenset(carriageway)
    for c in classified:
        if c.tier not in TIERS:
            continue
        line = proj.line(c.side.coords)
        km = clip.km(line)
        if km == 0:
            continue  # wholly outside the boundary: `measure` counts it nowhere either
        separate = c.side.side == "self" and c.side.tags.get("highway") not in carriageway
        out[(c.side.way_id, c.side.side)] = Side(
            c.tier, line, km, clip.by_subarea(line, km), separate
        )
    return out


def classified_sides(
    ways: list[WayRecord], cfg: ClassifierConfig, epsg: int, boundary: BaseGeometry, subareas=()
) -> dict[tuple[int, str], Side]:
    """One snapshot's way-sides in A-E classified with `cfg`, keyed by (way id, side): lines in
    `epsg`, per_side km clipped to `boundary` as `measure` clips them, so their tier sums are
    the run's stored per_side totals (the overlay re-reads snapshots through this, M8 §4.3)."""
    return _sides(
        classify_ways(ways, cfg),
        Projector(epsg),
        _Clip(boundary, subareas),
        cfg.road_classes.carriageway,
    )


def _tags_changed(a: Mapping[str, str], b: Mapping[str, str]) -> dict:
    return {k: (a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)}


def _diff(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    keys = set(a) | set(b)
    return {
        k: b.get(k, 0.0) - a.get(k, 0.0) for k in sorted(keys) if b.get(k, 0.0) != a.get(k, 0.0)
    }


def _totals(sides: dict[tuple[int, str], Side]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for s in sides.values():
        out[s.tier] += s.km
    return dict(sorted(out.items()))


ROAD_SIDES = frozenset({"left", "right"})


def _redraw_matches(a, b, lost, gained, clip: _Clip, dist_m: float, min_share: float):
    """gained key -> [(share, lost key)] of the lost sides it redraws (decision 15).

    A gained side matches a lost side of the same tier when at least `min_share` of it lies
    within `dist_m` of it; two road sides match only on the same side (both carry the way's
    centreline). A lost side counts as redrawn only when the gained sides matched to it together
    cover `min_share` of its part inside the boundary in turn (the part that counts), so a short
    stub never hides a long loss; matches to a lost side that fails this are dropped.
    """
    if not lost:
        return {}
    tree = STRtree([a[k].line for k in lost])
    pairs: dict[tuple, list] = defaultdict(list)
    by_lost: dict[tuple, list] = defaultdict(list)
    for key in gained:
        g = b[key]
        for i in tree.query(g.line.buffer(dist_m)):
            cand = lost[int(i)]
            if a[cand].tier != g.tier:
                continue
            if key[1] in ROAD_SIDES and cand[1] in ROAD_SIDES and key[1] != cand[1]:
                continue
            share = share_within(g.line, a[cand].line, dist_m)
            if share >= min_share:
                pairs[key].append((share, cand))
                by_lost[cand].append(key)
    covered = {
        cand
        for cand, keys in by_lost.items()
        if share_within(clip.inside(a[cand].line), unary_union([b[k].line for k in keys]), dist_m)
        >= min_share
    }
    out = {k: [m for m in ms if m[1] in covered] for k, ms in pairs.items()}
    return {k: ms for k, ms in out.items() if ms}


def _split_matches(
    a, b, shrunk, gained, ways_from: set[int], dist_m: float, min_share: float
) -> dict[tuple, tuple]:
    """gained key -> shrunk key of the persisting way-side it was split off (C1, decision 15).

    Only a side of a way id absent from `from` qualifies (a split gives the split-off pieces new
    ids). It matches a shrunk side of the same tier (and road side, as `_redraw_matches`) when
    at least `min_share` of it lies within `dist_m` of that side's `from` geometry. Pieces are
    assigned best share first; a shrunk side takes a piece only while the pieces it holds stay
    within its lost length (from km - to km) plus `SPLIT_SLACK_SHARE` of it and
    `SPLIT_SLACK_KM`, so a long new way along a slightly shortened one stays a gain.
    """
    if not shrunk or not gained:
        return {}
    tree = STRtree([a[k].line for k in shrunk])
    cands = []
    for key in gained:
        if key[0] in ways_from:
            continue
        g = b[key]
        for i in tree.query(g.line.buffer(dist_m)):
            cand = shrunk[int(i)]
            if a[cand].tier != g.tier:
                continue
            if key[1] in ROAD_SIDES and cand[1] in ROAD_SIDES and key[1] != cand[1]:
                continue
            share = share_within(g.line, a[cand].line, dist_m)
            if share >= min_share:
                cands.append((-share, key, cand))
    room = {}
    for k in shrunk:
        lost_km = a[k].km - b[k].km
        room[k] = lost_km * (1 + SPLIT_SLACK_SHARE) + SPLIT_SLACK_KM
    out = {}
    for _, key, cand in sorted(cands):
        if key in out or b[key].km > room[cand]:
            continue
        out[key] = cand
        room[cand] -= b[key].km
    return out


def compute_change(
    ways_from: list[WayRecord],
    ways_to: list[WayRecord],
    cfg: ClassifierConfig,
    epsg: int,
    boundary: BaseGeometry,
    subareas,
    redraw_dist_m: float = 15.0,
    redraw_share: float = 0.8,
) -> ChangeResult:
    """Way-side changes from `ways_from` to `ways_to` (both classified with `cfg`); `boundary` and
    the subarea polygons are in `epsg`."""
    proj, clip = Projector(epsg), _Clip(boundary, subareas)
    cls_from, cls_to = classify_ways(ways_from, cfg), classify_ways(ways_to, cfg)
    road = cfg.road_classes.carriageway
    a, b = _sides(cls_from, proj, clip, road), _sides(cls_to, proj, clip, road)
    tier_of_from = {(c.side.way_id, c.side.side): c.tier for c in cls_from}
    tier_of_to = {(c.side.way_id, c.side.side): c.tier for c in cls_to}
    tags_from = {w.id: w.tags for w in ways_from}
    tags_to = {w.id: w.tags for w in ways_to}
    rows: list[ChangeRow] = []
    for key in sorted(set(a) & set(b)):
        f, t = a[key], b[key]
        if f.tier != t.tier:
            changed = _tags_changed(tags_from[key[0]], tags_to[key[0]])
            rows.append(
                ChangeRow(
                    "retiered",
                    key[0],
                    key[0],
                    key[1],
                    f.tier,
                    t.tier,
                    t.km,
                    t.km_by_subarea,
                    changed,
                )
            )
        elif abs(t.km - f.km) > GEOMETRY_MIN_KM:
            rows.append(
                ChangeRow(
                    "geometry",
                    key[0],
                    key[0],
                    key[1],
                    f.tier,
                    t.tier,
                    t.km - f.km,
                    _diff(f.km_by_subarea, t.km_by_subarea),
                )
            )
    lost = sorted(set(a) - set(b))
    gained = sorted(set(b) - set(a))
    matches = _redraw_matches(a, b, lost, gained, clip, redraw_dist_m, redraw_share)
    shrunk = sorted(
        k for k in set(a) & set(b) if a[k].tier == b[k].tier and a[k].km - b[k].km > GEOMETRY_MIN_KM
    )
    splits = _split_matches(
        a,
        b,
        shrunk,
        [k for k in gained if k not in matches],
        {w.id for w in ways_from},
        redraw_dist_m,
        redraw_share,
    )
    for key in gained:
        g = b[key]
        best = max(matches.get(key, []), default=None, key=lambda m: (m[0], -m[1][0]))
        if best is None and key in splits:
            best = (1.0, splits[key])
        if best is not None:
            rows.append(
                ChangeRow(
                    "redrawn", best[1][0], key[0], key[1], g.tier, g.tier, g.km, g.km_by_subarea
                )
            )
        else:
            was = key[0] if key in tier_of_from else None  # the side existed, untiered/excluded
            rows.append(
                ChangeRow(
                    "gained",
                    was,
                    key[0],
                    key[1],
                    tier_of_from.get(key),
                    g.tier,
                    g.km,
                    g.km_by_subarea,
                )
            )
    consumed = {cand for ms in matches.values() for _, cand in ms}
    for key in lost:
        if key in consumed:
            continue
        f = a[key]
        now = key[0] if key in tier_of_to else None  # the side is still mapped, untiered/excluded
        rows.append(
            ChangeRow(
                "lost", key[0], now, key[1], f.tier, tier_of_to.get(key), f.km, f.km_by_subarea
            )
        )
    order = {c: i for i, c in enumerate(CATEGORIES)}
    rows.sort(key=lambda r: (order[r.category], -abs(r.km), r.way_id_to or r.way_id_from, r.side))
    return ChangeResult(rows, _totals(a), _totals(b))


COMPARED = ("city_id", "classifier_version", "classifier_parameters", "boundary_kind",
            "boundary_sha256")  # fmt: skip


def check_runs(conn, run_from: int, run_to: int) -> None:
    """Both runs done, of one city, classifier (version and parameters) and boundary, and
    `run_from`'s OSM timestamp before `run_to`'s; else ChangeRefused. Retiering by the
    classifier then cannot occur (spec §4.4)."""
    rows = {}
    for run_id in (run_from, run_to):
        try:
            rows[run_id] = fetch_run(conn, run_id)
        except KeyError as e:
            raise ChangeRefused(f"no run {run_id}") from e
        if rows[run_id]["status"] != "done":
            raise ChangeRefused(f"run {run_id} is {rows[run_id]['status']}, not done")
    a, b = rows[run_from], rows[run_to]
    t_from, t_to = (datetime.fromisoformat(r["osm_timestamp"]) for r in (a, b))
    if t_from >= t_to:
        raise ChangeRefused(
            f"run {run_from} (OSM {a['osm_timestamp']}) is not older than run {run_to} "
            f"(OSM {b['osm_timestamp']}): --from must be the earlier snapshot"
        )
    for col in COMPARED:
        if a[col] != b[col]:
            raise ChangeRefused(
                f"runs {run_from} and {run_to} differ in {col}: {a[col]} vs {b[col]}"
            )


def check_totals(
    result: ChangeResult,
    stored_from: Mapping[str, float],
    stored_to: Mapping[str, float],
    tol_km: float = 0.01,
) -> None:
    """The recomputed per_side tier totals (A-E) equal the stored ones within `tol_km`; a tier
    missing on one side counts as 0 km. Else ChangeRefused naming the tier and both values."""
    check_tier_totals("from", result.totals_from, stored_from, tol_km)
    check_tier_totals("to", result.totals_to, stored_to, tol_km)


def check_tier_totals(
    label: str, got: Mapping[str, float], stored: Mapping[str, float], tol_km: float = 0.01
) -> None:
    """One run's recomputed per_side tier totals (A-E) equal its stored ones within `tol_km`; a
    tier missing on one side counts as 0 km. Else ChangeRefused naming `run <label>`, the tier
    and both values."""
    for tier in TIERS:
        g, s = got.get(tier, 0.0), stored.get(tier, 0.0)
        if abs(g - s) > tol_km:
            raise ChangeRefused(
                f"run {label}: tier {tier} recomputed {g:.3f} km vs stored {s:.3f} km "
                f"(tolerance {tol_km} km)"
            )


# --- outputs ------------------------------------------------------------------------------------


def _km(v: float) -> str:
    return f"{v:.3f}"


def _tier(t: str | None, way_id: int | None) -> str:
    """A side's tier; `–` where the way-side is not mapped on that side at all."""
    if way_id is None:
        return "–"
    return t if t is not None else "untiered"


def _way(i: int | None) -> str:
    return "–" if i is None else f"[{i}]({OSM_WAY.format(i)})"


def _tags(changed: Mapping[str, tuple[str | None, str | None]]) -> str:
    return "; ".join(f"`{k}`: {a or '–'} → {b or '–'}" for k, (a, b) in changed.items())


def _cell(text: str) -> str:
    """Table cell text from config (city and subarea names): HTML-escaped, so the page never
    carries raw HTML into a renderer that passes it, and `|` escaped for the table."""
    return html.escape(text, quote=False).replace("|", "\\|")


RUNS_LINE = re.compile(r"^From run (\d+) \(OSM [^)]*\) to run (\d+) ", re.MULTILINE)


def change_runs(markdown: str) -> tuple[int, int] | None:
    """The (from, to) run ids of a change page's header, or None if it has none."""
    m = RUNS_LINE.search(markdown)
    return None if m is None else (int(m.group(1)), int(m.group(2)))


def render_markdown(
    result: ChangeResult, city: str, run_from: Mapping, run_to: Mapping, names: dict[str, str]
) -> str:
    """The change review page: header, per-Bezirk mapped km per category, top rows per category.

    `run_from`/`run_to` are run rows (`db.fetch_run`); `names` maps subarea id -> name. Rows
    with km outside every subarea add the remainder as the table's last Bezirk-level row.
    """
    lines = [
        f"# {_cell(city)}: mapped cycling infrastructure change",
        "",
        f"From run {run_from['id']} (OSM {run_from['osm_timestamp']}) to run {run_to['id']} "
        f"(OSM {run_to['osm_timestamp']}); classifier {run_from['classifier_version']}, "
        f"boundary sha `{run_from['boundary_sha256'][:12]}`.",
        "",
        MAPPED_KM_LINE,
        "Categories: mapped gained / lost / retiered / redrawn, and geometry (the same way-side "
        "and tier, its length changed by more than 1 m; km is the signed length change). A "
        "redrawn way-side lies within 15 m of replaced way-sides of the same tier for at least "
        "80 % of its length, and the new way-sides together cover 80 % of each one they "
        "replace; a way-side split off an existing way-side of the same tier (a new way id "
        "along a way-side that got shorter, up to 1.2 times the length it lost) counts as "
        "redrawn too. A redrawn row's km is the new "
        "way-side's.",
        "",
        "## Totals (per_side mapped km, recomputed and checked against both runs)",
        "",
        "The net change (to − from) is the change in mapped km per tier. The categories below "
        "do not sum to it: a redrawn or retiered row carries only its `to` km, and a split "
        "way's persisting piece shows its shortening as a negative geometry row, which its "
        "split-off (redrawn) pieces offset.",
        "",
        "| tier | from | to | net change (to − from) |",
        "|---|---:|---:|---:|",
    ]
    for t in (*TIERS, None):
        f = sum(result.totals_from.values()) if t is None else result.totals_from.get(t, 0.0)
        to = sum(result.totals_to.values()) if t is None else result.totals_to.get(t, 0.0)
        label = "**A–E**" if t is None else t
        lines.append(f"| {label} | {_km(f)} | {_km(to)} | {to - f:+.3f} |")
    by_cat = {c: [r for r in result.rows if r.category == c] for c in CATEGORIES}
    lines += ["", BEZIRK_HEADING, ""]
    lines += ["| | " + " | ".join(CATEGORIES) + " |", "|---|" + "---:|" * len(CATEGORIES)]
    if names:
        for sid, name in sorted(names.items(), key=lambda kv: kv[1]):
            cells = [_km(sum(r.km_by_subarea.get(sid, 0.0) for r in by_cat[c])) for c in CATEGORIES]
            lines.append(f"| {_cell(name)} | " + " | ".join(cells) + " |")
        if any(REMAINDER_ID in r.km_by_subarea for r in result.rows):
            cells = [
                _km(sum(r.km_by_subarea.get(REMAINDER_ID, 0.0) for r in by_cat[c]))
                for c in CATEGORIES
            ]
            lines.append(f"| {remainder_label(len(names))} | " + " | ".join(cells) + " |")
    total = [_km(sum(r.km for r in by_cat[c])) for c in CATEGORIES]
    lines.append(f"| **{_cell(city)}** | " + " | ".join(total) + " |")
    for c in CATEGORIES:
        rows = sorted(by_cat[c], key=lambda r: -abs(r.km))[:TOP_N]
        n = len(by_cat[c])
        lines += ["", f"## {c}: {n} way-side{'' if n == 1 else 's'} (top {TOP_N} by mapped km)", ""]
        if not rows:
            lines.append("None.")
            continue
        head = "| way (from) | way (to) | side | tier | mapped km |"
        sep = "|---|---|---|---|---:|"
        if c == "retiered":
            head, sep = head + " tags changed |", sep + "---|"
        lines += [head, sep]
        for r in rows:
            tier = (
                r.tier_to
                if r.tier_from == r.tier_to
                else f"{_tier(r.tier_from, r.way_id_from)} → {_tier(r.tier_to, r.way_id_to)}"
            )
            line = (
                f"| {_way(r.way_id_from)} | {_way(r.way_id_to)} | {r.side} | {tier} | {_km(r.km)} |"
            )
            if c == "retiered":
                line += f" {_tags(r.tags_changed)} |"
            lines.append(line)
    lines += ["", f"_{ODBL}_", ""]
    return "\n".join(lines)


def bezirk_table(markdown: str) -> str | None:
    """The per-Bezirk table of a change markdown (its `BEZIRK_HEADING` section's table lines),
    or None if the page has none. The app shows it as written, never re-computed."""
    lines = markdown.splitlines()
    if BEZIRK_HEADING not in lines:
        return None
    table = []
    for line in lines[lines.index(BEZIRK_HEADING) + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            table.append(line)
    return "\n".join(table) or None


def _coords(ways: Iterable[WayRecord]) -> dict[int, tuple]:
    return {w.id: w.coords for w in ways}


def _row_coords(row: ChangeRow, frm: dict, to: dict):
    return frm[row.way_id_from] if row.category == "lost" else to[row.way_id_to]


def write_geojson(
    result: ChangeResult,
    ways_from: list[WayRecord],
    ways_to: list[WayRecord],
    path: Path,
    *,
    run_from: int | None = None,
    run_to: int | None = None,
) -> Path:
    """One WGS84 Feature per row (the `from` way for a loss, the `to` way otherwise); the
    collection's properties name the two runs compared."""
    import json

    from shapely import LineString

    frm, to = _coords(ways_from), _coords(ways_to)
    feats = []
    for r in result.rows:
        props = {
            "category": r.category,
            "way_id_from": r.way_id_from,
            "way_id_to": r.way_id_to,
            "side": r.side,
            "tier_from": r.tier_from,
            "tier_to": r.tier_to,
            "km": round(r.km, 4),
            "km_by_subarea": {k: round(v, 4) for k, v in r.km_by_subarea.items()},
        }
        if r.tags_changed:
            props["tags_changed"] = {k: list(v) for k, v in r.tags_changed.items()}
        geom = _geojson_geometry(LineString(_row_coords(r, frm, to)))
        feats.append({"type": "Feature", "geometry": geom, "properties": props})
    doc = {
        "type": "FeatureCollection",
        "properties": {
            "attribution": ODBL,
            "unit": "mapped km (ADR 0006)",
            "run_from": run_from,
            "run_to": run_to,
        },
        "features": feats,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return path


def render_png(
    result: ChangeResult,
    ways_from: list[WayRecord],
    ways_to: list[WayRecord],
    boundary: BaseGeometry,
    path: Path,
    *,
    epsg: int,
    subareas=(),
    title: str = "",
) -> Path:
    """Static change map in the city EPSG (`boundary`, subarea polygons in `epsg`): gained, lost,
    retiered and redrawn way-sides clipped to the boundary, light-grey Bezirk outlines."""
    proj = Projector(epsg)
    frm, to = _coords(ways_from), _coords(ways_to)
    fig, ax = plt.subplots(figsize=(9, 9))
    for s in subareas:
        for poly in getattr(s.polygon, "geoms", [s.polygon]):
            ax.plot(*poly.exterior.xy, color=BEZIRK_OUTLINE, linewidth=0.6, zorder=1)
    for poly in getattr(boundary, "geoms", [boundary]):
        ax.plot(*poly.exterior.xy, color=INK_2, linewidth=0.8, zorder=2)
    km = defaultdict(float)
    for i, (cat, colour) in enumerate(CATEGORY_COLOURS.items()):
        for r in result.rows:
            if r.category != cat:
                continue
            km[cat] += r.km
            geom = clip_feature(proj.line(_row_coords(r, frm, to)), boundary)
            for line in getattr(geom, "geoms", [geom]) if geom is not None else []:
                ax.plot(*line.xy, color=colour, linewidth=1.2, zorder=10 - i,
                        solid_capstyle="round")  # fmt: skip
    ax.set_aspect("equal")
    ax.axis("off")
    handles = [
        Line2D([], [], color=colour, linewidth=2.5, label=f"{cat} ({km[cat]:.1f} mapped km)")
        for cat, colour in CATEGORY_COLOURS.items()
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False,
              fontsize=9)  # fmt: skip
    if title:
        ax.set_title(title, loc="left", fontsize=14)
    fig.text(0.02, 0.015, f"{ODBL} · {MAPPED_KM_LINE}", fontsize=7, color=INK_2, va="bottom",
             wrap=True)  # fmt: skip
    fig.subplots_adjust(left=0.02, right=0.72, top=0.96, bottom=0.07)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=DPI)
    plt.close(fig)
    return path
