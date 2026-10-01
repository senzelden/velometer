"""Cached per-city history files (clipped from region history) and dated snapshots."""

from datetime import UTC, datetime
from pathlib import Path

from velometer import osmium
from velometer.sources.geofabrik import HistoryFile


def SNAPSHOT_DATES(years: range) -> list[datetime]:  # noqa: N802
    return [datetime(y, 1, 1, tzinfo=UTC) for y in years]


def city_history(
    city_id: str,
    kind: str,
    files: list[HistoryFile],
    set_md5: str,
    boundary_geojson: Path,
    boundary_sha256: str,
    data_dir: Path,
) -> Path:
    out_dir = data_dir / "history" / "city"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{city_id}_{kind}_{set_md5[:8]}_{boundary_sha256[:8]}.osh.pbf"
    if dst.exists():
        return dst
    if len(files) > 1:
        merged = out_dir / f"{dst.name.removesuffix('.osh.pbf')}.merged.osh.pbf"
        try:
            osmium.merge_history([f.path for f in files], merged)
            return osmium.extract_history(merged, boundary_geojson, dst)
        finally:
            merged.unlink(missing_ok=True)
    return osmium.extract_history(files[0].path, boundary_geojson, dst)


def snapshot_at(city_history: Path, ts: datetime, data_dir: Path) -> Path:
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    ts = ts.astimezone(UTC)
    out_dir = data_dir / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = city_history.name.removesuffix(".osh.pbf")
    dst = out_dir / f"{stem}_{ts:%Y%m%d}.osm.pbf"
    if dst.exists():
        return dst
    return osmium.time_filter(city_history, ts, dst)
