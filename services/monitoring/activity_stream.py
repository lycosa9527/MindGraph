from datetime import datetime, timezone
from typing import Dict, Optional
import asyncio
import json
import logging
import re

from services.redis.redis_client import is_redis_available, get_redis

"""
Activity Stream Service
=======================

Real-time activity broadcasting service for public dashboard.
Manages SSE connections and broadcasts user activity events.

Features:
- Maintain active SSE connections
- Broadcast activity events to all connected clients
- User name masking for privacy (e.g., "王一二" -> "王**", "John Smith" -> "J*** S****")
- Store recent activities in Redis

Key Schema:
- dashboard:activities -> List of recent activities (max 100, TTL: 1 hour)
- user:anon:{user_id} -> Anonymized username (deprecated, kept for backward compatibility)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)

# Key prefixes
ACTIVITIES_KEY = "dashboard:activities"
ANON_USER_PREFIX = "user:anon:"
DEDUP_PREFIX = "dashboard:activity_dedup:"

# Max activities to store
MAX_ACTIVITIES = 100

# Activities TTL: 1 hour
ACTIVITIES_TTL_SECONDS = 3600

# Deduplication window: 60 seconds (to catch concurrent auto-complete requests)
# Some diagram types (e.g., mindmap) can take up to 30 seconds to generate,
# so we use a longer window to ensure all concurrent requests are deduplicated
DEDUP_WINDOW_SECONDS = 60


class ActivityStreamService:
    """
    Activity stream service for broadcasting events to SSE connections.

    Thread-safe: Uses asyncio.Queue for each connection.
    Graceful degradation: Works without Redis (in-memory only).
    """

    def __init__(self):
        """Initialize activity stream service."""
        # Map connection_id -> asyncio.Queue for broadcasting
        self._connections: Dict[str, asyncio.Queue] = {}
        # Counter for anonymized usernames
        self._anon_counter = 0
        # In-memory recent activities (fallback)
        self._memory_activities = []

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def _mask_user_name(self, name: Optional[str]) -> str:
        """
        Mask user name for privacy.

        Examples:
        - "王一二" -> "王**"
        - "张三" -> "张*"
        - "John Smith" -> "J*** S****"
        - "A" -> "*"
        - None or empty -> "User *"

        Args:
            name: User's real name (can be None or empty)

        Returns:
            Masked name string
        """
        if not name or not name.strip():
            return "User *"

        name = name.strip()

        # Check if name contains Chinese characters
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', name))

        if has_chinese:
            # Chinese name: keep first character, mask the rest
            if len(name) == 1:
                return "*"
            first_char = name[0]
            masked = "*" * (len(name) - 1)
            return f"{first_char}{masked}"
        else:
            # English/Western name: keep first char of each word, mask the rest
            words = name.split()
            masked_words = []
            for word in words:
                if len(word) == 1:
                    masked_words.append("*")
                else:
                    first_char = word[0]
                    masked = "*" * (len(word) - 1)
                    masked_words.append(f"{first_char}{masked}")
            return " ".join(masked_words)

    def _get_anon_username(self, user_id: int) -> str:
        """
        Get anonymized username for a user_id.

        DEPRECATED: This method is kept for backward compatibility but
        should not be used. Use _mask_user_name() instead.

        Uses consistent mapping stored in Redis or memory.
        """
        if self._use_redis():
            try:
                redis = get_redis()
                if redis:
                    anon_key = f"{ANON_USER_PREFIX}{user_id}"
                    cached_username = redis.get(anon_key)
                    if cached_username:
                        return cached_username

                    # Generate new anonymized username
                    # Use atomic Redis counter for consistent mapping across workers
                    counter_key = "dashboard:anon_counter"
                    counter = redis.incr(counter_key)  # Atomic increment, starts at 1
                    # chr(65) = 'A', chr(66) = 'B', etc.
                    username = f"User {chr(64 + counter)}"  # counter=1 -> 'A', counter=2 -> 'B'
                    redis.set(anon_key, username)  # No expiration (persistent mapping)
                    return username
            except Exception as e:
                logger.error("[ActivityStream] Error getting anonymized username: %s", e)

        # Fallback: in-memory mapping
        if not hasattr(self, '_anon_map'):
            self._anon_map = {}

        if user_id not in self._anon_map:
            self._anon_counter += 1
            self._anon_map[user_id] = f"User {chr(64 + self._anon_counter)}"  # User A (65), User B (66), etc.

        return self._anon_map[user_id]

    def add_connection(self, connection_id: str) -> asyncio.Queue:
        """
        Register a new SSE connection.

        Args:
            connection_id: Unique connection identifier

        Returns:
            asyncio.Queue for sending events to this connection
        """
        queue = asyncio.Queue()
        self._connections[connection_id] = queue
        logger.debug("[ActivityStream] Added connection: %s (total: %s)", connection_id, len(self._connections))
        return queue

    def remove_connection(self, connection_id: str):
        """
        Unregister an SSE connection.

        Args:
            connection_id: Connection identifier to remove
        """
        if connection_id in self._connections:
            del self._connections[connection_id]
            logger.debug(
                "[ActivityStream] Removed connection: %s (remaining: %s)",
                connection_id,
                len(self._connections)
            )

    def _check_and_set_dedup(self, user_id: int, action: str, diagram_type: str) -> bool:
        """
        Check if activity was already broadcast recently (deduplication).
        Uses Redis SETNX with TTL for atomic check-and-set operation.

        Args:
            user_id: User ID
            action: Action type (e.g., "generated")
            diagram_type: Diagram type (e.g., "mindmap")

        Returns:
            True if this is a duplicate (should skip), False if new (should broadcast)
        """
        # Create deduplication key: user_id + action + diagram_type
        dedup_key = f"{DEDUP_PREFIX}{user_id}:{action}:{diagram_type}"

        try:
            redis = get_redis()
            if not redis:
                # Redis unavailable - allow broadcast (shouldn't happen in production)
                logger.warning("[ActivityStream] Redis unavailable, skipping deduplication check")
                return False

            # SETNX: Set if not exists, returns True if set, False if already exists
            # This is atomic - perfect for deduplication
            was_set = redis.set(
                dedup_key,
                "1",
                ex=DEDUP_WINDOW_SECONDS,  # TTL: 60 seconds
                nx=True  # Only set if not exists
            )
            # If was_set is True, this is the first request (not duplicate)
            # If was_set is False, key already exists (duplicate)
            return not was_set  # Return True if duplicate
        except Exception as e:
            logger.error("[ActivityStream] Error checking dedup in Redis: %s", e)
            # On error, allow broadcast (fail open)
            return False

    def _store_activity(self, activity: Dict):
        """
        Store activity in Redis and memory.

        Note: Activities are stored in Redis only (not database) since history
        is not critical information. Redis provides sufficient persistence with
        TTL of 1 hour and max 100 items.
        """
        # Store in Redis (for real-time access and page load history)
        if self._use_redis():
            try:
                redis = get_redis()
                if redis:
                    # Add to list (left push)
                    redis.lpush(ACTIVITIES_KEY, json.dumps(activity, ensure_ascii=False))  # Preserve UTF-8 characters
                    # Trim to max size
                    redis.ltrim(ACTIVITIES_KEY, 0, MAX_ACTIVITIES - 1)
                    # Set TTL
                    redis.expire(ACTIVITIES_KEY, ACTIVITIES_TTL_SECONDS)
            except Exception as e:
                logger.error("[ActivityStream] Error storing activity in Redis: %s", e)

        # Fallback: in-memory storage (when Redis unavailable)
        self._memory_activities.insert(0, activity)
        if len(self._memory_activities) > MAX_ACTIVITIES:
            self._memory_activities = self._memory_activities[:MAX_ACTIVITIES]

    async def broadcast_activity(
        self,
        user_id: int,
        action: str,
        diagram_type: str,
        topic: str = "",
        user_name: Optional[str] = None
    ):
        """
        Broadcast an activity event to all connected clients.

        Deduplication: Prevents duplicate broadcasts for the same user/action/diagram_type
        within a 60-second window. This prevents multiple activity entries when
        auto-complete makes concurrent API calls to multiple LLM models (which can take
        up to 30 seconds for some diagram types like mindmap).

        Args:
            user_id: User ID
            action: Action type (e.g., "generated")
            diagram_type: Diagram type (e.g., "mindmap", "concept_map")
            topic: Topic/prompt (deprecated, not used in frontend)
            user_name: User's real name (will be masked for privacy)
        """
        # Check for duplicate activity (deduplication)
        # This prevents multiple broadcasts when auto-complete makes concurrent requests
        is_duplicate = self._check_and_set_dedup(user_id, action, diagram_type)
        if is_duplicate:
            logger.debug("[ActivityStream] Skipping duplicate activity: user %s, %s %s", user_id, action, diagram_type)
            return

        # Mask user name for privacy
        masked_username = self._mask_user_name(user_name)

        # Create activity event (topic field removed as it's not used in frontend)
        activity = {
            "type": "activity",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": masked_username,
            "user_id": user_id,  # Include user_id for database storage
            "action": action,
            "diagram_type": diagram_type,
            "topic": topic  # Include topic for database storage
        }

        # Store activity (Redis and memory - synchronous, fast)
        # Note: Database write removed - history is not important, Redis is sufficient
        self._store_activity(activity)

        # Broadcast to all connections
        activity_json = json.dumps(activity, ensure_ascii=False)  # Preserve UTF-8 characters
        disconnected = []

        for connection_id, queue in self._connections.items():
            try:
                await queue.put(activity_json)
            except Exception as e:
                logger.warning("[ActivityStream] Error broadcasting to %s: %s", connection_id, e)
                disconnected.append(connection_id)

        # Remove disconnected connections
        for conn_id in disconnected:
            self.remove_connection(conn_id)

        logger.debug("[ActivityStream] Broadcasted activity: %s %s %s", masked_username, action, diagram_type)

    def get_recent_activities(self, limit: int = 50) -> list:
        """
        Get recent activities.

        Args:
            limit: Maximum number of activities to return

        Returns:
            List of recent activity dicts
        """
        if self._use_redis():
            try:
                redis = get_redis()
                if redis:
                    activities_str = redis.lrange(ACTIVITIES_KEY, 0, limit - 1)
                    activities = []
                    for act_str in activities_str:
                        try:
                            activities.append(json.loads(act_str))
                        except json.JSONDecodeError:
                            continue
                    return activities
            except Exception as e:
                logger.error("[ActivityStream] Error getting activities from Redis: %s", e)

        # Fallback: in-memory
        return self._memory_activities[:limit]


# Global singleton instance
_activity_stream_service: Optional[ActivityStreamService] = None


def get_activity_stream_service() -> ActivityStreamService:
    """Get global activity stream service instance."""
    global _activity_stream_service
    if _activity_stream_service is None:
        _activity_stream_service = ActivityStreamService()
    return _activity_stream_service

