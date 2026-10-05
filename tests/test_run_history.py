import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from shapely import box

from tests.fake_subareas import config_subareas, without_subareas
from velometer import run as R
from velometer.config import (
    REMAINDER_ID,
    SubareaRelation,
    SubareasConfig,
    default_config_dir,
    load_cities,
    load_classifier,
    load_history,
)
from velometer.db import (
    canonical_parameters,
    create_schema,
    fetch_activity,
    fetch_diagnostics,
    fetch_history_set,
    history_runs,
    open_db,
    upsert_cities,
)
from velometer.models import ActivityYear, Boundary, Population
from velometer.pipeline.measure import measure
from velometer.pipeline.read import read_ways
from velometer.pipeline.tags import parts
from velometer.sources.boundaries import BoundaryRecord
from velometer.sources.geofabrik import HistoryFile, IndexSnapshot, history_set_md5
from velometer.subareas import SubareaPolygon, subarea_set_sha

CFG_DIR = default_config_dir()
CITY = next(c for c in load_cities(CFG_DIR / "cities.yaml") if c.id == "berlin")
CLS = load_classifier(CFG_DIR / "classifier" / "v1.yaml")
MINI = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"
SHA = "s" * 64
ACT_SHA = R.file_sha256(CFG_DIR / "activity.yaml")
SERIES = load_history(CFG_DIR / "history.yaml").year_range()
ACTIVITY_YEARS = list(range(SERIES.start, SERIES.stop + 1))  # the series years plus last + 1
INDEX = {
    "berlin": {"geometry": box(13.0, 52.0, 14.0, 53.0), "parent": None, "history": "http://x/h"}
}


class Fakes:
    def __init__(self, tmp_path, md5="m1", fail_year=None):
        self.tmp_path = tmp_path
        self.md5 = md5
        self.set_md5 = history_set_md5([self._file()])
        self.fail_year = fail_year
        self.calls: list[str] = []
        self.activity_args: list[tuple] = []

    def _file(self):
        return HistoryFile("berlin", MINI, self.md5, "published", date(2026, 10, 1))

    def deps(self, **override):
        def fetch_index(data_dir):
            return IndexSnapshot(self.tmp_path / "index.json", "i" * 64)

        def fetch_history(region, data_dir, index):
            self.calls.append("fetch_history")
            return self._file()

        def city_boundary(city, kind, data_dir, region_path=None):
            b = Boundary(
                city_id=city.id,
                kind=kind,
                source="t",
                source_version="t",
                area_km2=1e3,
                path=str(self.tmp_path / "b.geojson"),
                sha256=SHA,
            )
            pop = Population(value=100_000, year=2024, source="t")
            poly = box(380_000, 5_810_000, 410_000, 5_840_000)  # EPSG:25833, around Berlin
            return BoundaryRecord(b, self.tmp_path / "b.geojson", poly), pop

        def city_history(*args):
            return self.tmp_path / "city.osh.pbf"

        def snapshot_at(hist, ts, data_dir):
            if ts.year == self.fail_year:
                raise RuntimeError("snapshot boom")
            self.calls.append(f"snapshot_{ts.year}")
            assert ts.tzinfo is not None
            return MINI

        def activity(hist, years, cfg, *, city_id, boundary_kind, history_set_md5):
            self.activity_args.append((list(years), history_set_md5))
            return [
                ActivityYear(
                    city_id=city_id,
                    boundary_kind=boundary_kind,
                    year=y,
                    history_set_md5=history_set_md5,
                    n_edits=1,
                    n_changesets=1,
                    n_mappers=1,
                    top_mapper_share=1.0,
                    n_ways_created_cycling=0,
                    n_ways_deleted_cycling=0,
                )
                for y in years
            ]

        load_subareas, subarea_shas = config_subareas()  # the shipped Berlin has Bezirke
        d = dict(
            fetch_index=fetch_index,
            load_index=lambda path: INDEX,
            fetch_history=fetch_history,
            city_boundary=city_boundary,
            city_history=city_history,
            snapshot_at=snapshot_at,
            read_ways=read_ways,
            activity=activity,
            load_subareas=load_subareas,
            subarea_shas=subarea_shas,
        )
        return R.HistoryDeps(**{**d, **override})


