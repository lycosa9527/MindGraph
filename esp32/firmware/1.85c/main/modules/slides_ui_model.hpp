#pragma once

#include <cstdint>

#include "lvgl.h"

#include "slides_ui.hpp"

constexpr int k_slides_list_max = 12;

struct SlidesListRow {
    char id[40] = {};
    char title[64] = {};
    char type[24] = {};
};

struct SlidesUiSnapshot {
    SlidesUiPhase phase = SlidesUiPhase::wait;
    SlidesUiAction pending = SlidesUiAction::none;
    char status[48] = {};
    char library[48] = {};
    char picker_status[40] = {};
    SlidesListRow diagrams[k_slides_list_max] = {};
    uint8_t diagram_count = 0;
    uint8_t list_serial = 0;
    int pending_diagram = -1;
    int step_index = 0;
    int step_count = 0;
    bool can_prev = false;
    bool can_next = false;
    bool autoplay = false;
    bool deep = false;
    bool pad_enabled = false;
    bool busy = false;
    bool picker_open = false;
    bool picker_fetch = false;
    bool hidden = true;
};

struct SlidesWidgets {
    lv_obj_t *root = nullptr;
    lv_obj_t *online = nullptr;
    lv_obj_t *status = nullptr;
    lv_obj_t *seg = nullptr;
    lv_obj_t *seg_thumb = nullptr;
    lv_obj_t *first_level = nullptr;
    lv_obj_t *deep = nullptr;
    lv_obj_t *prev = nullptr;
    lv_obj_t *next = nullptr;
    lv_obj_t *autoplay = nullptr;
    lv_obj_t *library = nullptr;
    lv_obj_t *library_label = nullptr;
    lv_obj_t *host = nullptr;
    lv_obj_t *host_label = nullptr;
    lv_obj_t *picker = nullptr;
    lv_obj_t *picker_list = nullptr;
};

SlidesWidgets slides_face_build(lv_obj_t *layer, lv_event_cb_t on_action, lv_event_cb_t on_pick);
const lv_font_t *slides_face_find_cjk(lv_obj_t *node);
void slides_face_apply_cjk(lv_obj_t *node, const lv_font_t *font);
void slides_face_paint(
    SlidesWidgets &widgets,
    const SlidesUiSnapshot &snap,
    const lv_font_t *cjk_font,
    uint8_t &painted_list,
    lv_event_cb_t on_pick
);
