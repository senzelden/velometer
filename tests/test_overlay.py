"""Berlin plan-network fetch and overlay (M8 spec §4.2-4.3, task 5).

Synthetic geometry in EPSG:25833 around (390 000, 5 820 000); no real OSM or network ids.
"""

import json
import sqlite3
from pathlib import Path

import pytest
from shapely import LineString, box
from typer.testing import CliRunner

from tests.sqlite_util import committing
from velometer.cli import app
from velometer.config import ConfigError, default_config_dir
from velometer.plans import berlin, overlay
from velometer.report.change import ChangeRefused, Side, check_tier_totals

CFG_DIR = default_config_dir()
CFG = overlay.OverlayConfig(version="overlay_v1", buffer_m=12, max_angle_deg=30, min_part_m=20)
X, Y = 390_000.0, 5_820_000.0
BOUNDARY = box(X - 5_000, Y - 5_000, X + 5_000, Y + 5_000)
NETWORK = [LineString([(X - 500, Y), (X + 500, Y)])]  # 1 km west-east


def _side(coords, tier="A", separate=False) -> Side:
    line = LineString(coords)
    return Side(tier, line, line.length / 1000, separate=separate)


def _km(sides, network=NETWORK, boundary=BOUNDARY, tier="A") -> float:
    return overlay.on_network_km(sides, network, boundary, CFG)[tier]


# --- config -----------------------------------------------------------------------------------


def test_overlay_v1_is_the_shipped_parameter_set():
    cfg = overlay.load_overlay_config(CFG_DIR / "plans", "overlay_v1")
    assert cfg == CFG


def test_an_overlay_file_whose_version_differs_from_its_name_is_refused(tmp_path):
    (tmp_path / "overlay_v2.yaml").write_text(
        "version: overlay_v1\nbuffer_m: 12\nmax_angle_deg: 30\nmin_part_m: 20\n"
    )
    with pytest.raises(ConfigError, match="overlay_v2"):
        overlay.load_overlay_config(tmp_path, "overlay_v2")


# --- network lines ----------------------------------------------------------------------------


def _feature(geometry, cls="Radvorrangnetz"):
    return {"type": "Feature", "properties": {"ist_radvorrangnetz": cls}, "geometry": geometry}


def test_network_lines_explode_multilines_drop_zero_length_parts_and_normalise_classes():
    multi = {
        "type": "MultiLineString",
        "coordinates": [
            [[X, Y], [X + 100, Y]],
            [[X + 200, Y], [X + 200, Y]],  # zero-length part
            [[X + 300, Y], [X + 400, Y]],
        ],
    }
    single = {"type": "LineString", "coordinates": [[X, Y + 50], [X + 50, Y + 50]]}
    doc = {
        "type": "FeatureCollection",
        "features": [_feature(multi), _feature(single, "Ergänzungsnetz")],
    }
    got = overlay.network_lines(doc)
    assert sorted(got) == ["ergaenzungsnetz", "vorrangnetz"]
    assert [ln.length for ln in got["vorrangnetz"]] == [100.0, 100.0]
    assert [ln.length for ln in got["ergaenzungsnetz"]] == [50.0]


def test_an_unknown_network_class_is_refused():
    doc = {"type": "FeatureCollection",
           "features": [_feature({"type": "LineString", "coordinates": [[X, Y], [X + 1, Y]]},
                                 "Sonstiges")]}  # fmt: skip
    with pytest.raises(ValueError, match="Sonstiges"):
        overlay.network_lines(doc)


# --- on-network km ----------------------------------------------------------------------------


def test_a_side_parallel_at_8_m_counts_fully():
    side = _side([(X - 200, Y + 8), (X + 200, Y + 8)])
    assert _km({(1, "self"): side}) == pytest.approx(0.4)


def test_a_side_parallel_at_20_m_does_not_count():
    assert _km({(1, "self"): _side([(X - 200, Y + 20), (X + 200, Y + 20)])}) == 0.0


def test_a_side_crossing_at_90_degrees_contributes_nothing():
    assert _km({(1, "self"): _side([(X, Y - 200), (X, Y + 200)])}) == 0.0


