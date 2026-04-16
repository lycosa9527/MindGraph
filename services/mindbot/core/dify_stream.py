"""Batched Dify SSE streaming: accumulate answer deltas, flush segments to DingTalk."""

from __future__ import annotations

import functools
import logging
import os
import time
from typing import Any, Awaitable, Callable, Optional

from clients.dify import AsyncDifyClient, DifyFile
from services.mindbot.core.dify_sse_parse import (
    is_image_file_type,
    parse_message_file_event,
    parse_tts_audio_base64_chunk,
    workflow_outputs_file_hints,
)
from services.mindbot.dify.usage_parse import parse_dify_usage_from_stream_event
from utils.env_helpers import env_bool, env_float, env_int

logger = logging.getLogger(__name__)


_OPENAPI_TEXT_CHUNK = 5000


def _split_reply_chunks(text: str, max_len: int) -> list[str]:
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


@functools.cache
def _workflow_output_key() -> str:
    return os.getenv("MINDBOT_DIFY_WORKFLOW_OUTPUT_KEY", "").strip()


def _workflow_output_text(outputs: dict[str, Any]) -> Optional[str]:
    """
    Resolve assistant text from ``workflow_finished.data.outputs`` (Chatflow).

    If ``MINDBOT_DIFY_WORKFLOW_OUTPUT_KEY`` is set, use that key only.
    Otherwise try common keys: text, answer, output, result.
    """
    explicit = _workflow_output_key()
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


@functools.cache
def mindbot_stream_batch_params() -> tuple[int, float, int]:
    """``(min_chars, flush_interval_seconds, max_parts)`` from env (cached at first call)."""
    flush_ms = env_float("MINDBOT_STREAM_FLUSH_MS", 400.0)
    return (
        max(1, env_int("MINDBOT_STREAM_MIN_CHARS", 64)),
        max(0.05, flush_ms / 1000.0),
        max(1, env_int("MINDBOT_STREAM_MAX_PARTS", 40)),
    )


@functools.cache
def mindbot_stream_max_media_parts() -> int:
    return max(0, env_int("MINDBOT_STREAM_MAX_MEDIA_PARTS", 12))


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


