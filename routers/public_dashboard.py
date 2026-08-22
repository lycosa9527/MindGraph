"""
National data-center router (China-map dashboard).

Requires platform super-admin (``tab.settings.public_dashboard``).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from routers.auth.dependencies import require_settings_public_dashboard_short_lived
from routers.auth.helpers import get_beijing_now
from services.auth.ip_geolocation import get_geolocation_service
from services.monitoring.activity_stream import get_activity_stream_service
from services.monitoring.city_flag_tracker import get_city_flag_tracker, record_mappable_location_flag
from services.monitoring.national_dashboard import (
    aggregate_map_locations,
    collect_unique_public_ips,
    count_connected_users,
    count_registered_users,
    empty_dashboard_stats,
    filter_localhost_users,
    merge_city_flags,
    parse_cached_json,
    query_token_totals,
)
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from services.redis.redis_activity_tracker import get_activity_tracker
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS
from services.utils.typing_helpers import redis_decode
from utils.auth import get_client_ip
from utils.auth.admin_scope import AdminScope
from utils.db.rls_request import bind_dashboard_rls_dependency

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_CONCURRENT_SSE_CONNECTIONS = config.DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS
SSE_POLL_INTERVAL_SECONDS = config.DASHBOARD_SSE_POLL_INTERVAL_SECONDS
STATS_UPDATE_INTERVAL = config.DASHBOARD_STATS_UPDATE_INTERVAL
HEARTBEAT_INTERVAL = config.DASHBOARD_HEARTBEAT_INTERVAL

REGISTERED_USERS_CACHE_KEY = "dashboard:registered_users_cache"
REGISTERED_USERS_CACHE_TTL = config.DASHBOARD_REGISTERED_USERS_CACHE_TTL
TOKEN_USAGE_CACHE_KEY = "dashboard:token_usage_cache:v2"
TOKEN_USAGE_CACHE_TTL = config.DASHBOARD_TOKEN_USAGE_CACHE_TTL
MAP_DATA_CACHE_KEY = "dashboard:map_data_cache:v2"
MAP_DATA_CACHE_TTL = config.DASHBOARD_MAP_DATA_CACHE_TTL
SSE_CONNECTION_PREFIX = "dashboard:sse_connections:"


async def check_dashboard_rate_limit(
    request: Request,
    endpoint_name: str,
    max_requests: int = 60,
    window_seconds: int = 60,
) -> None:
    """Per-IP rate limit for dashboard endpoints."""
    client_ip = get_client_ip(request) if request else "unknown"
    rate_limiter = RedisRateLimiter()
    is_allowed, count, error_msg = await rate_limiter.check_and_record(
        category=f"dashboard_{endpoint_name}",
        identifier=client_ip,
        max_attempts=max_requests,
        window_seconds=window_seconds,
    )
    if not is_allowed:
        logger.warning(
            "Dashboard rate limit exceeded for %s: %s (%s/%s requests)",
            endpoint_name,
            client_ip,
            count,
            max_requests,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. {error_msg}",
        )


async def _cache_get_json(cache_key: str) -> Optional[Dict[str, Any]]:
    """Read a JSON object from Redis, deleting corrupt values."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        cached = await redis.get(cache_key)
    except REDIS_ERRORS as exc:
        logger.debug("Error reading dashboard cache %s: %s", cache_key, exc)
        return None
    parsed = parse_cached_json(redis_decode(cached))
    if cached and parsed is None:
        try:
            await redis.delete(cache_key)
        except REDIS_ERRORS as exc:
            logger.debug("Failed to delete invalid dashboard cache %s: %s", cache_key, exc)
    return parsed


async def _cache_set_json(cache_key: str, payload: Dict[str, Any], ttl: int) -> None:
    """Store a JSON object in Redis."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.set(cache_key, json.dumps(payload, ensure_ascii=False), ex=ttl)
    except REDIS_ERRORS as exc:
        logger.debug("Failed to cache dashboard payload %s: %s", cache_key, exc)


async def _cache_get_int(cache_key: str) -> Optional[int]:
    """Read a cached integer."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        cached = await redis.get(cache_key)
        if cached is None:
            return None
        return int(cached)
    except REDIS_ERRORS as exc:
        logger.debug("Error reading dashboard int cache %s: %s", cache_key, exc)
        return None