def test_a_side_at_45_degrees_contributes_nothing():
    assert _km({(1, "self"): _side([(X - 100, Y - 100), (X + 100, Y + 100)])}) == 0.0


def test_a_15_m_overlap_is_dropped():
    assert _km({(1, "self"): _side([(X, Y + 5), (X + 15, Y + 5)])}) == 0.0


def test_a_25_m_overlap_is_kept():
    assert _km({(1, "self"): _side([(X, Y + 5), (X + 25, Y + 5)])}) == pytest.approx(0.025)


def test_only_the_parallel_part_of_a_bent_side_counts():
    # 300 m along the network at 5 m, then 300 m straight away from it (north)
    side = _side([(X - 300, Y + 5), (X, Y + 5), (X, Y + 305)])
    assert _km({(1, "self"): side}) == pytest.approx(0.3, abs=0.011)


def test_a_multilinestring_network_feature_matches_on_each_part():
    doc = {"type": "FeatureCollection", "features": [_feature({
        "type": "MultiLineString",
        "coordinates": [[[X - 500, Y], [X - 100, Y]], [[X - 100, Y], [X - 100, Y]],
                        [[X + 100, Y], [X + 500, Y]]]})]}  # fmt: skip
    net = overlay.network_lines(doc)["vorrangnetz"]
    sides = {(1, "self"): _side([(X - 400, Y + 5), (X - 200, Y + 5)]),
             (2, "self"): _side([(X + 200, Y + 5), (X + 400, Y + 5)])}  # fmt: skip
    assert _km(sides, net) == pytest.approx(0.4)


def test_a_side_half_outside_the_boundary_counts_its_inside_part():
    boundary = box(X - 5_000, Y - 5_000, X, Y + 5_000)  # ends at x = X
    side = _side([(X - 200, Y + 8), (X + 200, Y + 8)])
    assert _km({(1, "self"): side}, boundary=boundary) == pytest.approx(0.2)


def test_tiers_a_and_b_are_kept_apart_and_c_to_e_ignored():
    sides = {(1, "left"): _side([(X - 200, Y + 6), (X + 200, Y + 6)], "A"),
             (1, "right"): _side([(X - 200, Y + 6), (X + 200, Y + 6)], "A"),
             (2, "self"): _side([(X - 100, Y - 6), (X + 100, Y - 6)], "B"),
             (3, "self"): _side([(X - 100, Y - 3), (X + 100, Y - 3)], "C")}  # fmt: skip
    got = overlay.on_network_km(sides, NETWORK, BOUNDARY, CFG)
    assert got == {"A": pytest.approx(0.8), "B": pytest.approx(0.2)}  # per_side: both road sides


def test_no_sides_or_no_network_gives_zero_for_both_tiers():
    assert overlay.on_network_km({}, NETWORK, BOUNDARY, CFG) == {"A": 0.0, "B": 0.0}
    side = {(1, "self"): _side([(X, Y), (X + 100, Y)])}
    assert overlay.on_network_km(side, [], BOUNDARY, CFG) == {"A": 0.0, "B": 0.0}


# --- totals guard -----------------------------------------------------------------------------


def test_a_totals_mismatch_aborts_naming_the_tier_and_both_values():
    with pytest.raises(ChangeRefused, match=r"run 7: tier B recomputed 2\.000 km vs stored 2\.500"):
        check_tier_totals("7", {"A": 1.0, "B": 2.0}, {"A": 1.0, "B": 2.5})
    check_tier_totals("7", {"A": 1.0}, {"A": 1.005, "C": 0.004})  # within 0.01 km


# --- fetch ------------------------------------------------------------------------------------


def _fc(ids):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": i, "properties": {"gisid": i, "projektnummer": i},
             "geometry": {"type": "LineString", "coordinates": [[X, Y], [X + 1, Y]]}}
            for i in ids
        ],
    }  # fmt: skip


