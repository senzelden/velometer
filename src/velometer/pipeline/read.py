"""Read OSM ways (with node locations) from .osm / .osm.pbf via pyosmium."""

from pathlib import Path

import osmium

from velometer.pipeline.types import ReadResult, WayRecord


def read_ways(path: Path) -> ReadResult:
    """Return highway ways with lon/lat coords. Ways with <2 resolvable nodes go to `skipped`."""
    ways: list[WayRecord] = []
    skipped: list[int] = []
    fp = osmium.FileProcessor(str(path)).with_locations()
    for obj in fp:
        if not obj.is_way() or "highway" not in obj.tags:
            continue
        coords = tuple((n.location.lon, n.location.lat) for n in obj.nodes if n.location.valid())
        if len(coords) < 2:
            skipped.append(obj.id)
            continue
        ways.append(WayRecord(id=obj.id, tags={t.k: t.v for t in obj.tags}, coords=coords))
    return ReadResult(ways=ways, skipped=skipped)
