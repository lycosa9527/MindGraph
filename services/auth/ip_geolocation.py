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
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
import ipaddress
import json
import logging
import threading

from services.redis.redis_client import is_redis_available, get_redis
from config.settings import config


try:
    # Try importing py-ip2region (official Python binding for xdb format)
    try:
        from ip2region.searcher import new_with_file_only as _new_with_file_only_func
        from ip2region.util import IPv4 as _ipv4_type, IPv6 as _ipv6_type
        IP2REGION_AVAILABLE = True
        NEW_WITH_FILE_ONLY = _new_with_file_only_func
        IPV4_TYPE = _ipv4_type
        IPV6_TYPE = _ipv6_type
    except ImportError:
        IP2REGION_AVAILABLE = False
        NEW_WITH_FILE_ONLY = None
        IPV4_TYPE = None
        IPV6_TYPE = None
except Exception:
    IP2REGION_AVAILABLE = False
    NEW_WITH_FILE_ONLY = None
    IPV4_TYPE = None
    IPV6_TYPE = None


logger = logging.getLogger(__name__)

# Key prefix
LOCATION_PREFIX = "ip:location:"

# Cache TTL: 30 days
CACHE_TTL_SECONDS = 30 * 24 * 3600

# Database file paths (xdb format for v2.x)
DB_FILE_PATH_V4 = Path("data/ip2region_v4.xdb")  # IPv4 database
DB_FILE_PATH_V6 = Path("data/ip2region_v6.xdb")  # IPv6 database (optional)

# Patch cache file (patches take priority over main database)
PATCHES_CACHE = Path("data/ip2region_patches_cache.json")

# Mapping of city names to province names for ECharts map
CITY_TO_PROVINCE = {
    # Direct municipalities
    "北京市": "北京",
    "上海市": "上海",
    "天津市": "天津",
    "重庆市": "重庆",
    # Jiangsu cities
    "南京市": "江苏",
    "苏州市": "江苏",
    "无锡市": "江苏",
    "常州市": "江苏",
    "镇江市": "江苏",
    "扬州市": "江苏",
    "泰州市": "江苏",
    "南通市": "江苏",
    "盐城市": "江苏",
    "淮安市": "江苏",
    "宿迁市": "江苏",
    "徐州市": "江苏",
    "连云港市": "江苏",
    # Zhejiang cities
    "杭州市": "浙江",
    "宁波市": "浙江",
    "温州市": "浙江",
    "嘉兴市": "浙江",
    "湖州市": "浙江",
    "绍兴市": "浙江",
    "金华市": "浙江",
    "衢州市": "浙江",
    "舟山市": "浙江",
    "台州市": "浙江",
    "丽水市": "浙江",
    # Guangdong cities
    "广州市": "广东",
    "深圳市": "广东",
    "珠海市": "广东",
    "汕头市": "广东",
    "佛山市": "广东",
    "韶关市": "广东",
    "湛江市": "广东",
    "肇庆市": "广东",
    "江门市": "广东",
    "茂名市": "广东",
    "惠州市": "广东",
    "梅州市": "广东",
    "汕尾市": "广东",
    "河源市": "广东",
    "阳江市": "广东",
    "清远市": "广东",
    "东莞市": "广东",
    "中山市": "广东",
    "潮州市": "广东",
    "揭阳市": "广东",
    "云浮市": "广东",
    # Shandong cities
    "济南市": "山东",
    "青岛市": "山东",
    "淄博市": "山东",
    "枣庄市": "山东",
    "东营市": "山东",
    "烟台市": "山东",
    "潍坊市": "山东",
    "济宁市": "山东",
    "泰安市": "山东",
    "威海市": "山东",
    "日照市": "山东",
    "临沂市": "山东",
    "德州市": "山东",
    "聊城市": "山东",
    "滨州市": "山东",
    "菏泽市": "山东",
    # Add more mappings as needed
}

