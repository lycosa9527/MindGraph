"""思维讲堂 TTS backend timing lines (first audio, synthesize, prefetch)."""

from __future__ import annotations

import base64
import logging

import pytest

from services.kitty.tts.lecture_cache import (
    format_tts_metric_detail,
    lecture_tts_elapsed,
    log_lecture_synthesize_done,
    log_lecture_tts,
    mark_lecture_tts_start,
    pcm_duration_from_chunks,
    pcm_duration_sec,
    record_live_lecture_audio,
    tts_log_level,
)


def test_pcm_duration_sec_from_16bit_mono() -> None:
    """22050 Hz 16-bit mono: 44100 bytes is one second."""
    assert pcm_duration_sec(44100) == 1.0
    assert pcm_duration_sec(0) == 0.0


def test_pcm_duration_from_chunks_decodes_base64() -> None:
    """Prefetch / cache chunks report playable audio length."""
    chunk = base64.b64encode(b"\x00" * 22050).decode("ascii")
    assert pcm_duration_from_chunks([(chunk, "pcm")]) == pytest.approx(0.5)


def test_pcm_duration_from_chunks_uses_sample_rate() -> None:
    """Qwen-TTS PCM is 24000 Hz; duration must not assume CosyVoice 22050."""
    chunk = base64.b64encode(b"\x00" * 48000).decode("ascii")
    assert pcm_duration_from_chunks([(chunk, "pcm")], sample_rate=24000) == pytest.approx(1.0)


def test_format_tts_metric_detail_order() -> None:
    """Live/cache lines share one field order for grepping."""
    detail = format_tts_metric_detail(
        source="live",
        chars=101,
        chunks=137,
        audio_sec=22.041,
    )
    assert detail == "source=live chars=101 chunks=137 audio=22.04s"


def test_log_lecture_tts_includes_elapsed(caplog: pytest.LogCaptureFixture) -> None:
    """TTS INFO lines carry elapsed= like auto-complete completed-in logs."""
    with caplog.at_level("INFO", logger="services.kitty.tts.lecture_cache"):
        log_lecture_tts(
            "first_audio",
            voice_session_id="voice-sess-1",
            step_id="overview-0",
            elapsed=0.82,
            detail="source=live chars=101",
        )
    assert any(
        "[MindClassroom] TTS first_audio" in rec.message
        and "elapsed=0.82s" in rec.message
        and "source=live" in rec.message
        for rec in caplog.records
    )


def test_record_live_lecture_audio_logs_first_chunk_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """First PCM chunk logs latency; later chunks only accumulate bytes."""
    session: dict = {"_kitty_lecture_step_id": "s1"}
    mark_lecture_tts_start(session, chars=40)
    chunk = base64.b64encode(b"\x00" * 100).decode("ascii")
    with caplog.at_level("INFO", logger="services.kitty.tts.lecture_cache"):
        record_live_lecture_audio(session, chunk, voice_session_id="sid-live-1")
        record_live_lecture_audio(session, chunk, voice_session_id="sid-live-1")
    first_audio = [rec for rec in caplog.records if "TTS first_audio" in rec.message]
    assert len(first_audio) == 1
    assert "elapsed=" in first_audio[0].message
    assert "source=live" in first_audio[0].message
    assert session["_kitty_lecture_pcm_chunks"] == 2


def test_log_lecture_synthesize_done_includes_audio_length(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """synthesize_done reports wall time and decoded audio duration."""
    session: dict = {}
    mark_lecture_tts_start(session, chars=101)
    session["_kitty_lecture_pcm_bytes"] = 44100
    session["_kitty_lecture_pcm_chunks"] = 10
    with caplog.at_level("INFO", logger="services.kitty.tts.lecture_cache"):
        log_lecture_synthesize_done(
            session,
            voice_session_id="sid-done-1",
            step_id="s1",
            chars=101,
        )
    line = next(rec.message for rec in caplog.records if "synthesize_done" in rec.message)
    assert "elapsed=" in line
    assert "audio=1.00s" in line
    assert "chars=101" in line
    assert "chunks=10" in line
    assert lecture_tts_elapsed(session) is not None


def test_tts_metric_events_are_info_start_events_are_debug() -> None:
    """Default uvicorn INFO keeps latency/duration; start/skip stay debug."""
    assert tts_log_level("first_audio") == logging.INFO
    assert tts_log_level("synthesize_done") == logging.INFO
    assert tts_log_level("prefetch_ready") == logging.INFO
    assert tts_log_level("cache_play_done") == logging.INFO
    assert tts_log_level("narrate") == logging.DEBUG
    assert tts_log_level("synthesize") == logging.DEBUG
    assert tts_log_level("prefetch_start") == logging.DEBUG
    assert tts_log_level("prefetch_request") == logging.DEBUG
    assert tts_log_level("prefetch_skip") == logging.DEBUG
    assert tts_log_level("cache_hit") == logging.DEBUG
    assert tts_log_level("narrate_skip") == logging.DEBUG
    assert tts_log_level("prefetch_miss_live") == logging.DEBUG
    assert tts_log_level("cache_play_aborted") == logging.DEBUG


def test_log_lecture_tts_start_is_debug(caplog: pytest.LogCaptureFixture) -> None:
    """narrate / synthesize must not appear at INFO."""
    with caplog.at_level("INFO", logger="services.kitty.tts.lecture_cache"):
        log_lecture_tts("narrate", voice_session_id="sid-debug-1", step_id="s1", detail="chars=10")
        log_lecture_tts("synthesize", voice_session_id="sid-debug-1", step_id="s1", detail="chars=10")
    assert not caplog.records
    with caplog.at_level("DEBUG", logger="services.kitty.tts.lecture_cache"):
        log_lecture_tts("prefetch_start", voice_session_id="sid-debug-1", step_id="s2", detail="chars=12")
    assert any("TTS prefetch_start" in rec.message for rec in caplog.records)


def test_log_lecture_tts_logger_name() -> None:
    """Uvicorn shows services.kitty.tts.lecture_cache INFO by default."""
    assert logging.getLogger("services.kitty.tts.lecture_cache").name.endswith("lecture_cache")
