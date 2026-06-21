"""
LLM chat dispatch with optional autocomplete phase signals.

When ``phase_emit`` is provided, uses ``chat_stream`` and emits ``waiting`` before
the LLM call and ``streaming`` on the first content token. Otherwise delegates to
blocking ``chat()`` unchanged.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Optional

from services.llm import llm_service

PhaseEmitter = Callable[[str], Awaitable[None]]

_LLM_DISPATCH_KEYS = (
    "user_id",
    "organization_id",
    "request_type",
    "endpoint_path",
    "diagram_type",
)


def llm_dispatch_kwargs(source: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Build keyword args for ``dispatch_llm_chat`` from agent kwargs."""
    out = {key: source[key] for key in _LLM_DISPATCH_KEYS if key in source}
    out.update(extra)
    out["phase_emit"] = source.get("phase_emit")
    return out


async def dispatch_llm_chat(
    *,
    phase_emit: Optional[PhaseEmitter],
    prompt: str,
    model: str,
    **kwargs: Any,
) -> str | dict[Any, Any]:
    """Run LLM chat; stream with phase signals when ``phase_emit`` is set."""
    llm_kwargs = {key: value for key, value in kwargs.items() if key != "phase_emit"}
    if phase_emit is None:
        return await llm_service.chat(prompt=prompt, model=model, **llm_kwargs)

    await phase_emit("waiting")

    buffer_parts: list[str] = []
    saw_streaming = False

    async for chunk in llm_service.chat_stream(
        prompt=prompt,
        model=model,
        yield_structured=True,
        **llm_kwargs,
    ):
        if isinstance(chunk, dict):
            chunk_type = chunk.get("type")
            if chunk_type != "token":
                continue
            content = chunk.get("content") or ""
        else:
            content = str(chunk)

        if not content:
            continue

        if not saw_streaming:
            await phase_emit("streaming")
            saw_streaming = True
        buffer_parts.append(content)

    return "".join(buffer_parts)
