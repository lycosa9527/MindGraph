"""
Public Dashboard Router
=======================

Public dashboard endpoints for real-time analytics visualization.
Requires dashboard session authentication (passkey-protected).

Endpoints:
- GET /api/public/stats - Get dashboard statistics
- GET /api/public/map-data - Get active users by city for map visualization
- GET /api/public/activity-stream - SSE stream for real-time activity updates

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import config
from models.domain.auth import User
from models.domain.token_usage import TokenUsage
from routers.auth.helpers import get_beijing_now, get_beijing_today_start_utc
from services.auth.ip_geolocation import get_geolocation_service
from services.monitoring.activity_stream import get_activity_stream_service
from services.monitoring.city_flag_tracker import get_city_flag_tracker
from services.monitoring.dashboard_session import get_dashboard_session_manager
from services.redis.redis_activity_tracker import get_activity_tracker
from services.redis.redis_client import is_redis_available, get_redis
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from utils.auth import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration constants (from environment variables)
MAX_CONCURRENT_SSE_CONNECTIONS = config.DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS
SSE_POLL_INTERVAL_SECONDS = config.DASHBOARD_SSE_POLL_INTERVAL_SECONDS
STATS_UPDATE_INTERVAL = config.DASHBOARD_STATS_UPDATE_INTERVAL
HEARTBEAT_INTERVAL = config.DASHBOARD_HEARTBEAT_INTERVAL

# Stats cache configuration
STATS_CACHE_KEY = "dashboard:stats_cache"
STATS_CACHE_TTL = config.DASHBOARD_STATS_CACHE_TTL

# Registered users cache (changes infrequently)
REGISTERED_USERS_CACHE_KEY = "dashboard:registered_users_cache"
REGISTERED_USERS_CACHE_TTL = config.DASHBOARD_REGISTERED_USERS_CACHE_TTL

# Token usage cache (increased TTL for better performance)
TOKEN_USAGE_CACHE_KEY = "dashboard:token_usage_cache"
TOKEN_USAGE_CACHE_TTL = config.DASHBOARD_TOKEN_USAGE_CACHE_TTL

# Map data cache configuration (1 hour for persistent heat map)
MAP_DATA_CACHE_KEY = "dashboard:map_data_cache"
MAP_DATA_CACHE_TTL = config.DASHBOARD_MAP_DATA_CACHE_TTL

# SSE connection tracking key prefix (Redis-based for multi-worker support)
SSE_CONNECTION_PREFIX = "dashboard:sse_connections:"


def is_localhost_ip(ip_address: str) -> bool:
    """
    Check if an IP address is localhost/local.

    Args:
        ip_address: IP address string

    Returns:
        True if IP is localhost/local, False otherwise
    """
    if not ip_address:
        return False

    ip_lower = ip_address.lower().strip()

    # Common localhost identifiers
    if ip_lower in ('localhost', '::1', '::', '0.0.0.0'):
        return True

    # Check IPv4 localhost range (127.0.0.0/8)
    if ip_lower.startswith('127.'):
        return True

    # Check IPv6 IPv4-mapped localhost (::ffff:127.x.x.x)
    if ip_lower.startswith('::ffff:127.'):
        return True

    return False


def filter_localhost_users(active_users: List[Dict]) -> List[Dict]:
    """
    Filter out localhost connections from active users list.

    Args:
        active_users: List of user dicts with 'ip_address' field

    Returns:
        Filtered list excluding localhost connections
    """
    return [user for user in active_users
            if not is_localhost_ip(user.get('ip_address', ''))]


def count_non_localhost_users(active_users: List[Dict]) -> int:
    """
    Count active users excluding localhost connections and users without valid IPs.

    This matches the map endpoint logic which filters out empty/unknown IPs.

    Args:
        active_users: List of user dicts with 'ip_address' field

    Returns:
        Count of non-localhost users with valid IP addresses
    """
    return sum(1 for user in active_users
               if (ip_address := user.get('ip_address', ''))
               and ip_address != 'unknown'
               and not is_localhost_ip(ip_address))


def verify_dashboard_session(request: Request) -> bool:
    """
    Verify dashboard session from cookie.

    Returns True if valid, raises HTTPException if invalid.
    """
    dashboard_token = request.cookies.get("dashboard_access_token")

    if not dashboard_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dashboard session required"
        )

    # Get client IP for validation (handles reverse proxies)
    client_ip = get_client_ip(request) if request else None

    session_manager = get_dashboard_session_manager()
    if not session_manager.verify_session(dashboard_token, client_ip=client_ip):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired dashboard session"
        )

    return True


async def check_dashboard_rate_limit(
    request: Request,
    endpoint_name: str,
    max_requests: int = 60,
    window_seconds: int = 60
):
    """
    Check rate limit for dashboard endpoints.

    Args:
        request: FastAPI request object
        endpoint_name: Name of the endpoint for logging
        max_requests: Maximum requests allowed in window (default: 60)
        window_seconds: Time window in seconds (default: 60)

    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = get_client_ip(request) if request else "unknown"
    rate_limiter = RedisRateLimiter()

    is_allowed, count, error_msg = rate_limiter.check_and_record(
        category=f'dashboard_{endpoint_name}',
        identifier=client_ip,
        max_attempts=max_requests,
        window_seconds=window_seconds
    )

    if not is_allowed:
        logger.warning(
            "Dashboard rate limit exceeded for %s: %s (%s/%s requests)",
            endpoint_name, client_ip, count, max_requests
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. {error_msg}"
        )


def get_cached_stats(tracker) -> Dict:
    """
    Get activity tracker stats from Redis cache or query directly.

    Caches stats for 3 seconds to reduce Redis load when multiple
    SSE connections query stats simultaneously.

    Args:
        tracker: RedisActivityTracker instance

    Returns:
        Dict with stats (same format as tracker.get_stats())
    """
    # Fallback to direct query if Redis unavailable
    if not is_redis_available():
        return tracker.get_stats()

    try:
        redis = get_redis()
        if not redis:
            return tracker.get_stats()

        # Try to get from cache
        cached = redis.get(STATS_CACHE_KEY)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                # Invalid cache entry - delete it and query fresh
                try:
                    redis.delete(STATS_CACHE_KEY)
                except Exception:
                    pass
                # Fall through to query and update cache

        # Cache miss or invalid - query stats and update cache
        stats = tracker.get_stats()
        try:
            redis.setex(
                STATS_CACHE_KEY,
                STATS_CACHE_TTL,
                json.dumps(stats, ensure_ascii=False)  # Preserve UTF-8 characters
            )
        except Exception as e:
            logger.debug("Failed to cache stats: %s", e)
            # Continue - cache failure shouldn't break stats query

        return stats

    except Exception as e:
        # Any Redis error - fallback to direct query
        logger.debug("Stats cache error: %s, falling back to direct query", e)
        return tracker.get_stats()


