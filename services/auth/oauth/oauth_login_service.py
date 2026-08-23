"""OAuth login/bind orchestration service."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from models.domain.auth import User
from models.domain.oauth_user_link import OAUTH_PROVIDER_DINGTALK, OAUTH_PROVIDER_WECHAT
from models.domain.organization_oauth_config import OrganizationOauthConfig
from repositories.oauth_user_link_repo import OauthUserLinkRepository
from repositories.organization_oauth_config_repo import OrganizationOauthConfigRepository
from services.auth.oauth.dingtalk_oauth_client import DingtalkOauthClient, DingtalkContactProfile
from services.auth.oauth.oauth_constants import (
    AUTH_ERROR_ALREADY_BOUND,
    AUTH_ERROR_CORP_MISMATCH,
    AUTH_ERROR_DISABLED,
    AUTH_ERROR_EXCHANGE_FAILED,
    AUTH_ERROR_EXTERNAL_TAKEN,
    AUTH_ERROR_INVALID_CODE,
    AUTH_ERROR_MISCONFIGURED,
    AUTH_ERROR_NOT_LINKED,
    AUTH_ERROR_RATE_LIMITED,
    DINGTALK_SCOPE_OPENID,
    OAUTH_ORG_UNSCOPED,
    normalize_oauth_error_code,
)
from services.auth.oauth.wechat_oauth_client import WechatOauthClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OauthProviderFlags:
    """Enabled OAuth providers for an organization."""

    wechat_enabled: bool
    dingtalk_enabled: bool
    wechat_app_id: str
    dingtalk_client_id: str
    dingtalk_scope: str
    wechat_callback_url: str
    dingtalk_callback_url: str


def oauth_feature_enabled() -> bool:
    """True when FEATURE_OAUTH_LOGIN is on."""
    return bool(getattr(config, "FEATURE_OAUTH_LOGIN", True))


def wechat_credentials_configured() -> bool:
    """True when global WeChat app credentials exist."""
    app_id = (getattr(config, "WECHAT_OAUTH_APP_ID", "") or "").strip()
    secret = (getattr(config, "WECHAT_OAUTH_APP_SECRET", "") or "").strip()
    return bool(app_id and secret)


def public_site_base_url() -> str:
    """Canonical HTTPS base for OAuth redirect URIs."""
    raw = (os.getenv("EXTERNAL_BASE_URL", "") or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return raw.rstrip("/")
    return ""


def wechat_callback_url() -> str:
    """Full WeChat OAuth callback URL."""
    base = public_site_base_url()
    if not base:
        return ""
    return f"{base}/api/auth/oauth/wechat/callback"


def require_wechat_callback_url() -> str:
    """Return the WeChat callback or fail closed when EXTERNAL_BASE_URL is unset."""
    url = wechat_callback_url()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AUTH_ERROR_MISCONFIGURED,
        )
    return url


def dingtalk_callback_url() -> str:
    """Full DingTalk OAuth callback URL."""
    base = public_site_base_url()
    if not base:
        return ""
    return f"{base}/api/auth/oauth/dingtalk/callback"


def encoded_callback_url(provider: str) -> str:
    """Url-encoded callback for embedded QR widgets."""
    if provider == OAUTH_PROVIDER_WECHAT:
        return quote(wechat_callback_url(), safe="")
    if provider == OAUTH_PROVIDER_DINGTALK:
        return quote(dingtalk_callback_url(), safe="")
    return ""


def _dingtalk_scope_for_config(row: OrganizationOauthConfig) -> str:
    """Scope for DTFrameLogin iframe embed.

    Official DingTalk docs require ``scope: openid`` for iframe/JS embed mode;
    ``openid corpid`` is for redirect flows only. Optional ``dingtalk_corp_id`` on
    the org row is validated server-side when the token response includes ``corpId``.
    """
    _ = row
    return DINGTALK_SCOPE_OPENID


def validate_dingtalk_corp_id(
    row: OrganizationOauthConfig,
    token_corp_id: Optional[str],
) -> None:
    """Reject token corpId when it conflicts with the school's configured corp."""
    expected = (row.dingtalk_corp_id or "").strip()
    if not expected:
        return
    actual = (token_corp_id or "").strip()
    if not actual:
        # openid-only iframe scope may omit corpId; per-school AppKey already scopes corp.
        return
    if actual != expected:
        raise ValueError(AUTH_ERROR_CORP_MISMATCH)


