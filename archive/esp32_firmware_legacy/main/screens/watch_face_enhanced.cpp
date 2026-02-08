// Enhanced Watch Face for ESP32
// Adapted from digital watch face design
// Integrated with ESP32 project's RTC, Battery, and WiFi managers

#include "standby_screen.h"
#include "rtc_manager.h"
#include "battery_manager.h"
#include "wifi_manager.h"
#include "font_manager.h"
#include "wallpaper_manager.h"
#include "ui_icons.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include <lvgl.h>
#include <stdint.h>
#include <stdbool.h>
#include <string>
#include <cstdlib>
#include <cstring>

static const char* TAG = "WATCH_FACE";

extern RTCManager rtcManager;
extern BatteryManager batteryManager;

// Screen resolution - use LVGL macros
#define SCREEN_WIDTH LV_HOR_RES
#define SCREEN_HEIGHT LV_VER_RES

// Global UI elements
static lv_obj_t* time_hour_label = nullptr;
static lv_obj_t* time_min_label = nullptr;
static lv_obj_t* time_colon_label = nullptr;
static lv_obj_t* date_label = nullptr;
static lv_obj_t* weekday_label = nullptr;
static lv_obj_t* battery_label = nullptr;
static lv_obj_t* battery_arc = nullptr;
static lv_obj_t* ip_label = nullptr;
static lv_obj_t* wifi_status_label = nullptr;

// AMOLED theme colors
#define COLOR_PRIMARY lv_color_make(0x00, 0xC6, 0xFF)    // Bright cyan
#define COLOR_SECONDARY lv_color_make(0xFF, 0x2D, 0x78)  // Pink
#define COLOR_ACCENT lv_color_make(0x9D, 0x4E, 0xFF)    // Purple
#define COLOR_BACKGROUND lv_color_make(0x0A, 0x0A, 0x12) // Dark blue-black
#define COLOR_TEXT lv_color_white()

// Static variables for colon blinking
static bool colon_visible = true;
static int64_t last_colon_toggle = 0;

