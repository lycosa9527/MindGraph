"""Organization fields embedded in auth user payloads (login, /me, register)."""

from __future__ import annotations

from typing import Optional


def _org_mindmate_agent_name(org) -> Optional[str]:
    if not org:
        return None
    raw = getattr(org, "mindmate_agent_name", None)
    if not raw:
        return None
    stripped = str(raw).strip()
    return stripped or None


def _org_mindmate_avatar_url(org) -> Optional[str]:
    if not org:
        return None
    raw = getattr(org, "mindmate_agent_avatar_url", None)
    if not raw:
        return None
    stripped = str(raw).strip()
    return stripped or None


def organization_session_payload(org) -> dict:
    """Build organization object for login, register, and /me responses."""
    if not org:
        return {
            "id": None,
            "code": None,
            "name": None,
            "display_name": None,
            "mindmate_agent_name": None,
            "mindmate_agent_avatar_url": None,
        }
    display_raw = getattr(org, "display_name", None)
    display_stripped = (str(display_raw).strip() if display_raw else "") or None
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "display_name": display_stripped,
        "mindmate_agent_name": _org_mindmate_agent_name(org),
        "mindmate_agent_avatar_url": _org_mindmate_avatar_url(org),
    }
