"""velometer command-line interface."""

from pathlib import Path

import typer

from velometer.config import ConfigError, default_config_dir, load_cities
from velometer.db import connect, create_schema, upsert_cities

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
    conn = connect(db)
    create_schema(conn)
    n = upsert_cities(conn, cities)
    typer.echo(f"{db}: schema ready, {n} cities loaded")
