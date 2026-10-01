"""City boundaries: GISCO LAU 2024 (default), URAU 2024 FUA, OSM admin relation (fallback)."""

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pyogrio
import shapely
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from velometer.config import CityConfig
from velometer.models import Boundary, Population
from velometer.osmium import relation_polygon
from velometer.sources.download import fetch, new_client

GISCO = "https://gisco-services.ec.europa.eu/distribution/v2"
LAU_URL = f"{GISCO}/lau/gpkg/LAU_RG_01M_2024_3035.gpkg"
FUA_URL = f"{GISCO}/urau/gpkg/URAU_RG_100K_2024_3035_FUA.gpkg"
FUA_FIELD = "URAU_CODE"
GISCO_VERSION = {"lau": "LAU 2024 (1:1M)", "fua": "URAU 2024 FUA (1:100k)"}
EUROSTAT_POP = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_pjangrp3"
    "?geo={nuts3}&sex=T&age=TOTAL&unit=NR&time=2024&format=JSON"
)


@dataclass(frozen=True)
class BoundaryRecord:
    boundary: Boundary
    geojson_path: Path
    polygon: BaseGeometry  # city EPSG


def fetch_gisco(data_dir: Path) -> tuple[Path, Path]:
    d = data_dir / "external" / "gisco"
    return fetch(LAU_URL, d / "LAU_RG_01M_2024_3035.gpkg"), fetch(
        FUA_URL, d / "URAU_RG_100K_2024_3035_FUA.gpkg"
    )


def select_feature(gpkg: Path, field: str, code: str) -> tuple[BaseGeometry, dict]:
    escaped = code.replace("'", "''")
    meta, _, geoms, values = pyogrio.raw.read(str(gpkg), where=f"{field} = '{escaped}'")
    if len(geoms) != 1:
        raise ValueError(f"{gpkg.name}: {field}={code!r} matched {len(geoms)} features")
    props = {name: values[i][0] for i, name in enumerate(meta["fields"])}
    return shapely.from_wkb(geoms[0]), props


def _to(geom: BaseGeometry, src: int, dst: int) -> BaseGeometry:
    tf = Transformer.from_crs(src, dst, always_xy=True)
    return transform(tf.transform, geom)


def _valid_polygonal(geom: BaseGeometry) -> BaseGeometry:
    """Repair an invalid geometry, keeping only its polygonal parts."""
    if geom.is_valid:
        return geom
    parts = []
    for part in shapely.get_parts(shapely.make_valid(geom)):
        if part.geom_type == "GeometryCollection":
            parts.extend(shapely.get_parts(part))
        else:
            parts.append(part)
    parts = [p for p in parts if p.geom_type == "Polygon" and not p.is_empty]
    if not parts:
        raise ValueError(f"geometry has no polygonal part after make_valid: {geom.wkt[:80]}")
    return parts[0] if len(parts) == 1 else shapely.MultiPolygon(parts)


def write_boundary(
    city: CityConfig,
    kind: str,
    geom_3035: BaseGeometry,
    source: str,
    data_dir: Path,
    src_epsg: int = 3035,
) -> BoundaryRecord:
    geom = _valid_polygonal(geom_3035)
    wgs = _valid_polygonal(_to(geom, src_epsg, 4326))
    out = data_dir / "boundaries" / f"{city.id}_{kind}.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    feature = {
        "type": "Feature",
        "properties": {"city_id": city.id, "kind": kind},
        "geometry": json.loads(shapely.to_geojson(wgs)),
    }
    out.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
    projected = _valid_polygonal(_to(geom, src_epsg, city.epsg))
    record = Boundary(
        city_id=city.id,
        kind=kind,
        source=source,
        source_version=GISCO_VERSION.get(kind, "OSM admin relation"),
        area_km2=projected.area / 1e6,
        path=str(out),
        sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
    )
    return BoundaryRecord(record, out, projected)


def load_boundary_polygon(geojson_path: Path, epsg: int) -> BaseGeometry:
    feats = json.loads(geojson_path.read_text())["features"]
    geom = shapely.union_all([shapely.from_geojson(json.dumps(f["geometry"])) for f in feats])
    return _valid_polygonal(_to(_valid_polygonal(geom), 4326, epsg))


def population(
    city: CityConfig, lau_props: dict, fetch_json: Callable[[str], dict] | None = None
) -> Population | None:
    raw = lau_props.get("POP_2024")
    if raw is not None and not math.isnan(raw) and raw > 0:
        return Population(value=int(raw), year=2024, source="GISCO LAU 2024 POP_2024")
    if not city.nuts3_code:
        return None
    dataset = f"demo_r_pjangrp3 {city.nuts3_code}"
    data = (fetch_json or _get_json)(EUROSTAT_POP.format(nuts3=city.nuts3_code))
    values = list((data.get("value") or {}).values())
    if not values or not values[0] or values[0] <= 0:
        raise ValueError(f"Eurostat {dataset} 2024: no positive population in response")
    return Population(value=int(values[0]), year=2024, source=f"Eurostat {dataset} 2024")


def _get_json(url: str) -> dict:
    with new_client() as c:
        r = c.get(url)
        r.raise_for_status()
        return r.json()


def city_boundary(
    city: CityConfig, kind: str, data_dir: Path, region_path: Path | None = None
) -> tuple[BoundaryRecord, Population | None]:
    if kind in ("lau", "fua"):
        code = city.lau_code if kind == "lau" else city.fua_code
        if not code:
            raise ValueError(f"{city.id}: no {kind}_code configured")
        lau, fua = fetch_gisco(data_dir)
        gpkg, field = (lau, "GISCO_ID") if kind == "lau" else (fua, FUA_FIELD)
        geom, props = select_feature(gpkg, field, code)
        rec = write_boundary(city, kind, geom, "Eurostat GISCO", data_dir)
        return rec, (population(city, props) if kind == "lau" else None)
    if region_path is None:
        raise ValueError("osm_admin boundaries need the city's Geofabrik region file")
    (data_dir / "boundaries").mkdir(parents=True, exist_ok=True)
    gj = relation_polygon(
        region_path,
        city.osm_relation_id,
        data_dir / "boundaries" / f"{city.id}_osm_admin.raw.geojson",
    )
    geom = load_boundary_polygon(gj, 4326)
    rec = write_boundary(
        city, "osm_admin", geom, f"OSM relation {city.osm_relation_id}", data_dir, src_epsg=4326
    )
    gj.unlink()
    return rec, None
