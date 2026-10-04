"""Cached per-city history files (clipped from region history) and dated snapshots."""

from datetime import UTC, datetime
from pathlib import Path

from velometer import osmium
from velometer.sources.geofabrik import HistoryFile


def SNAPSHOT_DATES(years: range) -> list[datetime]:  # noqa: N802
    return [datetime(y, 1, 1, tzinfo=UTC) for y in years]


def city_history_name(city_id: str, kind: str, set_md5: str, boundary_sha256: str) -> str:
    """The cached city history file's name (`city_history` writes it)."""
    return f"{city_id}_{kind}_{set_md5[:8]}_{boundary_sha256[:8]}.osh.pbf"


def dated_snapshot_name(city_history_file: str, ts: datetime) -> str:
    """The name of the snapshot `snapshot_at` cuts from a city history file at `ts` (UTC)."""
    stem = city_history_file.removesuffix(".osh.pbf")
    return f"{stem}_{ts.astimezone(UTC):%Y%m%d}.osm.pbf"


def history_snapshot_name(
    city_id: str, kind: str, set_md5: str, boundary_sha256: str, ts: datetime
) -> str:
    """The snapshot file of a history run: its city history file's name, dated."""
    return dated_snapshot_name(city_history_name(city_id, kind, set_md5, boundary_sha256), ts)


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
    dst = out_dir / city_history_name(city_id, kind, set_md5, boundary_sha256)
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
    dst = out_dir / dated_snapshot_name(city_history.name, ts)
    if dst.exists():
        return dst
    return osmium.time_filter(city_history, ts, dst)
