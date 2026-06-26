"""
Discover Dify server slots from the Organization ORM schema.

Server 1 uses legacy ``dify_api_base_url`` / ``dify_api_key``; additional servers
use ``dify_api_base_url_{n}`` / ``dify_api_key_{n}``. Adding paired columns in a
migration automatically exposes a new slot — no code constant to bump.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple

from models.domain.auth import Organization

_LEGACY_URL_FIELD = "dify_api_base_url"
_LEGACY_KEY_FIELD = "dify_api_key"
_URL_FIELD_PREFIX = "dify_api_base_url_"
_KEY_FIELD_PREFIX = "dify_api_key_"


@lru_cache(maxsize=1)
def _organization_column_names() -> frozenset[str]:
    """Column names on ``organizations`` (cached until process restart)."""
    return frozenset(Organization.__mapper__.columns.keys())


def clear_dify_server_schema_cache() -> None:
    """Clear cached schema introspection (for tests after model patches)."""
    if hasattr(_organization_column_names, "cache_clear"):
        _organization_column_names.cache_clear()
    organization_dify_server_slots.cache_clear()


@lru_cache(maxsize=1)
def organization_dify_server_slots() -> Tuple[int, ...]:
    """
    Server numbers that exist on the Organization model, in ascending order.

    Each slot requires both URL and key columns to be present in the schema.
    """
    columns = _organization_column_names()
    slots: list[int] = []
    if _LEGACY_URL_FIELD in columns and _LEGACY_KEY_FIELD in columns:
        slots.append(1)

    numbered: list[int] = []
    for name in columns:
        if not name.startswith(_URL_FIELD_PREFIX):
            continue
        suffix = name.removeprefix(_URL_FIELD_PREFIX)
        if not suffix.isdigit():
            continue
        key_name = f"{_KEY_FIELD_PREFIX}{suffix}"
        if key_name in columns:
            numbered.append(int(suffix))
    slots.extend(sorted(numbered))
    return tuple(slots)


def server_slot_field_names(server: int) -> Optional[Tuple[str, str]]:
    """Return ``(url_field, key_field)`` when *server* exists in the schema."""
    if server not in organization_dify_server_slots():
        return None
    if server == 1:
        return _LEGACY_URL_FIELD, _LEGACY_KEY_FIELD
    return f"{_URL_FIELD_PREFIX}{server}", f"{_KEY_FIELD_PREFIX}{server}"
