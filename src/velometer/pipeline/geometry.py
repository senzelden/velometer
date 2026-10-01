"""Projection to a city's metric CRS and length helpers (never measure in degrees)."""

from pyproj import Transformer
from shapely import LineString
from shapely.ops import transform


class Projector:
    def __init__(self, epsg: int) -> None:
        self.epsg = epsg
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