# Major Chinese cities/provinces coordinates
# Format: {name: {"lat": latitude, "lng": longitude}}
COORDINATES = {
    # Provinces
    "北京": {"lat": 39.9042, "lng": 116.4074},
    "上海": {"lat": 31.2304, "lng": 121.4737},
    "天津": {"lat": 39.3434, "lng": 117.3616},
    "重庆": {"lat": 29.5630, "lng": 106.5516},
    "广东": {"lat": 23.1291, "lng": 113.2644},  # Guangzhou
    "江苏": {"lat": 32.0603, "lng": 118.7969},  # Nanjing
    "浙江": {"lat": 30.2741, "lng": 120.1551},  # Hangzhou
    "山东": {"lat": 36.6512, "lng": 117.1201},  # Jinan
    "四川": {"lat": 30.6624, "lng": 104.0633},  # Chengdu
    "湖北": {"lat": 30.5928, "lng": 114.3055},  # Wuhan
    "河南": {"lat": 34.7466, "lng": 113.6254},  # Zhengzhou
    "湖南": {"lat": 28.2278, "lng": 112.9388},  # Changsha
    "河北": {"lat": 38.0428, "lng": 114.5149},  # Shijiazhuang
    "安徽": {"lat": 31.8206, "lng": 117.2272},  # Hefei
    "福建": {"lat": 26.0745, "lng": 119.2965},  # Fuzhou
    "辽宁": {"lat": 41.8057, "lng": 123.4315},  # Shenyang
    "陕西": {"lat": 34.3416, "lng": 108.9398},  # Xi'an
    "江西": {"lat": 28.6820, "lng": 115.8579},  # Nanchang
    "云南": {"lat": 25.0389, "lng": 102.7183},  # Kunming
    "广西": {"lat": 22.8170, "lng": 108.3669},  # Nanning
    "山西": {"lat": 37.8706, "lng": 112.5489},  # Taiyuan
    "内蒙古": {"lat": 40.8414, "lng": 111.7519},  # Hohhot
    "黑龙江": {"lat": 45.7731, "lng": 126.6849},  # Harbin
    "吉林": {"lat": 43.8171, "lng": 125.3235},  # Changchun
    "贵州": {"lat": 26.6470, "lng": 106.6302},  # Guiyang
    "新疆": {"lat": 43.8256, "lng": 87.6168},  # Urumqi
    "甘肃": {"lat": 36.0611, "lng": 103.8343},  # Lanzhou
    "海南": {"lat": 20.0444, "lng": 110.1999},  # Haikou
    "宁夏": {"lat": 38.4872, "lng": 106.2309},  # Yinchuan
    "青海": {"lat": 36.6171, "lng": 101.7782},  # Xining
    "西藏": {"lat": 29.6626, "lng": 91.1160},  # Lhasa
    # Major cities (more specific)
    "深圳": {"lat": 22.5431, "lng": 114.0579},
    "广州": {"lat": 23.1291, "lng": 113.2644},
    "杭州": {"lat": 30.2741, "lng": 120.1551},
    "南京": {"lat": 32.0603, "lng": 118.7969},
    "成都": {"lat": 30.6624, "lng": 104.0633},
    "武汉": {"lat": 30.5928, "lng": 114.3055},
    "西安": {"lat": 34.3416, "lng": 108.9398},
    "苏州": {"lat": 31.2989, "lng": 120.5853},
    "郑州": {"lat": 34.7466, "lng": 113.6254},
    "长沙": {"lat": 28.2278, "lng": 112.9388},
}


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
                        "[IPGeo] IPv4 database initialized from %s "
                        "(%.2f MB, file mode)",
                        DB_FILE_PATH_V4,
                        file_size_mb
                    )
                except Exception as e:
                    logger.error("[IPGeo] Failed to initialize IPv4 database: %s", e, exc_info=True)
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
                        "[IPGeo] IPv6 database initialized from %s "
                        "(%.2f MB, file mode)",
                        DB_FILE_PATH_V6,
                        file_size_mb
                    )
                except Exception as e:
                    logger.warning("[IPGeo] Failed to initialize IPv6 database: %s", e)
            else:
                logger.info("[IPGeo] IPv6 database not found at %s (optional)", DB_FILE_PATH_V6)

            # Check database age and warn if old
            if DB_FILE_PATH_V4.exists():
                self._check_database_age(DB_FILE_PATH_V4)

        except Exception as e:
            logger.error("[IPGeo] Failed to initialize databases: %s", e, exc_info=True)

    def _load_patch_cache(self):
        """Load patch cache for override lookups."""
        if not PATCHES_CACHE.exists():
            logger.debug("[IPGeo] No patch cache found")
            return

        try:
            # Try UTF-8 first, with fallback encodings
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312']
            cache_data = None

            for enc in encodings:
                try:
                    with open(PATCHES_CACHE, 'r', encoding=enc) as f:
                        cache_data = json.load(f)
                        break
                except UnicodeDecodeError:
                    continue

            if cache_data is None:
                logger.warning("[IPGeo] Could not decode patch cache with any encoding")
                self.patch_cache = {}
                return

            self.patch_cache = cache_data

            patch_count = self.patch_cache.get('total_patches', 0)
            if patch_count > 0:
                logger.info("[IPGeo] Loaded %s patches from cache", patch_count)
        except Exception as e:
            logger.warning("[IPGeo] Failed to load patch cache: %s", e, exc_info=True)
            self.patch_cache = {}

    def _ip_to_int(self, ip: str) -> int:
        """Convert IP address to integer for range checking."""
        try:
            return int(ipaddress.IPv4Address(ip))
        except ValueError:
            return 0

    def _normalize_province_name(self, province: str) -> str:
        """
        Normalize province name to match ECharts map format.
        Converts city names to province names (e.g., "南京市" -> "江苏").
        """
        if not province:
            return province

        # Check if it's a city name that needs conversion
        if province in CITY_TO_PROVINCE:
            return CITY_TO_PROVINCE[province]

        # If it already ends with "省" or is a direct province name, return as-is
        if province.endswith("省") or province in ["北京", "上海", "天津", "重庆", "内蒙古", "新疆", "西藏", "广西", "宁夏", "香港", "澳门"]:
            # Remove "省" suffix if present
            return province.rstrip("省")

        # If it ends with "市", try to find parent province
        if province.endswith("市"):
            # Try without "市" suffix
            city_name = province
            if city_name in CITY_TO_PROVINCE:
                return CITY_TO_PROVINCE[city_name]

        # Return as-is if no mapping found
        return province

    def _find_patch_for_ip(self, ip: str) -> Optional[Dict]:
        """
        Find patch entry for a given IP address.
        Patches take priority over main database.

        Returns: {province, city, country} or None
        """
        if not self.patch_cache or 'patches' not in self.patch_cache:
            return None

        patches = self.patch_cache.get('patches', [])
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

                if patch['start_int'] <= ip_int <= patch['end_int']:
                    # Found matching patch - return location data
                    province = patch.get('province', '')
                    city = patch.get('city', '')
                    country = patch.get('country', '中国')

                    # Normalize province name for ECharts map
                    province = self._normalize_province_name(province)

                    # Get coordinates for the location
                    coords = self._get_coordinates(province, city)

                    return {
                        "province": province,
                        "city": city,
                        "lat": coords.get('lat'),
                        "lng": coords.get('lng'),
                        "country": country
                    }
                elif ip_int < patch['start_int']:
                    right = mid - 1
                else:
                    left = mid + 1

            return None

        except Exception as e:
            logger.debug("[IPGeo] Error checking patch for IP %s: %s", ip, e)
            return None

    def _check_database_age(self, db_path: Path):
        """Check database age and warn if it's too old."""
        try:
            version_file = db_path.parent / "ip2region.version"
            age_days = None

            if version_file.exists():
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if lines:
                            download_time = datetime.fromisoformat(lines[0].strip())
                            age_days = (datetime.now() - download_time).days
                except Exception:
                    pass

            # Fallback to file modification time
            if age_days is None:
                mtime = datetime.fromtimestamp(db_path.stat().st_mtime)
                age_days = (datetime.now() - mtime).days

            # Warn if database is older than 60 days
            if age_days > 60:
                logger.warning(
                    "[IPGeo] Database %s is %s days old. "
                    "Consider updating for better accuracy.",
                    db_path.name,
                    age_days
                )
            elif age_days > 30:
                logger.info(
                    "[IPGeo] Database %s is %s days old. "
                    "Consider updating monthly for best accuracy.",
                    db_path.name,
                    age_days
                )

        except Exception as e:
            logger.debug("[IPGeo] Could not check database age: %s", e)

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def _get_from_cache(self, ip: str) -> Optional[Dict]:
        """Get location from Redis cache."""
        if not self._use_redis():
            return None

        try:
            redis = get_redis()
            if not redis:
                return None

            cache_key = f"{LOCATION_PREFIX}{ip}"
            cached_data = redis.get(cache_key)

            if cached_data:
                try:
                    return json.loads(cached_data)
                except json.JSONDecodeError:
                    logger.warning("[IPGeo] Invalid cached data for IP %s", ip)
                    redis.delete(cache_key)  # Clean up invalid cache
                    return None

            return None

        except Exception as e:
            logger.error("[IPGeo] Error reading cache: %s", e)
            return None

    def _store_in_cache(self, ip: str, location: Dict):
        """Store location in Redis cache."""
        if not self._use_redis():
            return

        try:
            redis = get_redis()
            if not redis:
                return

            cache_key = f"{LOCATION_PREFIX}{ip}"
            redis.setex(
                cache_key,
                CACHE_TTL_SECONDS,
                json.dumps(location, ensure_ascii=False)  # Preserve UTF-8 characters
            )
            logger.debug("[IPGeo] Cached location for IP %s", ip)

        except Exception as e:
            logger.error("[IPGeo] Error storing cache: %s", e)

    def _lookup_local(self, ip: str) -> Optional[Dict]:
        """
        Lookup IP using local ip2region xdb database.

        Returns: {province, city, lat, lng, country} or None
        """
        is_ipv6 = ':' in ip

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
            if hasattr(searcher, 'search'):
                # New API: searcher.search(ip)
                result = searcher.search(ip)
            elif hasattr(searcher, 'memorySearch'):
                # Old API: searcher.memorySearch(ip)
                result = searcher.memorySearch(ip)  # type: ignore[attr-defined]
            elif hasattr(searcher, 'binarySearch'):
                # Old API: searcher.binarySearch(ip)
                result = searcher.binarySearch(ip)  # type: ignore[attr-defined]
            elif hasattr(searcher, 'btreeSearch'):
                # Old API: searcher.btreeSearch(ip)
                result = searcher.btreeSearch(ip)  # type: ignore[attr-defined]
            else:
                logger.warning("[IPGeo] Unknown ip2region API for IP %s", ip)
                return None

            if not result:
                return None

            # Handle different result formats
            if isinstance(result, dict):
                region = result.get('region') or result.get('Region') or result.get('area')
            elif isinstance(result, str):
                region = result
            elif hasattr(result, 'region'):
                region = result.region
            elif hasattr(result, 'Region'):
                region = result.Region
            elif hasattr(result, 'area'):
                region = result.area
            else:
                # Try to convert to string
                region = str(result)

            if not region:
                return None

            # ip2region format: "国家|区域|省份|城市|ISP"
            # Example: "中国|0|北京|北京|0"
            parts = str(region).split('|')

            if len(parts) < 4:
                return None

            country = parts[0] if parts[0] != '0' else '中国'
            province = parts[2] if parts[2] != '0' else ''
            city = parts[3] if parts[3] != '0' else ''

            # Normalize province name for ECharts map (convert city names to provinces)
            province = self._normalize_province_name(province)

            # Get approximate coordinates for Chinese provinces/cities
            coords = self._get_coordinates(province, city)

            return {
                "province": province,
                "city": city,
                "lat": coords.get('lat'),
                "lng": coords.get('lng'),
                "country": country
            }

        except Exception as e:
            logger.warning("[IPGeo] Local lookup error for IP %s: %s", ip, e)
            return None

    def _get_coordinates(self, province: str, city: str) -> Dict[str, float]:
        """
        Get approximate coordinates for province/city.
        This is a simplified mapping - expand as needed.
        """
        # Try city first, then province
        if city and city in COORDINATES:
            return COORDINATES[city]
        elif province and province in COORDINATES:
            return COORDINATES[province]

        # Default to Beijing if not found
        return {"lat": 39.9042, "lng": 116.4074}

    async def get_location(self, ip: str) -> Optional[Dict]:
        """
        Get location for an IP address using local database with patch support.

        Process:
        1. Check Redis cache
        2. Check patch cache (patches take priority)
        3. If no patch, lookup in local ip2region database
        4. Store result in cache
        5. Return location data

        Args:
            ip: IP address string

        Returns:
            Dict with {province, city, lat, lng, country} or None if lookup fails
        """
        # Handle localhost IPs - return default location in DEBUG mode for testing
        if ip and (ip.startswith("127.") or ip.startswith("::1")):
            try:
                if config.debug:
                    # Return Beijing location for localhost in DEBUG mode
                    localhost_location = {
                        "province": "北京",
                        "city": "北京",
                        "lat": 39.9042,
                        "lng": 116.4074,
                        "country": "中国"
                    }
                    logger.debug("[IPGeo] Localhost IP %s mapped to Beijing (DEBUG mode)", ip)
                    return localhost_location
            except Exception:
                pass
            # In production, skip localhost IPs
            return None

        if not ip or ip == "unknown":
            return None

        # Check cache first
        cached = self._get_from_cache(ip)
        if cached:
            logger.debug("[IPGeo] Cache hit for IP %s", ip)
            return cached

        # Check patches first (patches take priority over main database)
        patch_location = self._find_patch_for_ip(ip)
        if patch_location:
            self._store_in_cache(ip, patch_location)
            logger.debug(
                "[IPGeo] Patch match for IP %s: %s, %s (from patch)",
                ip,
                patch_location.get('province'),
                patch_location.get('city')
            )
            return patch_location

        # Lookup in local database
        location = self._lookup_local(ip)
        if location:
            self._store_in_cache(ip, location)
            logger.debug(
                "[IPGeo] Local lookup successful for IP %s: %s, %s",
                ip,
                location.get('province'),
                location.get('city')
            )
            return location

        # Lookup failed - return default Beijing location for display purposes
        # Do NOT cache this default to avoid corrupting location data:
        # - Foreign IPs/VPNs won't be permanently marked as Beijing
        # - Transient failures won't persist incorrect data after recovery
        logger.warning("[IPGeo] Lookup failed for IP %s, returning Beijing as fallback (not cached)", ip)
        default_location = {
            "province": "北京",
            "city": "北京",
            "lat": 39.9042,
            "lng": 116.4074,
            "country": "中国",
            "is_fallback": True  # Flag to indicate this is a default location, not a real lookup
        }
        # Intentionally NOT caching the default location to allow retries on next lookup
        return default_location


# Global singleton instance with thread-safe initialization
class GeolocationServiceSingleton:
    """Thread-safe singleton wrapper for IPGeolocationService."""
    _instance: Optional[IPGeolocationService] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> IPGeolocationService:
        """
        Get global IP geolocation service instance (thread-safe singleton).

        Uses double-checked locking pattern to ensure only one instance is created
        even when multiple requests initialize the service simultaneously during startup.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check after acquiring lock (another thread might have created it)
                if cls._instance is None:
                    cls._instance = IPGeolocationService()
        return cls._instance


def get_geolocation_service() -> IPGeolocationService:
    """Get global IP geolocation service instance (thread-safe singleton)."""
    return GeolocationServiceSingleton.get_instance()
