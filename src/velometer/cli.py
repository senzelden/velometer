"""velometer command-line interface."""

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path

import httpx
import typer

from velometer import selection as _selection
from velometer.config import (
    BASES,
    CityConfig,
    ConfigError,
    PresetsConfig,
    default_config_dir,
    load_cities,
)
from velometer.db import SCHEMA_VERSION, SchemaError, create_schema, open_db, upsert_cities
from velometer.selection import Selector


class PlainOneway(StrEnum):
    traffic_side = "traffic_side"
    both_sides = "both_sides"


class CleanCitiesBasis(StrEnum):
    per_side = "per_side"
    qecio_weighted = "qecio_weighted"


app = typer.Typer(no_args_is_help=True, help="Protected cycling infrastructure from OSM.")
boundaries_app = typer.Typer(no_args_is_help=True, help="City boundaries.")
osm_app = typer.Typer(no_args_is_help=True, help="OSM region extracts.")
app.add_typer(boundaries_app, name="boundaries")
app.add_typer(osm_app, name="osm")
external_app = typer.Typer(no_args_is_help=True, help="External comparison figures.")
app.add_typer(external_app, name="external")
auth_app = typer.Typer(no_args_is_help=True, help="Geofabrik internal-server login.")
app.add_typer(auth_app, name="auth")

report_app = typer.Typer(no_args_is_help=True, help="Report surfaces (read-only).")
app.add_typer(report_app, name="report")

DB_OPT = typer.Option(Path("velometer.sqlite"), "--db", help="SQLite database path.")
DATA_OPT = typer.Option(Path("data"), "--data", help="Data directory.")
CONFIG_OPT = typer.Option(default_config_dir(), "--config-dir", help="Config directory.")
CC_BASIS_OPT = typer.Option(
    None,
    "--clean-cities-basis",
    help="Report Clean Cities figures on this length basis instead of the presets.yaml value "
    "(reporting only: every basis is stored, so no rerun is needed).",
)
SWITCH_HINT = "(switch with --clean-cities-basis)"


@contextmanager
def _open_schema(db: Path) -> Iterator:
    """open_db + create_schema; a schema that cannot be used is exit 1, not a traceback."""
    with open_db(db) as conn:
        try:
            create_schema(conn)
        except SchemaError as e:
            typer.echo(f"database error: {e}", err=True)
            raise typer.Exit(1) from e
        yield conn


@app.callback()
def main() -> None:
    """velometer: reproducible OSM cycling-infrastructure measurement."""


@app.command()
def migrate(
    activity_sha: str = typer.Option(
        ...,
        "--activity-sha",
        help="sha256 (64 lowercase hex) of the activity.yaml the stored activity rows were "
        "computed with; needed only to migrate a v5 database that has activity rows.",
    ),
    db: Path = DB_OPT,
) -> None:
    """Migrate the database to the current schema (v5 to v6 needs --activity-sha)."""
    if not re.fullmatch(r"[0-9a-f]{64}", activity_sha):
        typer.echo("error: --activity-sha must be 64 lowercase hex characters", err=True)
        raise typer.Exit(2)
    with open_db(db) as conn:
        try:
            create_schema(conn, activity_sha256_for_v5=activity_sha)
        except SchemaError as e:
            typer.echo(f"database error: {e}", err=True)
            raise typer.Exit(1) from e
    typer.echo(f"{db}: schema v{SCHEMA_VERSION}")


@app.command()
def init(
    db: Path = typer.Option(Path("velometer.sqlite"), help="SQLite database path."),  # noqa: B008
    config_dir: Path = typer.Option(default_config_dir(), help="Config directory."),  # noqa: B008
) -> None:
    """Create the SQLite schema and load config/cities.yaml (idempotent)."""
    try:
        cities = load_cities(config_dir / "cities.yaml")
    except ConfigError as e:
        typer.echo(f"config error: {e}", err=True)
        raise typer.Exit(1) from e
    with _open_schema(db) as conn:
        n = upsert_cities(conn, cities)
    typer.echo(f"{db}: schema ready, {n} cities loaded")


def _params_line(cfg) -> str:
    params = " ".join(f"{k}={v}" for k, v in cfg.parameters.model_dump().items())
    return f"classifier {cfg.version} ({params})"


def _presets_line(config: PresetsConfig) -> str:
    params = " ".join(f"{k}={v}" for k, v in config.parameters.model_dump().items())
    return f"presets ({params})"


def _with_basis(config: PresetsConfig, basis: CleanCitiesBasis | None) -> PresetsConfig:
    return config if basis is None else config.with_parameters(clean_cities_basis=basis.value)


def _fmt_value(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1f}%"


