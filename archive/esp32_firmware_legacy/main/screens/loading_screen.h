#ifndef LOADING_SCREEN_H
#define LOADING_SCREEN_H

#include <lvgl.h>

void loading_screen_init();
void loading_screen_show();
void loading_screen_hide();
void loading_screen_set_message(const char* message);
void loading_screen_set_progress(int percent);
void loading_screen_update();
bool loading_screen_is_visible();

/**
 * @brief Destroy the loading screen and free all resources
 * 
 * This function completely removes the loading screen from memory.
 * Call this after transitioning to the standby screen at boot.
 * 
 * Benefits:
 * - Guarantees no loading screen artifacts on other screens
 * - Frees ~5KB of RAM (screen objects are never used again after boot)
 * - Sets all pointers to nullptr for safety
 * 
 * After calling this, loading_screen_init() must be called again
 * if the loading screen is ever needed (typically not needed).
 */
void loading_screen_destroy();

// Debug helper functions
lv_obj_t* get_loading_screen_obj();

#endif