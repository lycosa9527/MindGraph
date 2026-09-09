#!/usr/bin/env python3
"""Pin Super's hardcoded launcher grid to 360x360 watch tiles."""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_CPP = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_system_super"
    / "src"
    / "shell_app_launcher.cpp"
)
MARKER = "LauncherMetrics launcher_metrics_for"

METRICS_BLOCK = """
struct LauncherMetrics {
    int32_t item_width;
    int32_t item_height;
    int32_t item_gap;
};

LauncherMetrics launcher_metrics_for(int32_t width_dp, int32_t height_dp)
{
    if (width_dp == 360 && height_dp == 360) {
        return {80, 80, 10};
    }
    return {LAUNCHER_ITEM_WIDTH, LAUNCHER_ITEM_HEIGHT, LAUNCHER_ITEM_GAP};
}

"""

OLD_ENV = """    const auto environment = owner_.get_environment();
    const auto density = std::max(environment.density, 0.001F);
    const auto fallback_width = static_cast<int32_t>(
                                    std::max(1.0F, static_cast<float>(environment.width_px) / density)
                                );
    const auto content_frame = context.gui().get_view_frame(SUPER_LAUNCHER_CONTENT_PATH);
    const auto available_width = content_frame.has_value() ?
                                 std::max<int32_t>(content_frame->width, LAUNCHER_ITEM_WIDTH) :
                                 std::max<int32_t>(fallback_width, LAUNCHER_ITEM_WIDTH);
    const auto launcher_columns = std::max<int32_t>(
                                      1,
                                      (available_width + LAUNCHER_ITEM_GAP) / (LAUNCHER_ITEM_WIDTH + LAUNCHER_ITEM_GAP)
                                  );
    const auto launcher_grid_width =
        launcher_columns * LAUNCHER_ITEM_WIDTH + (launcher_columns - 1) * LAUNCHER_ITEM_GAP;
    const auto launcher_grid_x = std::max<int32_t>(0, (available_width - launcher_grid_width) / 2);
"""

NEW_ENV = """    const auto environment = owner_.get_environment();
    const auto density = std::max(environment.density, 0.001F);
    const auto width_dp = static_cast<int32_t>(
                              std::max(1.0F, static_cast<float>(environment.width_px) / density)
                          );
    const auto height_dp = static_cast<int32_t>(
                               std::max(1.0F, static_cast<float>(environment.height_px) / density)
                           );
    const auto metrics = launcher_metrics_for(width_dp, height_dp);
    const auto fallback_width = width_dp;
    const auto content_frame = context.gui().get_view_frame(SUPER_LAUNCHER_CONTENT_PATH);
    const auto available_width = content_frame.has_value() ?
                                 std::max<int32_t>(content_frame->width, metrics.item_width) :
                                 std::max<int32_t>(fallback_width, metrics.item_width);
    auto launcher_columns = std::max<int32_t>(
                                1,
                                (available_width + metrics.item_gap) / (metrics.item_width + metrics.item_gap)
                            );
    if (width_dp == 360 && height_dp == 360) {
        launcher_columns = 2;
    }
    const auto launcher_grid_width =
        launcher_columns * metrics.item_width + (launcher_columns - 1) * metrics.item_gap;
    const auto launcher_grid_x = std::max<int32_t>(0, (available_width - launcher_grid_width) / 2);
"""

OLD_ITEM = """        const auto item_x = column * (LAUNCHER_ITEM_WIDTH + LAUNCHER_ITEM_GAP);
        const auto item_y = row * (LAUNCHER_ITEM_HEIGHT + LAUNCHER_ITEM_GAP);
        content_height = std::max(content_height, item_y + LAUNCHER_ITEM_HEIGHT);
"""

NEW_ITEM = """        const auto item_x = column * (metrics.item_width + metrics.item_gap);
        const auto item_y = row * (metrics.item_height + metrics.item_gap);
        content_height = std::max(content_height, item_y + metrics.item_height);
"""


def patch_launcher_cpp(path: Path) -> bool:
    """Rewrite Super launcher metrics for the 1.85C. True when the file changed."""
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        if OLD_ENV in text or OLD_ITEM in text:
            raise RuntimeError(f"round launcher patch is only half-applied: {path}")
        return False
    if "inline constexpr int32_t LAUNCHER_ITEM_GAP = 18;" not in text:
        raise RuntimeError(f"round launcher patch cannot find item constants: {path}")
    if OLD_ENV not in text or OLD_ITEM not in text:
        raise RuntimeError(f"round launcher patch cannot find layout block: {path}")
    text = text.replace(
        "inline constexpr int32_t LAUNCHER_ITEM_GAP = 18;\n",
        "inline constexpr int32_t LAUNCHER_ITEM_GAP = 18;\n" + METRICS_BLOCK,
        1,
    )
    text = text.replace(OLD_ENV, NEW_ENV, 1)
    text = text.replace(OLD_ITEM, NEW_ITEM, 1)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    """Patch the fetched Super launcher source if it is present."""
    if not LAUNCHER_CPP.is_file():
        print(f"round launcher: skip, missing {LAUNCHER_CPP}")
        return 0
    changed = patch_launcher_cpp(LAUNCHER_CPP)
    print(f"round launcher: patched {LAUNCHER_CPP} (changed={changed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
