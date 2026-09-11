#include "kitty_ui.hpp"

#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include "lvgl.h"
#include "private/utils.hpp"

#include "kitty_ptt_button.hpp"
#include "kitty_ui_mascot.hpp"
#include "kitty_ui_widgets.hpp"
#include "kitty_ui_work_ring.hpp"

namespace {

constexpr uint32_t k_violet = 0x7C3AED;
constexpr uint32_t k_violet_hold = 0x4F46E5;
constexpr uint32_t k_ink = 0x0F172A;
constexpr int k_pick_max = 12;

struct PickRow {
    char id[40] = {};
    char title[64] = {};
    char type[24] = {};
};

struct UiSnapshot {
    KittyUiState state = KittyUiState::connecting;
    char live[40] = {};
    char user[96] = {};
    char kitty[96] = {};
    char choices[4][48] = {};
    char library[80] = {};
    char picker_status[40] = {};
    PickRow picks[k_pick_max] = {};
    uint8_t pick_count = 0;
    uint8_t pick_serial = 0;
    int pending_choice = 0;
    int pending_pick = -1;
    bool pending_create = false;
    bool hold = false;
    bool picker = false;
    bool picker_fetch = false;
    bool hidden = true;
    bool click = false;
    uint8_t mic_level = 0;
};

std::mutex g_mutex;
UiSnapshot g_model;
bool g_teardown_pending = false;
KittyWidgets g_widgets;
lv_timer_t *g_timer = nullptr;
const lv_font_t *g_cjk_font = nullptr;
uint8_t g_painted_pick = 0;
bool g_hold_down = false;
bool g_touch_hold = false;
bool g_boot_hold = false;

void copy_field(char *dest, size_t dest_size, const std::string &src)
{
    if (dest_size == 0) {
        return;
    }
    const size_t n = src.size() < dest_size - 1 ? src.size() : dest_size - 1;
    std::memcpy(dest, src.c_str(), n);
    dest[n] = '\0';
}

bool is_online_state(const UiSnapshot &snap)
{
    if (snap.state == KittyUiState::connecting || snap.state == KittyUiState::error) {
        return false;
    }
    return std::strcmp(snap.live, "重连中") != 0;
}

const char *live_for(const UiSnapshot &snap)
{
    if (snap.live[0] != '\0') {
        return snap.live;
    }
    switch (snap.state) {
    case KittyUiState::listening:
        return "聆听中";
    case KittyUiState::thinking:
        return "思考中";
    case KittyUiState::speaking:
        return "说话中";
    case KittyUiState::error:
        return "出错了";
    case KittyUiState::connecting:
        return "连接中";
    default:
        return "在线";
    }
}

void set_choice_chip(lv_obj_t *chip, const char *text)
{
    if (chip == nullptr) {
        return;
    }
    lv_obj_t *label = lv_obj_get_child(chip, 0);
    if (text == nullptr || text[0] == '\0') {
        lv_obj_add_flag(chip, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    if (label != nullptr) {
        lv_label_set_text(label, text);
    }
    lv_obj_remove_flag(chip, LV_OBJ_FLAG_HIDDEN);
}

void set_hold(bool hold)
{
    if (g_hold_down == hold && g_model.hold == hold) {
        return;
    }
    g_model.hold = hold;
    g_hold_down = hold;
    if (!hold) {
        g_model.mic_level = 0;
        BROOKESIA_LOGI("Kitty mic hold end");
        return;
    }
    g_model.click = true;
    BROOKESIA_LOGI("Kitty mic hold start");
}

void sync_hold()
{
    set_hold(g_touch_hold || g_boot_hold);
}

void poll_boot_hold()
{
    if (g_model.hidden) {
        return;
    }
    const bool boot = kitty_ptt_button_held();
    if (boot == g_boot_hold) {
        return;
    }
    g_boot_hold = boot;
    sync_hold();
}

void on_hold(lv_event_t *event)
{
    const lv_event_code_t code = lv_event_get_code(event);
    std::lock_guard<std::mutex> lock(g_mutex);
    if (code == LV_EVENT_PRESSED) {
        g_touch_hold = true;
        sync_hold();
        return;
    }
    if (code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST) {
        g_touch_hold = false;
        sync_hold();
    }
}

void queue_click()
{
    g_model.click = true;
}

void on_library(lv_event_t *event)
{
    (void)event;
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.picker = !g_model.picker;
    queue_click();
    if (g_model.picker) {
        g_model.picker_fetch = true;
        copy_field(g_model.picker_status, sizeof(g_model.picker_status), "加载中");
        if (g_model.pick_count == 0) {
            ++g_model.pick_serial;
        }
    }
}

void on_choice(lv_event_t *event)
{
    const auto index = static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(event)));
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pending_choice = index;
    queue_click();
}

void on_pick_row(lv_event_t *event)
{
    const auto index = static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(event)));
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pending_pick = index;
    g_model.picker = false;
    queue_click();
}

