"""config/trust.yaml: the per-country gate, and that it never touches config_sha256."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.report_fixture import CLASSIFIER
from tests.test_run_history import CITY
from velometer import trust as tr
from velometer.cli import app
from velometer.config import (
    ConfigError,
    TrustThresholds,
    default_config_dir,
    load_activity,
    load_cities,
    load_trust,
)
from velometer.db import fetch_run
from velometer.report.maps import snapshot_path
from velometer.selection import report_selector, run_selector, trusted_countries
from velometer.trust import CityDiagnostics, CountryDiagnostics, breaches, diagnose_city

TRUSTED = {"status": "trusted", "basis": "test"}
PENDING = {"status": "pending", "basis": "test"}
THRESHOLDS = {
    "unrecognised_share_max": 0.5,
    "excluded_share_max": 0.5,
    "b_share_of_ab_max": 0.5,
    "boundary_diff_pct_max": 5.0,
}


def _config_with_trust(tmp_path, countries=None, thresholds=THRESHOLDS):
    cfg = tmp_path / "config"
    shutil.copytree(default_config_dir(), cfg)
    (cfg / "trust.yaml").write_text(
        yaml.safe_dump({"thresholds": thresholds, "countries": countries or {}})
    )
    return cfg


def _load(tmp_path, countries=None, thresholds=THRESHOLDS):
    path = tmp_path / "trust.yaml"
    path.write_text(yaml.safe_dump({"thresholds": thresholds, "countries": countries or {}}))
    return load_trust(path)


def test_the_committed_trust_file_loads():
    assert load_trust(default_config_dir() / "trust.yaml").countries["DE"].status == "trusted"


def test_absent_country_is_untrusted(tmp_path):
    cfg = _config_with_trust(tmp_path, countries={"DE": TRUSTED, "FR": PENDING})
    assert trusted_countries(cfg) == frozenset({"DE"})  # FR pending, NL absent


def test_trusted_with_golden_requires_signoff(tmp_path):
    golden = {"status": "trusted", "basis": "x", "golden": "g/nl"}
    with pytest.raises(ConfigError, match="signed_off"):
        _load(tmp_path, countries={"NL": golden})
    with pytest.raises(ConfigError, match="classifier_reviewed"):
        _load(tmp_path, countries={"NL": {**golden, "signed_off": "2026-10-03"}})
    ok = {**golden, "signed_off": "2026-10-03", "classifier_reviewed": "v2"}
    assert _load(tmp_path, countries={"NL": ok}).countries["NL"].golden == "g/nl"


def test_basis_de_is_optional_and_not_blank(tmp_path):
    assert _load(tmp_path, countries={"DE": TRUSTED}).countries["DE"].basis_de is None
    de = {**TRUSTED, "basis_de": "Abgleich (M2)"}
    assert _load(tmp_path, countries={"DE": de}).countries["DE"].basis_de == "Abgleich (M2)"
    with pytest.raises(ConfigError, match="basis_de"):
        _load(tmp_path, countries={"DE": {**TRUSTED, "basis_de": "  "}})


def test_pending_with_golden_needs_no_signoff(tmp_path):
    pending = {"status": "pending", "basis": "x", "golden": "g/nl"}
    assert _load(tmp_path, countries={"NL": pending}).countries["NL"].signed_off is None


@pytest.mark.parametrize(
    "bad",
    [
        {"unrecognised_share_max": 0},
        {"excluded_share_max": 1.5},
        {"boundary_diff_pct_max": 0},
        {"surprise": 1},
    ],
)
def test_bad_thresholds_are_config_errors(tmp_path, bad):
    with pytest.raises(ConfigError, match="trust.yaml"):
        _load(tmp_path, thresholds={**THRESHOLDS, **bad})


def test_bad_country_key_and_status_are_config_errors(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, countries={"germany": TRUSTED})
    with pytest.raises(ConfigError):
        _load(tmp_path, countries={"DE": {"status": "maybe", "basis": "x"}})


def test_missing_trust_file_is_a_config_error(tmp_path):
    cfg = _config_with_trust(tmp_path)
    (cfg / "trust.yaml").unlink()
    with pytest.raises(ConfigError, match="trust.yaml"):
        trusted_countries(cfg)


def test_trust_yaml_is_not_part_of_config_sha256(tmp_path):
    cfg = _config_with_trust(tmp_path, countries={"DE": TRUSTED})
    before = run_selector(cfg, "v2").config_sha256
    (cfg / "trust.yaml").write_text(
        yaml.safe_dump({"thresholds": THRESHOLDS, "countries": {"DE": PENDING, "FR": TRUSTED}})
    )
    assert run_selector(cfg, "v2").config_sha256 == before


# --- diagnostics (Task 7) -------------------------------------------------------------------
# tests/fixtures/trust/trust_city.osm = measure/mini_city.osm plus ways 8-10. Every way runs
# 0.0147 degrees of longitude at ~52.5 N, about 1 km (0.996-0.998 km in EPSG:25833): "L" below.
# Classified sides under v2 (cycling-tagged ways only count; ways 5-7 carry no cycling tags):
#   way 1 primary, cycleway:both=track        2 road sides, tier A
#   way 2 highway=cycleway                    1 standalone side, tier A
#   way 3 footway, bicycle=designated         1 standalone side, tier B
#   way 4 secondary, cycleway:right=lane      1 road side, tier D (left has no cycleway: no side)
#   way 8 secondary, cycleway:right=bogus     1 road side, no tier, unknown_value (unrecognised)
#   way 9 secondary, cycleway:right=shoulder  1 road side, tier excluded by rule X_shoulder
#   way 10 tertiary, cycleway:right=lane, :width and :surface set   1 road side, tier D
# so cycling_km = 8 L; A = 3 L, B = 1 L, D = 2 L (A-E km = 6 L).
TRUST_CITY = Path(__file__).parent / "fixtures" / "trust" / "trust_city.osm"
L = 0.997  # km; the ways differ by less than 0.3 %
REL = 0.01
BOX = [[13.39, 52.49], [13.43, 52.49], [13.43, 52.60], [13.39, 52.60], [13.39, 52.49]]
# 0.04 x 0.11 degrees at 52.5 N: 2.71 km x 12.23 km = 33.2 km2 (UTM scale factor 0.9997)
BOX_KM2 = 33.2
needs_osmium = pytest.mark.skipif(
    shutil.which("osmium") is None, reason="osmium-tool not installed"
)


def _geojson(ring):
    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }
    return json.dumps({"type": "FeatureCollection", "features": [feature]})


def _place(conn, data_dir, osm=TRUST_CITY):
    """`osm` as berlin's current LAU snapshot, and BOX as the boundary file its row names."""
    row = fetch_run(conn, report_selector(default_config_dir()).latest(conn, "berlin", "lau"))
    dst = snapshot_path(row, data_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["osmium", "cat", str(osm), "-o", str(dst)], check=True)
    path = conn.execute(
        "SELECT path FROM boundaries WHERE city_id='berlin' AND kind='lau'"
    ).fetchone()[0]
    Path(path).write_text(_geojson(BOX))


