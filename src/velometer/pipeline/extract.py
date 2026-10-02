"""Cached per-city snapshots clipped from a region extract (osmium extract, strategy smart)."""

from datetime import datetime
from pathlib import Path

from velometer.osmium import extract


def snapshot_name(
    city_id: str, kind: str, osm_timestamp: datetime, region_md5: str, boundary_sha256: str
) -> str:
    """The cached snapshot's file name: the one definition, shared with report.maps."""
    return f"{city_id}_{kind}_{osm_timestamp:%Y%m%d}_{region_md5[:8]}_{boundary_sha256[:8]}.osm.pbf"


def snapshot(
    region_path: Path,
    region_md5: str,
    osm_timestamp: datetime,
    city_id: str,
    kind: str,
    boundary_geojson: Path,
    boundary_sha256: str,
    data_dir: Path,
) -> Path:
    out_dir = data_dir / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = snapshot_name(city_id, kind, osm_timestamp, region_md5, boundary_sha256)
    dst = out_dir / name
    if dst.exists():
        return dst
    part = out_dir / (name.removesuffix(".osm.pbf") + ".part.osm.pbf")
    extract(region_path, boundary_geojson, part)
    part.replace(dst)
    return dst
