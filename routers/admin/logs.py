"""Admin Log Streaming Router.

Real-time log streaming endpoints for admin debug viewer.

Uses Server-Sent Events (SSE) for efficient one-way streaming.

Security:
- JWT authentication required
- Admin role check on all endpoints
- Read-only access to logs

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from routers.auth.dependencies import require_settings_performance
from services.monitoring.log_streamer import LogStreamer
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/admin/logs", tags=["Admin - Logs"])


@router.get("/files", dependencies=[Depends(require_settings_performance)])
async def list_log_files(scope: AdminScope = Depends(require_settings_performance)):
    """
    List available log files (ADMIN ONLY)

    Returns:
        List of log files with metadata (name, size, modified time)
    """
    try:
        log_streamer = LogStreamer()
        log_files = log_streamer.get_log_files()

        logger.info("Admin %s listed log files", scope.actor.phone)

        return log_files

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to list log files: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list log files: {str(e)}",
        ) from e


@router.get("/read", dependencies=[Depends(require_settings_performance)])
async def read_log_file(
    source: str = Query("app", description="Log source (app, uvicorn, error)"),
    start_line: int = Query(0, ge=0, description="Starting line number"),
    num_lines: int = Query(100, ge=1, le=1000, description="Number of lines to read"),
    scope: AdminScope = Depends(require_settings_performance),
):
    """
    Read a range of lines from a log file (ADMIN ONLY)

    Args:
        source: Log source (app, uvicorn, error)
        start_line: Starting line number (0-based)
        num_lines: Number of lines to read (max 1000)

    Returns:
        List of parsed log entries
    """
    try:
        log_streamer = LogStreamer()
        entries = await log_streamer.read_log_file(source, start_line, num_lines)

        logger.info(
            "Admin %s read %d log lines from %s",
            scope.actor.phone,
            len(entries),
            source,
        )

        return entries

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to read log file: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read log file: {str(e)}",
        ) from e


@router.get("/stream", dependencies=[Depends(require_settings_performance)])
async def stream_logs(
    source: str = Query("app", description="Log source (app, uvicorn, error, all)"),
    follow: bool = Query(True, description="Continue watching for new lines"),
    max_lines: int = Query(100, ge=1, le=1000, description="Max historical lines"),
    scope: AdminScope = Depends(require_settings_performance),
):
    """
    Stream logs in real-time using Server-Sent Events (ADMIN ONLY)

    This endpoint uses SSE for efficient one-way streaming from server to client.
    Client should connect with EventSource API.

    Args:
        source: Log source (app, uvicorn, error, all)
        follow: If True, continue watching for new lines (tail -f mode)
        max_lines: Maximum historical lines to send first

    Returns:
        StreamingResponse with text/event-stream content type

    Example client code:
        const eventSource = new EventSource('/api/auth/admin/logs/stream?source=app');
        eventSource.onmessage = (event) => {
            const logEntry = JSON.parse(event.data);
            console.log(logEntry);
        };
    """
    logger.info(
        "Admin %s started log stream: source=%s, follow=%s",
        scope.actor.phone,
        source,
        follow,
    )

    async def event_generator():
        """Generate SSE events from log stream."""
        try:
            log_streamer = LogStreamer()

            async for entry in log_streamer.tail_logs(source, follow, max_lines):
                # Format as SSE event
                # SSE format: data: {json}\n\n
                data = json.dumps(entry)
                yield f"data: {data}\n\n"

                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info("Log stream cancelled for admin %s", scope.actor.phone)
            yield 'data: {"message": "Stream closed"}\n\n'
        except (OSError, IOError, ValueError) as e:
            logger.error("Error in log stream: %s", e)
            error_data = json.dumps(
                {
                    "level": "ERROR",
                    "message": f"Stream error: {str(e)}",
                    "timestamp": "",
                }
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/tail", dependencies=[Depends(require_settings_performance)])
async def tail_logs(
    source: str = Query("app", description="Log source (app, uvicorn, error)"),
    lines: int = Query(50, ge=1, le=500, description="Number of last lines to read"),
    scope: AdminScope = Depends(require_settings_performance),
):
    """
    Get last N lines from a log file (like `tail -n`) (ADMIN ONLY)

    Args:
        source: Log source (app, uvicorn, error)
        lines: Number of last lines to read (max 500)

    Returns:
        List of parsed log entries
    """
    try:
        log_streamer = LogStreamer()

        # Read all lines, then take last N
        # For better performance, could optimize to seek from end
        entries = []
        async for entry in log_streamer.tail_logs(source, follow=False, max_lines=lines):
            entries.append(entry)

        # Take last N entries
        result = entries[-lines:] if len(entries) > lines else entries

        logger.info("Admin %s tailed %d lines from %s", scope.actor.phone, len(result), source)

        return result

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to tail log file: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to tail log file: {str(e)}",
        ) from e


@router.get("/search", dependencies=[Depends(require_settings_performance)])
async def search_logs(
    query: str = Query(..., min_length=1, description="Search query"),
    source: str = Query("app", description="Log source (app, uvicorn, error)"),
    max_results: int = Query(100, ge=1, le=500, description="Max results"),
    scope: AdminScope = Depends(require_settings_performance),
):
    """
    Search log files for matching lines (ADMIN ONLY)

    Args:
        query: Search query (case-insensitive substring match)
        source: Log source (app, uvicorn, error)
        max_results: Maximum number of results (max 500)

    Returns:
        List of matching log entries
    """
    try:
        log_streamer = LogStreamer()
        query_lower = query.lower()
        results = []

        # Read all lines and filter
        async for entry in log_streamer.tail_logs(source, follow=False, max_lines=10000):
            # Search in message and raw line
            if query_lower in entry.get("message", "").lower() or query_lower in entry.get("raw", "").lower():
                results.append(entry)

                if len(results) >= max_results:
                    break

        logger.info(
            "Admin %s searched logs: query='%s', source=%s, results=%d",
            scope.actor.phone,
            query,
            source,
            len(results),
        )

        return results

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to search logs: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search logs: {str(e)}",
        ) from e
