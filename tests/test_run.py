from datetime import UTC, datetime
from pathlib import Path

import pytest
from shapely import box

from velometer import run as R
from velometer.config import default_config_dir, load_cities
from velometer.db import create_schema, open_db, upsert_cities
from velometer.models import Boundary, Metric, Population
from velometer.pipeline.read import read_ways
from velometer.sources.boundaries import BoundaryRecord
from velometer.sources.geofabrik import RegionFile

CFG_DIR = default_config_dir()
CITY = next(c for c in load_cities(CFG_DIR / "cities.yaml") if c.id == "berlin")
MINI = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"


def _deps(tmp_path, calls, read=None, population=100_000):
    def fetch_region(region, data_dir):
        calls.append("fetch")
        return RegionFile(region, MINI, "u", "md5", datetime(2026, 9, 30, tzinfo=UTC))

    def city_boundary(city, kind, data_dir, region_path=None):
        b = Boundary(
            city_id=city.id,
            kind=kind,
            source="t",
            source_version="t",
            area_km2=1e6,
            path=str(tmp_path / "b.geojson"),
            sha256="s" * 64,
        )
        pop = Population(value=population, year=2024, source="t") if population else None
        return BoundaryRecord(b, tmp_path / "b.geojson", box(-1e9, -1e9, 1e9, 1e9)), pop

    def snapshot(*args, **kw):
        calls.append("snapshot")
        return MINI

    return R.RunDeps(
        fetch_region=fetch_region,
        city_boundary=city_boundary,
        snapshot=snapshot,
        read_ways=read or read_ways,
    )


@pytest.fixture
def conn(tmp_path):
    with open_db(tmp_path / "v.sqlite") as c:
        create_schema(c)
        upsert_cities(c, load_cities(CFG_DIR / "cities.yaml"))
        yield c


def _run(conn, tmp_path, deps, **kw):
    return R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=deps, **kw)


def test_run_persists_and_second_run_is_skipped(conn, tmp_path):
    calls = []
    first = _run(conn, tmp_path, _deps(tmp_path, calls))
    assert first.status == "done"
    second = _run(conn, tmp_path, _deps(tmp_path, calls))
    assert second.status == "skipped" and second.run_id == first.run_id
    assert calls.count("snapshot") == 1  # no rework when skipped
    per_100k = conn.execute("SELECT per_100k FROM metrics WHERE preset='ours_headline'").fetchone()[
        0
    ]
    num = conn.execute("SELECT numerator_km FROM metrics WHERE preset='ours_headline'").fetchone()[
        0
    ]
    assert per_100k == pytest.approx(num)  # population is exactly 100k


def test_run_key_includes_parameters(conn, tmp_path):
    a = _run(conn, tmp_path, _deps(tmp_path, []))
    b = _run(
        conn,
        tmp_path,
        _deps(tmp_path, []),
        parameters={"plain_cycleway_on_oneway": "both_sides"},
    )
    assert b.status == "done" and b.run_id != a.run_id
    again = _run(
        conn,
        tmp_path,
        _deps(tmp_path, []),
        parameters={"plain_cycleway_on_oneway": "both_sides"},
    )
    assert again.status == "skipped" and again.run_id == b.run_id


def test_force_reruns(conn, tmp_path):
    a = _run(conn, tmp_path, _deps(tmp_path, []))
    b = _run(conn, tmp_path, _deps(tmp_path, []), force=True)
    assert b.status == "done" and b.run_id != a.run_id


def test_failed_run_leaves_no_rows_and_is_retried(conn, tmp_path):
    def boom(path):
        raise RuntimeError("disk on fire")

    failed = _run(conn, tmp_path, _deps(tmp_path, [], read=boom))
    assert failed.status == "failed" and "disk on fire" in failed.error
    assert conn.execute("SELECT COUNT(*) FROM tier_lengths").fetchone()[0] == 0
    retried = _run(conn, tmp_path, _deps(tmp_path, []))
    assert retried.status == "done"


def test_failure_before_the_run_starts_is_reported_not_raised(conn, tmp_path):
    deps = _deps(tmp_path, [])

    def bad_boundary(*a, **kw):
        raise ValueError("Eurostat: no positive population in response")

    out = _run(conn, tmp_path, R.RunDeps(**{**deps.__dict__, "city_boundary": bad_boundary}))
    assert out.status == "failed" and out.run_id is None and "Eurostat" in out.error
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


def test_missing_population_leaves_per_100k_null(conn, tmp_path):
    out = _run(conn, tmp_path, _deps(tmp_path, [], population=None))
    assert out.status == "done"
    rows = conn.execute("SELECT per_100k FROM metrics").fetchall()
    assert rows and all(r[0] is None for r in rows)


def test_with_per_100k_none_and_scaling():
    m = Metric(
        preset="p", length_basis="per_side", value=1.0, numerator_km=50.0, denominator_km=100.0
    )
    assert R.with_per_100k([m], None)[0].per_100k is None
    assert R.with_per_100k([m], 200_000)[0].per_100k == pytest.approx(25.0)


def test_git_commit_marks_dirty_tree(monkeypatch):
    outputs = {("rev-parse", "HEAD"): "abc123\n", ("status", "--porcelain"): " M x\n"}
    monkeypatch.setattr(R, "_git", lambda *a: outputs[a])
    assert R.git_commit() == "abc123-dirty"