def test_fetch_pages_each_layer_until_a_short_page_and_records_url_licence_and_time(tmp_path):
    cfg = berlin.load_plan_sources(CFG_DIR / "plans" / "sources.yaml", "berlin")
    cfg = cfg.model_copy(update={"page_size": 2})
    calls = []

    def fake(url, params):
        calls.append((url, dict(params)))
        start, count = int(params["startIndex"]), int(params["count"])
        n = 5 if "radverkehrsnetz" in url else 2
        return json.dumps(_fc(range(start, min(start + count, n)))).encode()

    res = berlin.fetch_layers(cfg, tmp_path, fetch=fake)
    assert sorted(res.paths) == ["radverkehrsmassnahmen", "radverkehrsnetz"]
    netz = [p for u, p in calls if u.endswith("/radverkehrsnetz")]
    assert [p["startIndex"] for p in netz] == ["0", "2", "4"]
    massn = [p for u, p in calls if u.endswith("/radverkehrsmassnahmen")]
    assert [p["startIndex"] for p in massn] == ["0", "2"]  # a full last page needs one more
    for p in netz + massn:
        assert p["outputFormat"] == "application/json"
        assert p["srsName"] == "EPSG:25833"
        assert p["request"] == "GetFeature" and p["service"] == "WFS"
    doc = json.loads(res.paths["radverkehrsnetz"].read_text())
    assert [f["properties"]["gisid"] for f in doc["features"]] == [0, 1, 2, 3, 4]
    meta = json.loads((tmp_path / "retrieved.json").read_text())
    assert meta["retrieved_at"] == res.retrieved_at and res.retrieved_at.endswith("Z")
    assert meta["licence"] == "dl-de-zero-2.0"
    assert meta["layers"]["radverkehrsnetz"]["url"] == (
        "https://gdi.berlin.de/services/wfs/radverkehrsnetz"
    )
    assert meta["layers"]["radverkehrsnetz"]["features"] == 5


def test_fetch_refuses_a_page_count_below_the_servers_total(tmp_path):
    cfg = berlin.load_plan_sources(CFG_DIR / "plans" / "sources.yaml", "berlin")

    def fake(url, params):
        return json.dumps({**_fc([1]), "numberMatched": 3}).encode()

    with pytest.raises(ValueError, match="numberMatched 3"):
        berlin.fetch_layers(cfg, tmp_path, fetch=fake)
    assert not (tmp_path / "retrieved.json").exists()


# --- CLI ----------------------------------------------------------------------------------------

needs_osmium = pytest.mark.skipif(
    __import__("shutil").which("osmium") is None, reason="osmium-tool not installed"
)


def _network(data_dir: Path, vorrang_coords) -> None:
    out = data_dir / "plans" / "berlin"
    out.mkdir(parents=True)
    far = [[X + 9_000, Y + 9_000], [X + 9_500, Y + 9_000]]
    doc = {"type": "FeatureCollection", "features": [
        _feature({"type": "MultiLineString", "coordinates": [vorrang_coords]}),
        _feature({"type": "LineString", "coordinates": far}, "Ergänzungsnetz")]}  # fmt: skip
    (out / "radverkehrsnetz.geojson").write_text(json.dumps(doc))
    (out / "retrieved.json").write_text(json.dumps({"retrieved_at": "2026-10-07T10:00:00Z"}))


def _way1_offset(m: float) -> list[list[float]]:
    """Fixture way 9000000001 (tier A in both runs) projected to EPSG:25833, shifted north."""
    from velometer.pipeline.geometry import Projector
    from velometer.pipeline.read import read_ways

    fix = Path(__file__).parent / "fixtures" / "change" / "to.osm"
    way = next(w for w in read_ways(fix).ways if w.id == 9_000_000_001)
    return [[x, y + m] for x, y in Projector(25833).line(way.coords).coords]


def _overlay_rows(db_path):
    c = sqlite3.connect(db_path)
    rows = c.execute(
        "SELECT run_id, network_class, tier, mapped_km, network_km, overlay_version, "
        "network_retrieved_at FROM plan_overlay ORDER BY run_id, network_class, tier"
    ).fetchall()
    c.close()
    return rows


