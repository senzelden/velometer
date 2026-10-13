"""The rows of the German review page (M12 Task 10): every German string a reader can see, beside
its English, as JSON.

    uv run python tools/review_rows.py --out rows.json

A row is `{id, group, page, section, kind, file, path, en, de, src, quote}`:

- `id` is `f"{file}#{path}"`, unique and stable: `file` is the file the German lives in (relative
  to `--root`), `path` the place in it (a walk path, a source field, a catalogue key, a config
  location or an explanation key);
- `group` is Overview, Stories, a city name, Organisations, Plans, Glosses, UI, Config or Flagged
  years; `page` and `section` place the row inside it;
- `kind` is paragraph, heading, title, label, gloss, ui, config or explanation;
- `en` and `de` are the current texts (`de` is null where the German is missing), `src` the stamp
  of the English the German was made from (the English's own stamp where nothing is stored);
- `quote` is the original quotation of a gloss row, null elsewhere.

Rows are ordered by group, then page, then section, each page in file order. Not rows: the
`literals` of a translation file (number forms the check allows, not prose).
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from velometer import i18n
from velometer.config import load_cities, reader_prose
from velometer.content.check import COUNTER_PAGE, PLAN_DOCUMENTS
from velometer.content.models import Narrative, Organisation
from velometer.content.translate import (
    load_english,
    load_translation,
    src_hash,
    tr_strings,
    twin_path,
    walk,
)
from velometer.plans.models import REPORT_NOTES_DE_FILE
from velometer.timeseries import explanation, german_explanations, stamped_explanation

ROOT = Path(__file__).resolve().parents[1]
GROUPS = (
    "Overview",
    "Stories",
    None,
    "Organisations",
    "Plans",
    "Glosses",
    "UI",
    "Config",
    "Flagged years",
)  # fmt: skip  (None: the city groups, by name)
KINDS = ("paragraph", "heading", "title", "label", "gloss", "ui", "config", "explanation")
STORIES = "combined"


def _rel(path: Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _row(group, page, section, kind, file, path, en, de, src, quote=None) -> dict:
    assert kind in KINDS, kind
    return {
        "id": f"{file}#{path}", "group": group, "page": page, "section": section, "kind": kind,
        "file": file, "path": path, "en": en, "de": de, "src": src, "quote": quote,
    }  # fmt: skip


def _kind(walk_path: str) -> str:
    last = walk_path.split(".")[-2 if walk_path.startswith("sections.") else 0]
    if walk_path == "title":
        return "title"
    if walk_path.endswith(".heading"):
        return "heading"
    if walk_path.startswith("data_refs.") or last == "dimensions":
        return "label"
    return "paragraph"


def _place(model, rel: str, cities: dict[str, str]) -> tuple[str, str]:
    """(group, page) of an English content file."""
    if isinstance(model, Narrative):
        if model.city_id == STORIES:
            return "Stories", "Story"
        name = cities.get(model.city_id, model.city_id)
        return name, name
    if isinstance(model, Organisation):
        return "Organisations", model.name
    if rel.startswith("plans/"):
        return "Plans", model.title
    return "Overview", "Counters" if rel == COUNTER_PAGE else "Explainer"


def _section(model, walk_path: str) -> str:
    parts = walk_path.split(".")
    if parts[0] != "sections":
        return {"data_refs": "Data references"}.get(parts[0], "Top")
    i = int(parts[1])
    sec = model.sections[i]
    head = getattr(sec, "heading", None)
    name = head or getattr(sec, "role", None) or getattr(sec, "step", None) or ""
    return f"{i + 1:02d} {name}".strip()


def _english_files(content: Path) -> list[str]:
    rels = ["explainer.yaml", COUNTER_PAGE]
    rels += [f"narratives/{p.name}" for p in sorted((content / "narratives").glob("*.yaml"))]
    rels += [f"organisations/{p.name}" for p in sorted((content / "organisations").glob("*.yaml"))]
    rels += [r for r in PLAN_DOCUMENTS if r != COUNTER_PAGE]
    return [r for r in rels if (content / r).is_file()]


def content_rows(content: Path, root: Path, cities: dict[str, str]) -> list[dict]:
    """One row per translatable string of every English content file with a German twin."""
    rows = []
    for rel in _english_files(content):
        en = load_english(content / rel)
        de_path = content / twin_path(Path(rel))
        german = tr_strings(load_translation(de_path, en)) if de_path.is_file() else {}
        group, page = _place(en, rel, cities)
        file = _rel(de_path, root)
        for path, text in walk(en):
            tr = german.get(path)
            rows.append(_row(
                group, page, _section(en, path), _kind(path), file, path, text,
                tr.text if tr else None, tr.src if tr and tr.src else src_hash(text),
            ))  # fmt: skip
    return rows


def source_rows(content: Path, root: Path) -> list[dict]:
    """The German source titles and publishers and the German glosses of quotations."""
    rows = []
    for path in sorted((content / "sources").glob("*.yaml")):
        file, page = _rel(path, root), path.stem
        for s in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("sources", []):
            sid = s["id"]
            for field, kind in (("publisher", "label"), ("title", "title")):
                if s.get(f"{field}_de"):
                    en = s[field]
                    rows.append(_row("Glosses", page, sid, kind, file, f"{sid}.{field}_de", en,
                                     s[f"{field}_de"], src_hash(en)))  # fmt: skip
            if str(s.get("language", "")).split("-")[0] == "de":
                continue  # a German quotation needs no German gloss
            for e in s.get("excerpts", []):
                en = e.get("gloss_en") or ""
                rows.append(_row(
                    "Glosses", page, sid, "gloss", file, f"{sid}.{e['id']}.gloss_de", en,
                    e.get("gloss_de"), src_hash(e["text"]), quote=e["text"],
                ))  # fmt: skip
    return rows


def _flat(value) -> str:
    if isinstance(value, dict):
        return " | ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def ui_rows(catalogue_dir: Path, root: Path) -> list[dict]:
    """One row per catalogue key whose German differs from its English."""
    en, de = i18n.catalogue("en", catalogue_dir), i18n.catalogue("de", catalogue_dir)
    file = _rel(catalogue_dir / "de.yaml", root)
    rows = []
    for key, value in en.items():
        if key in de and de[key] != value:
            page, _, section = key.partition(".")
            rows.append(_row("UI", page, section.rpartition(".")[0] or section, "ui", file, key,
                             _flat(value), _flat(de[key]), src_hash(_flat(value))))  # fmt: skip
    return rows


def config_rows(config: Path, root: Path) -> list[dict]:
    """One row per English config reader prose with a German sibling (`reader_prose`); a value
    repeated in one file (figures.csv notes) is one row."""
    rows, seen = [], set()
    for where, en, de in reader_prose(config):
        name, _, path = where.partition(" ")
        if name == f"plans/{REPORT_NOTES_DE_FILE}":
            path = f"notes.{src_hash(en)}"
        file = _rel(config / name, root)
        if (file, en) in seen:
            continue
        seen.add((file, en))
        top = re.split(r"[ .]", path, maxsplit=1)[0]
        rows.append(_row("Config", file, top, "config", file, path, en, de or None, src_hash(en)))
    return rows


def explanation_rows(report: Path, root: Path) -> list[dict]:
    """One row per `###` entry of the German flagged-year explanations, in their order."""
    de_path = german_explanations(report)
    if not de_path.is_file():
        return []
    file = _rel(de_path, root)
    rows = []
    for key in re.findall(r"^### (\S+)\s*$", de_path.read_text(encoding="utf-8"), re.M):
        text, src = stamped_explanation(de_path, key)
        city, kind, label = (key.split("/") + ["", ""])[:3]
        rows.append(_row("Flagged years", f"{city}/{kind}", label, "explanation", file, key,
                         explanation(report, key), text, src))  # fmt: skip
    return rows


def _group_rank(row: dict) -> tuple[int, str]:
    if row["group"] in GROUPS:
        return GROUPS.index(row["group"]), ""
    return GROUPS.index(None), row["group"]


def build_rows(content: Path, config: Path, docs: Path, root: Path = ROOT) -> list[dict]:
    """Every review row, ordered by group, then page (first appearance), then file order."""
    cities = {c.id: c.name for c in load_cities(config / "cities.yaml")}
    rows = [
        *content_rows(content, root, cities),
        *source_rows(content, root),
        *ui_rows(content / "ui", root),
        *config_rows(config, root),
        *explanation_rows(docs / "review" / "m3_timeseries.md", root),
    ]
    first: dict[tuple[str, str], int] = {}
    for i, r in enumerate(rows):
        first.setdefault((r["group"], r["page"]), i)
    rows.sort(key=lambda r: (*_group_rank(r), first[(r["group"], r["page"])]))
    dupes = sorted(i for i, n in Counter(r["id"] for r in rows).items() if n > 1)
    if dupes:
        raise ValueError(f"duplicate review row ids: {dupes}")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--content", type=Path, default=ROOT / "content")
    ap.add_argument("--config", type=Path, default=ROOT / "config")
    ap.add_argument("--docs", type=Path, default=ROOT / "docs")
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    rows = build_rows(a.content, a.config, a.docs, a.root)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
