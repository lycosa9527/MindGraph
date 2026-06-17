"""Move module docstrings that appear after imports to the top of the file."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _module_docstring_after_imports(source: str) -> tuple[str, bool] | None:
    """Module docstring after imports."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    lines = source.splitlines(keepends=True)
    doc_nodes: list[ast.Expr] = []
    first_import_line: int | None = None

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if first_import_line is None:
                first_import_line = node.lineno
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str) and first_import_line is not None:
                doc_nodes.append(node)
        elif first_import_line is not None:
            break

    if not doc_nodes or first_import_line is None:
        return None

    remove_lines: set[int] = set()
    doc_parts: list[str] = []
    for node in doc_nodes:
        start = node.lineno - 1
        end = node.end_lineno or node.lineno
        for line_no in range(start, end):
            remove_lines.add(line_no)
        doc_parts.append(
            str(node.value.value) if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) else ""
        )

    merged = "\n\n".join(part for part in doc_parts if part.strip())
    if not merged.strip():
        return None

    kept = [line for index, line in enumerate(lines) if index not in remove_lines]
    # Drop leading blank lines before first import
    while kept and kept[0].strip() == "":
        kept.pop(0)

    doc_block = f'"""{merged}"""\n\n'
    return doc_block + "".join(kept), True


def main() -> int:
    """Main."""
    root = Path(__file__).resolve().parents[2]
    targets = (
        [root / name for name in sys.argv[1:]]
        if len(sys.argv) > 1
        else [
            root / "services",
            root / "routers",
            root / "agents",
            root / "clients",
            root / "config",
            root / "utils",
        ]
    )
    changed = 0
    for directory in targets:
        if directory.is_file():
            paths = [directory]
        else:
            paths = sorted(directory.rglob("*.py"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            if source.startswith('"""') or source.startswith("'''"):
                continue
            result = _module_docstring_after_imports(source)
            if result is None:
                continue
            fixed, did_change = result
            if did_change:
                path.write_text(fixed, encoding="utf-8")
                changed += 1
                print(path.relative_to(root))
    print(f"Repositioned docstrings in {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
