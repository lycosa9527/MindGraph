"""Unit tests for Fun-ASR and CosyVoice realtime protocol helpers."""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Awaitable, Callable, Optional, cast
from unittest.mock import MagicMock

import pytest
from websockets.exceptions import ConnectionClosedOK

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

PartialCb = Callable[[str, bool], Awaitable[None]]
ErrorCb = Callable[[str], Awaitable[None]]


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
async def test_stop_session_asr_bounds_hanging_finish() -> None:
    """asr_stop must bound DashScope finish so inbound cannot hang forever."""
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
        await asyncio.wait_for(bridge.stop_session_asr(vid), timeout=4.0)
        assert voice_sessions[vid].get("_fun_asr_client") is None
        await asyncio.wait_for(hung.wait(), timeout=0.5)
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_fun_asr_finish_promotes_last_partial_to_final() -> None:
    """PTT stop must emit sentence_end when DashScope never sets it."""
    emitted: list[tuple[str, bool]] = []

    async def on_partial(text: str, sentence_end: bool) -> None:
        """Collect partial/final ASR callbacks."""
        emitted.append((text, sentence_end))

    class DummyWs:
        """WebSocket stub that accepts finish-task without a live socket."""

        async def send(self, _payload: str) -> None:
            """Accept outbound ASR control frames."""
            return None

        async def close(self) -> None:
            """No-op close for finish promotion test."""
            return None

    client = FunAsrRealtimeClient(on_partial=on_partial)
    setattr(client, "_last_text", "添加一个广东民族文化的分支，并补完")
    setattr(client, "_emitted_sentence_end", False)
    setattr(client, "_task_id", "task-promote")
    setattr(client, "_closed", False)
    setattr(client, "_ws", DummyWs())
    getattr(client, "_task_finished").set()
    await client.finish()
    assert emitted == [("添加一个广东民族文化的分支，并补完", True)]
    assert getattr(client, "_closed") is True


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


@pytest.mark.asyncio
async def test_start_session_asr_echoes_utterance_id(monkeypatch) -> None:
    """asr_started / partial / final / error must carry the hold utterance_id."""
    vid = "voice-asr-utt-echo"
    sent: list[dict[str, object]] = []

    class FakeWs:
        """Collect outbound Kitty websocket payloads."""

        async def send_json(self, message: dict[str, object]) -> None:
            """Capture JSON frames."""
            sent.append(dict(message))

    class ImmediateAsr(FunAsrRealtimeClient):
        """ASR stub that exposes the session partial callback."""

        def __init__(
            self,
            *,
            on_partial: PartialCb,
            on_error: Optional[ErrorCb] = None,
            language_hints: Optional[list[str]] = None,
        ) -> None:
            """Capture callbacks then no-op start."""
            super().__init__(
                on_partial=on_partial,
                on_error=on_error,
                language_hints=language_hints,
            )
            self.partial_cb = on_partial

        async def start(self) -> None:
            """Mark started without DashScope."""
            return None

        async def finish(self) -> None:
            """No-op finish."""
            return None

    async def _noop_interrupt(_sid: str) -> None:
        """Skip TTS interrupt in unit test."""
        return None

    async def _noop_fanout(*_args: object, **_kwargs: object) -> None:
        """Skip voice-phase fanout in unit test."""
        return None

    monkeypatch.setattr(bridge, "FunAsrRealtimeClient", ImmediateAsr)
    monkeypatch.setattr(bridge, "interrupt_kitty_tts", _noop_interrupt)
    monkeypatch.setattr(bridge, "fanout_voice_phase_from_session", _noop_fanout)

    voice_sessions[vid] = {"_kitty_client_lane": "mobile"}
    try:
        fake_ws = FakeWs()
        await bridge.start_session_asr(
            cast(Any, fake_ws),
            vid,
            language_hints=["zh"],
            utterance_id="utt-hold-9",
        )
        assert any(
            frame.get("type") == "asr_started" and frame.get("utterance_id") == "utt-hold-9"
            for frame in sent
        )
        client = voice_sessions[vid]["_fun_asr_client"]
        assert isinstance(client, ImmediateAsr)
        await client.partial_cb("你好", True)
        assert any(
            frame.get("type") == "asr_final"
            and frame.get("text") == "你好"
            and frame.get("utterance_id") == "utt-hold-9"
            for frame in sent
        )
        assert await bridge.stop_session_asr(vid, utterance_id="utt-hold-9") == "你好"
        assert await bridge.stop_session_asr(vid, utterance_id="utt-other") == ""
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_feed_session_asr_ignores_stale_utterance() -> None:
    """Audio frames from a prior hold must not reach the active Fun-ASR client."""
    vid = "voice-asr-utt-stale"
    sent_pcm: list[bytes] = []

    class TrackingAsr(FunAsrRealtimeClient):
        """Record PCM frames."""

        def __init__(self) -> None:
            """Initialize with a no-op partial callback."""
            super().__init__(on_partial=lambda _t, _e: asyncio.sleep(0))

        async def send_pcm(self, pcm: bytes) -> None:
            """Capture PCM."""
            sent_pcm.append(pcm)

    voice_sessions[vid] = {
        "_fun_asr_client": TrackingAsr(),
        "_fun_asr_utterance_id": "utt-current",
        "_fun_asr_audio_frames": 0,
        "_fun_asr_audio_bytes": 0,
        "_fun_asr_first_audio_logged": False,
        "_fun_asr_dropped_before_start": 0,
    }
    try:
        payload = base64.b64encode(b"\x00\x01").decode("ascii")
        await bridge.feed_session_asr_audio(vid, payload, utterance_id="utt-stale")
        assert not sent_pcm
        await bridge.feed_session_asr_audio(vid, payload, utterance_id="utt-current")
        assert sent_pcm == [b"\x00\x01"]
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_fun_asr_send_pcm_reports_provider_disconnect() -> None:
    """Closed provider socket while sending audio must invoke on_error once."""
    errors: list[str] = []

    async def on_error(message: str) -> None:
        """Collect provider disconnect errors."""
        errors.append(message)

    class ClosedWs:
        """WebSocket stub that rejects sends as already closed."""

        async def send(self, _payload: bytes) -> None:
            """Raise connection closed."""
            raise ConnectionClosedOK(None, None)

        async def close(self) -> None:
            """No-op close."""
            return None

    client = FunAsrRealtimeClient(
        on_partial=lambda _t, _e: asyncio.sleep(0),
        on_error=on_error,
    )
    setattr(client, "_ws", ClosedWs())
    setattr(client, "_closed", False)
    await client.send_pcm(b"\x00\x01\x02\x03")
    await client.send_pcm(b"\x00\x01\x02\x03")
    assert len(errors) == 1
    assert "closed" in errors[0].lower() or "sending" in errors[0].lower()
