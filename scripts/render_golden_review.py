"""Render the human review sheet for the Berlin golden set: a markdown table and a PNG map."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from velometer.pipeline.geometry import Projector  # noqa: E402
from velometer.pipeline.read import read_ways  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
OUT = ROOT / "docs" / "review"
TIER_COLOUR = {
    "A": "#006d2c",
    "B": "#74c476",
    "C": "#1f78b4",
    "D": "#ff7f00",
    "E": "#6a3d9a",
    "excluded": "#e31a1c",
    "none": "#bdbdbd",
}
TIER_STYLE = {"none": ":"}  # no classifier output: dotted, so it never reads as a tier
TIER_RANK = ["A", "B", "C", "D", "E", "excluded"]
TAG_PREFIXES = (
    "cycleway",
    "bicycle",
    "foot",
    "segregated",
    "sidewalk",
    "oneway",
    "access",
    "area",
    "construction",
    "proposed",
    "junction",
    "dual_carriageway",
    "traffic_mode",
)


def best_tier(proposed: list[dict]) -> str:
    """Best tier A-E, else "excluded" if any side is excluded, else "none" (no output)."""
    tiers = {p["tier"] for p in proposed}
    return next((t for t in TIER_RANK if t in tiers), "none")


def proposed_cell(proposed: list[dict]) -> str:
    def one(p: dict) -> str:
        sub = f"/{p['subtype']}" if p.get("subtype") else ""
        direction = {True: ", bidirectional", False: ", oneway"}.get(p.get("bidirectional"), "")
        return f"{p['side']}:{p['tier']}{sub} ({p['rule']}{direction})"

    return "<br>".join(one(p) for p in proposed) or "- (no output)"


def key_tags(tags: dict[str, str]) -> str:
    items = sorted((k, v) for k, v in tags.items() if k.startswith(TAG_PREFIXES))
    return "<br>".join(f"`{k}={v}`" for k, v in items)


def write_markdown(golden: dict, tags_by_id: dict[int, dict[str, str]]) -> None:
    lines = [
        "# Berlin golden set: review sheet",
        "",
        f"Source: {golden['source']}. Classifier: {golden['classifier_version']}.",
        "",
        "Tier definitions: [ADR 0002 tier table](../adr/0002-tiered-classifier-from-qecio.md#tiers)"
        "; which tiers each headline sums: [`config/presets.yaml`](../../config/presets.yaml). "
        "Each proposed entry reads `side:tier/subtype (rule, bidirectional|oneway)`; "
        "`bidirectional` drives the `qecio_weighted` length (oneway counts half). "
        "Map: `berlin_golden.png` (red = excluded, dotted grey = no classifier output).",
        "",
        "**How to sign off:** compare each way's proposal with its tags and the OSM link. "
        "If it is right, set `confirmed: true` for that way in "
        "`tests/fixtures/berlin_golden.yaml`. If it is wrong, edit that way's `proposed` list "
        "to the correct `side`/`tier`/`rule` and then set `confirmed: true`; the test then "
        "fails until the classifier agrees. Unconfirmed ways are skipped and counted.",
        "",
    ]
    groups: dict[str, list[dict]] = {}
    for w in golden["ways"]:
        groups.setdefault(w["group"], []).append(w)
    for group, ways in groups.items():
        lines += [f"## {group} ({len(ways)})", ""]
        lines += ["| way | name | highway | key cycling tags | proposed |", "|---|---|---|---|---|"]
        for w in ways:
            link = f"[{w['way_id']}](https://www.openstreetmap.org/way/{w['way_id']})"
            prop = proposed_cell(w["proposed"])
            tags = key_tags(tags_by_id.get(w["way_id"], {}))
            lines.append(f"| {link} | {w['name']} | {w['highway']} | {tags} | {prop} |")
        lines.append("")
    (OUT / "berlin_golden.md").write_text("\n".join(lines), encoding="utf-8")


def write_png(golden: dict, coords_by_id: dict[int, tuple]) -> None:
    proj = Projector(25833)
    groups: dict[str, list[dict]] = {}
    for w in golden["ways"]:
        groups.setdefault(w["group"], []).append(w)
    ncols = 4
    nrows = -(-len(groups) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(20, 4.7 * nrows), squeeze=False)
    for ax, (group, ways) in zip(axes.flat, groups.items(), strict=False):
        for w in ways:
            x, y = proj.line(coords_by_id[w["way_id"]]).xy
            tier = best_tier(w["proposed"])
            ax.plot(x, y, color=TIER_COLOUR[tier], ls=TIER_STYLE.get(tier, "-"), lw=2.5)
        ax.set_title(f"{group} ({len(ways)})")
        ax.set_aspect("equal", adjustable="datalim")
        ax.tick_params(labelsize=6)
    for ax in list(axes.flat)[len(groups) :]:
        ax.axis("off")
    handles = [
        Line2D([0], [0], color=c, ls=TIER_STYLE.get(t, "-"), lw=3, label=t)
        for t, c in TIER_COLOUR.items()
    ]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), title="best proposed tier")
    fig.suptitle("Berlin golden set (EPSG:25833, metres) - " + golden["source"], fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.savefig(OUT / "berlin_golden.png", dpi=110)


def main() -> None:
    golden = yaml.safe_load((FIX / "berlin_golden.yaml").read_text())
    ways = {w.id: w for w in read_ways(FIX / "berlin_golden.osm").ways}
    OUT.mkdir(parents=True, exist_ok=True)
    write_markdown(golden, {i: dict(w.tags) for i, w in ways.items()})
    write_png(golden, {i: w.coords for i, w in ways.items()})


if __name__ == "__main__":
    main()
