"""Helpers the test modules share."""

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load_script(rel_path: str) -> ModuleType:
    """The module of a repository script that is no package module (`scripts/…`, `tools/…`),
    loaded from its path under the repository root and named after its file stem."""
    path = ROOT / rel_path
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
