#!/usr/bin/env python
"""
CI guard: forbid sync SCH kwargs on redis.asyncio client construction.
======================================================================

``redis_connection_options()`` sets ``maint_notifications_config``, which
redis-py 8.0.0 accepts on sync connections but not on async ones.  Any module
that imports ``redis.asyncio`` and passes ``redis_connection_options()`` to
``from_url`` will crash on the first command.

Policy
------
* ``services/redis/redis_async_client.py`` must import
  ``redis_async_connection_options``, not ``redis_connection_options``.
* No production module may call ``redis_connection_options()`` in a file that
  also references ``redis.asyncio`` (tests and this lint script are excluded).

Usage::

    python scripts/lint/lint_redis_connection_options.py
"""

from __future__ import annotations

import sys
from pathlib import Path

EXCLUDED_PARTS = {
    "tests",
    "test",
    "scripts",
    "migrations",
    "alembic",
    "node_modules",
    "frontend",
    "__pycache__",
    "venv",
    ".venv",
}

ASYNC_CLIENT_MODULE = "services/redis/redis_async_client.py"
CONNECTION_OPTIONS_MODULE = "services/redis/redis_connection_options.py"


def _normalise(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _iter_python_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in sorted(repo_root.rglob("*.py")):
        if EXCLUDED_PARTS & set(candidate.parts):
            continue
        files.append(candidate)
    return files


def _scan_file(path: Path, repo_root: Path) -> list[str]:
    rel = _normalise(path, repo_root)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    violations: list[str] = []
    uses_asyncio_redis = "redis.asyncio" in text
    uses_sync_options = "redis_connection_options()" in text
    uses_async_options = "redis_async_connection_options()" in text

    if rel in {ASYNC_CLIENT_MODULE, CONNECTION_OPTIONS_MODULE}:
        if rel == ASYNC_CLIENT_MODULE and "redis_connection_options" in text and not uses_async_options:
            violations.append(
                f"{rel}: async client must use redis_async_connection_options(), "
                "not redis_connection_options()",
            )
        return violations

    if uses_asyncio_redis and uses_sync_options:
        violations.append(
            f"{rel}: redis.asyncio module must not call redis_connection_options(); "
            "use redis_async_connection_options() instead",
        )
    return violations


def main() -> int:
    """Scan the repo and fail when sync SCH kwargs are used on async clients."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    violations: list[str] = []
    for file_path in _iter_python_files(repo_root):
        violations.extend(_scan_file(file_path, repo_root))

    if violations:
        formatted = "\n  ".join(violations)
        print(
            "[lint_redis_connection_options] sync SCH kwargs on async Redis client:\n  "
            + formatted,
            file=sys.stderr,
        )
        return 1

    print("[lint_redis_connection_options] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
