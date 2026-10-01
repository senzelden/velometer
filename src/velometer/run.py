"""Orchestrate one persisted city run: region -> boundary -> snapshot -> measure -> SQLite.

A run is keyed on (city, OSM timestamp, boundary kind + sha, classifier version + parameters);
a done run with the same key is skipped. `force` supersedes the existing done run: it is marked
`failed` with the error `superseded by --force`, so its result rows stay but it is no longer
"latest". If the forced re-run itself fails, the old run is restored to `done`.
"""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from velometer.config import CityConfig, load_classifier, load_presets
from velometer.db import (
    RunKey,
    canonical_parameters,
    complete_run,
    fail_run,
    find_done_run,
    set_population,
    start_run,
    upsert_boundary,
)
from velometer.models import Metric
from velometer.pipeline.extract import snapshot as _snapshot
from velometer.pipeline.measure import compute_metrics, measure
from velometer.pipeline.read import read_ways as _read_ways
from velometer.sources.boundaries import city_boundary as _city_boundary
from velometer.sources.geofabrik import fetch_region as _fetch_region


@dataclass(frozen=True)
class RunDeps:
    fetch_region: Callable = _fetch_region
    city_boundary: Callable = _city_boundary
    snapshot: Callable = _snapshot
    read_ways: Callable = _read_ways


@dataclass(frozen=True)
class RunOutcome:
    city_id: str
    status: Literal["done", "skipped", "failed"]
    run_id: int | None = None
    error: str | None = None


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def git_commit() -> str:
    try:
        sha = _git("rev-parse", "HEAD").strip()
        dirty = bool(_git("status", "--porcelain").strip())
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


def with_per_100k(metrics: list[Metric], population_value: int | None) -> list[Metric]:
    """Preset numerator km per 100k residents; stays None when the population is unknown."""
    if not population_value:
        return metrics
    return [
        m.model_copy(update={"per_100k": m.numerator_km / population_value * 100_000})
        for m in metrics
    ]


def _describe(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def run_city(
    conn,
    city: CityConfig,
    *,
    data_dir: Path,
    config_dir: Path,
    boundary_kind: str = "lau",
    classifier: str = "v1",
    parameters: dict[str, str] | None = None,
    force: bool = False,
    deps: RunDeps | None = None,
) -> RunOutcome:
    deps = deps or RunDeps()
    cfg = load_classifier(config_dir / "classifier" / f"{classifier}.yaml")
    if parameters:
        cfg = cfg.with_parameters(**parameters)
    presets = load_presets(config_dir / "presets.yaml", cfg)
    try:
        region = deps.fetch_region(city.geofabrik_region, data_dir)
        rec, pop = deps.city_boundary(city, boundary_kind, data_dir, region_path=region.path)
        upsert_boundary(conn, rec.boundary)
        if pop is not None:
            set_population(conn, city.id, pop)
    except Exception as e:  # noqa: BLE001 - no run row yet; report and let the next city run
        return RunOutcome(city.id, "failed", None, _describe(e))
    key = RunKey(
        city_id=city.id,
        osm_timestamp=region.osm_timestamp.isoformat().replace("+00:00", "Z"),
        boundary_kind=boundary_kind,
        boundary_sha256=rec.boundary.sha256,
        classifier_version=cfg.version,
        classifier_parameters=canonical_parameters(cfg.parameters.model_dump()),
    )
    done = find_done_run(conn, key)
    if done is not None and not force:
        return RunOutcome(city.id, "skipped", done)
    run_id = start_run(conn, key, git_commit=git_commit(), region_md5=region.md5)
    retired = False
    try:
        snap = deps.snapshot(
            region.path,
            region.md5,
            region.osm_timestamp,
            city.id,
            boundary_kind,
            rec.geojson_path,
            rec.boundary.sha256,
            data_dir,
        )
        ways = deps.read_ways(snap).ways
        result = measure(ways, cfg, city.epsg, boundary=rec.polygon)
        metrics = with_per_100k(compute_metrics(result, presets), pop.value if pop else None)
        if done is not None:  # the unique index admits one done run per key
            with conn:
                conn.execute(
                    "UPDATE runs SET status='failed', error='superseded by --force' WHERE id=?",
                    (done,),
                )
            retired = True
        complete_run(conn, run_id, city.id, result, metrics)
    except Exception as e:  # noqa: BLE001 - recorded on the run row, then the next city runs
        if retired:
            with conn:
                conn.execute("UPDATE runs SET status='done', error=NULL WHERE id=?", (done,))
        fail_run(conn, run_id, _describe(e))
        return RunOutcome(city.id, "failed", run_id, _describe(e))
    return RunOutcome(city.id, "done", run_id)
