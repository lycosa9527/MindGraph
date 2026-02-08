#include "standby_screen.h"
#include "loading_screen.h"
#include "app_state.h"
#include "rtc_manager.h"
#include "battery_manager.h"
#include "wifi_manager.h"
#include "ntp_sync.h"
#include "weather_api.h"
#include "launcher.h"
#include "font_manager.h"
#include "ui_icons.h"
#include "display_utils.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <lvgl.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <cstdio>

static const char* TAG = "STANDBY";

extern RTCManager rtcManager;
extern BatteryManager batteryManager;

static lv_obj_t* standby_screen = nullptr;
static bool standby_visible = false;
static int64_t last_update = 0;
static int64_t last_weather_fetch = 0;
static const int WEATHER_FETCH_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

// Static buffers to avoid stack overflow (embedded best practice)
static char time_str_buffer[8];
static char date_str_buffer[16];
static char temp_str_buffer[16];
static char ip_text_buffer[64];
static char batt_str_buffer[8];

// Previous value buffers for selective invalidation
// Only invalidate objects whose content actually changed to minimize SPI traffic
static char prev_time_str[8] = "";
static char prev_date_str[16] = "";
static char prev_weekday_str[8] = "";
static char prev_temp_str[16] = "";
static char prev_weather_str[32] = "";
static char prev_ip_str[64] = "";
static char prev_batt_str[8] = "";
static bool prev_wifi_connected = false;

// UI Elements
static lv_obj_t* time_label = nullptr;
static lv_obj_t* date_label = nullptr;
static lv_obj_t* weekday_label = nullptr;
static lv_obj_t* weather_label = nullptr;
static lv_obj_t* weather_temp_label = nullptr;
static lv_obj_t* ip_label = nullptr;
static lv_obj_t* battery_label = nullptr;
static lv_obj_t* wifi_icon_obj = nullptr;

// Professional color scheme - elegant dark theme
#define COLOR_BG_PRIMARY     lv_color_make(0x0A, 0x0E, 0x1A)  // Deep dark blue-gray
#define COLOR_BG_SECONDARY   lv_color_make(0x15, 0x1A, 0x25)  // Slightly lighter
#define COLOR_TEXT_PRIMARY   lv_color_make(0xE8, 0xEC, 0xF0)  // Light gray-white
#define COLOR_TEXT_SECONDARY lv_color_make(0x8A, 0x9B, 0xA8)  // Medium gray
#define COLOR_ACCENT         lv_color_make(0x4A, 0x9E, 0xFF)  // Bright blue
#define COLOR_TIME           lv_color_make(0xFF, 0xFF, 0xFF)  // Pure white for time
#define COLOR_DATE           lv_color_make(0xB8, 0xC5, 0xD6)  // Soft blue-gray

// Static styles
static lv_style_t style_bg;
static lv_style_t style_time;
static lv_style_t style_date;
static lv_style_t style_info;
static bool styles_initialized = false;

