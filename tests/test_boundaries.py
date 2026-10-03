import json

import numpy as np
import pyogrio
import pytest
import shapely
from shapely import MultiPolygon, Polygon
from shapely.geometry import box

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


def _spiked(x, y, d=10.0):
    """A square with a zero-width spike: invalid, make_valid splits off a LineString."""
    return Polygon(
        [(x, y), (x + d, y), (x + d, y + d), (x + d, y + 1.5 * d), (x + d, y + d), (x, y + d)]
    )


def test_invalid_multipolygon_keeps_every_part_after_repair():
    # make_valid -> GeometryCollection(MultiPolygon, LineString)
    mp = MultiPolygon([_spiked(0, 0), _sq(20, 0, 10)])
    assert not mp.is_valid
    fixed = b._valid_polygonal(mp)
    assert fixed.is_valid and fixed.geom_type == "MultiPolygon"
    assert fixed.area == pytest.approx(shapely.make_valid(mp).area)


def test_collection_with_nested_multipolygon_keeps_the_islands():
    # make_valid -> GeometryCollection(GeometryCollection(Polygon, LineString), MultiPolygon)
    gc = shapely.GeometryCollection([_spiked(0, 0), MultiPolygon([_sq(20, 0, 10), _sq(40, 0, 1)])])
    assert not gc.is_valid
    fixed = b._valid_polygonal(gc)
    assert fixed.is_valid and fixed.geom_type == "MultiPolygon"
    assert fixed.area == pytest.approx(shapely.make_valid(gc).area)


FALLBACK = CITY.model_copy(update={"population_nuts3": "DE300"})


def test_population_uses_lau_value_else_nuts3_fallback():
    pop = b.population(CITY, {"POP_2024": 3782202}, fetch_json=lambda url: pytest.fail("net"))
    assert (pop.value, pop.year, pop.source) == (3782202, 2024, "GISCO LAU 2024 POP_2024")
    paris = CITY.model_copy(
        update={"id": "paris", "nuts3_code": "FR101", "population_nuts3": "FR101"}
    )
    payload = {"value": {"0": 2084894}}
    pop = b.population(paris, {"POP_2024": 0}, fetch_json=lambda url: payload)
    assert pop.value == 2084894 and "demo_r_pjangrp3" in pop.source and pop.year == 2024


def test_population_nan_or_nonpositive_lau_falls_back_to_nuts3():
    payload = {"value": {"0": 2084894}}
    for bad in (float("nan"), 0.0, -5, None):
        pop = b.population(FALLBACK, {"POP_2024": bad}, fetch_json=lambda url: payload)
        assert pop.value == 2084894 and "demo_r_pjangrp3" in pop.source


def test_population_eurostat_anomaly_fails_loudly_and_missing_nuts3_is_none():
    for payload in ({"value": {}}, {"value": {"0": 0}}, {}):
        with pytest.raises(ValueError, match=r"demo_r_pjangrp3.*DE300"):
            b.population(FALLBACK, {"POP_2024": 0}, fetch_json=lambda url, p=payload: p)
    no_nuts = CITY.model_copy(update={"nuts3_code": None})
    assert b.population(no_nuts, {"POP_2024": 0}, fetch_json=lambda url: pytest.fail("net")) is None


def test_population_fallback_ignores_the_qecio_nuts3_code():
    # nuts3_code serves QECIO matching; a NUTS3 unit that is not the commune (Copenhagen's
    # DK011) must never stand in for the commune's population (spec section 2.7).
    copenhagen = CITY.model_copy(update={"id": "copenhagen", "nuts3_code": "DK011"})
    assert copenhagen.population_nuts3 is None
    got = b.population(copenhagen, {"POP_2024": 0}, fetch_json=lambda url: pytest.fail("net"))
    assert got is None


def test_population_model_rejects_nonpositive():
    from pydantic import ValidationError

    from velometer.models import Population

    with pytest.raises(ValidationError):
        Population(value=0, year=2024, source="x")


def test_load_boundary_polygon_keeps_multipolygon_parts(tmp_path):
    mp = MultiPolygon([_sq(4.5e6, 3.27e6), _sq(4.51e6, 3.27e6)])
    rec = b.write_boundary(CITY, "lau", mp, "GISCO", tmp_path)
    loaded = b.load_boundary_polygon(rec.geojson_path, CITY.epsg)
    assert loaded.geom_type == "MultiPolygon" and len(loaded.geoms) == 2
    assert loaded.area == pytest.approx(rec.polygon.area, rel=1e-6)


