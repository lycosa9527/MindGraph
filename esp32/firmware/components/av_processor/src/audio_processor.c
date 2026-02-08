/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <string.h>
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

#include "esp_gmf_element.h"
#include "esp_gmf_pool.h"
#include "esp_gmf_pipeline.h"
#include "esp_gmf_audio_helper.h"
#include "esp_gmf_audio_enc.h"
#include "esp_fourcc.h"
#include "esp_audio_enc_default.h"
#include "esp_gmf_audio_dec.h"
#include "esp_gmf_rate_cvt.h"
#include "esp_gmf_bit_cvt.h"
#include "esp_gmf_ch_cvt.h"
#include "esp_audio_types.h"
#include "esp_audio_dec_default.h"
#include "esp_audio_simple_dec_default.h"
#include "av_pipeline_pool.h"
#include "esp_gmf_fifo.h"
#include "esp_codec_dev.h"
#include "esp_gmf_new_databus.h"

#include "esp_vad.h"
#include "esp_afe_config.h"
#include "esp_gmf_afe.h"

#include "esp_audio_render.h"
#include "esp_gmf_io_codec_dev.h"
#include "gmf_loader_setup_defaults.h"
#include "audio_processor.h"

#if CONFIG_MEDIA_DUMP_ENABLE
#include "media_dump.h"
#endif  /* CONFIG_MEDIA_DUMP_ENABLE */

#define AUDIO_OPUS_PIP_TASK_STACK_SIZE (4096 * 10)
#define AUDIO_BUFFER_SIZE              (2048)
#define AUDIO_RINGBUFFER_SIZE          (8192)
#define AUDIO_FIFO_NUM                 (5)

static char *TAG = "AUDIO_PROCESSOR";

enum audio_render_stream_type_e {
    AUDIO_RENDER_STREAM_FEEDER   = 0,
    AUDIO_RENDER_STREAM_PLAYBACK = 1,
    AUDIO_RENDER_STREAM_TYPE_MAX = 2,
};

enum audio_player_state_e {
    AUDIO_RUN_STATE_IDLE,
    AUDIO_RUN_STATE_PLAYING,
    AUDIO_RUN_STATE_CLOSED,
    AUDIO_RUN_STATE_PAUSED,
};

typedef struct {
    esp_asp_handle_t           player;
    enum audio_player_state_e  state;
    esp_gmf_pool_handle_t      pool;
    audio_playback_config_t    config;
} audio_playback_t;

typedef struct {
    esp_asp_handle_t           player;
    enum audio_player_state_e  state;
    esp_gmf_pool_handle_t      pool;
    audio_prompt_config_t      config;
} audio_prompt_t;

typedef struct {
    esp_gmf_fifo_handle_t         fifo;
    enum audio_player_state_e     state;
    esp_gmf_task_handle_t         task;
    esp_gmf_pipeline_handle_t     pipe;
    esp_gmf_afe_manager_handle_t  afe_manager;
    esp_gmf_pool_handle_t         pool;
    afe_config_t                 *afe_cfg;
    audio_recorder_config_t       config;
} audio_recorder_t;

typedef struct {
    esp_gmf_pipeline_handle_t  pipe;
    esp_gmf_db_handle_t        fifo;
    esp_gmf_task_handle_t      task;
    esp_gmf_pool_handle_t      pool;
    audio_feeder_config_t      config;
    enum audio_player_state_e  state;
} audio_feeder_t;

typedef struct {
    esp_gmf_pool_handle_t             pool;
    audio_manager_config_t            config;
    esp_audio_render_handle_t         render_handle;
    esp_audio_render_stream_handle_t  stream[AUDIO_RENDER_STREAM_TYPE_MAX];
    bool                              enable_mixer;
} audio_manager_t;

static audio_manager_t  audio_manager;
static audio_recorder_t audio_recorder;
static audio_feeder_t   audio_feeder;
static audio_playback_t audio_playback;
static audio_prompt_t   audio_prompt;

static inline esp_opus_enc_frame_duration_t convert_opus_dec_frame_duration(int frame_duration)
{
    switch (frame_duration) {
        case 2:
            return ESP_OPUS_DEC_FRAME_DURATION_2_5_MS;
        case 5:
            return ESP_OPUS_DEC_FRAME_DURATION_5_MS;
        case 10:
            return ESP_OPUS_DEC_FRAME_DURATION_10_MS;
        case 20:
            return ESP_OPUS_DEC_FRAME_DURATION_20_MS;
        case 40:
            return ESP_OPUS_DEC_FRAME_DURATION_40_MS;
        case 60:
            return ESP_OPUS_DEC_FRAME_DURATION_60_MS;
        case 80:
            return ESP_OPUS_DEC_FRAME_DURATION_80_MS;
        case 100:
            return ESP_OPUS_DEC_FRAME_DURATION_100_MS;
        case 120:
            return ESP_OPUS_DEC_FRAME_DURATION_120_MS;
        default:
            return ESP_OPUS_DEC_FRAME_DURATION_INVALID;
    }
}

static inline esp_opus_enc_frame_duration_t convert_opus_enc_frame_duration(int frame_duration)
{
    switch (frame_duration) {
        case 2:
            return ESP_OPUS_ENC_FRAME_DURATION_2_5_MS;
        case 5:
            return ESP_OPUS_ENC_FRAME_DURATION_5_MS;
        case 10:
            return ESP_OPUS_ENC_FRAME_DURATION_10_MS;
        case 20:
            return ESP_OPUS_ENC_FRAME_DURATION_20_MS;
        case 40:
            return ESP_OPUS_ENC_FRAME_DURATION_40_MS;
        case 60:
            return ESP_OPUS_ENC_FRAME_DURATION_60_MS;
        case 80:
            return ESP_OPUS_ENC_FRAME_DURATION_80_MS;
        case 100:
            return ESP_OPUS_ENC_FRAME_DURATION_100_MS;
        case 120:
            return ESP_OPUS_ENC_FRAME_DURATION_120_MS;
        default:
            return ESP_OPUS_ENC_FRAME_DURATION_ARG;
    }
}

static int audio_render_write_hdlr(uint8_t *pcm_data, uint32_t len, void *ctx)
{
    if ((audio_playback.state != AUDIO_RUN_STATE_PLAYING && audio_feeder.state != AUDIO_RUN_STATE_PLAYING)
        || audio_prompt.state == AUDIO_RUN_STATE_PLAYING) {
        ESP_LOGD(TAG, "Audio playback and feeder are not playing, skip write");
        return ESP_OK;
    }
    ESP_LOGD(TAG, "Audio render write handler, data size: %ld", len);
    esp_codec_dev_write(audio_manager.config.play_dev, pcm_data, len);
    return ESP_OK;
}

static int playback_out_data_callback(uint8_t *data, int data_size, void *ctx)
{
    if (audio_playback.state != AUDIO_RUN_STATE_PLAYING || audio_prompt.state == AUDIO_RUN_STATE_PLAYING) {
        ESP_LOGD(TAG, "Audio playback is not playing, skip write");
        return ESP_OK;
    }
    if (audio_manager.enable_mixer) {
        esp_audio_render_stream_write(audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK], data, data_size);
    } else {
        esp_codec_dev_write(audio_manager.config.play_dev, data, data_size);
    }
    return ESP_OK;
}

static int prompt_out_data_callback(uint8_t *data, int data_size, void *ctx)
{
    esp_codec_dev_write(audio_manager.config.play_dev, data, data_size);
    return ESP_OK;
}

static int playback_event_callback(esp_asp_event_pkt_t *event, void *ctx)
{
    if (event->type == ESP_ASP_EVENT_TYPE_MUSIC_INFO) {
        esp_asp_music_info_t info = {0};
        memcpy(&info, event->payload, event->payload_size);
        ESP_LOGI(TAG, "Get info, rate:%d, channels:%d, bits:%d", info.sample_rate, info.channels, info.bits);
    } else if (event->type == ESP_ASP_EVENT_TYPE_STATE) {
        esp_asp_state_t st = 0;
        memcpy(&st, event->payload, event->payload_size);
        ESP_LOGI(TAG, "Get State, %d,%s", st, esp_audio_simple_player_state_to_str(st));
        if (((st == ESP_ASP_STATE_STOPPED) || (st == ESP_ASP_STATE_FINISHED) || (st == ESP_ASP_STATE_ERROR))) {
            audio_playback.state = AUDIO_RUN_STATE_IDLE;
        }
        if (audio_playback.config.event_cb) {
            audio_player_state_t state = AUDIO_PLAYER_STATE_IDLE;
            if (st == ESP_ASP_STATE_STOPPED) {
                state = AUDIO_PLAYER_STATE_STOPPED;
            } else if (st == ESP_ASP_STATE_FINISHED) {
                state = AUDIO_PLAYER_STATE_FINISHED;
            } else if (st == ESP_ASP_STATE_ERROR) {
                state = AUDIO_PLAYER_STATE_ERROR;
            } else if (st == ESP_ASP_STATE_RUNNING) {
                state = AUDIO_PLAYER_STATE_PLAYING;
            } else if (st == ESP_ASP_STATE_PAUSED) {
                state = AUDIO_PLAYER_STATE_PAUSED;
            }
            audio_playback.config.event_cb(state, audio_playback.config.event_cb_ctx);
        }
    }
    return ESP_OK;
}