@needs_osmium
def test_plans_overlay_checks_totals_and_stores_rows_per_run_class_and_tier(tmp_path):
    from tests.test_cli import _change_db

    db_path, cfg, data_dir, run_from, run_to = _change_db(tmp_path)
    _network(data_dir, _way1_offset(5))
    args = ["plans", "overlay", "berlin", "--version", "overlay_v1", "--data", str(data_dir),
            "--db", str(db_path), "--config-dir", str(cfg)]  # fmt: skip
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    rows = _overlay_rows(db_path)
    assert {r[0] for r in rows} == {run_from, run_to}
    assert len(rows) == 2 * 2 * 2  # runs x classes x tiers A, B
    by = {(r[0], r[1], r[2]): r for r in rows}
    for run_id in (run_from, run_to):
        assert by[run_id, "vorrangnetz", "A"][3] == pytest.approx(0.2037, abs=0.001)
        assert by[run_id, "vorrangnetz", "B"][3] == 0.0
        assert by[run_id, "ergaenzungsnetz", "A"][3] == 0.0
        assert by[run_id, "vorrangnetz", "A"][4] == pytest.approx(0.2037, abs=0.001)
        assert by[run_id, "ergaenzungsnetz", "A"][4] == pytest.approx(0.5)
    assert {r[5] for r in rows} == {"overlay_v1"}
    assert {r[6] for r in rows} == {"2026-10-07T10:00:00Z"}


@needs_osmium
def test_plans_overlay_aborts_on_a_totals_mismatch_and_writes_nothing(tmp_path):
    from tests.test_cli import _change_db

    db_path, cfg, data_dir, run_from, _ = _change_db(tmp_path)
    _network(data_dir, _way1_offset(5))
    c = sqlite3.connect(db_path)
    c.execute(
        "UPDATE tier_lengths SET length_km = length_km + 1 WHERE run_id=? AND tier='A' "
        "AND length_basis='per_side'",
        (run_from,),
    )
    c.commit()
    c.close()
    args = ["plans", "overlay", "berlin", "--data", str(data_dir), "--db", str(db_path),
            "--config-dir", str(cfg)]  # fmt: skip
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert f"run {run_from}: tier A recomputed" in result.output
    assert "vs stored" in result.output
    assert _overlay_rows(db_path) == []


@needs_osmium
def test_plans_overlay_without_a_fetched_network_says_to_fetch(tmp_path):
    from tests.test_cli import _change_db

    db_path, cfg, data_dir, *_ = _change_db(tmp_path)
    args = ["plans", "overlay", "berlin", "--data", str(data_dir), "--db", str(db_path),
            "--config-dir", str(cfg)]  # fmt: skip
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert "velometer plans fetch berlin" in result.output


# --- overlay_v2: a wider buffer for separately mapped ways ------------------------------------

V2 = overlay.OverlayConfig(
    version="overlay_v2", buffer_m=12, buffer_separate_m=25, max_angle_deg=30, min_part_m=20
)


def test_overlay_v2_is_the_shipped_parameter_set():
    assert overlay.load_overlay_config(CFG_DIR / "plans", "overlay_v2") == V2


def test_a_v1_file_without_a_separate_buffer_uses_buffer_m_for_both():
    assert CFG.buffer_separate_m is None
    assert CFG.separate_buffer_m == 12
    assert V2.separate_buffer_m == 25


def test_a_separate_way_at_20_m_counts_under_v2_and_not_under_v1():
    sides = {(1, "self"): _side([(X - 200, Y + 20), (X + 200, Y + 20)], separate=True)}
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, CFG)["A"] == 0.0
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V2)["A"] == pytest.approx(0.4)


def test_a_centreline_tagged_side_at_20_m_counts_under_neither():
    # the overlay reads `Side.separate`, never the side key; which sides are separate (road
    # sides and cycle streets are not) is `test_classified_sides_mark_only_ways_off_...`
    sides = {(1, "left"): _side([(X - 200, Y + 20), (X + 200, Y + 20)], separate=False)}
    for cfg in (CFG, V2):
        assert overlay.on_network_km(sides, NETWORK, BOUNDARY, cfg)["A"] == 0.0


def test_a_separate_way_at_30_m_counts_under_neither():
    sides = {(1, "self"): _side([(X - 200, Y + 30), (X + 200, Y + 30)], separate=True)}
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V2)["A"] == 0.0


