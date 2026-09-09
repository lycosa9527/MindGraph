#!/usr/bin/env python3
"""Stack Super keyboard motion and open passwords on 123."""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
SUPER_SRC = FIRMWARE_ROOT / "managed_components" / "espressif__brookesia_system_super" / "src"
KEYBOARD_CPP = SUPER_SRC / "shell_keyboard.cpp"
SHELL_IMPL = SUPER_SRC / "private" / "shell_impl.hpp"

SHOW_MARKER = "stacked = screen_w == 360 && screen_h == 360"
PASSWORD_MARKER = "options.password) {"

OLD_SHOW = """    const auto final_input_y = input_frame->y;
    const auto final_keyboard_y = keyboard_frame->y;
    const auto hidden_input_y = -std::max<int32_t>(input_frame->height, 1) - 2;
    const auto hidden_keyboard_y = owner_.get_environment().height_px + std::max<int32_t>(keyboard_frame->height, 1);
"""

NEW_SHOW = """    const auto final_input_y = input_frame->y;
    const auto final_keyboard_y = keyboard_frame->y;
    const auto environment = owner_.get_environment();
    const auto screen_w = environment.width_px;
    const auto screen_h = environment.height_px;
    const auto stacked = screen_w == 360 && screen_h == 360;
    const auto hidden_input_y = stacked ?
                                final_input_y + screen_h :
                                -std::max<int32_t>(input_frame->height, 1) - 2;
    const auto hidden_keyboard_y = stacked ?
                                   final_keyboard_y + screen_h :
                                   screen_h + std::max<int32_t>(keyboard_frame->height, 1);
"""

OLD_HIDE = """    auto completed_handler_ptr = std::make_shared<std::function<void()>>(std::move(completed_handler));
    const auto hidden_input_y = -std::max<int32_t>(input_frame->height, 1) - 2;
    const auto hidden_keyboard_y = owner_.get_environment().height_px + std::max<int32_t>(keyboard_frame->height, 1);
"""

NEW_HIDE = """    auto completed_handler_ptr = std::make_shared<std::function<void()>>(std::move(completed_handler));
    const auto environment = owner_.get_environment();
    const auto screen_w = environment.width_px;
    const auto screen_h = environment.height_px;
    const auto stacked = screen_w == 360 && screen_h == 360;
    const auto hidden_input_y = stacked ?
                                input_frame->y + screen_h :
                                -std::max<int32_t>(input_frame->height, 1) - 2;
    const auto hidden_keyboard_y = stacked ?
                                   keyboard_frame->y + screen_h :
                                   screen_h + std::max<int32_t>(keyboard_frame->height, 1);
"""

OLD_NORMALIZE = """    if (options.allowed_modes.empty()) {
        options.allowed_modes = default_keyboard_modes();
    }
"""

NEW_NORMALIZE = """    if (options.allowed_modes.empty()) {
        options.allowed_modes = default_keyboard_modes();
    }
    if (options.password) {
        options.mode = "number";
        if (std::find(options.allowed_modes.begin(), options.allowed_modes.end(), "number") ==
                options.allowed_modes.end()) {
            options.allowed_modes.push_back("number");
        }
    }
"""


def _replace_once(text: str, old: str, new: str, path: Path, label: str) -> str:
    """Replace one exact block or raise."""
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"round keyboard patch cannot find {label}: {path}")
    return text.replace(old, new, 1)


def patch_keyboard_cpp(path: Path) -> bool:
    """Slide the composer and pad as one stack. True when the file changed."""
    text = path.read_text(encoding="utf-8")
    if SHOW_MARKER in text and OLD_SHOW not in text and OLD_HIDE not in text:
        return False
    updated = _replace_once(text, OLD_SHOW, NEW_SHOW, path, "show animation")
    updated = _replace_once(updated, OLD_HIDE, NEW_HIDE, path, "hide animation")
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def patch_keyboard_options(path: Path) -> bool:
    """Open password requests on the number pad. True when the file changed."""
    text = path.read_text(encoding="utf-8")
    if PASSWORD_MARKER in text and OLD_NORMALIZE not in text:
        return False
    updated = _replace_once(text, OLD_NORMALIZE, NEW_NORMALIZE, path, "password mode")
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def apply_keyboard_patches() -> tuple[bool, bool]:
    """Patch Super keyboard sources when they are present."""
    motion = False
    password = False
    if KEYBOARD_CPP.is_file():
        motion = patch_keyboard_cpp(KEYBOARD_CPP)
    if SHELL_IMPL.is_file():
        password = patch_keyboard_options(SHELL_IMPL)
    return motion, password


def main() -> int:
    """CLI entry used by CMake before the Super sources compile."""
    if not KEYBOARD_CPP.is_file() and not SHELL_IMPL.is_file():
        print("round keyboard: skip, Super sources missing")
        return 0
    motion, password = apply_keyboard_patches()
    print(f"round keyboard: motion={motion} password={password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
