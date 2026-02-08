#include "ui_manager.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "config_manager.h"
#include "qrcode_generator.h"
#include "esp_log.h"
#include <string>

static const char* TAG = "UI_MGR";

static UIState current_state = UI_STATE_BOOT;
static bool ui_manager_initialized = false;
static lv_obj_t* watch_id_qrcode = nullptr;

void ui_manager_init() {
    if (ui_manager_initialized) {
        return;
    }
    
    current_state = UI_STATE_BOOT;
    // Screen functions manage their own display locking
    // Do NOT hold lock here - screen show functions have internal delays
    loading_screen_show();
    
    ui_manager_initialized = true;
}

void ui_manager_set_state(UIState state) {
    if (current_state == state) {
        return;
    }
    
    current_state = state;
    
    // CRITICAL FIX: Do NOT hold display lock while calling screen functions!
    // Screen show functions (launcher_show, standby_screen_show, etc.) internally call
    // display_switch_screen() which has vTaskDelay() calls for SPI queue management.
    // Holding the lock here for 500ms+ would starve LVGL's refresh task.
    // Each screen function manages its own display locking as needed.
    
    switch (state) {
        case UI_STATE_BOOT:
            loading_screen_show();
            break;
        case UI_STATE_SETUP:
            // TODO: Create setup screen or use launcher
            launcher_show();
            break;
        case UI_STATE_WAITING:
            // TODO: Create waiting screen or use standby
            standby_screen_show();
            break;
        case UI_STATE_CONNECTING:
            // Show standby screen with connecting status
            standby_screen_show();
            break;
        case UI_STATE_READY:
            {
                std::string student_name = config_get("student_name", "");
                if (student_name.length() > 0) {
                    // Show standby screen (it will display student name if available)
                    standby_screen_show();
                } else {
                    standby_screen_show();
                }
            }
            break;
        case UI_STATE_LEARNING_MODE:
            // TODO: Create learning mode screen or use launcher
            launcher_show();
            break;
        case UI_STATE_VOICE_INTERACTION:
            // Show standby screen with listening status
            standby_screen_show();
            break;
        case UI_STATE_ERROR:
            // TODO: Create error screen or use standby with error status
            standby_screen_show();
            ESP_LOGE(TAG, "Error occurred");
            break;
    }
}

UIState ui_manager_get_state() {
    return current_state;
}

void ui_manager_update() {
    if (!ui_manager_initialized) {
        ui_manager_init();
    }
    
    // BSP handles LVGL updates automatically via dedicated task
    // No need for manual display_update() call
}

void ui_manager_show_watch_id(const char* watch_id) {
    ESP_LOGI(TAG, "Watch ID - %s", watch_id);
    
    // Create QR code for watch ID if not already created
    if (watch_id_qrcode == nullptr && watch_id != nullptr && strlen(watch_id) > 0) {
        lv_display_t* disp = lv_display_get_default();
        if (disp != nullptr) {
            bsp_display_lock(0);
            lv_obj_t* current_screen = lv_screen_active();
            if (current_screen != nullptr) {
                // Create QR code on current screen (typically standby or setup screen)
                watch_id_qrcode = qrcode_create(current_screen, watch_id, 100, 155, 200);
                ESP_LOGI(TAG, "QR code created for watch ID: %s", watch_id);
            }
            bsp_display_unlock();
        }
    } else if (watch_id_qrcode != nullptr && watch_id != nullptr) {
        // Update existing QR code
        bsp_display_lock(0);
        qrcode_update(watch_id_qrcode, watch_id);
        bsp_display_unlock();
    }
}

void ui_manager_show_student_name(const char* student_name) {
    // TODO: Update display with student name
    ESP_LOGI(TAG, "Student - %s", student_name);
}

void ui_manager_show_transcription(const char* text) {
    // TODO: Update display with transcription
    ESP_LOGI(TAG, "Transcription - %s", text);
}

void ui_manager_show_error(const char* error_msg) {
    ESP_LOGE(TAG, "UI Error: %s", error_msg);
    // TODO: Create error display screen or update standby screen with error status
    // Screen functions manage their own display locking
    standby_screen_show();
}

void ui_manager_update_battery(int level, bool charging) {
    ESP_LOGI(TAG, "Battery - %d%% %s", level, charging ? "(charging)" : "");
}

void ui_manager_update_time(const char* time_str) {
    ESP_LOGI(TAG, "Time - %s", time_str);
}

void ui_manager_update_date(const char* date_str) {
    ESP_LOGI(TAG, "Date - %s", date_str);
}