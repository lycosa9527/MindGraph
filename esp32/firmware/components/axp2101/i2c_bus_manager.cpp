#include "i2c_bus_manager.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
#include "driver/gpio.h"

static const char* TAG = "I2C_BUS_MANAGER";
static i2c_master_bus_handle_t g_i2c_bus_handle = nullptr;

i2c_master_bus_handle_t get_i2c_bus_handle(void) {
    if (g_i2c_bus_handle == nullptr) {
        i2c_master_bus_config_t i2c_mst_cfg = {
            .i2c_port = I2C_NUM_0,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .flags = {
                .enable_internal_pullup = true,
            },
        };
        
        esp_err_t ret = i2c_new_master_bus(&i2c_mst_cfg, &g_i2c_bus_handle);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Failed to create I2C master bus: %s", esp_err_to_name(ret));
            return nullptr;
        }
        ESP_LOGI(TAG, "I2C master bus created successfully");
    }
    return g_i2c_bus_handle;
}

i2c_master_dev_handle_t create_i2c_device(uint8_t device_addr) {
    i2c_master_bus_handle_t bus_handle = get_i2c_bus_handle();
    if (bus_handle == nullptr) {
        ESP_LOGE(TAG, "Failed to get I2C bus handle");
        return nullptr;
    }
    
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = device_addr,
        .scl_speed_hz = 100000,
        .scl_wait_us = 0,
        .flags = {},
    };
    
    i2c_master_dev_handle_t dev_handle = nullptr;
    esp_err_t ret = i2c_master_bus_add_device(bus_handle, &dev_cfg, &dev_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add I2C device at address 0x%02X: %s", device_addr, esp_err_to_name(ret));
        return nullptr;
    }
    
    ESP_LOGI(TAG, "I2C device created at address 0x%02X", device_addr);
    return dev_handle;
}