@pytest.fixture
def diag_env(fixture_db, tmp_path):
    db_path, cfg, conn, _ = fixture_db
    data_dir = tmp_path / "data"
    _place(conn, data_dir)
    return db_path, cfg, conn, data_dir


def _diagnose(env):
    _, cfg, conn, data_dir = env
    return diagnose_city(
        conn, CITY, report_selector(cfg), data_dir, load_activity(cfg / "activity.yaml"),
        config_dir=cfg,
    )  # fmt: skip


@needs_osmium
def test_diagnose_shares_add_up(diag_env):
    d = _diagnose(diag_env)
    assert 0 <= d.unrecognised_share <= 1 and 0 <= d.excluded_share <= 1
    assert abs(sum(d.tier_mix.values()) - 1) < 1e-9
    assert d.excluded_share == pytest.approx(sum(d.excluded_by_rule.values()))


@needs_osmium
def test_diagnose_numbers_of_the_trust_city(diag_env):
    d = _diagnose(diag_env)
    assert d.city_id == "berlin" and d.osm_timestamp.startswith("2026-09-30")
    assert d.cycling_km == pytest.approx(8 * L, rel=REL)
    assert d.unrecognised_share == pytest.approx(1 / 8, rel=REL)  # way 8
    assert d.excluded_share == pytest.approx(1 / 8, rel=REL)  # way 9
    assert d.excluded_by_rule == {"X_shoulder": pytest.approx(1 / 8, rel=REL)}
    assert d.tier_mix == pytest.approx(
        {"A": 3 / 6, "B": 1 / 6, "C": 0, "D": 2 / 6, "E": 0}, rel=REL
    )
    assert d.b_share_of_ab == pytest.approx(1 / 4, rel=REL)
    assert set(d.completeness) == {"A", "B", "D"}
    assert d.completeness["D"]["width"] == pytest.approx(1 / 2, rel=REL)  # way 10 of ways 4, 10
    assert d.completeness["D"]["surface"] == pytest.approx(1 / 2, rel=REL)
    assert d.completeness["D"]["segregated"] == 0
    assert d.boundary_lau_km2 == pytest.approx(BOX_KM2, rel=0.02)


