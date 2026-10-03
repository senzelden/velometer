"""config/trust.yaml: the per-country gate, and that it never touches config_sha256."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

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
    assert out["cities"][0]["city_id"] == "berlin" and out["classifier_version"] == "v2"
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
