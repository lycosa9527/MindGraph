#ifndef LOADING_SCREEN_H
#define LOADING_SCREEN_H

#include <lvgl.h>

void loading_screen_init();
void loading_screen_show();
void loading_screen_hide();
void loading_screen_set_message(const char* message);
void loading_screen_set_progress(int percent);
void loading_screen_update();

#endif