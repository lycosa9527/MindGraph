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
_STREAM_END = object()


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


async def _anext_or_end(iterator: Any) -> Any:
    """Next chunk, or a sentinel when the generator is finished."""
    try:
        return await anext(iterator)
    except StopAsyncIteration:
        return _STREAM_END


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
    last_at = started
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
    pending: Optional[asyncio.Task[Any]] = None
    try:
        while True:
            if pending is None:
                pending = asyncio.create_task(_anext_or_end(iterator))
            done, _waiting = await asyncio.wait({pending}, timeout=STREAM_HEARTBEAT_SEC)
            if not done:
                elapsed = time.monotonic() - started
                _log_stream(
                    job_id,
                    branch=branch,
                    branch_total=branch_total,
                    branch_label=branch_label,
                    chars=sum(len(part) for part in parts),
                    elapsed_s=elapsed,
                    idle=True,
                )
                last_at = time.monotonic()
                continue
            finished = pending
            pending = None
            chunk = finished.result()
            if chunk is _STREAM_END:
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
                last_at=last_at,
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
                last_at = now
    finally:
        await _close_stream(iterator, pending)
    return "".join(parts), usage


async def _close_stream(iterator: Any, pending: Optional[asyncio.Task[Any]]) -> None:
    """Stop a leftover next-chunk task, then close the generator once."""
    if pending is not None and not pending.done():
        pending.cancel()
        try:
            await pending
        except asyncio.CancelledError:
            pass
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
