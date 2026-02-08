/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#pragma once

#include "esp_gmf_io.h"

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */

/**
 * @brief  File IO configurations, if any entry is zero then the configuration will be set to default values
 */
typedef struct {
    int         dir;  /*!< IO direction, reader or writer */
    const char *name; /*!< Name for this instance */
} file_io_cfg_t;

#define FILE_IO_CFG_DEFAULT() {     \
    .dir  = ESP_GMF_IO_DIR_READER,  \
    .name = NULL,                   \
}

/**
 * @brief  Initializes the file stream I/O with the provided configuration
 *
 * @param[in]   config  Pointer to the file IO configuration
 * @param[out]  io      Pointer to the file IO handle to be initialized
 *
 * @return
 *       - ESP_GMF_ERR_OK           Success
 *       - ESP_GMF_ERR_INVALID_ARG  Invalid configuration provided
 *       - ESP_GMF_ERR_MEMORY_LACK  Failed to allocate memory
 */
esp_gmf_err_t esp_gmf_io_file_init(file_io_cfg_t *config, esp_gmf_io_handle_t *io);

#ifdef __cplusplus
}
#endif /* __cplusplus */
