#pragma once

#include <cstdint>

#include "lvgl.h"

#include "recorder_ui.hpp"

struct RecorderUiSnapshot {
    RecorderUiPhase phase = RecorderUiPhase::idle;
    RecorderUiAction pending = RecorderUiAction::none;
    char status[48] = {};
    char elapsed[8] = {};
    char transcript[1200] = {};
    uint8_t mic_level = 0;
    bool can_start = true;
    bool can_pause = false;
    bool can_resume = false;
    bool can_stop = false;
    bool can_generate = false;
    bool busy = false;
    bool hidden = true;
};

struct RecorderWidgets {
    lv_obj_t *root = nullptr;
    lv_obj_t *dot = nullptr;
    lv_obj_t *status = nullptr;
    lv_obj_t *elapsed = nullptr;
    lv_obj_t *transcript = nullptr;
    lv_obj_t *pause = nullptr;
    lv_obj_t *main = nullptr;
    lv_obj_t *main_label = nullptr;
    lv_obj_t *main_ring = nullptr;
    lv_obj_t *stop = nullptr;
    lv_obj_t *generate = nullptr;
};

RecorderWidgets recorder_face_build(lv_obj_t *layer, lv_event_cb_t on_action);
const lv_font_t *recorder_face_find_cjk(lv_obj_t *node);
void recorder_face_apply_cjk(lv_obj_t *node, const lv_font_t *font);
void recorder_face_paint(RecorderWidgets &widgets, const RecorderUiSnapshot &snap);