@needs_osmium
def test_top_unmatched_signature_has_only_cycling_keys(diag_env):
    d = _diagnose(diag_env)
    # way 8 also has surface=asphalt and name=...: neither is a cycling key
    assert d.top_unmatched == [
        ("cycleway:right=bogus;highway=secondary", pytest.approx(L, rel=REL))
    ]


def test_signature_sorts_keys_truncates_values_and_leaves_out_other_tags():
    act = load_activity(default_config_dir() / "activity.yaml")
    tags = {"name": "x", "highway": "primary", "cycleway:both": "y" * 60, "bicycle": "yes"}
    assert tr.tag_signature(tags, act) == f"bicycle=yes;cycleway:both={'y' * 40};highway=primary"


@needs_osmium
def test_boundary_comparison_is_none_without_a_cached_region_file(diag_env):
    d = _diagnose(diag_env)
    assert d.boundary_osm_km2 is None and d.boundary_diff_pct is None


@needs_osmium
def test_boundary_diff_against_the_osm_relation_polygon(diag_env, monkeypatch):
    _, _, _, data_dir = diag_env
    region = data_dir / "raw" / "berlin-260930.osm.pbf"  # europe/germany/berlin, as cached
    region.parent.mkdir(parents=True)
    region.write_bytes(b"")
    wide = [[13.39, 52.49], [13.47, 52.49], [13.47, 52.60], [13.39, 52.60], [13.39, 52.49]]
    calls = []

    def fake_relation(src, relation_id, dst):
        calls.append((src, relation_id))
        dst.write_text(_geojson(wide))
        return dst

    monkeypatch.setattr(tr, "relation_polygon", fake_relation)
    d = _diagnose(diag_env)
    assert calls == [(region, CITY.osm_relation_id)]
    assert d.boundary_osm_km2 == pytest.approx(2 * BOX_KM2, rel=0.02)  # twice as wide
    assert d.boundary_diff_pct == pytest.approx(50, rel=0.02)  # |33.2 - 66.4| / 66.4


@needs_osmium
def test_no_cycling_tags_gives_zero_shares_not_nan(fixture_db, tmp_path):
    _, cfg, conn, _ = fixture_db
    plain = tmp_path / "plain.osm"
    plain.write_text(
        '<osm version="0.6"><node id="1" lat="52.5" lon="13.4"/>'
        '<node id="2" lat="52.5" lon="13.41"/>'
        '<way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/></way></osm>'
    )
    _place(conn, tmp_path / "data", plain)
    d = diagnose_city(
        conn, CITY, report_selector(cfg), tmp_path / "data", load_activity(cfg / "activity.yaml"),
        config_dir=cfg,
    )  # fmt: skip
    assert d.cycling_km == 0
    assert (d.unrecognised_share, d.excluded_share) == (0.0, 0.0)
    assert d.b_share_of_ab is None and set(d.tier_mix.values()) == {0.0}


def test_city_without_a_current_run_is_an_error_naming_it(fixture_db, tmp_path):
    _, cfg, conn, _ = fixture_db
    paris = next(c for c in load_cities(cfg / "cities.yaml") if c.id == "paris")
    with pytest.raises(tr.NoCurrentRun, match="paris"):
        diagnose_city(
            conn, paris, report_selector(cfg), tmp_path, load_activity(cfg / "activity.yaml")
        )


def _diag(**kw):
    base = dict(
        city_id="x", run_id=1, osm_timestamp="2026-09-30T00:00:00Z", cycling_km=10.0,
        unrecognised_share=0.0, excluded_share=0.0, excluded_by_rule={}, tier_mix={},
        b_share_of_ab=None, completeness={}, top_unmatched=[], boundary_lau_km2=1.0,
        boundary_osm_km2=None, boundary_diff_pct=None,
    )  # fmt: skip
    return CityDiagnostics(**{**base, **kw})


def test_breaches_names_each_metric_over_its_limit():
    d = _diag(unrecognised_share=0.2, excluded_share=0.1, b_share_of_ab=0.9, boundary_diff_pct=7)
    t = TrustThresholds(
        unrecognised_share_max=0.1,
        excluded_share_max=0.5,
        b_share_of_ab_max=0.8,
        boundary_diff_pct_max=5,
    )
    assert breaches(d, t) == ["unrecognised_share", "b_share_of_ab", "boundary_diff_pct"]


