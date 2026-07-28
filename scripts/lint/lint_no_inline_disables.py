"""Fail CI when inline lint suppressions appear outside allowed paths."""

from __future__ import annotations

import re
import subprocess
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


def _tracked_python_files(root: Path) -> list[Path]:
    """Return git-tracked ``*.py`` paths so gitignored trees (e.g. esp32/) match CI."""
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", "*.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(completed.stderr.strip() or "git ls-files failed", file=sys.stderr)
        return []
    paths: list[Path] = []
    for line in completed.stdout.splitlines():
        rel = line.strip()
        if not rel:
            continue
        paths.append(root / rel)
    return paths


def main() -> int:
    """Main."""
    root = Path(__file__).resolve().parents[2]
    violations: list[str] = []
    for py_path in _tracked_python_files(root):
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