def test_on_network_km_splits_centreline_and_separate_km():
    sides = {(1, "left"): _side([(X - 200, Y + 6), (X + 200, Y + 6)]),
             (2, "self"): _side([(X - 100, Y + 20), (X + 100, Y + 20)], "B", True)}  # fmt: skip
    got = overlay.on_network_km_by_geometry(sides, NETWORK, BOUNDARY, V2)
    assert got == {("A", "centreline"): pytest.approx(0.4), ("A", "separate"): 0.0,
                   ("B", "centreline"): 0.0, ("B", "separate"): pytest.approx(0.2)}  # fmt: skip


def test_overlay_facts_read_the_latest_overlay_version(fixture_db, tmp_path):
    from velometer.content.facts import evaluate
    from velometer.db import OverlayRow, replace_plan_overlay

    db_path, _cfg, _conn, data = fixture_db
    with committing(db_path) as c:
        run_id, ts = c.execute(
            "SELECT id, osm_timestamp FROM runs WHERE city_id='berlin' AND boundary_kind='lau' "
            "ORDER BY osm_timestamp LIMIT 1"
        ).fetchone()

    def row(version, km):
        return OverlayRow(run_id, "berlin", "vorrangnetz", "A", km, 873.1, version, "t")

    rows = [row("overlay_v1", 10.0), row("overlay_v2", 20.0)]
    c = sqlite3.connect(db_path)
    for v, row_v in (("overlay_v1", rows[0]), ("overlay_v2", rows[1])):
        replace_plan_overlay(c, "berlin", v, [row_v])
    c.close()
    assert evaluate(f"overlay.berlin.vorrangnetz.{ts[:10]}.ab_km", data, tmp_path) == 20.0


def test_classified_sides_mark_only_ways_off_the_carriageway_as_separate():
    from velometer.config import load_classifier
    from velometer.pipeline.types import WayRecord
    from velometer.report.change import classified_sides

    cfg = load_classifier(CFG_DIR / "classifier" / "v4.yaml")
    line = ((13.40, 52.50), (13.41, 52.50))
    tags = [{"highway": "cycleway"}, {"highway": "residential", "bicycle_road": "yes"},
            {"highway": "secondary", "cycleway:both": "track"}]  # fmt: skip
    ways = [WayRecord(9_000_000_101 + i, t, line) for i, t in enumerate(tags)]
    sides = classified_sides(ways, cfg, 25833, box(300_000, 5_700_000, 500_000, 5_900_000))
    got = {(k[0] - 9_000_000_100, k[1]): s.separate for k, s in sides.items()}
    assert got[1, "self"] is True
    assert got[2, "self"] is False  # a cycle street is the road centreline
    assert got[3, "left"] is False and got[3, "right"] is False


# --- overlay_v3: min_part_m over touching way-sides of one tier --------------------------------

V3 = V2.model_copy(update={"version": "overlay_v3", "merge_scope": "tier"})


def test_overlay_v3_is_v2_with_the_tier_merge_scope():
    assert overlay.load_overlay_config(CFG_DIR / "plans", "overlay_v3") == V3
    assert CFG.merge_scope == "side" and V2.merge_scope == "side"


def _chain(n, length, tiers, y=Y + 5, separate=True):
    """`n` ways of `length` m end to end along the network, the i-th of tier tiers[i]."""
    return {(i, "self"): _side([(X + i * length, y), (X + (i + 1) * length, y)], tiers[i],
                               separate)
            for i in range(n)}  # fmt: skip


def test_three_8_m_ways_end_to_end_count_24_m_under_v3_and_nothing_under_v2():
    sides = _chain(3, 8, "AAA")
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V2)["A"] == 0.0
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V3)["A"] == pytest.approx(0.024)


def test_touching_short_ways_of_different_tiers_do_not_merge():
    assert overlay.on_network_km(_chain(2, 12, "AB"), NETWORK, BOUNDARY, V3) == {
        "A": 0.0,
        "B": 0.0,
    }


def test_both_road_sides_of_one_short_way_do_not_add_up_to_a_part():
    line = [(X, Y + 3), (X + 12, Y + 3)]
    sides = {(1, "left"): _side(line), (1, "right"): _side(line)}  # 12 m of extent, 24 m per_side
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V3)["A"] == 0.0