@pytest.fixture
def conn(tmp_path):
    with open_db(tmp_path / "v.sqlite") as c:
        create_schema(c)
        upsert_cities(c, load_cities(CFG_DIR / "cities.yaml"))
        yield c


def _history(conn, tmp_path, fakes, years=range(2019, 2022), **kw):
    return R.run_history(
        conn,
        CITY,
        years,
        data_dir=tmp_path,
        config_dir=CFG_DIR,
        deps=fakes.deps(),
        **kw,
    )


def _runs(conn, source="history"):
    return conn.execute(
        "SELECT id, status, osm_timestamp, region_md5, population_year FROM runs "
        "WHERE source=? ORDER BY osm_timestamp, id",
        (source,),
    ).fetchall()


def test_run_history_makes_one_history_run_per_year(conn, tmp_path):
    out = _history(conn, tmp_path, Fakes(tmp_path))
    assert [o.status for o in out] == ["done"] * 3
    assert [o.year for o in out] == [2019, 2020, 2021]
    rows = _runs(conn)
    assert [r[2] for r in rows] == [f"{y}-01-01T00:00:00Z" for y in (2019, 2020, 2021)]
    assert {r[3] for r in rows} == {Fakes(tmp_path).set_md5}
    assert {r[4] for r in rows} == {2024}  # population held constant
    for o in out:
        d = fetch_diagnostics(conn, o.run_id)
        assert {"legacy_km", "unrecognised_cycling_km", "uncovered_km2"} <= set(d)
        assert d["uncovered_km2"] == pytest.approx(0, abs=1)


def test_history_run_records_peak_rss(conn, tmp_path):
    out = _history(conn, tmp_path, Fakes(tmp_path), years=range(2019, 2021))
    assert len(out) == 2
    peaks = [r[0] for r in conn.execute("SELECT peak_rss_kb FROM runs WHERE source='history'")]
    assert len(peaks) == 2 and all(p > 0 for p in peaks)


def test_rerun_skips_done_years(conn, tmp_path):
    fakes = Fakes(tmp_path)
    first = _history(conn, tmp_path, fakes)
    again = _history(conn, tmp_path, fakes)
    assert [o.status for o in again] == ["skipped"] * 3
    assert [o.run_id for o in again] == [o.run_id for o in first]
    assert fakes.calls.count("snapshot_2020") == 1


def test_new_history_set_makes_new_runs_and_series_uses_one_set(conn, tmp_path):
    old = _history(conn, tmp_path, Fakes(tmp_path, md5="old"))
    new = _history(conn, tmp_path, Fakes(tmp_path, md5="new"))
    assert [o.status for o in new] == ["done"] * 3
    from velometer.config import load_classifier
    from velometer.run import config_sha256

    cfg = load_classifier(CFG_DIR / "classifier" / "v1.yaml")
    kw = dict(
        classifier_version=cfg.version,
        classifier_parameters=canonical_parameters(cfg.parameters.model_dump()),
        config_sha256=config_sha256(
            CFG_DIR / "classifier" / "v1.yaml",
            CFG_DIR / "presets.yaml",
            CFG_DIR / "activity.yaml",
        ),
    )
    got_old = history_runs(
        conn, "berlin", "lau", history_set_md5=Fakes(tmp_path, md5="old").set_md5, **kw
    )
    got_new = history_runs(
        conn, "berlin", "lau", history_set_md5=Fakes(tmp_path, md5="new").set_md5, **kw
    )
    assert set(got_old.values()) == {o.run_id for o in old}
    assert set(got_new.values()) == {o.run_id for o in new}
    assert set(got_old.values()).isdisjoint(got_new.values())


