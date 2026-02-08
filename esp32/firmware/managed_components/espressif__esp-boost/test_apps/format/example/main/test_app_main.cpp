/*
 * SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: CC0-1.0
 */
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_heap_caps.h"
#include "unity.h"
#include "unity_test_utils.h"
#include "common_components.hpp"

// Some resources are lazy allocated in the LCD driver, the threadhold is left for that case
#define TEST_MEMORY_LEAK_THRESHOLD (0)

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 3, 0)
void setUp(void)
{
    unity_utils_record_free_mem();
}

void tearDown(void)
{
    size_t memory_leak_threshold = common_get_memory_leak_threshold();
    esp_reent_cleanup();    //clean up some of the newlib's lazy allocations
    unity_utils_evaluate_leaks_direct(memory_leak_threshold);

    /* restore the threshold */
    if (memory_leak_threshold != TEST_MEMORY_LEAK_THRESHOLD) {
        common_set_memory_leak_threshold(TEST_MEMORY_LEAK_THRESHOLD);
    }
}
#else
static size_t before_free_8bit;
static size_t before_free_32bit;

void check_leak(size_t before_free, size_t after_free, const char *type)
{
    ssize_t delta = before_free - after_free;
    size_t memory_leak_threshold = common_get_memory_leak_threshold();
    printf(
        "MALLOC_CAP_%s: Before %u bytes free, After %u bytes free (delta %d, max %u)\n",
        type, before_free, after_free, delta, memory_leak_threshold
    );
    TEST_ASSERT_MESSAGE(delta <= memory_leak_threshold, "memory leak");
}

void setUp(void)
{
    before_free_8bit = heap_caps_get_free_size(MALLOC_CAP_8BIT);
    before_free_32bit = heap_caps_get_free_size(MALLOC_CAP_32BIT);

    /* restore the threshold */
    if (common_get_memory_leak_threshold() != TEST_MEMORY_LEAK_THRESHOLD) {
        common_set_memory_leak_threshold(TEST_MEMORY_LEAK_THRESHOLD);
    }
}

void tearDown(void)
{
    size_t after_free_8bit = heap_caps_get_free_size(MALLOC_CAP_8BIT);
    size_t after_free_32bit = heap_caps_get_free_size(MALLOC_CAP_32BIT);
    check_leak(before_free_8bit, after_free_8bit, "8BIT");
    check_leak(before_free_32bit, after_free_32bit, "32BIT");
}
#endif

extern "C" void app_main(void)
{
    /**
     *  ________                                             __            ________                                             __           
     * |        \                                           |  \          |        \                                           |  \          
     * | $$$$$$$$______    ______   ______ ____    ______  _| $$_         | $$$$$$$$ __    __  ______   ______ ____    ______  | $$  ______  
     * | $$__   /      \  /      \ |      \    \  |      \|   $$ \ ______ | $$__    |  \  /  \|      \ |      \    \  /      \ | $$ /      \ 
     * | $$  \ |  $$$$$$\|  $$$$$$\| $$$$$$\$$$$\  \$$$$$$\\$$$$$$|      \| $$  \    \$$\/  $$ \$$$$$$\| $$$$$$\$$$$\|  $$$$$$\| $$|  $$$$$$\
     * | $$$$$ | $$  | $$| $$   \$$| $$ | $$ | $$ /      $$ | $$ __\$$$$$$| $$$$$     >$$  $$ /      $$| $$ | $$ | $$| $$  | $$| $$| $$    $$
     * | $$    | $$__/ $$| $$      | $$ | $$ | $$|  $$$$$$$ | $$|  \      | $$_____  /  $$$$\|  $$$$$$$| $$ | $$ | $$| $$__/ $$| $$| $$$$$$$$
     * | $$     \$$    $$| $$      | $$ | $$ | $$ \$$    $$  \$$  $$      | $$     \|  $$ \$$\\$$    $$| $$ | $$ | $$| $$    $$| $$ \$$     \
     *  \$$      \$$$$$$  \$$       \$$  \$$  \$$  \$$$$$$$   \$$$$        \$$$$$$$$ \$$   \$$ \$$$$$$$ \$$  \$$  \$$| $$$$$$$  \$$  \$$$$$$$
     *                                                                                                                | $$                    
     *                                                                                                                | $$                    
     *                                                                                                                \$$    
    */
    printf("  ________                                             __            ________                                             __           \r\n");
    printf(" |        \\                                           |  \\          |        \\                                           |  \\          \r\n");
    printf(" | $$$$$$$$______    ______   ______ ____    ______  _| $$_         | $$$$$$$$ __    __  ______   ______ ____    ______  | $$  ______  \r\n");
    printf(" | $$__   /      \\  /      \\ |      \\    \\  |      \\|   $$ \\ ______ | $$__    |  \\  /  \\|      \\ |      \\    \\  /      \\ | $$ /      \\ \r\n");
    printf(" | $$  \\ |  $$$$$$\\|  $$$$$$\\| $$$$$$\\$$$$\\  \\$$$$$$\\\\$$$$$$|      \\| $$  \\    \\$$\\/  $$ \\$$$$$$\\| $$$$$$\\$$$$\\|  $$$$$$\\| $$|  $$$$$$\\\r\n");
    printf(" | $$$$$ | $$  | $$| $$   \\$$| $$ | $$ | $$ /      $$ | $$ __\\$$$$$$| $$$$$     >$$  $$ /      $$| $$ | $$ | $$| $$  | $$| $$| $$    $$\r\n");
    printf(" | $$    | $$__/ $$| $$      | $$ | $$ | $$|  $$$$$$$ | $$|  \\      | $$_____  /  $$$$\\|  $$$$$$$| $$ | $$ | $$| $$__/ $$| $$| $$$$$$$$\r\n");
    printf(" | $$     \\$$    $$| $$      | $$ | $$ | $$ \\$$    $$  \\$$  $$      | $$     \\|  $$ \\$$\\\\$$    $$| $$ | $$ | $$| $$    $$| $$ \\$$     \\\r\n");
    printf("  \\$$      \\$$$$$$  \\$$       \\$$  \\$$  \\$$  \\$$$$$$$   \\$$$$        \\$$$$$$$$ \\$$   \\$$ \\$$$$$$$ \\$$  \\$$  \\$$| $$$$$$$  \\$$  \\$$$$$$$\r\n");
    printf("                                                                                                               | $$                    \r\n");
    printf("                                                                                                               | $$                     \r\n");
    printf("                                                                                                                \\$$                     \r\n");
    unity_run_menu();
}
