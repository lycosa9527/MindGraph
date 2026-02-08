/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#include "esp_gmf_err.h"
#include "esp_gmf_pool.h"
#include "esp_gmf_video_dec.h"
#include "esp_gmf_video_enc.h"
#include "esp_video_dec_default.h"
#include "esp_video_enc_default.h"

static const char *TAG = "GMF_SETUP_VID_CODEC";
static uint32_t setup_cnt = 0;

#if defined(CONFIG_GMF_VIDEO_CODEC_INIT_DECODER)
static esp_gmf_err_t gmf_loader_setup_default_video_dec(esp_gmf_pool_handle_t pool)
{
    ESP_GMF_NULL_CHECK(TAG, pool, return ESP_GMF_ERR_INVALID_ARG);

    esp_gmf_err_t ret = ESP_GMF_ERR_OK;
    esp_gmf_element_handle_t dec = NULL;
    if (setup_cnt == 0) {
        esp_video_dec_register_default();
    }
    esp_gmf_video_dec_cfg_t dec_cfg = {0};
    dec_cfg.codec_cc = CONFIG_GMF_VIDEO_DEC_CODEC_TYPE;
    ret = esp_gmf_video_dec_init(&dec_cfg, &dec);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to init video dec");
    ret = esp_gmf_pool_register_element(pool, dec, NULL);
    ESP_GMF_RET_ON_ERROR(TAG, ret, {esp_gmf_element_deinit(dec); return ret;}, "Failed to register video dec");
    return ret;
}
#endif  /* CONFIG_GMF_VIDEO_CODEC_INIT_DECODER */

#if defined(CONFIG_GMF_VIDEO_CODEC_INIT_ENCODER)
static esp_gmf_err_t gmf_loader_setup_default_video_enc(esp_gmf_pool_handle_t pool)
{
    ESP_GMF_NULL_CHECK(TAG, pool, return ESP_GMF_ERR_INVALID_ARG);

    esp_gmf_err_t ret = ESP_GMF_ERR_OK;
    esp_gmf_element_handle_t enc = NULL;
    if (setup_cnt == 0) {
        esp_video_enc_register_default();
    }
    esp_gmf_video_enc_cfg_t enc_cfg = {0};
    enc_cfg.codec_cc = CONFIG_GMF_VIDEO_ENC_CODEC_TYPE;
    ret = esp_gmf_video_enc_init(&enc_cfg, &enc);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to init video enc");
    ret = esp_gmf_pool_register_element(pool, enc, NULL);
    ESP_GMF_RET_ON_ERROR(TAG, ret, {esp_gmf_element_deinit(enc); return ret;}, "Failed to register video enc");
    return ret;
}
#endif  /* CONFIG_GMF_VIDEO_CODEC_INIT_ENCODER */

esp_gmf_err_t gmf_loader_setup_video_codec_default(esp_gmf_pool_handle_t pool)
{
    ESP_GMF_NULL_CHECK(TAG, pool, return ESP_GMF_ERR_INVALID_ARG);

    esp_gmf_err_t ret = ESP_GMF_ERR_OK;

#if defined(CONFIG_GMF_VIDEO_CODEC_INIT_ENCODER)
    ret = gmf_loader_setup_default_video_enc(pool);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to setup video enc");
#endif  /* CONFIG_GMF_VIDEO_CODEC_INIT_ENCODER */

#if defined(CONFIG_GMF_VIDEO_CODEC_INIT_DECODER)
    ret = gmf_loader_setup_default_video_dec(pool);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to setup video dec");
#endif  /* CONFIG_GMF_VIDEO_CODEC_INIT_DECODER */

    setup_cnt++;
    return ret;
}

esp_gmf_err_t gmf_loader_teardown_video_codec_default(esp_gmf_pool_handle_t pool)
{
    ESP_GMF_NULL_CHECK(TAG, pool, return ESP_GMF_ERR_INVALID_ARG);
    if (setup_cnt == 0) {
        ESP_LOGW(TAG, "Default video codec is not initialized");
        return ESP_GMF_ERR_OK;
    }
    if ((--setup_cnt) == 0) {
#if defined(CONFIG_GMF_VIDEO_CODEC_INIT_DECODER)
        esp_video_dec_unregister_default();
#endif  /* CONFIG_GMF_VIDEO_CODEC_INIT_DECODER */
#if defined(CONFIG_GMF_VIDEO_CODEC_INIT_ENCODER)
        esp_video_enc_unregister_default();
#endif  /* CONFIG_GMF_VIDEO_CODEC_INIT_ENCODER */
        ESP_LOGW(TAG, "unregistered default video codec");
        setup_cnt = 0;
    } else {
        ESP_LOGW(TAG, "Default video codec is still in use");
    }

    return ESP_GMF_ERR_OK;
}
