import json
from pathlib import Path

import pytest
import shapely
from shapely.geometry import box

from velometer import subareas as S
from velometer.config import CityConfig, SubareaRelation, SubareasConfig
from velometer.sources.boundaries import _to

X0, Y0 = 390_000.0, 5_820_000.0  # EPSG 25833, near Berlin
SIDE = 10_000.0  # a 100 km2 square LAU


def _lau():
    return box(X0, Y0, X0 + SIDE, Y0 + SIDE)


def _poly(slug: str, geom, sha: str = "x") -> S.SubareaPolygon:
    return S.SubareaPolygon(slug, slug.upper(), 1, geom, sha)


def _halves(gap: float = 0.0, overlap: float = 0.0):
    """Two vertical halves of the LAU; `gap`/`overlap` are fractions of the LAU width."""
    mid = X0 + SIDE / 2
    left = box(X0, Y0, mid - gap * SIDE / 2 + overlap * SIDE / 2, Y0 + SIDE)
    right = box(mid + gap * SIDE / 2 - overlap * SIDE / 2, Y0, X0 + SIDE, Y0 + SIDE)
    return [_poly("a", left), _poly("b", right)]


def test_exact_halves_pass_with_zero_percentages():
    assert S.check_subareas(_lau(), _halves()) == {"union_diff_pct": 0.0, "overlap_pct": 0.0}


def test_a_two_percent_gap_raises_with_the_measured_value():
    with pytest.raises(S.SubareaCheckError, match=r"2\.0"):
        S.check_subareas(_lau(), _halves(gap=0.02))


def test_a_half_percent_overlap_raises():
    with pytest.raises(S.SubareaCheckError, match="overlap"):
        S.check_subareas(_lau(), _halves(overlap=0.005))


def test_a_gap_within_tolerance_passes_and_reports_it():
    got = S.check_subareas(_lau(), _halves(gap=0.005))
    assert got["union_diff_pct"] == pytest.approx(0.5) and got["overlap_pct"] == 0.0


def test_a_union_spilling_outside_the_lau_counts_as_a_difference():
    wide = box(X0, Y0, X0 + SIDE * 1.03, Y0 + SIDE)
    with pytest.raises(S.SubareaCheckError, match=r"3\.0"):
        S.check_subareas(_lau(), [_poly("a", wide)])


def _city(slugs=("a", "b")) -> CityConfig:
    return CityConfig(
        id="berlin",
        name="Berlin",
        country_iso2="DE",
        epsg=25833,
        geofabrik_region="europe/germany/berlin",
        osm_relation_id=62422,
        subareas=SubareasConfig(
            source="osm_admin",
            admin_level=9,
            relations=[
                SubareaRelation(id=100 + i, name=s.upper(), slug=s) for i, s in enumerate(slugs)
            ],
        ),
    )


def _write_files(data_dir: Path, city: CityConfig, polys: list[S.SubareaPolygon]) -> None:
    b = data_dir / "boundaries"
    b.mkdir(parents=True, exist_ok=True)
    for p in polys:
        wgs = _to(p.polygon, city.epsg, 4326)
        feat = {
            "type": "Feature",
            "properties": {},
            "geometry": json.loads(shapely.to_geojson(wgs)),
        }
        (b / f"{city.id}_sub_{p.subarea_id}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": [feat]})
        )


def test_load_subareas_round_trips_polygons_in_the_city_epsg(tmp_path):
    city = _city()
    _write_files(tmp_path, city, _halves())
    loaded = S.load_subareas(city, tmp_path)
    assert [p.subarea_id for p in loaded] == ["a", "b"]
    assert [p.relation_id for p in loaded] == [100, 101]
    assert loaded[0].polygon.area == pytest.approx(SIDE * SIDE / 2, rel=1e-6)
    assert S.check_subareas(_lau(), loaded)["union_diff_pct"] == pytest.approx(0.0, abs=1e-6)


def test_load_subareas_names_the_missing_slug(tmp_path):
    city = _city()
    _write_files(tmp_path, city, _halves())
    (tmp_path / "boundaries" / "berlin_sub_b.geojson").unlink()
    with pytest.raises(FileNotFoundError, match="'b'"):
        S.load_subareas(city, tmp_path)


def test_load_subareas_of_a_city_without_subareas_is_empty(tmp_path):
    plain = _city().model_copy(update={"subareas": None})
    assert S.load_subareas(plain, tmp_path) == []


def test_subarea_set_sha_is_order_independent_and_tracks_file_changes():
    a, b = _poly("a", _lau(), "h1"), _poly("b", _lau(), "h2")
    assert S.subarea_set_sha([a, b]) == S.subarea_set_sha([b, a])
    changed = _poly("b", _lau(), "h3")
    assert S.subarea_set_sha([a, b]) != S.subarea_set_sha([a, changed])


def test_subarea_set_sha_follows_a_changed_file_on_disk(tmp_path):
    city = _city()
    _write_files(tmp_path, city, _halves())
    before = S.subarea_set_sha(S.load_subareas(city, tmp_path))
    _write_files(tmp_path, city, _halves(gap=0.01))
    assert S.subarea_set_sha(S.load_subareas(city, tmp_path)) != before


def test_fetch_subareas_writes_files_and_returns_rows(tmp_path, monkeypatch):
    city = _city()
    halves = {100: _halves()[0], 101: _halves()[1]}
    seen = []

    def fake_relation_polygon(src, relation_id, dst):
        seen.append((src, relation_id))
        wgs = _to(halves[relation_id].polygon, 25833, 4326)
        feat = {
            "type": "Feature",
            "properties": {},
            "geometry": json.loads(shapely.to_geojson(wgs)),
        }
        dst.write_text(json.dumps({"type": "FeatureCollection", "features": [feat]}))
        return dst

    monkeypatch.setattr(S, "relation_polygon", fake_relation_polygon)
    region = tmp_path / "berlin.osm.pbf"
    rows = S.fetch_subareas(city, region, tmp_path)
    assert seen == [(region, 100), (region, 101)]
    assert [r.subarea_id for r in rows] == ["a", "b"]
    assert rows[0].source == "OSM relation 100" and rows[0].relation_id == 100
    assert rows[0].area_km2 == pytest.approx(50.0, rel=1e-6)
    out = tmp_path / "boundaries" / "berlin_sub_a.geojson"
    assert rows[0].path == str(out)
    feature = json.loads(out.read_text())["features"][0]
    assert feature["properties"] == {
        "city_id": "berlin",
        "kind": "subarea",
        "subarea_id": "a",
        "name": "A",
    }
    import hashlib

    assert rows[0].sha256 == hashlib.sha256(out.read_bytes()).hexdigest()
    assert not list((tmp_path / "boundaries").glob("*.raw.geojson"))


def test_fetch_subareas_without_config_raises(tmp_path):
    plain = _city().model_copy(update={"subareas": None})
    with pytest.raises(ValueError, match="no subareas configured for berlin"):
        S.fetch_subareas(plain, tmp_path / "r.pbf", tmp_path)
