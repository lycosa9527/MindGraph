#include "slides_ui_model.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

#include "kitty_net.hpp"
#include "watch_face.hpp"

constexpr int32_t k_inset = watch_px(30);
constexpr int32_t k_mid = k_face / 2;
constexpr int32_t k_col = watch_px(150);
constexpr int32_t k_pad_w = watch_px(300);
constexpr int32_t k_pad_y = watch_px(84);
constexpr int32_t k_row = watch_px(52);
constexpr int32_t k_seg_gap = watch_px(10);
constexpr int32_t k_nav_y = k_pad_y + k_row + k_seg_gap;
constexpr int32_t k_auto_y = k_nav_y + k_row;
constexpr int32_t k_pill_y = watch_px(260);
constexpr int32_t k_pill_h = watch_px(44);
constexpr int32_t k_pill_r = watch_px(22);
constexpr int32_t k_tile_border = 2;
constexpr uint32_t k_grout = 0xE2E8F0;
constexpr uint32_t k_ink = 0x0F172A;
constexpr uint32_t k_tile_line = 0xF8FAFC;
constexpr uint32_t k_prev = 0x0284C7;
constexpr uint32_t k_next = 0x059669;
constexpr uint32_t k_seg_track = 0xCBD5E1;
constexpr uint32_t k_seg_thumb = 0xFFFFFF;
constexpr uint32_t k_seg_on_ink = 0x0F172A;
constexpr uint32_t k_seg_off_ink = 0x64748B;
constexpr int32_t k_seg_w = watch_px(240);
constexpr int32_t k_seg_x = (k_face - k_seg_w) / 2;
constexpr int32_t k_seg_hit = k_seg_w / 2;
constexpr int32_t k_seg_pad = watch_px(4);
constexpr int32_t k_seg_thumb_w = k_seg_hit - k_seg_pad;
constexpr int32_t k_seg_thumb_h = k_row - k_seg_pad * 2;
constexpr int32_t k_title_x = watch_px(100);
constexpr int32_t k_title_y = watch_px(16);
constexpr int32_t k_title_w = watch_px(160);
constexpr int32_t k_title_h = watch_px(22);
constexpr int32_t k_status_x = watch_px(64);
constexpr int32_t k_status_y = watch_px(42);
constexpr int32_t k_status_w = watch_px(232);
constexpr int32_t k_status_h = watch_px(24);
constexpr int32_t k_dot = watch_px(8);
constexpr int32_t k_picker_x = watch_px(44);
constexpr int32_t k_picker_y = watch_px(72);
constexpr int32_t k_picker_w = watch_px(272);
constexpr int32_t k_picker_h = watch_px(176);
constexpr int32_t k_picker_r = watch_px(16);
constexpr int32_t k_list_pad = watch_px(8);
constexpr int32_t k_list_w = watch_px(256);
constexpr int32_t k_list_h = watch_px(160);
constexpr int32_t k_row_w = watch_px(248);
constexpr int32_t k_row_h = watch_px(36);
constexpr int32_t k_row_label_w = watch_px(224);
constexpr int32_t k_row_label_h = watch_px(28);
constexpr int32_t k_label_h = watch_px(22);
constexpr int32_t k_hit_slop = watch_px(4);
constexpr uint32_t k_auto_on = 0xD97706;
constexpr uint32_t k_auto_off = 0xF59E0B;
constexpr uint32_t k_quit = 0xDC2626;
constexpr uint32_t k_ready = 0x16A34A;
constexpr uint32_t k_drop = 0x475569;
constexpr uint32_t k_card = 0xFFFFFF;
constexpr uint32_t k_line = 0xE2E8F0;
constexpr int32_t k_lib_x = watch_px(54);
constexpr int32_t k_lib_w = watch_px(136);
constexpr int32_t k_host_x = watch_px(206);
constexpr int32_t k_host_w = watch_px(100);
constexpr uint32_t k_online = 0x22C55E;
constexpr uint32_t k_wait = 0xF59E0B;
constexpr uint32_t k_online_ink = 0x15803D;
constexpr uint32_t k_wait_ink = 0xC2410C;

void slides_face_set_label(lv_obj_t *label, const char *text)
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

