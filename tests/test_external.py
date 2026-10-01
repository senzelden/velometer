"""External figures: curated CSV, QECIO summary, BikeNetKit.

The QECIO fixture rows are copied from the ECF QECIO v2.10 Summary-all.csv, which is derived from
OpenStreetMap data (c) OpenStreetMap contributors, ODbL.
"""

import os
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyogrio
import pytest
import shapely
from shapely import LineString

from velometer.config import default_config_dir, load_cities
from velometer.db import create_schema, fetch_external_figures, open_db, upsert_cities
from velometer.sources import external as X
from velometer.sources.download import DownloadError, md5_of

CFG = default_config_dir()
CITIES = load_cities(CFG / "cities.yaml")
FIX = Path(__file__).parent / "fixtures" / "external"
BERLIN = [c for c in CITIES if c.id == "berlin"]
CURATED = CFG / "external" / "figures.csv"


def _qecio_all_cities(path: Path) -> Path:
    """The fixture's Berlin row once per pilot city NUTS3 code (one row per configured code)."""
    head, berlin = (FIX / "qecio_summary_head.csv").read_text(encoding="utf-8").splitlines()[:2]
    rows = [berlin.replace(",DE300,", f",{c.nuts3_code},") for c in CITIES]
    path.write_text("\n".join([head, *rows]) + "\n", encoding="utf-8")
    return path


def test_curated_figures_all_validate_and_are_cited():
    figs = X.load_figures_csv(CURATED)
    assert {f.city_id for f in figs} <= {c.id for c in CITIES}
    for f in figs:
        assert f.source_url or "re-verify" in f.note, f


def test_curated_clean_cities_rows_follow_the_rules():
    figs = [f for f in X.load_figures_csv(CURATED) if f.source == "clean_cities_2025"]
    keys = [(f.city_id, f.source, f.metric_name, f.network_scope) for f in figs]
    assert len(keys) == len(set(keys))  # each (city, source, metric, scope) appears once
    metrics = {"protected_km", "network_km", "protected_share_pct"}
    for city in {f.city_id for f in figs}:
        assert {f.metric_name for f in figs if f.city_id == city} == metrics, city
    vienna_scopes = {f.network_scope for f in figs if f.city_id == "vienna"}
    assert vienna_scopes == {"whole_network", "incl_traffic_calmed_restricted_access"}


def test_qecio_rows_map_by_nuts3_and_carry_data_date():
    figs = X.qecio_figures(FIX / "qecio_summary_head.csv", BERLIN)
    berlin = {f.metric_name: f.value for f in figs if f.city_id == "berlin"}
    assert berlin["main_roads_km"] == pytest.approx(2149.623)
    assert berlin["cycle_tracks_km"] == pytest.approx(679.471)
    assert all(str(f.reference_date) == "2024-01-10" for f in figs if f.city_id == "berlin")


def test_qecio_nuts3_code_matching_no_row_raises():
    # Paris FR101 is not in the 2-row fixture: a typo or a missing row must not pass silently
    with pytest.raises(ValueError, match=r"FR101 \(paris\) matched 0"):
        X.qecio_figures(FIX / "qecio_summary_head.csv", CITIES)


def test_qecio_nuts3_code_matching_two_rows_raises(tmp_path):
    src = (FIX / "qecio_summary_head.csv").read_text(encoding="utf-8")
    dup = tmp_path / "dup.csv"
    dup.write_text(src.replace(",Berat,AL031,", ",Berlin,DE300,"), encoding="utf-8")
    with pytest.raises(ValueError, match=r"DE300 \(berlin\) matched 2"):
        X.qecio_figures(dup, BERLIN)


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


def _all_rows(conn) -> list[tuple]:
    return conn.execute(
        "SELECT city_id, source, metric_name, value, network_scope FROM external_figures "
        "ORDER BY city_id, source, metric_name, network_scope, value"
    ).fetchall()


def test_load_all_replaces_per_source_and_is_idempotent(tmp_path):
    curated = X.load_figures_csv(CURATED)
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        upsert_cities(conn, CITIES)
        first = X.load_all(conn, tmp_path / "data", CFG, qecio=False, bikenetkit=False)
        rows = _all_rows(conn)
        second = X.load_all(conn, tmp_path / "data", CFG, qecio=False, bikenetkit=False)
        assert first == second and _all_rows(conn) == rows
        assert first == dict(Counter(f.source for f in curated))
        assert len(rows) == len(curated)


@pytest.mark.slow
def test_real_qecio_summary_selects_exactly_one_row_per_pilot_city(tmp_path):
    from velometer.sources.download import fetch

    path = fetch(X.QECIO_URL, tmp_path / X.QECIO_LOCAL_NAME)
    figs = X.qecio_figures(path, CITIES)  # raises unless each nuts3_code matches one row
    for city in CITIES:
        got = [f for f in figs if f.city_id == city.id]
        assert {f.metric_name for f in got} == set(X.QECIO_COLUMNS), city.id
        assert len(got) == len(X.QECIO_COLUMNS), city.id
        assert all(f.network_scope == f"nuts3_{city.nuts3_code}" for f in got)


