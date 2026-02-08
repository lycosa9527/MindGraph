/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#pragma once

#include "esp_gmf_pool.h"
#include "esp_gmf_element.h"
#include "esp_gmf_pipeline.h"
#include "esp_audio_simple_player.h"

#ifdef __cplusplus
extern "C" {
#endif  /* __cplusplus */

/**
 * @brief Structure representing the audio simple player instance
 */
typedef struct {
    esp_gmf_pool_handle_t      pool;        /*!< Handle to the element pool used for ASP */
    esp_gmf_pipeline_handle_t  pipe;        /*!< Handle to the audio pipeline */
    esp_asp_state_t            state;       /*!< Current state of the player (running, paused, stopped, etc.) */
    void                      *work_task;   /*!< Pointer to the player's worker task */
    esp_asp_cfg_t              cfg;         /*!< Configuration parameters for the player */
    esp_asp_event_func         event_cb;    /*!< Callback function for player events */
    void                      *user_ctx;    /*!< User context passed to event callbacks */
    void                      *wait_event;  /*!< Event used for task synchronization */
} esp_audio_simple_player_t;

#ifdef __cplusplus
}
#endif  /* __cplusplus */
