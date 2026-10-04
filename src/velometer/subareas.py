"""Sub-city areas (Berlin's Bezirke): polygons assembled offline from OSM admin relations."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import shapely
from shapely.geometry.base import BaseGeometry

from velometer.config import CityConfig
from velometer.models import Subarea
from velometer.osmium import relation_polygon
from velometer.sources.boundaries import _to, _valid_polygonal, load_boundary_polygon


@dataclass(frozen=True)
class SubareaPolygon:
    subarea_id: str  # the slug
    name: str
    relation_id: int
    polygon: BaseGeometry  # city EPSG
    sha256: str  # of the written GeoJSON file


class SubareaCheckError(ValueError):
    """The subareas do not tile the city's LAU polygon within tolerance."""


def _path(city: CityConfig, data_dir: Path, slug: str) -> Path:
    return data_dir / "boundaries" / f"{city.id}_sub_{slug}.geojson"


def fetch_subareas(city: CityConfig, region_path: Path, data_dir: Path) -> list[Subarea]:
    """Assemble each configured relation from `region_path`; write its GeoJSON; return the rows.

    No check_epsg: the EPSG-zone rule is a city-level one.
    """
    if city.subareas is None:
        raise ValueError(f"no subareas configured for {city.id}")
    out_dir = data_dir / "boundaries"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for rel in city.subareas.relations:
        raw = out_dir / f"{city.id}_sub_{rel.slug}.raw.geojson"
        try:
            relation_polygon(region_path, rel.id, raw)
            geom = load_boundary_polygon(raw, city.epsg)  # repaired, city EPSG
        finally:
            raw.unlink(missing_ok=True)
        wgs = _valid_polygonal(_to(geom, city.epsg, 4326))
        out = _path(city, data_dir, rel.slug)
        feature = {
            "type": "Feature",
            "properties": {
                "city_id": city.id,
                "kind": "subarea",
                "subarea_id": rel.slug,
                "name": rel.name,
            },
            "geometry": json.loads(shapely.to_geojson(wgs)),
        }
        out.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
        rows.append(
            Subarea(
                city_id=city.id,
                subarea_id=rel.slug,
                name=rel.name,
                source=f"OSM relation {rel.id}",
                relation_id=rel.id,
                area_km2=geom.area / 1e6,
                path=str(out),
                sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
            )
        )
    return rows


def check_subareas(
    lau_polygon: BaseGeometry,
    polys: list[SubareaPolygon],
    union_tol: float = 0.01,
    overlap_tol: float = 0.001,
) -> dict[str, float]:
    """Union within `union_tol` and pairwise overlaps under `overlap_tol` of the LAU area.

    All polygons share one CRS (the city EPSG). Tolerances are fractions; the returned
    percentages are relative to the LAU area.
    """
    lau_area = lau_polygon.area
    union = shapely.union_all([p.polygon for p in polys])
    union_diff = 100 * union.symmetric_difference(lau_polygon).area / lau_area
    overlap = 0.0
    for i, a in enumerate(polys):
        for b in polys[i + 1 :]:
            overlap += a.polygon.intersection(b.polygon).area
    overlap_pct = 100 * overlap / lau_area
    problems = []
    if union_diff > union_tol * 100:
        problems.append(
            f"union differs from the LAU by {union_diff:.1f} % (limit {union_tol * 100:g} %)"
        )
    if overlap_pct > overlap_tol * 100:
        problems.append(
            f"pairwise overlap is {overlap_pct:.2f} % of the LAU (limit {overlap_tol * 100:g} %)"
        )
    if problems:
        raise SubareaCheckError("; ".join(problems))
    return {"union_diff_pct": union_diff, "overlap_pct": overlap_pct}


def load_subareas(city: CityConfig, data_dir: Path) -> list[SubareaPolygon]:
    """The written polygons of every configured subarea, in config order and the city EPSG."""
    if city.subareas is None:
        return []
    polys = []
    for rel in city.subareas.relations:
        path = _path(city, data_dir, rel.slug)
        if not path.is_file():
            raise FileNotFoundError(
                f"{city.id}: subarea {rel.slug!r} has no boundary file {path}; "
                f"run `velometer boundaries fetch --city {city.id} --subareas`"
            )
        polys.append(
            SubareaPolygon(
                subarea_id=rel.slug,
                name=rel.name,
                relation_id=rel.id,
                polygon=load_boundary_polygon(path, city.epsg),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return polys


def subarea_set_sha(polys: list[SubareaPolygon]) -> str:
    lines = sorted(f"{p.subarea_id}:{p.sha256}" for p in polys)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()
