"""Orchestrate one persisted city run: region -> boundary -> snapshot -> measure -> SQLite.

A run is keyed on (city, OSM timestamp, boundary kind + sha, classifier version + parameters,
config sha256 of the classifier, presets and activity YAML (see config_sha256), source `current` or
`history`) (see RunKey); a done run with the same key is skipped. A history run is reused only
within its history set: its region_md5 holds the md5 of the set (history_set_md5), where a current
run's holds its extract's md5 (for a boundary past the city's extract, the md5 of the merged
region set, which is also recorded in history_sets), and the database's done-key index
includes region_md5. `force` supersedes the existing done run: it is marked `failed` with the
error `superseded by run N`, inside the same transaction that completes the new run, so a failed
forced re-run leaves the old run done.
"""

import errno
import hashlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pyproj import Transformer
from shapely.ops import transform

from velometer.config import (
    CityConfig,
    load_activity,
    load_classifier,
    load_history,
    load_presets,
)
from velometer.db import (
    RunKey,
    canonical_parameters,
    complete_run,
    fail_run,
    fetch_activity,
    fetch_run,
    find_done_run,
    history_runs,
    replace_activity,
    set_population,
    start_run,
    subarea_shas,
    upsert_boundary,
    upsert_history_set,
)
from velometer.memory import PeakRss
from velometer.models import Metric
from velometer.osmium import merge as _merge
from velometer.pipeline.activity import activity as _activity
from velometer.pipeline.drift import drift_diagnostics
from velometer.pipeline.extract import snapshot as _snapshot
from velometer.pipeline.extract import snapshot_name
from velometer.pipeline.history import SNAPSHOT_DATES, history_snapshot_name
from velometer.pipeline.history import city_history as _city_history
from velometer.pipeline.history import snapshot_at as _snapshot_at
from velometer.pipeline.measure import (
    attribute_subareas,
    check_subarea_sums,
    compute_metrics,
    measure,
)
from velometer.pipeline.read import read_ways as _read_ways
from velometer.sources.boundaries import city_boundary as _city_boundary
from velometer.sources.geofabrik import (
    BASE,
    RegionFile,
    history_set_md5,
    region_geometry,
    regions_for,
    set_md5,
    to_3035,
    tolerance_m2,
    uncovered_m2,
)
from velometer.sources.geofabrik import fetch_history as _fetch_history
from velometer.sources.geofabrik import fetch_index as _fetch_index
from velometer.sources.geofabrik import fetch_region as _fetch_region
from velometer.sources.geofabrik import load_index as _load_index
from velometer.subareas import load_subareas as _load_subareas
from velometer.subareas import subarea_set_sha


def region_uncovered_km2(
    region: str, polygon_city_epsg, epsg: int, index: dict[str, dict]
) -> tuple[float, float]:
    """(km² of the polygon outside the region's extract, km² accepted as covered).

    Measured in EPSG:3035 with the regions_for tolerance, so a current run and a history run
    call the same boundary covered.
    """
    to_wgs84 = Transformer.from_crs(epsg, 4326, always_xy=True).transform
    target = to_3035(transform(to_wgs84, polygon_city_epsg))
    region_3035 = to_3035(region_geometry(index, region))
    return uncovered_m2(target, [region_3035]) / 1e6, tolerance_m2(target) / 1e6


def _region_uncovered_km2(
    region: str, polygon_city_epsg, epsg: int, data_dir: Path
) -> tuple[float, float]:
    index = _load_index(_fetch_index(data_dir).path)
    return region_uncovered_km2(region, polygon_city_epsg, epsg, index)


@dataclass(frozen=True)
class RunDeps:
    fetch_region: Callable = _fetch_region
    city_boundary: Callable = _city_boundary
    snapshot: Callable = _snapshot
    read_ways: Callable = _read_ways
    region_uncovered_km2: Callable = _region_uncovered_km2
    fetch_index: Callable = _fetch_index
    load_index: Callable = _load_index
    regions_for: Callable = regions_for
    merge: Callable = _merge
    load_subareas: Callable = _load_subareas
    subarea_shas: Callable = subarea_shas


