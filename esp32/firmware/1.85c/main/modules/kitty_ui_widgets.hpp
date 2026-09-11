#pragma once

#include "lvgl.h"

struct KittyWidgets {
    lv_obj_t *root = nullptr;
    lv_obj_t *online = nullptr;
    lv_obj_t *live = nullptr;
    lv_obj_t *user = nullptr;
    lv_obj_t *kitty = nullptr;
    lv_obj_t *choice_a = nullptr;
    lv_obj_t *choice_b = nullptr;
    lv_obj_t *mascot = nullptr;
    lv_obj_t *library = nullptr;
    lv_obj_t *library_label = nullptr;
    lv_obj_t *mic = nullptr;
    lv_obj_t *mic_ring_a = nullptr;
    lv_obj_t *mic_ring_b = nullptr;
    lv_obj_t *picker = nullptr;
    lv_obj_t *picker_list = nullptr;
    lv_obj_t *picker_row = nullptr;
    lv_obj_t *work_ring = nullptr;
};

KittyWidgets kitty_ui_build(
    lv_obj_t *layer,
    lv_event_cb_t on_hold,
    lv_event_cb_t on_library,
    lv_event_cb_t on_choice
);
