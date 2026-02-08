#ifndef DISPLAY_UTILS_H
#define DISPLAY_UTILS_H

#include "lvgl.h"

/**
 * @brief Clear the entire display with a solid color
 * @param color RGB565 color value (0x0000 = black, 0xFFFF = white)
 */
void display_clear_screen(uint16_t color);

/**
 * @brief DEPRECATED - Do not use for screen transitions
 */
void display_clear_before_switch(void);

/**
 * @brief Force full screen refresh
 */
void display_force_full_refresh(void);

/**
 * @brief Safely switch to a new screen with proper SPI queue management
 * 
 * This function handles screen transitions in a way that prevents SPI queue
 * overflow and ensures the new screen is fully rendered without artifacts.
 * 
 * @param new_screen The screen object to switch to
 */
void display_switch_screen(lv_obj_t* new_screen);

#endif
