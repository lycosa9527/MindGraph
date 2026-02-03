#ifndef WALLPAPER_MANAGER_H
#define WALLPAPER_MANAGER_H

#include <lvgl.h>

enum WallpaperType {
    WALLPAPER_DEFAULT,
    WALLPAPER_SETUP,
    WALLPAPER_WAITING,
    WALLPAPER_READY,
    WALLPAPER_LEARNING_MODE,
    WALLPAPER_ERROR
};

void wallpaper_set(lv_obj_t* screen, WallpaperType type);
lv_obj_t* wallpaper_create_background(lv_obj_t* parent, WallpaperType type);

#endif
