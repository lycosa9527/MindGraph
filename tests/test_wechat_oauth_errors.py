"""WeChat official errcode mapping and bind/login handlers."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Optional, cast

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.oauth_user_link import OAUTH_PROVIDER_WECHAT
from services.auth.oauth.oauth_constants import (
    AUTH_ERROR_ALREADY_BOUND,
    AUTH_ERROR_DISABLED,
    AUTH_ERROR_EXCHANGE_FAILED,
    AUTH_ERROR_EXTERNAL_TAKEN,
    AUTH_ERROR_INVALID_CODE,
    AUTH_ERROR_MISCONFIGURED,
    AUTH_ERROR_NOT_LINKED,
    AUTH_ERROR_RATE_LIMITED,
    OAUTH_MODE_LOGIN,
    normalize_oauth_error_code,
)
from services.auth.oauth.oauth_login_service import OauthLoginService
from services.auth.oauth.wechat_oauth_errors import (
    WECHAT_ERR_CODE_BEEN_USED,
    WECHAT_ERR_INVALID_APPSECRET,
    WECHAT_ERR_INVALID_CODE,
    WECHAT_ERR_MINUTE_QUOTA,
    WECHAT_ERR_SYSTEM,
    log_wechat_api_error,
    map_wechat_errcode,
    parse_wechat_errcode,
)

oauth_callback_mod = importlib.import_module("routers.auth.oauth.router")


def test_parse_wechat_errcode_ignores_success() -> None:
    """errcode 0 or missing is not an error."""
    assert parse_wechat_errcode({"access_token": "t"}) is None
    assert parse_wechat_errcode({"errcode": 0, "errmsg": "ok"}) is None
    assert parse_wechat_errcode({"errcode": "0"}) is None


def test_map_wechat_errcode_website_login_subset() -> None:
    """Official catalog codes used by sns/oauth2/access_token and sns/userinfo."""
    assert map_wechat_errcode(WECHAT_ERR_INVALID_CODE) == AUTH_ERROR_INVALID_CODE
    assert map_wechat_errcode(WECHAT_ERR_CODE_BEEN_USED) == AUTH_ERROR_INVALID_CODE
    assert map_wechat_errcode(WECHAT_ERR_INVALID_APPSECRET) == AUTH_ERROR_MISCONFIGURED
    assert map_wechat_errcode(WECHAT_ERR_MINUTE_QUOTA) == AUTH_ERROR_RATE_LIMITED
    assert map_wechat_errcode(WECHAT_ERR_SYSTEM) == AUTH_ERROR_RATE_LIMITED
    assert map_wechat_errcode(48001) == AUTH_ERROR_EXCHANGE_FAILED
    assert map_wechat_errcode(None) == AUTH_ERROR_EXCHANGE_FAILED


def test_log_wechat_api_error_returns_oauth_code(caplog: pytest.LogCaptureFixture) -> None:
    """Backend log includes official errcode, errmsg, rid, and toast code."""
    caplog.set_level("WARNING")
    code = log_wechat_api_error(
        api="sns/oauth2/access_token",
        data={
            "errcode": WECHAT_ERR_INVALID_CODE,
            "errmsg": "invalid code, rid: abc",
            "rid": "abc-1",
        },
    )
    assert code == AUTH_ERROR_INVALID_CODE
    text = caplog.text
    assert "errcode=40029" in text
    assert "rid=abc-1" in text
    assert "oauth=oauth_invalid_code" in text


def test_normalize_maps_client_setup_errors() -> None:
    """Missing env or empty code become specific user-facing codes."""
    assert normalize_oauth_error_code("wechat_not_configured") == AUTH_ERROR_MISCONFIGURED
    assert normalize_oauth_error_code("code_required") == AUTH_ERROR_INVALID_CODE
    assert normalize_oauth_error_code(AUTH_ERROR_ALREADY_BOUND) == AUTH_ERROR_ALREADY_BOUND


async def _existing_old_wechat(
    _self: object,
    _organization_id: int,
    _user_id: int,
    _provider: str,
) -> SimpleNamespace:
    """User already bound to wx-old."""
    return SimpleNamespace(external_id="wx-old", user_id=5)


async def _no_user_link(
    _self: object,
    _organization_id: int,
    _user_id: int,
    _provider: str,
) -> None:
    """No bind row for this user."""
    return None


async def _upsert_taken(_self: object, **_kwargs: object) -> None:
    """Identity belongs to another user."""
    raise ValueError("external_id_taken")


async def _resolve_missing(
    _self: object,
    _organization_id: int,
    _provider: str,
    _external_id: str,
) -> Optional[int]:
    """No oauth_user_links row."""
    return None


@pytest.mark.asyncio
async def test_complete_bind_rejects_second_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User already bound to a different WeChat must unbind first."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.OauthUserLinkRepository.get_for_user",
        _existing_old_wechat,
    )
    service = OauthLoginService(db=cast(AsyncSession, SimpleNamespace()))
    with pytest.raises(ValueError, match=AUTH_ERROR_ALREADY_BOUND):
        await service.complete_bind(
            organization_id=1,
            user_id=5,
            provider="wechat",
            external_id="wx-new",
        )


@pytest.mark.asyncio
async def test_complete_bind_rejects_identity_on_other_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WeChat already linked to another MindGraph user."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.OauthUserLinkRepository.get_for_user",
        _no_user_link,
    )
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.OauthUserLinkRepository.upsert_link",
        _upsert_taken,
    )
    service = OauthLoginService(db=cast(AsyncSession, SimpleNamespace()))
    with pytest.raises(ValueError, match=AUTH_ERROR_EXTERNAL_TAKEN):
        await service.complete_bind(
            organization_id=1,
            user_id=5,
            provider="wechat",
            external_id="wx-taken",
        )


@pytest.mark.asyncio
async def test_resolve_login_user_not_linked_is_not_signup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing bind is oauth_not_linked; no account is created."""
    monkeypatch.setattr(
        "services.auth.oauth.oauth_login_service.OauthUserLinkRepository.resolve_user_id",
        _resolve_missing,
    )
    service = OauthLoginService(db=cast(AsyncSession, SimpleNamespace()))
    with pytest.raises(ValueError, match=AUTH_ERROR_NOT_LINKED):
        await service.resolve_login_user(
            organization_id=1,
            provider="wechat",
            external_id="wx-unknown",
        )


