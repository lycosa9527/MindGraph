#pragma once

#include "kitty_ui.hpp"
#include "lvgl.h"

void kitty_ui_mascot_build(lv_obj_t *host);
void kitty_ui_mic_draw(lv_obj_t *mic);
void kitty_ui_mic_paint(lv_obj_t *mic, lv_obj_t *ring_a, lv_obj_t *ring_b, bool hold, uint8_t level);
void kitty_ui_mascot_tick(KittyUiState state);
