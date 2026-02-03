#ifndef FONT_MANAGER_H
#define FONT_MANAGER_H

#include <lvgl.h>

extern const lv_font_t* chinese_font_16_ptr;

void font_manager_init();

const lv_font_t* font_manager_get_font(int size, bool needs_chinese);

bool has_chinese_char(const char* text);

#endif
