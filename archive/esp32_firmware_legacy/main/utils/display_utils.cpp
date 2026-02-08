#include "display_utils.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "lvgl.h"
#include "esp_log.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "DISPLAY_UTILS";

/**
 * @brief Set the background color of the active screen
 * 
 * WARNING: This function only sets the background color. It does NOT delete
 * any child objects. For screen transitions, use lv_screen_load() directly
 * which properly handles the transition.
 * 
 * IMPORTANT: DO NOT use lv_obj_clean() on screens during transitions!
 * Screens have static objects created in their *_init() functions. Deleting
 * these objects creates dangling pointers and causes memory corruption.
 * 
 * @param color RGB565 color value (0x0000 = black, 0xFFFF = white)
 */
void display_clear_screen(uint16_t color) {
    lv_display_t* disp = lv_display_get_default();
    if (disp == nullptr) {
        ESP_LOGW(TAG, "Display not initialized, cannot clear");
        return;
    }
    
    ESP_LOGI(TAG, "Setting screen background to color 0x%04X", color);
    
    // Get current screen
    lv_obj_t* scr = lv_screen_active();
    if (scr == nullptr) {
        ESP_LOGW(TAG, "No active screen, cannot set background");
        return;
    }
    
    // Use LVGL to set screen background color
    bsp_display_lock(0);
    
    // Convert RGB565 to LVGL color
    // RGB565 format: 0x0000 = black, 0xFFFF = white
    // For black (0x0000), use lv_color_hex(0x000000)
    // For other colors, extract RGB components
    lv_color_t bg_color;
    if (color == 0x0000) {
        bg_color = lv_color_hex(0x000000);  // Black
    } else {
        // Extract RGB from RGB565: RRRRR GGGGGG BBBBB
        uint8_t r = ((color >> 11) & 0x1F) << 3;
        uint8_t g = ((color >> 5) & 0x3F) << 2;
        uint8_t b = (color & 0x1F) << 3;
        bg_color = lv_color_make(r, g, b);
    }
    
    lv_obj_set_style_bg_color(scr, bg_color, 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    
    // REMOVED: lv_obj_clean(scr)
    // DO NOT DELETE CHILDREN! Screen modules (loading_screen, standby_screen, launcher)
    // hold static pointers to their child objects. Deleting them creates dangling
    // pointers that cause memory corruption when those modules try to access them.
    // This was the root cause of the "loading screen leftover on standby" bug.
    
    // Invalidate entire screen to force redraw
    lv_obj_invalidate(scr);
    bsp_display_unlock();
    
    // Small delay to allow LVGL to process
    vTaskDelay(pdMS_TO_TICKS(20));
    
    // Force immediate refresh
    lv_refr_now(disp);
    vTaskDelay(pdMS_TO_TICKS(50));
    
    ESP_LOGI(TAG, "Screen background set");
}

/**
 * @brief DEPRECATED - Do not use for screen transitions
 * 
 * This function was originally intended to clear the screen before switching
 * to a new screen. However, it is NOT needed and can cause problems.
 * 
 * For screen transitions, simply call:
 * 1. old_screen_hide() - to hide/cleanup the old screen's objects
 * 2. lv_screen_load(new_screen) - LVGL handles the transition properly
 * 
 * lv_screen_load() will:
 * - Set the new screen as active
 * - Trigger a full redraw of the new screen  
 * - Stop rendering the old screen (objects preserved for reuse)
 * 
 * Using this function before lv_screen_load() is unnecessary and was causing
 * the "loading screen leftover on standby" bug due to object deletion.
 */
void display_clear_before_switch(void) {
    // DEPRECATED: This function should not be used for screen transitions
    // Keeping it for backwards compatibility but it now only sets background
    ESP_LOGW(TAG, "display_clear_before_switch() is deprecated - use lv_screen_load() directly");
    display_clear_screen(0x0000);  // Black
    vTaskDelay(pdMS_TO_TICKS(50));
}

void display_force_full_refresh(void) {
    lv_display_t* disp = lv_display_get_default();
    if (disp == nullptr) {
        return;
    }
    
    bsp_display_lock(0);
    // Invalidate entire screen using LVGL v9 API
    lv_obj_t* scr = lv_screen_active();
    if (scr != nullptr) {
        lv_obj_invalidate(scr);
    }
    bsp_display_unlock();
    
    // Force refresh
    lv_refr_now(disp);
    vTaskDelay(pdMS_TO_TICKS(50));
}

/**
 * @brief Safely switch to a new screen with proper SPI queue management
 * 
 * This function handles screen transitions by:
 * 1. Waiting for any pending SPI operations to complete
 * 2. Using direct screen load (no animation to avoid SPI queue overflow)
 * 3. Waiting for the refresh to complete before returning
 * 
 * The key insight is that LVGL screens are completely independent.
 * When you load a new screen, the old screen is NOT rendered at all.
 * The new screen's opaque background completely covers the display.
 * 
 * @param new_screen The screen object to switch to
 */
void display_switch_screen(lv_obj_t* new_screen) {
    if (new_screen == nullptr) {
        ESP_LOGE(TAG, "Cannot switch to null screen");
        return;
    }
    
    lv_display_t* disp = lv_display_get_default();
    if (disp == nullptr) {
        ESP_LOGE(TAG, "Display not initialized");
        return;
    }
    
    ESP_LOGI(TAG, "=== Screen transition starting ===");
    ESP_LOGI(TAG, "Target screen: %p", new_screen);
    
    // Step 1: Wait for any pending LVGL/SPI operations to drain
    // This is critical to prevent SPI queue overflow
    ESP_LOGI(TAG, "Step 1: Waiting for SPI queue to drain...");
    vTaskDelay(pdMS_TO_TICKS(200));
    
    // Step 2: Load the new screen directly (no animation)
    // Animation causes too many refresh operations and SPI queue overflow
    ESP_LOGI(TAG, "Step 2: Loading new screen directly...");
    lv_screen_load(new_screen);
    
    // Step 3: Wait for LVGL to process the screen change
    vTaskDelay(pdMS_TO_TICKS(100));
    
    // Step 4: Force a single full refresh
    ESP_LOGI(TAG, "Step 3: Forcing full refresh...");
    bsp_display_lock(0);
    lv_obj_invalidate(new_screen);
    bsp_display_unlock();
    
    // Wait for refresh to complete
    vTaskDelay(pdMS_TO_TICKS(200));
    
    // Verify the screen was loaded
    lv_obj_t* active = lv_screen_active();
    if (active == new_screen) {
        ESP_LOGI(TAG, "=== Screen transition complete (verified) ===");
    } else {
        ESP_LOGW(TAG, "Screen transition: active=%p, expected=%p", active, new_screen);
    }
}
