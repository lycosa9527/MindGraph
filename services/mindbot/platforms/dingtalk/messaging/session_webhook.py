"""Build DingTalk session webhook reply bodies (HTTP response to callback).

Supported outbound types for session webhook (per DingTalk docs):
text, markdown, actionCard (single / multi), feedCard.

MindBot uses ``text`` or ``markdown`` by env ``MINDBOT_REPLY_MSGTYPE`` (default markdown).

See DingTalk receive-message-1 (HTTP 响应格式) and enterprise robot message types docs
on open.dingtalk.com (receive-message-1, message-types-supported-by-enterprise-internal-robots).

OpenAPI fallback (``/v1.0/robot/groupMessages/send`` and ``oToMessages/batchSend``) uses
``openapi_robot_msg_param_for_answer`` so ``msgKey`` / ``msgParam`` stay aligned with the
same templates (``sampleText``, ``sampleMarkdown``, etc.).
"""

from __future__ import annotations

import os
import re
from typing import Any

_MAX_OUT = 20000
_OPENAPI_TEXT_MAX = 5000
_OPENAPI_MARKDOWN_TITLE_MAX = 80


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUT:
        return text
    return text[:_MAX_OUT] + "…"


def sanitize_markdown_for_dingtalk(text: str) -> str:
    """Light cleanup; DingTalk markdown is a subset of CommonMark."""
    if not text:
        return " "
    t = text.replace("\r\n", "\n")
    t = re.sub(r"\n{4,}", "\n\n\n", t)
    return t


def build_session_webhook_payload(answer: str, *, stream_chunk: bool = False) -> dict[str, Any]:
    """
    Build JSON body for POST sessionWebhook.

    ``MINDBOT_REPLY_MSGTYPE``: ``markdown`` (default) or ``text``.
    Markdown gives richer rendering in DingTalk clients per official examples.

    When ``stream_chunk`` is True, use ``text`` only so partial deltas are not broken
    markdown (used with ``MINDBOT_DIFY_STREAMING``).
    """
    if stream_chunk:
        text = _truncate(answer.strip() if isinstance(answer, str) else str(answer))
        return {"msgtype": "text", "text": {"content": text}}
    raw = os.getenv("MINDBOT_REPLY_MSGTYPE", "markdown").strip().lower()
    mode = raw if raw in ("text", "markdown") else "markdown"
    text = _truncate(answer.strip() if isinstance(answer, str) else str(answer))
    if mode == "text":
        return {"msgtype": "text", "text": {"content": text}}
    title = "MindBot"
    first = text.split("\n", 1)[0].strip()
    if first and len(first) <= 80:
        title = first
    body_md = sanitize_markdown_for_dingtalk(text)
    if not body_md.strip():
        body_md = " "
    return {"msgtype": "markdown", "markdown": {"title": title, "text": body_md}}


def _clip_openapi_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return "…"
    return text[: max_len - 1] + "…"


def markdown_title_and_body_for_openapi(answer: str) -> tuple[str, str]:
    """
    Title and body for ``sampleMarkdown`` (same rules as session webhook markdown).

    Per DingTalk robot send API: msgParam is
    ``{"title": "...", "text": "..."}``.
    """
    text = _truncate(answer.strip() if isinstance(answer, str) else str(answer))
    title = "MindBot"
    first = text.split("\n", 1)[0].strip()
    if first and len(first) <= _OPENAPI_MARKDOWN_TITLE_MAX:
        title = first
    body_md = sanitize_markdown_for_dingtalk(text)
    if not body_md.strip():
        body_md = " "
    body_md = _clip_openapi_text(body_md, _OPENAPI_TEXT_MAX)
    title = _clip_openapi_text(title, _OPENAPI_MARKDOWN_TITLE_MAX)
    return title, body_md


def _first_https_url_line(answer: str) -> str:
    for line in answer.strip().splitlines():
        line = line.strip()
        if line.startswith("https://"):
            return line[:2048]
    return ""


def openapi_robot_msg_param_stream_chunk(answer: str) -> tuple[str, dict[str, Any]]:
    """
    ``sampleText`` for a streaming segment (avoids half-rendered markdown in DingTalk).
    """
    content = _clip_openapi_text(
        answer.strip() if isinstance(answer, str) else str(answer),
        _OPENAPI_TEXT_MAX,
    )
    return "sampleText", {"content": content}


def openapi_robot_msg_param_for_answer(answer: str) -> tuple[str, dict[str, Any]]:
    """
    Build ``(msgKey, msgParam)`` for ``/v1.0/robot/groupMessages/send`` and
    ``/v1.0/robot/oToMessages/batchSend`` (msgParam is JSON-serialized by the caller).

    ``MINDBOT_OPENAPI_FALLBACK_MSGKEY`` overrides automatic choice. Supported:
    ``sampleText``, ``sampleMarkdown``, ``sampleImageMsg`` (HTTPS URL on first line).

    If unset, mirrors ``MINDBOT_REPLY_MSGTYPE``: markdown -> ``sampleMarkdown``,
    text -> ``sampleText``.

    Any other ``MINDBOT_OPENAPI_FALLBACK_MSGKEY`` value falls through to that same mirror
    logic (use ``send_group_robot_message`` with a custom ``msg_param`` for advanced keys
    like ``sampleLink`` / ``sampleActionCard``).
    """
    explicit = os.getenv("MINDBOT_OPENAPI_FALLBACK_MSGKEY", "").strip()
    if explicit:
        key = explicit.strip()
        lk = key.lower()
        if lk == "sampletext":
            content = _clip_openapi_text(
                answer.strip() if isinstance(answer, str) else str(answer),
                _OPENAPI_TEXT_MAX,
            )
            return key, {"content": content}
        if lk == "samplemarkdown":
            t, b = markdown_title_and_body_for_openapi(answer)
            return key, {"title": t, "text": b}
        if lk == "sampleimagemsg":
            url = _first_https_url_line(answer)
            if url:
                return key, {"photoURL": url}
            t, b = markdown_title_and_body_for_openapi(answer)
            return "sampleMarkdown", {"title": t, "text": b}

    raw = os.getenv("MINDBOT_REPLY_MSGTYPE", "markdown").strip().lower()
    mode = raw if raw in ("text", "markdown") else "markdown"
    if mode == "text":
        content = _clip_openapi_text(
            answer.strip() if isinstance(answer, str) else str(answer),
            _OPENAPI_TEXT_MAX,
        )
        return "sampleText", {"content": content}
    t, b = markdown_title_and_body_for_openapi(answer)
    return "sampleMarkdown", {"title": t, "text": b}
