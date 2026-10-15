"""`velometer report change`: way-side changes between two done runs (spec §4.4, decisions 14-17).

The fixtures in tests/fixtures/change/ use synthetic ids (ways 9000000001.., nodes 9100000001..),
never real OSM ids, inside a 1 km box near Berlin.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from shapely import Polygon, box

from velometer.config import REMAINDER_ID, default_config_dir, load_cities, load_classifier
from velometer.db import RunKey, create_schema, open_db, start_run, upsert_cities
from velometer.pipeline.extract import snapshot_name
from velometer.pipeline.geometry import Projector
from velometer.pipeline.history import city_history_name, snapshot_at
from velometer.pipeline.measure import measure
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord
from velometer.report import change as ch
from velometer.run import snapshot_path_for_run
from velometer.subareas import SubareaPolygon

FIX = Path(__file__).parent / "fixtures" / "change"
CFG_DIR = default_config_dir()
# v4: `highway=cycleway` + `foot=yes` is B (decision 9), so way 9000000004 retiers A -> B
CFG = load_classifier(CFG_DIR / "classifier" / "v4.yaml")
EPSG = 25833
BOUNDARY = box(380_000, 5_810_000, 410_000, 5_840_000)  # EPSG:25833, around Berlin
W = 9_000_000_000  # way id offset of the fixtures
FROM = read_ways(FIX / "from.osm").ways
TO = read_ways(FIX / "to.osm").ways


def _km(ways, way_id: int) -> float:
    way = next(w for w in ways if w.id == way_id)
    return Projector(EPSG).line(way.coords).length / 1000


def _sub(sid: str, polygon) -> SubareaPolygon:
    return SubareaPolygon(sid, sid.title(), 1, polygon, "x" * 64)


@pytest.fixture(scope="module")
def result() -> ch.ChangeResult:
    return ch.compute_change(FROM, TO, CFG, EPSG, BOUNDARY, [])


def _rows(result, category):
    return [r for r in result.rows if r.category == category]


def _ids(row) -> set[int]:
    return {i for i in (row.way_id_from, row.way_id_to) if i is not None}


def test_identical_way_has_no_row(result):
    assert not [r for r in result.rows if W + 1 in _ids(r)]


def test_way_only_in_from_is_lost(result):
    (row,) = _rows(result, "lost")
    assert (row.way_id_from, row.way_id_to, row.side) == (W + 2, None, "self")
    assert (row.tier_from, row.tier_to) == ("A", None)
    assert row.km == pytest.approx(_km(FROM, W + 2))


def test_way_only_in_to_far_from_everything_is_gained(result):
    (row,) = _rows(result, "gained")
    assert (row.way_id_from, row.way_id_to) == (None, W + 3)
    assert (row.tier_from, row.tier_to) == (None, "A")
    assert row.km == pytest.approx(_km(TO, W + 3))


def test_retagged_way_is_retiered_with_the_changed_tags(result):
    (row,) = _rows(result, "retiered")
    assert (row.way_id_from, row.way_id_to) == (W + 4, W + 4)
    assert (row.tier_from, row.tier_to) == ("A", "B")
    assert row.tags_changed == {"foot": (None, "yes")}
    assert row.km == pytest.approx(_km(TO, W + 4))


def test_way_replaced_by_two_covering_ways_is_redrawn_not_churn(result):
    rows = _rows(result, "redrawn")
    assert {r.way_id_to for r in rows} == {W + 6, W + 7}
    assert {r.way_id_from for r in rows} == {W + 5}
    assert all((r.tier_from, r.tier_to) == ("A", "A") for r in rows)
    assert sum(r.km for r in rows) == pytest.approx(_km(TO, W + 6) + _km(TO, W + 7))
    churn = _rows(result, "lost") + _rows(result, "gained")
    assert not [r for r in churn if _ids(r) & {W + 5, W + 6, W + 7}]


def test_extended_way_is_geometry_with_the_length_change(result):
    (row,) = _rows(result, "geometry")
    assert (row.way_id_from, row.way_id_to) == (W + 8, W + 8)
    assert (row.tier_from, row.tier_to) == ("A", "A")
    assert row.km == pytest.approx(_km(TO, W + 8) - _km(FROM, W + 8))
    assert row.km == pytest.approx(0.050, abs=0.002)


def test_a_redraw_needs_the_same_tier():
    # way 9000000006/7 as tier B (foot=yes) do not redraw the tier-A way 9000000005
    to = [
        w if w.id not in (W + 6, W + 7) else type(w)(w.id, {**w.tags, "foot": "yes"}, w.coords)
        for w in TO
    ]
    got = ch.compute_change(FROM, to, CFG, EPSG, BOUNDARY, [])
    assert not _rows(got, "redrawn")
    assert {r.way_id_from for r in _rows(got, "lost")} == {W + 2, W + 5}
    assert {r.way_id_to for r in _rows(got, "gained")} == {W + 3, W + 6, W + 7}


def _stored(ways, boundary=BOUNDARY) -> dict[str, float]:
    """Per_side tier sums (A-E) as `measure` stores them for a run."""
    stored: dict[str, float] = {}
    for t in measure(ways, CFG, EPSG, boundary=boundary).tier_lengths:
        if t.length_basis == "per_side" and t.tier != "excluded":
            stored[t.tier] = stored.get(t.tier, 0.0) + t.length_km
    return stored


def _way(way_id: int, lons: tuple[float, float], lat: float, **tags) -> WayRecord:
    return WayRecord(way_id, tags, ((lons[0], lat), (lons[1], lat)))


def test_a_short_stub_does_not_hide_a_long_loss():
    # a 30 m stub drawn on a deleted 400 m path lies wholly within 15 m of it, but covers
    # under 80 % of it: the path is lost and the stub gained (decision 15 needs both ways)
    long = _way(W + 101, (13.400, 13.4059), 52.52, highway="cycleway")
    stub = _way(W + 102, (13.400, 13.40044), 52.52, highway="cycleway")
    got = ch.compute_change([long], [stub], CFG, EPSG, BOUNDARY, [])
    assert [(r.category, r.way_id_from, r.way_id_to) for r in got.rows] == [
        ("gained", None, W + 102),
        ("lost", W + 101, None),
    ]


def test_road_sides_redraw_only_the_same_side():
    # the old road has a track on both sides; the split new ways only on the right. Both sides
    # carry the centreline, so without the side rule the right-side ways would hide the left loss
    old = _way(W + 201, (13.400, 13.4059), 52.53, highway="secondary", **{"cycleway:both": "track"})
    new = [
        _way(W + 202, (13.400, 13.403), 52.53, highway="secondary", **{"cycleway:right": "track"}),
        _way(W + 203, (13.403, 13.4059), 52.53, highway="secondary", **{"cycleway:right": "track"}),
    ]
    got = ch.compute_change([old], new, CFG, EPSG, BOUNDARY, [])
    rows = {(r.category, r.way_id_from, r.way_id_to, r.side) for r in got.rows}
    assert rows == {
        ("redrawn", W + 201, W + 202, "right"),
        ("redrawn", W + 201, W + 203, "right"),
        ("lost", W + 201, None, "left"),
    }


def test_a_way_split_into_the_old_id_and_a_new_id_is_redrawn_not_gained():
    # the common OSM split: the old id keeps the west half, the east half gets a new id. The
    # new piece lies on the old geometry, so it is a redraw (decision 15), not a new mapping
    old = _way(W + 301, (13.400, 13.4059), 52.54, highway="cycleway")
    kept = _way(W + 301, (13.400, 13.403), 52.54, highway="cycleway")
    piece = _way(W + 302, (13.403, 13.4059), 52.54, highway="cycleway")
    got = ch.compute_change([old], [kept, piece], CFG, EPSG, BOUNDARY, [])
    rows = {(r.category, r.way_id_from, r.way_id_to, r.tier_from, r.tier_to) for r in got.rows}
    assert rows == {
        ("geometry", W + 301, W + 301, "A", "A"),
        ("redrawn", W + 301, W + 302, "A", "A"),
    }
    (redrawn,) = _rows(got, "redrawn")
    assert redrawn.km == pytest.approx(_km([piece], W + 302))


def test_split_pieces_of_one_way_are_all_redrawn():
    old = _way(W + 311, (13.400, 13.4059), 52.545, highway="cycleway")
    new = [
        _way(W + 311, (13.400, 13.402), 52.545, highway="cycleway"),
        _way(W + 312, (13.402, 13.404), 52.545, highway="cycleway"),
        _way(W + 313, (13.404, 13.4059), 52.545, highway="cycleway"),
    ]
    got = ch.compute_change([old], new, CFG, EPSG, BOUNDARY, [])
    assert {(r.way_id_from, r.way_id_to) for r in _rows(got, "redrawn")} == {
        (W + 311, W + 312),
        (W + 311, W + 313),
    }
    assert not _rows(got, "gained")


def test_a_shrunk_way_absorbs_no_more_than_its_lost_length():
    # the old 400 m way loses 40 m; a new 300 m way drawn along its remaining part lies wholly
    # within 15 m of it but is far longer than what the old way lost: a gain, not a split piece
    old = _way(W + 321, (13.400, 13.4059), 52.55, highway="cycleway")
    kept = _way(W + 321, (13.400, 13.4053), 52.55, highway="cycleway")
    parallel = _way(W + 322, (13.400, 13.40443), 52.55001, highway="cycleway")
    got = ch.compute_change([old], [kept, parallel], CFG, EPSG, BOUNDARY, [])
    assert {(r.category, r.way_id_to) for r in got.rows} == {
        ("geometry", W + 321),
        ("gained", W + 322),
    }


def test_a_split_piece_needs_the_same_tier_and_a_new_way_id():
    old = _way(W + 331, (13.400, 13.4059), 52.555, highway="cycleway")
    kept = _way(W + 331, (13.400, 13.403), 52.555, highway="cycleway")
    tier_b = _way(W + 332, (13.403, 13.4059), 52.555, highway="footway", bicycle="designated")
    got = ch.compute_change([old], [kept, tier_b], CFG, EPSG, BOUNDARY, [])
    assert ("gained", W + 332) in {(r.category, r.way_id_to) for r in got.rows}
    # a footway mapped before (untiered) and now tagged for cycling is a gain, even on the
    # geometry a neighbouring way lost: it is not a new id split off that way
    footway = _way(W + 333, (13.403, 13.4059), 52.555, highway="footway")
    retagged = _way(W + 333, (13.403, 13.4059), 52.555, highway="cycleway")
    got = ch.compute_change([old, footway], [kept, retagged], CFG, EPSG, BOUNDARY, [])
    assert ("gained", W + 333) in {(r.category, r.way_id_to) for r in got.rows}


def test_totals_are_the_per_side_tier_sums_measure_stores(result):
    for ways, totals in ((FROM, result.totals_from), (TO, result.totals_to)):
        stored = _stored(ways)
        assert set(totals) == set(stored)
        assert all(totals[t] == pytest.approx(stored[t], abs=1e-9) for t in stored)
    ch.check_totals(result, _stored(FROM), _stored(TO))


def test_lengths_are_clipped_to_the_boundary():
    line = Projector(EPSG).line(next(w for w in TO if w.id == W + 3).coords)
    x_mid = (line.coords[0][0] + line.coords[-1][0]) / 2
    clipped = box(380_000, 5_810_000, x_mid, 5_840_000)  # cuts every fixture way in half-ish
    got = ch.compute_change(FROM, TO, CFG, EPSG, clipped, [])
    (row,) = _rows(got, "gained")
    assert row.km == pytest.approx(line.intersection(clipped).length / 1000)
    assert row.km < _km(TO, W + 3) * 0.6


def test_km_by_subarea_splits_rows_and_scales_a_shared_edge():
    line = Projector(EPSG).line(next(w for w in TO if w.id == W + 3).coords)
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    # north and south share the gained way as their common edge: both clip it in full
    north = Polygon([(x0 - 500, y0), (x0, y0), (x1, y1), (x1 + 500, y1), (x1 + 500, y1 + 500),
                     (x0 - 500, y0 + 500)])  # fmt: skip
    south = Polygon([(x0 - 500, y0), (x0, y0), (x1, y1), (x1 + 500, y1), (x1 + 500, y1 - 500),
                     (x0 - 500, y0 - 500)])  # fmt: skip
    got = ch.compute_change(
        FROM, TO, CFG, EPSG, BOUNDARY, [_sub("north", north), _sub("south", south)]
    )
    (row,) = _rows(got, "gained")
    assert sum(row.km_by_subarea.values()) == pytest.approx(row.km)
    x_mid = (x0 + x1) / 2
    west, east = (
        box(370_000, 5_800_000, x_mid, 5_850_000),
        box(x_mid, 5_800_000, 420_000, 5_850_000),
    )
    got = ch.compute_change(FROM, TO, CFG, EPSG, BOUNDARY, [_sub("west", west), _sub("east", east)])
    (row,) = _rows(got, "gained")
    assert row.km_by_subarea["west"] == pytest.approx(row.km / 2, rel=0.01)
    assert row.km_by_subarea["east"] == pytest.approx(row.km / 2, rel=0.01)


def test_totals_mismatch_refuses(result):
    ok = dict(result.totals_from)
    off = {**result.totals_to, "A": result.totals_to["A"] + 1.0}
    ch.check_totals(result, ok, dict(result.totals_to))
    with pytest.raises(ch.ChangeRefused) as e:
        ch.check_totals(result, ok, off)
    msg = str(e.value)
    assert "A" in msg
    assert f"{result.totals_to['A']:.3f}" in msg and f"{off['A']:.3f}" in msg


def test_a_tier_missing_on_one_side_counts_as_zero(result):
    with pytest.raises(ch.ChangeRefused, match=r"\bE\b"):
        ch.check_totals(result, {**result.totals_from, "E": 0.5}, dict(result.totals_to))


# --- runs: refusal and snapshot paths -----------------------------------------------------------

KEY = RunKey(
    city_id="berlin",
    osm_timestamp="2024-01-01T00:00:00Z",
    boundary_kind="lau",
    boundary_sha256="b" * 64,
    classifier_version="v4",
    classifier_parameters="{}",
    config_sha256="c" * 64,
    source="history",
)


@pytest.fixture
def conn(tmp_path):
    with open_db(tmp_path / "v.sqlite") as c:
        create_schema(c)
        upsert_cities(c, load_cities(CFG_DIR / "cities.yaml"))
        yield c


def _run(conn, key=KEY, md5="d" * 32, done=True) -> int:
    run_id = start_run(conn, key, git_commit="x", region_md5=md5)
    if done:
        conn.execute("UPDATE runs SET status='done' WHERE id=?", (run_id,))
    return run_id


def _current(**kw) -> RunKey:
    return RunKey(**{**KEY.__dict__, "osm_timestamp": "2026-09-30T20:21:22Z", "source": "current",
                     **kw})  # fmt: skip


def test_runs_of_the_same_classifier_and_boundary_pass(conn):
    ch.check_runs(conn, _run(conn), _run(conn, _current()))


@pytest.mark.parametrize(
    "field, value",
    [
        ("classifier_version", "v3"),
        ("boundary_sha256", "e" * 64),
        ("boundary_kind", "fua"),
        ("city_id", "paris"),
        ("classifier_parameters", '{"plain_cycleway_on_oneway":"both_sides"}'),
    ],
)
def test_runs_with_different_classifier_or_boundary_are_refused(conn, field, value):
    a, b = _run(conn), _run(conn, _current(**{field: value}))
    with pytest.raises(ch.ChangeRefused, match=field):
        ch.check_runs(conn, a, b)


@pytest.mark.parametrize("osm_timestamp", ["2024-01-01T00:00:00Z", "2023-01-01T00:00:00Z"])
def test_from_run_must_be_older_than_to_run(conn, osm_timestamp):
    # swapped arguments would silently turn every gain into a loss
    a, b = _run(conn), _run(conn, _current(osm_timestamp=osm_timestamp))
    with pytest.raises(ch.ChangeRefused, match=rf"run {a}.*not older than run {b}"):
        ch.check_runs(conn, a, b)


def test_non_done_run_is_refused(conn):
    a, b = _run(conn), _run(conn, _current(), done=False)
    with pytest.raises(ch.ChangeRefused, match=rf"run {b}.*running"):
        ch.check_runs(conn, a, b)


def test_missing_snapshot_is_refused_with_path(conn, tmp_path):
    run_id = _run(conn, _current(), md5="0123456789abcdef")
    want = (
        tmp_path
        / "snapshots"
        / snapshot_name(
            "berlin", "lau", datetime(2026, 9, 30, tzinfo=UTC), "0123456789abcdef", "b" * 64
        )
    )
    with pytest.raises(FileNotFoundError, match=re.escape(str(want))):
        snapshot_path_for_run(conn, run_id, tmp_path)
    want.parent.mkdir()
    want.write_bytes(b"")
    assert snapshot_path_for_run(conn, run_id, tmp_path) == want


def test_history_snapshot_path_is_the_one_snapshot_at_writes(conn, tmp_path):
    set_md5 = "fedcba9876543210" * 2
    run_id = _run(conn, md5=set_md5)
    hist = tmp_path / "history" / "city" / city_history_name("berlin", "lau", set_md5, "b" * 64)
    with pytest.raises(FileNotFoundError) as e:
        snapshot_path_for_run(conn, run_id, tmp_path)
    expected = Path(e.value.filename)
    assert expected.parent == tmp_path / "snapshots"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"")  # snapshot_at returns an existing snapshot without osmium
    assert snapshot_at(hist, datetime(2024, 1, 1, tzinfo=UTC), tmp_path) == expected
    assert snapshot_path_for_run(conn, run_id, tmp_path) == expected


# --- outputs ------------------------------------------------------------------------------------

RUN_FROM = {"id": 11, "osm_timestamp": "2024-01-01T00:00:00Z", "classifier_version": "v4",
            "boundary_sha256": "b" * 64}  # fmt: skip
RUN_TO = {**RUN_FROM, "id": 12, "osm_timestamp": "2026-09-30T20:21:22Z"}


def test_markdown_never_says_built(result):
    md = ch.render_markdown(result, "berlin", RUN_FROM, RUN_TO, {})
    assert "built" not in md.lower() and "removed" not in md.lower()
    assert "mapped km" in md
    assert "All figures are mapped km (ADR 0006): a gain is a way newly mapped as cycling " \
        "infrastructure, not a construction." in md  # fmt: skip
    assert "© OpenStreetMap contributors, ODbL 1.0" in md


def test_markdown_gives_the_net_change_per_tier_and_in_all(result):
    md = ch.render_markdown(result, "berlin", RUN_FROM, RUN_TO, {})
    assert "net change (to − from)" in md
    rows = {ln.split("|")[1].strip(): ln for ln in md.splitlines() if ln.startswith("| ")}
    for t in ch.TIERS:
        net = result.totals_to.get(t, 0.0) - result.totals_from.get(t, 0.0)
        assert rows[t].split("|")[4].strip() == f"{net:+.3f}", t
    total = sum(result.totals_to.values()) - sum(result.totals_from.values())
    assert rows["**A–E**"].split("|")[4].strip() == f"{total:+.3f}"


def test_markdown_lists_runs_bezirke_top_rows_and_changed_tags():
    line = Projector(EPSG).line(next(w for w in TO if w.id == W + 3).coords)
    x_mid = (line.coords[0][0] + line.coords[-1][0]) / 2
    subs = [_sub("west", box(370_000, 5_800_000, x_mid, 5_850_000)),
            _sub("east", box(x_mid, 5_800_000, 420_000, 5_850_000))]  # fmt: skip
    got = ch.compute_change(FROM, TO, CFG, EPSG, BOUNDARY, subs)
    md = ch.render_markdown(got, "berlin", RUN_FROM, RUN_TO, {"west": "Westend", "east": "Ostend"})
    for text in ("run 11", "run 12", "2024-01-01T00:00:00Z", "2026-09-30T20:21:22Z", "v4",
                 "b" * 12, "Westend", "Ostend", "https://www.openstreetmap.org/way/9000000003",
                 "foot"):  # fmt: skip
        assert text in md, text
    bezirk = [ln for ln in md.splitlines() if ln.startswith("| Westend")]
    assert len(bezirk) == 1
    gained = next(r for r in got.rows if r.category == "gained")
    assert f"{gained.km_by_subarea['west']:.3f}" in bezirk[0]


def test_the_bezirk_table_ends_with_the_remainder_outside_every_subarea():
    line = Projector(EPSG).line(next(w for w in TO if w.id == W + 3).coords)
    x_mid = (line.coords[0][0] + line.coords[-1][0]) / 2
    x_q = (x_mid + max(line.coords[0][0], line.coords[-1][0])) / 2
    subs = [_sub("west", box(370_000, 5_800_000, x_mid, 5_850_000)),
            _sub("east", box(x_mid, 5_800_000, x_q, 5_850_000))]  # fmt: skip
    got = ch.compute_change(FROM, TO, CFG, EPSG, BOUNDARY, subs)
    (gained,) = _rows(got, "gained")
    rest = gained.km_by_subarea[REMAINDER_ID]
    assert rest == pytest.approx(gained.km / 4, rel=0.02)  # the way's last quarter
    assert sum(gained.km_by_subarea.values()) == pytest.approx(gained.km)
    md = ch.render_markdown(got, "berlin", RUN_FROM, RUN_TO, {"west": "Westend", "east": "Ostend"})
    table = ch.bezirk_table(md).splitlines()
    assert [ln.split("|")[1].strip() for ln in table[2:]] == [
        "Ostend", "Westend", "Outside the 2 Bezirke (districts), at the LAU edge", "**berlin**"
    ]  # fmt: skip
    assert f"{rest:.3f}" in table[-2]


def test_subareas_covering_the_boundary_leave_no_remainder_row():
    subs = [_sub("west", box(370_000, 5_800_000, 395_000, 5_850_000)),
            _sub("east", box(395_000, 5_800_000, 420_000, 5_850_000))]  # fmt: skip
    got = ch.compute_change(FROM, TO, CFG, EPSG, BOUNDARY, subs)
    assert all(REMAINDER_ID not in r.km_by_subarea for r in got.rows)
    md = ch.render_markdown(got, "berlin", RUN_FROM, RUN_TO, {"west": "Westend", "east": "Ostend"})
    assert "Outside" not in md


def test_geojson_has_one_feature_per_row_in_wgs84(result, tmp_path):
    import json

    path = ch.write_geojson(result, FROM, TO, tmp_path / "maps" / "c.geojson")
    doc = json.loads(path.read_text())
    assert len(doc["features"]) == len(result.rows)
    lost = next(f for f in doc["features"] if f["properties"]["category"] == "lost")
    assert lost["properties"]["way_id_from"] == W + 2
    lon, lat = lost["geometry"]["coordinates"][0]
    assert 13.3 < lon < 13.5 and 52.4 < lat < 52.6
    assert "ODbL" in doc["properties"]["attribution"]


def test_png_has_four_categories_and_the_odbl_footer(result, tmp_path, monkeypatch):
    figs = []
    monkeypatch.setattr(ch.plt, "close", figs.append)
    sub = _sub("all", BOUNDARY)
    out = ch.render_png(result, FROM, TO, BOUNDARY, tmp_path / "c.png", epsg=EPSG, subareas=[sub])
    assert out.is_file() and out.stat().st_size > 0
    (fig,) = figs
    labels = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert [lb.split(" ")[0] for lb in labels] == ["gained", "lost", "retiered", "redrawn"]
    assert any("© OpenStreetMap contributors, ODbL 1.0" in t.get_text() for t in fig.texts)


# --- R4 guard: `report change` output is byte-identical across the M8 refactor -----------------

GOLDEN = FIX / "golden"


def _golden_outputs(tmp_path) -> tuple[str, bytes]:
    """The change markdown and GeoJSON of the fixture with a west/east split leaving a remainder
    (the subarea, redraw and split paths all run)."""
    line = Projector(EPSG).line(next(w for w in TO if w.id == W + 3).coords)
    x_mid = (line.coords[0][0] + line.coords[-1][0]) / 2
    x_q = (x_mid + max(line.coords[0][0], line.coords[-1][0])) / 2
    subs = [_sub("west", box(370_000, 5_800_000, x_mid, 5_850_000)),
            _sub("east", box(x_mid, 5_800_000, x_q, 5_850_000))]  # fmt: skip
    got = ch.compute_change(FROM, TO, CFG, EPSG, BOUNDARY, subs)
    md = ch.render_markdown(got, "berlin", RUN_FROM, RUN_TO, {"west": "Westend", "east": "Ostend"})
    path = ch.write_geojson(got, FROM, TO, tmp_path / "c.geojson", run_from=11, run_to=12)
    return md, path.read_bytes()


def test_change_markdown_and_geojson_match_the_golden_files(tmp_path):
    md, geojson = _golden_outputs(tmp_path)
    assert md == (GOLDEN / "change.md").read_text()
    assert geojson == (GOLDEN / "change.geojson").read_bytes()


def test_classified_sides_are_the_sides_compute_change_totals(result):
    sides = ch.classified_sides(FROM, CFG, EPSG, BOUNDARY)
    totals: dict[str, float] = {}
    for s in sides.values():
        totals[s.tier] = totals.get(s.tier, 0.0) + s.km
    assert totals == pytest.approx(result.totals_from)
    assert all(isinstance(s, ch.Side) for s in sides.values())
