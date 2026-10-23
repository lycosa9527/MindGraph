"""Tests for critical alert error collection."""

from unittest.mock import patch

import pytest

from services.infrastructure.monitoring.critical_alert import CriticalAlertService


@pytest.mark.asyncio
async def test_send_critical_alert_skips_persist_when_flag_false():
    """Critical alerts skip error persistence when persist_error is false."""
    with patch(
        "services.infrastructure.monitoring.critical_alert.record_failure",
    ) as mock_record:
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
        await CriticalAlertService.send_critical_alert(
            component="Application",
            error_type="RuntimeError",
            error_message="boom",
            persist_error=True,
        )
    mock_record.assert_called_once()
