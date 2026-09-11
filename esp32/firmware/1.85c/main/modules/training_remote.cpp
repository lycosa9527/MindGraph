#include "training_remote.hpp"

#include <atomic>
#include <ctime>
#include <string>
#include <vector>

#include "boost/chrono.hpp"
#include "boost/thread.hpp"
#include "esp_log.h"
#include "esp_netif.h"

#include "brookesia/lib_utils/thread_config.hpp"
#include "private/utils.hpp"

#include "kitty_net.hpp"
#include "training_remote_net.hpp"
#include "training_ui.hpp"

namespace {

constexpr const char *TAG = "training_remote";
constexpr int k_poll_ms = 2000;
constexpr int k_heartbeat_ms = 15000;
constexpr int k_steer_ms = 500;
constexpr int k_loop_ms = 120;

std::atomic<bool> g_run{false};
std::atomic<bool> g_thread_live{false};
std::string g_token;
std::vector<TrainingOrgItem> g_orgs;
std::vector<TrainingCourseItem> g_courses;
TrainingSnapshot g_hosted;
TrainingSnapshot g_org_view;
int g_org_id = 0;
std::string g_org_name;
int g_teacher_total = 0;
bool g_owns = false;
int64_t g_last_poll_ms = 0;
int64_t g_last_beat_ms = 0;
int64_t g_last_steer_ms = 0;
bool g_lists_loaded = false;

int64_t now_ms()
{
    return boost::chrono::duration_cast<boost::chrono::milliseconds>(
        boost::chrono::steady_clock::now().time_since_epoch()
    ).count();
}

void note_auth_status(int status)
{
    if (status == 404) {
        training_ui_set_phase(TrainingUiPhase::error);
        training_ui_set_status("未开启培训");
        return;
    }
    if (status == 401 || status == 403) {
        training_ui_set_phase(TrainingUiPhase::error);
        training_ui_set_status("无权限");
    }
}

bool wait_for_token()
{
    if (kitty_net_load_token(g_token)) {
        ESP_LOGI(TAG, "token ready");
        return true;
    }
    training_ui_set_phase(TrainingUiPhase::error);
    training_ui_set_status("需要 mgat_");
    return false;
}

bool wait_for_network()
{
    for (int i = 0; i < 80 && g_run.load(); ++i) {
        esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
        esp_netif_ip_info_t ip{};
        const bool have_ip = sta != nullptr
            && esp_netif_get_ip_info(sta, &ip) == ESP_OK
            && ip.ip.addr != 0;
        if (have_ip && std::time(nullptr) > 1700000000) {
            return true;
        }
        training_ui_set_status("连接中");
        boost::this_thread::sleep_for(boost::chrono::milliseconds(500));
    }
    training_ui_set_phase(TrainingUiPhase::error);
    training_ui_set_status("没有网络");
    return false;
}

bool refresh_lists()
{
    int org_status = 0;
    const bool orgs_ok = training_load_orgs(g_token, g_orgs, org_status);
    if (!orgs_ok) {
        note_auth_status(org_status);
    } else {
        training_ui_set_orgs(g_orgs);
    }
    int course_status = 0;
    if (training_load_courses(g_token, g_courses, course_status)) {
        training_ui_set_courses(g_courses);
    }
    return orgs_ok;
}

const TrainingOrgItem *org_by_id(int org_id)
{
    for (const auto &org : g_orgs) {
        if (org.id == org_id) {
            return &org;
        }
    }
    return nullptr;
}

const TrainingCourseItem *course_by_id(const std::string &course_id)
{
    for (const auto &course : g_courses) {
        if (course.id == course_id) {
            return &course;
        }
    }
    return nullptr;
}

bool fetch_active(int org_id, TrainingSnapshot &out)
{
    int status = 0;
    if (training_fetch_active(g_token, org_id, out, status)) {
        return true;
    }
    note_auth_status(status);
    return false;
}

void apply_owned(const TrainingSnapshot &snap)
{
    g_hosted = snap;
    g_owns = training_session_active(snap);
    if (snap.org_id > 0) {
        g_org_id = snap.org_id;
        const auto *org = org_by_id(snap.org_id);
        if (org != nullptr) {
            g_org_name = org->name;
        }
    }
}

void paint_host()
{
    const bool playing = g_owns && !g_hosted.course_id.empty();
    training_ui_set_school_name(g_org_name);
    training_ui_set_school_locked(g_owns);
    training_ui_set_active_course(g_hosted.course_id);
    training_ui_set_step(g_hosted.step_index, g_hosted.step_count);
    training_ui_set_can_prev(training_can_steer(g_hosted, -1));
    training_ui_set_can_next(training_can_steer(g_hosted, 1));
    training_ui_set_locked(g_hosted.pull_users);
    training_ui_set_pad_enabled(playing);
    if (!g_owns && training_session_active(g_org_view) && g_org_id > 0 && g_org_view.org_id == g_org_id) {
        training_ui_set_phase(TrainingUiPhase::foreign);
        training_ui_set_pill(TrainingHostPill::idle);
        training_ui_set_status("他人正在主持");
        training_ui_set_dropdown_mode(TrainingDropdownMode::courses);
        training_ui_set_dropdown_label(g_org_name.empty() ? "选择学校" : g_org_name);
        return;
    }
    if (g_owns && playing) {
        training_ui_set_phase(TrainingUiPhase::live);
        training_ui_set_pill(TrainingHostPill::stop);
        const auto *course = course_by_id(g_hosted.course_id);
        training_ui_set_dropdown_mode(TrainingDropdownMode::courses);
        training_ui_set_dropdown_label(course != nullptr ? course->title : "课程");
        training_ui_set_status("");
        return;
    }
    if (g_owns) {
        training_ui_set_phase(TrainingUiPhase::armed);
        training_ui_set_pill(TrainingHostPill::stop);
        training_ui_set_dropdown_mode(TrainingDropdownMode::courses);
        training_ui_set_dropdown_label("选择课程");
        training_ui_set_status("教室已就绪");
        return;
    }
    if (g_org_id > 0) {
        training_ui_set_phase(TrainingUiPhase::ready);
        training_ui_set_pill(TrainingHostPill::ready);
        training_ui_set_dropdown_mode(TrainingDropdownMode::courses);
        training_ui_set_dropdown_label(g_org_name.empty() ? "选择课程" : g_org_name);
        training_ui_set_status("点开始开课");
        return;
    }
    training_ui_set_phase(TrainingUiPhase::pick_school);
    training_ui_set_pill(TrainingHostPill::idle);
    training_ui_set_dropdown_mode(TrainingDropdownMode::schools);
    training_ui_set_dropdown_label("选择学校");
    training_ui_set_status("等待选择学校");
}

void select_org(int org_id)
{
    const auto *org = org_by_id(org_id);
    if (org == nullptr) {
        return;
    }
    g_org_id = org->id;
    g_org_name = org->name;
    training_fetch_ready(g_token, org_id, g_teacher_total);
    TrainingSnapshot view;
    if (fetch_active(org_id, view)) {
        g_org_view = view;
        if (g_hosted.session_id == view.session_id && training_session_active(view)) {
            apply_owned(view);
        }
    }
    training_ui_set_dropdown_open(false);
    training_ui_set_dropdown_mode(TrainingDropdownMode::courses);
    paint_host();
}

void hydrate()
{
    TrainingSnapshot hosted;
    if (fetch_active(0, hosted) && training_session_active(hosted)) {
        apply_owned(hosted);
        g_org_view = hosted;
        if (g_org_id > 0) {
            training_fetch_ready(g_token, g_org_id, g_teacher_total);
        }
    } else if (!hosted.session_id.empty() && hosted.org_id > 0) {
        g_hosted = TrainingSnapshot{};
        g_owns = false;
        g_org_id = hosted.org_id;
        const auto *org = org_by_id(hosted.org_id);
        if (org != nullptr) {
            g_org_name = org->name;
        }
    } else {
        g_hosted = TrainingSnapshot{};
        g_owns = false;
    }
    if (g_org_id > 0) {
        TrainingSnapshot view;
        if (fetch_active(g_org_id, view)) {
            g_org_view = view;
            if (g_owns && view.session_id == g_hosted.session_id) {
                apply_owned(view);
            }
        }
    }
    paint_host();
}

void handle_http_result(int status, const std::string &body, bool apply)
{
    if (status == 429) {
        training_ui_set_status("太快了");
        return;
    }
    if (status == 403) {
        if (training_detail_code(body) == "not_owner") {
            g_owns = false;
            training_ui_set_phase(TrainingUiPhase::foreign);
            training_ui_set_status("他人正在主持");
            return;
        }
        training_ui_set_status("无权限");
        return;
    }
    if (status == 404) {
        g_hosted = TrainingSnapshot{};
        g_owns = false;
        paint_host();
        return;
    }
    if (status != 200) {
        training_ui_set_status("出错了");
        return;
    }
    if (apply) {
        TrainingSnapshot snap;
        if (training_parse_snapshot(body, snap)) {
            apply_owned(snap);
        }
    }
    paint_host();
}

bool steer_ok()
{
    const int64_t now = now_ms();
    if (now - g_last_steer_ms < k_steer_ms) {
        training_ui_set_status("太快了");
        return false;
    }
    g_last_steer_ms = now;
    return true;
}

void post_step(int delta)
{
    if (!g_owns || !steer_ok()) {
        return;
    }
    training_ui_set_busy(true);
    if (delta != 0) {
        training_ui_set_locked(true);
    }
    int status = 0;
    std::string body;
    const std::string payload = std::string("{\"delta\":") + std::to_string(delta) + "}";
    training_http_json(g_token, "POST", training_session_url(g_hosted, "/step"), payload, status, body);
    handle_http_result(status, body, true);
    training_ui_set_busy(false);
}

void post_free(bool free_teachers)
{
    if (!g_owns || !steer_ok()) {
        return;
    }
    if (free_teachers == !g_hosted.pull_users) {
        return;
    }
    training_ui_set_busy(true);
    int status = 0;
    std::string body;
    const char *payload = free_teachers ? "{\"free\":true}" : "{\"free\":false}";
    training_http_json(g_token, "POST", training_session_url(g_hosted, "/free"), payload, status, body);
    handle_http_result(status, body, true);
    training_ui_set_busy(false);
}

void leave_owned_session()
{
    if (!g_owns || g_hosted.session_id.empty() || g_token.empty()) {
        g_owns = false;
        return;
    }
    int status = 0;
    std::string body;
    training_http_json(g_token, "POST", training_session_url(g_hosted, "/end"), "", status, body);
    ESP_LOGI(TAG, "session ended after home id=%s status=%d", g_hosted.session_id.c_str(), status);
    g_hosted = TrainingSnapshot{};
    g_owns = false;
    g_org_view = TrainingSnapshot{};
    training_ui_set_confirm(false);
}

void post_end()
{
    if (!g_owns || g_hosted.session_id.empty()) {
        training_ui_set_confirm(false);
        return;
    }
    training_ui_set_busy(true);
    leave_owned_session();
    hydrate();
    training_ui_set_busy(false);
}

void post_start()
{
    if (g_org_id <= 0) {
        training_ui_set_status("请先选择学校");
        return;
    }
    if (g_owns) {
        return;
    }
    if (training_session_active(g_org_view)) {
        training_ui_set_status("他人正在主持");
        return;
    }
    if (!training_fetch_ready(g_token, g_org_id, g_teacher_total)) {
        training_ui_set_status("无法核对人数");
        return;
    }
    training_ui_set_busy(true);
    int status = 0;
    std::string body;
    const std::string payload = "{\"org_id\":" + std::to_string(g_org_id)
        + ",\"confirm_teacher_total\":" + std::to_string(g_teacher_total) + "}";
    training_http_json(g_token, "POST", "/api/training/sessions", payload, status, body);
    if (status != 200) {
        const std::string code = training_detail_code(body);
        if (code == "confirm_mismatch" && training_fetch_ready(g_token, g_org_id, g_teacher_total)) {
            const std::string retry = "{\"org_id\":" + std::to_string(g_org_id)
                + ",\"confirm_teacher_total\":" + std::to_string(g_teacher_total) + "}";
            training_http_json(g_token, "POST", "/api/training/sessions", retry, status, body);
        }
        if (status != 200) {
            if (code == "instructor_busy") {
                training_ui_set_status("已在其他校");
            } else if (code == "org_busy") {
                hydrate();
                training_ui_set_status("学校占用");
            } else {
                training_ui_set_status("无法开始");
            }
            training_ui_set_busy(false);
            return;
        }
    }
    handle_http_result(status, body, true);
    training_ui_set_busy(false);
}

void post_play(const std::string &course_id)
{
    if (!g_owns) {
        training_ui_set_status("请先点击开始");
        return;
    }
    if (course_id.empty() || !steer_ok()) {
        return;
    }
    training_ui_set_busy(true);
    int status = 0;
    std::string body;
    const std::string payload = "{\"course_id\":\"" + course_id + "\"}";
    training_http_json(g_token, "POST", training_session_url(g_hosted, "/play"), payload, status, body);
    handle_http_result(status, body, true);
    training_ui_set_busy(false);
}

void post_heartbeat()
{
    if (!g_owns || g_hosted.session_id.empty()) {
        return;
    }
    int status = 0;
    std::string body;
    training_http_json(g_token, "POST", training_session_url(g_hosted, "/heartbeat"), "", status, body);
    if (status == 200) {
        TrainingSnapshot snap;
        if (training_parse_snapshot(body, snap) && training_session_active(snap)) {
            apply_owned(snap);
            paint_host();
        }
    } else if (status == 403) {
        g_owns = false;
        paint_host();
    }
}

void handle_action(TrainingUiAction action)
{
    switch (action) {
    case TrainingUiAction::prev:
        post_step(-1);
        break;
    case TrainingUiAction::next:
        post_step(1);
        break;
    case TrainingUiAction::lock:
        post_free(false);
        break;
    case TrainingUiAction::free:
        post_free(true);
        break;
    case TrainingUiAction::stop:
        if (g_owns && !g_hosted.course_id.empty()) {
            training_ui_set_confirm(true);
        }
        break;
    case TrainingUiAction::start:
        if (g_owns) {
            training_ui_set_confirm(true);
        } else {
            post_start();
        }
        break;
    case TrainingUiAction::confirm_end:
        post_end();
        break;
    case TrainingUiAction::cancel_end:
        training_ui_set_confirm(false);
        break;
    case TrainingUiAction::toggle_dropdown:
        break;
    case TrainingUiAction::change_school:
        if (!g_owns) {
            training_ui_set_dropdown_mode(TrainingDropdownMode::schools);
            training_ui_set_dropdown_open(true);
        }
        break;
    case TrainingUiAction::pick_org: {
        const int index = training_ui_take_org_index();
        if (index >= 0 && index < static_cast<int>(g_orgs.size())) {
            select_org(g_orgs[static_cast<size_t>(index)].id);
        }
        break;
    }
    case TrainingUiAction::pick_course: {
        const int index = training_ui_take_course_index();
        if (index >= 0 && index < static_cast<int>(g_courses.size())) {
            post_play(g_courses[static_cast<size_t>(index)].id);
        }
        break;
    }
    default:
        break;
    }
}

void remote_loop()
{
    training_ui_set_status("连接中");
    if (!wait_for_network() || !wait_for_token()) {
        g_run.store(false);
        g_thread_live.store(false);
        return;
    }
    g_lists_loaded = refresh_lists();
    if (g_orgs.size() == 1) {
        select_org(g_orgs[0].id);
    }
    hydrate();
    while (g_run.load()) {
        if (training_ui_is_hidden()) {
            leave_owned_session();
            while (g_run.load() && training_ui_is_hidden()) {
                boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
            }
            continue;
        }
        if (!g_lists_loaded) {
            g_lists_loaded = refresh_lists();
            if (g_orgs.size() == 1 && g_org_id == 0) {
                select_org(g_orgs[0].id);
            }
        }
        const TrainingUiAction action = training_ui_take_action();
        if (action != TrainingUiAction::none) {
            handle_action(action);
        }
        const int64_t now = now_ms();
        if (now - g_last_poll_ms >= k_poll_ms) {
            g_last_poll_ms = now;
            hydrate();
        }
        if (g_owns && now - g_last_beat_ms >= k_heartbeat_ms) {
            g_last_beat_ms = now;
            post_heartbeat();
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
    }
    leave_owned_session();
    g_thread_live.store(false);
}

} // namespace

bool training_remote_start()
{
    g_run.store(true);
    bool expected = false;
    if (!g_thread_live.compare_exchange_strong(expected, true)) {
        return true;
    }
    BROOKESIA_THREAD_CONFIG_GUARD({
        .name = "training_remote",
        .stack_size = 24 * 1024,
        .stack_in_ext = true,
    });
    boost::thread(remote_loop).detach();
    return true;
}

void training_remote_stop()
{
    g_run.store(false);
}
