"""`velometer dataset bundle` (M17 Task 7): the public export's CSVs and a README as one
reproducible zip, and the Zenodo metadata as a text sheet, for a manual deposit.

The notices of the README are the preamble lines of the bundled CSVs themselves (ADR 0008:
`csvexport.csv_preamble`) plus the OSM and boundary notices of `credits`, never retyped here. The
commit, the classifier versions, the OSM timestamps and the repo URL come from the export's
`build.json`, so the bundle reflects what was exported, not the tree at bundle time.
"""

import json
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from velometer import credits
from velometer.app.urls import absolute_url
from velometer.report import csvexport

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "content" / "dataset"
CREATOR = "Dennis Senzel"
LICENCE = "odbl-1.0"
KEYWORDS = ("cycling infrastructure", "OpenStreetMap", "open data", "urban mobility", "Europe")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # the zip format's earliest date


class BundleError(Exception):
    """The export cannot be bundled; the message says why."""


def _build(site: Path) -> dict:
    path = site / "build.json"
    if not path.is_file():
        raise BundleError(f"{path}: no build.json; give a finished public export")
    build = json.loads(path.read_text(encoding="utf-8"))
    if not build.get("public"):
        raise BundleError(f"{path}: not a public export (run `app export --public`)")
    if not build.get("commit") or build.get("commit") == "unknown":
        raise BundleError(f"{path}: no commit recorded; re-export from a git checkout")
    if build.get("dirty"):
        raise BundleError(f"{path}: exported from a dirty tree; export a committed state")
    repo_url = (build.get("site") or {}).get("repo_url")
    site_url = (build.get("site") or {}).get("url")
    if not repo_url or not site_url:
        raise BundleError(f"{path}: the site block lacks repo_url or url")
    return build


def preamble_notices(csvs: dict[str, str]) -> list[str]:
    """The distinct notice lines of the CSV preambles (the `#` lines but the commit and time
    stamp), in first-seen order, over the files in name order."""
    seen: list[str] = []
    for name in sorted(csvs):
        for line in csvs[name].splitlines():
            if not line.startswith("# "):
                break
            text = line[2:]
            if text.startswith("velometer ") and " generated " in text:
                continue
            if text not in seen:
                seen.append(text)
    return seen


def notices(csvs: dict[str, str]) -> list[str]:
    """The preamble notices verbatim; a file set without the OSM notice is refused (ODbL §4.2)."""
    found = preamble_notices(csvs)
    for label, line in (("OSM", csvexport.ATTRIBUTION), ("boundary", csvexport.BOUNDARIES)):
        if line[2:] not in found:
            raise BundleError(f"the CSV preambles carry no {label} notice; re-export the data")
    return found


def credit_lines() -> list[str]:
    """The credits of the three statistics offices and Eurostat's disclaimer, as `credits` words
    them, whichever of them a given file's rows used."""
    lines = [text for text, _lang in credits.CREDITS.values()]
    note = credits.disclaimer(list(credits.BODIES))
    return lines + ([note] if note else [])


def render_readme(build: dict, csv_names: list[str], csvs: dict[str, str]) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701  (Markdown, not HTML)
    )
    stamps = build["osm_timestamps"]
    return env.get_template("README.md.j2").render(
        commit=build["commit"],
        n_cities=len(stamps),
        site_url=build["site"]["url"],
        methodology_url=absolute_url(build["site"]["url"], "/methodology", "/"),
        terms_note=credits.BOUNDARY_TERMS_NOTE,
        credit_lines=credit_lines(),
        repo_url=build["site"]["repo_url"],
        files=csv_names,
        notices=notices(csvs),
        classifier_versions=build["classifier_versions"],
        timestamp_lines=[f"  - {c}: {', '.join(ts)}" for c, ts in sorted(stamps.items())],
        odbl_url=credits.ODBL_URL,
        creator=CREATOR,
    )


def zenodo_sheet(build: dict) -> str:
    stamps = [t for ts in build["osm_timestamps"].values() for t in ts]
    first, last = min(stamps)[:10], max(stamps)[:10]
    n = len(build["osm_timestamps"])
    desc = (
        f"CSV tables of protected cycling infrastructure in {n} European cities, as mapped in "
        f"OpenStreetMap (snapshots {first} to {last}), exported from {build['site']['url']} at "
        f"commit {build['commit']}. Lengths are mapped kilometres, not built kilometres. "
        "The README names the sources, notices, classifier versions and snapshot timestamps. "
        + credits.BOUNDARY_TERMS_NOTE
        + " Credits: "
        + "; ".join(credit_lines())
    )
    lines = [
        "Zenodo metadata for the dataset deposit (type: Dataset). Paste each field by hand.",
        "",
        "Title: velometer data: protected cycling infrastructure in European cities, "
        + build["commit"],
        f"Creators: {CREATOR}",
        f"Description: {desc}",
        f"License: {LICENCE}",
        f"Keywords: {'; '.join(KEYWORDS)}",
        f"Version: {build['commit']}",
        f"Related identifier: isSupplementTo {build['site']['repo_url']} (resource type: Software)",
        "",
    ]
    return "\n".join(lines)


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    """A zip that depends only on the members: sorted, one fixed time, fixed permissions and
    creator system, deterministic deflate."""
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            z.writestr(info, members[name], compresslevel=9)
    return buf.getvalue()


def bundle(site: Path, out: Path) -> tuple[Path, Path]:
    """Write `velometer-data-<commit>.zip` and `zenodo-metadata.txt` into `out`."""
    site, out = Path(site), Path(out)
    build = _build(site)
    csv_paths = sorted((site / "data").glob("*.csv"))
    if not csv_paths:
        raise BundleError(f"{site / 'data'}: no CSV files")
    csvs = {p.name: p.read_text(encoding="utf-8") for p in csv_paths}
    members = {f"data/{p.name}": p.read_bytes() for p in csv_paths}
    members["README.md"] = render_readme(build, sorted(csvs), csvs).encode("utf-8")
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / f"velometer-data-{build['commit']}.zip"
    zpath.write_bytes(_zip_bytes(members))
    mpath = out / "zenodo-metadata.txt"
    mpath.write_text(zenodo_sheet(build), encoding="utf-8")
    return zpath, mpath
