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

#include "esp_capture_sink.h"
#include "esp_err.h"
#include "esp_video_dec.h"

/**
 * @brief  Default maximum number of video paths
 */
 #define DEFAULT_VID_MAX_PATH 2

/**
 * @brief  Video capture handle type
 */
typedef void *video_capture_handle_t;

/**
 * @brief  Video render handle type
 */
typedef void *video_render_handle_t;

/**
 * @brief  Video frame structure
 */
typedef struct {
    uint8_t  *data;  /*!< Frame data buffer */
    size_t    size;  /*!< Frame data size */
} video_frame_t;

/**
 * @brief  Video render decode callback function type
 *
 * @param[in]  ctx   User context pointer
 * @param[in]  data  Decoded frame data
 * @param[in]  size  Size of decoded frame data
 */
typedef void (*video_render_decode_callback_t)(void *ctx, const uint8_t *data, size_t size);

/**
 * @brief  Video capture frame callback function type
 *
 * @param[in]  ctx        User context pointer
 * @param[in]  index      Frame index
 * @param[in]  vid_frame  Captured video frame
 */
typedef void (*video_capture_frame_callback_t)(void *ctx, int sink_idx, esp_capture_stream_frame_t *vid_frame);

/**
 * @brief  Video render configuration structure
 */
typedef struct {
    esp_video_dec_cfg_t             decode_cfg;     /*!< Video decoder configuration */
    esp_video_codec_resolution_t    resolution;     /*!< Video resolution */
    video_render_decode_callback_t  decode_cb;      /*!< Decode callback function */
    void                           *decode_cb_ctx;  /*!< Decode callback context */
} video_render_config_t;

/**
 * @brief  Video capture configuration structure
 */
typedef struct {
    void                           *camera_config;                   /*!< Camera configuration */
    uint8_t                         sink_num;                        /*!< Number of sinks */
    esp_capture_sink_cfg_t          sink_cfg[DEFAULT_VID_MAX_PATH];  /*!< Sink configurations */
    video_capture_frame_callback_t  capture_frame_cb;                /*!< Capture frame callback function, this is valid only when stream_mode is true */
    void                           *capture_frame_cb_ctx;            /*!< Capture frame callback context, this is only valid when stream_mode is true */
    bool                            stream_mode;                     /*!< Stream mode, When stream_mode is true, the capture frame will be captured from capture_frame_cb,
                                                                        otherwise, we need called video_capture_fetch_frame_acquire and video_capture_fetch_frame_release to get the frame manually */
} video_capture_config_t;

/**
 * @brief  Opens a video capture session
 *
 * @param[in]  config  Video capture configuration
 *
 * @return
 *       - video_capture_handle  On success
 *       - NULL                  On failure
 */
video_capture_handle_t video_capture_open(video_capture_config_t *config);

/**
 * @brief  Closes a video capture session
 *
 * @param[in]  handle  Video capture handle
 */
void video_capture_close(video_capture_handle_t handle);

/**
 * @brief  Starts video capture
 *
 * @param[in]  handle  Video capture handle
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t video_capture_start(video_capture_handle_t handle);

/**
 * @brief  Stops video capture
 *
 * @param[in]  handle  Video capture handle
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t video_capture_stop(video_capture_handle_t handle);

/**
 * @brief  Fetches a video frame from the capture pipeline
 *         This function is only valid when stream_mode is false 
 *
 * @param[in]  handle  Video capture handle
 * @param[in]  sink_idx  Sink index
 * @param[out] frame   Video frame to fetch
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t video_capture_fetch_frame_acquire(video_capture_handle_t handle, int sink_idx, esp_capture_stream_frame_t *frame);

/**
 * @brief  Releases a video frame from the capture pipeline
 *         This function is only valid when stream_mode is false 
 *
 * @param[in]  handle  Video capture handle
 * @param[in]  sink_idx  Sink index
 * @param[in]  frame   Video frame to release
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t video_capture_fetch_frame_release(video_capture_handle_t handle, int sink_idx, esp_capture_stream_frame_t *frame);

/**
 * @brief  Opens a video render session
 *
 * @param[in]  config  Video render configuration
 *
 * @return
 *       - video_render_handle  On success
 *       - NULL                 On failure
 */
video_render_handle_t video_render_open(video_render_config_t *config);

/**
 * @brief  Closes a video render session
 *
 * @param[in]  handle  Video render handle
 */
void video_render_close(video_render_handle_t handle);

/**
 * @brief  Starts video rendering
 *
 * @param[in]  handle  Video render handle
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t video_render_start(video_render_handle_t handle);

/**
 * @brief  Stops video rendering
 *
 * @param[in]  handle  Video render handle
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t video_render_stop(video_render_handle_t handle);

/**
 * @brief  Feeds a video frame to the render pipeline
 *
 * @param[in]  handle  Video render handle
 * @param[in]  frame   Video frame to feed
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t video_render_feed_frame(video_render_handle_t handle, video_frame_t *frame);

#ifdef __cplusplus
}
#endif  /* __cplusplus */
