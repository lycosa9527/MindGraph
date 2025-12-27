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

import json
import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db
from models.auth import User
from models.token_usage import TokenUsage
from services.redis_activity_tracker import get_activity_tracker
from services.dashboard_session import get_dashboard_session_manager
from services.ip_geolocation import get_geolocation_service
from services.activity_stream import get_activity_stream_service
from routers.auth.helpers import get_beijing_now, get_beijing_today_start_utc

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration constants
MAX_CONCURRENT_SSE_CONNECTIONS = 2  # Max concurrent SSE connections per IP
SSE_POLL_INTERVAL_SECONDS = 5  # Poll for updates every N seconds
STATS_UPDATE_INTERVAL = 10  # Send stats update every N seconds
HEARTBEAT_INTERVAL = 30  # Send heartbeat every N seconds

# Stats cache configuration
STATS_CACHE_KEY = "dashboard:stats_cache"
STATS_CACHE_TTL = 3  # Cache for 3 seconds

# Track active SSE connections per IP to prevent DoS
_active_sse_connections: Dict[str, int] = {}


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
    
    session_manager = get_dashboard_session_manager()
    if not session_manager.verify_session(dashboard_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired dashboard session"
        )
    
    return True


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
    from services.redis_client import is_redis_available, get_redis
    
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
            logger.debug(f"Failed to cache stats: {e}")
            # Continue - cache failure shouldn't break stats query
        
        return stats
        
    except Exception as e:
        # Any Redis error - fallback to direct query
        logger.debug(f"Stats cache error: {e}, falling back to direct query")
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
    
    try:
        # Get connected users count
        tracker = get_activity_tracker()
        stats = get_cached_stats(tracker)
        connected_users = stats.get('active_users_count', 0)
        
        # Get registered users count
        registered_users = db.query(User).count()
        
        # Get token usage stats
        beijing_now = get_beijing_now()
        today_start = get_beijing_today_start_utc()
        
        # Tokens used today
        today_tokens_query = db.query(
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= today_start,
            TokenUsage.success == True
        ).first()
        
        tokens_used_today = int(today_tokens_query.total_tokens or 0) if today_tokens_query else 0
        
        # Total tokens used (all time)
        total_tokens_query = db.query(
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.success == True
        ).first()
        
        total_tokens_used = int(total_tokens_query.total_tokens or 0) if total_tokens_query else 0
        
        return {
            "timestamp": beijing_now.isoformat(),
            "connected_users": connected_users,
            "registered_users": registered_users,
            "tokens_used_today": tokens_used_today,
            "total_tokens_used": total_tokens_used
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard statistics"
        )


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
    
    try:
        # Get active users
        tracker = get_activity_tracker()
        active_users = tracker.get_active_users()
        
        # Group by IP address and lookup locations
        ip_geolocation = get_geolocation_service()
        province_data = defaultdict(int)  # {province_name: count}
        city_data = defaultdict(int)  # {city_name: count}
        city_coords = {}  # {city_name: [lng, lat]}
        
        for user in active_users:
            ip_address = user.get('ip_address', '')
            if not ip_address or ip_address == 'unknown':
                continue
            
            # Lookup location
            location = await ip_geolocation.get_location(ip_address)
            if not location:
                continue
            
            city = location.get('city', '')
            province = location.get('province', '')
            
            # Count by province for map highlighting
            if province:
                province_data[province] += 1
            
            # Also track city-level data for scatter points
            location_name = city if city else province
            if location_name:
                city_data[location_name] += 1
                
                # Store coordinates (use first occurrence)
                if location_name not in city_coords:
                    lat = location.get('lat')
                    lng = location.get('lng')
                    if lat is not None and lng is not None:
                        city_coords[location_name] = [lng, lat]
        
        # Build map data for province highlighting (ECharts map series format)
        map_data = []
        for province_name, count in province_data.items():
            map_data.append({
                "name": province_name,
                "value": count
            })
        
        # Build series data for scatter points
        series_data = []
        for city_name, count in city_data.items():
            coords = city_coords.get(city_name)
            if coords:
                series_data.append({
                    "name": city_name,
                    "value": [coords[0], coords[1], count]  # [lng, lat, count]
                })
        
        return {
            "map_data": map_data,  # For province highlighting
            "series_data": series_data  # For scatter points
        }
        
    except Exception as e:
        logger.error(f"Error getting map data: {e}", exc_info=True)
        # Return empty data on error (don't break dashboard)
        return {
            "map_data": [],
            "series_data": []
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
    
    # Rate limiting: Check concurrent connections per IP
    client_ip = request.client.host if request.client else "unknown"
    current_connections = _active_sse_connections.get(client_ip, 0)
    if current_connections >= MAX_CONCURRENT_SSE_CONNECTIONS:
        logger.warning(f"IP {client_ip} exceeded max concurrent SSE connections ({MAX_CONCURRENT_SSE_CONNECTIONS})")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {MAX_CONCURRENT_SSE_CONNECTIONS} concurrent connections allowed"
        )
    
    # Increment connection count
    _active_sse_connections[client_ip] = current_connections + 1
    logger.info(f"Dashboard SSE connection started for IP {client_ip} (connections: {_active_sse_connections[client_ip]})")
    
    # Register connection with activity stream service
    connection_id = str(uuid.uuid4())
    activity_service = get_activity_stream_service()
    event_queue = activity_service.add_connection(connection_id)
    
    async def event_generator():
        """Generate SSE events from activity stream service."""
        tracker = get_activity_tracker()
        last_stats = None
        
        try:
            # Send initial state
            try:
                stats = get_cached_stats(tracker)
                initial_stats = {
                    "connected_users": stats.get('active_users_count', 0),
                    "registered_users": 0,  # Will be updated by stats endpoint
                    "tokens_used_today": 0,  # Will be updated by stats endpoint
                    "total_tokens_used": 0  # Will be updated by stats endpoint
                }
            except Exception as e:
                logger.error(f"Error getting initial state: {e}")
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
            
            last_stats = initial_stats
            
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
                    logger.error(f"Error reading activity queue: {e}")
                
                # Send stats update periodically
                stats_counter += 1
                if stats_counter >= (STATS_UPDATE_INTERVAL // SSE_POLL_INTERVAL_SECONDS):
                    try:
                        current_stats = get_cached_stats(tracker)
                        stats_update = {
                            "connected_users": current_stats.get('active_users_count', 0)
                        }
                        
                        stats_data = json.dumps({
                            'type': 'stats_update',
                            **stats_update
                        })
                        yield f"data: {stats_data}\n\n"
                        stats_counter = 0
                    except Exception as e:
                        logger.error(f"Error getting stats: {e}")
                
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
            logger.info(f"Activity stream cancelled for connection {connection_id}")
            return
        except Exception as e:
            logger.error(f"Error in activity stream: {e}", exc_info=True)
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
            if client_ip in _active_sse_connections:
                _active_sse_connections[client_ip] = max(0, _active_sse_connections[client_ip] - 1)
                if _active_sse_connections[client_ip] == 0:
                    del _active_sse_connections[client_ip]
                logger.debug(f"Dashboard SSE connection closed for IP {client_ip} (remaining: {_active_sse_connections.get(client_ip, 0)})")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )



