#ifndef STANDBY_SCREEN_H
#define STANDBY_SCREEN_H

#include <lvgl.h>

void standby_screen_init();
void standby_screen_show();
void standby_screen_hide();
void standby_screen_update();
bool standby_screen_is_visible();

/**
 * @brief Destroy the standby screen and free all resources
 * 
 * Call this function to completely destroy the standby screen and free all
 * associated LVGL objects. After calling this, standby_screen_init() must be
 * called again before showing the screen.
 * 
 * Use cases:
 * - Theme/font changes requiring full UI rebuild
 * - Memory pressure situations
 * - Clean shutdown
 */
void standby_screen_destroy();

#endif