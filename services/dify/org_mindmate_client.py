"""Resolve AsyncDifyClient for MindMate from organization override or global env."""

from __future__ import annotations

import logging
import os
from typing import Optional, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient
from models.domain.auth import Organization

logger = logging.getLogger(__name__)


class MindmateDifyNotConfiguredError(Exception):
    """Raised when neither org override nor global Dify credentials are available."""


def _global_dify_credentials() -> tuple[str, str, int]:
    api_key = (os.getenv("DIFY_API_KEY") or "").strip()
    api_url = (os.getenv("DIFY_API_URL") or "https://api.dify.ai/v1").strip()
    timeout = int(os.getenv("DIFY_TIMEOUT", "300"))
    return api_key, api_url, timeout


def global_mindmate_dify_credentials() -> tuple[str, str]:
    """Return global MindMate Dify API key and base URL from environment."""
    api_key, api_url, _timeout = _global_dify_credentials()
    return api_key, api_url


async def _org_dify_credentials(
    db: AsyncSession,
    organization_id: int,
) -> Optional[tuple[str, str]]:
    org = (
        await db.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one_or_none()
    if org is None:
        return None
    base_url = (cast(Optional[str], getattr(org, "dify_api_base_url", None)) or "").strip()
    api_key = (cast(Optional[str], getattr(org, "dify_api_key", None)) or "").strip()
    if base_url and api_key:
        return api_key, base_url
    if base_url or api_key:
        logger.debug(
            "Organization %s has incomplete MindMate Dify override; using global env",
            organization_id,
        )
    return None


async def resolve_mindmate_dify_client(
    db: AsyncSession,
    organization_id: Optional[int],
) -> AsyncDifyClient:
    """
    Build Dify client for MindMate: per-org credentials when both URL and key are set,
    otherwise global ``DIFY_API_*`` environment variables.
    """
    api_key = ""
    api_url = ""
    timeout = int(os.getenv("DIFY_TIMEOUT", "300"))

    if organization_id is not None:
        org_creds = await _org_dify_credentials(db, organization_id)
        if org_creds is not None:
            api_key, api_url = org_creds

    if not api_key:
        global_key, global_url, timeout = _global_dify_credentials()
        api_key = global_key
        api_url = global_url

    if not api_key:
        raise MindmateDifyNotConfiguredError()

    return AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)


async def resolve_mindmate_dify_client_or_http(
    db: AsyncSession,
    organization_id: Optional[int],
    *,
    detail: str,
) -> AsyncDifyClient:
    """Like ``resolve_mindmate_dify_client`` but raises HTTP 500 with *detail* if unconfigured."""
    try:
        return await resolve_mindmate_dify_client(db, organization_id)
    except MindmateDifyNotConfiguredError as exc:
        raise HTTPException(status_code=500, detail=detail) from exc
