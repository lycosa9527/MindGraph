#include "kitty_agent.hpp"
#include "kitty_agent_shared.hpp"

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
#include "kitty_ui.hpp"
#include "kitty_ws.hpp"

namespace {

constexpr const char *TAG = "kitty_agent";

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

void kitty_agent_send_hello()
{
    boost::json::object hello;
    hello["type"] = "hello";
    hello["listen_mode"] = g_kitty_listen_auto.load() ? "auto" : "manual";
    hello["firmware"] = "1.85c";
    hello["device_id"] = watch_device_id();
    hello["audio_format"] = "pcm";
    kitty_send_obj(std::move(hello));
}

bool wait_for_token()
{
    if (kitty_net_load_token(g_kitty_token)) {
        ESP_LOGI(TAG, "token ready");
        return true;
    }
    kitty_ui_set_state(KittyUiState::error);
    kitty_ui_set_live("需要 mgat_");
    kitty_ui_set_kitty_text("在 sdkconfig.defaults.local 写入 token");
    return false;
}

bool wait_for_network()
{
    for (int i = 0; i < 80; ++i) {
        if (kitty_ui_is_hidden()) {
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
        boost::this_thread::sleep_for(boost::chrono::milliseconds(500));
    }
    ESP_LOGW(TAG, "network wait timed out");
    return false;
}

} // namespace

bool kitty_agent_is_library_id(const std::string &id)
{
    return id.size() == 36 && id[8] == '-';
}

bool kitty_agent_has_library_scope()
{
    return kitty_agent_is_library_id(g_kitty_scope);
}

void kitty_agent_request_leave()
{
    g_kitty_interrupt.store(true);
    g_kitty_pending_auto_listen.store(false);
    g_kitty_speaking.store(false);
    g_kitty_playing_pcm.store(false);
}

void kitty_agent_leave_session()
{
    kitty_agent_request_leave();
    kitty_audio_spk_stop();
    if (!kitty_ws_is_open()) {
        return;
    }
    kitty_send_obj({{"type", "abort"}, {"reason", "home"}});
    kitty_send_obj({{"type", "stop"}});
    kitty_ws_close();
    ESP_LOGI(TAG, "session closed after home");
}

bool kitty_agent_bind_ws()
{
    g_kitty_interrupt.store(false);
    g_kitty_pending_auto_listen.store(false);
    kitty_ui_set_state(KittyUiState::connecting);
    kitty_ws_set_handler(kitty_agent_handle_inbound);
    if (!kitty_ws_connect(kitty_net_ws_url(g_kitty_scope), g_kitty_token)) {
        return false;
    }
    for (int i = 0; i < 80 && !kitty_ws_is_open(); ++i) {
        if (kitty_ui_is_hidden()) {
            kitty_ws_close();
            return false;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(100));
    }
    if (!kitty_ws_is_open()) {
        ESP_LOGW(TAG, "ws open timeout scope=%s", g_kitty_scope.c_str());
        kitty_ws_close();
        return false;
    }
    boost::json::object start;
    start["type"] = "start";
    start["client_lane"] = "mobile";
    start["diagram_type"] = g_kitty_diagram_type;
    start["active_panel"] = "none";
    kitty_ws_send_json(boost::json::serialize(start));
    kitty_agent_send_hello();
    kitty_ui_set_state(KittyUiState::idle);
    kitty_ui_set_live("");
    ESP_LOGI(TAG, "start mobile lane scope=%s", g_kitty_scope.c_str());
    return true;
}

bool kitty_agent_connect_session()
{
    if (kitty_ui_is_hidden()) {
        return false;
    }
    kitty_ui_set_state(KittyUiState::connecting);
    wait_for_network();
    if (kitty_ui_is_hidden()) {
        return false;
    }
    if (!kitty_agent_has_library_scope()) {
        std::string title;
        std::string diagram_type;
        if (!kitty_net_bootstrap(g_kitty_token, g_kitty_scope, title, diagram_type)) {
            kitty_ui_set_state(KittyUiState::error);
            kitty_ui_set_kitty_text("无法打开桌面图");
            return false;
        }
        g_kitty_diagram_type = diagram_type.empty() ? "circle_map" : diagram_type;
        kitty_ui_set_library(kitty_net_diagram_caption(title, g_kitty_diagram_type));
    }
    return kitty_agent_bind_ws();
}

namespace {

bool bind_kitty_scope(const KittyDiagramItem &item, bool enqueue_desktop)
{
    if (item.id.empty()) {
        return false;
    }
    g_kitty_scope = item.id;
    g_kitty_diagram_type = item.type.empty() ? "mindmap" : item.type;
    kitty_ui_set_library(kitty_net_diagram_caption(item.title, item.type));
    if (enqueue_desktop) {
        if (!kitty_net_enqueue_open_library(g_kitty_token, item.id, item.title)) {
            ESP_LOGW(TAG, "desktop open_library enqueue failed id=%s", item.id.c_str());
        } else {
            ESP_LOGI(TAG, "desktop open_library enqueued id=%s", item.id.c_str());
        }
    }
    return kitty_agent_bind_ws();
}

} // namespace

bool kitty_agent_attach_scope(const KittyDiagramItem &item)
{
    return bind_kitty_scope(item, true);
}

bool kitty_agent_follow_library(const KittyDiagramItem &item)
{
    if (item.id.empty()) {
        if (!kitty_agent_has_library_scope()) {
            return true;
        }
        KittyDiagramItem cleared;
        cleared.id = "watch";
        cleared.title = "";
        cleared.type = "mindmap";
        ESP_LOGI(TAG, "follow desktop focus clear → watch");
        return bind_kitty_scope(cleared, false);
    }
    if (item.id == g_kitty_scope) {
        if (!item.title.empty()) {
            const std::string dtype = item.type.empty() ? g_kitty_diagram_type : item.type;
            if (!item.type.empty()) {
                g_kitty_diagram_type = item.type;
            }
            kitty_ui_set_library(kitty_net_diagram_caption(item.title, dtype));
        }
        return true;
    }
    if (!kitty_agent_is_library_id(item.id)) {
        return true;
    }
    KittyDiagramItem bind = item;
    if (bind.title.empty()) {
        bind.title = "思维导图";
    }
    if (bind.type.empty()) {
        bind.type = "mindmap";
    }
    ESP_LOGI(TAG, "follow desktop library id=%s title=%s", bind.id.c_str(), bind.title.c_str());
    return bind_kitty_scope(bind, false);
}

namespace {

void refresh_library()
{
    std::vector<KittyDiagramItem> items;
    if (!kitty_net_list_diagrams(g_kitty_token, items)) {
        kitty_ui_set_picker_status("无法加载");
        return;
    }
    kitty_ui_set_diagrams(items);
}

void agent_loop()
{
    BROOKESIA_LOGI("Kitty watch agent starting");
    kitty_ui_start();
    kitty_audio_init();
    kitty_audio_run_smoke();

    if (!kitty_net_server_configured()) {
        kitty_ui_set_state(KittyUiState::error);
        kitty_ui_set_kitty_text("设置服务器地址");
        ESP_LOGW(TAG, "MINDGRAPH_KITTY_SERVER_URL is empty");
        return;
    }

    if (!wait_for_token()) {
        ESP_LOGW(TAG, "MINDGRAPH_KITTY_MGAT is empty");
        return;
    }
    for (;;) {
        if (kitty_ui_is_hidden()) {
            boost::this_thread::sleep_for(boost::chrono::milliseconds(k_kitty_hold_poll_ms));
            continue;
        }
        if (kitty_agent_connect_session()) {
            break;
        }
        kitty_ui_set_live("重连中");
        boost::this_thread::sleep_for(boost::chrono::seconds(3));
    }
    kitty_ui_set_state(KittyUiState::idle);

    int reconnect_fails = 0;
    std::time_t user_override_until = 0;
    for (;;) {
        if (kitty_ui_is_hidden()) {
            if (kitty_ws_is_open()) {
                kitty_agent_leave_session();
            }
            boost::this_thread::sleep_for(boost::chrono::milliseconds(k_kitty_hold_poll_ms));
            continue;
        }
        if (kitty_ui_picker_needs_list()) {
            refresh_library();
        }
        if (kitty_ui_take_create_mindmap()) {
            kitty_ui_clear_desktop_focus();
            user_override_until = std::time(nullptr) + 3;
            kitty_ui_set_live("新建中");
            KittyDiagramItem created;
            if (!kitty_net_create_mindmap(g_kitty_token, created)) {
                kitty_ui_set_kitty_text("新建失败");
                kitty_ui_set_state(KittyUiState::idle);
                kitty_ui_set_live("");
            } else if (!kitty_agent_attach_scope(created)) {
                kitty_ui_set_live("重连中");
            }
        }
        KittyDiagramItem picked;
        if (kitty_ui_take_diagram_pick(picked)) {
            kitty_ui_clear_desktop_focus();
            user_override_until = std::time(nullptr) + 3;
            if (!kitty_agent_attach_scope(picked)) {
                kitty_ui_set_live("重连中");
            }
        }
        if (std::time(nullptr) < user_override_until) {
            KittyDiagramItem ignored;
            kitty_ui_take_desktop_focus(ignored);
        } else if (
            !kitty_ui_hold_active()
            && !g_kitty_speaking.load()
            && !g_kitty_playing_pcm.load()
        ) {
            KittyDiagramItem focus;
            if (kitty_ui_take_desktop_focus(focus)) {
                const bool leave_library = focus.id.empty() && kitty_agent_has_library_scope();
                const bool join_library =
                    kitty_agent_is_library_id(focus.id) && focus.id != g_kitty_scope;
                if (leave_library || join_library) {
                    kitty_ui_set_live("同步中");
                }
                if (!kitty_agent_follow_library(focus)) {
                    kitty_ui_set_live("重连中");
                }
            }
        }
        const int choice = kitty_ui_take_choice();
        if (choice > 0) {
            kitty_agent_send_clarify_choice(choice);
        }
        if (!kitty_ws_is_open() && !kitty_ui_is_hidden()) {
            kitty_ui_set_state(KittyUiState::connecting);
            if (kitty_agent_connect_session()) {
                reconnect_fails = 0;
            } else {
                reconnect_fails += 1;
                const int wait_s = reconnect_fails > 4 ? 5 : reconnect_fails;
                kitty_ui_set_live("重连中");
                boost::this_thread::sleep_for(boost::chrono::seconds(wait_s));
            }
        }
        if (kitty_ui_take_click()) {
            kitty_audio_play_click();
        }
        if (kitty_ui_hold_active() && kitty_ws_is_open()) {
            kitty_agent_run_ptt();
        } else if (
            g_kitty_pending_auto_listen.load()
            && g_kitty_listen_auto.load()
            && !g_kitty_speaking.load()
            && !g_kitty_playing_pcm.load()
            && kitty_ws_is_open()
        ) {
            kitty_agent_run_auto_listen();
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(k_kitty_hold_poll_ms));
    }
}

} // namespace

bool start_kitty_watch()
{
    BROOKESIA_THREAD_CONFIG_GUARD({
        .name = "kitty_agent",
        .stack_size = 48 * 1024,
        .stack_in_ext = true,
    });
    boost::thread(agent_loop).detach();
    return true;
}
