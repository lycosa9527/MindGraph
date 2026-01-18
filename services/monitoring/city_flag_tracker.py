from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import logging

from services.redis.redis_client import is_redis_available, get_redis

"""
City Flag Tracker Service
=========================

Tracks city flags for the public dashboard map visualization.
When users log in from a city, a flag is placed on that city for 1 hour.

Features:
- Track city flags with timestamps
- Auto-expire flags after 1 hour
- Redis-based storage for multi-worker support
- Graceful degradation (in-memory fallback)

Key Schema:
- dashboard:city_flags:{city_name} -> timestamp (TTL: 1 hour)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)

# Key prefix
CITY_FLAG_PREFIX = "dashboard:city_flags:"

# Flag duration: 1 hour
FLAG_DURATION_SECONDS = 3600


class CityFlagTracker:
    """
    City flag tracker service for dashboard map visualization.

    Tracks which cities have had user logins in the last hour.
    Flags are displayed on the map to show recent activity.
    """

    def __init__(self):
        """Initialize city flag tracker."""
        # In-memory fallback for when Redis is disabled
        self._memory_flags: Dict[str, Dict[str, Any]] = {}

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def record_city_flag(self, city_name: str, province_name: Optional[str] = None,
                        lat: Optional[float] = None, lng: Optional[float] = None):
        """
        Record a flag for a city (triggered when user logs in from that city).

        Args:
            city_name: City name (e.g., "北京", "上海")
            province_name: Optional province name for fallback
            lat: Optional latitude coordinate
            lng: Optional longitude coordinate
        """
        if not city_name:
            # Use province as fallback if city not available
            if province_name:
                city_name = province_name
            else:
                return  # No location data available

        flag_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'lat': lat,
            'lng': lng
        }

        if self._use_redis():
            try:
                redis = get_redis()
                if redis:
                    flag_key = f"{CITY_FLAG_PREFIX}{city_name}"
                    # Store flag data with coordinates
                    redis.setex(
                        flag_key,
                        FLAG_DURATION_SECONDS,
                        json.dumps(flag_data, ensure_ascii=False)
                    )
                    logger.debug("[CityFlag] Recorded flag for city: %s (lat: %s, lng: %s)", city_name, lat, lng)
                    return
            except Exception as e:
                logger.error("[CityFlag] Error recording flag in Redis: %s", e)

        # Fallback: in-memory storage
        self._memory_flags[city_name] = flag_data
        # Clean up expired flags periodically
        self._cleanup_expired_flags()

    def _cleanup_expired_flags(self):
        """Remove expired flags from memory."""
        now = datetime.now(timezone.utc)
        expired_cities = []
        for city, flag_data in self._memory_flags.items():
            if isinstance(flag_data, dict):
                timestamp_str = flag_data.get('timestamp', '')
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if (now - timestamp).total_seconds() > FLAG_DURATION_SECONDS:
                            expired_cities.append(city)
                    except ValueError:
                        expired_cities.append(city)  # Invalid timestamp, remove it
            elif isinstance(flag_data, datetime):
                if (now - flag_data).total_seconds() > FLAG_DURATION_SECONDS:
                    expired_cities.append(city)

        for city in expired_cities:
            del self._memory_flags[city]

    def get_active_flags(self) -> List[Dict[str, Any]]:
        """
        Get list of cities with active flags (within last hour).

        Returns:
            List of dicts with 'city', 'timestamp', 'lat', 'lng' keys
        """
        flags = []
        now = datetime.now(timezone.utc)

        if self._use_redis():
            try:
                redis = get_redis()
                if redis:
                    # Scan for all city flag keys
                    pattern = f"{CITY_FLAG_PREFIX}*"
                    cursor = 0
                    while True:
                        cursor, keys = redis.scan(cursor, match=pattern, count=100)
                        for key in keys:
                            try:
                                city_name = key.decode('utf-8').replace(CITY_FLAG_PREFIX, '')
                                flag_data_str = redis.get(key)
                                if flag_data_str:
                                    # Try to parse as JSON (new format with coordinates)
                                    try:
                                        flag_data = json.loads(flag_data_str.decode('utf-8'))
                                        timestamp_str = flag_data.get('timestamp', '')
                                        if timestamp_str:
                                            timestamp = datetime.fromisoformat(timestamp_str)
                                            # Check if flag is still valid (within 1 hour)
                                            if (now - timestamp).total_seconds() < FLAG_DURATION_SECONDS:
                                                flags.append({
                                                    'city': city_name,
                                                    'timestamp': timestamp_str,
                                                    'lat': flag_data.get('lat'),
                                                    'lng': flag_data.get('lng')
                                                })
                                    except (json.JSONDecodeError, ValueError):
                                        # Fallback: old format (timestamp string only)
                                        timestamp = datetime.fromisoformat(flag_data_str.decode('utf-8'))
                                        if (now - timestamp).total_seconds() < FLAG_DURATION_SECONDS:
                                            flags.append({
                                                'city': city_name,
                                                'timestamp': timestamp.isoformat(),
                                                'lat': None,
                                                'lng': None
                                            })
                            except Exception as e:
                                logger.debug("[CityFlag] Error processing flag key %s: %s", key, e)
                                continue

                        if cursor == 0:
                            break

                    return flags
            except Exception as e:
                logger.error("[CityFlag] Error getting flags from Redis: %s", e)

        # Fallback: in-memory
        self._cleanup_expired_flags()
        for city, flag_data in self._memory_flags.items():
            if isinstance(flag_data, dict):
                flags.append({
                    'city': city,
                    'timestamp': flag_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                    'lat': flag_data.get('lat'),
                    'lng': flag_data.get('lng')
                })
            else:
                # Old format
                flags.append({
                    'city': city,
                    'timestamp': flag_data.isoformat() if isinstance(flag_data, datetime) else str(flag_data),
                    'lat': None,
                    'lng': None
                })

        return flags


# Global singleton instance
_city_flag_tracker: Optional[CityFlagTracker] = None


def get_city_flag_tracker() -> CityFlagTracker:
    """Get global city flag tracker instance."""
    global _city_flag_tracker
    if _city_flag_tracker is None:
        _city_flag_tracker = CityFlagTracker()
    return _city_flag_tracker

