/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#pragma once

#include "esp_err.h"
#include "esp_gmf_pool.h"
#include "av_processor_type.h"

#ifdef __cplusplus
extern "C" {
#endif  /* __cplusplus */

/**
 * @brief  Initialize audio playback pool
 *
 *         Creates and initializes a memory pool for audio playback operations.
 *         This pool manages memory for audio data that is being played back from
 *         various sources (files, streams, etc.).
 *
 * @param  pool  Pointer to store the created pool handle
 * @return
 *       - ESP_OK               Pool initialized successfully
 *       - ESP_ERR_NO_MEM       Insufficient memory to create pool
 *       - ESP_ERR_INVALID_ARG  Invalid parameter provided
 */
esp_err_t av_audio_playback_pool_init(esp_gmf_pool_handle_t *pool);

/**
 * @brief  Deinitialize audio playback pool
 *
 *         Destroys the audio playback pool and frees all associated memory.
 *
 * @param  pool  Handle of the pool to deinitialize
 * @return
 *       - ESP_OK               Pool deinitialized successfully
 *       - ESP_ERR_INVALID_ARG  Invalid pool handle
 */
esp_err_t av_audio_playback_pool_deinit(esp_gmf_pool_handle_t pool);

/**
 * @brief  Initialize audio recorder pool
 *
 * @param  pool        Pointer to store the created pool handle
 * @param  encoder_cfg Pointer to encoder configuration. If NULL, default PCM configuration will be used.
 * @return
 *       - ESP_OK               Pool initialized successfully
 *       - ESP_ERR_NO_MEM       Insufficient memory to create pool
 *       - ESP_ERR_INVALID_ARG  Invalid parameter provided
 */
esp_err_t av_audio_recorder_pool_init(esp_gmf_pool_handle_t *pool, const av_processor_encoder_config_t *encoder_cfg);

/**
 * @brief  Deinitialize audio recorder pool
 *
 *         Destroys the audio recorder pool and frees all associated memory.
 *         Make sure encoder is not running or else may cause memory violation error
 *
 * @param  pool  Handle of the pool to deinitialize
 * @return
 *       - ESP_OK               Pool deinitialized successfully
 *       - ESP_ERR_INVALID_ARG  Invalid pool handle
 */
esp_err_t av_audio_recorder_pool_deinit(esp_gmf_pool_handle_t pool);

/**
 * @brief  Initialize audio feeder pool
 *
 *         Creates and initializes a memory pool for audio feeder operations.
 *         This pool manages memory for audio data that is being fed into
 *         various processing pipelines or output streams.
 *
 * @param  pool         Pointer to store the created pool handle
 * @param  decoder_cfg  Pointer to decoder configuration. If NULL, default PCM configuration will be used.
 * @return
 *       - ESP_OK               Pool initialized successfully
 *       - ESP_ERR_NO_MEM       Insufficient memory to create pool
 *       - ESP_ERR_INVALID_ARG  Invalid parameter provided
 */
esp_err_t av_audio_feeder_pool_init(esp_gmf_pool_handle_t *pool, const av_processor_decoder_config_t *decoder_cfg);

/**
 * @brief  Deinitialize audio feeder pool
 *
 *         Destroys the audio feeder pool and frees all associated memory.
 *         Make sure decoder is not running or else may cause memory violation error
 *
 * @param  pool  Handle of the pool to deinitialize
 * @return
 *       - ESP_OK               Pool deinitialized successfully
 *       - ESP_ERR_INVALID_ARG  Invalid pool handle
 */
esp_err_t av_audio_feeder_pool_deinit(esp_gmf_pool_handle_t pool);

#ifdef __cplusplus
}
#endif  /* __cplusplus */
