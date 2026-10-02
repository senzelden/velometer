"""Tier map per city: the current run's snapshot, classified once and written twice.

Sides come from the run's snapshot file (`data/snapshots/`), classified with the report
classifier. Tiers A-E only; `excluded` and untiered sides are omitted. Two files come from the
same classification pass:

- `<city>_<kind>.png`: a static image drawn in the city's projected EPSG, tiers in chart colours;
- `<city>_<kind>.geojson`: the same sides in WGS84 for the app's interactive map, each with its
  way id, side, tier, subtype, rule id, km (measured in the city EPSG and clipped to the boundary,
  as `pipeline.measure` does) and a subset of the way's OSM tags. The boundary rides along as a
  `boundary` member and the run as a `properties` member of the FeatureCollection.

A `.run` marker next to them holds the run id they were made from, so an unchanged run is not
redrawn; a missing PNG or GeoJSON is.
"""

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # before pyplot: no display needed

import matplotlib.pyplot as plt  # noqa: E402
import shapely  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from shapely import LineString  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402
from shapely.prepared import prep  # noqa: E402

from velometer.config import ConfigError, load_cities, load_classifier  # noqa: E402
from velometer.db import fetch_boundary, fetch_run  # noqa: E402
from velometer.pipeline.classify import classify_ways  # noqa: E402
from velometer.pipeline.extract import snapshot_name  # noqa: E402
from velometer.pipeline.geometry import Projector, length_km  # noqa: E402
from velometer.pipeline.measure import clipped_length_km  # noqa: E402
from velometer.pipeline.read import read_ways  # noqa: E402
from velometer.pipeline.types import Classified  # noqa: E402
from velometer.report.charts import INK_2, OUTLINE, TIER_COLOURS, TIER_LABEL  # noqa: E402
from velometer.report.data import ReportData  # noqa: E402
from velometer.sources.boundaries import load_boundary_polygon  # noqa: E402

TIERS = "ABCDE"
TIER_SET = frozenset(TIERS)
DECIMALS = 5  # ~1 m at these latitudes: plenty for a zoomable map, a third fewer bytes than 7
# OSM tag keys kept in the GeoJSON (the popup): exact keys, and prefix/suffix families.
TAG_KEYS = frozenset({"highway", "bicycle", "foot", "segregated", "bicycle_road", "cyclestreet"})
TAG_PREFIXES = ("cycleway", "oneway")
DPI = 150
ODBL = "Map data © OpenStreetMap contributors, ODbL 1.0"
MAPPED_KM = "OSM mapped km, not built km"  # ADR 0006


def snapshot_path(run_row: dict, data_dir: Path) -> Path:
    """The run's snapshot file, named exactly as `pipeline.extract.snapshot` writes it."""
    ts = datetime.fromisoformat(run_row["osm_timestamp"]).astimezone(UTC)
    return (
        Path(data_dir)
        / "snapshots"
        / snapshot_name(
            run_row["city_id"],
            run_row["boundary_kind"],
            ts,
            run_row["region_md5"],
            run_row["boundary_sha256"],
        )
    )


def tiered(
    snapshot: Path, config_dir: Path, classifier: str
) -> tuple[list[Classified], dict[int, Mapping[str, str]]]:
    """The snapshot's sides classified once: those in tiers A-E, and each way's OSM tags."""
    cfg = load_classifier(Path(config_dir) / "classifier" / f"{classifier}.yaml")
    ways = read_ways(snapshot).ways
    sides = [c for c in classify_ways(ways, cfg) if c.tier in TIER_SET]
    return sides, {w.id: w.tags for w in ways}


def _by_tier(sides: list[Classified], proj: Projector) -> dict[str, list[LineString]]:
    out: dict[str, list[LineString]] = {t: [] for t in TIERS}
    for c in sides:
        if c.tier in TIER_SET:
            out[c.tier].append(proj.line(c.side.coords))
    return {t: lines for t, lines in out.items() if lines}


def tier_sides(
    snapshot: Path, config_dir: Path, classifier: str, epsg: int
) -> dict[str, list[LineString]]:
    """Tiered side geometries per tier A-E in `epsg`; excluded and untiered sides are dropped."""
    return _by_tier(tiered(snapshot, config_dir, classifier)[0], Projector(epsg))


def keep_tag(key: str) -> bool:
    """The OSM tags the map popup shows: highway, cycleway*, sidewalk*:bicycle, bicycle, foot,
    segregated, oneway*, bicycle_road, cyclestreet."""
    return (
        key in TAG_KEYS
        or key.startswith(TAG_PREFIXES)
        or (key.startswith("sidewalk") and key.endswith(":bicycle"))
    )


def _round(coords) -> list[list[float]]:
    return [[round(x, DECIMALS), round(y, DECIMALS)] for x, y in coords]


def side_features(
    sides: list[Classified],
    way_tags: Mapping[int, Mapping[str, str]],
    proj: Projector,
    outline: BaseGeometry | None,
) -> list[dict]:
    """One GeoJSON Feature per side in tiers A-E (WGS84, rounded to DECIMALS).

    `km` is the side's length in `proj`'s EPSG, clipped to `outline` (same EPSG) when given, as
    `pipeline.measure` measures it for the run. `tags` are the way's OSM tags (as on the linked
    openstreetmap.org page, not the classifier's per-side view) filtered by `keep_tag`.
    """
    prepared = None if outline is None else prep(outline)
    feats = []
    for c in sides:
        if c.tier not in TIER_SET:
            continue
        line = proj.line(c.side.coords)
        km = length_km(line) if outline is None else clipped_length_km(line, prepared, outline)
        tags = way_tags.get(c.side.way_id, {})
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": _round(c.side.coords)},
                "properties": {
                    "way_id": c.side.way_id,
                    "side": c.side.side,
                    "tier": c.tier,
                    "subtype": c.subtype,
                    "rule_id": c.rule_id,
                    "km": round(km, 3),
                    "tags": {k: v for k, v in sorted(tags.items()) if keep_tag(k)},
                },
            }
        )
    return feats