def test_breaches_ignores_none_and_values_at_the_limit():
    t = TrustThresholds(
        unrecognised_share_max=0.1,
        excluded_share_max=0.5,
        b_share_of_ab_max=0.8,
        boundary_diff_pct_max=5,
    )
    assert (
        breaches(_diag(unrecognised_share=0.1, b_share_of_ab=None, boundary_diff_pct=None), t) == []
    )


T = TrustThresholds(**THRESHOLDS)


def _country(*cities):
    return CountryDiagnostics(
        country="XX", classifier_version="v2", config_sha256="a" * 64, cities=list(cities)
    )


def test_write_country_keeps_hand_written_notes(tmp_path):
    js, md = tr.write_country(tmp_path, _country(_diag(city_id="first")), T, [])
    assert json.loads(js.read_text())["cities"][0]["city_id"] == "first"
    text = md.read_text()
    assert text.startswith("# Trust review: XX") and "| first |" in text
    md.write_text(
        text.replace("# Trust review: XX", "# Trust review: XX\n\nMY NOTE above.")
        + "\nMY NOTE below\n"
    )
    tr.write_country(tmp_path, _country(_diag(city_id="second")), T, [_diag(city_id="pilot")])
    after = md.read_text()
    assert "MY NOTE above." in after and "MY NOTE below" in after
    assert "| second |" in after and "| first |" not in after  # the block was replaced
    assert "### Pilot comparison" in after and "| pilot |" in after
    assert after.count(tr.TRUST_BEGIN) == after.count(tr.TRUST_END) == 1
    assert json.loads(js.read_text())["cities"][0]["city_id"] == "second"


def test_shares_below_one_percent_show_two_decimals(tmp_path):
    # Stockholm read "0.1%" against a limit of "0.1%" while under it: a value or limit below 1 %
    # needs 2 decimals to be compared; larger shares keep 1
    t = TrustThresholds(
        unrecognised_share_max=0.001,
        excluded_share_max=0.5,
        b_share_of_ab_max=0.5,
        boundary_diff_pct_max=5,
    )
    d = _diag(city_id="c", unrecognised_share=0.0012, excluded_share=0.154, b_share_of_ab=0.004)
    _, md = tr.write_country(tmp_path, _country(d), t, [])
    text = md.read_text()
    assert "Limits: unrecognised 0.10%, excluded 50.0%, B of A+B 50.0%" in text
    assert "| c | 1 | 10.0 | 0.12% | 15.4% | 0.40% |" in text


def test_write_country_appends_a_block_to_a_file_without_one(tmp_path):
    md = tmp_path / "review" / "trust" / "XX.md"
    md.parent.mkdir(parents=True)
    md.write_text("only my notes\n")
    tr.write_country(tmp_path, _country(_diag()), T, [])
    assert md.read_text().startswith("only my notes\n") and tr.TRUST_BEGIN in md.read_text()


def test_cli_diagnose_writes_the_review_files(diag_env, tmp_path):
    db_path, cfg, _, data_dir = diag_env
    docs = tmp_path / "docs"
    res = CliRunner().invoke(app, [
        "trust", "diagnose", "--country", "DE", "--db", str(db_path), "--data", str(data_dir),
        "--config-dir", str(cfg), "--docs", str(docs),
    ])  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "berlin:" in res.output
    out = json.loads((docs / "review" / "trust" / "DE.json").read_text())
    assert out["cities"][0]["city_id"] == "berlin" and out["classifier_version"] == CLASSIFIER
    assert (docs / "review" / "trust" / "DE.md").is_file()


def test_cli_diagnose_without_a_current_run_exits_1_naming_the_city(fixture_db, tmp_path):
    db_path, cfg, _, _ = fixture_db
    res = CliRunner().invoke(app, [
        "trust", "diagnose", "--country", "FR", "--db", str(db_path), "--data", str(tmp_path),
        "--config-dir", str(cfg), "--docs", str(tmp_path / "docs"),
    ])  # fmt: skip
    assert res.exit_code == 1 and "paris" in res.output
    assert not (tmp_path / "docs").exists()


def test_cli_diagnose_unknown_country_exits_2(fixture_db, tmp_path):
    db_path, cfg, _, _ = fixture_db
    res = CliRunner().invoke(app, ["trust", "diagnose", "--country", "ZZ", "--db", str(db_path),
                                   "--config-dir", str(cfg)])  # fmt: skip
    assert res.exit_code == 2


