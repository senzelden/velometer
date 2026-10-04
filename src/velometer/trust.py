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
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel

from velometer.config import (
    ActivityConfig,
    CityConfig,
    TrustThresholds,
    default_config_dir,
    load_classifier,
    load_trust,
)
from velometer.db import fetch_boundary, fetch_run
from velometer.osmium import relation_polygon
from velometer.pipeline.activity import cycling_tags
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.drift import is_unmatched_road_side
from velometer.pipeline.measure import measure
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import Classified
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


def _pct(x: float | None, limit: float | None = None) -> str:
    """A share as a percentage: 2 decimals when it or its limit is below 1 %, so a value and a
    limit that differ there do not print alike ("0.1%" against "0.1%"); 1 decimal otherwise."""
    if x is None:
        return "n/a"
    places = 2 if min(x, x if limit is None else limit) < 0.01 else 1
    return f"{100 * x:.{places}f}%"


def _row(d: CityDiagnostics, t: TrustThresholds) -> str:
    diff = "n/a" if d.boundary_diff_pct is None else f"{d.boundary_diff_pct:.1f}%"
    over = ", ".join(breaches(d, t)) or "none"
    return (
        f"| {d.city_id} | {d.run_id} | {d.cycling_km:.1f} "
        f"| {_pct(d.unrecognised_share, t.unrecognised_share_max)} "
        f"| {_pct(d.excluded_share, t.excluded_share_max)} "
        f"| {_pct(d.b_share_of_ab, t.b_share_of_ab_max)} | {diff} | {over} |"
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


# --- golden samples ---------------------------------------------------------------------------


class Sample(BaseModel):
    way_id: int
    city_id: str
    group: str  # rule id, "unmatched:<n>" or "extra"
    name: str  # the way's name tag or ""
    highway: str
    proposed: list[dict]  # [{side, tier, rule, subtype, bidirectional}], as berlin_golden


def proposed_sides(classified: Iterable[Classified]) -> dict[int, list[dict]]:
    """The classifier's output per way in the berlin_golden schema: sides with a tier (or
    `excluded`), sorted by side."""
    out: dict[int, list[dict]] = defaultdict(list)
    for c in classified:
        if c.tier is not None:
            out[c.side.way_id].append(
                {
                    "side": c.side.side,
                    "tier": c.tier,
                    "rule": c.rule_id,
                    "subtype": c.subtype,
                    "bidirectional": c.attrs.get("bidirectional"),
                }
            )
    return {w: sorted(p, key=lambda d: d["side"]) for w, p in out.items()}


def observed_tiers(ways: Iterable, cfg) -> dict[int, set[tuple[str, str, str]]]:
    """The classifier's verdict per way: (side, tier, rule_id) of every tiered way-side. A way
    with no tiered side is absent (a defaultdict, so a lookup gives the empty set)."""
    out: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
    for c in classify_ways(ways, cfg):
        if c.tier is not None:
            out[c.side.way_id].add((c.side.side, c.tier, c.rule_id))
    return out


def make_sample(
    way_id: int,
    group: str,
    classified: Iterable[Classified],
    tags_by_way: Mapping[int, Mapping[str, str]],
    city_by_way: Mapping[int, str] | None = None,
    city_id: str = "",
) -> Sample:
    tags = tags_by_way[way_id]
    return Sample(
        way_id=way_id,
        city_id=(city_by_way or {}).get(way_id, city_id),
        group=group,
        name=tags.get("name", ""),
        highway=tags.get("highway", ""),
        proposed=proposed_sides(classified).get(way_id, []),
    )


def sample_ways(
    classified: list[Classified],
    way_lengths: Mapping[int, float],
    tags_by_way: Mapping[int, Mapping[str, str]],
    *,
    activity_cfg: ActivityConfig,
    top_rules: int = 6,
    per_rule: int = 1,
    unmatched: int = 3,
    city_by_way: Mapping[int, str] | None = None,
    city_id: str = "",
) -> list[Sample]:
    """The longest way-side of each of the `top_rules` rules with the most km (tiers A-E and
    excluded), then of each of the `unmatched` largest unmatched tag signatures (road sides no
    rule recognised, on ways with cycling tags). Deduplicated by way id: a way already picked is
    skipped and the next longest side of the group is taken. Deterministic: ties break on way id.
    """

    def longest(sides: list[Classified], n: int, taken: set[int]) -> list[int]:
        ranked = sorted(
            sides, key=lambda c: (-way_lengths[c.side.way_id], c.side.way_id, c.side.side)
        )
        picked: list[int] = []
        for c in ranked:
            w = c.side.way_id
            if w not in taken and w not in picked:
                picked.append(w)
            if len(picked) == n:
                break
        return picked

    by_rule: dict[str, list[Classified]] = defaultdict(list)
    by_sig: dict[str, list[Classified]] = defaultdict(list)
    for c in classified:
        if c.tier in (*TIERS, "excluded") and c.rule_id is not None:
            by_rule[c.rule_id].append(c)
        if is_unmatched_road_side(c) and cycling_tags(tags_by_way[c.side.way_id], activity_cfg):
            by_sig[tag_signature(tags_by_way[c.side.way_id], activity_cfg)].append(c)

    def km(sides: list[Classified]) -> float:
        return sum(way_lengths[c.side.way_id] for c in sides)

    taken: set[int] = set()
    picks: list[tuple[int, str]] = []
    rules = sorted(by_rule, key=lambda r: (-km(by_rule[r]), r))[:top_rules]
    for rule in rules:
        for w in longest(by_rule[rule], per_rule, taken):
            taken.add(w)
            picks.append((w, rule))
    sigs = sorted(by_sig, key=lambda s: (-km(by_sig[s]), s))[:unmatched]
    for n, sig in enumerate(sigs, 1):
        for w in longest(by_sig[sig], 1, taken):
            taken.add(w)
            picks.append((w, f"unmatched:{n}"))
    return [
        make_sample(w, group, classified, tags_by_way, city_by_way, city_id) for w, group in picks
    ]


@dataclass
class SampleInputs:
    """What `trust sample` needs from the current LAU runs of one country's cities."""

    classified: list[Classified] = field(default_factory=list)
    way_lengths: dict[int, float] = field(default_factory=dict)
    tags_by_way: dict[int, Mapping[str, str]] = field(default_factory=dict)
    city_by_way: dict[int, str] = field(default_factory=dict)  # first city to hold the way
    snapshots: dict[str, Path] = field(default_factory=dict)  # city id -> its snapshot
    stamps: list[str] = field(default_factory=list)  # "<city id> <osm timestamp>"


def load_sample_inputs(
    conn, cities: Iterable[CityConfig], selector: Selector, data_dir: Path, config_dir: Path
) -> SampleInputs:
    """Classify each city's current LAU snapshot with the selector's classifier.

    Raises NoCurrentRun, or FileNotFoundError naming a city whose snapshot or boundary file is
    missing."""
    classifier = load_classifier(Path(config_dir) / "classifier" / f"{selector.version}.yaml")
    inputs = SampleInputs()
    for c in cities:
        run_id = selector.latest(conn, c.id, "lau")
        if run_id is None:
            raise NoCurrentRun(f"no current LAU run for: {c.id}")
        row = fetch_run(conn, run_id)
        snap = snapshot_path(row, data_dir)
        boundary = fetch_boundary(conn, c.id, "lau")
        if not snap.is_file() or boundary is None or not Path(boundary.path).is_file():
            raise FileNotFoundError(f"{c.id}: snapshot or boundary file not found")
        ways = read_ways(snap).ways
        result = measure(
            ways, classifier, c.epsg, boundary=load_boundary_polygon(Path(boundary.path), c.epsg)
        )
        inputs.classified += result.classified
        inputs.way_lengths |= result.way_lengths
        for w in ways:
            inputs.tags_by_way[w.id] = w.tags
            inputs.city_by_way.setdefault(w.id, c.id)
        inputs.snapshots[c.id] = snap
        inputs.stamps.append(f"{c.id} {row['osm_timestamp']}")
    return inputs


GOLDEN_HEADER = f"# {ODBL}\n"


def golden_doc(samples: list[Sample], source: str, classifier_version: str) -> dict:
    """The berlin_golden.yaml schema: every way unconfirmed, for the user to sign off."""
    return {
        "source": source,
        "classifier_version": classifier_version,
        "ways": [
            {**s.model_dump(exclude={"city_id"}), "confirmed": False, "note": ""} for s in samples
        ],
    }


def add_osm_attribution(path: Path) -> None:
    """Put the ODbL note (the wording of GOLDEN_HEADER) into an .osm file as an XML comment
    right after the XML declaration (ADR 0008); a file that already carries it is left alone."""
    text = path.read_text(encoding="utf-8")
    if ODBL in text:
        return
    comment = f"<!-- {ODBL} -->"
    if text.startswith("<?xml"):
        end = text.index("?>") + 2
        text = f"{text[:end]}\n{comment}{text[end:]}"
    else:
        text = f"{comment}\n{text}"
    _write_atomic(path, text)


def write_golden_yaml(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    _write_atomic(path, GOLDEN_HEADER + body)


def _sample_tags(tags: Mapping[str, str], cfg: ActivityConfig) -> str:
    keep = dict(cycling_tags(tags, cfg))
    if "highway" in tags:
        keep["highway"] = tags["highway"]
    return "<br>".join(f"`{k}={keep[k]}`" for k in sorted(keep))


def write_golden_review(
    docs_dir: Path,
    country: str,
    samples: list[Sample],
    tags_by_way: Mapping[int, Mapping[str, str]],
    activity_cfg: ActivityConfig,
) -> Path:
    """docs/review/trust/<cc>_golden.md: one row per sample, with an empty verdict column."""
    out = Path(docs_dir) / "review" / "trust"
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Golden samples: {country}",
        "",
        "Open each way, compare the tags with our tier and rule, write the verdict (ok, or what "
        "is wrong), then set `confirmed: true` in the yaml for the ways you agree with.",
        "",
        "| way | city | tags | our tier / rule | verdict |",
        "|---|---|---|---|---|",
    ]
    for s in samples:
        link = f"[{s.way_id}](https://www.openstreetmap.org/way/{s.way_id})"
        ours = (
            "<br>".join(f"{p['side']}: {p['tier']} / {p['rule']}" for p in s.proposed)
            or "no output"
        )
        lines.append(
            f"| {link} {s.name} | {s.city_id} | {_sample_tags(tags_by_way[s.way_id], activity_cfg)}"
            f" | {ours} | |"
        )
    lines += ["", ODBL, ""]
    path = out / f"{country}_golden.md"
    _write_atomic(path, "\n".join(lines))
    return path


# --- golden diff (a new classifier against the signed-off golden samples) -------------------

GOLDEN_DIFF_BEGIN = "<!-- golden-diff:start -->"
GOLDEN_DIFF_END = "<!-- golden-diff:end -->"


@dataclass(frozen=True)
class RetierRow:
    """One side of a retiered golden way; the new tier and rule are None where the new
    classifier gives that side none, the old ones where the golden file had no such side."""

    way_id: int
    name: str
    side: str
    old_tier: str | None
    old_rule: str | None
    new_tier: str | None
    new_rule: str | None
    tags: Mapping[str, str]


@dataclass
class GoldenDiff:
    cc: str
    renamed: list[int] = field(default_factory=list)  # same (side, tier), other rule ids
    retiered: list[RetierRow] = field(default_factory=list)  # the (side, tier) set differs
    unchanged: list[int] = field(default_factory=list)
    proposed: dict[int, list[dict]] = field(default_factory=dict)  # new classifier, per way


def golden_diff(yml: Path, osm: Path, cfg, cc: str | None = None) -> GoldenDiff:
    """Compare the golden file's `proposed` sides with the classifier `cfg` on the same ways.

    A way is unchanged when its (side, tier, rule) set is the same, renamed when only the rule
    ids differ, retiered when its (side, tier) set differs. `min_classifier` plays no part."""
    ways = yaml.safe_load(Path(yml).read_text())["ways"]
    osm_ways = read_ways(osm).ways
    observed = observed_tiers(osm_ways, cfg)
    tags_by_way = {w.id: dict(w.tags) for w in osm_ways}
    diff = GoldenDiff(cc=cc if cc is not None else Path(yml).stem.upper())
    diff.proposed = proposed_sides(classify_ways(osm_ways, cfg))
    for w in ways:
        wid = w["way_id"]
        old = {(p["side"], p["tier"], p["rule"]) for p in w["proposed"]}
        new = observed.get(wid, set())
        if old == new:
            diff.unchanged.append(wid)
        elif {(s, t) for s, t, _ in old} == {(s, t) for s, t, _ in new}:
            diff.renamed.append(wid)
        else:
            name = w.get("name") or tags_by_way.get(wid, {}).get("name", "")
            old_by = {s: (t, r) for s, t, r in old}
            new_by = {s: (t, r) for s, t, r in new}
            for side in sorted(old_by.keys() | new_by.keys()):
                (ot, orule) = old_by.get(side, (None, None))
                (nt, nrule) = new_by.get(side, (None, None))
                diff.retiered.append(
                    RetierRow(wid, name, side, ot, orule, nt, nrule, tags_by_way.get(wid, {}))
                )
    return diff


def _tier_rules(proposed: list[dict]) -> str:
    return ", ".join(sorted({f"{p['tier']} {p['rule']}" for p in proposed}))


def write_v4_proposal(
    yml: Path, diff: GoldenDiff, cfg, out_dir: Path, name: str | None = None
) -> Path:
    """<out_dir>/<name> (default the yml's name): the golden file re-proposed by `cfg`.

    Renamed and unchanged ways keep their sign-off; a retiered way is unconfirmed, its note
    recording the old tier and rule."""
    doc = yaml.safe_load(Path(yml).read_text())
    old_version = doc.get("classifier_version", "?")
    retiered = {r.way_id for r in diff.retiered}
    ways = []
    for w in doc["ways"]:
        wid = w["way_id"]
        new = {**w, "proposed": diff.proposed.get(wid, [])}
        if wid in retiered:
            new["confirmed"] = False
            new["note"] = f"{old_version}: {_tier_rules(w['proposed'])}; awaiting re-sign"
        ways.append(new)
    doc = {**doc, "classifier_version": cfg.version, "ways": ways}
    out = Path(out_dir) / (name or Path(yml).name)
    write_golden_yaml(out, doc)
    return out


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _tr(tier: str | None, rule: str | None) -> str:
    return f"{tier} {rule}" if tier is not None else "none"


def render_golden_changes(diffs: Mapping[str, GoldenDiff], version: str) -> str:
    """The generated block of v4-changes.md: a count line and a retiered table per country."""
    lines = [GOLDEN_DIFF_BEGIN, ""]
    for d in diffs.values():
        n_retiered = len({r.way_id for r in d.retiered})
        lines.append(
            f"- {d.cc}: {len(d.renamed)} renamed, {n_retiered} retiered, "
            f"{len(d.unchanged)} unchanged"
        )
    for cc, d in diffs.items():
        lines += [
            "",
            f"## {cc}",
            "",
            f"| way | name | tags | old tier / rule | {version} tier / rule | side | verdict |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in d.retiered:
            link = f"[{r.way_id}](https://www.openstreetmap.org/way/{r.way_id})"
            tags = "<br>".join(f"`{_cell(f'{k}={v}')}`" for k, v in sorted(r.tags.items()))
            lines.append(
                f"| {link} | {_cell(r.name)} | {tags} | {_tr(r.old_tier, r.old_rule)} "
                f"| {_tr(r.new_tier, r.new_rule)} | {r.side} | |"
            )
    lines += ["", GOLDEN_DIFF_END, "", ODBL, ""]
    return "\n".join(lines)


def write_golden_changes(path: Path, diffs: Mapping[str, GoldenDiff], version: str) -> Path:
    """Write the generated block into `path`; text outside the markers is kept."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    full = render_golden_changes(diffs, version)
    block = full[full.index(GOLDEN_DIFF_BEGIN) : full.index(GOLDEN_DIFF_END) + len(GOLDEN_DIFF_END)]
    old = path.read_text() if path.exists() else None
    if old is not None and GOLDEN_DIFF_BEGIN in old and GOLDEN_DIFF_END in old:
        head, _, rest = old.partition(GOLDEN_DIFF_BEGIN)
        text = head + block + rest.partition(GOLDEN_DIFF_END)[2]
    elif old is not None:
        text = old.rstrip("\n") + "\n\n" + block + "\n"
    else:
        title = f"# Golden samples against classifier {version}\n\n"
        text = title + full
    _write_atomic(path, text)
    return path


# --- trust check ------------------------------------------------------------------------------

SHARE_THRESHOLDS = ("unrecognised_share_max", "excluded_share_max", "b_share_of_ab_max")
PLACEHOLDER = 1.0
EXEMPT_NO_EVIDENCE = frozenset({"DE"})  # the Berlin golden set predates the trust layer


def expects_newer_classifier(way: Mapping, classifier_version: str) -> bool:
    """The golden way's verdict needs a later classifier (its `min_classifier`, e.g. "v3") than
    `classifier_version`: it is not compared yet, and its country cannot be trusted."""
    want = way.get("min_classifier")
    return want is not None and int(want.removeprefix("v")) > int(
        classifier_version.removeprefix("v")
    )


def golden_paths(cc: str, config_dir: Path, root: Path | None = None) -> tuple[Path, Path] | None:
    """(yaml, osm) of the golden fixtures the country's `golden` entry in trust.yaml names, or
    None when it names none. The entry is a path without extension, relative to the repo root
    (`root`, default the parent of `config_dir`). The files are not checked to exist."""
    ct = load_trust(Path(config_dir) / "trust.yaml").countries.get(cc)
    if ct is None or ct.golden is None:
        return None
    base = Path(root if root is not None else Path(config_dir).parent) / ct.golden
    return base.parent / f"{base.name}.yaml", base.parent / f"{base.name}.osm"


def golden_problems(cc: str, paths: tuple[Path, Path], classifier_path: Path) -> list[str]:
    """(a): the country's golden fixtures (`golden_paths`) must be fully confirmed and every
    confirmed way must match the classifier at `classifier_path`."""
    yml, osm = paths
    for f in (yml, osm):
        if not f.is_file():
            return [f"{cc}: golden fixture missing: {f}"]
    ways = yaml.safe_load(yml.read_text())["ways"]
    cfg = load_classifier(classifier_path)
    observed = observed_tiers(read_ways(osm).ways, cfg)
    out = []
    unconfirmed = [w for w in ways if not w["confirmed"]]
    if unconfirmed:
        out.append(f"{cc}: {len(unconfirmed)}/{len(ways)} golden ways unconfirmed")
    for w in ways:
        if not w["confirmed"]:
            continue
        if expects_newer_classifier(w, cfg.version):
            out.append(
                f"{cc}: golden way {w['way_id']} expects classifier {w['min_classifier']} "
                f"(report classifier {cfg.version})"
            )
            continue
        want = {(p["side"], p["tier"], p["rule"]) for p in w["proposed"]}
        if observed[w["way_id"]] != want:
            out.append(f"{cc}: golden way {w['way_id']} does not match the report classifier")
    return out


def stale_problems(cc: str, cd: CountryDiagnostics, latest: Mapping[str, int | None]) -> list[str]:
    """(c): each city's `run_id` in <cc>.json must be the latest current LAU run."""
    return [
        f"{cc}: {d.city_id} diagnosed run {d.run_id}, current run is {latest.get(d.city_id)} "
        f"(stale: re-run `velometer trust diagnose --country {cc}`)"
        for d in cd.cities
        if latest.get(d.city_id) != d.run_id
    ]


def breach_problems(
    cc: str, cd: CountryDiagnostics, thresholds: TrustThresholds, md_text: str
) -> list[str]:
    """(d): every breach needs a `### <city>/<metric>` heading (the reviewer's note) in <cc>.md."""
    out = []
    for d in cd.cities:
        for metric in breaches(d, thresholds):
            heading = re.compile(rf"^### {re.escape(d.city_id)}/{re.escape(metric)}\b", re.M)
            if not heading.search(md_text):
                out.append(
                    f"{cc}: {d.city_id} breaches {metric} with no `### {d.city_id}/{metric}` "
                    f"note in {cc}.md"
                )
    return out


def placeholder_problems(t: TrustThresholds) -> list[str]:
    """(e): a share threshold still at 1.0 limits nothing."""
    return [
        f"threshold {name} is still the placeholder {PLACEHOLDER}"
        for name in SHARE_THRESHOLDS
        if getattr(t, name) == PLACEHOLDER
    ]
