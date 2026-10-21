"""Cut one self-hosted Protomaps PMTiles extract that covers every city (M16 spec §4.3).

The extract is the union of each city's largest boundary (FUA), padded 2 km, cut out of a dated
Protomaps daily build with the pinned `pmtiles` CLI (go-pmtiles). The CLI binary is downloaded
once into the git-ignored `data/cache/bin/` and verified against `PMTILES_SHA256`.

    uv run python tools/tiles.py --site DIR --maxzoom 13 --out data/tiles/velometer.pmtiles
    uv run python tools/tiles.py --site DIR --measure

The extract keeps every layer of the build, `landcover` included (the CLI cannot drop a layer).
The style draws no landcover, and the extract is not offered as a tile service.
The data are OpenStreetMap, © OpenStreetMap contributors, ODbL (docs/review/m16-legal.md §1.7).
"""

import argparse
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

PMTILES_VERSION = "1.31.2"  # released 2026-07-22
PMTILES_URL = (
    f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/"
    f"go-pmtiles_{PMTILES_VERSION}_Linux_x86_64.tar.gz"
)
# The release publishes no checksum file; this is the asset digest the GitHub release API reports
# (`digest: sha256:...`), and it matches a download made on 2026-10-21.
PMTILES_SHA256 = "3ed7dbf4ec2e6dfe5e25b6f70d1ffc932729f93c86db353bf514dd71010a312f"
# Protomaps keeps only the latest week and some older builds; 20260811 (basemap 4.15.1) was still
# served on 2026-10-21 (https://build-metadata.protomaps.dev/builds.json lists what exists).
PROTOMAPS_BUILD = "20260811"
BUILD_URL = f"https://build.protomaps.com/{PROTOMAPS_BUILD}.pmtiles"

BIN_DIR = ROOT / "data" / "cache" / "bin"
# Chosen by measured size (dry run, 2026-10-21): z13 898 MB, z14 1.7 GB, z15 3.6 GB; maps overzoom.
MAXZOOM = 13
PAD_KM = 2.0
KM_PER_DEGREE = 111.32

BBox = tuple[float, float, float, float]


def _vertices(geometry: dict) -> list[tuple[float, float]]:
    def walk(node):
        if node and isinstance(node[0], (int, float)):
            yield (node[0], node[1])
        else:
            for child in node:
                yield from walk(child)

    return list(walk(geometry["coordinates"]))


def city_bboxes(cities_yaml: Path, maps_dir: Path) -> dict[str, BBox]:
    """Lon/lat box of each city's FUA boundary in the export, padded `PAD_KM` on every side."""
    cities = yaml.safe_load(Path(cities_yaml).read_text())["cities"]
    boxes: dict[str, BBox] = {}
    for city in cities:
        cid = city["id"]
        path = Path(maps_dir) / f"{cid}_fua.geojson"
        if not path.exists():
            raise FileNotFoundError(f"no FUA boundary for {cid}: {path}")
        pts = _vertices(json.loads(path.read_text())["boundary"]["geometry"])
        lons, lats = [p[0] for p in pts], [p[1] for p in pts]
        south, north = min(lats) - PAD_KM / KM_PER_DEGREE, max(lats) + PAD_KM / KM_PER_DEGREE
        coslat = math.cos(math.radians(max(abs(south), abs(north))))
        dlon = PAD_KM / (KM_PER_DEGREE * coslat)
        boxes[cid] = (min(lons) - dlon, south, max(lons) + dlon, north)
    return boxes


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 (pinned https URL)
        return response.read()


def _binary_from(data: bytes) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        return tar.extractfile(tar.getmember("pmtiles")).read()