def resolve_provider_flags(row: Optional[OrganizationOauthConfig]) -> OauthProviderFlags:
    """Build provider availability for frontend.

    WeChat is platform-wide (feature flag + .env AppID/Secret). DingTalk stays
    per school because each school brings its own AppKey/Secret.
    """
    wechat_on = bool(oauth_feature_enabled() and wechat_credentials_configured())
    ding_key = (row.dingtalk_login_app_key or "").strip() if row else ""
    ding_secret = (row.dingtalk_login_app_secret or "").strip() if row else ""
    ding_on = bool(
        oauth_feature_enabled() and row is not None and row.dingtalk_login_enabled and ding_key and ding_secret
    )
    app_id = (getattr(config, "WECHAT_OAUTH_APP_ID", "") or "").strip()
    scope = _dingtalk_scope_for_config(row) if row else DINGTALK_SCOPE_OPENID
    return OauthProviderFlags(
        wechat_enabled=wechat_on,
        dingtalk_enabled=ding_on,
        wechat_app_id=app_id if wechat_on else "",
        dingtalk_client_id=ding_key if ding_on else "",
        dingtalk_scope=scope if ding_on else "",
        wechat_callback_url=wechat_callback_url() if wechat_on else "",
        dingtalk_callback_url=dingtalk_callback_url() if ding_on else "",
    )


