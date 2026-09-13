#pragma once

#include "sdkconfig.h"

#include <cstdint>

inline constexpr int32_t k_face = CONFIG_BROOKESIA_HAL_ADAPTOR_DISPLAY_LCD_PANEL_H_RES;

inline constexpr int32_t watch_px(int32_t design_360)
{
    return design_360 * k_face / 360;
}
