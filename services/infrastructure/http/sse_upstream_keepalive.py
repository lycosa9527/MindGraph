"""SSE upstream keepalive bridge for slow streaming backends (e.g. Dify vision)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from typing import TypeVar

T = TypeVar("T")


class _UpstreamEnd:
    """Sentinel marking completion of the upstream async iterator."""


_END = _UpstreamEnd()


async def iter_upstream_with_keepalive(
    upstream: AsyncIterator[T],
    *,
    interval_seconds: float = 25.0,
) -> AsyncGenerator[T | None, None]:
    """
    Yield items from *upstream*.

    When no upstream item arrives within *interval_seconds*, yield ``None`` so the
    caller can emit an SSE comment (``: keepalive\\n\\n``) and reset reverse-proxy
    read timers during long silent phases.
    """
    queue: asyncio.Queue[T | _UpstreamEnd] = asyncio.Queue()

    async def _producer() -> None:
        try:
            async for item in upstream:
                await queue.put(item)
        finally:
            await queue.put(_END)

    producer = asyncio.create_task(_producer())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval_seconds)
            except TimeoutError:
                yield None
                continue
            if isinstance(item, _UpstreamEnd):
                break
            yield item
    finally:
        producer.cancel()
        try:
            await producer
        except asyncio.CancelledError:
            pass
