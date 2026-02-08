#include "smart_response_app.h"
#include "websocket_client.h"
#include "ui_manager.h"
#include "launcher.h"
#include "font_manager.h"
#include "config_manager.h"
#include "audio_handler.h"
#include "wifi_manager.h"
#include "standby_screen.h"
#include "display_utils.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "cJSON.h"
#include <cstring>
#include <stdint.h>
#include <stdbool.h>
#include <string>
#include <mbedtls/base64.h>
#include "esp_log.h"

static const char* TAG = "SMART_RESPONSE";

static lv_obj_t* app_screen = nullptr;
static lv_obj_t* status_label = nullptr;
static bool app_running = false;

static void back_btn_event_cb(lv_event_t* e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        smart_response_app_hide();
        standby_screen_show();
    }
}

static void websocket_message_callback(cJSON* doc) {
    if (doc == nullptr) {
        ESP_LOGE(TAG, "Received null JSON document");
        return;
    }
    
    cJSON* type_item = cJSON_GetObjectItem(doc, "type");
    const char* msg_type = (type_item && cJSON_IsString(type_item)) ? type_item->valuestring : "";
    
    if (strcmp(msg_type, "transcription") == 0) {
        cJSON* text_item = cJSON_GetObjectItem(doc, "text");
        const char* text = (text_item && cJSON_IsString(text_item)) ? text_item->valuestring : "";
        if (strlen(text) > 0) {
            ui_manager_show_transcription(text);
            ESP_LOGI(TAG, "Transcription: %s", text);
        }
    } else if (strcmp(msg_type, "audio_response") == 0) {
        cJSON* data_item = cJSON_GetObjectItem(doc, "data");
        
        const char* audio_data = (data_item && cJSON_IsString(data_item)) ? data_item->valuestring : "";
        
        if (strlen(audio_data) > 0) {
            ESP_LOGI(TAG, "Received audio response, starting playback");
            audio_start_playback();
            
            size_t input_len = strlen(audio_data);
            size_t output_len = 0;
            
            uint8_t* decoded = (uint8_t*)malloc(input_len);
            if (decoded != nullptr) {
                int result = mbedtls_base64_decode(decoded, input_len, &output_len, (const unsigned char*)audio_data, input_len);
                
                if (result == 0 && output_len > 0) {
                    int16_t* pcm_data = (int16_t*)decoded;
                    size_t samples = output_len / sizeof(int16_t);
                    audio_play_buffer(pcm_data, samples);
                } else {
                    ESP_LOGE(TAG, "Base64 decode failed: %d", result);
                }
                
                free(decoded);
            }
        }
    } else if (strcmp(msg_type, "enter_learning_mode") == 0) {
        ESP_LOGI(TAG, "Entering learning mode - starting audio capture");
        audio_start_capture();
        ui_manager_set_state(UI_STATE_LEARNING_MODE);
    } else if (strcmp(msg_type, "exit_learning_mode") == 0) {
        ESP_LOGI(TAG, "Exiting learning mode - stopping audio capture");
        audio_stop_capture();
        ui_manager_set_state(UI_STATE_READY);
    }
}

static void websocket_state_callback(WatchState state) {
    switch (state) {
        case WATCH_STATE_DISCONNECTED:
            ui_manager_set_state(UI_STATE_CONNECTING);
            break;
        case WATCH_STATE_CONNECTING:
            ui_manager_set_state(UI_STATE_CONNECTING);
            break;
        case WATCH_STATE_AUTHENTICATING:
            ui_manager_set_state(UI_STATE_CONNECTING);
            break;
        case WATCH_STATE_READY:
            ui_manager_set_state(UI_STATE_READY);
            break;
        case WATCH_STATE_LEARNING_MODE:
            ui_manager_set_state(UI_STATE_LEARNING_MODE);
            audio_start_capture();
            break;
        default:
            break;
    }
}

void smart_response_app_init() {
    if (app_screen != nullptr) {
        return;
    }
    
    app_screen = lv_obj_create(nullptr);
    lv_obj_set_style_bg_color(app_screen, lv_color_hex(0x1a1a1a), 0);
    lv_obj_remove_flag(app_screen, LV_OBJ_FLAG_SCROLLABLE);
    
    lv_obj_t* title = lv_label_create(app_screen);
    lv_label_set_text(title, "智回");
    lv_obj_set_style_text_font(title, font_manager_get_font(24, true), 0);
    lv_obj_set_style_text_color(title, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 20);
    
    status_label = lv_label_create(app_screen);
    lv_label_set_text(status_label, "连接中...");
    lv_obj_set_style_text_font(status_label, font_manager_get_font(18, true), 0);
    lv_obj_set_style_text_color(status_label, lv_color_hex(0x888888), 0);
    lv_obj_align(status_label, LV_ALIGN_CENTER, 0, 0);
    
    lv_obj_t* back_btn = lv_btn_create(app_screen);
    lv_obj_set_size(back_btn, 80, 40);
    lv_obj_align(back_btn, LV_ALIGN_BOTTOM_MID, 0, -20);
    lv_obj_add_event_cb(back_btn, back_btn_event_cb, LV_EVENT_CLICKED, nullptr);
    
    lv_obj_t* back_label = lv_label_create(back_btn);
    lv_label_set_text(back_label, "返回");
    lv_obj_set_style_text_font(back_label, font_manager_get_font(16, true), 0);
    lv_obj_center(back_label);
}

