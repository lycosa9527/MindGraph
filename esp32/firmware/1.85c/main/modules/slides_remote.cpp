#include "slides_remote.hpp"

#include <atomic>
#include <ctime>
#include <mutex>
#include <string>
#include <vector>

#include "boost/chrono.hpp"
#include "boost/json.hpp"
#include "boost/thread.hpp"
#include "esp_log.h"
#include "esp_netif.h"

#include "brookesia/lib_utils/thread_config.hpp"
#include "private/utils.hpp"

#include "kitty_net.hpp"
#include "kitty_ws.hpp"
#include "slides_remote_net.hpp"
#include "slides_ui.hpp"

namespace {

constexpr const char *TAG = "slides_remote";
constexpr int k_steer_ms = 400;
constexpr int k_loop_ms = 120;
constexpr int k_draw_settle_ms = 1000;

std::atomic<bool> g_run{false};
std::atomic<bool> g_thread_live{false};
std::mutex g_mutex;
std::string g_token;
SlidesSnapshot g_snap;
SlidesSnapshot g_incoming;
bool g_incoming_ready = false;
bool g_own_ws = false;
std::vector<KittyDiagramItem> g_diagrams;
std::string g_diagram_id;
int64_t g_last_steer_ms = 0;

int64_t now_ms()
{
    return boost::chrono::duration_cast<boost::chrono::milliseconds>(
        boost::chrono::steady_clock::now().time_since_epoch()
    ).count();
}

void note_auth_status(int status)
{
    if (status == 401 || status == 403) {
        slides_ui_set_phase(SlidesUiPhase::error);
        slides_ui_set_status("无权限");
    }
}

bool wait_for_token()
{
    if (kitty_net_load_token(g_token)) {
        ESP_LOGI(TAG, "token ready");
        return true;
    }
    slides_ui_set_phase(SlidesUiPhase::error);
    slides_ui_set_status("需要 mgat_");
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
        slides_ui_set_status("连接中");
        boost::this_thread::sleep_for(boost::chrono::milliseconds(500));
    }
    slides_ui_set_phase(SlidesUiPhase::error);
    slides_ui_set_status("没有网络");
    return false;
}

bool steer_ok()
{
    const int64_t now = now_ms();
    if (now - g_last_steer_ms < k_steer_ms) {
        return false;
    }
    g_last_steer_ms = now;
    return true;
}

void paint_snap(const SlidesSnapshot &snap)
{
    const bool live = slides_session_live(snap);
    slides_ui_set_phase(live ? SlidesUiPhase::live : SlidesUiPhase::wait);
    slides_ui_set_pad_enabled(live);
    slides_ui_set_step(snap.slide_index, snap.slide_count);
    slides_ui_set_can_prev(live && snap.can_prev);
    slides_ui_set_can_next(live && snap.can_next);
    slides_ui_set_autoplay(live && snap.autoplay);
    slides_ui_set_deep(snap.traversal == "deep");
    if (live) {
        slides_ui_set_status("");
        return;
    }
    slides_ui_set_status(g_diagram_id.empty() ? "请选图库" : "点开始放映");
}

void on_ws_frame(const std::string &raw)
{
    SlidesSnapshot snap;
    if (!slides_parse_ws_frame(raw, snap)) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_mutex);
    g_incoming = snap;
    g_incoming_ready = true;
}

void drain_incoming()
{
    SlidesSnapshot snap;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (!g_incoming_ready) {
            return;
        }
        snap = g_incoming;
        g_incoming_ready = false;
    }
    g_snap = snap;
    paint_snap(g_snap);
}

void hydrate()
{
    int status = 0;
    SlidesSnapshot snap;
    if (!slides_fetch_active(g_token, snap, status)) {
        note_auth_status(status);
        if (status == 0) {
            slides_ui_set_status("无法连接");
        }
        return;
    }
    g_snap = snap;
    paint_snap(g_snap);
}

void release_ws()
{
    if (!g_own_ws && !kitty_ws_owned_by(KittyWsOwner::slides)) {
        return;
    }
    kitty_ws_set_handler(nullptr);
    kitty_ws_close_owned(KittyWsOwner::slides);
    g_own_ws = false;
}

bool bind_ws()
{
    if (kitty_ws_is_open() && kitty_ws_owned_by(KittyWsOwner::slides)) {
        g_own_ws = true;
        return true;
    }
    if (kitty_ws_is_connecting() && kitty_ws_owned_by(KittyWsOwner::slides)) {
        return false;
    }
    kitty_ws_set_handler(on_ws_frame);
    if (!kitty_ws_connect(slides_ws_url(), g_token, KittyWsOwner::slides)) {
        g_own_ws = false;
        return false;
    }
    for (int i = 0; i < 80 && !kitty_ws_is_open(); ++i) {
        if (!g_run.load() || slides_ui_is_hidden()) {
            release_ws();
            return false;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(100));
    }
    if (!kitty_ws_is_open()) {
        ESP_LOGW(TAG, "ws open timeout");
        release_ws();
        return false;
    }
    g_own_ws = true;
    ESP_LOGI(TAG, "ws ready");
    return true;
}