class OauthLoginService:
    """Business logic for OAuth QR login and bind."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._org_repo = OrganizationOauthConfigRepository(db)
        self._link_repo = OauthUserLinkRepository(db)

    async def get_org_config(self, organization_id: int) -> Optional[OrganizationOauthConfig]:
        """Load org OAuth config."""
        return await self._org_repo.get_by_org(organization_id)

    def _wechat_client(self) -> WechatOauthClient:
        return WechatOauthClient(
            app_id=getattr(config, "WECHAT_OAUTH_APP_ID", ""),
            app_secret=getattr(config, "WECHAT_OAUTH_APP_SECRET", ""),
        )

    def _dingtalk_client(self, row: OrganizationOauthConfig) -> DingtalkOauthClient:
        return DingtalkOauthClient(
            client_id=(row.dingtalk_login_app_key or ""),
            client_secret=(row.dingtalk_login_app_secret or ""),
        )

    async def _validate_corp_id(
        self,
        row: OrganizationOauthConfig,
        token_corp_id: Optional[str],
    ) -> None:
        validate_dingtalk_corp_id(row, token_corp_id)

    async def exchange_wechat_identity(
        self,
        code: str,
    ) -> tuple[str, str, Optional[str]]:
        """Return external_id, openid, nickname."""
        client = self._wechat_client()
        try:
            token = await client.exchange_code(code)
        except ValueError as exc:
            raise ValueError(normalize_oauth_error_code(exc)) from exc
        nickname: Optional[str] = None
        profile = None
        try:
            profile = await client.fetch_userinfo(token.access_token, token.openid)
            nickname = profile.nickname
        except ValueError as exc:
            logger.warning("WeChat userinfo optional fetch skipped: %s", exc)
        external_id = WechatOauthClient.resolve_external_id(token, profile)
        return external_id, token.openid, nickname

    async def exchange_dingtalk_identity(
        self,
        row: OrganizationOauthConfig,
        auth_code: str,
    ) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Return unionId, openId, nick, corpId from token response."""
        client = self._dingtalk_client(row)
        try:
            token = await client.exchange_auth_code(auth_code)
        except ValueError as exc:
            raise ValueError(normalize_oauth_error_code(exc)) from exc
        await self._validate_corp_id(row, token.corp_id)
        try:
            profile: DingtalkContactProfile = await client.fetch_contact_me(token.access_token)
        except ValueError as exc:
            raise ValueError(normalize_oauth_error_code(exc)) from exc
        return profile.union_id, profile.open_id, profile.nick, token.corp_id

    async def complete_bind(
        self,
        *,
        organization_id: int,
        user_id: int,
        provider: str,
        external_id: str,
        openid: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> None:
        """Link OAuth identity to logged-in user.

        Same WeChat/DingTalk on this user is idempotent. A different identity
        requires unbind first. Identity already on another user is rejected.
        """
        existing = await self._link_repo.get_for_user(organization_id, user_id, provider)
        incoming = (external_id or "").strip()
        if existing is not None and (existing.external_id or "").strip() != incoming:
            logger.info(
                "OAuth bind blocked already_bound provider=%s org=%s user=%s",
                provider,
                organization_id,
                user_id,
            )
            raise ValueError(AUTH_ERROR_ALREADY_BOUND)
        try:
            await self._link_repo.upsert_link(
                organization_id=organization_id,
                user_id=user_id,
                provider=provider,
                external_id=external_id,
                openid=openid,
                nickname=nickname,
                linked_via="self",
            )
        except ValueError as exc:
            if str(exc) == "external_id_taken":
                logger.info(
                    "OAuth bind blocked external_taken provider=%s org=%s user=%s",
                    provider,
                    organization_id,
                    user_id,
                )
                raise ValueError(AUTH_ERROR_EXTERNAL_TAKEN) from exc
            raise
        logger.info(
            "OAuth bind ok provider=%s org=%s user=%s",
            provider,
            organization_id,
            user_id,
        )

    async def resolve_login_user(
        self,
        *,
        organization_id: int,
        provider: str,
        external_id: str,
    ) -> User:
        """Find linked user for login or raise oauth_not_linked.

        QR login never creates an account. Teachers must register, then bind
        WeChat/DingTalk under Account linking before scan sign-in works.
        """
        if int(organization_id) <= OAUTH_ORG_UNSCOPED:
            return await self._resolve_login_user_unscoped(provider, external_id)
        uid = await self._link_repo.resolve_user_id(organization_id, provider, external_id)
        if uid is None:
            logger.info(
                "OAuth login not linked provider=%s org=%s — register and bind first",
                provider,
                organization_id,
            )
            raise ValueError(AUTH_ERROR_NOT_LINKED)
        row = (await self._db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if row is None:
            logger.warning(
                "OAuth login link user missing provider=%s org=%s user_id=%s",
                provider,
                organization_id,
                uid,
            )
            raise ValueError(AUTH_ERROR_NOT_LINKED)
        if row.organization_id != organization_id:
            logger.warning(
                "OAuth login org mismatch provider=%s org=%s user_id=%s user_org=%s",
                provider,
                organization_id,
                uid,
                row.organization_id,
            )
            raise ValueError(AUTH_ERROR_NOT_LINKED)
        return row

    async def _resolve_login_user_unscoped(self, provider: str, external_id: str) -> User:
        """Find the bound user when login was started without a school invite."""
        links = await self._link_repo.list_by_external(provider, external_id)
        user_ids = {int(link.user_id) for link in links}
        if len(user_ids) != 1:
            logger.info(
                "OAuth login not linked provider=%s unscoped matches=%s — register and bind first",
                provider,
                len(user_ids),
            )
            raise ValueError(AUTH_ERROR_NOT_LINKED)
        uid = next(iter(user_ids))
        row = (await self._db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if row is None:
            logger.warning(
                "OAuth login link user missing provider=%s unscoped user_id=%s",
                provider,
                uid,
            )
            raise ValueError(AUTH_ERROR_NOT_LINKED)
        return row

    def assert_feature_enabled(self) -> None:
        """Raise if master OAuth flag is off."""
        if not oauth_feature_enabled():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=AUTH_ERROR_DISABLED,
            )

    async def assert_provider_enabled(
        self,
        organization_id: int,
        provider: str,
    ) -> Optional[OrganizationOauthConfig]:
        """Ensure the provider is available. DingTalk still needs a school row."""
        self.assert_feature_enabled()
        row = await self._org_repo.get_by_org(organization_id)
        flags = resolve_provider_flags(row)
        if provider == OAUTH_PROVIDER_WECHAT:
            if not flags.wechat_enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=AUTH_ERROR_MISCONFIGURED,
                )
            return row
        if provider == OAUTH_PROVIDER_DINGTALK and (row is None or not flags.dingtalk_enabled):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=AUTH_ERROR_DISABLED)
        return row

    async def require_dingtalk_config(self, organization_id: int) -> OrganizationOauthConfig:
        """DingTalk QR login needs a school AppKey/Secret row."""
        row = await self.assert_provider_enabled(organization_id, OAUTH_PROVIDER_DINGTALK)
        if row is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=AUTH_ERROR_DISABLED)
        return row

    @staticmethod
    def map_value_error(exc: ValueError) -> HTTPException:
        """Map service ValueError codes to HTTP responses."""
        code = normalize_oauth_error_code(exc)
        if code == AUTH_ERROR_NOT_LINKED:
            return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=code)
        if code == AUTH_ERROR_ALREADY_BOUND:
            return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=code)
        if code == AUTH_ERROR_RATE_LIMITED:
            return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=code)
        if code == AUTH_ERROR_MISCONFIGURED:
            return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=code)
        if code in {
            AUTH_ERROR_CORP_MISMATCH,
            AUTH_ERROR_EXTERNAL_TAKEN,
            AUTH_ERROR_EXCHANGE_FAILED,
            AUTH_ERROR_INVALID_CODE,
        }:
            return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=AUTH_ERROR_EXCHANGE_FAILED)
