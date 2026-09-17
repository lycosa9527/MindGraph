#include "super_kitty_agent.hpp"
#include "super_kitty_agent_shared.hpp"

#include <atomic>
#include <cstdio>
#include <ctime>

#include "boost/chrono.hpp"
#include "boost/json.hpp"
#include "boost/thread.hpp"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"

#include "brookesia/lib_utils/thread_config.hpp"
#include "private/utils.hpp"

#include "kitty_audio.hpp"
#include "kitty_net.hpp"
#include "kitty_ws.hpp"
#include "super_kitty_audio.hpp"
#include "super_kitty_ui.hpp"
#include "super_kitty_wake.hpp"

namespace {

constexpr const char *TAG = "skitty_agent";
constexpr int k_draw_settle_ms = 1000;

std::atomic<bool> g_run{false};
std::atomic<bool> g_thread_live{false};

bool agent_active()
{
    return g_run.load() && !super_kitty_ui_is_hidden();
}

bool wait_multinet_create()
{
    for (int i = 0; i < 150; ++i) {
        if (!agent_active()) {
            return false;
        }
        if (super_kitty_wake_create_finished()) {
            return true;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(100));
    }
    ESP_LOGW(TAG, "MultiNet create timed out");
    return super_kitty_wake_create_finished();
}

void start_capture_stack()
{
    super_kitty_wake_start();
    (void)wait_multinet_create();
    super_kitty_audio_init();
    super_kitty_audio_start();
    if (!super_kitty_wake_multinet_ready()) {
        super_kitty_ui_set_live("唤醒未就绪");
    }
}

bool wait_face_ready()
{
    for (int i = 0; i < 40; ++i) {
        if (!agent_active()) {
            return false;
        }
        if (super_kitty_ui_face_ready()) {
            boost::this_thread::sleep_for(boost::chrono::milliseconds(200));
            return agent_active();
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(50));
    }
    return super_kitty_ui_face_ready() && agent_active();
}

bool wait_draw_settle()
{
    const int ticks = k_draw_settle_ms / static_cast<int>(k_super_kitty_hold_poll_ms);
    for (int i = 0; i < ticks; ++i) {
        if (!agent_active()) {
            return false;
        }
        super_kitty_wake_poll();
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_super_kitty_hold_poll_ms));
    }
    return agent_active();
}

bool wait_reconnect(int seconds)
{
    const int ticks = seconds * 1000 / static_cast<int>(k_super_kitty_hold_poll_ms);
    for (int i = 0; i < ticks; ++i) {
        if (!g_run.load() || super_kitty_ui_is_hidden()) {
            return false;
        }
        super_kitty_wake_poll();
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_super_kitty_hold_poll_ms));
    }
    return agent_active();
}

std::string watch_device_id()
{
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    char buf[18];
    std::snprintf(
        buf,
        sizeof(buf),
        "%02x:%02x:%02x:%02x:%02x:%02x",
        mac[0],
        mac[1],
        mac[2],
        mac[3],
        mac[4],
        mac[5]
    );
    return std::string(buf);
}

void send_hello()
{
    boost::json::object hello;
    hello["type"] = "hello";
    hello["listen_mode"] = "auto";
    hello["firmware"] = "super_kitty";
    hello["device_id"] = watch_device_id();
    hello["audio_format"] = "pcm";
    hello["tts_enabled"] = true;
    super_kitty_send_obj(std::move(hello));
}

bool wait_for_token()
{
    if (kitty_net_load_token(g_super_kitty_token)) {
        ESP_LOGI(TAG, "token ready");
        return true;
    }
    super_kitty_ui_set_state(KittyUiState::error);
    super_kitty_ui_set_live("需要 mgat_");
    super_kitty_ui_set_kitty_text("在 sdkconfig.defaults.local 写入 token");
    return false;
}

bool wait_for_network()
{
    for (int i = 0; i < 80; ++i) {
        if (!agent_active()) {
            return false;
        }
        esp_netif_t *sta = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
        esp_netif_ip_info_t ip{};
        const bool have_ip = sta != nullptr
            && esp_netif_get_ip_info(sta, &ip) == ESP_OK
            && ip.ip.addr != 0;
        if (have_ip && std::time(nullptr) > 1700000000) {
            return true;
        }
        super_kitty_wake_poll();
        boost::this_thread::sleep_for(boost::chrono::milliseconds(500));
    }
    ESP_LOGW(TAG, "network wait timed out");
    return false;
}

} // namespace

bool super_kitty_agent_is_library_id(const std::string &id)
{
    return id.size() == 36 && id[8] == '-';
}

bool super_kitty_agent_has_library_scope()
{
    return super_kitty_agent_is_library_id(g_super_kitty_scope);
}

void super_kitty_agent_request_leave()
{
    g_super_kitty_interrupt.store(true);
    g_super_kitty_speaking.store(false);
    g_super_kitty_playing_pcm.store(false);
}

