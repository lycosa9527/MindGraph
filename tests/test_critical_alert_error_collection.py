"""Tests for critical alert error collection deduplication."""

from unittest.mock import patch

import pytest

from services.infrastructure.monitoring.critical_alert import CriticalAlertService


@pytest.mark.asyncio
async def test_send_critical_alert_skips_persist_when_flag_false():
    """Critical alerts skip error persistence when persist_error is false."""
    with patch(
        "services.infrastructure.monitoring.critical_alert.record_failure",
    ) as mock_record:
        with patch(
            "services.infrastructure.monitoring.critical_alert.admin_sms_alerts_enabled",
            return_value=False,
        ):
            await CriticalAlertService.send_critical_alert(
                component="Application",
                error_type="RuntimeError",
                error_message="boom",
                persist_error=False,
            )
    mock_record.assert_not_called()


@pytest.mark.asyncio
async def test_send_critical_alert_persists_when_flag_true():
    """Critical alerts persist to the error collector when persist_error is true."""
    with patch(
        "services.infrastructure.monitoring.critical_alert.record_failure",
    ) as mock_record:
        with patch(
            "services.infrastructure.monitoring.critical_alert.admin_sms_alerts_enabled",
            return_value=False,
        ):
            await CriticalAlertService.send_critical_alert(
                component="Application",
                error_type="RuntimeError",
                error_message="boom",
                persist_error=True,
            )
    mock_record.assert_called_once()


@pytest.mark.asyncio
async def test_send_unhandled_exception_alert_does_not_persist():
    """Unhandled exception alerts never write to the error collector."""
    with patch(
        "services.infrastructure.monitoring.critical_alert.record_failure",
    ) as mock_record:
        with patch(
            "services.infrastructure.monitoring.critical_alert.admin_sms_alerts_enabled",
            return_value=False,
        ):
            await CriticalAlertService.send_unhandled_exception_alert(
                component="Application",
                exception_type="ValueError",
                error_message="boom",
                stack_trace="trace",
                request_path="/api/test",
            )
    mock_record.assert_not_called()
