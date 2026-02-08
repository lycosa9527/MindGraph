/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_capture_defaults.h"
#include "esp_video_dec_mjpeg.h"
#include "driver/i2c_master.h"
#if CONFIG_IDF_TARGET_ESP32P4
#include "esp_video_init.h"
#endif  /* CONFIG_IDF_TARGET_ESP32P4 */

#include "esp_log.h"
#include "sdkconfig.h"
#include "video_processor.h"
#include "esp_board_manager_adapter.h"

#define CAMERA_PIN_PWDN      -1
#define CAMERA_PIN_RESET     -1
#define CAMERA_PIN_D0        13
#define CAMERA_PIN_D1        47
#define CAMERA_PIN_D2        14
#define CAMERA_PIN_D3        3
#define CAMERA_PIN_D4        12
#define CAMERA_PIN_D5        42
#define CAMERA_PIN_D6        41
#define CAMERA_PIN_D7        39
#define CAMERA_PIN_VSYNC     21
#define CAMERA_PIN_HREF      38
#define CAMERA_PIN_PCLK      11
#define CAMERA_PIN_XCLK      40
#define CAMERA_PIN_XCLK_FREQ 20000000

#if CONFIG_IDF_TARGET_ESP32P4
#define LCD_WIDTH  1024
#define LCD_HEIGHT 600
#else
#define LCD_WIDTH  320
#define LCD_HEIGHT 240
#endif  /* CONFIG_IDF_TARGET_ESP32P4 */

#define STREAM_MODE true

static const char *TAG = "video_preview";

static esp_lcd_panel_handle_t panel_handle   = NULL;
static video_render_handle_t  render_handle  = NULL;
static video_capture_handle_t capture_handle = NULL;

static void video_render_decode_callback(void *ctx, const uint8_t *data, size_t size)
{
    esp_lcd_panel_draw_bitmap(panel_handle, 0, 0, LCD_WIDTH, LCD_HEIGHT, data);
}

static void video_capture_encode_callback(void *ctx, int index, esp_capture_stream_frame_t *vid_frame)
{
    ESP_LOGI(TAG, "video_capture_encode_callback: index: %d, size: %zu", index, vid_frame->size);
    video_frame_t frame = {
        .data = vid_frame->data,
        .size = vid_frame->size,
    };
    video_render_feed_frame(render_handle, &frame);
}

static esp_err_t video_passthru_init(void)
{
    esp_board_manager_adapter_info_t bsp_info = {0};
    esp_board_manager_adapter_config_t bsp_config = ESP_BOARD_MANAGER_ADAPTER_CONFIG_DEFAULT();
    bsp_config.enable_lcd = true;
    esp_board_manager_adapter_init(&bsp_config, &bsp_info);
    panel_handle = bsp_info.lcd_panel;

    video_render_config_t render_cfg = {
        .decode_cb = video_render_decode_callback,
        .resolution = {
            .width = LCD_WIDTH,
            .height = LCD_HEIGHT,
        },
        .decode_cfg = {
            .codec_type = ESP_VIDEO_CODEC_TYPE_MJPEG, .out_fmt = ESP_VIDEO_CODEC_PIXEL_FMT_RGB565_LE, .codec_cc = ESP_VIDEO_DEC_SW_MJPEG_TAG,
        },
    };

    render_handle = video_render_open(&render_cfg);
    if (!render_handle) {
        ESP_LOGE(TAG, "Failed to open video render");
        return ESP_FAIL;
    }
    video_render_start(render_handle);

    video_capture_config_t capture_cfg = {
        .capture_frame_cb = video_capture_encode_callback,
        .capture_frame_cb_ctx = NULL,
        .sink_num = 1,
        .sink_cfg = {
            [0] = {
                .video_info = {
                    .format_id = ESP_CAPTURE_FMT_ID_MJPEG,
                    .width = LCD_WIDTH,
                    .height = LCD_HEIGHT,
                    .fps = 10,
                },
            }},
        .stream_mode = STREAM_MODE,
    };

#if CONFIG_IDF_TARGET_ESP32P4
    i2c_master_bus_handle_t i2c_master_handle;
    esp_err_t ret = i2c_master_get_bus_handle(0, &i2c_master_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to get I2C bus handle");
        return ESP_FAIL;
    }
    const esp_video_init_csi_config_t base_csi_config = {
        .sccb_config = {
            .init_sccb = false,
            .i2c_handle = i2c_master_handle,
            .freq = 400000,
        },
        .reset_pin = -1,
        .pwdn_pin = -1,
    };
    capture_cfg.camera_config = (void *)&base_csi_config;
#else
    esp_capture_video_dvp_src_cfg_t dvp_config = {0};
    dvp_config.buf_count = 2;
    dvp_config.reset_pin = CAMERA_PIN_RESET;
    dvp_config.pwr_pin = CAMERA_PIN_PWDN;
    dvp_config.data[0] = CAMERA_PIN_D0;
    dvp_config.data[1] = CAMERA_PIN_D1;
    dvp_config.data[2] = CAMERA_PIN_D2;
    dvp_config.data[3] = CAMERA_PIN_D3;
    dvp_config.data[4] = CAMERA_PIN_D4;
    dvp_config.data[5] = CAMERA_PIN_D5;
    dvp_config.data[6] = CAMERA_PIN_D6;
    dvp_config.data[7] = CAMERA_PIN_D7;
    dvp_config.vsync_pin = CAMERA_PIN_VSYNC;
    dvp_config.href_pin = CAMERA_PIN_HREF;
    dvp_config.pclk_pin = CAMERA_PIN_PCLK;
    dvp_config.xclk_pin = CAMERA_PIN_XCLK;
    dvp_config.xclk_freq = CAMERA_PIN_XCLK_FREQ;
    capture_cfg.camera_config = &dvp_config;
#endif  /* CONFIG_IDF_TARGET_ESP32P4 */

    capture_handle = video_capture_open(&capture_cfg);
    if (!capture_handle) {
        ESP_LOGE("main", "Failed to open video capture");
        return ESP_FAIL;
    }
    video_capture_start(capture_handle);

    if (STREAM_MODE == false) {
        while (1) {
            static int frame_count = 0;
            esp_capture_stream_frame_t frame = {0};
            frame.stream_type = ESP_CAPTURE_STREAM_TYPE_VIDEO;
            video_capture_fetch_frame_acquire(capture_handle, 0, &frame);
            video_frame_t frame_data = {
                .data = frame.data,
                .size = frame.size,
            };
            ESP_LOGI(TAG, "video_passthru_init: frame_data: %p, size: %zu", frame_data.data, frame_data.size);
            video_render_feed_frame(render_handle, &frame_data);
            video_capture_fetch_frame_release(capture_handle, 0, &frame);
            frame_count++;
            ESP_LOGI(TAG, "video_passthru_init: frame_count: %d", frame_count);
            vTaskDelay(pdMS_TO_TICKS(5000));
        }
    }
    return ESP_OK;
}

int app_main(void)
{
    ESP_LOGI(TAG, "Starting video passthru");
    esp_err_t ret = video_passthru_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize video passthru");
        return 1;
    }
    ESP_LOGI(TAG, "Video passthru initialized successfully");
    return 0;
}
