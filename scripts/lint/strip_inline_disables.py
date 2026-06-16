"""Remove inline pylint/noqa suppressions from Python sources (one-off maintenance)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_INLINE_PYLINT = re.compile(r"\s*#\s*pylint:\s*disable=[^\n#]*")
_INLINE_NOQA = re.compile(r"\s*#\s*noqa(?::[^\n#]*)?")
_SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules", "frontend", "typings"}


def _should_skip(path: Path) -> bool:
    return any(part in _SKIP_DIRS for part in path.parts)


def strip_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = _INLINE_PYLINT.sub("", original)
    updated = _INLINE_NOQA.sub("", updated)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    changed = 0
    for py_path in sorted(root.rglob("*.py")):
        if _should_skip(py_path):
            continue
        if strip_file(py_path):
            changed += 1
            print(py_path.relative_to(root))
    print(f"Updated {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