def test_a_merged_v3_part_keeps_per_side_km():
    a, b = [(X, Y + 3), (X + 12, Y + 3)], [(X + 12, Y + 3), (X + 24, Y + 3)]
    sides = {(1, "left"): _side(a), (1, "right"): _side(a),
             (2, "left"): _side(b), (2, "right"): _side(b)}  # fmt: skip
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V3)["A"] == pytest.approx(0.048)


def test_v1_and_v2_keep_the_per_side_scope_on_the_same_chain():
    sides = _chain(3, 8, "AAA", separate=False)
    for cfg in (CFG, V2):
        assert overlay.on_network_km(sides, NETWORK, BOUNDARY, cfg)["A"] == 0.0


def test_short_ways_that_touch_only_across_network_classes_do_not_merge():
    # way 1 follows a west-east line of one class; way 2 continues it end to start, turning
    # north along a line of the other class (each fails the angle test on the other's line)
    west_east = [LineString([(X - 50, Y), (X + 17, Y)])]
    south_north = [LineString([(X + 17, Y), (X + 17, Y + 60)])]
    sides = {(1, "self"): _side([(X, Y + 5), (X + 12, Y + 5)], separate=True),
             (2, "self"): _side([(X + 12, Y + 5), (X + 12, Y + 17)], separate=True)}  # fmt: skip
    assert overlay.on_network_km(sides, west_east, BOUNDARY, V3)["A"] == 0.0
    assert overlay.on_network_km(sides, south_north, BOUNDARY, V3)["A"] == 0.0
    both = west_east + south_north  # the same chain on one class's lines does merge
    assert overlay.on_network_km(sides, both, BOUNDARY, V3)["A"] == pytest.approx(0.024)


def test_short_ways_with_a_gap_between_them_do_not_merge():
    sides = {(1, "self"): _side([(X, Y + 5), (X + 12, Y + 5)], separate=True),
             (2, "self"): _side([(X + 14, Y + 5), (X + 26, Y + 5)], separate=True)}  # fmt: skip
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V3)["A"] == 0.0


def test_a_short_way_touching_a_long_kept_way_of_its_tier_counts_under_v3():
    sides = {(1, "self"): _side([(X, Y + 5), (X + 50, Y + 5)], separate=True),
             (2, "self"): _side([(X + 50, Y + 5), (X + 58, Y + 5)], separate=True)}  # fmt: skip
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V2)["A"] == pytest.approx(0.050)
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V3)["A"] == pytest.approx(0.058)


def test_a_separate_way_split_into_short_osm_ways_counts_fully_only_under_v3():
    # a cycleway 20 m beside the network road, split at crossings and attribute changes; the
    # second piece bends, so the chain is not straight
    xs = [0, 15, 22, 52, 61, 75, 100]
    coords = [(X + x, Y + 20 + (1.5 if x == 22 else 0)) for x in xs]
    sides = {(i, "self"): _side([coords[i], coords[i + 1]], separate=True)
             for i in range(len(xs) - 1)}  # fmt: skip
    total = sum(s.km for s in sides.values())
    long_ones = sum(s.km for s in sides.values() if s.km >= 0.020)
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, CFG)["A"] == 0.0  # 20 m > 12 m
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V2)["A"] == pytest.approx(long_ones)
    assert overlay.on_network_km(sides, NETWORK, BOUNDARY, V3)["A"] == pytest.approx(total)
    assert total > long_ones


# --- overlay_v4: matches end at a free end of a network line -----------------------------------

V4 = V3.model_copy(update={"version": "overlay_v4", "clip_free_ends": True})
# the network turns at a junction: a stem from the south ends at (X, Y), an arm leaves it east;
# the street continues west of the junction off the network
TURN = [LineString([(X, Y - 300), (X, Y)]), LineString([(X, Y), (X + 300, Y)])]
OVERRUN = {(1, "self"): _side([(X + 300, Y + 5), (X + 600, Y + 5)], separate=True)}
ON_TURN = {(1, "self"): _side([(X - 100, Y + 5), (X + 200, Y + 5)], separate=True)}


def test_overlay_v4_is_v3_with_free_ends_clipped():
    assert overlay.load_overlay_config(CFG_DIR / "plans", "overlay_v4") == V4
    assert not (CFG.clip_free_ends or V2.clip_free_ends or V3.clip_free_ends)