def _other_basis_lines(rows: dict[str, list], config: PresetsConfig) -> list[str]:
    """`<preset> on <other basis>: <values> (switch ...)` for each parameterised preset.

    `rows` maps a label ("" for a single run) to that run's metrics.
    """
    from velometer.pipeline.measure import select_metric

    lines = []
    for p in config.presets:
        if not p.parameterised:
            continue
        selected = config.parameters.resolve(p.basis)
        for basis in (b for b in BASES if b != selected):
            alt = config.with_parameters(**{p.basis.parameter: basis})
            values = []
            for label, metrics in rows.items():
                m = select_metric(metrics, p.id, alt)
                values.append(f"{label} {_fmt_value(m and m.value)}".strip())
            lines.append(f"{p.id} on {basis}: {', '.join(values)} {SWITCH_HINT}")
    return lines


def _config_error(e: ConfigError):
    typer.echo(f"config error: {e}", err=True)
    return typer.Exit(1)


def _all_cities(config_dir: Path) -> list[CityConfig]:
    try:
        return load_cities(config_dir / "cities.yaml")
    except ConfigError as e:
        raise _config_error(e) from e


def _select_cities(config_dir: Path, wanted: list[str] | None) -> list[CityConfig]:
    cities = _all_cities(config_dir)
    if wanted is None:
        return cities
    by_id = {c.id: c for c in cities}
    unknown = [w for w in wanted if w not in by_id]
    if unknown:
        typer.echo(
            f"error: unknown city {', '.join(unknown)} (known: {', '.join(by_id)})", err=True
        )
        raise typer.Exit(2)
    return [by_id[w] for w in wanted]


def run_selector(
    config_dir: Path, classifier: str, basis: CleanCitiesBasis | None = None
) -> Selector:
    """selection.run_selector, with a config error as exit 1."""
    try:
        return _selection.run_selector(config_dir, classifier, basis)
    except ConfigError as e:
        raise _config_error(e) from e


def report_selector(config_dir: Path) -> Selector:
    """selection.report_selector, with a config error as exit 1."""
    try:
        return _selection.report_selector(config_dir)
    except ConfigError as e:
        raise _config_error(e) from e


def _report_classifier(config_dir: Path, classifier: str | None) -> str:
    """The explicit --classifier, else the report classifier of config/report.yaml."""
    from velometer.config import load_report

    if classifier is not None:
        return classifier
    try:
        return load_report(
            config_dir / "report.yaml", config_dir / "presets.yaml"
        ).report_classifier
    except ConfigError as e:
        raise _config_error(e) from e


def _run_cities(
    selected: list[CityConfig],
    *,
    db: Path,
    data: Path,
    config_dir: Path,
    boundary: str,
    classifier: str,
    force: bool,
    plain: PlainOneway | None,
) -> list:
    from velometer import run as run_mod
    from velometer.config import load_classifier

    parameters = {"plain_cycleway_on_oneway": plain.value} if plain is not None else None
    try:
        cfg = load_classifier(config_dir / "classifier" / f"{classifier}.yaml")
        if parameters:
            cfg = cfg.with_parameters(**parameters)
    except ConfigError as e:
        raise _config_error(e) from e
    typer.echo(_params_line(cfg))
    deps = run_mod.RunDeps()
    all_cities = _all_cities(config_dir)
    outcomes = []
    with _open_schema(db) as conn:
        upsert_cities(conn, all_cities)
        for city in selected:
            out = run_mod.run_city(
                conn,
                city,
                data_dir=data,
                config_dir=config_dir,
                boundary_kind=boundary,
                classifier=classifier,
                parameters=parameters,
                force=force,
                deps=deps,
            )
            line = f"{city.id} {out.status} run={out.run_id if out.run_id is not None else '-'}"
            typer.echo(f"{line} {out.error}" if out.error else line)
            outcomes.append(out)
    return outcomes


