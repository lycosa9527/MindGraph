"""Regression: OAuth implementation matches official API endpoints and params."""

from __future__ import annotations

import inspect

from services.auth.oauth import dingtalk_oauth_client as dd
from services.auth.oauth import wechat_oauth_client as wx
from services.auth.oauth.oauth_constants import (
    DINGTALK_SCOPE_OPENID,
    OAUTH_STATE_TTL_SECONDS,
)

# Official WeChat 网站应用 doc endpoints
_WECHAT_OFFICIAL_TOKEN = "https://api.weixin.qq.com/sns/oauth2/access_token"
_WECHAT_OFFICIAL_USERINFO = "https://api.weixin.qq.com/sns/userinfo"

# Official DingTalk OAuth 2.0 doc endpoints (not legacy oapi.dingtalk.com)
_DINGTALK_OFFICIAL_USER_TOKEN = "https://api.dingtalk.com/v1.0/oauth2/userAccessToken"
_DINGTALK_OFFICIAL_CONTACT_ME = "https://api.dingtalk.com/v1.0/contact/users/me"


def test_wechat_client_uses_official_open_platform_urls() -> None:
    """WeChat token/userinfo URLs match open.weixin.qq.com website-app docs."""
    assert wx._WECHAT_ACCESS_TOKEN_URL == _WECHAT_OFFICIAL_TOKEN
    assert wx._WECHAT_USERINFO_URL == _WECHAT_OFFICIAL_USERINFO


def test_dingtalk_client_uses_oauth2_not_legacy_oapi() -> None:
    """DingTalk login client must use api.dingtalk.com v1.0 OAuth, not oapi.dingtalk.com."""
    assert dd._DINGTALK_USER_TOKEN_URL == _DINGTALK_OFFICIAL_USER_TOKEN
    assert dd._DINGTALK_CONTACT_ME_URL == _DINGTALK_OFFICIAL_CONTACT_ME
    assert "oapi.dingtalk.com" not in dd._DINGTALK_USER_TOKEN_URL
    assert "oapi.dingtalk.com" not in dd._DINGTALK_CONTACT_ME_URL


def test_dingtalk_token_request_body_field_names() -> None:
    """userAccessToken POST body uses official camelCase field names."""
    source = inspect.getsource(dd.DingtalkOauthClient.exchange_auth_code)
    assert "clientId" in source
    assert "clientSecret" in source
    assert "grantType" in source
    assert '"code"' in source or "'code'" in source


def test_oauth_state_ttl_matches_wechat_code_lifetime() -> None:
    """WeChat authorization code TTL is 10 minutes per official doc."""
    assert OAUTH_STATE_TTL_SECONDS == 600


def test_dingtalk_embed_scope_is_openid_only() -> None:
    """DTFrameLogin iframe embed requires openid scope per DingTalk tutorial."""
    assert DINGTALK_SCOPE_OPENID == "openid"
