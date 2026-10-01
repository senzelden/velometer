"""velometer command-line interface."""

from enum import StrEnum
from pathlib import Path

import typer

from velometer.config import ConfigError, default_config_dir, load_cities
from velometer.db import SchemaError, create_schema, open_db, upsert_cities


class PlainOneway(StrEnum):
    traffic_side = "traffic_side"
    both_sides = "both_sides"


app = typer.Typer(no_args_is_help=True, help="Protected cycling infrastructure from OSM.")


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


@app.command()
def classify(
    file: Path = typer.Option(..., exists=True, dir_okay=False, help=".osm or .osm.pbf"),  # noqa: B008
    epsg: int = typer.Option(..., help="Projected CRS for lengths (city EPSG)."),
    classifier: str = typer.Option("v1", help="Classifier version (config/classifier/<v>.yaml)."),
    config_dir: Path = typer.Option(default_config_dir(), help="Config directory."),  # noqa: B008
    plain_cycleway_on_oneway: PlainOneway | None = typer.Option(  # noqa: B008
        None,
        help="Override the classifier parameter: plain cycleway=* on a oneway road counts on "
        "the traffic side only, or on both sides.",
    ),
) -> None:
    """Classify one OSM file and print tier lengths, road lengths and preset metrics."""
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
        typer.echo(f"config error: {e}", err=True)
        raise typer.Exit(1) from e
    if plain_cycleway_on_oneway is not None:
        cfg = cfg.with_parameters(plain_cycleway_on_oneway=plain_cycleway_on_oneway.value)
    read = read_ways(file)
    result = measure(read.ways, cfg, epsg)
    params = " ".join(f"{k}={v}" for k, v in cfg.parameters.model_dump().items())
    typer.echo(f"classifier {cfg.version} ({params})")
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
