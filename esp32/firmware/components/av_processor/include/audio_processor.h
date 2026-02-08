/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif  /* __cplusplus */

#include "esp_err.h"
#include "esp_gmf_afe_manager.h"
#include "esp_audio_simple_player_advance.h"
#include "av_processor_type.h"

/* Brief:  Default audio manager configuration
 *  Note: When use OPUS decoder or OPUS encoder, the recorder_task_config and feeder_task_config
 *  task stack size need be set to more than 4096 * 10 bytes.
 */
#define DEFAULT_AUDIO_MANAGER_CONFIG() {  \
    .play_dev          = NULL,            \
    .rec_dev           = NULL,            \
    .mic_layout        = {0},             \
    .board_sample_rate = 16000,           \
    .board_bits        = 32,              \
    .board_channels    = 2,               \
}

#define DEFAULT_AUDIO_FEEDER_CONFIG() {  \
    .feeder_task_config = {              \
        .task_stack        = 0,          \
        .task_prio         = 0,          \
        .task_core         = 0,          \
        .task_stack_in_ext = true        \
    },                                   \
    .feeder_mixer_gain = {               \
        .initial_gain = 0.9,             \
        .target_gain = 1.0,              \
        .transition_time = 1500          \
    },                                   \
}

#define DEFAULT_AUDIO_PLAYBACK_CONFIG() {  \
    .event_cb              = NULL,         \
    .event_cb_ctx          = NULL,         \
    .playback_task_config = {              \
        .task_stack        = 4096,         \
        .task_prio         = 5,            \
        .task_core         = 0,            \
        .task_stack_in_ext = true,         \
    },                                     \
    .playback_mixer_gain = {               \
        .initial_gain = 0.6,               \
        .target_gain = 1.0,                \
        .transition_time = 1500            \
    }                                      \
}

#define DEFAULT_AUDIO_PROMPT_CONFIG() {  \
    .prompt_task_config = {              \
        .task_stack = 4096,              \
        .task_prio = 5,                  \
        .task_core = 0,                  \
        .task_stack_in_ext = true        \
    }                                    \
}

#define DEFAULT_AUDIO_RECORDER_CONFIG() {  \
    .afe_feed_task_config = {              \
        .task_stack        = 40 * 1024,    \
        .task_prio         = 5,            \
        .task_core         = 0,            \
        .task_stack_in_ext = true,         \
    },                                     \
    .afe_fetch_task_config = {             \
        .task_stack = 6 * 1024,            \
        .task_prio = 5,                    \
        .task_core = 1,                    \
        .task_stack_in_ext = true          \
    },                                     \
    .recorder_task_config  = {             \
        .task_stack = 4096,                \
        .task_prio = 10,                   \
        .task_core = 0,                    \
        .task_stack_in_ext = true          \
    },                                     \
    .recorder_event_cb     = NULL,         \
    .recorder_ctx          = NULL,         \
    .input_cb              = NULL,         \
    .input_ctx             = NULL,         \
}

/**
 * @brief  Default AFE configuration macro
 */
#define DEFAULT_AV_PROCESSOR_AFE_CONFIG() {  \
    .model              = "model",           \
    .ai_mode_wakeup     = false,             \
    .vad_enable         = true,              \
    .vad_mode           = 4,                 \
    .vad_min_speech_ms  = 64,                \
    .vad_min_noise_ms   = 1000,              \
    .agc_enable         = true,              \
    .afe_type           = AFE_TYPE_SR,       \
    .enable_vcmd_detect = false,             \
    .vcmd_timeout_ms    = 5000,              \
    .mn_language        = "cn",              \
    .wakeup_end_time_ms = 2000,              \
    .wakeup_time_ms     = 10000              \
}

/**
 * @brief  Audio focus control mode - determines which audio stream gets priority
 */
 typedef enum {
    AUDIO_MIXER_FOCUS_FEEDER   = 0,  /*!< Focus on FEEDER stream - boost feeder, reduce playback */
    AUDIO_MIXER_FOCUS_PLAYBACK = 1,  /*!< Focus on PLAYBACK stream - boost playback, reduce feeder */
    AUDIO_MIXER_FOCUS_BALANCED = 2,  /*!< Balanced mode - both streams at equal levels */
} audio_mixer_focus_mode_t;

