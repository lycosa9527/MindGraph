#!/usr/bin/env python3
"""Park the Super status bar in the 12 o'clock pocket on 360x360.

Super animates placement.y to SUPER_STATUS_BAR_EXPANDED_Y (0). On a round
face that slams the capsule into the pole and clips both ends. JSON y=34
cannot win once the animation runs.
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
LAUNCH_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_super"
    / "src"
    / "shell_launch.cpp"
)
DIALOG_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_super"
    / "src"
    / "shell_message_dialog.cpp"
)

HELPER_OLD = """int32_t get_collapsed_status_bar_y(core::AppContext &context)
{
    auto frame = context.gui().get_view_frame(SUPER_STATUS_BAR_PATH);
    if (frame && frame->height > 0) {
        return -std::max(std::abs(SUPER_STATUS_BAR_COLLAPSED_Y), frame->height * 2);
    }
    return SUPER_STATUS_BAR_COLLAPSED_Y;
}
"""

HELPER_NEW = """int32_t get_collapsed_status_bar_y(core::AppContext &context)
{
    auto frame = context.gui().get_view_frame(SUPER_STATUS_BAR_PATH);
    if (frame && frame->height > 0) {
        return -std::max(std::abs(SUPER_STATUS_BAR_COLLAPSED_Y), frame->height * 2);
    }
    return SUPER_STATUS_BAR_COLLAPSED_Y;
}

int32_t get_expanded_status_bar_y(const gui::Environment &environment)
{
    const auto density = std::max(environment.density, 0.001F);
    const auto width_dp = static_cast<int32_t>(
                              std::max(1.0F, static_cast<float>(environment.width_px) / density)
                          );
    const auto height_dp = static_cast<int32_t>(
                               std::max(1.0F, static_cast<float>(environment.height_px) / density)
                           );
    if (width_dp == 360 && height_dp == 360) {
        return 30;
    }
    return SUPER_STATUS_BAR_EXPANDED_Y;
}
"""

LAUNCH_OLD = """    const auto status_bar_target_y = system_ui_expanded_ ?
                                     SUPER_STATUS_BAR_EXPANDED_Y :
                                     get_collapsed_status_bar_y(*context_);
"""

LAUNCH_NEW = """    const auto status_bar_target_y = system_ui_expanded_ ?
                                     get_expanded_status_bar_y(owner_.get_environment()) :
                                     get_collapsed_status_bar_y(*context_);
"""

DIALOG_OLD = """    const auto status_bar_target_y = expanded ?
                                     SUPER_STATUS_BAR_EXPANDED_Y :
                                     get_collapsed_status_bar_y(*context_);
"""

DIALOG_NEW = """    const auto status_bar_target_y = expanded ?
                                     get_expanded_status_bar_y(owner_.get_environment()) :
                                     get_collapsed_status_bar_y(*context_);
"""


def replace_once(path: Path, old: str, new: str, already: str) -> int:
    """Replace old with new. 0 already done, 1 changed, raise if missing."""
    text = path.read_text(encoding="utf-8")
    if already in text:
        return 0
    if old not in text:
        raise RuntimeError(f"round status patch cannot find block in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return 1


def main() -> int:
    """Patch Super status-bar Y for the 1.85C."""
    if not IMPL_HPP.is_file():
        print(f"round status: skip, missing {IMPL_HPP}")
        return 0
    changed = 0
    changed += replace_once(
        IMPL_HPP, HELPER_OLD, HELPER_NEW, "get_expanded_status_bar_y"
    )
    if LAUNCH_CPP.is_file():
        changed += replace_once(
            LAUNCH_CPP, LAUNCH_OLD, LAUNCH_NEW, "get_expanded_status_bar_y(owner_"
        )
    if DIALOG_CPP.is_file():
        changed += replace_once(
            DIALOG_CPP, DIALOG_OLD, DIALOG_NEW, "get_expanded_status_bar_y(owner_"
        )
    print(f"round status: patched Super status bar Y (changed={changed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
