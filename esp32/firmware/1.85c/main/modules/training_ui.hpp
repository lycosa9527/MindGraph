#pragma once

#include <string>
#include <vector>

struct TrainingOrgItem {
    int id = 0;
    std::string name;
};

struct TrainingCourseItem {
    std::string id;
    std::string title;
};

enum class TrainingUiPhase {
    pick_school,
    ready,
    armed,
    live,
    foreign,
    error,
};

enum class TrainingHostPill {
    idle,
    ready,
    stop,
};

enum class TrainingUiAction {
    none,
    prev,
    next,
    stop,
    lock,
    free,
    start,
    confirm_end,
    cancel_end,
    toggle_dropdown,
    pick_org,
    pick_course,
    change_school,
};

enum class TrainingDropdownMode {
    schools,
    courses,
};

bool training_ui_start();
void training_ui_show();
void training_ui_hide();
bool training_ui_is_hidden();
void training_ui_set_phase(TrainingUiPhase phase);
void training_ui_set_status(const std::string &text);
void training_ui_set_step(int index, int count);
void training_ui_set_can_prev(bool enabled);
void training_ui_set_can_next(bool enabled);
void training_ui_set_locked(bool locked);
void training_ui_set_pad_enabled(bool enabled);
void training_ui_set_pill(TrainingHostPill pill);
void training_ui_set_busy(bool busy);
void training_ui_set_confirm(bool open);
void training_ui_set_dropdown_open(bool open);
void training_ui_set_dropdown_mode(TrainingDropdownMode mode);
void training_ui_set_dropdown_label(const std::string &text);
void training_ui_set_school_name(const std::string &text);
void training_ui_set_school_locked(bool locked);
void training_ui_set_orgs(const std::vector<TrainingOrgItem> &items);
void training_ui_set_courses(const std::vector<TrainingCourseItem> &items);
void training_ui_set_active_course(const std::string &course_id);
TrainingUiAction training_ui_take_action();
int training_ui_take_org_index();
int training_ui_take_course_index();
