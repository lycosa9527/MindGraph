#include <mutex>
#include <string>

#include "esp_log.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "kitty_net.hpp"
#include "kitty_ws.hpp"

namespace {

constexpr const char *TAG = "kitty_ws";
constexpr TickType_t k_stop_settle_ticks = pdMS_TO_TICKS(250);

esp_websocket_client_handle_t g_client = nullptr;
std::function<void(const std::string &)> g_handler;
std::mutex g_mutex;
std::string g_rx;
std::string g_url;
bool g_open = false;

void dispatch_text(const std::string &payload)
{
    std::function<void(const std::string &)> handler;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        handler = g_handler;
    }
    if (handler) {
        handler(payload);
    }
}

void on_event(void *arg, esp_event_base_t base, int32_t event_id, void *event_data)
{
    (void)arg;
    (void)base;
    auto *event = static_cast<esp_websocket_event_data_t *>(event_data);
    if (event_id == WEBSOCKET_EVENT_CONNECTED) {
        g_open = true;
        ESP_LOGI(TAG, "connected");
        return;
    }
    if (event_id == WEBSOCKET_EVENT_DISCONNECTED || event_id == WEBSOCKET_EVENT_ERROR) {
        g_open = false;
        g_rx.clear();
        ESP_LOGW(TAG, "socket closed id=%d", static_cast<int>(event_id));
        return;
    }
    if (event_id != WEBSOCKET_EVENT_DATA || event == nullptr || event->data_ptr == nullptr || event->data_len <= 0) {
        return;
    }
    if (event->op_code != 1 && event->op_code != 0) {
        return;
    }
    if (event->op_code == 1 || event->payload_offset == 0) {
        g_rx.assign(event->data_ptr, static_cast<size_t>(event->data_len));
    } else {
        g_rx.append(event->data_ptr, static_cast<size_t>(event->data_len));
    }
    const int total = event->payload_offset + event->data_len;
    if (event->payload_len > 0 && total < event->payload_len) {
        return;
    }
    dispatch_text(g_rx);
    g_rx.clear();
}

void destroy_client()
{
    g_open = false;
    g_rx.clear();
    if (g_client == nullptr) {
        return;
    }
    const esp_err_t stopped = esp_websocket_client_stop(g_client);
    if (stopped != ESP_OK && stopped != ESP_FAIL) {
        ESP_LOGW(TAG, "stop failed %d", static_cast<int>(stopped));
    }
    esp_websocket_client_destroy(g_client);
    g_client = nullptr;
    vTaskDelay(k_stop_settle_ticks);
}

} // namespace

bool kitty_ws_connect(const std::string &url, const std::string &bearer)
{
    destroy_client();
    if (url.empty()) {
        return false;
    }
    g_url = url;
    esp_websocket_client_config_t config = {};
    config.uri = g_url.c_str();
    config.buffer_size = 4096;
    config.task_stack = 16 * 1024;
    config.network_timeout_ms = 12000;
    config.disable_auto_reconnect = true;
    g_client = esp_websocket_client_init(&config);
    if (g_client == nullptr) {
        ESP_LOGE(TAG, "init failed");
        return false;
    }
    if (!bearer.empty()) {
        const std::string auth = "Bearer " + bearer;
        esp_websocket_client_append_header(g_client, "Authorization", auth.c_str());
    }
    esp_websocket_client_append_header(g_client, "X-MG-Client", "esp32-watch");
    const std::string account = kitty_net_account();
    if (!account.empty()) {
        esp_websocket_client_append_header(g_client, "X-MG-Account", account.c_str());
    }
    esp_websocket_register_events(g_client, WEBSOCKET_EVENT_ANY, on_event, nullptr);
    const esp_err_t started = esp_websocket_client_start(g_client);
    if (started != ESP_OK) {
        ESP_LOGE(TAG, "start failed %d", static_cast<int>(started));
        destroy_client();
        return false;
    }
    ESP_LOGI(TAG, "connecting %s", g_url.c_str());
    return true;
}

void kitty_ws_close()
{
    destroy_client();
}

bool kitty_ws_is_open()
{
    return g_open && g_client != nullptr && esp_websocket_client_is_connected(g_client);
}

bool kitty_ws_send_json(const std::string &json)
{
    if (!kitty_ws_is_open() || json.empty()) {
        return false;
    }
    const int sent = esp_websocket_client_send_text(
        g_client,
        json.c_str(),
        static_cast<int>(json.size()),
        pdMS_TO_TICKS(1000)
    );
    return sent > 0;
}

void kitty_ws_set_handler(std::function<void(const std::string &)> handler)
{
    std::lock_guard<std::mutex> lock(g_mutex);
    g_handler = std::move(handler);
}
