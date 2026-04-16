"""Batch recall robot messages (group + one-to-one)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.mindbot.platforms.dingtalk.api.constants import (
    PATH_ROBOT_GROUP_MESSAGES_BATCH_RECALL,
    PATH_ROBOT_OTO_MESSAGES_BATCH_RECALL,
    ROBOT_RECALL_MAX_KEYS,
)
from services.mindbot.platforms.dingtalk.api.http import post_v1_json

logger = logging.getLogger(__name__)


async def batch_recall_group_robot_messages(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    process_query_keys: list[str],
) -> Optional[dict[str, Any]]:
    """
    POST ``/v1.0/robot/groupMessages/batchRecall``.

    Up to ``ROBOT_RECALL_MAX_KEYS`` keys per request; longer lists are chunked.

    Returns the last successful response body when **all** chunks succeed, or
    ``None`` when any chunk fails.  A WARNING is logged with the failing chunk
    index and the count of chunks that already succeeded.

    Docs: https://open.dingtalk.com/document/development/bots-send-query-and-recall-group-chat-messages
    """
    keys = [k.strip() for k in process_query_keys if k.strip()]
    if not keys:
        return None
    total_chunks = (len(keys) + ROBOT_RECALL_MAX_KEYS - 1) // ROBOT_RECALL_MAX_KEYS
    last: Optional[dict[str, Any]] = None
    succeeded = 0
    for i in range(0, len(keys), ROBOT_RECALL_MAX_KEYS):
        chunk_idx = i // ROBOT_RECALL_MAX_KEYS
        chunk = keys[i : i + ROBOT_RECALL_MAX_KEYS]
        payload = {
            "robotCode": robot_code.strip(),
            "openConversationId": open_conversation_id.strip(),
            "processQueryKeys": chunk,
        }
        status, body = await post_v1_json(
            PATH_ROBOT_GROUP_MESSAGES_BATCH_RECALL,
            access_token,
            payload,
        )
        if status != 200 or body is None:
            logger.warning(
                "[MindBot] group batchRecall failed chunk_idx=%s/%s "
                "status=%s succeeded_before=%s total_chunks=%s",
                chunk_idx,
                total_chunks - 1,
                status,
                succeeded,
                total_chunks,
            )
            return None
        succeeded += 1
        last = body
    return last


async def batch_recall_oto_robot_messages(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    process_query_keys: list[str],
) -> Optional[dict[str, Any]]:
    """
    POST ``/v1.0/robot/otoMessages/batchRecall``.

    Requires ``openConversationId`` for the one-to-one session.

    Returns the last successful response body when **all** chunks succeed, or
    ``None`` when any chunk fails.  A WARNING is logged with the failing chunk
    index and the count of chunks that already succeeded.

    Docs: https://open.dingtalk.com/document/development/batch-message-recall-chat
    """
    keys = [k.strip() for k in process_query_keys if k.strip()]
    if not keys:
        return None
    total_chunks = (len(keys) + ROBOT_RECALL_MAX_KEYS - 1) // ROBOT_RECALL_MAX_KEYS
    last: Optional[dict[str, Any]] = None
    succeeded = 0
    for i in range(0, len(keys), ROBOT_RECALL_MAX_KEYS):
        chunk_idx = i // ROBOT_RECALL_MAX_KEYS
        chunk = keys[i : i + ROBOT_RECALL_MAX_KEYS]
        payload = {
            "robotCode": robot_code.strip(),
            "openConversationId": open_conversation_id.strip(),
            "processQueryKeys": chunk,
        }
        status, body = await post_v1_json(
            PATH_ROBOT_OTO_MESSAGES_BATCH_RECALL,
            access_token,
            payload,
        )
        if status != 200 or body is None:
            logger.warning(
                "[MindBot] oTo batchRecall failed chunk_idx=%s/%s "
                "status=%s succeeded_before=%s total_chunks=%s",
                chunk_idx,
                total_chunks - 1,
                status,
                succeeded,
                total_chunks,
            )
            return None
        succeeded += 1
        last = body
    return last
