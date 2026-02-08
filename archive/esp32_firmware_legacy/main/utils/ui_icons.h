#ifndef UI_ICONS_H
#define UI_ICONS_H

#include <lvgl.h>

enum IconType {
    ICON_WIFI_CONNECTED,
    ICON_WIFI_DISCONNECTED,
    ICON_BATTERY_FULL,
    ICON_BATTERY_MEDIUM,
    ICON_BATTERY_LOW,
    ICON_BATTERY_CHARGING,
    ICON_MICROPHONE,
    ICON_MICROPHONE_LISTENING,
    ICON_SPEAKER,
    ICON_SPEAKER_PLAYING,
    ICON_ERROR,
    ICON_SUCCESS,
    ICON_WARNING,
    ICON_SETTINGS
};

lv_obj_t* icon_create(lv_obj_t* parent, IconType type, int32_t size, int32_t x, int32_t y);
void icon_set_color(lv_obj_t* icon_obj, lv_color_t color);
void icon_set_type(lv_obj_t* icon_obj, IconType type);

#endif