// Create gradient background with stars
static void create_gradient_background(lv_obj_t* parent) {
    // Set background color
    lv_obj_set_style_bg_color(parent, COLOR_BACKGROUND, 0);
    
    // Create gradient effect using style
    static lv_style_t style_bg;
    lv_style_init(&style_bg);
    lv_style_set_bg_color(&style_bg, COLOR_BACKGROUND);
    lv_style_set_bg_grad_color(&style_bg, lv_color_make(0x15, 0x15, 0x25));
    lv_style_set_bg_grad_dir(&style_bg, LV_GRAD_DIR_VER);
    lv_obj_add_style(parent, &style_bg, 0);
    
    // Add star effect (simplified - fewer stars for performance)
    for(int i = 0; i < 20; i++) {
        lv_obj_t* star = lv_obj_create(parent);
        int size = 1 + (rand() % 2);
        lv_obj_set_size(star, size, size);
        lv_obj_set_pos(star, rand() % SCREEN_WIDTH, rand() % SCREEN_HEIGHT);
        lv_obj_set_style_bg_color(star, lv_color_make(200 + rand() % 55, 200 + rand() % 55, 255), 0);
        lv_obj_set_style_bg_opa(star, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(star, LV_RADIUS_CIRCLE, 0);
        lv_obj_clear_flag(star, LV_OBJ_FLAG_CLICKABLE);
    }
}

// Create large time display (adapted for available fonts)
static void create_time_display(lv_obj_t* parent) {
    // Create time container
    lv_obj_t* time_container = lv_obj_create(parent);
    lv_obj_remove_style_all(time_container);
    lv_obj_set_size(time_container, SCREEN_WIDTH - 40, 120);
    lv_obj_align(time_container, LV_ALIGN_TOP_MID, 0, 40);
    lv_obj_set_style_bg_opa(time_container, LV_OPA_TRANSP, 0);
    
    // Get largest available font (16px)
    const lv_font_t* time_font = font_manager_get_font(16, false);
    if (time_font == nullptr) {
        time_font = &lv_font_montserrat_14;
    }
    
    // Hour display - use larger text by scaling
    // Note: Scale value is in 256ths (256 = 1x, 512 = 2x, 768 = 3x)
    time_hour_label = lv_label_create(time_container);
    lv_obj_set_style_text_font(time_hour_label, time_font, 0);
    lv_obj_set_style_text_color(time_hour_label, COLOR_PRIMARY, 0);
    lv_label_set_text(time_hour_label, "12");
    // Scale up using transform (LVGL v9: scale in 256ths, 768 = 3x)
    lv_obj_set_style_transform_scale(time_hour_label, 768, 0);
    lv_obj_set_style_transform_pivot_x(time_hour_label, 0, 0);
    lv_obj_set_style_transform_pivot_y(time_hour_label, 0, 0);
    lv_obj_align(time_hour_label, LV_ALIGN_LEFT_MID, -20, 0);
    
    // Colon (blinking)
    time_colon_label = lv_label_create(time_container);
    lv_obj_set_style_text_font(time_colon_label, time_font, 0);
    lv_obj_set_style_text_color(time_colon_label, COLOR_PRIMARY, 0);
    lv_label_set_text(time_colon_label, ":");
    lv_obj_set_style_transform_scale(time_colon_label, 768, 0);
    lv_obj_set_style_transform_pivot_x(time_colon_label, 0, 0);
    lv_obj_set_style_transform_pivot_y(time_colon_label, 0, 0);
    lv_obj_align(time_colon_label, LV_ALIGN_CENTER, 0, 0);
    
    // Minute display
    time_min_label = lv_label_create(time_container);
    lv_obj_set_style_text_font(time_min_label, time_font, 0);
    lv_obj_set_style_text_color(time_min_label, COLOR_PRIMARY, 0);
    lv_label_set_text(time_min_label, "30");
    lv_obj_set_style_transform_scale(time_min_label, 768, 0);
    lv_obj_set_style_transform_pivot_x(time_min_label, 0, 0);
    lv_obj_set_style_transform_pivot_y(time_min_label, 0, 0);
    lv_obj_align(time_min_label, LV_ALIGN_RIGHT_MID, 20, 0);
    
    // Add glow effect using shadow
    static lv_style_t style_glow;
    lv_style_init(&style_glow);
    lv_style_set_shadow_color(&style_glow, COLOR_PRIMARY);
    lv_style_set_shadow_width(&style_glow, 15);
    lv_style_set_shadow_spread(&style_glow, 3);
    lv_style_set_shadow_opa(&style_glow, LV_OPA_60);
    
    lv_obj_add_style(time_hour_label, &style_glow, 0);
    lv_obj_add_style(time_min_label, &style_glow, 0);
}

// Create date and weekday display
static void create_date_display(lv_obj_t* parent) {
    // Create date container
    lv_obj_t* date_container = lv_obj_create(parent);
    lv_obj_remove_style_all(date_container);
    lv_obj_set_size(date_container, SCREEN_WIDTH - 40, 60);
    lv_obj_align(date_container, LV_ALIGN_TOP_MID, 0, 140);
    lv_obj_set_style_bg_opa(date_container, LV_OPA_TRANSP, 0);
    
    const lv_font_t* date_font = font_manager_get_font(16, false);
    if (date_font == nullptr) {
        date_font = &lv_font_montserrat_14;
    }
    
    // Date display
    date_label = lv_label_create(date_container);
    lv_obj_set_style_text_font(date_label, date_font, 0);
    lv_obj_set_style_text_color(date_label, COLOR_TEXT, 0);
    lv_label_set_text(date_label, "2026-02-04");
    lv_obj_align(date_label, LV_ALIGN_CENTER, 0, -15);
    
    // Weekday display
    weekday_label = lv_label_create(date_container);
    lv_obj_set_style_text_font(weekday_label, date_font, 0);
    lv_obj_set_style_text_color(weekday_label, COLOR_SECONDARY, 0);
    lv_label_set_text(weekday_label, "WEDNESDAY");
    lv_obj_align(weekday_label, LV_ALIGN_CENTER, 0, 15);
}

// Create battery display with arc indicator
static void create_battery_display(lv_obj_t* parent) {
    // Battery arc indicator
    battery_arc = lv_arc_create(parent);
    lv_arc_set_rotation(battery_arc, 270);
    lv_arc_set_bg_angles(battery_arc, 0, 360);
    lv_arc_set_angles(battery_arc, 0, 270); // Start at 75%
    lv_obj_set_size(battery_arc, 60, 60);
    lv_obj_align(battery_arc, LV_ALIGN_BOTTOM_LEFT, 30, -40);
    
    // Set arc style
    lv_obj_set_style_arc_color(battery_arc, COLOR_PRIMARY, LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(battery_arc, 6, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(battery_arc, lv_color_make(60, 60, 80), LV_PART_MAIN);
    lv_obj_set_style_arc_width(battery_arc, 6, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(battery_arc, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(battery_arc, 0, LV_PART_MAIN);
    
    // Battery percentage label
    battery_label = lv_label_create(parent);
    const lv_font_t* font = font_manager_get_font(16, false);
    if (font == nullptr) {
        font = &lv_font_montserrat_14;
    }
    lv_obj_set_style_text_font(battery_label, font, 0);
    lv_obj_set_style_text_color(battery_label, COLOR_TEXT, 0);
    lv_label_set_text(battery_label, "75%");
    lv_obj_align_to(battery_label, battery_arc, LV_ALIGN_OUT_BOTTOM_MID, 0, 5);
}

// Create WiFi/IP display
static void create_wifi_display(lv_obj_t* parent) {
    // WiFi container
    lv_obj_t* wifi_container = lv_obj_create(parent);
    lv_obj_remove_style_all(wifi_container);
    lv_obj_set_size(wifi_container, SCREEN_WIDTH - 40, 50);
    lv_obj_align(wifi_container, LV_ALIGN_BOTTOM_MID, 0, -20);
    lv_obj_set_style_bg_opa(wifi_container, LV_OPA_TRANSP, 0);
    
    const lv_font_t* font = font_manager_get_font(16, false);
    if (font == nullptr) {
        font = &lv_font_montserrat_14;
    }
    
    // WiFi status label
    wifi_status_label = lv_label_create(wifi_container);
    lv_obj_set_style_text_font(wifi_status_label, font, 0);
    lv_obj_set_style_text_color(wifi_status_label, COLOR_SECONDARY, 0);
    lv_label_set_text(wifi_status_label, "WiFi");
    lv_obj_align(wifi_status_label, LV_ALIGN_LEFT_MID, 0, 0);
    
    // IP address label
    ip_label = lv_label_create(wifi_container);
    lv_obj_set_style_text_font(ip_label, font, 0);
    lv_obj_set_style_text_color(ip_label, COLOR_TEXT, 0);
    lv_label_set_text(ip_label, "0.0.0.0");
    lv_obj_align(ip_label, LV_ALIGN_RIGHT_MID, 0, 0);
}

// Create status bar at top
static void create_status_bar(lv_obj_t* parent) {
    // Status bar container
    lv_obj_t* status_bar = lv_obj_create(parent);
    lv_obj_remove_style_all(status_bar);
    lv_obj_set_size(status_bar, SCREEN_WIDTH, 25);
    lv_obj_align(status_bar, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_opa(status_bar, LV_OPA_TRANSP, 0);
    
    const lv_font_t* font = font_manager_get_font(16, false);
    if (font == nullptr) {
        font = &lv_font_montserrat_14;
    }
    
    // WiFi icon (using existing icon system)
    lv_obj_t* wifi_icon_obj = icon_create(status_bar, ICON_WIFI_CONNECTED, 20, 5, 5);
    
    // Small time display in status bar
    lv_obj_t* status_time = lv_label_create(status_bar);
    lv_obj_set_style_text_font(status_time, font, 0);
    lv_obj_set_style_text_color(status_time, COLOR_TEXT, 0);
    lv_label_set_text(status_time, "12:30");
    lv_obj_align(status_time, LV_ALIGN_CENTER, 0, 0);
}

// Initialize enhanced watch face
void watch_face_enhanced_init(lv_obj_t* parent) {
    if (parent == nullptr) {
        ESP_LOGE(TAG, "Parent object is null");
        return;
    }
    
    ESP_LOGI(TAG, "Initializing enhanced watch face");
    
    // Initialize random seed for stars
    srand(esp_timer_get_time() / 1000);
    
    // Create gradient background
    create_gradient_background(parent);
    
    // Create status bar
    create_status_bar(parent);
    
    // Create time display
    create_time_display(parent);
    
    // Create date display
    create_date_display(parent);
    
    // Create battery display
    create_battery_display(parent);
    
    // Create WiFi/IP display
    create_wifi_display(parent);
    
    ESP_LOGI(TAG, "Enhanced watch face initialized");
}

// Update watch face display
void watch_face_enhanced_update() {
    if (time_hour_label == nullptr || time_min_label == nullptr) {
        return;
    }
    
    // Get time from RTC manager
    uint8_t hour, minute, second;
    rtcManager.getTime(&hour, &minute, &second);
    
    // Format time strings
    char hour_str[4];
    char min_str[4];
    snprintf(hour_str, sizeof(hour_str), "%02d", (int)hour);
    snprintf(min_str, sizeof(min_str), "%02d", (int)minute);
    
    // Update time labels
    lv_label_set_text(time_hour_label, hour_str);
    lv_label_set_text(time_min_label, min_str);
    
    // Blink colon every second
    int64_t current_time = esp_timer_get_time() / 1000000; // seconds
    if (current_time - last_colon_toggle >= 1) {
        colon_visible = !colon_visible;
        lv_obj_set_style_text_opa(time_colon_label, colon_visible ? LV_OPA_COVER : LV_OPA_TRANSP, 0);
        last_colon_toggle = current_time;
    }
    
    // Update date
    if (date_label != nullptr && weekday_label != nullptr) {
        uint8_t day, month;
        uint16_t year;
        rtcManager.getDate(&day, &month, &year);
        
        // Format date
        char date_str[16];
        snprintf(date_str, sizeof(date_str), "%04d-%02d-%02d", (int)year, (int)month, (int)day);
        lv_label_set_text(date_label, date_str);
        
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
            lv_label_set_text(weekday_label, weekdays[day_of_week]);
        }
    }
    
    // Update battery
    if (battery_arc != nullptr && battery_label != nullptr) {
        int battery_level = batteryManager.getBatteryLevel();
        bool charging = batteryManager.isCharging();
        
        // Update arc angle (0-360 degrees)
        int angle = (battery_level * 360) / 100;
        lv_arc_set_angles(battery_arc, 0, angle);
        
        // Update label
        char batt_str[10];
        snprintf(batt_str, sizeof(batt_str), "%d%%", battery_level);
        lv_label_set_text(battery_label, batt_str);
        
        // Change color if charging
        if (charging) {
            lv_obj_set_style_arc_color(battery_arc, COLOR_SECONDARY, LV_PART_INDICATOR);
        } else if (battery_level > 50) {
            lv_obj_set_style_arc_color(battery_arc, COLOR_PRIMARY, LV_PART_INDICATOR);
        } else if (battery_level > 20) {
            lv_obj_set_style_arc_color(battery_arc, lv_color_make(0xFF, 0xFF, 0x00), LV_PART_INDICATOR);
        } else {
            lv_obj_set_style_arc_color(battery_arc, lv_color_make(0xFF, 0x00, 0x00), LV_PART_INDICATOR);
        }
    }
    
    // Update WiFi/IP
    if (ip_label != nullptr && wifi_status_label != nullptr) {
        std::string ip = wifi_get_ip();
        if (wifi_is_connected() && !ip.empty()) {
            lv_label_set_text(ip_label, ip.c_str());
            lv_obj_set_style_text_color(ip_label, COLOR_PRIMARY, 0);
            lv_label_set_text(wifi_status_label, "WiFi");
        } else {
            lv_label_set_text(ip_label, "Not Connected");
            lv_obj_set_style_text_color(ip_label, lv_color_make(0x66, 0x66, 0x66), 0);
            lv_label_set_text(wifi_status_label, "Offline");
        }
    }
    
    // Update status bar time
    lv_obj_t* status_time = lv_obj_get_child(lv_obj_get_parent(time_hour_label), 0);
    if (status_time != nullptr) {
        lv_obj_t* time_label = lv_obj_get_child(status_time, 1);
        if (time_label != nullptr) {
            char status_time_str[8];
            int result = snprintf(status_time_str, sizeof(status_time_str), "%02d:%02d", (int)hour, (int)minute);
            if (result < 0 || result >= (int)sizeof(status_time_str)) {
                ESP_LOGW(TAG, "Time string truncation occurred");
            }
            lv_label_set_text(time_label, status_time_str);
        }
    }
}