# --- golden samples and trust check (Task 8) -------------------------------------------------
from tests.golden_util import check_golden  # noqa: E402
from velometer.pipeline.drift import is_unmatched_road_side  # noqa: E402
from velometer.pipeline.measure import measure  # noqa: E402
from velometer.pipeline.read import read_ways  # noqa: E402
from velometer.pipeline.types import Classified, WaySide  # noqa: E402

ACT = load_activity(default_config_dir() / "activity.yaml")


def _trust_city_sample_inputs():
    ways = read_ways(TRUST_CITY).ways
    cfg = load_classifier(default_config_dir() / "classifier" / "v2.yaml")
    result = measure(ways, cfg, 25833)
    return result.classified, result.way_lengths, {w.id: w.tags for w in ways}


def test_sample_ways_picks_longest_side_per_top_rule_then_unmatched():
    classified, lengths, tags = _trust_city_sample_inputs()
    got = tr.sample_ways(classified, lengths, tags, activity_cfg=ACT, city_id="berlin")
    # rules by km: A_track_side (2 sides of way 1: 1.996), D_lane (ways 4 and 10: 1.993, the
    # longer, 4, wins), then A_cycleway and B_path (0.998 each, tie broken by id), X_shoulder;
    # and the one unmatched signature (way 8)
    assert [(s.way_id, s.group) for s in got] == [
        (1, "A_track_side"), (4, "D_lane"), (2, "A_cycleway"), (3, "B_path"),
        (9, "X_shoulder"), (8, "unmatched:1"),
    ]  # fmt: skip
    assert got == tr.sample_ways(classified, lengths, tags, activity_cfg=ACT, city_id="berlin")
    one = got[0]
    assert one.city_id == "berlin" and one.highway == "primary" and one.name == ""
    assert [(p["side"], p["tier"], p["rule"]) for p in one.proposed] == [
        ("left", "A", "A_track_side"),
        ("right", "A", "A_track_side"),
    ]
    limited = tr.sample_ways(classified, lengths, tags, activity_cfg=ACT, top_rules=2, unmatched=0)
    assert [s.way_id for s in limited] == [1, 4]


def _side(way_id, side="right"):
    return WaySide(way_id, side, "road_side", {}, ((0.0, 0.0), (1.0, 0.0)))


def test_sample_ways_dedupes_by_way_id_and_takes_the_next_longest():
    tags = {
        1: {"highway": "primary", "cycleway:right": "bogus", "cycleway:left": "lane"},
        2: {"highway": "primary", "cycleway:left": "lane"},
        3: {"highway": "residential"},  # no cycling tags: never an unmatched sample
    }
    classified = [
        Classified(_side(1, "left"), "D", None, "D_lane", {}),
        Classified(_side(2, "left"), "D", None, "D_lane", {}),
        Classified(_side(1, "right"), None, None, None, {}),  # unmatched, same way as the D_lane
        Classified(_side(3), None, None, None, {}),
    ]
    assert is_unmatched_road_side(classified[3])
    lengths = {1: 5.0, 2: 1.0, 3: 9.0}
    got = tr.sample_ways(classified, lengths, tags, activity_cfg=ACT)
    assert [(s.way_id, s.group) for s in got] == [(1, "D_lane")]  # 2 is no signature's longest
    got = tr.sample_ways(classified, lengths, tags, activity_cfg=ACT, per_rule=2)
    assert [(s.way_id, s.group) for s in got] == [(1, "D_lane"), (2, "D_lane")]


def test_golden_yaml_has_the_berlin_schema_and_round_trips(tmp_path):
    berlin = yaml.safe_load((Path(__file__).parent / "fixtures" / "berlin_golden.yaml").read_text())
    classified, lengths, tags = _trust_city_sample_inputs()
    samples = tr.sample_ways(classified, lengths, tags, activity_cfg=ACT, city_id="berlin")
    path = tmp_path / "g" / "xx.yaml"
    tr.write_golden_yaml(path, tr.golden_doc(samples, "src", "v2"))
    text = path.read_text()
    assert text.startswith("# Map data © OpenStreetMap contributors, ODbL 1.0")
    doc = yaml.safe_load(text)
    assert set(doc) == set(berlin) and doc["classifier_version"] == "v2"
    assert set(doc["ways"][0]) == set(berlin["ways"][0])
    assert {set_ for w in doc["ways"] for set_ in [w["confirmed"]]} == {False}
    assert all(w["note"] == "" for w in doc["ways"])
    # the way entries feed the Berlin checker unchanged
    observed = {
        w["way_id"]: {(p["side"], p["tier"], p["rule"]) for p in w["proposed"]} for w in doc["ways"]
    }
    for w in doc["ways"]:
        w["confirmed"] = True
    check_golden(doc["ways"], observed)


