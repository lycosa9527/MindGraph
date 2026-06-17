"""
Guard uvicorn reload watcher against self-referential project symlinks.

On WSL, an accidental ``MindGraph -> project root`` symlink breaks watchfiles with
"File system loop found" and prevents auto-reload from starting.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def clear_reload_breaking_symlinks(project_root: str | Path) -> list[str]:
    """
    Remove symlinks under ``project_root`` that resolve to the root or an ancestor.

    Returns:
        Paths (as strings) of removed symlinks.
    """
    root = Path(project_root).resolve()
    removed: list[str] = []

    try:
        entries = list(root.iterdir())
    except OSError as exc:
        logger.debug("[LAUNCHER] Could not scan project root for reload loops: %s", exc)
        return removed

    for entry in entries:
        if not entry.is_symlink():
            continue
        try:
            target = entry.resolve()
        except OSError as exc:
            logger.warning(
                "[LAUNCHER] Broken symlink blocks reload watcher; removing: %s (%s)",
                entry,
                exc,
            )
            entry.unlink()
            removed.append(str(entry))
            continue

        if target == root or root in target.parents:
            logger.warning(
                "[LAUNCHER] Removing reload-breaking symlink: %s -> %s",
                entry,
                target,
            )
            entry.unlink()
            removed.append(str(entry))

    return removed
