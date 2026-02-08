#include "websocket_client.h"
#include "cJSON.h"
#include "esp_log.h"
#include "esp_http_client.h"
#include <string>
#include <cstring>

static const char* TAG = "WEBSOCKET";
static WatchState current_state = WATCH_STATE_DISCONNECTED;
static OnMessageCallback message_callback = nullptr;
static OnStateChangeCallback state_callback = nullptr;
static std::string watch_id;
static std::string auth_token;
static std::string server_url;
static bool websocket_initialized = false;

bool websocket_init() {
    if (websocket_initialized) {
        return true;
    }
    websocket_initialized = true;
    ESP_LOGI(TAG, "Initialized (stub)");
    return true;
}

void websocket_set_callbacks(OnMessageCallback on_msg, OnStateChangeCallback on_state) {
    message_callback = on_msg;
    state_callback = on_state;
}

bool websocket_connect(const char* server_url_str, const char* watch_id_str, const char* auth_token_str) {
    if (!websocket_initialized) {
        websocket_init();
    }
    
    server_url = server_url_str ? server_url_str : "";
    watch_id = watch_id_str ? watch_id_str : "";
    auth_token = auth_token_str ? auth_token_str : "";
    
    current_state = WATCH_STATE_CONNECTING;
    if (state_callback) {
        state_callback(current_state);
    }
    
    ESP_LOGI(TAG, "Connecting to %s (stub)", server_url.c_str());
    
    current_state = WATCH_STATE_CONNECTED;
    if (state_callback) {
        state_callback(current_state);
    }
    
    return true;
}

void websocket_disconnect() {
    if (current_state != WATCH_STATE_DISCONNECTED) {
        current_state = WATCH_STATE_DISCONNECTED;
        if (state_callback) {
            state_callback(current_state);
        }
    }
    ESP_LOGI(TAG, "Disconnected");
}

void websocket_handle() {
}

bool websocket_is_connected() {
    return current_state == WATCH_STATE_CONNECTED || 
           current_state == WATCH_STATE_AUTHENTICATING ||
           current_state == WATCH_STATE_READY ||
           current_state == WATCH_STATE_LEARNING_MODE;
}

WatchState websocket_get_state() {
    return current_state;
}

bool websocket_send_json(cJSON* doc) {
    if (!websocket_is_connected() || doc == nullptr) {
        return false;
    }
    char* json_string = cJSON_Print(doc);
    if (json_string == nullptr) {
        ESP_LOGE(TAG, "Failed to serialize JSON");
        return false;
    }
    ESP_LOGI(TAG, "Sending JSON: %s (stub)", json_string);
    free(json_string);
    return true;
}

bool websocket_send_audio(const uint8_t* data, size_t len) {
    if (!websocket_is_connected()) {
        return false;
    }
    ESP_LOGI(TAG, "Sending audio %zu bytes (stub)", len);
    return true;
}
