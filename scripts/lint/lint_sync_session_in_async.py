#!/usr/bin/env python
"""
CI / pre-commit guard: forbid SyncSessionLocal() inside async def bodies.
=========================================================================

Rationale
---------
Phase 6 of the database tuning work moved every PostgreSQL session reachable
from the asyncio event loop onto the async engine.  Constructing a
``SyncSessionLocal()`` inside an ``async def`` block re-introduces a blocking
psycopg2 connection on the event loop thread, which is exactly the latency
cliff Phase 6 set out to eliminate.

Policy
------
Inside any ``async def`` body the following construct is forbidden:

* ``SyncSessionLocal(...)`` calls (returns a synchronous SQLAlchemy ``Session``).

The guard performs a static AST scan and supports a baseline file
(:data:`BASELINE_FILE_NAME`) so legacy code paths can be grandfathered while
they are migrated module by module.  Pull requests may not introduce *new*
violations.

Usage::

    python scripts/lint/lint_sync_session_in_async.py
    python scripts/lint/lint_sync_session_in_async.py --update-baseline

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple


BASELINE_FILE_NAME = "sync_session_in_async_baseline.txt"

DEFAULT_SCAN_PATHS = (
    "routers",
    "services",
    "clients",
    "utils",
    "models",
    "config",
)

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


class _Finding:
    __slots__ = ("path", "lineno", "snippet")

    def __init__(self, path: str, lineno: int, snippet: str) -> None:
        self.path = path
        self.lineno = lineno
        self.snippet = snippet


def _iter_python_files(root: Path) -> Iterable[Path]:
    for candidate in sorted(root.rglob("*.py")):
        parts = set(candidate.parts)
        if parts & EXCLUDED_PARTS:
            continue
        yield candidate


def _normalise_rel(rel_path: str) -> str:
    return rel_path.replace("\\", "/")


def _format_entry(rel_path: str, snippet: str) -> str:
    return f"{_normalise_rel(rel_path)} :: {snippet}"


def _load_baseline(baseline_path: Path) -> Set[str]:
    if not baseline_path.exists():
        return set()
    return {
        line.strip()
        for line in baseline_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _is_sync_session_local(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name) and func.id == "SyncSessionLocal":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "SyncSessionLocal":
        return True
    return False


class _AsyncBodyScanner(ast.NodeVisitor):
    """Walks an AST and reports violations only inside ``async def`` bodies."""

    def __init__(self, source_lines: List[str], path: str) -> None:
        self._lines = source_lines
        self._path = path
        self._async_depth = 0
        self.findings: List[_Finding] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._async_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self._async_depth -= 1

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._async_depth > 0 and _is_sync_session_local(node):
            line_text = (
                self._lines[node.lineno - 1].strip() if node.lineno - 1 < len(self._lines) else "SyncSessionLocal(...)"
            )
            self.findings.append(_Finding(self._path, node.lineno, line_text))
        self.generic_visit(node)


def _scan_file(path: Path, repo_root: Path) -> List[_Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    try:
        rel_path = str(path.relative_to(repo_root))
    except ValueError:
        rel_path = str(path)
    scanner = _AsyncBodyScanner(text.splitlines(), rel_path)
    scanner.visit(tree)
    return scanner.findings


def _collect_findings(repo_root: Path, scan_paths: List[str]) -> List[_Finding]:
    findings: List[_Finding] = []
    for raw in scan_paths:
        target = (repo_root / raw).resolve()
        if not target.exists():
            print(f"[lint_sync_session_in_async] skip missing path: {target}", file=sys.stderr)
            continue
        files = [target] if target.is_file() else list(_iter_python_files(target))
        for file_path in files:
            findings.extend(_scan_file(file_path, repo_root))
    return findings


def _write_baseline(baseline_path: Path, findings: List[_Finding]) -> None:
    entries = sorted({_format_entry(f.path, f.snippet) for f in findings})
    header = (
        "# Baseline of SyncSessionLocal() usage inside async def bodies.\n"
        "# One entry per line: <relative/path> :: <line snippet>.\n"
        "# Remove a line when you migrate the call to AsyncSessionLocal/get_db.\n"
        "# Regenerate with: python scripts/lint/lint_sync_session_in_async.py --update-baseline\n"
        "\n"
    )
    baseline_path.write_text(header + "\n".join(entries) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[1])
    parser.add_argument(
        "paths",
        nargs="*",
        default=list(DEFAULT_SCAN_PATHS),
        help="Paths to scan (default: routers, services, clients, utils, models, config).",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite the baseline file from current findings (use with care).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent.parent
    baseline_path = Path(__file__).resolve().parent / BASELINE_FILE_NAME
    findings = _collect_findings(repo_root, args.paths)

    if args.update_baseline:
        _write_baseline(baseline_path, findings)
        print(f"[lint_sync_session_in_async] baseline written to {baseline_path}")
        return 0

    baseline = _load_baseline(baseline_path)
    new_violations: List[Tuple[str, int, str]] = []
    for finding in findings:
        if _format_entry(finding.path, finding.snippet) in baseline:
            continue
        new_violations.append((finding.path, finding.lineno, finding.snippet))

    if new_violations:
        formatted = "\n  ".join(
            f"{_normalise_rel(path)}:{lineno}: {snippet}" for path, lineno, snippet in new_violations
        )
        print(
            "[lint_sync_session_in_async] SyncSessionLocal() inside async def detected:\n  " + formatted,
            file=sys.stderr,
        )
        print(
            "\nReplace SyncSessionLocal()/Session with AsyncSessionLocal()/get_db "
            "and use the async engine.  See docs/db-tuning.md.  If the addition is "
            "genuinely synchronous-only context (e.g. Celery, dedicated thread, CLI), "
            "regenerate the baseline (--update-baseline) only with reviewer approval.",
            file=sys.stderr,
        )
        return 1

    print(f"[lint_sync_session_in_async] OK — {len(findings)} grandfathered, no new violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
