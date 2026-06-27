"""WeChat Open Platform OAuth client (网站应用 snsapi_login)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from services.auth.oauth.oauth_constants import WECHAT_ACCESS_TOKEN_URL, WECHAT_USERINFO_URL
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WechatTokenResult:
    """Token exchange result."""

    access_token: str
    openid: str
    unionid: Optional[str]
    refresh_token: Optional[str]


@dataclass(frozen=True)
class WechatUserInfo:
    """Optional profile from userinfo endpoint."""

    openid: str
    nickname: Optional[str]
    unionid: Optional[str]


class WechatOauthClient:
    """HTTP client for WeChat website OAuth."""

    def __init__(self, *, app_id: str, app_secret: str, timeout: float = 15.0) -> None:
        self._app_id = (app_id or "").strip()
        self._app_secret = (app_secret or "").strip()
        self._timeout = timeout

    async def exchange_code(self, code: str) -> WechatTokenResult:
        """Exchange authorization code for access token."""
        auth_code = (code or "").strip()
        if not auth_code:
            raise ValueError("code_required")
        if not self._app_id or not self._app_secret:
            raise ValueError("wechat_not_configured")
        params = urlencode(
            {
                "appid": self._app_id,
                "secret": self._app_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
            }
        )
        url = f"{WECHAT_ACCESS_TOKEN_URL}?{params}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("WeChat token exchange failed: %s", exc)
            raise ValueError("wechat_exchange_failed") from exc
        if data.get("errcode"):
            logger.warning("WeChat token error: %s", data)
            raise ValueError("wechat_exchange_failed")
        access = data.get("access_token")
        openid = data.get("openid")
        if not access or not openid:
            raise ValueError("wechat_exchange_failed")
        unionid = data.get("unionid")
        refresh = data.get("refresh_token")
        return WechatTokenResult(
            access_token=str(access),
            openid=str(openid),
            unionid=str(unionid) if unionid else None,
            refresh_token=str(refresh) if refresh else None,
        )

    async def fetch_userinfo(self, access_token: str, openid: str) -> WechatUserInfo:
        """Fetch nickname and unionid from userinfo endpoint."""
        params = urlencode(
            {
                "access_token": access_token,
                "openid": openid,
                "lang": "zh_CN",
            }
        )
        url = f"{WECHAT_USERINFO_URL}?{params}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("WeChat userinfo failed: %s", exc)
            raise ValueError("wechat_userinfo_failed") from exc
        if data.get("errcode"):
            raise ValueError("wechat_userinfo_failed")
        nick = data.get("nickname")
        unionid = data.get("unionid")
        return WechatUserInfo(
            openid=str(openid),
            nickname=str(nick) if nick else None,
            unionid=str(unionid) if unionid else None,
        )

    @staticmethod
    def resolve_external_id(token: WechatTokenResult, profile: Optional[WechatUserInfo] = None) -> str:
        """Prefer unionid; fallback openid."""
        if profile and profile.unionid:
            return profile.unionid
        if token.unionid:
            return token.unionid
        return token.openid
