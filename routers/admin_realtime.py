"""
Admin Realtime Monitoring Router
==================================

Real-time user activity monitoring endpoints for admin panel.

Uses Server-Sent Events (SSE) for efficient one-way streaming of user activities.

Security:
- JWT authentication required
- Admin role check on all endpoints

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config.database import get_db
from models.auth import User
from utils.auth import get_current_user, is_admin
from services.redis_activity_tracker import get_activity_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/admin/realtime", tags=["Admin - Realtime"])

# Configuration constants
MAX_CONCURRENT_SSE_CONNECTIONS = 2  # Max concurrent SSE connections per admin
SSE_POLL_INTERVAL_SECONDS = 1  # Poll Redis every N seconds
USERS_UPDATE_INTERVAL = 5  # Send full user list update every N seconds
HEARTBEAT_INTERVAL = 10  # Send heartbeat every N seconds

# Track active SSE connections per admin to prevent DoS
# Format: {user_id: count}
_active_sse_connections: dict[int, int] = {}


@router.get("/stats", dependencies=[Depends(get_current_user)])
async def get_realtime_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current real-time statistics (ADMIN ONLY)
    
    Returns:
        Dict with stats: active_users_count, unique_users_count, etc.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        tracker = get_activity_tracker()
        stats = tracker.get_stats()
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get realtime stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/active-users", dependencies=[Depends(get_current_user)])
async def get_active_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of currently active users (ADMIN ONLY)
    
    Returns:
        List of active user sessions
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        tracker = get_activity_tracker()
        active_users = tracker.get_active_users()
        
        return {
            'users': active_users,
            'count': len(active_users),
            'timestamp': tracker.get_stats()['timestamp']
        }
        
    except Exception as e:
        logger.error(f"Failed to get active users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active users: {str(e)}"
        )


@router.get("/activities", dependencies=[Depends(get_current_user)])
async def get_recent_activities(
    limit: int = Query(100, ge=1, le=500, description="Number of activities to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent activity history (ADMIN ONLY)
    
    Args:
        limit: Maximum number of activities to return (max 500)
    
    Returns:
        List of recent activities
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        tracker = get_activity_tracker()
        activities = tracker.get_recent_activities(limit=limit)
        
        return {
            'activities': activities,
            'count': len(activities)
        }
        
    except Exception as e:
        logger.error(f"Failed to get activities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activities: {str(e)}"
        )


@router.get("/stream", dependencies=[Depends(get_current_user)])
async def stream_realtime_updates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream real-time user activity updates using Server-Sent Events (ADMIN ONLY)
    
    This endpoint uses SSE for efficient one-way streaming from server to client.
    Client should connect with EventSource API.
    
    Returns:
        StreamingResponse with text/event-stream content type
    
    Event Types:
    - 'stats': Overall statistics update
    - 'user_joined': New user became active
    - 'user_left': User session ended
    - 'activity': User activity update
    - 'heartbeat': Keep-alive ping
    
    Example client code:
        const eventSource = new EventSource('/api/auth/admin/realtime/stream');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data);
        };
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Rate limiting: Check concurrent connections
    user_id = current_user.id
    current_connections = _active_sse_connections.get(user_id, 0)
    if current_connections >= MAX_CONCURRENT_SSE_CONNECTIONS:
        logger.warning(f"Admin {current_user.phone} exceeded max concurrent SSE connections ({MAX_CONCURRENT_SSE_CONNECTIONS})")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {MAX_CONCURRENT_SSE_CONNECTIONS} concurrent connections allowed"
        )
    
    # Increment connection count
    _active_sse_connections[user_id] = current_connections + 1
    logger.info(f"Admin {current_user.phone} started realtime stream (connections: {_active_sse_connections[user_id]})")
    
    async def event_generator():
        """Generate SSE events from activity tracker."""
        tracker = get_activity_tracker()
        last_stats = None
        
        try:
            # Send initial state (wrap in try-except to ensure cleanup on error)
            try:
                stats = tracker.get_stats()
                active_users = tracker.get_active_users()
            except Exception as e:
                logger.error(f"Error getting initial state: {e}")
                error_data = json.dumps({
                    'type': 'error',
                    'error': 'Failed to fetch initial state'
                })
                yield f"data: {error_data}\n\n"
                return  # Exit generator, finally block will cleanup
            
            initial_data = json.dumps({
                'type': 'initial',
                'stats': stats,
                'users': active_users
            })
            yield f"data: {initial_data}\n\n"
            
            last_stats = stats
            
            # Poll for updates
            heartbeat_counter = 0
            last_session_ids = {u['session_id'] for u in active_users}
            
            while True:
                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
                
                # Check if client disconnected (FastAPI will raise CancelledError on disconnect)
                # This check happens before expensive operations
                try:
                    # Get current state
                    current_stats = tracker.get_stats()
                    current_users = tracker.get_active_users()
                except Exception as e:
                    # If Redis fails, log and break to avoid infinite error loop
                    logger.error(f"Error getting tracker data: {e}")
                    error_data = json.dumps({
                        'type': 'error',
                        'error': 'Failed to fetch activity data'
                    })
                    yield f"data: {error_data}\n\n"
                    break
                
                current_session_ids = {u['session_id'] for u in current_users}
                
                # Check for stats changes (compare all key metrics)
                stats_changed = (
                    current_stats['active_users_count'] != last_stats['active_users_count'] or
                    current_stats['unique_users_count'] != last_stats['unique_users_count'] or
                    current_stats['recent_activities_count'] != last_stats['recent_activities_count']
                )
                if stats_changed:
                    stats_data = json.dumps({
                        'type': 'stats',
                        'stats': current_stats
                    })
                    yield f"data: {stats_data}\n\n"
                    last_stats = current_stats
                
                # Check for new sessions (more accurate than user_ids since users can have multiple sessions)
                new_session_ids = current_session_ids - last_session_ids
                if new_session_ids:
                    for session_id in new_session_ids:
                        user_data = next((u for u in current_users if u['session_id'] == session_id), None)
                        if user_data:
                            user_joined_data = json.dumps({
                                'type': 'user_joined',
                                'user': user_data,
                                'stats': current_stats  # Include stats update
                            })
                            yield f"data: {user_joined_data}\n\n"
                
                # Check for sessions that ended
                left_session_ids = last_session_ids - current_session_ids
                if left_session_ids:
                    for session_id in left_session_ids:
                        session_left_data = json.dumps({
                            'type': 'user_left',
                            'session_id': session_id
                        })
                        yield f"data: {session_left_data}\n\n"
                
                # Send full user list update periodically
                if heartbeat_counter % USERS_UPDATE_INTERVAL == 0:
                    users_update = json.dumps({
                        'type': 'users_update',
                        'users': current_users
                    })
                    yield f"data: {users_update}\n\n"
                
                # Send heartbeat periodically
                if heartbeat_counter % HEARTBEAT_INTERVAL == 0:
                    heartbeat_data = json.dumps({
                        'type': 'heartbeat',
                        'timestamp': current_stats['timestamp']
                    })
                    yield f"data: {heartbeat_data}\n\n"
                
                last_session_ids = current_session_ids
                heartbeat_counter += 1
                
        except asyncio.CancelledError:
            logger.info(f"Realtime stream cancelled for admin {current_user.phone}")
            # Don't yield after cancellation - client disconnected
            return
        except Exception as e:
            logger.error(f"Error in realtime stream: {e}", exc_info=True)
            try:
                error_data = json.dumps({
                    'type': 'error',
                    'error': str(e)
                })
                yield f"data: {error_data}\n\n"
            except Exception:
                # If we can't yield, client likely disconnected
                return
        finally:
            # Decrement connection count on cleanup (always runs, even on initial error)
            if user_id in _active_sse_connections:
                _active_sse_connections[user_id] = max(0, _active_sse_connections[user_id] - 1)
                if _active_sse_connections[user_id] == 0:
                    del _active_sse_connections[user_id]
                logger.debug(f"Admin {current_user.phone} SSE connection closed (remaining: {_active_sse_connections.get(user_id, 0)})")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