@app.command()
def classify(
    file: Path | None = typer.Option(  # noqa: B008
        None, exists=True, dir_okay=False, help=".osm or .osm.pbf (file mode)."
    ),
    epsg: int | None = typer.Option(None, help="Projected CRS for lengths (file mode)."),
    city: str | None = typer.Option(None, help="City id: persisted run (city mode)."),
    boundary: str = typer.Option("lau", help="Boundary kind (city mode)."),
    force: bool = typer.Option(False, "--force", help="Re-run even if a done run exists."),
    classifier: str = typer.Option("v1", help="Classifier version (config/classifier/<v>.yaml)."),
    config_dir: Path = CONFIG_OPT,
    db: Path = DB_OPT,
    data: Path = DATA_OPT,
    plain_cycleway_on_oneway: PlainOneway | None = typer.Option(  # noqa: B008
        None,
        help="Override the classifier parameter: plain cycleway=* on a oneway road counts on "
        "the traffic side only, or on both sides.",
    ),
    clean_cities_basis: CleanCitiesBasis | None = CC_BASIS_OPT,
) -> None:
    """Classify one OSM file (--file/--epsg) or run one city into the database (--city)."""
    if file is not None and city is not None:
        typer.echo("error: --file and --city are mutually exclusive", err=True)
        raise typer.Exit(2)
    if city is not None:
        outcomes = _run_cities(
            _select_cities(config_dir, [city]),
            db=db,
            data=data,
            config_dir=config_dir,
            boundary=boundary,
            classifier=classifier,
            force=force,
            plain=plain_cycleway_on_oneway,
        )
        _print_city_metrics(
            outcomes, db, boundary, run_selector(config_dir, classifier, clean_cities_basis)
        )
        if outcomes[0].status == "failed":
            raise typer.Exit(1)
        return
    if file is None or epsg is None:
        typer.echo("error: give --file with --epsg, or --city", err=True)
        raise typer.Exit(2)
    _classify_file(file, epsg, classifier, config_dir, plain_cycleway_on_oneway, clean_cities_basis)


def _print_city_metrics(outcomes: list, db: Path, boundary: str, sel: Selector) -> None:
    """The preset values of each run the command made or found (done and skipped), if any."""
    from velometer.db import fetch_run_results
    from velometer.pipeline.measure import select_metric

    with _open_schema(db) as conn:
        for out in outcomes:
            if out.run_id is None or out.status == "failed":
                continue
            metrics = fetch_run_results(conn, out.run_id).metrics
            typer.echo(_presets_line(sel.presets))
            for p in sel.presets.presets:
                m = select_metric(metrics, p.id, sel.presets)
                typer.echo(f"{out.city_id} {p.id}: {_fmt_value(m and m.value)}")
            for line in _other_basis_lines({out.city_id: metrics}, sel.presets):
                typer.echo(line)


def _classify_file(
    file: Path,
    epsg: int,
    classifier: str,
    config_dir: Path,
    plain: PlainOneway | None,
    basis: CleanCitiesBasis | None,
) -> None:
    from velometer.config import load_classifier, load_presets
    from velometer.pipeline.geometry import require_projected
    from velometer.pipeline.measure import compute_metrics, measure, select_metric
    from velometer.pipeline.read import read_ways

    try:
        require_projected(epsg)
    except ValueError as e:
        typer.echo(f"error: --epsg {epsg}: {e}", err=True)
        raise typer.Exit(1) from e
    try:
        cfg = load_classifier(config_dir / "classifier" / f"{classifier}.yaml")
        presets = _with_basis(load_presets(config_dir / "presets.yaml", cfg), basis)
    except ConfigError as e:
        raise _config_error(e) from e
    if plain is not None:
        cfg = cfg.with_parameters(plain_cycleway_on_oneway=plain.value)
    read = read_ways(file)
    result = measure(read.ways, cfg, epsg)
    typer.echo(_params_line(cfg))
    typer.echo(_presets_line(presets))
    typer.echo(f"ways: {len(read.ways)}  skipped ways: {len(read.skipped)}")
    typer.echo("\ntier  subtype            basis            km       ways")
    for t in result.tier_lengths:
        typer.echo(
            f"{t.tier:<5} {t.subtype or '-':<18} {t.length_basis:<16} "
            f"{t.length_km:>8.3f} {t.n_ways:>6}"
        )
    typer.echo("\nroad class               km")
    for r in result.road_lengths:
        typer.echo(f"{r.road_class:<24} {r.length_km:>8.3f}")
    typer.echo("\npreset               value     num km   den km")
    metrics = compute_metrics(result, presets.presets)
    for p in presets.presets:
        m = select_metric(metrics, p.id, presets)
        if m is None:
            continue
        value = "n/a" if m.value is None else f"{m.value:.1f}"
        typer.echo(f"{m.preset:<20} {value:>7} {m.numerator_km:>9.3f} {m.denominator_km:>8.3f}")
    for line in _other_basis_lines({"": metrics}, presets):
        typer.echo(line)
    typer.echo(
        f"\nparallel duplicates flagged: {len(result.duplicates)}  "
        f"dual-carriageway ways: {len(result.dual_pairs)}"
    )
    po = result.plain_oneway
    line = f"plain cycleway on oneway roads: {po.n_ways} ways, {po.length_km:.3f} km road"
    if po.n_ways:
        shifts = ", ".join(f"{t} {v:+.3f} km" for t, v in po.delta_per_side_km.items()) or "none"
        line += f"; switching to {po.other_mode} changes per_side (non-excluded tiers): {shifts}"
    typer.echo(line)
    if result.unknown_values:
        typer.echo(f"unknown cycleway values: {result.unknown_values}")


