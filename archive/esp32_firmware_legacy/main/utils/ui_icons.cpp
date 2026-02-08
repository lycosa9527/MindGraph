#include "ui_icons.h"
#include <lvgl.h>
#include <cstring>

lv_obj_t* icon_create(lv_obj_t* parent, IconType type, int32_t size, int32_t x, int32_t y) {
    lv_obj_t* icon = lv_label_create(parent);
    lv_obj_set_size(icon, size, size);
    lv_obj_set_style_text_align(icon, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_font(icon, &lv_font_montserrat_14, 0);
    
    const char* icon_text = "";
    lv_color_t icon_color = lv_color_hex(0xFFFFFF);
    
    switch (type) {
        case ICON_WIFI_CONNECTED:
            icon_text = "W";  // WiFi - use text instead of emoji
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_WIFI_DISCONNECTED:
            icon_text = "W";  // WiFi disconnected
            icon_color = lv_color_hex(0xFF0000);
            break;
        case ICON_BATTERY_FULL:
            icon_text = "B";  // Battery full
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_BATTERY_MEDIUM:
            icon_text = "B";  // Battery medium
            icon_color = lv_color_hex(0xFFFF00);
            break;
        case ICON_BATTERY_LOW:
            icon_text = "B";  // Battery low
            icon_color = lv_color_hex(0xFF0000);
            break;
        case ICON_BATTERY_CHARGING:
            icon_text = "B+";  // Battery charging
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_MICROPHONE:
            icon_text = "M";  // Microphone
            icon_color = lv_color_hex(0x888888);
            break;
        case ICON_MICROPHONE_LISTENING:
            icon_text = "M";  // Microphone listening
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_SPEAKER:
            icon_text = "S";  // Speaker
            icon_color = lv_color_hex(0x888888);
            break;
        case ICON_SPEAKER_PLAYING:
            icon_text = "S";  // Speaker playing
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_ERROR:
            icon_text = "X";  // Error
            icon_color = lv_color_hex(0xFF0000);
            break;
        case ICON_SUCCESS:
            icon_text = "OK";  // Success
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_WARNING:
            icon_text = "!";  // Warning
            icon_color = lv_color_hex(0xFFFF00);
            break;
        case ICON_SETTINGS:
            icon_text = "S";  // Settings
            icon_color = lv_color_hex(0x888888);
            break;
    }
    
    lv_label_set_text(icon, icon_text);
    lv_obj_set_style_text_color(icon, icon_color, 0);
    lv_obj_align(icon, LV_ALIGN_TOP_LEFT, x, y);
    
    return icon;
}

void icon_set_color(lv_obj_t* icon_obj, lv_color_t color) {
    if (icon_obj != nullptr) {
        lv_obj_set_style_text_color(icon_obj, color, 0);
    }
}

void icon_set_type(lv_obj_t* icon_obj, IconType type) {
    if (icon_obj == nullptr) {
        return;
    }
    
    const char* icon_text = "";
    lv_color_t icon_color = lv_color_hex(0xFFFFFF);
    
    switch (type) {
        case ICON_WIFI_CONNECTED:
            icon_text = "W";
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_WIFI_DISCONNECTED:
            icon_text = "W";
            icon_color = lv_color_hex(0xFF0000);
            break;
        case ICON_BATTERY_FULL:
            icon_text = "B";
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_BATTERY_MEDIUM:
            icon_text = "B";
            icon_color = lv_color_hex(0xFFFF00);
            break;
        case ICON_BATTERY_LOW:
            icon_text = "B";
            icon_color = lv_color_hex(0xFF0000);
            break;
        case ICON_BATTERY_CHARGING:
            icon_text = "B+";
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_MICROPHONE:
            icon_text = "M";
            icon_color = lv_color_hex(0x888888);
            break;
        case ICON_MICROPHONE_LISTENING:
            icon_text = "M";
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_SPEAKER:
            icon_text = "S";
            icon_color = lv_color_hex(0x888888);
            break;
        case ICON_SPEAKER_PLAYING:
            icon_text = "S";
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_ERROR:
            icon_text = "X";
            icon_color = lv_color_hex(0xFF0000);
            break;
        case ICON_SUCCESS:
            icon_text = "OK";
            icon_color = lv_color_hex(0x00FF00);
            break;
        case ICON_WARNING:
            icon_text = "!";
            icon_color = lv_color_hex(0xFFFF00);
            break;
        case ICON_SETTINGS:
            icon_text = "S";
            icon_color = lv_color_hex(0x888888);
            break;
    }
    
    lv_label_set_text(icon_obj, icon_text);
    lv_obj_set_style_text_color(icon_obj, icon_color, 0);
}