static int prompt_event_callback(esp_asp_event_pkt_t *event, void *ctx)
{
    if (event->type == ESP_ASP_EVENT_TYPE_MUSIC_INFO) {
        esp_asp_music_info_t info = {0};
        memcpy(&info, event->payload, event->payload_size);
        ESP_LOGI(TAG, "Get info, rate:%d, channels:%d, bits:%d", info.sample_rate, info.channels, info.bits);
    } else if (event->type == ESP_ASP_EVENT_TYPE_STATE) {
        esp_asp_state_t st = 0;
        memcpy(&st, event->payload, event->payload_size);
        ESP_LOGI(TAG, "prompt_event_callback: Get State, %d,%s", st, esp_audio_simple_player_state_to_str(st));
        if (((st == ESP_ASP_STATE_STOPPED) || (st == ESP_ASP_STATE_FINISHED) || (st == ESP_ASP_STATE_ERROR))) {
            audio_prompt.state = AUDIO_RUN_STATE_IDLE;
        }
    }
    return ESP_OK;
}

static esp_err_t recorder_pipeline_event(esp_gmf_event_pkt_t *event, void *ctx)
{
    ESP_LOGD(TAG, "CB: RECV Pipeline EVT: el:%s-%p, type:%d, sub:%s, payload:%p, size:%d,%p",
             OBJ_GET_TAG(event->from), event->from, event->type, esp_gmf_event_get_state_str(event->sub),
             event->payload, event->payload_size, ctx);
    return ESP_OK;
}

static int recorder_outport_acquire_write(void *handle, esp_gmf_data_bus_block_t *blk, int wanted_size, int block_ticks)
{
    int res = esp_gmf_fifo_acquire_write(audio_recorder.fifo, blk, wanted_size, block_ticks);
    if (res != ESP_GMF_ERR_OK && res != ESP_GMF_IO_ABORT) {
        ESP_LOGW(TAG, "Failed to acquire write (%d)", res);
    }
    return res;
}

static int recorder_outport_release_write(void *handle, esp_gmf_data_bus_block_t *blk, int block_ticks)
{
    int res = esp_gmf_fifo_release_write(audio_recorder.fifo, blk, block_ticks);
    if (res != ESP_GMF_ERR_OK && res != ESP_GMF_IO_ABORT) {
        ESP_LOGW(TAG, "Failed to release write (%d)", res);
    }
    return res;
}

static int recorder_inport_acquire_read(void *handle, esp_gmf_data_bus_block_t *blk, int wanted_size, int block_ticks)
{
    esp_codec_dev_read(audio_manager.config.rec_dev, blk->buf, wanted_size);
    blk->valid_size = wanted_size;
    if (audio_recorder.config.input_cb) {
        audio_recorder.config.input_cb(blk->buf, blk->valid_size, audio_recorder.config.input_ctx);
    }
#if CONFIG_MEDIA_DUMP_ENABLE && CONFIG_MEDIA_DUMP_AUDIO_BEFORE_AEC
    media_dump_feed(NULL, (uint8_t *)blk->buf, blk->valid_size);
#endif  /* CONFIG_MEDIA_DUMP_ENABLE && CONFIG_MEDIA_DUMP_AUDIO_BEFORE_AEC */
    return ESP_GMF_IO_OK;
}

static int recorder_inport_release_read(void *handle, esp_gmf_data_bus_block_t *blk, int block_ticks)
{
    return ESP_GMF_IO_OK;
}

static void esp_gmf_afe_event_cb(esp_gmf_obj_handle_t obj, esp_gmf_afe_evt_t *event, void *user_data)
{
    if (audio_recorder.config.recorder_event_cb) {
        audio_recorder.config.recorder_event_cb((void *)event, audio_recorder.config.recorder_ctx);
    }
    av_processor_afe_config_t *cfg = &audio_recorder.config.afe_config;
    bool handle_vcmd = cfg && cfg->ai_mode_wakeup && cfg->enable_vcmd_detect;

    switch (event->type) {
        case ESP_GMF_AFE_EVT_WAKEUP_START: {
            if (handle_vcmd) {
                esp_gmf_afe_vcmd_detection_cancel(obj);
                esp_gmf_afe_vcmd_detection_begin(obj);
            }
            esp_gmf_afe_wakeup_info_t *info = event->event_data;
            ESP_LOGI(TAG, "WAKEUP_START [%d : %d]", info->wake_word_index, info->wakenet_model_index);
            break;
        }
        case ESP_GMF_AFE_EVT_WAKEUP_END: {
            if (handle_vcmd) {
                esp_gmf_afe_vcmd_detection_cancel(obj);
            }
            ESP_LOGD(TAG, "WAKEUP_END");
            break;
        }
        case ESP_GMF_AFE_EVT_VAD_START: {
            if (handle_vcmd) {
                esp_gmf_afe_vcmd_detection_cancel(obj);
                esp_gmf_afe_vcmd_detection_begin(obj);
            }
            ESP_LOGD(TAG, "VAD_START");
            break;
        }
        case ESP_GMF_AFE_EVT_VAD_END: {
            if (handle_vcmd) {
                esp_gmf_afe_vcmd_detection_cancel(obj);
            }
            ESP_LOGD(TAG, "VAD_END");
            break;
        }
        case ESP_GMF_AFE_EVT_VCMD_DECT_TIMEOUT: {
            ESP_LOGD(TAG, "VCMD_DECT_TIMEOUT");
            break;
        }
        default: {
            esp_gmf_afe_vcmd_info_t *info = event->event_data;
            ESP_LOGW(TAG, "Command %d, phrase_id %d, prob %f, str: %s",
                     event->type, info->phrase_id, info->prob, info->str);
            break;
        }
    }
}

static esp_err_t recorder_setup_afe_config(void)
{
    av_processor_afe_config_t *cfg = &audio_recorder.config.afe_config;

    srmodel_list_t *models = esp_srmodel_init(cfg && cfg->model ? cfg->model : "model");
    if (!models) {
        if (cfg && cfg->ai_mode_wakeup) {
            ESP_LOGE(TAG, "Failed to initialize SR model. When ai_mode_wakeup is enabled, model is must be set");
            return ESP_FAIL;
        }
        ESP_LOGW(TAG, "No voice wakeup model found");
    }
    audio_recorder.afe_cfg = afe_config_init(audio_manager.config.mic_layout, models,
                                             cfg ? cfg->afe_type : AFE_TYPE_SR, AFE_MODE_LOW_COST);
    if (!audio_recorder.afe_cfg) {
        ESP_LOGE(TAG, "Failed to initialize AFE config");
        return ESP_FAIL;
    }
    audio_recorder.afe_cfg->aec_init = true;
    audio_recorder.afe_cfg->vad_init = cfg ? cfg->vad_enable : true;
    if (audio_recorder.afe_cfg->vad_init) {
        audio_recorder.afe_cfg->vad_mode = cfg ? cfg->vad_mode : 4;
        audio_recorder.afe_cfg->vad_min_speech_ms = cfg ? cfg->vad_min_speech_ms : 64;
        audio_recorder.afe_cfg->vad_min_noise_ms = cfg ? cfg->vad_min_noise_ms : 1000;
    }
    audio_recorder.afe_cfg->agc_init = cfg ? cfg->agc_enable : true;
    audio_recorder.afe_cfg->wakenet_init = cfg ? cfg->ai_mode_wakeup : false;

    esp_gmf_afe_manager_cfg_t afe_manager_cfg = DEFAULT_GMF_AFE_MANAGER_CFG(audio_recorder.afe_cfg, NULL, NULL, NULL, NULL);
    if (audio_recorder.config.afe_feed_task_config.task_stack > 0) {
        afe_manager_cfg.feed_task_setting.stack_size = audio_recorder.config.afe_feed_task_config.task_stack;
    }
    if (audio_recorder.config.afe_feed_task_config.task_prio > 0) {
        afe_manager_cfg.feed_task_setting.prio = audio_recorder.config.afe_feed_task_config.task_prio;
    }
    if (audio_recorder.config.afe_feed_task_config.task_core >= 0) {
        afe_manager_cfg.feed_task_setting.core = audio_recorder.config.afe_feed_task_config.task_core;
    }
    if (audio_recorder.config.afe_fetch_task_config.task_stack > 0) {
        afe_manager_cfg.fetch_task_setting.stack_size = audio_recorder.config.afe_fetch_task_config.task_stack;
    }
    if (audio_recorder.config.afe_fetch_task_config.task_prio > 0) {
        afe_manager_cfg.fetch_task_setting.prio = audio_recorder.config.afe_fetch_task_config.task_prio;
    }
    if (audio_recorder.config.afe_fetch_task_config.task_core >= 0) {
        afe_manager_cfg.fetch_task_setting.core = audio_recorder.config.afe_fetch_task_config.task_core;
    }
    esp_err_t ret = esp_gmf_afe_manager_create(&afe_manager_cfg, &audio_recorder.afe_manager);
    if (ret != ESP_OK) {
        afe_config_free(audio_recorder.afe_cfg);
        ESP_LOGE(TAG, "Failed to create AFE manager");
        return ESP_FAIL;
    }
    esp_gmf_element_handle_t gmf_afe = NULL;
    esp_gmf_afe_cfg_t gmf_afe_cfg = DEFAULT_GMF_AFE_CFG(audio_recorder.afe_manager, esp_gmf_afe_event_cb, NULL, models);
    gmf_afe_cfg.vcmd_detect_en = cfg ? cfg->enable_vcmd_detect : false;
    if (gmf_afe_cfg.vcmd_detect_en) {
        gmf_afe_cfg.vcmd_timeout = cfg ? cfg->vcmd_timeout_ms : 5000;
    }
    if (cfg && cfg->ai_mode_wakeup) {
        gmf_afe_cfg.mn_language = cfg->mn_language ? cfg->mn_language : "cn";
        gmf_afe_cfg.wakeup_end = cfg->wakeup_end_time_ms;
        gmf_afe_cfg.wakeup_time = cfg->wakeup_time_ms;
    } else {
        gmf_afe_cfg.wakeup_end = 0;
        gmf_afe_cfg.wakeup_time = 0;
    }

    ret = esp_gmf_afe_init(&gmf_afe_cfg, &gmf_afe);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {goto _quit;}, "Failed to initialize AFE element");

    afe_config_free(audio_recorder.afe_cfg);
    audio_recorder.afe_cfg = NULL;

    esp_gmf_pool_register_element(audio_recorder.pool, gmf_afe, NULL);
    return ESP_OK;

