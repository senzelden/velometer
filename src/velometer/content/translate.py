"""German translation files beside the English content (M12 spec §4.4).

A translation file mirrors its English file's structure and holds only the translatable strings,
each `{text, src}`. Strings are addressed by walk paths: `title`, `dek`, `intro.<i>`,
`sections.<i>.heading`, `sections.<i>.paragraphs.<j>`, `sections.<i>.dimensions.<k>` and
`data_refs.<id>` (a data reference's label). `src` is the stamp of the English string the text
was translated from; `stamp` writes it, the content check compares it with the English today.
A blank text counts as missing: it falls back to English and is a completeness gap.

Translation files are machine-written and comment-free: `stamp` and `edit_path` re-dump the
whole file, so YAML comments and hand formatting do not survive.
"""

import hashlib
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from velometer.content.models import (
    ContentError,
    DocumentTr,
    Explainer,
    Narrative,
    NarrativeTr,
    Organisation,
    OrganisationTr,
    Tr,
)

English = Narrative | Explainer | Organisation
Translation = NarrativeTr | DocumentTr | OrganisationTr
DE = "de"
FOLD_OVER = 80  # longer strings are dumped in folded style


def src_hash(text: str) -> str:
    """The stamp of an English string: whitespace-normalised, so re-wrapping is not an edit."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()[:12]


def twin_path(en_rel: Path) -> Path:
    """`narratives/berlin.yaml` -> `narratives/de/berlin.yaml`."""
    return en_rel.parent / DE / en_rel.name


def english_path(de_rel: Path) -> Path:
    """The English file of a translation file; ValueError when the path is not one."""
    if de_rel.parent.name != DE:
        raise ValueError(f"{de_rel}: a translation file lives in a `{DE}/` directory")
    return de_rel.parent.parent / de_rel.name


# --- walking ------------------------------------------------------------------------------


def walk(model: English) -> Iterator[tuple[str, str]]:
    """(walk path, text) of every translatable string of an English model, in file order."""
    if isinstance(model, Narrative):
        yield "title", model.title
        yield "dek", model.dek
    elif isinstance(model, Explainer):
        yield "title", model.title
        for i, p in enumerate(model.intro):
            yield f"intro.{i}", p
    for i, sec in enumerate(model.sections):
        if sec.heading is not None:
            yield f"sections.{i}.heading", sec.heading
        for j, p in enumerate(sec.paragraphs):
            yield f"sections.{i}.paragraphs.{j}", p
        for k, v in (getattr(sec, "dimensions", None) or {}).items():
            yield f"sections.{i}.dimensions.{k}", v
    for d in model.data_refs:
        yield f"data_refs.{d.id}", d.label


def tr_strings(tr: Translation) -> dict[str, Tr]:
    """walk path -> German string of a translation model (null items and blank texts left
    out: they are missing)."""
    out = _tr_strings(tr)
    return {path: t for path, t in out.items() if t.text.strip()}


def _tr_strings(tr: Translation) -> dict[str, Tr]:
    out: dict[str, Tr] = {}
    for key in ("title", "dek"):
        if getattr(tr, key, None) is not None:
            out[key] = getattr(tr, key)
    for i, p in enumerate(getattr(tr, "intro", [])):
        if p is not None:
            out[f"intro.{i}"] = p
    for i, sec in enumerate(tr.sections):
        if sec.heading is not None:
            out[f"sections.{i}.heading"] = sec.heading
        for j, p in enumerate(sec.paragraphs):
            if p is not None:
                out[f"sections.{i}.paragraphs.{j}"] = p
        for k, v in (getattr(sec, "dimensions", None) or {}).items():
            out[f"sections.{i}.dimensions.{k}"] = v
    for rid, label in tr.data_refs.items():
        out[f"data_refs.{rid}"] = label
    return out


def translation_model(en_model: English) -> type[Translation]:
    if isinstance(en_model, Narrative):
        return NarrativeTr
    if isinstance(en_model, Organisation):
        return OrganisationTr
    return DocumentTr


def _set(doc: dict, path: str, text: str) -> None:
    """Set the string at a walk path of an English model's dump."""
    head, _, rest = path.partition(".")
    if head == "data_refs":
        next(d for d in doc["data_refs"] if d["id"] == rest)["label"] = text
        return
    node: Any = doc
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = text
    else:
        node[last] = text


