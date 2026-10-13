"""External comparison figures: curated CSV, ECF QECIO v2.10 summary, BikeNetKit (Zenodo)."""

import csv
import re
import sqlite3
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import pyogrio
import shapely

from velometer import i18n
from velometer.config import CityConfig, ConfigError, load_cities
from velometer.db import replace_external_figures
from velometer.models import ExternalFigure
from velometer.pipeline.geometry import Projector, length_km
from velometer.sources.download import fetch, md5_of

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
# the parts of the notes the QECIO and BikeNetKit loaders store (English, in the database);
# `note_de` builds a German page's note from the same catalogue parts
NUTS3_NOT_CITY = i18n.t("en", "figure.note.nuts3_not_city")
QECIO_HALVES = i18n.t("en", "figure.note.qecio_halves")
BIKENETKIT_NOTE = i18n.t("en", "figure.note.bikenetkit")
_QECIO_NOTE = re.compile(
    r"(?P<nuts>NUTS3 \S+ \([^()]*\)); "
    + re.escape(QECIO_HALVES)
    + r"(?P<rest>(?:; .*?)??)(?P<not_city>; "
    + re.escape(NUTS3_NOT_CITY)
    + r")?; "
    + re.escape(i18n.t("en", "figure.note.file_md5", md5=""))
    + r"(?P<md5>[0-9a-f]{32})"
)


def note_de(note: str, cities: list[CityConfig]) -> str | None:
    """The German of a note `qecio_figures` or `bikenetkit_figures` stored, built from the same
    parts (a city's `nuts3_note` from its `nuts3_note_de`); None for any other note, or for a
    caveat that is no city's `nuts3_note`."""
    if note == BIKENETKIT_NOTE:
        return i18n.t("de", "figure.note.bikenetkit")
    m = _QECIO_NOTE.fullmatch(note)
    if m is None:
        return None
    parts = [m["nuts"], i18n.t("de", "figure.note.qecio_halves")]
    if caveat := m["rest"].removeprefix("; "):
        german = next((c.nuts3_note_de for c in cities if c.nuts3_note == caveat), None)
        if german is None:
            return None
        parts.append(german)
    if m["not_city"]:
        parts.append(i18n.t("de", "figure.note.nuts3_not_city"))
    parts.append(i18n.t("de", "figure.note.file_md5", md5=m["md5"]))
    return "; ".join(parts)


def retrieved_at(path: Path) -> date:
    """UTC date a downloaded file was last written (its retrieval date)."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).date()


def load_figures_csv(path: Path) -> list[ExternalFigure]:
    """The curated rows. Each must cite an http(s) source_url; `row <n>` in an error is the
    row's line in the file (the header is line 1)."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for n, r in enumerate(rows, start=2):
        r.pop("note_de", None)  # the German note is display text (report.data.figure_notes_de)
        url = r["source_url"] = (r.get("source_url") or "").strip()  # stored as validated
        if not url:
            raise ConfigError(f"row {n}: source_url is required")
        if not url.lower().startswith(("http://", "https://")):
            raise ConfigError(f"row {n}: source_url must be http(s)")
    return [
        ExternalFigure.model_validate({**r, "reference_date": r["reference_date"] or None})
        for r in rows
    ]


def qecio_figures(csv_path: Path, cities: list[CityConfig]) -> list[ExternalFigure]:
    """QECIO rows of every city with a nuts3_code; each code must select exactly one row."""
    by_nuts = {c.nuts3_code: c for c in cities if c.nuts3_code}
    out = []
    got = retrieved_at(csv_path)
    digest = md5_of(csv_path)
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["NUTS_ID"] in by_nuts]
    matched = Counter(r["NUTS_ID"] for r in rows)
    bad = {code: matched[code] for code in by_nuts if matched[code] != 1}
    if bad:
        detail = ", ".join(f"{code} ({by_nuts[code].id}) matched {n}" for code, n in bad.items())
        raise ValueError(f"{csv_path.name}: each nuts3_code must match one row: {detail}")
    for row in rows:
        city = by_nuts[row["NUTS_ID"]]
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
                    retrieved_at=got,
                    note="; ".join(
                        p
                        for p in (
                            f"NUTS3 {row['NUTS_ID']} ({row['City']})",
                            QECIO_HALVES,
                            city.nuts3_note,
                            NUTS3_NOT_CITY if city.nuts3_is_city is False else None,
                            f"file md5 {digest}",
                        )
                        if p
                    ),
                )
            )
    return out


def bikenetkit_figures(zip_dir: Path, cities: list[CityConfig]) -> list[ExternalFigure]:
    out = []
    got = retrieved_at(zip_dir / "bike_networks.zip")
    with zipfile.ZipFile(zip_dir / "bike_networks.zip") as z:
        for city in cities:
            cid = city.bikenetkit_id
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
                    retrieved_at=got,
                    note=BIKENETKIT_NOTE,
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
    refresh_qecio: bool = False,
) -> dict[str, int]:
    """Replace each source's rows; return rows per source. Curated CSV sources always load."""
    cities = load_cities(config_dir / "cities.yaml")
    curated = load_figures_csv(figures_csv or config_dir / "external" / "figures.csv")
    counts: dict[str, int] = dict(Counter(f.source for f in curated))
    for source in counts:
        replace_external_figures(conn, source, [f for f in curated if f.source == source])
    if qecio:
        dst = data_dir / "external" / "qecio" / QECIO_LOCAL_NAME
        if refresh_qecio:
            dst.unlink(missing_ok=True)
        fetch(QECIO_URL, dst)
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
