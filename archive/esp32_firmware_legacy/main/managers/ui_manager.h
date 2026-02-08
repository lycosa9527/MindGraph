#ifndef UI_MANAGER_H
#define UI_MANAGER_H

#include "esp_err.h"
#include "bsp/display.h"
#include "loading_screen.h"
#include "standby_screen.h"
#include "launcher.h"

enum UIState {
    UI_STATE_BOOT,
    UI_STATE_SETUP,
    UI_STATE_WAITING,
    UI_STATE_CONNECTING,
    UI_STATE_READY,
    UI_STATE_LEARNING_MODE,
    UI_STATE_VOICE_INTERACTION,
    UI_STATE_ERROR
};

void ui_manager_init();
void ui_manager_set_state(UIState state);
UIState ui_manager_get_state();
void ui_manager_update();
void ui_manager_show_watch_id(const char* watch_id);
void ui_manager_show_student_name(const char* student_name);
void ui_manager_show_transcription(const char* text);
void ui_manager_show_error(const char* error_msg);
void ui_manager_update_battery(int level, bool charging);
void ui_manager_update_time(const char* time_str);
void ui_manager_update_date(const char* date_str);

#endif