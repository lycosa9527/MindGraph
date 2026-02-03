#include "loading_screen.h"
#include "font_manager.h"
#include "wallpaper_manager.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "esp_timer.h"
#include "esp_log.h"
#include <stdint.h>
#include <stdbool.h>
#include <cstring>

static const char* TAG = "LOADING";

static lv_obj_t* loading_screen = nullptr;
static lv_obj_t* logo_label = nullptr;
static lv_obj_t* message_label = nullptr;
static lv_obj_t* spinner = nullptr;
static lv_obj_t* progress_bar = nullptr;
static bool loading_visible = false;
static uint32_t spinner_angle = 0;
static int64_t last_spinner_update = 0;

static inline int clamp_percent(int value) {
    if (value < 0) return 0;
    if (value > 100) return 100;
    return value;
}

void loading_screen_init() {
    ESP_LOGI("LOADING", "loading_screen_init() called");
    if (loading_screen != nullptr) {
        ESP_LOGI("LOADING", "loading_screen already exists, returning");
        return;
    }
    
    // Ensure display is initialized before creating LVGL objects
    if (lv_display_get_default() == nullptr) {
        ESP_LOGE("LOADING", "Display not initialized! Cannot create loading screen.");
        return;
    }
    
    ESP_LOGI("LOADING", "Creating loading_screen object...");
    bsp_display_lock(0);
    loading_screen = lv_obj_create(nullptr);
    if (loading_screen == nullptr) {
        ESP_LOGE("LOADING", "Failed to create loading_screen!");
        bsp_display_unlock();
        return;
    }
    ESP_LOGI("LOADING", "loading_screen created successfully");
    
    // Use wallpaper manager for background
    wallpaper_set(loading_screen, WALLPAPER_DEFAULT);
    lv_obj_remove_flag(loading_screen, LV_OBJ_FLAG_SCROLLABLE);

    ESP_LOGI("LOADING", "Creating logo_label...");
    logo_label = lv_label_create(loading_screen);
    if (logo_label == nullptr) {
        ESP_LOGE("LOADING", "Failed to create logo_label!");
        bsp_display_unlock();
        return;
    }
    ESP_LOGI("LOADING", "Getting font for logo_label...");
    const lv_font_t* font = font_manager_get_font(32, true);
    if (font == nullptr) {
        ESP_LOGE("LOADING", "font_manager_get_font(32, true) returned NULL!");
        ESP_LOGE("LOADING", "Chinese fonts may not be linked properly!");
        font = &lv_font_montserrat_14;
    } else {
        ESP_LOGI("LOADING", "Chinese font loaded: line_height=%d", font->line_height);
    }
    ESP_LOGI("LOADING", "Setting font for logo_label...");
    // CRITICAL FIX: Set font BEFORE setting text, and verify font is actually set
    lv_obj_set_style_text_font(logo_label, font, 0);
    // Verify font was set correctly
    const lv_font_t* verify_font = lv_obj_get_style_text_font(logo_label, 0);
    if (verify_font != font) {
        ESP_LOGE("LOADING", "ERROR: Font not set correctly! Expected %p, got %p", font, verify_font);
    } else {
        ESP_LOGI("LOADING", "✓ Font verified: %p", verify_font);
    }
    lv_label_set_text(logo_label, "智回");
    ESP_LOGI("LOADING", "Text set to: 智回");
    lv_obj_set_style_text_color(logo_label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_align(logo_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(logo_label, LV_ALIGN_CENTER, 0, -100);
    ESP_LOGI(TAG, "logo_label created and configured");
    
    ESP_LOGI(TAG, "Creating designer_label...");
    lv_obj_t* designer_label = lv_label_create(loading_screen);
    if (designer_label == nullptr) {
        ESP_LOGE(TAG, "Failed to create designer_label!");
        bsp_display_unlock();
        return;
    }
    font = font_manager_get_font(14, true);
    if (font == nullptr) {
        ESP_LOGE(TAG, "font_manager_get_font(14, true) returned NULL!");
        ESP_LOGE(TAG, "Chinese fonts may not be linked properly!");
        font = &lv_font_montserrat_14;
    }
    // Set font BEFORE setting text to ensure LVGL uses it
    lv_obj_set_style_text_font(designer_label, font, 0);
    lv_label_set_text(designer_label, "Designed by MindSpring");
    lv_obj_set_style_text_color(designer_label, lv_color_hex(0x666666), 0);
    lv_obj_set_style_text_align(designer_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(designer_label, LV_ALIGN_CENTER, 0, -60);
    ESP_LOGI(TAG, "designer_label created and configured");
    
    ESP_LOGI(TAG, "Creating spinner...");
    spinner = lv_spinner_create(loading_screen);
    if (spinner == nullptr) {
        ESP_LOGE(TAG, "Failed to create spinner!");
        bsp_display_unlock();
        return;
    }
    lv_obj_set_size(spinner, 60, 60);
    lv_obj_set_style_arc_color(spinner, lv_color_hex(0x00FF00), LV_PART_MAIN);
    lv_obj_set_style_arc_color(spinner, lv_color_hex(0x333333), LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(spinner, 6, LV_PART_MAIN);
    lv_obj_set_style_arc_width(spinner, 6, LV_PART_INDICATOR);
    lv_obj_align(spinner, LV_ALIGN_CENTER, 0, -20);
    ESP_LOGI(TAG, "spinner created and configured");
    
    ESP_LOGI(TAG, "Creating message_label...");
    message_label = lv_label_create(loading_screen);
    if (message_label == nullptr) {
        ESP_LOGE(TAG, "Failed to create message_label!");
        bsp_display_unlock();
        return;
    }
    font = font_manager_get_font(18, true);
    if (font == nullptr) {
        ESP_LOGE(TAG, "font_manager_get_font(18, true) returned NULL!");
        ESP_LOGE(TAG, "Chinese fonts may not be linked properly!");
        font = &lv_font_montserrat_14;
    }
    // Set font BEFORE setting text to ensure LVGL uses it
    lv_obj_set_style_text_font(message_label, font, 0);
    lv_label_set_text(message_label, "初始化中...");
    lv_obj_set_style_text_color(message_label, lv_color_hex(0x888888), 0);
    lv_obj_set_style_text_align(message_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(message_label, LV_ALIGN_CENTER, 0, 40);
    ESP_LOGI(TAG, "message_label created and configured");
    
    ESP_LOGI(TAG, "Creating progress_bar...");
    progress_bar = lv_bar_create(loading_screen);
    if (progress_bar == nullptr) {
        ESP_LOGE(TAG, "Failed to create progress_bar!");
        bsp_display_unlock();
        return;
    }
    lv_obj_set_size(progress_bar, 300, 10);
    lv_obj_set_style_bg_color(progress_bar, lv_color_hex(0x333333), LV_PART_MAIN);
    lv_obj_set_style_bg_color(progress_bar, lv_color_hex(0x00FF00), LV_PART_INDICATOR);
    lv_obj_align(progress_bar, LV_ALIGN_CENTER, 0, 80);
    lv_bar_set_value(progress_bar, 0, LV_ANIM_OFF);
    ESP_LOGI(TAG, "progress_bar created and configured");
    
    loading_visible = false;
    bsp_display_unlock();
    ESP_LOGI(TAG, "loading_screen_init() completed successfully");
}

void loading_screen_show() {
    ESP_LOGI(TAG, "loading_screen_show() called");
    if (loading_screen == nullptr) {
        ESP_LOGI(TAG, "loading_screen is nullptr, calling init...");
        loading_screen_init();
    }
    
    if (loading_screen == nullptr) {
        ESP_LOGE(TAG, "loading_screen is still nullptr after init!");
        return;
    }
    
    if (lv_display_get_default() == nullptr) {
        ESP_LOGE(TAG, "Display not initialized! Cannot show loading screen.");
        return;
    }
    
    ESP_LOGI(TAG, "Loading screen...");
    bsp_display_lock(0);
    lv_screen_load(loading_screen);
    ESP_LOGI(TAG, "Screen loaded");
    loading_visible = true;
    last_spinner_update = esp_timer_get_time() / 1000;
    
    loading_screen_set_message("初始化中...");
    loading_screen_set_progress(0);
    bsp_display_unlock();
    // NOTE: lv_timer_handler() is now called by dedicated LVGL task
    ESP_LOGI(TAG, "loading_screen_show() completed");
}

void loading_screen_hide() {
    loading_visible = false;
}

void loading_screen_set_message(const char* message) {
    if (message_label != nullptr) {
        bsp_display_lock(0);
        // Always use Chinese font for message label (it includes ASCII too)
        const lv_font_t* font = font_manager_get_font(18, true);
        if (font == nullptr) {
            ESP_LOGW(TAG, "Chinese font not available, using default");
            font = &lv_font_montserrat_14;
        }
        // Set font BEFORE setting text to ensure LVGL uses it
        lv_obj_set_style_text_font(message_label, font, 0);
        lv_label_set_text(message_label, message);
        bsp_display_unlock();
    }
}

void loading_screen_set_progress(int percent) {
    if (progress_bar != nullptr) {
        percent = clamp_percent(percent);
        bsp_display_lock(0);
        lv_bar_set_value(progress_bar, percent, LV_ANIM_ON);
        bsp_display_unlock();
    }
}

void loading_screen_update() {
    if (!loading_visible || loading_screen == nullptr) {
        return;
    }
    
    int64_t current_time = esp_timer_get_time() / 1000;
    if (current_time - last_spinner_update > 16) {
        last_spinner_update = current_time;
        spinner_angle += 5;
        if (spinner_angle >= 360) {
            spinner_angle = 0;
        }
    }
}
bool loading_screen_is_visible() {
    return loading_visible;
}