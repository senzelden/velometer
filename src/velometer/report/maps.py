"""Static tier map per city: the current run's snapshot, classified and drawn (PNG).

Sides come from the run's snapshot file (`data/snapshots/`), classified with the report
classifier and drawn in the city's projected EPSG. Tiers A-E use the chart colours;
`excluded` and untiered sides are omitted. A `.run` marker next to each PNG holds the run id it
was drawn from, so an unchanged run is not redrawn.
"""

from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # before pyplot: no display needed

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from shapely import LineString  # noqa: E402

from velometer.config import ConfigError, load_cities, load_classifier  # noqa: E402
from velometer.db import fetch_boundary, fetch_run  # noqa: E402
from velometer.pipeline.classify import classify_ways  # noqa: E402
from velometer.pipeline.extract import snapshot_name  # noqa: E402
from velometer.pipeline.geometry import Projector  # noqa: E402
from velometer.pipeline.read import read_ways  # noqa: E402
from velometer.report.charts import INK_2, TIER_COLOURS, TIER_LABEL  # noqa: E402
from velometer.report.data import ReportData  # noqa: E402
from velometer.sources.boundaries import load_boundary_polygon  # noqa: E402

TIERS = "ABCDE"
DPI = 150
OUTLINE = "#9a9994"
ODBL = "Map data © OpenStreetMap contributors, ODbL 1.0"


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


def tier_sides(
    snapshot: Path, config_dir: Path, classifier: str, epsg: int
) -> dict[str, list[LineString]]:
    """Tiered side geometries per tier A-E in `epsg`; excluded and untiered sides are dropped."""
    cfg = load_classifier(Path(config_dir) / "classifier" / f"{classifier}.yaml")
    proj = Projector(epsg)
    out: dict[str, list[LineString]] = {t: [] for t in TIERS}
    for c in classify_ways(read_ways(snapshot).ways, cfg):
        if c.tier in out:
            out[c.tier].append(proj.line(c.side.coords))
    return {t: lines for t, lines in out.items() if lines}


def _epsg(config_dir: Path, city_id: str) -> int:
    for c in load_cities(Path(config_dir) / "cities.yaml"):
        if c.id == city_id:
            return c.epsg
    raise ConfigError(f"city {city_id} is not in cities.yaml")


def _draw(sides, outline, title: str, footer: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 9))
    if outline is not None:
        for poly in getattr(outline, "geoms", [outline]):
            ax.plot(*poly.exterior.xy, color=OUTLINE, linewidth=0.8, zorder=1)
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
    fig.subplots_adjust(left=0.02, right=0.78, top=0.94, bottom=0.07)
    plt.savefig(out, dpi=DPI)
    plt.close(fig)


def up_to_date(maps_dir: Path, city_id: str, kind: str, run_id: int) -> bool:
    """True when the PNG exists and its marker names `run_id`."""
    png, marker = Path(maps_dir) / f"{city_id}_{kind}.png", Path(maps_dir) / f"{city_id}_{kind}.run"
    return png.is_file() and marker.is_file() and marker.read_text().strip() == str(run_id)


def build_map(
    data: ReportData, city_id: str, kind: str, data_dir: Path, maps_dir: Path
) -> Path | None:
    """Write maps_dir/<city>_<kind>.png and its .run marker; None without a run or snapshot.

    An existing PNG whose marker holds the current run id is left alone.
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
    sides = tier_sides(snap, data.config_dir, point.classifier_version, epsg)
    boundary = fetch_boundary(data.conn, city_id, kind)
    outline = None
    if boundary is not None and Path(boundary.path).is_file():
        outline = load_boundary_polygon(Path(boundary.path), epsg)
    footer = f"{ODBL}\nOSM {point.osm_timestamp}, classifier {point.classifier_version}"
    maps_dir.mkdir(parents=True, exist_ok=True)
    _draw(
        sides, outline, f"{point.city_name} ({kind.upper()}): protected cycling tiers", footer, png
    )
    marker.write_text(f"{point.run_id}\n")
    return png
