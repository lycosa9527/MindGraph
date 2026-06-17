#!/usr/bin/env python3
"""Flag bare AsyncSessionLocal() / SyncSessionLocal() without rls_async_session nearby."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"scripts", "alembic", "tests", ".git", "node_modules", "frontend"}
ALLOW_MARKERS = (
    "rls_async_session",
    "rls_sync_session",
    "user_rls_session",
    "actor_rls_session",
    "system_rls_session",
    "panel_superadmin_rls_session",
    "set_rls_context",
    "apply_rls_context",
    "system_bootstrap",
    "register_rls_listeners",
)

PATTERN = re.compile(r"\b(AsyncSessionLocal|SyncSessionLocal)\s*\(")


def _should_scan(path: Path) -> bool:
    """Should scan."""
    parts = path.relative_to(ROOT).parts
    if parts[0] in SKIP_DIRS:
        return False
    if path.name == "rls_context.py":
        return False
    return path.suffix == ".py"


def main() -> int:
    """Main."""
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
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
