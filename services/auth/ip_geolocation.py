"""
IP Geolocation Service
======================

IP to location lookup service using local database (ip2region).
No external API calls - all lookups are done locally.

Features:
- IP to location lookup (province, city, coordinates)
- Local database (ip2region) - no external API calls
- Redis caching (30-day TTL) for performance
- Graceful error handling

Key Schema:
- ip:location:{ip} -> JSON with {province, city, lat, lng, country} (TTL: 30 days)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司
(Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import ipaddress
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from config.settings import config
from services.auth.china_geo import (
    is_localhost_ip,
    is_private_or_reserved_ip,
    lookup_coordinates,
    normalize_city_name,
    normalize_province_name,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import (
    BACKGROUND_INFRA_ERRORS,
    FILE_IO_ERRORS,
    JSON_PARSE_ERRORS,
    REDIS_ERRORS,
)

_IPGEO_INIT_ERRORS = (ImportError,) + FILE_IO_ERRORS
_IPGEO_PATCH_ERRORS = JSON_PARSE_ERRORS + FILE_IO_ERRORS
_IPGEO_VERSION_PARSE_ERRORS = (ValueError, OSError) + FILE_IO_ERRORS


try:
    from ip2region.searcher import new_with_file_only as _new_with_file_only_func
    from ip2region.util import IPv4 as _ipv4_type
    from ip2region.util import IPv6 as _ipv6_type

    IP2REGION_AVAILABLE = True
    NEW_WITH_FILE_ONLY = _new_with_file_only_func
    IPV4_TYPE = _ipv4_type
    IPV6_TYPE = _ipv6_type
except ImportError:
    IP2REGION_AVAILABLE = False
    NEW_WITH_FILE_ONLY = None
    IPV4_TYPE = None
    IPV6_TYPE = None


logger = logging.getLogger(__name__)

# v2: do not reuse v1 cache entries that defaulted failed lookups to Beijing.
LOCATION_PREFIX = "ip:location:v2:"

# Cache TTL: 30 days
CACHE_TTL_SECONDS = 30 * 24 * 3600

# Database file paths (xdb format for v2.x)
DB_FILE_PATH_V4 = Path("data/ip2region_v4.xdb")  # IPv4 database
DB_FILE_PATH_V6 = Path("data/ip2region_v6.xdb")  # IPv6 database (optional)

# Patch cache file (patches take priority over main database)
PATCHES_CACHE = Path("data/ip2region_patches_cache.json")


class IPGeolocationService:
    """
    IP geolocation service using local ip2region database.

    No external API calls - all lookups are done locally.
    Thread-safe: Uses Redis for caching (atomic operations).
    Graceful degradation: Returns None if database not available.
    """

    def __init__(self):
        """Initialize geolocation service with local database."""
        self.searcher_v4 = None
        self.searcher_v6 = None
        self.patch_cache = {}  # Patch override cache
        self._init_database()
        self._load_patch_cache()

    def is_ready(self) -> bool:
        """
        Check if the geolocation database is ready for lookups.

        Returns:
            True if at least IPv4 database is loaded, False otherwise
        """
        return self.searcher_v4 is not None

    def _init_database(self):
        """Initialize ip2region xdb databases (IPv4 and IPv6)."""
        if not IP2REGION_AVAILABLE:
            logger.warning("[IPGeo] ip2region not installed. Install with: pip install py-ip2region")
            return

        try:
            # Ensure data directory exists
            DB_FILE_PATH_V4.parent.mkdir(parents=True, exist_ok=True)

            # Initialize IPv4 database
            if DB_FILE_PATH_V4.exists():
                try:
                    # Use file-only mode to avoid loading entire database into memory per worker
                    # In multi-worker setups, this prevents ~45MB memory duplication per worker
                    # Performance is still good due to OS page caching and Redis caching (30-day TTL)
                    # Based on: https://github.com/lionsoul2014/ip2region/tree/master/binding/python
                    if IPV4_TYPE is None or NEW_WITH_FILE_ONLY is None:
                        raise ImportError("ip2region module not properly imported")
                    self.searcher_v4 = NEW_WITH_FILE_ONLY(IPV4_TYPE, str(DB_FILE_PATH_V4))

                    file_size_mb = DB_FILE_PATH_V4.stat().st_size / 1024 / 1024
                    logger.info(
                        "[IPGeo] IPv4 database initialized from %s (%.2f MB, file mode)",
                        DB_FILE_PATH_V4,
                        file_size_mb,
                    )
                except _IPGEO_INIT_ERRORS as e:
                    logger.error(
                        "[IPGeo] Failed to initialize IPv4 database: %s",
                        e,
                        exc_info=True,
                    )
            else:
                logger.warning("[IPGeo] IPv4 database file not found at %s", DB_FILE_PATH_V4)

            # Initialize IPv6 database (optional)
            if DB_FILE_PATH_V6.exists():
                try:
                    # Use file-only mode to avoid loading entire database into memory per worker
                    # In multi-worker setups, this prevents ~35MB memory duplication per worker
                    if IPV6_TYPE is None or NEW_WITH_FILE_ONLY is None:
                        raise ImportError("ip2region module not properly imported")
                    self.searcher_v6 = NEW_WITH_FILE_ONLY(IPV6_TYPE, str(DB_FILE_PATH_V6))

                    file_size_mb = DB_FILE_PATH_V6.stat().st_size / 1024 / 1024
                    logger.info(
                        "[IPGeo] IPv6 database initialized from %s (%.2f MB, file mode)",
                        DB_FILE_PATH_V6,
                        file_size_mb,
                    )
                except _IPGEO_INIT_ERRORS as e:
                    logger.warning("[IPGeo] Failed to initialize IPv6 database: %s", e)
            else:
                logger.info("[IPGeo] IPv6 database not found at %s (optional)", DB_FILE_PATH_V6)

            # Check database age and warn if old
            if DB_FILE_PATH_V4.exists():
                self._check_database_age(DB_FILE_PATH_V4)

        except FILE_IO_ERRORS as e:
            logger.error("[IPGeo] Failed to initialize databases: %s", e, exc_info=True)

    def _load_patch_cache(self):
        """Load patch cache for override lookups."""
        if not PATCHES_CACHE.exists():
            logger.debug("[IPGeo] No patch cache found")
            return

        try:
            # Try UTF-8 first, with fallback encodings
            encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312"]
            cache_data = None

            for enc in encodings:
                try:
                    with open(PATCHES_CACHE, "r", encoding=enc) as f:
                        cache_data = json.load(f)
                        break
                except UnicodeDecodeError:
                    continue

            if cache_data is None:
                logger.warning("[IPGeo] Could not decode patch cache with any encoding")
                self.patch_cache = {}
                return

            self.patch_cache = cache_data

            patch_count = self.patch_cache.get("total_patches", 0)
            if patch_count > 0:
                logger.info("[IPGeo] Loaded %s patches from cache", patch_count)
        except _IPGEO_PATCH_ERRORS as e:
            logger.warning("[IPGeo] Failed to load patch cache: %s", e, exc_info=True)
            self.patch_cache = {}

    def _ip_to_int(self, ip: str) -> int:
        """Convert IP address to integer for range checking."""
        try:
            return int(ipaddress.IPv4Address(ip))
        except ValueError:
            return 0

    def _normalize_province_name(self, province: str, city: str = "") -> str:
        """Normalize province name to match ECharts map format."""
        return normalize_province_name(province, city)

    def _find_patch_for_ip(self, ip: str) -> Optional[Dict]:
        """
        Find patch entry for a given IP address.
        Patches take priority over main database.

        Returns: {province, city, country} or None
        """
        if not self.patch_cache or "patches" not in self.patch_cache:
            return None

        patches = self.patch_cache.get("patches", [])
        if not patches:
            return None

        try:
            ip_int = self._ip_to_int(ip)
            if ip_int == 0:
                return None

            # Binary search for matching range
            left, right = 0, len(patches) - 1

            while left <= right:
                mid = (left + right) // 2
                patch = patches[mid]

                if patch["start_int"] <= ip_int <= patch["end_int"]:
                    # Found matching patch - return location data
                    city = normalize_city_name(patch.get("city", ""))
                    province = self._normalize_province_name(patch.get("province", ""), city)
                    country = patch.get("country", "中国")
                    coords = lookup_coordinates(province, city) or {}

                    return {
                        "province": province,
                        "city": city,
                        "lat": coords.get("lat"),
                        "lng": coords.get("lng"),
                        "country": country,
                    }
                if ip_int < patch["start_int"]:
                    right = mid - 1
                else:
                    left = mid + 1

            return None

        except BACKGROUND_INFRA_ERRORS as e:
            logger.debug("[IPGeo] Error checking patch for IP %s: %s", ip, e)
            return None

    def _check_database_age(self, db_path: Path):
        """Check database age and warn if it's too old."""
        try:
            version_file = db_path.parent / "ip2region.version"
            age_days = None

            if version_file.exists():
                try:
                    with open(version_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        if lines:
                            download_time = datetime.fromisoformat(lines[0].strip())
                            age_days = (datetime.now() - download_time).days
                except _IPGEO_VERSION_PARSE_ERRORS as exc:
                    logger.debug("IP geolocation DB version file parse failed: %s", exc)

            # Fallback to file modification time
            if age_days is None:
                mtime = datetime.fromtimestamp(db_path.stat().st_mtime)
                age_days = (datetime.now() - mtime).days

            # Warn if database is older than 60 days
            if age_days > 60:
                logger.warning(
                    "[IPGeo] Database %s is %s days old. Consider updating for better accuracy.",
                    db_path.name,
                    age_days,
                )
            elif age_days > 30:
                logger.info(
                    "[IPGeo] Database %s is %s days old. Consider updating monthly for best accuracy.",
                    db_path.name,
                    age_days,
                )

        except FILE_IO_ERRORS as e:
            logger.debug("[IPGeo] Could not check database age: %s", e)

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    async def _get_from_cache(self, ip: str) -> Optional[Dict]:
        """Get location from Redis cache."""
        if not self._use_redis():
            return None

        try:
            redis = get_async_redis()
            if not redis:
                return None

            cache_key = f"{LOCATION_PREFIX}{ip}"
            cached_data = await redis.get(cache_key)

            if cached_data:
                try:
                    cached_location = json.loads(cached_data)
                except json.JSONDecodeError:
                    logger.warning("[IPGeo] Invalid cached data for IP %s", ip)
                    await redis.delete(cache_key)
                    return None
                if cached_location.get("is_fallback"):
                    await redis.delete(cache_key)
                    return None
                return cached_location

            return None

        except REDIS_ERRORS as e:
            logger.error("[IPGeo] Error reading cache: %s", e)
            return None

    async def _store_in_cache(self, ip: str, location: Dict) -> None:
        """Store location in Redis cache."""
        if not self._use_redis():
            return

        try:
            redis = get_async_redis()
            if not redis:
                return

            cache_key = f"{LOCATION_PREFIX}{ip}"
            await redis.setex(
                cache_key,
                CACHE_TTL_SECONDS,
                json.dumps(location, ensure_ascii=False),
            )
            logger.debug("[IPGeo] Cached location for IP %s", ip)

        except REDIS_ERRORS as e:
            logger.error("[IPGeo] Error storing cache: %s", e)

    def _lookup_local(self, ip: str) -> Optional[Dict]:
        """
        Lookup IP using local ip2region xdb database.

        Returns: {province, city, lat, lng, country} or None
        """
        is_ipv6 = ":" in ip

        # Select appropriate searcher
        searcher = self.searcher_v6 if is_ipv6 else self.searcher_v4

        if not searcher:
            if is_ipv6:
                logger.debug("[IPGeo] IPv6 database not available for %s", ip)
            else:
                logger.debug("[IPGeo] IPv4 database not available for %s", ip)
            return None

        try:
            # Lookup in database - try different API methods
            result = None
            region = None

            # Try new xdb API (py-ip2region)
            if hasattr(searcher, "search"):
                # New API: searcher.search(ip)
                result = searcher.search(ip)
            elif hasattr(searcher, "memorySearch"):
                result = getattr(searcher, "memorySearch")(ip)
            elif hasattr(searcher, "binarySearch"):
                result = getattr(searcher, "binarySearch")(ip)
            elif hasattr(searcher, "btreeSearch"):
                result = getattr(searcher, "btreeSearch")(ip)
            else:
                logger.warning("[IPGeo] Unknown ip2region API for IP %s", ip)
                return None

            if not result:
                return None

            # Handle different result formats
            if isinstance(result, dict):
                region = result.get("region") or result.get("Region") or result.get("area")
            elif isinstance(result, str):
                region = result
            elif hasattr(result, "region"):
                region = result.region
            elif hasattr(result, "Region"):
                region = result.Region
            elif hasattr(result, "area"):
                region = result.area
            else:
                # Try to convert to string
                region = str(result)

            if not region:
                return None

            # ip2region format: "国家|区域|省份|城市|ISP"
            # Example: "中国|0|北京|北京|0"
            parts = str(region).split("|")

            if len(parts) < 4:
                return None

            country = parts[0] if parts[0] != "0" else ""
            raw_province = parts[2] if parts[2] != "0" else ""
            raw_city = parts[3] if parts[3] != "0" else ""
            city = normalize_city_name(raw_city)
            province = self._normalize_province_name(raw_province, city)
            if not country and (province or city):
                country = "中国"
            coords = lookup_coordinates(province, city) or {}

            return {
                "province": province,
                "city": city,
                "lat": coords.get("lat"),
                "lng": coords.get("lng"),
                "country": country,
            }

        except BACKGROUND_INFRA_ERRORS as e:
            logger.warning("[IPGeo] Local lookup error for IP %s: %s", ip, e)
            return None

    def _debug_localhost_location(self) -> Optional[Dict]:
        """Optional Beijing pin for loopback in DEBUG only — never used in production."""
        try:
            if config.debug:
                logger.debug("[IPGeo] Localhost IP mapped to Beijing (DEBUG mode)")
                return {
                    "province": "北京",
                    "city": "北京",
                    "lat": 39.9042,
                    "lng": 116.4074,
                    "country": "中国",
                    "is_debug_localhost": True,
                    "is_fallback": True,
                }
        except (AttributeError, TypeError) as exc:
            logger.debug("Localhost IP geolocation debug pin skipped: %s", exc)
        return None

    async def get_location(self, ip: str) -> Optional[Dict]:
        """
        Get location for an IP address using local database with patch support.

        Failed, private, and foreign lookups return None — they must not
        appear as Beijing on the national map.
        """
        if not ip or ip == "unknown":
            return None
        if is_localhost_ip(ip):
            return self._debug_localhost_location()
        if is_private_or_reserved_ip(ip):
            logger.debug("[IPGeo] Skipping private/reserved IP %s", ip)
            return None

        cached = await self._get_from_cache(ip)
        if cached:
            logger.debug("[IPGeo] Cache hit for IP %s", ip)
            return cached

        patch_location = self._find_patch_for_ip(ip)
        if patch_location:
            await self._store_in_cache(ip, patch_location)
            logger.debug(
                "[IPGeo] Patch match for IP %s: %s, %s (from patch)",
                ip,
                patch_location.get("province"),
                patch_location.get("city"),
            )
            return patch_location

        location = self._lookup_local(ip)
        if location:
            await self._store_in_cache(ip, location)
            logger.debug(
                "[IPGeo] Local lookup successful for IP %s: %s, %s",
                ip,
                location.get("province"),
                location.get("city"),
            )
            return location

        logger.debug("[IPGeo] Lookup failed for IP %s (no Beijing fallback)", ip)
        return None


# Global singleton instance with thread-safe initialization
class GeolocationServiceSingleton:
    """Thread-safe singleton wrapper for IPGeolocationService."""

    instance: Optional[IPGeolocationService] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> IPGeolocationService:
        """
        Get global IP geolocation service instance (thread-safe singleton).

        Uses double-checked locking pattern to ensure only one instance is created
        even when multiple requests initialize the service simultaneously during startup.
        """
        if cls.instance is None:
            with cls._lock:
                # Double-check after acquiring lock (another thread might have created it)
                if cls.instance is None:
                    cls.instance = IPGeolocationService()
        return cls.instance


def get_geolocation_service() -> IPGeolocationService:
    """Get global IP geolocation service instance (thread-safe singleton)."""
    return GeolocationServiceSingleton.get_instance()
