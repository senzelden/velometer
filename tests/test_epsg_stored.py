"""Spec section 5.3: the boundaries stored on disk lie in each city's configured UTM zone.

Reads `data/boundaries` read-only (ruling P1) and skips where the checkout has none.
"""

from pathlib import Path

import pytest

from velometer.config import default_config_dir, load_cities
from velometer.sources.boundaries import check_epsg, load_boundary_polygon

BOUNDARIES = Path(__file__).resolve().parents[1] / "data" / "boundaries"
CITIES = {c.id: c for c in load_cities(default_config_dir() / "cities.yaml")}


def test_stored_admin_boundaries_pass_the_epsg_check():
    files = sorted(BOUNDARIES.glob("*_lau.geojson")) if BOUNDARIES.is_dir() else []
    if not files:
        pytest.skip("no data/boundaries in this checkout")
    for path in files:
        city = CITIES[path.name.removesuffix("_lau.geojson")]
        wgs = load_boundary_polygon(path, 4326)  # the stored file is EPSG:4326
        check_epsg(city, wgs)  # applies the city's epsg_exception, as write_boundary does