def test_one_failing_year_does_not_stop_the_others(conn, tmp_path):
    out = _history(conn, tmp_path, Fakes(tmp_path, fail_year=2020))
    assert [o.status for o in out] == ["done", "failed", "done"]
    assert out[1].run_id is not None and "snapshot boom" in out[1].error
    assert [r[1] for r in _runs(conn)] == ["done", "failed", "done"]
    healed = _history(conn, tmp_path, Fakes(tmp_path))  # a re-run retries only the failed year
    assert [o.status for o in healed] == ["skipped", "done", "skipped"]


def test_pre_run_failure_returns_one_failed_outcome_and_no_run_row(conn, tmp_path):
    fakes = Fakes(tmp_path)

    def boom(region, data_dir, index):
        raise RuntimeError("auth refused")

    out = R.run_history(
        conn,
        CITY,
        range(2019, 2022),
        data_dir=tmp_path,
        config_dir=CFG_DIR,
        deps=fakes.deps(fetch_history=boom),
    )
    assert len(out) == 1
    assert (out[0].status, out[0].run_id) == ("failed", None)
    assert "auth refused" in out[0].error
    assert _runs(conn) == []
    assert fakes.activity_args == []


def test_activity_written_once_per_city_kind_set(conn, tmp_path):
    fakes = Fakes(tmp_path)
    _history(conn, tmp_path, fakes)
    assert fakes.activity_args == [(ACTIVITY_YEARS, fakes.set_md5)]
    stored = [a.year for a in fetch_activity(conn, "berlin", "lau", fakes.set_md5, ACT_SHA)]
    assert stored == ACTIVITY_YEARS
    _history(conn, tmp_path, fakes)  # everything reused: rows already match, no recompute
    assert len(fakes.activity_args) == 1
    _history(conn, tmp_path, fakes, force=True)  # forced: replaced, never duplicated
    assert len(fakes.activity_args) == 2
    assert len(fetch_activity(conn, "berlin", "lau", fakes.set_md5, ACT_SHA)) == len(ACTIVITY_YEARS)


def test_activity_covers_the_current_window_without_a_current_run(conn, tmp_path):
    fakes = Fakes(tmp_path)
    _history(conn, tmp_path, fakes)
    assert _runs(conn, "current") == []
    years = [a.year for a in fetch_activity(conn, "berlin", "lau", fakes.set_md5, ACT_SHA)]
    assert years[-1] == SERIES.stop  # last + 1: the current point's window
    assert [r[2] for r in _runs(conn)][-1] == "2021-01-01T00:00:00Z"  # but no extra run


def test_activity_is_the_same_with_or_without_a_current_run(conn, tmp_path):
    run = R.run_city(
        conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=_current_deps(tmp_path)
    )
    assert run.status == "done"
    fakes = Fakes(tmp_path)
    _history(conn, tmp_path, fakes)
    assert fakes.activity_args == [(ACTIVITY_YEARS, fakes.set_md5)]


def test_retrying_some_years_keeps_the_activity_of_every_year(conn, tmp_path):
    fakes = Fakes(tmp_path, fail_year=2020)
    _history(conn, tmp_path, fakes, years=range(2018, 2023))
    retry = Fakes(tmp_path)
    out = _history(conn, tmp_path, retry, years=range(2020, 2021))  # retry the failed year only
    assert [o.status for o in out] == ["done"]
    years = [a.year for a in fetch_activity(conn, "berlin", "lau", fakes.set_md5, ACT_SHA)]
    assert set(range(2018, 2023)) <= set(years)
    assert years == ACTIVITY_YEARS


PRIVACY_OSH = Path(__file__).parent / "fixtures" / "history" / "privacy.osh"
PRIVACY_UID, PRIVACY_USER = 987654321, "zz_mapper_name"  # the fixture's only mapper


def _cells(conn):
    """(table, column, value) of every cell of every table in the database."""
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        cur = conn.execute(f'SELECT * FROM "{t}"')
        cols = [d[0] for d in cur.description]
        for row in cur:
            yield from ((t, c, v) for c, v in zip(cols, row, strict=True))


