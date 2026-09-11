#pragma once

#include <string>
#include <vector>

#include "kitty_net.hpp"

enum class KittyUiState {
    connecting,
    idle,
    listening,
    thinking,
    speaking,
    error,
};

bool kitty_ui_start();
void kitty_ui_set_state(KittyUiState state);
void kitty_ui_set_live(const std::string &text);
void kitty_ui_set_user_text(const std::string &text);
void kitty_ui_set_kitty_text(const std::string &text);
void kitty_ui_set_choice(int index, const std::string &text);
void kitty_ui_begin_user_turn();
void kitty_ui_set_library(const std::string &title);
void kitty_ui_set_mic_level(uint8_t level);
void kitty_ui_set_diagrams(const std::vector<KittyDiagramItem> &items);
void kitty_ui_set_picker_status(const std::string &text);
bool kitty_ui_picker_needs_list();
bool kitty_ui_take_diagram_pick(KittyDiagramItem &item);
bool kitty_ui_take_create_mindmap();
bool kitty_ui_hold_active();
void kitty_ui_clear_hold();
int kitty_ui_take_choice();
bool kitty_ui_take_click();
bool kitty_ui_is_hidden();
void kitty_ui_show();
void kitty_ui_hide();
