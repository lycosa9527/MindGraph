"""Dify Service API HTTP error parsing and typed exceptions (Chatflow / app API).

Maps JSON ``code`` and HTTP status from Dify responses per official API docs
(chat-messages, files, conversations, etc.).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import aiohttp

from clients.dify_exceptions import (
    DifyAPIError,
    DifyAppUnavailableError,
    DifyCompletionRequestError,
    DifyConversationNotFoundError,
    DifyDraftWorkflowError,
    DifyFileAccessDeniedError,
    DifyFileNotFoundError,
    DifyFileTooLargeError,
    DifyInvalidParamError,
    DifyModelNotSupportError,
    DifyProviderNotInitializeError,
    DifyQuotaExceededError,
    DifyS3StorageError,
    DifyUnsupportedFileTypeError,
    DifyWorkflowIdFormatError,
    DifyWorkflowNotFoundError,
)

logger = logging.getLogger(__name__)

# Gateway responses while Dify (or the proxy in front of it) is restarting.
DIFY_UPSTREAM_OUTAGE_STATUSES = frozenset({502, 503, 504})


def dify_error_is_upstream_outage(exc: BaseException) -> bool:
    """True when Dify is restarting or its gateway cannot reach the app."""
    if isinstance(exc, DifyAPIError):
        return exc.status_code in DIFY_UPSTREAM_OUTAGE_STATUSES
    return False


def dify_stream_chunk_is_upstream_outage(chunk: dict) -> bool:
    """True when a streamed error event is a gateway or connection failure."""
    status = chunk.get("status")
    return isinstance(status, int) and status in DIFY_UPSTREAM_OUTAGE_STATUSES


def mindmate_turn_on_backup(*, notify_backup: bool, server: Optional[int]) -> bool:
    """True when this chat turn is already on the backup Dify server."""
    return notify_backup or server == 2


def mindmate_upstream_error_code(*, on_backup: bool) -> str:
    """SSE / collab error code for a Dify gateway outage on this turn."""
    if on_backup:
        return "dify_backup_unavailable"
    return "dify_main_unavailable"


async def parse_dify_error_response(
    response: aiohttp.ClientResponse,
) -> tuple[str, Optional[str]]:
    """Read Dify JSON error body: ``message`` and ``code``."""
    error_msg = f"HTTP {response.status}"
    error_code: Optional[str] = None
    try:
        error_data = await response.json()
        if isinstance(error_data, dict):
            error_msg = error_data.get("message", error_msg)
            raw = error_data.get("code")
            if isinstance(raw, str):
                error_code = raw.strip() or None
            elif raw is not None:
                error_code = str(raw)
    except (json.JSONDecodeError, ValueError, aiohttp.ClientError):
        pass
    return error_msg, error_code


def raise_for_dify_http_error(
    status: int,
    message: str,
    code: Optional[str],
    endpoint: str,
) -> None:
    """
    Raise the appropriate ``DifyAPIError`` subclass.

    Called after a non-2xx response; ``endpoint`` is the path fragment (e.g. ``/chat-messages``).
    """
    ec = (code or "").strip() if isinstance(code, str) else None
    ep = endpoint.lower()

    if status == 404:
        if ec in ("conversation_not_exists", "conversation_variable_not_exists"):
            raise DifyConversationNotFoundError(message)
        if ec == "file_not_found":
            raise DifyFileNotFoundError(message)
        if "conversation" in ep:
            raise DifyConversationNotFoundError(message)
        if "file" in ep:
            raise DifyFileNotFoundError(message)

    if "conversation not exist" in message.lower():
        raise DifyConversationNotFoundError(message)

    if status == 403 and ec == "file_access_denied":
        raise DifyFileAccessDeniedError(message)

    if status == 413 or ec == "file_too_large":
        raise DifyFileTooLargeError(message)

    if status == 415 and ec == "unsupported_file_type":
        raise DifyUnsupportedFileTypeError(message)

    if status == 400 and ec:
        if ec == "invalid_param":
            raise DifyInvalidParamError(message)
        if ec == "app_unavailable":
            raise DifyAppUnavailableError(message)
        if ec == "provider_not_initialize":
            raise DifyProviderNotInitializeError(message)
        if ec == "provider_quota_exceeded":
            raise DifyQuotaExceededError(message)
        if ec == "model_currently_not_support":
            raise DifyModelNotSupportError(message)
        if ec == "workflow_not_found":
            raise DifyWorkflowNotFoundError(message)
        if ec == "draft_workflow_error":
            raise DifyDraftWorkflowError(message)
        if ec == "workflow_id_format_error":
            raise DifyWorkflowIdFormatError(message)
        if ec == "completion_request_error":
            raise DifyCompletionRequestError(message)
        if ec in (
            "no_file_uploaded",
            "too_many_files",
            "unsupported_preview",
            "unsupported_estimate",
        ):
            raise DifyInvalidParamError(message)

    if status == 503 and ec and ec.startswith("s3_"):
        raise DifyS3StorageError(message, error_code=ec)

    raise DifyAPIError(message, status_code=status, error_code=ec)
