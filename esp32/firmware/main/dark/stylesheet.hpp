/*
 * SPDX-FileCopyrightText: 2024-2025 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#pragma once

#include "systems/speaker/stylesheets/360x360/dark/stylesheet.hpp"

namespace esp_brookesia::systems::speaker {

// Use the 360x360 Speaker stylesheet for now
// Note: Display is 410x502, but Speaker system only has 360x360 stylesheet
// This may cause layout issues, but will allow the system to function
constexpr Stylesheet STYLESHEET_410_502_DARK = STYLESHEET_360_360_DARK_STYLESHEET;

} // namespace esp_brookesia::systems::speaker

#ifdef ESP_BROOKESIA_SPEAKER_DEFAULT_DARK_STYLESHEET
#undef ESP_BROOKESIA_SPEAKER_DEFAULT_DARK_STYLESHEET
#endif
#define ESP_BROOKESIA_SPEAKER_DEFAULT_DARK_STYLESHEET() esp_brookesia::systems::speaker::STYLESHEET_410_502_DARK
