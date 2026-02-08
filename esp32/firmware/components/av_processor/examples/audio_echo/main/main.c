/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "sdkconfig.h"

#include "esp_check.h"
#include "esp_gmf_afe.h"
#include "esp_codec_dev.h"
#include "audio_processor.h"

#include "esp_board_manager_adapter.h"

static const char *TAG = "AUDIO_PASSTHRU";

#define AUDIO_BUFFER_SIZE 1024

static esp_err_t audio_passthru_init(void)
{
    esp_board_manager_adapter_info_t bsp_info = {0};
    esp_board_manager_adapter_config_t bsp_config = ESP_BOARD_MANAGER_ADAPTER_CONFIG_DEFAULT();
    av_processor_afe_config_t afe_config = DEFAULT_AV_PROCESSOR_AFE_CONFIG();
    audio_manager_config_t config = DEFAULT_AUDIO_MANAGER_CONFIG();

    esp_board_manager_adapter_init(&bsp_config, &bsp_info);
    config.play_dev = bsp_info.play_dev;
    config.rec_dev = bsp_info.rec_dev;
    strcpy(config.mic_layout, bsp_info.mic_layout);
    config.board_sample_rate = bsp_info.sample_rate;
    config.board_bits = bsp_info.sample_bits;
    config.board_channels = bsp_info.channels;
    audio_manager_init(&config);

    esp_codec_dev_set_out_vol(config.play_dev, 60);
    esp_codec_dev_set_in_gain(config.rec_dev, 26.0);

    audio_playback_config_t playback_config = DEFAULT_AUDIO_PLAYBACK_CONFIG();
    audio_playback_open(&playback_config);

    av_processor_encoder_config_t recorder_cfg = {0};
    recorder_cfg.format = AV_PROCESSOR_FORMAT_ID_G711A;
    recorder_cfg.params.g711.audio_info.sample_rate = 16000;
    recorder_cfg.params.g711.audio_info.sample_bits = 16;
    recorder_cfg.params.g711.audio_info.channels = 1;
    recorder_cfg.params.g711.audio_info.frame_duration = 20;

    audio_recorder_config_t recorder_config = DEFAULT_AUDIO_RECORDER_CONFIG();
    memcpy((void *)&recorder_config.encoder_cfg, &recorder_cfg, sizeof(av_processor_encoder_config_t));
    memcpy(&recorder_config.afe_config, &afe_config, sizeof(av_processor_afe_config_t));
    recorder_config.recorder_event_cb = NULL;
    recorder_config.recorder_ctx = NULL;
    audio_recorder_open(&recorder_config);

    av_processor_decoder_config_t feeder_cfg = {0};
    feeder_cfg.format = AV_PROCESSOR_FORMAT_ID_G711A;
    feeder_cfg.params.g711.audio_info.sample_rate = 16000;
    feeder_cfg.params.g711.audio_info.sample_bits = 16;
    feeder_cfg.params.g711.audio_info.channels = 1;
    feeder_cfg.params.g711.audio_info.frame_duration = 20;

    audio_feeder_config_t feeder_config = DEFAULT_AUDIO_FEEDER_CONFIG();
    memcpy((void *)&feeder_config.decoder_cfg, &feeder_cfg, sizeof(av_processor_decoder_config_t));
    audio_feeder_open(&feeder_config);
    // audio_processor_mixer_open();
    audio_feeder_run();

    return ESP_OK;
}

int app_main(void)
{
    audio_passthru_init();

    uint8_t *audio_data = esp_gmf_oal_calloc(1, AUDIO_BUFFER_SIZE);
    if (!audio_data) {
        ESP_LOGE(TAG, "Failed to allocate audio buffer");
        return ESP_FAIL;
    }
    while (1) {
        int ret = audio_recorder_read_data(audio_data, AUDIO_BUFFER_SIZE);
        if (ret > 0) {
            audio_feeder_feed_data(audio_data, ret);
        }
    }
    return 0;
}
