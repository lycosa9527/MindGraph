from typing import List, Optional
import ipaddress
import logging
import os
import uuid

from services.redis.redis_client import is_redis_available, get_redis

"""
Redis Bayi IP Whitelist Service
=================================

High-performance IP whitelist management using Redis Set.
Replaces in-memory set for multi-worker support and dynamic management.

Features:
- O(1) IP lookup (Redis Set)
- Dynamic IP management (add/remove without restart)
- Shared across all workers
- Persistent (survives restarts)
- Fallback to in-memory set if Redis unavailable

Key Schema:
- bayi:ip_whitelist -> SET {ip1, ip2, ip3, ...}

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)

# Redis key for IP whitelist Set
WHITELIST_KEY = "bayi:ip_whitelist"

# ============================================================================
# DISTRIBUTED LOCK FOR MULTI-WORKER COORDINATION
# ============================================================================
#
# Problem: Uvicorn does NOT set UVICORN_WORKER_ID automatically.
# All workers get default '0', causing all to load IP whitelist.
#
# Solution: Redis-based distributed lock ensures only ONE worker loads whitelist.
# Uses SETNX (SET if Not eXists) with TTL for crash safety.
#
# Key: bayi:whitelist:load:lock
# Value: {worker_pid}:{uuid} (unique identifier per worker)
# TTL: 5 minutes (enough for loading, auto-release if worker crashes)
# ============================================================================

WHITELIST_LOAD_LOCK_KEY = "bayi:whitelist:load:lock"
WHITELIST_LOAD_LOCK_TTL = 300  # 5 minutes - enough for loading, auto-release on crash
_whitelist_load_lock_id: Optional[str] = None  # This worker's unique lock identifier


def _generate_whitelist_load_lock_id() -> str:
    """Generate unique lock ID for this worker: {pid}:{uuid}"""
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


def acquire_whitelist_load_lock() -> bool:
    """
    Attempt to acquire the whitelist load lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should load whitelist)
        False if lock held by another worker
    """
    global _whitelist_load_lock_id

    if not is_redis_available():
        # No Redis = single worker mode, proceed
        logger.debug("[BayiWhitelist] Redis unavailable, assuming single worker mode for whitelist loading")
        return True

    redis = get_redis()
    if not redis:
        return True  # Fallback to single worker mode

    try:
        # Generate unique ID for this worker
        if _whitelist_load_lock_id is None:
            _whitelist_load_lock_id = _generate_whitelist_load_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        acquired = redis.set(
            WHITELIST_LOAD_LOCK_KEY,
            _whitelist_load_lock_id,
            nx=True,  # Only set if not exists
            ex=WHITELIST_LOAD_LOCK_TTL  # TTL in seconds
        )

        if acquired:
            logger.debug(f"[BayiWhitelist] Lock acquired by this worker (id={_whitelist_load_lock_id})")
            return True
        else:
            # Lock held by another worker - check who
            holder = redis.get(WHITELIST_LOAD_LOCK_KEY)
            logger.info(f"[BayiWhitelist] Another worker holds the whitelist load lock (holder={holder}), skipping whitelist load")
            return False

    except Exception as e:
        logger.warning(f"[BayiWhitelist] Lock acquisition failed: {e}, proceeding anyway")
        return True  # On error, proceed (better to have duplicate than no whitelist)


class BayiIPWhitelist:
    """
    Redis-based bayi IP whitelist service.

    Provides fast IP lookups with automatic in-memory fallback.
    Uses Redis Set for O(1) lookup performance.

    Thread-safe: All operations are atomic Redis commands.
    """

    def __init__(self):
        """Initialize BayiIPWhitelist instance."""
        pass

    def _normalize_ip(self, ip: str) -> Optional[str]:
        """
        Normalize IP address for consistent storage and lookup.

        Args:
            ip: IP address string

        Returns:
            Normalized IP string or None if invalid
        """
        try:
            ip_addr = ipaddress.ip_address(ip)
            return str(ip_addr)
        except ValueError:
            logger.warning(f"[BayiWhitelist] Invalid IP address format: {ip}")
            return None

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def is_ip_whitelisted(self, ip: str) -> bool:
        """
        Check if IP is whitelisted.

        Args:
            ip: Client IP address string

        Returns:
            True if IP is whitelisted, False otherwise
        """
        normalized_ip = self._normalize_ip(ip)
        if not normalized_ip:
            return False

        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    # O(1) lookup in Redis Set
                    is_member = redis.sismember(WHITELIST_KEY, normalized_ip)
                    if is_member:
                        logger.debug(f"[BayiWhitelist] IP {ip} matched whitelist entry (Redis)")
                        return True
                    return False
                except Exception as e:
                    logger.warning(f"[BayiWhitelist] Redis error checking IP {ip}, falling back to in-memory: {e}")
                    # Fall through to in-memory fallback

        # Fallback to in-memory set (backward compatibility)
        # Import here to avoid circular import
        import utils.auth as auth_module
        if normalized_ip in auth_module.BAYI_IP_WHITELIST:
            logger.debug(f"[BayiWhitelist] IP {ip} matched whitelist entry (in-memory fallback)")
            return True

        return False

    def add_ip(self, ip: str, added_by: str = "system") -> bool:
        """
        Add IP to whitelist.

        Args:
            ip: IP address to add
            added_by: Who added the IP (for logging)

        Returns:
            True if added successfully, False otherwise
        """
        normalized_ip = self._normalize_ip(ip)
        if not normalized_ip:
            logger.warning(f"[BayiWhitelist] Cannot add invalid IP: {ip}")
            return False

        if not self._use_redis():
            logger.warning(f"[BayiWhitelist] Redis unavailable, cannot add IP {ip}")
            return False

        redis = get_redis()
        if not redis:
            return False

        try:
            # Add to Redis Set (SADD returns number of members added)
            added = redis.sadd(WHITELIST_KEY, normalized_ip)
            if added > 0:
                logger.info(f"[BayiWhitelist] Added IP {ip} to whitelist (by {added_by})")
                return True
            else:
                logger.debug(f"[BayiWhitelist] IP {ip} already in whitelist")
                return True  # Already exists, consider it success
        except Exception as e:
            logger.error(f"[BayiWhitelist] Failed to add IP {ip}: {e}")
            return False

    def remove_ip(self, ip: str) -> bool:
        """
        Remove IP from whitelist.

        Args:
            ip: IP address to remove

        Returns:
            True if removed successfully, False otherwise
        """
        normalized_ip = self._normalize_ip(ip)
        if not normalized_ip:
            logger.warning(f"[BayiWhitelist] Cannot remove invalid IP: {ip}")
            return False

        if not self._use_redis():
            logger.warning(f"[BayiWhitelist] Redis unavailable, cannot remove IP {ip}")
            return False

        redis = get_redis()
        if not redis:
            return False

        try:
            # Remove from Redis Set (SREM returns number of members removed)
            removed = redis.srem(WHITELIST_KEY, normalized_ip)
            if removed > 0:
                logger.info(f"[BayiWhitelist] Removed IP {ip} from whitelist")
                return True
            else:
                logger.debug(f"[BayiWhitelist] IP {ip} not in whitelist")
                return False
        except Exception as e:
            logger.error(f"[BayiWhitelist] Failed to remove IP {ip}: {e}")
            return False

    def list_ips(self) -> List[str]:
        """
        List all whitelisted IPs.

        Returns:
            List of whitelisted IP addresses
        """
        if not self._use_redis():
            # Fallback to in-memory set
            import utils.auth as auth_module
            return list(auth_module.BAYI_IP_WHITELIST)

        redis = get_redis()
        if not redis:
            return []

        try:
            # Get all members of Redis Set
            ips = redis.smembers(WHITELIST_KEY)
            return sorted(list(ips)) if ips else []
        except Exception as e:
            logger.error(f"[BayiWhitelist] Failed to list IPs: {e}")
            # Fallback to in-memory set
            import utils.auth as auth_module
            return list(auth_module.BAYI_IP_WHITELIST)

    def load_from_env(self) -> int:
        """
        Load IPs from environment variable into Redis.

        Uses Redis distributed lock to ensure only ONE worker loads the whitelist.
        This prevents multiple workers from loading the same IPs simultaneously.

        Reads BAYI_IP_WHITELIST env var (comma-separated) and adds to Redis Set.
        This is called on application startup for backward compatibility.

        Returns:
            Number of IPs successfully loaded
        """
        # Try to acquire lock - only one worker should load whitelist
        if not acquire_whitelist_load_lock():
            # Another worker is loading whitelist, skip
            # Return 0 since whitelist will be loaded by another worker
            return 0

        import os
        # Import here to avoid circular import
        import utils.auth as auth_module

        whitelist_str = os.getenv("BAYI_IP_WHITELIST", "").strip()
        if not whitelist_str:
            if auth_module.AUTH_MODE == "bayi":
                logger.info("[BayiWhitelist] No IPs in BAYI_IP_WHITELIST env var")
            return 0

        if not self._use_redis():
            logger.warning("[BayiWhitelist] Redis unavailable, cannot load IPs from env var")
            return 0

        count = 0
        errors = 0

        for ip_entry in whitelist_str.split(","):
            ip_entry = ip_entry.strip()
            if not ip_entry:
                continue

            normalized_ip = self._normalize_ip(ip_entry)
            if normalized_ip:
                if self.add_ip(normalized_ip, added_by="startup"):
                    count += 1
                else:
                    errors += 1
            else:
                errors += 1
                if auth_module.AUTH_MODE == "bayi":
                    logger.warning(f"[BayiWhitelist] Invalid IP entry in BAYI_IP_WHITELIST: {ip_entry}")

        if auth_module.AUTH_MODE == "bayi":
            if count > 0:
                logger.info(f"[BayiWhitelist] Loaded {count} IP(s) from env var into Redis")
            if errors > 0:
                logger.warning(f"[BayiWhitelist] {errors} invalid IP entries skipped")

        return count


# Singleton instance
_bayi_whitelist_instance: Optional[BayiIPWhitelist] = None


def get_bayi_whitelist() -> BayiIPWhitelist:
    """Get singleton instance of BayiIPWhitelist."""
    global _bayi_whitelist_instance
    if _bayi_whitelist_instance is None:
        _bayi_whitelist_instance = BayiIPWhitelist()
    return _bayi_whitelist_instance


# Convenience alias
bayi_whitelist = get_bayi_whitelist()

