"""Withdraw accepts optional upload-failure reason for observability."""

from __future__ import annotations

import logging

import pytest

from routers.features.showcase.routes_posts import _normalize_withdraw_reason
from services.showcase.posts.lifecycle import log_withdraw


def test_normalize_withdraw_reason_defaults_and_clips() -> None:
    """Empty input becomes hard_delete; long reasons are clipped."""
    assert _normalize_withdraw_reason(None) == "hard_delete"
    assert _normalize_withdraw_reason("  ") == "hard_delete"
    assert _normalize_withdraw_reason("upload_SHOWCASE_STORAGE_CORS_OR_NETWORK") == (
        "upload_SHOWCASE_STORAGE_CORS_OR_NETWORK"
    )
    long = "x" * 300
    assert len(_normalize_withdraw_reason(long)) == 200


def test_log_withdraw_upload_reason_uses_upload_rollback_stage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Upload-prefixed reasons log as upload_rollback for log searches."""
    with caplog.at_level(logging.INFO, logger="showcase.workflow"):
        log_withdraw(
            post_id="9ed6d704-14de-42e5-838d-95199c79f4a7",
            user_id=3,
            reason="upload_SHOWCASE_STORAGE_CORS_OR_NETWORK",
        )
    assert any("stage=upload_rollback" in record.message for record in caplog.records)