def test_a_side_overrunning_a_free_network_end_is_clipped_at_the_end_under_v4():
    # NETWORK ends at X + 500; 200 m of the side lie alongside it, 100 m past its end
    assert overlay.on_network_km(OVERRUN, NETWORK, BOUNDARY, V4)["A"] == pytest.approx(0.2)


def test_a_side_on_the_street_continuing_past_a_network_turn_counts_only_along_the_arm():
    # the 100 m west of the junction lie on the continuing street, past the arm's start; the
    # stem's end is no continuation of the arm (90 degrees), so the arm's start is a free end
    assert overlay.on_network_km(ON_TURN, TURN, BOUNDARY, V4)["A"] == pytest.approx(0.2)
    west = {(1, "self"): _side([(X - 100, Y + 5), (X - 1, Y + 5)], separate=True)}
    assert overlay.on_network_km(west, TURN, BOUNDARY, V4)["A"] == 0.0


_BEND = (0.9397, 0.3420)  # cos, sin of 20 degrees


@pytest.mark.parametrize(
    ("network", "side"),
    [
        # two edges with a 0.4 m gap at the joint; the piece over X + 0..10 has its midpoint in it
        ([LineString([(X - 500, Y), (X + 4.8, Y)]), LineString([(X + 5.2, Y), (X + 500, Y)])],
         [(X - 100, Y - 20), (X + 100, Y - 20)]),
        # a 20 degree bend at X + 5 (within max_angle_deg), the side 20 m off on its outer side:
        # pieces at the outer corner project past the first edge's end and before the second's
        # start
        ([LineString([(X - 500, Y), (X + 5, Y)]),
          LineString([(X + 5, Y), (X + 5 + 470 * _BEND[0], Y + 470 * _BEND[1])])],
         [(X - 96.7, Y - 20), (X + 8.527, Y - 20),
          (X + 8.527 + 100 * _BEND[0], Y - 20 + 100 * _BEND[1])]),
    ],
    ids=["gap", "bend"],
)  # fmt: skip
def test_a_side_across_an_interior_joint_keeps_its_full_length_under_v4(network, side):
    sides = {(1, "self"): _side(side, separate=True)}
    v3 = overlay.on_network_km(sides, network, BOUNDARY, V3)["A"]
    assert v3 == pytest.approx(sides[1, "self"].km)
    assert overlay.on_network_km(sides, network, BOUNDARY, V4)["A"] == pytest.approx(v3)


def test_v1_to_v3_still_count_past_a_free_end_and_a_turn():
    # values from before overlay_v4 existed (any piece within its buffer of a line matches)
    for sides, network in ((OVERRUN, NETWORK), (ON_TURN, TURN)):
        got = [overlay.on_network_km(sides, network, BOUNDARY, c)["A"] for c in (CFG, V2, V3)]
        assert got == [pytest.approx(0.22), pytest.approx(0.23), pytest.approx(0.23)]


# --- default overlay version ------------------------------------------------------------------


def test_the_default_overlay_version_is_the_highest_numbered_file(tmp_path):
    for v in ("overlay_v2", "overlay_v10", "overlay_v9"):
        (tmp_path / f"{v}.yaml").write_text("")
    (tmp_path / "overlay_vx.yaml").write_text("")
    assert overlay.latest_overlay_version(tmp_path) == "overlay_v10"


def test_no_overlay_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="overlay_v"):
        overlay.latest_overlay_version(tmp_path)


@needs_osmium
def test_plans_overlay_without_a_version_runs_the_highest_numbered_file(tmp_path):
    from tests.test_cli import _change_db

    db_path, cfg, data_dir, *_ = _change_db(tmp_path)
    _network(data_dir, _way1_offset(5))
    v3 = (cfg / "plans" / "overlay_v3.yaml").read_text()
    (cfg / "plans" / "overlay_v12.yaml").write_text(v3.replace("overlay_v3", "overlay_v12"))
    args = ["plans", "overlay", "berlin", "--data", str(data_dir), "--db", str(db_path),
            "--config-dir", str(cfg)]  # fmt: skip
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert {r[5] for r in _overlay_rows(db_path)} == {"overlay_v12"}