def test_no_mapper_id_or_name_reaches_the_database(conn, tmp_path):
    """Spec §4: after a run with real activity over a history naming one mapper, no cell of any
    table holds that mapper's uid or user name."""
    fakes = Fakes(tmp_path)
    deps = fakes.deps(city_history=lambda *a: PRIVACY_OSH, activity=R.HistoryDeps().activity)
    out = R.run_history(
        conn, CITY, range(2019, 2021), data_dir=tmp_path, config_dir=CFG_DIR, deps=deps
    )
    assert {o.status for o in out} == {"done"}
    act = {a.year: a for a in fetch_activity(conn, "berlin", "lau", fakes.set_md5, ACT_SHA)}
    assert act[2020].n_edits == 3 and act[2020].top_mapper_share == 1.0  # the fixture was read
    leaks = [
        (t, c, v)
        for t, c, v in _cells(conn)
        if (isinstance(v, int | float) and v == PRIVACY_UID)
        or (isinstance(v, str) and (str(PRIVACY_UID) in v or PRIVACY_USER in v))
    ]
    assert leaks == []


def _current_deps(tmp_path):
    from velometer.sources.geofabrik import RegionFile

    h = Fakes(tmp_path).deps()
    return R.RunDeps(
        fetch_region=lambda region, d: RegionFile(
            region, MINI, "u", "md5", datetime(2026, 9, 30, tzinfo=UTC)
        ),
        city_boundary=h.city_boundary,
        snapshot=lambda *a, **k: MINI,
        read_ways=read_ways,
        region_uncovered_km2=lambda *a: (0.0, 1.0),
        load_subareas=h.load_subareas,
        subarea_shas=h.subarea_shas,
    )


def test_current_run_unaffected_by_history_runs(conn, tmp_path):
    deps = _current_deps(tmp_path)
    cur = R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=deps)
    _history(conn, tmp_path, Fakes(tmp_path), years=range(2026, 2027))
    again = R.run_city(conn, CITY, data_dir=tmp_path, config_dir=CFG_DIR, deps=deps)
    assert again.status == "skipped" and again.run_id == cur.run_id
    from velometer.db import latest_done_run

    assert latest_done_run(conn, "berlin", "lau") == cur.run_id


def test_history_set_provenance_recorded_once(conn, tmp_path):
    fakes = Fakes(tmp_path)
    _history(conn, tmp_path, fakes)
    _history(conn, tmp_path, fakes, force=True)
    assert conn.execute("SELECT COUNT(*) FROM history_sets").fetchone()[0] == 1
    hs = fetch_history_set(conn, fakes.set_md5)
    assert hs["regions"] == [
        {
            "region": "berlin",
            "md5": "m1",
            "md5_source": "published",
            "fetched_at": "2026-10-01",
        }
    ]
    assert hs["index_sha256"] == "i" * 64
    assert hs["index_path"] == str(tmp_path / "index.json")
    assert hs["uncovered_km2"] == pytest.approx(0, abs=1)
    assert fetch_history_set(conn, "nope") is None
    json.dumps(hs)


def test_keyboard_interrupt_leaves_the_year_failed_not_running_and_reraises(conn, tmp_path):
    fakes = Fakes(tmp_path)

    def interrupt(hist, ts, data_dir):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        R.run_history(
            conn,
            CITY,
            range(2019, 2021),
            data_dir=tmp_path,
            config_dir=CFG_DIR,
            deps=fakes.deps(snapshot_at=interrupt),
        )
    rows = conn.execute("SELECT status, error FROM runs").fetchall()
    assert rows == [("failed", "KeyboardInterrupt: ")]


def test_activity_failure_is_a_failed_outcome_and_the_year_runs_stay_done(conn, tmp_path):
    def boom(*args, **kw):
        raise RuntimeError("activity boom")

    out = R.run_history(
        conn,
        CITY,
        range(2019, 2021),
        data_dir=tmp_path,
        config_dir=CFG_DIR,
        deps=Fakes(tmp_path).deps(activity=boom),
    )
    assert [o.status for o in out] == ["done", "done", "failed"]
    assert out[2].run_id is None and "activity boom" in out[2].error
    assert [r[1] for r in _runs(conn)] == ["done", "done"]
    assert fetch_activity(conn, "berlin", "lau", Fakes(tmp_path).set_md5, ACT_SHA) == []


