#include "training_ui_model.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>

constexpr int32_t k_face = 360;
constexpr int32_t k_inset = 30;
constexpr int32_t k_mid = 180;
constexpr int32_t k_col = 150;
constexpr int32_t k_pad_w = 300;
constexpr int32_t k_pad_y = 84;
constexpr int32_t k_row = 52;
constexpr int32_t k_pill_y = 260;
constexpr int32_t k_pill_h = 44;
constexpr int32_t k_pill_r = 22;
constexpr int32_t k_school_x = 54;
constexpr int32_t k_school_w = 136;
constexpr int32_t k_start_x = 206;
constexpr int32_t k_start_w = 100;
constexpr int32_t k_tile_border = 2;
constexpr uint32_t k_grout = 0xE2E8F0;
constexpr uint32_t k_ink = 0x0F172A;
constexpr uint32_t k_card = 0xFFFFFF;
constexpr uint32_t k_line = 0xE2E8F0;
constexpr uint32_t k_tile_line = 0xF8FAFC;
constexpr uint32_t k_stop = 0xDC2626;
constexpr uint32_t k_lock = 0x1D4ED8;
constexpr uint32_t k_lock_off = 0x60A5FA;
constexpr uint32_t k_free = 0x0F766E;
constexpr uint32_t k_free_off = 0x14B8A6;
constexpr uint32_t k_prev = 0x0284C7;
constexpr uint32_t k_next = 0x059669;
constexpr uint32_t k_drop = 0x475569;
constexpr uint32_t k_ready = 0x16A34A;
constexpr uint32_t k_idle = 0x65A30D;
constexpr uint32_t k_online = 0x22C55E;
constexpr uint32_t k_wait = 0xF59E0B;
constexpr uint32_t k_online_ink = 0x15803D;
constexpr uint32_t k_wait_ink = 0xC2410C;

void training_face_set_label(lv_obj_t *label, const char *text)
{
    if (label == nullptr || text == nullptr) {
        return;
    }
    const char *now = lv_label_get_text(label);
    if (now != nullptr && std::strcmp(now, text) == 0) {
        return;
    }
    lv_label_set_text(label, text);
}

bool training_face_is_stock_font(const lv_font_t *font)
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

const lv_font_t *training_face_find_cjk(lv_obj_t *node)
{
    if (node == nullptr) {
        return nullptr;
    }
    const lv_font_t *font = lv_obj_get_style_text_font(node, LV_PART_MAIN);
    if (!training_face_is_stock_font(font)) {
        return font;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        const lv_font_t *found = training_face_find_cjk(lv_obj_get_child(node, i));
        if (found != nullptr) {
            return found;
        }
    }
    return nullptr;
}

void training_face_apply_cjk(lv_obj_t *node, const lv_font_t *font)
{
    if (node == nullptr || font == nullptr) {
        return;
    }
    if (lv_obj_has_class(node, &lv_label_class)) {
        lv_obj_set_style_text_font(node, font, 0);
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        training_face_apply_cjk(lv_obj_get_child(node, i), font);
    }
}

void training_face_bubble(lv_obj_t *node)
{
    if (node == nullptr) {
        return;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        lv_obj_t *child = lv_obj_get_child(node, i);
        lv_obj_add_flag(child, LV_OBJ_FLAG_GESTURE_BUBBLE);
        training_face_bubble(child);
    }
}