@pytest.fixture
def fake_osmium(monkeypatch):
    """Record argv of every osmium call and write the file named by `-o`."""
    from velometer import osmium as O

    seen = []

    def run(*args):
        seen.append(args)
        if "-o" in args:
            Path(args[args.index("-o") + 1]).write_text("<osm/>")
        return ""

    monkeypatch.setattr(O, "_run", run)
    return seen


@needs_osmium
def test_cli_sample_writes_fixtures_and_review_sheet(diag_env, tmp_path, fake_osmium):
    db_path, cfg, _, data_dir = diag_env
    docs, tests_dir = tmp_path / "docs", tmp_path / "tests"
    res = CliRunner().invoke(app, [
        "trust", "sample", "--country", "DE", "--extra-way", "5", "--db", str(db_path),
        "--data", str(data_dir), "--config-dir", str(cfg), "--docs", str(docs),
        "--tests-dir", str(tests_dir),
    ])  # fmt: skip
    assert res.exit_code == 0, res.output
    golden = tests_dir / "fixtures" / "golden"
    doc = yaml.safe_load((golden / "de.yaml").read_text())
    assert [(w["way_id"], w["group"]) for w in doc["ways"]] == [
        (1, "A_track_side"), (4, "D_lane"), (2, "A_cycleway"), (3, "B_path"),
        (9, "X_shoulder"), (8, "unmatched:1"), (5, "extra"),
    ]  # fmt: skip
    assert doc["ways"][-1]["proposed"] == [] and not any(w["confirmed"] for w in doc["ways"])
    (getid,) = [a for a in fake_osmium if a[0] == "getid"]
    assert getid[-7:] == ("w1", "w4", "w2", "w3", "w9", "w8", "w5")
    assert "snapshots" in getid[-8]  # the city's snapshot is the source
    assert (golden / "de.osm").is_file() and not list(golden.glob("*part*"))
    sheet = (docs / "review" / "trust" / "DE_golden.md").read_text()
    assert "https://www.openstreetmap.org/way/4" in sheet and "D / D_lane" in sheet
    assert sheet.count("\n| [") == 7 and "bogus" in sheet and "ODbL 1.0" in sheet
    assert "name=" not in sheet  # only cycling keys and highway are shown


@needs_osmium
def test_cli_sample_writes_the_odbl_note_into_the_osm(diag_env, tmp_path, fake_osmium):
    db_path, cfg, _, data_dir = diag_env
    tests_dir = tmp_path / "tests"
    res = CliRunner().invoke(app, [
        "trust", "sample", "--country", "DE", "--db", str(db_path), "--data", str(data_dir),
        "--config-dir", str(cfg), "--docs", str(tmp_path / "docs"), "--tests-dir", str(tests_dir),
    ])  # fmt: skip
    assert res.exit_code == 0, res.output
    text = (tests_dir / "fixtures" / "golden" / "de.osm").read_text()
    assert f"<!-- {tr.ODBL} -->" in text  # the wording of the .yaml header (ADR 0008)


def test_osm_attribution_follows_the_xml_declaration_and_is_added_once(tmp_path):
    osm = tmp_path / "x.osm"
    osm.write_text("<?xml version='1.0' encoding='UTF-8'?>\n<osm version=\"0.6\">\n</osm>\n")
    tr.add_osm_attribution(osm)
    tr.add_osm_attribution(osm)
    lines = osm.read_text().splitlines()
    assert lines[0].startswith("<?xml") and lines[1] == f"<!-- {tr.ODBL} -->"
    assert osm.read_text().count(tr.ODBL) == 1
    bare = tmp_path / "y.osm"
    bare.write_text("<osm/>")
    tr.add_osm_attribution(bare)
    assert bare.read_text() == f"<!-- {tr.ODBL} -->\n<osm/>"


@needs_osmium
def test_cli_sample_refuses_to_overwrite_signed_off_fixtures(diag_env, tmp_path, fake_osmium):
    db_path, cfg, _, data_dir = diag_env
    tests_dir = tmp_path / "tests"
    (tests_dir / "fixtures" / "golden").mkdir(parents=True)
    keep = tests_dir / "fixtures" / "golden" / "de.yaml"
    keep.write_text("mine")
    args = [
        "trust", "sample", "--country", "DE", "--db", str(db_path), "--data", str(data_dir),
        "--config-dir", str(cfg), "--docs", str(tmp_path / "docs"), "--tests-dir", str(tests_dir),
    ]  # fmt: skip
    res = CliRunner().invoke(app, args)
    assert res.exit_code == 1 and keep.read_text() == "mine" and not fake_osmium
    assert CliRunner().invoke(app, [*args, "--force"]).exit_code == 0


