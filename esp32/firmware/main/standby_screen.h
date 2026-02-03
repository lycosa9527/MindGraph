#ifndef STANDBY_SCREEN_H
#define STANDBY_SCREEN_H

#include <lvgl.h>

void standby_screen_init();
void standby_screen_show();
void standby_screen_hide();
void standby_screen_update();
bool standby_screen_is_visible();

#endif