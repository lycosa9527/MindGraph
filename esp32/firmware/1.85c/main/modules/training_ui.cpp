#include "training_ui.hpp"

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include "lvgl.h"
#include "private/utils.hpp"

#include "training_ui_model.hpp"

namespace {

std::mutex g_mutex;
TrainingUiSnapshot g_model;
TrainingWidgets g_widgets;
lv_timer_t *g_timer = nullptr;
const lv_font_t *g_cjk_font = nullptr;
uint8_t g_painted_list = 0;
bool g_teardown_pending = false;

void copy_field(char *dest, size_t dest_size, const std::string &src)
{
    if (dest_size == 0) {
        return;
    }
    const size_t n = src.size() < dest_size - 1 ? src.size() : dest_size - 1;
    std::memcpy(dest, src.c_str(), n);
    dest[n] = '\0';
}

void queue_action(TrainingUiAction action)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model.busy && action != TrainingUiAction::cancel_end) {
        return;
    }
    g_model.pending = action;
}

void on_action(lv_event_t *event)
{
    const auto action = static_cast<TrainingUiAction>(
        reinterpret_cast<intptr_t>(lv_event_get_user_data(event))
    );
    if (action == TrainingUiAction::toggle_dropdown) {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (g_model.busy) {
            return;
        }
        g_model.dropdown_open = !g_model.dropdown_open;
        ++g_model.list_serial;
        return;
    }
    queue_action(action);
}

void on_pick_org(lv_event_t *event)
{
    const int index = static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(event)));
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model.busy) {
        return;
    }
    g_model.pending_org = index;
    g_model.pending = TrainingUiAction::pick_org;
    g_model.dropdown_open = false;
}

void on_pick_course(lv_event_t *event)
{
    const int index = static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(event)));
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model.busy) {
        return;
    }
    g_model.pending_course = index;
    g_model.pending = TrainingUiAction::pick_course;
    g_model.dropdown_open = false;
}

void teardown_widgets()
{
    if (g_widgets.root != nullptr && lv_obj_is_valid(g_widgets.root)) {
        lv_obj_delete(g_widgets.root);
    }
    g_widgets = {};
    g_painted_list = 0;
    g_cjk_font = nullptr;
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
    g_widgets = training_face_build(host, on_action, on_pick_org, on_pick_course);
    g_cjk_font = training_face_find_cjk(host);
    if (g_cjk_font == nullptr) {
        g_cjk_font = training_face_find_cjk(lv_layer_top());
    }
    if (g_cjk_font != nullptr) {
        training_face_apply_cjk(g_widgets.root, g_cjk_font);
        BROOKESIA_LOGI("Training face using Super CJK font");
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
    TrainingUiSnapshot snap;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        snap = g_model;
    }
    if (snap.hidden) {
        teardown_widgets();
        return;
    }
    lv_obj_remove_flag(g_widgets.root, LV_OBJ_FLAG_HIDDEN);
    training_face_paint(
        g_widgets, snap, g_cjk_font, g_painted_list, on_action, on_pick_org, on_pick_course
    );
}

} // namespace

bool training_ui_start()
{
    if (g_timer != nullptr) {
        return true;
    }
    g_timer = lv_timer_create(tick, 80, nullptr);
    return g_timer != nullptr;
}

void training_ui_show()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = false;
    g_teardown_pending = false;
}

void training_ui_hide()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = true;
    g_model.dropdown_open = false;
    g_model.confirm = false;
    g_model.pending = TrainingUiAction::none;
    g_teardown_pending = true;
}

bool training_ui_is_hidden()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.hidden;
}

void training_ui_set_phase(TrainingUiPhase phase)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.phase = phase;
}

void training_ui_set_status(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.status, sizeof(g_model.status), text);
}

void training_ui_set_step(int index, int count)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.step_index = index;
    g_model.step_count = count;
}

void training_ui_set_can_prev(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_prev = enabled;
}

void training_ui_set_can_next(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_next = enabled;
}

void training_ui_set_locked(bool locked)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.locked = locked;
}

void training_ui_set_pad_enabled(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pad_enabled = enabled;
}

void training_ui_set_pill(TrainingHostPill pill)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.pill = pill;
}

void training_ui_set_busy(bool busy)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.busy = busy;
}

void training_ui_set_confirm(bool open)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.confirm = open;
}

void training_ui_set_dropdown_open(bool open)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.dropdown_open = open;
    ++g_model.list_serial;
}

void training_ui_set_dropdown_mode(TrainingDropdownMode mode)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.dropdown_mode = mode;
    ++g_model.list_serial;
}

void training_ui_set_dropdown_label(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.dropdown_label, sizeof(g_model.dropdown_label), text);
}

void training_ui_set_school_name(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.school_name, sizeof(g_model.school_name), text);
    ++g_model.list_serial;
}

void training_ui_set_school_locked(bool locked)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.school_locked = locked;
    ++g_model.list_serial;
}

void training_ui_set_orgs(const std::vector<TrainingOrgItem> &items)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.org_count = 0;
    const size_t n = items.size() < static_cast<size_t>(k_training_list_max)
        ? items.size()
        : static_cast<size_t>(k_training_list_max);
    for (size_t i = 0; i < n; ++i) {
        g_model.orgs[i].org_id = items[i].id;
        copy_field(g_model.orgs[i].title, sizeof(g_model.orgs[i].title), items[i].name);
        ++g_model.org_count;
    }
    ++g_model.list_serial;
}

void training_ui_set_courses(const std::vector<TrainingCourseItem> &items)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.course_count = 0;
    const size_t n = items.size() < static_cast<size_t>(k_training_list_max)
        ? items.size()
        : static_cast<size_t>(k_training_list_max);
    for (size_t i = 0; i < n; ++i) {
        copy_field(g_model.courses[i].id, sizeof(g_model.courses[i].id), items[i].id);
        copy_field(g_model.courses[i].title, sizeof(g_model.courses[i].title), items[i].title);
        ++g_model.course_count;
    }
    ++g_model.list_serial;
}

void training_ui_set_active_course(const std::string &course_id)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.active_course, sizeof(g_model.active_course), course_id);
    ++g_model.list_serial;
}

TrainingUiAction training_ui_take_action()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const TrainingUiAction action = g_model.pending;
    g_model.pending = TrainingUiAction::none;
    return action;
}

int training_ui_take_org_index()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const int index = g_model.pending_org;
    g_model.pending_org = -1;
    return index;
}

int training_ui_take_course_index()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const int index = g_model.pending_course;
    g_model.pending_course = -1;
    return index;
}