def _extract_agent_thought_text(ev: dict[str, Any]) -> str:
    """
    Best-effort text from Dify ``agent_thought`` (and similar) streaming events.

    Field names vary by Dify version and app mode; we accept common top-level and
    ``data`` payload keys.
    """
    for key in ("thought", "observation", "tool_input"):
        val = ev.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    data = ev.get("data")
    if isinstance(data, dict):
        for key in ("thought", "observation", "tool_input", "message"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


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
    pipeline_ctx: str = "",
    on_media: Optional[
        Callable[[str, dict[str, Any]], Awaitable[tuple[bool, bool]]]
    ] = None,
    on_message_replace: Optional[Callable[[], Awaitable[None]]] = None,
    on_stream_started: Optional[Callable[[], None]] = None,
) -> tuple[str, Optional[str], Optional[str], Optional[dict[str, int]], str]:
    """
    Consume Dify ``stream_chat`` SSE (ChunkChatCompletionResponse), batch ``answer`` deltas.

    Returns ``(full_text, conversation_id, error_token, usage_snapshot, native_reasoning)``.
    ``native_reasoning`` concatenates Dify ``agent_thought`` payloads (when present);
    it is cleared on ``message_replace`` so discarded streams do not leak. Merge with
    tag-embedded reasoning in ``format_mindbot_reply_for_dingtalk``.

    ``on_media`` when set receives (kind, payload): ``image`` (url), ``audio`` (bytes),
    ``markdown`` (text for file links). OpenAPI-only sends; session webhook is not used.

    ``on_message_replace`` when set is awaited after Dify ``message_replace`` (answer reset);
    use to reset AI card or UI state that tracks cumulative deltas.

    Stale-conversation retry uses a single recursive call with ``on_stale_conversation=None``
    (at most 2 total attempts); the second call does not retry again so stack depth is bounded.
    """
    defer_to_end = env_bool("MINDBOT_STREAM_DEFER_TO_END", False)
    native_media = env_bool("MINDBOT_DIFY_NATIVE_MEDIA_ENABLED", True)
    tts_enabled = env_bool("MINDBOT_DIFY_TTS_ENABLED", True)
    max_media = mindbot_stream_max_media_parts()
    use_media = native_media and on_media is not None

    logger.debug(
        "[MindBot] dify_sse_start %s has_conv_id=%s query_chars=%s defer_to_end=%s "
        "batch_min_chars=%s batch_flush_s=%.3f batch_max_parts=%s native_media=%s",
        pipeline_ctx,
        bool((conversation_id or "").strip()),
        len(text),
        defer_to_end,
        min_chars,
        flush_interval_s,
        max_parts,
        use_media,
    )
    usage_snapshot: Optional[dict[str, int]] = None
    full = ""
    buf = ""
    last_flush = time.monotonic()
    parts_sent = 0
    outbound_count = 0
    media_sent = 0
    conv_id: Optional[str] = None
    saw_answer = False
    wf_fallback_text: Optional[str] = None
    wf_file_hints: list[dict[str, Any]] = []
    deferred_flushed = False
    pending_after_text: list[tuple[str, dict[str, Any]]] = []
    sent_urls: set[str] = set()
    tts_chunks: list[bytes] = []
    tts_voice_pending: Optional[bytes] = None
    native_reasoning_accum = ""

    async def flush_buf_if_any() -> Optional[str]:
        nonlocal buf, parts_sent, outbound_count, last_flush
        if not buf:
            return None
        flush_chars = len(buf)
        logger.debug(
            "[MindBot] dify_sse_buffer_flush %s reason=coalesce chunk_chars=%s "
            "full_acc_chars=%s",
            pipeline_ctx,
            flush_chars,
            len(full),
        )
        ok, token_failed = await on_batch(buf)
        buf = ""
        if not ok:
            return "token_failed" if token_failed else "send_failed"
        parts_sent += 1
        outbound_count += 1
        last_flush = time.monotonic()
        return None

    async def send_media_now(kind: str, payload: dict[str, Any]) -> Optional[str]:
        nonlocal media_sent, outbound_count
        if not use_media or not on_media:
            return None
        if max_media > 0 and media_sent >= max_media:
            logger.warning(
                "[MindBot] dify_sse_max_media %s cap=%s",
                pipeline_ctx,
                max_media,
            )
            return None
        ok, token_failed = await on_media(kind, payload)
        if not ok:
            return "token_failed" if token_failed else "send_failed"
        media_sent += 1
        outbound_count += 1
        return None

    async def enqueue_or_send_file(
        url: str,
        type_s: str,
        filename: str,
        *,
        immediate: bool,
    ) -> Optional[str]:
        if url in sent_urls:
            return None
        sent_urls.add(url)
        if is_image_file_type(type_s):
            if immediate:
                return await send_media_now("image", {"url": url})
            pending_after_text.append(("image", {"url": url}))
            return None
        link_md = f"[file]({url})"
        if filename:
            link_md = f"**{filename}**\n{link_md}"
        if immediate:
            return await send_media_now("markdown", {"text": link_md})
        pending_after_text.append(("markdown", {"text": link_md}))
        return None

    async def flush_pending_after_text_queue() -> Optional[str]:
        for kind, pl in pending_after_text:
            err = await send_media_now(kind, pl)
            if err:
                return err
        pending_after_text.clear()
        return None

    async def flush_tts_voice_if_any() -> Optional[str]:
        nonlocal tts_voice_pending
        if not tts_voice_pending:
            return None
        err = await send_media_now(
            "audio",
            {"bytes": tts_voice_pending, "duration_ms": 0},
        )
        tts_voice_pending = None
        return err

    _active_conv_id = conversation_id
    _stream_started = False

    async for ev in dify.stream_chat(
        message=text,
        user_id=user_id,
        conversation_id=_active_conv_id,
        files=files,
        auto_generate_name=False,
        inputs=inputs,
    ):
        if not _stream_started:
            _stream_started = True
            if on_stream_started is not None:
                on_stream_started()
        evt = ev.get("event")
        cid = ev.get("conversation_id")
        if isinstance(cid, str) and cid.strip():
            conv_id = cid.strip()

        if evt == "error":
            err = ev.get("message") or ev.get("error") or "dify stream error"
            code = ev.get("code")
            status = ev.get("status")
            if (
                _active_conv_id
                and _stream_error_is_conversation_not_exists(ev)
                and on_stale_conversation is not None
            ):
                logger.warning(
                    "[MindBot] dify_sse_stale_conversation %s retry_without_conv",
                    pipeline_ctx,
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
                    on_stale_conversation=None,
                    pipeline_ctx=pipeline_ctx,
                    on_media=on_media,
                    on_message_replace=on_message_replace,
                    on_stream_started=on_stream_started,
                )
            logger.warning(
                "[MindBot] dify_sse_error_event %s err=%s code=%s status=%s",
                pipeline_ctx,
                err,
                code,
                status,
            )
            return full, conv_id, "dify_error", usage_snapshot, native_reasoning_accum

        if evt == "ping":
            continue

        if evt == "agent_thought":
            thought_piece = _extract_agent_thought_text(ev)
            if thought_piece:
                if native_reasoning_accum:
                    native_reasoning_accum = native_reasoning_accum + "\n\n" + thought_piece
                else:
                    native_reasoning_accum = thought_piece
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
                wf_file_hints.extend(workflow_outputs_file_hints(outputs))
            continue

        if evt == "message_replace":
            repl = ev.get("answer") or ""
            if outbound_count > 0:
                logger.warning(
                    "[MindBot] dify_sse_message_replace %s prior_outbound_batches=%s",
                    pipeline_ctx,
                    outbound_count,
                )
            logger.info(
                "[MindBot] dify_sse_message_replace %s new_answer_chars=%s buf_cleared=1",
                pipeline_ctx,
                len(repl) if isinstance(repl, str) else 0,
            )
            if on_message_replace is not None:
                await on_message_replace()
            full = repl
            buf = ""
            saw_answer = bool(repl.strip())
            # Align with answer reset: prior ``agent_thought`` chunks belonged to the
            # discarded stream and must not merge into ``format_mindbot_reply_for_dingtalk``.
            native_reasoning_accum = ""
            continue

        if evt == "message_file" and use_media:
            parsed = parse_message_file_event(ev)
            if not parsed:
                continue
            url = parsed["url"]
            type_s = str(parsed.get("type") or "document")
            fn = str(parsed.get("filename") or "")
            immediate = not defer_to_end
            if not defer_to_end:
                err_t = await flush_buf_if_any()
                if err_t:
                    return full, conv_id, err_t, usage_snapshot, native_reasoning_accum
            err_t = await enqueue_or_send_file(
                url, type_s, fn, immediate=immediate
            )
            if err_t:
                return full, conv_id, err_t, usage_snapshot, native_reasoning_accum
            saw_answer = True
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
                flush_reason = (
                    "min_chars" if len(to_send) >= min_chars else "flush_interval"
                )
                buf = ""
                last_flush = time.monotonic()
                logger.debug(
                    "[MindBot] dify_sse_buffer_flush %s reason=%s chunk_chars=%s "
                    "batch_index=%s full_acc_chars=%s",
                    pipeline_ctx,
                    flush_reason,
                    len(to_send),
                    parts_sent + 1,
                    len(full),
                )
                ok, token_failed = await on_batch(to_send)
                if not ok:
                    return (
                        full,
                        conv_id,
                        "token_failed" if token_failed else "send_failed",
                        usage_snapshot,
                        native_reasoning_accum,
                    )
                parts_sent += 1
                outbound_count += 1
            continue

        if use_media and tts_enabled and evt == "tts_message":
            chunk = parse_tts_audio_base64_chunk(ev)
            if chunk:
                _tts_max_bytes = env_int("MINDBOT_TTS_MAX_BYTES", 10 * 1024 * 1024)
                _tts_current = sum(len(c) for c in tts_chunks)
                if _tts_current + len(chunk) <= _tts_max_bytes:
                    tts_chunks.append(chunk)
                else:
                    logger.warning(
                        "[MindBot] tts_chunks_cap_reached total_bytes=%s limit=%s — dropping chunk",
                        _tts_current,
                        _tts_max_bytes,
                    )
            continue

        if use_media and tts_enabled and evt == "tts_message_end":
            audio_bytes = b"".join(tts_chunks)
            tts_chunks.clear()
            if audio_bytes:
                tts_voice_pending = audio_bytes
                saw_answer = True
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
                    for idx, part in enumerate(
                        _split_reply_chunks(full, _OPENAPI_TEXT_CHUNK),
                        start=1,
                    ):
                        if outbound_count >= max_parts:
                            logger.warning(
                                "[MindBot] dify_sse_max_parts %s defer_mode batches=%s",
                                pipeline_ctx,
                                outbound_count,
                            )
                            break
                        logger.debug(
                            "[MindBot] dify_sse_buffer_flush %s reason=defer_to_end "
                            "part=%s chunk_chars=%s full_acc_chars=%s",
                            pipeline_ctx,
                            idx,
                            len(part),
                            len(full),
                        )
                        ok, token_failed = await on_batch(part)
                        if not ok:
                            return (
                                full,
                                conv_id,
                                "token_failed" if token_failed else "send_failed",
                                usage_snapshot,
                                native_reasoning_accum,
                            )
                        outbound_count += 1
                deferred_flushed = True
            else:
                err_t = await flush_buf_if_any()
                if err_t:
                    return full, conv_id, err_t, usage_snapshot, native_reasoning_accum

            for hint in wf_file_hints:
                u = hint.get("url")
                if not isinstance(u, str) or not u.strip():
                    continue
                t = str(hint.get("type") or "document")
                fn = str(hint.get("filename") or "")
                err_t = await enqueue_or_send_file(
                    u.strip(), t, fn, immediate=False
                )
                if err_t:
                    return full, conv_id, err_t, usage_snapshot, native_reasoning_accum
                saw_answer = True
            wf_file_hints.clear()

            err_t = await flush_pending_after_text_queue()
            if err_t:
                return full, conv_id, err_t, usage_snapshot, native_reasoning_accum
            err_t = await flush_tts_voice_if_any()
            if err_t:
                return full, conv_id, err_t, usage_snapshot, native_reasoning_accum
            continue

    if not full.strip() and wf_fallback_text:
        full = wf_fallback_text
        saw_answer = bool(full.strip())

    saw_content = (
        saw_answer
        or bool(media_sent)
        or bool(pending_after_text)
        or bool(tts_voice_pending)
        or bool(native_reasoning_accum.strip())
    )
    if not saw_content and not full.strip():
        logger.warning(
            "[MindBot] dify_sse_outcome %s outcome=dify_empty",
            pipeline_ctx,
        )
        return "", conv_id, "dify_empty", usage_snapshot, native_reasoning_accum

    if defer_to_end and not deferred_flushed and full.strip():
        for idx, part in enumerate(
            _split_reply_chunks(full, _OPENAPI_TEXT_CHUNK),
            start=1,
        ):
            if outbound_count >= max_parts:
                break
            logger.debug(
                "[MindBot] dify_sse_buffer_flush %s reason=defer_tail part=%s "
                "chunk_chars=%s full_acc_chars=%s",
                pipeline_ctx,
                idx,
                len(part),
                len(full),
            )
            ok, token_failed = await on_batch(part)
            if not ok:
                return (
                    full,
                    conv_id,
                    "token_failed" if token_failed else "send_failed",
                    usage_snapshot,
                    native_reasoning_accum,
                )
            outbound_count += 1

    if buf:
        logger.debug(
            "[MindBot] dify_sse_buffer_flush %s reason=stream_end_residual chunk_chars=%s "
            "full_acc_chars=%s",
            pipeline_ctx,
            len(buf),
            len(full),
        )
        ok, token_failed = await on_batch(buf)
        if not ok:
            return (
                full,
                conv_id,
                "token_failed" if token_failed else "send_failed",
                usage_snapshot,
                native_reasoning_accum,
            )
        outbound_count += 1
    elif full.strip() and outbound_count == 0:
        for idx, part in enumerate(
            _split_reply_chunks(full, _OPENAPI_TEXT_CHUNK),
            start=1,
        ):
            if parts_sent >= max_parts:
                logger.warning(
                    "[MindBot] dify_sse_max_parts %s workflow_or_single parts_sent=%s",
                    pipeline_ctx,
                    parts_sent,
                )
                break
            logger.debug(
                "[MindBot] dify_sse_buffer_flush %s reason=workflow_or_zero_batch "
                "part=%s chunk_chars=%s full_acc_chars=%s",
                pipeline_ctx,
                idx,
                len(part),
                len(full),
            )
            ok, token_failed = await on_batch(part)
            if not ok:
                return (
                    full,
                    conv_id,
                    "token_failed" if token_failed else "send_failed",
                    usage_snapshot,
                    native_reasoning_accum,
                )
            parts_sent += 1
            outbound_count += 1

    if use_media:
        err_t = await flush_pending_after_text_queue()
        if err_t:
            return full, conv_id, err_t, usage_snapshot, native_reasoning_accum
        err_t = await flush_tts_voice_if_any()
        if err_t:
            return full, conv_id, err_t, usage_snapshot, native_reasoning_accum

    logger.debug(
        "[MindBot] dify_sse_outcome %s outcome=ok reply_chars=%s dify_conv=%s "
        "outbound_batches=%s parts_sent=%s media_parts=%s usage=%s defer=%s",
        pipeline_ctx,
        len(full),
        (conv_id or "")[:32],
        outbound_count,
        parts_sent,
        media_sent,
        usage_snapshot,
        int(defer_to_end),
    )
    return full, conv_id, None, usage_snapshot, native_reasoning_accum
