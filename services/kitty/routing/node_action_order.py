"""Canonical execution order for Kitty node-action tool combinations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

# Lower runs first. Auto-complete always after structural; branch fill before
# whole-map fill (whole-map would replace branch children).
_ACTION_RANK: Dict[str, int] = {
    "update_center": 10,
    "delete_node": 20,
    "update_node": 30,
    "add_node": 40,
    "auto_complete_branch": 50,
    "auto_complete": 60,
    "clarify_options": 90,
}

_DEFAULT_RANK = 80


def action_execution_rank(action: str) -> int:
    """Return sort rank for a router action name (lower = earlier)."""
    return _ACTION_RANK.get(str(action or "").strip(), _DEFAULT_RANK)


def action_sort_key(cmd: Dict[str, Any], original_index: int) -> Tuple[int, int]:
    """
    Sort key for mixed tool calls.

    Structural mutations before auto-complete; within a tier, preserve the
    model's relative order via ``original_index``.
    """
    action = str(cmd.get("action") or "").strip()
    return (action_execution_rank(action), original_index)


def order_node_action_commands(
    commands: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return commands in safe execution order (copies)."""
    indexed = [
        (idx, dict(cmd))
        for idx, cmd in enumerate(commands)
        if isinstance(cmd, dict) and cmd.get("action") not in (None, "none")
    ]
    indexed.sort(key=lambda item: action_sort_key(item[1], item[0]))
    return [cmd for _idx, cmd in indexed]
