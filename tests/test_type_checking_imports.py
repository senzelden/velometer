"""Names imported only under TYPE_CHECKING must be quoted in annotations.

Python 3.12/3.13 evaluate annotations eagerly (3.14 does not), so an unquoted use raises
NameError on import there. The check is on the source, so it fails on any interpreter.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "velometer"


def _unquoted_uses(tree: ast.Module) -> list[tuple[int, str]]:
    guarded: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.If) and ast.unparse(node.test) in (
            "TYPE_CHECKING",
            "typing.TYPE_CHECKING",
        ):
            for imp in ast.walk(node):
                if isinstance(imp, ast.ImportFrom | ast.Import):
                    guarded |= {(a.asname or a.name).split(".")[0] for a in imp.names}
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            anns = [a.annotation for a in node.args.posonlyargs + node.args.args]
            anns += [a.annotation for a in node.args.kwonlyargs]
            anns += [node.args.vararg and node.args.vararg.annotation]
            anns += [node.args.kwarg and node.args.kwarg.annotation, node.returns]
        elif isinstance(node, ast.AnnAssign):
            anns = [node.annotation]
        else:
            continue
        for ann in anns:
            if ann is None:
                continue
            for n in ast.walk(ann):  # a quoted annotation is an ast.Constant: not walked into
                if isinstance(n, ast.Name) and n.id in guarded:
                    bad.append((n.lineno, n.id))
    return bad


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_type_checking_names_are_quoted_in_annotations(path):
    source = path.read_text()
    if "from __future__ import annotations" in source:
        return
    assert _unquoted_uses(ast.parse(source)) == []