def _parse_years(value: str | None) -> range | None:
    """`A-B` (inclusive) -> range(A, B + 1); anything else, or B < A, is exit 2."""
    if value is None:
        return None
    m = re.fullmatch(r"\s*(\d{4})\s*-\s*(\d{4})\s*", value)
    if m is None or int(m[2]) < int(m[1]):
        typer.echo(f"error: --years {value!r}: expected A-B with A <= B, e.g. 2018-2026", err=True)
        raise typer.Exit(2)
    return range(int(m[1]), int(m[2]) + 1)


def _run_history_cities(
    selected: list[CityConfig],
    years: range,
    *,
    db: Path,
    data: Path,
    config_dir: Path,
    boundary: str,
    classifier: str,
    force: bool,
) -> list:
    from velometer import run as run_mod

    deps = run_mod.HistoryDeps()
    outcomes = []
    with _open_schema(db) as conn:
        upsert_cities(conn, _all_cities(config_dir))
        for city in selected:
            for out in run_mod.run_history(
                conn,
                city,
                years,
                data_dir=data,
                config_dir=config_dir,
                boundary_kind=boundary,
                classifier=classifier,
                deps=deps,
                force=force,
            ):
                run = out.run_id if out.run_id is not None else "-"
                year = out.year if out.year is not None else "-"
                line = f"{city.id} {year} {out.status} run={run}"
                typer.echo(f"{line} {out.error}" if out.error else line)
                outcomes.append(out)
    return outcomes


@app.command()
def run(
    cities: str = typer.Option("all", help="'all' or comma-separated city ids."),
    boundary: str = typer.Option("lau", help="Boundary kind."),
    force: bool = typer.Option(False, "--force", help="Re-run even if a done run exists."),
    classifier: str | None = typer.Option(
        None,
        "--classifier",
        help="Classifier version (default: report_classifier in config/report.yaml).",
    ),
    config_dir: Path = CONFIG_OPT,
    db: Path = DB_OPT,
    data: Path = DATA_OPT,
    plain_cycleway_on_oneway: PlainOneway | None = typer.Option(  # noqa: B008
        None,
        help="Override the classifier parameter: plain cycleway=* on a oneway road counts on "
        "the traffic side only, or on both sides.",
    ),
    years: str | None = typer.Option(
        None,
        "--years",
        help="History run: one snapshot per year A-B inclusive (e.g. 2018-2026), at Y-01-01, "
        "from Geofabrik full history (needs VELOMETER_OSM_USER/PASSWORD).",
    ),
) -> None:
    """Run cities end to end (region, boundary, clip, classify, persist); done runs are skipped."""
    classifier = _report_classifier(config_dir, classifier)
    year_range = _parse_years(years)
    wanted = None if cities == "all" else [c.strip() for c in cities.split(",") if c.strip()]
    if year_range is not None:
        if plain_cycleway_on_oneway is not None:
            typer.echo("error: --plain-cycleway-on-oneway does not apply to --years", err=True)
            raise typer.Exit(2)
        history = _run_history_cities(
            _select_cities(config_dir, wanted),
            year_range,
            db=db,
            data=data,
            config_dir=config_dir,
            boundary=boundary,
            classifier=classifier,
            force=force,
        )
        if any(o.status == "failed" for o in history):
            raise typer.Exit(1)
        return
    outcomes = _run_cities(
        _select_cities(config_dir, wanted),
        db=db,
        data=data,
        config_dir=config_dir,
        boundary=boundary,
        classifier=classifier,
        force=force,
        plain=plain_cycleway_on_oneway,
    )
    if any(o.status == "failed" for o in outcomes):
        raise typer.Exit(1)


@boundaries_app.command("fetch")
def boundaries_fetch(
    city: str | None = typer.Option(None, help="City id (default: all cities)."),
    kind: str = typer.Option("all", help="lau, fua, osm_admin or all."),
    config_dir: Path = CONFIG_OPT,
    db: Path = DB_OPT,
    data: Path = DATA_OPT,
) -> None:
    """Fetch and store city boundaries (and the LAU population)."""
    from velometer import run as run_mod
    from velometer.db import set_population, upsert_boundary

    deps = run_mod.RunDeps()
    kinds = ("lau", "fua", "osm_admin") if kind == "all" else (kind,)
    if any(k not in ("lau", "fua", "osm_admin") for k in kinds):
        typer.echo(f"error: unknown --kind {kind!r}", err=True)
        raise typer.Exit(2)
    selected = _select_cities(config_dir, [city] if city else None)
    failed = False
    with _open_schema(db) as conn:
        upsert_cities(conn, _all_cities(config_dir))
        for c in selected:
            region_path = None
            for k in kinds:
                code = {"lau": c.lau_code, "fua": c.fua_code, "osm_admin": True}[k]
                if not code and kind == "all":
                    typer.echo(f"{c.id} {k} skipped (no code configured)")
                    continue
                try:
                    if k == "osm_admin" and region_path is None:
                        region_path = deps.fetch_region(c.geofabrik_region, data).path
                    rec, pop = deps.city_boundary(c, k, data, region_path=region_path)
                    upsert_boundary(conn, rec.boundary)
                    if pop is not None:
                        set_population(conn, c.id, pop)
                except Exception as e:  # noqa: BLE001 - report per boundary, keep going
                    typer.echo(f"{c.id} {k} failed {type(e).__name__}: {e}", err=True)
                    failed = True
                    continue
                popmsg = f" population={pop.value}" if pop else ""
                typer.echo(f"{c.id} {k} area_km2={rec.boundary.area_km2:.1f}{popmsg}")
    if failed:
        raise typer.Exit(1)


