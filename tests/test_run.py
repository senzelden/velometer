import subprocess
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
from velometer.sources.geofabrik import IndexSnapshot, RegionFile

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
        region_uncovered_km2=lambda *a: (0.0, 1.0),  # coverage has its own tests
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


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _status(conn, run_id):
    return conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()[0]


def test_force_reruns_and_leaves_exactly_one_done_row(conn, tmp_path):
    a = _run(conn, tmp_path, _deps(tmp_path, []))
    b = _run(conn, tmp_path, _deps(tmp_path, []), force=True)
    assert b.status == "done" and b.run_id != a.run_id
    done = [r[0] for r in conn.execute("SELECT id FROM runs WHERE status='done'")]
    assert done == [b.run_id]
    assert _status(conn, a.run_id) == "failed"


def test_forced_run_failing_inside_complete_run_keeps_old_run_done(conn, tmp_path, monkeypatch):
    a = _run(conn, tmp_path, _deps(tmp_path, []))
    tiers_before = _count(conn, "tier_lengths")
    # duplicate metric rows violate the primary key mid-transaction, after earlier inserts
    monkeypatch.setattr(R, "with_per_100k", lambda metrics, pop: metrics + metrics)
    b = _run(conn, tmp_path, _deps(tmp_path, []), force=True)
    assert b.status == "failed" and b.run_id != a.run_id
    assert _status(conn, a.run_id) == "done"
    assert _status(conn, b.run_id) == "failed"
    assert _count(conn, "tier_lengths") == tiers_before  # new run's rows rolled back
    assert (
        conn.execute("SELECT COUNT(*) FROM metrics WHERE run_id=?", (b.run_id,)).fetchone()[0] == 0
    )


