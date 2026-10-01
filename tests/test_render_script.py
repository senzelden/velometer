import importlib.util
from pathlib import Path

import pytest

from velometer.models import Boundary, Metric

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "render_m2_results.py"
_spec = importlib.util.spec_from_file_location("render_m2_results", _PATH)
render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render)


def _boundary(sha: str = "b" * 64) -> Boundary:
    return Boundary(
        city_id="berlin",
        kind="lau",
        source="Eurostat GISCO",
        source_version="LAU 2024 (1:1M)",
        area_km2=891.1,
        path="p",
        sha256=sha,
    )


def _run(**kw) -> dict:
    return {
        "id": 6,
        "osm_timestamp": "2026-10-02T20:21:00Z",
        "classifier_version": "v1",
        "classifier_parameters": "{}",
        "git_commit": "0123456789abcdef-dirty",
        "config_sha256": "c" * 64,
        "region_md5": "d" * 32,
        "boundary_sha256": "b" * 64,
        "population_value": 3_782_202,
        "population_year": 2024,
        "population_source": "GISCO LAU 2024 POP_2024",
        **kw,
    }


def _row(**run_kw) -> dict:
    from velometer.models import City

    city = City(
        id="berlin",
        name="Berlin",
        country_iso2="DE",
        osm_relation_id=62422,
        epsg=25833,
        geofabrik_region="r",
        population=None,  # the cities row may be empty or newer: never read for provenance
    )
    m = Metric(
        preset="ours_headline", length_basis="per_side", value=1.0, numerator_km=1, denominator_km=1
    )
    return {
        "city": city,
        "run": _run(**run_kw),
        "metrics": {"ours_headline": m},
        "roads": {},
        "tier_km": {(b, t): 0.0 for b in ("per_side", "qecio_weighted") for t in render.TIERS},
        "completeness": [],
        "boundary": _boundary(),
    }


def test_provenance_keeps_dirty_marker_boundary_sha_and_run_population():
    md = render.markdown([_row()])
    assert "`0123456-dirty`" in md
    assert "`bbbbbbbbbbbb`" in md and "`cccccccccccc`" in md
    assert "3,782,202 (2024) | GISCO LAU 2024 POP_2024" in md


def test_boundary_row_must_be_the_one_the_run_used():
    render.check_boundary("berlin", _run(), _boundary())
    with pytest.raises(SystemExit, match="re-run"):
        render.check_boundary("berlin", _run(), _boundary("e" * 64))
    with pytest.raises(SystemExit):
        render.check_boundary("berlin", _run(), None)


def test_chart_title_comes_from_the_run_rows():
    title = render.chart_title([_row()])
    assert "OSM 2026-10-02" in title and "classifier v1" in title and "LAU 2024" in title
    assert "1 pilot cities" in title
