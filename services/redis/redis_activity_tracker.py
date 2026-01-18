"""
Redis User Activity Tracker
============================

Tracks active users and their real-time activities using Redis.
Shared across all workers for accurate counts.

Features:
- Real-time active user tracking (shared across workers)
- Session management with automatic expiry
- Activity history with TTL
- Thread-safe atomic operations

Key Schema:
- activity:session:{session_id} -> hash{user_id, phone, name, ip, activity, ...}
- activity:user:{user_id} -> set{session_ids}
- activity:history -> list[{activity_entry_json}] (capped)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
import json
import logging
import uuid

import asyncio

from services.auth.ip_geolocation import get_geolocation_service
from services.monitoring.city_flag_tracker import get_city_flag_tracker
from services.redis.redis_client import is_redis_available, get_redis



logger = logging.getLogger(__name__)

# Beijing timezone (UTC+8)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))

def get_beijing_now() -> datetime:
    """Get current datetime in Beijing timezone (UTC+8)"""
    return datetime.now(BEIJING_TIMEZONE)


# Key prefixes
SESSION_PREFIX = "activity:session:"
USER_SESSIONS_PREFIX = "activity:user:"
HISTORY_KEY = "activity:history"

# Configuration
SESSION_TTL = 1800  # 30 minutes session timeout
MAX_HISTORY = 1000  # Keep last 1000 activities


class RedisActivityTracker:
    """
    Redis-based user activity tracker.

    Tracks active users and their sessions in Redis,
    shared across all workers for accurate active user counts.

    Falls back to in-memory tracking if Redis is unavailable.
    """

    # Activity type mappings
    ACTIVITY_TYPES = {
        'diagram_generation': 'Generating Diagram',
        'node_palette': 'Using Node Palette',
        'autocomplete': 'Auto-complete',
        'voice_conversation': 'Voice Conversation',
        'ai_assistant': 'AI Assistant',
        'export_png': 'Exporting PNG',
        'export_dingtalk': 'Exporting DingTalk',
        'login': 'Login',
        'logout': 'Logout',
        'page_view': 'Viewing Page',
    }

    def __init__(self):
        # In-memory fallback for when Redis is disabled
        self._memory_sessions: Dict[str, Dict] = {}
        self._memory_user_sessions: Dict[int, Set[str]] = {}
        self._memory_history: List[Dict] = []

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def start_session(
        self,
        user_id: int,
        user_phone: str,
        user_name: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        reuse_existing: bool = True
    ) -> str:
        """
        Start tracking a new user session.

        Args:
            user_id: User ID
            user_phone: User phone number
            user_name: Optional user name
            session_id: Optional custom session ID
            ip_address: Optional IP address
            reuse_existing: If True, reuse existing active session

        Returns:
            Session ID
        """
        if self._use_redis():
            return self._redis_start_session(
                user_id, user_phone, user_name, session_id, ip_address, reuse_existing
            )
        else:
            return self._memory_start_session(
                user_id, user_phone, user_name, session_id, ip_address, reuse_existing
            )

    def _redis_start_session(
        self,
        user_id: int,
        user_phone: str,
        user_name: Optional[str],
        session_id: Optional[str],
        ip_address: Optional[str],
        reuse_existing: bool
    ) -> str:
        """Start session using Redis."""
        redis = get_redis()
        if not redis:
            return self._memory_start_session(
                user_id, user_phone, user_name, session_id, ip_address, reuse_existing
            )

        try:
            # If reuse_existing, find existing session
            if reuse_existing and session_id is None:
                user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"
                existing_sessions = redis.smembers(user_sessions_key)

                if existing_sessions:
                    # Find most recent active session
                    for sid in existing_sessions:
                        session_key = f"{SESSION_PREFIX}{sid}"
                        if redis.exists(session_key):
                            # Refresh TTL and update info
                            redis.expire(session_key, SESSION_TTL)
                            if user_name:
                                redis.hset(session_key, "user_name", user_name)
                            if ip_address:
                                redis.hset(session_key, "ip_address", ip_address)
                            redis.hset(session_key, "last_activity", get_beijing_now().isoformat())
                            logger.debug("Reusing session %s for user %s", sid[:8], user_id)

                            # Record city flag for reused session (async, fire-and-forget)
                            # This ensures flags are shown for all active sessions, including returning users
                            if ip_address and ip_address != 'unknown':
                                self._record_city_flag_async(ip_address)

                            return sid

            # Create new session
            if session_id is None:
                session_id = f"session_{uuid.uuid4().hex[:12]}"

            now = get_beijing_now()
            session_key = f"{SESSION_PREFIX}{session_id}"
            user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"

            # Store session data
            session_data = {
                "session_id": session_id,
                "user_id": str(user_id),
                "user_phone": user_phone,
                "user_name": user_name or "",
                "ip_address": ip_address or "",
                "created_at": now.isoformat(),
                "last_activity": now.isoformat(),
                "current_activity": "",
                "activity_count": "0"
            }

            redis.hset(session_key, mapping=session_data)
            redis.expire(session_key, SESSION_TTL)

            # Add to user's session set
            redis.sadd(user_sessions_key, session_id)
            redis.expire(user_sessions_key, SESSION_TTL)

            # Log activity
            self._log_activity(user_id, user_phone, 'login', session_id=session_id)

            # Record city flag for new session (async, fire-and-forget)
            # This ensures flags are shown for all active sessions, not just logins
            if ip_address and ip_address != 'unknown':
                self._record_city_flag_async(ip_address)

            logger.debug("Started session %s for user %s", session_id[:8], user_id)
            return session_id

        except Exception as e:
            logger.error("[ActivityTracker] Redis error: %s", e)
            return self._memory_start_session(
                user_id, user_phone, user_name, session_id, ip_address, reuse_existing
            )

    def _record_city_flag_async(self, ip_address: str):
        """
        Record city flag asynchronously (fire-and-forget).

        This function schedules the city flag recording in a background task
        to avoid blocking the session creation.
        """
        try:
            async def _record_flag():
                try:
                    geolocation = get_geolocation_service()
                    location = await geolocation.get_location(ip_address)
                    if location and not location.get('is_fallback'):
                        city = location.get('city', '')
                        province = location.get('province', '')
                        lat = location.get('lat')
                        lng = location.get('lng')
                        if city or province:
                            flag_tracker = get_city_flag_tracker()
                            flag_tracker.record_city_flag(city, province, lat, lng)
                except Exception as e:
                    logger.debug("Failed to record city flag: %s", e)

            # Schedule async task (fire-and-forget)
            try:
                # Try to get the current event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Event loop is running, create a task
                    asyncio.create_task(_record_flag())
                except RuntimeError:
                    # No running event loop, try to get/create one
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(_record_flag())
                        else:
                            loop.run_until_complete(_record_flag())
                    except RuntimeError:
                        # No event loop available, create new one
                        asyncio.run(_record_flag())
            except Exception as e:
                logger.debug("Failed to schedule city flag recording: %s", e)
        except Exception as e:
            logger.debug("Failed to record city flag: %s", e)

    def _memory_start_session(
        self,
        user_id: int,
        user_phone: str,
        user_name: Optional[str],
        session_id: Optional[str],
        ip_address: Optional[str],
        reuse_existing: bool
    ) -> str:
        """Start session using in-memory storage (fallback)."""
        # Find existing session
        if reuse_existing and session_id is None:
            if user_id in self._memory_user_sessions:
                for sid in self._memory_user_sessions[user_id]:
                    if sid in self._memory_sessions:
                        # Update session info (consistent with Redis mode)
                        self._memory_sessions[sid]['last_activity'] = get_beijing_now()
                        if user_name:
                            self._memory_sessions[sid]['user_name'] = user_name
                        if ip_address:
                            self._memory_sessions[sid]['ip_address'] = ip_address

                        # Record city flag for reused session (async, fire-and-forget)
                        # This ensures flags are shown for all active sessions, including returning users
                        if ip_address and ip_address != 'unknown':
                            self._record_city_flag_async(ip_address)

                        return sid

        # Create new session
        if session_id is None:
            session_id = f"session_{uuid.uuid4().hex[:12]}"

        now = get_beijing_now()
        self._memory_sessions[session_id] = {
            'session_id': session_id,
            'user_id': user_id,
            'user_phone': user_phone,
            'user_name': user_name,
            'ip_address': ip_address,
            'created_at': now,
            'last_activity': now,
            'current_activity': None,
            'activity_count': 0
        }

        if user_id not in self._memory_user_sessions:
            self._memory_user_sessions[user_id] = set()
        self._memory_user_sessions[user_id].add(session_id)

        # Record city flag for new session (async, fire-and-forget)
        # This ensures flags are shown for all active sessions, not just logins
        if ip_address and ip_address != 'unknown':
            self._record_city_flag_async(ip_address)

        return session_id

    def end_session(self, session_id: Optional[str] = None, user_id: Optional[int] = None):
        """End a user session."""
        if self._use_redis():
            self._redis_end_session(session_id, user_id)
        else:
            self._memory_end_session(session_id, user_id)

    def _redis_end_session(self, session_id: Optional[str], user_id: Optional[int]):
        """End session using Redis."""
        redis = get_redis()
        if not redis:
            return self._memory_end_session(session_id, user_id)

        try:
            if session_id:
                session_key = f"{SESSION_PREFIX}{session_id}"
                session_data = redis.hgetall(session_key)

                if session_data:
                    uid = int(session_data.get('user_id', 0))
                    user_phone = session_data.get('user_phone', '')

                    # Log logout
                    self._log_activity(uid, user_phone, 'logout', session_id=session_id)

                    # Remove session
                    redis.delete(session_key)

                    # Remove from user's session set
                    user_sessions_key = f"{USER_SESSIONS_PREFIX}{uid}"
                    redis.srem(user_sessions_key, session_id)

                    logger.debug("Ended session %s", session_id[:8])

            elif user_id:
                user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"
                sessions = redis.smembers(user_sessions_key)

                for sid in sessions:
                    session_key = f"{SESSION_PREFIX}{sid}"
                    session_data = redis.hgetall(session_key)
                    if session_data:
                        user_phone = session_data.get('user_phone', '')
                        self._log_activity(user_id, user_phone, 'logout', session_id=sid)
                    redis.delete(session_key)

                redis.delete(user_sessions_key)
                logger.debug("Ended all sessions for user %s", user_id)

        except Exception as e:
            logger.error("[ActivityTracker] Redis error ending session: %s", e)

    def _memory_end_session(self, session_id: Optional[str], user_id: Optional[int]):
        """End session using in-memory storage."""
        if session_id and session_id in self._memory_sessions:
            session = self._memory_sessions[session_id]
            uid = session['user_id']
            del self._memory_sessions[session_id]

            if uid in self._memory_user_sessions:
                self._memory_user_sessions[uid].discard(session_id)
                if not self._memory_user_sessions[uid]:
                    del self._memory_user_sessions[uid]

        elif user_id and user_id in self._memory_user_sessions:
            for sid in list(self._memory_user_sessions[user_id]):
                if sid in self._memory_sessions:
                    del self._memory_sessions[sid]
            del self._memory_user_sessions[user_id]

    def record_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict] = None,
        session_id: Optional[str] = None,
        user_name: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Record a user activity."""
        if self._use_redis():
            self._redis_record_activity(user_id, user_phone, activity_type, details, session_id, user_name, ip_address)
        else:
            self._memory_record_activity(user_id, user_phone, activity_type, details, session_id, user_name, ip_address)

    def _redis_record_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict],
        session_id: Optional[str],
        user_name: Optional[str],
        ip_address: Optional[str]
    ):
        """Record activity using Redis."""
        redis = get_redis()
        if not redis:
            return self._memory_record_activity(
                user_id, user_phone, activity_type, details, session_id, user_name, ip_address
            )

        try:
            now = get_beijing_now()

            # Find or create session
            if session_id is None:
                session_id = self.start_session(user_id, user_phone, user_name=user_name, ip_address=ip_address)

            session_key = f"{SESSION_PREFIX}{session_id}"

            # Get IP address from session if not provided
            session_ip = ip_address
            if not session_ip and redis.exists(session_key):
                session_ip = redis.hget(session_key, "ip_address")
                if session_ip:
                    session_ip = session_ip.decode('utf-8') if isinstance(session_ip, bytes) else session_ip

            if redis.exists(session_key):
                # Update session
                pipe = redis.pipeline()
                pipe.hset(session_key, "last_activity", now.isoformat())
                pipe.hset(session_key, "current_activity", activity_type)
                pipe.hincrby(session_key, "activity_count", 1)
                # Update IP address if provided and session doesn't have one
                if session_ip and session_ip != 'unknown':
                    existing_ip = redis.hget(session_key, "ip_address")
                    if not existing_ip or existing_ip == b'unknown' or existing_ip == 'unknown':
                        pipe.hset(session_key, "ip_address", session_ip)
                # Update user_name if provided and session doesn't have one or it's empty
                if user_name:
                    existing_name = redis.hget(session_key, "user_name")
                    if not existing_name or existing_name == "":
                        pipe.hset(session_key, "user_name", user_name)
                pipe.expire(session_key, SESSION_TTL)
                pipe.execute()

            # Record city flag if IP address is available
            # This ensures flags appear when users use the app, not just at login
            if session_ip and session_ip != 'unknown':
                self._record_city_flag_async(session_ip)

            # Log activity
            self._log_activity(user_id, user_phone, activity_type, details, session_id)

        except Exception as e:
            logger.error("[ActivityTracker] Redis error recording activity: %s", e)

    def _memory_record_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict],
        session_id: Optional[str],
        user_name: Optional[str],
        ip_address: Optional[str]
    ):
        """Record activity using in-memory storage."""
        now = get_beijing_now()

        if session_id is None:
            session_id = self.start_session(user_id, user_phone, user_name=user_name, ip_address=ip_address)

        # Get IP address from session if not provided
        session_ip = ip_address
        if not session_ip and session_id in self._memory_sessions:
            session_ip = self._memory_sessions[session_id].get('ip_address')

        if session_id in self._memory_sessions:
            # Update IP address if provided
            if session_ip and session_ip != 'unknown':
                session_data = self._memory_sessions[session_id]
                existing_ip = session_data.get('ip_address')
                if not existing_ip or existing_ip == 'unknown':
                    session_data['ip_address'] = session_ip
            session = self._memory_sessions[session_id]
            session['last_activity'] = now
            session['current_activity'] = activity_type
            session['activity_count'] = session.get('activity_count', 0) + 1
            # Update user_name if provided and session doesn't have one or it's empty
            if user_name and (not session.get('user_name') or session.get('user_name') == ""):
                session['user_name'] = user_name

        # Record city flag if IP address is available
        # This ensures flags appear when users use the app, not just at login
        if session_ip and session_ip != 'unknown':
            self._record_city_flag_async(session_ip)

        # Log activity
        self._log_activity(user_id, user_phone, activity_type, details, session_id)

    def _log_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict] = None,
        session_id: Optional[str] = None
    ):
        """Log activity to history."""
        activity_label = self.ACTIVITY_TYPES.get(activity_type, activity_type)

        entry = {
            'timestamp': get_beijing_now().isoformat(),
            'user_id': user_id,
            'user_phone': user_phone,
            'activity_type': activity_type,
            'activity_label': activity_label,
            'details': details or {},
            'session_id': session_id
        }

        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    # Push to list and trim
                    redis.lpush(HISTORY_KEY, json.dumps(entry))
                    redis.ltrim(HISTORY_KEY, 0, MAX_HISTORY - 1)
                    return
                except Exception as e:
                    logger.error("[ActivityTracker] Redis error logging activity: %s", e)

        # Fallback to memory
        self._memory_history.append(entry)
        if len(self._memory_history) > MAX_HISTORY:
            self._memory_history = self._memory_history[-MAX_HISTORY:]

    def get_active_users(self, hours: int = 1) -> List[Dict]:
        """
        Get list of currently active users.

        Args:
            hours: Time window in hours - only return users active within this window (default: 1 hour)
        """
        if self._use_redis():
            return self._redis_get_active_users(hours)
        else:
            return self._memory_get_active_users(hours)

    def _redis_get_active_users(self, hours: int = 1) -> List[Dict]:
        """
        Get active users from Redis.

        Args:
            hours: Time window in hours - only return users active within this window (default: 1 hour)
        """
        redis = get_redis()
        if not redis:
            return self._memory_get_active_users(hours)

        try:
            # Calculate cutoff time (users active within last N hours)
            now = get_beijing_now()
            cutoff_time = now - timedelta(hours=hours)

            # Scan for all session keys
            active_users = []
            cursor = 0

            while True:
                cursor, keys = redis.scan(cursor, match=f"{SESSION_PREFIX}*", count=100)

                for key in keys:
                    session_data = redis.hgetall(key)
                    if session_data:
                        try:
                            # Parse dates with fallback to current time if invalid
                            try:
                                created_at = datetime.fromisoformat(session_data.get('created_at', ''))
                            except (ValueError, TypeError):
                                created_at = get_beijing_now()
                                session_id_val = session_data.get('session_id', 'unknown')
                                logger.debug(
                                    "Invalid created_at for session %s, using current time",
                                    session_id_val
                                )

                            try:
                                last_activity = datetime.fromisoformat(session_data.get('last_activity', ''))
                            except (ValueError, TypeError):
                                last_activity = get_beijing_now()
                                session_id_val = session_data.get('session_id', 'unknown')
                                logger.debug(
                                    "Invalid last_activity for session %s, using current time",
                                    session_id_val
                                )

                            # Filter: Only include users active within the time window
                            if last_activity < cutoff_time:
                                continue  # Skip sessions inactive for longer than the window

                            # Calculate duration with error handling
                            try:
                                duration = str(now - created_at).split('.', maxsplit=1)[0]
                            except Exception:
                                duration = '0:00:00'

                            user_data = {
                                'session_id': session_data.get('session_id', ''),
                                'user_id': int(session_data.get('user_id', 0)),
                                'user_phone': session_data.get('user_phone', ''),
                                'user_name': session_data.get('user_name', ''),
                                'ip_address': session_data.get('ip_address', ''),
                                'current_activity': session_data.get('current_activity', ''),
                                'current_activity_label': self.ACTIVITY_TYPES.get(
                                    session_data.get('current_activity', ''),
                                    session_data.get('current_activity', 'Unknown')
                                ),
                                'last_activity': last_activity.isoformat(),
                                'activity_count': int(session_data.get('activity_count', 0)),
                                'session_duration': duration
                            }
                            active_users.append(user_data)
                        except Exception as e:
                            logger.debug("Error parsing session data: %s", e)

                if cursor == 0:
                    break

            # Sort by last activity
            active_users.sort(key=lambda x: x['last_activity'], reverse=True)
            return active_users

        except Exception as e:
            logger.error("[ActivityTracker] Redis error getting active users: %s", e)
            return self._memory_get_active_users()

    def _memory_get_active_users(self, hours: int = 1) -> List[Dict]:
        """
        Get active users from in-memory storage.

        Args:
            hours: Time window in hours - only return users active within this window (default: 1 hour)
        """
        now = get_beijing_now()
        timeout = timedelta(hours=hours)  # Use configurable time window instead of fixed 30 minutes

        # Clean stale sessions (older than timeout)
        stale = [sid for sid, s in self._memory_sessions.items()
                 if now - s['last_activity'] > timeout]
        for sid in stale:
            self.end_session(session_id=sid)

        # Calculate cutoff time for filtering
        cutoff_time = now - timeout

        active_users = []
        for session_id, session in self._memory_sessions.items():
            # Filter: Only include users active within the time window
            if session['last_activity'] < cutoff_time:
                continue  # Skip sessions inactive for longer than the window

            user_data = {
                'session_id': session_id,
                'user_id': session['user_id'],
                'user_phone': session['user_phone'],
                'user_name': session.get('user_name'),
                'ip_address': session.get('ip_address'),
                'current_activity': session.get('current_activity'),
                'current_activity_label': self.ACTIVITY_TYPES.get(
                    session.get('current_activity', ''),
                    session.get('current_activity', 'Unknown')
                ),
                'last_activity': session['last_activity'].isoformat(),
                'activity_count': session.get('activity_count', 0),
                'session_duration': str(now - session['created_at']).split('.', maxsplit=1)[0]
            }
            active_users.append(user_data)

        active_users.sort(key=lambda x: x['last_activity'], reverse=True)
        return active_users

    def get_recent_activities(self, limit: int = 100) -> List[Dict]:
        """Get recent activity history."""
        if self._use_redis():
            return self._redis_get_recent_activities(limit)
        else:
            return self._memory_get_recent_activities(limit)

    def _redis_get_recent_activities(self, limit: int) -> List[Dict]:
        """Get recent activities from Redis."""
        redis = get_redis()
        if not redis:
            return self._memory_get_recent_activities(limit)

        try:
            entries = redis.lrange(HISTORY_KEY, 0, limit - 1)
            return [json.loads(entry) for entry in entries]
        except Exception as e:
            logger.error("[ActivityTracker] Redis error getting activities: %s", e)
            return self._memory_get_recent_activities(limit)

    def _memory_get_recent_activities(self, limit: int) -> List[Dict]:
        """Get recent activities from memory."""
        activities = self._memory_history[-limit:]
        return [
            {
                'timestamp': act['timestamp'] if isinstance(act['timestamp'], str)
                             else act['timestamp'].isoformat(),
                'user_id': act['user_id'],
                'user_phone': act['user_phone'],
                'activity_type': act['activity_type'],
                'activity_label': act['activity_label'],
                'details': act['details'],
                'session_id': act.get('session_id')
            }
            for act in reversed(activities)
        ]

    def get_stats(self) -> Dict:
        """Get overall statistics."""
        if self._use_redis():
            return self._redis_get_stats()
        else:
            return self._memory_get_stats()

    def _redis_get_stats(self) -> Dict:
        """Get stats from Redis."""
        redis = get_redis()
        if not redis:
            return self._memory_get_stats()

        try:
            # Count session keys
            session_count = 0
            user_ids = set()
            cursor = 0

            while True:
                cursor, keys = redis.scan(cursor, match=f"{SESSION_PREFIX}*", count=100)
                session_count += len(keys)

                for key in keys:
                    user_id = redis.hget(key, "user_id")
                    if user_id:
                        user_ids.add(user_id)

                if cursor == 0:
                    break

            history_count = redis.llen(HISTORY_KEY) or 0

            return {
                'active_users_count': session_count,
                'unique_users_count': len(user_ids),
                'total_sessions': session_count,
                'recent_activities_count': history_count,
                'storage': 'redis',
                'timestamp': get_beijing_now().isoformat()
            }

        except Exception as e:
            logger.error("[ActivityTracker] Redis error getting stats: %s", e)
            return self._memory_get_stats()

    def _memory_get_stats(self) -> Dict:
        """Get stats from in-memory storage."""
        return {
            'active_users_count': len(self._memory_sessions),
            'unique_users_count': len(self._memory_user_sessions),
            'total_sessions': len(self._memory_sessions),
            'recent_activities_count': len(self._memory_history),
            'storage': 'memory',
            'timestamp': get_beijing_now().isoformat()
        }


class ActivityTrackerSingleton:
    """Singleton wrapper for RedisActivityTracker."""
    _instance: Optional[RedisActivityTracker] = None

    @classmethod
    def get_instance(cls) -> RedisActivityTracker:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = RedisActivityTracker()
        return cls._instance


def get_activity_tracker() -> RedisActivityTracker:
    """Get or create global activity tracker instance."""
    return ActivityTrackerSingleton.get_instance()
