#!/usr/bin/env python3
"""Keep Super's iPhone-style home indicator visible on the 1.85C.

Brookesia already draws ``gesture_indicator`` on the system overlay and
handles the bottom-edge swipe-home. Stock Super hides the bar except while
the gesture is in flight. This keeps the same component on screen.
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

BIND_OLD = """    add_binding_update(
        updates,
        SUPER_GESTURE_INDICATOR_PATH,
        "gesture_indicator_hidden",
        bool_to_binding(hidden)
    );
"""

BIND_NEW = """    (void)hidden;
    add_binding_update(
        updates,
        SUPER_GESTURE_INDICATOR_PATH,
        "gesture_indicator_hidden",
        bool_to_binding(false)
    );
"""

WIDTH_OLD = """int32_t get_fallback_gesture_indicator_width(const gui::Environment &environment)
{
    return std::clamp<int32_t>(std::max<int32_t>(environment.width_px / 5, 1), 96, 180);
}
"""

WIDTH_NEW = """int32_t get_fallback_gesture_indicator_width(const gui::Environment &environment)
{
    if (environment.width_px == 360 && environment.height_px == 360) {
        return 56;
    }
    return std::clamp<int32_t>(std::max<int32_t>(environment.width_px / 5, 1), 96, 180);
}
"""


def replace_once(path: Path, old: str, new: str, already: str) -> int:
    """Replace old with new. 0 already done, 1 changed, raise if missing."""
    text = path.read_text(encoding="utf-8")
    if already in text:
        return 0
    if old not in text:
        raise RuntimeError(f"round home indicator cannot find block in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return 1


def main() -> int:
    """Patch Super to keep the home indicator visible."""
    if not IMPL_HPP.is_file():
        print(f"round home indicator: skip, missing {IMPL_HPP}")
        return 0
    changed = 0
    changed += replace_once(IMPL_HPP, BIND_OLD, BIND_NEW, "(void)hidden;")
    changed += replace_once(
        IMPL_HPP, WIDTH_OLD, WIDTH_NEW, "width_px == 360 && environment.height_px == 360"
    )
    print(f"round home indicator: Super gesture bar stays visible (changed={changed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
