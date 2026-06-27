"""Unit tests for OAuth QR login helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.organization_oauth_config import OrganizationOauthConfig

from services.auth.oauth.dingtalk_oauth_client import DingtalkContactProfile, DingtalkTokenResult
from services.auth.oauth.oauth_constants import (
    AUTH_ERROR_EXCHANGE_FAILED,
    AUTH_ERROR_NOT_LINKED,
    normalize_oauth_error_code,
)
from services.auth.oauth.oauth_login_service import (
    oauth_feature_enabled,
    OauthLoginService,
    resolve_provider_flags,
    wechat_credentials_configured,
)
from services.auth.oauth.wechat_oauth_client import WechatOauthClient, WechatTokenResult, WechatUserInfo


def _org_oauth_row(**fields: object) -> OrganizationOauthConfig:
    """Build org OAuth config row for tests."""
    payload: dict[str, object] = {
        "organization_id": 1,
        "wechat_login_enabled": False,
        "dingtalk_login_enabled": False,
        "dingtalk_login_app_key": "",
        "dingtalk_login_app_secret": "",
        "dingtalk_corp_id": "",
    }
    payload.update(fields)
    return cast(OrganizationOauthConfig, SimpleNamespace(**payload))


def test_wechat_resolve_external_id_prefers_unionid() -> None:
    """Unionid wins over openid."""
    token = WechatTokenResult(
        access_token="t",
        openid="oid",
        unionid="uid",
        refresh_token=None,
    )
    profile = WechatUserInfo(openid="oid", nickname="n", unionid="uid2")
    assert WechatOauthClient.resolve_external_id(token, profile) == "uid2"


def test_wechat_resolve_external_id_falls_back_openid() -> None:
    """Openid used when unionid missing."""
    token = WechatTokenResult(
        access_token="t",
        openid="oid-only",
        unionid=None,
        refresh_token=None,
    )
    assert WechatOauthClient.resolve_external_id(token, None) == "oid-only"


def test_resolve_provider_flags_all_off_when_feature_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Master flag off disables all providers."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.oauth_feature_enabled",
        lambda: False,
    )
    row = _org_oauth_row(
        wechat_login_enabled=True,
        dingtalk_login_enabled=True,
        dingtalk_login_app_key="key",
        dingtalk_login_app_secret="secret",
    )
    flags = resolve_provider_flags(row)
    assert flags.wechat_enabled is False
    assert flags.dingtalk_enabled is False


def test_resolve_provider_flags_dingtalk_requires_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DingTalk needs app key and secret."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.oauth_feature_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.wechat_credentials_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.config",
        SimpleNamespace(WECHAT_OAUTH_APP_ID="wx123", WECHAT_OAUTH_APP_SECRET="sec"),
    )
    row = _org_oauth_row(
        wechat_login_enabled=True,
        dingtalk_login_enabled=True,
        dingtalk_login_app_key="",
        dingtalk_login_app_secret="secret",
    )
    flags = resolve_provider_flags(row)
    assert flags.wechat_enabled is True
    assert flags.dingtalk_enabled is False


def test_resolve_provider_flags_dingtalk_embed_scope_openid_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DTFrameLogin iframe uses openid scope even when corp_id is configured."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.oauth_feature_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.wechat_credentials_configured",
        lambda: False,
    )
    row = _org_oauth_row(
        dingtalk_login_enabled=True,
        dingtalk_login_app_key="dk",
        dingtalk_login_app_secret="ds",
        dingtalk_corp_id="corp123",
    )
    flags = resolve_provider_flags(row)
    assert flags.dingtalk_enabled is True
    assert flags.dingtalk_scope == "openid"


@pytest.mark.asyncio
async def test_validate_corp_id_skips_when_token_omits_corp_id() -> None:
    """openid iframe scope may not return corpId; do not fail when absent."""
    service = OauthLoginService(db=cast(AsyncSession, SimpleNamespace()))
    row = _org_oauth_row(dingtalk_corp_id="expected-corp")
    await service._validate_corp_id(row, None)  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_exchange_dingtalk_identity_corp_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corp mismatch raises oauth_corp_mismatch."""
    row = _org_oauth_row(
        dingtalk_login_app_key="k",
        dingtalk_login_app_secret="s",
        dingtalk_corp_id="expected-corp",
    )
    service = OauthLoginService(db=cast(AsyncSession, SimpleNamespace()))

    class FakeDingtalkClient:
        """Stub DingTalk client for corp mismatch test."""

        async def exchange_auth_code(self, auth_code: str) -> DingtalkTokenResult:
            """Return token with mismatched corp_id."""
            _ = auth_code
            return DingtalkTokenResult(
                access_token="token",
                expire_in=7200,
                corp_id="other-corp",
                refresh_token=None,
            )

        async def fetch_contact_me(self, access_token: str) -> DingtalkContactProfile:
            """Return minimal contact profile."""
            _ = access_token
            return DingtalkContactProfile(
                union_id="union",
                open_id="open",
                nick="nick",
                mobile=None,
            )

    monkeypatch.setattr(service, "_dingtalk_client", lambda _row: FakeDingtalkClient())

    with pytest.raises(ValueError, match="oauth_corp_mismatch"):
        await service.exchange_dingtalk_identity(row, "auth-code-123")


def test_oauth_feature_enabled_reads_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature flag helper reads config."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.config",
        SimpleNamespace(FEATURE_OAUTH_LOGIN=True),
    )
    assert oauth_feature_enabled() is True


def test_wechat_credentials_configured_requires_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """WeChat creds need app id and secret."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.config",
        SimpleNamespace(WECHAT_OAUTH_APP_ID="wx", WECHAT_OAUTH_APP_SECRET=""),
    )
    assert wechat_credentials_configured() is False


def test_normalize_oauth_error_code_maps_client_errors() -> None:
    """Client-specific failures surface as oauth_exchange_failed."""
    assert normalize_oauth_error_code("wechat_exchange_failed") == AUTH_ERROR_EXCHANGE_FAILED
    assert normalize_oauth_error_code("dingtalk_userinfo_failed") == AUTH_ERROR_EXCHANGE_FAILED
    assert normalize_oauth_error_code(AUTH_ERROR_NOT_LINKED) == AUTH_ERROR_NOT_LINKED
