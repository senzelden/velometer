from pyproj import Geod

from velometer.pipeline.geometry import Projector, length_km


def test_one_km_geodesic_segment_measures_one_km_in_utm():
    lon2, lat2, _ = Geod(ellps="WGS84").fwd(13.4, 52.5, 90, 1000.0)
    line = Projector(25833).line(((13.4, 52.5), (lon2, lat2)))
    assert abs(length_km(line) - 1.0) < 0.005


def test_lengths_are_not_degrees():
    line = Projector(25833).line(((13.4, 52.5), (13.5, 52.5)))
    assert 6.0 < length_km(line) < 7.5  # 0.1° lon at 52.5°N ≈ 6.8 km, not 0.1
