#ifndef WATCH_FACE_ENHANCED_H
#define WATCH_FACE_ENHANCED_H

#include <lvgl.h>

// Initialize enhanced watch face on parent object
void watch_face_enhanced_init(lv_obj_t* parent);

// Update watch face display (call periodically, e.g., every second)
void watch_face_enhanced_update();

#endif
