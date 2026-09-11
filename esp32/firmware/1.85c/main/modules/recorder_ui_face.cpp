#include "recorder_ui_model.hpp"

#include <cstdint>
#include <cstring>

#include "lvgl.h"

constexpr int32_t k_face = 360;
constexpr int32_t k_card_h = 190;
constexpr int32_t k_rec = 64;
constexpr int32_t k_side_btn = 44;
constexpr int32_t k_gap = 4;
constexpr int32_t k_cluster_x = 56;
constexpr int32_t k_dock_y = 262;
constexpr int32_t k_side_y = 272;
constexpr int32_t k_gen_x = 238;
constexpr int32_t k_gen_y = 276;
constexpr int32_t k_gen_w = 64;
constexpr int32_t k_gen_h = 36;
constexpr uint32_t k_page = 0xF9FAFB;
constexpr uint32_t k_ink = 0x1C1917;
constexpr uint32_t k_muted = 0x57534E;
constexpr uint32_t k_card = 0xFFFFFF;
constexpr uint32_t k_line = 0xE5E7EB;
constexpr uint32_t k_side = 0xF3F4F6;
constexpr uint32_t k_side_ring = 0x78716C;
constexpr uint32_t k_live = 0xDC2626;
constexpr uint32_t k_paused = 0xD97706;
constexpr uint32_t k_idle_dot = 0xA8A29E;
constexpr uint32_t k_resume = 0x111827;
constexpr uint32_t k_generate = 0x1C1917;

bool recorder_face_set_label(lv_obj_t *label, const char *text)
{
    if (label == nullptr || text == nullptr) {
        return false;
    }
    const char *now = lv_label_get_text(label);
    if (now != nullptr && std::strcmp(now, text) == 0) {
        return false;
    }
    lv_label_set_text(label, text);
    return true;
}

void recorder_face_scroll_transcript_end(lv_obj_t *label)
{
    if (label == nullptr) {
        return;
    }
    lv_obj_t *card = lv_obj_get_parent(label);
    if (card == nullptr) {
        return;
    }
    lv_obj_update_layout(card);
    const int32_t remain = lv_obj_get_scroll_bottom(card);
    if (remain <= 0) {
        return;
    }
    lv_obj_scroll_to_y(card, lv_obj_get_scroll_y(card) + remain, LV_ANIM_OFF);
}

bool recorder_face_is_stock_font(const lv_font_t *font)
{
    return font == nullptr
        || font == LV_FONT_DEFAULT
        || font == &lv_font_montserrat_12
        || font == &lv_font_montserrat_16
        || font == &lv_font_montserrat_20
        || font == &lv_font_montserrat_24
        || font == &lv_font_montserrat_28
        || font == &lv_font_montserrat_32
        || font == &lv_font_montserrat_36
        || font == &lv_font_montserrat_40
        || font == &lv_font_montserrat_44
        || font == &lv_font_montserrat_48;
}

const lv_font_t *recorder_face_find_cjk(lv_obj_t *node)
{
    if (node == nullptr) {
        return nullptr;
    }
    const lv_font_t *font = lv_obj_get_style_text_font(node, LV_PART_MAIN);
    if (!recorder_face_is_stock_font(font)) {
        return font;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        const lv_font_t *found = recorder_face_find_cjk(lv_obj_get_child(node, i));
        if (found != nullptr) {
            return found;
        }
    }
    return nullptr;
}

void recorder_face_apply_cjk(lv_obj_t *node, const lv_font_t *font)
{
    if (node == nullptr || font == nullptr) {
        return;
    }
    if (lv_obj_has_class(node, &lv_label_class) && !lv_obj_has_flag(node, LV_OBJ_FLAG_USER_1)) {
        lv_obj_set_style_text_font(node, font, 0);
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        recorder_face_apply_cjk(lv_obj_get_child(node, i), font);
    }
}

void recorder_face_bubble(lv_obj_t *node)
{
    if (node == nullptr) {
        return;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        lv_obj_t *child = lv_obj_get_child(node, i);
        lv_obj_add_flag(child, LV_OBJ_FLAG_GESTURE_BUBBLE);
        recorder_face_bubble(child);
    }
}

