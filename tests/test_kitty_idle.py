"""Kitty WS idle timeout must not fire during lecture TTS."""

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
