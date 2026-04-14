"""Shared Dify chat invocation for MindBot (reusable when adding non-DingTalk platforms)."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from clients.dify import (
    AsyncDifyClient,
    DifyAPIError,
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
    pipeline_ctx: str = "",
) -> Optional[dict[str, Any]]:
    """
    Run one blocking Dify chat for MindBot.

    If the cached ``conversation_id`` no longer exists in Dify, clears the binding
    (via ``on_stale_conversation``) and retries once without ``conversation_id``.

    Returns the parsed response dict or ``None`` on failure (logged).
    """
    logger.debug(
        "[MindBot] dify_blocking_request %s has_conv_id=%s text_chars=%s file_count=%s",
        pipeline_ctx,
        bool((conversation_id or "").strip()),
        len(text),
        len(files or []),
    )
    try:
        out = await dify.chat_blocking(
            message=text,
            user_id=user_id,
            conversation_id=conversation_id,
            auto_generate_name=False,
            files=files or None,
            inputs=inputs,
        )
        ans = out.get("answer", "") if isinstance(out, dict) else ""
        if not isinstance(ans, str):
            ans = str(ans)
        cid = out.get("conversation_id") if isinstance(out, dict) else None
        cids = (cid or "")[:32] if isinstance(cid, str) else ""
        logger.info(
            "[MindBot] dify_blocking_response %s answer_chars=%s dify_conv=%s",
            pipeline_ctx,
            len(ans),
            cids,
        )
        return out
    except DifyConversationNotFoundError:
        if conversation_id and on_stale_conversation is not None:
            logger.warning(
                "[MindBot] dify_blocking_stale_conversation %s retry_without_conv",
                pipeline_ctx,
            )
            await on_stale_conversation()
            try:
                out = await dify.chat_blocking(
                    message=text,
                    user_id=user_id,
                    conversation_id=None,
                    auto_generate_name=False,
                    files=files or None,
                    inputs=inputs,
                )
                ans = out.get("answer", "") if isinstance(out, dict) else ""
                if not isinstance(ans, str):
                    ans = str(ans)
                cid = out.get("conversation_id") if isinstance(out, dict) else None
                cids = (cid or "")[:32] if isinstance(cid, str) else ""
                logger.info(
                    "[MindBot] dify_blocking_response %s answer_chars=%s dify_conv=%s retry=1",
                    pipeline_ctx,
                    len(ans),
                    cids,
                )
                return out
            except Exception:
                logger.exception(
                    "[MindBot] dify_blocking_retry_failed %s",
                    pipeline_ctx,
                )
                return None
        logger.exception(
            "[MindBot] dify_blocking_conversation_missing %s",
            pipeline_ctx,
        )
        return None
    except DifyAPIError as exc:
        logger.warning(
            "[MindBot] dify_blocking_dify_api_error %s status=%s code=%s msg=%s",
            pipeline_ctx,
            exc.status_code,
            exc.error_code,
            exc.message,
        )
        return None
    except Exception:
        logger.exception(
            "[MindBot] dify_blocking_failed %s",
            pipeline_ctx,
        )
        return None
