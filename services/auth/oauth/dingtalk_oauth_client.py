"""DingTalk OAuth 2.0 client for third-party website scan login."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from services.auth.oauth.oauth_constants import DINGTALK_CONTACT_ME_URL, DINGTALK_USER_TOKEN_URL
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DingtalkTokenResult:
    """User access token from authCode exchange."""

    access_token: str
    expire_in: int
    corp_id: Optional[str]
    refresh_token: Optional[str]


@dataclass(frozen=True)
class DingtalkContactProfile:
    """User profile from contact/users/me."""

    union_id: str
    open_id: Optional[str]
    nick: Optional[str]
    mobile: Optional[str]


class DingtalkOauthClient:
    """HTTP client for DingTalk OAuth 2.0 login."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        timeout: float = 15.0,
    ) -> None:
        self._client_id = (client_id or "").strip()
        self._client_secret = (client_secret or "").strip()
        self._timeout = timeout

    async def exchange_auth_code(self, auth_code: str) -> DingtalkTokenResult:
        """Exchange authCode for user access token."""
        code = (auth_code or "").strip()
        if not code:
            raise ValueError("auth_code_required")
        if not self._client_id or not self._client_secret:
            raise ValueError("dingtalk_not_configured")
        body = {
            "clientId": self._client_id,
            "clientSecret": self._client_secret,
            "code": code,
            "grantType": "authorization_code",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(DINGTALK_USER_TOKEN_URL, json=body)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("DingTalk token exchange failed: %s", exc)
            raise ValueError("dingtalk_exchange_failed") from exc
        access = data.get("accessToken")
        if not access:
            logger.warning("DingTalk token missing accessToken: %s", data)
            raise ValueError("dingtalk_exchange_failed")
        expire = data.get("expireIn")
        corp = data.get("corpId")
        refresh = data.get("refreshToken")
        return DingtalkTokenResult(
            access_token=str(access),
            expire_in=int(expire) if isinstance(expire, int) else 7200,
            corp_id=str(corp) if corp else None,
            refresh_token=str(refresh) if refresh else None,
        )

    async def fetch_contact_me(self, access_token: str) -> DingtalkContactProfile:
        """Fetch current user's unionId via contact/users/me."""
        token = (access_token or "").strip()
        if not token:
            raise ValueError("access_token_required")
        headers = {"x-acs-dingtalk-access-token": token}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(DINGTALK_CONTACT_ME_URL, headers=headers)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("DingTalk contact/me failed: %s", exc)
            raise ValueError("dingtalk_userinfo_failed") from exc
        union_id = data.get("unionId")
        if not union_id:
            raise ValueError("dingtalk_userinfo_failed")
        open_id = data.get("openId")
        nick = data.get("nick")
        mobile = data.get("mobile")
        return DingtalkContactProfile(
            union_id=str(union_id),
            open_id=str(open_id) if open_id else None,
            nick=str(nick) if nick else None,
            mobile=str(mobile) if mobile else None,
        )
