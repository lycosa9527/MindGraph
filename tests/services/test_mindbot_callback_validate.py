"""Tests for pipeline/callback_validate.py (hdr_for_cfg, validate_callback_fast fast paths)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.mindbot.errors import MindbotErrorCode, mindbot_error_headers
from services.mindbot.pipeline.callback_validate import (
    hdr_for_cfg,
    validate_callback_fast,
)


def _make_cfg(
    org_id: int = 1,
    robot_code: str = "rc-test",
    is_enabled: bool = True,
    app_secret: str = "secret-val",
) -> SimpleNamespace:
    return SimpleNamespace(
        organization_id=org_id,
        dingtalk_robot_code=robot_code,
        dingtalk_app_secret=app_secret,
        is_enabled=is_enabled,
    )


# ---------------------------------------------------------------------------
# hdr_for_cfg
# ---------------------------------------------------------------------------


def test_hdr_for_cfg_ok() -> None:
    cfg = _make_cfg(org_id=5, robot_code="r1")
    result = hdr_for_cfg(cfg, MindbotErrorCode.OK)
    expected = mindbot_error_headers(
        MindbotErrorCode.OK, organization_id=5, robot_code="r1"
    )
    assert result == expected


def test_hdr_for_cfg_dify_failed() -> None:
    cfg = _make_cfg(org_id=7, robot_code="r2")
    result = hdr_for_cfg(cfg, MindbotErrorCode.DIFY_FAILED)
    assert result.get("X-MindBot-Error-Code") == MindbotErrorCode.DIFY_FAILED.value


def test_hdr_for_cfg_strips_robot_code_whitespace() -> None:
    cfg = _make_cfg(robot_code="  rc-padded  ")
    result = hdr_for_cfg(cfg, MindbotErrorCode.OK)
    assert result.get("X-MindBot-Robot-Code") == "rc-padded"


# ---------------------------------------------------------------------------
# validate_callback_fast — feature-disabled path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_callback_fast_feature_disabled_returns_404() -> None:
    with patch("services.mindbot.pipeline.callback_validate.config") as mock_cfg:
        mock_cfg.FEATURE_MINDBOT = False
        ok, early, ctx = await validate_callback_fast(
            timestamp_header="ts",
            sign_header="sg",
            body={"msgId": "m1"},
        )
    assert ok is False
    assert early is not None
    status, _headers = early
    assert status == 404
    assert ctx is None


# ---------------------------------------------------------------------------
# validate_callback_fast — probe (empty body, no signature) returns 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_callback_fast_shared_probe_returns_200() -> None:
    """Empty body + no sig + no config = shared endpoint probe; must return 200."""
    with patch("services.mindbot.pipeline.callback_validate.config") as mock_cfg:
        mock_cfg.FEATURE_MINDBOT = True
        ok, early, ctx = await validate_callback_fast(
            timestamp_header=None,
            sign_header=None,
            body={},
            resolved_config=None,
        )
    assert ok is False
    assert early is not None
    status, _ = early
    assert status == 200
    assert ctx is None


# ---------------------------------------------------------------------------
# validate_callback_fast — no resolved_config with real body → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_callback_fast_no_config_real_body_returns_404() -> None:
    with patch("services.mindbot.pipeline.callback_validate.config") as mock_cfg:
        mock_cfg.FEATURE_MINDBOT = True
        ok, early, ctx = await validate_callback_fast(
            timestamp_header="12345",
            sign_header="sigvalue",
            body={"msgId": "m1", "text": {"content": "hi"}},
            resolved_config=None,
        )
    assert ok is False
    assert early is not None
    status, _ = early
    assert status == 404
    assert ctx is None


# ---------------------------------------------------------------------------
# validate_callback_fast — config disabled returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_callback_fast_config_disabled_returns_404() -> None:
    cfg = _make_cfg(is_enabled=False)
    with patch("services.mindbot.pipeline.callback_validate.config") as mock_cfg:
        mock_cfg.FEATURE_MINDBOT = True
        ok, early, ctx = await validate_callback_fast(
            timestamp_header="12345",
            sign_header="sig",
            body={"msgId": "m1"},
            resolved_config=cfg,
        )
    assert ok is False
    assert early is not None
    status, _ = early
    assert status == 404
    assert ctx is None


# ---------------------------------------------------------------------------
# validate_callback_fast — path probe (resolved config, empty body) returns 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_callback_fast_path_probe_returns_200() -> None:
    cfg = _make_cfg(is_enabled=True)
    with patch("services.mindbot.pipeline.callback_validate.config") as mock_cfg:
        mock_cfg.FEATURE_MINDBOT = True
        ok, early, ctx = await validate_callback_fast(
            timestamp_header=None,
            sign_header=None,
            body={},
            resolved_config=cfg,
        )
    assert ok is False
    assert early is not None
    status, _ = early
    assert status == 200
    assert ctx is None


# ---------------------------------------------------------------------------
# validate_callback_fast — invalid signature returns 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_callback_fast_invalid_signature_returns_401() -> None:
    cfg = _make_cfg(is_enabled=True, app_secret="real-secret")
    with patch("services.mindbot.pipeline.callback_validate.config") as mock_cfg:
        mock_cfg.FEATURE_MINDBOT = True
        with patch(
            "services.mindbot.pipeline.callback_validate.verify_dingtalk_sign",
            return_value=False,
        ):
            ok, early, ctx = await validate_callback_fast(
                timestamp_header="99999",
                sign_header="bad-sig",
                body={"msgId": "m1", "text": {"content": "hi"}},
                resolved_config=cfg,
            )
    assert ok is False
    assert early is not None
    status, _ = early
    assert status == 401
    assert ctx is None


# ---------------------------------------------------------------------------
# validate_callback_fast — duplicate message (Redis returns False) → 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_callback_fast_duplicate_message_returns_200() -> None:
    cfg = _make_cfg(is_enabled=True)
    body = {"msgId": "dup-msg-1", "msgtype": "text", "text": {"content": "hi"}}
    with patch("services.mindbot.pipeline.callback_validate.config") as mock_cfg:
        mock_cfg.FEATURE_MINDBOT = True
        with patch(
            "services.mindbot.pipeline.callback_validate.verify_dingtalk_sign",
            return_value=True,
        ):
            with patch(
                "services.mindbot.pipeline.callback_validate.redis_setnx_ttl",
                AsyncMock(return_value=False),
            ):
                ok, early, ctx = await validate_callback_fast(
                    timestamp_header="ts",
                    sign_header="sg",
                    body=body,
                    resolved_config=cfg,
                )
    assert ok is False
    assert early is not None
    status, headers = early
    assert status == 200
    assert headers.get("X-MindBot-Error-Code") == MindbotErrorCode.DUPLICATE_MESSAGE.value
    assert ctx is None
