"""Read content YAML into validated models; every failure is a ContentError naming the file."""

from pathlib import Path
from typing import Any, Literal, overload

import yaml
from pydantic import ValidationError

from velometer.content.models import (
    ContentError,
    Explainer,
    Narrative,
    Organisation,
    OrgMapping,
    Source,
)
from velometer.content.translate import load_translation, merge, twin_path

Fallback = dict[str, frozenset[str]]


def _read(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ContentError(f"{path}: {e}") from e


def load_sources(dir: Path) -> dict[str, Source]:
    """Merge every `*.yaml` (top-level `sources:` list) of the registry directory by id."""
    out: dict[str, Source] = {}
    for path in sorted(dir.glob("*.yaml")):
        doc = _read(path)
        if (
            not isinstance(doc, dict)
            or set(doc) != {"sources"}
            or not isinstance(doc["sources"], list)
        ):
            raise ContentError(f"{path}: expected a mapping with a single `sources:` list")
        for raw in doc["sources"]:
            try:
                src = Source.model_validate(raw)
            except ValidationError as e:
                raise ContentError(f"{path}: {e}") from e
            if src.id in out:
                raise ContentError(f"{path}: duplicate source id {src.id}")
            out[src.id] = src
    return out


def _german(
    models: dict[str, Any], dir: Path, errors: dict[str, str] | None
) -> tuple[dict[str, Any], Fallback]:
    """The English models of `dir` merged with their translations in `dir/de/`, and per file
    stem the walk paths still in English. A missing translation leaves the whole file in
    English; a broken one too, its message recorded under `de/<stem>` (raised without
    `errors`)."""
    out: dict[str, Any] = {}
    fallback: Fallback = {}
    for stem, model in models.items():
        de_path = twin_path(Path(dir) / f"{stem}.yaml")
        out[stem], fallback[stem] = merge(model, None)
        if not de_path.is_file():
            continue
        try:
            tr = load_translation(de_path, model)
            try:
                out[stem], fallback[stem] = merge(model, tr)
            except ValueError as e:  # pydantic's ValidationError: a rule the merged text breaks
                raise ContentError(f"{de_path}: {e}") from e
        except ContentError as e:
            if errors is None:
                raise
            errors[f"de/{stem}"] = str(e)
    return out, fallback


@overload
def load_narratives(
    dir: Path, errors: dict[str, str] | None = None, lang: Literal["en"] = "en"
) -> dict[str, Narrative]: ...
@overload
def load_narratives(
    dir: Path, errors: dict[str, str] | None, lang: Literal["de"]
) -> tuple[dict[str, Narrative], Fallback]: ...
@overload
def load_narratives(
    dir: Path, errors: dict[str, str] | None = None, *, lang: Literal["de"]
) -> tuple[dict[str, Narrative], Fallback]: ...
def load_narratives(
    dir: Path, errors: dict[str, str] | None = None, lang: Literal["en", "de"] = "en"
) -> dict[str, Narrative] | tuple[dict[str, Narrative], Fallback]:
    """Load `<city_id>.yaml` files; the file stem must equal the narrative's `city_id`.

    Without `errors` the first bad file raises. With it, each bad file's message is recorded
    under its stem and the file is skipped, so one broken narrative leaves the others readable.
    With `lang="de"`: (narratives in German, fallback), `fallback` the walk paths per stem that
    are still English (`_german`).
    """
    out: dict[str, Narrative] = {}
    for path in sorted(dir.glob("*.yaml")):
        try:
            out[path.stem] = _narrative(path)
        except ContentError as e:
            if errors is None:
                raise
            errors[path.stem] = str(e)
    return _german(out, dir, errors) if lang == "de" else out


def _narrative(path: Path) -> Narrative:
    try:
        narrative = Narrative.model_validate(_read(path))
    except ValidationError as e:
        raise ContentError(f"{path}: {e}") from e
    if narrative.city_id != path.stem:
        raise ContentError(
            f"{path}: file stem must equal city_id, but city_id is {narrative.city_id}"
        )
    return narrative


@overload
def load_document(path: Path, lang: Literal["en"] = "en") -> Explainer | None: ...
@overload
def load_document(path: Path, lang: Literal["de"]) -> tuple[Explainer | None, Fallback]: ...
def load_document(
    path: Path, lang: Literal["en", "de"] = "en"
) -> Explainer | None | tuple[Explainer | None, Fallback]:
    """An explainer-shaped page (the explainer, `plans/berlin.yaml`, `counters.yaml`), or None
    when the file does not exist. With `lang="de"`: (the page in German or None, fallback),
    `fallback` keyed by the file stem as in `load_narratives`; a broken translation raises."""
    doc = None
    if path.exists():
        try:
            doc = Explainer.model_validate(_read(path))
        except ValidationError as e:
            raise ContentError(f"{path}: {e}") from e
    if lang != "de":
        return doc
    if doc is None:
        return None, {}
    merged, fallback = _german({path.stem: doc}, path.parent, None)
    return merged[path.stem], fallback


load_explainer = load_document


@overload
def load_organisations(
    dir: Path, errors: dict[str, str] | None = None, lang: Literal["en"] = "en"
) -> dict[str, Organisation]: ...
@overload
def load_organisations(
    dir: Path, errors: dict[str, str] | None, lang: Literal["de"]
) -> tuple[dict[str, Organisation], Fallback]: ...
@overload
def load_organisations(
    dir: Path, errors: dict[str, str] | None = None, *, lang: Literal["de"]
) -> tuple[dict[str, Organisation], Fallback]: ...
def load_organisations(
    dir: Path, errors: dict[str, str] | None = None, lang: Literal["en", "de"] = "en"
) -> dict[str, Organisation] | tuple[dict[str, Organisation], Fallback]:
    """Load `<id>.yaml` profiles; the file stem must equal the organisation's `id`. `errors` and
    `lang` as in `load_narratives`."""
    out: dict[str, Organisation] = {}
    for path in sorted(Path(dir).glob("*.yaml")):
        try:
            out[path.stem] = _organisation(path)
        except ContentError as e:
            if errors is None:
                raise
            errors[path.stem] = str(e)
    return _german(out, Path(dir), errors) if lang == "de" else out


def _organisation(path: Path) -> Organisation:
    try:
        org = Organisation.model_validate(_read(path))
    except ValidationError as e:
        raise ContentError(f"{path}: {e}") from e
    if org.id != path.stem:
        raise ContentError(f"{path}: file stem must equal id, but id is {org.id}")
    return org


def load_organisation_map(path: Path) -> list[OrgMapping]:
    """`config/organisations.yaml`: a list of {city, source, organisation}."""
    doc = _read(path)
    if not isinstance(doc, list):
        raise ContentError(f"{path}: expected a list of {{city, source, organisation}}")
    try:
        return [OrgMapping.model_validate(m) for m in doc]
    except ValidationError as e:
        raise ContentError(f"{path}: {e}") from e
