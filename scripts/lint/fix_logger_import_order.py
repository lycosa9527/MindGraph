"""Move ``logger = logging.getLogger(__name__)`` below all module imports."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_LOGGER_RE = re.compile(r"^(\s*)logger\s*=\s*logging\.getLogger\(__name__\)\s*$")


def fix_file(path: Path) -> bool:
    """Fix file."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    logger_indices = [
        index for index, line in enumerate(lines) if _LOGGER_RE.match(line.rstrip("\n"))
    ]
    if not logger_indices:
        return False

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    import_end = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_end = max(import_end, node.end_lineno or node.lineno)

    if import_end == 0:
        return False

    moved = False
    for logger_index in reversed(logger_indices):
        logger_line_no = logger_index + 1
        if logger_line_no >= import_end:
            continue
        # Check for imports after logger line
        has_later_import = any(
            isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno > logger_line_no
            for node in tree.body
        )
        if not has_later_import:
            continue
        logger_line = lines.pop(logger_index)
        # Remove following blank line if present
        if logger_index < len(lines) and lines[logger_index].strip() == "":
            lines.pop(logger_index)
        insert_at = import_end - 1
        if insert_at < len(lines) and lines[insert_at].strip() != "":
            logger_line = logger_line if logger_line.endswith("\n") else logger_line + "\n"
            lines.insert(insert_at, "\n" + logger_line)
        else:
            lines.insert(insert_at, logger_line)
        moved = True
        break

    if not moved:
        return False
    path.write_text("".join(lines), encoding="utf-8")
    return True


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
            if fix_file(path):
                changed += 1
                print(path.relative_to(root))
    print(f"Fixed logger import order in {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