static void init_styles() {
    if (styles_initialized) return;
    
    // Background style - use solid color (gradient causes vertical bar artifacts)
    lv_style_init(&style_bg);
    lv_style_set_bg_color(&style_bg, COLOR_BG_PRIMARY);
    // Removed gradient - causes vertical bar rendering artifacts
    // lv_style_set_bg_grad_color(&style_bg, COLOR_BG_SECONDARY);
    // lv_style_set_bg_grad_dir(&style_bg, LV_GRAD_DIR_VER);
    lv_style_set_bg_opa(&style_bg, LV_OPA_COVER);
    
    // Time style - large, bold
    lv_style_init(&style_time);
    lv_style_set_text_color(&style_time, COLOR_TIME);
    lv_style_set_text_opa(&style_time, LV_OPA_COVER);
    lv_style_set_text_align(&style_time, LV_TEXT_ALIGN_CENTER);
    
    // Date style - medium, secondary color
    lv_style_init(&style_date);
    lv_style_set_text_color(&style_date, COLOR_DATE);
    lv_style_set_text_opa(&style_date, LV_OPA_COVER);
    lv_style_set_text_align(&style_date, LV_TEXT_ALIGN_CENTER);
    
    // Info style - small, secondary text
    lv_style_init(&style_info);
    lv_style_set_text_color(&style_info, COLOR_TEXT_SECONDARY);
    lv_style_set_text_opa(&style_info, LV_OPA_COVER);
    lv_style_set_text_align(&style_info, LV_TEXT_ALIGN_CENTER);
    
    styles_initialized = true;
}

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
    
    // Initialize styles
    init_styles();
    
    // Create main screen
    // NOTE: Screen objects created with lv_obj_create(nullptr) automatically fill the display
    // Do NOT set explicit size - it causes rendering artifacts (vertical bars)
    standby_screen = lv_obj_create(nullptr);
    lv_obj_remove_flag(standby_screen, LV_OBJ_FLAG_SCROLLABLE);
    // Removed: lv_obj_set_size() - screen objects auto-size to display
    // Removed: lv_obj_align() - screen objects are already positioned correctly
    // Use direct style setting like loading screen (instead of static style) to avoid rendering issues
    lv_obj_set_style_bg_color(standby_screen, COLOR_BG_PRIMARY, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(standby_screen, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_add_event_cb(standby_screen, standby_touch_event_cb, LV_EVENT_CLICKED, nullptr);
    lv_obj_add_event_cb(standby_screen, standby_touch_event_cb, LV_EVENT_PRESSED, nullptr);
    
    // Get font
    const lv_font_t* font_16 = font_manager_get_font(16, false);
    if (font_16 == nullptr) {
        font_16 = &lv_font_montserrat_14;
    }
    const lv_font_t* font_14 = &lv_font_montserrat_14;
    
    int screen_w = LV_HOR_RES;
    int screen_h = LV_VER_RES;
    
    // Calculate layout positions (centered, professional spacing)
    int center_y = screen_h / 2;
    int time_y = center_y - 60;      // Time above center
    int date_y = center_y - 10;       // Date near center
    int weekday_y = center_y + 15;   // Weekday below date
    int weather_y = center_y + 50;   // Weather info
    
    // TIME - Large, prominent (HH:MM format)
    time_label = lv_label_create(standby_screen);
    lv_obj_add_style(time_label, &style_time, 0);
    lv_obj_set_style_text_font(time_label, font_16, 0);
    lv_label_set_text(time_label, "--:--");
    lv_obj_align(time_label, LV_ALIGN_TOP_MID, 0, time_y);
    
    // DATE - Medium size (YYYY-MM-DD)
    date_label = lv_label_create(standby_screen);
    lv_obj_add_style(date_label, &style_date, 0);
    lv_obj_set_style_text_font(date_label, font_16, 0);
    lv_label_set_text(date_label, "---- -- --");
    lv_obj_align(date_label, LV_ALIGN_TOP_MID, 0, date_y);
    
    // WEEKDAY - Below date
    weekday_label = lv_label_create(standby_screen);
    lv_obj_add_style(weekday_label, &style_date, 0);
    lv_obj_set_style_text_font(weekday_label, font_14, 0);
    lv_label_set_text(weekday_label, "---");
    lv_obj_align(weekday_label, LV_ALIGN_TOP_MID, 0, weekday_y);
    
    // WEATHER - Temperature and condition
    weather_temp_label = lv_label_create(standby_screen);
    lv_obj_add_style(weather_temp_label, &style_info, 0);
    lv_obj_set_style_text_font(weather_temp_label, font_16, 0);
    lv_obj_set_style_text_color(weather_temp_label, COLOR_ACCENT, 0);
    lv_label_set_text(weather_temp_label, "--°C");
    lv_obj_align(weather_temp_label, LV_ALIGN_TOP_MID, 0, weather_y);
    
    weather_label = lv_label_create(standby_screen);
    lv_obj_add_style(weather_label, &style_info, 0);
    lv_obj_set_style_text_font(weather_label, font_14, 0);
    lv_label_set_text(weather_label, "No Data");
    lv_obj_align(weather_label, LV_ALIGN_TOP_MID, 0, weather_y + 20);
    
    // BOTTOM BAR - IP Address and Battery
    // IP Address (center aligned)
    ip_label = lv_label_create(standby_screen);
    lv_obj_add_style(ip_label, &style_info, 0);
    lv_obj_set_style_text_font(ip_label, font_14, 0);
    lv_label_set_text(ip_label, "Disconnected");
    lv_obj_align(ip_label, LV_ALIGN_BOTTOM_MID, 0, -10);
    
    // Battery (right side)
    battery_label = lv_label_create(standby_screen);
    lv_obj_add_style(battery_label, &style_info, 0);
    lv_obj_set_style_text_font(battery_label, font_14, 0);
    lv_label_set_text(battery_label, "--%");
    lv_obj_align(battery_label, LV_ALIGN_BOTTOM_RIGHT, -10, -10);
    
    // WiFi icon (top right)
    wifi_icon_obj = icon_create(standby_screen, ICON_WIFI_DISCONNECTED, 20, screen_w - 30, 10);
    
    // NTP sync and weather API will be initialized later after WiFi is ready
    // They are initialized in standby_screen_show() to avoid boot loop
    
    standby_visible = false;
    bsp_display_unlock();
    
    ESP_LOGI(TAG, "Standby screen initialized - Clean professional design");
}

void standby_screen_show() {
    ESP_LOGI(TAG, "=== standby_screen_show() called ===");
    
    // Debug: Check current active screen before showing
    lv_obj_t* current_screen = lv_screen_active();
    ESP_LOGI(TAG, "[DEBUG] Current active screen before show: %p (standby_screen=%p)", 
             current_screen, standby_screen);
    
    // Debug: Check if loading screen is still visible
    bool loading_vis = loading_screen_is_visible();
    ESP_LOGI(TAG, "[DEBUG] loading_screen_is_visible()=%d", loading_vis);
    
    if (standby_screen == nullptr) {
        ESP_LOGI(TAG, "[DEBUG] standby_screen is nullptr, calling init...");
        standby_screen_init();
    }
    
    if (standby_screen == nullptr) {
        ESP_LOGE(TAG, "[DEBUG] standby_screen is still nullptr after init!");
        return;
    }
    
    // Initialize NTP sync and weather API when showing (after WiFi is ready)
    static bool ntp_weather_initialized = false;
    if (!ntp_weather_initialized) {
        ESP_LOGI(TAG, "[DEBUG] Initializing NTP and weather API...");
        // Initialize NTP sync
        ntp_sync_init();
        
        // Initialize weather API
        weather_api_init();
        
        // Configure weather API - QWeather (和风天气)
        // API Key: 210d39e0b1e644bdbfb0c28af693ea94
        // Location: 北京昌平 (Changping, Beijing) - Location ID: 101010700
        weather_api_set_config("210d39e0b1e644bdbfb0c28af693ea94", "101010700", nullptr);
        ESP_LOGI(TAG, "Weather API configured for Changping, Beijing (101010700)");
        
        ntp_weather_initialized = true;
    }
    
    // CRITICAL FIX: Release lock BEFORE calling lv_screen_load()
    // lv_screen_load() marks the screen dirty and queues refresh operations
    // Holding the lock prevents LVGL's refresh task from processing the SPI queue
    // This causes "spi transmit (queue) color failed" errors
    bsp_display_lock(0);
    
    // Debug: Check if loading screen objects are still visible
    lv_obj_t* loading_obj = get_loading_screen_obj();
    if (loading_obj != nullptr) {
        bool loading_hidden = lv_obj_has_flag(loading_obj, LV_OBJ_FLAG_HIDDEN);
        ESP_LOGI(TAG, "[DEBUG] Loading screen object exists: %p, hidden=%d", loading_obj, loading_hidden);
    } else {
        ESP_LOGI(TAG, "[DEBUG] Loading screen object is nullptr");
    }
    
    bsp_display_unlock();
    
    // Use the centralized screen transition function
    // This handles SPI queue management and ensures complete rendering
    ESP_LOGI(TAG, "[DEBUG] Switching to standby screen...");
    display_switch_screen(standby_screen);
    
    // Debug: Verify screen was loaded
    lv_obj_t* active_screen = lv_screen_active();
    if (active_screen == standby_screen) {
        ESP_LOGI(TAG, "[DEBUG] [OK] Standby screen successfully loaded, active screen matches");
    } else {
        ESP_LOGW(TAG, "[DEBUG] [WARN] Active screen mismatch! Expected %p, got %p", standby_screen, active_screen);
    }
    
    standby_visible = true;
    last_update = 0;
    
    // Delay immediate update to ensure everything is initialized
    // Update will happen in the main loop
    // standby_screen_update();
    
    ESP_LOGI(TAG, "[DEBUG] standby_screen_show() completed, standby_visible=%d", standby_visible);
    ESP_LOGI(TAG, "=== standby_screen_show() finished ===");
}

void standby_screen_hide() {
    standby_visible = false;
    ESP_LOGI(TAG, "Standby screen hidden");
}

void standby_screen_update() {
    if (!standby_visible || standby_screen == nullptr) {
        return;
    }
    
    int64_t current_time = esp_timer_get_time() / 1000;
    // Reduce update frequency to prevent SPI queue overflow (root cause of horizontal bars)
    // Update every 2 seconds instead of 1 second to avoid overwhelming SPI queue
    if (current_time - last_update < 2000) {
        return;
    }
    last_update = current_time;
    
    // Get current app state ONCE (using fixed-size buffers - no heap allocations)
    AppState state = app_state_get();
    
    // Fetch weather periodically when WiFi is connected
    int64_t current_time_ms = esp_timer_get_time() / 1000;
    if (state.wifi_connected && 
        (current_time_ms - last_weather_fetch > WEATHER_FETCH_INTERVAL_MS)) {
        if (weather_api_fetch()) {
            last_weather_fetch = current_time_ms;
            ESP_LOGI(TAG, "Weather fetch initiated");
        }
    }
    
    // SELECTIVE INVALIDATION: Track which objects actually changed
    // Only invalidate objects with new content to minimize SPI traffic
    bool time_changed = false;
    bool date_changed = false;
    bool weekday_changed = false;
    bool temp_changed = false;
    bool weather_changed = false;
    bool ip_changed = false;
    bool batt_changed = false;
    bool wifi_changed = false;
    
    // Temporary buffers for weekday and weather condition
    char weekday_str[8] = "";
    char weather_cond_str[32] = "";
    
    // Update TIME (HH:MM format)
    // Minimize display lock duration to prevent SPI queue overflow
    bsp_display_lock(0);
    
    if (time_label != nullptr) {
        if (rtcManager.isValid()) {
            uint8_t hour, minute, second;
            rtcManager.getTime(&hour, &minute, &second);
            snprintf(time_str_buffer, sizeof(time_str_buffer), "%02d:%02d", (int)hour, (int)minute);
        } else {
            snprintf(time_str_buffer, sizeof(time_str_buffer), "--:--");
        }
        if (strcmp(time_str_buffer, prev_time_str) != 0) {
            lv_label_set_text(time_label, time_str_buffer);
            strncpy(prev_time_str, time_str_buffer, sizeof(prev_time_str) - 1);
            time_changed = true;
        }
    }
    
    // Update DATE (YYYY-MM-DD)
    if (date_label != nullptr && weekday_label != nullptr) {
        if (rtcManager.isValid()) {
            uint8_t day, month;
            uint16_t year;
            rtcManager.getDate(&day, &month, &year);
            
            // Format date
            snprintf(date_str_buffer, sizeof(date_str_buffer), "%04d-%02d-%02d", (int)year, (int)month, (int)day);
            
            // Calculate weekday
            const char* weekdays[] = {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"};
            int y = (int)year;
            int m = (int)month;
            int d = (int)day;
            
            if (m < 3) {
                m += 12;
                y -= 1;
            }
            
            int k = y % 100;
            int j = y / 100;
            int day_of_week = (d + (13 * (m + 1)) / 5 + k + k / 4 + j / 4 - 2 * j) % 7;
            if (day_of_week < 0) day_of_week += 7;
            
            if (day_of_week >= 0 && day_of_week < 7) {
                strncpy(weekday_str, weekdays[day_of_week], sizeof(weekday_str) - 1);
            }
        } else {
            snprintf(date_str_buffer, sizeof(date_str_buffer), "---- -- --");
            strncpy(weekday_str, "---", sizeof(weekday_str) - 1);
        }
        
        if (strcmp(date_str_buffer, prev_date_str) != 0) {
            lv_label_set_text(date_label, date_str_buffer);
            strncpy(prev_date_str, date_str_buffer, sizeof(prev_date_str) - 1);
            date_changed = true;
        }
        if (strcmp(weekday_str, prev_weekday_str) != 0) {
            lv_label_set_text(weekday_label, weekday_str);
            strncpy(prev_weekday_str, weekday_str, sizeof(prev_weekday_str) - 1);
            weekday_changed = true;
        }
    }
    
    // Update WEATHER (from app state - reuse state from above)
    if (weather_temp_label != nullptr && weather_label != nullptr) {
        if (state.weather_available) {
            // Format temperature
            snprintf(temp_str_buffer, sizeof(temp_str_buffer), "%.0f°C", state.weather_temperature);
            
            // Format condition
            if (state.weather_condition[0] != '\0') {
                strncpy(weather_cond_str, state.weather_condition, sizeof(weather_cond_str) - 1);
            } else {
                strncpy(weather_cond_str, "Clear", sizeof(weather_cond_str) - 1);
            }
        } else {
            // No valid data yet
            snprintf(temp_str_buffer, sizeof(temp_str_buffer), "--°C");
            if (state.wifi_connected) {
                strncpy(weather_cond_str, "Loading...", sizeof(weather_cond_str) - 1);
            } else {
                strncpy(weather_cond_str, "No WiFi", sizeof(weather_cond_str) - 1);
            }
        }
        
        if (strcmp(temp_str_buffer, prev_temp_str) != 0) {
            lv_label_set_text(weather_temp_label, temp_str_buffer);
            strncpy(prev_temp_str, temp_str_buffer, sizeof(prev_temp_str) - 1);
            temp_changed = true;
        }
        if (strcmp(weather_cond_str, prev_weather_str) != 0) {
            lv_label_set_text(weather_label, weather_cond_str);
            strncpy(prev_weather_str, weather_cond_str, sizeof(prev_weather_str) - 1);
            weather_changed = true;
        }
    }
    
    // Update IP ADDRESS (from app state - reuse state from above)
    if (ip_label != nullptr) {
        if (state.wifi_connected && state.wifi_ip[0] != '\0') {
            snprintf(ip_text_buffer, sizeof(ip_text_buffer), "Connected: %s", state.wifi_ip);
        } else {
            snprintf(ip_text_buffer, sizeof(ip_text_buffer), "Disconnected");
        }
        
        if (strcmp(ip_text_buffer, prev_ip_str) != 0) {
            lv_label_set_text(ip_label, ip_text_buffer);
            if (state.wifi_connected && state.wifi_ip[0] != '\0') {
                lv_obj_set_style_text_color(ip_label, COLOR_ACCENT, 0);
            } else {
                lv_obj_set_style_text_color(ip_label, lv_color_make(0xFF, 0x00, 0x00), 0); // Red
            }
            strncpy(prev_ip_str, ip_text_buffer, sizeof(prev_ip_str) - 1);
            ip_changed = true;
        }
    }
    
    // Update BATTERY (from app state)
    if (battery_label != nullptr) {
        int battery_level = batteryManager.getBatteryLevel();
        bool charging = batteryManager.isCharging();
        
        // Update app state if changed
        app_state_set_battery(battery_level, charging);
        
        snprintf(batt_str_buffer, sizeof(batt_str_buffer), "%d%%", battery_level);
        
        if (strcmp(batt_str_buffer, prev_batt_str) != 0) {
            lv_label_set_text(battery_label, batt_str_buffer);
            
            // Change color based on level
            if (battery_level > 50) {
                lv_obj_set_style_text_color(battery_label, COLOR_TEXT_SECONDARY, 0);
            } else if (battery_level > 20) {
                lv_obj_set_style_text_color(battery_label, lv_color_make(0xFF, 0xFF, 0x00), 0);
            } else {
                lv_obj_set_style_text_color(battery_label, lv_color_make(0xFF, 0x00, 0x00), 0);
            }
            strncpy(prev_batt_str, batt_str_buffer, sizeof(prev_batt_str) - 1);
            batt_changed = true;
        }
    }
    
    // Update WiFi icon (from app state - reuse state from above)
    if (wifi_icon_obj != nullptr) {
        if (state.wifi_connected != prev_wifi_connected) {
            if (state.wifi_connected) {
                icon_set_type(wifi_icon_obj, ICON_WIFI_CONNECTED);
            } else {
                icon_set_type(wifi_icon_obj, ICON_WIFI_DISCONNECTED);
            }
            prev_wifi_connected = state.wifi_connected;
            wifi_changed = true;
        }
    }
    
    // SELECTIVE INVALIDATION: Only invalidate objects that actually changed
    // This dramatically reduces SPI traffic and prevents queue overflow
    if (time_changed && time_label != nullptr) lv_obj_invalidate(time_label);
    if (date_changed && date_label != nullptr) lv_obj_invalidate(date_label);
    if (weekday_changed && weekday_label != nullptr) lv_obj_invalidate(weekday_label);
    if (temp_changed && weather_temp_label != nullptr) lv_obj_invalidate(weather_temp_label);
    if (weather_changed && weather_label != nullptr) lv_obj_invalidate(weather_label);
    if (ip_changed && ip_label != nullptr) lv_obj_invalidate(ip_label);
    if (batt_changed && battery_label != nullptr) lv_obj_invalidate(battery_label);
    if (wifi_changed && wifi_icon_obj != nullptr) lv_obj_invalidate(wifi_icon_obj);
    
    bsp_display_unlock();
    // LVGL's dedicated task will refresh invalidated areas automatically
    // Small delay to let SPI queue process before next update
    vTaskDelay(pdMS_TO_TICKS(10));
}

bool standby_screen_is_visible() {
    return standby_visible;
}

void standby_screen_destroy() {
    ESP_LOGI(TAG, "=== standby_screen_destroy() called ===");
    
    if (standby_screen == nullptr) {
        ESP_LOGI(TAG, "Standby screen already destroyed or never created");
        return;
    }
    
    standby_visible = false;
    
    // Reset previous value buffers for selective invalidation
    prev_time_str[0] = '\0';
    prev_date_str[0] = '\0';
    prev_weekday_str[0] = '\0';
    prev_temp_str[0] = '\0';
    prev_weather_str[0] = '\0';
    prev_ip_str[0] = '\0';
    prev_batt_str[0] = '\0';
    prev_wifi_connected = false;
    
    bsp_display_lock(0);
    
    ESP_LOGI(TAG, "Deleting standby screen object and all children...");
    lv_obj_del(standby_screen);
    
    // Set all pointers to nullptr for safety
    standby_screen = nullptr;
    time_label = nullptr;
    date_label = nullptr;
    weekday_label = nullptr;
    weather_label = nullptr;
    weather_temp_label = nullptr;
    ip_label = nullptr;
    battery_label = nullptr;
    wifi_icon_obj = nullptr;
    
    bsp_display_unlock();
    
    ESP_LOGI(TAG, "Standby screen destroyed - memory freed");
    ESP_LOGI(TAG, "=== standby_screen_destroy() finished ===");
}
