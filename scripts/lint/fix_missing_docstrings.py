"""Add minimal docstrings to functions and classes that lack them."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _docstring_for_name(name: str, *, is_class: bool = False) -> str:
    if is_class:
        return f'"""{name} helper."""'
    if name.startswith("test_"):
        rest = name[5:].replace("_", " ")
        return f'"""Test {rest}."""'
    if name.startswith("_"):
        readable = name[1:].replace("_", " ")
        return f'"""{readable.capitalize()}."""'
    readable = name.replace("_", " ")
    return f'"""{readable.capitalize()}."""'


def _has_docstring(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return True
    if not node.body:
        return False
    return isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)


def _body_indent(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    def_line = lines[node.lineno - 1]
    base = def_line[: len(def_line) - len(def_line.lstrip())]
    return f"{base}    "


def _insert_line(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    if not node.body:
        return node.lineno + 1
    return node.body[0].lineno


def _is_module_or_class_member(node: ast.AST, parent_map: dict[ast.AST, ast.AST]) -> bool:
    parent = parent_map.get(node)
    return isinstance(parent, (ast.Module, ast.ClassDef))


def fix_file(path: Path) -> bool:
    """Add missing docstrings in one file."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return False
    parent_map: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    lines = source.splitlines(keepends=True)
    targets: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if not _is_module_or_class_member(node, parent_map):
            continue
        if _has_docstring(node):
            continue
        insert_at = _insert_line(node)
        indent = _body_indent(lines, node)
        doc = _docstring_for_name(node.name, is_class=isinstance(node, ast.ClassDef))
        targets.append((insert_at, f"{indent}{doc}\n"))

    if not targets:
        return False
    for insert_at, line in sorted(targets, key=lambda item: item[0], reverse=True):
        lines.insert(insert_at - 1, line)
    path.write_text("".join(lines), encoding="utf-8")
    return True


def main() -> int:
    """Run docstring insertion across target directories."""
    root = Path(__file__).resolve().parents[2]
    dirs = (
        [root / name for name in sys.argv[1:]]
        if len(sys.argv) > 1
        else [
            root / "scripts",
            root / "tests",
            root / "loadtests",
            root / "tasks",
        ]
    )
    changed = 0
    for directory in dirs:
        for path in sorted(directory.rglob("*.py")):
            if path.name == "fix_missing_docstrings.py":
                continue
            if fix_file(path):
                changed += 1
                print(path.relative_to(root))
    print(f"Updated {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