void super_kitty_agent_leave_session()
{
    super_kitty_agent_request_leave();
    super_kitty_audio_stop();
    super_kitty_wake_stop();
    if (!kitty_ws_owned_by(KittyWsOwner::super_kitty)) {
        return;
    }
    if (kitty_ws_is_open()) {
        super_kitty_send_obj({{"type", "abort"}, {"reason", "home"}});
        super_kitty_send_obj({{"type", "stop"}});
    }
    kitty_ws_close();
    ESP_LOGI(TAG, "session closed after home");
}

bool super_kitty_agent_bind_ws()
{
    g_super_kitty_interrupt.store(false);
    super_kitty_ui_set_state(KittyUiState::connecting);
    kitty_ws_set_handler(super_kitty_agent_handle_inbound);
    if (!kitty_ws_connect(kitty_net_ws_url(g_super_kitty_scope), g_super_kitty_token, KittyWsOwner::super_kitty)) {
        return false;
    }
    for (int i = 0; i < 80 && !kitty_ws_is_open(); ++i) {
        if (!agent_active()) {
            kitty_ws_close();
            return false;
        }
        super_kitty_wake_poll();
        boost::this_thread::sleep_for(boost::chrono::milliseconds(100));
    }
    if (!kitty_ws_is_open()) {
        ESP_LOGW(TAG, "ws open timeout scope=%s", g_super_kitty_scope.c_str());
        kitty_ws_close();
        return false;
    }
    boost::json::object start;
    start["type"] = "start";
    start["client_lane"] = "mobile";
    start["diagram_type"] = g_super_kitty_diagram_type;
    start["active_panel"] = "none";
    kitty_ws_send_json(boost::json::serialize(start));
    send_hello();
    super_kitty_ui_set_state(KittyUiState::idle);
    super_kitty_ui_set_live("");
    kitty_audio_play_click();
    ESP_LOGI(TAG, "start mobile lane firmware=super_kitty scope=%s", g_super_kitty_scope.c_str());
    return true;
}

bool super_kitty_agent_connect_session(bool adopt_desktop)
{
    if (!agent_active()) {
        return false;
    }
    super_kitty_ui_set_state(KittyUiState::connecting);
    wait_for_network();
    if (!agent_active()) {
        return false;
    }
    const bool need_boot = adopt_desktop || !super_kitty_agent_has_library_scope();
    if (need_boot) {
        std::string boot_scope;
        std::string title;
        std::string diagram_type;
        if (kitty_net_bootstrap(g_super_kitty_token, boot_scope, title, diagram_type)) {
            if (super_kitty_agent_is_library_id(boot_scope)) {
                g_super_kitty_scope = boot_scope;
                g_super_kitty_diagram_type = diagram_type.empty() ? "mindmap" : diagram_type;
                super_kitty_ui_set_library(kitty_net_diagram_caption(title, g_super_kitty_diagram_type));
            } else if (adopt_desktop || !super_kitty_agent_has_library_scope()) {
                g_super_kitty_scope = boot_scope.empty() ? "watch" : boot_scope;
                g_super_kitty_diagram_type = diagram_type.empty() ? "mindmap" : diagram_type;
                super_kitty_ui_set_library(kitty_net_diagram_caption(title, g_super_kitty_diagram_type));
            }
        } else if (!super_kitty_agent_has_library_scope()) {
            super_kitty_ui_set_state(KittyUiState::error);
            super_kitty_ui_set_kitty_text("无法打开桌面图");
            return false;
        }
    }
    return super_kitty_agent_bind_ws();
}

namespace {

bool bind_scope(const KittyDiagramItem &item, bool enqueue_desktop)
{
    if (item.id.empty()) {
        return false;
    }
    g_super_kitty_scope = item.id;
    g_super_kitty_diagram_type = item.type.empty() ? "mindmap" : item.type;
    super_kitty_ui_set_library(kitty_net_diagram_caption(item.title, item.type));
    if (enqueue_desktop) {
        if (!kitty_net_enqueue_open_library(g_super_kitty_token, item.id, item.title)) {
            ESP_LOGW(TAG, "desktop open_library enqueue failed id=%s", item.id.c_str());
        }
    }
    return super_kitty_agent_bind_ws();
}

} // namespace

bool super_kitty_agent_attach_scope(const KittyDiagramItem &item)
{
    return bind_scope(item, true);
}

bool super_kitty_agent_follow_library(const KittyDiagramItem &item)
{
    if (item.id.empty()) {
        if (!super_kitty_agent_has_library_scope()) {
            return true;
        }
        KittyDiagramItem cleared;
        cleared.id = "watch";
        cleared.title = "";
        cleared.type = "mindmap";
        return bind_scope(cleared, false);
    }
    if (item.id == g_super_kitty_scope) {
        if (!item.title.empty()) {
            const std::string dtype = item.type.empty() ? g_super_kitty_diagram_type : item.type;
            if (!item.type.empty()) {
                g_super_kitty_diagram_type = item.type;
            }
            super_kitty_ui_set_library(kitty_net_diagram_caption(item.title, dtype));
        }
        return true;
    }
    if (!super_kitty_agent_is_library_id(item.id)) {
        return true;
    }
    KittyDiagramItem bind = item;
    if (bind.title.empty()) {
        bind.title = "思维导图";
    }
    if (bind.type.empty()) {
        bind.type = "mindmap";
    }
    return bind_scope(bind, false);
}