@pytest.mark.slow
def test_berlin_2018_history_run(tmp_path):
    """Real Geofabrik history (login-only, about 400 MB); data/ in the repo is the cache."""
    data = Path(__file__).parent.parent / "data"
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn)
        upsert_cities(conn, load_cities(CFG_DIR / "cities.yaml"))
        out = R.run_history(conn, CITY, range(2018, 2019), data_dir=data, config_dir=CFG_DIR)
        assert [o.status for o in out] == ["done"], out
        run_id = out[0].run_id
        row = conn.execute("SELECT osm_timestamp FROM runs WHERE id=?", (run_id,)).fetchone()
        assert row[0] == "2018-01-01T00:00:00Z"
        headline = conn.execute(
            "SELECT value FROM metrics WHERE run_id=? AND preset='ours_headline'", (run_id,)
        ).fetchone()
        assert headline is not None and headline[0] is not None
        tiers = conn.execute(
            "SELECT length_km FROM tier_lengths WHERE run_id=?", (run_id,)
        ).fetchall()
        assert tiers and all(km >= 0 for (km,) in tiers)
        diag = fetch_diagnostics(conn, run_id)
        assert diag["legacy_km"] > 0  # pitfall 7: opposite_* / sidewalk:*:bicycle ways classify
        print("SLOWNUMBERS", {"headline": headline[0], **diag})
        snap = next((data / "snapshots").glob("berlin_lau_*_20180101.osm.pbf"))
        ways = read_ways(snap).ways
        legacy_ids = {
            w.id
            for w in ways
            if any(p.startswith("opposite") for p in parts(w.tags.get("cycleway")))
            or any(k.startswith("sidewalk:") and k.endswith(":bicycle") for k in w.tags)
        }
        assert legacy_ids
        result = measure(ways, CLS, CITY.epsg)  # unclipped: every legacy way must get a tier
        by_way = {}
        for c in result.classified:
            by_way.setdefault(c.side.way_id, []).append(c)
        # a legacy-tagged way's cycling-tagged road sides all classify; none is unrecognised
        for wid in legacy_ids:
            for c in by_way.get(wid, []):
                if c.side.kind == "road_side" and (
                    "opposite" in c.side.tags.get("cycleway", "")
                    or any(k.startswith("sidewalk:") for k in c.side.tags)
                ):
                    assert c.tier is not None and "unknown_value" not in c.attrs, wid


def test_editing_activity_yaml_reruns_every_year_and_old_runs_are_not_selected(conn, tmp_path):
    import shutil

    cfg = tmp_path / "config"
    shutil.copytree(CFG_DIR, cfg)
    fakes = Fakes(tmp_path)
    years = range(2025, 2027)

    def run():
        return R.run_history(
            conn, CITY, years, data_dir=tmp_path, config_dir=cfg, deps=fakes.deps()
        )

    first = run()
    assert [o.status for o in first] == ["done", "done"]
    assert [o.status for o in run()] == ["skipped", "skipped"]
    old_sha = R.config_sha256(
        cfg / "classifier" / "v1.yaml", cfg / "presets.yaml", cfg / "activity.yaml"
    )
    old_act = R.file_sha256(cfg / "activity.yaml")
    (cfg / "activity.yaml").write_text((cfg / "activity.yaml").read_text() + "\n# edit\n")
    second = run()
    assert [o.status for o in second] == ["done", "done"]  # not skipped
    new_sha = R.config_sha256(
        cfg / "classifier" / "v1.yaml", cfg / "presets.yaml", cfg / "activity.yaml"
    )
    kw = dict(
        classifier_version=CLS.version,
        classifier_parameters=canonical_parameters(CLS.parameters.model_dump()),
        history_set_md5=fakes.set_md5,
    )
    got = history_runs(conn, "berlin", "lau", config_sha256=new_sha, **kw)
    assert set(got.values()) == {o.run_id for o in second}
    assert set(history_runs(conn, "berlin", "lau", config_sha256=old_sha, **kw).values()) == {
        o.run_id for o in first
    }
    new_act = R.file_sha256(cfg / "activity.yaml")
    assert new_act != old_act
    assert fetch_activity(conn, "berlin", "lau", fakes.set_md5, new_act)
    assert fetch_activity(conn, "berlin", "lau", fakes.set_md5, old_act)  # the old rows stay


