#include "es7210_driver.h"
#include "i2c_bus_manager.h"
#include "driver/i2s_std.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "ES7210";
#define ES7210_PA_CTRL_GPIO GPIO_NUM_46

static bool es7210_initialized = false;
static i2s_chan_handle_t i2s_rx_handle = nullptr;
static uint32_t current_sample_rate = 16000;
static i2c_master_dev_handle_t es7210_dev_handle = nullptr;

static uint8_t es7210_read_reg(uint8_t reg) {
    if (es7210_dev_handle == nullptr) {
        return 0;
    }
    uint8_t data = 0;
    esp_err_t ret = i2c_master_transmit_receive(es7210_dev_handle, &reg, 1, &data, 1, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read register 0x%02X: %s", reg, esp_err_to_name(ret));
        return 0;
    }
    return data;
}

static bool es7210_write_reg(uint8_t reg, uint8_t value) {
    if (es7210_dev_handle == nullptr) {
        return false;
    }
    uint8_t write_buf[2] = {reg, value};
    esp_err_t ret = i2c_master_transmit(es7210_dev_handle, write_buf, 2, pdMS_TO_TICKS(100));
    return ret == ESP_OK;
}

bool es7210_init() {
    if (es7210_initialized) {
        return true;
    }
    
    es7210_dev_handle = create_i2c_device(ES7210_I2C_ADDR);
    if (es7210_dev_handle == nullptr) {
        ESP_LOGE(TAG, "Failed to create I2C device");
        return false;
    }
    
    vTaskDelay(pdMS_TO_TICKS(10));
    
    uint8_t chip_id = es7210_read_reg(0xFD);
    if (chip_id != 0x20) {
        ESP_LOGE(TAG, "Chip ID mismatch (got 0x%02X, expected 0x20)", chip_id);
        return false;
    }
    
    es7210_write_reg(0x00, 0xFF);
    vTaskDelay(pdMS_TO_TICKS(10));
    
    es7210_write_reg(0x00, 0x41);
    vTaskDelay(pdMS_TO_TICKS(10));
    
    es7210_write_reg(0x01, 0x00);
    es7210_write_reg(0x02, 0x00);
    es7210_write_reg(0x03, 0x00);
    es7210_write_reg(0x04, 0x00);
    es7210_write_reg(0x05, 0x00);
    
    es7210_write_reg(0x06, 0x00);
    
    es7210_write_reg(0x07, 0x20);
    
    es7210_write_reg(0x08, 0x00);
    
    es7210_write_reg(0x11, 0x00);
    es7210_write_reg(0x12, 0x00);
    
    es7210_write_reg(0x13, 0x00);
    es7210_write_reg(0x14, 0x00);
    es7210_write_reg(0x15, 0x00);
    
    es7210_write_reg(0x20, 0x00);
    es7210_write_reg(0x21, 0x00);
    es7210_write_reg(0x22, 0x00);
    es7210_write_reg(0x23, 0x00);
    
    es7210_write_reg(0x40, 0x0F);
    
    es7210_write_reg(0x41, 0x00);
    es7210_write_reg(0x42, 0x00);
    
    es7210_write_reg(0x43, 0x00);
    es7210_write_reg(0x44, 0x00);
    es7210_write_reg(0x45, 0x00);
    es7210_write_reg(0x46, 0x00);
    
    es7210_write_reg(0x47, 0x00);
    es7210_write_reg(0x48, 0x00);
    es7210_write_reg(0x49, 0x00);
    es7210_write_reg(0x4A, 0x00);
    
    es7210_write_reg(0x4B, 0x00);
    es7210_write_reg(0x4C, 0x00);
    
    gpio_set_direction(ES7210_PA_CTRL_GPIO, GPIO_MODE_OUTPUT);
    gpio_set_level(ES7210_PA_CTRL_GPIO, 1);
    
    vTaskDelay(pdMS_TO_TICKS(10));
    
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    esp_err_t ret = i2s_new_channel(&chan_cfg, nullptr, &i2s_rx_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create I2S channel: %s", esp_err_to_name(ret));
        return false;
    }
    
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(current_sample_rate),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = GPIO_NUM_40,
            .ws = GPIO_NUM_45,
            .dout = I2S_GPIO_UNUSED,
            .din = GPIO_NUM_42,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };
    
    ret = i2s_channel_init_std_mode(i2s_rx_handle, &std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize I2S channel: %s", esp_err_to_name(ret));
        i2s_del_channel(i2s_rx_handle);
        i2s_rx_handle = nullptr;
        return false;
    }
    
    es7210_initialized = true;
    ESP_LOGI(TAG, "Initialized");
    return true;
}

