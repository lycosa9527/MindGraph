#!/usr/bin/env python3
"""Start Super AudioPlayback without the V2 AFE processor.

Settings volume/mute talk to AudioPlayback. Stock on_start() refuses to
run unless PlaybackIface exists, and that interface is only registered
when the HAL audio processor (AFE / WakeNet / barge-in) is on.

V1 is PCM5101 + MEMS: no ES8311, no ES7210, no AEC. Processor stays
off. CodecPlayer is still there and already applies software volume on
the dummy DAC, so AudioPlayback can start in control-only mode.
"""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
PLAYBACK_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_service_audio"
    / "src"
    / "audio_playback.cpp"
)

START_OLD = """    auto playback_handle = hal::acquire_interface<hal::audio::PlaybackIface>(
                               hal::audio::PlaybackIface::get_default_instance_name()
                           );
    auto playback_iface = playback_handle.get();
    BROOKESIA_CHECK_NULL_RETURN(playback_iface, false, "Failed to get audio playback interface");
    BROOKESIA_CHECK_FALSE_RETURN(
    playback_iface->open([this](AudioPlayState state) {
        on_playback_event(state);
    }),
    false, "Failed to open audio playback"
    );

    play_state_ = AudioPlayState::Idle;
    pause_requested_ = false;
    clear_pending_interrupt_playback();
    playback_iface_ = std::move(playback_handle);
"""

START_NEW = """    auto playback_handle = hal::acquire_interface<hal::audio::PlaybackIface>(
                               hal::audio::PlaybackIface::get_default_instance_name()
                           );
    auto playback_iface = playback_handle.get();
    if (playback_iface == nullptr) {
        BROOKESIA_LOGW(
            "Audio playback interface is not available; start volume and mute control only"
        );
    } else {
        BROOKESIA_CHECK_FALSE_RETURN(
        playback_iface->open([this](AudioPlayState state) {
            on_playback_event(state);
        }),
        false, "Failed to open audio playback"
        );
        playback_iface_ = std::move(playback_handle);
    }

    play_state_ = AudioPlayState::Idle;
    pause_requested_ = false;
    clear_pending_interrupt_playback();
"""

ALREADY = "start volume and mute control only"


def replace_once(path: Path, old: str, new: str, already: str) -> int:
    """Replace old with new. 0 already done, 1 changed, raise if missing."""
    text = path.read_text(encoding="utf-8")
    if already in text:
        return 0
    if old not in text:
        raise RuntimeError(f"round audio volume cannot find block in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return 1


def main() -> int:
    """Allow AudioPlayback to start for Settings volume on V1."""
    if not PLAYBACK_CPP.is_file():
        print(f"round audio volume: skip, missing {PLAYBACK_CPP}")
        return 0
    changed = replace_once(PLAYBACK_CPP, START_OLD, START_NEW, ALREADY)
    print(f"round audio volume: AudioPlayback control-only start (changed={changed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