void on_create_mindmap(lv_event_t *event)
{
    (void)event;
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pending_create = true;
    g_model.picker = false;
    queue_click();
}

void hide_face()
{
    g_model.hidden = true;
    g_model.picker = false;
    g_model.pending_create = false;
    g_model.hold = false;
    g_model.click = false;
    g_hold_down = false;
    g_touch_hold = false;
    g_boot_hold = false;
    g_teardown_pending = true;
}

void poll_pointer()
{
    if (g_widgets.root == nullptr || lv_obj_has_flag(g_widgets.root, LV_OBJ_FLAG_HIDDEN)) {
        return;
    }
    lv_indev_t *indev = lv_indev_get_next(nullptr);
    while (indev != nullptr) {
        if (lv_indev_get_type(indev) == LV_INDEV_TYPE_POINTER) {
            lv_point_t point;
            lv_indev_get_point(indev, &point);
            const bool pressed = lv_indev_get_state(indev) == LV_INDEV_STATE_PRESSED;
            const bool on_mic = pressed
                && g_widgets.mic != nullptr
                && lv_obj_is_valid(g_widgets.mic)
                && lv_obj_hit_test(g_widgets.mic, &point);
            std::lock_guard<std::mutex> lock(g_mutex);
            if (on_mic) {
                g_touch_hold = true;
                sync_hold();
            } else if (!pressed) {
                g_touch_hold = false;
                sync_hold();
            }
        }
        indev = lv_indev_get_next(indev);
    }
}

void set_label_if_changed(lv_obj_t *label, const char *text)
{
    if (label == nullptr || text == nullptr) {
        return;
    }
    const char *cur = lv_label_get_text(label);
    if (cur != nullptr && std::strcmp(cur, text) == 0) {
        return;
    }
    lv_label_set_text(label, text);
}

