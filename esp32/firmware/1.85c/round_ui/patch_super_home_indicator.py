#!/usr/bin/env python3
"""Keep Super's home indicator hidden except while swipe-home is in flight.

Stock Super already hides ``gesture_indicator`` on the launcher and in apps
until the bottom-edge gesture starts. An earlier 1.85C patch forced the bar
on; this restores the hidden binding and only keeps the round-watch width.
"""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
IMPL_HPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_super"
    / "src"
    / "private"
    / "shell_impl.hpp"
)

BIND_FORCE_VISIBLE = """    (void)hidden;
    add_binding_update(
        updates,
        SUPER_GESTURE_INDICATOR_PATH,
        "gesture_indicator_hidden",
        bool_to_binding(false)
    );
"""

BIND_STOCK = """    add_binding_update(
        updates,
        SUPER_GESTURE_INDICATOR_PATH,
        "gesture_indicator_hidden",
        bool_to_binding(hidden)
    );
"""

WIDTH_STOCK = """int32_t get_fallback_gesture_indicator_width(const gui::Environment &environment)
{
    return std::clamp<int32_t>(std::max<int32_t>(environment.width_px / 5, 1), 96, 180);
}
"""

WIDTH_WATCH = """int32_t get_fallback_gesture_indicator_width(const gui::Environment &environment)
{
    if ((environment.width_px == 360 && environment.height_px == 360) ||
        (environment.width_px == 466 && environment.height_px == 466)) {
        return environment.width_px == 466 ? 72 : 56;
    }
    return std::clamp<int32_t>(std::max<int32_t>(environment.width_px / 5, 1), 96, 180);
}
"""

WIDTH_WATCH_360 = """int32_t get_fallback_gesture_indicator_width(const gui::Environment &environment)
{
    if (environment.width_px == 360 && environment.height_px == 360) {
        return 56;
    }
    return std::clamp<int32_t>(std::max<int32_t>(environment.width_px / 5, 1), 96, 180);
}
"""


def replace_once(path: Path, old: str, new: str) -> int:
    """Replace old with new. 0 already done, 1 changed, raise if missing."""
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return 0
    if old not in text:
        raise RuntimeError(f"round home indicator cannot find block in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return 1


def restore_hidden_binding(path: Path) -> int:
    """Honor the hidden flag so the bar stays off the home screen."""
    text = path.read_text(encoding="utf-8")
    if BIND_FORCE_VISIBLE in text:
        path.write_text(text.replace(BIND_FORCE_VISIBLE, BIND_STOCK, 1), encoding="utf-8")
        return 1
    if BIND_STOCK in text:
        return 0
    raise RuntimeError(f"round home indicator cannot find hidden bind in {path}")


def main() -> int:
    """Patch Super home-indicator width; restore hide-when-idle."""
    if not IMPL_HPP.is_file():
        print(f"round home indicator: skip, missing {IMPL_HPP}")
        return 0
    changed = 0
    changed += restore_hidden_binding(IMPL_HPP)
    text = IMPL_HPP.read_text(encoding="utf-8")
    if WIDTH_WATCH_360 in text:
        IMPL_HPP.write_text(text.replace(WIDTH_WATCH_360, WIDTH_WATCH, 1), encoding="utf-8")
        changed += 1
    else:
        changed += replace_once(IMPL_HPP, WIDTH_STOCK, WIDTH_WATCH)
    print(f"round home indicator: hidden except during swipe-home (changed={changed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
