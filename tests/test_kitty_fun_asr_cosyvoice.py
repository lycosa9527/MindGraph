"""Unit tests for Fun-ASR and CosyVoice realtime protocol helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from services.kitty.asr.fun_asr_realtime import (
    FunAsrRealtimeClient,
    build_fun_asr_finish_task,
    build_fun_asr_run_task,
    _extract_asr_text,
)
from services.kitty.audio import session_bridge as bridge
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.tts.cosyvoice_realtime import (
    build_cosyvoice_continue_task,
    build_cosyvoice_finish_task,
    build_cosyvoice_run_task,
    resolve_kitty_tts_model_and_voice,
)


def test_fun_asr_run_task_payload() -> None:
    """run-task uses fun-asr-realtime defaults (pcm / 16k / VAD punctuation off)."""
    payload = build_fun_asr_run_task(
        "task-1",
        model="fun-asr-realtime",
        language_hints=["zh"],
    )
    assert payload["header"]["action"] == "run-task"
    assert payload["header"]["task_id"] == "task-1"
    assert payload["header"]["streaming"] == "duplex"
    assert payload["payload"]["model"] == "fun-asr-realtime"
    assert payload["payload"]["task"] == "asr"
    assert payload["payload"]["parameters"]["format"] == "pcm"
    assert payload["payload"]["parameters"]["sample_rate"] == 16000
    assert payload["payload"]["parameters"]["semantic_punctuation_enabled"] is False
    assert payload["payload"]["parameters"]["language_hints"] == ["zh"]


def test_fun_asr_finish_task_payload() -> None:
    """finish-task correlates by task_id."""
    payload = build_fun_asr_finish_task("task-1")
    assert payload["header"]["action"] == "finish-task"
    assert payload["header"]["task_id"] == "task-1"


def test_extract_asr_text_sentence_end() -> None:
    """result-generated payload maps to text + sentence_end."""
    text, ended = _extract_asr_text({"output": {"sentence": {"text": "你好", "sentence_end": True}}})
    assert text == "你好"
    assert ended is True


def test_cosyvoice_run_continue_finish_flow() -> None:
    """CosyVoice client events: run-task → continue-task → finish-task."""
    task_id = "tts-task-1"
    run_msg = build_cosyvoice_run_task(
        task_id,
        model="cosyvoice-v3.5-flash",
        voice="clone-voice-id",
    )
    assert run_msg["header"]["action"] == "run-task"
    assert run_msg["payload"]["task"] == "tts"
    assert run_msg["payload"]["function"] == "SpeechSynthesizer"
    assert run_msg["payload"]["parameters"]["voice"] == "clone-voice-id"
    assert run_msg["payload"]["parameters"]["format"] == "pcm"
    assert run_msg["payload"]["parameters"]["sample_rate"] == 22050

    cont = build_cosyvoice_continue_task(task_id, "已添加节点")
    assert cont["header"]["action"] == "continue-task"
    assert cont["payload"]["input"]["text"] == "已添加节点"

    fin = build_cosyvoice_finish_task(task_id)
    assert fin["header"]["action"] == "finish-task"
    assert fin["header"]["task_id"] == task_id


def test_tts_voice_fallback_without_env(monkeypatch) -> None:
    """Unset KITTY_TTS_VOICE uses YUMI longyumi_v3 with v3-flash for v3.5 models."""
    monkeypatch.delenv("KITTY_TTS_VOICE", raising=False)
    monkeypatch.setenv("KITTY_TTS_MODEL", "cosyvoice-v3.5-flash")
    model, voice = resolve_kitty_tts_model_and_voice()
    assert voice == "longyumi_v3"
    assert model == "cosyvoice-v3-flash"


@pytest.mark.asyncio
async def test_speak_kitty_serializes_utterances(monkeypatch) -> None:
    """Second speak waits for the first — no overlapping CosyVoice teardown."""
    monkeypatch.setenv("KITTY_TTS_ENABLED", "true")
    vid = "voice-tts-serial"
    voice_sessions[vid] = {"_kitty_tts_enabled": True}
    order: list[str] = []
    gate = asyncio.Event()

    class FakeClient:
        """Stub CosyVoice client that gates the first utterance."""

        async def speak(self, text: str) -> None:
            """Record start/end around an optional gate wait."""
            order.append(f"start:{text}")
            if text == "first":
                await gate.wait()
            order.append(f"end:{text}")

        async def interrupt(self) -> None:
            """No-op interrupt for serialization test."""
            return None

        async def close(self) -> None:
            """No-op close for serialization test."""
            return None

    async def fake_get_or_create(websocket, voice_session_id, session):
        """Install a single FakeClient on the session."""
        del websocket, voice_session_id
        existing = session.get("_cosyvoice_client")
        if existing is not None:
            return existing
        client = FakeClient()
        session["_cosyvoice_client"] = client
        return client

    monkeypatch.setattr(bridge, "_get_or_create_cosyvoice_client", fake_get_or_create)
    monkeypatch.setattr(bridge, "resolve_kitty_tts_enabled", lambda: True)

    ws = MagicMock()
    try:
        await bridge.speak_kitty_final_reply(ws, vid, "first")
        await bridge.speak_kitty_final_reply(ws, vid, "second")
        await asyncio.sleep(0.05)
        assert order == ["start:first"]
        gate.set()
        for _ in range(50):
            if order == ["start:first", "end:first", "start:second", "end:second"]:
                break
            await asyncio.sleep(0.02)
        assert order == ["start:first", "end:first", "start:second", "end:second"]
    finally:
        await bridge.teardown_session_audio(vid)
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_interrupt_drains_pending_tts(monkeypatch) -> None:
    """Barge-in bumps generation and drops queued utterances."""
    monkeypatch.setenv("KITTY_TTS_ENABLED", "true")
    vid = "voice-tts-interrupt"
    voice_sessions[vid] = {"_kitty_tts_enabled": True}
    spoken: list[str] = []
    hold = asyncio.Event()

    class FakeClient:
        """Stub CosyVoice client that holds speak until interrupt."""

        async def speak(self, text: str) -> None:
            """Append spoken text then wait on the hold event."""
            spoken.append(text)
            await hold.wait()

        async def interrupt(self) -> None:
            """Release the hold so speak can finish."""
            hold.set()

        async def close(self) -> None:
            """No-op close for interrupt test."""
            return None

    async def fake_get_or_create(websocket, voice_session_id, session):
        """Install a holding FakeClient on the session."""
        del websocket, voice_session_id
        client = FakeClient()
        session["_cosyvoice_client"] = client
        return client

    monkeypatch.setattr(bridge, "_get_or_create_cosyvoice_client", fake_get_or_create)
    monkeypatch.setattr(bridge, "resolve_kitty_tts_enabled", lambda: True)

    ws = MagicMock()
    try:
        await bridge.speak_kitty_final_reply(ws, vid, "keep")
        await asyncio.sleep(0.05)
        await bridge.speak_kitty_final_reply(ws, vid, "drop-me")
        await bridge.interrupt_kitty_tts(vid)
        hold.set()
        await asyncio.sleep(0.05)
        assert spoken == ["keep"]
        assert "drop-me" not in spoken
    finally:
        await bridge.teardown_session_audio(vid)
        voice_sessions.pop(vid, None)


def test_tts_voice_default_yumi(monkeypatch) -> None:
    """Default voice parameter is longyumi_v3 (YUMI)."""
    monkeypatch.delenv("KITTY_TTS_VOICE", raising=False)
    monkeypatch.setenv("KITTY_TTS_MODEL", "cosyvoice-v3-flash")
    model, voice = resolve_kitty_tts_model_and_voice()
    assert model == "cosyvoice-v3-flash"
    assert voice == "longyumi_v3"


@pytest.mark.asyncio
async def test_stop_session_asr_does_not_await_hanging_finish() -> None:
    """asr_stop must return immediately so context_update is not blocked."""
    vid = "voice-asr-stop-noblock"
    hung = asyncio.Event()

    class HangingAsrClient(FunAsrRealtimeClient):
        """ASR client whose finish() hangs until the test observes it."""

        def __init__(self) -> None:
            """Initialize with a no-op partial callback."""
            super().__init__(on_partial=lambda _t, _e: asyncio.sleep(0))

        async def finish(self) -> None:
            """Signal hang start then sleep longer than the stop timeout."""
            hung.set()
            await asyncio.sleep(30)

    voice_sessions[vid] = {"_fun_asr_client": HangingAsrClient()}
    try:
        await asyncio.wait_for(bridge.stop_session_asr(vid), timeout=0.5)
        assert voice_sessions[vid].get("_fun_asr_client") is None
        await asyncio.wait_for(hung.wait(), timeout=0.5)
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_fun_asr_close_times_out_hanging_ws() -> None:
    """DashScope close handshake must not block beyond the teardown budget."""

    class HangingWs:
        """WebSocket stub whose close() hangs past the teardown budget."""

        async def close(self) -> None:
            """Sleep longer than Fun-ASR close timeout."""
            await asyncio.sleep(30)

    client = FunAsrRealtimeClient(on_partial=lambda _t, _e: asyncio.sleep(0))
    setattr(client, "_ws", HangingWs())
    setattr(client, "_closed", False)
    setattr(client, "_reader_task", None)
    await asyncio.wait_for(client.close(), timeout=2.0)
    assert getattr(client, "_closed") is True
    assert getattr(client, "_ws") is None
