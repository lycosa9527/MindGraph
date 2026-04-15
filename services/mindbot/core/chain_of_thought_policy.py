"""Resolve whether to show chain-of-thought for the current DingTalk callback.

MindGraph maps per-chat scopes (1:1, internal group, cross-org) to visibility.
This is finer-grained than AstrBot's typical ``display_reasoning_text`` /
``show_reasoning`` flags on the provider or agent runner; behavior aligns with
AstrBot's idea of gating a separate reasoning channel before it reaches the user.
"""

from __future__ import annotations

from typing import Any

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.education.metrics import dingtalk_chat_scope
from services.mindbot.platforms.dingtalk.cards.ai_card_create import is_cross_org_group_body


def effective_show_chain_of_thought(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
) -> bool:
    """
    Per-chat policy: 1:1 vs internal group vs cross-org (external) group.

    Cross-org groups use LWCP tokens; internal groups have normal sender staff ids.
    Unknown scope defaults to hiding thinking (same as internal group default).
    """
    if is_cross_org_group_body(body):
        return bool(cfg.show_chain_of_thought_cross_org_group)
    scope = dingtalk_chat_scope(body)
    if scope == "oto":
        return bool(cfg.show_chain_of_thought_oto)
    if scope == "group":
        return bool(cfg.show_chain_of_thought_internal_group)
    return False
