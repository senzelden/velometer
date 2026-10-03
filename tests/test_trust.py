"""config/trust.yaml: the per-country gate, and that it never touches config_sha256."""

import shutil

import pytest
import yaml

from velometer.config import ConfigError, default_config_dir, load_trust
from velometer.selection import run_selector, trusted_countries

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
