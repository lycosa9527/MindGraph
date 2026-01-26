"""
Health check endpoints for MindGraph application.

Provides endpoints to check the health status of various system components:
- Basic health check
- Redis health check
- Database health check
- Comprehensive health check (all components)
- Application status endpoint
"""

import time
import asyncio
import logging
from typing import Dict, Any

import psutil
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from config.settings import config
from config.database import check_integrity, engine, DATABASE_URL
from models.responses import DatabaseHealthResponse
from services.infrastructure.recovery.database_check_state import get_database_check_state_manager
from services.llm import llm_service
from services.redis.redis_client import is_redis_available, RedisOps
from sqlalchemy import text

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
    elif check_status == "unknown":
        # Unknown status treated as error for safety
        if current_status == "healthy":
            return "degraded", 503
        return current_status, current_code
    elif check_status in ("unhealthy", "unavailable", "error"):
        # Degrade from healthy, or maintain current degraded/unhealthy state
        if current_status == "healthy":
            return "degraded", 503
        return current_status, current_code
    return current_status, current_code


async def _check_application_health() -> Dict[str, Any]:
    """Check application health status."""
    try:
        # Import app lazily to avoid circular import
        import main  # pylint: disable=import-outside-toplevel
        app = main.app
        uptime = time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0
        return {
            "status": "healthy",
            "version": config.version,
            "uptime_seconds": round(uptime, 1)
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Application health check failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


async def _check_redis_health() -> Dict[str, Any]:
    """Check Redis health status with timeout."""
    try:
        if not is_redis_available():
            return {
                "status": "unavailable",
                "message": "Redis not connected"
            }

        # Add timeout protection
        ping_result = await asyncio.wait_for(
            asyncio.to_thread(RedisOps.ping),
            timeout=2.0
        )

        if ping_result:
            info = await asyncio.wait_for(
                asyncio.to_thread(RedisOps.info, "server"),
                timeout=2.0
            )
            # Check if info() returned empty dict (indicates failure)
            if not info:
                return {
                    "status": "unhealthy",
                    "message": "Redis info failed"
                }
            return {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        return {
            "status": "unhealthy",
            "message": "Ping failed"
        }
    except asyncio.TimeoutError:
        logger.warning("Redis health check timed out")
        return {
            "status": "error",
            "error": "Health check timed out"
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Redis health check failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


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
                "database_stats": {}
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
                "database_stats": {}
            }

        # Add timeout protection for database check
        async def _do_check():
            # Use database-agnostic integrity check
            is_healthy = await asyncio.to_thread(check_integrity)
            
            if is_healthy:
                message = "Database connection and integrity check passed"
            else:
                message = "Database integrity check failed"

            # Get basic database stats (database-agnostic)
            current_stats = {}
            try:
                # For PostgreSQL, get database size using pg_database_size
                # For other databases, skip size stats
                if "postgresql" in DATABASE_URL.lower():
                    with engine.connect() as conn:
                        # Extract database name from URL
                        db_name = DATABASE_URL.split("/")[-1].split("?")[0]
                        result = conn.execute(
                            text("SELECT pg_size_pretty(pg_database_size(:db_name)) as size"),
                            {"db_name": db_name}
                        )
                        size_row = result.fetchone()
                        if size_row:
                            current_stats = {
                                "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
                                "size": size_row[0] if size_row else "unknown"
                            }
                else:
                    # For other databases, just show connection URL (masked)
                    current_stats = {
                        "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
                    }
            except Exception as e:  # pylint: disable=broad-except
                logger.debug("Failed to get database stats: %s", e)
                # Stats are optional, continue without them

            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "database_healthy": is_healthy,
                "database_message": message,
                "database_stats": current_stats
            }

        result = await asyncio.wait_for(_do_check(), timeout=5.0)
        # Mark check as completed successfully
        await state_manager.complete_check(success=result.get("database_healthy", False))
        return result

    except asyncio.TimeoutError:
        # Check if check is still in progress (legitimate long-running check)
        if await state_manager.is_check_in_progress():
            logger.info(
                "Database health check timed out but check is still in progress "
                "(long-running operation, not an error)"
            )
            return {
                "status": "healthy",
                "database_healthy": True,
                "database_message": "Database check in progress (long-running operation)",
                "database_stats": {}
            }

        # Real timeout - check is not in progress, something went wrong
        logger.warning("Database health check timed out (check not in progress)")
        if check_started:
            await state_manager.complete_check(success=False)
        return {
            "status": "error",
            "error": "Health check timed out"
        }
    except ImportError as e:
        logger.error("Database check module not available: %s", e)
        if check_started:
            await state_manager.complete_check(success=False)
        return {
            "status": "unavailable",
            "message": "Database check module not available"
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Database health check failed: %s", e, exc_info=True)
        if check_started:
            await state_manager.complete_check(success=False)
        return {
            "status": "error",
            "error": str(e)
        }


async def _check_processes_health() -> Dict[str, Any]:
    """Check process monitor health status."""
    try:
        # pylint: disable=import-outside-toplevel
        from services.infrastructure.monitoring.process_monitor import get_process_monitor
        process_monitor = get_process_monitor()
        status = process_monitor.get_status()

        # Determine overall status
        unhealthy_count = sum(
            1 for service_status in status.values()
            if service_status.get('status') == 'unhealthy'
        )
        degraded_count = sum(
            1 for service_status in status.values()
            if service_status.get('status') == 'degraded'
        )

        overall_status = "healthy"
        if unhealthy_count > 0:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "services": status,
            "unhealthy_count": unhealthy_count,
            "degraded_count": degraded_count,
            "total_services": len(status)
        }
    except ImportError:
        return {
            "status": "unavailable",
            "message": "Process monitor not available"
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Process health check failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


async def _check_llm_health() -> Dict[str, Any]:
    """Check LLM services health status with timeout."""
    try:
        # Add timeout protection (LLM checks can take 5+ seconds per model)
        health_data = await asyncio.wait_for(
            llm_service.health_check(),
            timeout=30.0  # Allow up to 30 seconds for all models
        )

        metrics = llm_service.get_performance_metrics()
        circuit_states = {}
        if metrics and isinstance(metrics, dict):
            circuit_states = {
                model: data.get('circuit_state', 'closed')
                for model, data in metrics.items()
                if isinstance(data, dict)
            }

        available_models = health_data.get('available_models', [])
        unhealthy_count = sum(
            1 for model in available_models
            if model in health_data
            and health_data[model].get('status') != 'healthy'
        )

        return {
            "status": "healthy" if unhealthy_count == 0 else "degraded",
            "available_models": available_models,
            "healthy_count": len(available_models) - unhealthy_count,
            "unhealthy_count": unhealthy_count,
            "total_models": len(available_models),
            "circuit_states": circuit_states,
            "health_data": health_data
        }
    except asyncio.TimeoutError:
        logger.warning("LLM health check timed out")
        return {
            "status": "error",
            "error": "Health check timed out (exceeded 30 seconds)"
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("LLM health check failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "ok", "version": config.version}


@router.get("/health/redis")
async def redis_health_check():
    """
    Redis health check endpoint.

    Returns Redis connection status.
    """
    if not is_redis_available():
        return {
            "status": "unavailable",
            "message": "Redis not connected"
        }

    try:
        # Test connection
        if RedisOps.ping():
            info = RedisOps.info("server")
            return {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        return {
            "status": "unhealthy",
            "message": "Ping failed"
        }
    except Exception as e:  # pylint: disable=broad-except
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health_check():
    """
    Database health check endpoint.

    Returns database integrity status and statistics.

    Note: This endpoint performs a fast integrity check. For detailed backup
    information, use the admin panel or recovery tools.

    Returns:
        - 200 OK: Database is healthy
        - 503 Service Unavailable: Database is unhealthy or corrupted
        - 500 Internal Server Error: Health check failed
    """
    try:
        # Database-agnostic integrity check
        is_healthy = check_integrity()
        
        if is_healthy:
            message = "Database connection and integrity check passed"
        else:
            message = "Database integrity check failed"

        # Get basic database stats (database-agnostic)
        current_stats = {}
        try:
            # For PostgreSQL, get database size using pg_database_size
            if "postgresql" in DATABASE_URL.lower():
                with engine.connect() as conn:
                    # Extract database name from URL
                    db_name = DATABASE_URL.split("/")[-1].split("?")[0]
                    result = conn.execute(
                        text("SELECT pg_size_pretty(pg_database_size(:db_name)) as size"),
                        {"db_name": db_name}
                    )
                    size_row = result.fetchone()
                    if size_row:
                        current_stats = {
                            "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
                            "size": size_row[0] if size_row else "unknown"
                        }
            else:
                # For other databases, just show connection URL (masked)
                current_stats = {
                    "database_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
                }
        except Exception as e:  # pylint: disable=broad-except
            logger.debug("Failed to get database stats: %s", e)
            # Stats are optional, continue without them

        response_data = {
            "status": "healthy" if is_healthy else "unhealthy",
            "database_healthy": is_healthy,
            "database_message": message,
            "database_stats": current_stats,
            "timestamp": int(time.time())
        }

        # Return appropriate HTTP status code
        status_code = 200 if is_healthy else 503

        return JSONResponse(
            content=response_data,
            status_code=status_code
        )

    except ImportError as e:
        logger.error("Database check module not available: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Database health check unavailable"
        ) from e
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Database health check error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database health check failed: {str(e)}"
        ) from e


@router.get("/health/all")
async def comprehensive_health_check(
    include_llm: bool = Query(False, description="Include LLM service health checks (makes actual API calls)")
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
            logger.error("%s health check raised exception: %s", check_name, result, exc_info=True)
            checks[check_name] = {
                "status": "error",
                "error": str(result)
            }
            overall_status, overall_status_code = _update_overall_status(
                overall_status, overall_status_code, "error"
            )
            errors.append(f"{check_name} check failed: {str(result)}")
        else:
            # Validate result structure
            if not isinstance(result, dict) or "status" not in result:
                logger.error("%s returned invalid result structure: %s", check_name, result)
                checks[check_name] = {
                    "status": "error",
                    "error": "Invalid result structure"
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
                logger.warning("%s health check returned %s: %s", check_name, check_status, error_msg)
                if check_status == "error":
                    errors.append(f"{check_name} check failed: {error_msg}")

    # Handle skipped LLM check
    if not include_llm:
        checks["llm_services"] = {
            "status": "skipped",
            "message": (
                "LLM health check disabled by default. "
                "Use ?include_llm=true to enable (makes actual API calls)."
            )
        }

    # Build response
    response_data = {
        "status": overall_status,
        "timestamp": check_timestamp,
        "checks": checks
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
        "total": total_count
    }

    return JSONResponse(
        content=response_data,
        status_code=overall_status_code
    )


@router.get("/health/processes")
async def processes_health_check():
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
        # pylint: disable=import-outside-toplevel
        from services.infrastructure.monitoring.process_monitor import get_process_monitor
        process_monitor = get_process_monitor()
        status = process_monitor.get_status()

        # Determine overall status
        unhealthy_count = sum(
            1 for service_status in status.values()
            if service_status.get('status') == 'unhealthy'
        )
        degraded_count = sum(
            1 for service_status in status.values()
            if service_status.get('status') == 'degraded'
        )

        overall_status = "healthy"
        status_code = 200
        if unhealthy_count > 0:
            overall_status = "unhealthy"
            status_code = 503
        elif degraded_count > 0:
            overall_status = "degraded"
            status_code = 503

        response_data = {
            "status": overall_status,
            "services": status,
            "unhealthy_count": unhealthy_count,
            "degraded_count": degraded_count,
            "total_services": len(status),
            "timestamp": int(time.time())
        }

        return JSONResponse(
            content=response_data,
            status_code=status_code
        )
    except ImportError:
        return JSONResponse(
            content={
                "status": "unavailable",
                "message": "Process monitor not available"
            },
            status_code=503
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Process health check error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Process health check failed: {str(e)}"
        ) from e


@router.get("/status")
async def get_status():
    """Application status endpoint with metrics"""
    # Import app lazily to avoid circular import
    import main  # pylint: disable=import-outside-toplevel
    app = main.app

    memory = psutil.virtual_memory()
    uptime = time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0

    return {
        "status": "running",
        "framework": "FastAPI",
        "version": config.version,
        "uptime_seconds": round(uptime, 1),
        "memory_percent": round(memory.percent, 1),
        "timestamp": time.time()
    }
