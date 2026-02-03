#ifndef DIFY_APP_H
#define DIFY_APP_H

#include <lvgl.h>

void dify_app_init();
void dify_app_show();
void dify_app_hide();
void dify_app_update();
bool dify_app_is_running();

#endif