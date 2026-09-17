#include "super_kitty_ui.hpp"

#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include "lvgl.h"
#include "private/utils.hpp"

#include "kitty_ui_work_ring.hpp"
#include "super_kitty_ui_widgets.hpp"
#include "watch_face.hpp"

namespace {

constexpr uint32_t k_violet = 0x7C3AED;
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
    bool pending_focus = false;
    char pending_focus_id[40] = {};
    char pending_focus_title[64] = {};
    char pending_focus_type[24] = {};
    bool picker = false;
    bool picker_fetch = false;
    bool hidden = true;
    bool click = false;
};

std::mutex g_mutex;
UiSnapshot g_model;
std::atomic<bool> g_face_ready{false};
bool g_teardown_pending = false;
SuperKittyWidgets g_widgets;
lv_timer_t *g_timer = nullptr;
const lv_font_t *g_cjk_font = nullptr;
uint8_t g_painted_pick = 0;
bool g_have_live_color = false;
bool g_live_online = false;
bool g_lib_down = false;
bool g_block_home = false;

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
        return "说你好kitty";
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

void queue_click()
{
    g_model.click = true;
}

void swallow_press()
{
    lv_indev_t *indev = lv_indev_active();
    if (indev != nullptr) {
        lv_indev_wait_release(indev);
    }
}

void set_picker(bool open)
{
    g_model.picker = open;
    g_model.picker_fetch = open;
    if (open) {
        copy_field(g_model.picker_status, sizeof(g_model.picker_status), "加载中");
        if (g_model.pick_count == 0) {
            ++g_model.pick_serial;
        }
    }
    queue_click();
    BROOKESIA_LOGI("Super Kitty library picker %s", open ? "open" : "close");
}

void on_library(lv_event_t *event)
{
    if (event == nullptr || lv_event_get_code(event) != LV_EVENT_PRESSED) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_lib_down) {
        return;
    }
    g_lib_down = true;
    swallow_press();
    set_picker(!g_model.picker);
}

bool hit_obj(lv_obj_t *obj, const lv_point_t *point)
{
    return obj != nullptr && lv_obj_is_valid(obj) && lv_obj_hit_test(obj, point);
}

