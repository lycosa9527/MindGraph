"""
Embed session bootstrap: mgat_ API token → browser JWT cookies.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.helpers import set_auth_cookies
from services.auth.embed_session_handoff import (
    append_embed_query,
    consume_embed_handoff,
    create_embed_handoff,
    sanitize_embed_next_path,
)
from services.auth.vpn_geo_enforcement import record_vpn_login_geo
from services.redis.cache.redis_user_cache import user_cache
from services.redis.session.redis_session_manager import (
    get_refresh_token_manager,
    get_session_manager,
)
from services.utils.error_types import REDIS_ERRORS
from utils.auth import create_access_token, create_refresh_token
from utils.auth.mg_client import bind_mg_client_from_header
from utils.auth.request_helpers import get_client_ip
from utils.auth.tokens import compute_device_hash
from utils.auth.user_tokens import validate_user_token
from utils.db.rls_request import bind_system_bootstrap_rls_dependency

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])
_bearer = HTTPBearer(auto_error=False)

EMBED_CLIENT_WORD = "word-addin"


@router.post("/embed/handoff")
async def create_embed_session_handoff(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
) -> dict[str, Any]:
    """
    Exchange a valid mgat_ token for a short-lived one-time handoff code.

    The Word add-in (or similar) then navigates to ``/embed/complete`` so cookies
    are issued on the MindGraph origin.
    """
    bind_mg_client_from_header(request)
    account = (request.headers.get("X-MG-Account") or "").strip()
    ip_id = get_rate_limit_identifier(None, request)
    rate_id = f"{ip_id}:acct:{account or 'none'}"
    await check_endpoint_rate_limit(
        "embed_handoff",
        rate_id,
        max_requests=30,
        window_seconds=60,
    )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token required",
        )
    token = credentials.credentials.strip()
    if not token.startswith("mgat_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token required",
        )
    user = await validate_user_token(token, account, request)
    code = await create_embed_handoff(int(user.id))
    if not code:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Handoff temporarily unavailable",
        )
    return {"handoff": code, "expires_in": 60}


@router.get("/embed/complete")
async def complete_embed_session(
    request: Request,
    handoff: str = Query(..., min_length=8, max_length=128),
    next_path: str = Query("/mindgraph", alias="next"),
    db: AsyncSession = Depends(get_async_db),
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
) -> RedirectResponse:
    """Consume handoff code, set auth cookies, redirect into the SPA."""
    rate_id = get_rate_limit_identifier(None, request)
    await check_endpoint_rate_limit(
        "embed_complete",
        rate_id,
        max_requests=60,
        window_seconds=60,
    )

    user_id = await consume_embed_handoff(handoff)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired handoff",
        )

    user = await user_cache.get_by_id(user_id)
    if not user:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            db.expunge(user)
            try:
                await user_cache.cache_user(user)
            except REDIS_ERRORS:
                logger.debug("[EmbedComplete] user cache write failed", exc_info=True)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_token = create_access_token(user)
    refresh_token_value, refresh_token_hash = create_refresh_token(user.id)
    device_hash = compute_device_hash(request)
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    session_ok = await get_session_manager().store_session(user.id, access_token, device_hash=device_hash)
    refresh_ok = await get_refresh_token_manager().store_refresh_token(
        user_id=user.id,
        token_hash=refresh_token_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )
    if not session_ok or not refresh_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session persistence failed",
        )

    redirect = RedirectResponse(
        url=append_embed_query(sanitize_embed_next_path(next_path), EMBED_CLIENT_WORD),
        status_code=status.HTTP_302_FOUND,
    )
    set_auth_cookies(redirect, access_token, refresh_token_value, request)
    await record_vpn_login_geo(user.id, request)
    return redirect