lv_obj_t *training_face_label(
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

lv_obj_t *training_face_disk(lv_obj_t *parent, int32_t size, uint32_t color)
{
    lv_obj_t *disk = lv_obj_create(parent);
    lv_obj_remove_style_all(disk);
    lv_obj_set_size(disk, size, size);
    lv_obj_set_style_radius(disk, size / 2, 0);
    lv_obj_set_style_bg_color(disk, lv_color_hex(color), 0);
    lv_obj_set_style_bg_opa(disk, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(disk, 0, 0);
    lv_obj_set_style_border_width(disk, 0, 0);
    lv_obj_clear_flag(disk, LV_OBJ_FLAG_SCROLLABLE);
    return disk;
}

lv_obj_t *training_face_card(lv_obj_t *parent, int32_t x, int32_t y, int32_t width, int32_t height, int32_t radius)
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

lv_obj_t *training_face_piece(
    lv_obj_t *parent,
    int32_t x,
    int32_t y,
    int32_t width,
    int32_t height,
    uint32_t bg,
    int32_t radius,
    int32_t border_w,
    uint32_t border
)
{
    lv_obj_t *piece = lv_obj_create(parent);
    lv_obj_remove_style_all(piece);
    lv_obj_set_pos(piece, x, y);
    lv_obj_set_size(piece, width, height);
    lv_obj_set_style_radius(piece, radius, 0);
    lv_obj_set_style_bg_color(piece, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(piece, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(piece, lv_color_hex(border), 0);
    lv_obj_set_style_border_width(piece, border_w, 0);
    lv_obj_set_style_border_opa(piece, border_w > 0 ? LV_OPA_COVER : LV_OPA_TRANSP, 0);
    lv_obj_set_style_pad_all(piece, 0, 0);
    lv_obj_set_style_clip_corner(piece, radius > 0, 0);
    lv_obj_clear_flag(piece, LV_OBJ_FLAG_SCROLLABLE);
    return piece;
}

void training_face_style_btn(lv_obj_t *btn, uint32_t bg, uint32_t fg, bool enabled)
{
    if (btn == nullptr) {
        return;
    }
    lv_obj_set_style_bg_color(btn, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(btn, enabled ? LV_OPA_COVER : LV_OPA_70, 0);
    lv_obj_t *label = lv_obj_get_child(btn, 0);
    if (label != nullptr) {
        lv_obj_set_style_text_color(label, lv_color_hex(fg), 0);
        lv_obj_set_style_text_opa(label, enabled ? LV_OPA_COVER : LV_OPA_70, 0);
    }
}

lv_obj_t *training_face_btn(
    lv_obj_t *parent,
    int32_t x,
    int32_t y,
    int32_t width,
    int32_t height,
    const char *caption,
    TrainingUiAction action,
    lv_event_cb_t on_action,
    uint32_t bg
)
{
    lv_obj_t *btn = training_face_piece(
        parent, x, y, width, height, bg, 0, k_tile_border, k_tile_line
    );
    lv_obj_add_flag(btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_ext_click_area(btn, 4);
    lv_obj_add_event_cb(btn, on_action, LV_EVENT_CLICKED, reinterpret_cast<void *>(static_cast<intptr_t>(action)));
    lv_obj_t *label = lv_label_create(btn);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0xFFFFFF), 0);
    lv_label_set_text(label, caption);
    lv_obj_center(label);
    return btn;
}

lv_obj_t *training_face_picker_row(
    lv_obj_t *list,
    const char *caption,
    uint32_t bg,
    uint32_t fg,
    lv_event_cb_t on_click,
    intptr_t user,
    const lv_font_t *cjk_font
)
{
    lv_obj_t *row = lv_obj_create(list);
    lv_obj_remove_style_all(row);
    lv_obj_set_size(row, 248, 36);
    lv_obj_set_style_radius(row, 10, 0);
    lv_obj_set_style_bg_color(row, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(row, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_hor(row, 10, 0);
    lv_obj_set_style_clip_corner(row, true, 0);
    if (on_click != nullptr) {
        lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(row, on_click, LV_EVENT_CLICKED, reinterpret_cast<void *>(user));
    }
    lv_obj_t *label = lv_label_create(row);
    lv_obj_set_size(label, 224, 28);
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_LEFT, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(fg), 0);
    lv_label_set_text(label, caption);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 0, 0);
    if (cjk_font != nullptr) {
        lv_obj_set_style_text_font(label, cjk_font, 0);
    }
    return row;
}

TrainingWidgets training_face_build(
    lv_obj_t *layer,
    lv_event_cb_t on_action,
    lv_event_cb_t on_pick_org,
    lv_event_cb_t on_pick_course
)
{
    (void)on_pick_org;
    (void)on_pick_course;
    TrainingWidgets widgets;
    widgets.root = lv_obj_create(layer);
    lv_obj_remove_style_all(widgets.root);
    lv_obj_set_size(widgets.root, k_face, k_face);
    lv_obj_set_pos(widgets.root, 0, 0);
    lv_obj_set_style_bg_color(widgets.root, lv_color_hex(k_grout), 0);
    lv_obj_set_style_bg_opa(widgets.root, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(widgets.root, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_clip_corner(widgets.root, true, 0);
    lv_obj_clear_flag(widgets.root, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = training_face_label(widgets.root, 100, 16, 160, 22, LV_TEXT_ALIGN_CENTER, k_ink);
    lv_label_set_text(title, "校本培训");

    lv_obj_t *status_row = lv_obj_create(widgets.root);
    lv_obj_remove_style_all(status_row);
    lv_obj_set_pos(status_row, 64, 42);
    lv_obj_set_size(status_row, 232, 24);
    lv_obj_set_flex_flow(status_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(status_row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(status_row, 6, 0);
    lv_obj_clear_flag(status_row, LV_OBJ_FLAG_SCROLLABLE);
    widgets.online = training_face_disk(status_row, 8, k_wait);
    widgets.status = lv_label_create(status_row);
    lv_obj_set_style_text_align(widgets.status, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(widgets.status, lv_color_hex(k_wait_ink), 0);
    lv_label_set_long_mode(widgets.status, LV_LABEL_LONG_DOT);
    lv_label_set_text(widgets.status, "");

    widgets.prev = training_face_btn(
        widgets.root, k_inset, k_pad_y, k_col, k_row, "上一页", TrainingUiAction::prev, on_action, k_prev
    );
    widgets.next = training_face_btn(
        widgets.root, k_mid, k_pad_y, k_col, k_row, "下一页", TrainingUiAction::next, on_action, k_next
    );
    widgets.stop = training_face_btn(
        widgets.root, k_inset, k_pad_y + k_row, k_pad_w, k_row, "停止", TrainingUiAction::stop, on_action, k_stop
    );
    widgets.lock = training_face_btn(
        widgets.root, k_inset, k_pad_y + k_row * 2, k_col, k_row, "锁定", TrainingUiAction::lock, on_action, k_lock
    );
    widgets.free = training_face_btn(
        widgets.root,
        k_mid,
        k_pad_y + k_row * 2,
        k_col,
        k_row,
        "自由",
        TrainingUiAction::free,
        on_action,
        k_free_off
    );

    widgets.dropdown = training_face_piece(
        widgets.root, k_school_x, k_pill_y, k_school_w, k_pill_h, k_drop, k_pill_r, k_tile_border, k_tile_line
    );
    lv_obj_add_flag(widgets.dropdown, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(
        widgets.dropdown,
        on_action,
        LV_EVENT_CLICKED,
        reinterpret_cast<void *>(static_cast<intptr_t>(TrainingUiAction::toggle_dropdown))
    );
    widgets.dropdown_label = lv_label_create(widgets.dropdown);
    lv_obj_set_size(widgets.dropdown_label, k_school_w - 20, 22);
    lv_obj_set_style_text_align(widgets.dropdown_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(widgets.dropdown_label, lv_color_hex(0xFFFFFF), 0);
    lv_label_set_long_mode(widgets.dropdown_label, LV_LABEL_LONG_DOT);
    lv_obj_center(widgets.dropdown_label);
    lv_label_set_text(widgets.dropdown_label, "选择学校");

    widgets.pill = training_face_piece(
        widgets.root, k_start_x, k_pill_y, k_start_w, k_pill_h, k_idle, k_pill_r, k_tile_border, k_tile_line
    );
    lv_obj_add_flag(widgets.pill, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(
        widgets.pill,
        on_action,
        LV_EVENT_CLICKED,
        reinterpret_cast<void *>(static_cast<intptr_t>(TrainingUiAction::start))
    );
    widgets.pill_label = lv_label_create(widgets.pill);
    lv_obj_set_style_text_align(widgets.pill_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(widgets.pill_label, lv_color_hex(0xFFFFFF), 0);
    lv_label_set_text(widgets.pill_label, "开始");
    lv_obj_center(widgets.pill_label);

    widgets.picker = training_face_card(widgets.root, 44, 72, 272, 176, 16);
    lv_obj_add_flag(widgets.picker, LV_OBJ_FLAG_HIDDEN);
    widgets.picker_list = lv_obj_create(widgets.picker);
    lv_obj_remove_style_all(widgets.picker_list);
    lv_obj_set_pos(widgets.picker_list, 8, 8);
    lv_obj_set_size(widgets.picker_list, 256, 160);
    lv_obj_set_flex_flow(widgets.picker_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(widgets.picker_list, 6, 0);
    lv_obj_set_scroll_dir(widgets.picker_list, LV_DIR_VER);
    lv_obj_add_flag(widgets.picker_list, LV_OBJ_FLAG_SCROLLABLE);

    widgets.confirm = training_face_card(widgets.root, 56, 110, 248, 140, 16);
    lv_obj_add_flag(widgets.confirm, LV_OBJ_FLAG_HIDDEN);
    lv_obj_t *confirm_title = training_face_label(widgets.confirm, 16, 16, 216, 24, LV_TEXT_ALIGN_CENTER, k_ink);
    lv_label_set_text(confirm_title, "停止");
    lv_obj_t *confirm_body = training_face_label(widgets.confirm, 16, 44, 216, 36, LV_TEXT_ALIGN_CENTER, 0x64748B);
    lv_label_set_long_mode(confirm_body, LV_LABEL_LONG_WRAP);
    lv_label_set_text(confirm_body, "再按一次结束本场");
    lv_obj_t *ok = training_face_btn(
        widgets.confirm, 20, 88, 100, 36, "结束", TrainingUiAction::confirm_end, on_action, k_stop
    );
    lv_obj_t *cancel = training_face_btn(
        widgets.confirm, 128, 88, 100, 36, "取消", TrainingUiAction::cancel_end, on_action, 0x94A3B8
    );
    training_face_style_btn(ok, k_stop, 0xFFFFFF, true);
    training_face_style_btn(cancel, 0x94A3B8, 0xFFFFFF, true);

    training_face_bubble(widgets.root);
    lv_obj_remove_flag(widgets.picker_list, LV_OBJ_FLAG_GESTURE_BUBBLE);
    return widgets;
}

const char *training_face_phase_status(const TrainingUiSnapshot &snap)
{
    if (snap.status[0] != '\0') {
        return snap.status;
    }
    switch (snap.phase) {
    case TrainingUiPhase::foreign:
        return "他人正在主持";
    case TrainingUiPhase::error:
        return "出错了";
    case TrainingUiPhase::armed:
        return "教室已就绪";
    case TrainingUiPhase::live:
        return "";
    case TrainingUiPhase::ready:
        return "点开始开课";
    default:
        return "等待选择学校";
    }
}

void training_face_paint_status(TrainingWidgets &widgets, const TrainingUiSnapshot &snap, const char *status)
{
    const bool good = snap.phase == TrainingUiPhase::ready
        || snap.phase == TrainingUiPhase::armed
        || snap.phase == TrainingUiPhase::live;
    if (widgets.online != nullptr) {
        lv_obj_set_style_bg_color(widgets.online, lv_color_hex(good ? k_online : k_wait), 0);
        lv_obj_remove_flag(widgets.online, LV_OBJ_FLAG_HIDDEN);
    }
    if (widgets.status != nullptr) {
        lv_obj_set_style_text_color(widgets.status, lv_color_hex(good ? k_online_ink : k_wait_ink), 0);
        training_face_set_label(widgets.status, status);
    }
}

void training_face_paint_picker(
    TrainingWidgets &widgets,
    const TrainingUiSnapshot &snap,
    const lv_font_t *cjk_font,
    uint8_t &painted_list,
    lv_event_cb_t on_action,
    lv_event_cb_t on_pick_org,
    lv_event_cb_t on_pick_course
)
{
    if (widgets.picker == nullptr || widgets.picker_list == nullptr) {
        return;
    }
    if (!snap.dropdown_open) {
        lv_obj_add_flag(widgets.picker, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    lv_obj_remove_flag(widgets.picker, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(widgets.picker);
    if (painted_list == snap.list_serial && lv_obj_get_child_count(widgets.picker_list) > 0) {
        return;
    }
    lv_obj_clean(widgets.picker_list);
    if (snap.dropdown_mode == TrainingDropdownMode::courses) {
        if (snap.school_name[0] != '\0' && !snap.school_locked) {
            char caption[64] = {};
            std::snprintf(caption, sizeof(caption), "学校 · %s", snap.school_name);
            training_face_picker_row(
                widgets.picker_list,
                caption,
                0xF1F5F9,
                0x64748B,
                on_action,
                static_cast<intptr_t>(TrainingUiAction::change_school),
                cjk_font
            );
        }
        if (snap.course_count == 0) {
            training_face_picker_row(widgets.picker_list, "暂无课程", 0xF1F5F9, 0x64748B, nullptr, 0, cjk_font);
        }
        for (uint8_t i = 0; i < snap.course_count; ++i) {
            const bool active = snap.active_course[0] != '\0'
                && std::strcmp(snap.courses[i].id, snap.active_course) == 0;
            training_face_picker_row(
                widgets.picker_list,
                snap.courses[i].title,
                active ? k_lock : 0xF1F5F9,
                active ? 0xFFFFFF : k_ink,
                on_pick_course,
                static_cast<intptr_t>(i),
                cjk_font
            );
        }
    } else if (snap.org_count == 0) {
        training_face_picker_row(widgets.picker_list, "暂无学校", 0xF1F5F9, 0x64748B, nullptr, 0, cjk_font);
    } else {
        for (uint8_t i = 0; i < snap.org_count; ++i) {
            training_face_picker_row(
                widgets.picker_list,
                snap.orgs[i].title,
                0xF1F5F9,
                k_ink,
                on_pick_org,
                static_cast<intptr_t>(i),
                cjk_font
            );
        }
    }
    painted_list = snap.list_serial;
}

void training_face_paint(
    TrainingWidgets &widgets,
    const TrainingUiSnapshot &snap,
    const lv_font_t *cjk_font,
    uint8_t &painted_list,
    lv_event_cb_t on_action,
    lv_event_cb_t on_pick_org,
    lv_event_cb_t on_pick_course
)
{
    char step_line[48] = {};
    if (snap.phase == TrainingUiPhase::live && snap.step_count > 0) {
        std::snprintf(step_line, sizeof(step_line), "%d / %d", snap.step_index + 1, snap.step_count);
    }
    const char *status = step_line[0] != '\0' ? step_line : training_face_phase_status(snap);
    training_face_paint_status(widgets, snap, status);
    training_face_set_label(
        widgets.dropdown_label,
        snap.dropdown_label[0] != '\0' ? snap.dropdown_label : "选择学校"
    );
    const bool live = snap.pad_enabled && !snap.confirm;
    training_face_style_btn(widgets.prev, k_prev, 0xFFFFFF, live && snap.can_prev && !snap.busy);
    training_face_style_btn(widgets.next, k_next, 0xFFFFFF, live && snap.can_next && !snap.busy);
    training_face_style_btn(widgets.stop, k_stop, 0xFFFFFF, live && !snap.busy);
    training_face_style_btn(
        widgets.lock, snap.locked ? k_lock : k_lock_off, 0xFFFFFF, live && !snap.busy
    );
    training_face_style_btn(
        widgets.free, snap.locked ? k_free_off : k_free, 0xFFFFFF, live && !snap.busy
    );
    if (widgets.pill != nullptr && widgets.pill_label != nullptr) {
        uint32_t bg = k_idle;
        const char *caption = "开始";
        if (snap.pill == TrainingHostPill::ready) {
            bg = k_ready;
        } else if (snap.pill == TrainingHostPill::stop) {
            bg = k_stop;
            caption = "停止";
        }
        const bool host_ok = !snap.busy && snap.phase != TrainingUiPhase::foreign;
        lv_obj_set_style_bg_color(widgets.pill, lv_color_hex(bg), 0);
        lv_obj_set_style_bg_opa(widgets.pill, host_ok ? LV_OPA_COVER : LV_OPA_70, 0);
        lv_obj_set_style_text_color(widgets.pill_label, lv_color_hex(0xFFFFFF), 0);
        lv_obj_set_style_text_opa(widgets.pill_label, host_ok ? LV_OPA_COVER : LV_OPA_70, 0);
        training_face_set_label(widgets.pill_label, caption);
    }
    training_face_paint_picker(
        widgets, snap, cjk_font, painted_list, on_action, on_pick_org, on_pick_course
    );
    if (widgets.confirm != nullptr) {
        if (snap.confirm) {
            lv_obj_remove_flag(widgets.confirm, LV_OBJ_FLAG_HIDDEN);
            lv_obj_move_foreground(widgets.confirm);
        } else {
            lv_obj_add_flag(widgets.confirm, LV_OBJ_FLAG_HIDDEN);
        }
    }
}
