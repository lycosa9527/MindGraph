#ifndef QRCODE_GENERATOR_H
#define QRCODE_GENERATOR_H

#include <lvgl.h>
#include <stdint.h>

lv_obj_t* qrcode_create(lv_obj_t* parent, const char* text, int32_t size, int32_t x, int32_t y);
void qrcode_update(lv_obj_t* qrcode_obj, const char* text);
void qrcode_delete(lv_obj_t* qrcode_obj);

#endif
