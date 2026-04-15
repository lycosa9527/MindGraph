"""DingTalk AI interactive card — public API re-exports.

Implementation is split across:
- ``ai_card_create`` — body inspection, delivery pre-checks, createAndDeliver
- ``ai_card_update`` — streaming updates, receiver mode, mark-error, admin probe

All names are re-exported from this module so callers do not need to change.
"""

from __future__ import annotations

from services.mindbot.platforms.dingtalk.cards.ai_card_create import (
    ai_card_body_deliverable,
    ai_card_overflow_remainder_for_markdown,
    create_and_deliver_ai_card,
    is_cross_org_group_body,
    mindbot_ai_card_param_key,
    mindbot_ai_card_template_id,
    mindbot_ai_card_wiring_enabled,
    prefetch_ai_card_access_token,
)
from services.mindbot.platforms.dingtalk.cards.ai_card_update import (
    AiCardProbeResult,
    mark_ai_card_stream_error,
    probe_ai_card_streaming_update_api,
    streaming_update_ai_card,
    update_ai_card_receiver,
)

__all__ = [
    "AiCardProbeResult",
    "ai_card_body_deliverable",
    "ai_card_overflow_remainder_for_markdown",
    "create_and_deliver_ai_card",
    "is_cross_org_group_body",
    "mark_ai_card_stream_error",
    "mindbot_ai_card_param_key",
    "mindbot_ai_card_template_id",
    "mindbot_ai_card_wiring_enabled",
    "prefetch_ai_card_access_token",
    "probe_ai_card_streaming_update_api",
    "streaming_update_ai_card",
    "update_ai_card_receiver",
]
