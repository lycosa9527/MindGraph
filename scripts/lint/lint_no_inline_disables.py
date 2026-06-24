"""Fail CI when inline lint suppressions appear outside allowed paths."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_INLINE_SUPPRESSION = re.compile(
    r"#\s*(pylint:\s*disable=|noqa\b|type:\s*ignore\b)",
    re.IGNORECASE,
)


def _is_allowed(path: Path, _root: Path) -> bool:
    """Is allowed."""
    parts = set(path.parts)
    if "typings" in parts:
        return True
    if "alembic" in parts and "versions" in parts:
        return True
    return False


def main() -> int:
    """Main."""
    root = Path(__file__).resolve().parents[2]
    violations: list[str] = []
    for py_path in sorted(root.rglob("*.py")):
        if any(part in py_path.parts for part in ("__pycache__", ".venv", "venv", "node_modules", "frontend")):
            continue
        if _is_allowed(py_path, root):
            continue
        for line_no, line in enumerate(py_path.read_text(encoding="utf-8").splitlines(), start=1):
            if _INLINE_SUPPRESSION.search(line):
                violations.append(f"{py_path.relative_to(root)}:{line_no}:{line.strip()}")
    if violations:
        print("Inline lint suppressions are forbidden (use proper fixes or pyproject policy):", file=sys.stderr)
        for item in violations:
            print(f"  {item}", file=sys.stderr)
        return 1
    print("No forbidden inline suppressions found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