/**
 * @brief  Audio player state enumeration
 */
typedef enum {
    AUDIO_PLAYER_STATE_IDLE,      /*!< Player is idle */
    AUDIO_PLAYER_STATE_PLAYING,   /*!< Player is playing */
    AUDIO_PLAYER_STATE_FINISHED,  /*!< Player has finished playing */
    AUDIO_PLAYER_STATE_STOPPED,   /*!< Player has stopped */
    AUDIO_PLAYER_STATE_PAUSED,    /*!< Player is paused */
    AUDIO_PLAYER_STATE_ERROR,     /*!< Player has encountered an error */
} audio_player_state_t;

/**
 * @brief  Type definition for the audio recorder event callback function
 *
 * @param[in]  event  Pointer to the event data, which can contain information about the recorder's state
 * @param[in]  ctx    User-defined context pointer, passed when registering the callback
 */
typedef void (*recorder_event_callback_t)(void *event, void *ctx);

/**
 * @brief  Type definition for the audio recorder input data callback function
 * @note   This callback is used to get the audio data from the input.
 *
 * @param[in]  data       Pointer to the audio data to be read
 * @param[in]  data_size  Size of the audio data to be read
 * @param[in]  ctx        User-defined context pointer
 */
typedef void (*recorder_input_callback_t)(uint8_t *data, int data_size, void *ctx);

/**
 * @brief  Type definition for the audio playback event callback function
 *
 * @param[in]  state  Playback state
 * @param[in]  ctx    User-defined context pointer
 */
typedef void (*playback_event_callback_t)(audio_player_state_t state, void *ctx);

/**
 * @brief  AFE (Audio Front-End) configuration structure
 *
 *         This structure contains all AFE-related configuration parameters that were previously
 *         configured via Kconfig. These parameters control the behavior of the audio front-end
 *         processing including wake word detection, VAD, AGC, and other audio processing features.
 */
 typedef struct {
    const char  *model;               /*!< Model path/name for SR model initialization */
    bool         ai_mode_wakeup;      /*!< AI mode: true for WAKEUP mode, false for DIRECT mode */
    bool         vad_enable;          /*!< Enable Voice Activity Detection (VAD) */
    int          vad_mode;            /*!< VAD mode value (1-4), larger values are more sensitive to human voice */
    int          vad_min_speech_ms;   /*!< Minimum speech duration in milliseconds */
    int          vad_min_noise_ms;    /*!< Minimum noise duration in milliseconds */
    bool         agc_enable;          /*!< Enable Automatic Gain Control (AGC) */
    afe_type_t   afe_type;            /*!< AFE type: AFE_TYPE_SR (0) or AFE_TYPE_VC (1) */
    bool         enable_vcmd_detect;  /*!< Enable Voice Command Detection */
    int          vcmd_timeout_ms;     /*!< Voice command detection timeout in milliseconds */
    const char  *mn_language;         /*!< Model language (e.g., "cn", "en") */
    int          wakeup_end_time_ms;  /*!< Wakeup end time in milliseconds */
    int          wakeup_time_ms;      /*!< Wakeup time in milliseconds */
} av_processor_afe_config_t;

/* Brief:  Audio mixer gain configuration */
typedef struct {
    float  initial_gain;     /*!< Initial gain value */
    float  target_gain;      /*!< Target gain value */
    int    transition_time;  /*!< Transition time in milliseconds */
} audio_mixer_gain_config_t;

/* Brief:  Common task configuration */
typedef struct {
    int   task_stack;         /*!< Task stack size (0 means use default) */
    int   task_prio;          /*!< Task priority */
    int   task_core;          /*!< Task core ID */
    bool  task_stack_in_ext;  /*!< Whether to allocate task stack in external memory */
} audio_task_config_t;

