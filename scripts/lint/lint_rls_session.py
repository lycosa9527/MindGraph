#!/usr/bin/env python3
"""Flag bare AsyncSessionLocal() / SyncSessionLocal() / open_async_session() without RLS helpers nearby."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"scripts", "alembic", "tests", ".git", "node_modules", "frontend", "__pycache__", ".venv", "venv"}
ALLOW_MARKERS = (
    "rls_async_session",
    "rls_sync_session",
    "user_rls_session",
    "actor_rls_session",
    "system_rls_session",
    "panel_superadmin_rls_session",
    "set_rls_context",
    "apply_rls_context",
    "bind_session_rls_context",
    "system_bootstrap",
    "register_rls_listeners",
    "get_async_db",
    "get_async_db_with_request_rls",
)

PATTERN = re.compile(r"\b(AsyncSessionLocal|SyncSessionLocal|open_async_session)\s*\(")
# Factory / dependency wiring definitions themselves are allowed.
ALLOW_PATH_SUFFIXES = {
    Path("config") / "db_sessions.py",
    Path("utils") / "db" / "rls_context.py",
    Path("config") / "database.py",
}


def _iter_python_files() -> list[Path]:
    """Walk the tree without descending into skipped directories."""
    files: list[Path] = []
    stack = [ROOT]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    continue
                stack.append(entry)
                continue
            if entry.suffix == ".py":
                files.append(entry)
    return files


def _should_scan(path: Path) -> bool:
    """Should scan."""
    rel = path.relative_to(ROOT)
    if rel in ALLOW_PATH_SUFFIXES:
        return False
    return True


def main() -> int:
    """Main."""
    violations: list[str] = []
    for path in _iter_python_files():
        if not _should_scan(path):
            continue
        text = path.read_text(encoding="utf-8")
        for match in PATTERN.finditer(text):
            start = max(0, match.start() - 400)
            window = text[start : match.start() + 80]
            if any(marker in window for marker in ALLOW_MARKERS):
                continue
            line = text[: match.start()].count("\n") + 1
            rel = path.relative_to(ROOT)
            violations.append(f"{rel}:{line}: bare {match.group(1)}()")
    if violations:
        print("RLS session lint violations (use rls_async_session / set_rls_context):")
        for item in sorted(violations):
            print(f"  {item}")
        return 1
    print("RLS session lint: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
