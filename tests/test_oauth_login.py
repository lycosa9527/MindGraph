"""Unit tests for OAuth QR login helpers."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.organization_oauth_config import OrganizationOauthConfig
from routers.auth.oauth.router import wechat_oauth_callback

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
    validate_dingtalk_corp_id,
    wechat_credentials_configured,
)
from services.auth.oauth.oauth_post_login import (
    OAUTH_LOGIN_SUCCESS_PATH,
    issue_oauth_login_redirect,
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


def test_validate_corp_id_skips_when_token_omits_corp_id() -> None:
    """openid iframe scope may not return corpId; do not fail when absent."""
    row = _org_oauth_row(dingtalk_corp_id="expected-corp")
    validate_dingtalk_corp_id(row, None)


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


def test_wechat_callback_does_not_use_injected_response() -> None:
    """Cookies must go on the returned RedirectResponse, not a discarded Response param."""
    params = inspect.signature(wechat_oauth_callback).parameters
    assert "response" not in params


def test_normalize_oauth_error_code_maps_client_errors() -> None:
    """Client-specific failures surface as oauth_exchange_failed."""
    assert normalize_oauth_error_code("wechat_exchange_failed") == AUTH_ERROR_EXCHANGE_FAILED
    assert normalize_oauth_error_code("dingtalk_userinfo_failed") == AUTH_ERROR_EXCHANGE_FAILED
    assert normalize_oauth_error_code(AUTH_ERROR_NOT_LINKED) == AUTH_ERROR_NOT_LINKED


async def _resolve_user_id_missing(
    _self: object,
    _organization_id: int,
    _provider: str,
    _external_id: str,
) -> None:
    """No oauth_user_links row."""
    return None


async def _resolve_user_id_nine(
    _self: object,
    _organization_id: int,
    _provider: str,
    _external_id: str,
) -> int:
    """Bound to user 9."""
    return 9


@pytest.mark.asyncio
async def test_resolve_login_user_blocks_unlinked_wechat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scan login never creates an account; missing bind is oauth_not_linked."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.OauthUserLinkRepository.resolve_user_id",
        _resolve_user_id_missing,
    )
    service = OauthLoginService(db=cast(AsyncSession, SimpleNamespace()))
    with pytest.raises(ValueError, match=AUTH_ERROR_NOT_LINKED):
        await service.resolve_login_user(
            organization_id=1,
            provider="wechat",
            external_id="wx-union-missing",
        )


@pytest.mark.asyncio
async def test_resolve_login_user_blocks_org_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linked user in another school cannot sign in to this org."""
    linked = SimpleNamespace(id=9, organization_id=99)

    class ResultStub:
        """Scalar result stub."""

        def scalar_one_or_none(self) -> object:
            """Return the linked user in another org."""
            return linked

    class DbStub:
        """Session stub."""

        async def execute(self, _stmt: object) -> ResultStub:
            """Return the linked-user row."""
            return ResultStub()

    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.OauthUserLinkRepository.resolve_user_id",
        _resolve_user_id_nine,
    )
    service = OauthLoginService(db=cast(AsyncSession, DbStub()))
    with pytest.raises(ValueError, match=AUTH_ERROR_NOT_LINKED):
        await service.resolve_login_user(
            organization_id=1,
            provider="wechat",
            external_id="wx-union-other-org",
        )


def _oauth_cookie_names(response: RedirectResponse) -> set[str]:
    """Cookie names on a Starlette response."""
    names: set[str] = set()
    raw_headers = response.raw_headers
    for header_name, header_value in raw_headers:
        if header_name == b"set-cookie":
            cookie_pair = header_value.decode("latin-1").split(";", 1)[0]
            names.add(cookie_pair.split("=", 1)[0].strip())
    return names


class _SessionMgr:
    """Redis session stub."""

    async def store_session(self, *_args: object, **_kwargs: object) -> bool:
        """Pretend Redis stored the access session."""
        return True


class _RefreshMgr:
    """Refresh-token stub."""

    async def store_refresh_token(self, *_args: object, **_kwargs: object) -> bool:
        """Pretend Redis stored the refresh token."""
        return True


async def _skip_activity(*_args: object, **_kwargs: object) -> None:
    """Skip login activity persistence in unit tests."""
    return None


def _patch_oauth_session_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub Redis, JWT, and activity so cookie attachment can be tested."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_post_login.get_session_manager",
        _SessionMgr,
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_post_login.get_refresh_token_manager",
        _RefreshMgr,
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_post_login.create_access_token",
        lambda _user: "access-jwt",
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_post_login.create_refresh_token",
        lambda _uid: ("refresh-val", "refresh-hash"),
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_post_login.compute_device_hash",
        lambda _req: "devhash",
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_post_login.get_client_ip",
        lambda _req: "203.0.113.9",
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_post_login.track_user_activity",
        _skip_activity,
    )
    monkeypatch.setattr("routers.auth.helpers.is_https", lambda _req: True)
    monkeypatch.setattr(
        "routers.auth.helpers.clear_token_refresh_attempts",
        _skip_activity,
    )


@pytest.mark.asyncio
async def test_issue_oauth_login_redirect_sets_cookies_on_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WeChat callback must attach Set-Cookie to the returned 303, not a discarded Response."""
    _patch_oauth_session_deps(monkeypatch)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/auth/oauth/wechat/callback",
        "raw_path": b"/api/auth/oauth/wechat/callback",
        "query_string": b"",
        "headers": [],
        "scheme": "https",
        "server": ("testserver", 443),
        "client": ("203.0.113.9", 12345),
    }
    request = Request(scope)
    user = cast(User, SimpleNamespace(id=4, phone="13800000000", name="Teacher"))
    redirect = await issue_oauth_login_redirect(
        user,
        request,
        cast(AsyncSession, SimpleNamespace()),
        method="oauth_wechat",
    )
    assert redirect.status_code == 303
    assert redirect.headers["location"] == OAUTH_LOGIN_SUCCESS_PATH
    names = _oauth_cookie_names(redirect)
    assert "access_token" in names
    assert "refresh_token" in names
    assert "csrf_token" in names
