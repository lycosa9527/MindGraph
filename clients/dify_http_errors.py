"""Dify Service API HTTP error parsing and typed exceptions (Chatflow / app API).

Maps JSON ``code`` and HTTP status from Dify responses per official API docs
(chat-messages, files, conversations, etc.).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


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
    # Late import: ``clients.dify`` imports this module at load time.
    from clients import dify as dify_mod

    ec = (code or "").strip() if isinstance(code, str) else None
    ep = endpoint.lower()

    if status == 404:
        if ec in ("conversation_not_exists", "conversation_variable_not_exists"):
            raise dify_mod.DifyConversationNotFoundError(message)
        if ec == "file_not_found":
            raise dify_mod.DifyFileNotFoundError(message)
        if "conversation" in ep:
            raise dify_mod.DifyConversationNotFoundError(message)
        if "file" in ep:
            raise dify_mod.DifyFileNotFoundError(message)

    if status == 403 and ec == "file_access_denied":
        raise dify_mod.DifyFileAccessDeniedError(message)

    if status == 413 or ec == "file_too_large":
        raise dify_mod.DifyFileTooLargeError(message)

    if status == 415 and ec == "unsupported_file_type":
        raise dify_mod.DifyUnsupportedFileTypeError(message)

    if status == 400 and ec:
        if ec == "invalid_param":
            raise dify_mod.DifyInvalidParamError(message)
        if ec == "app_unavailable":
            raise dify_mod.DifyAppUnavailableError(message)
        if ec == "provider_not_initialize":
            raise dify_mod.DifyProviderNotInitializeError(message)
        if ec == "provider_quota_exceeded":
            raise dify_mod.DifyQuotaExceededError(message)
        if ec == "model_currently_not_support":
            raise dify_mod.DifyModelNotSupportError(message)
        if ec == "workflow_not_found":
            raise dify_mod.DifyWorkflowNotFoundError(message)
        if ec == "draft_workflow_error":
            raise dify_mod.DifyDraftWorkflowError(message)
        if ec == "workflow_id_format_error":
            raise dify_mod.DifyWorkflowIdFormatError(message)
        if ec == "completion_request_error":
            raise dify_mod.DifyCompletionRequestError(message)
        if ec in (
            "no_file_uploaded",
            "too_many_files",
            "unsupported_preview",
            "unsupported_estimate",
        ):
            raise dify_mod.DifyInvalidParamError(message)

    if status == 503 and ec and ec.startswith("s3_"):
        raise dify_mod.DifyS3StorageError(message, error_code=ec)

    raise dify_mod.DifyAPIError(message, status_code=status, error_code=ec)
