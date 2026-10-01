"""Thin wrappers around the osmium-tool CLI (the only place velometer shells out to osmium)."""

import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

INSTALL_HINT = "osmium-tool not found; install it with: sudo apt install osmium-tool"


class OsmiumError(RuntimeError):
    pass


def _run(*args: str) -> str:
    if shutil.which("osmium") is None:
        raise OsmiumError(INSTALL_HINT)
    proc = subprocess.run(["osmium", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise OsmiumError(f"osmium {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def require_osmium() -> str:
    return _run("--version").splitlines()[0]


def extract(src: Path, polygon_geojson: Path, dst: Path, strategy: str = "smart") -> Path:
    _run(
        "extract",
        "-p",
        str(polygon_geojson),
        "-s",
        strategy,
        "--overwrite",
        "-o",
        str(dst),
        str(src),
    )
    return dst


def fileinfo_timestamp(path: Path) -> datetime | None:
    raw = _run("fileinfo", "-g", "header.option.osmosis_replication_timestamp", str(path)).strip()
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None


def relation_polygon(src: Path, relation_id: int, dst_geojson: Path) -> Path:
    with tempfile.TemporaryDirectory(dir=dst_geojson.parent) as tmp:
        rel = Path(tmp) / "rel.osm.pbf"
        raw = Path(tmp) / "all.geojson"
        _run("getid", "-r", "--overwrite", "-o", str(rel), str(src), f"r{relation_id}")
        _run("export", "--overwrite", "-f", "geojson", "-o", str(raw), str(rel))
        feats = [
            f
            for f in json.loads(raw.read_text())["features"]
            if f["geometry"]["type"] in ("Polygon", "MultiPolygon")
        ]
        if not feats:
            raise OsmiumError(f"relation {relation_id} did not assemble into an area")
        part = Path(tmp) / "out.part.geojson"
        part.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        part.replace(dst_geojson)
    return dst_geojson
