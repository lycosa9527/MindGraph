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
from typing import Any, Dict, List, Optional, Set
import asyncio
import json
import logging
import uuid

from services.auth.ip_geolocation import get_geolocation_service
from services.monitoring.city_flag_tracker import get_city_flag_tracker
from services.redis import keys as _keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available


logger = logging.getLogger(__name__)

# Beijing timezone (UTC+8)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))


def get_beijing_now() -> datetime:
    """Get current datetime in Beijing timezone (UTC+8)"""
    return datetime.now(BEIJING_TIMEZONE)


# Key fragments derived from central registry so changes to keys.py propagate here.
SESSION_PREFIX = _keys.ACTIVITY_SESSION.split("{", maxsplit=1)[0]  # "activity:session:"
USER_SESSIONS_PREFIX = _keys.ACTIVITY_USER.split("{", maxsplit=1)[0]  # "activity:user:"
HISTORY_KEY = _keys.ACTIVITY_HISTORY

# Configuration
SESSION_TTL = _keys.TTL_ACTIVITY_SESSION
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
        "diagram_generation": "Generating Diagram",
        "node_palette": "Using Node Palette",
        "autocomplete": "Auto-complete",
        "voice_conversation": "Voice Conversation",
        "ai_assistant": "AI Assistant",
        "export_png": "Exporting PNG",
        "export_dingtalk": "Exporting DingTalk",
        "login": "Login",
        "logout": "Logout",
        "page_view": "Viewing Page",
    }

    def __init__(self):
        # In-memory fallback for when Redis is disabled
        self._memory_sessions: Dict[str, Dict] = {}
        self._memory_user_sessions: Dict[int, Set[str]] = {}
        self._memory_history: List[Dict] = []

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    async def start_session(
        self,
        user_id: int,
        user_phone: str,
        user_name: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        reuse_existing: bool = True,
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
            return await self._redis_start_session(
                user_id, user_phone, user_name, session_id, ip_address, reuse_existing
            )
        return self._memory_start_session(user_id, user_phone, user_name, session_id, ip_address, reuse_existing)

    async def _redis_start_session(
        self,
        user_id: int,
        user_phone: str,
        user_name: Optional[str],
        session_id: Optional[str],
        ip_address: Optional[str],
        reuse_existing: bool,
    ) -> str:
        """Start session using Redis.

        Session reuse: batch-checks all candidate sessions with a single
        pipelined EXISTS, then updates the first live one in one pipeline.
        New session: creates the hash + set membership in one pipeline.
        """
        redis_client = get_async_redis()
        if not redis_client:
            return self._memory_start_session(user_id, user_phone, user_name, session_id, ip_address, reuse_existing)

        try:
            if reuse_existing and session_id is None:
                reused = await self._try_reuse_session(redis_client, user_id, user_name, ip_address)
                if reused:
                    return reused

            return await self._create_new_session(redis_client, user_id, user_phone, user_name, session_id, ip_address)

        except Exception as exc:
            logger.error("[ActivityTracker] Redis error: %s", exc)
            return self._memory_start_session(user_id, user_phone, user_name, session_id, ip_address, reuse_existing)

    async def _try_reuse_session(
        self,
        redis_client: Any,
        user_id: int,
        user_name: Optional[str],
        ip_address: Optional[str],
    ) -> Optional[str]:
        """Try to reuse an existing active session, minimising round-trips.

        Also garbage-collects expired session IDs from the user's session
        set so it does not grow without bound.
        """
        user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"
        existing_sessions = await redis_client.smembers(user_sessions_key)
        if not existing_sessions:
            return None

        session_list = list(existing_sessions)
        session_keys = [f"{SESSION_PREFIX}{sid}" for sid in session_list]

        async with redis_client.pipeline(transaction=False) as pipe:
            for key in session_keys:
                pipe.exists(key)
            alive_flags = await pipe.execute()

        dead_sids = []
        reused_sid = None

        for sid, alive in zip(session_list, alive_flags):
            if not alive:
                dead_sids.append(sid)
                continue

            if reused_sid is not None:
                continue

            session_key = f"{SESSION_PREFIX}{sid}"
            async with redis_client.pipeline(transaction=False) as update_pipe:
                update_pipe.expire(session_key, SESSION_TTL)
                if user_name:
                    update_pipe.hset(session_key, "user_name", user_name)
                if ip_address:
                    update_pipe.hset(session_key, "ip_address", ip_address)
                update_pipe.hset(session_key, "last_activity", get_beijing_now().isoformat())
                await update_pipe.execute()

            reused_sid = sid

        # Remove expired session IDs from the user's set to prevent
        # unbounded growth of ghost entries.
        if dead_sids:
            await redis_client.srem(user_sessions_key, *dead_sids)

        if reused_sid:
            logger.debug("Reusing session %s for user %s", reused_sid[:8], user_id)
            if ip_address and ip_address != "unknown":
                self._record_city_flag_async(ip_address)

        return reused_sid

    async def _create_new_session(
        self,
        redis_client: Any,
        user_id: int,
        user_phone: str,
        user_name: Optional[str],
        session_id: Optional[str],
        ip_address: Optional[str],
    ) -> str:
        """Create a brand-new session using a single pipeline."""
        if session_id is None:
            session_id = f"session_{uuid.uuid4().hex[:12]}"

        now = get_beijing_now()
        session_key = f"{SESSION_PREFIX}{session_id}"
        user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"

        session_data = {
            "session_id": session_id,
            "user_id": str(user_id),
            "user_phone": user_phone,
            "user_name": user_name or "",
            "ip_address": ip_address or "",
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "current_activity": "",
            "activity_count": "0",
        }

        async with redis_client.pipeline(transaction=False) as pipe:
            pipe.hset(session_key, mapping=session_data)
            pipe.expire(session_key, SESSION_TTL)
            pipe.sadd(user_sessions_key, session_id)
            pipe.expire(user_sessions_key, SESSION_TTL)
            await pipe.execute()

        await self._log_activity(user_id, user_phone, "login", session_id=session_id)

        if ip_address and ip_address != "unknown":
            self._record_city_flag_async(ip_address)

        logger.debug("Started session %s for user %s", session_id[:8], user_id)
        return session_id

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
                    if location and not location.get("is_fallback"):
                        city = location.get("city", "")
                        province = location.get("province", "")
                        lat = location.get("lat")
                        lng = location.get("lng")
                        if city or province:
                            flag_tracker = get_city_flag_tracker()
                            await flag_tracker.record_city_flag(city, province, lat, lng)
                except Exception as e:
                    logger.debug("Failed to record city flag: %s", e)

            try:
                try:
                    asyncio.get_running_loop()
                    asyncio.create_task(_record_flag())
                except RuntimeError:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(_record_flag())
                        else:
                            loop.run_until_complete(_record_flag())
                    except RuntimeError:
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
        reuse_existing: bool,
    ) -> str:
        """Start session using in-memory storage (fallback)."""
        if reuse_existing and session_id is None:
            if user_id in self._memory_user_sessions:
                for sid in self._memory_user_sessions[user_id]:
                    if sid in self._memory_sessions:
                        self._memory_sessions[sid]["last_activity"] = get_beijing_now()
                        if user_name:
                            self._memory_sessions[sid]["user_name"] = user_name
                        if ip_address:
                            self._memory_sessions[sid]["ip_address"] = ip_address

                        if ip_address and ip_address != "unknown":
                            self._record_city_flag_async(ip_address)

                        return sid

        if session_id is None:
            session_id = f"session_{uuid.uuid4().hex[:12]}"

        now = get_beijing_now()
        self._memory_sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "user_phone": user_phone,
            "user_name": user_name,
            "ip_address": ip_address,
            "created_at": now,
            "last_activity": now,
            "current_activity": None,
            "activity_count": 0,
        }

        if user_id not in self._memory_user_sessions:
            self._memory_user_sessions[user_id] = set()
        self._memory_user_sessions[user_id].add(session_id)

        if ip_address and ip_address != "unknown":
            self._record_city_flag_async(ip_address)

        return session_id

    async def end_session(self, session_id: Optional[str] = None, user_id: Optional[int] = None):
        """End a user session."""
        if self._use_redis():
            await self._redis_end_session(session_id, user_id)
        else:
            self._memory_end_session(session_id, user_id)

    async def _redis_end_session(self, session_id: Optional[str], user_id: Optional[int]):
        """End session using Redis."""
        redis = get_async_redis()
        if not redis:
            self._memory_end_session(session_id, user_id)
            return

        try:
            if session_id:
                session_key = f"{SESSION_PREFIX}{session_id}"
                session_data = await redis.hgetall(session_key)

                if session_data:
                    uid = int(session_data.get("user_id", 0))
                    user_phone = session_data.get("user_phone", "")

                    await self._log_activity(uid, user_phone, "logout", session_id=session_id)

                    await redis.delete(session_key)

                    user_sessions_key = f"{USER_SESSIONS_PREFIX}{uid}"
                    await redis.srem(user_sessions_key, session_id)

                    logger.debug("Ended session %s", session_id[:8])

            elif user_id:
                user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"
                sessions = await redis.smembers(user_sessions_key)

                for sid in sessions:
                    session_key = f"{SESSION_PREFIX}{sid}"
                    session_data = await redis.hgetall(session_key)
                    if session_data:
                        user_phone = session_data.get("user_phone", "")
                        await self._log_activity(user_id, user_phone, "logout", session_id=sid)
                    await redis.delete(session_key)

                await redis.delete(user_sessions_key)
                logger.debug("Ended all sessions for user %s", user_id)

        except Exception as e:
            logger.error("[ActivityTracker] Redis error ending session: %s", e)

    def _memory_end_session(self, session_id: Optional[str], user_id: Optional[int]):
        """End session using in-memory storage."""
        if session_id and session_id in self._memory_sessions:
            session = self._memory_sessions[session_id]
            uid = session["user_id"]
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

    async def record_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict] = None,
        session_id: Optional[str] = None,
        user_name: Optional[str] = None,
        ip_address: Optional[str] = None,
    ):
        """Record a user activity."""
        if self._use_redis():
            await self._redis_record_activity(
                user_id,
                user_phone,
                activity_type,
                details,
                session_id,
                user_name,
                ip_address,
            )
        else:
            await self._memory_record_activity(
                user_id,
                user_phone,
                activity_type,
                details,
                session_id,
                user_name,
                ip_address,
            )

    async def _redis_record_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict],
        session_id: Optional[str],
        user_name: Optional[str],
        ip_address: Optional[str],
    ):
        """Record activity using Redis."""
        redis = get_async_redis()
        if not redis:
            await self._memory_record_activity(
                user_id,
                user_phone,
                activity_type,
                details,
                session_id,
                user_name,
                ip_address,
            )
            return

        try:
            now = get_beijing_now()

            if session_id is None:
                session_id = await self.start_session(user_id, user_phone, user_name=user_name, ip_address=ip_address)

            session_key = f"{SESSION_PREFIX}{session_id}"

            session_ip = ip_address
            if not session_ip and await redis.exists(session_key):
                session_ip = await redis.hget(session_key, "ip_address")
                if session_ip:
                    session_ip = session_ip.decode("utf-8") if isinstance(session_ip, bytes) else session_ip

            if await redis.exists(session_key):
                async with redis.pipeline(transaction=False) as pipe:
                    pipe.hset(session_key, "last_activity", now.isoformat())
                    pipe.hset(session_key, "current_activity", activity_type)
                    pipe.hincrby(session_key, "activity_count", 1)
                    if session_ip and session_ip != "unknown":
                        existing_ip = await redis.hget(session_key, "ip_address")
                        if not existing_ip or existing_ip == "unknown":
                            pipe.hset(session_key, "ip_address", session_ip)
                    if user_name:
                        existing_name = await redis.hget(session_key, "user_name")
                        if not existing_name or existing_name == "":
                            pipe.hset(session_key, "user_name", user_name)
                    pipe.expire(session_key, SESSION_TTL)
                    await pipe.execute()

            if session_ip and session_ip != "unknown":
                self._record_city_flag_async(session_ip)

            await self._log_activity(user_id, user_phone, activity_type, details, session_id)

        except Exception as e:
            logger.error("[ActivityTracker] Redis error recording activity: %s", e)

    async def _memory_record_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict],
        session_id: Optional[str],
        user_name: Optional[str],
        ip_address: Optional[str],
    ):
        """Record activity using in-memory storage."""
        now = get_beijing_now()

        if session_id is None:
            session_id = await self.start_session(user_id, user_phone, user_name=user_name, ip_address=ip_address)

        session_ip = ip_address
        if not session_ip and session_id in self._memory_sessions:
            session_ip = self._memory_sessions[session_id].get("ip_address")

        if session_id in self._memory_sessions:
            if session_ip and session_ip != "unknown":
                session_data = self._memory_sessions[session_id]
                existing_ip = session_data.get("ip_address")
                if not existing_ip or existing_ip == "unknown":
                    session_data["ip_address"] = session_ip
            session = self._memory_sessions[session_id]
            session["last_activity"] = now
            session["current_activity"] = activity_type
            session["activity_count"] = session.get("activity_count", 0) + 1
            if user_name and (not session.get("user_name") or session.get("user_name") == ""):
                session["user_name"] = user_name

        if session_ip and session_ip != "unknown":
            self._record_city_flag_async(session_ip)

        await self._log_activity(user_id, user_phone, activity_type, details, session_id)

    async def _log_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict] = None,
        session_id: Optional[str] = None,
    ):
        """Log activity to history."""
        activity_label = self.ACTIVITY_TYPES.get(activity_type, activity_type)

        entry = {
            "timestamp": get_beijing_now().isoformat(),
            "user_id": user_id,
            "user_phone": user_phone,
            "activity_type": activity_type,
            "activity_label": activity_label,
            "details": details or {},
            "session_id": session_id,
        }

        if self._use_redis():
            redis = get_async_redis()
            if redis:
                try:
                    async with redis.pipeline(transaction=False) as pipe:
                        pipe.lpush(HISTORY_KEY, json.dumps(entry))
                        pipe.ltrim(HISTORY_KEY, 0, MAX_HISTORY - 1)
                        await pipe.execute()
                    return
                except Exception as e:
                    logger.error("[ActivityTracker] Redis error logging activity: %s", e)

        # Fallback to memory
        self._memory_history.append(entry)
        if len(self._memory_history) > MAX_HISTORY:
            self._memory_history = self._memory_history[-MAX_HISTORY:]

    async def get_active_users(self, hours: int = 1) -> List[Dict]:
        """
        Get list of currently active users.

        Args:
            hours: Time window in hours - only return users active within this window (default: 1 hour)
        """
        if self._use_redis():
            return await self._redis_get_active_users(hours)
        return await self._memory_get_active_users(hours)

    async def _redis_get_active_users(self, hours: int = 1) -> List[Dict]:
        """
        Get active users from Redis.

        Args:
            hours: Time window in hours - only return users active within this window (default: 1 hour)
        """
        redis = get_async_redis()
        if not redis:
            return await self._memory_get_active_users(hours)

        try:
            now = get_beijing_now()
            cutoff_time = now - timedelta(hours=hours)

            active_users = []
            cursor = 0

            while True:
                cursor, keys = await redis.scan(cursor, match=_keys.ACTIVITY_SESSION_PATTERN, count=100)

                for key in keys:
                    session_data = await redis.hgetall(key)
                    if not session_data:
                        continue
                    try:
                        try:
                            created_at = datetime.fromisoformat(session_data.get("created_at", ""))
                        except (ValueError, TypeError):
                            created_at = get_beijing_now()
                            session_id_val = session_data.get("session_id", "unknown")
                            logger.debug(
                                "Invalid created_at for session %s, using current time",
                                session_id_val,
                            )

                        try:
                            last_activity = datetime.fromisoformat(session_data.get("last_activity", ""))
                        except (ValueError, TypeError):
                            last_activity = get_beijing_now()
                            session_id_val = session_data.get("session_id", "unknown")
                            logger.debug(
                                "Invalid last_activity for session %s, using current time",
                                session_id_val,
                            )

                        if last_activity < cutoff_time:
                            continue

                        try:
                            duration = str(now - created_at).split(".", maxsplit=1)[0]
                        except Exception:
                            duration = "0:00:00"

                        user_data = {
                            "session_id": session_data.get("session_id", ""),
                            "user_id": int(session_data.get("user_id", 0)),
                            "user_phone": session_data.get("user_phone", ""),
                            "user_name": session_data.get("user_name", ""),
                            "ip_address": session_data.get("ip_address", ""),
                            "current_activity": session_data.get("current_activity", ""),
                            "current_activity_label": self.ACTIVITY_TYPES.get(
                                session_data.get("current_activity", ""),
                                session_data.get("current_activity", "Unknown"),
                            ),
                            "last_activity": last_activity.isoformat(),
                            "activity_count": int(session_data.get("activity_count", 0)),
                            "session_duration": duration,
                        }
                        active_users.append(user_data)
                    except Exception as e:
                        logger.debug("Error parsing session data: %s", e)

                if cursor == 0:
                    break

            active_users.sort(key=lambda x: x["last_activity"], reverse=True)
            return active_users

        except Exception as e:
            logger.error("[ActivityTracker] Redis error getting active users: %s", e)
            return await self._memory_get_active_users()

    async def _memory_get_active_users(self, hours: int = 1) -> List[Dict]:
        """
        Get active users from in-memory storage.

        Args:
            hours: Time window in hours - only return users active within this window (default: 1 hour)
        """
        now = get_beijing_now()
        timeout = timedelta(hours=hours)

        stale = [sid for sid, s in self._memory_sessions.items() if now - s["last_activity"] > timeout]
        for sid in stale:
            await self.end_session(session_id=sid)

        cutoff_time = now - timeout

        active_users = []
        for session_id, session in self._memory_sessions.items():
            if session["last_activity"] < cutoff_time:
                continue

            user_data = {
                "session_id": session_id,
                "user_id": session["user_id"],
                "user_phone": session["user_phone"],
                "user_name": session.get("user_name"),
                "ip_address": session.get("ip_address"),
                "current_activity": session.get("current_activity"),
                "current_activity_label": self.ACTIVITY_TYPES.get(
                    session.get("current_activity", ""),
                    session.get("current_activity", "Unknown"),
                ),
                "last_activity": session["last_activity"].isoformat(),
                "activity_count": session.get("activity_count", 0),
                "session_duration": str(now - session["created_at"]).split(".", maxsplit=1)[0],
            }
            active_users.append(user_data)

        active_users.sort(key=lambda x: x["last_activity"], reverse=True)
        return active_users

    async def get_recent_activities(self, limit: int = 100) -> List[Dict]:
        """Get recent activity history."""
        if self._use_redis():
            return await self._redis_get_recent_activities(limit)
        return self._memory_get_recent_activities(limit)

    async def _redis_get_recent_activities(self, limit: int) -> List[Dict]:
        """Get recent activities from Redis."""
        redis = get_async_redis()
        if not redis:
            return self._memory_get_recent_activities(limit)

        try:
            entries = await redis.lrange(HISTORY_KEY, 0, limit - 1)
            return [json.loads(entry) for entry in entries]
        except Exception as e:
            logger.error("[ActivityTracker] Redis error getting activities: %s", e)
            return self._memory_get_recent_activities(limit)

    def _memory_get_recent_activities(self, limit: int) -> List[Dict]:
        """Get recent activities from memory."""
        activities = self._memory_history[-limit:]
        return [
            {
                "timestamp": act["timestamp"] if isinstance(act["timestamp"], str) else act["timestamp"].isoformat(),
                "user_id": act["user_id"],
                "user_phone": act["user_phone"],
                "activity_type": act["activity_type"],
                "activity_label": act["activity_label"],
                "details": act["details"],
                "session_id": act.get("session_id"),
            }
            for act in reversed(activities)
        ]

    async def get_stats(self) -> Dict:
        """Get overall statistics."""
        if self._use_redis():
            return await self._redis_get_stats()
        return self._memory_get_stats()

    async def _redis_get_stats(self) -> Dict:
        """Get stats from Redis."""
        redis = get_async_redis()
        if not redis:
            return self._memory_get_stats()

        try:
            all_keys = []
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=_keys.ACTIVITY_SESSION_PATTERN, count=100)
                all_keys.extend(keys)
                if cursor == 0:
                    break

            session_count = len(all_keys)
            user_ids: set = set()

            if all_keys:
                async with redis.pipeline(transaction=False) as pipe:
                    for key in all_keys:
                        pipe.hget(key, "user_id")
                    results = await pipe.execute()
                for uid in results:
                    if uid:
                        user_ids.add(uid)

            history_count = await redis.llen(HISTORY_KEY) or 0

            return {
                "active_users_count": session_count,
                "unique_users_count": len(user_ids),
                "total_sessions": session_count,
                "recent_activities_count": history_count,
                "storage": "redis",
                "timestamp": get_beijing_now().isoformat(),
            }

        except Exception as exc:
            logger.error("[ActivityTracker] Redis error getting stats: %s", exc)
            return self._memory_get_stats()

    def _memory_get_stats(self) -> Dict:
        """Get stats from in-memory storage."""
        return {
            "active_users_count": len(self._memory_sessions),
            "unique_users_count": len(self._memory_user_sessions),
            "total_sessions": len(self._memory_sessions),
            "recent_activities_count": len(self._memory_history),
            "storage": "memory",
            "timestamp": get_beijing_now().isoformat(),
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
