"""ZhiHui teacher TTS endpoint smoke tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from fastapi import HTTPException

from routers.features.zhihui import routes as zhihui_routes


@pytest.mark.asyncio
async def test_synthesize_teacher_script_returns_mpeg() -> None:
    """Happy path: DashScope TTS bytes returned as audio/mpeg Response."""
    fake_tts = MagicMock()
    fake_tts.is_available.return_value = True
    fake_tts.synthesize_text = AsyncMock(return_value=b"ID3fake-mp3-bytes")

    with (
        patch.object(
            type(zhihui_routes.config),
            "FEATURE_ZHIHUI",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch.object(zhihui_routes, "get_tts_service", return_value=fake_tts),
    ):
        response = await zhihui_routes.synthesize_teacher_script(
            zhihui_routes.TeacherTtsRequest(text="今天我们聊聊竞争对手。"),
            _scope=MagicMock(),
        )

    assert response.media_type == "audio/mpeg"
    assert bytes(response.body).startswith(b"ID3")
    fake_tts.synthesize_text.assert_awaited()


@pytest.mark.asyncio
async def test_synthesize_teacher_script_unavailable() -> None:
    """503 when TTS keys are missing."""
    fake_tts = MagicMock()
    fake_tts.is_available.return_value = False

    with (
        patch.object(
            type(zhihui_routes.config),
            "FEATURE_ZHIHUI",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch.object(zhihui_routes, "get_tts_service", return_value=fake_tts),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await zhihui_routes.synthesize_teacher_script(
                zhihui_routes.TeacherTtsRequest(text="旁白"),
                _scope=MagicMock(),
            )
    assert exc_info.value.status_code == 503
