"""
Derived organization privatization state for admin organization lists.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional, cast

from models.domain.auth import Organization


def organization_is_privatized(org: Organization) -> bool:
    """
    True when the org meets all MindMate privatization criteria.

    Privatized only when all of:
    - custom agent name (mindmate_agent_name)
    - uploaded agent avatar (mindmate_agent_avatar_url)
    - dedicated Dify credentials (dify_api_base_url and dify_api_key)
    """
    agent_name = (cast(Optional[str], getattr(org, "mindmate_agent_name", None)) or "").strip()
    avatar_url = (cast(Optional[str], getattr(org, "mindmate_agent_avatar_url", None)) or "").strip()
    dify_url = (cast(Optional[str], getattr(org, "dify_api_base_url", None)) or "").strip()
    dify_key = (cast(Optional[str], getattr(org, "dify_api_key", None)) or "").strip()
    has_dedicated_dify = bool(dify_url and dify_key)
    return bool(agent_name and avatar_url and has_dedicated_dify)


def org_privatization_list_field(org: Organization) -> dict[str, Any]:
    """Serialized privatization flag for admin organization list payloads."""
    return {"is_privatized": organization_is_privatized(org)}
