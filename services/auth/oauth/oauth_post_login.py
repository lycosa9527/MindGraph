"""Issue browser JWT session after OAuth login."""

from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from routers.auth.helpers import set_auth_cookies, track_user_activity
from services.redis.session.redis_session_manager import get_refresh_token_manager, get_session_manager
from utils.auth import compute_device_hash, create_access_token, create_refresh_token, get_client_ip


async def issue_oauth_browser_session(
    user: User,
    http_request: Request,
    response: Response,
    db: AsyncSession,
    *,
    method: str,
) -> None:
    """Set JWT cookies and record login activity after OAuth scan."""
    session_manager = get_session_manager()
    client_ip = get_client_ip(http_request)
    token = create_access_token(user)
    refresh_value, refresh_hash = create_refresh_token(user.id)
    device_hash = compute_device_hash(http_request)
    user_agent = http_request.headers.get("User-Agent", "")

    await session_manager.store_session(user.id, token, device_hash=device_hash)
    refresh_manager = get_refresh_token_manager()
    await refresh_manager.store_refresh_token(
        user_id=user.id,
        token_hash=refresh_hash,
        ip_address=client_ip,
        user_agent=user_agent,
        device_hash=device_hash,
    )
    set_auth_cookies(response, token, refresh_value, http_request)
    await track_user_activity(
        user,
        "login",
        {"method": method, "provider": method.split("_", maxsplit=1)[-1]},
        http_request,
        db,
    )