@external_app.command("load")
def external_load(
    figures: Path | None = typer.Option(  # noqa: B008
        None, "--figures", exists=True, dir_okay=False, help="Curated CSV (default: config)."
    ),
    qecio: bool = typer.Option(True, "--qecio/--no-qecio", help="Fetch and load QECIO v2.10."),
    bikenetkit: bool = typer.Option(
        True, "--bikenetkit/--no-bikenetkit", help="Fetch and load BikeNetKit."
    ),
    refresh_qecio: bool = typer.Option(
        False, "--refresh-qecio", help="Delete the cached QECIO file and download it again."
    ),
    config_dir: Path = CONFIG_OPT,
    db: Path = DB_OPT,
    data: Path = DATA_OPT,
) -> None:
    """Load curated, QECIO and BikeNetKit figures into external_figures."""
    import zipfile

    from pyogrio.errors import DataSourceError

    from velometer.sources import external
    from velometer.sources.download import DownloadError

    cities = _all_cities(config_dir)
    try:
        with open_db(db) as conn:
            create_schema(conn)
            upsert_cities(conn, cities)
            counts = external.load_all(
                conn,
                data,
                config_dir,
                qecio=qecio,
                bikenetkit=bikenetkit,
                figures_csv=figures,
                refresh_qecio=refresh_qecio,
            )
    except (
        DownloadError,
        SchemaError,
        ValueError,
        KeyError,
        OSError,
        zipfile.BadZipFile,
        DataSourceError,
    ) as e:
        typer.echo(f"external load failed: {type(e).__name__}: {e}", err=True)
        raise typer.Exit(1) from e
    for source, n in counts.items():
        typer.echo(f"{source} {n} rows")


@osm_app.command("fetch-history")
def osm_fetch_history(
    region: str | None = typer.Option(
        None, help="Geofabrik region id, e.g. europe/germany/berlin."
    ),
    city: str | None = typer.Option(None, help="City id: fetch the regions covering its boundary."),
    boundary: str = typer.Option("lau", help="Boundary kind (with --city)."),
    config_dir: Path = CONFIG_OPT,
    data: Path = DATA_OPT,
) -> None:
    """Download full-history PBFs (login via VELOMETER_OSM_USER/PASSWORD); prints no secrets."""
    from velometer import run as run_mod

    if (region is None) == (city is None):
        typer.echo("error: give exactly one of --region and --city", err=True)
        raise typer.Exit(2)
    deps = run_mod.HistoryDeps()
    try:
        if city is not None:
            (c,) = _select_cities(config_dir, [city])
            rec, _ = deps.city_boundary(c, boundary, data)
            files = run_mod.resolve_history_set(rec.polygon, c.epsg, data, deps).files
        else:
            index = deps.load_index(deps.fetch_index(data).path)
            if region not in index or not index[region]["history"]:
                typer.echo(f"error: no history file for region {region!r}", err=True)
                raise typer.Exit(2)
            files = [deps.fetch_history(region, data, index)]
    except typer.Exit:
        raise
    except Exception as e:  # noqa: BLE001 - one readable line, never a traceback with headers
        typer.echo(f"error: {type(e).__name__}: {e}", err=True)
        raise typer.Exit(1) from e
    for f in files:
        typer.echo(
            f"region={f.region} path={f.path} md5={f.md5} md5_source={f.md5_source} "
            f"size={f.path.stat().st_size}"
        )


