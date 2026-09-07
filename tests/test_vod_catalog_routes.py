"""VOD catalog routes: feature gate, org isolation, play payload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from models.domain.auth import User
from models.domain.vod import VodMedia
from services.features.vod.catalog import (
    VodCatalogError,
    issue_play_token,
    optional_list_org_filter,
    public_player_config,
    resolve_catalog_org_id,
    serialize_media,
)
from services.features.vod.credentials import TencentVodCredentials, TencentVodNotConfiguredError
from services.infrastructure.http.feature_gate import feature_flag_gate
from utils.auth.admin_panel_permissions import (
    CAP_TAB_VOD_EDIT,
    CAP_TAB_VOD_VIEW,
    capabilities_for_role,
)
from utils.auth.admin_scope import AdminScope


def _request(path: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    return Request(scope)


def _creds() -> TencentVodCredentials:
    return TencentVodCredentials(
        app_id=1500005696,
        secret_id="sid",
        secret_key="skey",
        play_key="PlayKey12",
        region="ap-guangzhou",
        license_url="https://license.example/vod",
        license_key="licensekeyexample",
        procedure="",
        psign_ttl=3600,
        upload_ttl=7200,
        adaptive_definition=10,
    )


def _school_scope() -> AdminScope:
    """School admin locked to organization 5."""
    return AdminScope(
        actor=SimpleNamespace(id=2),
        role="school_admin",
        capabilities=frozenset({CAP_TAB_VOD_VIEW, CAP_TAB_VOD_EDIT}),
        org_ids=frozenset({5}),
        effective_org_id=5,
        read_only=False,
    )


def _super_scope() -> AdminScope:
    """Superadmin with no organization selected."""
    return AdminScope(
        actor=SimpleNamespace(id=1),
        role="superadmin",
        capabilities=frozenset({CAP_TAB_VOD_VIEW, CAP_TAB_VOD_EDIT}),
        org_ids=None,
        effective_org_id=None,
        read_only=False,
    )


def _media_row(*, file_id: str = "file-1", media_id: str = "a") -> VodMedia:
    """Transient catalog row with an in-memory owner."""
    owner = User(id=2, name="Ada", password_hash="x", phone="13800000000")
    row = VodMedia(
        id=media_id,
        organization_id=5,
        owner_id=2,
        file_id=file_id,
        title="Lesson",
        description="",
        status="ready",
        duration_ms=1500,
        class_id=0,
        source_context="org:5:user:2:media:a",
    )
    row.owner = owner
    return row


@pytest.mark.asyncio
async def test_feature_gate_blocks_vod_when_off() -> None:
    """FEATURE_VOD off returns 404 for /api/vod paths."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_VOD=False),
    ):
        response = await feature_flag_gate(_request("/api/vod/media"), call_next)
    assert response.status_code == 404
    assert response.body
    call_next.assert_not_called()


def test_school_admin_and_superadmin_have_vod_caps() -> None:
    """School admins and superadmins receive tab.vod view and edit."""
    school = capabilities_for_role("school_admin")
    superadmin = capabilities_for_role("superadmin")
    assert CAP_TAB_VOD_VIEW in school
    assert CAP_TAB_VOD_EDIT in school
    assert CAP_TAB_VOD_VIEW in superadmin
    assert CAP_TAB_VOD_EDIT in superadmin
    assert CAP_TAB_VOD_VIEW not in capabilities_for_role("teacher")


def test_school_admin_cannot_list_other_org() -> None:
    """School admins cannot resolve a catalog org outside their school."""
    scope = _school_scope()
    assert optional_list_org_filter(scope, None) == 5
    with pytest.raises(VodCatalogError) as exc:
        resolve_catalog_org_id(scope, 9)
    assert exc.value.http_status == 403
    assert exc.value.code == "cross_org_forbidden"


def test_superadmin_may_filter_or_require_org_for_write() -> None:
    """Superadmins list all orgs unless filtered; writes require an org id."""
    scope = _super_scope()
    assert optional_list_org_filter(scope, None) is None
    assert resolve_catalog_org_id(scope, 12) == 12
    with pytest.raises(VodCatalogError) as exc:
        resolve_catalog_org_id(scope, None)
    assert exc.value.http_status == 400


def test_play_token_shape_has_no_secrets() -> None:
    """Play payload has TCPlayer fields and never leaks PlayKey or CAM keys."""
    row = _media_row(file_id="387700000", media_id="mid-1")
    with patch(
        "services.features.vod.catalog.load_tencent_vod_credentials",
        return_value=_creds(),
    ):
        payload = issue_play_token(row)
    assert payload["appId"] == "1500005696"
    assert payload["fileId"] == "387700000"
    assert payload["licenseUrl"] == "https://license.example/vod"
    assert payload["licenseKey"] == "licensekeyexample"
    assert payload["id"] == "mid-1"
    assert isinstance(payload["psign"], str) and payload["psign"].count(".") == 2
    assert isinstance(payload["expireAt"], int)
    blob = str(payload)
    assert "PlayKey12" not in blob
    assert "skey" not in blob
    assert "myqcloud.com" not in blob


def test_public_config_hides_secrets() -> None:
    """Public config is appId plus licenseUrl, or configured=false."""
    with patch(
        "services.features.vod.catalog.load_tencent_vod_credentials",
        return_value=_creds(),
    ):
        cfg = public_player_config()
    assert cfg == {
        "configured": True,
        "appId": "1500005696",
        "licenseUrl": "https://license.example/vod",
        "licenseKey": "licensekeyexample",
    }
    with patch(
        "services.features.vod.catalog.load_tencent_vod_credentials",
        side_effect=TencentVodNotConfiguredError("missing"),
    ):
        empty = public_player_config()
    assert empty["configured"] is False


def test_serialize_media_omits_cdn_hosts() -> None:
    """Catalog JSON has no cover_url or other durable VOD hosts."""
    row = _media_row()
    data = serialize_media(row)
    assert data["owner_name"] == "Ada"
    assert "cover_url" not in data
    assert "http" not in str(data)


def test_catalog_error_maps_to_http() -> None:
    """VodCatalogError carries the HTTP status used by the route layer."""
    err = VodCatalogError("not_found", http_status=404)
    assert err.http_status == 404
    assert err.code == "not_found"
