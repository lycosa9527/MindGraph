"""Unit tests for Voice Notes Tencent ASR V2 bridge helpers."""

from __future__ import annotations

import base64
import json
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.api.voice_notes_ws import VOICE_NOTES_MAX_WS_MESSAGES_PER_SECOND
from services.features.tencent_asr_v2_errors import (
    TENCENT_ASR_CATEGORY_RETRY,
    TENCENT_ASR_NO_V2_FRAME,
    TencentAsrHandshakeError,
    tencent_asr_connect_error,
)
from services.features.voice_notes_asr_bridge import (
    ASR_CONFIG_USER_MESSAGE,
    run_voice_notes_asr_relay,
    voice_notes_error_json,
)
from services.features.voice_notes_markdown import (
    strip_voice_notes_markdown_meta,
    wrap_voice_notes_markdown,
)
from services.features.voice_notes_usage import (
    VOICE_NOTES_MODEL_ALIAS,
    VOICE_NOTES_PREFLIGHT_TOKENS,
    assert_voice_notes_usage_budget,
    estimate_voice_notes_asr_tokens,
    voice_notes_budget_error_payload,
)
from services.infrastructure.http.error_handler import (
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)
from services.infrastructure.monitoring.ws_metrics import _ENDPOINT_COUNTER
from services.monitoring.module_activity import VALID_MODULES
from services.redis.redis_activity_tracker import RedisActivityTracker


def test_voice_notes_error_json_shape() -> None:
    """Browser error frames use type/code/message."""
    raw = voice_notes_error_json("asr_config", "missing key")
    payload = json.loads(raw)
    assert payload == {"type": "error", "code": "asr_config", "message": "missing key"}


def test_voice_notes_token_estimate_from_pcm_and_transcript() -> None:
    """One second of PCM16 @16kHz maps to the duration proxy; chars add output."""
    pcm_one_sec = 16_000 * 2
    input_tokens, output_tokens, total = estimate_voice_notes_asr_tokens(pcm_one_sec, 12)
    assert input_tokens == 100
    assert output_tokens == 12
    assert total == 112


def test_voice_notes_budget_error_codes() -> None:
    """Budget exceptions map to browser error codes."""
    coin = ThinkingCoinInsufficientError(balance=1, cost=5, user_message="no coins")
    daily = UserDailyTokenCapExceededError(cap=10, used=10, user_message="cap hit")
    assert voice_notes_budget_error_payload(coin) == ("thinking_coin", "no coins")
    assert voice_notes_budget_error_payload(daily) == ("daily_token_cap", "cap hit")


def test_voice_notes_ws_allows_high_rate_pcm_frames() -> None:
    """96 kHz ScriptProcessor can exceed the default 40 msg/s WS cap."""
    assert VOICE_NOTES_MAX_WS_MESSAGES_PER_SECOND >= 80


def test_voice_notes_activity_and_metrics_wiring() -> None:
    """Module activity + WS metrics labels are registered for voice notes."""
    assert "voice_notes" in VALID_MODULES
    assert "voice_notes" in RedisActivityTracker.ACTIVITY_TYPES
    assert _ENDPOINT_COUNTER.get("voice_notes_asr") == "ws_voice_notes_connections"
    assert VOICE_NOTES_MODEL_ALIAS == "tencent-asr-v2"


@pytest.mark.asyncio
async def test_voice_notes_relay_start_append_stop() -> None:
    """Relay starts Tencent ASR V2, forwards PCM, finishes on stop."""
    sent: List[str] = []
    frames = [
        json.dumps({"type": "append", "audio": base64.b64encode(b"\x00\x01").decode()}),
        json.dumps({"type": "stop"}),
    ]

    async def fake_receive(_ws: Any) -> str:
        if not frames:
            raise RuntimeError("no more messages")
        return frames.pop(0)

    fake_asr = MagicMock()
    fake_asr.start = AsyncMock()
    fake_asr.send_pcm = AsyncMock()
    fake_asr.finish = AsyncMock()
    fake_asr.close = AsyncMock()

    with (
        patch(
            "services.features.voice_notes_asr_bridge.TencentAsrV2Client",
            return_value=fake_asr,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.receive_websocket_text_frame",
            side_effect=fake_receive,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.safe_websocket_send_text",
            side_effect=lambda _ws, text: sent.append(text),
        ),
    ):
        await run_voice_notes_asr_relay(MagicMock())

    fake_asr.start.assert_awaited_once()
    fake_asr.send_pcm.assert_awaited()
    pcm_arg = fake_asr.send_pcm.await_args.args[0]
    assert pcm_arg == b"\x00\x01"
    fake_asr.finish.assert_awaited()

    types = [json.loads(item)["type"] for item in sent]
    assert "started" in types
    assert "stopped" in types