def merge(en_model: English, tr: Translation | None) -> tuple[English, frozenset[str]]:
    """The English model with the German text and the German `literals`, and the walk paths
    that fell back to English (no German string). Facts, quotes, data-ref targets, roles,
    steps and ids stay the English file's."""
    english = dict(walk(en_model))
    if tr is None:
        return en_model, frozenset(english)
    german = {p: s.text for p, s in tr_strings(tr).items() if p in english}
    doc = en_model.model_dump()
    for path, text in german.items():
        _set(doc, path, text)
    doc["literals"] = list(tr.literals)
    return type(en_model).model_validate(doc), frozenset(english) - frozenset(german)


# --- files --------------------------------------------------------------------------------


def _read(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ContentError(f"{path}: {e}") from e


def english_model(en_path: Path) -> type[English]:
    """The English model of a content file, by its directory."""
    kind = Path(en_path).parent.name
    return {"narratives": Narrative, "organisations": Organisation}.get(kind, Explainer)


def load_english(path: Path) -> English:
    try:
        return english_model(path).model_validate(_read(path))
    except ValidationError as e:
        raise ContentError(f"{path}: {e}") from e


def load_translation(de_path: Path, en_model: English) -> Translation:
    """The translation file of `en_model`; ContentError naming the file when it is invalid."""
    try:
        return translation_model(en_model).model_validate(_read(de_path) or {})
    except ValidationError as e:
        raise ContentError(f"{de_path}: {e}") from e


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, s: str) -> yaml.Node:
    # folded only where it round-trips: one line, no edge or doubled whitespace
    plain = "\n" not in s and s == s.strip() and "  " not in s and "\t" not in s
    style = ">" if len(s) > FOLD_OVER and plain else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style=style)


_Dumper.add_representer(str, _str)


def dump(path: Path, doc: Any) -> None:
    """Write YAML with keys in their order and long strings folded."""
    text = yaml.dump(doc, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=FOLD_OVER)
    if yaml.safe_load(text) != doc:  # pragma: no cover - the representer keeps it lossless
        raise ValueError(f"{path}: YAML dump does not round-trip")
    Path(path).write_text(text, encoding="utf-8")


def _is_tr(node: Any) -> bool:
    return isinstance(node, dict) and "text" in node and set(node) <= {"text", "src"}


def _is_translated(node: Any) -> bool:
    return _is_tr(node) and isinstance(node["text"], str) and bool(node["text"].strip())


def _tr_nodes(doc: dict) -> Iterator[tuple[str, dict]]:
    """(walk path, `{text, src}` mapping) of a translation file's raw YAML."""
    for key in ("title", "dek"):
        if _is_tr(doc.get(key)):
            yield key, doc[key]
    for i, p in enumerate(doc.get("intro") or []):
        if _is_tr(p):
            yield f"intro.{i}", p
    for i, sec in enumerate(doc.get("sections") or []):
        if not isinstance(sec, dict):
            continue
        if _is_tr(sec.get("heading")):
            yield f"sections.{i}.heading", sec["heading"]
        for j, p in enumerate(sec.get("paragraphs") or []):
            if _is_tr(p):
                yield f"sections.{i}.paragraphs.{j}", p
        for k, v in (sec.get("dimensions") or {}).items():
            if _is_tr(v):
                yield f"sections.{i}.dimensions.{k}", v
    for rid, label in (doc.get("data_refs") or {}).items():
        if _is_tr(label):
            yield f"data_refs.{rid}", label


def stamp(de_path: Path, en_model: English) -> int:
    """Write `src` (the stamp of today's English) for every German string of the file that has
    an English twin; returns how many. Run by whoever translated, never as a blanket fix."""
    doc = _read(de_path)
    if not isinstance(doc, dict):
        raise ContentError(f"{de_path}: expected a mapping")
    english = dict(walk(en_model))
    n = 0
    for path, node in _tr_nodes(doc):
        if path in english and _is_translated(node):
            node["src"] = src_hash(english[path])
            n += 1
    dump(de_path, doc)
    return n


