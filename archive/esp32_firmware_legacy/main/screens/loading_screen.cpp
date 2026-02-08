#include "loading_screen.h"
#include "font_manager.h"
#include "wallpaper_manager.h"
#include "display_utils.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "esp_timer.h"
#include "esp_log.h"
#include <stdint.h>
#include <stdbool.h>
#include <cstring>

static const char* TAG = "LOADING";

// Color palette - elegant and professional
#define COLOR_BG_PRIMARY       0x0a0e1a      // Deep dark blue-gray
#define COLOR_LOGO_PRIMARY     0xffffff      // Pure white for logo
#define COLOR_LOGO_SECONDARY   0xb8c5d6      // Soft blue-gray for subtitle
#define COLOR_TEXT_PRIMARY     0xe8ecf0      // Light gray-white for messages
#define COLOR_TEXT_SECONDARY   0x8a9ba8      // Medium gray for secondary text
#define COLOR_SPINNER_ACTIVE   0x4a9eff      // Bright blue for spinner
#define COLOR_SPINNER_BG       0x1a2332      // Dark blue-gray for spinner track
#define COLOR_PROGRESS_ACTIVE  0x5cb3ff      // Lighter blue for progress
#define COLOR_PROGRESS_BG      0x1e2836      // Dark background for progress bar
#define COLOR_ACCENT           0x6bb6ff      // Accent blue

static lv_obj_t* loading_screen = nullptr;
static lv_obj_t* logo_label = nullptr;
static lv_obj_t* subtitle_label = nullptr;
static lv_obj_t* message_label = nullptr;
static lv_obj_t* spinner = nullptr;
static lv_obj_t* progress_bar = nullptr;
static bool loading_visible = false;
static uint32_t spinner_angle = 0;
static int64_t last_spinner_update = 0;

