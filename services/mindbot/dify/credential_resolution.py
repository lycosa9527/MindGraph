"""
Effective Dify credentials for MindBot config rows (export and read-time resolution).

Mirrors runtime callback semantics: each ``OrganizationMindbotConfig`` stores
resolved URL/key at save time when ``use_org_dify_settings`` is true; export
re-resolves org-linked bots from the live org row so custom per-bot apps are
included.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from models.domain.mindbot_config import OrganizationMindbotConfig
from repositories.mindbot_repo import MindbotConfigRepository
from repositories.mindbot_usage_repo import MindbotUsageRepository
from services.dify.dify_servers import org_server_credentials, primary_server_no
from services.dify.org_mindmate_client import global_mindmate_dify_credentials
from utils.dify_user_key import parse_mindbot_dify_key

__all__ = [
    "MindbotDifyEndpoint",
    "distinct_mindbot_endpoints_for_org",
    "resolve_mindbot_config_credentials",
    "staff_id_from_mindbot_dify_user",
]


@dataclass(frozen=True)
class MindbotDifyEndpoint:
    """One distinct Dify app used by MindBot in an organization."""

    mindbot_config_id: int
    api_key: str
    api_url: str


def _org_linked_dify_credentials(org: Organization) -> tuple[str, str]:
    """Primary org MindMate server credentials, else global .env fallback."""
    selected = primary_server_no(org)
    creds = org_server_credentials(org, selected)
    if creds is not None:
        return creds
    return global_mindmate_dify_credentials()


def resolve_mindbot_config_credentials(
    cfg: OrganizationMindbotConfig,
    org: Organization,
) -> Optional[MindbotDifyEndpoint]:
    """Return effective Dify credentials for one MindBot config row."""
    if bool(getattr(cfg, "use_org_dify_settings", True)):
        api_key, api_url = _org_linked_dify_credentials(org)
    else:
        api_key = (getattr(cfg, "dify_api_key", None) or "").strip()
        api_url = (getattr(cfg, "dify_api_base_url", None) or "").strip()
    if not api_key or not api_url:
        return None
    config_id = getattr(cfg, "id", None)
    if config_id is None:
        return None
    return MindbotDifyEndpoint(
        mindbot_config_id=int(config_id),
        api_key=api_key,
        api_url=api_url,
    )


def _dedupe_endpoints(endpoints: List[MindbotDifyEndpoint]) -> List[MindbotDifyEndpoint]:
    seen: set[tuple[str, str]] = set()
    out: List[MindbotDifyEndpoint] = []
    for item in endpoints:
        key = (item.api_url, item.api_key)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


async def distinct_mindbot_endpoints_for_org(
    db: AsyncSession,
    org: Organization,
    *,
    staff_id: Optional[str] = None,
) -> List[MindbotDifyEndpoint]:
    """
    All distinct Dify apps for enabled MindBot configs in one org.

    When *staff_id* is set, narrow to configs that appear in usage events for
    that staff (falls back to all enabled configs when no events exist).
    """
    config_repo = MindbotConfigRepository(db)
    configs = await config_repo.list_by_organization_id(int(org.id))
    enabled = [row for row in configs if bool(getattr(row, "is_enabled", True))]
    if not enabled:
        return []

    allowed_config_ids: Optional[set[int]] = None
    if staff_id:
        usage_repo = MindbotUsageRepository(db)
        config_ids = await usage_repo.distinct_config_ids_for_staff(int(org.id), staff_id)
        if config_ids:
            allowed_config_ids = config_ids

    resolved: List[MindbotDifyEndpoint] = []
    for cfg in enabled:
        cfg_id = int(cfg.id)
        if allowed_config_ids is not None and cfg_id not in allowed_config_ids:
            continue
        creds = resolve_mindbot_config_credentials(cfg, org)
        if creds is not None:
            resolved.append(creds)
    return _dedupe_endpoints(resolved)


def staff_id_from_mindbot_dify_user(dify_user: str) -> Optional[str]:
    """Extract DingTalk staff id from ``mindbot_{org}_{staff}``."""
    _org_id, staff = parse_mindbot_dify_key(dify_user)
    return staff
