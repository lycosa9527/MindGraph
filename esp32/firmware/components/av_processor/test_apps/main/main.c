/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#include <string.h>
#include "esp_heap_trace.h"
#include "esp_heap_caps.h"
#include "unity.h"
#include "esp_log.h"

#include "unity.h"
#include "unity_test_runner.h"
#include "unity_test_utils_memory.h"

#define TAG                        "MAIN"
#define TEST_MEMORY_LEAK_THRESHOLD (1024)

void setUp(void)
{
    unity_utils_record_free_mem();
}

void tearDown(void)
{
    unity_utils_evaluate_leaks_direct(TEST_MEMORY_LEAK_THRESHOLD);
}

void app_main(void)
{
    unity_run_menu();
}