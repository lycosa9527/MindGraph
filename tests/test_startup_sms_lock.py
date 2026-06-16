"""Startup SMS lock lifecycle — one send per boot across staggered Uvicorn workers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.auth.sms_service import SMS_NOTIFICATION_RATE_LIMIT_MESSAGE

LIFESPAN_MODULE = "services.infrastructure.lifecycle.lifespan"


@pytest.mark.asyncio
async def test_startup_sms_keeps_lock_after_successful_send() -> None:
    release_mock = AsyncMock()
    send_mock = AsyncMock(return_value=(True, "Notification sent to 1 phone(s)"))
    sms_middleware = AsyncMock()
    sms_middleware.is_available = True
    sms_middleware.send_notification = send_mock

    with (
        patch(f"{LIFESPAN_MODULE}.admin_sms_alerts_enabled", return_value=True),
        patch.dict(
            "os.environ",
            {
                "SMS_STARTUP_NOTIFICATION_ENABLED": "true",
                "TENCENT_SMS_TEMPLATE_STARTUP": "2590580",
            },
            clear=False,
        ),
        patch(f"{LIFESPAN_MODULE}.ADMIN_PHONES", ["13800000000"]),
        patch(
            f"{LIFESPAN_MODULE}.get_sms_middleware",
            return_value=sms_middleware,
        ),
        patch(
            f"{LIFESPAN_MODULE}.acquire_startup_sms_notification_lock",
            new=AsyncMock(return_value="worker-lock-token"),
        ),
        patch(
            f"{LIFESPAN_MODULE}.release_startup_sms_notification_lock",
            new=release_mock,
        ),
    ):
        from services.infrastructure.lifecycle.lifespan import _send_startup_sms_notification_once

        await _send_startup_sms_notification_once()

    send_mock.assert_awaited_once()
    release_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_sms_releases_lock_after_failed_send() -> None:
    release_mock = AsyncMock()
    send_mock = AsyncMock(return_value=(False, "SMS notification failed for all recipients"))
    sms_middleware = AsyncMock()
    sms_middleware.is_available = True
    sms_middleware.send_notification = send_mock

    with (
        patch(f"{LIFESPAN_MODULE}.admin_sms_alerts_enabled", return_value=True),
        patch.dict(
            "os.environ",
            {
                "SMS_STARTUP_NOTIFICATION_ENABLED": "true",
                "TENCENT_SMS_TEMPLATE_STARTUP": "2590580",
            },
            clear=False,
        ),
        patch(f"{LIFESPAN_MODULE}.ADMIN_PHONES", ["13800000000"]),
        patch(
            f"{LIFESPAN_MODULE}.get_sms_middleware",
            return_value=sms_middleware,
        ),
        patch(
            f"{LIFESPAN_MODULE}.acquire_startup_sms_notification_lock",
            new=AsyncMock(return_value="worker-lock-token"),
        ),
        patch(
            f"{LIFESPAN_MODULE}.release_startup_sms_notification_lock",
            new=release_mock,
        ),
    ):
        from services.infrastructure.lifecycle.lifespan import _send_startup_sms_notification_once

        await _send_startup_sms_notification_once()

    release_mock.assert_awaited_once_with("worker-lock-token")


@pytest.mark.asyncio
async def test_startup_sms_keeps_lock_after_provider_rate_limit_failure() -> None:
    release_mock = AsyncMock()
    send_mock = AsyncMock(return_value=(False, SMS_NOTIFICATION_RATE_LIMIT_MESSAGE))
    sms_middleware = AsyncMock()
    sms_middleware.is_available = True
    sms_middleware.send_notification = send_mock

    with (
        patch(f"{LIFESPAN_MODULE}.admin_sms_alerts_enabled", return_value=True),
        patch.dict(
            "os.environ",
            {
                "SMS_STARTUP_NOTIFICATION_ENABLED": "true",
                "TENCENT_SMS_TEMPLATE_STARTUP": "2590580",
            },
            clear=False,
        ),
        patch(f"{LIFESPAN_MODULE}.ADMIN_PHONES", ["13800000000"]),
        patch(
            f"{LIFESPAN_MODULE}.get_sms_middleware",
            return_value=sms_middleware,
        ),
        patch(
            f"{LIFESPAN_MODULE}.acquire_startup_sms_notification_lock",
            new=AsyncMock(return_value="worker-lock-token"),
        ),
        patch(
            f"{LIFESPAN_MODULE}.release_startup_sms_notification_lock",
            new=release_mock,
        ),
    ):
        from services.infrastructure.lifecycle.lifespan import _send_startup_sms_notification_once

        await _send_startup_sms_notification_once()

    release_mock.assert_not_awaited()
