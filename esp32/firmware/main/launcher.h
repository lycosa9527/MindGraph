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

#endif