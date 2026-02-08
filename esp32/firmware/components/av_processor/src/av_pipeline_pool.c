/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "esp_err.h"
#include "esp_log.h"
#include "esp_audio_dec_default.h"
#include "esp_audio_enc_default.h"
#include "esp_audio_simple_dec_default.h"
#include "esp_gmf_audio_dec.h"
#include "esp_gmf_audio_enc.h"
#include "esp_gmf_ch_cvt.h"
#include "esp_gmf_bit_cvt.h"
#include "esp_gmf_rate_cvt.h"
#include "esp_gmf_pool.h"
#include "esp_gmf_element.h"
#include "esp_gmf_fade.h"
#include "esp_gmf_err.h"
#include "av_processor_type.h"

static char *TAG = "AV_PIPELINE_POOL";

esp_err_t av_audio_playback_pool_init(esp_gmf_pool_handle_t *pool)
{
    *pool = NULL;
    esp_gmf_err_t ret = ESP_GMF_ERR_OK;
    esp_gmf_element_handle_t hd = NULL;
    esp_err_t err = esp_gmf_pool_init(pool);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return err;}, "Failed to initialize GMF pool");
    esp_audio_simple_dec_cfg_t es_dec_cfg = DEFAULT_ESP_GMF_AUDIO_DEC_CONFIG();
    esp_gmf_audio_dec_init(&es_dec_cfg, &hd);
    esp_gmf_pool_register_element(*pool, hd, NULL);
    return ret;
}

esp_err_t av_audio_playback_pool_deinit(esp_gmf_pool_handle_t pool)
{
    return esp_gmf_pool_deinit(pool);
}

esp_err_t av_audio_feeder_pool_init(esp_gmf_pool_handle_t *pool, const av_processor_decoder_config_t *decoder_cfg)
{
    *pool = NULL;
    esp_err_t ret = ESP_OK;
    esp_audio_simple_dec_cfg_t dec_cfg = DEFAULT_ESP_GMF_AUDIO_DEC_CONFIG();
    esp_gmf_element_handle_t el = NULL;
    esp_gmf_pool_init(pool);

    // Default to PCM if no config provided
    av_processor_format_id_t format = AV_PROCESSOR_FORMAT_ID_PCM;
    if (decoder_cfg) {
        format = decoder_cfg->format;
    }

    switch (format) {
        case AV_PROCESSOR_FORMAT_ID_PCM:
            dec_cfg.dec_type = ESP_AUDIO_SIMPLE_DEC_TYPE_PCM;
            break;

        case AV_PROCESSOR_FORMAT_ID_G711A: {
            dec_cfg.dec_type = ESP_AUDIO_SIMPLE_DEC_TYPE_G711A;
            esp_g711_dec_cfg_t g711_dec_cfg = {0};
            g711_dec_cfg.channel = decoder_cfg ? decoder_cfg->params.g711.audio_info.channels : 1;
            dec_cfg.dec_cfg = &g711_dec_cfg;
            dec_cfg.cfg_size = sizeof(esp_g711_dec_cfg_t);
            break;
        }

        case AV_PROCESSOR_FORMAT_ID_G711U: {
            dec_cfg.dec_type = ESP_AUDIO_SIMPLE_DEC_TYPE_G711U;
            esp_g711_dec_cfg_t g711_dec_cfg = {0};
            g711_dec_cfg.channel = decoder_cfg ? decoder_cfg->params.g711.audio_info.channels : 1;
            dec_cfg.dec_cfg = &g711_dec_cfg;
            dec_cfg.cfg_size = sizeof(esp_g711_dec_cfg_t);
            break;
        }

        case AV_PROCESSOR_FORMAT_ID_OPUS: {
            dec_cfg.dec_type = ESP_AUDIO_SIMPLE_DEC_TYPE_RAW_OPUS;
            esp_opus_dec_cfg_t opus_dec_cfg = ESP_OPUS_DEC_CONFIG_DEFAULT();
            if (decoder_cfg) {
                // Convert frame_duration from int to esp_opus_enc_frame_duration_t
                int frame_duration = decoder_cfg->params.opus.audio_info.frame_duration;
                switch (frame_duration) {
                    case 2: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_2_5_MS; break;
                    case 5: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_5_MS; break;
                    case 10: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_10_MS; break;
                    case 20: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_20_MS; break;
                    case 40: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_40_MS; break;
                    case 60: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_60_MS; break;
                    case 80: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_80_MS; break;
                    case 100: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_100_MS; break;
                    case 120: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_120_MS; break;
                    default: opus_dec_cfg.frame_duration = ESP_OPUS_DEC_FRAME_DURATION_60_MS; break;
                }
                opus_dec_cfg.channel = decoder_cfg->params.opus.audio_info.channels;
                opus_dec_cfg.sample_rate = decoder_cfg->params.opus.audio_info.sample_rate;
            }
            dec_cfg.dec_cfg = &opus_dec_cfg;
            dec_cfg.cfg_size = sizeof(esp_opus_dec_cfg_t);
            break;
        }

        case AV_PROCESSOR_FORMAT_ID_AAC:
            dec_cfg.dec_type = ESP_AUDIO_SIMPLE_DEC_TYPE_AAC;
            esp_aac_dec_cfg_t aac_dec_cfg = {0};
            aac_dec_cfg.no_adts_header = decoder_cfg->params.aac.no_adts_header;
            aac_dec_cfg.aac_plus_enable = decoder_cfg->params.aac.aac_plus_enable;
            dec_cfg.dec_cfg = &aac_dec_cfg;
            dec_cfg.cfg_size = sizeof(esp_aac_dec_cfg_t);
            break;

        default:
            ESP_LOGE(TAG, "Unsupported format: " AV_PROCESSOR_FOURCC_FMT, AV_PROCESSOR_FOURCC_ARGS(format));
            return ESP_ERR_NOT_SUPPORTED;
    }

    esp_gmf_audio_dec_init(&dec_cfg, &el);
    esp_gmf_pool_register_element(*pool, el, NULL);

    esp_ae_ch_cvt_cfg_t es_ch_cvt_cfg = DEFAULT_ESP_GMF_CH_CVT_CONFIG();
    ret = esp_gmf_ch_cvt_init(&es_ch_cvt_cfg, &el);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to init audio ch cvt");
    ret = esp_gmf_pool_register_element(*pool, el, NULL);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to register element in pool");

    esp_ae_bit_cvt_cfg_t es_bit_cvt_cfg = DEFAULT_ESP_GMF_BIT_CVT_CONFIG();
    ret = esp_gmf_bit_cvt_init(&es_bit_cvt_cfg, &el);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to init audio bit cvt");
    ret = esp_gmf_pool_register_element(*pool, el, NULL);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to register element in pool");

    esp_ae_rate_cvt_cfg_t es_rate_cvt_cfg = DEFAULT_ESP_GMF_RATE_CVT_CONFIG();
    esp_gmf_rate_cvt_init(&es_rate_cvt_cfg, &el);
    esp_gmf_pool_register_element(*pool, el, NULL);
    return ret;
}