_quit:
    if (audio_recorder.afe_cfg) {
        afe_config_free(audio_recorder.afe_cfg);
        audio_recorder.afe_cfg = NULL;
    }
    if (audio_recorder.afe_manager) {
        esp_gmf_afe_manager_destroy(audio_recorder.afe_manager);
        audio_recorder.afe_manager = NULL;
    }
    return ret;
}

static void recorder_get_pipeline_config(const av_processor_encoder_config_t *encoder_cfg,
                                         const char ***elements, int *element_count,
                                         const char **input_name, const char **output_name)
{
    switch (encoder_cfg->format) {
        case AV_PROCESSOR_FORMAT_ID_G711A:
        case AV_PROCESSOR_FORMAT_ID_G711U:
            static const char *pipeline_g711[] = {"ai_afe", "aud_rate_cvt", "aud_enc"};
            *elements = pipeline_g711;
            *element_count = sizeof(pipeline_g711) / sizeof(pipeline_g711[0]);
            break;
        case AV_PROCESSOR_FORMAT_ID_OPUS:
            static const char *pipeline_opus[] = {"ai_afe", "aud_enc"};
            *elements = pipeline_opus;
            *element_count = sizeof(pipeline_opus) / sizeof(pipeline_opus[0]);
            break;
        case AV_PROCESSOR_FORMAT_ID_PCM:
        default:
            static const char *pipeline_pcm[] = {"ai_afe", "aud_rate_cvt", "aud_ch_cvt", "aud_bit_cvt", "aud_enc"};
            *elements = pipeline_pcm;
            *element_count = sizeof(pipeline_pcm) / sizeof(pipeline_pcm[0]);
            break;
    }

    *input_name = (*elements)[0];
    *output_name = (*elements)[*element_count - 1];
}

static esp_err_t recorder_setup_pipeline_ports(const char *input_name, const char *output_name)
{
    esp_gmf_port_handle_t outport = NEW_ESP_GMF_PORT_OUT_BLOCK(
        recorder_outport_acquire_write,
        recorder_outport_release_write,
        NULL, NULL, AUDIO_BUFFER_SIZE, portMAX_DELAY);

    esp_err_t ret = esp_gmf_pipeline_reg_el_port(audio_recorder.pipe, output_name, ESP_GMF_IO_DIR_WRITER, outport);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to register output port");

    esp_gmf_port_handle_t inport = NEW_ESP_GMF_PORT_IN_BYTE(
        recorder_inport_acquire_read,
        recorder_inport_release_read,
        NULL, NULL, AUDIO_BUFFER_SIZE, portMAX_DELAY);

    ret = esp_gmf_pipeline_reg_el_port(audio_recorder.pipe, input_name, ESP_GMF_IO_DIR_READER, inport);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to register input port");

    return ESP_OK;
}

static esp_err_t recorder_setup_task_and_run(void)
{
    esp_gmf_task_cfg_t cfg = DEFAULT_ESP_GMF_TASK_CONFIG();
    if (audio_recorder.config.recorder_task_config.task_stack > 0) {
        cfg.thread.stack = audio_recorder.config.recorder_task_config.task_stack;
        if (audio_recorder.config.encoder_cfg.format == AV_PROCESSOR_FORMAT_ID_OPUS && cfg.thread.stack < (4096 * 10)) {
            ESP_LOGW(TAG, "Recorder OPUS encoder requires larger stack size, using default 40k stack");
            cfg.thread.stack = AUDIO_OPUS_PIP_TASK_STACK_SIZE;
        }
    } else {
        cfg.thread.stack = AUDIO_OPUS_PIP_TASK_STACK_SIZE;
    }
    cfg.thread.prio = audio_recorder.config.recorder_task_config.task_prio;
    cfg.thread.core = audio_recorder.config.recorder_task_config.task_core;
    cfg.thread.stack_in_ext = audio_recorder.config.recorder_task_config.task_stack_in_ext;
    cfg.name = "audio_recorder_task";

    esp_err_t ret = esp_gmf_task_init(&cfg, &audio_recorder.task);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create recorder task");
        return ESP_FAIL;
    }
    esp_gmf_pipeline_bind_task(audio_recorder.pipe, audio_recorder.task);
    esp_gmf_pipeline_loading_jobs(audio_recorder.pipe);
    esp_gmf_pipeline_set_event(audio_recorder.pipe, recorder_pipeline_event, NULL);
    esp_gmf_task_set_timeout(audio_recorder.task, 8000);
    ret = esp_gmf_pipeline_run(audio_recorder.pipe);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to run recorder pipeline");

    return ESP_OK;
}

static void recorder_cleanup_on_error(void)
{
    if (audio_recorder.pipe) {
        esp_gmf_pipeline_stop(audio_recorder.pipe);
        esp_gmf_pipeline_destroy(audio_recorder.pipe);
        audio_recorder.pipe = NULL;
    }
    if (audio_recorder.task) {
        esp_gmf_task_deinit(audio_recorder.task);
        audio_recorder.task = NULL;
    }
    if (audio_recorder.fifo) {
        esp_gmf_fifo_destroy(audio_recorder.fifo);
        audio_recorder.fifo = NULL;
    }
    if (audio_recorder.afe_cfg) {
        afe_config_free(audio_recorder.afe_cfg);
        audio_recorder.afe_cfg = NULL;
    }
    if (audio_recorder.afe_manager) {
        ESP_LOGW(TAG, "AFE manager destroy");
        esp_gmf_afe_manager_destroy(audio_recorder.afe_manager);
        audio_recorder.afe_manager = NULL;
    }
}