void poll_library()
{
    if (g_widgets.root == nullptr || lv_obj_has_flag(g_widgets.root, LV_OBJ_FLAG_HIDDEN)) {
        g_block_home = false;
        g_lib_down = false;
        return;
    }
    lv_indev_t *indev = lv_indev_get_next(nullptr);
    bool saw_pointer = false;
    while (indev != nullptr) {
        if (lv_indev_get_type(indev) == LV_INDEV_TYPE_POINTER) {
            saw_pointer = true;
            lv_point_t point{};
            lv_indev_get_point(indev, &point);
            const bool pressed = lv_indev_get_state(indev) == LV_INDEV_STATE_PRESSED;
            const bool on_chrome = hit_obj(g_widgets.library, &point)
                || hit_obj(g_widgets.picker, &point)
                || hit_obj(g_widgets.picker_list, &point);
            std::lock_guard<std::mutex> lock(g_mutex);
            g_block_home = on_chrome || g_model.picker;
            if (pressed && on_chrome && hit_obj(g_widgets.library, &point) && !g_lib_down) {
                g_lib_down = true;
                swallow_press();
                set_picker(!g_model.picker);
            } else if (!pressed) {
                g_lib_down = false;
            }
        }
        indev = lv_indev_get_next(indev);
    }
    if (!saw_pointer) {
        g_block_home = false;
        g_lib_down = false;
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
    swallow_press();
    set_picker(false);
}

void on_create_mindmap(lv_event_t *event)
{
    (void)event;
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pending_create = true;
    swallow_press();
    set_picker(false);
}

void hide_face()
{
    g_model.hidden = true;
    g_model.picker = false;
    g_model.picker_fetch = false;
    g_model.pending_create = false;
    g_model.pending_pick = -1;
    g_model.pending_choice = 0;
    g_model.pending_focus = false;
    g_model.pending_focus_id[0] = '\0';
    g_model.pending_focus_title[0] = '\0';
    g_model.pending_focus_type[0] = '\0';
    g_model.click = false;
    g_teardown_pending = true;
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
    lv_obj_set_size(row, watch_px(264), watch_px(40));
    lv_obj_set_style_radius(row, watch_px(12), 0);
    lv_obj_set_style_bg_color(row, lv_color_hex(bg), 0);
    lv_obj_set_style_bg_opa(row, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_hor(row, watch_px(10), 0);
    lv_obj_set_style_clip_corner(row, true, 0);
    if (on_click != nullptr) {
        lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(row, on_click, LV_EVENT_CLICKED, reinterpret_cast<void *>(user));
    }
    lv_obj_add_flag(row, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_t *label = lv_label_create(row);
    lv_obj_set_size(label, watch_px(240), watch_px(32));
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
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
    super_kitty_ui_picker_present(g_widgets, snap.picker);
    if (!snap.picker) {
        if (lv_obj_get_child_count(g_widgets.picker_list) > 0) {
            lv_obj_clean(g_widgets.picker_list);
        }
        g_painted_pick = 0;
        return;
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
    g_have_live_color = false;
    g_face_ready.store(false);
}

bool ensure_widgets()
{
    lv_obj_t *host = lv_screen_active();
    if (g_widgets.root != nullptr && lv_obj_is_valid(g_widgets.root)) {
        if (host != nullptr && lv_obj_get_parent(g_widgets.root) != host) {
            teardown_widgets();
        }
    }
    if (g_widgets.root != nullptr && !lv_obj_is_valid(g_widgets.root)) {
        g_widgets = {};
        g_painted_pick = 0;
        g_cjk_font = nullptr;
        g_face_ready.store(false);
    }
    if (g_widgets.root != nullptr) {
        return false;
    }
    if (host == nullptr) {
        return false;
    }
    g_widgets = super_kitty_ui_build(host, on_library, on_choice);
    g_cjk_font = find_cjk_font(host);
    if (g_cjk_font == nullptr) {
        g_cjk_font = find_cjk_font(lv_layer_top());
    }
    if (g_cjk_font != nullptr) {
        apply_cjk_font(g_widgets.root, g_cjk_font);
        BROOKESIA_LOGI("Super Kitty face using Super CJK font");
    } else {
        BROOKESIA_LOGW("Super Kitty face has no Super CJK font");
    }
    BROOKESIA_LOGI("Super Kitty Super app face ready");
    g_face_ready.store(true);
    return true;
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
    const bool created = ensure_widgets();
    if (g_widgets.root == nullptr) {
        return;
    }
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
    lv_obj_move_foreground(g_widgets.root);
    if (g_widgets.library != nullptr) {
        lv_obj_move_foreground(g_widgets.library);
    }
    (void)created;
    poll_library();
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
        if (!g_have_live_color || g_live_online != online) {
            lv_obj_set_style_text_color(
                g_widgets.live,
                lv_color_hex(online ? 0x15803D : 0x64748B),
                0
            );
            g_live_online = online;
            g_have_live_color = true;
        }
    }
    set_label_if_changed(
        g_widgets.library_label,
        snap.library[0] != '\0' ? snap.library : "图库"
    );
    paint_picker(snap);
    if (!snap.picker) {
        if (g_widgets.user != nullptr) {
            if (snap.user[0] == '\0') {
                lv_obj_add_flag(g_widgets.user, LV_OBJ_FLAG_HIDDEN);
            } else {
                lv_obj_remove_flag(g_widgets.user, LV_OBJ_FLAG_HIDDEN);
                set_label_if_changed(g_widgets.user, snap.user);
            }
        }
        if (g_widgets.kitty != nullptr) {
            if (snap.kitty[0] == '\0') {
                lv_obj_add_flag(g_widgets.kitty, LV_OBJ_FLAG_HIDDEN);
            } else {
                lv_obj_remove_flag(g_widgets.kitty, LV_OBJ_FLAG_HIDDEN);
                set_label_if_changed(g_widgets.kitty, snap.kitty);
            }
        }
        for (int i = 0; i < 4; ++i) {
            set_choice_chip(g_widgets.choices[i], snap.choices[i]);
        }
        if (g_widgets.choice_grid != nullptr
            && (snap.choices[0][0] != '\0' || snap.choices[1][0] != '\0'
                || snap.choices[2][0] != '\0' || snap.choices[3][0] != '\0')) {
            lv_obj_move_foreground(g_widgets.choice_grid);
        }
    }
    kitty_ui_work_ring_paint(g_widgets.work_ring, snap.state);
}

} // namespace

bool super_kitty_ui_start()
{
    if (g_timer != nullptr) {
        return true;
    }
    g_timer = lv_timer_create(tick, 80, nullptr);
    return g_timer != nullptr;
}

void super_kitty_ui_set_state(KittyUiState state)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.state = state;
    g_model.live[0] = '\0';
}

void super_kitty_ui_set_live(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.live, sizeof(g_model.live), text);
}