# --- trust check ---------------------------------------------------------------------------


def _check_env(tmp_path, report_db_with_trust, *, golden=True, **country):
    """A DE-trusted fixture config with fresh evidence: a fully confirmed golden set that matches
    the report classifier, a current <cc>.json whose one breach has its note, and thresholds
    below the placeholder. Returns (argv, paths)."""
    ct = {
        "status": "trusted",
        "basis": "t",
        "classifier_reviewed": CLASSIFIER,
        "signed_off": "2026-10-03",
    }
    if golden:
        ct["golden"] = "tests/fixtures/golden/de"
    db_path, cfg = report_db_with_trust({"DE": {**ct, **country}})
    trust = yaml.safe_load((cfg / "trust.yaml").read_text())
    trust["thresholds"] = THRESHOLDS
    (cfg / "trust.yaml").write_text(yaml.safe_dump(trust))

    tests_dir, docs = tmp_path / "tests", tmp_path / "docs"
    gdir = tests_dir / "fixtures" / "golden"
    gdir.mkdir(parents=True)
    shutil.copy(TRUST_CITY, gdir / "de.osm")
    classified, lengths, tags = _trust_city_sample_inputs()
    samples = tr.sample_ways(classified, lengths, tags, activity_cfg=ACT, city_id="berlin")
    doc = tr.golden_doc(samples, "t", CLASSIFIER)
    for w in doc["ways"]:
        w["confirmed"] = True
    tr.write_golden_yaml(gdir / "de.yaml", doc)

    conn = open_readonly(db_path)
    run_id = report_selector(cfg).latest(conn, "berlin", "lau")
    conn.close()
    city = _diag(city_id="berlin", run_id=run_id, unrecognised_share=0.9)  # over the 0.5 limit
    tr.write_country(docs, _country(city).model_copy(update={"country": "DE"}), T, [])
    md = docs / "review" / "trust" / "DE.md"
    md.write_text(md.read_text() + "\n### berlin/unrecognised_share\n\nreviewed: a one-off.\n")
    argv = ["trust", "check", "--db", str(db_path), "--config-dir", str(cfg),
            "--docs", str(docs), "--tests-dir", str(tests_dir)]  # fmt: skip
    return argv, {"cfg": cfg, "docs": docs, "golden": gdir, "md": md, "run_id": run_id}


from velometer.config import load_classifier  # noqa: E402
from velometer.report.data import open_readonly  # noqa: E402

NEXT = f"v{int(CLASSIFIER.removeprefix('v')) + 1}"  # a classifier newer than the report one


def _check(argv):
    res = CliRunner().invoke(app, argv)
    return res.exit_code, res.output


def test_check_clean_case_exits_0(tmp_path, report_db_with_trust):
    argv, _ = _check_env(tmp_path, report_db_with_trust)
    assert _check(argv) == (0, "trust check: ok\n")


