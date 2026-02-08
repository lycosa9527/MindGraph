/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif  /* __cplusplus */

/**
 * @brief  Register an IO (Input/Output) to the Audio Simple Player (ASP) pool
 *
 * @param  handle  The handle to the Audio Simple Player instance
 */
void asp_pool_register_io(esp_asp_handle_t handle);

/**
 * @brief  Register an audio processing to the Audio Simple Player (ASP) pool
 *
 * @param  handle  The handle to the Audio Simple Player instance
 */
void asp_pool_register_audio(esp_asp_handle_t handle);

#ifdef __cplusplus
}
#endif  /* __cplusplus */