async def _cache_set_int(cache_key: str, value: int, ttl: int) -> None:
    """Store an integer in Redis."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.set(cache_key, str(value), ex=ttl)
    except REDIS_ERRORS as exc:
        logger.debug("Failed to cache dashboard int %s: %s", cache_key, exc)


async def _load_token_totals(db: AsyncSession) -> tuple[int, int]:
    """Cached LLM + MindBot token totals (today / all-time)."""
    cached = await _cache_get_json(TOKEN_USAGE_CACHE_KEY)
    if cached is not None:
        today = cached.get("today")
        total = cached.get("total")
        if isinstance(today, int) and isinstance(total, int):
            return today, total
    tokens_today, tokens_total = await query_token_totals(db)
    await _cache_set_json(
        TOKEN_USAGE_CACHE_KEY,
        {"today": tokens_today, "total": tokens_total},
        TOKEN_USAGE_CACHE_TTL,
    )
    return tokens_today, tokens_total


async def _load_registered_users(db: AsyncSession) -> int:
    """Cached registered-user count."""
    cached = await _cache_get_int(REGISTERED_USERS_CACHE_KEY)
    if cached is not None:
        return cached
    registered_users = await count_registered_users(db)
    await _cache_set_int(REGISTERED_USERS_CACHE_KEY, registered_users, REGISTERED_USERS_CACHE_TTL)
    return registered_users


@router.get("/stats")
async def get_dashboard_stats(
    request: Request,
    _scope: AdminScope = Depends(require_settings_public_dashboard_short_lived),
    _dashboard_rls: None = Depends(bind_dashboard_rls_dependency),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Live user counts plus token totals for the national data center."""
    await check_dashboard_rate_limit(request, "stats", max_requests=60, window_seconds=60)
    beijing_now = get_beijing_now()
    tracker = get_activity_tracker()
    try:
        active_users = await tracker.get_active_users(hours=1)
        connected_users = count_connected_users(active_users)
        registered_users = await _load_registered_users(db)
        tokens_today, tokens_total = await _load_token_totals(db)
    except DATABASE_ERRORS as exc:
        logger.error("Error getting dashboard stats: %s", exc, exc_info=True)
        return empty_dashboard_stats(beijing_now.isoformat())
    return {
        "timestamp": beijing_now.isoformat(),
        "connected_users": connected_users,
        "registered_users": registered_users,
        "tokens_used_today": tokens_today,
        "total_tokens_used": tokens_total,
    }


async def _record_active_city_flags(
    city_coords: Dict[str, list[float]],
    city_to_location: Dict[str, Dict[str, Any]],
) -> None:
    """Refresh city-flag TTLs for cities that currently have mappable users."""
    for city_name, coords in city_coords.items():
        location_info = city_to_location.get(city_name)
        if not location_info:
            continue
        lat = location_info.get("lat") or coords[1]
        lng = location_info.get("lng") or coords[0]
        await record_mappable_location_flag(
            {
                "city": location_info.get("city") or city_name,
                "province": location_info.get("province"),
                "lat": lat,
                "lng": lng,
                "country": "中国",
            }
        )


@router.get("/map-data")
async def get_map_data(
    request: Request,
    _scope: AdminScope = Depends(require_settings_public_dashboard_short_lived),
) -> Dict[str, Any]:
    """Province highlights and city pins for currently active public IPs."""
    await check_dashboard_rate_limit(request, "map_data", max_requests=30, window_seconds=60)
    cached = await _cache_get_json(MAP_DATA_CACHE_KEY)
    if cached is not None and "map_data" in cached:
        return cached

    ip_geolocation = get_geolocation_service()
    if not ip_geolocation.is_ready():
        logger.debug("[MapData] IP geolocation database not ready, returning empty data")
        return {"map_data": [], "flag_data": [], "database_loading": True}

    try:
        tracker = get_activity_tracker()
        active_users = filter_localhost_users(await tracker.get_active_users(hours=1))
        ip_addresses, ip_to_user = collect_unique_public_ips(active_users)

        sem = asyncio.Semaphore(10)

        async def _geolocate(ip: str):
            async with sem:
                return await ip_geolocation.get_location(ip)

        locations = await asyncio.gather(*[_geolocate(ip) for ip in ip_addresses], return_exceptions=True)
        ip_location_rows = []
        for ip_address, location in zip(ip_addresses, locations):
            if isinstance(location, Exception) or not isinstance(location, dict):
                continue
            ip_location_rows.append((ip_address, location, len(ip_to_user[ip_address])))

        map_data, city_coords, city_to_location = aggregate_map_locations(ip_location_rows)
        await _record_active_city_flags(city_coords, city_to_location)
        flag_tracker = get_city_flag_tracker()
        flag_data = merge_city_flags(await flag_tracker.get_active_flags(), city_coords, city_to_location)
        result = {
            "map_data": map_data,
            "flag_data": flag_data,
            "database_loading": False,
        }
        await _cache_set_json(MAP_DATA_CACHE_KEY, result, MAP_DATA_CACHE_TTL)
        return result
    except REDIS_ERRORS as exc:
        logger.error("Error getting map data: %s", exc, exc_info=True)
        return {"map_data": [], "flag_data": [], "database_loading": False}