@osm_app.command("fetch")
def osm_fetch(
    city: str | None = typer.Option(None, help="City id (default: all cities)."),
    config_dir: Path = CONFIG_OPT,
    data: Path = DATA_OPT,
) -> None:
    """Download each city's Geofabrik region extract (md5-verified)."""
    from velometer import run as run_mod

    deps = run_mod.RunDeps()
    failed = False
    for c in _select_cities(config_dir, [city] if city else None):
        try:
            rf = deps.fetch_region(c.geofabrik_region, data)
        except Exception as e:  # noqa: BLE001 - report per city, keep going
            typer.echo(f"{c.id} failed {type(e).__name__}: {e}", err=True)
            failed = True
            continue
        typer.echo(
            f"{c.id} region={rf.region} path={rf.path} "
            f"osm_timestamp={rf.osm_timestamp.isoformat()} md5={rf.md5}"
        )
    if failed:
        raise typer.Exit(1)


RESULT_COLUMNS = (
    ["city", "osm_date", "headline", "ecf_qecio", "clean_cities"]
    + [f"{t}_km" for t in "ABCDE"]
    + ["main_km", "headline_per_100k"]
)


CLASSIFIER_REPORT_OPT = typer.Option(
    None,
    "--classifier",
    help="Report runs of this classifier with its default parameters"
    " (default: report_classifier in config/report.yaml).",
)


