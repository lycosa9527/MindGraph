"""
School persona inputs for the shared MindMate Dify chatflow.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from models.domain.auth import Organization
from utils.auth.org_privatization import organization_is_privatized
from utils.db.session_open import system_rls_session

DEFAULT_AGENT_LABEL = "MindMate"


def _stripped(value: object) -> str:
    """Return stripped text, or empty when the value is missing."""
    if value is None:
        return ""
    return str(value).strip()


def persona_inputs_for_org(org: Optional[Organization]) -> dict[str, str]:
    """
    Build the three Start variables for one organization.

    Incomplete privatization keeps the public MindMate name and alias.
    School name is display_name, then the organization name.
    """
    if org is None:
        return {
            "mg_agent_name": DEFAULT_AGENT_LABEL,
            "mg_agent_alias": DEFAULT_AGENT_LABEL,
            "mg_school_name": "",
        }
    school_name = _stripped(getattr(org, "display_name", None)) or _stripped(getattr(org, "name", None))
    if not organization_is_privatized(org):
        return {
            "mg_agent_name": DEFAULT_AGENT_LABEL,
            "mg_agent_alias": DEFAULT_AGENT_LABEL,
            "mg_school_name": school_name,
        }
    agent_name = _stripped(getattr(org, "mindmate_agent_name", None)) or DEFAULT_AGENT_LABEL
    agent_alias = _stripped(getattr(org, "mindmate_agent_alias", None)) or agent_name
    return {
        "mg_agent_name": agent_name,
        "mg_agent_alias": agent_alias,
        "mg_school_name": school_name,
    }


def apply_persona_inputs(inputs: dict[str, Any], org: Optional[Organization]) -> None:
    """Overwrite the three persona keys. Never forward a school blurb."""
    inputs.pop("mg_school_blurb", None)
    inputs.update(persona_inputs_for_org(org))


async def _organization_for_persona(organization_id: Optional[int]) -> Optional[Organization]:
    """Load one organization row, or None when the id is missing."""
    if organization_id is None:
        return None
    async with system_rls_session() as db:
        result = await db.execute(select(Organization).where(Organization.id == organization_id))
        return result.scalar_one_or_none()


async def apply_persona_inputs_for_organization_id(
    inputs: dict[str, Any],
    organization_id: Optional[int],
) -> None:
    """Load the organization row and overwrite persona keys on inputs."""
    apply_persona_inputs(inputs, await _organization_for_persona(organization_id))
