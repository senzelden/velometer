"""velometer command-line interface."""

from enum import StrEnum
from pathlib import Path

import typer

from velometer.config import CityConfig, ConfigError, default_config_dir, load_cities
from velometer.db import SchemaError, create_schema, open_db, upsert_cities


class PlainOneway(StrEnum):
    traffic_side = "traffic_side"
    both_sides = "both_sides"


app = typer.Typer(no_args_is_help=True, help="Protected cycling infrastructure from OSM.")
boundaries_app = typer.Typer(no_args_is_help=True, help="City boundaries.")
osm_app = typer.Typer(no_args_is_help=True, help="OSM region extracts.")
app.add_typer(boundaries_app, name="boundaries")
external_app = typer.Typer(no_args_is_help=True, help="External comparison figures.")
app.add_typer(osm_app, name="osm")
app.add_typer(external_app, name="external")

DB_OPT = typer.Option(Path("velometer.sqlite"), "--db", help="SQLite database path.")
DATA_OPT = typer.Option(Path("data"), "--data", help="Data directory.")
CONFIG_OPT = typer.Option(default_config_dir(), "--config-dir", help="Config directory.")


@app.callback()
def main() -> None:
    """velometer: reproducible OSM cycling-infrastructure measurement."""


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
    try:
        with open_db(db) as conn:
            create_schema(conn)
            n = upsert_cities(conn, cities)
    except SchemaError as e:
        typer.echo(f"database error: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"{db}: schema ready, {n} cities loaded")


def _params_line(cfg) -> str:
    params = " ".join(f"{k}={v}" for k, v in cfg.parameters.model_dump().items())
    return f"classifier {cfg.version} ({params})"


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
    with open_db(db) as conn:
        create_schema(conn)
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
        if outcomes[0].status == "failed":
            raise typer.Exit(1)
        return
    if file is None or epsg is None:
        typer.echo("error: give --file with --epsg, or --city", err=True)
        raise typer.Exit(2)
    _classify_file(file, epsg, classifier, config_dir, plain_cycleway_on_oneway)


def _classify_file(
    file: Path, epsg: int, classifier: str, config_dir: Path, plain: PlainOneway | None
) -> None:
    from velometer.config import load_classifier, load_presets
    from velometer.pipeline.geometry import require_projected
    from velometer.pipeline.measure import compute_metrics, measure
    from velometer.pipeline.read import read_ways

    try:
        require_projected(epsg)
    except ValueError as e:
        typer.echo(f"error: --epsg {epsg}: {e}", err=True)
        raise typer.Exit(1) from e
    try:
        cfg = load_classifier(config_dir / "classifier" / f"{classifier}.yaml")
        presets = load_presets(config_dir / "presets.yaml", cfg)
    except ConfigError as e:
        raise _config_error(e) from e
    if plain is not None:
        cfg = cfg.with_parameters(plain_cycleway_on_oneway=plain.value)
    read = read_ways(file)
    result = measure(read.ways, cfg, epsg)
    typer.echo(_params_line(cfg))
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
    for m in compute_metrics(result, presets):
        value = "n/a" if m.value is None else f"{m.value:.1f}"
        typer.echo(f"{m.preset:<20} {value:>7} {m.numerator_km:>9.3f} {m.denominator_km:>8.3f}")
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


@app.command()
def run(
    cities: str = typer.Option("all", help="'all' or comma-separated city ids."),
    boundary: str = typer.Option("lau", help="Boundary kind."),
    force: bool = typer.Option(False, "--force", help="Re-run even if a done run exists."),
    classifier: str = typer.Option("v1", help="Classifier version."),
    config_dir: Path = CONFIG_OPT,
    db: Path = DB_OPT,
    data: Path = DATA_OPT,
    plain_cycleway_on_oneway: PlainOneway | None = typer.Option(  # noqa: B008
        None,
        help="Override the classifier parameter: plain cycleway=* on a oneway road counts on "
        "the traffic side only, or on both sides.",
    ),
) -> None:
    """Run cities end to end (region, boundary, clip, classify, persist); done runs are skipped."""
    wanted = None if cities == "all" else [c.strip() for c in cities.split(",") if c.strip()]
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
    with open_db(db) as conn:
        create_schema(conn)
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
    config_dir: Path = CONFIG_OPT,
    db: Path = DB_OPT,
    data: Path = DATA_OPT,
) -> None:
    """Load curated, QECIO and BikeNetKit figures into external_figures."""
    from velometer.sources import external
    from velometer.sources.download import DownloadError

    cities = _all_cities(config_dir)
    try:
        with open_db(db) as conn:
            create_schema(conn)
            upsert_cities(conn, cities)
            counts = external.load_all(
                conn, data, config_dir, qecio=qecio, bikenetkit=bikenetkit, figures_csv=figures
            )
    except (DownloadError, SchemaError, ValueError, KeyError, OSError) as e:
        typer.echo(f"external load failed: {type(e).__name__}: {e}", err=True)
        raise typer.Exit(1) from e
    for source, n in counts.items():
        typer.echo(f"{source} {n} rows")


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


@app.command()
def results(
    boundary: str = typer.Option("lau", help="Boundary kind."),
    db: Path = DB_OPT,
) -> None:
    """One row per city: the latest done run's headline metrics and per-side tier km."""
    from velometer.db import fetch_cities, fetch_run_results, latest_done_run

    def fmt(v: float | None) -> str:
        return "n/a" if v is None else f"{v:.1f}"

    rows = []
    with open_db(db) as conn:
        create_schema(conn)
        for c in fetch_cities(conn):
            run_id = latest_done_run(conn, c.id, boundary)
            if run_id is None:
                continue
            r = fetch_run_results(conn, run_id)
            m = {x.preset: x for x in r.metrics}
            tier_km = dict.fromkeys("ABCDE", 0.0)
            for t in r.tier_lengths:
                if t.length_basis == "per_side" and t.tier in tier_km:
                    tier_km[t.tier] += t.length_km
            main = next(
                (x.length_km for x in r.road_lengths if x.road_class == "main_excl_motorway"),
                None,
            )
            head, ecf, clean = (
                m.get(p) for p in ("ours_headline", "ecf_qecio", "clean_cities_2025")
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
    if not rows:
        typer.echo(f"no done runs for boundary {boundary!r}")
        return
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(RESULT_COLUMNS)]
    typer.echo("  ".join(h.ljust(w) for h, w in zip(RESULT_COLUMNS, widths, strict=True)).rstrip())
    for r in rows:
        typer.echo("  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)).rstrip())