@pytest.mark.asyncio
async def test_voice_notes_relay_settles_usage_for_user() -> None:
    """Successful relay with a user settles ASR proxy tokens."""
    user = MagicMock()
    user.id = 42
    user.organization_id = 7
    settle = AsyncMock(return_value=100)

    with (
        patch(
            "services.features.voice_notes_asr_bridge.TencentAsrV2Client",
        ) as ctor,
        patch(
            "services.features.voice_notes_asr_bridge.receive_websocket_text_frame",
            return_value=json.dumps({"type": "stop"}),
        ),
        patch(
            "services.features.voice_notes_asr_bridge.safe_websocket_send_text",
            new_callable=AsyncMock,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.settle_voice_notes_usage",
            settle,
        ),
    ):
        client = MagicMock()
        client.start = AsyncMock()
        client.send_pcm = AsyncMock()
        client.finish = AsyncMock()
        client.close = AsyncMock()
        ctor.return_value = client
        await run_voice_notes_asr_relay(MagicMock(), user=user)

    settle.assert_awaited_once()
    settle_args = settle.await_args
    assert settle_args is not None
    assert settle_args.kwargs["user"] is user
    assert settle_args.kwargs["success"] is True


@pytest.mark.asyncio
async def test_voice_notes_relay_passes_diarization_flag() -> None:
    """TencentAsrV2Client is constructed with the session speaker toggle."""
    captured: dict[str, Any] = {}

    def fake_ctor(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        client = MagicMock()
        client.start = AsyncMock()
        client.send_pcm = AsyncMock()
        client.finish = AsyncMock()
        client.close = AsyncMock()
        return client

    with (
        patch(
            "services.features.voice_notes_asr_bridge.TencentAsrV2Client",
            side_effect=fake_ctor,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.receive_websocket_text_frame",
            return_value=json.dumps({"type": "stop"}),
        ),
        patch(
            "services.features.voice_notes_asr_bridge.safe_websocket_send_text",
            new_callable=AsyncMock,
        ),
    ):
        await run_voice_notes_asr_relay(
            MagicMock(),
            diarization_enabled=True,
            speaker_context_id="vp-24h-abc",
        )

    assert captured.get("speaker_diarization") is True
    assert captured.get("speaker_context_id") == "vp-24h-abc"


@pytest.mark.asyncio
async def test_voice_notes_relay_opening_handshake_timeout() -> None:
    """Connect timeout is a classified handshake error, not a relay traceback."""
    sent: List[str] = []
    client = MagicMock()
    client.start = AsyncMock(
        side_effect=TencentAsrHandshakeError(tencent_asr_connect_error("timed out during opening handshake"))
    )
    client.finish = AsyncMock()
    client.close = AsyncMock()

    with (
        patch(
            "services.features.voice_notes_asr_bridge.TencentAsrV2Client",
            return_value=client,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.safe_websocket_send_text",
            side_effect=lambda _ws, text: sent.append(text),
        ),
    ):
        await run_voice_notes_asr_relay(MagicMock())

    payloads = [json.loads(item) for item in sent]
    assert payloads[0]["type"] == "error"
    assert payloads[0]["code"] == TENCENT_ASR_CATEGORY_RETRY
    assert payloads[0]["provider_code"] == TENCENT_ASR_NO_V2_FRAME
    assert any(item["type"] == "stopped" for item in payloads)
    client.finish.assert_awaited()


@pytest.mark.asyncio
async def test_voice_notes_relay_asr_config_hides_env_names() -> None:
    """Config RuntimeError is logged server-side; the browser sees a fixed string."""
    sent: List[str] = []
    client = MagicMock()
    client.start = AsyncMock(
        side_effect=RuntimeError("Tencent ASR is not configured (TENCENT_ASR_APP_ID plus SecretId/SecretKey)")
    )
    client.finish = AsyncMock()
    client.close = AsyncMock()

    with (
        patch(
            "services.features.voice_notes_asr_bridge.TencentAsrV2Client",
            return_value=client,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.safe_websocket_send_text",
            side_effect=lambda _ws, text: sent.append(text),
        ),
    ):
        await run_voice_notes_asr_relay(MagicMock())

    payloads = [json.loads(item) for item in sent]
    error = next(item for item in payloads if item["type"] == "error")
    assert error["code"] == "asr_config"
    assert error["message"] == ASR_CONFIG_USER_MESSAGE
    assert "TENCENT_ASR" not in error["message"]
    assert "Secret" not in error["message"]


@pytest.mark.asyncio
async def test_voice_notes_relay_stops_pcm_after_provider_error() -> None:
    """Provider on_error stops the receive loop; later appends are not sent."""
    sent: List[str] = []
    pcm_calls: list[bytes] = []
    frames = [
        json.dumps({"type": "append", "audio": base64.b64encode(b"\x00\x01").decode()}),
        json.dumps({"type": "append", "audio": base64.b64encode(b"\x00\x02").decode()}),
        json.dumps({"type": "stop"}),
    ]

    async def fake_receive(_ws: Any) -> str:
        if not frames:
            raise RuntimeError("no more messages")
        return frames.pop(0)

    captured: dict[str, Any] = {}

    def fake_ctor(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        client = MagicMock()
        client.start = AsyncMock()
        client.finish = AsyncMock()
        client.close = AsyncMock()

        async def send_pcm(pcm: bytes) -> None:
            pcm_calls.append(pcm)
            on_error = captured.get("on_error")
            if on_error is not None:
                await on_error(tencent_asr_connect_error("upstream closed"))

        client.send_pcm = AsyncMock(side_effect=send_pcm)
        return client

    with (
        patch(
            "services.features.voice_notes_asr_bridge.TencentAsrV2Client",
            side_effect=fake_ctor,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.receive_websocket_text_frame",
            side_effect=fake_receive,
        ),
        patch(
            "services.features.voice_notes_asr_bridge.safe_websocket_send_text",
            side_effect=lambda _ws, text: sent.append(text),
        ),
    ):
        await run_voice_notes_asr_relay(MagicMock())

    assert pcm_calls == [b"\x00\x01"]
    types = [json.loads(item)["type"] for item in sent]
    assert "error" in types
    assert "stopped" in types


@pytest.mark.asyncio
async def test_voice_notes_preflight_reserves_one_token() -> None:
    """Cap preflight uses 1 token so used == cap cannot start a session."""
    user = MagicMock()
    user.id = 7
    user.organization_id = 3
    budget = AsyncMock()
    with patch(
        "services.features.voice_notes_usage.assert_llm_usage_budget",
        budget,
    ):
        await assert_voice_notes_usage_budget(user, lang="en")
    budget.assert_awaited_once()
    assert budget.await_args is not None
    assert budget.await_args.kwargs["estimated_tokens"] == VOICE_NOTES_PREFLIGHT_TOKENS
    assert VOICE_NOTES_PREFLIGHT_TOKENS == 1


def test_strip_voice_notes_markdown_meta_keeps_talker_lines() -> None:
    """Mindmap generate must not send the trailing talker-status comment."""
    markdown = (
        '说话人1：你好\nRoy：在的\n\n<!-- mg-voice-notes:1\n{"v":1,"ids":[0,2],"names":{"2":"Roy"},"ctx":"vp_1"}\n-->'
    )
    assert strip_voice_notes_markdown_meta(markdown) == "说话人1：你好\nRoy：在的"
    assert strip_voice_notes_markdown_meta("说话人1：你好") == "说话人1：你好"


def test_wrap_voice_notes_markdown_matches_mobile_meta() -> None:
    """Watch COS blobs use the same trailing comment mobile Voice Notes writes."""
    wrapped = wrap_voice_notes_markdown("会议先定三个目标", saved_at_ms=1_000, elapsed_ms=12)
    assert strip_voice_notes_markdown_meta(wrapped) == "会议先定三个目标"
    assert "<!-- mg-voice-notes:1" in wrapped
    assert '"saved_at":1000' in wrapped
    assert '"elapsed_ms":12' in wrapped
    assert wrap_voice_notes_markdown("  \n") == ""