static esp_err_t recorder_configure_all_encoders(void)
{
    if (!audio_recorder.pipe) {
        ESP_LOGE(TAG, "Pipeline not initialized for encoder configuration");
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t ret = ESP_OK;
    const av_processor_encoder_config_t *encoder_cfg = &audio_recorder.config.encoder_cfg;
    esp_gmf_element_handle_t enc_el = NULL;
    esp_gmf_pipeline_get_el_by_name(audio_recorder.pipe, "aud_enc", &enc_el);
    if (!enc_el) {
        ESP_LOGE(TAG, "Failed to get encoder element");
        return ESP_FAIL;
    }
    esp_gmf_info_sound_t info = {0};
    switch (encoder_cfg->format) {
        case AV_PROCESSOR_FORMAT_ID_G711A:
        case AV_PROCESSOR_FORMAT_ID_G711U:
            ESP_LOGI(TAG, "Configuring G711 encoder");
            if (encoder_cfg->params.g711.audio_info.channels != 1 || encoder_cfg->params.g711.audio_info.sample_rate != 8000) {
                ESP_LOGW(TAG, "G711 encoder only supports 1 channel and 8000 sample rate, using default config");
            }
            esp_g711_enc_config_t g711_enc_cfg = ESP_G711_ENC_CONFIG_DEFAULT();
            g711_enc_cfg.channel = encoder_cfg->params.g711.audio_info.channels;
            g711_enc_cfg.sample_rate = encoder_cfg->params.g711.audio_info.sample_rate;
            g711_enc_cfg.frame_duration = encoder_cfg->params.g711.audio_info.frame_duration;
            esp_audio_enc_config_t g711_cfg = {
                .type = encoder_cfg->format == AV_PROCESSOR_FORMAT_ID_G711A ? ESP_AUDIO_TYPE_G711A : ESP_AUDIO_TYPE_G711U,
                .cfg_sz = sizeof(esp_g711_enc_config_t),
                .cfg = &g711_enc_cfg,
            };
            ret = esp_gmf_audio_enc_reconfig(enc_el, &g711_cfg);
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to configure G711 encoder");
            esp_gmf_obj_handle_t rate_cvt = NULL;
            esp_gmf_pipeline_get_el_by_name(audio_recorder.pipe, "aud_rate_cvt", &rate_cvt);
            if (rate_cvt) {
                ret = esp_gmf_rate_cvt_set_dest_rate(rate_cvt, 8000);
                ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to set G711 rate converter destination rate");
            }
            esp_gmf_info_sound_t req_info = {
                .sample_rates = 16000,
                .channels = 1,
                .bits = 16,
            };
            ret = esp_gmf_pipeline_report_info(audio_recorder.pipe, ESP_GMF_INFO_SOUND, &req_info, sizeof(req_info));
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to report sound info for G711 encoder");
            break;

        case AV_PROCESSOR_FORMAT_ID_OPUS:
            ESP_LOGI(TAG, "Configuring OPUS encoder");
            esp_opus_enc_config_t opus_enc_cfg = ESP_OPUS_ENC_CONFIG_DEFAULT();
            opus_enc_cfg.channel = encoder_cfg->params.opus.audio_info.channels;
            opus_enc_cfg.sample_rate = encoder_cfg->params.opus.audio_info.sample_rate;
            opus_enc_cfg.frame_duration = convert_opus_enc_frame_duration(encoder_cfg->params.opus.audio_info.frame_duration);
            opus_enc_cfg.enable_vbr = encoder_cfg->params.opus.enable_vbr;
            opus_enc_cfg.bitrate = encoder_cfg->params.opus.bitrate;
            esp_audio_enc_config_t opus_cfg = {
                .type = ESP_AUDIO_TYPE_OPUS,
                .cfg_sz = sizeof(esp_opus_enc_config_t),
                .cfg = &opus_enc_cfg,
            };
            ret = esp_gmf_audio_enc_reconfig(enc_el, &opus_cfg);
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to configure OPUS encoder");
            esp_gmf_obj_handle_t rate_cvt_opus = NULL;
            ret = esp_gmf_pipeline_get_el_by_name(audio_recorder.pipe, "aud_rate_cvt", &rate_cvt_opus);
            if (ret == ESP_OK && rate_cvt_opus) {
                ret = esp_gmf_rate_cvt_set_dest_rate(rate_cvt_opus, 16000);
                ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to set OPUS rate converter destination rate");
            }
            info.sample_rates = 16000;
            info.channels = 1;
            info.bits = 16;
            info.format_id = ESP_AUDIO_TYPE_OPUS;
            ret = esp_gmf_pipeline_report_info(audio_recorder.pipe, ESP_GMF_INFO_SOUND, &info, sizeof(info));
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to report sound info for OPUS encoder");
            break;
        case AV_PROCESSOR_FORMAT_ID_PCM:
        default:
            ESP_LOGI(TAG, "Configuring PCM encoder");
            esp_gmf_obj_handle_t rate_cvt_pcm = NULL;
            esp_gmf_pipeline_get_el_by_name(audio_recorder.pipe, "aud_rate_cvt", &rate_cvt_pcm);
            if (rate_cvt_pcm) {
                ret = esp_gmf_rate_cvt_set_dest_rate(rate_cvt_pcm, encoder_cfg->params.pcm.audio_info.sample_rate);
                ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to set PCM rate converter destination rate");
            }
            esp_gmf_element_handle_t ch_cvt = NULL;
            esp_gmf_pipeline_get_el_by_name(audio_recorder.pipe, "aud_ch_cvt", &ch_cvt);
            if (ch_cvt) {
                ret = esp_gmf_ch_cvt_set_dest_channel(ch_cvt, encoder_cfg->params.pcm.audio_info.channels);
                ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to set PCM channel converter channels");
            }
            esp_gmf_element_handle_t bit_cvt = NULL;
            esp_gmf_pipeline_get_el_by_name(audio_recorder.pipe, "aud_bit_cvt", &bit_cvt);
            if (bit_cvt) {
                ret = esp_gmf_bit_cvt_set_dest_bits(bit_cvt, encoder_cfg->params.pcm.audio_info.sample_bits);
                ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to set PCM bit converter bits");
            }
            esp_pcm_enc_config_t pcm_enc_cfg = ESP_PCM_ENC_CONFIG_DEFAULT();
            pcm_enc_cfg.sample_rate = encoder_cfg->params.pcm.audio_info.sample_rate;
            pcm_enc_cfg.channel = encoder_cfg->params.pcm.audio_info.channels;
            pcm_enc_cfg.bits_per_sample = encoder_cfg->params.pcm.audio_info.sample_bits;
            pcm_enc_cfg.frame_duration = encoder_cfg->params.pcm.audio_info.frame_duration;

            esp_audio_enc_config_t enc_cfg = {
                .type = ESP_AUDIO_TYPE_PCM,
                .cfg_sz = sizeof(esp_pcm_enc_config_t),
                .cfg = &pcm_enc_cfg,
            };
            ret = esp_gmf_audio_enc_reconfig(enc_el, &enc_cfg);
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to configure PCM encoder");

            info.sample_rates = 16000;
            info.channels = 1;
            info.bits = 16;
            ret = esp_gmf_pipeline_report_info(audio_recorder.pipe, ESP_GMF_INFO_SOUND, &info, sizeof(info));
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to report sound info for PCM encoder");
            break;
    }

    ESP_LOGI(TAG, "All encoders configured successfully");
    return ESP_OK;
}

static int feeder_outport_acquire_write(void *handle, esp_gmf_data_bus_block_t *load, int wanted_size, int block_ticks)
{
    return wanted_size;
}

static int feeder_outport_release_write(void *handle, esp_gmf_data_bus_block_t *blk, int block_ticks)
{
    if (audio_manager.enable_mixer) {
        esp_audio_render_stream_write(audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER], blk->buf, blk->valid_size);
    } else {
        esp_codec_dev_write(audio_manager.config.play_dev, blk->buf, blk->valid_size);
    }
    return blk->valid_size;
}

static int feeder_inport_acquire_read(void *handle, esp_gmf_data_bus_block_t *blk, int wanted_size, int block_ticks)
{
    if (audio_feeder.config.decoder_cfg.format == AV_PROCESSOR_FORMAT_ID_PCM) {
        esp_gmf_data_bus_block_t _blk = {0};
        _blk.buf = blk->buf;
        _blk.buf_length = blk->buf_length;
        int ret = esp_gmf_db_acquire_read(audio_feeder.fifo, &_blk, wanted_size, block_ticks);
        if (ret < 0) {
            ESP_LOGE(TAG, "Ringbuffer acquire read failed (%d)", ret);
            return ret;
        }
        memcpy(blk->buf, _blk.buf, _blk.valid_size);
        blk->valid_size = _blk.valid_size;
        esp_gmf_db_release_read(audio_feeder.fifo, &_blk, block_ticks);
        blk->valid_size = _blk.valid_size;
    } else {
        int ret = esp_gmf_db_acquire_read(audio_feeder.fifo, blk, wanted_size, block_ticks);
        if (ret < 0) {
            ESP_LOGE(TAG, "FIFO acquire read failed (%d)", ret);
            return ret;
        }
        esp_gmf_db_release_read(audio_feeder.fifo, blk, block_ticks);
    }
    return ESP_GMF_ERR_OK;
}

static int feeder_inport_release_read(void *handle, esp_gmf_data_bus_block_t *blk, int block_ticks)
{
    return blk->valid_size;
}

