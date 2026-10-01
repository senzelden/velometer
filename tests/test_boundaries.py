import json

import numpy as np
import pyogrio
import pytest
import shapely
from shapely import MultiPolygon, Polygon

from velometer.config import CityConfig
from velometer.sources import boundaries as b

CITY = CityConfig(
    id="berlin",
    name="Berlin",
    country_iso2="DE",
    epsg=25833,
    geofabrik_region="europe/germany/berlin",
    osm_relation_id=62422,
    lau_code="DE_11000000",
    fua_code="DE001F",
    nuts3_code="DE300",
)


def _gpkg(path, rows):
    """rows: list of (code, geometry_in_3035, pop)."""
    geoms = np.array([shapely.to_wkb(g) for _, g, _ in rows], dtype=object)
    fields = [
        np.array([c for c, _, _ in rows], dtype=object),
        np.array([p for _, _, p in rows], dtype=np.int64),
    ]
    pyogrio.raw.write(
        str(path),
        geoms,
        fields,
        ["GISCO_ID", "POP_2024"],
        geometry_type="MultiPolygon",
        crs="EPSG:3035",
        driver="GPKG",
    )
    return path


def _sq(x, y, d=1000):
    return Polygon([(x, y), (x + d, y), (x + d, y + d), (x, y + d)])


def test_select_feature_requires_exactly_one(tmp_path):
    g = _gpkg(
        tmp_path / "l.gpkg",
        [
            ("DE_11000000", MultiPolygon([_sq(4.5e6, 3.27e6)]), 5),
            ("DE_X", MultiPolygon([_sq(4.6e6, 3.27e6)]), 1),
            ("DE_DUP", MultiPolygon([_sq(4.7e6, 3.27e6)]), 1),
            ("DE_DUP", MultiPolygon([_sq(4.8e6, 3.27e6)]), 1),
        ],
    )
    geom, props = b.select_feature(g, "GISCO_ID", "DE_11000000")
    assert props["POP_2024"] == 5 and geom.area == pytest.approx(1e6)
    with pytest.raises(ValueError, match="0 features"):
        b.select_feature(g, "GISCO_ID", "nope")
    with pytest.raises(ValueError, match="2 features"):
        b.select_feature(g, "GISCO_ID", "DE_DUP")


def test_boundary_geojson_keeps_all_parts(tmp_path):
    mp = MultiPolygon([_sq(4.5e6, 3.27e6), _sq(4.51e6, 3.27e6)])
    rec = b.write_boundary(CITY, "lau", mp, "GISCO", tmp_path)
    gj = json.loads(rec.geojson_path.read_text())
    assert gj["features"][0]["geometry"]["type"] == "MultiPolygon"
    assert len(gj["features"][0]["geometry"]["coordinates"]) == 2
    assert rec.boundary.area_km2 == pytest.approx(2.0, rel=0.02)  # in the city EPSG
    assert rec.polygon.area == pytest.approx(2e6, rel=0.02)
    assert len(rec.boundary.sha256) == 64


def test_bowtie_boundary_is_made_valid_on_write_and_load(tmp_path):
    bowtie = Polygon(
        [
            (4.5e6, 3.27e6),
            (4.5e6 + 2000, 3.27e6 + 2000),
            (4.5e6 + 2000, 3.27e6),
            (4.5e6, 3.27e6 + 2000),
        ]
    )
    assert not bowtie.is_valid
    rec = b.write_boundary(CITY, "lau", bowtie, "GISCO", tmp_path)
    assert rec.polygon.is_valid and rec.polygon.area > 0
    assert rec.polygon.geom_type in ("Polygon", "MultiPolygon")
    loaded = b.load_boundary_polygon(rec.geojson_path, CITY.epsg)
    assert loaded.is_valid and loaded.area == pytest.approx(rec.polygon.area, rel=1e-6)
    # a hand-written invalid GeoJSON is repaired on load as well
    wgs = b._to(bowtie, 3035, 4326)
    raw = tmp_path / "raw.geojson"
    raw.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": json.loads(shapely.to_geojson(wgs)),
                    }
                ],
            }
        )
    )
    assert b.load_boundary_polygon(raw, CITY.epsg).is_valid


def test_population_uses_lau_value_else_nuts3_fallback():
    pop = b.population(CITY, {"POP_2024": 3782202}, fetch_json=lambda url: pytest.fail("net"))
    assert (pop.value, pop.year, pop.source) == (3782202, 2024, "GISCO LAU 2024 POP_2024")
    paris = CITY.model_copy(update={"id": "paris", "nuts3_code": "FR101"})
    payload = {"value": {"0": 2084894}}
    pop = b.population(paris, {"POP_2024": 0}, fetch_json=lambda url: payload)
    assert pop.value == 2084894 and "demo_r_pjangrp3" in pop.source and pop.year == 2024


@pytest.mark.slow
def test_every_pilot_city_code_selects_exactly_one_feature(tmp_path_factory):
    """Network: download GISCO once; assert the rule that each configured code is unique."""
    from velometer.config import default_config_dir, load_cities

    data = tmp_path_factory.mktemp("data")
    lau, fua = b.fetch_gisco(data)
    for city in load_cities(default_config_dir() / "cities.yaml"):
        b.select_feature(lau, "GISCO_ID", city.lau_code)
        b.select_feature(fua, b.FUA_FIELD, city.fua_code)