def _select_regions(polygon_city_epsg, epsg: int, data_dir: Path, deps, select=None):
    """Index snapshot, the index, and the regions covering the polygon (shared by both run kinds).

    `select` defaults to the module's regions_for, looked up at call time.
    """
    snap = deps.fetch_index(data_dir)
    index = deps.load_index(snap.path)
    to_wgs84 = Transformer.from_crs(epsg, 4326, always_xy=True).transform
    selection = (select or regions_for)(transform(to_wgs84, polygon_city_epsg), index)
    return snap, index, selection


def _region_path(index: dict[str, dict], region_id: str) -> str:
    """Download path (`europe/germany/berlin`) of an index region id, from its pbf URL."""
    url = index[region_id].get("pbf")
    prefix, suffix = f"{BASE}/", "-latest.osm.pbf"
    if not url or not (url.startswith(prefix) and url.endswith(suffix)):
        raise ValueError(f"region {region_id} has no current extract in the Geofabrik index")
    return url.removeprefix(prefix).removesuffix(suffix)


def _covering_region(
    conn, city: CityConfig, kind: str, polygon, data_dir: Path, deps: RunDeps, uncovered: float
) -> RegionFile:
    """The current extract of the regions covering a boundary the city's own region does not.

    One region is used as it is; several are merged into data/raw/merged (reused when present).
    The returned RegionFile carries the set md5 and the oldest region timestamp, and the set is
    recorded in history_sets (current sets and history sets never share an md5: the files differ).
    """
    try:
        snap, index, selection = _select_regions(
            polygon, city.epsg, data_dir, deps, deps.regions_for
        )
    except ValueError as e:  # R18: no covering set either
        raise ValueError(
            f"{city.id}/{kind}: region {city.geofabrik_region} leaves {uncovered:.1f} km² of the "
            f"boundary uncovered and no set of regions covers it: {e}"
        ) from e
    files = [deps.fetch_region(_region_path(index, r), data_dir) for r in selection.regions]
    fetched_at = datetime.now(UTC).date().isoformat()  # RegionFile carries no fetch date
    ids = selection.regions  # index ids, as history sets record them (not download paths)
    md5 = set_md5([(rid, f.md5) for rid, f in zip(ids, files, strict=True)])
    if len(files) == 1:
        path = files[0].path
    else:
        path = data_dir / "raw" / "merged" / f"{city.id}_{kind}_{md5[:8]}.osm.pbf"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            deps.merge([f.path for f in files], path)
    upsert_history_set(
        conn,
        md5,
        [
            {"region": rid, "md5": f.md5, "md5_source": "published", "fetched_at": fetched_at}
            for rid, f in zip(ids, files, strict=True)
        ],
        index_path=str(snap.path),
        index_sha256=snap.sha256,
        uncovered_km2=selection.uncovered_km2,
    )
    oldest = min(f.osm_timestamp for f in files)
    return RegionFile(city.geofabrik_region, path, "", md5, oldest)


@dataclass(frozen=True)
class RunOutcome:
    city_id: str
    status: Literal["done", "skipped", "failed"]
    run_id: int | None = None
    error: str | None = None
    year: int | None = None  # history runs: the snapshot year


def _git(*args: str) -> str:
    # run in the source tree so the recorded commit never depends on the process cwd
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent,
    ).stdout


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


