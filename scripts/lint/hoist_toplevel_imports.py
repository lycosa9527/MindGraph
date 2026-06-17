"""Move imports from function bodies to module top level."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _import_source(source: str, node: ast.Import | ast.ImportFrom) -> str:
    """Import source."""
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise ValueError(f"Could not extract import source at line {node.lineno}")
    return segment.strip()


def _in_function(node: ast.AST, parent_map: dict[ast.AST, ast.AST]) -> bool:
    """In function."""
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return True
        current = parent_map.get(current)
    return False


def _last_import_line(tree: ast.Module) -> int:
    """Last import line."""
    last = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = max(last, node.end_lineno or node.lineno)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            break
    return last


def hoist_file(path: Path) -> bool:
    """Hoist file."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return False

    parent_map: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    to_hoist: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if not _in_function(node, parent_map):
            continue
        text = _import_source(source, node)
        if text in seen:
            to_hoist.append((node.lineno, node.end_lineno or node.lineno, text))
            continue
        seen.add(text)
        to_hoist.append((node.lineno, node.end_lineno or node.lineno, text))

    if not to_hoist:
        return False

    lines = source.splitlines(keepends=True)
    unique_imports: list[str] = []
    for _, _, text in sorted(to_hoist, key=lambda item: item[0]):
        if text not in unique_imports:
            unique_imports.append(text)

    insert_after = _last_import_line(tree)
    import_block = "".join(f"{line}\n" for line in unique_imports)
    if insert_after:
        lines.insert(insert_after, f"{import_block}\n")
    else:
        lines.insert(0, f"{import_block}\n")

    # Re-parse to get updated line numbers for removals
    updated = "".join(lines)
    tree2 = ast.parse(updated, filename=str(path))
    parent_map2: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree2):
        for child in ast.iter_child_nodes(parent):
            parent_map2[child] = parent

    removals: list[tuple[int, int]] = []
    for node in ast.walk(tree2):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if not _in_function(node, parent_map2):
            continue
        start = node.lineno
        end = node.end_lineno or node.lineno
        removals.append((start, end))

    lines2 = updated.splitlines(keepends=True)
    for start, end in sorted(removals, key=lambda item: item[0], reverse=True):
        del lines2[start - 1 : end]
        if start - 1 < len(lines2) and lines2[start - 1].strip() == "":
            del lines2[start - 1]

    path.write_text("".join(lines2), encoding="utf-8")
    return True


def main() -> int:
    """Main."""
    root = Path(__file__).resolve().parents[2]
    targets = [root / name for name in sys.argv[1:]] if len(sys.argv) > 1 else [
        root / "scripts",
        root / "tests",
        root / "loadtests",
        root / "tasks",
    ]
    changed = 0
    for base in targets:
        if base.is_file():
            paths = [base]
        else:
            paths = sorted(base.rglob("*.py"))
        for path in paths:
            if path.name in {"hoist_toplevel_imports.py", "fix_missing_docstrings.py"}:
                continue
            if hoist_file(path):
                changed += 1
                print(path.relative_to(root))
    print(f"Hoisted imports in {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