bool es7210_start() {
    if (!es7210_initialized) {
        if (!es7210_init()) {
            return false;
        }
    }
    
    es7210_write_reg(0x06, 0x00);
    vTaskDelay(pdMS_TO_TICKS(10));
    
    if (i2s_channel_enable(i2s_rx_handle) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable I2S channel");
        return false;
    }
    
    ESP_LOGI(TAG, "Started");
    return true;
}

bool es7210_stop() {
    if (!es7210_initialized) {
        return false;
    }
    
    i2s_channel_disable(i2s_rx_handle);
    es7210_write_reg(0x06, 0x0F);
    
    ESP_LOGI(TAG, "Stopped");
    return true;
}

bool es7210_read_pdm(int16_t* mic1_data, int16_t* mic2_data, size_t samples) {
    if (!es7210_initialized || mic1_data == nullptr || mic2_data == nullptr) {
        return false;
    }
    
    size_t bytes_read = 0;
    int16_t* buffer = (int16_t*)malloc(samples * 2 * sizeof(int16_t));
    if (buffer == nullptr) {
        return false;
    }
    
    if (i2s_channel_read(i2s_rx_handle, buffer, samples * 2 * sizeof(int16_t), &bytes_read, portMAX_DELAY) != ESP_OK) {
        free(buffer);
        return false;
    }
    
    size_t samples_read = bytes_read / sizeof(int16_t) / 2;
    
    for (size_t i = 0; i < samples_read && i < samples; i++) {
        mic1_data[i] = buffer[i * 2];
        mic2_data[i] = buffer[i * 2 + 1];
    }
    
    for (size_t i = samples_read; i < samples; i++) {
        mic1_data[i] = 0;
        mic2_data[i] = 0;
    }
    
    free(buffer);
    return true;
}

void es7210_set_sample_rate(uint32_t sample_rate) {
    if (!es7210_initialized) {
        return;
    }
    
    current_sample_rate = sample_rate;
    
    uint8_t mclk_div = 1;
    uint8_t sclk_div = 1;
    uint8_t lrck_div_h = 0;
    uint8_t lrck_div_l = 0;
    
    if (sample_rate == 8000) {
        mclk_div = 12;
        sclk_div = 2;
        lrck_div_h = 0x00;
        lrck_div_l = 0xC0;
    } else if (sample_rate == 16000) {
        mclk_div = 6;
        sclk_div = 2;
        lrck_div_h = 0x00;
        lrck_div_l = 0xC0;
    } else if (sample_rate == 44100) {
        mclk_div = 2;
        sclk_div = 1;
        lrck_div_h = 0x01;
        lrck_div_l = 0x78;
    } else if (sample_rate == 48000) {
        mclk_div = 2;
        sclk_div = 1;
        lrck_div_h = 0x01;
        lrck_div_l = 0x40;
    }
    
    es7210_write_reg(0x02, mclk_div);
    es7210_write_reg(0x03, sclk_div);
    es7210_write_reg(0x04, lrck_div_h);
    es7210_write_reg(0x05, lrck_div_l);
    
    i2s_std_clk_config_t clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(sample_rate);
    i2s_channel_reconfig_std_clock(i2s_rx_handle, &clk_cfg);
}

void es7210_set_gain(uint8_t channel, uint8_t gain) {
    if (!es7210_initialized || channel > 3) {
        return;
    }
    
    uint8_t reg = 0x43 + channel;
    uint8_t gain_value = (gain > 37) ? 37 : gain;
    es7210_write_reg(reg, gain_value);
}