void smart_response_app_show() {
    if (app_screen == nullptr) {
        smart_response_app_init();
    }
    
    // Use centralized screen transition for consistent SPI queue handling
    display_switch_screen(app_screen);
    app_running = true;
    
    ui_manager_set_state(UI_STATE_CONNECTING);
    
    websocket_set_callbacks(websocket_message_callback, websocket_state_callback);
    
    std::string server_url = config_get_default_server_url();
    std::string watch_id = config_get_watch_id();
    std::string auth_token = config_get("auth_token", "");
    
    if (server_url.length() > 0 && watch_id.length() > 0 && wifi_is_connected()) {
        websocket_init();
        websocket_connect(server_url.c_str(), watch_id.c_str(), auth_token.c_str());
        ESP_LOGI(TAG, "Connecting to %s as %s", server_url.c_str(), watch_id.c_str());
    } else {
        ESP_LOGW(TAG, "Cannot connect - missing config or WiFi");
        if (server_url.length() == 0) {
            ESP_LOGW(TAG, "  Missing server_url");
        }
        if (watch_id.length() == 0) {
            ESP_LOGW(TAG, "  Missing watch_id");
        }
        if (!wifi_is_connected()) {
            ESP_LOGW(TAG, "  WiFi not connected");
        }
    }
    
    ESP_LOGI(TAG, "Started");
}

void smart_response_app_hide() {
    app_running = false;
    
    audio_stop_capture();
    audio_stop_playback();
    
    websocket_disconnect();
    
    ESP_LOGI(TAG, "Stopped");
}

void smart_response_app_update() {
    if (!app_running || app_screen == nullptr || status_label == nullptr) {
        return;
    }
    
    WatchState ws_state = websocket_get_state();
    
    if (ws_state == WATCH_STATE_READY || ws_state == WATCH_STATE_LEARNING_MODE) {
        if (ws_state == WATCH_STATE_LEARNING_MODE) {
            lv_label_set_text(status_label, "学习中...");
            lv_obj_set_style_text_color(status_label, lv_color_hex(0x00FF00), 0);
        } else {
            lv_label_set_text(status_label, "已连接");
            lv_obj_set_style_text_color(status_label, lv_color_hex(0x00FF00), 0);
        }
    } else if (ws_state == WATCH_STATE_CONNECTING || ws_state == WATCH_STATE_AUTHENTICATING) {
        lv_label_set_text(status_label, "连接中...");
        lv_obj_set_style_text_color(status_label, lv_color_hex(0xFFFF00), 0);
    } else if (wifi_is_connected()) {
        lv_label_set_text(status_label, "等待连接...");
        lv_obj_set_style_text_color(status_label, lv_color_hex(0xFFFF00), 0);
    } else {
        lv_label_set_text(status_label, "WiFi未连接");
        lv_obj_set_style_text_color(status_label, lv_color_hex(0xFF0000), 0);
    }
    
    if (ws_state == WATCH_STATE_LEARNING_MODE && audio_is_capturing()) {
        size_t samples = 0;
        int16_t* audio_data = audio_get_capture_buffer(&samples);
        if (audio_data != nullptr && samples > 0) {
            websocket_send_audio((uint8_t*)audio_data, samples * sizeof(int16_t));
        }
    }
}

bool smart_response_app_is_running() {
    return app_running;
}

void smart_response_app_destroy() {
    ESP_LOGI(TAG, "=== smart_response_app_destroy() called ===");
    
    if (app_screen == nullptr) {
        ESP_LOGI(TAG, "Smart response app screen already destroyed or never created");
        return;
    }
    
    // Stop any running operations first
    if (app_running) {
        smart_response_app_hide();
    }
    
    bsp_display_lock(0);
    
    ESP_LOGI(TAG, "Deleting smart response app screen and all children...");
    lv_obj_del(app_screen);
    
    // Set all pointers to nullptr for safety
    app_screen = nullptr;
    status_label = nullptr;
    
    bsp_display_unlock();
    
    ESP_LOGI(TAG, "Smart response app screen destroyed - memory freed");
    ESP_LOGI(TAG, "=== smart_response_app_destroy() finished ===");
}