def file_sha256(path: Path) -> str:
    """Hex sha256 of the file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_sha256(classifier_path: Path, presets_path: Path, activity_path: Path) -> str:
    """sha256 over the classifier, presets and activity YAML, each as `<name> NUL <bytes> NUL`.

    The separators keep a byte moved from one file's tail to the next file's head from colliding.
    """
    digest = hashlib.sha256()
    for path in (classifier_path, presets_path, activity_path):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def _describe(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}"


class SubareaStaleError(ValueError):
    """A subarea file on disk is not the one `boundaries fetch --subareas` checked."""


def _attribute_subareas(conn, city, boundary_kind, data_dir, deps, ways, result, cfg, polygon):
    """Per-subarea lengths and the set sha, or (None, None) where the city has none.

    Only the LAU run is split. A subarea file whose sha256 differs from (or has no) `subareas`
    row was written without passing the union/overlap checks, so the run fails.
    """
    if boundary_kind != "lau" or city.subareas is None:
        return None, None
    polys = deps.load_subareas(city, data_dir)
    checked = deps.subarea_shas(conn, city.id)
    for p in polys:
        if checked.get(p.subarea_id) != p.sha256:
            raise SubareaStaleError(
                f"{city.id}: subarea {p.subarea_id!r} file sha256 {p.sha256} does not match the "
                f"checked row ({checked.get(p.subarea_id)}); re-run "
                f"`velometer boundaries fetch --city {city.id} --subareas`"
            )
    parts = attribute_subareas(ways, result, cfg, city.epsg, polygon, polys)
    check_subarea_sums(result, parts)
    return parts, subarea_set_sha(polys)


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
    classifier_path = config_dir / "classifier" / f"{classifier}.yaml"
    presets_path = config_dir / "presets.yaml"
    cfg = load_classifier(classifier_path)
    if parameters:
        cfg = cfg.with_parameters(**parameters)
    presets = load_presets(presets_path, cfg).presets
    try:
        region = deps.fetch_region(city.geofabrik_region, data_dir)
        rec, pop = deps.city_boundary(city, boundary_kind, data_dir, region_path=region.path)
        uncovered, tolerance = deps.region_uncovered_km2(
            city.geofabrik_region, rec.polygon, city.epsg, data_dir
        )
        if uncovered > tolerance:  # e.g. a FUA reaching past the city's own extract (R18)
            region = _covering_region(
                conn, city, boundary_kind, rec.polygon, data_dir, deps, uncovered
            )
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
        config_sha256=config_sha256(classifier_path, presets_path, config_dir / "activity.yaml"),
    )
    done = find_done_run(conn, key)
    if done is not None and not force:
        return RunOutcome(city.id, "skipped", done)
    run_id = start_run(conn, key, git_commit=git_commit(), region_md5=region.md5, population=pop)
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
        with PeakRss() as peak:
            ways = deps.read_ways(snap).ways
            result = measure(ways, cfg, city.epsg, boundary=rec.polygon)
            metrics = with_per_100k(compute_metrics(result, presets), pop.value if pop else None)
            parts, sub_sha = _attribute_subareas(
                conn, city, boundary_kind, data_dir, deps, ways, result, cfg, rec.polygon
            )
        complete_run(
            conn,
            run_id,
            city.id,
            result,
            metrics,
            supersedes=done,
            peak_rss_kb=round(peak.peak_mb * 1024),
            subareas=parts,
            subarea_sha=sub_sha,
        )
    except Exception as e:  # noqa: BLE001 - recorded on the run row, then the next city runs
        fail_run(conn, run_id, _describe(e))
        return RunOutcome(city.id, "failed", run_id, _describe(e))
    except BaseException as e:  # Ctrl-C / SystemExit: never leave the row `running`
        fail_run(conn, run_id, _describe(e))
        raise
    return RunOutcome(city.id, "done", run_id)


def run_snapshot_path(run_row: dict, data_dir: Path) -> Path:
    """Where the run's snapshot was written: `pipeline.extract.snapshot`'s name for a current run,
    `pipeline.history.snapshot_at`'s for a history run (whose region_md5 is its set md5)."""
    ts = datetime.fromisoformat(run_row["osm_timestamp"]).astimezone(UTC)
    args = (run_row["city_id"], run_row["boundary_kind"])
    md5, sha = run_row["region_md5"], run_row["boundary_sha256"]
    if run_row["source"] == "history":
        name = history_snapshot_name(*args, md5, sha, ts)
    else:
        name = snapshot_name(*args, ts, md5, sha)
    return Path(data_dir) / "snapshots" / name


