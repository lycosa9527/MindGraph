"""
Health check endpoints for MindGraph application.

Provides endpoints to check the health status of various system components:
- Basic health check
- Redis health check
- Database health check
- Comprehensive health check (all components)
- Application status endpoint

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Dict, cast

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from config.database import DATABASE_URL, async_engine, check_integrity_async, engine
from config.settings import config
from models.domain.auth import User
from models.responses import DatabaseHealthResponse
from services.infrastructure.lifecycle.app_runtime import get_uptime_seconds
from services.infrastructure.monitoring.health_checks import (
    check_application_health,
    check_processes_health,
)
from services.infrastructure.monitoring.health_checks.processes import (
    processes_health_payload,
)
from services.infrastructure.monitoring.redis_info_cache import (
    cached_redis_info as _cached_redis_info,
    fetch_redis_memory_stats as _fetch_redis_memory_stats,
)
from services.infrastructure.monitoring.ws_metrics import (
    collab_ws_metrics_alerts,
    get_ws_metrics_snapshot,
    ws_metrics_prometheus_text,
)
from services.infrastructure.recovery.database_check_state import (
    get_database_check_state_manager,
)
from services.llm import llm_service
from services.online_collab.spec.online_collab_live_spec_shutdown import (
    collab_live_spec_durability_alerts,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _update_overall_status(current_status: str, current_code: int, check_status: str):
    """
    Helper function to update overall health status based on individual check results.

    Args:
        current_status: Current overall status ("healthy", "degraded", "unhealthy")
        current_code: Current HTTP status code (200, 503, 500)
        check_status: Status of the individual check ("healthy", "unhealthy",
            "error", "unavailable", "skipped", "unknown")

    Returns:
        Tuple of (updated_status, updated_code)
    """
    if check_status in ("healthy", "skipped"):
        return current_status, current_code
    if check_status == "error" and current_code == 200:
        # First error when system was healthy -> mark as unhealthy with 500
        return "unhealthy", 500
    if check_status == "unknown":
        # Unknown status treated as error for safety
        if current_status == "healthy":
            return "degraded", 503
        return current_status, current_code
    if check_status in ("unhealthy", "unavailable", "error"):
        # Degrade from healthy, or maintain current degraded/unhealthy state
        if current_status == "healthy":
            return "degraded", 503
        return current_status, current_code
    return current_status, current_code


async def _check_application_health() -> Dict[str, Any]:
    """Check application health status."""
    return await check_application_health()


async def _fetch_redis_hotkeys(redis_client: Any) -> Any:
    """Fetch hot keys using HOTKEYS (Redis >= 8.6). Returns None on older versions."""
    try:
        return await redis_client.execute_command("HOTKEYS")
    except REDIS_ERRORS:
        return None


async def _check_redis_health() -> Dict[str, Any]:
    """Check Redis health status with timeout using the native async client."""
    try:
        if not is_redis_available():
            return {"status": "unavailable", "message": "Redis not connected"}

        redis_client = get_async_redis()
        if redis_client is None:
            return {"status": "unavailable", "message": "Async Redis client not initialized"}

        ping_result = await asyncio.wait_for(
            cast(Awaitable[bool], redis_client.ping()),
            timeout=2.0,
        )

        if ping_result:
            info = await asyncio.wait_for(_cached_redis_info(redis_client, "server"), timeout=2.0)
            if not info:
                return {"status": "unhealthy", "message": "Redis info failed"}

            memory = await asyncio.wait_for(
                _fetch_redis_memory_stats(redis_client),
                timeout=2.0,
            )
            hotkeys = await asyncio.wait_for(
                _fetch_redis_hotkeys(redis_client),
                timeout=2.0,
            )

            result: Dict[str, Any] = {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "memory": memory,
            }
            if hotkeys is not None:
                result["hotkeys"] = hotkeys
            return result

        return {"status": "unhealthy", "message": "Ping failed"}
    except asyncio.TimeoutError:
        logger.warning("Redis health check timed out")
        return {"status": "error", "error": "Health check timed out"}
    except REDIS_ERRORS as e:
        logger.error("Redis health check failed: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


async def _check_database_health() -> Dict[str, Any]:
    """Check database health status with state management."""
    state_manager = get_database_check_state_manager()
    check_started = False

    try:
        # Check if a database check is already in progress
        if await state_manager.is_check_in_progress():
            logger.debug("Database check already in progress, returning in-progress status")
            return {
                "status": "healthy",
                "database_healthy": True,
                "database_message": "Database check in progress (long-running operation)",
                "database_stats": {},
            }

        # Try to start a new check
        check_started = await state_manager.start_check()
        if not check_started:
            # Another check started between our check and start_check call
            logger.debug("Database check started by another process, returning in-progress status")
            return {
                "status": "healthy",
                "database_healthy": True,
                "database_message": "Database check in progress (long-running operation)",
                "database_stats": {},
            }

        # Add timeout protection for database check
        async def _do_check():
            is_healthy = await check_integrity_async()

            if is_healthy:
                message = "Database connection and integrity check passed"
            else:
                message = "Database integrity check failed"

            current_stats: Dict[str, Any] = {}
            try:
                if "postgresql" in DATABASE_URL.lower():
                    async with async_engine.connect() as conn:
                        db_name = DATABASE_URL.split("/")[-1].split("?")[0]
                        result = await conn.execute(
                            text("SELECT pg_size_pretty(pg_database_size(:db_name)) as size"),
                            {"db_name": db_name},
                        )
                        size_row = result.fetchone()
                        if size_row:
                            current_stats["size"] = size_row[0] if size_row else "unknown"
            except DATABASE_ERRORS as e:
                logger.debug("Failed to get database stats: %s", e)

            current_stats["pool"] = _collect_pool_stats(async_engine.pool)
            current_stats["sync_pool"] = _collect_pool_stats(engine.pool)

            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "database_healthy": is_healthy,
                "database_message": message,
                "database_stats": current_stats,
            }

        result = await asyncio.wait_for(_do_check(), timeout=5.0)
        # Mark check as completed successfully
        await state_manager.complete_check(success=result.get("database_healthy", False))
        return result

    except asyncio.TimeoutError:
        # Check if check is still in progress (legitimate long-running check)
        if await state_manager.is_check_in_progress():
            logger.info(
                "Database health check timed out but check is still in progress (long-running operation, not an error)"
            )
            return {
                "status": "healthy",
                "database_healthy": True,
                "database_message": "Database check in progress (long-running operation)",
                "database_stats": {},
            }

        # Real timeout - check is not in progress, something went wrong
        logger.warning("Database health check timed out (check not in progress)")
        if check_started:
            await state_manager.complete_check(success=False)
        return {"status": "error", "error": "Health check timed out"}
    except ImportError as e:
        logger.error("Database check module not available: %s", e)
        if check_started:
            await state_manager.complete_check(success=False)
        return {
            "status": "unavailable",
            "message": "Database check module not available",
        }
    except DATABASE_ERRORS as e:
        logger.error("Database health check failed: %s", e, exc_info=True)
        if check_started:
            await state_manager.complete_check(success=False)
        return {"status": "error", "error": str(e)}


async def _check_processes_health() -> Dict[str, Any]:
    """Check process monitor health status."""
    return await check_processes_health()


async def _check_llm_health() -> Dict[str, Any]:
    """Check LLM services health status with timeout."""
    try:
        # Add timeout protection (LLM checks can take 5+ seconds per model)
        health_data = await asyncio.wait_for(
            llm_service.health_check(),
            timeout=30.0,  # Allow up to 30 seconds for all models
        )

        metrics = llm_service.get_performance_metrics()
        circuit_states = {}
        if metrics and isinstance(metrics, dict):
            circuit_states = {
                model: data.get("circuit_state", "closed") for model, data in metrics.items() if isinstance(data, dict)
            }

        available_models = health_data.get("available_models", [])
        unhealthy_count = sum(
            1 for model in available_models if model in health_data and health_data[model].get("status") != "healthy"
        )

        return {
            "status": "healthy" if unhealthy_count == 0 else "degraded",
            "available_models": available_models,
            "healthy_count": len(available_models) - unhealthy_count,
            "unhealthy_count": unhealthy_count,
            "total_models": len(available_models),
            "circuit_states": circuit_states,
            "health_data": health_data,
        }
    except asyncio.TimeoutError:
        logger.warning("LLM health check timed out")
        return {
            "status": "error",
            "error": "Health check timed out (exceeded 30 seconds)",
        }
    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("LLM health check failed: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "ok", "version": config.version}


@router.get("/health/ready")
async def readiness_probe(request: Request):
    """
    Readiness for load balancers and rolling deploys.

    Returns 503 while this worker is in the lifespan shutdown path so ingress
    can stop sending **new** HTTP traffic; existing WebSockets still drain per
    shutdown order in ``lifespan``.
    """
    if getattr(request.app.state, "is_shutting_down", False):
        return JSONResponse(
            status_code=503,
            content={
                "status": "draining",
                "detail": "Worker is shutting down",
            },
        )
    return {"status": "ready", "version": config.version}


@router.get("/health/websocket")
async def websocket_metrics_check(_current_user: User = Depends(get_current_user)):
    """
    WebSocket counters (per process) and optional Redis aggregate active count.
    Requires authentication.
    """
    snap = await get_ws_metrics_snapshot()
    alerts = collab_ws_metrics_alerts(snap)
    try:
        alerts.extend(await collab_live_spec_durability_alerts())
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        logger.debug("[WSMetrics] live-spec durability alerts skipped: %s", exc)
    for token in alerts:
        logger.warning("[WSMetrics][collab_alert] %s", token)
    snap["collab_alerts"] = alerts
    return snap


@router.get("/metrics")
async def prometheus_metrics(_current_user: User = Depends(get_current_user)):
    """Authenticated Prometheus text-format metrics for collaboration SLOs."""
    snap = await get_ws_metrics_snapshot()
    return Response(
        content=ws_metrics_prometheus_text(snap),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/health/redis")
async def redis_health_check(_current_user: User = Depends(get_current_user)):
    """
    Redis health check endpoint.

    Returns Redis connection status, memory usage, and hot keys (Redis >= 8.6).
    All Redis I/O uses the native async client with a 2-second timeout so the
    endpoint never blocks the event loop or hangs indefinitely.
    """
    if not is_redis_available():
        return {"status": "unavailable", "message": "Redis not connected"}

    redis_client = get_async_redis()
    if redis_client is None:
        return {"status": "unavailable", "message": "Async Redis client not initialized"}

    try:
        ping_ok = await asyncio.wait_for(
            cast(Awaitable[bool], redis_client.ping()),
            timeout=2.0,
        )
        if not ping_ok:
            return {"status": "unhealthy", "message": "Ping failed"}

        info = await asyncio.wait_for(_cached_redis_info(redis_client, "server"), timeout=2.0)

        memory = await asyncio.wait_for(
            _fetch_redis_memory_stats(redis_client),
            timeout=2.0,
        )
        hotkeys = await asyncio.wait_for(
            _fetch_redis_hotkeys(redis_client),
            timeout=2.0,
        )

        result: Dict[str, Any] = {
            "status": "healthy",
            "version": info.get("redis_version", "unknown"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "memory": memory,
        }
        if hotkeys is not None:
            result["hotkeys"] = hotkeys
        return result

    except asyncio.TimeoutError:
        return {"status": "unhealthy", "message": "Redis health check timed out"}
    except REDIS_ERRORS as exc:
        return {"status": "error", "error": str(exc)}


def _collect_pool_stats(pool_obj: Any) -> Dict[str, Any]:
    """Snapshot a SQLAlchemy ``QueuePool`` for the health endpoint (G4).

    Returns ``{}`` on any error so a probe failure on the introspection side
    never poisons the response.  All pool methods are synchronous and very
    cheap (in-memory counters), so this is safe to call from async contexts
    without offloading.
    """
    try:
        size = pool_obj.size()
        checked_in = pool_obj.checkedin()
        checked_out = pool_obj.checkedout()
        overflow = pool_obj.overflow()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[health] pool stats unavailable: %s", exc)
        return {}

    return {
        "size": int(size),
        "checked_in": int(checked_in),
        "checked_out": int(checked_out),
        "overflow": int(overflow),
        "total": int(size) + int(overflow),
    }


async def _async_database_health_check() -> Dict[str, Any]:
    """Run the database health probe natively against the async engine."""
    is_healthy = await check_integrity_async()
    message = "Database connection and integrity check passed" if is_healthy else "Database integrity check failed"

    current_stats: Dict[str, Any] = {}
    try:
        if "postgresql" in DATABASE_URL.lower():
            async with async_engine.connect() as conn:
                db_name = DATABASE_URL.split("/")[-1].split("?")[0]
                result = await conn.execute(
                    text("SELECT pg_size_pretty(pg_database_size(:db_name)) as size"),
                    {"db_name": db_name},
                )
                size_row = result.fetchone()
                if size_row:
                    current_stats["size"] = size_row[0] if size_row else "unknown"
    except DATABASE_ERRORS as exc:
        logger.debug("Failed to get database stats: %s", exc)

    current_stats["pool"] = _collect_pool_stats(async_engine.pool)
    current_stats["sync_pool"] = _collect_pool_stats(engine.pool)

    return {
        "is_healthy": is_healthy,
        "message": message,
        "stats": current_stats,
    }


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health_check(_current_user: User = Depends(get_current_user)):
    """
    Database health check endpoint.

    Returns database integrity status and statistics.  All DB I/O uses the
    native async engine with a 5-second timeout so the endpoint never blocks
    the event loop or hangs indefinitely.

    Returns:
        - 200 OK: Database is healthy
        - 503 Service Unavailable: Database is unhealthy or corrupted
        - 500 Internal Server Error: Health check failed
    """
    try:
        probe = await asyncio.wait_for(
            _async_database_health_check(),
            timeout=5.0,
        )

        response_data = {
            "status": "healthy" if probe["is_healthy"] else "unhealthy",
            "database_healthy": probe["is_healthy"],
            "database_message": probe["message"],
            "database_stats": probe["stats"],
            "timestamp": int(time.time()),
        }

        status_code = 200 if probe["is_healthy"] else 503
        return JSONResponse(content=response_data, status_code=status_code)

    except asyncio.TimeoutError:
        logger.warning("Database health check timed out")
        raise HTTPException(
            status_code=503,
            detail="Database health check timed out",
        ) from None
    except ImportError as exc:
        logger.error("Database check module not available: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Database health check unavailable",
        ) from exc
    except DATABASE_ERRORS as exc:
        logger.error("Database health check error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Database health check failed",
        ) from exc


@router.get("/health/all")
async def comprehensive_health_check(
    include_llm: bool = Query(False, description="Include LLM service health checks (makes actual API calls)"),
    _current_user: User = Depends(get_current_user),
):
    """
    Comprehensive health check endpoint that checks all system components.

    Checks:
    - Application status
    - Redis connection
    - Database integrity
    - Process monitoring (Qdrant, Celery, Redis)
    - LLM services (optional, disabled by default to avoid API costs)

    Args:
        include_llm: If True, includes LLM service health checks (makes actual API calls).
                     Default: False (to avoid costs and latency)

    Returns:
        - 200 OK: All systems healthy
        - 503 Service Unavailable: Some systems unhealthy (degraded state)
        - 500 Internal Server Error: Health check itself failed

    Note:
        LLM health checks make actual API calls to providers, which can:
        - Incur token costs
        - Add latency (5+ seconds per model)
        - Hit rate limits
        Use ?include_llm=true only when you need to verify LLM connectivity.
    """
    # Import app lazily to avoid circular import

    # Use single timestamp for consistency
    check_timestamp = int(time.time())
    overall_status = "healthy"
    overall_status_code = 200
    checks = {}
    errors = []

    # Execute independent checks in parallel for better performance
    tasks = [
        _check_application_health(),
        _check_redis_health(),
        _check_database_health(),
        _check_processes_health(),
    ]

    if include_llm:
        tasks.append(_check_llm_health())

    # Run all checks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    check_names = ["application", "redis", "database", "processes"]
    if include_llm:
        check_names.append("llm_services")

    for check_name, result in zip(check_names, results):
        if isinstance(result, Exception):
            logger.error(
                "%s health check raised exception: %s",
                check_name,
                result,
                exc_info=True,
            )
            checks[check_name] = {"status": "error", "error": str(result)}
            overall_status, overall_status_code = _update_overall_status(overall_status, overall_status_code, "error")
            errors.append(f"{check_name} check failed: {str(result)}")
        else:
            # Validate result structure
            if not isinstance(result, dict) or "status" not in result:
                logger.error("%s returned invalid result structure: %s", check_name, result)
                checks[check_name] = {
                    "status": "error",
                    "error": "Invalid result structure",
                }
                overall_status, overall_status_code = _update_overall_status(
                    overall_status, overall_status_code, "error"
                )
                errors.append(f"{check_name} returned invalid result")
                continue

            checks[check_name] = result
            check_status = result.get("status", "unknown")
            overall_status, overall_status_code = _update_overall_status(
                overall_status, overall_status_code, check_status
            )

            # Log errors for non-healthy checks
            if check_status not in ("healthy", "skipped"):
                error_msg = result.get("error") or result.get("message", "Unknown error")
                logger.warning(
                    "%s health check returned %s: %s",
                    check_name,
                    check_status,
                    error_msg,
                )
                if check_status == "error":
                    errors.append(f"{check_name} check failed: {error_msg}")

    # Handle skipped LLM check
    if not include_llm:
        checks["llm_services"] = {
            "status": "skipped",
            "message": (
                "LLM health check disabled by default. Use ?include_llm=true to enable (makes actual API calls)."
            ),
        }

    # Build response
    response_data = {
        "status": overall_status,
        "timestamp": check_timestamp,
        "checks": checks,
    }

    if errors:
        response_data["errors"] = errors

    # Count healthy vs unhealthy components (exclude skipped from counts)
    healthy_count = sum(1 for check in checks.values() if check.get("status") == "healthy")
    skipped_count = sum(1 for check in checks.values() if check.get("status") == "skipped")
    total_count = len(checks)
    unhealthy_count = total_count - healthy_count - skipped_count

    response_data["summary"] = {
        "healthy": healthy_count,
        "unhealthy": unhealthy_count,
        "skipped": skipped_count,
        "total": total_count,
    }

    return JSONResponse(content=response_data, status_code=overall_status_code)


@router.get("/health/processes")
async def processes_health_check(_current_user: User = Depends(get_current_user)):
    """
    Process monitor health check endpoint.

    Returns detailed status of monitored services (Qdrant, Celery, Redis)
    including metrics, restart counts, and circuit breaker status.

    Returns:
        - 200 OK: All processes healthy
        - 503 Service Unavailable: Some processes unhealthy
        - 500 Internal Server Error: Health check failed
    """
    try:
        payload = processes_health_payload()
        status_code = int(payload.pop("status_code", 200))
        payload["timestamp"] = int(time.time())
        return JSONResponse(content=payload, status_code=status_code)
    except ImportError:
        return JSONResponse(
            content={
                "status": "unavailable",
                "message": "Process monitor not available",
            },
            status_code=503,
        )
    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Process health check error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Process health check failed: {str(e)}") from e


@router.get("/status")
async def get_status():
    """Application status endpoint with metrics"""
    memory = psutil.virtual_memory()
    uptime = get_uptime_seconds()

    return {
        "status": "running",
        "framework": "FastAPI",
        "version": config.version,
        "uptime_seconds": round(uptime, 1),
        "memory_percent": round(memory.percent, 1),
        "timestamp": time.time(),
    }
