"""External comparison figures: curated CSV, ECF QECIO v2.10 summary, BikeNetKit (Zenodo)."""

import csv
import sqlite3
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

import pyogrio
import shapely

from velometer.config import CityConfig, load_cities
from velometer.db import replace_external_figures
from velometer.models import ExternalFigure
from velometer.pipeline.geometry import Projector, length_km
from velometer.sources.download import fetch

QECIO_URL = "https://european-cyclists-federation.github.io/Download/Summary/Summary-all.csv"
# The CSV has no published md5, so the local name carries the version (fetch trusts existing files).
QECIO_LOCAL_NAME = "Summary-all-v2.10.csv"
QECIO_COLUMNS = {  # metric_name -> Summary-all.csv column (v2.10)
    "main_roads_km": "overview-main-road-network",
    "cycle_tracks_km": "overview-cycle_tracks-km",
    "cycle_lanes_km": "overview-cycle_lanes-km",
    "shared_pedestrians_km": "overview-shared_pedestrians-km",
    "total_cycle_infra_km": "overview-total-cycle-infrastructure",
}
ZENODO = "https://zenodo.org/api/records/22271229/files/{name}/content"
BIKENETKIT_FILES = {
    "bike_networks.zip": "ffccda3c4fa40953a31d4cb8d88930d5",
    "boundaries.zip": "655c204a16f17b644e6a22d40cf1f68a",
}
BIKENETKIT_IDS = {
    "berlin": "berlin_de",
    "paris": "paris_fr",
    "vienna": "vienna_at",
    "copenhagen": "copenhagen_dk",
    "wroclaw": "wroclaw_pl",
}
RETRIEVED = date(2026, 10, 1)


def load_figures_csv(path: Path) -> list[ExternalFigure]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [
        ExternalFigure.model_validate({**r, "reference_date": r["reference_date"] or None})
        for r in rows
    ]


def qecio_figures(csv_path: Path, cities: list[CityConfig]) -> list[ExternalFigure]:
    by_nuts = {c.nuts3_code: c for c in cities if c.nuts3_code}
    out = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            city = by_nuts.get(row["NUTS_ID"])
            if city is None:
                continue
            ref = date.fromisoformat(row["Date"].strip()[:10])
            for metric, col in QECIO_COLUMNS.items():
                out.append(
                    ExternalFigure(
                        city_id=city.id,
                        source="qecio_v2_10",
                        metric_name=metric,
                        value=float(row[col]),
                        unit="km",
                        reference_date=ref,
                        network_scope=f"nuts3_{row['NUTS_ID']}",
                        length_basis="unknown",
                        source_url=QECIO_URL,
                        retrieved_at=RETRIEVED,
                        note=f"NUTS3 {row['NUTS_ID']} ({row['City']}); QECIO halves "
                        "unidirectional infrastructure",
                    )
                )
    return out


def bikenetkit_figures(zip_dir: Path, cities: list[CityConfig]) -> list[ExternalFigure]:
    out = []
    with zipfile.ZipFile(zip_dir / "bike_networks.zip") as z:
        for city in cities:
            cid = BIKENETKIT_IDS.get(city.id)
            if cid is None:
                continue
            target = zip_dir / "bikenetkit" / f"{cid}.gpkg"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(f"bike_networks/{cid}.gpkg"))
            meta, _, geoms, _ = pyogrio.raw.read(str(target), layer="edges")
            if not str(meta["crs"]).upper().endswith("EPSG:4326"):
                raise ValueError(f"{target.name}: expected EPSG:4326, got {meta['crs']}")
            proj = Projector(city.epsg)
            total = 0.0
            for wkb in geoms:
                g = shapely.from_wkb(wkb)
                for part in getattr(g, "geoms", [g]):
                    total += length_km(proj.line(tuple(part.coords)))
            out.append(
                ExternalFigure(
                    city_id=city.id,
                    source="bikenetkit_v1",
                    metric_name="bike_network_km",
                    value=total,
                    unit="km",
                    reference_date=None,
                    network_scope="bikenetkit_bike_network",
                    length_basis="unknown",
                    source_url="https://doi.org/10.5281/zenodo.22271229",
                    retrieved_at=RETRIEVED,
                    note="OSM/Nominatim city boundary; includes cycleway, designated paths, "
                    "living streets, cycle streets and side tracks (no lanes); undirected "
                    "edges counted once; snapshot 'summer 2026' (unverified)",
                )
            )
    return out


def load_all(
    conn: sqlite3.Connection,
    data_dir: Path,
    config_dir: Path,
    *,
    qecio: bool,
    bikenetkit: bool,
    figures_csv: Path | None = None,
) -> dict[str, int]:
    """Replace each source's rows; return rows per source. Curated CSV sources always load."""
    cities = load_cities(config_dir / "cities.yaml")
    curated = load_figures_csv(figures_csv or config_dir / "external" / "figures.csv")
    counts: dict[str, int] = dict(Counter(f.source for f in curated))
    for source in counts:
        replace_external_figures(conn, source, [f for f in curated if f.source == source])
    if qecio:
        dst = fetch(QECIO_URL, data_dir / "external" / "qecio" / QECIO_LOCAL_NAME)
        figs = qecio_figures(dst, cities)
        replace_external_figures(conn, "qecio_v2_10", figs)
        counts["qecio_v2_10"] = len(figs)
    if bikenetkit:
        zip_dir = data_dir / "external" / "bikenetkit"
        for name, md5 in BIKENETKIT_FILES.items():
            fetch(ZENODO.format(name=name), zip_dir / name, md5=md5)
        figs = bikenetkit_figures(zip_dir, cities)
        replace_external_figures(conn, "bikenetkit_v1", figs)
        counts["bikenetkit_v1"] = len(figs)
    return counts