def boundary_feature(path: Path, city_id: str, kind: str) -> dict:
    """The boundary file's geometry (WGS84) as one Feature, rounded to DECIMALS."""
    feats = json.loads(Path(path).read_text())["features"]
    geom = shapely.union_all([shapely.from_geojson(json.dumps(f["geometry"])) for f in feats])
    geom = shapely.transform(geom, lambda xy: xy.round(DECIMALS))
    return {
        "type": "Feature",
        "properties": {"city_id": city_id, "kind": kind},
        "geometry": json.loads(shapely.to_geojson(geom)),
    }


def write_atomic(path: Path, data: bytes) -> None:
    """Write `data` to a temp file beside `path`, then rename it over `path`."""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _epsg(config_dir: Path, city_id: str) -> int:
    for c in load_cities(Path(config_dir) / "cities.yaml"):
        if c.id == city_id:
            return c.epsg
    raise ConfigError(f"city {city_id} is not in cities.yaml")


def _draw(sides, outline, title: str, footer: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 9))
    if outline is not None:
        for poly in getattr(outline, "geoms", [outline]):
            # interior rings too: an enclave (Frederiksberg in København) is not city area
            for ring in (poly.exterior, *poly.interiors):
                ax.plot(*ring.xy, color=OUTLINE, linewidth=0.8, zorder=1)
    for i, tier in enumerate(TIERS):  # A drawn last: on top where sides overlap
        for line in sides.get(tier, []):
            ax.plot(*line.xy, color=TIER_COLOURS[i], linewidth=1.1, zorder=10 - i,
                    solid_capstyle="round")  # fmt: skip
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=14)
    handles = [
        Line2D([], [], color=TIER_COLOURS[i], linewidth=2.5, label=TIER_LABEL[t])
        for i, t in enumerate(TIERS)
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False,
              fontsize=9)  # fmt: skip
    fig.text(0.02, 0.015, footer, fontsize=8, color=INK_2, va="bottom")
    # the legend sits right of the axes: leave room for its longest label inside the figure
    fig.subplots_adjust(left=0.02, right=0.74, top=0.94, bottom=0.07)
    plt.savefig(out, dpi=DPI)
    plt.close(fig)


def up_to_date(maps_dir: Path, city_id: str, kind: str, run_id: int) -> bool:
    """True when the PNG and GeoJSON exist and their marker names `run_id`."""
    stem = Path(maps_dir) / f"{city_id}_{kind}"
    marker = stem.with_suffix(".run")
    return (
        stem.with_suffix(".png").is_file()
        and stem.with_suffix(".geojson").is_file()
        and marker.is_file()
        and marker.read_text().strip() == str(run_id)
    )


def build_map(
    data: ReportData, city_id: str, kind: str, data_dir: Path, maps_dir: Path
) -> Path | None:
    """Write maps_dir/<city>_<kind>.png, .geojson and the .run marker; None without a run or
    snapshot. Returns the PNG's path.

    Existing files whose marker holds the current run id are left alone.
    """
    point = data.current(city_id, kind)
    if point is None:
        return None
    row = fetch_run(data.conn, point.run_id)
    snap = snapshot_path(row, data_dir)
    if not snap.is_file():
        return None
    maps_dir = Path(maps_dir)
    png, marker = maps_dir / f"{city_id}_{kind}.png", maps_dir / f"{city_id}_{kind}.run"
    if up_to_date(maps_dir, city_id, kind, point.run_id):
        return png
    epsg = _epsg(data.config_dir, city_id)
    proj = Projector(epsg)
    classified, way_tags = tiered(snap, data.config_dir, point.classifier_version)
    sides = _by_tier(classified, proj)
    boundary = fetch_boundary(data.conn, city_id, kind)
    outline, boundary_member = None, None
    if boundary is not None and Path(boundary.path).is_file():
        outline = load_boundary_polygon(Path(boundary.path), epsg)
        boundary_member = boundary_feature(Path(boundary.path), city_id, kind)
    footer = (
        f"{ODBL} · {MAPPED_KM}\nOSM {point.osm_timestamp}, classifier {point.classifier_version}"
    )
    maps_dir.mkdir(parents=True, exist_ok=True)
    _draw(
        sides, outline, f"{point.city_name} ({kind.upper()}): protected cycling tiers", footer, png
    )
    collection = {
        "type": "FeatureCollection",
        "properties": {
            "run_id": point.run_id,
            "osm_timestamp": point.osm_timestamp,
            "classifier": point.classifier_version,
        },
        "boundary": boundary_member,
        "features": side_features(classified, way_tags, proj, outline),
    }
    text = json.dumps(collection, ensure_ascii=False, separators=(",", ":"))
    write_atomic(maps_dir / f"{city_id}_{kind}.geojson", text.encode("utf-8"))
    marker.write_text(f"{point.run_id}\n")
    return png
