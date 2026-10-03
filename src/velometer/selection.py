"""Which done runs a report covers: the classifier, its parameters and the config on disk.

A library module (no CLI imports); errors are `ConfigError`, which the CLI turns into exit 1.
"""

from dataclasses import dataclass
from pathlib import Path

from velometer.config import (
    PresetsConfig,
    load_classifier,
    load_presets,
    load_report,
    load_trust,
)
from velometer.db import canonical_parameters, latest_done_run
from velometer.run import config_sha256, file_sha256


@dataclass(frozen=True)
class Selector:
    """Which done runs a report covers: classifier, its parameters, the config on disk."""

    version: str
    parameters: str  # canonical JSON
    config_sha256: str
    presets: PresetsConfig
    activity_sha256: str  # sha256 of activity.yaml's bytes: keys the activity rows

    def latest(self, conn, city_id: str, boundary: str) -> int | None:
        return latest_done_run(
            conn, city_id, boundary, self.version, self.parameters, self.config_sha256
        )

    def stale(self, conn, city_id: str, boundary: str) -> bool:
        """True when the city has done runs of this classifier, but none of the current config."""
        return (
            self.latest(conn, city_id, boundary) is None
            and latest_done_run(conn, city_id, boundary, self.version, self.parameters) is not None
        )

    @property
    def short_sha(self) -> str:
        return self.config_sha256[:12]


def run_selector(config_dir: Path, classifier: str, basis: str | None = None) -> Selector:
    """The classifier, parameters and config sha of the config on disk: which runs to report.

    `basis` overrides presets.yaml's clean_cities_basis (reporting only). Raises ConfigError.
    """
    classifier_path = config_dir / "classifier" / f"{classifier}.yaml"
    activity_path = config_dir / "activity.yaml"
    cfg = load_classifier(classifier_path)
    presets = load_presets(config_dir / "presets.yaml", cfg)
    if basis is not None:
        presets = presets.with_parameters(clean_cities_basis=str(getattr(basis, "value", basis)))
    return Selector(
        cfg.version,
        canonical_parameters(cfg.parameters.model_dump()),
        config_sha256(classifier_path, config_dir / "presets.yaml", activity_path),
        presets,
        file_sha256(activity_path),
    )


def report_selector(config_dir: Path) -> Selector:
    """The runs every report surface shows: the classifier named in config/report.yaml."""
    report = load_report(config_dir / "report.yaml", config_dir / "presets.yaml")
    return run_selector(config_dir, report.report_classifier)


def trusted_countries(config_dir: Path) -> frozenset[str]:
    """ISO2 codes of the countries signed off in config/trust.yaml; absent counts as pending."""
    trust = load_trust(config_dir / "trust.yaml")
    return frozenset(cc for cc, t in trust.countries.items() if t.status == "trusted")