# --- WFS paging guards ------------------------------------------------------------------------


def _one_layer_cfg():
    cfg = berlin.load_plan_sources(CFG_DIR / "plans" / "sources.yaml", "berlin")
    layer = cfg.layers["radverkehrsnetz"]
    return cfg.model_copy(update={"page_size": 2, "layers": {"radverkehrsnetz": layer}})


def test_fetch_sorts_on_the_layers_stable_id(tmp_path):
    cfg = berlin.load_plan_sources(CFG_DIR / "plans" / "sources.yaml", "berlin")
    seen = {}

    def fake(url, params):
        seen[url.rsplit("/", 1)[1]] = params["sortBy"]
        return json.dumps(_fc([])).encode()

    berlin.fetch_layers(cfg, tmp_path, fetch=fake)
    assert seen == {"radverkehrsnetz": "gisid", "radverkehrsmassnahmen": "projektnummer"}


@pytest.mark.parametrize("matched", [5, None])
def test_a_server_ignoring_start_index_is_refused_not_looped(tmp_path, matched):
    calls = []

    def fake(url, params):
        calls.append(params["startIndex"])
        return json.dumps(
            {**_fc([0, 1]), **({"numberMatched": matched} if matched else {})}
        ).encode()

    with pytest.raises(ValueError, match="repeated"):
        berlin.fetch_layers(_one_layer_cfg(), tmp_path, fetch=fake)
    assert len(calls) == 2
    assert not (tmp_path / "retrieved.json").exists()


def test_a_server_capping_count_is_paged_to_number_matched(tmp_path):
    cfg = _one_layer_cfg().model_copy(update={"page_size": 5})

    def fake(url, params):
        start = int(params["startIndex"])
        return json.dumps({**_fc(range(start, min(start + 2, 7))), "numberMatched": 7}).encode()

    res = berlin.fetch_layers(cfg, tmp_path, fetch=fake)
    doc = json.loads(res.paths["radverkehrsnetz"].read_text())
    assert [f["properties"]["gisid"] for f in doc["features"]] == list(range(7))


def test_a_final_count_other_than_number_matched_is_refused(tmp_path):
    def fake(url, params):
        start = int(params["startIndex"])
        return json.dumps({**_fc(range(start, min(start + 2, 3))), "numberMatched": 4}).encode()

    with pytest.raises(ValueError, match="numberMatched 4"):
        berlin.fetch_layers(_one_layer_cfg(), tmp_path, fetch=fake)


def test_paging_stops_at_the_page_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(berlin, "MAX_PAGES", 3)

    def fake(url, params):
        start = int(params["startIndex"])
        return json.dumps(_fc([start, start + 1])).encode()  # endless full pages of new ids

    with pytest.raises(ValueError, match="3 pages"):
        berlin.fetch_layers(_one_layer_cfg(), tmp_path, fetch=fake)


def test_duplicate_ids_within_one_page_are_refused(tmp_path):
    def fake(url, params):
        return json.dumps(_fc([0, 0])).encode()  # one page, the same gisid twice

    with pytest.raises(ValueError, match="gisid 0 more than once"):
        berlin.fetch_layers(_one_layer_cfg(), tmp_path, fetch=fake)
    assert not (tmp_path / "retrieved.json").exists()


@pytest.mark.parametrize("null", [False, True], ids=["missing", "json-null"])
def test_a_feature_without_the_sort_property_is_refused_naming_it(tmp_path, null):
    # M8-19: a JSON null was reported as a missing property; the message covers both
    def fake(url, params):
        doc = _fc([0, 1])
        if null:
            doc["features"][1]["properties"]["gisid"] = None
        else:
            del doc["features"][1]["properties"]["gisid"]
        return json.dumps(doc).encode()

    with pytest.raises(ValueError, match="no value for its 'gisid' property") as e:
        berlin.fetch_layers(_one_layer_cfg(), tmp_path, fetch=fake)
    assert "repeated" not in str(e.value)


def test_the_wfs_fetch_sends_the_velometer_user_agent(agent_server):
    from velometer.sources.download import user_agent

    url, agents = agent_server
    berlin._http_get(url, {"a": "b"})
    assert agents == [user_agent()]
