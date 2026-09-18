"""Geo middleware must soft-resolve invalid mgat_ tokens (no ASGI crash)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from services.auth.email_login_cn_api_geo import maybe_enforce_email_login_cn_geo_api_async
from services.auth.vpn_geo_enforcement import maybe_enforce_vpn_cn_geo_async
from utils.auth.role_constants import ROLE_STUDENT


def _mgat_request() -> MagicMock:
    """Minimal HTTP connection shaped like Request for geo helpers."""
    connection = MagicMock()
    connection.url.path = "/api/auth/me"
    connection.headers = {
        "Authorization": "Bearer mgat_deadbeef",
        "X-MG-Account": "13800000000",
        "X-Language": "zh",
        "Accept-Language": "zh-CN",
    }
    connection.state = MagicMock(spec=[])
    return connection


@pytest.mark.asyncio
async def test_email_cn_geo_invalid_mgat_does_not_raise() -> None:
    """Invalid mgat_ during email CN geo resolve must return None, not HTTPException."""
    connection = _mgat_request()
    with (
        patch(
            "services.auth.email_login_cn_api_geo.EMAIL_LOGIN_CN_BLOCK_ENABLED",
            True,
        ),
        patch(
            "services.auth.email_login_cn_api_geo.AUTH_MODE",
            "standard",
        ),
        patch(
            "services.auth.email_login_cn_api_geo.try_decode_access_token_payload_from_connection",
            return_value=None,
        ),
        patch(
            "services.auth.email_login_cn_api_geo.extract_session_token",
            return_value="mgat_deadbeef",
        ),
        patch(
            "services.auth.email_login_cn_api_geo.validate_user_token",
            new=AsyncMock(
                side_effect=HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                )
            ),
        ),
    ):
        result = await maybe_enforce_email_login_cn_geo_api_async(connection)
    assert result is None


@pytest.mark.asyncio
async def test_email_cn_geo_skips_learning_space_students() -> None:
    """Synthetic student emails must not hit email-login GeoIP blocks."""
    connection = _mgat_request()
    connection.url.path = "/api/learning-space/student/change-password"
    student = MagicMock()
    student.role = ROLE_STUDENT
    student.learning_class_id = 23
    student.email = "s23.4830@student.learning.local"
    student.email_login_whitelisted_from_cn = False
    connection.state = MagicMock()
    setattr(connection.state, "auth_context_user", student)

    with (
        patch(
            "services.auth.email_login_cn_api_geo.EMAIL_LOGIN_CN_BLOCK_ENABLED",
            True,
        ),
        patch(
            "services.auth.email_login_cn_api_geo.AUTH_MODE",
            "standard",
        ),
        patch(
            "services.auth.email_login_cn_api_geo.AUTH_CONTEXT_USER_ATTR",
            "auth_context_user",
        ),
        patch(
            "services.auth.email_login_cn_api_geo.email_cn_geo_blocked",
            return_value=(True, "login_email_geoip_unavailable", False),
        ) as blocked,
    ):
        result = await maybe_enforce_email_login_cn_geo_api_async(connection)

    assert result is None
    blocked.assert_not_called()


@pytest.mark.asyncio
async def test_email_cn_geo_still_blocks_real_email_when_geoip_missing() -> None:
    """Real email accounts still get geo unavailable when country cannot be resolved."""
    connection = _mgat_request()
    teacher = MagicMock()
    teacher.role = "user"
    teacher.learning_class_id = None
    teacher.email = "teacher@example.com"
    teacher.email_login_whitelisted_from_cn = False
    connection.state = MagicMock()
    setattr(connection.state, "auth_context_user", teacher)

    with (
        patch(
            "services.auth.email_login_cn_api_geo.EMAIL_LOGIN_CN_BLOCK_ENABLED",
            True,
        ),
        patch(
            "services.auth.email_login_cn_api_geo.AUTH_MODE",
            "standard",
        ),
        patch(
            "services.auth.email_login_cn_api_geo.AUTH_CONTEXT_USER_ATTR",
            "auth_context_user",
        ),
        patch(
            "services.auth.email_login_cn_api_geo.get_client_ip",
            return_value="1.2.3.4",
        ),
        patch(
            "services.auth.email_login_cn_api_geo.email_cn_geo_blocked",
            return_value=(True, "login_email_geoip_unavailable", False),
        ),
        patch(
            "services.auth.email_login_cn_api_geo.Messages.error",
            return_value="geo unavailable",
        ),
    ):
        result = await maybe_enforce_email_login_cn_geo_api_async(connection)

    assert isinstance(result, JSONResponse)
    assert result.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_vpn_cn_geo_invalid_mgat_does_not_raise() -> None:
    """Invalid mgat_ during VPN/CN geo resolve must return None, not HTTPException."""
    connection = _mgat_request()
    with (
        patch(
            "services.auth.vpn_geo_enforcement.maybe_enforce_email_login_cn_geo_api_async",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.auth.vpn_geo_enforcement._vpn_geo_prereqs_ok",
            return_value=True,
        ),
        patch(
            "services.auth.vpn_geo_enforcement.try_decode_access_token_payload_from_connection",
            return_value=None,
        ),
        patch(
            "services.auth.vpn_geo_enforcement.extract_session_token",
            return_value="mgat_deadbeef",
        ),
        patch(
            "services.auth.vpn_geo_enforcement.validate_user_token",
            new=AsyncMock(
                side_effect=HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                )
            ),
        ),
    ):
        result = await maybe_enforce_vpn_cn_geo_async(connection)
    assert result is None
