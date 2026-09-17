#include "super_kitty_ui_widgets.hpp"

#include "kitty_ui_mascot.hpp"
#include "kitty_ui_work_ring.hpp"
#include "watch_face.hpp"

namespace {

constexpr uint32_t k_bg = 0xF8FAFC;
constexpr uint32_t k_ink = 0x0F172A;
constexpr uint32_t k_mute = 0x64748B;
constexpr uint32_t k_card = 0xFFFFFF;
constexpr uint32_t k_line = 0xE2E8F0;
constexpr uint32_t k_violet = 0x7C3AED;

lv_obj_t *make_label(
    lv_obj_t *parent,
    int32_t x,
    int32_t y,
    int32_t width,
    int32_t height,
    lv_text_align_t align,
    uint32_t color
)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_remove_style_all(label);
    lv_obj_set_pos(label, x, y);
    lv_obj_set_size(label, width, height);
    lv_obj_set_style_text_align(label, align, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(color), 0);
    lv_obj_set_style_bg_opa(label, LV_OPA_TRANSP, 0);
    lv_obj_set_style_pad_all(label, 0, 0);
    lv_obj_set_style_border_width(label, 0, 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    lv_label_set_text(label, "");
    return label;
}

lv_obj_t *make_disk(lv_obj_t *parent, int32_t x, int32_t y, int32_t size, uint32_t color)
{
    lv_obj_t *disk = lv_obj_create(parent);
    lv_obj_remove_style_all(disk);
    lv_obj_set_pos(disk, x, y);
    lv_obj_set_size(disk, size, size);
    lv_obj_set_style_radius(disk, size / 2, 0);
    lv_obj_set_style_bg_color(disk, lv_color_hex(color), 0);
    lv_obj_set_style_bg_opa(disk, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(disk, 0, 0);
    lv_obj_set_style_border_width(disk, 0, 0);
    lv_obj_clear_flag(disk, LV_OBJ_FLAG_SCROLLABLE);
    return disk;
}

lv_obj_t *make_card(lv_obj_t *parent, int32_t x, int32_t y, int32_t width, int32_t height, int32_t radius)
{
    lv_obj_t *card = lv_obj_create(parent);
    lv_obj_remove_style_all(card);
    lv_obj_set_pos(card, x, y);
    lv_obj_set_size(card, width, height);
    lv_obj_set_style_radius(card, radius, 0);
    lv_obj_set_style_bg_color(card, lv_color_hex(k_card), 0);
    lv_obj_set_style_bg_opa(card, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(card, lv_color_hex(k_line), 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_pad_all(card, 0, 0);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    return card;
}

lv_obj_t *make_choice_grid(lv_obj_t *parent)
{
    lv_obj_t *grid = lv_obj_create(parent);
    lv_obj_remove_style_all(grid);
    lv_obj_set_pos(grid, watch_px(62), watch_px(94));
    lv_obj_set_size(grid, watch_px(236), watch_px(132));
    lv_obj_set_flex_flow(grid, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(grid, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_row(grid, 8, 0);
    lv_obj_set_style_pad_column(grid, 8, 0);
    lv_obj_set_style_bg_opa(grid, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(grid, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(grid, LV_OBJ_FLAG_CLICKABLE);
    return grid;
}

lv_obj_t *make_choice(lv_obj_t *parent, int32_t index, lv_event_cb_t on_choice)
{
    lv_obj_t *chip = make_card(parent, 0, 0, watch_px(114), watch_px(62), watch_px(16));
    lv_obj_set_style_clip_corner(chip, true, 0);
    lv_obj_set_style_border_color(chip, lv_color_hex(k_violet), 0);
    lv_obj_set_style_border_width(chip, 2, 0);
    lv_obj_add_flag(chip, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_ext_click_area(chip, 6);
    lv_obj_add_event_cb(chip, on_choice, LV_EVENT_CLICKED, reinterpret_cast<void *>(static_cast<intptr_t>(index)));
    lv_obj_t *label = lv_label_create(chip);
    lv_obj_set_style_text_color(label, lv_color_hex(k_ink), 0);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_WRAP);
    lv_obj_set_size(label, watch_px(98), watch_px(48));
    lv_obj_center(label);
    lv_label_set_text(label, "");
    lv_obj_add_flag(chip, LV_OBJ_FLAG_HIDDEN);
    return chip;
}

void bubble_home_gesture(lv_obj_t *node)
{
    if (node == nullptr) {
        return;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        lv_obj_t *child = lv_obj_get_child(node, i);
        lv_obj_add_flag(child, LV_OBJ_FLAG_GESTURE_BUBBLE);
        bubble_home_gesture(child);
    }
}

} // namespace

SuperKittyWidgets super_kitty_ui_build(
    lv_obj_t *layer,
    lv_event_cb_t on_library,
    lv_event_cb_t on_choice
)
{
    SuperKittyWidgets widgets;
    widgets.root = lv_obj_create(layer);
    lv_obj_remove_style_all(widgets.root);
    lv_obj_set_size(widgets.root, k_face, k_face);
    lv_obj_set_pos(widgets.root, 0, 0);
    lv_obj_set_style_bg_color(widgets.root, lv_color_hex(k_bg), 0);
    lv_obj_set_style_bg_opa(widgets.root, LV_OPA_COVER, 0);
    lv_obj_clear_flag(widgets.root, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(widgets.root, LV_OBJ_FLAG_CLICKABLE);
    widgets.work_ring = kitty_ui_work_ring_build(widgets.root);

    lv_obj_t *title = make_label(
        widgets.root, watch_px(70), watch_px(28), watch_px(220), watch_px(22), LV_TEXT_ALIGN_CENTER, k_ink
    );
    lv_label_set_text(title, "超级小猫");

    lv_obj_t *status = lv_obj_create(widgets.root);
    lv_obj_remove_style_all(status);
    lv_obj_set_pos(status, watch_px(70), watch_px(50));
    lv_obj_set_size(status, watch_px(220), watch_px(18));
    lv_obj_set_flex_flow(status, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(status, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(status, 6, 0);
    lv_obj_clear_flag(status, LV_OBJ_FLAG_SCROLLABLE);
    widgets.online = make_disk(status, 0, 0, 8, 0x22C55E);
    lv_obj_add_flag(widgets.online, LV_OBJ_FLAG_HIDDEN);
    widgets.live = lv_label_create(status);
    lv_obj_set_style_text_color(widgets.live, lv_color_hex(k_mute), 0);
    lv_label_set_long_mode(widgets.live, LV_LABEL_LONG_DOT);
    lv_label_set_text(widgets.live, "连接中");

    widgets.mascot = lv_obj_create(widgets.root);
    lv_obj_remove_style_all(widgets.mascot);
    lv_obj_set_pos(widgets.mascot, watch_px(110), watch_px(88));
    lv_obj_set_size(widgets.mascot, watch_px(140), watch_px(140));
    lv_obj_set_style_bg_opa(widgets.mascot, LV_OPA_TRANSP, 0);
    lv_obj_set_style_pad_all(widgets.mascot, 0, 0);
    lv_obj_clear_flag(widgets.mascot, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(widgets.mascot, LV_OBJ_FLAG_CLICKABLE);
    kitty_ui_mascot_build(widgets.mascot);

    widgets.user = make_label(
        widgets.root, watch_px(40), watch_px(92), watch_px(280), watch_px(40), LV_TEXT_ALIGN_RIGHT, k_violet
    );
    lv_label_set_long_mode(widgets.user, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_bg_opa(widgets.user, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(widgets.user, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_flag(widgets.user, LV_OBJ_FLAG_HIDDEN);
    widgets.kitty = make_label(
        widgets.root, watch_px(40), watch_px(136), watch_px(280), watch_px(40), LV_TEXT_ALIGN_LEFT, k_ink
    );
    lv_label_set_long_mode(widgets.kitty, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_bg_opa(widgets.kitty, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(widgets.kitty, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_flag(widgets.kitty, LV_OBJ_FLAG_HIDDEN);

    widgets.choice_grid = make_choice_grid(widgets.root);
    for (int32_t i = 0; i < 4; ++i) {
        widgets.choices[i] = make_choice(widgets.choice_grid, i + 1, on_choice);
    }

    widgets.library = make_card(widgets.root, watch_px(98), watch_px(264), watch_px(164), watch_px(52), watch_px(26));
    lv_obj_add_flag(widgets.library, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_clip_corner(widgets.library, true, 0);
    lv_obj_set_ext_click_area(widgets.library, watch_px(12));
    lv_obj_add_event_cb(widgets.library, on_library, LV_EVENT_PRESSED, nullptr);
    widgets.library_label = lv_label_create(widgets.library);
    lv_obj_set_size(widgets.library_label, watch_px(140), watch_px(22));
    lv_obj_set_style_text_align(widgets.library_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(widgets.library_label, lv_color_hex(k_ink), 0);
    lv_label_set_long_mode(widgets.library_label, LV_LABEL_LONG_DOT);
    lv_obj_center(widgets.library_label);
    lv_label_set_text(widgets.library_label, "图库");

    widgets.picker = make_card(widgets.root, watch_px(40), watch_px(62), watch_px(280), watch_px(186), watch_px(16));
    lv_obj_add_flag(widgets.picker, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(widgets.picker, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_clip_corner(widgets.picker, true, 0);
    widgets.picker_list = lv_obj_create(widgets.picker);
    lv_obj_remove_style_all(widgets.picker_list);
    lv_obj_set_pos(widgets.picker_list, watch_px(8), watch_px(8));
    lv_obj_set_size(widgets.picker_list, watch_px(264), watch_px(170));
    lv_obj_set_flex_flow(widgets.picker_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(widgets.picker_list, 6, 0);
    lv_obj_set_style_bg_color(widgets.picker_list, lv_color_hex(k_card), 0);
    lv_obj_set_style_bg_opa(widgets.picker_list, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(widgets.picker_list, watch_px(12), 0);
    lv_obj_set_style_clip_corner(widgets.picker_list, true, 0);
    lv_obj_set_scroll_dir(widgets.picker_list, LV_DIR_VER);
    lv_obj_add_flag(widgets.picker_list, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(widgets.picker_list, LV_OBJ_FLAG_CLICKABLE);

    bubble_home_gesture(widgets.root);
    lv_obj_move_foreground(widgets.root);
    if (widgets.work_ring != nullptr) {
        lv_obj_move_foreground(widgets.work_ring);
    }
    lv_obj_remove_flag(widgets.library, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_remove_flag(widgets.picker, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_remove_flag(widgets.picker_list, LV_OBJ_FLAG_GESTURE_BUBBLE);
    if (widgets.choice_grid != nullptr) {
        lv_obj_remove_flag(widgets.choice_grid, LV_OBJ_FLAG_GESTURE_BUBBLE);
        for (lv_obj_t *chip : widgets.choices) {
            if (chip != nullptr) {
                lv_obj_remove_flag(chip, LV_OBJ_FLAG_GESTURE_BUBBLE);
            }
        }
    }
    super_kitty_ui_picker_present(widgets, false);
    return widgets;
}

void super_kitty_ui_set_hidden(lv_obj_t *obj, bool hidden)
{
    if (obj == nullptr) {
        return;
    }
    if (lv_obj_has_flag(obj, LV_OBJ_FLAG_HIDDEN) == hidden) {
        return;
    }
    if (hidden) {
        lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_HIDDEN);
}

void super_kitty_ui_picker_present(const SuperKittyWidgets &widgets, bool open)
{
    if (!open) {
        super_kitty_ui_set_hidden(widgets.picker, true);
        super_kitty_ui_set_hidden(widgets.mascot, false);
        super_kitty_ui_set_hidden(widgets.choice_grid, false);
        return;
    }
    super_kitty_ui_set_hidden(widgets.mascot, true);
    super_kitty_ui_set_hidden(widgets.user, true);
    super_kitty_ui_set_hidden(widgets.kitty, true);
    super_kitty_ui_set_hidden(widgets.choice_grid, true);
    super_kitty_ui_set_hidden(widgets.picker, false);
    if (widgets.picker != nullptr) {
        lv_obj_move_foreground(widgets.picker);
    }
    if (widgets.library != nullptr) {
        lv_obj_move_foreground(widgets.library);
    }
}