def snapshot_path_for_run(conn, run_id: int, data_dir: Path) -> Path:
    """The cached snapshot behind a run; FileNotFoundError (naming the path) when it is gone."""
    path = run_snapshot_path(fetch_run(conn, run_id), data_dir)
    if not path.is_file():
        why = f"run {run_id}: no snapshot file {path} (re-run the city to rebuild it)"
        raise FileNotFoundError(errno.ENOENT, why, str(path))
    return path


@dataclass(frozen=True)
class HistoryDeps:
    fetch_index: Callable = _fetch_index
    load_index: Callable = _load_index
    fetch_history: Callable = _fetch_history
    city_boundary: Callable = _city_boundary
    city_history: Callable = _city_history
    snapshot_at: Callable = _snapshot_at
    read_ways: Callable = _read_ways
    activity: Callable = _activity
    load_subareas: Callable = _load_subareas
    subarea_shas: Callable = subarea_shas


@dataclass(frozen=True)
class HistorySet:
    files: list
    set_md5: str
    uncovered_km2: float
    index_path: Path
    index_sha256: str


def resolve_history_set(
    polygon_city_epsg, epsg: int, data_dir: Path, deps: HistoryDeps
) -> HistorySet:
    """Index snapshot, the regions covering the polygon, and their history files."""
    snap, index, selection = _select_regions(polygon_city_epsg, epsg, data_dir, deps)
    files = [deps.fetch_history(r, data_dir, index) for r in selection.regions]
    return HistorySet(
        files, history_set_md5(files), selection.uncovered_km2, snap.path, snap.sha256
    )