def test_failed_run_rolls_back_every_result_table_and_is_retried(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(R, "with_per_100k", lambda metrics, pop: metrics + metrics)
    failed = _run(conn, tmp_path, _deps(tmp_path, []))
    assert failed.status == "failed" and failed.run_id is not None
    assert _status(conn, failed.run_id) == "failed"
    for table in ("tier_lengths", "road_lengths", "metrics", "completeness", "duplicates"):
        assert _count(conn, table) == 0, table
    monkeypatch.undo()
    assert _run(conn, tmp_path, _deps(tmp_path, [])).status == "done"


def test_boundary_clips_stored_lengths(conn, tmp_path):
    from pyproj import Transformer

    _, y = Transformer.from_crs(4326, CITY.epsg, always_xy=True).transform(13.41, 52.535)
    full = _run(conn, tmp_path, _deps(tmp_path, []))
    small = box(-1e9, -1e9, 1e9, y)  # south of the fixture's northern ways

    deps = _deps(tmp_path, [])

    def city_boundary(city, kind, data_dir, region_path=None):
        rec, pop = deps.city_boundary(city, kind, data_dir, region_path)
        b = rec.boundary.model_copy(update={"sha256": "c" * 64})
        return BoundaryRecord(b, rec.geojson_path, small), pop

    clipped = _run(conn, tmp_path, R.RunDeps(**{**deps.__dict__, "city_boundary": city_boundary}))
    assert clipped.status == "done" and clipped.run_id != full.run_id

    def all_public(run_id):
        return conn.execute(
            "SELECT length_km FROM road_lengths WHERE run_id=? AND road_class='all_public'",
            (run_id,),
        ).fetchone()[0]

    assert 0 < all_public(clipped.run_id) < all_public(full.run_id)


def test_failure_before_the_run_starts_is_reported_not_raised(conn, tmp_path):
    deps = _deps(tmp_path, [])

    def bad_boundary(*a, **kw):
        raise ValueError("Eurostat: no positive population in response")

    out = _run(conn, tmp_path, R.RunDeps(**{**deps.__dict__, "city_boundary": bad_boundary}))
    assert out.status == "failed" and out.run_id is None and "Eurostat" in out.error
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


BERLIN_BOX = box(380_000, 5_810_000, 410_000, 5_840_000)  # EPSG:25833, 900 km², holds MINI


def _guarded(tmp_path, region_25833):
    """Deps with a realistic boundary and a fake index whose Berlin extract is region_25833."""
    from pyproj import Transformer
    from shapely.ops import transform

    from velometer.sources.geofabrik import BASE

    to_wgs84 = Transformer.from_crs(CITY.epsg, 4326, always_xy=True).transform
    index = {
        "berlin": {
            "geometry": transform(to_wgs84, region_25833),
            "parent": "germany",
            "history": None,
            "pbf": f"{BASE}/{CITY.geofabrik_region}-latest.osm.pbf",
        }
    }
    deps = _deps(tmp_path, [])

    def city_boundary(city, kind, data_dir, region_path=None):
        rec, pop = deps.city_boundary(city, kind, data_dir, region_path)
        return BoundaryRecord(rec.boundary, rec.geojson_path, BERLIN_BOX), pop

    return R.RunDeps(
        **{
            **deps.__dict__,
            "city_boundary": city_boundary,
            "region_uncovered_km2": lambda region, poly, epsg, data_dir: R.region_uncovered_km2(
                region, poly, epsg, index
            ),
            # an uncovered boundary now looks for a covering set: serve the same fake index
            "fetch_index": lambda data_dir: IndexSnapshot(tmp_path / "idx.json", "i" * 64),
            "load_index": lambda path: index,
        }
    )


def test_boundary_the_region_does_not_cover_fails_before_any_run_row(conn, tmp_path):
    inside = box(390_000, 5_820_000, 400_000, 5_830_000)  # extract smaller than the boundary
    out = _run(conn, tmp_path, _guarded(tmp_path, inside), boundary_kind="fua")
    assert out.status == "failed" and out.run_id is None
    assert "uncovered" in out.error and "berlin/fua" in out.error
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0


def test_boundary_inside_the_region_runs(conn, tmp_path):
    out = _run(conn, tmp_path, _guarded(tmp_path, BERLIN_BOX.buffer(5_000)))
    assert out.status == "done", out.error


def test_uncovered_sliver_within_tolerance_runs_and_above_it_fails(conn, tmp_path):
    # tolerance is max(0.1% of 900 km², 1 km²) = 1 km²; a 30 km long strip of width w is left out
    def short_by(w):
        return box(380_000 + w, 5_809_000, 411_000, 5_841_000)

    assert _run(conn, tmp_path, _guarded(tmp_path, short_by(20))).status == "done"  # 0.6 km²
    out = _run(conn, tmp_path, _guarded(tmp_path, short_by(50)), boundary_kind="fua")  # 1.5 km²
    assert out.status == "failed" and "uncovered" in out.error


def test_region_uncovered_km2_matches_the_regions_for_rule():
    from pyproj import Transformer
    from shapely.ops import transform

    from velometer.sources.geofabrik import BASE

    to_wgs84 = Transformer.from_crs(CITY.epsg, 4326, always_xy=True).transform
    region = box(390_000, 5_810_000, 410_000, 5_840_000)  # leaves 300 km² of BERLIN_BOX out
    index = {
        "x": {
            "geometry": transform(to_wgs84, region),
            "pbf": f"{BASE}/{CITY.geofabrik_region}-latest.osm.pbf",
        }
    }
    uncovered, tolerance = R.region_uncovered_km2(
        CITY.geofabrik_region, BERLIN_BOX, CITY.epsg, index
    )
    assert uncovered == pytest.approx(300, rel=0.01)
    assert tolerance == pytest.approx(1.0)
    with pytest.raises(ValueError, match="not in the Geofabrik index"):
        R.region_uncovered_km2("europe/nowhere", BERLIN_BOX, CITY.epsg, index)


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


def test_git_commit_clean_sha(monkeypatch):
    outputs = {("rev-parse", "HEAD"): "abc123\n", ("status", "--porcelain"): ""}
    monkeypatch.setattr(R, "_git", lambda *a: outputs[a])
    assert R.git_commit() == "abc123"


def test_git_commit_unknown_when_git_fails(monkeypatch):
    def fail(*a):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(R, "_git", fail)
    assert R.git_commit() == "unknown"


def test_git_runs_in_the_source_tree_not_the_process_cwd(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, stdout="x\n")

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    R._git("rev-parse", "HEAD")
    assert Path(seen["cwd"]) == Path(R.__file__).resolve().parent


def test_git_commit_marks_dirty_tree(monkeypatch):
    outputs = {("rev-parse", "HEAD"): "abc123\n", ("status", "--porcelain"): " M x\n"}
    monkeypatch.setattr(R, "_git", lambda *a: outputs[a])
    assert R.git_commit() == "abc123-dirty"


def test_both_sides_run_does_not_displace_the_default_run(conn, tmp_path):
    from velometer.db import latest_done_run
    from velometer.reconcile import reconcile_city

    default = _run(conn, tmp_path, _deps(tmp_path, []))
    both = _run(
        conn,
        tmp_path,
        _deps(tmp_path, []),
        parameters={"plain_cycleway_on_oneway": "both_sides"},
    )
    assert both.status == "done" and both.run_id > default.run_id
    assert latest_done_run(conn, "berlin", "lau") == default.run_id
    conn.execute(
        "INSERT INTO external_figures (city_id, source, metric_name, value, unit, reference_date,"
        " network_scope, length_basis, source_url, retrieved_at) VALUES ('berlin',"
        " 'clean_cities_2025', 'protected_km', 1, 'km', NULL, 'whole_network', 'unknown', 'u',"
        " '2026-10-01')"
    )
    from velometer.config import load_classifier, load_presets

    presets = load_presets(
        CFG_DIR / "presets.yaml", load_classifier(CFG_DIR / "classifier" / "v1.yaml")
    )
    report = reconcile_city(conn, "berlin", CFG_DIR / "reconcile.yaml", presets=presets)
    assert report.run_id == default.run_id
    (gap,) = (g for g in report.gaps if "~" not in g.key)
    a_b = conn.execute(
        "SELECT SUM(length_km) FROM tier_lengths WHERE run_id=? AND tier IN ('A','B') "
        "AND length_basis='per_side'",
        (default.run_id,),
    ).fetchone()[0]
    assert gap.ours == pytest.approx(a_b)


def _config_copy(tmp_path) -> Path:
    import shutil

    dst = tmp_path / "config"
    shutil.copytree(CFG_DIR, dst)
    return dst


def test_changed_presets_yaml_does_not_reuse_the_done_run(conn, tmp_path):
    cfg = _config_copy(tmp_path)
    first = R.run_city(conn, CITY, data_dir=tmp_path, config_dir=cfg, deps=_deps(tmp_path, []))
    same = R.run_city(conn, CITY, data_dir=tmp_path, config_dir=cfg, deps=_deps(tmp_path, []))
    assert same.status == "skipped" and same.run_id == first.run_id
    presets = cfg / "presets.yaml"
    presets.write_text(
        presets.read_text().replace("denominator: all_public", "denominator: main_excl_motorway")
    )
    again = R.run_city(conn, CITY, data_dir=tmp_path, config_dir=cfg, deps=_deps(tmp_path, []))
    assert again.status == "done" and again.run_id != first.run_id


def test_run_row_records_population_and_config_sha(conn, tmp_path):
    out = _run(conn, tmp_path, _deps(tmp_path, [], population=123_456))
    row = conn.execute(
        "SELECT population_value, population_year, population_source, config_sha256 FROM runs "
        "WHERE id=?",
        (out.run_id,),
    ).fetchone()
    expected_sha = R.config_sha256(
        CFG_DIR / "classifier" / "v1.yaml", CFG_DIR / "presets.yaml", CFG_DIR / "activity.yaml"
    )
    assert row == (123_456, 2024, "t", expected_sha)


def test_interrupted_run_is_marked_failed_not_left_running(conn, tmp_path):
    def interrupted(path):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _run(conn, tmp_path, _deps(tmp_path, [], read=interrupted))
    rows = conn.execute("SELECT status, error FROM runs").fetchall()
    assert rows == [("failed", "KeyboardInterrupt: ")]


@pytest.mark.slow
def test_berlin_end_to_end(tmp_path):
    """Spec section 4: one real Berlin run from an empty data dir (network, about 200 MB)."""
    from velometer.sources.download import md5_of

    data = tmp_path / "data"
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        out = R.run_city(conn, CITY, data_dir=data, config_dir=CFG_DIR)
        assert out.status == "done", out.error
        run = conn.execute(
            "SELECT region_md5, osm_timestamp FROM runs WHERE id=?", (out.run_id,)
        ).fetchone()
        (region,) = (data / "raw").glob("berlin-*.osm.pbf")
        assert run[0] == md5_of(region)
        assert run[1] is not None
        headline = conn.execute(
            "SELECT value FROM metrics WHERE run_id=? AND preset='ours_headline'", (out.run_id,)
        ).fetchone()
        assert headline is not None and headline[0] is not None
        tiers = conn.execute(
            "SELECT length_km FROM tier_lengths WHERE run_id=?", (out.run_id,)
        ).fetchall()
        assert tiers and all(km >= 0 for (km,) in tiers)
        again = R.run_city(conn, CITY, data_dir=data, config_dir=CFG_DIR)
        assert again.status == "skipped" and again.run_id == out.run_id


def test_config_sha_separates_the_files(tmp_path):
    """Moving a byte from one file's end to the next file's start must change the hash."""
    a1, b1, c1 = tmp_path / "a.yaml", tmp_path / "b.yaml", tmp_path / "c.yaml"
    c1.write_text("zz")
    a1.write_text("xx")
    b1.write_text("yy")
    first = R.config_sha256(a1, b1, c1)
    a1.write_text("xxy")
    b1.write_text("y")
    assert R.config_sha256(a1, b1, c1) != first
    b1.write_text("yy")
    c1.write_text("z")
    a1.write_text("xx")
    b1.write_text("yyz")
    assert R.config_sha256(a1, b1, c1) != first
    b1.write_text("yy")
    c1.write_text("zz")
    assert R.config_sha256(a1, b1, c1) == first  # still a pure function of the file contents


def test_config_sha_covers_activity_yaml(tmp_path):
    d = _config_copy(tmp_path)
    args = (d / "classifier/v2.yaml", d / "presets.yaml", d / "activity.yaml")
    before = R.config_sha256(*args)
    (d / "activity.yaml").write_text((d / "activity.yaml").read_text() + "\n# edit\n")
    assert R.config_sha256(*args) != before


def test_file_sha256_is_the_hex_sha256_of_the_bytes(tmp_path):
    import hashlib

    p = tmp_path / "f.yaml"
    p.write_bytes(b"abc")
    assert R.file_sha256(p) == hashlib.sha256(b"abc").hexdigest()


def test_gitattributes_pins_config_to_lf():
    text = (Path(__file__).resolve().parent.parent / ".gitattributes").read_text()
    assert "config/** text eol=lf" in text.splitlines()


def test_both_bases_of_clean_cities_are_stored_by_a_run(conn, tmp_path):
    out = _run(conn, tmp_path, _deps(tmp_path, []))
    rows = conn.execute(
        "SELECT preset, length_basis FROM metrics WHERE run_id=? ORDER BY preset, length_basis",
        (out.run_id,),
    ).fetchall()
    assert rows == [
        ("clean_cities_2025", "per_side"),
        ("clean_cities_2025", "qecio_weighted"),
        ("ecf_qecio", "qecio_weighted"),
        ("ours_headline", "per_side"),
    ]


# --- FUA current runs: the boundary reaches past the city's extract (merged covering regions) ---


class _Fua:
    """Deps whose own region does not cover the boundary, plus a fake index and region set."""

    def __init__(self, tmp_path, regions, selection=None):
        from velometer.sources.geofabrik import BASE, RegionSelection

        self.tmp_path = tmp_path
        self.regions = regions  # id -> (md5, osm_timestamp)
        self.merge_calls: list[list[Path]] = []
        self.polygons = []
        self.fetched: list[str] = []
        self.index = {
            rid: {
                "geometry": box(0, 0, 1, 1),
                "parent": None,
                "history": "h",
                "pbf": f"{BASE}/europe/{rid}-latest.osm.pbf",
            }
            for rid in regions
        }
        self.selection = RegionSelection(sorted(selection or regions), 0.25)

    def deps(self, **override):
        base = _deps(self.tmp_path, [])

        def city_boundary(city, kind, data_dir, region_path=None):
            rec, pop = base.city_boundary(city, kind, data_dir, region_path)
            return BoundaryRecord(rec.boundary, rec.geojson_path, BERLIN_BOX), pop

        def fetch_region(region, data_dir):
            self.fetched.append(region)
            rid = region.rsplit("/", 1)[-1]
            md5, ts = self.regions.get(rid, ("c" * 32, datetime(2026, 9, 30, tzinfo=UTC)))
            path = self.tmp_path / f"{rid}.osm"
            path.write_bytes(MINI.read_bytes())
            return RegionFile(region, path, "u", md5, ts)

        def regions_for(polygon_wgs84, index):
            self.polygons.append(polygon_wgs84)
            if isinstance(self.selection, Exception):
                raise self.selection
            return self.selection

        def merge(srcs, dst):
            self.merge_calls.append(list(srcs))
            dst.write_bytes(srcs[0].read_bytes())
            return dst

        fields = {
            **base.__dict__,
            "city_boundary": city_boundary,
            "fetch_region": fetch_region,
            "region_uncovered_km2": lambda *a: (50.0, 1.0),
            "fetch_index": lambda data_dir: IndexSnapshot(self.tmp_path / "idx.json", "i" * 64),
            "load_index": lambda path: self.index,
            "regions_for": regions_for,
            "merge": merge,
        }
        return R.RunDeps(**{**fields, **override})


T1, T2 = datetime(2026, 9, 29, tzinfo=UTC), datetime(2026, 9, 30, tzinfo=UTC)
R1, R2 = ("a" * 32, T2), ("b" * 32, T1)


def _fua_row(conn, run_id):
    return conn.execute(
        "SELECT source, region_md5, osm_timestamp, status FROM runs WHERE id=?", (run_id,)
    ).fetchone()


def test_current_fua_run_merges_covering_regions(conn, tmp_path):
    from velometer.db import fetch_history_set
    from velometer.sources.geofabrik import set_md5

    fua = _Fua(tmp_path, {"r1": R1, "r2": R2})
    out = _run(conn, tmp_path, fua.deps(), boundary_kind="fua")
    assert out.status == "done", out.error
    source, region_md5, _, _ = _fua_row(conn, out.run_id)
    assert source == "current"
    assert region_md5 == set_md5([("r1", "a" * 32), ("r2", "b" * 32)])
    hs = fetch_history_set(conn, region_md5)
    regions = hs["regions"]
    assert [r["region"] for r in regions] == ["r1", "r2"]
    assert fua.fetched[1:] == ["europe/r1", "europe/r2"]  # paths only to fetch, ids are recorded
    assert {r["md5_source"] for r in regions} == {"published"}
    assert regions[0]["fetched_at"] == datetime.now(UTC).date().isoformat()
    assert hs["index_sha256"] == "i" * 64 and hs["uncovered_km2"] == 0.25
    assert len(fua.merge_calls) == 1 and len(fua.merge_calls[0]) == 2
    merged = tmp_path / "raw" / "merged" / f"berlin_fua_{region_md5[:8]}.osm.pbf"
    assert merged.exists()
    lon, lat = fua.polygons[0].centroid.x, fua.polygons[0].centroid.y
    assert 12 < lon < 15 and 52 < lat < 53  # selection is asked in WGS84, not the city's EPSG


def test_current_fua_single_covering_region_needs_no_merge(conn, tmp_path):
    from velometer.sources.geofabrik import set_md5

    fua = _Fua(tmp_path, {"r1": R1})
    out = _run(conn, tmp_path, fua.deps(), boundary_kind="fua")
    assert out.status == "done", out.error
    assert fua.merge_calls == []
    assert _fua_row(conn, out.run_id)[1] == set_md5([("r1", "a" * 32)])
    assert not (tmp_path / "raw" / "merged").exists()


def test_current_fua_timestamp_is_the_oldest_region(conn, tmp_path):
    fua = _Fua(tmp_path, {"r1": R1, "r2": R2})  # r1 is newer (T2), r2 older (T1)
    out = _run(conn, tmp_path, fua.deps(), boundary_kind="fua")
    assert _fua_row(conn, out.run_id)[2] == "2026-09-29T00:00:00Z"


def test_current_run_without_any_covering_set_still_fails_before_a_run_row(conn, tmp_path):
    fua = _Fua(tmp_path, {"r1": R1})
    fua.selection = ValueError("the index leaf regions with history do not cover the polygon")
    out = _run(conn, tmp_path, fua.deps(), boundary_kind="fua")
    assert out.status == "failed" and out.run_id is None
    assert "uncovered" in out.error and "berlin/fua" in out.error
    assert "do not cover the polygon" in out.error  # the original message is carried
    assert _count(conn, "runs") == 0 and _count(conn, "history_sets") == 0


def test_merged_file_is_reused(conn, tmp_path):
    fua = _Fua(tmp_path, {"r1": R1, "r2": R2})
    assert _run(conn, tmp_path, fua.deps(), boundary_kind="fua").status == "done"
    assert _run(conn, tmp_path, fua.deps(), boundary_kind="fua", force=True).status == "done"
    assert len(fua.merge_calls) == 1


def test_covered_city_run_never_touches_the_index(conn, tmp_path):
    def boom(*a, **k):
        raise AssertionError("index used for a covered boundary")

    deps = R.RunDeps(**{**_deps(tmp_path, []).__dict__, "fetch_index": boom, "regions_for": boom})
    assert _run(conn, tmp_path, deps).status == "done"
    assert _count(conn, "history_sets") == 0