lv_obj_t *recorder_face_label(
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
    lv_obj_set_pos(label, x, y);
    lv_obj_set_size(label, width, height);
    lv_obj_set_style_text_align(label, align, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(color), 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
    lv_label_set_text(label, "");
    return label;
}

lv_obj_t *recorder_face_disk(lv_obj_t *parent, int32_t x, int32_t y, int32_t size, uint32_t color)
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

lv_obj_t *recorder_face_card(lv_obj_t *parent, int32_t x, int32_t y, int32_t width, int32_t height)
{
    lv_obj_t *card = lv_obj_create(parent);
    lv_obj_remove_style_all(card);
    lv_obj_set_pos(card, x, y);
    lv_obj_set_size(card, width, height);
    lv_obj_set_style_radius(card, 12, 0);
    lv_obj_set_style_bg_color(card, lv_color_hex(k_card), 0);
    lv_obj_set_style_bg_opa(card, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(card, lv_color_hex(k_line), 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_pad_all(card, 8, 0);
    lv_obj_set_style_clip_corner(card, true, 0);
    lv_obj_set_scroll_dir(card, LV_DIR_VER);
    lv_obj_add_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    return card;
}

lv_obj_t *recorder_face_glyph(lv_obj_t *parent, int32_t width, int32_t height, uint32_t color, int32_t radius)
{
    lv_obj_t *glyph = lv_obj_create(parent);
    lv_obj_remove_style_all(glyph);
    lv_obj_set_size(glyph, width, height);
    lv_obj_set_style_radius(glyph, radius, 0);
    lv_obj_set_style_bg_color(glyph, lv_color_hex(color), 0);
    lv_obj_set_style_bg_opa(glyph, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(glyph, 0, 0);
    lv_obj_clear_flag(glyph, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(glyph, LV_OBJ_FLAG_SCROLLABLE);
    return glyph;
}

void recorder_face_add_pause_glyph(lv_obj_t *btn, uint32_t color)
{
    lv_obj_t *left = recorder_face_glyph(btn, 4, 14, color, 1);
    lv_obj_t *right = recorder_face_glyph(btn, 4, 14, color, 1);
    lv_obj_align(left, LV_ALIGN_CENTER, -4, 0);
    lv_obj_align(right, LV_ALIGN_CENTER, 4, 0);
}

void recorder_face_add_stop_glyph(lv_obj_t *btn, uint32_t color)
{
    lv_obj_t *square = recorder_face_glyph(btn, 12, 12, color, 2);
    lv_obj_center(square);
}

void recorder_face_draw_play(lv_event_t *event)
{
    if (lv_event_get_code(event) != LV_EVENT_DRAW_MAIN) {
        return;
    }
    lv_obj_t *obj = static_cast<lv_obj_t *>(lv_event_get_target(event));
    lv_layer_t *layer = lv_event_get_layer(event);
    if (obj == nullptr || layer == nullptr) {
        return;
    }
    lv_area_t area;
    lv_obj_get_coords(obj, &area);
    const int32_t height = lv_area_get_height(&area);
    lv_draw_triangle_dsc_t dsc;
    lv_draw_triangle_dsc_init(&dsc);
    dsc.color = lv_obj_get_style_text_color(obj, LV_PART_MAIN);
    dsc.opa = lv_obj_get_style_text_opa(obj, LV_PART_MAIN);
    dsc.p[0].x = static_cast<lv_value_precise_t>(area.x1);
    dsc.p[0].y = static_cast<lv_value_precise_t>(area.y1);
    dsc.p[1].x = static_cast<lv_value_precise_t>(area.x2);
    dsc.p[1].y = static_cast<lv_value_precise_t>(area.y1 + height / 2);
    dsc.p[2].x = static_cast<lv_value_precise_t>(area.x1);
    dsc.p[2].y = static_cast<lv_value_precise_t>(area.y2);
    lv_draw_triangle(layer, &dsc);
}

void recorder_face_add_play_glyph(lv_obj_t *btn, uint32_t color)
{
    lv_obj_t *play = lv_obj_create(btn);
    lv_obj_remove_style_all(play);
    lv_obj_set_size(play, 18, 22);
    lv_obj_add_flag(play, LV_OBJ_FLAG_USER_1);
    lv_obj_clear_flag(play, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(play, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_opa(play, LV_OPA_TRANSP, 0);
    lv_obj_set_style_text_color(play, lv_color_hex(color), 0);
    lv_obj_set_style_text_opa(play, LV_OPA_COVER, 0);
    lv_obj_add_event_cb(play, recorder_face_draw_play, LV_EVENT_DRAW_MAIN, nullptr);
    lv_obj_align(play, LV_ALIGN_CENTER, 2, 0);
}

lv_obj_t *recorder_face_btn(
    lv_obj_t *parent,
    int32_t x,
    int32_t y,
    int32_t size,
    RecorderUiAction action,
    lv_event_cb_t on_action,
    uint32_t bg
)
{
    lv_obj_t *btn = recorder_face_disk(parent, x, y, size, bg);
    lv_obj_add_flag(btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_ext_click_area(btn, 4);
    lv_obj_add_event_cb(
        btn,
        on_action,
        LV_EVENT_CLICKED,
        reinterpret_cast<void *>(static_cast<intptr_t>(action))
    );
    return btn;
}

void recorder_face_style_btn(lv_obj_t *btn, uint32_t bg, uint32_t fg, bool enabled)
{
    if (btn == nullptr) {
        return;
    }
    lv_obj_set_style_bg_color(btn, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(btn, enabled ? LV_OPA_COVER : LV_OPA_40, 0);
    const uint32_t count = lv_obj_get_child_count(btn);
    for (uint32_t i = 0; i < count; ++i) {
        lv_obj_t *child = lv_obj_get_child(btn, i);
        const lv_opa_t opa = enabled ? LV_OPA_COVER : LV_OPA_40;
        if (lv_obj_has_class(child, &lv_label_class) || lv_obj_has_flag(child, LV_OBJ_FLAG_USER_1)) {
            lv_obj_set_style_text_color(child, lv_color_hex(fg), 0);
            lv_obj_set_style_text_opa(child, opa, 0);
            continue;
        }
        lv_obj_set_style_bg_color(child, lv_color_hex(fg), 0);
        lv_obj_set_style_bg_opa(child, opa, 0);
    }
}

const char *recorder_face_phase_status(const RecorderUiSnapshot &snap)
{
    if (snap.status[0] != '\0') {
        return snap.status;
    }
    switch (snap.phase) {
    case RecorderUiPhase::connecting:
        return "连接中";
    case RecorderUiPhase::recording:
        return "录音中";
    case RecorderUiPhase::paused:
        return "已暂停";
    case RecorderUiPhase::stopping:
        return "停止中";
    case RecorderUiPhase::saving:
        return "保存中";
    case RecorderUiPhase::generating:
        return "正在生成思维导图";
    case RecorderUiPhase::ready:
        return "可生成思维导图";
    case RecorderUiPhase::error:
        return "出错了";
    default:
        return "等待开始";
    }
}

uint32_t recorder_face_dot_color(const RecorderUiSnapshot &snap)
{
    if (snap.phase == RecorderUiPhase::recording) {
        return k_live;
    }
    if (snap.phase == RecorderUiPhase::paused) {
        return k_paused;
    }
    return k_idle_dot;
}

RecorderWidgets recorder_face_build(lv_obj_t *layer, lv_event_cb_t on_action)
{
    RecorderWidgets widgets;
    widgets.root = lv_obj_create(layer);
    lv_obj_remove_style_all(widgets.root);
    lv_obj_set_size(widgets.root, k_face, k_face);
    lv_obj_set_pos(widgets.root, 0, 0);
    lv_obj_set_style_bg_color(widgets.root, lv_color_hex(k_page), 0);
    lv_obj_set_style_bg_opa(widgets.root, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(widgets.root, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_clip_corner(widgets.root, true, 0);
    lv_obj_clear_flag(widgets.root, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = recorder_face_label(widgets.root, 80, 16, 200, 22, LV_TEXT_ALIGN_CENTER, k_ink);
    lv_label_set_text(title, "语音笔记");

    lv_obj_t *status_row = lv_obj_create(widgets.root);
    lv_obj_remove_style_all(status_row);
    lv_obj_set_pos(status_row, 48, 40);
    lv_obj_set_size(status_row, 264, 22);
    lv_obj_set_flex_flow(status_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(status_row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(status_row, 6, 0);
    lv_obj_clear_flag(status_row, LV_OBJ_FLAG_SCROLLABLE);
    widgets.dot = recorder_face_disk(status_row, 0, 0, 8, k_idle_dot);
    widgets.status = lv_label_create(status_row);
    lv_obj_set_style_text_color(widgets.status, lv_color_hex(k_muted), 0);
    lv_label_set_long_mode(widgets.status, LV_LABEL_LONG_DOT);
    lv_obj_set_width(widgets.status, 168);
    lv_label_set_text(widgets.status, "等待开始");
    widgets.elapsed = lv_label_create(status_row);
    lv_obj_set_style_text_color(widgets.elapsed, lv_color_hex(k_muted), 0);
    lv_label_set_text(widgets.elapsed, "00:00");

    lv_obj_t *card = recorder_face_card(widgets.root, 44, 66, 272, k_card_h);
    widgets.transcript = lv_label_create(card);
    lv_obj_set_width(widgets.transcript, 248);
    lv_obj_set_style_text_color(widgets.transcript, lv_color_hex(k_ink), 0);
    lv_obj_set_style_text_align(widgets.transcript, LV_TEXT_ALIGN_LEFT, 0);
    lv_label_set_long_mode(widgets.transcript, LV_LABEL_LONG_WRAP);
    lv_label_set_text(widgets.transcript, "点红色按钮开始录音");

    const int32_t rec_x = k_cluster_x + k_side_btn + k_gap;
    const int32_t stop_x = rec_x + k_rec + k_gap;
    widgets.pause = recorder_face_btn(
        widgets.root, k_cluster_x, k_side_y, k_side_btn, RecorderUiAction::pause, on_action, k_side
    );
    lv_obj_set_style_border_width(widgets.pause, 2, 0);
    lv_obj_set_style_border_color(widgets.pause, lv_color_hex(k_side_ring), 0);
    lv_obj_set_style_border_opa(widgets.pause, LV_OPA_COVER, 0);
    recorder_face_add_pause_glyph(widgets.pause, k_ink);
    widgets.stop = recorder_face_btn(
        widgets.root, stop_x, k_side_y, k_side_btn, RecorderUiAction::stop, on_action, k_side
    );
    lv_obj_set_style_border_width(widgets.stop, 2, 0);
    lv_obj_set_style_border_color(widgets.stop, lv_color_hex(k_side_ring), 0);
    lv_obj_set_style_border_opa(widgets.stop, LV_OPA_COVER, 0);
    recorder_face_add_stop_glyph(widgets.stop, 0xB91C1C);
    widgets.main_ring = recorder_face_disk(widgets.root, rec_x - 6, k_dock_y - 6, k_rec + 12, k_live);
    lv_obj_set_style_bg_opa(widgets.main_ring, LV_OPA_0, 0);
    lv_obj_set_style_border_width(widgets.main_ring, 2, 0);
    lv_obj_set_style_border_color(widgets.main_ring, lv_color_hex(k_live), 0);
    lv_obj_set_style_border_opa(widgets.main_ring, LV_OPA_0, 0);
    lv_obj_clear_flag(widgets.main_ring, LV_OBJ_FLAG_CLICKABLE);
    widgets.main = recorder_face_btn(
        widgets.root, rec_x, k_dock_y, k_rec, RecorderUiAction::start, on_action, k_live
    );
    recorder_face_add_play_glyph(widgets.main, 0xFFFFFF);
    widgets.main_label = lv_obj_get_child(widgets.main, 0);
    lv_obj_move_foreground(widgets.main);

    widgets.generate = lv_obj_create(widgets.root);
    lv_obj_remove_style_all(widgets.generate);
    lv_obj_set_pos(widgets.generate, k_gen_x, k_gen_y);
    lv_obj_set_size(widgets.generate, k_gen_w, k_gen_h);
    lv_obj_set_style_radius(widgets.generate, 18, 0);
    lv_obj_set_style_bg_color(widgets.generate, lv_color_hex(k_generate), 0);
    lv_obj_set_style_bg_opa(widgets.generate, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(widgets.generate, 0, 0);
    lv_obj_clear_flag(widgets.generate, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(widgets.generate, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(
        widgets.generate,
        on_action,
        LV_EVENT_CLICKED,
        reinterpret_cast<void *>(static_cast<intptr_t>(RecorderUiAction::generate))
    );
    lv_obj_t *gen_label = lv_label_create(widgets.generate);
    lv_obj_set_style_text_color(gen_label, lv_color_hex(0xFAFAF9), 0);
    lv_label_set_text(gen_label, "生导图");
    lv_obj_center(gen_label);

    recorder_face_bubble(widgets.root);
    return widgets;
}

void recorder_face_paint(RecorderWidgets &widgets, const RecorderUiSnapshot &snap)
{
    if (widgets.dot != nullptr) {
        lv_obj_set_style_bg_color(widgets.dot, lv_color_hex(recorder_face_dot_color(snap)), 0);
    }
    recorder_face_set_label(widgets.status, recorder_face_phase_status(snap));
    recorder_face_set_label(widgets.elapsed, snap.elapsed[0] != '\0' ? snap.elapsed : "00:00");
    const char *words = snap.transcript[0] != '\0' ? snap.transcript : "点红色按钮开始录音";
    if (recorder_face_set_label(widgets.transcript, words)) {
        recorder_face_scroll_transcript_end(widgets.transcript);
    }
    recorder_face_style_btn(widgets.pause, k_side, k_ink, snap.can_pause && !snap.busy);
    recorder_face_style_btn(widgets.stop, k_side, 0xB91C1C, snap.can_stop && !snap.busy);
    const bool main_ok = (snap.can_start || snap.can_resume || snap.can_pause) && !snap.busy;
    const uint32_t main_bg = snap.can_resume ? k_resume : k_live;
    recorder_face_style_btn(widgets.main, main_bg, 0xFFFFFF, main_ok);
    if (widgets.main_label != nullptr) {
        if ((snap.can_start || snap.can_resume) && !snap.busy) {
            lv_obj_remove_flag(widgets.main_label, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(widgets.main_label, LV_OBJ_FLAG_HIDDEN);
        }
    }
    if (widgets.main_ring != nullptr) {
        const bool live = snap.phase == RecorderUiPhase::recording && snap.mic_level > 0;
        const uint8_t level = live ? snap.mic_level : 0;
        const int32_t rec_x = k_cluster_x + k_side_btn + k_gap;
        const int32_t grow = static_cast<int32_t>(level) / 16;
        lv_obj_set_style_border_opa(widgets.main_ring, live ? LV_OPA_50 : LV_OPA_0, 0);
        lv_obj_set_size(widgets.main_ring, k_rec + 12 + grow, k_rec + 12 + grow);
        lv_obj_set_pos(widgets.main_ring, rec_x - 6 - grow / 2, k_dock_y - 6 - grow / 2);
    }
    if (widgets.generate != nullptr) {
        const bool on = snap.can_generate && !snap.busy;
        lv_obj_set_style_bg_color(widgets.generate, lv_color_hex(on ? k_generate : k_side), 0);
        lv_obj_set_style_bg_opa(widgets.generate, LV_OPA_COVER, 0);
        if (on) {
            lv_obj_add_flag(widgets.generate, LV_OBJ_FLAG_CLICKABLE);
        } else {
            lv_obj_clear_flag(widgets.generate, LV_OBJ_FLAG_CLICKABLE);
        }
        const uint32_t count = lv_obj_get_child_count(widgets.generate);
        for (uint32_t i = 0; i < count; ++i) {
            lv_obj_t *child = lv_obj_get_child(widgets.generate, i);
            if (lv_obj_has_class(child, &lv_label_class)) {
                lv_obj_set_style_text_color(child, lv_color_hex(on ? 0xFAFAF9 : k_muted), 0);
            }
        }
    }
}
