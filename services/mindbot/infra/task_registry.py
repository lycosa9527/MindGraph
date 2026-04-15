"""Track asyncio tasks spawned by MindBot so shutdown can wait for in-flight pipelines."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Set

from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

_active: Set[asyncio.Task] = set()


def register(task: asyncio.Task) -> None:
    """Register a background task; removes itself when done."""
    _active.add(task)

    def _discard(_t: asyncio.Task) -> None:
        _active.discard(_t)

    task.add_done_callback(_discard)


async def drain(timeout_s: float = 30.0) -> None:
    """Wait for registered tasks, up to ``timeout_s``.

    If ``MINDBOT_SHUTDOWN_CANCEL_PENDING`` is true and tasks remain after the
    wait, they are cancelled and gathered (best-effort).
    """
    if not _active:
        return
    pending = set(_active)
    done, still = await asyncio.wait(pending, timeout=timeout_s)
    if still:
        logger.warning(
            "[MindBot] task_registry drain: %s task(s) still pending after %.1fs",
            len(still),
            timeout_s,
        )
        if env_bool("MINDBOT_SHUTDOWN_CANCEL_PENDING", False):
            for t in still:
                t.cancel()
            try:
                cancel_wait = float(os.getenv("MINDBOT_SHUTDOWN_CANCEL_JOIN_S", "5"))
                results = await asyncio.wait_for(
                    asyncio.gather(*still, return_exceptions=True),
                    timeout=cancel_wait,
                )
                errors = [r for r in results if isinstance(r, Exception)]
                logger.warning(
                    "[MindBot] task_registry drain: cancelled %s task(s), %s raised exceptions",
                    len(still),
                    len(errors),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[MindBot] task_registry drain: cancel gather timed out for %s task(s)",
                    len(still),
                )
    else:
        logger.debug("[MindBot] task_registry drain: completed %s task(s)", len(done))
