"""Shared Dify chat invocation for MindBot (reusable when adding non-DingTalk platforms)."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from clients.dify import (
    AsyncDifyClient,
    DifyConversationNotFoundError,
    DifyFile,
)

logger = logging.getLogger(__name__)


async def mindbot_dify_chat_blocking(
    dify: AsyncDifyClient,
    *,
    text: str,
    user_id: str,
    conversation_id: Optional[str],
    files: Optional[list[DifyFile]],
    inputs: Optional[dict[str, Any]] = None,
    on_stale_conversation: Optional[Callable[[], Awaitable[None]]] = None,
) -> Optional[dict[str, Any]]:
    """
    Run one blocking Dify chat for MindBot.

    If the cached ``conversation_id`` no longer exists in Dify, clears the binding
    (via ``on_stale_conversation``) and retries once without ``conversation_id``.

    Returns the parsed response dict or ``None`` on failure (logged).
    """
    try:
        return await dify.chat_blocking(
            message=text,
            user_id=user_id,
            conversation_id=conversation_id,
            auto_generate_name=False,
            files=files or None,
            inputs=inputs,
        )
    except DifyConversationNotFoundError:
        if conversation_id and on_stale_conversation is not None:
            logger.warning(
                "[MindBot] Dify conversation not found; clearing binding and retrying",
            )
            await on_stale_conversation()
            try:
                return await dify.chat_blocking(
                    message=text,
                    user_id=user_id,
                    conversation_id=None,
                    auto_generate_name=False,
                    files=files or None,
                    inputs=inputs,
                )
            except Exception as exc:
                logger.exception("[MindBot] Dify chat_blocking retry failed: %s", exc)
                return None
        logger.exception("[MindBot] Dify chat_blocking conversation missing")
        return None
    except Exception as exc:
        logger.exception("[MindBot] Dify chat_blocking failed: %s", exc)
        return None
