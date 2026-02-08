/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif  /* __cplusplus */

#include <stdint.h>
#include <stdbool.h>
#include "esp_afe_config.h"

/**
 * @brief  AV Processor FourCC definition
 */
#define AV_PROCESSOR_FOURCC(a, b, c, d) ((uint32_t)(a) | ((uint32_t)(b) << 8) | ((uint32_t)(c) << 16) | ((uint32_t)(d) << 24))

/**
 * @brief  Format string for printing FourCC value as characters and hex
 */
#define AV_PROCESSOR_FOURCC_FMT "%c%c%c%c (0x%08x)"

/**
 * @brief  Arguments for printing FourCC value
 *
 * @param fourcc  FourCC value to print
 *
 * @note  Use with AV_PROCESSOR_FOURCC_FMT in printf-style functions:
 *        ESP_LOGE(TAG, "Format: " AV_PROCESSOR_FOURCC_FMT, AV_PROCESSOR_FOURCC_ARGS(format));
 */
#define AV_PROCESSOR_FOURCC_ARGS(fourcc)  \
    (char)((fourcc) & 0xFF),              \
    (char)(((fourcc) >> 8) & 0xFF),       \
    (char)(((fourcc) >> 16) & 0xFF),      \
    (char)(((fourcc) >> 24) & 0xFF),      \
    (fourcc)

/**
 * @brief  AV Processor format ID definition
 *
 * @note  Aligned with GMF FourCC definition for audio video codecs and formats
 *        Detailed info refer to `https://github.com/espressif/esp-gmf/blob/main/gmf_core/helpers/include/esp_fourcc.h`
 */
typedef enum {
    AV_PROCESSOR_FORMAT_ID_PCM   = AV_PROCESSOR_FOURCC('P', 'C', 'M', ' '),  /*!< PCM (Uncompressed) encoder */
    AV_PROCESSOR_FORMAT_ID_G711A = AV_PROCESSOR_FOURCC('A', 'L', 'A', 'U'),  /*!< G.711 A-law encoder */
    AV_PROCESSOR_FORMAT_ID_G711U = AV_PROCESSOR_FOURCC('U', 'L', 'A', 'W'),  /*!< G.711 μ-law encoder */
    AV_PROCESSOR_FORMAT_ID_OPUS  = AV_PROCESSOR_FOURCC('O', 'P', 'U', 'S'),  /*!< OPUS encoder */
    AV_PROCESSOR_FORMAT_ID_AAC   = AV_PROCESSOR_FOURCC('A', 'A', 'C', ' '),  /*!< AAC encoder */
    AV_PROCESSOR_FORMAT_ID_MP3   = AV_PROCESSOR_FOURCC('M', 'P', '3', ' '),  /*!< MP3 encoder */
} av_processor_format_id_t;

typedef struct {
    uint32_t  sample_rate;     /*!< Sample rate in Hz (e.g., 8000, 16000, 24000, 32000, 44100, 48000) */
    uint8_t   sample_bits;     /*!< Sample bits in bits (e.g., 8, 16, 24, 32) */
    uint8_t   channels;        /*!< Number of audio channels (1-4) */
    uint8_t   frame_duration;  /*!< Frame duration in milliseconds */
} av_processor_audio_info_t;

/**
 * @brief  PCM encoder/decoder configuration
 */
typedef struct {
    av_processor_audio_info_t  audio_info;
} av_processor_pcm_config_t;

/**
 * @brief  OPUS encoder configuration
 */
typedef struct {
    av_processor_audio_info_t  audio_info;  /*!< Audio information */
    bool                       enable_vbr;  /*!< Enable Variable Bit Rate (VBR) */
    int                        bitrate;     /*!< Bitrate in bps */
} av_processor_opus_encoder_config_t;

/**
 * @brief  OPUS decoder configuration
 */
typedef struct {
    av_processor_audio_info_t  audio_info;
} av_processor_opus_decoder_config_t;

/**
 * @brief  AAC decoder configuration
 */
typedef struct {
    av_processor_audio_info_t  audio_info;
    bool                       no_adts_header;   /*!< Set if AAC frame data not contain ADTS header */
    bool                       aac_plus_enable;  /*!< Set if need AAC-Plus support */
} av_processor_aac_decoder_config_t;

/**
 * @brief  G.711 encoder/decoder configuration
 */
typedef struct {
    av_processor_audio_info_t  audio_info;
} av_processor_g711_config_t;

typedef struct {
    av_processor_audio_info_t  audio_info;
    int                        bitrate;     /*!< Bitrate in bps */
    bool                       adts_used;   /*!< Whether write ADTS header: true - add ADTS header, false - raw aac data only */
} av_processor_aac_encoder_config_t;

/**
 * @brief  Audio encoder configuration structure
 *
 *         This structure contains the encoder format type and corresponding format-specific parameters.
 *         Only the parameters for the selected format (indicated by format) should be used.
 */
typedef struct {
    av_processor_format_id_t  format;  /*!< Encoder format ID */
    union {
        av_processor_pcm_config_t           pcm;   /*!< PCM encoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_PCM) */
        av_processor_opus_encoder_config_t  opus;  /*!< OPUS encoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_OPUS) */
        av_processor_g711_config_t          g711;  /*!< G.711 encoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_G711A or AV_PROCESSOR_FORMAT_ID_G711U) */
        av_processor_aac_encoder_config_t   aac;   /*!< AAC encoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_AAC) */
    } params;                                      /*!< Format-specific encoder parameters */
} av_processor_encoder_config_t;

/**
 * @brief  Audio decoder configuration structure
 *
 *         This structure contains the decoder format type and corresponding format-specific parameters.
 *         Only the parameters for the selected format (indicated by format) should be used.
 */
typedef struct {
    av_processor_format_id_t  format;  /*!< Decoder format ID */
    union {
        av_processor_pcm_config_t           pcm;   /*!< PCM decoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_PCM) */
        av_processor_opus_decoder_config_t  opus;  /*!< OPUS decoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_OPUS) */
        av_processor_g711_config_t          g711;  /*!< G.711 decoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_G711A or AV_PROCESSOR_FORMAT_ID_G711U) */
        av_processor_aac_decoder_config_t   aac;   /*!< AAC decoder configuration (used when format == AV_PROCESSOR_FORMAT_ID_AAC) */
    } params;                                      /*!< Format-specific decoder parameters */
} av_processor_decoder_config_t;

#ifdef __cplusplus
}
#endif  /* __cplusplus */