@app.command()
def results(
    boundary: str = typer.Option("lau", help="Boundary kind."),
    classifier: str | None = CLASSIFIER_REPORT_OPT,
    config_dir: Path = CONFIG_OPT,
    db: Path = DB_OPT,
    clean_cities_basis: CleanCitiesBasis | None = CC_BASIS_OPT,
) -> None:
    """One row per city: the latest done run's headline metrics and per-side tier km.

    Reports runs of the config on disk (classifier and presets YAML), not older ones.
    """
    from velometer.db import fetch_cities, fetch_run_results
    from velometer.pipeline.measure import select_metric

    sel = run_selector(config_dir, _report_classifier(config_dir, classifier), clean_cities_basis)

    def fmt(v: float | None) -> str:
        return "n/a" if v is None else f"{v:.1f}"

    rows = []
    metrics_by_city: dict[str, list] = {}
    stale: list[str] = []
    with _open_schema(db) as conn:
        for c in fetch_cities(conn):
            run_id = sel.latest(conn, c.id, boundary)
            if run_id is None:
                if sel.stale(conn, c.id, boundary):
                    stale.append(c.id)
                continue
            r = fetch_run_results(conn, run_id)
            metrics_by_city[c.id] = r.metrics
            head, ecf, clean = (
                select_metric(r.metrics, p, sel.presets)
                for p in ("ours_headline", "ecf_qecio", "clean_cities_2025")
            )
            tier_km = dict.fromkeys("ABCDE", 0.0)
            for t in r.tier_lengths:
                if t.length_basis == "per_side" and t.tier in tier_km:
                    tier_km[t.tier] += t.length_km
            main = next(
                (x.length_km for x in r.road_lengths if x.road_class == "main_excl_motorway"),
                None,
            )
            rows.append(
                [
                    c.id,
                    r.osm_timestamp[:10],
                    fmt(head and head.value),
                    fmt(ecf and ecf.value),
                    fmt(clean and clean.value),
                ]
                + [fmt(tier_km[t]) for t in "ABCDE"]
                + [fmt(main), fmt(head and head.per_100k)]
            )
    for cid in stale:
        typer.echo(
            f"note: {cid} has no done {boundary!r} run of the current config {sel.short_sha}"
        )
    if not rows:
        typer.echo(f"no done runs for boundary {boundary!r} of the current config {sel.short_sha}")
        return
    typer.echo(_presets_line(sel.presets))
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(RESULT_COLUMNS)]
    typer.echo("  ".join(h.ljust(w) for h, w in zip(RESULT_COLUMNS, widths, strict=True)).rstrip())
    for r in rows:
        typer.echo("  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)).rstrip())
    for line in _other_basis_lines(metrics_by_city, sel.presets):
        typer.echo(line)


@app.command()
def reconcile(
    city: list[str] = typer.Option(  # noqa: B008
        None, "--city", help="City id (repeatable); default all."
    ),
    boundary: str = typer.Option("lau", help="Boundary kind."),
    classifier: str | None = CLASSIFIER_REPORT_OPT,
    write: bool = typer.Option(False, "--write", help="Rewrite the generated report block."),
    check: bool = typer.Option(
        False,
        "--check",
        help="Exit 1 if a flagged gap lacks an explanation, a required comparison has no figure,"
        " or the explanations name another run than the latest.",
    ),
    report: Path = typer.Option(  # noqa: B008
        Path("docs/reconciliation.md"), "--report", help="Report file."
    ),
    db: Path = DB_OPT,
    config_dir: Path = CONFIG_OPT,
    clean_cities_basis: CleanCitiesBasis | None = CC_BASIS_OPT,
) -> None:
    """Compare our latest run per city (of the config on disk) with external figures.

    Gaps use the Clean Cities basis selected by presets.yaml or --clean-cities-basis; the
    other basis is listed as informational `~<basis>` rows. Flags and --check use the selected
    one only.
    """
    from velometer import reconcile as rc

    if write and clean_cities_basis is not None:
        typer.echo(
            "error: --write follows presets.yaml; drop --clean-cities-basis "
            "(or change clean_cities_basis in presets.yaml and re-run)",
            err=True,
        )
        raise typer.Exit(2)
    wanted = {c.id for c in _select_cities(config_dir, city or None)}
    sel = run_selector(config_dir, _report_classifier(config_dir, classifier), clean_cities_basis)
    config_path = config_dir / "reconcile.yaml"
    all_by_city: dict[str, rc.CityReport] = {}
    skipped: list[str] = []
    with _open_schema(db) as conn:
        for c in _all_cities(config_dir):
            rep = rc.reconcile_city(
                conn,
                c.id,
                config_path,
                boundary,
                classifier_version=sel.version,
                classifier_parameters=sel.parameters,
                config_sha256=sel.config_sha256,
                presets=sel.presets,
            )
            if rep is None:
                if c.id in wanted:
                    skipped.append(c.id)
                    typer.echo(
                        f"note: {c.id} has no done {boundary!r} run of the current config "
                        f"{sel.short_sha}, skipped"
                    )
                continue
            all_by_city[c.id] = rep
    shown = {k: v for k, v in all_by_city.items() if k in wanted}
    typer.echo(_presets_line(sel.presets))
    typer.echo(rc.render_block(shown))
    try:
        if write:  # every city with a done run, so --city never drops other tables
            rc.write_report(report, all_by_city)
        if check:
            gaps = [g for r in shown.values() for g in r.gaps]
            missing = rc.missing_explanations(report, gaps)
            for key in missing:
                typer.echo(f"missing explanation: ### {key}", err=True)
            required = rc.missing_required(shown, rc.load_comparisons(config_path))
            for key in required:
                typer.echo(f"required comparison has no external figure: {key}", err=True)
            stale_runs = rc.unexplained_runs(report, shown)
            for line in stale_runs:
                typer.echo(f"explanations out of date: {line}", err=True)
            if stale_runs:
                typer.echo(
                    "after re-checking the explanations, set: "
                    + rc.explained_against_marker(all_by_city),
                    err=True,
                )
            for key in rc.stale_explanations(report, gaps, set(shown)):
                typer.echo(f"warning: ### {key} matches no flagged gap", err=True)
            for cid in skipped:
                typer.echo(
                    f"no done run for {cid} of the current config {sel.short_sha}: cannot check it",
                    err=True,
                )
            if missing or required or stale_runs or skipped:
                raise typer.Exit(1)
    except (OSError, ValueError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def timeseries(
    city: list[str] = typer.Option(  # noqa: B008
        None, "--city", help="City id (repeatable); default all."
    ),
    boundary: str = typer.Option(
        None,
        "--boundary",
        help="lau or fua; default both (--check requires the kinds in config/history.yaml).",
    ),
    classifier: str | None = typer.Option(
        None,
        "--classifier",
        help="Report runs of this classifier with its default parameters"
        " (default: report_classifier in config/report.yaml).",
    ),
    write: bool = typer.Option(False, "--write", help="Rewrite the generated report block."),
    check: bool = typer.Option(
        False,
        "--check",
        help="Exit 1 if a flagged city-year lacks an explanation, the explanations name another"
        " history set than the current one, or a required city/kind lacks a"
        " year of config/history.yaml.",
    ),
    report: Path = typer.Option(  # noqa: B008
        Path("docs/review/m3_timeseries.md"), "--report", help="Report file."
    ),
    db: Path = DB_OPT,
    config_dir: Path = CONFIG_OPT,
) -> None:
    """Yearly series (history runs plus the current run) per city and boundary, with flags.

    Uses each city's most recently recorded history set that has done runs of the config on disk.
    """
    from velometer import timeseries as ts
    from velometer.config import load_activity, load_history

    if boundary not in (None, "lau", "fua"):
        typer.echo("error: --boundary must be lau or fua", err=True)
        raise typer.Exit(2)
    wanted = {c.id for c in _select_cities(config_dir, city or None)}
    kinds = (boundary,) if boundary else ("lau", "fua")
    try:
        cfg = load_activity(config_dir / "activity.yaml")
        history_cfg = load_history(config_dir / "history.yaml")
    except ConfigError as e:
        raise _config_error(e) from e
    sel = run_selector(config_dir, _report_classifier(config_dir, classifier))
    built: dict[tuple[str, str], ts.CitySeries] = {}
    with _open_schema(db) as conn:
        for c in _all_cities(config_dir):
            for kind in ("lau", "fua"):  # every kind, so --write never drops other tables
                cs = ts.build_city(conn, c.id, kind, sel, history_cfg.year_range())
                if cs is not None:
                    built[(c.id, kind)] = cs
    shown = {k: v for k, v in built.items() if k[0] in wanted and k[1] in kinds}
    all_flags = {k: ts.city_flags(v, cfg) for k, v in built.items()}
    shown_flags = [f for k, fl in all_flags.items() if k in shown for f in fl]
    for cs in shown.values():
        for note in cs.notes:
            typer.echo(f"note: {note}")
    typer.echo(_presets_line(sel.presets))
    block_args = (
        {k: v.points for k, v in shown.items()},
        shown_flags,
        {k: v.provenance for k, v in shown.items()},
    )
    typer.echo(ts.render_block(*block_args))
    try:
        if write:
            ts.write_report(
                report,
                ts.render_block(
                    {k: v.points for k, v in built.items()},
                    [f for fl in all_flags.values() for f in fl],
                    {k: v.provenance for k, v in built.items()},
                ),
            )
        if check:
            problems = False
            ts.check_markers(report)
            for cid in sorted(wanted):
                for kind in history_cfg.required(cid):
                    if boundary not in (None, kind):
                        continue
                    if (cid, kind) not in built:
                        problems = True
                        typer.echo(
                            f"no history runs for {cid}/{kind} of the current config "
                            f"{sel.short_sha}: cannot check it",
                            err=True,
                        )
                        continue
                    for year in built[(cid, kind)].missing_years:
                        problems = True
                        typer.echo(
                            f"missing history year {cid}/{kind}/{year} (config/history.yaml "
                            f"years {history_cfg.years}): rerun `run --years`",
                            err=True,
                        )
            for key in ts.missing_explanations(report, shown_flags):
                problems = True
                typer.echo(f"missing explanation: ### {key}", err=True)
            sets = {k: v.set_md5 for k, v in shown.items()}
            stale = ts.unexplained_sets(report, sets)
            for line in stale:
                typer.echo(f"explanations out of date: {line}", err=True)
            if stale:
                problems = True
                typer.echo(
                    "after re-checking the explanations, set: "
                    + ts.explained_against_marker({k: v.set_md5 for k, v in built.items()}),
                    err=True,
                )
            for key in ts.stale_explanations(report, shown_flags, set(shown)):
                typer.echo(f"warning: ### {key} matches no flag", err=True)
            if problems:
                raise typer.Exit(1)
    except (OSError, ValueError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e


@auth_app.command("check")
def auth_check(data: Path = DATA_OPT) -> None:
    """Log in with VELOMETER_OSM_USER/PASSWORD and store the cookie; prints only ok or the error."""
    from velometer.sources.geofabrik_auth import AuthError, load_or_login, new_auth_client

    try:
        with new_auth_client() as c:
            cookie = load_or_login(data, client=c, force=True)
    except (AuthError, httpx.HTTPError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"ok: cookie valid until {cookie.expires:%Y-%m-%d %H:%M} UTC")


@report_app.command("csv")
def report_csv(
    city: str | None = typer.Option(None, "--city", help="City id; default all cities."),
    out: Path | None = typer.Option(None, "--out", help="Write here instead of stdout."),  # noqa: B008
    db: Path = DB_OPT,
    config_dir: Path = CONFIG_OPT,
) -> None:
    """One CSV row per city, boundary kind and year or `current`, with ODbL attribution."""
    from datetime import UTC, datetime

    from velometer.reconcile import short_commit
    from velometer.report.csvexport import to_csv
    from velometer.report.data import ReportData, open_readonly
    from velometer.run import git_commit

    try:
        conn = open_readonly(db)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    try:
        data = ReportData(conn, config_dir)
        if city is not None and city not in {c.id for c in data.cities()}:
            typer.echo(f"error: unknown city {city!r}", err=True)
            raise typer.Exit(1)
        text = to_csv(
            data.csv_rows(city),
            short_commit(git_commit()),
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    except sqlite3.Error as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    finally:
        conn.close()
    if out is None:
        typer.echo(text, nl=False)
    else:
        out.write_text(text)


@report_app.command("charts")
def report_charts(
    out: Path = typer.Option(Path("docs/review"), "--out", help="Directory for the PNGs."),  # noqa: B008
    db: Path = DB_OPT,
    config_dir: Path = CONFIG_OPT,
) -> None:
    """Write m4_headline.png, m4_tiers.png and m4_rankings.png (plus .vl.json specs)."""
    from velometer.report.charts import write_pngs
    from velometer.report.data import ReportData, open_readonly

    try:
        conn = open_readonly(db)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    try:
        paths = write_pngs(ReportData(conn, config_dir), out)
    except sqlite3.Error as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    finally:
        conn.close()
    for p in paths:
        typer.echo(str(p))
