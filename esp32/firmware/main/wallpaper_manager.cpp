#include "wallpaper_manager.h"
#include <lvgl.h>

void wallpaper_set(lv_obj_t* screen, WallpaperType type) {
    if (screen == nullptr) {
        return;
    }
    
    lv_color_t bg_color = lv_color_hex(0x000000);
    
    switch (type) {
        case WALLPAPER_DEFAULT:
            bg_color = lv_color_hex(0x000000);
            break;
        case WALLPAPER_SETUP:
            bg_color = lv_color_hex(0x1a1a2e);
            break;
        case WALLPAPER_WAITING:
            bg_color = lv_color_hex(0x0f3460);
            break;
        case WALLPAPER_READY:
            bg_color = lv_color_hex(0x16213e);
            break;
        case WALLPAPER_LEARNING_MODE:
            bg_color = lv_color_hex(0x0a1929);
            break;
        case WALLPAPER_ERROR:
            bg_color = lv_color_hex(0x2d1b1b);
            break;
    }
    
    lv_obj_set_style_bg_color(screen, bg_color, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, LV_PART_MAIN);
}

lv_obj_t* wallpaper_create_background(lv_obj_t* parent, WallpaperType type) {
    lv_obj_t* bg = lv_obj_create(parent);
    lv_obj_remove_style_all(bg);
    lv_display_t* disp = lv_display_get_default();
    if (disp != nullptr) {
        int screen_width = lv_display_get_horizontal_resolution(disp);
        int screen_height = lv_display_get_vertical_resolution(disp);
        lv_obj_set_size(bg, screen_width, screen_height);
    } else {
        lv_obj_set_size(bg, LV_HOR_RES, LV_VER_RES);
    }
    lv_obj_clear_flag(bg, LV_OBJ_FLAG_SCROLLABLE);
    
    wallpaper_set(bg, type);
    
    return bg;
}
