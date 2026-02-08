/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#pragma once

#include "esp_gmf_element.h"

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */

/**
 * @brief  Configuration for the GMF copier.
 */
typedef struct {
    uint8_t  copy_num; /*!< Number of copies */
} esp_gmf_copier_cfg_t;

/**
 * @brief  Initializes the GMF copier using copier configuration.
 *
 * @param[in]   config  Pointer to the copier configuration
 * @param[out]  handle  Pointer to the copier handle to be initialized
 *
 * @return
 *       - ESP_GMF_ERR_OK           Success
 *       - ESP_GMF_ERR_INVALID_ARG  Invalid configuration provided
 *       - ESP_GMF_ERR_MEMORY_LACK  Failed to allocate memory
 */
esp_gmf_err_t esp_gmf_copier_init(esp_gmf_copier_cfg_t *config, esp_gmf_obj_handle_t *handle);

#ifdef __cplusplus
}
#endif /* __cplusplus */