bool is_stock_font(const lv_font_t *font)
{
    if (font == nullptr || font == LV_FONT_DEFAULT) {
        return true;
    }
    return font == &lv_font_montserrat_8
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

const lv_font_t *find_cjk_font(lv_obj_t *node)
{
    if (node == nullptr) {
        return nullptr;
    }
    const lv_font_t *font = lv_obj_get_style_text_font(node, LV_PART_MAIN);
    if (!is_stock_font(font)) {
        return font;
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        const lv_font_t *found = find_cjk_font(lv_obj_get_child(node, i));
        if (found != nullptr) {
            return found;
        }
    }
    return nullptr;
}

void apply_cjk_font(lv_obj_t *node, const lv_font_t *font)
{
    if (node == nullptr || font == nullptr) {
        return;
    }
    if (lv_obj_has_class(node, &lv_label_class)) {
        lv_obj_set_style_text_font(node, font, 0);
    }
    const uint32_t count = lv_obj_get_child_count(node);
    for (uint32_t i = 0; i < count; ++i) {
        apply_cjk_font(lv_obj_get_child(node, i), font);
    }
}

lv_obj_t *add_picker_row(
    const char *caption,
    uint32_t bg,
    uint32_t fg,
    lv_event_cb_t on_click,
    intptr_t user
)
{
    lv_obj_t *row = lv_obj_create(g_widgets.picker_list);
    lv_obj_remove_style_all(row);
    lv_obj_set_size(row, 264, 40);
    lv_obj_set_style_radius(row, 12, 0);
    lv_obj_set_style_bg_color(row, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(row, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_hor(row, 10, 0);
    lv_obj_set_style_clip_corner(row, true, 0);
    if (on_click != nullptr) {
        lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(row, on_click, LV_EVENT_CLICKED, reinterpret_cast<void *>(user));
    }
    lv_obj_add_flag(row, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_t *label = lv_label_create(row);
    lv_obj_set_size(label, 240, 32);
    lv_label_set_long_mode(label, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_anim_duration(label, lv_anim_speed_clamped(14, 3000, 10000), 0);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_LEFT, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(fg), 0);
    lv_label_set_text(label, caption);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 0, 0);
    if (g_cjk_font != nullptr) {
        lv_obj_set_style_text_font(label, g_cjk_font, 0);
    }
    return row;
}

void paint_picker(const UiSnapshot &snap)
{
    if (g_widgets.picker == nullptr || g_widgets.picker_list == nullptr) {
        return;
    }
    if (!snap.picker) {
        lv_obj_add_flag(g_widgets.picker, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    lv_obj_remove_flag(g_widgets.picker, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(g_widgets.picker);
    if (g_widgets.picker_row != nullptr) {
        lv_obj_add_flag(g_widgets.picker_row, LV_OBJ_FLAG_HIDDEN);
    }
    if (g_painted_pick == snap.pick_serial && lv_obj_get_child_count(g_widgets.picker_list) > 0) {
        return;
    }
    lv_obj_clean(g_widgets.picker_list);
    add_picker_row("新建思维导图", k_violet, 0xFFFFFF, on_create_mindmap, 0);
    if (snap.pick_count == 0) {
        add_picker_row(
            snap.picker_status[0] != '\0' ? snap.picker_status : "图库为空",
            0xF1F5F9,
            0x64748B,
            nullptr,
            0
        );
    }
    for (uint8_t i = 0; i < snap.pick_count; ++i) {
        const std::string caption = kitty_net_diagram_caption(snap.picks[i].title, snap.picks[i].type);
        add_picker_row(caption.c_str(), 0xF1F5F9, k_ink, on_pick_row, static_cast<intptr_t>(i));
    }
    g_painted_pick = snap.pick_serial;
}

void teardown_widgets()
{
    if (g_widgets.root != nullptr && lv_obj_is_valid(g_widgets.root)) {
        lv_obj_delete(g_widgets.root);
    }
    g_widgets = {};
    g_painted_pick = 0;
    g_cjk_font = nullptr;
    g_hold_down = false;
    g_touch_hold = false;
}

void ensure_widgets()
{
    if (g_widgets.root != nullptr) {
        return;
    }
    lv_obj_t *host = lv_screen_active();
    if (host == nullptr) {
        return;
    }
    g_widgets = kitty_ui_build(host, on_hold, on_library, on_choice);
    g_cjk_font = find_cjk_font(host);
    if (g_cjk_font == nullptr) {
        g_cjk_font = find_cjk_font(lv_layer_top());
    }
    if (g_cjk_font != nullptr) {
        apply_cjk_font(g_widgets.root, g_cjk_font);
        BROOKESIA_LOGI("Kitty face using Super CJK font");
    } else {
        BROOKESIA_LOGW("Kitty face has no Super CJK font");
    }
    BROOKESIA_LOGI("Kitty Super app face ready");
}

void tick(lv_timer_t *timer)
{
    (void)timer;
    bool hidden = true;
    bool teardown = false;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        hidden = g_model.hidden;
        teardown = g_teardown_pending;
        g_teardown_pending = false;
    }
    if (hidden || teardown) {
        teardown_widgets();
        return;
    }
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        poll_boot_hold();
    }
    ensure_widgets();
    if (g_widgets.root == nullptr) {
        return;
    }
    poll_pointer();
    UiSnapshot snap;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        snap = g_model;
    }
    if (snap.hidden) {
        teardown_widgets();
        return;
    }
    lv_obj_remove_flag(g_widgets.root, LV_OBJ_FLAG_HIDDEN);
    const bool online = is_online_state(snap);
    if (g_widgets.online != nullptr) {
        if (online) {
            lv_obj_remove_flag(g_widgets.online, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(g_widgets.online, LV_OBJ_FLAG_HIDDEN);
        }
    }
    if (g_widgets.live != nullptr) {
        set_label_if_changed(g_widgets.live, live_for(snap));
        lv_obj_set_style_text_color(
            g_widgets.live,
            lv_color_hex(online ? 0x15803D : 0x64748B),
            0
        );
    }
    set_label_if_changed(g_widgets.user, snap.user);
    set_label_if_changed(g_widgets.kitty, snap.kitty);
    for (int i = 0; i < 4; ++i) {
        set_choice_chip(g_widgets.choices[i], snap.choices[i]);
    }
    if (g_widgets.choice_grid != nullptr && !snap.picker
        && (snap.choices[0][0] != '\0' || snap.choices[1][0] != '\0'
            || snap.choices[2][0] != '\0' || snap.choices[3][0] != '\0')) {
        lv_obj_move_foreground(g_widgets.choice_grid);
    }
    set_label_if_changed(
        g_widgets.library_label,
        snap.library[0] != '\0' ? snap.library : "图库"
    );
    paint_picker(snap);
    kitty_ui_work_ring_paint(g_widgets.work_ring, snap.state);
    kitty_ui_mascot_tick(snap.state);
    if (g_widgets.mic != nullptr) {
        lv_obj_set_style_bg_color(
            g_widgets.mic,
            lv_color_hex(g_hold_down ? k_violet_hold : k_violet),
            0
        );
        uint8_t level = snap.mic_level;
        if (g_hold_down && level < 24) {
            level = static_cast<uint8_t>(24 + (lv_tick_get() / 80) % 80);
        }
        kitty_ui_mic_paint(g_widgets.mic, g_widgets.mic_ring_a, g_widgets.mic_ring_b, g_hold_down, level);
    }
}

} // namespace

bool kitty_ui_start()
{
    if (g_timer != nullptr) {
        return true;
    }
    kitty_ptt_button_init();
    g_timer = lv_timer_create(tick, 80, nullptr);
    return g_timer != nullptr;
}

void kitty_ui_set_state(KittyUiState state)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.state = state;
    g_model.live[0] = '\0';
}

void kitty_ui_set_live(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.live, sizeof(g_model.live), text);
}

void kitty_ui_set_user_text(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.user, sizeof(g_model.user), text);
}

