import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from velometer import osmium
from velometer.osmium import OsmiumError, merge_history, time_filter
from velometer.pipeline.history import SNAPSHOT_DATES, city_history, snapshot_at
from velometer.pipeline.read import read_ways
from velometer.sources.geofabrik import HistoryFile

pytestmark = pytest.mark.skipif(shutil.which("osmium") is None, reason="osmium-tool not installed")

FIX = Path(__file__).parent / "fixtures" / "history"
POLY = FIX / "boundary.geojson"
HF = HistoryFile("t", FIX / "mini.osh", "0" * 32, "computed", date(2026, 1, 1))


def _d(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=UTC)


def _ids(path):
    return {w.id for w in read_ways(path).ways}


def test_snapshot_dates_are_new_year_utc():
    assert SNAPSHOT_DATES(range(2018, 2021)) == [_d(2018), _d(2019), _d(2020)]


def test_time_filter_shows_each_way_as_it_was(tmp_path):
    src = FIX / "mini.osh"
    s2018 = time_filter(src, _d(2018), tmp_path / "a.osm.pbf")
    s2020 = time_filter(src, _d(2020), tmp_path / "b.osm.pbf")
    w18 = {w.id: w for w in read_ways(s2018).ways}
    w20 = {w.id: w for w in read_ways(s2020).ways}
    assert 1 in w18 and "segregated" not in w18[1].tags
    assert w20[1].tags["segregated"] == "yes"
    assert 3 not in w18 and 3 not in w20


def test_city_history_keeps_way_that_left_boundary(tmp_path):
    hist = city_history("t", "lau", [HF], "set", POLY, "b" * 64, tmp_path)
    snap = snapshot_at(hist, _d(2018), tmp_path)
    assert 2 in _ids(snap)  # inside in 2018, outside later
    assert 4 not in _ids(snap)  # never inside


def test_deleted_way_absent_after_deletion(tmp_path):
    hist = city_history("t", "lau", [HF], "set", POLY, "b" * 64, tmp_path)
    assert 3 in _ids(snapshot_at(hist, _d(2022), tmp_path))
    assert 3 not in _ids(snapshot_at(hist, _d(2023), tmp_path))


def test_city_history_and_snapshots_are_cached(tmp_path, monkeypatch):
    hist = city_history("t", "lau", [HF], "set12345", POLY, "b" * 64, tmp_path)
    snap = snapshot_at(hist, _d(2018), tmp_path)
    assert hist == tmp_path / "history" / "city" / "t_lau_set12345_bbbbbbbb.osh.pbf"
    assert snap == tmp_path / "snapshots" / "t_lau_set12345_bbbbbbbb_20180101.osm.pbf"
    calls = []
    monkeypatch.setattr(osmium, "_run", lambda *a: calls.append(a) or "")
    assert city_history("t", "lau", [HF], "set12345", POLY, "b" * 64, tmp_path) == hist
    assert snapshot_at(hist, _d(2018), tmp_path) == snap
    assert calls == []


def test_multiple_files_are_merged_before_extract(tmp_path):
    hf2 = HistoryFile("u", FIX / "mini.osh", "1" * 32, "computed", date(2026, 1, 1))
    hist = city_history("t", "lau", [HF, hf2], "set", POLY, "b" * 64, tmp_path)
    assert 2 in _ids(snapshot_at(hist, _d(2018), tmp_path))
    assert list(hist.parent.glob("*.merged*")) == []


def _versions(path, tmp_path):
    out = tmp_path / (path.name + ".xml.osh")
    osmium._run("cat", "--overwrite", "-o", str(out), str(path))
    import re

    return sorted(re.findall(r'<(node|way) id="(\d+)" version="(\d+)"', out.read_text()))


def test_merge_history_dedups_identical_versions(tmp_path):
    src = FIX / "mini.osh"
    merged = merge_history([src, src], tmp_path / "m.osh.pbf")
    assert _versions(merged, tmp_path) == _versions(src, tmp_path)


def test_failed_osmium_leaves_no_part_file(tmp_path):
    with pytest.raises(OsmiumError):
        time_filter(tmp_path / "missing.osh", _d(2018), tmp_path / "x.osm.pbf")
    with pytest.raises(OsmiumError):
        merge_history([tmp_path / "missing.osh"], tmp_path / "y.osh.pbf")
    assert list(tmp_path.iterdir()) == []