def test_check_a_unconfirmed_golden_way(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    path = p["golden"] / "de.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["ways"][0]["confirmed"] = False
    path.write_text(yaml.safe_dump(doc))
    code, out = _check(argv)
    assert code == 1 and out == "DE: 1/6 golden ways unconfirmed\n"


def test_check_a_confirmed_way_that_no_longer_matches(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    path = p["golden"] / "de.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["ways"][2]["proposed"][0]["tier"] = "E"
    path.write_text(yaml.safe_dump(doc))
    code, out = _check(argv)
    assert code == 1 and out == "DE: golden way 2 does not match the report classifier\n"


def test_check_a_way_expecting_a_newer_classifier_blocks_trust(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    path = p["golden"] / "de.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["ways"][2]["proposed"][0]["tier"] = "E"  # the verdict only a later classifier gives
    doc["ways"][2]["min_classifier"] = NEXT
    path.write_text(yaml.safe_dump(doc))
    code, out = _check(argv)
    want = f"DE: golden way 2 expects classifier {NEXT} (report classifier {CLASSIFIER})\n"
    assert code == 1 and out == want
    doc["ways"][2]["min_classifier"] = CLASSIFIER  # reached: the way is compared again
    path.write_text(yaml.safe_dump(doc))
    code, out = _check(argv)
    assert code == 1 and out == "DE: golden way 2 does not match the report classifier\n"


def test_check_a_missing_golden_fixture(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    (p["golden"] / "de.osm").unlink()
    code, out = _check(argv)
    assert code == 1 and "DE: golden fixture missing:" in out and out.count("\n") == 1


def test_check_b_classifier_reviewed_is_not_the_report_classifier(tmp_path, report_db_with_trust):
    argv, _ = _check_env(tmp_path, report_db_with_trust, classifier_reviewed="v1")
    code, out = _check(argv)
    assert (
        code == 1
        and out == f"DE: classifier_reviewed is v1, the report classifier is {CLASSIFIER}\n"
    )


def test_check_without_golden_skips_a(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust, golden=False)
    (p["golden"] / "de.yaml").unlink()
    assert _check(argv) == (0, "trust check: ok\n")


def test_check_b_applies_to_a_trusted_country_without_golden(tmp_path, report_db_with_trust):
    # spec 3.3: a classifier switch forces a re-review of every trusted country
    argv, p = _check_env(tmp_path, report_db_with_trust, golden=False, classifier_reviewed="v1")
    (p["golden"] / "de.yaml").unlink()
    code, out = _check(argv)
    assert code == 1
    assert out == f"DE: classifier_reviewed is v1, the report classifier is {CLASSIFIER}\n"


def test_check_b_flags_a_trusted_country_that_names_no_reviewed_classifier(
    tmp_path, report_db_with_trust
):
    argv, p = _check_env(tmp_path, report_db_with_trust, golden=False)
    trust = yaml.safe_load((p["cfg"] / "trust.yaml").read_text())
    del trust["countries"]["DE"]["classifier_reviewed"]
    (p["cfg"] / "trust.yaml").write_text(yaml.safe_dump(trust))
    code, out = _check(argv)
    assert code == 1
    assert out == f"DE: classifier_reviewed is not set, the report classifier is {CLASSIFIER}\n"


def test_check_c_city_of_a_trusted_country_missing_from_its_json(tmp_path, report_db_with_trust):
    # a new city in an already trusted country must not enter the report undiagnosed
    argv, p = _check_env(tmp_path, report_db_with_trust)
    path = p["cfg"] / "cities.yaml"
    doc = yaml.safe_load(path.read_text())
    berlin = next(c for c in doc["cities"] if c["id"] == "berlin")
    doc["cities"].append({**berlin, "id": "potsdam", "name": "Potsdam"})
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    code, out = _check(argv)
    assert code == 1
    assert out == ("DE: potsdam is not in DE.json (run `velometer trust diagnose --country DE`)\n")


def test_check_c_stale_run_ids(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    js = p["docs"] / "review" / "trust" / "DE.json"
    data = json.loads(js.read_text())
    data["cities"][0]["run_id"] = p["run_id"] - 1
    js.write_text(json.dumps(data))
    code, out = _check(argv)
    assert code == 1
    assert out == (
        f"DE: berlin diagnosed run {p['run_id'] - 1}, current run is {p['run_id']} "
        "(stale: re-run `velometer trust diagnose --country DE`)\n"
    )


def test_check_d_breach_without_a_note_heading(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    p["md"].write_text(p["md"].read_text().replace("### berlin/unrecognised_share", "### berlin"))
    code, out = _check(argv)
    assert code == 1
    assert out == (
        "DE: berlin breaches unrecognised_share with no "
        "`### berlin/unrecognised_share` note in DE.md\n"
    )


def test_check_e_placeholder_threshold(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    trust = yaml.safe_load((p["cfg"] / "trust.yaml").read_text())
    trust["thresholds"]["excluded_share_max"] = 1.0
    (p["cfg"] / "trust.yaml").write_text(yaml.safe_dump(trust))
    code, out = _check(argv)
    assert code == 1 and out == "threshold excluded_share_max is still the placeholder 1.0\n"


def test_check_f_trusted_country_with_a_city_but_no_json(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    trust = yaml.safe_load((p["cfg"] / "trust.yaml").read_text())
    ok = {"status": "trusted", "basis": "t", "classifier_reviewed": CLASSIFIER}
    trust["countries"]["FR"] = ok  # paris is in cities.yaml
    assert not any(c.country_iso2 == "IS" for c in load_cities(p["cfg"] / "cities.yaml"))
    trust["countries"]["IS"] = ok  # no city: nothing to check
    (p["cfg"] / "trust.yaml").write_text(yaml.safe_dump(trust))
    code, out = _check(argv)
    assert code == 1
    assert out == "FR: no FR.json (run `velometer trust diagnose`)\n"


def test_check_f_exempts_germany(tmp_path, report_db_with_trust):
    argv, p = _check_env(tmp_path, report_db_with_trust)
    (p["docs"] / "review" / "trust" / "DE.json").unlink()
    assert _check(argv) == (0, "trust check: ok\n")
