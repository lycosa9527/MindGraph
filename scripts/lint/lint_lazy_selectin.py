#!/usr/bin/env python
"""
CI / pre-commit guard: forbid new ``lazy="selectin"`` declarations.
==================================================================

Rationale
---------
``lazy="selectin"`` instructs SQLAlchemy to issue a separate ``SELECT … IN``
for every parent the application loads, which silently amplifies traffic
when the parent is large or referenced from a hot endpoint.  We learned
this the hard way on ``User.diagrams``, ``ChatChannel.messages`` and
``TokenUsage.user`` — see ``docs/db-tuning.md``.

Policy
------
The default loading strategy for one-to-many or many-to-many relationships
is ``lazy="select"`` (or no flag at all).  When a query genuinely benefits
from eager loading, request it on the **specific** query via
``options(selectinload(Parent.children))`` so the cost is local to that
call site.

The script scans ``models/**.py`` and compares every ``lazy="selectin"``
occurrence against a baseline file
(:data:`BASELINE_FILE_NAME`).  Pre-existing declarations are grandfathered
in; the build only fails on *new* declarations introduced by the current
change.  As individual relationships are migrated to ``lazy="select"`` and
explicit ``selectinload(...)`` options, drop the corresponding line from
the baseline.

To regenerate the baseline (e.g. after batch migration) run::

    python scripts/lint/lint_lazy_selectin.py --update-baseline

and review the diff before committing.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Set, Tuple


BASELINE_FILE_NAME = "lazy_selectin_baseline.txt"

_PATTERN = re.compile(r'lazy\s*=\s*["\']selectin["\']')


def _iter_python_files(root: Path) -> Iterable[Path]:
    yield from sorted(root.rglob("*.py"))


def _scan_file(path: Path) -> List[Tuple[int, str]]:
    findings: List[Tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return findings
    for lineno, line in enumerate(text.splitlines(), 1):
        if _PATTERN.search(line):
            findings.append((lineno, line.strip()))
    return findings


def _normalise_rel(rel_path: str) -> str:
    """Use forward slashes so the baseline is portable across platforms."""

    return rel_path.replace("\\", "/")


def _format_entry(rel_path: str, snippet: str) -> str:
    """Single canonical baseline line: ``relative/path :: snippet``."""

    return f"{_normalise_rel(rel_path)} :: {snippet}"


def _load_baseline(baseline_path: Path) -> Set[str]:
    if not baseline_path.exists():
        return set()
    return {
        line.strip()
        for line in baseline_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _collect_findings(repo_root: Path, scan_paths: List[str]) -> List[Tuple[str, int, str]]:
    findings: List[Tuple[str, int, str]] = []
    for raw in scan_paths:
        target = (repo_root / raw).resolve()
        if not target.exists():
            print(f"[lint_lazy_selectin] skip missing path: {target}", file=sys.stderr)
            continue
        files = [target] if target.is_file() else list(_iter_python_files(target))
        for file_path in files:
            for lineno, snippet in _scan_file(file_path):
                try:
                    rel_path = str(file_path.relative_to(repo_root))
                except ValueError:
                    rel_path = str(file_path)
                findings.append((rel_path, lineno, snippet))
    return findings


def _write_baseline(baseline_path: Path, findings: List[Tuple[str, int, str]]) -> None:
    entries = sorted({_format_entry(rel, snippet) for rel, _, snippet in findings})
    header = (
        '# Baseline of lazy="selectin" declarations grandfathered into the build.\n'
        "# One entry per line: <relative/path> :: <line snippet>.\n"
        '# Remove a line as you migrate the matching relationship to lazy="select".\n'
        "# Regenerate with: python scripts/lint/lint_lazy_selectin.py --update-baseline\n"
        "\n"
    )
    baseline_path.write_text(header + "\n".join(entries) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "paths",
        nargs="*",
        default=["models"],
        help="Paths to scan (default: models/).",
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
        print(f"[lint_lazy_selectin] baseline written to {baseline_path}")
        return 0

    baseline = _load_baseline(baseline_path)
    new_violations: List[str] = []
    for rel_path, lineno, snippet in findings:
        if _format_entry(rel_path, snippet) in baseline:
            continue
        new_violations.append(f"{_normalise_rel(rel_path)}:{lineno}: {snippet}")

    if new_violations:
        print(
            '[lint_lazy_selectin] new lazy="selectin" declarations introduced:\n  ' + "\n  ".join(new_violations),
            file=sys.stderr,
        )
        print(
            '\nUse lazy="select" (default) on collections and request eager loading '
            "explicitly with .options(selectinload(...)) at the call site. "
            "See docs/db-tuning.md. If the addition is intentional, regenerate the "
            "baseline (--update-baseline) only with reviewer approval.",
            file=sys.stderr,
        )
        return 1

    print(f"[lint_lazy_selectin] OK — {len(findings)} grandfathered, no new violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