static esp_err_t feeder_configure_all_decoders(void)
{
    esp_gmf_element_handle_t dec_el = NULL;
    esp_gmf_pipeline_get_el_by_name(audio_feeder.pipe, "aud_dec", &dec_el);
    if (!dec_el) {
        ESP_LOGE(TAG, "Failed to get decoder element");
        return ESP_FAIL;
    }
    esp_err_t ret = ESP_OK;
    const av_processor_decoder_config_t *decoder_cfg = &audio_feeder.config.decoder_cfg;
    esp_gmf_info_sound_t info = {0};
    switch (decoder_cfg->format) {
        case AV_PROCESSOR_FORMAT_ID_PCM:
            ESP_LOGI(TAG, "Configuring PCM decoder");
            info.sample_rates = decoder_cfg->params.pcm.audio_info.sample_rate;
            info.channels = decoder_cfg->params.pcm.audio_info.channels;
            info.bits = decoder_cfg->params.pcm.audio_info.sample_bits;
            info.format_id = ESP_AUDIO_SIMPLE_DEC_TYPE_PCM;
            ret = esp_gmf_audio_dec_reconfig_by_sound_info(dec_el, &info);
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to configure PCM decoder");
            break;

        case AV_PROCESSOR_FORMAT_ID_OPUS:
            ESP_LOGI(TAG, "Configuring OPUS decoder");
            esp_opus_dec_cfg_t opus_dec_cfg = ESP_OPUS_DEC_CONFIG_DEFAULT();
            opus_dec_cfg.frame_duration = convert_opus_dec_frame_duration(decoder_cfg->params.opus.audio_info.frame_duration);
            opus_dec_cfg.channel = decoder_cfg->params.opus.audio_info.channels;
            opus_dec_cfg.sample_rate = decoder_cfg->params.opus.audio_info.sample_rate;

            esp_audio_simple_dec_cfg_t dec_cfg = {
                .dec_type = ESP_AUDIO_TYPE_OPUS,
                .dec_cfg = &opus_dec_cfg,
                .cfg_size = sizeof(esp_opus_dec_cfg_t),
            };
            ret = esp_gmf_audio_dec_reconfig(dec_el, &dec_cfg);
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to configure OPUS decoder");

            info.sample_rates = decoder_cfg->params.opus.audio_info.sample_rate;
            info.channels = decoder_cfg->params.opus.audio_info.channels;
            info.bits = 16;
            info.format_id = ESP_FOURCC_OPUS;
            break;

        case AV_PROCESSOR_FORMAT_ID_G711A:
            ESP_LOGI(TAG, "Configuring G711A decoder");
            info.sample_rates = 8000;
            info.channels = 1;
            info.bits = 16;
            info.format_id = ESP_AUDIO_SIMPLE_DEC_TYPE_G711A;
            ret = esp_gmf_audio_dec_reconfig_by_sound_info(dec_el, &info);
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to configure G711A decoder");
            break;

        case AV_PROCESSOR_FORMAT_ID_G711U:
            ESP_LOGI(TAG, "Configuring G711U decoder");
            info.sample_rates = 8000;
            info.channels = 1;
            info.bits = 16;
            info.format_id = ESP_AUDIO_SIMPLE_DEC_TYPE_G711U;
            ret = esp_gmf_audio_dec_reconfig_by_sound_info(dec_el, &info);
            ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to configure G711U decoder");
            break;

        default:
            ESP_LOGE(TAG, "Unsupported decoder format: " AV_PROCESSOR_FOURCC_FMT, AV_PROCESSOR_FOURCC_ARGS(decoder_cfg->format));
            return ESP_ERR_NOT_SUPPORTED;
    }

    esp_gmf_pipeline_report_info(audio_feeder.pipe, ESP_GMF_INFO_SOUND, &info, sizeof(info));

    esp_gmf_element_handle_t rate_cvt_el = NULL;
    esp_gmf_pipeline_get_el_by_name(audio_feeder.pipe, "aud_rate_cvt", &rate_cvt_el);
    if (rate_cvt_el) {
        esp_gmf_rate_cvt_set_dest_rate(rate_cvt_el, audio_manager.config.board_sample_rate);
    }
    esp_gmf_element_handle_t ch_cvt_el = NULL;
    esp_gmf_pipeline_get_el_by_name(audio_feeder.pipe, "aud_ch_cvt", &ch_cvt_el);
    if (ch_cvt_el) {
        esp_gmf_ch_cvt_set_dest_channel(ch_cvt_el, audio_manager.config.board_channels);
    }
    esp_gmf_element_handle_t bit_cvt_el = NULL;
    esp_gmf_pipeline_get_el_by_name(audio_feeder.pipe, "aud_bit_cvt", &bit_cvt_el);
    if (bit_cvt_el) {
        esp_gmf_bit_cvt_set_dest_bits(bit_cvt_el, audio_manager.config.board_bits);
    }
    ESP_LOGI(TAG, "All decoders configured successfully");
    return ESP_OK;
}

static esp_err_t feeder_setup_pipeline_ports(void)
{
    esp_gmf_port_handle_t inport = {0};
    if (audio_feeder.config.decoder_cfg.format == AV_PROCESSOR_FORMAT_ID_PCM) {
        inport = NEW_ESP_GMF_PORT_IN_BYTE(
            feeder_inport_acquire_read,
            feeder_inport_release_read,
            NULL, NULL, AUDIO_BUFFER_SIZE, portMAX_DELAY);
    } else {
        inport = NEW_ESP_GMF_PORT_IN_BLOCK(
            feeder_inport_acquire_read,
            feeder_inport_release_read,
            NULL, NULL, AUDIO_BUFFER_SIZE, portMAX_DELAY);
    }
    esp_err_t ret = esp_gmf_pipeline_reg_el_port(audio_feeder.pipe, "aud_dec", ESP_GMF_IO_DIR_READER, inport);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to register playback input port");

    esp_gmf_port_handle_t outport = NEW_ESP_GMF_PORT_OUT_BYTE(
        feeder_outport_acquire_write,
        feeder_outport_release_write,
        NULL, NULL, AUDIO_BUFFER_SIZE, portMAX_DELAY);

    ret = esp_gmf_pipeline_reg_el_port(audio_feeder.pipe, "aud_rate_cvt", ESP_GMF_IO_DIR_WRITER, outport);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to register playback output port");

    return ESP_OK;
}

static void feeder_cleanup_on_error(void)
{
    if (audio_feeder.pipe) {
        esp_gmf_pipeline_destroy(audio_feeder.pipe);
        audio_feeder.pipe = NULL;
    }
    if (audio_feeder.task) {
        esp_gmf_task_deinit(audio_feeder.task);
        audio_feeder.task = NULL;
    }
    if (audio_feeder.fifo) {
        esp_gmf_db_deinit(audio_feeder.fifo);
        audio_feeder.fifo = NULL;
    }
}

