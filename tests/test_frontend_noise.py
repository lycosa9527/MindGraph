"""Benign frontend noise denylist (scoped to frontend source)."""

from __future__ import annotations

from unittest.mock import patch

from services.monitoring.error_reporting import record_failure
from services.monitoring.frontend_noise import is_benign_frontend_noise


def test_wechat_bridge_is_noise() -> None:
    """WeChat JS bridge attribute errors must not enter error collection."""
    assert is_benign_frontend_noise("Cannot read properties of undefined (reading 'weixinPostMessageHandlers')")
    assert is_benign_frontend_noise("weixinDispatchMessage failed")
    assert is_benign_frontend_noise("WeixinJSBridge invoke error")


def test_stale_css_and_chunk_is_noise() -> None:
    """Stale deploy chunk / CSS preload failures are expected after release."""
    assert is_benign_frontend_noise("Unable to preload CSS for /assets/index-abc.css")
    assert is_benign_frontend_noise("Failed to fetch dynamically imported module: https://x/assets/x.js")
    assert is_benign_frontend_noise("Loading chunk index-abc failed")


def test_script_error_is_noise() -> None:
    """Opaque cross-origin Script error has no actionable stack."""
    assert is_benign_frontend_noise("Script error.")
    assert is_benign_frontend_noise("Script error")


def test_offset_height_is_not_noise() -> None:
    """Bare Element Plus / measure races must not be broadly denylisted."""
    assert not is_benign_frontend_noise("Cannot read properties of null (reading 'offsetHeight')")


def test_record_failure_skips_frontend_noise_only() -> None:
    """Frontend source skips noise; application source still records the same text."""
    noise = "Unable to preload CSS for /assets/App.css"
    with (
        patch("services.monitoring.error_reporting.error_collection_enabled", return_value=True),
        patch("services.monitoring.error_reporting.ErrorCollectorService.record") as record,
    ):
        record_failure(source="frontend", component="browser", message=noise)
        record.assert_not_called()

        record_failure(source="application", component="api", message=noise)
        record.assert_called_once()
        assert record.call_args[0][0].message == noise


def test_record_failure_keeps_application_offset_height() -> None:
    """Non-frontend sources are never filtered by the frontend noise denylist."""
    msg = "Cannot read properties of null (reading 'offsetHeight')"
    with (
        patch("services.monitoring.error_reporting.error_collection_enabled", return_value=True),
        patch("services.monitoring.error_reporting.ErrorCollectorService.record") as record,
    ):
        record_failure(source="application", component="api", message=msg)
        record.assert_called_once()
