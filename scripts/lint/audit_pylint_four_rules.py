"""Audit counts for the four pylint rules targeted by the hardening sweep."""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path

RULES = (
    "global-statement",
    "import-outside-toplevel",
    "protected-access",
    "broad-except",
)

_SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules", "frontend", "typings"}
_SKIP_PARTS = {"alembic/versions"}
_SKIP_FILES = {
    "services/infrastructure/process/fatal_process_exit.py",
}


def _should_skip(path: Path, root: Path) -> bool:
    """Should skip."""
    if any(part in _SKIP_DIRS for part in path.parts):
        return True
    rel = path.relative_to(root).as_posix()
    if rel in _SKIP_FILES:
        return True
    return any(rel.startswith(part) for part in _SKIP_PARTS)


def _attribute_root_name(node: ast.Attribute) -> str | None:
    """Attribute root name."""
    current: ast.expr = node.value
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


class _RuleVisitor(ast.NodeVisitor):
    """_RuleVisitor helper."""

    def __init__(self) -> None:
        """init  ."""
        self.globals_count = 0
        self.function_imports = 0
        self.broad_except = 0
        self.protected_access = 0
        self._in_function = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit functiondef."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit asyncfunctiondef."""
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Visit function."""
        self._in_function += 1
        self.generic_visit(node)
        self._in_function -= 1

    def visit_Global(self, node: ast.Global) -> None:
        """Visit global."""
        self.globals_count += len(node.names)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import."""
        if self._in_function:
            self.function_imports += 1
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit importfrom."""
        if self._in_function:
            self.function_imports += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit excepthandler."""
        if node.type is None:
            self.broad_except += 1
        elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
            self.broad_except += 1
        elif isinstance(node.type, ast.Tuple):
            names = [elt.id for elt in node.type.elts if isinstance(elt, ast.Name)]
            if "Exception" in names and len(names) == 1:
                self.broad_except += 1
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute."""
        if isinstance(node.attr, str) and node.attr.startswith("_"):
            root = _attribute_root_name(node)
            if root in {"self", "cls"}:
                self.generic_visit(node)
                return
            if isinstance(node.value, ast.Name) and node.value.id in {
                "os",
                "sys",
                "request",
                "record",
            }:
                self.protected_access += 1
            elif isinstance(node.value, ast.Attribute) and root not in {"self", "cls"}:
                self.protected_access += 1
        self.generic_visit(node)


def audit_file(path: Path) -> dict[str, int]:
    """Audit file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return {}
    visitor = _RuleVisitor()
    visitor.visit(tree)
    return {
        "global-statement": visitor.globals_count,
        "import-outside-toplevel": visitor.function_imports,
        "protected-access": visitor.protected_access,
        "broad-except": visitor.broad_except,
    }


def main() -> int:
    """Main."""
    parser = argparse.ArgumentParser(description="Audit four-rule pylint counts (AST approximation)")
    parser.add_argument(
        "--fail",
        action="store_true",
        help="Exit 1 if any rule has violations (for CI gates)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    totals: dict[str, int] = defaultdict(int)
    by_dir: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for py_path in sorted(root.rglob("*.py")):
        if _should_skip(py_path, root):
            continue
        counts = audit_file(py_path)
        if not counts:
            continue
        top = py_path.relative_to(root).parts[0] if py_path.relative_to(root).parts else "."
        for rule, count in counts.items():
            if count:
                totals[rule] += count
                by_dir[top][rule] += count

    print("Pylint four-rule audit (AST approximation)")
    print("=" * 50)
    for rule in RULES:
        print(f"  {rule}: {totals[rule]}")
    print()
    print("By top-level directory:")
    for directory in sorted(by_dir):
        parts = [f"{rule}={by_dir[directory][rule]}" for rule in RULES if by_dir[directory][rule]]
        if parts:
            print(f"  {directory}: {', '.join(parts)}")
    if args.fail and any(totals[rule] for rule in RULES):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
