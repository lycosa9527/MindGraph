#include "qrcode_generator.h"
#include <lvgl.h>
#include <string.h>

#if LV_USE_QRCODE

lv_obj_t* qrcode_create(lv_obj_t* parent, const char* text, int32_t size, int32_t x, int32_t y) {
    lv_obj_t* qr = lv_qrcode_create(parent, size, lv_color_hex(0x000000), lv_color_hex(0xFFFFFF));
    
    if (qr != nullptr && text != nullptr) {
        lv_qrcode_update(qr, text, strlen(text));
        lv_obj_align(qr, LV_ALIGN_TOP_LEFT, x, y);
    }
    
    return qr;
}

void qrcode_update(lv_obj_t* qrcode_obj, const char* text) {
    if (qrcode_obj != nullptr && text != nullptr) {
        lv_qrcode_update(qrcode_obj, text, strlen(text));
    }
}

void qrcode_delete(lv_obj_t* qrcode_obj) {
    if (qrcode_obj != nullptr) {
        lv_obj_del(qrcode_obj);
    }
}

#else

lv_obj_t* qrcode_create(lv_obj_t* parent, const char* text, int32_t size, int32_t x, int32_t y) {
    lv_obj_t* label = lv_label_create(parent);
    lv_label_set_text(label, "QR");
    lv_obj_set_style_text_color(label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(label, LV_ALIGN_TOP_LEFT, x, y);
    return label;
}

void qrcode_update(lv_obj_t* qrcode_obj, const char* text) {
    if (qrcode_obj != nullptr) {
        lv_label_set_text(qrcode_obj, text);
    }
}

void qrcode_delete(lv_obj_t* qrcode_obj) {
    if (qrcode_obj != nullptr) {
        lv_obj_del(qrcode_obj);
    }
}

#endif