typedef struct {
    audio_task_config_t            feeder_task_config;  /*!< Feeder task configuration */
    av_processor_decoder_config_t  decoder_cfg;         /*!< Decoder configuration */
    audio_mixer_gain_config_t      feeder_mixer_gain;   /*!< Feeder mixer gain configuration */
} audio_feeder_config_t;

typedef struct {
    playback_event_callback_t  event_cb;              /*!< Playback event callback. The second parameter is always NULL*/
    void                      *event_cb_ctx;          /*!< Playback event context */
    audio_task_config_t        playback_task_config;  /*!< Playback task configuration */
    audio_mixer_gain_config_t  playback_mixer_gain;   /*!< Playback mixer gain configuration */
} audio_playback_config_t;

typedef struct {
    audio_task_config_t        prompt_task_config;  /*!< Prompt task configuration */
} audio_prompt_config_t;

typedef struct {
    audio_task_config_t            afe_feed_task_config;   /*!< AFE feed task configuration */
    av_processor_afe_config_t      afe_config;             /*!< AFE configuration */
    audio_task_config_t            afe_fetch_task_config;  /*!< AFE fetch task configuration */
    audio_task_config_t            recorder_task_config;   /*!< Recorder task configuration */
    av_processor_encoder_config_t  encoder_cfg;            /*!< Encoder configuration */
    recorder_event_callback_t      recorder_event_cb;      /*!< Recorder event callback */
    void                          *recorder_ctx;           /*!< Recorder context */
    recorder_input_callback_t      input_cb;               /*!< Recorder input data callback */
    void                          *input_ctx;              /*!< Recorder input data context */
} audio_recorder_config_t;

/* Brief:  Audio manager configuration */
typedef struct {
    void  *play_dev;
    void  *rec_dev;
    char   mic_layout[8];
    int    board_sample_rate;
    int    board_bits;
    int    board_channels;
} audio_manager_config_t;

