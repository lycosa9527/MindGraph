"""Tests for DashScope TTS family routing and HTTP payload builders."""

from __future__ import annotations

import pytest

from services.kitty.tts.cosyvoice_realtime import (
    CosyVoiceRealtimeClient,
    resolve_kitty_tts_voice,
)
from services.kitty.tts.factory import HttpKittyTtsClient, create_kitty_tts_client
from services.kitty.tts.qwen_realtime_adapter import QwenRealtimeKittyTtsClient
from services.tts.http_payloads import (
    build_qwen_tts_http_body,
    build_speech_synthesizer_body,
    decode_audio_b64,
    extract_audio_url,
    parse_sse_json_line,
    speech_synthesizer_headers,
)
from services.tts.qwen_realtime_events import (
    build_qwen_session_finish,
    build_qwen_session_update,
    build_qwen_text_append,
    build_qwen_text_commit,
)
from services.tts.routing import (
    MODE_HTTP,
    MODE_REALTIME,
    PROTOCOL_INFERENCE_WS,
    PROTOCOL_QWEN_HTTP,
    PROTOCOL_QWEN_RT_WS,
    PROTOCOL_SPEECH_HTTP,
    default_voice_for_model,
    resolve_tts_mode,
    resolve_tts_route,
    to_http_model,
    to_realtime_model,
)
from services.tts.voices.types import FAMILY_COSYVOICE, FAMILY_QWEN_AUDIO


def test_resolve_tts_mode_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """KITTY_TTS_MODE accepts http aliases; default is realtime."""
    monkeypatch.delenv("KITTY_TTS_MODE", raising=False)
    assert resolve_tts_mode() == MODE_REALTIME
    assert resolve_tts_mode("http") == MODE_HTTP
    assert resolve_tts_mode("non-realtime") == MODE_HTTP
    monkeypatch.setenv("KITTY_TTS_MODE", "REST")
    assert resolve_tts_mode() == MODE_HTTP


def test_cosyvoice_and_qwen_audio_routes() -> None:
    """CosyVoice / Qwen-Audio share inference WS vs SpeechSynthesizer HTTP."""
    live = resolve_tts_route("cosyvoice-v3.5-flash")
    assert live.family == FAMILY_COSYVOICE
    assert live.protocol == PROTOCOL_INFERENCE_WS
    assert live.needs_designed_voice is True
    assert live.default_voice == ""
    http = resolve_tts_route("cosyvoice-v3.5-flash", mode="http")
    assert http.protocol == PROTOCOL_SPEECH_HTTP
    assert http.sample_rate == 24000
    audio = resolve_tts_route("qwen-audio-3.0-tts-flash")
    assert audio.family == FAMILY_QWEN_AUDIO
    assert audio.protocol == PROTOCOL_INFERENCE_WS
    assert audio.default_voice == "longanhuan_v3.6"
    v3 = resolve_tts_route("cosyvoice-v3-flash")
    assert default_voice_for_model(v3.model) == "longyumi_v3"


def test_qwen_tts_realtime_and_http_coercion() -> None:
    """Qwen-TTS model names map between realtime WS and multimodal HTTP."""
    assert to_http_model("qwen3-tts-flash-realtime") == "qwen3-tts-flash"
    assert to_realtime_model("qwen3-tts-flash") == "qwen3-tts-flash-realtime"
    live = resolve_tts_route("qwen3-tts-flash", mode="realtime")
    assert live.protocol == PROTOCOL_QWEN_RT_WS
    assert live.model == "qwen3-tts-flash-realtime"
    assert live.default_voice == "Cherry"
    rest = resolve_tts_route("qwen3-tts-flash-realtime", mode="http")
    assert rest.protocol == PROTOCOL_QWEN_HTTP
    assert rest.model == "qwen3-tts-flash"


def test_mode_is_orthogonal_to_model() -> None:
    """Same product model can be realtime or HTTP; mode does not change family."""
    models = (
        "cosyvoice-v3.5-flash",
        "qwen-audio-3.0-tts-flash",
        "qwen3-tts-flash",
        "qwen3-tts-flash-realtime",
    )
    for model in models:
        live = resolve_tts_route(model, mode="realtime")
        rest = resolve_tts_route(model, mode="http")
        assert live.mode == MODE_REALTIME
        assert rest.mode == MODE_HTTP
        assert live.family == rest.family
        assert live.protocol != rest.protocol


