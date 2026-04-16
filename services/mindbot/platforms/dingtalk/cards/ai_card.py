"""DingTalk AI interactive card — public API re-exports.

Implementation is split across:
- ``ai_card_create`` — body inspection, delivery pre-checks, createAndDeliver
- ``ai_card_update`` — streaming updates, receiver mode, mark-error, admin probe

All names are re-exported from this module so callers do not need to change.
"""

from __future__ import annotations

from services.mindbot.platforms.dingtalk.cards import ai_card_create
from services.mindbot.platforms.dingtalk.cards import ai_card_update

ai_card_body_deliverable = ai_card_create.ai_card_body_deliverable
ai_card_overflow_remainder_for_markdown = ai_card_create.ai_card_overflow_remainder_for_markdown
create_and_deliver_ai_card = ai_card_create.create_and_deliver_ai_card
is_cross_org_group_body = ai_card_create.is_cross_org_group_body
mindbot_ai_card_param_key = ai_card_create.mindbot_ai_card_param_key
mindbot_ai_card_streaming_max_chars = ai_card_create.mindbot_ai_card_streaming_max_chars
mindbot_ai_card_template_id = ai_card_create.mindbot_ai_card_template_id
mindbot_ai_card_wiring_enabled = ai_card_create.mindbot_ai_card_wiring_enabled
prefetch_ai_card_access_token = ai_card_create.prefetch_ai_card_access_token

AiCardProbeResult = ai_card_update.AiCardProbeResult
mark_ai_card_stream_error = ai_card_update.mark_ai_card_stream_error
probe_ai_card_streaming_update_api = ai_card_update.probe_ai_card_streaming_update_api
streaming_update_ai_card = ai_card_update.streaming_update_ai_card
update_ai_card_receiver = ai_card_update.update_ai_card_receiver

__all__ = [
    "AiCardProbeResult",
    "ai_card_body_deliverable",
    "ai_card_overflow_remainder_for_markdown",
    "create_and_deliver_ai_card",
    "is_cross_org_group_body",
    "mark_ai_card_stream_error",
    "mindbot_ai_card_param_key",
    "mindbot_ai_card_streaming_max_chars",
    "mindbot_ai_card_template_id",
    "mindbot_ai_card_wiring_enabled",
    "prefetch_ai_card_access_token",
    "probe_ai_card_streaming_update_api",
    "streaming_update_ai_card",
    "update_ai_card_receiver",
]
