"""Batched Dify SSE streaming: accumulate answer deltas, flush segments to DingTalk."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Awaitable, Callable, Optional

from clients.dify import AsyncDifyClient, DifyFile
from services.mindbot.dify_usage_parse import parse_dify_usage_from_stream_event
from utils.env_helpers import env_bool, env_float, env_int

logger = logging.getLogger(__name__)


_OPENAPI_TEXT_CHUNK = 5000


def _split_reply_chunks(text: str, max_len: int) -> list[str]:
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def _workflow_output_text(outputs: dict) -> Optional[str]:
    """
    Resolve assistant text from ``workflow_finished.data.outputs`` (Chatflow).

    If ``MINDBOT_DIFY_WORKFLOW_OUTPUT_KEY`` is set, use that key only.
    Otherwise try common keys: text, answer, output, result.
    """
    explicit = os.getenv("MINDBOT_DIFY_WORKFLOW_OUTPUT_KEY", "").strip()
    if explicit and explicit in outputs:
        val = outputs.get(explicit)
        if isinstance(val, str) and val.strip():
            return val
        return None
    for key in ("text", "answer", "output", "result", "summary"):
        val = outputs.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


def mindbot_stream_batch_params() -> tuple[int, float, int]:
    """``(min_chars, flush_interval_seconds, max_parts)`` from env."""
    flush_ms = env_float("MINDBOT_STREAM_FLUSH_MS", 400.0)
    return (
        max(1, env_int("MINDBOT_STREAM_MIN_CHARS", 64)),
        max(0.05, flush_ms / 1000.0),
        max(1, env_int("MINDBOT_STREAM_MAX_PARTS", 40)),
    )


def _should_flush(
    buffer: str,
    *,
    min_chars: int,
    last_flush_mono: float,
    flush_interval_s: float,
) -> bool:
    if not buffer:
        return False
    if len(buffer) >= min_chars:
        return True
    return time.monotonic() - last_flush_mono >= flush_interval_s


def _stream_error_is_conversation_not_exists(ev: dict[str, Any]) -> bool:
    """True when Dify SSE error indicates the conversation id is invalid or deleted."""
    code = ev.get("code")
    if isinstance(code, str) and code.strip().lower() == "conversation_not_exists":
        return True
    if code == "conversation_not_exists":
        return True
    err = ev.get("message") or ev.get("error") or ""
    if isinstance(err, str):
        low = err.lower()
        if "conversation_not_exists" in low:
            return True
        if "conversation" in low and "not exist" in low:
            return True
    return False


async def mindbot_consume_dify_stream_batched(
    dify: AsyncDifyClient,
    *,
    text: str,
    user_id: str,
    conversation_id: Optional[str],
    files: Optional[list[DifyFile]],
    min_chars: int,
    flush_interval_s: float,
    max_parts: int,
    on_batch: Callable[[str], Awaitable[tuple[bool, bool]]],
    inputs: Optional[dict[str, Any]] = None,
    on_stale_conversation: Optional[Callable[[], Awaitable[None]]] = None,
    stale_retry_done: bool = False,
) -> tuple[str, Optional[str], Optional[str], Optional[dict[str, int]]]:
    """
    Consume Dify ``stream_chat`` SSE (ChunkChatCompletionResponse), batch ``answer`` deltas.

    Matches Dify Service API streaming: ``message`` (text chunks), ``message_end``,
    ``message_replace`` (moderation / full text replacement), ``error``, ``ping``,
    ``workflow_finished`` (optional text from ``outputs`` when no ``message`` deltas),
    and other Chatflow prelude events.

    ``MINDBOT_STREAM_DEFER_TO_END``: accumulate only; send after ``message_end`` (avoids
    partial DingTalk bubbles before ``message_replace``).

    ``on_batch`` returns ``(success, token_failed)`` like OpenAPI helpers.

    Returns ``(full_text, conversation_id, error_token, usage_or_none)`` where
    ``error_token`` is one of: ``None`` (ok), ``"dify_error"``, ``"dify_empty"``,
    ``"send_failed"``, ``"token_failed"``.     ``usage_or_none`` may include Dify
    ``prompt_tokens`` / ``completion_tokens`` / ``total_tokens`` from ``message_end``.

    If the stream fails with a stale ``conversation_id``, ``on_stale_conversation``
    is invoked and the stream is retried once without ``conversation_id``.
    """
    defer_to_end = env_bool("MINDBOT_STREAM_DEFER_TO_END", False)
    usage_snapshot: Optional[dict[str, int]] = None
    full = ""
    buf = ""
    last_flush = time.monotonic()
    parts_sent = 0
    outbound_count = 0
    conv_id: Optional[str] = None
    saw_answer = False
    wf_fallback_text: Optional[str] = None
    deferred_flushed = False

    async for ev in dify.stream_chat(
        message=text,
        user_id=user_id,
        conversation_id=conversation_id,
        files=files,
        auto_generate_name=False,
        inputs=inputs,
    ):
        evt = ev.get("event")
        cid = ev.get("conversation_id")
        if isinstance(cid, str) and cid.strip():
            conv_id = cid.strip()

        if evt == "error":
            err = ev.get("message") or ev.get("error") or "dify stream error"
            code = ev.get("code")
            status = ev.get("status")
            if (
                conversation_id
                and not stale_retry_done
                and _stream_error_is_conversation_not_exists(ev)
                and on_stale_conversation is not None
            ):
                logger.warning(
                    "[MindBot] Dify stream conversation not found; clearing binding and retrying",
                )
                await on_stale_conversation()
                return await mindbot_consume_dify_stream_batched(
                    dify,
                    text=text,
                    user_id=user_id,
                    conversation_id=None,
                    files=files,
                    min_chars=min_chars,
                    flush_interval_s=flush_interval_s,
                    max_parts=max_parts,
                    on_batch=on_batch,
                    inputs=inputs,
                    on_stale_conversation=on_stale_conversation,
                    stale_retry_done=True,
                )
            logger.warning(
                "[MindBot] Dify stream error event: %s code=%s status=%s",
                err,
                code,
                status,
            )
            return full, conv_id, "dify_error", usage_snapshot

        if evt == "ping":
            continue

        if evt in ("workflow_started", "node_started", "node_finished"):
            continue

        if evt == "workflow_finished":
            data = ev.get("data") or {}
            outputs = data.get("outputs")
            if isinstance(outputs, dict):
                extracted = _workflow_output_text(outputs)
                if extracted:
                    wf_fallback_text = extracted
            continue

        if evt == "message_replace":
            if outbound_count > 0:
                logger.warning(
                    "[MindBot] message_replace after %s DingTalk sends; "
                    "clients may still show earlier partials",
                    outbound_count,
                )
            repl = ev.get("answer") or ""
            full = repl
            buf = ""
            saw_answer = bool(repl.strip())
            continue

        if evt in ("message", "agent_message"):
            delta = ev.get("answer") or ""
            if not delta:
                continue
            saw_answer = True
            full += delta
            if defer_to_end:
                continue
            buf += delta
            if (
                buf
                and parts_sent < max_parts
                and _should_flush(
                    buf,
                    min_chars=min_chars,
                    last_flush_mono=last_flush,
                    flush_interval_s=flush_interval_s,
                )
            ):
                to_send = buf
                buf = ""
                last_flush = time.monotonic()
                ok, token_failed = await on_batch(to_send)
                if not ok:
                    return (
                        full,
                        conv_id,
                        "token_failed" if token_failed else "send_failed",
                        usage_snapshot,
                    )
                parts_sent += 1
                outbound_count += 1
            continue

        if evt == "message_end":
            parsed_u = parse_dify_usage_from_stream_event(ev)
            if parsed_u:
                usage_snapshot = parsed_u
            if not full.strip() and wf_fallback_text:
                full = wf_fallback_text
                saw_answer = bool(full.strip())
            if defer_to_end:
                if full.strip():
                    for part in _split_reply_chunks(full, _OPENAPI_TEXT_CHUNK):
                        if outbound_count >= max_parts:
                            logger.warning(
                                "[MindBot] MINDBOT_STREAM_MAX_PARTS reached in defer mode",
                            )
                            break
                        ok, token_failed = await on_batch(part)
                        if not ok:
                            return (
                                full,
                                conv_id,
                                "token_failed" if token_failed else "send_failed",
                                usage_snapshot,
                            )
                        outbound_count += 1
                deferred_flushed = True
            elif buf:
                ok, token_failed = await on_batch(buf)
                buf = ""
                if not ok:
                    return (
                        full,
                        conv_id,
                        "token_failed" if token_failed else "send_failed",
                        usage_snapshot,
                    )
                parts_sent += 1
                outbound_count += 1
            break

    if not full.strip() and wf_fallback_text:
        full = wf_fallback_text
        saw_answer = bool(full.strip())

    if not saw_answer and not full.strip():
        return "", conv_id, "dify_empty", usage_snapshot

    if defer_to_end:
        if not deferred_flushed and full.strip():
            for part in _split_reply_chunks(full, _OPENAPI_TEXT_CHUNK):
                if outbound_count >= max_parts:
                    break
                ok, token_failed = await on_batch(part)
                if not ok:
                    return (
                        full,
                        conv_id,
                        "token_failed" if token_failed else "send_failed",
                        usage_snapshot,
                    )
                outbound_count += 1
        return full, conv_id, None, usage_snapshot

    if buf:
        ok, token_failed = await on_batch(buf)
        if not ok:
            return (
                full,
                conv_id,
                "token_failed" if token_failed else "send_failed",
                usage_snapshot,
            )
        outbound_count += 1
    elif full.strip() and outbound_count == 0:
        for part in _split_reply_chunks(full, _OPENAPI_TEXT_CHUNK):
            if parts_sent >= max_parts:
                logger.warning(
                    "[MindBot] MINDBOT_STREAM_MAX_PARTS reached (workflow or single-shot)",
                )
                break
            ok, token_failed = await on_batch(part)
            if not ok:
                return (
                    full,
                    conv_id,
                    "token_failed" if token_failed else "send_failed",
                    usage_snapshot,
                )
            parts_sent += 1
            outbound_count += 1

    return full, conv_id, None, usage_snapshot
