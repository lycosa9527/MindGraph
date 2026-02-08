#ifndef LAUNCHER_H
#define LAUNCHER_H

#include <lvgl.h>

enum AppType {
    APP_SMART_RESPONSE,
    APP_DIFY_XIAOZHI
};

typedef void (*AppLaunchCallback)(AppType app);

void launcher_init();
void launcher_show();
void launcher_hide();
void launcher_set_app_launch_callback(AppLaunchCallback callback);
bool launcher_is_visible();

/**
 * @brief Destroy the launcher screen and free all resources
 * 
 * Call this function to completely destroy the launcher screen and free all
 * associated LVGL objects. After calling this, launcher_init() must be
 * called again before showing the screen.
 * 
 * Use cases:
 * - Theme/font changes requiring full UI rebuild
 * - Memory pressure situations
 * - Clean shutdown
 */
void launcher_destroy();

#endif