@router.get("/stats")
async def get_dashboard_stats(
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get public dashboard statistics.

    Returns:
        Dict with connected_users, registered_users, tokens_used_today, total_tokens_used
    """
    # Verify dashboard session
    verify_dashboard_session(request)

    # Rate limiting: 60 requests per minute per IP
    await check_dashboard_rate_limit(request, 'stats', max_requests=60, window_seconds=60)

    try:
        # Get connected users count (excluding localhost)
        tracker = get_activity_tracker()
        active_users = tracker.get_active_users(hours=1)  # Match map endpoint time window
        # Filter out localhost connections
        connected_users = count_non_localhost_users(active_users)

        # Get registered users count (cached)
        beijing_now = get_beijing_now()
        today_start = get_beijing_today_start_utc()

        # Check Redis availability once (optimization)
        redis_available = is_redis_available()
        redis = get_redis() if redis_available else None

        # Get registered users count (cached)
        registered_users = None
        if redis:
            try:
                cached_count = redis.get(REGISTERED_USERS_CACHE_KEY)
                if cached_count:
                    registered_users = int(cached_count)
            except Exception as e:
                logger.debug("Error reading registered users cache: %s", e)

        if registered_users is None:
            registered_users = db.query(User).count()
            # Cache the result
            if redis:
                try:
                    redis.setex(
                        REGISTERED_USERS_CACHE_KEY,
                        REGISTERED_USERS_CACHE_TTL,
                        str(registered_users)
                    )
                except Exception as e:
                    logger.debug("Failed to cache registered users count: %s", e)

        # Get token usage stats (cached)
        tokens_used_today = None
        total_tokens_used = None

        if redis:
            try:
                cached_tokens = redis.get(TOKEN_USAGE_CACHE_KEY)
                if cached_tokens:
                    token_data = json.loads(cached_tokens)
                    tokens_used_today = token_data.get('today', None)
                    total_tokens_used = token_data.get('total', None)
            except Exception as e:
                logger.debug("Error reading token usage cache: %s", e)

        if tokens_used_today is None or total_tokens_used is None:
            # Optimize: Use a single query with conditional aggregation to get both values
            # This is faster than two separate queries - scans table only once
            # Single query that calculates both today and total in one pass
            # Uses conditional aggregation to avoid scanning the table twice
            token_stats_query = db.query(
                func.sum(
                    case(
                        (TokenUsage.created_at >= today_start, TokenUsage.total_tokens),
                        else_=0
                    )
                ).label('today_tokens'),
                func.sum(TokenUsage.total_tokens).label('total_tokens')
            ).filter(
                TokenUsage.success.is_(True)
            ).first()

            if token_stats_query:
                tokens_used_today = int(token_stats_query.today_tokens or 0)
                total_tokens_used = int(token_stats_query.total_tokens or 0)
            else:
                tokens_used_today = 0
                total_tokens_used = 0

            # Cache the result
            if is_redis_available():
                redis = get_redis()
                if redis:
                    try:
                        token_data = {
                            'today': tokens_used_today,
                            'total': total_tokens_used
                        }
                        redis.setex(
                            TOKEN_USAGE_CACHE_KEY,
                            TOKEN_USAGE_CACHE_TTL,
                            json.dumps(token_data)
                        )
                    except Exception as e:
                        logger.debug("Failed to cache token usage: %s", e)

        return {
            "timestamp": beijing_now.isoformat(),
            "connected_users": connected_users,
            "registered_users": registered_users,
            "tokens_used_today": tokens_used_today,
            "total_tokens_used": total_tokens_used
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting dashboard stats: %s", e, exc_info=True)
        # Return empty stats on error (don't break dashboard)
        beijing_now = get_beijing_now()
        return {
            "timestamp": beijing_now.isoformat(),
            "connected_users": 0,
            "registered_users": 0,
            "tokens_used_today": 0,
            "total_tokens_used": 0
        }


@router.get("/map-data")
async def get_map_data(
    request: Request
) -> Dict[str, Any]:
    """
    Get active users by province and city for map visualization.

    Returns:
        Dict with:
        - map_data: [{name: "北京", value: count}] for province highlighting
        - series_data: [{name: "北京", value: [lng, lat, count]}] for scatter points
    """
    # Verify dashboard session
    verify_dashboard_session(request)

    # Rate limiting: 30 requests per minute per IP (more expensive endpoint)
    await check_dashboard_rate_limit(request, 'map_data', max_requests=30, window_seconds=60)

    # Try to get from cache first
    if is_redis_available():
        redis = get_redis()
        if redis:
            try:
                cached = redis.get(MAP_DATA_CACHE_KEY)
                if cached:
                    try:
                        return json.loads(cached)
                    except json.JSONDecodeError:
                        # Invalid cache entry - delete it
                        try:
                            redis.delete(MAP_DATA_CACHE_KEY)
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("Error reading map data cache: %s", e)

    try:
        # Check if IP geolocation database is ready
        ip_geolocation = get_geolocation_service()
        if not ip_geolocation.is_ready():
            # Database not ready yet - return empty data with loading flag
            logger.debug("[MapData] IP geolocation database not ready, returning empty data")
            return {
                "map_data": [],
                "flag_data": [],
                "database_loading": True
            }

        # Get active users within last hour
        tracker = get_activity_tracker()
        active_users = tracker.get_active_users(hours=1)  # Show all users active within last hour

        # Filter out localhost connections
        active_users = filter_localhost_users(active_users)

        # Extract unique IP addresses for geolocation
        ip_addresses = []
        ip_to_user = {}
        for user in active_users:
            ip_address = user.get('ip_address', '')
            if ip_address and ip_address != 'unknown':
                if ip_address not in ip_to_user:
                    ip_addresses.append(ip_address)
                    ip_to_user[ip_address] = []
                ip_to_user[ip_address].append(user)

        # Parallelize IP geolocation lookups (database already checked above)
        location_tasks = [ip_geolocation.get_location(ip) for ip in ip_addresses]
        locations = await asyncio.gather(*location_tasks, return_exceptions=True)

        # Process locations for province highlighting and flag creation
        province_data = defaultdict(int)  # {province_name: count}
        city_coords = {}  # {city_name: [lng, lat]}
        city_to_location = {}  # {city_name: location_info}

        for ip_address, location in zip(ip_addresses, locations):
            # Skip only failed lookups (include fallback Beijing locations)
            if isinstance(location, Exception) or not location:
                continue

            # Type guard: location is now guaranteed to be a dict
            if not isinstance(location, dict):
                continue

            city = location.get('city', '')
            province = location.get('province', '')

            # Count users for this IP
            user_count = len(ip_to_user[ip_address])

            # Count by province for map highlighting
            if province:
                province_data[province] += user_count

            # Track city coordinates and location info for flags
            location_name = city if city else province
            if location_name:
                # Store coordinates (use first occurrence)
                if location_name not in city_coords:
                    lat = location.get('lat')
                    lng = location.get('lng')
                    if lat is not None and lng is not None:
                        city_coords[location_name] = [lng, lat]

                # Store location info for flag creation
                if location_name not in city_to_location:
                    city_to_location[location_name] = {
                        'city': city,
                        'province': province,
                        'lat': location.get('lat'),
                        'lng': location.get('lng')
                    }

        # Build map data for province highlighting (ECharts map series format)
        map_data = []
        for province_name, count in province_data.items():
            map_data.append({
                "name": province_name,
                "value": count
            })

        # Get city flags (cities with logins/activities in last hour)
        flag_tracker = get_city_flag_tracker()
        active_flags = flag_tracker.get_active_flags()

        # Refresh/create flags for ALL cities with currently active users
        # This ensures flags stay active as long as users are active, and all active users are represented
        # record_city_flag() refreshes TTL if flag exists, or creates new flag if it doesn't
        for city_name, coords in city_coords.items():
            # Get location info for this city
            location_info = city_to_location.get(city_name)
            if location_info:
                lat = location_info.get('lat') or coords[1]  # Prefer geolocation lat, fallback to coords
                lng = location_info.get('lng') or coords[0]  # Prefer geolocation lng, fallback to coords
                city = location_info.get('city') or city_name
                province = location_info.get('province')

                # Record/refresh flag for this city (record_city_flag refreshes TTL if flag exists)
                flag_tracker.record_city_flag(city, province, lat, lng)

                # Update active_flags list for this response
                # Remove existing flag if present, then add refreshed one
                active_flags = [f for f in active_flags if f['city'] != city_name]
                active_flags.append({
                    'city': city_name,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'lat': lat,
                    'lng': lng
                })

        # Build flag data with coordinates
        flag_data = []
        for flag in active_flags:
            city_name = flag['city']
            lat = flag.get('lat')
            lng = flag.get('lng')

            # Use stored coordinates if available
            if lat is not None and lng is not None:
                coords = [lng, lat]
            else:
                # Try to get coordinates from city_coords (if city is in active users)
                coords = city_coords.get(city_name)

            if coords:
                flag_data.append({
                    "name": city_name,
                    "value": [coords[0], coords[1]],  # [lng, lat]
                    "timestamp": flag['timestamp']
                })

        result = {
            "map_data": map_data,  # For province highlighting
            "flag_data": flag_data,  # For city flags (active session indicators)
            "database_loading": False  # Database is ready
        }

        # Cache the result
        if is_redis_available():
            redis = get_redis()
            if redis:
                try:
                    redis.setex(
                        MAP_DATA_CACHE_KEY,
                        MAP_DATA_CACHE_TTL,
                        json.dumps(result, ensure_ascii=False)
                    )
                except Exception as e:
                    logger.debug("Failed to cache map data: %s", e)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting map data: %s", e, exc_info=True)
        # Return empty data on error (don't break dashboard)
        return {
            "map_data": [],
            "series_data": [],
            "flag_data": [],
            "database_loading": False  # Error occurred, not a loading state
        }


@router.get("/activity-history")
async def get_activity_history(
    request: Request,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get historical activity data for the dashboard.

    Returns recent activities from Redis to populate the activity panel
    on page load. Activities are stored in Redis (not database) since
    history is not critical information.

    Args:
        limit: Maximum number of activities to return (default: 100, max: 500)

    Returns:
        Dict with 'activities' list containing activity objects
    """
    # Verify dashboard session
    verify_dashboard_session(request)

    # Rate limiting: 30 requests per minute per IP
    await check_dashboard_rate_limit(request, 'activity_history', max_requests=30, window_seconds=60)

    # Clamp limit to reasonable range
    limit = max(1, min(limit, 500))

    try:
        # Get recent activities from Redis (not database - history is not important)
        activity_service = get_activity_stream_service()
        activities = activity_service.get_recent_activities(limit=limit)

        # Convert to JSON-serializable format (activities already in correct format)
        activity_list = []
        for activity in activities:
            activity_list.append({
                "type": activity.get("type", "activity"),
                "timestamp": activity.get("timestamp", ""),
                "user": activity.get("user", "User *"),
                "action": activity.get("action", ""),
                "diagram_type": activity.get("diagram_type", "")
            })

        return {
            "activities": activity_list,
            "count": len(activity_list)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting activity history: %s", e, exc_info=True)
        # Return empty list on error (don't break dashboard)
        return {
            "activities": [],
            "count": 0
        }


@router.get("/activity-stream")
async def stream_activity_updates(
    request: Request
):
    """
    Stream real-time activity updates using Server-Sent Events.

    This endpoint uses SSE for efficient one-way streaming from server to client.
    Client should connect with EventSource API.

    Returns:
        StreamingResponse with text/event-stream content type

    Event Types:
    - 'activity': User activity update
    - 'stats_update': Statistics update
    - 'heartbeat': Keep-alive ping
    """
    # Verify dashboard session
    verify_dashboard_session(request)

    # Rate limiting: Check concurrent connections per IP (Redis-based)
    client_ip = get_client_ip(request) if request else "unknown"
    connection_key = f"{SSE_CONNECTION_PREFIX}{client_ip}"

    # Track connection in Redis for multi-worker support
    connection_tracked = False
    if is_redis_available():
        redis = get_redis()
        if redis:
            try:
                # Atomic increment and get current count
                current_connections = redis.incr(connection_key)
                # Set expiration (5 minutes) to auto-cleanup stale entries
                redis.expire(connection_key, 300)
                connection_tracked = True

                if current_connections > MAX_CONCURRENT_SSE_CONNECTIONS:
                    # Decrement since we're rejecting
                    redis.decr(connection_key)
                    logger.warning(
                        "IP %s exceeded max concurrent SSE connections (%s)",
                        client_ip, MAX_CONCURRENT_SSE_CONNECTIONS
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Maximum {MAX_CONCURRENT_SSE_CONNECTIONS} concurrent connections allowed"
                    )

                logger.info(
                    "Dashboard SSE connection started for IP %s (connections: %s)",
                    client_ip, current_connections
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(
                    "Error tracking SSE connection in Redis: %s, continuing without tracking",
                    e
                )
                # Continue without tracking - don't block on Redis errors

    if not connection_tracked:
        logger.debug("SSE connection tracking skipped (Redis unavailable or error)")

    # Register connection with activity stream service
    connection_id = str(uuid.uuid4())
    activity_service = get_activity_stream_service()
    event_queue = activity_service.add_connection(connection_id)

    async def event_generator():
        """Generate SSE events from activity stream service."""
        tracker = get_activity_tracker()

        try:
            # Send initial state
            try:
                active_users = tracker.get_active_users(hours=1)  # Get users active within last hour
                # Filter out localhost connections
                connected_users_count = count_non_localhost_users(active_users)
                initial_stats = {
                    "connected_users": connected_users_count,
                    "registered_users": 0,  # Will be updated by stats endpoint
                    "tokens_used_today": 0,  # Will be updated by stats endpoint
                    "total_tokens_used": 0  # Will be updated by stats endpoint
                }
            except Exception as e:
                logger.error("Error getting initial state: %s", e, exc_info=True)
                error_data = json.dumps({
                    'type': 'error',
                    'error': 'Failed to fetch initial state'
                })
                yield f"data: {error_data}\n\n"
                return

            initial_data = json.dumps({
                'type': 'initial',
                'stats': initial_stats
            })
            yield f"data: {initial_data}\n\n"

            # Poll for updates
            heartbeat_counter = 0
            stats_counter = 0

            while True:
                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)

                # Check for activity events from queue (non-blocking)
                try:
                    # Check queue with timeout
                    try:
                        activity_json = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                        yield f"data: {activity_json}\n\n"
                    except asyncio.TimeoutError:
                        pass  # No activity event, continue
                except Exception as e:
                    logger.error("Error reading activity queue: %s", e)

                # Send stats update periodically
                stats_counter += 1
                if stats_counter >= (STATS_UPDATE_INTERVAL // SSE_POLL_INTERVAL_SECONDS):
                    try:
                        active_users = tracker.get_active_users(hours=1)  # Get users active within last hour
                        # Filter out localhost connections
                        connected_users_count = count_non_localhost_users(active_users)
                        stats_update = {
                            "connected_users": connected_users_count
                        }

                        stats_data = json.dumps({
                            'type': 'stats_update',
                            **stats_update
                        })
                        yield f"data: {stats_data}\n\n"
                        stats_counter = 0
                    except Exception as e:
                        logger.error("Error getting stats: %s", e, exc_info=True)

                # Send heartbeat periodically
                heartbeat_counter += 1
                if heartbeat_counter >= (HEARTBEAT_INTERVAL // SSE_POLL_INTERVAL_SECONDS):
                    heartbeat_data = json.dumps({
                        'type': 'heartbeat',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    yield f"data: {heartbeat_data}\n\n"
                    heartbeat_counter = 0

        except asyncio.CancelledError:
            logger.info("Activity stream cancelled for connection %s", connection_id)
            return
        except Exception as e:
            logger.error("Error in activity stream: %s", e, exc_info=True)
            try:
                error_data = json.dumps({
                    'type': 'error',
                    'error': str(e)
                })
                yield f"data: {error_data}\n\n"
            except Exception:
                return
        finally:
            # Cleanup
            activity_service.remove_connection(connection_id)

            # Decrement connection count in Redis (only if we tracked it)
            # Use variables from outer scope (closure)
            if connection_tracked:
                if is_redis_available():
                    redis = get_redis()
                    if redis:
                        try:
                            remaining = redis.decr(connection_key)
                            if remaining <= 0:
                                redis.delete(connection_key)
                            logger.debug(
                                "Dashboard SSE connection closed for IP %s (remaining: %s)",
                                client_ip, max(0, remaining)
                            )
                        except Exception as e:
                            logger.debug("Error decrementing SSE connection count: %s", e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