void kitty_ui_set_kitty_text(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.kitty, sizeof(g_model.kitty), text);
}

void kitty_ui_set_choice(int index, const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (index < 1 || index > 4) {
        return;
    }
    copy_field(g_model.choices[index - 1], sizeof(g_model.choices[index - 1]), text);
}

void kitty_ui_begin_user_turn()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.user[0] = '\0';
    g_model.kitty[0] = '\0';
    for (auto &choice : g_model.choices) {
        choice[0] = '\0';
    }
}

void kitty_ui_set_library(const std::string &title)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.library, sizeof(g_model.library), title);
}

void kitty_ui_set_mic_level(uint8_t level)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.mic_level = level;
}

void kitty_ui_set_diagrams(const std::vector<KittyDiagramItem> &items)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pick_count = 0;
    const size_t n = items.size() < static_cast<size_t>(k_pick_max) ? items.size() : static_cast<size_t>(k_pick_max);
    for (size_t i = 0; i < n; ++i) {
        copy_field(g_model.picks[i].id, sizeof(g_model.picks[i].id), items[i].id);
        copy_field(g_model.picks[i].title, sizeof(g_model.picks[i].title), items[i].title);
        copy_field(g_model.picks[i].type, sizeof(g_model.picks[i].type), items[i].type);
        ++g_model.pick_count;
    }
    ++g_model.pick_serial;
    g_model.picker_fetch = false;
    if (g_model.pick_count == 0) {
        copy_field(g_model.picker_status, sizeof(g_model.picker_status), "图库为空");
    } else {
        g_model.picker_status[0] = '\0';
    }
}

void kitty_ui_set_picker_status(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.picker_status, sizeof(g_model.picker_status), text);
    g_model.picker_fetch = false;
    ++g_model.pick_serial;
}

bool kitty_ui_picker_needs_list()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.picker && g_model.picker_fetch;
}

bool kitty_ui_take_diagram_pick(KittyDiagramItem &item)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model.pending_pick < 0 || g_model.pending_pick >= static_cast<int>(g_model.pick_count)) {
        g_model.pending_pick = -1;
        return false;
    }
    item.id = g_model.picks[g_model.pending_pick].id;
    item.title = g_model.picks[g_model.pending_pick].title;
    item.type = g_model.picks[g_model.pending_pick].type;
    g_model.pending_pick = -1;
    return !item.id.empty();
}

bool kitty_ui_take_create_mindmap()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const bool pending = g_model.pending_create;
    g_model.pending_create = false;
    return pending;
}

bool kitty_ui_hold_active()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    poll_boot_hold();
    return g_model.hold;
}

void kitty_ui_clear_hold()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_hold_down) {
        g_model.hold = false;
        g_model.mic_level = 0;
    }
}

int kitty_ui_take_choice()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const int choice = g_model.pending_choice;
    g_model.pending_choice = 0;
    return choice;
}

bool kitty_ui_take_click()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const bool click = g_model.click;
    g_model.click = false;
    return click;
}

bool kitty_ui_is_hidden()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.hidden;
}

void kitty_ui_show()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = false;
    g_teardown_pending = false;
}

void kitty_ui_hide()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    hide_face();
}
