#pragma once

#include "kitty_ui.hpp"
#include "lvgl.h"

lv_obj_t *kitty_ui_work_ring_build(lv_obj_t *parent);
void kitty_ui_work_ring_paint(lv_obj_t *ring, KittyUiState state);
