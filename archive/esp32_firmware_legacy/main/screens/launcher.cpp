#include "launcher.h"
#include "standby_screen.h"
#include "wallpaper_manager.h"
#include "ui_icons.h"
#include "display_utils.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "font_manager.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "LAUNCHER";

static lv_obj_t* launcher_screen = nullptr;
static lv_obj_t* app_smart_response = nullptr;
static lv_obj_t* app_dify = nullptr;
static AppLaunchCallback app_launch_callback = nullptr;
static bool launcher_visible = false;

static void app_btn_event_cb(lv_event_t* e) {
    lv_event_code_t code = lv_event_get_code(e);
    lv_obj_t* btn = (lv_obj_t*)lv_event_get_target(e);
    
    if (code == LV_EVENT_CLICKED) {
        AppType app_type = (AppType)(intptr_t)lv_obj_get_user_data(btn);
        
        if (app_launch_callback) {
            app_launch_callback(app_type);
        }
        
        launcher_hide();
    }
}

static lv_obj_t* create_app_button(lv_obj_t* parent, const char* label, IconType icon_type, AppType app_type, int x, int y) {
    // Note: This function is called from within launcher_init() which already holds the lock
    lv_obj_t* btn = lv_btn_create(parent);
    lv_obj_set_size(btn, 150, 150);
    lv_obj_set_pos(btn, x, y);
    lv_obj_set_style_radius(btn, 20, 0);
    lv_obj_set_user_data(btn, (void*)(intptr_t)app_type);
    lv_obj_add_event_cb(btn, app_btn_event_cb, LV_EVENT_CLICKED, nullptr);
    
    lv_obj_t* label_obj = lv_label_create(btn);
    const lv_font_t* btn_font = font_manager_get_font(16, true);
    if (btn_font == nullptr) {
        ESP_LOGW("LAUNCHER", "Chinese font not available, using default");
        btn_font = &lv_font_montserrat_14;
    }
    // Set font BEFORE setting text to ensure LVGL uses it
    lv_obj_set_style_text_font(label_obj, btn_font, 0);
    lv_label_set_text(label_obj, label);
    lv_obj_set_style_text_align(label_obj, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(label_obj, LV_ALIGN_CENTER, 0, 20);
    
    // Use ui_icons module for app icons
    lv_obj_t* icon = icon_create(btn, icon_type, 40, 0, -30);
    
    return btn;
}

void launcher_init() {
    if (launcher_screen != nullptr) {
        return;
    }
    
    bsp_display_lock(0);
    launcher_screen = lv_obj_create(nullptr);
    // Use wallpaper manager for background
    wallpaper_set(launcher_screen, WALLPAPER_SETUP);
    lv_obj_remove_flag(launcher_screen, LV_OBJ_FLAG_SCROLLABLE);
    
    lv_obj_t* title = lv_label_create(launcher_screen);
    // Use 16px font (matching available compiled font) instead of 24px
    const lv_font_t* title_font = font_manager_get_font(16, true);
    if (title_font == nullptr) {
        ESP_LOGW("LAUNCHER", "Chinese font not available for title, using default");
        title_font = &lv_font_montserrat_14;
    }
    // Set font BEFORE setting text to ensure LVGL uses it
    lv_obj_set_style_text_font(title, title_font, 0);
    lv_label_set_text(title, "应用");
    lv_obj_set_style_text_color(title, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 20);
    
    // Use actual display resolution instead of hardcoded values
    // Hardcoded values (410x502) caused rendering artifacts (vertical bars)
    int screen_width = LV_HOR_RES;
    int screen_height = LV_VER_RES;
    int center_x = screen_width / 2;
    int center_y = screen_height / 2;
    
    app_smart_response = create_app_button(launcher_screen, "智回", ICON_MICROPHONE, APP_SMART_RESPONSE, center_x - 90, center_y - 80);
    app_dify = create_app_button(launcher_screen, "MindMate", ICON_SETTINGS, APP_DIFY_XIAOZHI, center_x - 90, center_y + 80);
    
    launcher_visible = false;
    bsp_display_unlock();
}

void launcher_show() {
    if (launcher_screen == nullptr) {
        launcher_init();
    }
    
    // Use the centralized screen transition function
    ESP_LOGI(TAG, "Switching to launcher screen...");
    display_switch_screen(launcher_screen);
    
    launcher_visible = true;
    ESP_LOGI(TAG, "Shown");
}

void launcher_hide() {
    launcher_visible = false;
    standby_screen_show();
    ESP_LOGI(TAG, "Hidden, returning to standby");
}

void launcher_set_app_launch_callback(AppLaunchCallback callback) {
    app_launch_callback = callback;
}

bool launcher_is_visible() {
    return launcher_visible;
}

void launcher_destroy() {
    ESP_LOGI(TAG, "=== launcher_destroy() called ===");
    
    if (launcher_screen == nullptr) {
        ESP_LOGI(TAG, "Launcher screen already destroyed or never created");
        return;
    }
    
    launcher_visible = false;
    
    bsp_display_lock(0);
    
    ESP_LOGI(TAG, "Deleting launcher screen object and all children...");
    lv_obj_del(launcher_screen);
    
    // Set all pointers to nullptr for safety
    launcher_screen = nullptr;
    app_smart_response = nullptr;
    app_dify = nullptr;
    
    bsp_display_unlock();
    
    ESP_LOGI(TAG, "Launcher screen destroyed - memory freed");
    ESP_LOGI(TAG, "=== launcher_destroy() finished ===");
}