esp_err_t av_audio_feeder_pool_deinit(esp_gmf_pool_handle_t pool)
{
    return esp_gmf_pool_deinit(pool);
}

esp_err_t av_audio_recorder_pool_init(esp_gmf_pool_handle_t *pool, const av_processor_encoder_config_t *encoder_cfg)
{
    *pool = NULL;
    esp_gmf_err_t ret = ESP_GMF_ERR_OK;
    esp_audio_enc_config_t enc_cfg = DEFAULT_ESP_GMF_AUDIO_ENC_CONFIG();
    esp_gmf_element_handle_t el = NULL;
    esp_err_t err = esp_gmf_pool_init(pool);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return err;}, "Failed to initialize GMF pool");

    esp_gmf_audio_enc_init(&enc_cfg, &el);
    esp_gmf_pool_register_element(*pool, el, NULL);

    esp_ae_ch_cvt_cfg_t es_ch_cvt_cfg = DEFAULT_ESP_GMF_CH_CVT_CONFIG();
    ret = esp_gmf_ch_cvt_init(&es_ch_cvt_cfg, &el);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to init audio ch cvt");
    ret = esp_gmf_pool_register_element(*pool, el, NULL);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to register element in pool");

    esp_ae_bit_cvt_cfg_t es_bit_cvt_cfg = DEFAULT_ESP_GMF_BIT_CVT_CONFIG();
    ret = esp_gmf_bit_cvt_init(&es_bit_cvt_cfg, &el);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to init audio bit cvt");
    ret = esp_gmf_pool_register_element(*pool, el, NULL);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to register element in pool");

    esp_ae_rate_cvt_cfg_t es_rate_cvt_cfg = DEFAULT_ESP_GMF_RATE_CVT_CONFIG();
    esp_gmf_rate_cvt_init(&es_rate_cvt_cfg, &el);
    esp_gmf_pool_register_element(*pool, el, NULL);

    return err;
}

esp_err_t av_audio_recorder_pool_deinit(esp_gmf_pool_handle_t pool)
{
    return esp_gmf_pool_deinit(pool);
}