"""Evaluator for classifier rule match expressions (spec §4, classify.py grammar)."""

from collections.abc import Mapping
from typing import Any

from velometer.pipeline.tags import parts

_BOOL = {True: "yes", False: "no"}


def _norm(value: Any) -> str:
    # PyYAML (YAML 1.1) turns `yes`/`no` into booleans; OSM values are strings.
    if isinstance(value, bool):
        return _BOOL[value]
    return str(value)


def _check(parts: set[str], cond: Any, lists: Mapping[str, list[str]]) -> bool:
    if isinstance(cond, dict):
        if "absent" in cond:
            return not parts if cond["absent"] else bool(parts)
        if "not_in" in cond:
            return not parts & {_norm(v) for v in cond["not_in"]}
        if "in_list" in cond:
            return bool(parts & {_norm(v) for v in lists[cond["in_list"]]})
        raise ValueError(f"unknown condition {cond!r}")
    allowed = {_norm(v) for v in cond} if isinstance(cond, list) else {_norm(cond)}
    return bool(parts & allowed)


def matches(expr: dict, tags: Mapping[str, str], lists: Mapping[str, list[str]]) -> bool:
    """True if every entry of `expr` holds. Keys are `all`/`any`/`not` or tag keys."""
    for key, cond in expr.items():
        if key == "all":
            ok = all(matches(e, tags, lists) for e in cond)
        elif key == "any":
            ok = any(matches(e, tags, lists) for e in cond)
        elif key == "not":
            ok = not matches(cond, tags, lists)
        else:
            ok = _check(set(parts(tags.get(key))), cond, lists)
        if not ok:
            return False
    return True


def validate_expr(expr: dict, lists: Mapping[str, list[str]]) -> None:
    """Raise ValueError if `expr` uses an unknown operator, condition or value list."""
    if not isinstance(expr, dict) or not expr:
        raise ValueError(f"match expression must be a non-empty mapping, got {expr!r}")
    for key, cond in expr.items():
        if key in ("all", "any"):
            if not isinstance(cond, list) or not cond:
                raise ValueError(f"{key} needs a non-empty list")
            for e in cond:
                validate_expr(e, lists)
        elif key == "not":
            validate_expr(cond, lists)
        elif isinstance(cond, dict):
            if set(cond) not in ({"absent"}, {"not_in"}, {"in_list"}):
                raise ValueError(f"unknown condition {cond!r} for key {key!r}")
            if "absent" in cond and not isinstance(cond["absent"], bool):
                raise ValueError(f"absent must be a bool for key {key!r}, got {cond['absent']!r}")
            if "not_in" in cond and (not isinstance(cond["not_in"], list) or not cond["not_in"]):
                raise ValueError(
                    f"not_in must be a non-empty list for key {key!r}, got {cond['not_in']!r}"
                )
            if "in_list" in cond:
                if not isinstance(cond["in_list"], str):
                    raise ValueError(f"in_list must be a str for key {key!r}")
                if cond["in_list"] not in lists:
                    raise ValueError(f"unknown value list {cond['in_list']!r}")
        elif not isinstance(cond, (str, bool, int, float, list)):
            raise ValueError(f"unsupported condition {cond!r} for key {key!r}")
