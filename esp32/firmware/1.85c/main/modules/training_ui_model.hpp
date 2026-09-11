#pragma once

#include <cstdint>

#include "lvgl.h"

#include "training_ui.hpp"

constexpr int k_training_list_max = 20;

struct TrainingListRow {
    char id[40] = {};
    char title[64] = {};
    int org_id = 0;
};

struct TrainingUiSnapshot {
    TrainingUiPhase phase = TrainingUiPhase::pick_school;
    TrainingHostPill pill = TrainingHostPill::idle;
    TrainingDropdownMode dropdown_mode = TrainingDropdownMode::schools;
    TrainingUiAction pending = TrainingUiAction::none;
    char status[48] = {};
    char dropdown_label[48] = {};
    char school_name[48] = {};
    char active_course[40] = {};
    TrainingListRow orgs[k_training_list_max] = {};
    TrainingListRow courses[k_training_list_max] = {};
    uint8_t org_count = 0;
    uint8_t course_count = 0;
    uint8_t list_serial = 0;
    int pending_org = -1;
    int pending_course = -1;
    int step_index = 0;
    int step_count = 0;
    bool can_prev = false;
    bool can_next = false;
    bool locked = true;
    bool pad_enabled = false;
    bool busy = false;
    bool confirm = false;
    bool dropdown_open = false;
    bool school_locked = false;
    bool hidden = true;
};

struct TrainingWidgets {
    lv_obj_t *root = nullptr;
    lv_obj_t *online = nullptr;
    lv_obj_t *status = nullptr;
    lv_obj_t *prev = nullptr;
    lv_obj_t *next = nullptr;
    lv_obj_t *stop = nullptr;
    lv_obj_t *lock = nullptr;
    lv_obj_t *free = nullptr;
    lv_obj_t *dropdown = nullptr;
    lv_obj_t *dropdown_label = nullptr;
    lv_obj_t *pill = nullptr;
    lv_obj_t *pill_label = nullptr;
    lv_obj_t *picker = nullptr;
    lv_obj_t *picker_list = nullptr;
    lv_obj_t *confirm = nullptr;
};

TrainingWidgets training_face_build(
    lv_obj_t *layer,
    lv_event_cb_t on_action,
    lv_event_cb_t on_pick_org,
    lv_event_cb_t on_pick_course
);
const lv_font_t *training_face_find_cjk(lv_obj_t *node);
void training_face_apply_cjk(lv_obj_t *node, const lv_font_t *font);
void training_face_paint(
    TrainingWidgets &widgets,
    const TrainingUiSnapshot &snap,
    const lv_font_t *cjk_font,
    uint8_t &painted_list,
    lv_event_cb_t on_action,
    lv_event_cb_t on_pick_org,
    lv_event_cb_t on_pick_course
);
