"""Per-country tagging diagnostics: the evidence for signing a country off in config/trust.yaml.

Computed from each city's current LAU run snapshot, classified with the report classifier, for
any country (pending ones too). Shares are over `cycling_km`: the per_side km of every classified
side, of any kind, whose way carries cycling tags (`pipeline.activity.cycling_tags`). A country
with no cycling km has shares of 0.0. Areas in km² are measured in the city's EPSG.

A library module (no CLI imports); `write_country` writes `<cc>.json` (machine) and the
generated block of `<cc>.md` (between `TRUST_BEGIN` and `TRUST_END`; hand-written notes outside
the block are kept).
"""

import re
import tempfile
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from velometer.config import (
    ActivityConfig,
    CityConfig,
    TrustThresholds,
    default_config_dir,
    load_classifier,
)
from velometer.db import fetch_boundary, fetch_run
from velometer.osmium import relation_polygon
from velometer.pipeline.activity import cycling_tags
from velometer.pipeline.drift import is_unmatched_road_side
from velometer.pipeline.measure import measure
from velometer.pipeline.read import read_ways
from velometer.report.maps import snapshot_path
from velometer.selection import Selector
from velometer.sources.boundaries import load_boundary_polygon

TIERS = "ABCDE"
TOP_UNMATCHED = 20
VALUE_MAX = 40  # characters of a tag value kept in a signature
TRUST_BEGIN = "<!-- trust:begin -->"
TRUST_END = "<!-- trust:end -->"
NOTES_HEADER = (
    "# Trust review: {cc}\n\n"
    "Hand-written notes go here. Only the generated block below is replaced when "
    "`velometer trust diagnose` runs again; everything outside it is kept.\n\n"
)
ODBL = "Map data © OpenStreetMap contributors, ODbL 1.0"


class NoCurrentRun(LookupError):
    """The city has no current LAU run of the report config."""


class CityDiagnostics(BaseModel):
    city_id: str
    run_id: int  # the current LAU run diagnosed
    osm_timestamp: str
    cycling_km: float  # per-side km of sides whose way carries cycling tags
    unrecognised_share: float  # (no tier or unknown_value) & cycling tags, over cycling_km
    excluded_share: float  # tier "excluded" over cycling_km
    excluded_by_rule: dict[str, float]  # rule_id -> share of cycling_km
    tier_mix: dict[str, float]  # A..E -> share of A-E per_side km
    b_share_of_ab: float | None  # None when A+B = 0
    completeness: dict[str, dict[str, float]]  # tier -> {width, surface, segregated}
    top_unmatched: list[tuple[str, float]]  # (tag signature, km), 20 largest
    boundary_lau_km2: float
    boundary_osm_km2: float | None  # None when no region file is cached
    boundary_diff_pct: float | None


class CountryDiagnostics(BaseModel):
    country: str
    classifier_version: str
    config_sha256: str
    cities: list[CityDiagnostics]


def tag_signature(tags, cfg: ActivityConfig) -> str:
    """`highway=<v>` plus every tag `cycling_tags` counts: keys sorted, joined with `;`, values
    cut to VALUE_MAX characters."""
    keep = dict(cycling_tags(tags, cfg))
    if "highway" in tags:
        keep["highway"] = tags["highway"]
    return ";".join(f"{k}={keep[k][:VALUE_MAX]}" for k in sorted(keep))


def _ratio(num: float, den: float) -> float:
    return num / den if den else 0.0


def region_file(region: str, data_dir: Path) -> Path | None:
    """The newest cached Geofabrik extract of `region` (`<data>/raw/<name>-YYMMDD.osm.pbf`)."""
    name = region.rsplit("/", 1)[-1]
    pattern = re.compile(rf"{re.escape(name)}-\d{{6}}\.osm\.pbf")
    found = sorted(
        p for p in (Path(data_dir) / "raw").glob(f"{name}-*") if pattern.fullmatch(p.name)
    )
    return found[-1] if found else None


def _osm_area_km2(city: CityConfig, data_dir: Path) -> float | None:
    region = region_file(city.geofabrik_region, data_dir)
    if region is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        gj = relation_polygon(region, city.osm_relation_id, Path(tmp) / "relation.geojson")
        return load_boundary_polygon(gj, city.epsg).area / 1e6


