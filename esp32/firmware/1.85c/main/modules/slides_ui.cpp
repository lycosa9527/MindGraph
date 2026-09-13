#include "slides_ui.hpp"

#include <cstddef>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include "lvgl.h"
#include "private/utils.hpp"

#include "slides_ui_model.hpp"

namespace {

std::mutex g_mutex;
SlidesUiSnapshot g_model;
SlidesWidgets g_widgets;
lv_timer_t *g_timer = nullptr;
const lv_font_t *g_cjk_font = nullptr;
uint8_t g_painted_list = 0;
bool g_teardown_pending = false;
bool g_have_paint = false;
SlidesUiSnapshot g_last_paint;

void copy_field(char *dest, size_t dest_size, const std::string &src)
{
    if (dest_size == 0) {
        return;
    }
    const size_t n = src.size() < dest_size - 1 ? src.size() : dest_size - 1;
    std::memcpy(dest, src.c_str(), n);
    dest[n] = '\0';
}

void queue_action(SlidesUiAction action)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model.busy) {
        return;
    }
    g_model.pending = action;
}

void on_action(lv_event_t *event)
{
    const auto action = static_cast<SlidesUiAction>(
        reinterpret_cast<intptr_t>(lv_event_get_user_data(event))
    );
    if (action == SlidesUiAction::toggle_library) {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (g_model.busy) {
            return;
        }
        g_model.picker_open = !g_model.picker_open;
        if (g_model.picker_open) {
            g_model.picker_fetch = true;
            copy_field(g_model.picker_status, sizeof(g_model.picker_status), "加载中");
        }
        ++g_model.list_serial;
        return;
    }
    if (action == SlidesUiAction::host) {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (g_model.busy) {
            return;
        }
        const bool start = g_model.phase != SlidesUiPhase::live;
        if (start && g_model.library[0] == '\0') {
            return;
        }
        g_model.pending = action;
        return;
    }
    queue_action(action);
}

void on_pick(lv_event_t *event)
{
    const int index = static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(event)));
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model.busy) {
        return;
    }
    g_model.pending_diagram = index;
    g_model.pending = SlidesUiAction::pick_diagram;
    g_model.picker_open = false;
}

bool paint_unchanged(const SlidesUiSnapshot &snap)
{
    if (!g_have_paint) {
        return false;
    }
    return snap.phase == g_last_paint.phase
        && snap.step_index == g_last_paint.step_index
        && snap.step_count == g_last_paint.step_count
        && snap.can_prev == g_last_paint.can_prev
        && snap.can_next == g_last_paint.can_next
        && snap.autoplay == g_last_paint.autoplay
        && snap.deep == g_last_paint.deep
        && snap.pad_enabled == g_last_paint.pad_enabled
        && snap.busy == g_last_paint.busy
        && snap.picker_open == g_last_paint.picker_open
        && snap.list_serial == g_last_paint.list_serial
        && snap.diagram_count == g_last_paint.diagram_count
        && std::strcmp(snap.status, g_last_paint.status) == 0
        && std::strcmp(snap.library, g_last_paint.library) == 0
        && std::strcmp(snap.picker_status, g_last_paint.picker_status) == 0;
}

void teardown_widgets()
{
    if (g_widgets.root != nullptr && lv_obj_is_valid(g_widgets.root)) {
        lv_obj_delete(g_widgets.root);
    }
    g_widgets = {};
    g_painted_list = 0;
    g_cjk_font = nullptr;
    g_have_paint = false;
    g_last_paint = {};
}

void ensure_widgets()
{
    if (g_widgets.root != nullptr && !lv_obj_is_valid(g_widgets.root)) {
        g_widgets = {};
        g_have_paint = false;
    }
    if (g_widgets.root != nullptr) {
        return;
    }
    lv_obj_t *host = lv_screen_active();
    if (host == nullptr) {
        return;
    }
    g_widgets = slides_face_build(host, on_action, on_pick);
    g_cjk_font = slides_face_find_cjk(host);
    if (g_cjk_font == nullptr) {
        g_cjk_font = slides_face_find_cjk(lv_layer_top());
    }
    if (g_cjk_font != nullptr) {
        slides_face_apply_cjk(g_widgets.root, g_cjk_font);
        BROOKESIA_LOGI("Slides face using Super CJK font");
    }
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
    ensure_widgets();
    if (g_widgets.root == nullptr) {
        return;
    }
    SlidesUiSnapshot snap;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        snap = g_model;
    }
    if (snap.hidden) {
        teardown_widgets();
        return;
    }
    lv_obj_remove_flag(g_widgets.root, LV_OBJ_FLAG_HIDDEN);
    if (paint_unchanged(snap)) {
        return;
    }
    slides_face_paint(g_widgets, snap, g_cjk_font, g_painted_list, on_pick);
    g_last_paint = snap;
    g_have_paint = true;
}

} // namespace

bool slides_ui_start()
{
    if (g_timer != nullptr) {
        return true;
    }
    g_timer = lv_timer_create(tick, 80, nullptr);
    return g_timer != nullptr;
}

void slides_ui_show()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = false;
    g_teardown_pending = false;
}

void slides_ui_hide()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = true;
    g_model.picker_open = false;
    g_model.pending = SlidesUiAction::none;
    g_teardown_pending = true;
}

bool slides_ui_is_hidden()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.hidden;
}

void slides_ui_set_phase(SlidesUiPhase phase)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.phase = phase;
}

void slides_ui_set_status(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.status, sizeof(g_model.status), text);
}

void slides_ui_set_step(int index, int count)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.step_index = index;
    g_model.step_count = count;
}

void slides_ui_set_can_prev(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_prev = enabled;
}

void slides_ui_set_can_next(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_next = enabled;
}

void slides_ui_set_autoplay(bool on)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.autoplay = on;
}

void slides_ui_set_deep(bool deep)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.deep = deep;
}

void slides_ui_set_pad_enabled(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pad_enabled = enabled;
}

void slides_ui_set_busy(bool busy)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.busy = busy;
}

void slides_ui_set_library(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.library, sizeof(g_model.library), text);
}

void slides_ui_set_picker_status(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.picker_status, sizeof(g_model.picker_status), text);
    g_model.picker_fetch = false;
    ++g_model.list_serial;
}

void slides_ui_set_diagrams(const std::vector<SlidesDiagramItem> &items)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.diagram_count = 0;
    const size_t n = items.size() < static_cast<size_t>(k_slides_list_max)
        ? items.size()
        : static_cast<size_t>(k_slides_list_max);
    for (size_t i = 0; i < n; ++i) {
        copy_field(g_model.diagrams[i].id, sizeof(g_model.diagrams[i].id), items[i].id);
        copy_field(g_model.diagrams[i].title, sizeof(g_model.diagrams[i].title), items[i].title);
        copy_field(g_model.diagrams[i].type, sizeof(g_model.diagrams[i].type), items[i].type);
        ++g_model.diagram_count;
    }
    g_model.picker_fetch = false;
    if (g_model.diagram_count == 0) {
        copy_field(g_model.picker_status, sizeof(g_model.picker_status), "图库为空");
    } else {
        g_model.picker_status[0] = '\0';
    }
    ++g_model.list_serial;
}

bool slides_ui_picker_needs_list()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.picker_open && g_model.picker_fetch;
}

SlidesUiAction slides_ui_take_action()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const SlidesUiAction action = g_model.pending;
    g_model.pending = SlidesUiAction::none;
    return action;
}

int slides_ui_take_diagram_index()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const int index = g_model.pending_diagram;
    g_model.pending_diagram = -1;
    return index;
}
