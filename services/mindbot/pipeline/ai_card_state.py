"""AI-card streaming state machine extracted from dify_paths.py.

Encapsulates the mutable state that tracks whether an AI card has been
created, its accumulated markdown buffer, the current DingTalk access token,
and the update mode (``stream`` vs ``receiver``).
"""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import Any, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.core.reply_thinking import format_mindbot_reply_for_dingtalk
from services.mindbot.platforms.dingtalk.cards.ai_card import (
    ai_card_body_deliverable,
    is_cross_org_group_body,
    mark_ai_card_stream_error,
    mindbot_ai_card_wiring_enabled,
    prefetch_ai_card_access_token,
    streaming_update_ai_card,
    update_ai_card_receiver,
)
from services.mindbot.platforms.dingtalk.cards.ai_card_errors import describe_ai_card_failure

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CardStreamState:
    """Typed accumulator for AI-card streaming state within one Dify turn."""

    use_card: bool
    buffer_only: bool
    cum: str = ""
    out_track_id: Optional[str] = None
    token: Optional[str] = None
    created: bool = False
    update_mode: str = "stream"
    t0: float = dataclasses.field(default_factory=time.monotonic)
    first_chunk: bool = False
    card_chars_confirmed: int = 0

    def hidden_reply_from_cum(self, cfg: OrganizationMindbotConfig) -> str:
        """Re-apply hide rules on accumulated visible text."""
        return format_mindbot_reply_for_dingtalk(
            self.cum,
            show_chain_of_thought=False,
            chain_of_thought_max_chars=int(cfg.chain_of_thought_max_chars),
            native_reasoning="",
        )

    def reset(self, cfg: OrganizationMindbotConfig) -> None:
        """Reset state after a Dify ``message_replace`` event."""
        self.cum = ""
        self.out_track_id = None
        self.token = None
        self.created = False
        self.update_mode = "stream"
        self.card_chars_confirmed = 0
        self.use_card = (
            mindbot_ai_card_wiring_enabled(cfg) and not self.buffer_only
        )

    async def finalize(
        self,
        cfg: OrganizationMindbotConfig,
        reply_text: str,
        pipeline_ctx: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Send the final AI-card update.

        Returns ``(True, None)`` on success, ``(False, None)`` on failure.
        The caller is responsible for sending overflow remainder or fallback
        text when finalization fails.
        """
        tok = self.token
        out_tid = self.out_track_id
        if not tok or not isinstance(out_tid, str):
            return False, None

        fin_use_receiver = self.update_mode == "receiver"
        if fin_use_receiver:
            fin_ok, fin_code, fin_detail, fin_tok = await update_ai_card_receiver(
                cfg,
                access_token=str(tok),
                out_track_id=str(out_tid),
                markdown_full=reply_text,
                is_finalize=True,
                pipeline_ctx=pipeline_ctx,
            )
        else:
            fin_ok, fin_code, fin_detail, fin_tok = await streaming_update_ai_card(
                cfg,
                access_token=str(tok),
                out_track_id=str(out_tid),
                markdown_full=reply_text,
                is_finalize=True,
                pipeline_ctx=pipeline_ctx,
            )
        if fin_tok:
            self.token = fin_tok

        if fin_ok:
            return True, None

        logger.warning(
            "[MindBot] ai_card_finalize_failed %s %s",
            pipeline_ctx,
            describe_ai_card_failure(fin_code, fin_detail),
        )
        if not fin_use_receiver:
            mk_ok, mk_code, mk_detail, mk_tok = await mark_ai_card_stream_error(
                cfg,
                access_token=str(self.token or tok),
                out_track_id=str(out_tid),
                pipeline_ctx=pipeline_ctx,
            )
            if mk_tok:
                self.token = mk_tok
            if not mk_ok:
                logger.warning(
                    "[MindBot] ai_card_mark_error_after_finalize_failed %s %s",
                    pipeline_ctx,
                    describe_ai_card_failure(mk_code, mk_detail),
                )
        return False, None


async def init_card_stream_state(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    pipeline_ctx: str,
) -> CardStreamState:
    """Create and initialise a :class:`CardStreamState` for a streaming turn."""
    card_wiring = mindbot_ai_card_wiring_enabled(cfg)
    is_cross_org = is_cross_org_group_body(body)

    if card_wiring:
        deliverable, skip_reason = ai_card_body_deliverable(body)
        if not deliverable:
            logger.info(
                "[MindBot] ai_card_skipped %s reason=%s",
                pipeline_ctx,
                skip_reason,
            )
            card_wiring = False

    if is_cross_org and card_wiring:
        logger.info(
            "[MindBot] ai_card_skipped %s reason=cross_org_group",
            pipeline_ctx,
        )
        card_wiring = False

    outbound = "ai_card" if card_wiring else ("buffer→plain" if is_cross_org else "plain")
    logger.info("[MindBot] route %s outbound=%s", pipeline_ctx, outbound)

    initial_token: Optional[str] = None
    if card_wiring:
        initial_token = await prefetch_ai_card_access_token(cfg)
        if not initial_token:
            logger.warning(
                "[MindBot] ai_card_token_prefetch_failed %s disabling_card_wiring",
                pipeline_ctx,
            )
            card_wiring = False

    return CardStreamState(
        use_card=card_wiring,
        buffer_only=is_cross_org,
        token=initial_token,
    )
