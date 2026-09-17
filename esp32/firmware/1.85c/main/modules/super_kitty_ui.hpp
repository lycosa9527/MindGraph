#pragma once

#include <string>
#include <vector>

#include "kitty_net.hpp"
#include "kitty_ui.hpp"

bool super_kitty_ui_start();
void super_kitty_ui_set_state(KittyUiState state);
void super_kitty_ui_set_live(const std::string &text);
void super_kitty_ui_set_user_text(const std::string &text);
void super_kitty_ui_set_kitty_text(const std::string &text);
void super_kitty_ui_set_choice(int index, const std::string &text);
void super_kitty_ui_begin_user_turn();
void super_kitty_ui_set_library(const std::string &title);
void super_kitty_ui_set_listen_level(uint8_t level);
void super_kitty_ui_set_diagrams(const std::vector<KittyDiagramItem> &items);
void super_kitty_ui_set_picker_status(const std::string &text);
bool super_kitty_ui_picker_needs_list();
bool super_kitty_ui_take_diagram_pick(KittyDiagramItem &item);
bool super_kitty_ui_take_create_mindmap();
void super_kitty_ui_queue_desktop_focus(const KittyDiagramItem &item);
bool super_kitty_ui_take_desktop_focus(KittyDiagramItem &item);
void super_kitty_ui_clear_desktop_focus();
int super_kitty_ui_take_choice();
bool super_kitty_ui_take_click();
bool super_kitty_ui_is_hidden();
bool super_kitty_ui_blocks_home();
bool super_kitty_ui_face_ready();
void super_kitty_ui_show();
void super_kitty_ui_hide();