def test_qecio_mapping_ignores_the_city_name_column(tmp_path):
    # QECIO names are NUTS3 unit names ("Wien", "Byen København"), so only NUTS_ID may match.
    src = (FIX / "qecio_summary_head.csv").read_text(encoding="utf-8")
    renamed = tmp_path / "renamed.csv"
    renamed.write_text(src.replace("DE,Berlin,DE300", "DE,Berlin-Brandenburg-Unit,DE300"))
    figs = X.qecio_figures(renamed, BERLIN)
    assert {f.city_id for f in figs} == {"berlin"}
    assert "Berlin-Brandenburg-Unit" in figs[0].note


def _qecio_copy(tmp_path: Path, mtime: float | None = None) -> Path:
    p = tmp_path / "q.csv"
    p.write_bytes((FIX / "qecio_summary_head.csv").read_bytes())
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def test_qecio_retrieved_at_is_file_mtime_utc_date(tmp_path):
    p = _qecio_copy(tmp_path, datetime(2026, 3, 4, 23, 30, tzinfo=UTC).timestamp())
    figs = X.qecio_figures(p, BERLIN)
    assert {str(f.retrieved_at) for f in figs} == {"2026-03-04"}


def test_bikenetkit_retrieved_at_is_zip_mtime_utc_date(tmp_path):
    gpkg = tmp_path / "berlin_de.gpkg"
    _write_edges(gpkg, LineString([(13.4, 52.5), (13.4147, 52.5)]))
    _zip_gpkg(tmp_path, gpkg)
    ts = datetime(2026, 8, 9, 1, 0, tzinfo=UTC).timestamp()
    os.utime(tmp_path / "bike_networks.zip", (ts, ts))
    (f,) = X.bikenetkit_figures(tmp_path, [c for c in CITIES if c.id == "berlin"])
    assert str(f.retrieved_at) == "2026-08-09"
    assert "compare against tiers A+B+E" in f.note


def test_qecio_notes_carry_file_md5(tmp_path):
    p = _qecio_copy(tmp_path)
    figs = X.qecio_figures(p, BERLIN)
    assert figs and all(f"file md5 {md5_of(p)}" in f.note for f in figs)


def test_qecio_dk011_note_flags_byen_kobenhavn(tmp_path):
    src = (FIX / "qecio_summary_head.csv").read_text(encoding="utf-8")
    p = tmp_path / "dk.csv"
    p.write_text(src.replace("DE,Berlin,DE300", "DK,Byen København,DK011"), encoding="utf-8")
    figs = X.qecio_figures(p, [c for c in CITIES if c.id == "copenhagen"])
    assert {f.city_id for f in figs} == {"copenhagen"}
    assert all("Byen København" in f.note and "185 km2" in f.note for f in figs)


def test_vienna_rows_point_at_each_other():
    figs = X.load_figures_csv(CFG / "external" / "figures.csv")
    vie = [f for f in figs if f.city_id == "vienna" and f.metric_name == "protected_km"]
    by_scope = {f.network_scope: f.note for f in vie}
    assert "superseded" in by_scope["whole_network"]
    assert (
        "date of web correction not published" in by_scope["incl_traffic_calmed_restricted_access"]
    )


def test_refresh_qecio_deletes_cache_before_fetch(tmp_path, monkeypatch):
    cached = tmp_path / "data" / "external" / "qecio" / X.QECIO_LOCAL_NAME
    cached.parent.mkdir(parents=True)
    cached.write_text("stale")
    seen = []

    def fake_fetch(url, dst, **kw):
        seen.append(dst.exists())
        _qecio_all_cities(dst)
        return dst

    monkeypatch.setattr(X, "fetch", fake_fetch)
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        upsert_cities(conn, CITIES)
        X.load_all(conn, tmp_path / "data", CFG, qecio=True, bikenetkit=False, refresh_qecio=True)
        assert seen == [False]
        X.load_all(conn, tmp_path / "data", CFG, qecio=True, bikenetkit=False)
        assert seen == [False, True]  # without the flag the cache is kept


def test_failed_qecio_fetch_keeps_curated_rows(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise DownloadError("offline")

    monkeypatch.setattr(X, "fetch", boom)
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        upsert_cities(conn, CITIES)
        with pytest.raises(DownloadError):
            X.load_all(conn, tmp_path / "data", CFG, qecio=True, bikenetkit=False)
        curated = [f for f in X.load_figures_csv(CURATED) if f.city_id == "berlin"]
        assert len(fetch_external_figures(conn, "berlin")) == len(curated) > 0


def test_vienna_web_correction_is_dated_after_the_report():
    figs = [f for f in X.load_figures_csv(CURATED) if f.city_id == "vienna"]
    pdf = {f.reference_date for f in figs if f.network_scope == "whole_network"}
    web = {f.reference_date for f in figs if f.network_scope != "whole_network"}
    assert len(pdf) == len(web) == 1 and min(web) > max(pdf)
