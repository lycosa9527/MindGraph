#include "i2c_bus_manager.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "I2C_BUS";
static i2c_master_bus_handle_t s_i2c_bus_handle = nullptr;

i2c_master_bus_handle_t get_i2c_bus_handle() {
    if (s_i2c_bus_handle == nullptr) {
        i2c_master_bus_config_t i2c_bus_config = {
            .i2c_port = I2C_NUM_0,
            .sda_io_num = GPIO_NUM_15,
            .scl_io_num = GPIO_NUM_14,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = {
                .enable_internal_pullup = true,
                .allow_pd = false,
            },
        };
        
        esp_err_t ret = i2c_new_master_bus(&i2c_bus_config, &s_i2c_bus_handle);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Failed to create I2C bus: %s", esp_err_to_name(ret));
            return nullptr;
        }
        ESP_LOGI(TAG, "I2C bus initialized");
    }
    return s_i2c_bus_handle;
}

i2c_master_dev_handle_t create_i2c_device(uint8_t addr) {
    i2c_master_bus_handle_t bus = get_i2c_bus_handle();
    if (bus == nullptr) {
        return nullptr;
    }
    
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = addr,
        .scl_speed_hz = 100000,
        .scl_wait_us = 0,
        .flags = {},
    };
    
    i2c_master_dev_handle_t dev_handle = nullptr;
    esp_err_t ret = i2c_master_bus_add_device(bus, &dev_cfg, &dev_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add I2C device 0x%02X: %s", addr, esp_err_to_name(ret));
        return nullptr;
    }
    return dev_handle;
}