def ensure_pmtiles(
    bin_dir: Path = BIN_DIR,
    fetch: Callable[[str], bytes] = _download,
    sha256: str = PMTILES_SHA256,
) -> Path:
    """The pinned `pmtiles` binary in `bin_dir`.

    The verified tarball is cached beside the binary. Every call re-hashes the cached tarball
    against the pin (a mismatch is downloaded again and verified) and restores the binary from it
    when the binary is missing or differs, so a tampered cache is never run.
    """
    bin_dir = Path(bin_dir)
    binary = bin_dir / f"pmtiles-{PMTILES_VERSION}"
    tarball = bin_dir / f"pmtiles-{PMTILES_VERSION}.tar.gz"
    data = tarball.read_bytes() if tarball.exists() else b""
    if hashlib.sha256(data).hexdigest() != sha256:
        data = fetch(PMTILES_URL)
        got = hashlib.sha256(data).hexdigest()
        if got != sha256:
            raise ValueError(f"pmtiles download sha256 {got} does not match the pinned {sha256}")
        bin_dir.mkdir(parents=True, exist_ok=True)
        tarball.write_bytes(data)
    payload = _binary_from(data)
    if not binary.exists() or binary.read_bytes() != payload:
        partial = binary.with_name(binary.name + ".part")
        partial.write_bytes(payload)
        partial.chmod(0o755)
        partial.replace(binary)
    return binary


def region_geojson(bboxes: dict[str, BBox]) -> dict:
    """One MultiPolygon feature made of every city's box."""
    polygons = [[[[w, s], [e, s], [e, n], [w, n], [w, s]]] for (w, s, e, n) in bboxes.values()]
    return {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "MultiPolygon", "coordinates": polygons},
    }


def _run(argv: list[str]) -> None:
    subprocess.run(argv, check=True)


def _capture(argv: list[str]) -> str:
    done = subprocess.run(argv, check=True, capture_output=True, text=True)
    return done.stdout + done.stderr


def extract(
    build_url: str,
    bboxes: dict[str, BBox],
    maxzoom: int,
    out: Path,
    binary: Path | None = None,
    run: Callable[[list[str]], None] = _run,
) -> int:
    """Cut `out` (bytes returned) from `build_url`, all cities, zoom 0 to `maxzoom`."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    binary = binary or ensure_pmtiles()
    region = out.with_name(out.stem + ".region.geojson")
    partial = out.with_name(out.stem + ".part.pmtiles")
    region.write_text(json.dumps(region_geojson(bboxes)))
    argv = [
        str(binary),
        "extract",
        build_url,
        "--region",
        str(region),
        "--maxzoom",
        str(maxzoom),
        str(partial),
    ]
    try:
        run(argv)
        partial.replace(out)
    finally:
        region.unlink(missing_ok=True)
        partial.unlink(missing_ok=True)
    return out.stat().st_size


def measure(
    build_url: str,
    bboxes: dict[str, BBox],
    maxzoom: int,
    binary: Path | None = None,
    capture: Callable[[list[str]], str] = _capture,
) -> str:
    """The archive size `pmtiles extract --dry-run` predicts for `maxzoom`; nothing is kept."""
    binary = binary or ensure_pmtiles()
    with tempfile.TemporaryDirectory() as tmp:
        region = Path(tmp) / "region.geojson"
        region.write_text(json.dumps(region_geojson(bboxes)))
        argv = [str(binary), "extract", build_url, "--region", str(region)]
        argv += ["--maxzoom", str(maxzoom), "--dry-run", os.devnull]
        text = capture(argv)
    match = re.search(r"archive size of ([\d.]+ [KMGT]?B)", text)
    if not match:
        raise RuntimeError(f"no archive size in the pmtiles output: {text[-300:]}")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", type=Path, required=True, help="export directory with maps/")
    ap.add_argument("--maxzoom", type=int, default=MAXZOOM)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "tiles" / "velometer.pmtiles")
    ap.add_argument("--measure", action="store_true", help="print the size at z14 and z15")
    ap.add_argument("--build-url", default=BUILD_URL)
    ap.add_argument("--cities", type=Path, default=ROOT / "config" / "cities.yaml")
    args = ap.parse_args(argv)

    boxes = city_bboxes(args.cities, args.site / "maps")
    if args.measure:
        for zoom in (14, 15):
            print(f"z{zoom}: {measure(args.build_url, boxes, zoom)}", flush=True)
        return 0
    size = extract(args.build_url, boxes, args.maxzoom, args.out)
    print(f"{args.out}: {size} bytes, build {PROTOMAPS_BUILD}, maxzoom {args.maxzoom}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
