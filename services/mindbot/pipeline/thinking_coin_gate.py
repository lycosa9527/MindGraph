"""Block a MindBot turn when the linked account is short of thinking coins.

DingTalk has no web toast. The reply text is the same catalog message the
platform shows, sent on the session webhook before Dify is called.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.domain.messages import Language, Messages, get_request_language
from services.auth.thinking_coin.usage_wire import assert_thinking_coin_llm_budget
from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError
from services.redis.cache.redis_user_cache import user_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

_MINDMATE_REQUEST_TYPE = "mindmate"
_PREFLIGHT_SKIP_ERRORS = DATABASE_ERRORS + BACKGROUND_INFRA_ERRORS + REDIS_ERRORS


def mindbot_reply_language(ui_language: Optional[str]) -> Language:
    """DingTalk replies default to Chinese when the account has no UI language."""
    raw = (ui_language or "").strip()
    if not raw:
        return "zh"
    return get_request_language(raw)


def _insufficient_reply(
    exc: ThinkingCoinInsufficientError,
    lang: Language,
    reveal_balance: bool,
) -> str:
    """1:1 chats include the balance. Group chats do not name the sender's numbers."""
    if not reveal_balance:
        return Messages.error("thinking_coin_insufficient_shared", lang)
    text = (exc.user_message or "").strip()
    if text:
        return text
    return Messages.error("thinking_coin_insufficient", lang, exc.balance, exc.cost)


async def mindbot_thinking_coin_block_reply(
    linked_user_id: Optional[int],
    organization_id: Optional[int],
    *,
    reveal_balance: bool = True,
) -> Optional[str]:
    """Return the user-facing reply when this turn must not call Dify.

    Unlinked senders and paid accounts (thinking coins do not apply) return None.
    A balance check that cannot reach the wallet also returns None so a cache
    or database outage does not drop the turn.
    """
    if linked_user_id is None:
        return None

    lang: Language = "zh"
    try:
        user = await user_cache.get_by_id(int(linked_user_id))
        if user is not None:
            lang = mindbot_reply_language(getattr(user, "ui_language", None))
            user_org = getattr(user, "organization_id", None)
            if user_org is not None:
                organization_id = int(user_org)
        await assert_thinking_coin_llm_budget(
            int(linked_user_id),
            organization_id,
            _MINDMATE_REQUEST_TYPE,
            lang=lang,
        )
    except ThinkingCoinInsufficientError as exc:
        return _insufficient_reply(exc, lang, reveal_balance)
    except _PREFLIGHT_SKIP_ERRORS:
        logger.warning(
            "[MindBot] thinking coin preflight failed user_id=%s",
            linked_user_id,
            exc_info=True,
        )
        return None
    return None