def _stub_gisco(monkeypatch, tmp_path, lau_code="DE_11000000", pop=5):
    lau = _gpkg(tmp_path / "lau.gpkg", [(lau_code, MultiPolygon([_sq(4.5e6, 3.27e6)]), pop)])
    fua = tmp_path / "fua.gpkg"
    geoms = np.array([shapely.to_wkb(MultiPolygon([_sq(4.5e6, 3.27e6, 3000)]))], dtype=object)
    pyogrio.raw.write(
        str(fua),
        geoms,
        [np.array(["DE001F"], dtype=object)],
        [b.FUA_FIELD],
        geometry_type="MultiPolygon",
        crs="EPSG:3035",
        driver="GPKG",
    )
    monkeypatch.setattr(b, "fetch_gisco", lambda d: (lau, fua))


def test_city_boundary_lau_and_fua(tmp_path, monkeypatch):
    _stub_gisco(monkeypatch, tmp_path)
    data = tmp_path / "fresh"
    rec, pop = b.city_boundary(CITY, "lau", data)
    assert rec.boundary.kind == "lau" and pop.value == 5
    rec, pop = b.city_boundary(CITY, "fua", data)
    assert rec.boundary.kind == "fua" and pop is None
    assert rec.boundary.area_km2 == pytest.approx(9.0, rel=0.02)


def test_city_boundary_missing_code_fails_before_download(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "fetch_gisco", lambda d: pytest.fail("download"))
    no_fua = CITY.model_copy(update={"fua_code": None})
    with pytest.raises(ValueError, match="fua_code"):
        b.city_boundary(no_fua, "fua", tmp_path)