namespace {

void refresh_library()
{
    std::vector<KittyDiagramItem> items;
    if (!kitty_net_list_diagrams(g_super_kitty_token, items)) {
        super_kitty_ui_set_picker_status("无法加载");
        return;
    }
    super_kitty_ui_set_diagrams(items);
}

void finish_agent()
{
    super_kitty_agent_leave_session();
    g_thread_live.store(false);
}

std::time_t g_listen_cool_until = 0;

bool should_listen()
{
    if (g_super_kitty_speaking.load() || g_super_kitty_playing_pcm.load()) {
        return false;
    }
    if (std::time(nullptr) < g_listen_cool_until) {
        return false;
    }
    return super_kitty_wake_take_address();
}

void agent_loop()
{
    BROOKESIA_LOGI("Super Kitty watch agent starting");
    if (!wait_face_ready()) {
        finish_agent();
        return;
    }
    start_capture_stack();

    if (!kitty_net_server_configured()) {
        super_kitty_ui_set_state(KittyUiState::error);
        super_kitty_ui_set_kitty_text("设置服务器地址");
        finish_agent();
        return;
    }

    if (!wait_for_token()) {
        finish_agent();
        return;
    }

    int reconnect_fails = 0;
    std::time_t user_override_until = 0;
    bool was_hidden = false;
    while (g_run.load()) {
        if (super_kitty_ui_is_hidden()) {
            was_hidden = true;
            if (kitty_ws_is_open()) {
                super_kitty_agent_leave_session();
            }
            boost::this_thread::sleep_for(boost::chrono::milliseconds(k_super_kitty_hold_poll_ms));
            continue;
        }
        super_kitty_wake_poll();
        if (was_hidden) {
            if (!wait_face_ready()) {
                continue;
            }
            start_capture_stack();
            was_hidden = false;
        }
        if (super_kitty_ui_picker_needs_list()) {
            refresh_library();
        }
        if (super_kitty_ui_take_create_mindmap()) {
            super_kitty_ui_clear_desktop_focus();
            user_override_until = std::time(nullptr) + 3;
            super_kitty_ui_set_live("新建中");
            KittyDiagramItem created;
            if (!kitty_net_create_mindmap(g_super_kitty_token, created)) {
                super_kitty_ui_set_kitty_text("新建失败");
                super_kitty_ui_set_state(KittyUiState::idle);
                super_kitty_ui_set_live("");
            } else if (!super_kitty_agent_attach_scope(created)) {
                super_kitty_ui_set_live("重连中");
            }
        }
        KittyDiagramItem picked;
        if (super_kitty_ui_take_diagram_pick(picked)) {
            super_kitty_ui_clear_desktop_focus();
            user_override_until = std::time(nullptr) + 3;
            if (!super_kitty_agent_attach_scope(picked)) {
                super_kitty_ui_set_live("重连中");
            }
        }
        if (std::time(nullptr) < user_override_until) {
            KittyDiagramItem ignored;
            super_kitty_ui_take_desktop_focus(ignored);
        } else if (!g_super_kitty_speaking.load() && !g_super_kitty_playing_pcm.load()) {
            KittyDiagramItem focus;
            if (super_kitty_ui_take_desktop_focus(focus)) {
                if (!super_kitty_agent_follow_library(focus)) {
                    super_kitty_ui_set_live("重连中");
                }
            }
        }
        const int choice = super_kitty_ui_take_choice();
        if (choice > 0) {
            super_kitty_agent_send_clarify_choice(choice);
        }
        if (!kitty_ws_is_open() && agent_active()) {
            super_kitty_ui_set_state(KittyUiState::connecting);
            if (super_kitty_agent_connect_session(std::time(nullptr) >= user_override_until)) {
                reconnect_fails = 0;
            } else {
                reconnect_fails += 1;
                const int wait_s = reconnect_fails > 4 ? 5 : reconnect_fails;
                super_kitty_ui_set_live("重连中");
                wait_reconnect(wait_s);
            }
        }
        if (super_kitty_ui_take_click()) {
            kitty_audio_play_click();
        }
        if (kitty_ws_is_open() && should_listen()) {
            super_kitty_agent_run_addressed_listen();
            g_listen_cool_until = std::time(nullptr) + 2;
            super_kitty_audio_clear();
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_super_kitty_hold_poll_ms));
    }
    finish_agent();
}

} // namespace

bool super_kitty_agent_start()
{
    g_run.store(true);
    bool expected = false;
    if (!g_thread_live.compare_exchange_strong(expected, true)) {
        return true;
    }
    BROOKESIA_THREAD_CONFIG_GUARD({
        .name = "skitty_agent",
        .stack_size = 48 * 1024,
        .stack_in_ext = true,
    });
    boost::thread(agent_loop).detach();
    return true;
}

void super_kitty_agent_stop()
{
    g_run.store(false);
    super_kitty_agent_request_leave();
}
