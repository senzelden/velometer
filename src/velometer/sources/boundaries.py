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
EUROSTAT_URAU = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_cpop1"
    "?format=JSON&lang=EN&cities={code}&indic_ur=DE1001V"
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


def _polygons(geom: BaseGeometry) -> list[BaseGeometry]:
    """Every non-empty Polygon in `geom`, unpacking multi-part types and nested collections."""
    if geom.geom_type == "Polygon":
        return [] if geom.is_empty else [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for part in shapely.get_parts(geom) for p in _polygons(part)]
    return []


def _valid_polygonal(geom: BaseGeometry) -> BaseGeometry:
    """Repair an invalid geometry, keeping all of its polygonal parts (islands included)."""
    if geom.is_valid and geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = _polygons(shapely.make_valid(geom))
    if not parts:
        raise ValueError(f"geometry has no polygonal part after make_valid: {geom.wkt[:80]}")
    return parts[0] if len(parts) == 1 else shapely.MultiPolygon(parts)


def utm_epsg(lon: float) -> int:
    """ETRS89 / UTM zone EPSG code (25828-25838 in Europe) for a longitude."""
    return 25800 + math.floor((lon + 180) / 6) + 1


def check_epsg(city: CityConfig, polygon_4326: BaseGeometry) -> None:
    """Refuse a city whose configured EPSG is not the UTM zone of its boundary's centroid."""
    expected = utm_epsg(polygon_4326.centroid.x)
    if expected != city.epsg:
        raise ValueError(
            f"{city.id}: configured EPSG {city.epsg} but the boundary centroid lies in "
            f"UTM zone EPSG {expected}"
        )


def write_boundary(
    city: CityConfig,
    kind: str,
    geom_3035: BaseGeometry,
    source: str,
    data_dir: Path,
    src_epsg: int = 3035,
    source_version: str | None = None,
) -> BoundaryRecord:
    geom = _valid_polygonal(geom_3035)
    wgs = _valid_polygonal(_to(geom, src_epsg, 4326))
    if kind == "lau":  # the admin layer (GISCO or OSM relation); a FUA may straddle zones
        check_epsg(city, wgs)
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
        source_version=source_version or GISCO_VERSION.get(kind, "OSM admin relation"),
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
    # Only a NUTS3 unit identical to the commune may stand in (spec section 2.7); nuts3_code is
    # for QECIO matching and can be larger (Copenhagen DK011).
    nuts3 = city.population_nuts3
    if not nuts3:
        return _population_urau(city, fetch_json)
    dataset = f"demo_r_pjangrp3 {nuts3}"
    data = (fetch_json or _get_json)(EUROSTAT_POP.format(nuts3=nuts3))
    values = list((data.get("value") or {}).values())
    if not values or not values[0] or values[0] <= 0:
        raise ValueError(f"Eurostat {dataset} 2024: no positive population in response")
    return Population(value=int(values[0]), year=2024, source=f"Eurostat {dataset} 2024")


def _population_urau(
    city: CityConfig, fetch_json: Callable[[str], dict] | None
) -> Population | None:
    code = city.population_urau
    if not code:
        return None
    dataset = f"urb_cpop1 {code}"
    data = (fetch_json or _get_json)(EUROSTAT_URAU.format(code=code))
    dims = data.get("dimension") or {}
    for name, dim in dims.items():
        if name != "time" and len((dim.get("category") or {}).get("index") or {}) > 1:
            raise ValueError(f"Eurostat {dataset}: unexpected extra dimension {name!r}")
    years = ((dims.get("time") or {}).get("category") or {}).get("index") or {}
    values = data.get("value") or {}
    positive = [
        int(year)
        for year, idx in years.items()
        if (v := values.get(str(idx))) is not None and v > 0
    ]
    if not positive:
        raise ValueError(f"Eurostat {dataset}: no positive population in response")
    year = max(positive)
    return Population(
        value=int(values[str(years[str(year)])]), year=year, source=f"Eurostat {dataset} {year}"
    )


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
        if kind == "lau" and city.admin_boundary == "osm_relation":
            if region_path is None:
                raise ValueError("an osm_relation admin boundary needs the Geofabrik region file")
            rec = _osm_relation_boundary(city, "lau", region_path, data_dir)
            return rec, population(city, props)
        rec = write_boundary(city, kind, geom, "Eurostat GISCO", data_dir)
        return rec, (population(city, props) if kind == "lau" else None)
    if region_path is None:
        raise ValueError("osm_admin boundaries need the city's Geofabrik region file")
    return _osm_relation_boundary(city, "osm_admin", region_path, data_dir), None


def _osm_relation_boundary(
    city: CityConfig, kind: str, region_path: Path, data_dir: Path
) -> BoundaryRecord:
    (data_dir / "boundaries").mkdir(parents=True, exist_ok=True)
    gj = relation_polygon(
        region_path,
        city.osm_relation_id,
        data_dir / "boundaries" / f"{city.id}_{kind}.raw.geojson",
    )
    geom = load_boundary_polygon(gj, 4326)
    rec = write_boundary(
        city,
        kind,
        geom,
        f"OSM relation {city.osm_relation_id}",
        data_dir,
        src_epsg=4326,
        source_version="OSM admin relation",
    )
    gj.unlink()
    return rec