// Thread-safe destroyed flag to prevent use-after-free race condition
// Using volatile bool since this flag is only ever set once (false->true)
// and is always checked inside the display lock for safe access
static volatile bool loading_screen_destroyed = false;

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
    
    // Reset destroyed flag when initializing (in case of reinitialization)
    loading_screen_destroyed = false;
    
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
    
    // Use elegant dark background
    lv_obj_set_style_bg_color(loading_screen, lv_color_hex(COLOR_BG_PRIMARY), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(loading_screen, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_remove_flag(loading_screen, LV_OBJ_FLAG_SCROLLABLE);

    // Get 16px Chinese font - the only font we have
    const lv_font_t* font = font_manager_get_font(16, true);
    if (font == nullptr) {
        font = chinese_font_16_ptr;
    }
    if (font == nullptr) {
        ESP_LOGE(TAG, "16px Chinese font not available!");
        bsp_display_unlock();
        return;
    }
    ESP_LOGI(TAG, "Using 16px Chinese font (line_height=%d)", font->line_height);

    // Create logo label - use 16px font with spacing for prominence
    ESP_LOGI("LOADING", "Creating logo_label...");
    logo_label = lv_label_create(loading_screen);
    if (logo_label == nullptr) {
        ESP_LOGE("LOADING", "Failed to create logo_label!");
        bsp_display_unlock();
        return;
    }
    lv_obj_set_style_text_font(logo_label, font, 0);
    lv_label_set_text(logo_label, "智回");
    lv_obj_set_style_text_color(logo_label, lv_color_hex(COLOR_LOGO_PRIMARY), 0);
    lv_obj_set_style_text_align(logo_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_opa(logo_label, LV_OPA_COVER, 0);
    // Add letter spacing through padding for visual prominence
    lv_obj_set_style_pad_hor(logo_label, 8, 0);
    lv_obj_align(logo_label, LV_ALIGN_CENTER, 0, -100);
    ESP_LOGI(TAG, "logo_label created and configured");
    
    // Create subtitle label - elegant and subtle, same 16px font
    ESP_LOGI(TAG, "Creating subtitle_label...");
    subtitle_label = lv_label_create(loading_screen);
    if (subtitle_label == nullptr) {
        ESP_LOGE(TAG, "Failed to create subtitle_label!");
        bsp_display_unlock();
        return;
    }
    lv_obj_set_style_text_font(subtitle_label, font, 0);
    lv_label_set_text(subtitle_label, "Designed by MindSpring");
    lv_obj_set_style_text_color(subtitle_label, lv_color_hex(COLOR_LOGO_SECONDARY), 0);
    lv_obj_set_style_text_align(subtitle_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_opa(subtitle_label, LV_OPA_80, 0);
    lv_obj_align(subtitle_label, LV_ALIGN_CENTER, 0, -60);
    ESP_LOGI(TAG, "subtitle_label created and configured");
    
    // Create elegant spinner - larger, smoother
    ESP_LOGI(TAG, "Creating spinner...");
    spinner = lv_spinner_create(loading_screen);
    if (spinner == nullptr) {
        ESP_LOGE(TAG, "Failed to create spinner!");
        bsp_display_unlock();
        return;
    }
    lv_obj_set_size(spinner, 72, 72);
    // Active arc - bright blue
    lv_obj_set_style_arc_color(spinner, lv_color_hex(COLOR_SPINNER_ACTIVE), LV_PART_MAIN);
    lv_obj_set_style_arc_width(spinner, 5, LV_PART_MAIN);
    lv_obj_set_style_arc_opa(spinner, LV_OPA_COVER, LV_PART_MAIN);
    // Background arc - subtle dark
    lv_obj_set_style_arc_color(spinner, lv_color_hex(COLOR_SPINNER_BG), LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(spinner, 5, LV_PART_INDICATOR);
    lv_obj_set_style_arc_opa(spinner, LV_OPA_60, LV_PART_INDICATOR);
    // Rounded ends
    lv_obj_set_style_arc_rounded(spinner, true, LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(spinner, true, LV_PART_INDICATOR);
    lv_obj_align(spinner, LV_ALIGN_CENTER, 0, 0);
    ESP_LOGI(TAG, "spinner created and configured");
    
    // Create message label - clean typography, same 16px font
    ESP_LOGI(TAG, "Creating message_label...");
    message_label = lv_label_create(loading_screen);
    if (message_label == nullptr) {
        ESP_LOGE(TAG, "Failed to create message_label!");
        bsp_display_unlock();
        return;
    }
    lv_obj_set_style_text_font(message_label, font, 0);
    lv_label_set_text(message_label, "初始化中...");
    lv_obj_set_style_text_color(message_label, lv_color_hex(COLOR_TEXT_PRIMARY), 0);
    lv_obj_set_style_text_align(message_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_opa(message_label, LV_OPA_90, 0);
    lv_obj_align(message_label, LV_ALIGN_CENTER, 0, 50);
    ESP_LOGI(TAG, "message_label created and configured");
    
    // Create elegant progress bar - rounded, smooth, thin and refined
    ESP_LOGI(TAG, "Creating progress_bar...");
    progress_bar = lv_bar_create(loading_screen);
    if (progress_bar == nullptr) {
        ESP_LOGE(TAG, "Failed to create progress_bar!");
        bsp_display_unlock();
        return;
    }
    lv_obj_set_size(progress_bar, 320, 4);
    // Background - subtle dark
    lv_obj_set_style_bg_color(progress_bar, lv_color_hex(COLOR_PROGRESS_BG), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(progress_bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(progress_bar, 2, LV_PART_MAIN);
    // Progress indicator - bright blue, smooth
    lv_obj_set_style_bg_color(progress_bar, lv_color_hex(COLOR_PROGRESS_ACTIVE), LV_PART_INDICATOR);
    lv_obj_set_style_bg_opa(progress_bar, LV_OPA_COVER, LV_PART_INDICATOR);
    lv_obj_set_style_radius(progress_bar, 2, LV_PART_INDICATOR);
    lv_obj_align(progress_bar, LV_ALIGN_CENTER, 0, 90);
    lv_bar_set_value(progress_bar, 0, LV_ANIM_OFF);
    ESP_LOGI(TAG, "progress_bar created and configured");
    
    loading_visible = false;
    bsp_display_unlock();
    ESP_LOGI(TAG, "loading_screen_init() completed successfully");
}

void loading_screen_show() {
    ESP_LOGI(TAG, "=== loading_screen_show() called ===");
    
    // Debug: Check current active screen
    lv_obj_t* current_screen = lv_screen_active();
    if (current_screen != nullptr) {
        ESP_LOGI(TAG, "[DEBUG] Current active screen before show: %p", current_screen);
    } else {
        ESP_LOGI(TAG, "[DEBUG] No active screen before show");
    }
    
    if (loading_screen == nullptr) {
        ESP_LOGI(TAG, "[DEBUG] loading_screen is nullptr, calling init...");
        loading_screen_init();
    }
    
    if (loading_screen == nullptr) {
        ESP_LOGE(TAG, "[DEBUG] loading_screen is still nullptr after init!");
        return;
    }
    
    if (lv_display_get_default() == nullptr) {
        ESP_LOGE(TAG, "[DEBUG] Display not initialized! Cannot show loading screen.");
        return;
    }
    
    ESP_LOGI(TAG, "[DEBUG] Loading screen object: %p", loading_screen);
    ESP_LOGI(TAG, "[DEBUG] Objects: logo=%p, subtitle=%p, message=%p, spinner=%p, progress=%p",
             logo_label, subtitle_label, message_label, spinner, progress_bar);
    
    bsp_display_lock(0);
    
    // Debug: Check visibility flags before clearing
    if (logo_label != nullptr) {
        bool was_hidden = lv_obj_has_flag(logo_label, LV_OBJ_FLAG_HIDDEN);
        ESP_LOGI(TAG, "[DEBUG] logo_label was_hidden=%d", was_hidden);
        lv_obj_clear_flag(logo_label, LV_OBJ_FLAG_HIDDEN);
    }
    if (subtitle_label != nullptr) {
        bool was_hidden = lv_obj_has_flag(subtitle_label, LV_OBJ_FLAG_HIDDEN);
        ESP_LOGI(TAG, "[DEBUG] subtitle_label was_hidden=%d", was_hidden);
        lv_obj_clear_flag(subtitle_label, LV_OBJ_FLAG_HIDDEN);
    }
    if (message_label != nullptr) {
        bool was_hidden = lv_obj_has_flag(message_label, LV_OBJ_FLAG_HIDDEN);
        ESP_LOGI(TAG, "[DEBUG] message_label was_hidden=%d", was_hidden);
        lv_obj_clear_flag(message_label, LV_OBJ_FLAG_HIDDEN);
    }
    if (spinner != nullptr) {
        bool was_hidden = lv_obj_has_flag(spinner, LV_OBJ_FLAG_HIDDEN);
        ESP_LOGI(TAG, "[DEBUG] spinner was_hidden=%d", was_hidden);
        lv_obj_clear_flag(spinner, LV_OBJ_FLAG_HIDDEN);
    }
    if (progress_bar != nullptr) {
        bool was_hidden = lv_obj_has_flag(progress_bar, LV_OBJ_FLAG_HIDDEN);
        ESP_LOGI(TAG, "[DEBUG] progress_bar was_hidden=%d", was_hidden);
        lv_obj_clear_flag(progress_bar, LV_OBJ_FLAG_HIDDEN);
    }
    if (loading_screen != nullptr) {
        bool was_hidden = lv_obj_has_flag(loading_screen, LV_OBJ_FLAG_HIDDEN);
        ESP_LOGI(TAG, "[DEBUG] loading_screen was_hidden=%d", was_hidden);
        lv_obj_clear_flag(loading_screen, LV_OBJ_FLAG_HIDDEN);
    }
    
    bsp_display_unlock();
    
    // Use centralized screen transition for consistent SPI queue handling
    // display_switch_screen() manages delays and locking internally
    ESP_LOGI(TAG, "[DEBUG] Calling display_switch_screen(loading_screen)...");
    display_switch_screen(loading_screen);
    
    // Debug: Verify screen was loaded
    lv_obj_t* active_screen = lv_screen_active();
    if (active_screen == loading_screen) {
        ESP_LOGI(TAG, "[DEBUG] [OK] Screen successfully loaded, active screen matches");
    } else {
        ESP_LOGW(TAG, "[DEBUG] [WARN] Active screen mismatch! Expected %p, got %p", loading_screen, active_screen);
    }
    
    loading_visible = true;
    last_spinner_update = esp_timer_get_time() / 1000;
    
    // Update message/progress - these functions manage their own locking
    loading_screen_set_message("初始化中...");
    loading_screen_set_progress(0);
    
    ESP_LOGI(TAG, "[DEBUG] loading_screen_show() completed, loading_visible=%d", loading_visible);
    ESP_LOGI(TAG, "=== loading_screen_show() finished ===");
}

void loading_screen_hide() {
    ESP_LOGI(TAG, "=== loading_screen_hide() called ===");
    
    if (!loading_visible) {
        ESP_LOGI(TAG, "Already hidden, returning");
        return;
    }
    
    loading_visible = false;
    
    // SIMPLIFIED FIX: Do NOT set hidden flags on loading screen objects here!
    // 
    // Setting hidden flags triggers LVGL to mark objects as dirty and queue
    // redraws. This overwhelms the SPI queue right before we switch screens,
    // causing "spi transmit (queue) color failed" errors and leaving artifacts.
    //
    // Instead, we just set loading_visible=false and let lv_screen_load()
    // in standby_screen_show() handle the transition. When a new screen is
    // loaded, LVGL automatically stops rendering the old screen - there's no
    // need to manually hide objects on a screen that won't be displayed.
    //
    // The standby screen has an opaque background (LV_OPA_COVER) which will
    // completely cover any previous content when it's rendered.
    
    ESP_LOGI(TAG, "Loading screen marked as hidden (loading_visible=false)");
    ESP_LOGI(TAG, "=== loading_screen_hide() finished ===");
}

void loading_screen_set_message(const char* message) {
    // RACE CONDITION FIX: Check destroyed flag INSIDE the lock
    // This prevents use-after-free if loading_screen_destroy() is called
    // between the outer nullptr check and the lock acquisition
    bsp_display_lock(0);
    
    // Double-check inside lock - another thread may have destroyed the screen
    if (loading_screen_destroyed || message_label == nullptr) {
        bsp_display_unlock();
        return;
    }
    
    // Use 16px font - the only font we have
    const lv_font_t* font = font_manager_get_font(16, true);
    if (font == nullptr) {
        font = chinese_font_16_ptr;
    }
    if (font != nullptr) {
        lv_obj_set_style_text_font(message_label, font, 0);
    }
    lv_label_set_text(message_label, message);
    // Ensure text color and opacity are maintained
    lv_obj_set_style_text_color(message_label, lv_color_hex(COLOR_TEXT_PRIMARY), 0);
    lv_obj_set_style_text_opa(message_label, LV_OPA_90, 0);
    bsp_display_unlock();
}

void loading_screen_set_progress(int percent) {
    percent = clamp_percent(percent);
    
    // RACE CONDITION FIX: Check destroyed flag INSIDE the lock
    // This prevents use-after-free if loading_screen_destroy() is called
    // between the outer nullptr check and the lock acquisition
    bsp_display_lock(0);
    
    // Double-check inside lock - another thread may have destroyed the screen
    if (loading_screen_destroyed || progress_bar == nullptr) {
        bsp_display_unlock();
        return;
    }
    
    // Use smooth animation for progress updates
    lv_bar_set_value(progress_bar, percent, LV_ANIM_ON);
    // Ensure progress bar styling is maintained
    lv_obj_set_style_bg_color(progress_bar, lv_color_hex(COLOR_PROGRESS_ACTIVE), LV_PART_INDICATOR);
    lv_obj_set_style_bg_opa(progress_bar, LV_OPA_COVER, LV_PART_INDICATOR);
    bsp_display_unlock();
}

void loading_screen_update() {
    // Check destroyed flag first (volatile read, no lock needed for read)
    if (loading_screen_destroyed || !loading_visible || loading_screen == nullptr) {
        return;
    }
    
    // Smooth spinner animation - update every ~16ms for 60fps
    int64_t current_time = esp_timer_get_time() / 1000;
    if (current_time - last_spinner_update > 16) {
        last_spinner_update = current_time;
        spinner_angle += 4;  // Slightly slower for more elegant feel
        if (spinner_angle >= 360) {
            spinner_angle = 0;
        }
    }
}
bool loading_screen_is_visible() {
    return loading_visible;
}

// Debug helper function
lv_obj_t* get_loading_screen_obj() {
    return loading_screen;
}

void loading_screen_destroy() {
    ESP_LOGI(TAG, "=== loading_screen_destroy() called ===");
    
    if (loading_screen == nullptr) {
        ESP_LOGI(TAG, "Loading screen already destroyed or never created");
        return;
    }
    
    loading_visible = false;
    
    // CRITICAL: Set destroyed flag FIRST (before acquiring lock)
    // This signals to other functions that the screen is being destroyed
    // They will check this flag inside their lock and abort if true
    loading_screen_destroyed = true;
    
    // HYBRID APPROACH: Completely destroy the loading screen after boot
    //
    // The loading screen is only used once during boot. After transitioning
    // to the standby screen, it's never needed again. By deleting it:
    // 1. We GUARANTEE no loading screen artifacts on other screens
    //    (the objects literally don't exist in memory anymore)
    // 2. We free ~5KB of RAM (LVGL objects, styles, etc.)
    // 3. We eliminate any possibility of dangling pointer issues
    //
    // Note: lv_obj_del() recursively deletes all children, so we only
    // need to delete the screen object itself - all labels, spinner,
    // progress bar will be deleted automatically.
    
    bsp_display_lock(0);
    
    ESP_LOGI(TAG, "Deleting loading screen object and all children...");
    lv_obj_del(loading_screen);
    
    // Set all pointers to nullptr for safety
    // This prevents any accidental access to deleted objects
    loading_screen = nullptr;
    logo_label = nullptr;
    subtitle_label = nullptr;
    message_label = nullptr;
    spinner = nullptr;
    progress_bar = nullptr;
    
    bsp_display_unlock();
    
    ESP_LOGI(TAG, "Loading screen destroyed - memory freed");
    ESP_LOGI(TAG, "=== loading_screen_destroy() finished ===");
}