#!/usr/bin/env python3
"""Block Super swipe-home while Voice Notes is still recording.

The recorder exports ``mindgraph_home_gesture_allowed``. Super checks it
before arming the bottom-edge exit so a live take cannot be dismissed.
"""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
SHELL_DISPLAY = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_super"
    / "src"
    / "shell_display.cpp"
)

WEAK_OLD = """#include "private/shell_impl.hpp"

namespace esp_brookesia::system::super {
"""

WEAK_NEW = """#include "private/shell_impl.hpp"

extern "C" __attribute__((weak)) bool mindgraph_home_gesture_allowed(void)
{
    return true;
}

namespace esp_brookesia::system::super {
"""

ARM_OLD = """    if (gesture_exit_armed_ || gesture_exit_hold_timer_id_ != core::INVALID_TIMER_ID) {
        return;
    }
    gesture_exit_armed_ = true;
"""

ARM_NEW = """    if (gesture_exit_armed_ || gesture_exit_hold_timer_id_ != core::INVALID_TIMER_ID) {
        return;
    }
    if (!mindgraph_home_gesture_allowed()) {
        animate_gesture_indicator_rebound();
        gesture_tracking_ = false;
        (void)refresh_system_ui_state_bindings();
        return;
    }
    gesture_exit_armed_ = true;
"""

EXIT_OLD = """void ShellApp::trigger_gesture_exit()
{
    if (context_ == nullptr || gesture_exit_triggered_) {
        return;
    }
    gesture_exit_triggered_ = true;
"""

EXIT_NEW = """void ShellApp::trigger_gesture_exit()
{
    if (context_ == nullptr || gesture_exit_triggered_) {
        return;
    }
    if (!mindgraph_home_gesture_allowed()) {
        animate_gesture_indicator_rebound();
        return;
    }
    gesture_exit_triggered_ = true;
"""


def replace_once(path: Path, old: str, new: str, already: str) -> int:
    """Replace old with new. 0 already done, 1 changed, raise if missing."""
    text = path.read_text(encoding="utf-8")
    if already in text and new in text:
        return 0
    if old not in text:
        raise RuntimeError(f"home gate cannot find block in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return 1


def main() -> int:
    """Patch Super swipe-home to honor the recorder gate."""
    if not SHELL_DISPLAY.is_file():
        print(f"home gate: skip, missing {SHELL_DISPLAY}")
        return 0
    changed = 0
    changed += replace_once(
        SHELL_DISPLAY, WEAK_OLD, WEAK_NEW, "mindgraph_home_gesture_allowed"
    )
    changed += replace_once(
        SHELL_DISPLAY, ARM_OLD, ARM_NEW, "animate_gesture_indicator_rebound();\n        gesture_tracking_ = false;"
    )
    changed += replace_once(
        SHELL_DISPLAY, EXIT_OLD, EXIT_NEW, "mindgraph_home_gesture_allowed()) {\n        animate_gesture_indicator_rebound();"
    )
    print(f"home gate: Super swipe-home honors recorder (changed={changed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