def test_city_boundary_osm_admin_on_fresh_data_dir(tmp_path, monkeypatch):
    def fake_relation_polygon(src, relation_id, dst):
        assert dst.parent.is_dir(), "boundaries dir must exist before relation_polygon"
        wgs = b._to(_sq(4.5e6, 3.27e6), 3035, 4326)
        dst.write_text(
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
        return dst

    monkeypatch.setattr(b, "relation_polygon", fake_relation_polygon)
    rec, pop = b.city_boundary(
        CITY, "osm_admin", tmp_path / "fresh", region_path=tmp_path / "r.pbf"
    )
    assert pop is None and rec.boundary.kind == "osm_admin"
    assert rec.boundary.area_km2 == pytest.approx(1.0, rel=0.02)
    assert not (tmp_path / "fresh" / "boundaries" / "berlin_osm_admin.raw.geojson").exists()


@pytest.mark.slow
def test_every_pilot_city_code_selects_exactly_one_feature(tmp_path_factory):
    """Network: download GISCO once; assert the rule that each configured code is unique."""
    from velometer.config import default_config_dir, load_cities

    data = tmp_path_factory.mktemp("data")
    lau, fua = b.fetch_gisco(data)
    for city in load_cities(default_config_dir() / "cities.yaml"):
        b.select_feature(lau, "GISCO_ID", city.lau_code)
        b.select_feature(fua, b.FUA_FIELD, city.fua_code)


URAU_JSON = {  # the shape of the Eurostat JSON-stat response (dimension time, values by index)
    "value": {"0": 515695.0, "2": 522250.0},
    "dimension": {"time": {"category": {"index": {"2021": 0, "2022": 1, "2023": 2}}}},
}


def test_population_falls_back_to_urban_audit_latest_year():
    city = CITY.model_copy(update={"population_urau": "FR003C", "population_nuts3": None})
    pop = b.population(city, {"POP_2024": 0}, fetch_json=lambda url: URAU_JSON)
    assert (pop.value, pop.year) == (522250, 2023)
    assert "urb_cpop1 FR003C" in pop.source


def test_urau_request_names_the_city_and_indicator():
    seen = []
    city = CITY.model_copy(update={"population_urau": "FR003C"})
    b.population(city, {}, fetch_json=lambda url: seen.append(url) or URAU_JSON)
    assert "cities=FR003C" in seen[0] and "indic_ur=DE1001V" in seen[0]


def test_urau_without_positive_value_or_with_extra_dimension_fails_loudly():
    city = CITY.model_copy(update={"population_urau": "FR003C"})
    empty = {**URAU_JSON, "value": {"1": 0}}
    with pytest.raises(ValueError, match="urb_cpop1 FR003C"):
        b.population(city, {}, fetch_json=lambda url: empty)
    extra = {
        **URAU_JSON,
        "dimension": {
            **URAU_JSON["dimension"],
            "cities": {"category": {"index": {"FR003C": 0, "FR001C": 1}}},
        },
    }
    with pytest.raises(ValueError, match="extra dimension"):
        b.population(city, {}, fetch_json=lambda url: extra)


def test_population_nuts3_wins_over_urau():
    city = CITY.model_copy(update={"population_urau": "FR003C", "population_nuts3": "DE300"})
    urls = []

    def fake(url):
        urls.append(url)
        if "urb_cpop1" in url:
            pytest.fail("urb_cpop1 must not be called")
        return {"value": {"0": 2084894}}

    pop = b.population(city, {"POP_2024": 0}, fetch_json=fake)
    assert pop.value == 2084894 and "demo_r_pjangrp3" in pop.source and len(urls) == 1


def test_utm_epsg_rule():
    assert b.utm_epsg(13.4) == 25833 and b.utm_epsg(2.35) == 25831 and b.utm_epsg(24.9) == 25835


def test_lau_with_wrong_epsg_is_refused(tmp_path):
    city = CITY.model_copy(update={"epsg": 25832})  # Berlin is 25833
    with pytest.raises(ValueError, match="EPSG 25832.*UTM zone.*25833"):
        b.check_epsg(city, box(13.3, 52.4, 13.5, 52.6))
    with pytest.raises(ValueError, match="EPSG 25832"):  # write_boundary applies it to lau
        b.write_boundary(city, "lau", MultiPolygon([_sq(4.5e6, 3.27e6)]), "GISCO", tmp_path)
    # a FUA may straddle zones: not checked
    b.write_boundary(city, "fua", MultiPolygon([_sq(4.5e6, 3.27e6)]), "GISCO", tmp_path)


def test_osm_relation_admin_boundary_keeps_kind_lau(tmp_path, monkeypatch):
    _stub_gisco(monkeypatch, tmp_path, pop=3782202)
    seen = {}

    def fake_relation_polygon(src, relation_id, dst):
        seen["relation"] = relation_id
        wgs = b._to(_sq(4.5e6, 3.27e6, 2000), 3035, 4326)
        feat = {
            "type": "Feature",
            "properties": {},
            "geometry": json.loads(shapely.to_geojson(wgs)),
        }
        dst.write_text(json.dumps({"type": "FeatureCollection", "features": [feat]}))
        return dst

    monkeypatch.setattr(b, "relation_polygon", fake_relation_polygon)
    city = CITY.model_copy(update={"admin_boundary": "osm_relation"})
    rec, pop = b.city_boundary(city, "lau", tmp_path / "d", region_path=tmp_path / "r.pbf")
    assert seen["relation"] == 62422
    assert rec.boundary.kind == "lau" and rec.boundary.source == "OSM relation 62422"
    assert rec.boundary.area_km2 == pytest.approx(4.0, rel=0.02)  # not the 1 km2 GISCO polygon
    assert pop.value == 3782202
    with pytest.raises(ValueError, match="region file"):
        b.city_boundary(city, "lau", tmp_path / "d")


@pytest.mark.slow
def test_urb_cpop1_live_lyon():
    city = CITY.model_copy(update={"population_urau": "FR003C", "population_nuts3": None})
    pop = b.population(city, {"POP_2024": 0})
    assert 400_000 < pop.value < 700_000


def test_epsg_exception_accepts_only_the_adjacent_zone():
    poly = box(13.3, 52.4, 13.5, 52.6)  # zone 25833
    adjacent = CITY.model_copy(update={"epsg": 25832, "epsg_exception": "national standard"})
    b.check_epsg(adjacent, poly)
    two_away = CITY.model_copy(update={"epsg": 25831, "epsg_exception": "national standard"})
    with pytest.raises(ValueError, match="EPSG 25831"):
        b.check_epsg(two_away, poly)
