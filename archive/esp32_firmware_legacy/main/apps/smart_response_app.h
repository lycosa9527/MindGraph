#ifndef SMART_RESPONSE_APP_H
#define SMART_RESPONSE_APP_H

#include <lvgl.h>

void smart_response_app_init();
void smart_response_app_show();
void smart_response_app_hide();
void smart_response_app_update();
bool smart_response_app_is_running();

/**
 * @brief Destroy the smart response app screen and free all resources
 * 
 * Call this function to completely destroy the app screen and free all
 * associated LVGL objects. After calling this, smart_response_app_init() must
 * be called again before showing the app.
 * 
 * Use cases:
 * - Theme/font changes requiring full UI rebuild
 * - Memory pressure situations
 * - Clean shutdown
 */
void smart_response_app_destroy();

#endif