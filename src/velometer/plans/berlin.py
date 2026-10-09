"""Berlin plan-network datasets from the city's WFS (`velometer plans fetch berlin`, M8 §4.2).

Each layer in `config/plans/sources.yaml` is fetched with WFS 2.0.0 GetFeature as GeoJSON in the
served EPSG (25833), sorted on the layer's stable id and paged with `count`/`startIndex` until
the server's `numberMatched` is reached (or, without one, a page comes back short), and written
to `<out_dir>/<layer>.geojson`; `retrieved.json` records each layer's URL, the licence and the
retrieval time. Raw files live under `data/` and are never committed.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from velometer.config import ConfigError
from velometer.sources.download import user_agent

TIMEOUT_S = 120.0
MAX_PAGES = 1000  # Berlin's largest layer is 3 pages; a server that pages forever is refused
NETWORK_LAYER = "radverkehrsnetz"  # the layer `plans overlay` matches sides against

Fetch = Callable[[str, dict[str, str]], bytes]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WfsLayer(_Strict):
    url: str
    type_name: str
    record: str  # the dataset's metadata record
    sort_by: str  # a property unique per feature, so pages neither overlap nor skip


class PlanSourcesConfig(_Strict):
    """One city's plan-network datasets."""

    licence: str
    licence_url: str
    srs: str
    page_size: int = Field(gt=0)
    layers: dict[str, WfsLayer]


@dataclass(frozen=True)
class FetchResult:
    paths: dict[str, Path]  # layer name -> GeoJSON file
    retrieved_at: str  # ISO 8601 UTC, `Z`


def load_plan_sources(path: Path, city: str) -> PlanSourcesConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"{path}: {e}") from e
    if not isinstance(raw, dict) or city not in raw:
        raise ConfigError(f"{path}: no plan sources for city {city!r}")
    try:
        return PlanSourcesConfig.model_validate(raw[city])
    except ValidationError as e:
        raise ConfigError(f"{path}: {e}") from e


def _http_get(url: str, params: dict[str, str]) -> bytes:
    r = httpx.get(
        url,
        params=params,
        timeout=TIMEOUT_S,
        follow_redirects=True,
        headers={"User-Agent": user_agent()},
    )
    r.raise_for_status()
    return r.content


def _fetch_layer(layer: WfsLayer, cfg: PlanSourcesConfig, fetch: Fetch) -> dict:
    """All features of one layer, one FeatureCollection; ValueError if the server's
    `numberMatched` disagrees with the features received, a feature lacks the `sort_by`
    property, an id appears twice (within a page or across pages), or the layer has not ended
    after `MAX_PAGES` pages."""
    features: list = []
    seen: set = set()
    matched = None
    for _ in range(MAX_PAGES):
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer.type_name,
            "outputFormat": "application/json",
            "srsName": cfg.srs,
            "sortBy": layer.sort_by,
            "count": str(cfg.page_size),
            "startIndex": str(len(features)),
        }
        page = json.loads(fetch(layer.url, params))
        if page.get("type") != "FeatureCollection":
            raise ValueError(f"{layer.url}: not a GeoJSON FeatureCollection")
        if isinstance(page.get("numberMatched"), int):
            matched = page["numberMatched"]
        got = page.get("features") or []
        ids = []
        for f in got:
            props = f.get("properties") or {}
            if props.get(layer.sort_by) is None:
                raise ValueError(
                    f"{layer.url}: a feature at startIndex {len(features)} has no "
                    f"{layer.sort_by!r} property (the layer's sort_by, which must be unique)"
                )
            ids.append(props[layer.sort_by])
        if len(set(ids)) < len(ids):
            dup = next(i for i in ids if ids.count(i) > 1)
            raise ValueError(
                f"{layer.url}: the page at startIndex {len(features)} has "
                f"{layer.sort_by} {dup!r} more than once"
            )
        if seen.intersection(ids):
            of = f", server numberMatched {matched}" if matched is not None else ""
            raise ValueError(
                f"{layer.url}: the page at startIndex {len(features)} repeated features already "
                f"received ({len(features)} received{of})"
            )
        seen.update(ids)
        features += got
        # a server may cap `count` below page_size, so a short page ends the layer only when
        # there is no numberMatched to page towards
        if not got or (
            len(features) >= matched if matched is not None else len(got) < cfg.page_size
        ):
            break
    else:
        raise ValueError(f"{layer.url}: no end of the layer after {MAX_PAGES} pages")
    if matched is not None and matched != len(features):
        raise ValueError(
            f"{layer.url}: received {len(features)} features, server numberMatched {matched}"
        )
    return {"type": "FeatureCollection", "features": features}


def fetch_layers(cfg: PlanSourcesConfig, out_dir: Path, fetch: Fetch = _http_get) -> FetchResult:
    """Fetch every layer, then write the GeoJSON files and `retrieved.json` (nothing is written
    unless every layer arrived whole)."""
    retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    docs = {name: _fetch_layer(layer, cfg, fetch) for name, layer in cfg.layers.items()}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, doc in docs.items():
        paths[name] = out_dir / f"{name}.geojson"
        paths[name].write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    meta = {
        "retrieved_at": retrieved_at,
        "licence": cfg.licence,
        "licence_url": cfg.licence_url,
        "srs": cfg.srs,
        "layers": {
            name: {
                "url": layer.url,
                "type_name": layer.type_name,
                "record": layer.record,
                "features": len(docs[name]["features"]),
            }
            for name, layer in cfg.layers.items()
        },
    }
    (out_dir / "retrieved.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return FetchResult(paths, retrieved_at)
