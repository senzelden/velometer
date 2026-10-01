"""External figures: curated CSV, QECIO summary, BikeNetKit.

The QECIO fixture rows are copied from the ECF QECIO v2.10 Summary-all.csv, which is derived from
OpenStreetMap data (c) OpenStreetMap contributors, ODbL.
"""

import zipfile
from pathlib import Path

import numpy as np
import pyogrio
import pytest
import shapely
from shapely import LineString

from velometer.config import default_config_dir, load_cities
from velometer.db import create_schema, fetch_external_figures, open_db, upsert_cities
from velometer.sources import external as X

CFG = default_config_dir()
CITIES = load_cities(CFG / "cities.yaml")
FIX = Path(__file__).parent / "fixtures" / "external"


def test_curated_figures_all_validate_and_are_cited():
    figs = X.load_figures_csv(CFG / "external" / "figures.csv")
    assert {f.city_id for f in figs} <= {c.id for c in CITIES}
    for f in figs:
        assert f.source_url or "re-verify" in f.note, f
    cc = {
        (f.city_id, f.metric_name, f.network_scope): f.value
        for f in figs
        if f.source == "clean_cities_2025"
    }
    assert cc[("berlin", "protected_km", "whole_network")] == 925
    assert cc[("vienna", "protected_share_pct", "incl_traffic_calmed_restricted_access")] == 22.0


def test_qecio_rows_map_by_nuts3_and_carry_data_date():
    figs = X.qecio_figures(FIX / "qecio_summary_head.csv", CITIES)
    berlin = {f.metric_name: f.value for f in figs if f.city_id == "berlin"}
    assert berlin["main_roads_km"] == pytest.approx(2149.623)
    assert berlin["cycle_tracks_km"] == pytest.approx(679.471)
    assert all(str(f.reference_date) == "2024-01-10" for f in figs if f.city_id == "berlin")
    assert not [f for f in figs if f.city_id == "paris"]  # not in the 2-row fixture


def _write_edges(path: Path, line: LineString, crs: str = "EPSG:4326") -> None:
    pyogrio.raw.write(
        str(path),
        np.array([shapely.to_wkb(line)], dtype=object),
        [np.array([1])],
        ["osmid"],
        geometry_type="LineString",
        crs=crs,
        layer="edges",
        driver="GPKG",
    )


def _zip_gpkg(tmp_path: Path, gpkg: Path) -> None:
    with zipfile.ZipFile(tmp_path / "bike_networks.zip", "w") as z:
        z.write(gpkg, f"bike_networks/{gpkg.name}")


def test_bikenetkit_network_km_is_measured_in_city_epsg(tmp_path):
    # a gpkg "edges" layer with one 1 km line near Berlin (EPSG:4326 lon/lat)
    gpkg = tmp_path / "berlin_de.gpkg"
    _write_edges(gpkg, LineString([(13.4, 52.5), (13.4147, 52.5)]))
    _zip_gpkg(tmp_path, gpkg)
    (f,) = X.bikenetkit_figures(tmp_path, [c for c in CITIES if c.id == "berlin"])
    assert f.metric_name == "bike_network_km" and f.value == pytest.approx(1.0, abs=0.01)


def test_bikenetkit_rejects_non_wgs84_edges(tmp_path):
    gpkg = tmp_path / "berlin_de.gpkg"
    _write_edges(gpkg, LineString([(390000, 5820000), (391000, 5820000)]), "EPSG:25833")
    _zip_gpkg(tmp_path, gpkg)
    with pytest.raises(ValueError, match="EPSG:4326"):
        X.bikenetkit_figures(tmp_path, [c for c in CITIES if c.id == "berlin"])


def test_bikenetkit_missing_city_in_zip_raises(tmp_path):
    gpkg = tmp_path / "paris_fr.gpkg"
    _write_edges(gpkg, LineString([(2.3, 48.8), (2.31, 48.8)]))
    _zip_gpkg(tmp_path, gpkg)
    with pytest.raises(KeyError):
        X.bikenetkit_figures(tmp_path, [c for c in CITIES if c.id == "berlin"])


def test_load_all_replaces_per_source_and_is_idempotent(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        upsert_cities(conn, CITIES)
        first = X.load_all(conn, tmp_path / "data", CFG, qecio=False, bikenetkit=False)
        second = X.load_all(conn, tmp_path / "data", CFG, qecio=False, bikenetkit=False)
        assert first == second
        assert set(first) == {"clean_cities_2025", "official", "changing_cities"}
        assert first["clean_cities_2025"] == 18
        assert len(fetch_external_figures(conn, "berlin")) == 3 + 4


@pytest.mark.slow
def test_real_qecio_summary_has_expected_columns_and_berlin_row(tmp_path):
    from velometer.sources.download import fetch

    path = fetch(X.QECIO_URL, tmp_path / X.QECIO_LOCAL_NAME)
    berlin = {
        f.metric_name: f.value for f in X.qecio_figures(path, CITIES) if f.city_id == "berlin"
    }
    assert set(berlin) == set(X.QECIO_COLUMNS)
    assert berlin["main_roads_km"] == pytest.approx(2149.623)


def test_qecio_mapping_ignores_the_city_name_column(tmp_path):
    # QECIO names are NUTS3 unit names ("Wien", "Byen København"), so only NUTS_ID may match.
    src = (FIX / "qecio_summary_head.csv").read_text(encoding="utf-8")
    renamed = tmp_path / "renamed.csv"
    renamed.write_text(src.replace("DE,Berlin,DE300", "DE,Berlin-Brandenburg-Unit,DE300"))
    figs = X.qecio_figures(renamed, CITIES)
    assert {f.city_id for f in figs} == {"berlin"}
    assert "Berlin-Brandenburg-Unit" in figs[0].note
