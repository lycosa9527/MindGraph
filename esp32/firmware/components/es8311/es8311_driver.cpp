#include "es8311_driver.h"
#include "i2c_bus_manager.h"
#include "driver/i2s_std.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "ES8311";
static bool es8311_initialized = false;
static i2s_chan_handle_t i2s_tx_handle = nullptr;
static uint32_t current_sample_rate = 16000;
static uint8_t current_volume = 50;
static i2c_master_dev_handle_t es8311_dev_handle = nullptr;

static uint8_t es8311_read_reg(uint8_t reg) {
    if (es8311_dev_handle == nullptr) {
        return 0;
    }
    uint8_t data = 0;
    esp_err_t ret = i2c_master_transmit_receive(es8311_dev_handle, &reg, 1, &data, 1, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read register 0x%02X: %s", reg, esp_err_to_name(ret));
        return 0;
    }
    return data;
}

static bool es8311_write_reg(uint8_t reg, uint8_t value) {
    if (es8311_dev_handle == nullptr) {
        return false;
    }
    uint8_t write_buf[2] = {reg, value};
    esp_err_t ret = i2c_master_transmit(es8311_dev_handle, write_buf, 2, pdMS_TO_TICKS(100));
    return ret == ESP_OK;
}

bool es8311_init() {
    if (es8311_initialized) {
        return true;
    }
    
    es8311_dev_handle = create_i2c_device(ES8311_I2C_ADDR);
    if (es8311_dev_handle == nullptr) {
        ESP_LOGE(TAG, "Failed to create I2C device");
        return false;
    }
    
    vTaskDelay(pdMS_TO_TICKS(10));
    
    uint8_t chip_id = es8311_read_reg(0xFD);
    if (chip_id != 0x31) {
        ESP_LOGE(TAG, "Chip ID mismatch (got 0x%02X, expected 0x31)", chip_id);
        return false;
    }
    
    es8311_write_reg(0x00, 0x80);
    vTaskDelay(pdMS_TO_TICKS(10));
    es8311_write_reg(0x00, 0x00);
    vTaskDelay(pdMS_TO_TICKS(10));
    
    es8311_write_reg(0x01, 0x00);
    es8311_write_reg(0x02, 0x00);
    es8311_write_reg(0x03, 0x00);
    es8311_write_reg(0x04, 0x00);
    es8311_write_reg(0x05, 0x00);
    es8311_write_reg(0x06, 0x00);
    es8311_write_reg(0x07, 0x00);
    es8311_write_reg(0x08, 0x00);
    
    es8311_write_reg(0x09, 0x00);
    es8311_write_reg(0x0A, 0x00);
    
    es8311_write_reg(0x0B, 0x00);
    es8311_write_reg(0x0C, 0x00);
    es8311_write_reg(0x0D, 0x00);
    es8311_write_reg(0x0E, 0x00);
    es8311_write_reg(0x0F, 0x00);
    es8311_write_reg(0x10, 0x00);
    es8311_write_reg(0x11, 0x00);
    es8311_write_reg(0x12, 0x00);
    es8311_write_reg(0x13, 0x00);
    es8311_write_reg(0x14, 0x00);
    
    es8311_write_reg(0x15, 0x00);
    es8311_write_reg(0x16, 0x00);
    es8311_write_reg(0x17, 0x00);
    es8311_write_reg(0x18, 0x00);
    es8311_write_reg(0x19, 0x00);
    es8311_write_reg(0x1A, 0x00);
    es8311_write_reg(0x1B, 0x00);
    es8311_write_reg(0x1C, 0x00);
    es8311_write_reg(0x1D, 0x00);
    es8311_write_reg(0x1E, 0x00);
    es8311_write_reg(0x1F, 0x00);
    
    es8311_write_reg(0x20, 0x00);
    es8311_write_reg(0x21, 0x00);
    es8311_write_reg(0x22, 0x00);
    es8311_write_reg(0x23, 0x00);
    es8311_write_reg(0x24, 0x00);
    es8311_write_reg(0x25, 0x00);
    es8311_write_reg(0x26, 0x00);
    es8311_write_reg(0x27, 0x00);
    es8311_write_reg(0x28, 0x00);
    es8311_write_reg(0x29, 0x00);
    es8311_write_reg(0x2A, 0x00);
    es8311_write_reg(0x2B, 0x00);
    es8311_write_reg(0x2C, 0x00);
    es8311_write_reg(0x2D, 0x00);
    es8311_write_reg(0x2E, 0x00);
    es8311_write_reg(0x2F, 0x00);
    
    vTaskDelay(pdMS_TO_TICKS(10));
    
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    esp_err_t ret = i2s_new_channel(&chan_cfg, &i2s_tx_handle, nullptr);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create I2S channel: %s", esp_err_to_name(ret));
        return false;
    }
    
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(current_sample_rate),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = GPIO_NUM_41,
            .ws = GPIO_NUM_45,
            .dout = GPIO_NUM_42,
            .din = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };
    
    ret = i2s_channel_init_std_mode(i2s_tx_handle, &std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize I2S channel: %s", esp_err_to_name(ret));
        i2s_del_channel(i2s_tx_handle);
        i2s_tx_handle = nullptr;
        return false;
    }
    
    es8311_initialized = true;
    ESP_LOGI(TAG, "Initialized");
    return true;
}

