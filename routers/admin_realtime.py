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
from services.user_activity_tracker import get_activity_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/admin/realtime", tags=["Admin - Realtime"])


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
    
    logger.info(f"Admin {current_user.phone} started realtime stream")
    
    async def event_generator():
        """Generate SSE events from activity tracker."""
        tracker = get_activity_tracker()
        last_stats = None
        last_user_ids = set()
        
        try:
            # Send initial state
            stats = tracker.get_stats()
            active_users = tracker.get_active_users()
            
            initial_data = json.dumps({
                'type': 'initial',
                'stats': stats,
                'users': active_users
            })
            yield f"data: {initial_data}\n\n"
            
            last_stats = stats
            last_user_ids = {u['user_id'] for u in active_users}
            
            # Poll for updates
            heartbeat_counter = 0
            last_session_ids = {u['session_id'] for u in active_users}
            
            while True:
                await asyncio.sleep(1)  # Check every second
                
                # Get current state
                current_stats = tracker.get_stats()
                current_users = tracker.get_active_users()
                current_session_ids = {u['session_id'] for u in current_users}
                current_user_ids = {u['user_id'] for u in current_users}
                
                # Check for stats changes
                if current_stats['active_users_count'] != last_stats['active_users_count']:
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
                                'user': user_data
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
                
                # Send full user list update periodically (every 5 seconds)
                if heartbeat_counter % 5 == 0:
                    users_update = json.dumps({
                        'type': 'users_update',
                        'users': current_users
                    })
                    yield f"data: {users_update}\n\n"
                
                # Send heartbeat every 10 seconds
                if heartbeat_counter % 10 == 0:
                    heartbeat_data = json.dumps({
                        'type': 'heartbeat',
                        'timestamp': current_stats['timestamp']
                    })
                    yield f"data: {heartbeat_data}\n\n"
                
                last_session_ids = current_session_ids
                last_user_ids = current_user_ids
                heartbeat_counter += 1
                
        except asyncio.CancelledError:
            logger.info(f"Realtime stream cancelled for admin {current_user.phone}")
            yield "data: {\"type\": \"stream_closed\"}\n\n"
        except Exception as e:
            logger.error(f"Error in realtime stream: {e}", exc_info=True)
            error_data = json.dumps({
                'type': 'error',
                'error': str(e)
            })
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

