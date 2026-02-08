#ifndef DIFY_APP_H
#define DIFY_APP_H

#include <lvgl.h>

void dify_app_init();
void dify_app_show();
void dify_app_hide();
void dify_app_update();
bool dify_app_is_running();

/**
 * @brief Destroy the dify app screen and free all resources
 * 
 * Call this function to completely destroy the app screen and free all
 * associated LVGL objects. After calling this, dify_app_init() must
 * be called again before showing the app.
 * 
 * Use cases:
 * - Theme/font changes requiring full UI rebuild
 * - Memory pressure situations
 * - Clean shutdown
 */
void dify_app_destroy();

#endif