# --- subareas (M6) ---

SUB_SHA = "a" * 64
WITH_SUBAREAS = CITY.model_copy(
    update={
        "subareas": SubareasConfig(
            source="osm_admin",
            admin_level=9,
            relations=[SubareaRelation(id=1, name="A", slug="a")],
        )
    }
)


def _sub_history(conn, tmp_path, *, city=WITH_SUBAREAS, kind="lau", load=None, checked=None):
    polys = [SubareaPolygon("a", "A", 1, box(-1e9, -1e9, 1e9, 1e9), SUB_SHA)]
    deps = Fakes(tmp_path).deps(
        load_subareas=load or (lambda c, d: polys),
        subarea_shas=lambda c, city_id: {"a": SUB_SHA} if checked is None else checked,
    )
    return R.run_history(
        conn,
        city,
        range(2019, 2021),
        data_dir=tmp_path,
        config_dir=CFG_DIR,
        deps=deps,
        boundary_kind=kind,
    )


def _sub_count(conn, run_id):
    return sum(
        conn.execute(f"SELECT COUNT(*) FROM {t} WHERE run_id=?", (run_id,)).fetchone()[0]
        for t in ("subarea_tier_lengths", "subarea_road_lengths")
    )


def _sha(conn, run_id):
    return conn.execute("SELECT subarea_sha FROM runs WHERE id=?", (run_id,)).fetchone()[0]


def test_history_runs_of_a_city_with_subareas_store_them(conn, tmp_path):
    outs = _sub_history(conn, tmp_path)
    assert [o.status for o in outs] == ["done", "done"]
    expected = subarea_set_sha([SubareaPolygon("a", "A", 1, None, SUB_SHA)])
    for o in outs:
        assert _sha(conn, o.run_id) == expected
        assert _sub_count(conn, o.run_id) > 0


def test_history_fua_and_plain_city_store_no_subareas(conn, tmp_path):
    for outs in (
        _sub_history(conn, tmp_path, kind="fua"),
        _sub_history(conn, tmp_path, city=without_subareas(CITY)),
    ):
        assert [o.status for o in outs] == ["done", "done"]
        for o in outs:
            assert _sha(conn, o.run_id) is None and _sub_count(conn, o.run_id) == 0


def test_history_missing_subarea_file_fails_each_year(conn, tmp_path):
    def load(city, d):
        raise FileNotFoundError("berlin: subarea 'a' has no boundary file x")

    outs = _sub_history(conn, tmp_path, load=load)
    assert [o.status for o in outs] == ["failed", "failed"]
    assert all("FileNotFoundError" in o.error for o in outs)


def test_history_sum_error_fails_the_year(conn, tmp_path, monkeypatch):
    small = [SubareaPolygon("a", "A", 1, box(0, 0, 1, 1), SUB_SHA)]
    real = R.attribute_subareas

    def drop_remainder(*a):  # a dropped part, as a bug in the attribution would leave
        return {k: v for k, v in real(*a).items() if k != REMAINDER_ID}

    monkeypatch.setattr(R, "attribute_subareas", drop_remainder)
    outs = _sub_history(conn, tmp_path, load=lambda c, d: small)
    assert [o.status for o in outs] == ["failed", "failed"]
    assert all("SubareaSumError" in o.error for o in outs)


def test_history_stale_subarea_file_fails_each_year(conn, tmp_path):
    outs = _sub_history(conn, tmp_path, checked={"a": "b" * 64})
    assert [o.status for o in outs] == ["failed", "failed"]
    assert all(SUB_SHA in o.error and "b" * 64 in o.error for o in outs)
