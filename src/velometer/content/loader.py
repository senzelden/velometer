"""Read content YAML into validated models; every failure is a ContentError naming the file."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from velometer.content.models import ContentError, Explainer, Narrative, Source


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


def load_narratives(dir: Path) -> dict[str, Narrative]:
    """Load `<city_id>.yaml` files; the file stem must equal the narrative's `city_id`."""
    out: dict[str, Narrative] = {}
    for path in sorted(dir.glob("*.yaml")):
        try:
            narrative = Narrative.model_validate(_read(path))
        except ValidationError as e:
            raise ContentError(f"{path}: {e}") from e
        if narrative.city_id != path.stem:
            raise ContentError(
                f"{path}: file stem must equal city_id, but city_id is {narrative.city_id}"
            )
        out[narrative.city_id] = narrative
    return out


def load_explainer(path: Path) -> Explainer | None:
    """The explainer page, or None when the file does not exist."""
    if not path.exists():
        return None
    try:
        return Explainer.model_validate(_read(path))
    except ValidationError as e:
        raise ContentError(f"{path}: {e}") from e
