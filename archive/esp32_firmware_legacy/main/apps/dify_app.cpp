#include "dify_app.h"
#include "standby_screen.h"
#include "font_manager.h"
#include "display_utils.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include <stdint.h>
#include <stdbool.h>
#include "esp_log.h"

static const char* TAG = "DIFY_APP";

namespace {
constexpr uint32_t COLOR_BG_DARK = 0x1a1a1a;
constexpr uint32_t COLOR_TEXT_WHITE = 0xFFFFFF;
constexpr uint32_t COLOR_TEXT_GRAY = 0x888888;
constexpr uint32_t COLOR_TEXT_GREEN = 0x00FF00;
constexpr int FONT_SIZE_TITLE = 24;
constexpr int FONT_SIZE_STATUS = 18;
constexpr int FONT_SIZE_BUTTON = 16;
constexpr int TITLE_OFFSET_Y = 20;
constexpr int BUTTON_WIDTH = 80;
constexpr int BUTTON_HEIGHT = 40;
constexpr int BUTTON_OFFSET_Y = -20;
}

static lv_obj_t* app_screen = nullptr;
static lv_obj_t* status_label = nullptr;
static bool app_running = false;

static void back_btn_event_cb(lv_event_t* e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        dify_app_hide();
        standby_screen_show();
    }
}

void dify_app_init() {
    if (app_screen != nullptr) {
        return;
    }
    
    app_screen = lv_obj_create(nullptr);
    lv_obj_set_style_bg_color(app_screen, lv_color_hex(COLOR_BG_DARK), 0);
    lv_obj_remove_flag(app_screen, LV_OBJ_FLAG_SCROLLABLE);
    
    lv_obj_t* title = lv_label_create(app_screen);
    lv_label_set_text(title, "MindMate");
    lv_obj_set_style_text_font(title, font_manager_get_font(FONT_SIZE_TITLE, true), 0);
    lv_obj_set_style_text_color(title, lv_color_hex(COLOR_TEXT_WHITE), 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, TITLE_OFFSET_Y);
    
    status_label = lv_label_create(app_screen);
    lv_label_set_text(status_label, "初始化中...");
    lv_obj_set_style_text_font(status_label, font_manager_get_font(FONT_SIZE_STATUS, true), 0);
    lv_obj_set_style_text_color(status_label, lv_color_hex(COLOR_TEXT_GRAY), 0);
    lv_obj_align(status_label, LV_ALIGN_CENTER, 0, 0);
    
    lv_obj_t* back_btn = lv_btn_create(app_screen);
    lv_obj_set_size(back_btn, BUTTON_WIDTH, BUTTON_HEIGHT);
    lv_obj_align(back_btn, LV_ALIGN_BOTTOM_MID, 0, BUTTON_OFFSET_Y);
    lv_obj_add_event_cb(back_btn, back_btn_event_cb, LV_EVENT_CLICKED, nullptr);
    
    lv_obj_t* back_label = lv_label_create(back_btn);
    lv_label_set_text(back_label, "返回");
    lv_obj_set_style_text_font(back_label, font_manager_get_font(FONT_SIZE_BUTTON, true), 0);
    lv_obj_center(back_label);
}

void dify_app_show() {
    if (app_screen == nullptr) {
        dify_app_init();
    }
    
    // Use centralized screen transition for consistent SPI queue handling
    display_switch_screen(app_screen);
    app_running = true;
    
    ESP_LOGI(TAG, "Started");
    ESP_LOGI(TAG, "TODO: Connect to Dify server (similar to xiaozhi)");
}

void dify_app_hide() {
    app_running = false;
    ESP_LOGI(TAG, "Stopped");
}

void dify_app_update() {
    if (!app_running || app_screen == nullptr || status_label == nullptr) {
        return;
    }
    
    lv_label_set_text(status_label, "MindMate就绪");
    lv_obj_set_style_text_color(status_label, lv_color_hex(COLOR_TEXT_GREEN), 0);
}

bool dify_app_is_running() {
    return app_running;
}

void dify_app_destroy() {
    ESP_LOGI(TAG, "=== dify_app_destroy() called ===");
    
    if (app_screen == nullptr) {
        ESP_LOGI(TAG, "Dify app screen already destroyed or never created");
        return;
    }
    
    // Stop any running operations first
    if (app_running) {
        dify_app_hide();
    }
    
    bsp_display_lock(0);
    
    ESP_LOGI(TAG, "Deleting dify app screen and all children...");
    lv_obj_del(app_screen);
    
    // Set all pointers to nullptr for safety
    app_screen = nullptr;
    status_label = nullptr;
    
    bsp_display_unlock();
    
    ESP_LOGI(TAG, "Dify app screen destroyed - memory freed");
    ESP_LOGI(TAG, "=== dify_app_destroy() finished ===");
}