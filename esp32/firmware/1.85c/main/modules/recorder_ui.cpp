#include "recorder_ui.hpp"

#include <cstddef>
#include <cstring>
#include <mutex>
#include <string>

#include "lvgl.h"
#include "private/utils.hpp"

#include "recorder_ui_model.hpp"

namespace {

constexpr uint32_t k_hold_arm_ms = 2500;

std::mutex g_mutex;
RecorderUiSnapshot g_model;
RecorderWidgets g_widgets;
lv_timer_t *g_timer = nullptr;
const lv_font_t *g_cjk_font = nullptr;
bool g_teardown_pending = false;
uint32_t g_hold_since = 0;
RecorderUiAction g_hold_action = RecorderUiAction::none;

void copy_field(char *dest, size_t dest_size, const std::string &src)
{
    if (dest_size == 0) {
        return;
    }
    const size_t n = src.size() < dest_size - 1 ? src.size() : dest_size - 1;
    std::memcpy(dest, src.c_str(), n);
    dest[n] = '\0';
}

void queue_action(RecorderUiAction action)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model.busy && action != RecorderUiAction::stop) {
        return;
    }
    g_model.pending = action;
}

bool hold_allowed(RecorderUiAction action)
{
    if (action == RecorderUiAction::pause) {
        return g_model.can_pause && !g_model.busy;
    }
    if (action == RecorderUiAction::stop) {
        return g_model.can_stop;
    }
    return false;
}

void clear_hold_arm()
{
    g_hold_since = 0;
    g_hold_action = RecorderUiAction::none;
}

void on_action(lv_event_t *event)
{
    const auto action = static_cast<RecorderUiAction>(
        reinterpret_cast<intptr_t>(lv_event_get_user_data(event))
    );
    if (action == RecorderUiAction::pause || action == RecorderUiAction::stop) {
        return;
    }
    if (action == RecorderUiAction::start) {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (g_model.can_pause) {
            return;
        }
    }
    queue_action(action);
}

void on_confirm_hold(lv_event_t *event)
{
    const auto action = static_cast<RecorderUiAction>(
        reinterpret_cast<intptr_t>(lv_event_get_user_data(event))
    );
    const lv_event_code_t code = lv_event_get_code(event);
    if (code == LV_EVENT_PRESSED) {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (!hold_allowed(action)) {
            clear_hold_arm();
            return;
        }
        g_hold_since = lv_tick_get();
        g_hold_action = action;
        return;
    }
    if (code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST) {
        if (g_hold_action == action) {
            clear_hold_arm();
        }
    }
}

void poll_hold_arm()
{
    if (g_hold_since == 0) {
        return;
    }
    const RecorderUiAction action = g_hold_action;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (!hold_allowed(action)) {
            clear_hold_arm();
            return;
        }
    }
    if (lv_tick_elaps(g_hold_since) < k_hold_arm_ms) {
        return;
    }
    clear_hold_arm();
    queue_action(action);
}

void bind_hold(lv_obj_t *btn, RecorderUiAction action)
{
    if (btn == nullptr) {
        return;
    }
    void *data = reinterpret_cast<void *>(static_cast<intptr_t>(action));
    lv_obj_add_event_cb(btn, on_confirm_hold, LV_EVENT_PRESSED, data);
    lv_obj_add_event_cb(btn, on_confirm_hold, LV_EVENT_RELEASED, data);
    lv_obj_add_event_cb(btn, on_confirm_hold, LV_EVENT_PRESS_LOST, data);
}

void teardown_widgets()
{
    if (g_widgets.root != nullptr && lv_obj_is_valid(g_widgets.root)) {
        lv_obj_delete(g_widgets.root);
    }
    g_widgets = {};
    g_cjk_font = nullptr;
    clear_hold_arm();
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
    g_widgets = recorder_face_build(host, on_action);
    bind_hold(g_widgets.pause, RecorderUiAction::pause);
    bind_hold(g_widgets.stop, RecorderUiAction::stop);
    g_cjk_font = recorder_face_find_cjk(host);
    if (g_cjk_font == nullptr) {
        g_cjk_font = recorder_face_find_cjk(lv_layer_top());
    }
    if (g_cjk_font != nullptr) {
        recorder_face_apply_cjk(g_widgets.root, g_cjk_font);
        BROOKESIA_LOGI("Recorder face using Super CJK font");
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
    poll_hold_arm();
    RecorderUiSnapshot snap;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        snap = g_model;
    }
    if (g_hold_since != 0) {
        const uint32_t held = lv_tick_elaps(g_hold_since);
        snap.hold_action = g_hold_action;
        if (held >= k_hold_arm_ms) {
            snap.hold_progress = 100;
        } else {
            snap.hold_progress = static_cast<uint8_t>((held * 100U) / k_hold_arm_ms);
        }
    } else {
        snap.hold_progress = 0;
        snap.hold_action = RecorderUiAction::none;
    }
    if (snap.hidden) {
        teardown_widgets();
        return;
    }
    lv_obj_remove_flag(g_widgets.root, LV_OBJ_FLAG_HIDDEN);
    recorder_face_paint(g_widgets, snap);
}

} // namespace

bool recorder_ui_start()
{
    if (g_timer != nullptr) {
        return true;
    }
    g_timer = lv_timer_create(tick, 80, nullptr);
    return g_timer != nullptr;
}

void recorder_ui_show()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = false;
    g_teardown_pending = false;
}

void recorder_ui_hide()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.hidden = true;
    g_model.pending = RecorderUiAction::none;
    clear_hold_arm();
    g_teardown_pending = true;
}

bool recorder_ui_is_hidden()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model.hidden;
}

void recorder_ui_set_phase(RecorderUiPhase phase)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.phase = phase;
}

void recorder_ui_set_status(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.status, sizeof(g_model.status), text);
}

void recorder_ui_set_elapsed(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.elapsed, sizeof(g_model.elapsed), text);
}

void recorder_ui_set_transcript(const std::string &text)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    copy_field(g_model.transcript, sizeof(g_model.transcript), text);
}

void recorder_ui_set_mic_level(uint8_t level)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.mic_level = level;
}

void recorder_ui_set_can_start(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_start = enabled;
}

void recorder_ui_set_can_pause(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_pause = enabled;
}

void recorder_ui_set_can_resume(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_resume = enabled;
}

void recorder_ui_set_can_stop(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_stop = enabled;
}

void recorder_ui_set_can_generate(bool enabled)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.can_generate = enabled;
}

void recorder_ui_set_busy(bool busy)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_model.busy = busy;
}

RecorderUiAction recorder_ui_take_action()
{
    std::lock_guard<std::mutex> lock(g_mutex);
    const RecorderUiAction action = g_model.pending;
    g_model.pending = RecorderUiAction::none;
    return action;
}
