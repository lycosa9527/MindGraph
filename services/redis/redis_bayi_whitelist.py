"""Redis Bayi IP Whitelist Service.

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

from typing import List, Optional, TYPE_CHECKING
import importlib
import ipaddress
import logging
import os
import types
import uuid

from services.redis.redis_client import is_redis_available, get_redis

if TYPE_CHECKING:
    pass

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


class AuthModuleLoader:
    """Lazy loads utils.auth module to avoid circular imports."""

    def __init__(self):
        """Initialize auth module loader."""
        self._module: Optional[types.ModuleType] = None
        self._load_attempted: bool = False

    def get(self):
        """Get utils.auth module, loading it lazily if needed."""
        if not self._load_attempted:
            self._load_attempted = True
            try:
                auth_module = importlib.import_module("utils.auth")
                self._module = auth_module
            except ImportError:
                self._module = None
        return self._module


_auth_loader = AuthModuleLoader()


def _get_auth_module():
    """Lazy load utils.auth module to avoid circular imports."""
    return _auth_loader.get()


class WhitelistLoadLockManager:
    """Manages whitelist load lock state without global variables."""

    def __init__(self):
        """Initialize lock manager."""
        self._lock_id: Optional[str] = None

    def _generate_lock_id(self) -> str:
        """Generate unique lock ID for this worker: {pid}:{uuid}"""
        return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"

    def get_lock_id(self) -> str:
        """Get or generate lock ID for this worker."""
        if self._lock_id is None:
            self._lock_id = self._generate_lock_id()
        return self._lock_id

    def acquire(self) -> bool:
        """
        Attempt to acquire the whitelist load lock.

        Uses Redis SETNX for atomic lock acquisition.
        Only ONE worker across all processes can hold this lock.

        Returns:
            True if lock acquired (this worker should load whitelist)
            False if lock held by another worker
        """
        if not is_redis_available():
            logger.debug("[BayiWhitelist] Redis unavailable, assuming single worker mode for whitelist loading")
            return True

        redis = get_redis()
        if not redis:
            return True

        try:
            lock_id = self.get_lock_id()
            acquired = redis.set(
                WHITELIST_LOAD_LOCK_KEY,
                lock_id,
                nx=True,
                ex=WHITELIST_LOAD_LOCK_TTL
            )

            if acquired:
                logger.debug("[BayiWhitelist] Lock acquired by this worker (id=%s)", lock_id)
                return True

            holder = redis.get(WHITELIST_LOAD_LOCK_KEY)
            logger.info(
                "[BayiWhitelist] Another worker holds the whitelist load lock (holder=%s), "
                "skipping whitelist load",
                holder
            )
            return False

        except Exception as e:
            logger.warning("[BayiWhitelist] Lock acquisition failed: %s, proceeding anyway", e)
            return True


_lock_manager = WhitelistLoadLockManager()


def acquire_whitelist_load_lock() -> bool:
    """
    Attempt to acquire the whitelist load lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should load whitelist)
        False if lock held by another worker
    """
    return _lock_manager.acquire()


class BayiIPWhitelist:
    """
    Redis-based bayi IP whitelist service.

    Provides fast IP lookups with automatic in-memory fallback.
    Uses Redis Set for O(1) lookup performance.

    Thread-safe: All operations are atomic Redis commands.
    """

    def __init__(self):
        """Initialize BayiIPWhitelist instance."""

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
            logger.warning("[BayiWhitelist] Invalid IP address format: %s", ip)
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
                        logger.debug("[BayiWhitelist] IP %s matched whitelist entry (Redis)", ip)
                        return True
                    return False
                except Exception as e:
                    logger.warning(
                        "[BayiWhitelist] Redis error checking IP %s, falling back to in-memory: %s",
                        ip,
                        e
                    )
                    # Fall through to in-memory fallback

        # Fallback to in-memory set (backward compatibility)
        auth_module = _get_auth_module()
        if auth_module and normalized_ip in auth_module.BAYI_IP_WHITELIST:
            logger.debug("[BayiWhitelist] IP %s matched whitelist entry (in-memory fallback)", ip)
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
            logger.warning("[BayiWhitelist] Cannot add invalid IP: %s", ip)
            return False

        if not self._use_redis():
            logger.warning("[BayiWhitelist] Redis unavailable, cannot add IP %s", ip)
            return False

        redis = get_redis()
        if not redis:
            return False

        try:
            # Add to Redis Set (SADD returns number of members added)
            added = redis.sadd(WHITELIST_KEY, normalized_ip)
            if added > 0:
                logger.info("[BayiWhitelist] Added IP %s to whitelist (by %s)", ip, added_by)
                return True
            logger.debug("[BayiWhitelist] IP %s already in whitelist", ip)
            return True
        except Exception as e:
            logger.error("[BayiWhitelist] Failed to add IP %s: %s", ip, e)
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
            logger.warning("[BayiWhitelist] Cannot remove invalid IP: %s", ip)
            return False

        if not self._use_redis():
            logger.warning("[BayiWhitelist] Redis unavailable, cannot remove IP %s", ip)
            return False

        redis = get_redis()
        if not redis:
            return False

        try:
            # Remove from Redis Set (SREM returns number of members removed)
            removed = redis.srem(WHITELIST_KEY, normalized_ip)
            if removed > 0:
                logger.info("[BayiWhitelist] Removed IP %s from whitelist", ip)
                return True
            logger.debug("[BayiWhitelist] IP %s not in whitelist", ip)
            return False
        except Exception as e:
            logger.error("[BayiWhitelist] Failed to remove IP %s: %s", ip, e)
            return False

    def list_ips(self) -> List[str]:
        """
        List all whitelisted IPs.

        Returns:
            List of whitelisted IP addresses
        """
        if not self._use_redis():
            auth_module = _get_auth_module()
            if auth_module:
                return list(auth_module.BAYI_IP_WHITELIST)
            return []

        redis = get_redis()
        if not redis:
            return []

        try:
            # Get all members of Redis Set
            ips = redis.smembers(WHITELIST_KEY)
            return sorted(list(ips)) if ips else []
        except Exception as e:
            logger.error("[BayiWhitelist] Failed to list IPs: %s", e)
            auth_module = _get_auth_module()
            if auth_module:
                return list(auth_module.BAYI_IP_WHITELIST)
            return []

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
            return 0

        auth_module = _get_auth_module()
        whitelist_str = os.getenv("BAYI_IP_WHITELIST", "").strip()
        if not whitelist_str:
            if auth_module and auth_module.AUTH_MODE == "bayi":
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
                if auth_module and auth_module.AUTH_MODE == "bayi":
                    logger.warning("[BayiWhitelist] Invalid IP entry in BAYI_IP_WHITELIST: %s", ip_entry)

        if auth_module and auth_module.AUTH_MODE == "bayi":
            if count > 0:
                logger.info("[BayiWhitelist] Loaded %d IP(s) from env var into Redis", count)
            if errors > 0:
                logger.warning("[BayiWhitelist] %d invalid IP entries skipped", errors)

        return count


class BayiWhitelistSingleton:
    """Manages singleton instance without global statement."""

    def __init__(self):
        """Initialize singleton manager."""
        self._instance: Optional[BayiIPWhitelist] = None

    def get(self) -> BayiIPWhitelist:
        """Get singleton instance of BayiIPWhitelist."""
        if self._instance is None:
            self._instance = BayiIPWhitelist()
        return self._instance


_singleton_manager = BayiWhitelistSingleton()


def get_bayi_whitelist() -> BayiIPWhitelist:
    """Get singleton instance of BayiIPWhitelist."""
    return _singleton_manager.get()


# Convenience alias
bayi_whitelist = get_bayi_whitelist()