bool slides_face_is_stock_font(const lv_font_t *font)
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

const lv_font_t *slides_face_find_cjk(lv_obj_t *node)
{
    if (node == nullptr) {
        return nullptr;
    }
    const lv_font_t *font = lv_obj_get_style_text_font(node, LV_PART_MAIN);
    if (!slides_face_is_stock_font(font)) {
        return font;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        const lv_font_t *found = slides_face_find_cjk(lv_obj_get_child(node, i));
        if (found != nullptr) {
            return found;
        }
    }
    return nullptr;
}

void slides_face_apply_cjk(lv_obj_t *node, const lv_font_t *font)
{
    if (node == nullptr || font == nullptr) {
        return;
    }
    if (lv_obj_has_class(node, &lv_label_class)) {
        lv_obj_set_style_text_font(node, font, 0);
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        slides_face_apply_cjk(lv_obj_get_child(node, i), font);
    }
}

void slides_face_bubble(lv_obj_t *node)
{
    if (node == nullptr) {
        return;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        lv_obj_t *child = lv_obj_get_child(node, i);
        lv_obj_add_flag(child, LV_OBJ_FLAG_GESTURE_BUBBLE);
        slides_face_bubble(child);
    }
}

lv_obj_t *slides_face_label(
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

lv_obj_t *slides_face_disk(lv_obj_t *parent, int32_t size, uint32_t color)
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

lv_obj_t *slides_face_piece(
    lv_obj_t *parent,
    int32_t x,
    int32_t y,
    int32_t width,
    int32_t height,
    uint32_t bg,
    int32_t radius
)
{
    lv_obj_t *piece = lv_obj_create(parent);
    lv_obj_remove_style_all(piece);
    lv_obj_set_pos(piece, x, y);
    lv_obj_set_size(piece, width, height);
    lv_obj_set_style_radius(piece, radius, 0);
    lv_obj_set_style_bg_color(piece, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(piece, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(piece, lv_color_hex(k_tile_line), 0);
    lv_obj_set_style_border_width(piece, k_tile_border, 0);
    lv_obj_set_style_pad_all(piece, 0, 0);
    lv_obj_set_style_clip_corner(piece, radius > 0, 0);
    lv_obj_clear_flag(piece, LV_OBJ_FLAG_SCROLLABLE);
    return piece;
}

void slides_face_style_btn(lv_obj_t *btn, uint32_t bg, bool enabled)
{
    if (btn == nullptr) {
        return;
    }
    lv_obj_set_style_bg_color(btn, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(btn, enabled ? LV_OPA_COVER : LV_OPA_70, 0);
    lv_obj_t *label = lv_obj_get_child(btn, 0);
    if (label != nullptr) {
        lv_obj_set_style_text_opa(label, enabled ? LV_OPA_COVER : LV_OPA_70, 0);
    }
}

void slides_face_style_seg(lv_obj_t *btn, uint32_t ink, bool enabled)
{
    if (btn == nullptr) {
        return;
    }
    lv_obj_t *label = lv_obj_get_child(btn, 0);
    if (label == nullptr) {
        return;
    }
    lv_obj_set_style_text_color(label, lv_color_hex(ink), 0);
    lv_obj_set_style_text_opa(label, enabled ? LV_OPA_COVER : LV_OPA_70, 0);
}

lv_obj_t *slides_face_hit(
    lv_obj_t *parent,
    int32_t x,
    int32_t y,
    int32_t width,
    int32_t height,
    const char *caption,
    SlidesUiAction action,
    lv_event_cb_t on_action,
    uint32_t ink
)
{
    lv_obj_t *btn = lv_obj_create(parent);
    lv_obj_remove_style_all(btn);
    lv_obj_set_pos(btn, x, y);
    lv_obj_set_size(btn, width, height);
    lv_obj_set_style_bg_opa(btn, LV_OPA_TRANSP, 0);
    lv_obj_set_style_pad_all(btn, 0, 0);
    lv_obj_set_style_border_width(btn, 0, 0);
    lv_obj_clear_flag(btn, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_ext_click_area(btn, k_hit_slop);
    lv_obj_add_event_cb(btn, on_action, LV_EVENT_CLICKED, reinterpret_cast<void *>(static_cast<intptr_t>(action)));
    lv_obj_t *label = lv_label_create(btn);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(ink), 0);
    lv_label_set_text(label, caption);
    lv_obj_center(label);
    return btn;
}

void slides_face_slide_thumb(lv_obj_t *thumb, bool deep)
{
    if (thumb == nullptr) {
        return;
    }
    const int32_t x = deep ? (k_seg_w - k_seg_pad - k_seg_thumb_w) : k_seg_pad;
    if (lv_obj_get_x(thumb) != x) {
        lv_obj_set_x(thumb, x);
    }
}

lv_obj_t *slides_face_card(lv_obj_t *parent, int32_t x, int32_t y, int32_t width, int32_t height, int32_t radius)
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

lv_obj_t *slides_face_picker_row(
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
    lv_obj_set_size(row, k_row_w, k_row_h);
    lv_obj_set_style_radius(row, watch_px(10), 0);
    lv_obj_set_style_bg_color(row, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(row, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_hor(row, watch_px(10), 0);
    lv_obj_set_style_clip_corner(row, true, 0);
    if (on_click != nullptr) {
        lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(row, on_click, LV_EVENT_CLICKED, reinterpret_cast<void *>(user));
    }
    lv_obj_t *label = lv_label_create(row);
    lv_obj_set_size(label, k_row_label_w, k_row_label_h);
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

lv_obj_t *slides_face_btn(
    lv_obj_t *parent,
    int32_t x,
    int32_t y,
    int32_t width,
    int32_t height,
    const char *caption,
    SlidesUiAction action,
    lv_event_cb_t on_action,
    uint32_t bg,
    int32_t radius
)
{
    lv_obj_t *btn = slides_face_piece(parent, x, y, width, height, bg, radius);
    lv_obj_add_flag(btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_ext_click_area(btn, k_hit_slop);
    lv_obj_add_event_cb(btn, on_action, LV_EVENT_CLICKED, reinterpret_cast<void *>(static_cast<intptr_t>(action)));
    lv_obj_t *label = lv_label_create(btn);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0xFFFFFF), 0);
    lv_label_set_text(label, caption);
    lv_obj_center(label);
    return btn;
}

SlidesWidgets slides_face_build(lv_obj_t *layer, lv_event_cb_t on_action, lv_event_cb_t on_pick)
{
    SlidesWidgets widgets;
    widgets.root = lv_obj_create(layer);
    lv_obj_remove_style_all(widgets.root);
    lv_obj_set_size(widgets.root, k_face, k_face);
    lv_obj_set_pos(widgets.root, 0, 0);
    lv_obj_set_style_bg_color(widgets.root, lv_color_hex(k_grout), 0);
    lv_obj_set_style_bg_opa(widgets.root, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(widgets.root, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_clip_corner(widgets.root, true, 0);
    lv_obj_clear_flag(widgets.root, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = slides_face_label(
        widgets.root, k_title_x, k_title_y, k_title_w, k_title_h, LV_TEXT_ALIGN_CENTER, k_ink
    );
    lv_label_set_text(title, "演讲模式");

    lv_obj_t *status_row = lv_obj_create(widgets.root);
    lv_obj_remove_style_all(status_row);
    lv_obj_set_pos(status_row, k_status_x, k_status_y);
    lv_obj_set_size(status_row, k_status_w, k_status_h);
    lv_obj_set_flex_flow(status_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(status_row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(status_row, watch_px(6), 0);
    lv_obj_clear_flag(status_row, LV_OBJ_FLAG_SCROLLABLE);
    widgets.online = slides_face_disk(status_row, k_dot, k_wait);
    widgets.status = lv_label_create(status_row);
    lv_obj_set_style_text_align(widgets.status, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(widgets.status, lv_color_hex(k_wait_ink), 0);
    lv_label_set_long_mode(widgets.status, LV_LABEL_LONG_DOT);
    lv_label_set_text(widgets.status, "");

    widgets.seg = slides_face_piece(widgets.root, k_seg_x, k_pad_y, k_seg_w, k_row, k_seg_track, k_row / 2);
    lv_obj_set_style_border_width(widgets.seg, 0, 0);
    widgets.seg_thumb = slides_face_piece(
        widgets.seg, k_seg_pad, k_seg_pad, k_seg_thumb_w, k_seg_thumb_h, k_seg_thumb, k_seg_thumb_h / 2
    );
    lv_obj_set_style_border_width(widgets.seg_thumb, 0, 0);
    widgets.first_level = slides_face_hit(
        widgets.seg, 0, 0, k_seg_hit, k_row, "一级分支", SlidesUiAction::first_level, on_action, k_seg_on_ink
    );
    widgets.deep = slides_face_hit(
        widgets.seg, k_seg_hit, 0, k_seg_hit, k_row, "深度遍历", SlidesUiAction::deep, on_action, k_seg_off_ink
    );
    widgets.prev = slides_face_btn(
        widgets.root, k_inset, k_nav_y, k_col, k_row, "上一页", SlidesUiAction::prev, on_action, k_prev, 0
    );
    widgets.next = slides_face_btn(
        widgets.root, k_mid, k_nav_y, k_col, k_row, "下一页", SlidesUiAction::next, on_action, k_next, 0
    );
    widgets.autoplay = slides_face_btn(
        widgets.root,
        k_inset,
        k_auto_y,
        k_pad_w,
        k_row,
        "自动轮播",
        SlidesUiAction::autoplay,
        on_action,
        k_auto_off,
        0
    );
    widgets.library = slides_face_piece(
        widgets.root, k_lib_x, k_pill_y, k_lib_w, k_pill_h, k_drop, k_pill_r
    );
    lv_obj_add_flag(widgets.library, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(
        widgets.library,
        on_action,
        LV_EVENT_CLICKED,
        reinterpret_cast<void *>(static_cast<intptr_t>(SlidesUiAction::toggle_library))
    );
    widgets.library_label = lv_label_create(widgets.library);
    lv_obj_set_size(widgets.library_label, k_lib_w - watch_px(20), k_label_h);
    lv_obj_set_style_text_align(widgets.library_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(widgets.library_label, lv_color_hex(0xFFFFFF), 0);
    lv_label_set_long_mode(widgets.library_label, LV_LABEL_LONG_DOT);
    lv_obj_center(widgets.library_label);
    lv_label_set_text(widgets.library_label, "图库");

    widgets.host = slides_face_piece(
        widgets.root, k_host_x, k_pill_y, k_host_w, k_pill_h, k_ready, k_pill_r
    );
    lv_obj_add_flag(widgets.host, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(
        widgets.host,
        on_action,
        LV_EVENT_CLICKED,
        reinterpret_cast<void *>(static_cast<intptr_t>(SlidesUiAction::host))
    );
    widgets.host_label = lv_label_create(widgets.host);
    lv_obj_set_style_text_align(widgets.host_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(widgets.host_label, lv_color_hex(0xFFFFFF), 0);
    lv_label_set_text(widgets.host_label, "开始");
    lv_obj_center(widgets.host_label);

    widgets.picker = slides_face_card(
        widgets.root, k_picker_x, k_picker_y, k_picker_w, k_picker_h, k_picker_r
    );
    lv_obj_add_flag(widgets.picker, LV_OBJ_FLAG_HIDDEN);
    widgets.picker_list = lv_obj_create(widgets.picker);
    lv_obj_remove_style_all(widgets.picker_list);
    lv_obj_set_pos(widgets.picker_list, k_list_pad, k_list_pad);
    lv_obj_set_size(widgets.picker_list, k_list_w, k_list_h);
    lv_obj_set_flex_flow(widgets.picker_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(widgets.picker_list, watch_px(6), 0);
    lv_obj_set_scroll_dir(widgets.picker_list, LV_DIR_VER);
    lv_obj_add_flag(widgets.picker_list, LV_OBJ_FLAG_SCROLLABLE);

    slides_face_bubble(widgets.root);
    lv_obj_remove_flag(widgets.picker_list, LV_OBJ_FLAG_GESTURE_BUBBLE);
    (void)on_pick;
    return widgets;
}

void slides_face_paint_picker(
    SlidesWidgets &widgets,
    const SlidesUiSnapshot &snap,
    const lv_font_t *cjk_font,
    uint8_t &painted_list,
    lv_event_cb_t on_pick
)
{
    if (widgets.picker == nullptr || widgets.picker_list == nullptr) {
        return;
    }
    if (!snap.picker_open) {
        lv_obj_add_flag(widgets.picker, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    lv_obj_remove_flag(widgets.picker, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(widgets.picker);
    if (painted_list == snap.list_serial && lv_obj_get_child_count(widgets.picker_list) > 0) {
        return;
    }
    lv_obj_clean(widgets.picker_list);
    if (snap.diagram_count == 0) {
        slides_face_picker_row(
            widgets.picker_list,
            snap.picker_status[0] != '\0' ? snap.picker_status : "图库为空",
            0xF1F5F9,
            0x64748B,
            nullptr,
            0,
            cjk_font
        );
    }
    for (uint8_t i = 0; i < snap.diagram_count; ++i) {
        const std::string caption = kitty_net_diagram_caption(snap.diagrams[i].title, snap.diagrams[i].type);
        slides_face_picker_row(
            widgets.picker_list,
            caption.c_str(),
            0xF1F5F9,
            k_ink,
            on_pick,
            static_cast<intptr_t>(i),
            cjk_font
        );
    }
    painted_list = snap.list_serial;
}

void slides_face_paint(
    SlidesWidgets &widgets,
    const SlidesUiSnapshot &snap,
    const lv_font_t *cjk_font,
    uint8_t &painted_list,
    lv_event_cb_t on_pick
)
{
    char step_line[48] = {};
    if (snap.phase == SlidesUiPhase::live && snap.step_count > 0) {
        std::snprintf(step_line, sizeof(step_line), "%d / %d", snap.step_index + 1, snap.step_count);
    }
    const bool good = snap.phase == SlidesUiPhase::live;
    const char *status = step_line[0] != '\0' ? step_line : (snap.status[0] != '\0' ? snap.status : "请选图库");
    if (widgets.online != nullptr) {
        lv_obj_set_style_bg_color(widgets.online, lv_color_hex(good ? k_online : k_wait), 0);
    }
    if (widgets.status != nullptr) {
        lv_obj_set_style_text_color(widgets.status, lv_color_hex(good ? k_online_ink : k_wait_ink), 0);
        slides_face_set_label(widgets.status, status);
    }
    const bool live = snap.pad_enabled && !snap.busy;
    if (widgets.seg != nullptr) {
        lv_obj_set_style_bg_opa(widgets.seg, live ? LV_OPA_COVER : LV_OPA_70, 0);
    }
    slides_face_slide_thumb(widgets.seg_thumb, snap.deep);
    slides_face_style_seg(widgets.first_level, snap.deep ? k_seg_off_ink : k_seg_on_ink, live);
    slides_face_style_seg(widgets.deep, snap.deep ? k_seg_on_ink : k_seg_off_ink, live);
    slides_face_style_btn(widgets.prev, k_prev, live && snap.can_prev);
    slides_face_style_btn(widgets.next, k_next, live && snap.can_next);
    slides_face_style_btn(widgets.autoplay, snap.autoplay ? k_auto_on : k_auto_off, live);
    slides_face_set_label(
        widgets.library_label, snap.library[0] != '\0' ? snap.library : "图库"
    );
    if (widgets.host != nullptr && widgets.host_label != nullptr) {
        const bool start = snap.phase != SlidesUiPhase::live;
        const bool host_ok = !snap.busy && (start ? snap.library[0] != '\0' : true);
        lv_obj_set_style_bg_color(widgets.host, lv_color_hex(start ? k_ready : k_quit), 0);
        lv_obj_set_style_bg_opa(widgets.host, host_ok ? LV_OPA_COVER : LV_OPA_70, 0);
        lv_obj_set_style_text_opa(widgets.host_label, host_ok ? LV_OPA_COVER : LV_OPA_70, 0);
        slides_face_set_label(widgets.host_label, start ? "开始" : "退出");
    }
    slides_face_paint_picker(widgets, snap, cjk_font, painted_list, on_pick);
}