esp_err_t av_processor_audio_manager_init(audio_manager_config_t *config)
{
    ESP_LOGI(TAG, "Initializing audio manager...");
    if (config == NULL) {
        ESP_LOGE(TAG, "Invalid configuration");
        return ESP_FAIL;
    }
    audio_manager.config = *config;

    esp_audio_dec_register_default();
    esp_audio_simple_dec_register_default();
    esp_audio_enc_register_default();

    audio_recorder.state = AUDIO_RUN_STATE_CLOSED;
    audio_feeder.state = AUDIO_RUN_STATE_CLOSED;
    audio_playback.state = AUDIO_RUN_STATE_CLOSED;
    // Default disable mixer
    audio_manager.enable_mixer = false;
    ESP_LOGI(TAG, "Audio manager initialized successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_manager_deinit(void)
{
    ESP_LOGI(TAG, "Deinitializing audio manager...");
    esp_audio_dec_unregister_default();
    esp_audio_simple_dec_unregister_default();
    esp_audio_enc_unregister_default();
    ESP_LOGI(TAG, "Audio manager deinitialized successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_playback_open(audio_playback_config_t *config)
{
    ESP_LOGI(TAG, "Opening audio playback...");

    if (config == NULL) {
        ESP_LOGE(TAG, "Invalid configuration");
        return ESP_FAIL;
    }
    audio_playback.config = *config;

    av_audio_playback_pool_init(&audio_playback.pool);
    esp_asp_cfg_t cfg = {
        .in.cb = NULL,
        .in.user_ctx = NULL,
        .out.cb = playback_out_data_callback,
        .out.user_ctx = NULL,
        .task_prio = audio_playback.config.playback_task_config.task_prio,
        .task_stack = audio_playback.config.playback_task_config.task_stack,
        .task_core = audio_playback.config.playback_task_config.task_core,
        .task_stack_in_ext = audio_playback.config.playback_task_config.task_stack_in_ext,
    };
    esp_err_t err = esp_audio_simple_player_new(&cfg, &audio_playback.player);
    if (err != ESP_OK || !audio_playback.player) {
        ESP_LOGE(TAG, "Failed to create audio playback player");
        return ESP_FAIL;
    }
    err = esp_audio_simple_player_set_event(audio_playback.player, playback_event_callback, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set playback event callback");
        esp_audio_simple_player_destroy(audio_playback.player);
        audio_playback.player = NULL;
        return ESP_FAIL;
    }
    audio_playback.state = AUDIO_RUN_STATE_IDLE;
    ESP_LOGI(TAG, "Audio playback opened successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_playback_close(void)
{
    if (audio_playback.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGW(TAG, "Audio playback is already closed");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Closing audio playback...");
    if (audio_playback.state == AUDIO_RUN_STATE_PLAYING) {
        esp_audio_simple_player_stop(audio_playback.player);
    }
    if (audio_playback.player) {
        esp_err_t err = esp_audio_simple_player_destroy(audio_playback.player);
        ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to destroy audio playback player");
        audio_playback.player = NULL;
    }
    if (audio_playback.pool) {
        av_audio_playback_pool_deinit(audio_playback.pool);
        audio_playback.pool = NULL;
    }
    audio_playback.state = AUDIO_RUN_STATE_CLOSED;
    ESP_LOGI(TAG, "Audio playback closed successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_playback_play(const char *url)
{
    if (!url) {
        ESP_LOGE(TAG, "Invalid URL for playback");
        return ESP_FAIL;
    }
    if (audio_playback.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot play playback - not opened");
        return ESP_FAIL;
    }
    if (audio_playback.state == AUDIO_RUN_STATE_PLAYING) {
        ESP_LOGW(TAG, "Audio playback is already playing, stopping current playback");
        esp_audio_simple_player_stop(audio_playback.player);
    }
    audio_playback.state = AUDIO_RUN_STATE_PLAYING;
    ESP_LOGI(TAG, "Starting playback: %s, state: %d", url, audio_playback.state);
    esp_err_t err = esp_audio_simple_player_run(audio_playback.player, url, NULL);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {audio_playback.state = AUDIO_RUN_STATE_IDLE; return ESP_FAIL;}, "Failed to start playback");

    return ESP_OK;
}

esp_err_t av_processor_audio_playback_play_to_end(const char *url)
{
    if (!url) {
        ESP_LOGE(TAG, "Invalid URL for playback");
        return ESP_FAIL;
    }
    if (audio_playback.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot play playback - not opened");
        return ESP_FAIL;
    }
    if (audio_playback.state == AUDIO_RUN_STATE_PLAYING) {
        ESP_LOGW(TAG, "Audio playback is already playing, waiting for it to end");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Waiting for playback to end: %s", url);
    esp_err_t err = esp_audio_simple_player_run_to_end(audio_playback.player, url, NULL);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to wait for playback to end");
    audio_playback.state = AUDIO_RUN_STATE_IDLE;
    return ESP_OK;
}

esp_err_t av_processor_audio_playback_pause(void)
{
    if (audio_playback.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot pause playback - not opened");
        return ESP_FAIL;
    }
    if (audio_playback.state == AUDIO_RUN_STATE_PAUSED) {
        ESP_LOGW(TAG, "Audio playback is already paused");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Pausing audio playback...");
    esp_err_t err = esp_audio_simple_player_pause(audio_playback.player);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to pause playback");
    audio_playback.state = AUDIO_RUN_STATE_PAUSED;
    ESP_LOGI(TAG, "Audio playback paused successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_playback_resume(void)
{
    if (audio_playback.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot resume playback - not opened");
        return ESP_FAIL;
    }
    if (audio_playback.state == AUDIO_RUN_STATE_PLAYING) {
        ESP_LOGW(TAG, "Audio playback is already playing");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Resuming audio playback...");
    esp_err_t err = esp_audio_simple_player_resume(audio_playback.player);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to resume playback");
    audio_playback.state = AUDIO_RUN_STATE_PLAYING;
    ESP_LOGI(TAG, "Audio playback resumed successfully");
    return ESP_OK;
}

enum audio_player_state_e audio_playback_get_state(void)
{
    return audio_playback.state;
}

esp_err_t av_processor_audio_playback_stop(void)
{
    if (audio_playback.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot stop playback - not opened");
        return ESP_FAIL;
    }
    if (audio_playback.state == AUDIO_RUN_STATE_IDLE) {
        ESP_LOGW(TAG, "Audio playback is already idle");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Stopping audio playback...");
    esp_err_t err = esp_audio_simple_player_stop(audio_playback.player);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to stop playback");

    audio_playback.state = AUDIO_RUN_STATE_IDLE;
    ESP_LOGI(TAG, "Audio playback stopped successfully");
    return ESP_OK;
}


esp_err_t av_processor_audio_prompt_open(audio_prompt_config_t *config)
{
    if (config == NULL) {
        ESP_LOGE(TAG, "Invalid configuration");
        return ESP_FAIL;
    }
    audio_prompt.config = *config;

    av_audio_playback_pool_init(&audio_prompt.pool);

    esp_asp_cfg_t cfg = {
        .in.cb = NULL,
        .in.user_ctx = NULL,
        .out.cb = prompt_out_data_callback,
        .out.user_ctx = NULL,
        .task_prio = audio_prompt.config.prompt_task_config.task_prio,
        .task_stack = audio_prompt.config.prompt_task_config.task_stack,
        .task_core = audio_prompt.config.prompt_task_config.task_core,
        .task_stack_in_ext = audio_prompt.config.prompt_task_config.task_stack_in_ext,
    };
    esp_err_t err = esp_audio_simple_player_new(&cfg, &audio_prompt.player);
    if (err != ESP_OK || !audio_prompt.player) {
        ESP_LOGE(TAG, "Failed to create audio prompt player");
        return ESP_FAIL;
    }
    err = esp_audio_simple_player_set_event(audio_prompt.player, prompt_event_callback, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set prompt event callback");
        esp_audio_simple_player_destroy(audio_prompt.player);
        audio_prompt.player = NULL;
        return ESP_FAIL;
    }
    audio_prompt.state = AUDIO_RUN_STATE_IDLE;
    ESP_LOGI(TAG, "Audio prompt opened successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_prompt_close(void)
{
    if (audio_prompt.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGW(TAG, "Audio prompt is already closed");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Closing audio prompt...");
    if (audio_prompt.state == AUDIO_RUN_STATE_IDLE) {
        ESP_LOGW(TAG, "Audio prompt is already idle");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Stopping audio prompt...");
    if (audio_prompt.state == AUDIO_RUN_STATE_PLAYING) {
        // NOTE: Normally, not will reach here, because the prompt is played to end automatically.
        ESP_LOGW(TAG, "Audio prompt is playing, stopping current prompt");
        esp_audio_simple_player_stop(audio_prompt.player);
    }
    if (audio_prompt.player) {
        esp_err_t err = esp_audio_simple_player_destroy(audio_prompt.player);
        ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to destroy audio prompt player");
        audio_prompt.player = NULL;
    }
    if (audio_prompt.pool) {
        av_audio_playback_pool_deinit(audio_prompt.pool);
        audio_prompt.pool = NULL;
    }
    audio_prompt.state = AUDIO_RUN_STATE_IDLE;
    ESP_LOGI(TAG, "Audio prompt stopped successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_prompt_play(const char *url)
{
    if (!url) {
        ESP_LOGE(TAG, "Invalid URL for prompt");
        return ESP_FAIL;
    }
    if (audio_prompt.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot play prompt - not opened");
        return ESP_FAIL;
    }
    if (audio_prompt.state == AUDIO_RUN_STATE_PLAYING) {
        // NOTE: Normally, not will reach here, because the prompt is played to end automatically.
        ESP_LOGW(TAG, "Audio prompt is already playing, stopping current prompt");
        esp_audio_simple_player_stop(audio_prompt.player);
    }
    audio_prompt.state = AUDIO_RUN_STATE_PLAYING;
    ESP_LOGI(TAG, "Starting prompt: %s, state: %d", url, audio_prompt.state);
    esp_err_t err = esp_audio_simple_player_run_to_end(audio_prompt.player, url, NULL);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to start prompt");
    audio_prompt.state = AUDIO_RUN_STATE_IDLE;

    return ESP_OK;
}

esp_err_t av_processor_audio_recorder_open(audio_recorder_config_t *config)
{
    ESP_LOGI(TAG, "Opening audio recorder...");

    if (config == NULL) {
        ESP_LOGE(TAG, "Invalid configuration");
        return ESP_FAIL;
    }
    memcpy(&audio_recorder.config, config, sizeof(audio_recorder_config_t));

    esp_err_t err = esp_gmf_fifo_create(5, 1, &audio_recorder.fifo);
    if (err != ESP_GMF_ERR_OK) {
        ESP_LOGE(TAG, "Failed to create FIFO, err: %d", err);
        return ESP_FAIL;
    }
    av_audio_recorder_pool_init(&audio_recorder.pool, &audio_recorder.config.encoder_cfg);
    ESP_GMF_POOL_SHOW_ITEMS(audio_recorder.pool);
    err = recorder_setup_afe_config();
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {goto cleanup_and_exit;}, "Failed to setup AFE config");

    const char **elements;
    int element_count = 0;
    const char *input_name = NULL, *output_name = NULL;
    recorder_get_pipeline_config(&audio_recorder.config.encoder_cfg, &elements, &element_count, &input_name, &output_name);

    err = esp_gmf_pool_new_pipeline(audio_recorder.pool, NULL, elements, element_count, NULL, &audio_recorder.pipe);
    if (err != ESP_OK || audio_recorder.pipe == NULL) {
        ESP_LOGE(TAG, "Failed to create recorder pipeline: %02x", err);
        goto cleanup_and_exit;
    }
    err = recorder_configure_all_encoders();
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {goto cleanup_and_exit;}, "Failed to configure encoders");

    err = recorder_setup_pipeline_ports(input_name, output_name);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {goto cleanup_and_exit;}, "Failed to setup pipeline ports");

    err = recorder_setup_task_and_run();
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {goto cleanup_and_exit;}, "Failed to setup task and run");

    audio_recorder.state = AUDIO_RUN_STATE_PLAYING;

    ESP_LOGI(TAG, "Audio recorder opened successfully");
    return ESP_OK;

cleanup_and_exit:
    ESP_LOGE(TAG, "Failed to open audio recorder, cleaning up...");
    recorder_cleanup_on_error();
    return ESP_FAIL;
}

esp_err_t audio_recorder_get_afe_manager_handle(esp_gmf_afe_manager_handle_t *afe_manager_handle)
{
    if (!afe_manager_handle) {
        ESP_LOGE(TAG, "Invalid parameters for recorder get origin AFE handle");
        return ESP_FAIL;
    }
    if (!audio_recorder.afe_manager) {
        ESP_LOGE(TAG, "Audio recorder AFE manager not initialized");
        return ESP_FAIL;
    }
    *afe_manager_handle = audio_recorder.afe_manager;
    return ESP_OK;
}

esp_err_t audio_recorder_get_afe_element_handle(esp_gmf_element_handle_t *afe_element_handle)
{
    if (!afe_element_handle) {
        ESP_LOGE(TAG, "Invalid parameters for recorder get AFE element handle");
        return ESP_FAIL;
    }
    esp_gmf_pipeline_get_el_by_name(audio_recorder.pipe, "ai_afe", afe_element_handle);
    if (!afe_element_handle) {
        ESP_LOGE(TAG, "Failed to get AFE element handle");
        return ESP_FAIL;
    }
    return ESP_OK;
}

esp_err_t av_processor_audio_recorder_close(void)
{
    if (audio_recorder.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGW(TAG, "Audio recorder is already closed");
        return ESP_OK;
    }
    // NOTE: Set task priority to 23 is a workaround for the issue that the recorder task is preempted by other tasks.
    UBaseType_t basic_priority = uxTaskPriorityGet(NULL);
    vTaskPrioritySet(NULL, 23);
    vTaskDelay(pdMS_TO_TICKS(10));
    ESP_LOGI(TAG, "Closing audio recorder...");
    if (audio_recorder.pipe) {
        esp_gmf_fifo_abort(audio_recorder.fifo);
        esp_gmf_pipeline_stop(audio_recorder.pipe);
        audio_recorder.pipe = NULL;
    }
    if (audio_recorder.task) {
        esp_gmf_task_deinit(audio_recorder.task);
        audio_recorder.task = NULL;
    }
    if (audio_recorder.fifo) {
        esp_gmf_fifo_destroy(audio_recorder.fifo);
        audio_recorder.fifo = NULL;
    }
    if (audio_recorder.afe_cfg) {
        afe_config_free(audio_recorder.afe_cfg);
        audio_recorder.afe_cfg = NULL;
    }
    if (audio_recorder.afe_manager) {
        esp_gmf_afe_manager_destroy(audio_recorder.afe_manager);
        audio_recorder.afe_manager = NULL;
    }
    if (audio_recorder.pipe) {
        esp_gmf_pipeline_destroy(audio_recorder.pipe);
        audio_recorder.pipe = NULL;
    }
    if (audio_recorder.pool) {
        av_audio_recorder_pool_deinit(audio_recorder.pool);
        audio_recorder.pool = NULL;
    }
    audio_recorder.state = AUDIO_RUN_STATE_CLOSED;

    vTaskPrioritySet(NULL, basic_priority);

    ESP_LOGI(TAG, "Audio recorder closed successfully");
    return ESP_OK;
}

esp_err_t av_processor_audio_recorder_read_data(uint8_t *data, int data_size)
{
    if (!data || data_size <= 0) {
        ESP_LOGE(TAG, "Invalid parameters for recorder read");
        return ESP_FAIL;
    }
    if (audio_recorder.state == AUDIO_RUN_STATE_CLOSED || !audio_recorder.fifo) {
        ESP_LOGE(TAG, "Recorder not available for reading");
        return ESP_FAIL;
    }
    esp_gmf_data_bus_block_t blk = {0};
    int ret = esp_gmf_fifo_acquire_read(audio_recorder.fifo, &blk, data_size, portMAX_DELAY);
    if (ret < 0) {
        ESP_LOGE(TAG, "Failed to acquire read from recorder FIFO (%d)", ret);
        return ret;
    }
    int bytes_to_copy = blk.valid_size;
    if (bytes_to_copy > data_size) {
        ESP_LOGI(TAG, "Read data size is larger than expected, valid size: %d, expected: %d", bytes_to_copy, data_size);
        bytes_to_copy = data_size;
    }
    memcpy(data, blk.buf, bytes_to_copy);
    esp_gmf_fifo_release_read(audio_recorder.fifo, &blk, portMAX_DELAY);

#if CONFIG_MEDIA_DUMP_ENABLE && CONFIG_MEDIA_DUMP_AUDIO_AFTER_AEC
    media_dump_feed(NULL, (uint8_t *)blk.buf, blk.valid_size);
#endif  /* CONFIG_MEDIA_DUMP_ENABLE && CONFIG_MEDIA_DUMP_AUDIO_AFTER_AEC */
    return bytes_to_copy;
}
esp_err_t audio_feeder_feed_data(uint8_t *data, int data_size)
{
    if (!data || data_size <= 0) {
        ESP_LOGE(TAG, "Invalid parameters for playback feed");
        return ESP_FAIL;
    }
    if (audio_feeder.state == AUDIO_RUN_STATE_CLOSED || !audio_feeder.fifo) {
        ESP_LOGW(TAG, "Playback not available for feeding");
        return ESP_FAIL;
    }
    esp_gmf_data_bus_block_t blk = {0};

    if (audio_feeder.config.decoder_cfg.format == AV_PROCESSOR_FORMAT_ID_PCM) {
        int ret = esp_gmf_db_acquire_write(audio_feeder.fifo, &blk, data_size, portMAX_DELAY);
        if (ret < 0) {
            ESP_LOGE(TAG, "Failed to acquire write to playback FIFO (0x%x)", ret);
            return ESP_FAIL;
        }
        blk.buf = (uint8_t *)data;
        blk.valid_size = data_size;
        ret = esp_gmf_db_release_write(audio_feeder.fifo, &blk, portMAX_DELAY);
        ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to release write to playback FIFO");
    } else {
        int ret = esp_gmf_db_acquire_write(audio_feeder.fifo, &blk, data_size, portMAX_DELAY);
        if (ret < 0) {
            ESP_LOGE(TAG, "Failed to acquire write to playback FIFO (0x%x)", ret);
            return ESP_FAIL;
        }
        int bytes_to_copy = (data_size < blk.buf_length) ? data_size : blk.buf_length;
        memcpy(blk.buf, data, bytes_to_copy);
        blk.valid_size = bytes_to_copy;

        ret = esp_gmf_db_release_write(audio_feeder.fifo, &blk, portMAX_DELAY);
        ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to release write to playback FIFO");
    }
    return ESP_OK;
}

esp_err_t audio_feeder_open(audio_feeder_config_t *config)
{
    ESP_LOGI(TAG, "Opening audio feeder...");
    if (config == NULL) {
        ESP_LOGE(TAG, "Invalid decoder configuration");
        return ESP_FAIL;
    }
    memcpy(&audio_feeder.config, config, sizeof(audio_feeder_config_t));
    esp_err_t err;
    if (audio_feeder.config.decoder_cfg.format == AV_PROCESSOR_FORMAT_ID_PCM) {
        err = esp_gmf_db_new_ringbuf(1, AUDIO_RINGBUFFER_SIZE, &audio_feeder.fifo);
        ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to create playback ringbuffer");
    } else {
        err = esp_gmf_db_new_fifo(AUDIO_FIFO_NUM, 1, &audio_feeder.fifo);
        ESP_GMF_RET_ON_NOT_OK(TAG, err, {return ESP_FAIL;}, "Failed to create playback FIFO");
    }
    const char *elements[] = {"aud_dec", "aud_ch_cvt", "aud_bit_cvt", "aud_rate_cvt"};
    av_audio_feeder_pool_init(&audio_feeder.pool, &audio_feeder.config.decoder_cfg);
    ESP_GMF_POOL_SHOW_ITEMS(audio_feeder.pool);
    err = esp_gmf_pool_new_pipeline(audio_feeder.pool, NULL, elements,
                                    sizeof(elements) / sizeof(char *), NULL, &audio_feeder.pipe);
    if (err != ESP_OK || !audio_feeder.pipe) {
        ESP_LOGE(TAG, "Failed to create feeder pipeline");
        goto cleanup_and_exit;
    }
    err = feeder_configure_all_decoders();
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {goto cleanup_and_exit;}, "Failed to configure decoders");

    err = feeder_setup_pipeline_ports();
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {goto cleanup_and_exit;}, "Failed to setup pipeline ports");

    esp_gmf_task_cfg_t cfg = DEFAULT_ESP_GMF_TASK_CONFIG();
    if (audio_feeder.config.feeder_task_config.task_stack > 0) {
        cfg.thread.stack = audio_feeder.config.feeder_task_config.task_stack;
        if (audio_feeder.config.decoder_cfg.format == AV_PROCESSOR_FORMAT_ID_OPUS && cfg.thread.stack < (4096 * 10)) {
            ESP_LOGW(TAG, "Feeder OPUS decoder requires larger stack size, using default 40k stack");
            cfg.thread.stack = AUDIO_OPUS_PIP_TASK_STACK_SIZE;
        }
    } else {
        cfg.thread.stack = AUDIO_OPUS_PIP_TASK_STACK_SIZE;
    }
    cfg.thread.prio = audio_feeder.config.feeder_task_config.task_prio;
    cfg.thread.core = audio_feeder.config.feeder_task_config.task_core;
    cfg.thread.stack_in_ext = audio_feeder.config.feeder_task_config.task_stack_in_ext;
    cfg.name = "audio_feeder_task";

    err = esp_gmf_task_init(&cfg, &audio_feeder.task);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {goto cleanup_and_exit;}, "Failed to create playback task");

    esp_gmf_pipeline_bind_task(audio_feeder.pipe, audio_feeder.task);
    esp_gmf_pipeline_loading_jobs(audio_feeder.pipe);

    audio_feeder.state = AUDIO_RUN_STATE_IDLE;
    ESP_LOGI(TAG, "Audio feeder opened successfully");
    return ESP_OK;

cleanup_and_exit:
    ESP_LOGE(TAG, "Failed to open audio feeder, cleaning up...");
    feeder_cleanup_on_error();
    return ESP_FAIL;
}

esp_err_t audio_feeder_close(void)
{
    if (audio_feeder.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGW(TAG, "Audio feeder is already closed");
        return ESP_OK;
    }
    ESP_LOGI(TAG, "Closing audio feeder...");
    if (audio_feeder.state == AUDIO_RUN_STATE_PLAYING) {
        audio_feeder_stop();
    }
    if (audio_feeder.pipe) {
        esp_gmf_pipeline_destroy(audio_feeder.pipe);
        audio_feeder.pipe = NULL;
    }
    if (audio_feeder.task) {
        esp_gmf_task_deinit(audio_feeder.task);
        audio_feeder.task = NULL;
    }
    if (audio_feeder.fifo) {
        esp_gmf_db_deinit(audio_feeder.fifo);
        audio_feeder.fifo = NULL;
    }
    if (audio_feeder.pool) {
        av_audio_feeder_pool_deinit(audio_feeder.pool);
        audio_feeder.pool = NULL;
    }
    audio_feeder.state = AUDIO_RUN_STATE_CLOSED;
    ESP_LOGI(TAG, "Audio playback closed successfully");
    return ESP_OK;
}

esp_err_t audio_feeder_run(void)
{
    if (audio_feeder.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot run playback - not opened");
        return ESP_FAIL;
    }
    if (audio_feeder.state == AUDIO_RUN_STATE_PLAYING) {
        ESP_LOGW(TAG, "Audio playback is already running");
        return ESP_OK;
    }
    esp_err_t ret = esp_gmf_pipeline_run(audio_feeder.pipe);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to start playback pipeline");

    audio_feeder.state = AUDIO_RUN_STATE_PLAYING;
    ESP_LOGI(TAG, "Audio playback started successfully");
    return ESP_OK;
}

esp_err_t audio_feeder_stop(void)
{
    if (audio_feeder.state == AUDIO_RUN_STATE_CLOSED) {
        ESP_LOGE(TAG, "Cannot stop feeder - not opened");
        return ESP_FAIL;
    }
    if (audio_feeder.state == AUDIO_RUN_STATE_IDLE) {
        ESP_LOGW(TAG, "Audio feeder is already stopped");
        return ESP_OK;
    }
    esp_gmf_db_done_write(audio_feeder.fifo);
    ESP_LOGI(TAG, "Stopping audio feeder...");
    esp_err_t ret = esp_gmf_pipeline_stop(audio_feeder.pipe);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ESP_FAIL;}, "Failed to stop feeder pipeline");

    audio_feeder.state = AUDIO_RUN_STATE_IDLE;
    ESP_LOGI(TAG, "Audio feeder stopped successfully");
    return ESP_OK;
}

esp_err_t audio_processor_mixer_open(void)
{
    ESP_LOGI(TAG, "Initializing audio render...");
    esp_audio_render_cfg_t cfg = {
        .max_stream_num = AUDIO_RENDER_STREAM_TYPE_MAX,
        .out_sample_info = {
            .sample_rate = audio_manager.config.board_sample_rate,
            .bits_per_sample = audio_manager.config.board_bits,
            .channel = audio_manager.config.board_channels,
        },
        .out_writer = audio_render_write_hdlr,
    };
    esp_err_t ret = esp_audio_render_create(&cfg, &audio_manager.render_handle);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, {return ret;}, "Failed to create audio render");

    esp_audio_render_stream_get(audio_manager.render_handle, ESP_AUDIO_RENDER_FIRST_STREAM, &audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER]);
    esp_audio_render_stream_get(audio_manager.render_handle, ESP_AUDIO_RENDER_SECOND_STREAM, &audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK]);

    esp_audio_render_mixer_gain_t feeder_mixer_gain = {0};
    feeder_mixer_gain.initial_gain = audio_feeder.config.feeder_mixer_gain.initial_gain;
    feeder_mixer_gain.target_gain = audio_feeder.config.feeder_mixer_gain.target_gain;
    feeder_mixer_gain.transition_time = audio_feeder.config.feeder_mixer_gain.transition_time;
    esp_audio_render_stream_set_mixer_gain(audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER], &feeder_mixer_gain);

    esp_audio_render_mixer_gain_t playback_mixer_gain = {0};
    playback_mixer_gain.initial_gain = audio_playback.config.playback_mixer_gain.initial_gain;
    playback_mixer_gain.target_gain = audio_playback.config.playback_mixer_gain.target_gain;
    playback_mixer_gain.transition_time = audio_playback.config.playback_mixer_gain.transition_time;
    esp_audio_render_stream_set_mixer_gain(audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK], &playback_mixer_gain);

    esp_audio_render_sample_info_t render_sample_info = {
        .sample_rate = audio_manager.config.board_sample_rate,
        .bits_per_sample = audio_manager.config.board_bits,
        .channel = audio_manager.config.board_channels,
    };
    esp_audio_render_set_out_sample_info(audio_manager.render_handle, &render_sample_info);
    esp_err_t err = esp_audio_render_stream_open(audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK], &render_sample_info);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return err;}, "Failed to open audio render stream");
    err = esp_audio_render_stream_open(audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER], &render_sample_info);
    ESP_GMF_RET_ON_NOT_OK(TAG, err, {return err;}, "Failed to open audio render stream");

    audio_manager.enable_mixer = true;

    return ESP_OK;
}

esp_err_t audio_processor_mixer_close(void)
{
    if (!audio_manager.enable_mixer) {
        ESP_LOGE(TAG, "Audio mixer not enabled");
        return ESP_FAIL;
    }
    if (audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK]) {
        esp_audio_render_stream_close(audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK]);
    }
    if (audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER]) {
        esp_audio_render_stream_close(audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER]);
    }
    esp_audio_render_destroy(audio_manager.render_handle);
    for (int i = 0; i < AUDIO_RENDER_STREAM_TYPE_MAX; i++) {
        esp_audio_render_stream_close(audio_manager.stream[i]);
        audio_manager.stream[i] = NULL;
    }
    audio_manager.render_handle = NULL;
    return ESP_OK;
}

