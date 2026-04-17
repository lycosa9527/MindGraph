#!/usr/bin/env python
"""
Audit script: find async functions that transitively call sync Redis.
====================================================================

The lint guard ``scripts/lint/lint_sync_redis_in_async.py`` only flags direct
synchronous Redis usage inside an ``async def`` body.  This script extends
the analysis one level deeper:

1. Identify every sync function in the repository whose body contains a
   synchronous Redis call (``get_redis()``, bare ``RedisOps.<name>(...)``,
   or ``asyncio.to_thread(redis_client.<name>, ...)``).
2. Identify every async function in the repository that calls one of those
   "sync-Redis helpers" without wrapping the call in ``asyncio.to_thread``.
3. Report each such call as a transitive violation.

This is a one-shot diagnostic — not wired into CI — meant to be run
periodically during cleanup work.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

DEFAULT_SCAN_PATHS = (
    "routers",
    "services",
    "clients",
    "utils",
    "models",
    "config",
    "agents",
    "llm_chunking",
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
    "tasks",
}


def _iter_python_files(root: Path) -> Iterable[Path]:
    for candidate in sorted(root.rglob("*.py")):
        parts = set(candidate.parts)
        if parts & EXCLUDED_PARTS:
            continue
        yield candidate


def _is_sync_redis_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name) and func.id == "get_redis":
        return True
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "RedisOps":
            return True
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "to_thread"
        and isinstance(func.value, ast.Name)
        and func.value.id == "asyncio"
        and call.args
    ):
        first_arg = call.args[0]
        if isinstance(first_arg, ast.Attribute):
            value = first_arg.value
            if isinstance(value, ast.Name) and value.id in {
                "redis_client",
                "RedisOps",
                "redis",
            }:
                return True
    return False


class _SyncHelperCollector(ast.NodeVisitor):
    """Find sync def helpers that contain synchronous Redis calls."""

    def __init__(self, qualified_module: str) -> None:
        self._qualified_module = qualified_module
        self._scope: List[str] = []
        self._async_depth = 0
        self.sync_helpers: Set[str] = set()
        self.local_sync_helpers: Set[str] = set()

    def _qualify(self, name: str) -> str:
        if self._scope:
            return ".".join(self._scope + [name])
        return name

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scope.append(node.name)
        self._async_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self._async_depth -= 1
            self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope.append(node.name)
        contains_sync_redis = self._function_contains_sync_redis(node)
        if contains_sync_redis and self._async_depth == 0:
            qualified = f"{self._qualified_module}.{self._qualify_current()}"
            self.sync_helpers.add(qualified)
            self.local_sync_helpers.add(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def _qualify_current(self) -> str:
        return ".".join(self._scope)

    @staticmethod
    def _function_contains_sync_redis(func: ast.FunctionDef) -> bool:
        for descendant in ast.walk(func):
            if isinstance(descendant, ast.Call) and _is_sync_redis_call(descendant):
                return True
        return False


class _AsyncCallerScanner(ast.NodeVisitor):
    """Find async def bodies that call any name in ``sync_helper_names``."""

    def __init__(
        self,
        source_lines: List[str],
        path: str,
        sync_helper_names: Set[str],
    ) -> None:
        self._lines = source_lines
        self._path = path
        self._sync_names = sync_helper_names
        self._async_depth = 0
        self.findings: List[Tuple[int, str, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._async_depth += 1
        try:
            self.generic_visit(node)
        finally:
            self._async_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self._async_depth > 0:
            target_name: Optional[str] = None
            if isinstance(node.func, ast.Name):
                target_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                target_name = node.func.attr
            if target_name and target_name in self._sync_names:
                line_text = (
                    self._lines[node.lineno - 1].strip()
                    if node.lineno - 1 < len(self._lines)
                    else f"<call to {target_name}>"
                )
                self.findings.append((node.lineno, target_name, line_text))
        self.generic_visit(node)


def _collect_sync_helpers(repo_root: Path, scan_paths: Sequence[str]) -> Dict[str, Set[str]]:
    per_file: Dict[str, Set[str]] = {}
    for raw in scan_paths:
        target = (repo_root / raw).resolve()
        if not target.exists():
            continue
        files = [target] if target.is_file() else list(_iter_python_files(target))
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            collector = _SyncHelperCollector(str(path.relative_to(repo_root)).replace("\\", "/"))
            collector.visit(tree)
            if collector.local_sync_helpers:
                per_file[str(path.relative_to(repo_root)).replace("\\", "/")] = collector.local_sync_helpers
    return per_file


def _scan_async_callers(
    repo_root: Path,
    scan_paths: Sequence[str],
    per_file_sync_helpers: Dict[str, Set[str]],
) -> List[Tuple[str, int, str, str]]:
    findings: List[Tuple[str, int, str, str]] = []
    for raw in scan_paths:
        target = (repo_root / raw).resolve()
        if not target.exists():
            continue
        files = [target] if target.is_file() else list(_iter_python_files(target))
        for path in files:
            rel = str(path.relative_to(repo_root)).replace("\\", "/")
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            local_helpers = per_file_sync_helpers.get(rel, set())
            all_helpers: Set[str] = set(local_helpers)
            for helpers in per_file_sync_helpers.values():
                all_helpers.update(helpers)
            scanner = _AsyncCallerScanner(text.splitlines(), rel, all_helpers)
            scanner.visit(tree)
            for lineno, target_name, snippet in scanner.findings:
                findings.append((rel, lineno, target_name, snippet))
    return findings


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    scan_paths = list(DEFAULT_SCAN_PATHS)

    per_file_sync_helpers = _collect_sync_helpers(repo_root, scan_paths)
    if not per_file_sync_helpers:
        print("[audit_transitive_sync_redis] no sync Redis helpers detected.")
        return 0

    print("[audit_transitive_sync_redis] sync helpers that call sync Redis:")
    for rel, names in sorted(per_file_sync_helpers.items()):
        for name in sorted(names):
            print(f"  {rel} :: {name}()")
    print()

    findings = _scan_async_callers(repo_root, scan_paths, per_file_sync_helpers)
    if not findings:
        print("[audit_transitive_sync_redis] no async functions call those sync helpers directly.")
        return 0

    print("[audit_transitive_sync_redis] async def callers of sync-Redis helpers:")
    for rel, lineno, target_name, snippet in findings:
        print(f"  {rel}:{lineno}: -> {target_name}()  // {snippet}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