def test_http_and_qwen_realtime_payloads() -> None:
    """SpeechSynthesizer, Qwen-TTS HTTP, and Qwen-TTS WS events match Aliyun docs."""
    speech = build_speech_synthesizer_body(
        "qwen-audio-3.0-tts-flash",
        "花园。",
        "longanhuan_v3.6",
        audio_format="wav",
        sample_rate=24000,
        instruction="语速适中",
    )
    assert speech["model"] == "qwen-audio-3.0-tts-flash"
    assert speech["input"]["voice"] == "longanhuan_v3.6"
    assert speech["input"]["instruction"] == "语速适中"
    qwen = build_qwen_tts_http_body(
        "qwen3-tts-flash",
        "hello",
        "Cherry",
        language_type="Chinese",
    )
    assert qwen["input"]["language_type"] == "Chinese"
    assert speech_synthesizer_headers(stream=True) == {"X-DashScope-SSE": "enable"}
    assert not speech_synthesizer_headers(stream=False)
    session = build_qwen_session_update(voice="Cherry", mode="server_commit")
    assert session["type"] == "session.update"
    assert session["event_id"].startswith("event_")
    assert session["session"]["voice"] == "Cherry"
    appended = build_qwen_text_append("hi", event_id="event_test")
    assert appended == {
        "event_id": "event_test",
        "type": "input_text_buffer.append",
        "text": "hi",
    }
    assert build_qwen_text_commit()["type"] == "input_text_buffer.commit"
    finished = build_qwen_session_finish()
    assert finished["type"] == "session.finish"
    assert finished["event_id"].startswith("event_")
    parsed = parse_sse_json_line('data: {"output":{"audio":{"url":"https://x/a.wav"}}}')
    assert parsed is not None
    assert extract_audio_url(parsed) == "https://x/a.wav"
    assert decode_audio_b64("YQ==") == b"a"
    assert parse_sse_json_line("data: [DONE]") is None


async def _noop_audio(_b64: str, _fmt: str) -> None:
    return None


async def _noop_done() -> None:
    return None


async def _noop_error(_err: str) -> None:
    return None


def test_factory_picks_client_by_model_and_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default stays CosyVoice WS; env switches HTTP or Qwen-TTS Realtime."""
    monkeypatch.delenv("KITTY_TTS_MODE", raising=False)
    monkeypatch.delenv("KITTY_TTS_MODEL", raising=False)
    monkeypatch.delenv("KITTY_TTS_VOICE", raising=False)
    default = create_kitty_tts_client(
        on_audio=_noop_audio,
        on_done=_noop_done,
        on_error=_noop_error,
    )
    assert isinstance(default, CosyVoiceRealtimeClient)

    monkeypatch.setenv("KITTY_TTS_MODE", "http")
    monkeypatch.setenv("KITTY_TTS_MODEL", "cosyvoice-v3-flash")
    http_client = create_kitty_tts_client(
        on_audio=_noop_audio,
        on_done=_noop_done,
        on_error=_noop_error,
    )
    assert isinstance(http_client, HttpKittyTtsClient)

    monkeypatch.setenv("KITTY_TTS_MODE", "realtime")
    monkeypatch.setenv("KITTY_TTS_MODEL", "qwen3-tts-flash")
    qwen = create_kitty_tts_client(
        on_audio=_noop_audio,
        on_done=_noop_done,
        on_error=_noop_error,
    )
    assert isinstance(qwen, QwenRealtimeKittyTtsClient)

    monkeypatch.setenv("KITTY_TTS_MODE", "http")
    qwen_http = create_kitty_tts_client(
        on_audio=_noop_audio,
        on_done=_noop_done,
        on_error=_noop_error,
    )
    assert isinstance(qwen_http, HttpKittyTtsClient)


def test_unset_voice_follows_model_family(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qwen-TTS defaults to Cherry, not CosyVoice YUMI."""
    monkeypatch.delenv("KITTY_TTS_VOICE", raising=False)
    monkeypatch.setenv("KITTY_TTS_MODEL", "qwen3-tts-flash")
    assert resolve_kitty_tts_voice() == "Cherry"
    monkeypatch.setenv("KITTY_TTS_MODEL", "cosyvoice-v3-flash")
    assert resolve_kitty_tts_voice() == "longyumi_v3"


@pytest.mark.asyncio
async def test_http_client_splits_long_captions(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP lecture captions use the same ~90-char CosyVoice chunking."""
    texts: list[str] = []

    async def fake_synth(request) -> bytes:
        texts.append(request.text)
        return b"\x00\x01"

    monkeypatch.setattr("services.kitty.tts.factory.synthesize_http", fake_synth)
    route = resolve_tts_route("cosyvoice-v3-flash", mode=MODE_HTTP)
    heard: list[int] = []

    async def on_audio(_b64: str, _fmt: str) -> None:
        heard.append(1)

    client = HttpKittyTtsClient(
        route=route,
        voice="longyumi_v3",
        on_audio=on_audio,
        on_done=_noop_done,
        on_error=_noop_error,
    )
    sentence = "我们先看右上角这一支，地理区位。它主要回答昌平在哪、怎么去、地形如何。"
    await client.speak(sentence * 8)
    assert len(texts) >= 3
    assert heard == [1] * len(texts)


@pytest.mark.asyncio
async def test_http_client_raises_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty HTTP audio must fail the utterance so the lecture can emit tts_done."""

    async def fake_synth(_request) -> bytes:
        return b""

    monkeypatch.setattr("services.kitty.tts.factory.synthesize_http", fake_synth)
    route = resolve_tts_route("cosyvoice-v3-flash", mode=MODE_HTTP)
    client = HttpKittyTtsClient(
        route=route,
        voice="longyumi_v3",
        on_audio=_noop_audio,
        on_done=_noop_done,
        on_error=_noop_error,
    )
    with pytest.raises(RuntimeError, match="no audio"):
        await client.speak("右上看地理区位。")
