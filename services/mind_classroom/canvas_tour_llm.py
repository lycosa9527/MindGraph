"""Stream canvas-tour script completions from DashScope."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from services.llm import llm_service
from services.mind_classroom.progress_log import (
    STREAM_HEARTBEAT_SEC,
    format_llm_stream_detail,
    log_job_stage,
    should_log_llm_stream,
)
from services.mind_classroom.tour_progress import patch_tour_progress

_REQUEST_TYPE = "mind_classroom_canvas_tour"


def stream_chunk_text(chunk: Any) -> tuple[str, Optional[dict[str, Any]]]:
    """Split a chat_stream item into visible text and optional usage."""
    if chunk is None:
        return "", None
    if isinstance(chunk, str):
        return chunk, None
    if not isinstance(chunk, dict):
        return "", None
    kind = chunk.get("type")
    if kind == "usage":
        usage = chunk.get("usage")
        return "", usage if isinstance(usage, dict) else None
    if kind == "thinking":
        return "", None
    content = chunk.get("content")
    if isinstance(content, str) and content:
        return content, None
    return "", None


async def _next_chunk(
    iterator: Any,
    *,
    job_id: Optional[str],
    branch: Optional[int],
    branch_total: Optional[int],
    branch_label: str,
    started: float,
    chars: int,
    last_at: list[float],
) -> Any:
    """Next item from this task.

    ``chat_stream`` pins ``llm_call`` with a ``ContextVar`` token. A fresh
    ``asyncio.Task`` per chunk resets that token in another context and
    raises ``ValueError``, which fails the tour. The idle heartbeat is a
    loop timer so the generator never changes tasks.
    """
    loop = asyncio.get_running_loop()
    timer: dict[str, Optional[asyncio.TimerHandle]] = {"handle": None}

    def _fire() -> None:
        now = time.monotonic()
        _log_stream(
            job_id,
            branch=branch,
            branch_total=branch_total,
            branch_label=branch_label,
            chars=chars,
            elapsed_s=now - started,
            idle=True,
        )
        last_at[0] = now
        timer["handle"] = loop.call_later(STREAM_HEARTBEAT_SEC, _fire)

    timer["handle"] = loop.call_later(STREAM_HEARTBEAT_SEC, _fire)
    try:
        return await anext(iterator)
    finally:
        handle = timer["handle"]
        if handle is not None:
            handle.cancel()


async def stream_tour_script_text(
    *,
    prompt: str,
    model: str,
    system_message: str,
    max_tokens: int,
    temperature: float,
    user_id: Optional[int],
    organization_id: Optional[int],
    job_id: Optional[str] = None,
    celery_task_id: Optional[str] = None,
    branch: Optional[int] = None,
    branch_total: Optional[int] = None,
    branch_label: str = "",
) -> tuple[str, Optional[dict[str, Any]]]:
    """Collect one streamed script and INFO-log tokens as they arrive."""
    started = time.monotonic()
    parts: list[str] = []
    usage: Optional[dict[str, Any]] = None
    last_chars = 0
    last_at = [started]
    saw_token = False
    iterator = aiter(
        llm_service.chat_stream(
            prompt=prompt,
            model=model,
            system_message=system_message,
            max_tokens=max_tokens,
            temperature=temperature,
            user_id=user_id,
            organization_id=organization_id,
            request_type=_REQUEST_TYPE,
            use_knowledge_base=False,
            yield_structured=True,
        )
    )
    try:
        while True:
            try:
                chunk = await _next_chunk(
                    iterator,
                    job_id=job_id,
                    branch=branch,
                    branch_total=branch_total,
                    branch_label=branch_label,
                    started=started,
                    chars=sum(len(part) for part in parts),
                    last_at=last_at,
                )
            except StopAsyncIteration:
                break
            text, usage_chunk = stream_chunk_text(chunk)
            if usage_chunk is not None:
                usage = usage_chunk
            if text:
                parts.append(text)
            chars = sum(len(part) for part in parts)
            now = time.monotonic()
            first_token = bool(text) and not saw_token
            if text:
                saw_token = True
            if first_token:
                await _publish_streaming_branch(
                    job_id,
                    celery_task_id=celery_task_id,
                    branch=branch,
                    branch_label=branch_label,
                    chars=chars,
                )
            if job_id and should_log_llm_stream(
                chars=chars,
                last_chars=last_chars,
                last_at=last_at[0],
                now=now,
                first_token=first_token,
            ):
                _log_stream(
                    job_id,
                    branch=branch,
                    branch_total=branch_total,
                    branch_label=branch_label,
                    chars=chars,
                    elapsed_s=now - started,
                    first_token=first_token,
                )
                last_chars = chars
                last_at[0] = now
    finally:
        await _close_stream(iterator)
    return "".join(parts), usage


async def _close_stream(iterator: Any) -> None:
    """Close the generator in the task that has been pulling it."""
    aclose = getattr(iterator, "aclose", None)
    if aclose is None:
        return
    await aclose()


async def _publish_streaming_branch(
    job_id: Optional[str],
    *,
    celery_task_id: Optional[str],
    branch: Optional[int],
    branch_label: str,
    chars: int,
) -> None:
    if not job_id:
        return
    await patch_tour_progress(
        job_id,
        celery_task_id=celery_task_id,
        status="generating",
        stage="llm_streaming",
        phase="llm_streaming",
        branch=branch,
        branch_state="streaming",
        branch_label=branch_label,
        chars=chars,
    )


def _log_stream(
    job_id: Optional[str],
    *,
    branch: Optional[int],
    branch_total: Optional[int],
    branch_label: str,
    chars: int,
    elapsed_s: float,
    first_token: bool = False,
    idle: bool = False,
) -> None:
    if not job_id:
        return
    log_job_stage(
        job_id,
        format_llm_stream_detail(
            branch=branch,
            branch_total=branch_total,
            branch_label=branch_label,
            chars=chars,
            elapsed_s=elapsed_s,
            first_token=first_token,
            idle=idle,
        ),
        status="generating",
        phase="llm_streaming",
    )
