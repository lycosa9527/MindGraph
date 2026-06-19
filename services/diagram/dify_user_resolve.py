"""Resolve library save user id from HTTP request context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.requests.requests_diagram import GenerateDingTalkRequest
from services.diagram.generation_library_save import SAVE_LIMIT_REACHED
from services.diagram.generation_session_registry import lookup_generation_session
from services.diagram.library_save_user_notices import (
    library_save_limit_notice,
    library_save_skip_user_notice,
)
from utils.dify_user_key import resolve_user_and_org_from_dify_key

__all__ = [
    "DiagramSaveIdentity",
    "library_save_limit_notice",
    "library_save_skip_reason",
    "library_save_skip_user_notice",
    "resolve_diagram_save_identity",
]


@dataclass(frozen=True)
class DiagramSaveIdentity:
    """Resolved owner for generate_dingtalk library persistence."""

    user_id: Optional[int]
    organization_id: Optional[int]
    dify_user_key: str


def _dify_user_key_from_request(
    request: Request,
    req: Optional[GenerateDingTalkRequest],
) -> str:
    """
    Read the Dify ``user`` string forwarded by the HTTP tool.

    Priority: ``X-MG-Dify-User`` header, then ``dify_user_id`` / ``mg_dify_user`` body fields.
    """
    header_key = (request.headers.get("X-MG-Dify-User") or "").strip()
    if header_key:
        return header_key
    if req is not None:
        for field_name in ("dify_user_id", "mg_dify_user"):
            body_key = getattr(req, field_name, None)
            if isinstance(body_key, str) and body_key.strip():
                return body_key.strip()
    return ""


def _conversation_id_from_request(req: Optional[GenerateDingTalkRequest]) -> Optional[str]:
    if req is None:
        return None
    conv = getattr(req, "conversation_id", None)
    if isinstance(conv, str) and conv.strip():
        return conv.strip()[:100]
    return None


def _identity_from_session_user(
    session: dict,
    *,
    dify_user_key: str,
) -> DiagramSaveIdentity:
    org_raw = session.get("organization_id")
    org_id = int(org_raw) if org_raw is not None else None
    session_dify = session.get("dify_user_id")
    resolved_dify = dify_user_key
    if not resolved_dify and isinstance(session_dify, str):
        resolved_dify = session_dify.strip()
    return DiagramSaveIdentity(
        user_id=int(session["user_id"]),
        organization_id=org_id,
        dify_user_key=resolved_dify[:256],
    )


async def _identity_from_session(
    db: AsyncSession,
    session: dict,
    *,
    dify_user_key: str,
) -> DiagramSaveIdentity:
    session_user = session.get("user_id")
    if isinstance(session_user, int) and session_user > 0:
        return _identity_from_session_user(session, dify_user_key=dify_user_key)
    session_dify = session.get("dify_user_id")
    resolved_dify = dify_user_key
    if not resolved_dify and isinstance(session_dify, str):
        resolved_dify = session_dify.strip()
    if not resolved_dify:
        return DiagramSaveIdentity(user_id=None, organization_id=None, dify_user_key="")
    user_id, org_id = await resolve_user_and_org_from_dify_key(db, resolved_dify)
    return DiagramSaveIdentity(
        user_id=user_id,
        organization_id=org_id,
        dify_user_key=resolved_dify[:256],
    )


def library_save_skip_reason(
    *,
    user_id: Optional[int],
    saved_id: Optional[str],
    dify_user_key: str,
) -> Optional[str]:
    """
    Return a structured skip reason when library save did not produce a diagram id.

    Returns None when save succeeded.
    """
    if saved_id and saved_id != SAVE_LIMIT_REACHED:
        return None
    if saved_id == SAVE_LIMIT_REACHED:
        return "limit_reached"
    if user_id is None:
        key = (dify_user_key or "").strip()
        if key.startswith("mindbot_"):
            return "unbound_staff"
        return "no_user"
    return "save_error"


async def resolve_diagram_save_identity(
    db: AsyncSession,
    request: Request,
    current_user: Optional[User],
    req: Optional[GenerateDingTalkRequest] = None,
) -> DiagramSaveIdentity:
    """Resolve MindGraph user, org, and Dify key for library persistence."""
    if current_user is not None and hasattr(current_user, "id"):
        org_raw = getattr(current_user, "organization_id", None)
        org_id = int(org_raw) if org_raw is not None else None
        return DiagramSaveIdentity(
            user_id=int(current_user.id),
            organization_id=org_id,
            dify_user_key="",
        )

    dify_key = _dify_user_key_from_request(request, req)
    conversation_id = _conversation_id_from_request(req)

    if dify_key:
        user_id, org_id = await resolve_user_and_org_from_dify_key(db, dify_key)
        if user_id is not None or dify_key.startswith("mindbot_"):
            return DiagramSaveIdentity(
                user_id=user_id,
                organization_id=org_id,
                dify_user_key=dify_key,
            )

    session = await lookup_generation_session(
        conversation_id=conversation_id,
        dify_user_key=dify_key or None,
    )
    if session is not None:
        return await _identity_from_session(db, session, dify_user_key=dify_key)

    if dify_key:
        user_id, org_id = await resolve_user_and_org_from_dify_key(db, dify_key)
        return DiagramSaveIdentity(
            user_id=user_id,
            organization_id=org_id,
            dify_user_key=dify_key,
        )

    return DiagramSaveIdentity(user_id=None, organization_id=None, dify_user_key="")
