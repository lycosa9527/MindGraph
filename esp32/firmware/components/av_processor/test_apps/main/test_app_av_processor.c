/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "unity.h"
#include "av_processor_type.h"
#include "audio_processor.h"
#include "video_processor.h"

static const char *TAG = "TEST_APP_AV_PROCESSOR";

typedef enum {
    AUDIO_CODEC_FORMAT_PCM = 0,
    AUDIO_CODEC_FORMAT_G711A,
    AUDIO_CODEC_FORMAT_OPUS,
} audio_codec_format_t;

static void configure_audio_codec(audio_codec_format_t format, av_processor_encoder_config_t *recorder_cfg, av_processor_decoder_config_t *feeder_cfg)
{
    if (format == AUDIO_CODEC_FORMAT_G711A) {
        recorder_cfg->format = AV_PROCESSOR_FORMAT_ID_G711A;
        recorder_cfg->params.g711.audio_info.sample_rate = 16000;
        recorder_cfg->params.g711.audio_info.sample_bits = 16;
        recorder_cfg->params.g711.audio_info.channels = 1;
        recorder_cfg->params.g711.audio_info.frame_duration = 20;
    }
    else if (format == AUDIO_CODEC_FORMAT_OPUS) {
        recorder_cfg->format = AV_PROCESSOR_FORMAT_ID_OPUS;
        recorder_cfg->params.opus.audio_info.sample_rate = 16000;
        recorder_cfg->params.opus.audio_info.sample_bits = 16;
        recorder_cfg->params.opus.audio_info.channels = 1;
        recorder_cfg->params.opus.audio_info.frame_duration = 60;
        recorder_cfg->params.opus.enable_vbr = false;
        recorder_cfg->params.opus.bitrate = 24000;
    }
    if (format == AUDIO_CODEC_FORMAT_G711A) {
        feeder_cfg->format = AV_PROCESSOR_FORMAT_ID_G711A;
        feeder_cfg->params.g711.audio_info.sample_rate = 16000;
        feeder_cfg->params.g711.audio_info.sample_bits = 16;
        feeder_cfg->params.g711.audio_info.channels = 1;
        feeder_cfg->params.g711.audio_info.frame_duration = 20;
    } else if (format == AUDIO_CODEC_FORMAT_OPUS) {
        feeder_cfg->format = AV_PROCESSOR_FORMAT_ID_OPUS;
        feeder_cfg->params.opus.audio_info.sample_rate = 16000;
        feeder_cfg->params.opus.audio_info.sample_bits = 16;
        feeder_cfg->params.opus.audio_info.channels = 1;
        feeder_cfg->params.opus.audio_info.frame_duration = 60;
    }
}

TEST_CASE("test audio manager init and deinit", "[av_processor]")
{
    audio_manager_config_t config = {
        .play_dev = NULL,
        .rec_dev = NULL,
        .mic_layout = "RMNM",
        .board_sample_rate = 16000,
        .board_bits = 16,
        .board_channels = 1,
        // .enable_mixer = true,
    };
    audio_manager_init(&config);
    audio_manager_deinit();
}

TEST_CASE("test audio playback open and close", "[av_processor]")
{
    audio_manager_config_t config = {
        .play_dev = NULL,
        .rec_dev = NULL,
        .mic_layout = "RMNM",
        .board_sample_rate = 16000,
        .board_bits = 16,
        .board_channels = 1,
        // .enable_mixer = true,
    };
    audio_manager_init(&config);
    vTaskDelay(pdMS_TO_TICKS(100));

    audio_playback_config_t playback_config = DEFAULT_AUDIO_PLAYBACK_CONFIG();
    for (int i = 0; i < 10; i++) {
        audio_playback_open(&playback_config);
        vTaskDelay(pdMS_TO_TICKS(1000));
        audio_playback_close();
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    audio_manager_deinit();
    vTaskDelay(pdMS_TO_TICKS(100));
}

TEST_CASE("test audio recorder open and close (SR and VC model switch)", "[av_processor]")
{
    audio_manager_config_t config = {
        .play_dev = NULL,
        .rec_dev = NULL,
        .mic_layout = "RMNM",
        .board_sample_rate = 16000,
        .board_bits = 16,
        .board_channels = 1,
    };
    audio_manager_init(&config);
    vTaskDelay(pdMS_TO_TICKS(100));

    audio_recorder_config_t recorder_config = DEFAULT_AUDIO_RECORDER_CONFIG();
    static av_processor_afe_config_t afe_config = DEFAULT_AV_PROCESSOR_AFE_CONFIG();
    av_processor_encoder_config_t recorder_cfg = {0};
    av_processor_decoder_config_t feeder_cfg = {0};

    configure_audio_codec(AUDIO_CODEC_FORMAT_G711A, &recorder_cfg, &feeder_cfg);
    memcpy(&recorder_config.afe_config, &afe_config, sizeof(av_processor_afe_config_t));
    memcpy((void *)&recorder_config.encoder_cfg, &recorder_cfg, sizeof(av_processor_encoder_config_t));
    int recorder_count = 0;
    for (int i = 0; i < 20; i++) {
        ESP_LOGI(TAG, "test audio recorder open and close (SR and VC model switch), count: %d", i);
        if (recorder_count % 2 == 0) {
            recorder_config.afe_config.afe_type = AFE_TYPE_SR;
        } else {
            recorder_config.afe_config.afe_type = AFE_TYPE_VC;
        }
        recorder_count++;
        printf("start open recorder\n");
        audio_recorder_open(&recorder_config);
        vTaskDelay(pdMS_TO_TICKS(500));
        printf("start close recorder\n");
        audio_recorder_close();
        printf("end close recorder\n");
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    audio_manager_deinit();
    vTaskDelay(pdMS_TO_TICKS(100));
}

TEST_CASE("test audio feeder open and close", "[av_processor]")
{
    audio_manager_config_t config = {
        .play_dev = NULL,
        .rec_dev = NULL,
        .mic_layout = "RMNM",
        .board_sample_rate = 16000,
        .board_bits = 32,
        .board_channels = 2,
    };
    audio_manager_init(&config);
    vTaskDelay(pdMS_TO_TICKS(100));

    audio_feeder_config_t feeder_config = DEFAULT_AUDIO_FEEDER_CONFIG();
    feeder_config.decoder_cfg.format = AV_PROCESSOR_FORMAT_ID_PCM;
    for (int i = 0; i < 50; i++) {
        audio_feeder_open(&feeder_config);
        vTaskDelay(pdMS_TO_TICKS(500));
        audio_feeder_close();
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    audio_manager_deinit();
    vTaskDelay(pdMS_TO_TICKS(100));
}