esp_err_t audio_processor_ramp_control(audio_mixer_focus_mode_t mode)
{
    if (!audio_manager.enable_mixer || !audio_manager.render_handle) {
        ESP_LOGE(TAG, "Audio render not initialized or mixer not enabled, enable_mixer: %d, render_handle: %p", audio_manager.enable_mixer, audio_manager.render_handle);
        return ESP_ERR_INVALID_STATE;
    }
    if (!audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER] || !audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK]) {
        ESP_LOGE(TAG, "Audio render streams not available");
        return ESP_ERR_INVALID_STATE;
    }
    switch (mode) {
        case AUDIO_MIXER_FOCUS_FEEDER:
            esp_audio_render_stream_set_fade(audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER], true);
            esp_audio_render_stream_set_fade(audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK], false);
            break;
        case AUDIO_MIXER_FOCUS_PLAYBACK:
            esp_audio_render_stream_set_fade(audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK], true);
            esp_audio_render_stream_set_fade(audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER], false);
            break;
        case AUDIO_MIXER_FOCUS_BALANCED:
            esp_audio_render_stream_set_fade(audio_manager.stream[AUDIO_RENDER_STREAM_FEEDER], true);
            esp_audio_render_stream_set_fade(audio_manager.stream[AUDIO_RENDER_STREAM_PLAYBACK], true);
            break;
        default:
            ESP_LOGE(TAG, "Invalid focus mode: %d", mode);
            return ESP_ERR_INVALID_ARG;
    }
    return ESP_OK;
}
