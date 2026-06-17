"""Remove docstring literals wrongly placed after function/class bodies."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _is_docstring_expr(node: ast.stmt) -> bool:
    """Is docstring expr."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _remove_misplaced_docstrings(source: str) -> tuple[str, bool]:
    """Remove misplaced docstrings."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, False

    lines = source.splitlines(keepends=True)
    remove_lines: set[int] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if len(node.body) < 2:
            continue
        first = node.body[0]
        last = node.body[-1]
        if not _is_docstring_expr(last):
            continue
        if _is_docstring_expr(first):
            continue
        end_line = last.end_lineno or last.lineno
        for line_no in range(last.lineno, end_line + 1):
            remove_lines.add(line_no)

    if not remove_lines:
        return source, False

    kept = [line for index, line in enumerate(lines, start=1) if index not in remove_lines]
    return "".join(kept), True


def main() -> int:
    """Main."""
    root = Path(__file__).resolve().parents[2]
    dirs = [root / name for name in sys.argv[1:]] if len(sys.argv) > 1 else [
        root / "services",
        root / "routers",
        root / "agents",
        root / "clients",
        root / "config",
        root / "utils",
    ]
    changed = 0
    for directory in dirs:
        for path in sorted(directory.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            fixed, did_change = _remove_misplaced_docstrings(source)
            if did_change:
                path.write_text(fixed, encoding="utf-8")
                changed += 1
                print(path.relative_to(root))
    print(f"Cleaned {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
