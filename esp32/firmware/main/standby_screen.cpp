#include "standby_screen.h"
#include "rtc_manager.h"
#include "battery_manager.h"
#include "wifi_manager.h"
#include "websocket_client.h"
#include "launcher.h"
#include "font_manager.h"
#include "wallpaper_manager.h"
#include "ui_icons.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "esp_log.h"
#include "esp_timer.h"
#include <stdint.h>
#include <stdbool.h>
#include <string>

static const char* TAG = "STANDBY";

extern RTCManager rtcManager;
extern BatteryManager batteryManager;

static lv_obj_t* standby_screen = nullptr;
static lv_obj_t* time_label = nullptr;
static lv_obj_t* date_label = nullptr;
static lv_obj_t* battery_label = nullptr;
static lv_obj_t* battery_icon = nullptr;
static lv_obj_t* wifi_icon = nullptr;
static lv_obj_t* status_label = nullptr;
static bool standby_visible = false;
static int64_t last_update = 0;

static void standby_touch_event_cb(lv_event_t* e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED || code == LV_EVENT_PRESSED) {
        standby_screen_hide();
        launcher_show();
    }
}

void standby_screen_init() {
    if (standby_screen != nullptr) {
        return;
    }
    
    bsp_display_lock(0);
    standby_screen = lv_obj_create(nullptr);
    // Use wallpaper manager for background
    wallpaper_set(standby_screen, WALLPAPER_READY);
    lv_obj_remove_flag(standby_screen, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(standby_screen, standby_touch_event_cb, LV_EVENT_CLICKED, nullptr);
    lv_obj_add_event_cb(standby_screen, standby_touch_event_cb, LV_EVENT_PRESSED, nullptr);
    
    time_label = lv_label_create(standby_screen);
    lv_label_set_text(time_label, "00:00:00");
    lv_obj_set_style_text_font(time_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(time_label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(time_label, LV_ALIGN_CENTER, 0, -60);
    
    date_label = lv_label_create(standby_screen);
    lv_label_set_text(date_label, "2026-02-03");
    lv_obj_set_style_text_font(date_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(date_label, lv_color_hex(0x888888), 0);
    lv_obj_align(date_label, LV_ALIGN_CENTER, 0, -10);
    
    status_label = lv_label_create(standby_screen);
    const lv_font_t* chinese_font = font_manager_get_font(16, true);
    if (chinese_font == nullptr) {
        ESP_LOGE(TAG, "Chinese font not available for status_label!");
        chinese_font = &lv_font_montserrat_14;
    } else {
        ESP_LOGI(TAG, "Setting Chinese font for status_label: line_height=%d", chinese_font->line_height);
    }
    // Set font BEFORE setting text to ensure LVGL uses it
    lv_obj_set_style_text_font(status_label, chinese_font, 0);
    lv_label_set_text(status_label, "就绪");
    lv_obj_set_style_text_color(status_label, lv_color_hex(0x00FF00), 0);
    lv_obj_align(status_label, LV_ALIGN_CENTER, 0, 30);
    
    battery_label = lv_label_create(standby_screen);
    lv_label_set_text(battery_label, "100%");
    lv_obj_set_style_text_font(battery_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(battery_label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(battery_label, LV_ALIGN_TOP_RIGHT, -10, 10);
    
    // Use ui_icons module for battery and WiFi icons
    battery_icon = icon_create(standby_screen, ICON_BATTERY_FULL, 20, -50, 10);
    
    wifi_icon = icon_create(standby_screen, ICON_WIFI_CONNECTED, 20, 10, 10);
    
    standby_visible = false;
    bsp_display_unlock();
}

void standby_screen_show() {
    if (standby_screen == nullptr) {
        standby_screen_init();
    }
    
    bsp_display_lock(0);
    lv_screen_load(standby_screen);
    bsp_display_unlock();
    standby_visible = true;
    last_update = 0;
    standby_screen_update();
    
    ESP_LOGI(TAG, "Shown");
}

void standby_screen_hide() {
    standby_visible = false;
    ESP_LOGI(TAG, "Hidden");
}

void standby_screen_update() {
    if (!standby_visible || standby_screen == nullptr) {
        return;
    }
    
    int64_t current_time = esp_timer_get_time() / 1000;
    if (current_time - last_update < 1000) {
        return;
    }
    last_update = current_time;
    
    bsp_display_lock(0);
    if (time_label != nullptr) {
        std::string time_str = rtcManager.getTimeString();
        lv_label_set_text(time_label, time_str.c_str());
    }
    
    if (date_label != nullptr) {
        std::string date_str = rtcManager.getDateString();
        lv_label_set_text(date_label, date_str.c_str());
    }
    
    if (battery_label != nullptr) {
        int battery_level = batteryManager.getBatteryLevel();
        bool charging = batteryManager.isCharging();
        
        char battery_text[16];
        snprintf(battery_text, sizeof(battery_text), "%d%%", battery_level);
        lv_label_set_text(battery_label, battery_text);
        
        // Update battery icon using ui_icons module
        if (charging) {
            lv_obj_set_style_text_color(battery_label, lv_color_hex(0x00FF00), 0);
            icon_set_type(battery_icon, ICON_BATTERY_CHARGING);
        } else if (battery_level > 50) {
            lv_obj_set_style_text_color(battery_label, lv_color_hex(0x00FF00), 0);
            icon_set_type(battery_icon, ICON_BATTERY_FULL);
        } else if (battery_level > 20) {
            lv_obj_set_style_text_color(battery_label, lv_color_hex(0xFFFF00), 0);
            icon_set_type(battery_icon, ICON_BATTERY_MEDIUM);
        } else {
            lv_obj_set_style_text_color(battery_label, lv_color_hex(0xFF0000), 0);
            icon_set_type(battery_icon, ICON_BATTERY_LOW);
        }
    }
    
    // Update WiFi icon using ui_icons module
    if (wifi_icon != nullptr) {
        if (wifi_is_connected()) {
            icon_set_type(wifi_icon, ICON_WIFI_CONNECTED);
        } else {
            icon_set_type(wifi_icon, ICON_WIFI_DISCONNECTED);
        }
    }
    
    if (status_label != nullptr) {
        const lv_font_t* chinese_font = font_manager_get_font(16, true);
        if (chinese_font != nullptr) {
            // Set font BEFORE setting text to ensure LVGL uses it
            lv_obj_set_style_text_font(status_label, chinese_font, 0);
        }
        if (websocket_is_connected()) {
            lv_label_set_text(status_label, "已连接");
            lv_obj_set_style_text_color(status_label, lv_color_hex(0x00FF00), 0);
        } else if (wifi_is_connected()) {
            lv_label_set_text(status_label, "连接中...");
            lv_obj_set_style_text_color(status_label, lv_color_hex(0xFFFF00), 0);
        } else {
            lv_label_set_text(status_label, "离线");
            lv_obj_set_style_text_color(status_label, lv_color_hex(0xFF0000), 0);
        }
    }
    bsp_display_unlock();
}

bool standby_screen_is_visible() {
    return standby_visible;
}