/**
 * @brief  Initializes the audio manager module.
 *
 * @param[in]  config  Pointer to the audio manager configuration structure
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_manager_init(audio_manager_config_t *config);

/**
 * @brief  Deinitializes the audio manager component
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_manager_deinit();

/**
 * @brief  Opens the audio recorder and registers an event callback
 *
 * @param[in]  config  Pointer to the audio recorder configuration structure.
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_recorder_open(audio_recorder_config_t *config);

/**
 * @brief  Get the AFE manager handle of the audio recorder
 * @note   This function is used to get the AFE manager handle of the audio recorder.
 *         When you get the AFE manager handle, you can use the AFE manager API to configure the AFE.
 *         For example:
 *         ```c
 *         esp_gmf_afe_manager_handle_t afe_manager_handle;
 *         audio_recorder_get_afe_manager_handle(&afe_manager_handle);
 *         esp_gmf_afe_manager_suspend(afe_manager_handle, true);
 *         ```
 *
 * @param[out]  afe_manager_handle  Pointer to the AFE manager handle
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_recorder_get_afe_manager_handle(esp_gmf_afe_manager_handle_t *afe_manager_handle);

/* @brief  Get the AFE element handle of the audio recorder
 * @note   This function is used to get the AFE element handle of the audio recorder.
 *         When you get the AFE element handle, you can call all APIs in esp_gmf_afe.h to configure the AFE.
 *         For example:
 *         ```c
 *         esp_gmf_element_handle_t afe_element_handle;
 *         audio_recorder_get_afe_element_handle(&afe_element_handle);
 *         esp_gmf_afe_trigger_wakeup(afe_element_handle);
 *         ```
 *
 * @param[out]  afe_element_handle  Pointer to the AFE element handle
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
 esp_err_t audio_recorder_get_afe_element_handle(esp_gmf_element_handle_t *afe_element_handle);

/**
 * @brief  Closes the audio recorder
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_recorder_close(void);

/**
 * @brief  Reads audio data from the recorder.
 *
 * @param[out]  data       Pointer to the buffer where the audio data will be stored
 * @param[in]   data_size  Size of the buffer to store the audio data.
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_recorder_read_data(uint8_t *data, int data_size);

/**
 * @brief  Opens the audio feeder system
 *
 * @param[in]  config  Pointer to the audio feeder configuration structure.
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_feeder_open(audio_feeder_config_t *config);

/**
 * @brief  Closes the audio feeder module
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_feeder_close(void);

/**
 * @brief  Starts the audio feeder operation.
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_feeder_run(void);

/**
 * @brief  Stops the ongoing audio feeder
 *
 * @return
 *       - ESP_OK  On successfully stopping the audio playback
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_feeder_stop(void);

/**
 * @brief  Feeds audio data into the feeder system
 *
 * @param[in]  data       Pointer to the audio data to be fed into the feeder system
 * @param[in]  data_size  Size of the audio data to be fed into the feeder system
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_feeder_feed_data(uint8_t *data, int data_size);

/**
 * @brief  Open the audio playback module
 *
 * @param[in]  config  Pointer to the audio playback configuration structure.
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_playback_open(audio_playback_config_t *config);

/**
 * @brief  Close the audio playback module
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_playback_close(void);

/**
 * @brief  Play an audio playback from the specified URL. Eg: "http://192.168.1.100:8000/audio.mp3", "file:///sdcard/audio.mp3"
 *
 * @param[in]  url  URL pointing to the audio playback file to be played
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_playback_play(const char *url);

/**
 * @brief  Wait for the audio playback to end. This function will block until the audio playback is ended.
 *
 * @param[in]  url  URL pointing to the audio playback file to be played
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_playback_play_to_end(const char *url);

/**
 * @brief  Pauses the audio playback module
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_playback_pause(void);
/**
 * @brief  Resumes the audio playback module
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_playback_resume(void);

/**
 * @brief  Stop the currently playing audio playback module
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_playback_stop(void);

/**
 * @brief  Open the audio prompt module
 * @note  This function not provide pause and resume functionality, because the prompt is played to end automatically.
 *        This function's priority is higher than the audio playback and feeder, so when the prompt is playing, the audio playback
 *        and feeder decoded data will be ignored.
 *
 * @param[in]  config  Pointer to the audio prompt configuration structure.
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_prompt_open(audio_prompt_config_t *config);

/**
 * @brief  Close the audio prompt module
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_prompt_close(void);

/**
 * @brief  Play an audio prompt from the specified URL.
 *
 * @param[in]  url  URL pointing to the audio prompt file to be played
 * @note  Audio prompt is not supported mixer, so when play prompt, the audio playback and feeder decoded data will be ignored.
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t av_processor_audio_prompt_play(const char *url);

/**
 * @brief  Open the audio mixer module
 *
 * @note  This function must be called after audio_playback_open and audio_feeder_open and the audio_mixer must be enabled
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_processor_mixer_open(void);

/**
 * @brief  Close the audio mixer module
 *
 * @return
 *       - ESP_OK  On success
 *       - Other   Appropriate esp_err_t error code on failure
 */
esp_err_t audio_processor_mixer_close(void);

/**
 * @brief  Control audio focus between FEEDER and PLAYBACK streams
 *
 * @note  This function controls the fade processors for both feeder and playback streams
 *        to create smooth volume transitions and focus on the desired audio source.
 *        This only works when the audio mixer is enabled.
 *
 * @param[in]  mode  The focus control mode:
 *                   - AUDIO_FOCUS_FEEDER: Focus on FEEDER stream (boost feeder, reduce playback)
 *                   - AUDIO_FOCUS_PLAYBACK: Focus on PLAYBACK stream (boost playback, reduce feeder)
 *                   - AUDIO_FOCUS_BALANCED: Balanced mode (both streams at equal levels)
 *
 * @return
 *       - ESP_OK                 On success
 *       - ESP_ERR_INVALID_ARG    Invalid mode parameter
 *       - ESP_ERR_INVALID_STATE  Audio render not initialized or streams not available
 *       - ESP_FAIL               Failed to control fade processors
 */
esp_err_t audio_processor_ramp_control(audio_mixer_focus_mode_t mode);

#ifdef __cplusplus
}
#endif  /* __cplusplus */
