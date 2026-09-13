#!/usr/bin/env python3
"""Pin Super's launcher grid to 360x360 watch tiles with vertical scroll."""

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
    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        if (width_dp == 466) {
            return {104, 104, 13};
        }
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
    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
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

METRIC_ITEM = """        const auto item_x = launcher_grid_x + column * (metrics.item_width + metrics.item_gap);
        const auto item_y = row * (metrics.item_height + metrics.item_gap);
        content_height = std::max(content_height, item_y + metrics.item_height);
"""

LOOP_VERTICAL_UNCENTERED = """    int32_t content_height = content_frame.has_value() ? std::max<int32_t>(content_frame->height, 1) : 1;
    for (size_t i = 0; i < visible_apps.size(); ++i) {
        const auto &app = visible_apps[i];
        const auto column = static_cast<int32_t>(i % static_cast<size_t>(launcher_columns));
        const auto row = static_cast<int32_t>(i / static_cast<size_t>(launcher_columns));
        const auto item_x = column * (metrics.item_width + metrics.item_gap);
        const auto item_y = row * (metrics.item_height + metrics.item_gap);
        content_height = std::max(content_height, item_y + metrics.item_height);
"""

LOOP_VERTICAL = """    int32_t content_height = content_frame.has_value() ? std::max<int32_t>(content_frame->height, 1) : 1;
    for (size_t i = 0; i < visible_apps.size(); ++i) {
        const auto &app = visible_apps[i];
        const auto column = static_cast<int32_t>(i % static_cast<size_t>(launcher_columns));
        const auto row = static_cast<int32_t>(i / static_cast<size_t>(launcher_columns));
        const auto item_x = launcher_grid_x + column * (metrics.item_width + metrics.item_gap);
        const auto item_y = row * (metrics.item_height + metrics.item_gap);
        content_height = std::max(content_height, item_y + metrics.item_height);
"""

LOOP_HORIZONTAL = """    int32_t content_height = content_frame.has_value() ? std::max<int32_t>(content_frame->height, 1) : 1;
    int32_t content_width = launcher_grid_width;
    const bool watch_360 = width_dp == 360 && height_dp == 360;
    for (size_t i = 0; i < visible_apps.size(); ++i) {
        const auto &app = visible_apps[i];
        int32_t column = 0;
        int32_t row = 0;
        if (watch_360) {
            const auto page = static_cast<int32_t>(i / 4);
            const auto local = static_cast<int32_t>(i % 4);
            column = page * 2 + (local % 2);
            row = local / 2;
        } else {
            column = static_cast<int32_t>(i % static_cast<size_t>(launcher_columns));
            row = static_cast<int32_t>(i / static_cast<size_t>(launcher_columns));
        }
        const auto item_x = column * (metrics.item_width + metrics.item_gap);
        const auto item_y = row * (metrics.item_height + metrics.item_gap);
        content_height = std::max(content_height, item_y + metrics.item_height);
        content_width = std::max(content_width, item_x + metrics.item_width);
"""

BIND_VERTICAL = """    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        content_height += width_dp == 466 ? 100 : 48;
    }
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_SLOT_GRID_PATH,
        "content_height",
        std::to_string(content_height)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_ITEM_LAYER_PATH,
        "content_height",
        std::to_string(content_height)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_DRAG_LAYER_PATH,
        "content_height",
        std::to_string(content_height)
    );
"""

BIND_STOCK = """    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_SLOT_GRID_PATH,
        "content_height",
        std::to_string(content_height)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_ITEM_LAYER_PATH,
        "content_height",
        std::to_string(content_height)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_DRAG_LAYER_PATH,
        "content_height",
        std::to_string(content_height)
    );
"""

BIND_HORIZONTAL = """    if (watch_360) {
        content_width += 24;
        content_height = metrics.item_height * 2 + metrics.item_gap;
    }
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_SLOT_GRID_PATH,
        "content_height",
        std::to_string(content_height)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_SLOT_GRID_PATH,
        "content_width",
        std::to_string(content_width)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_ITEM_LAYER_PATH,
        "content_height",
        std::to_string(content_height)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_ITEM_LAYER_PATH,
        "content_width",
        std::to_string(content_width)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_DRAG_LAYER_PATH,
        "content_height",
        std::to_string(content_height)
    );
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_DRAG_LAYER_PATH,
        "content_width",
        std::to_string(content_width)
    );
"""


def apply_metrics_if_needed(text: str, path: Path) -> str:
    """Install watch tile metrics on stock Super launcher source."""
    if MARKER in text:
        if OLD_ENV in text or OLD_ITEM in text:
            raise RuntimeError(f"round launcher patch is only half-applied: {path}")
        return text
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
    return text.replace(OLD_ITEM, METRIC_ITEM, 1)


