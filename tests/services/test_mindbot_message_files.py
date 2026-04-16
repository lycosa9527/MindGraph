"""Tests for DingTalk message file download helpers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.mindbot.platforms.dingtalk.media.message_files import (
    download_url_bytes,
    get_message_file_download_url,
)


# ---------------------------------------------------------------------------
# get_message_file_download_url — None / empty input guard (P0 fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_url_returns_none_when_download_code_is_none() -> None:
    result = await get_message_file_download_url(
        access_token="tok",
        robot_code="RC",
        download_code=None,  # type: ignore[arg-type]
    )
    assert result is None


@pytest.mark.asyncio
async def test_download_url_returns_none_when_robot_code_is_none() -> None:
    result = await get_message_file_download_url(
        access_token="tok",
        robot_code=None,  # type: ignore[arg-type]
        download_code="DC",
    )
    assert result is None


@pytest.mark.asyncio
async def test_download_url_returns_none_when_both_empty_strings() -> None:
    result = await get_message_file_download_url(
        access_token="tok",
        robot_code="",
        download_code="   ",
    )
    assert result is None


# ---------------------------------------------------------------------------
# get_message_file_download_url — successful URL path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_url_returns_url_on_success() -> None:
    fake_body = json.dumps({"downloadUrl": "https://example.com/file.bin"})

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=fake_body)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch(
        "services.mindbot.platforms.dingtalk.media.message_files.get_dingtalk_api_session",
        return_value=mock_session,
    ):
        result = await get_message_file_download_url(
            access_token="tok",
            robot_code="RC",
            download_code="DC",
        )

    assert result == "https://example.com/file.bin"


@pytest.mark.asyncio
async def test_download_url_returns_url_from_nested_data() -> None:
    fake_body = json.dumps({"data": {"downloadUrl": "https://cdn.example.com/img.png"}})

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=fake_body)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch(
        "services.mindbot.platforms.dingtalk.media.message_files.get_dingtalk_api_session",
        return_value=mock_session,
    ):
        result = await get_message_file_download_url(
            access_token="tok",
            robot_code="RC",
            download_code="DC",
        )

    assert result == "https://cdn.example.com/img.png"


@pytest.mark.asyncio
async def test_download_url_returns_none_on_http_error() -> None:
    mock_resp = MagicMock()
    mock_resp.status = 403
    mock_resp.text = AsyncMock(return_value='{"message":"Forbidden"}')
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)

    with patch(
        "services.mindbot.platforms.dingtalk.media.message_files.get_dingtalk_api_session",
        return_value=mock_session,
    ):
        result = await get_message_file_download_url(
            access_token="tok",
            robot_code="RC",
            download_code="DC",
        )

    assert result is None


# ---------------------------------------------------------------------------
# download_url_bytes — max-bytes truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_url_bytes_returns_none_when_too_large() -> None:
    big_data = b"x" * 10

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=big_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    with (
        patch(
            "services.mindbot.platforms.dingtalk.media.message_files.get_outbound_session",
            return_value=mock_session,
        ),
        patch(
            "services.mindbot.platforms.dingtalk.media.message_files.MAX_DOWNLOAD_MEDIA_BYTES",
            5,
        ),
    ):
        result = await download_url_bytes("https://example.com/big.bin")

    assert result is None


@pytest.mark.asyncio
async def test_download_url_bytes_returns_data_within_limit() -> None:
    data = b"hello"

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    with patch(
        "services.mindbot.platforms.dingtalk.media.message_files.get_outbound_session",
        return_value=mock_session,
    ):
        result = await download_url_bytes("https://example.com/small.bin")

    assert result == data
