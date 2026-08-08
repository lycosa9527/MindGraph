"""Unit tests for Voice Notes Fun-ASR bridge helpers and punctuation flag."""

from __future__ import annotations

import base64
import json
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.voice_notes_asr_bridge import (
    run_voice_notes_asr_relay,
    voice_notes_error_json,
)
from services.features.voice_notes_usage import (
    estimate_voice_notes_asr_tokens,
    voice_notes_budget_error_payload,
)
from services.infrastructure.http.error_handler import (
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)
from services.infrastructure.monitoring.ws_metrics import _ENDPOINT_COUNTER
from services.kitty.asr.fun_asr_realtime import build_fun_asr_run_task
from services.monitoring.module_activity import VALID_MODULES
from services.redis.redis_activity_tracker import RedisActivityTracker


def test_fun_asr_run_task_semantic_punctuation_enabled() -> None:
    """Voice notes pass semantic_punctuation_enabled=True for meeting punctuation."""
    payload = build_fun_asr_run_task(
        "task-vn",
        model="fun-asr-realtime",
        language_hints=["zh"],
        semantic_punctuation_enabled=True,
    )
    assert payload["payload"]["parameters"]["semantic_punctuation_enabled"] is True
    assert payload["payload"]["parameters"]["format"] == "pcm"
    assert payload["payload"]["parameters"]["sample_rate"] == 16000


def test_fun_asr_run_task_semantic_punctuation_default_false() -> None:
    """Kitty path keeps semantic punctuation off by default."""
    payload = build_fun_asr_run_task("task-kitty", model="fun-asr-realtime")
    assert payload["payload"]["parameters"]["semantic_punctuation_enabled"] is False


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


def test_voice_notes_activity_and_metrics_wiring() -> None:
    """Module activity + WS metrics labels are registered for voice notes."""
    assert "voice_notes" in VALID_MODULES
    assert "voice_notes" in RedisActivityTracker.ACTIVITY_TYPES
    assert _ENDPOINT_COUNTER.get("voice_notes_asr") == "ws_voice_notes_connections"


@pytest.mark.asyncio
async def test_voice_notes_relay_start_append_stop() -> None:
    """Relay starts Fun-ASR, forwards PCM, finishes on stop."""
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
            "services.features.voice_notes_asr_bridge.FunAsrRealtimeClient",
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
        await run_voice_notes_asr_relay(MagicMock(), language_hints=["zh"])

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
    """Successful relay with a user settles Fun-ASR proxy tokens."""
    user = MagicMock()
    user.id = 42
    user.organization_id = 7
    settle = AsyncMock(return_value=100)

    with (
        patch(
            "services.features.voice_notes_asr_bridge.FunAsrRealtimeClient",
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
async def test_voice_notes_relay_passes_semantic_punctuation() -> None:
    """FunAsrRealtimeClient is constructed with meeting punctuation enabled."""
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
            "services.features.voice_notes_asr_bridge.FunAsrRealtimeClient",
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
        await run_voice_notes_asr_relay(MagicMock())

    assert captured.get("semantic_punctuation_enabled") is True
