"""
National data-center dashboard helpers (stats + China map aggregation).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count
from sqlalchemy.sql.functions import sum as sa_sum

from models.domain.auth import User
from models.domain.token_usage import TokenUsage
from services.auth.china_geo import (
    is_china_mappable,
    is_localhost_ip,
    is_mappable_client_ip,
    is_non_geo_label,
    is_unknown_ip,
    normalize_province_name,
)
from utils.auth.mindbot_token_stats import aggregate_mindbot_token_totals
from utils.auth.token_stats_queries import get_beijing_today_start_utc

LocationRecord = Mapping[str, Any]
ActiveUser = Mapping[str, Any]


def filter_localhost_users(active_users: Sequence[ActiveUser]) -> List[Dict[str, Any]]:
    """Drop loopback sessions from the live-user list."""
    return [dict(user) for user in active_users if not is_localhost_ip(str(user.get("ip_address", "")))]


def count_connected_users(active_users: Sequence[ActiveUser]) -> int:
    """Count live users with a real (non-localhost, non-unknown) IP."""
    total = 0
    for user in active_users:
        ip_address = str(user.get("ip_address", ""))
        if ip_address and not is_unknown_ip(ip_address) and not is_localhost_ip(ip_address):
            total += 1
    return total


def collect_unique_public_ips(
    active_users: Sequence[ActiveUser],
) -> Tuple[List[str], Dict[str, List[Dict[str, Any]]]]:
    """Group active users by public client IP (skip private/proxy leftovers)."""
    ip_to_users: Dict[str, List[Dict[str, Any]]] = {}
    ip_addresses: List[str] = []
    for user in active_users:
        ip_address = str(user.get("ip_address", ""))
        if not is_mappable_client_ip(ip_address):
            continue
        if ip_address not in ip_to_users:
            ip_addresses.append(ip_address)
            ip_to_users[ip_address] = []
        ip_to_users[ip_address].append(dict(user))
    return ip_addresses, ip_to_users


def _location_label(location: LocationRecord) -> str:
    city = str(location.get("city") or "").strip()
    province = str(location.get("province") or "").strip()
    return city or province


def aggregate_map_locations(
    ip_locations: Iterable[Tuple[str, Optional[LocationRecord], int]],
) -> Tuple[List[Dict[str, Any]], Dict[str, List[float]], Dict[str, Dict[str, Any]]]:
    """
    Build province counts and city pins from successful China lookups only.

    Failed lookups, foreign IPs, and the old Beijing fallback must not appear.
    """
    province_data: Dict[str, int] = defaultdict(int)
    city_coords: Dict[str, List[float]] = {}
    city_to_location: Dict[str, Dict[str, Any]] = {}

    for _ip_address, location, user_count in ip_locations:
        if not location or not is_china_mappable(location):
            continue
        province = str(location.get("province") or "")
        city = str(location.get("city") or "")
        if province:
            province_data[province] += user_count
        location_name = _location_label(location)
        if not location_name:
            continue
        lat = location.get("lat")
        lng = location.get("lng")
        if location_name not in city_coords and lat is not None and lng is not None:
            city_coords[location_name] = [float(lng), float(lat)]
        if location_name not in city_to_location:
            city_to_location[location_name] = {
                "city": city,
                "province": province,
                "lat": lat,
                "lng": lng,
            }

    map_data = [{"name": name, "value": count} for name, count in province_data.items()]
    return map_data, city_coords, city_to_location


def _is_mappable_flag_name(city_name: str) -> bool:
    """Drop ISP leftovers such as 移动 that old workers wrote into Redis."""
    if not city_name or is_non_geo_label(city_name):
        return False
    return bool(normalize_province_name(city_name))


def merge_city_flags(
    active_flags: Sequence[Mapping[str, Any]],
    city_coords: Mapping[str, Sequence[float]],
    city_to_location: Mapping[str, Mapping[str, Any]],
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Refresh flags for cities that currently have mappable users."""
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    flags_by_city = {
        str(flag.get("city")): dict(flag)
        for flag in active_flags
        if flag.get("city") and _is_mappable_flag_name(str(flag.get("city")))
    }
    for city_name, coords in city_coords.items():
        location_info = city_to_location.get(city_name)
        if not location_info:
            continue
        lat = location_info.get("lat")
        lng = location_info.get("lng")
        if lat is None:
            lat = coords[1]
        if lng is None:
            lng = coords[0]
        flags_by_city[city_name] = {
            "city": city_name,
            "timestamp": timestamp,
            "lat": lat,
            "lng": lng,
        }

    flag_data: List[Dict[str, Any]] = []
    for flag in flags_by_city.values():
        city_name = str(flag.get("city") or "")
        if not _is_mappable_flag_name(city_name):
            continue
        lat = flag.get("lat")
        lng = flag.get("lng")
        if lat is None or lng is None:
            stored = city_coords.get(city_name)
            if not stored:
                continue
            lng, lat = stored[0], stored[1]
        flag_data.append(
            {
                "name": city_name,
                "value": [float(lng), float(lat)],
                "timestamp": flag.get("timestamp", timestamp),
            }
        )
    return flag_data


def empty_dashboard_stats(timestamp: str) -> Dict[str, Any]:
    """Empty dashboard stats."""
    return {
        "timestamp": timestamp,
        "connected_users": 0,
        "registered_users": 0,
        "tokens_used_today": 0,
        "total_tokens_used": 0,
    }


def parse_cached_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse a Redis JSON blob; return None on empty/invalid payloads."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


async def count_registered_users(db: AsyncSession) -> int:
    """Count all registered users (dashboard RLS sees the full table)."""
    return int((await db.execute(select(sa_count()).select_from(User))).scalar_one())


async def query_token_totals(db: AsyncSession) -> Tuple[int, int]:
    """
    Sum successful LLM + MindBot tokens (Beijing today and all-time).

    Matches the admin data-center totals so the national panel is not a
    TokenUsage-only subset that looks empty next to the management charts.
    """
    today_start = get_beijing_today_start_utc()
    token_stats_result = await db.execute(
        select(
            sa_sum(
                case(
                    (
                        TokenUsage.created_at >= today_start,
                        TokenUsage.total_tokens,
                    ),
                    else_=0,
                )
            ).label("today_tokens"),
            sa_sum(TokenUsage.total_tokens).label("total_tokens"),
        ).where(TokenUsage.success)
    )
    token_row = token_stats_result.one_or_none()
    tokens_today = int(token_row.today_tokens or 0) if token_row else 0
    tokens_total = int(token_row.total_tokens or 0) if token_row else 0

    mindbot_today = await aggregate_mindbot_token_totals(db, created_since=today_start)
    mindbot_all = await aggregate_mindbot_token_totals(db)
    tokens_today += int(mindbot_today["total_tokens"])
    tokens_total += int(mindbot_all["total_tokens"])
    return tokens_today, tokens_total
