"""
Graceful shutdown sequence extracted from FastAPI lifespan (modular teardown).

Ordering note: Redis pub/sub fan-out listeners stop before draining local WebSockets
so in-flight broadcasts are not enqueueing onto sockets that then receive GOING_AWAY.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from clients.llm import close_httpx_clients
from services.infrastructure.lifecycle.lifespan_redis_integration import (
    close_redis_connection,
    stop_fanout_listeners,
)

if TYPE_CHECKING:
    import fastapi.applications


logger = logging.getLogger(__name__)


@dataclass
class LifespanBackgroundTasks:
    """Mutable holder for asyncio tasks spawned during lifespan startup."""

    cleanup_task: Optional[asyncio.Task] = None
    workshop_cleanup_task: Optional[asyncio.Task] = None
    session_manager_task: Optional[asyncio.Task] = None
    worker_perf_task: Optional[asyncio.Task] = None
    worker_perf_stop: Optional[asyncio.Event] = None
    backup_scheduler_task: Optional[asyncio.Task] = None
    abuseipdb_scheduler_task: Optional[asyncio.Task] = None
    process_monitor_task: Optional[asyncio.Task] = None
    health_monitor_task: Optional[asyncio.Task] = None


async def run_lifespan_shutdown(
    *,
    fastapi_app: "fastapi.applications.FastAPI",
    is_main_worker: bool,
    holdings: LifespanBackgroundTasks,
) -> None:
    """Run the full teardown sequence formerly inline in lifespan()."""
    fastapi_app.state.is_shutting_down = True
    await asyncio.sleep(0.1)

    try:
        from services.mindbot.infra.task_registry import drain as mindbot_task_drain

        await mindbot_task_drain(
            timeout_s=float(os.getenv("MINDBOT_SHUTDOWN_DRAIN_TIMEOUT_S", "35")),
        )
        if is_main_worker:
            logger.info("MindBot pipeline background tasks drained")
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("MindBot task drain error: %s", exc)

    try:
        from clients.dify import close_async_dify_shared_sessions

        await close_async_dify_shared_sessions()
        if is_main_worker:
            logger.info("Async Dify shared HTTP sessions closed")
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Async Dify session close error: %s", exc)

    if holdings.cleanup_task:
        holdings.cleanup_task.cancel()
        try:
            await holdings.cleanup_task
        except asyncio.CancelledError:
            pass
        if is_main_worker:
            logger.debug("Temp image cleanup scheduler stopped")

    if holdings.workshop_cleanup_task:
        holdings.workshop_cleanup_task.cancel()
        try:
            await holdings.workshop_cleanup_task
        except asyncio.CancelledError:
            pass
        if is_main_worker:
            logger.debug("Workshop cleanup scheduler stopped")

    if holdings.session_manager_task:
        holdings.session_manager_task.cancel()
        try:
            await holdings.session_manager_task
        except asyncio.CancelledError:
            pass
        if is_main_worker:
            logger.debug("Workshop session manager idle monitor stopped")

    if holdings.worker_perf_stop is not None:
        holdings.worker_perf_stop.set()
    if holdings.worker_perf_task:
        holdings.worker_perf_task.cancel()
        try:
            await holdings.worker_perf_task
        except asyncio.CancelledError:
            pass

    if holdings.backup_scheduler_task:
        holdings.backup_scheduler_task.cancel()
        try:
            await holdings.backup_scheduler_task
        except asyncio.CancelledError:
            pass

    if holdings.abuseipdb_scheduler_task:
        holdings.abuseipdb_scheduler_task.cancel()
        try:
            await holdings.abuseipdb_scheduler_task
        except asyncio.CancelledError:
            pass

    if holdings.process_monitor_task:
        try:
            from services.infrastructure.monitoring.process_monitor import get_process_monitor

            proc_mon = get_process_monitor()
            await proc_mon.stop()
        except Exception as exc:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to stop process monitor: %s", exc)
        holdings.process_monitor_task.cancel()
        try:
            await holdings.process_monitor_task
        except asyncio.CancelledError:
            pass
        if is_main_worker:
            logger.info("Process monitor stopped")

    if holdings.health_monitor_task:
        try:
            from services.infrastructure.monitoring.health_monitor import get_health_monitor

            health_monitor = get_health_monitor()
            await health_monitor.stop()
        except Exception as exc:  # pylint: disable=broad-except
            if is_main_worker:
                logger.warning("Failed to stop health monitor: %s", exc)
        holdings.health_monitor_task.cancel()
        try:
            await holdings.health_monitor_task
        except asyncio.CancelledError:
            pass
        if is_main_worker:
            logger.info("Health monitor stopped")

    try:
        from services.llm import llm_service

        llm_service.cleanup()
        if is_main_worker:
            logger.info("LLM Service cleaned up")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to cleanup LLM Service: %s", exc)

    try:
        from services.utils.update_notifier import update_notifier

        update_notifier.shutdown()
        if is_main_worker:
            logger.info("Update notifier flushed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to flush update notifier: %s", exc)

    try:
        from services.redis.redis_token_buffer import get_token_tracker

        token_tracker = get_token_tracker()
        await token_tracker.flush()
        if is_main_worker:
            logger.info("TokenTracker flushed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to flush TokenTracker: %s", exc)

    try:
        from services.redis.cache.redis_diagram_cache import get_diagram_cache

        diagram_cache = get_diagram_cache()
        await diagram_cache.flush()
        if is_main_worker:
            logger.info("Diagram cache flushed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to flush diagram cache: %s", exc)

    try:
        from services.auth.sms_middleware import shutdown_sms_service

        await shutdown_sms_service()
        if is_main_worker:
            logger.info("SMS service shut down")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to shutdown SMS service: %s", exc)

    try:
        await close_httpx_clients()
        if is_main_worker:
            logger.info("LLM httpx clients closed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to close httpx clients: %s", exc)

    try:
        from services.online_collab.spec.online_collab_live_flush import (  # pylint: disable=import-outside-toplevel
            cancel_all_pending_live_spec_db_flushes,
        )
        from services.online_collab.spec.online_collab_live_spec_shutdown import (  # pylint: disable=import-outside-toplevel
            flush_all_live_specs_on_shutdown,
        )

        await cancel_all_pending_live_spec_db_flushes()
        await flush_all_live_specs_on_shutdown()
    except Exception as live_flush_exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning(
                "[LiveSpec] Shutdown flush skipped or partial: %s",
                live_flush_exc,
            )

    try:
        from config.database import close_db

        await close_db()
        if is_main_worker:
            logger.info("Database connections closed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to close database: %s", exc)

    await stop_fanout_listeners(is_main_worker)

    try:
        from utils.ws_session_registry import _registry as _ws_registry  # pylint: disable=import-outside-toplevel

        await _ws_registry.close_all(code=1001, reason="Server shutting down")
        await asyncio.sleep(0.5)
        if is_main_worker:
            logger.info("WebSocket sessions drained")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("WebSocket graceful drain failed: %s", exc)

    close_redis_connection(is_main_worker)

    try:
        from services.mindbot.platforms.dingtalk.cards.stream_client import get_stream_manager

        await get_stream_manager().stop_all()
        if is_main_worker:
            logger.info("DingTalk Stream SDK clients stopped")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to stop DingTalk Stream SDK clients: %s", exc)

    try:
        from services.mindbot.infra.http_client import close_mindbot_http_sessions

        await close_mindbot_http_sessions()
        if is_main_worker:
            logger.info("MindBot HTTP sessions closed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to close MindBot HTTP sessions: %s", exc)

    try:
        from services.mindbot.infra.redis_async import close_async_redis

        await close_async_redis()
        if is_main_worker:
            logger.info("MindBot async Redis client closed")
    except Exception as exc:  # pylint: disable=broad-except
        if is_main_worker:
            logger.warning("Failed to close MindBot async Redis client: %s", exc)
