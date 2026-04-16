"""Query robot message delivery / read status (OpenAPI)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.mindbot.platforms.dingtalk.api.constants import (
    PATH_ROBOT_GROUP_MESSAGES_QUERY,
    PATH_ROBOT_PRIVATE_CHAT_MESSAGES_QUERY,
)
from services.mindbot.platforms.dingtalk.api.http import post_v1_json

logger = logging.getLogger(__name__)


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(
            "[MindBot] robot_query: non-numeric value %r for int field, using default %s",
            value,
            default,
        )
        return default


async def query_private_chat_robot_messages(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    process_query_key: str,
    *,
    max_results: int = 200,
) -> Optional[dict[str, Any]]:
    """
    POST ``/v1.0/robot/privateChatMessages/query``.

    Docs: https://open.dingtalk.com/document/orgapp/query-the-read-status-of-robot-messages-in-private-chats
    Body: ``robotCode``, ``openConversationId``, ``processQueryKey``, ``maxResults`` (1–200).
    """
    payload: dict[str, Any] = {
        "robotCode": robot_code.strip(),
        "openConversationId": open_conversation_id.strip(),
        "processQueryKey": process_query_key.strip(),
        "maxResults": max(1, min(200, _safe_int(max_results, default=200))),
    }
    status, body = await post_v1_json(
        PATH_ROBOT_PRIVATE_CHAT_MESSAGES_QUERY,
        access_token,
        payload,
    )
    if status != 200:
        logger.warning("[MindBot] privateChatMessages/query status=%s", status)
        return None
    return body


async def query_group_robot_messages(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    process_query_key: str,
) -> Optional[dict[str, Any]]:
    """
    POST ``/v1.0/robot/groupMessages/query``.

    Docs: https://open.dingtalk.com/document/development/bots-send-query-and-recall-group-chat-messages
    Body: ``robotCode``, ``openConversationId``, ``processQueryKey``.
    """
    payload = {
        "robotCode": robot_code.strip(),
        "openConversationId": open_conversation_id.strip(),
        "processQueryKey": process_query_key.strip(),
    }
    status, body = await post_v1_json(
        PATH_ROBOT_GROUP_MESSAGES_QUERY,
        access_token,
        payload,
    )
    if status != 200:
        logger.warning("[MindBot] groupMessages/query status=%s", status)
        return None
    return body