def apply_vertical_loop(text: str, path: Path) -> str:
    """Use row-major 2-column tiles instead of sideways 2x2 pages."""
    if LOOP_HORIZONTAL in text:
        return text.replace(LOOP_HORIZONTAL, LOOP_VERTICAL, 1)
    if LOOP_VERTICAL_UNCENTERED in text:
        return text.replace(LOOP_VERTICAL_UNCENTERED, LOOP_VERTICAL, 1)
    if LOOP_VERTICAL in text:
        return text
    raise RuntimeError(f"round launcher patch cannot find item loop: {path}")


BIND_VERTICAL_62 = BIND_VERTICAL.replace(
    "content_height += width_dp == 466 ? 100 : 48;",
    "content_height += width_dp == 466 ? 62 : 48;",
    1,
)


def apply_vertical_bind(text: str, path: Path) -> str:
    """Grow content height so the last row can scroll into the circle."""
    if BIND_VERTICAL in text:
        return text
    if BIND_VERTICAL_62 in text:
        return text.replace(BIND_VERTICAL_62, BIND_VERTICAL, 1)
    if BIND_HORIZONTAL in text:
        return text.replace(BIND_HORIZONTAL, BIND_VERTICAL, 1)
    if BIND_STOCK in text:
        return text.replace(BIND_STOCK, BIND_VERTICAL, 1)
    raise RuntimeError(f"round launcher patch cannot find content_height bind: {path}")


GRID_STAGE_NARROW = """    add_binding_update(binding_updates, SUPER_LAUNCHER_GRID_STAGE_PATH, "grid_x", std::to_string(launcher_grid_x));
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_GRID_STAGE_PATH,
        "grid_width",
        std::to_string(launcher_grid_width)
    );
"""

GRID_STAGE_FULL = """    add_binding_update(binding_updates, SUPER_LAUNCHER_GRID_STAGE_PATH, "grid_x", "0");
    add_binding_update(
        binding_updates,
        SUPER_LAUNCHER_GRID_STAGE_PATH,
        "grid_width",
        std::to_string(available_width)
    );
"""


def apply_full_width_scroll_stage(text: str) -> str:
    """Keep the scroll viewport as wide as the content band, center tiles inside it."""
    if GRID_STAGE_NARROW in text:
        return text.replace(GRID_STAGE_NARROW, GRID_STAGE_FULL, 1)
    return text


def migrate_round_466(text: str) -> str:
    """Widen 360-only watch checks so the 466 AMOLED uses the same grid."""
    replacements = (
        (
            """    if (width_dp == 360 && height_dp == 360) {
        return {80, 80, 10};
    }""",
            """    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        if (width_dp == 466) {
            return {104, 104, 13};
        }
        return {80, 80, 10};
    }""",
        ),
        (
            """    if (width_dp == 360 && height_dp == 360) {
        launcher_columns = 2;
    }""",
            """    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        launcher_columns = 2;
    }""",
        ),
        (
            """    if (width_dp == 360 && height_dp == 360) {
        content_height += 48;
    }""",
            """    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        content_height += width_dp == 466 ? 100 : 48;
    }""",
        ),
    )
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new, 1)
    return text


CREATE_FAIL_OLD = """        if (!create_result) {
            return std::unexpected(create_result.error());
        }
"""
CREATE_FAIL_NEW = """        if (!create_result) {
            BROOKESIA_LOGW(
                "Launcher tile skipped: app(%1%), error(%2%)",
                app.manifest.id,
                create_result.error()
            );
            continue;
        }
"""
DUP_PAD = """    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        content_height += width_dp == 466 ? 100 : 48;
    }
    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        content_height += width_dp == 466 ? 100 : 48;
    }
"""
SINGLE_PAD = """    if ((width_dp == 360 && height_dp == 360) || (width_dp == 466 && height_dp == 466)) {
        content_height += width_dp == 466 ? 100 : 48;
    }
"""


def apply_skip_failed_tiles(text: str) -> str:
    """Keep other launcher tiles if one icon template fails to instantiate."""
    if "Launcher tile skipped:" in text:
        return text
    if CREATE_FAIL_OLD not in text:
        raise RuntimeError("round launcher patch cannot find create_view failure")
    return text.replace(CREATE_FAIL_OLD, CREATE_FAIL_NEW, 1)


def apply_single_scroll_pad(text: str) -> str:
    """Drop a doubled last-row scroll pad from a previous 466 migrate."""
    if DUP_PAD in text:
        return text.replace(DUP_PAD, SINGLE_PAD, 1)
    return text


def patch_launcher_cpp(path: Path) -> bool:
    """Rewrite Super launcher metrics for the round watches. True when the file changed."""
    text = path.read_text(encoding="utf-8")
    original = text
    text = apply_metrics_if_needed(text, path)
    text = apply_vertical_loop(text, path)
    text = apply_vertical_bind(text, path)
    text = migrate_round_466(text)
    text = apply_skip_failed_tiles(text)
    text = apply_single_scroll_pad(text)
    text = apply_full_width_scroll_stage(text)
    if text == original:
        return False
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
