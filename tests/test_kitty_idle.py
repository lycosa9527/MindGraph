"""Kitty WS idle timeout must not fire during lecture TTS."""

from services.kitty.tts.lecture_cache import LECTURE_HOLD_UNTIL_KEY, PREFETCH_KEY
from services.kitty.ws.idle import kitty_idle_should_close, kitty_session_holds_idle


def test_lecture_flag_holds_idle() -> None:
    """In-flight narrate keeps the socket even after the quiet interval."""
    session = {"_kitty_lecture": True}
    assert kitty_session_holds_idle(session) is True
    assert (
        kitty_idle_should_close(
            session,
            last_inbound_monotonic=0.0,
            now_monotonic=400.0,
            timeout_sec=300.0,
        )
        is False
    )


def test_speaking_or_prefetch_holds_idle() -> None:
    """Synthesis and N+1 lookahead also keep the socket."""
    assert kitty_session_holds_idle({"_kitty_tts_speaking": True}) is True
    assert kitty_session_holds_idle({PREFETCH_KEY: object()}) is True


def test_hold_until_covers_client_playback() -> None:
    """After server TTS finishes, PCM duration plus slack still holds idle."""
    now = 1000.0
    session = {LECTURE_HOLD_UNTIL_KEY: now + 120.0}
    assert kitty_session_holds_idle(session, now_monotonic=now) is True
    assert kitty_session_holds_idle(session, now_monotonic=now + 119.0) is True
    assert kitty_session_holds_idle(session, now_monotonic=now + 121.0) is False
    assert (
        kitty_idle_should_close(
            session,
            last_inbound_monotonic=0.0,
            now_monotonic=now + 50.0,
            timeout_sec=300.0,
        )
        is False
    )


def test_quiet_session_idles_after_timeout() -> None:
    """No lecture hold and a stale inbound clock closes the socket."""
    session = {"_kitty_lecture": False}
    assert kitty_session_holds_idle(session) is False
    assert (
        kitty_idle_should_close(
            session,
            last_inbound_monotonic=0.0,
            now_monotonic=300.0,
            timeout_sec=300.0,
        )
        is True
    )
    assert (
        kitty_idle_should_close(
            session,
            last_inbound_monotonic=10.0,
            now_monotonic=200.0,
            timeout_sec=300.0,
        )
        is False
    )