def skeleton(en_model: English, texts: dict[str, str], literals: list[str]) -> dict:
    """The raw YAML of a translation file for `en_model` holding `texts` (walk path -> German;
    a path left out is null in a list and absent elsewhere), unstamped."""

    def s(path: str) -> dict | None:
        return {"text": texts[path]} if path in texts else None

    doc: dict[str, Any] = {}
    if isinstance(en_model, Narrative):
        doc["city_id"] = en_model.city_id
    if isinstance(en_model, Organisation):
        doc["id"] = en_model.id
    for key in ("title", "dek"):
        if key in texts:
            doc[key] = s(key)
    if isinstance(en_model, Explainer):
        doc["intro"] = [s(f"intro.{i}") for i in range(len(en_model.intro))]
    sections = []
    for i, sec in enumerate(en_model.sections):
        out: dict[str, Any] = {}
        if f"sections.{i}.heading" in texts:
            out["heading"] = s(f"sections.{i}.heading")
        out["paragraphs"] = [s(f"sections.{i}.paragraphs.{j}") for j in range(len(sec.paragraphs))]
        dims = getattr(sec, "dimensions", None)
        if dims:
            out["dimensions"] = {
                k: s(f"sections.{i}.dimensions.{k}")
                for k in dims
                if f"sections.{i}.dimensions.{k}" in texts
            }
        sections.append(out)
    doc["sections"] = sections
    refs = {
        d.id: s(f"data_refs.{d.id}") for d in en_model.data_refs if f"data_refs.{d.id}" in texts
    }
    if refs:
        doc["data_refs"] = refs
    if literals:
        doc["literals"] = list(literals)
    return doc


def _view(node: Any) -> Any:
    """A translation file's raw YAML with each `{text, src}` shown as its text."""
    if _is_tr(node):
        return node["text"]
    if isinstance(node, list):
        return [_view(x) for x in node]
    if isinstance(node, dict):
        return {k: _view(v) for k, v in node.items()}
    return node


def _unview(new: Any, old: Any, wrap: bool) -> Any:
    """`new` (a `_view` value after an edit) back in the file's shape: a string keeps its
    mapping's `src`, and in a translation file a new string becomes `{text}`."""
    if isinstance(new, str) and (_is_tr(old) or (wrap and old is None)):
        return {**(old or {}), "text": new}
    if isinstance(new, list):
        olds = old if isinstance(old, list) else []
        return [_unview(x, olds[i] if i < len(olds) else None, wrap) for i, x in enumerate(new)]
    if isinstance(new, dict) and not _is_tr(new):
        olds = old if isinstance(old, dict) else {}
        return {k: _unview(v, olds.get(k), wrap) for k, v in new.items()}
    return new


def edit_path(file: Path, walk_path: str, fn: Callable[[Any], Any]) -> None:
    """Load a content YAML file, replace the value at `walk_path` (a dotted path of keys and
    list indices; an English `data_refs.<id>` names the reference's label) with `fn(value)`,
    and dump it. In a translation file `fn` sees and returns text, never `{text, src}`."""
    doc = _read(file)
    parts = walk_path.split(".")
    if parts[0] == "data_refs" and isinstance(doc.get("data_refs"), list) and len(parts) == 2:
        parts = [
            "data_refs",
            next(i for i, d in enumerate(doc["data_refs"]) if d["id"] == parts[1]),
        ]
        parts.append("label")
    node: Any = doc
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last: Any = int(parts[-1]) if isinstance(node, list) else parts[-1]
    old = node[last] if isinstance(node, list) or last in node else None
    node[last] = _unview(fn(_view(old)), old, wrap=Path(file).parent.name == DE)
    dump(file, doc)


# --- history ------------------------------------------------------------------------------

History = Callable[[Path], list[str]]


def git_history(path: Path) -> list[str]:
    """The committed texts of a file, newest first; [] outside git or without history."""
    path = Path(path).resolve()

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=path.parent, check=True, capture_output=True, text=True
        ).stdout

    try:
        shas = git("log", "--format=%H", "--", path.name).split()
        return [git("show", f"{sha}:./{path.name}") for sha in shas]
    except (OSError, subprocess.CalledProcessError):
        return []


def _english_at(doc: Any, walk_path: str) -> str | None:
    """The string at a walk path of a raw English file, None when it has none."""
    try:
        head, _, rest = walk_path.partition(".")
        if head == "data_refs":
            return next(d["label"] for d in doc["data_refs"] if d["id"] == rest)
        node: Any = doc
        for part in walk_path.split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
    except (KeyError, IndexError, TypeError, ValueError, StopIteration):
        return None
    return node if isinstance(node, str) else None


def old_english(en_text_versions: list[str], walk_path: str, src: str) -> str | None:
    """The English string a stale stamp was made from: the newest earlier version of the file
    whose string at `walk_path` has stamp `src`."""
    for text in en_text_versions:
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        value = _english_at(doc, walk_path)
        if value is not None and src_hash(value) == src:
            return value
    return None