class _RollbackDb:
    """Session stub that records rollback."""

    def __init__(self) -> None:
        self.rolled_back = False

    async def rollback(self) -> None:
        """Mark rollback."""
        self.rolled_back = True


def _callback_request() -> Request:
    """Minimal ASGI request for the WeChat callback."""
    return Request(
        {
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
    )


async def _consume_wechat_login_state(_state: str) -> SimpleNamespace:
    """Unscoped WeChat login state."""
    return SimpleNamespace(
        provider=OAUTH_PROVIDER_WECHAT,
        mode=OAUTH_MODE_LOGIN,
        organization_id=0,
        user_id=None,
    )


@pytest.mark.asyncio
async def test_wechat_callback_not_linked_redirects_to_auth_toast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unbound scan must 303 to /auth?error=oauth_not_linked for the login toast."""

    async def _assert_enabled(_self: object, _org_id: int, _provider: str) -> None:
        return None

    async def _exchange(_self: object, _code: str) -> tuple[str, str, str]:
        return ("wx-union", "wx-open", "nick")

    async def _resolve_unlinked(_self: object, **_kwargs: object) -> None:
        raise ValueError(AUTH_ERROR_NOT_LINKED)

    monkeypatch.setattr(
        oauth_callback_mod,
        "consume_oauth_state",
        _consume_wechat_login_state,
    )
    monkeypatch.setattr(OauthLoginService, "assert_provider_enabled", _assert_enabled)
    monkeypatch.setattr(OauthLoginService, "exchange_wechat_identity", _exchange)
    monkeypatch.setattr(OauthLoginService, "resolve_login_user", _resolve_unlinked)
    db = _RollbackDb()
    redirect = await oauth_callback_mod.wechat_oauth_callback(
        request=_callback_request(),
        code="wx-code",
        state="st",
        _system_rls=None,
        db=cast(AsyncSession, db),
    )
    assert redirect.status_code == 303
    assert redirect.headers["location"] == f"/auth?error={AUTH_ERROR_NOT_LINKED}"
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_wechat_callback_http_error_redirects_instead_of_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider HTTPException after scan must still become a login-page toast."""

    async def _assert_disabled(_self: object, _org_id: int, _provider: str) -> None:
        raise HTTPException(status_code=404, detail=AUTH_ERROR_DISABLED)

    monkeypatch.setattr(
        oauth_callback_mod,
        "consume_oauth_state",
        _consume_wechat_login_state,
    )
    monkeypatch.setattr(OauthLoginService, "assert_provider_enabled", _assert_disabled)
    db = _RollbackDb()
    redirect = await oauth_callback_mod.wechat_oauth_callback(
        request=_callback_request(),
        code="wx-code",
        state="st",
        _system_rls=None,
        db=cast(AsyncSession, db),
    )
    assert redirect.status_code == 303
    assert redirect.headers["location"] == f"/auth?error={AUTH_ERROR_DISABLED}"
    assert db.rolled_back is True