void refresh_library()
{
    std::vector<KittyDiagramItem> items;
    if (!kitty_net_list_diagrams(g_token, items)) {
        slides_ui_set_picker_status("无法加载");
        return;
    }
    g_diagrams = std::move(items);
    std::vector<SlidesDiagramItem> rows;
    rows.reserve(g_diagrams.size());
    for (const auto &item : g_diagrams) {
        SlidesDiagramItem row;
        row.id = item.id;
        row.title = item.title;
        row.type = item.type;
        rows.push_back(row);
    }
    slides_ui_set_diagrams(rows);
}

void post_action(const std::string &json, bool need_live)
{
    if (need_live && !slides_session_live(g_snap)) {
        return;
    }
    if (!steer_ok()) {
        return;
    }
    slides_ui_set_busy(true);
    int status = 0;
    if (!slides_post_command(g_token, json, status) || (status != 200 && status != 201)) {
        if (status == 404) {
            g_snap = SlidesSnapshot{};
            paint_snap(g_snap);
        } else {
            note_auth_status(status);
            slides_ui_set_status("发送失败");
        }
    } else if (!g_own_ws || !kitty_ws_is_open()) {
        hydrate();
    }
    slides_ui_set_busy(false);
}

void post_start()
{
    if (g_diagram_id.empty()) {
        slides_ui_set_status("请选图库");
        return;
    }
    boost::json::object body;
    body["action"] = "start";
    body["diagram_id"] = g_diagram_id;
    post_action(boost::json::serialize(body), false);
}

void pick_diagram(int index)
{
    if (index < 0 || index >= static_cast<int>(g_diagrams.size())) {
        return;
    }
    const auto &item = g_diagrams[static_cast<size_t>(index)];
    g_diagram_id = item.id;
    slides_ui_set_library(kitty_net_diagram_caption(item.title, item.type));
    if (!slides_session_live(g_snap)) {
        slides_ui_set_status("点开始放映");
    }
}

void handle_action(SlidesUiAction action)
{
    switch (action) {
    case SlidesUiAction::prev:
        post_action("{\"action\":\"prev\"}", true);
        break;
    case SlidesUiAction::next:
        post_action("{\"action\":\"next\"}", true);
        break;
    case SlidesUiAction::autoplay:
        post_action(
            g_snap.autoplay ? "{\"action\":\"autoplay\",\"on\":false}"
                            : "{\"action\":\"autoplay\",\"on\":true}",
            true
        );
        break;
    case SlidesUiAction::first_level:
        post_action("{\"action\":\"traversal\",\"mode\":\"firstLevel\"}", true);
        break;
    case SlidesUiAction::deep:
        post_action("{\"action\":\"traversal\",\"mode\":\"deep\"}", true);
        break;
    case SlidesUiAction::host:
        if (slides_session_live(g_snap)) {
            post_action("{\"action\":\"quit\"}", true);
        } else {
            post_start();
        }
        break;
    case SlidesUiAction::pick_diagram:
        pick_diagram(slides_ui_take_diagram_index());
        break;
    default:
        break;
    }
}

void remote_loop()
{
    slides_ui_set_status("连接中");
    if (!wait_for_network() || !wait_for_token()) {
        g_run.store(false);
        g_thread_live.store(false);
        return;
    }
    for (int i = 0; i < k_draw_settle_ms / k_loop_ms && g_run.load(); ++i) {
        if (!slides_ui_is_hidden()) {
            break;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
    }
    for (int i = 0; i < k_draw_settle_ms / k_loop_ms && g_run.load() && !slides_ui_is_hidden(); ++i) {
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
    }
    int reconnect_fails = 0;
    while (g_run.load()) {
        if (slides_ui_is_hidden()) {
            release_ws();
            while (g_run.load() && slides_ui_is_hidden()) {
                boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
            }
            reconnect_fails = 0;
            continue;
        }
        drain_incoming();
        if (slides_ui_picker_needs_list()) {
            refresh_library();
        }
        const SlidesUiAction action = slides_ui_take_action();
        if (action != SlidesUiAction::none) {
            handle_action(action);
        }
        if (kitty_ws_is_open() && kitty_ws_owned_by(KittyWsOwner::slides)) {
            g_own_ws = true;
        } else if (kitty_ws_is_connecting() && kitty_ws_owned_by(KittyWsOwner::slides)) {
            slides_ui_set_status("连接中");
        } else if (!kitty_ws_is_open()) {
            slides_ui_set_status("连接中");
            if (bind_ws()) {
                reconnect_fails = 0;
            } else if (!(kitty_ws_is_connecting() && kitty_ws_owned_by(KittyWsOwner::slides))) {
                hydrate();
                reconnect_fails += 1;
                const int wait_s = reconnect_fails > 4 ? 5 : reconnect_fails;
                slides_ui_set_status("重连中");
                boost::this_thread::sleep_for(boost::chrono::seconds(wait_s));
            }
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_loop_ms));
    }
    release_ws();
    g_thread_live.store(false);
}

} // namespace

bool slides_remote_start()
{
    g_run.store(true);
    bool expected = false;
    if (!g_thread_live.compare_exchange_strong(expected, true)) {
        return true;
    }
    BROOKESIA_THREAD_CONFIG_GUARD({
        .name = "slides_remote",
        .stack_size = 20 * 1024,
        .stack_in_ext = true,
    });
    boost::thread(remote_loop).detach();
    return true;
}

void slides_remote_stop()
{
    g_run.store(false);
}