bool es8311_start() {
    if (!es8311_initialized) {
        if (!es8311_init()) {
            return false;
        }
    }
    
    es8311_write_reg(0x12, 0x03);
    vTaskDelay(pdMS_TO_TICKS(10));
    
    es8311_write_reg(0x0F, 0x50);
    es8311_write_reg(0x10, 0x00);
    es8311_write_reg(0x11, 0x00);
    
    es8311_write_reg(0x1F, 0x00);
    es8311_write_reg(0x1E, 0x00);
    
    es8311_set_volume(current_volume);
    
    if (i2s_channel_enable(i2s_tx_handle) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable I2S channel");
        return false;
    }
    
    ESP_LOGI(TAG, "Started");
    return true;
}

bool es8311_stop() {
    if (!es8311_initialized) {
        return false;
    }
    
    i2s_channel_disable(i2s_tx_handle);
    es8311_write_reg(0x12, 0x00);
    
    ESP_LOGI(TAG, "Stopped");
    return true;
}

bool es8311_write_audio(int16_t* pcm_data, size_t samples) {
    if (!es8311_initialized || pcm_data == nullptr) {
        return false;
    }
    
    size_t bytes_written = 0;
    size_t bytes_to_write = samples * sizeof(int16_t);
    
    if (i2s_channel_write(i2s_tx_handle, pcm_data, bytes_to_write, &bytes_written, portMAX_DELAY) != ESP_OK) {
        return false;
    }
    
    return bytes_written == bytes_to_write;
}

void es8311_set_volume(uint8_t volume) {
    if (!es8311_initialized) {
        return;
    }
    
    current_volume = (volume > 100) ? 100 : volume;
    
    uint8_t volume_reg = 0;
    if (current_volume == 0) {
        volume_reg = 0xFF;
    } else {
        volume_reg = 192 - (current_volume * 192 / 100);
    }
    
    es8311_write_reg(0x1F, volume_reg);
}

void es8311_set_sample_rate(uint32_t sample_rate) {
    if (!es8311_initialized) {
        return;
    }
    
    current_sample_rate = sample_rate;
    
    uint8_t mclk_div = 0;
    uint8_t bclk_div = 0;
    uint8_t lrck_div = 0;
    
    if (sample_rate == 8000) {
        mclk_div = 0x00;
        bclk_div = 0x04;
        lrck_div = 0x10;
    } else if (sample_rate == 16000) {
        mclk_div = 0x00;
        bclk_div = 0x04;
        lrck_div = 0x08;
    } else if (sample_rate == 44100) {
        mclk_div = 0x00;
        bclk_div = 0x02;
        lrck_div = 0x02;
    } else if (sample_rate == 48000) {
        mclk_div = 0x00;
        bclk_div = 0x02;
        lrck_div = 0x02;
    }
    
    es8311_write_reg(0x01, mclk_div);
    es8311_write_reg(0x02, bclk_div);
    es8311_write_reg(0x03, lrck_div);
    
    i2s_std_clk_config_t clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(sample_rate);
    i2s_channel_reconfig_std_clock(i2s_tx_handle, &clk_cfg);
}