def _iso_z(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


def run_history(
    conn,
    city: CityConfig,
    years: range,
    *,
    data_dir: Path,
    config_dir: Path,
    boundary_kind: str = "lau",
    classifier: str = "v1",
    deps: HistoryDeps | None = None,
    force: bool = False,
) -> list[RunOutcome]:
    """One history run per year (snapshot at Y-01-01 of the city's history file), resumable.

    A done history run is reused when its (city, year, boundary, classifier, config) key and its
    history set match; a new history set (new download) makes every year run again. The
    population of the boundary is held constant across years. Yearly mapping activity is written
    once per (city, boundary, history set) and always covers the config/history.yaml years plus
    the year after the last (the current point's window), whatever `years` this call runs.
    Failures before the first year (boundary, index,
    download, history extract) return one failed outcome and write no run row; a failing year
    records a failed run and the next year runs.
    """
    deps = deps or HistoryDeps()
    classifier_path = config_dir / "classifier" / f"{classifier}.yaml"
    presets_path = config_dir / "presets.yaml"
    cfg = load_classifier(classifier_path)
    presets = load_presets(presets_path, cfg).presets
    activity_cfg = load_activity(config_dir / "activity.yaml")
    series_years = load_history(config_dir / "history.yaml").year_range()
    activity_years = range(series_years.start, series_years.stop + 1)
    try:
        rec, pop = deps.city_boundary(city, boundary_kind, data_dir)
        upsert_boundary(conn, rec.boundary)
        if pop is not None:
            set_population(conn, city.id, pop)
        hs = resolve_history_set(rec.polygon, city.epsg, data_dir, deps)
        hist = deps.city_history(
            city.id,
            boundary_kind,
            hs.files,
            hs.set_md5,
            rec.geojson_path,
            rec.boundary.sha256,
            data_dir,
        )
        upsert_history_set(
            conn,
            hs.set_md5,
            [
                {
                    "region": f.region,
                    "md5": f.md5,
                    "md5_source": f.md5_source,
                    "fetched_at": f.fetched_at.isoformat(),
                }
                for f in hs.files
            ],
            index_path=str(hs.index_path),
            index_sha256=hs.index_sha256,
            uncovered_km2=hs.uncovered_km2,
        )
    except Exception as e:  # noqa: BLE001 - no run row yet; report and let the next city run
        return [RunOutcome(city.id, "failed", None, _describe(e))]
    params = canonical_parameters(cfg.parameters.model_dump())
    sha = config_sha256(classifier_path, presets_path, config_dir / "activity.yaml")
    activity_sha = file_sha256(config_dir / "activity.yaml")
    done_before = history_runs(
        conn,
        city.id,
        boundary_kind,
        classifier_version=cfg.version,
        classifier_parameters=params,
        config_sha256=sha,
        history_set_md5=hs.set_md5,
    )
    outcomes = []
    for ts in SNAPSHOT_DATES(years):
        year = ts.year
        key = RunKey(
            city_id=city.id,
            osm_timestamp=_iso_z(ts),
            boundary_kind=boundary_kind,
            boundary_sha256=rec.boundary.sha256,
            classifier_version=cfg.version,
            classifier_parameters=params,
            config_sha256=sha,
            source="history",
        )
        done = done_before.get(key.osm_timestamp)
        if done is not None and not force:
            outcomes.append(RunOutcome(city.id, "skipped", done, year=year))
            continue
        run_id = start_run(
            conn, key, git_commit=git_commit(), region_md5=hs.set_md5, population=pop
        )
        try:
            snap = deps.snapshot_at(hist, ts, data_dir)
            with PeakRss() as peak:
                ways = deps.read_ways(snap).ways
                result = measure(ways, cfg, city.epsg, boundary=rec.polygon)
                metrics = with_per_100k(
                    compute_metrics(result, presets), pop.value if pop else None
                )
                parts, sub_sha = _attribute_subareas(
                    conn, city, boundary_kind, data_dir, deps, ways, result, cfg, rec.polygon
                )
            diagnostics = drift_diagnostics(result, ways, activity_cfg)
            diagnostics["uncovered_km2"] = hs.uncovered_km2
            complete_run(
                conn,
                run_id,
                city.id,
                result,
                metrics,
                supersedes=done,
                diagnostics=diagnostics,
                peak_rss_kb=round(peak.peak_mb * 1024),
                subareas=parts,
                subarea_sha=sub_sha,
            )
        except Exception as e:  # noqa: BLE001 - recorded on the run row, then the next year runs
            fail_run(conn, run_id, _describe(e))
            outcomes.append(RunOutcome(city.id, "failed", run_id, _describe(e), year))
            continue
        except BaseException as e:  # Ctrl-C / SystemExit: never leave the row `running`
            fail_run(conn, run_id, _describe(e))
            raise
        outcomes.append(RunOutcome(city.id, "done", run_id, year=year))
    if years:
        _write_activity(
            conn,
            city,
            boundary_kind,
            activity_years,
            hist,
            hs.set_md5,
            activity_sha,
            activity_cfg,
            deps,
            outcomes,
        )
    return outcomes


def _write_activity(
    conn, city, boundary_kind, wanted, hist, set_md5, activity_sha, activity_cfg, deps, outcomes
) -> None:
    """Replace the (set, activity.yaml)'s activity rows with `wanted` (series years plus last + 1).

    The standard window rule makes year last + 1 cover [last-01-01, end of the history file),
    which is the current point's window; the series shows it only with a current point. Rows are
    kept when every year was reused and the stored years already match.
    """
    if all(o.status == "skipped" for o in outcomes):
        have = [a.year for a in fetch_activity(conn, city.id, boundary_kind, set_md5, activity_sha)]
        if have == list(wanted):
            return
    try:
        rows = deps.activity(
            hist,
            wanted,
            activity_cfg,
            city_id=city.id,
            boundary_kind=boundary_kind,
            history_set_md5=set_md5,
        )
        replace_activity(conn, city.id, boundary_kind, set_md5, activity_sha, rows)
    except Exception as e:  # noqa: BLE001 - the year runs stand; surface the failure as an outcome
        outcomes.append(RunOutcome(city.id, "failed", None, f"activity: {_describe(e)}"))