@router.get("/activity-history")
async def get_activity_history(
    request: Request,
    limit: int = 100,
    _scope: AdminScope = Depends(require_settings_public_dashboard_short_lived),
) -> Dict[str, Any]:
    """Recent activity rows for the live panel."""
    await check_dashboard_rate_limit(request, "activity_history", max_requests=30, window_seconds=60)
    clamped = max(1, min(limit, 500))
    try:
        activity_service = get_activity_stream_service()
        activities = await activity_service.get_recent_activities(limit=clamped)
        activity_list = [
            {
                "type": activity.get("type", "activity"),
                "timestamp": activity.get("timestamp", ""),
                "user": activity.get("user", "User *"),
                "action": activity.get("action", ""),
                "diagram_type": activity.get("diagram_type", ""),
            }
            for activity in activities
        ]
        return {"activities": activity_list, "count": len(activity_list)}
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("Error getting activity history: %s", exc, exc_info=True)
        return {"activities": [], "count": 0}


async def _track_sse_connection(client_ip: str) -> bool:
    """Increment the per-IP SSE counter. Returns True when Redis tracked it."""
    if not is_redis_available():
        return False
    redis = get_async_redis()
    if not redis:
        return False
    try:
        current_connections = await redis.incr(f"{SSE_CONNECTION_PREFIX}{client_ip}")
        await redis.expire(f"{SSE_CONNECTION_PREFIX}{client_ip}", 300)
        if current_connections > MAX_CONCURRENT_SSE_CONNECTIONS:
            await redis.decr(f"{SSE_CONNECTION_PREFIX}{client_ip}")
            logger.warning(
                "IP %s exceeded max concurrent SSE connections (%s)",
                client_ip,
                MAX_CONCURRENT_SSE_CONNECTIONS,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Maximum {MAX_CONCURRENT_SSE_CONNECTIONS} concurrent connections allowed",
            )
        logger.info(
            "Dashboard SSE connection started for IP %s (connections: %s)",
            client_ip,
            current_connections,
        )
        return True
    except REDIS_ERRORS as exc:
        logger.warning("Error tracking SSE connection in Redis: %s, continuing without tracking", exc)
        return False


async def _release_sse_connection(client_ip: str, connection_tracked: bool) -> None:
    """Decrement the per-IP SSE counter."""
    if not connection_tracked or not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        remaining = await redis.decr(f"{SSE_CONNECTION_PREFIX}{client_ip}")
        if remaining <= 0:
            await redis.delete(f"{SSE_CONNECTION_PREFIX}{client_ip}")
        logger.debug(
            "Dashboard SSE connection closed for IP %s (remaining: %s)",
            client_ip,
            max(0, remaining),
        )
    except REDIS_ERRORS as exc:
        logger.debug("Error decrementing SSE connection count: %s", exc)


async def _connected_users_count() -> int:
    """Live connected-user count for SSE frames (tokens stay on /stats)."""
    tracker = get_activity_tracker()
    active_users = await tracker.get_active_users(hours=1)
    return count_connected_users(active_users)


@router.get("/activity-stream")
async def stream_activity_updates(
    request: Request,
    _scope: AdminScope = Depends(require_settings_public_dashboard_short_lived),
):
    """SSE stream: activity events, connected-user ticks, heartbeats."""
    client_ip = get_client_ip(request) if request else "unknown"
    connection_tracked = await _track_sse_connection(client_ip)
    connection_id = str(uuid.uuid4())
    activity_service = get_activity_stream_service()
    event_queue = activity_service.add_connection(connection_id)

    async def event_generator():
        try:
            try:
                initial_stats = {"connected_users": await _connected_users_count()}
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.error("Error getting initial state: %s", exc, exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'error': 'Failed to fetch initial state'})}\n\n"
                return

            # Do not send token/registered zeros — the Vue client would overwrite /stats.
            yield f"data: {json.dumps({'type': 'initial', 'stats': initial_stats})}\n\n"

            heartbeat_counter = 0
            stats_counter = 0
            while True:
                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
                try:
                    activity_json = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield f"data: {activity_json}\n\n"
                except asyncio.TimeoutError:
                    pass
                except BACKGROUND_INFRA_ERRORS as exc:
                    logger.error("Error reading activity queue: %s", exc)

                stats_counter += 1
                if stats_counter >= (STATS_UPDATE_INTERVAL // SSE_POLL_INTERVAL_SECONDS):
                    try:
                        stats_data = {
                            "type": "stats_update",
                            "connected_users": await _connected_users_count(),
                        }
                        yield f"data: {json.dumps(stats_data)}\n\n"
                        stats_counter = 0
                    except BACKGROUND_INFRA_ERRORS as exc:
                        logger.error("Error getting stats: %s", exc, exc_info=True)

                heartbeat_counter += 1
                if heartbeat_counter >= (HEARTBEAT_INTERVAL // SSE_POLL_INTERVAL_SECONDS):
                    heartbeat_data = {
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    yield f"data: {json.dumps(heartbeat_data)}\n\n"
                    heartbeat_counter = 0
        except asyncio.CancelledError:
            logger.info("Activity stream cancelled for connection %s", connection_id)
            return
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.error("Error in activity stream: %s", exc, exc_info=True)
            try:
                yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
            except REDIS_ERRORS:
                return
        finally:
            activity_service.remove_connection(connection_id)
            await _release_sse_connection(client_ip, connection_tracked)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
