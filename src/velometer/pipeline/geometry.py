"""Projection to a city's metric CRS and length helpers (never measure in degrees)."""

import pyproj
from pyproj import Transformer
from shapely import LineString
from shapely.ops import transform


def require_projected(epsg: int) -> int:
    """Return `epsg` if it names a projected CRS; raise ValueError otherwise (CLAUDE.md rule)."""
    try:
        crs = pyproj.CRS.from_epsg(epsg)
    except pyproj.exceptions.CRSError as e:
        raise ValueError(f"EPSG:{epsg} is not a projected CRS (unknown code: {e})") from e
    if not crs.is_projected:
        raise ValueError(f"EPSG:{epsg} is not a projected CRS ({crs.name}); lengths need metres")
    return epsg


class Projector:
    def __init__(self, epsg: int) -> None:
        self.epsg = require_projected(epsg)
        self._tf = Transformer.from_crs(4326, epsg, always_xy=True)
        self._cache: dict[tuple, LineString] = {}

    def line(self, coords: tuple[tuple[float, float], ...]) -> LineString:
        hit = self._cache.get(coords)
        if hit is None:
            hit = transform(self._tf.transform, LineString(coords))
            self._cache[coords] = hit
        return hit


def length_km(line: LineString) -> float:
    return line.length / 1000.0
