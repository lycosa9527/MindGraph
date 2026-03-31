"""Mutation-idle monitor task for workshop WebSocket connections."""

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)

from services.redis.redis_client import get_redis as get_redis_client
from services.workshop.workshop_redis_keys import mutation_idle_key


async def run_mutation_idle_monitor(
    websocket: WebSocket,
    code: str,
    user_id: int,
) -> None:
    """
    Close the socket when the mutation-idle Redis key expires (no diagram edits).
    Ping does not refresh this key.
    """
    while True:
        await asyncio.sleep(30)
        redis = get_redis_client()
        if not redis:
            continue
        mut_key = mutation_idle_key(code, user_id)
        try:
            exists = await asyncio.to_thread(redis.exists, mut_key)
        except (RuntimeError, TypeError, ValueError, OSError):
            continue
        if not exists:
            try:
                await websocket.send_json(
                    {
                        "type": "kicked",
                        "reason": "mutation_idle",
                    }
                )
            except Exception as exc:
                logger.debug("Mutation idle kick notification send failed: %s", exc)
            try:
                await websocket.close(code=4002, reason="mutation idle")
            except Exception as exc:
                logger.debug("Mutation idle WebSocket close failed: %s", exc)
            return


def start_mutation_idle_monitor(
    websocket: WebSocket,
    code: str,
    user_id: int,
) -> asyncio.Task:
    """Schedule :func:`run_mutation_idle_monitor` and return the task."""
    return asyncio.create_task(
        run_mutation_idle_monitor(websocket, code, user_id),
    )