void super_kitty_ui_set_user_text(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.user, sizeof(g_model.user), text);
}

void super_kitty_ui_set_kitty_text(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.kitty, sizeof(g_model.kitty), text);
}

void super_kitty_ui_set_choice(int index, const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (index < 1 || index > 4) {
        return;
    }
    copy_field(g_model.choices[index - 1], sizeof(g_model.choices[index - 1]), text);
}

void super_kitty_ui_begin_user_turn()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.user[0] = '\0';
    g_model.kitty[0] = '\0';
    for (auto &choice : g_model.choices) {
        choice[0] = '\0';
    }
}

void super_kitty_ui_set_library(const std::string &title)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.library, sizeof(g_model.library), title);
}

void super_kitty_ui_set_listen_level(uint8_t level)
{
    (void)level;
}

void super_kitty_ui_set_diagrams(const std::vector<KittyDiagramItem> &items)
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

void super_kitty_ui_set_picker_status(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.picker_status, sizeof(g_model.picker_status), text);
    g_model.picker_fetch = false;
    ++g_model.pick_serial;
}

bool super_kitty_ui_picker_needs_list()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.picker && g_model.picker_fetch;
}

bool super_kitty_ui_take_diagram_pick(KittyDiagramItem &item)
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

bool super_kitty_ui_take_create_mindmap()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const bool pending = g_model.pending_create;
    g_model.pending_create = false;
    return pending;
}

void super_kitty_ui_queue_desktop_focus(const KittyDiagramItem &item)
{
    if (item.id.size() >= sizeof(UiSnapshot::pending_focus_id)) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.pending_focus_id, sizeof(g_model.pending_focus_id), item.id);
    copy_field(g_model.pending_focus_title, sizeof(g_model.pending_focus_title), item.title);
    copy_field(g_model.pending_focus_type, sizeof(g_model.pending_focus_type), item.type);
    g_model.pending_focus = true;
}

bool super_kitty_ui_take_desktop_focus(KittyDiagramItem &item)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_model.pending_focus) {
        return false;
    }
    item.id = g_model.pending_focus_id;
    item.title = g_model.pending_focus_title;
    item.type = g_model.pending_focus_type;
    g_model.pending_focus = false;
    g_model.pending_focus_id[0] = '\0';
    g_model.pending_focus_title[0] = '\0';
    g_model.pending_focus_type[0] = '\0';
    return true;
}

void super_kitty_ui_clear_desktop_focus()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pending_focus = false;
    g_model.pending_focus_id[0] = '\0';
    g_model.pending_focus_title[0] = '\0';
    g_model.pending_focus_type[0] = '\0';
}

int super_kitty_ui_take_choice()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const int choice = g_model.pending_choice;
    g_model.pending_choice = 0;
    return choice;
}

bool super_kitty_ui_take_click()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const bool click = g_model.click;
    g_model.click = false;
    return click;
}

bool super_kitty_ui_is_hidden()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.hidden;
}

bool super_kitty_ui_blocks_home()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return !g_model.hidden && (g_block_home || g_model.picker);
}

bool super_kitty_ui_face_ready()
{
    return g_face_ready.load();
}

void super_kitty_ui_show()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = false;
    g_teardown_pending = false;
}

void super_kitty_ui_hide()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    hide_face();
}