def diagnose_city(
    conn,
    city: CityConfig,
    selector: Selector,
    data_dir: Path,
    activity_cfg: ActivityConfig,
    *,
    config_dir: Path | None = None,
) -> CityDiagnostics:
    """The city's current LAU run of `selector`, re-classified from its snapshot.

    `config_dir` (default: the repo config) holds the classifier named by `selector.version`.
    Raises NoCurrentRun, or FileNotFoundError naming a missing snapshot or boundary file.
    """
    run_id = selector.latest(conn, city.id, "lau")
    if run_id is None:
        raise NoCurrentRun(f"{city.id}: no current LAU run")
    row = fetch_run(conn, run_id)
    snap = snapshot_path(row, data_dir)
    if not snap.is_file():
        raise FileNotFoundError(f"{city.id}: snapshot not found: {snap}")
    boundary = fetch_boundary(conn, city.id, "lau")
    if boundary is None or not Path(boundary.path).is_file():
        raise FileNotFoundError(f"{city.id}: boundary file not found for run {run_id}")
    polygon = load_boundary_polygon(Path(boundary.path), city.epsg)

    classifier = (config_dir or default_config_dir()) / "classifier" / f"{selector.version}.yaml"
    ways = read_ways(snap).ways
    result = measure(ways, load_classifier(classifier), city.epsg, boundary=polygon)
    tags_by_way = {w.id: w.tags for w in ways}

    cycling = excluded = unrecognised = 0.0
    by_rule: dict[str, float] = defaultdict(float)
    unmatched: dict[str, float] = defaultdict(float)
    tier_km: dict[str, float] = dict.fromkeys(TIERS, 0.0)
    for c in result.classified:
        length = result.way_lengths[c.side.way_id]
        tags = tags_by_way[c.side.way_id]
        if c.tier in tier_km:
            tier_km[c.tier] += length
        if not cycling_tags(tags, activity_cfg):
            continue
        cycling += length
        if c.tier == "excluded":
            excluded += length
            by_rule[str(c.rule_id)] += length
        if is_unmatched_road_side(c):  # the same definition as pipeline.drift
            unrecognised += length
            unmatched[tag_signature(tags, activity_cfg)] += length

    ab = tier_km["A"] + tier_km["B"]
    osm_km2 = _osm_area_km2(city, Path(data_dir))
    lau_km2 = polygon.area / 1e6
    return CityDiagnostics(
        city_id=city.id,
        run_id=run_id,
        osm_timestamp=row["osm_timestamp"],
        cycling_km=cycling,
        unrecognised_share=_ratio(unrecognised, cycling),
        excluded_share=_ratio(excluded, cycling),
        excluded_by_rule={r: _ratio(km, cycling) for r, km in sorted(by_rule.items())},
        tier_mix={t: _ratio(km, sum(tier_km.values())) for t, km in tier_km.items()},
        b_share_of_ab=_ratio(tier_km["B"], ab) if ab else None,
        completeness={
            m.tier: {
                "width": m.share_with_width,
                "surface": m.share_with_surface,
                "segregated": m.share_with_segregated,
            }
            for m in result.completeness
        },
        top_unmatched=sorted(unmatched.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_UNMATCHED],
        boundary_lau_km2=lau_km2,
        boundary_osm_km2=osm_km2,
        boundary_diff_pct=None if not osm_km2 else abs(lau_km2 - osm_km2) / osm_km2 * 100,
    )


def breaches(d: CityDiagnostics, t: TrustThresholds) -> list[str]:
    """Names of the metrics over their limit (strictly); a metric that is None is not checked."""
    checks = [
        ("unrecognised_share", d.unrecognised_share, t.unrecognised_share_max),
        ("excluded_share", d.excluded_share, t.excluded_share_max),
        ("b_share_of_ab", d.b_share_of_ab, t.b_share_of_ab_max),
        ("boundary_diff_pct", d.boundary_diff_pct, t.boundary_diff_pct_max),
    ]
    return [name for name, value, limit in checks if value is not None and value > limit]


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _row(d: CityDiagnostics, t: TrustThresholds) -> str:
    diff = "n/a" if d.boundary_diff_pct is None else f"{d.boundary_diff_pct:.1f}%"
    over = ", ".join(breaches(d, t)) or "none"
    return (
        f"| {d.city_id} | {d.run_id} | {d.cycling_km:.1f} | {_pct(d.unrecognised_share)} "
        f"| {_pct(d.excluded_share)} | {_pct(d.b_share_of_ab)} | {diff} | {over} |"
    )


TABLE_HEAD = (
    "| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff "
    "| over limit |\n"
    "|---|---|---|---|---|---|---|---|"
)


def _block(cd: CountryDiagnostics, t: TrustThresholds, pilots: list[CityDiagnostics]) -> str:
    out = [
        TRUST_BEGIN,
        f"## Diagnostics {cd.country} (generated)",
        "",
        f"Classifier {cd.classifier_version}, config {cd.config_sha256[:12]}. "
        "Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides "
        "whose way carries cycling tags.",
        "",
        f"Limits: unrecognised {_pct(t.unrecognised_share_max)}, "
        f"excluded {_pct(t.excluded_share_max)}, B of A+B {_pct(t.b_share_of_ab_max)}, "
        f"boundary diff {t.boundary_diff_pct_max:g}%.",
        "",
        TABLE_HEAD,
        *(_row(d, t) for d in cd.cities),
    ]
    if pilots:
        out += ["", "### Pilot comparison", "", TABLE_HEAD, *(_row(d, t) for d in pilots)]
    for d in cd.cities:
        out += ["", f"### {d.city_id}: top unmatched tag signatures (OSM {d.osm_timestamp})", ""]
        out += [f"- `{sig}`: {km:.2f} km" for sig, km in d.top_unmatched[:5]] or ["- none"]
    out += ["", ODBL, TRUST_END]
    return "\n".join(out)


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(text)
    tmp.replace(path)


def write_country(
    docs_dir: Path,
    cd: CountryDiagnostics,
    thresholds: TrustThresholds,
    pilots: list[CityDiagnostics],
) -> tuple[Path, Path]:
    """docs/review/trust/<cc>.json and the generated block of <cc>.md; returns both paths.

    An existing .md keeps everything outside the block; one without a block gets it appended.
    """
    out = Path(docs_dir) / "review" / "trust"
    out.mkdir(parents=True, exist_ok=True)
    js, md = out / f"{cd.country}.json", out / f"{cd.country}.md"
    _write_atomic(js, cd.model_dump_json(indent=2) + "\n")
    block = _block(cd, thresholds, pilots)
    old = md.read_text() if md.exists() else None
    if old is None:
        text = NOTES_HEADER.format(cc=cd.country) + block + "\n"
    elif TRUST_BEGIN in old and TRUST_END in old:
        head, _, rest = old.partition(TRUST_BEGIN)
        tail = rest.partition(TRUST_END)[2]
        text = head + block + tail
    else:
        text = old.rstrip("\n") + "\n\n" + block + "\n"
    _write_atomic(md, text)
    return js, md
