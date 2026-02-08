#include "i2c_bus_manager.h"
#include "bsp/esp32_s3_touch_amoled_2_06.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "I2C_BUS";
static i2c_master_bus_handle_t s_i2c_bus_handle = nullptr;

i2c_master_bus_handle_t get_i2c_bus_handle() {
    if (s_i2c_bus_handle == nullptr) {
        // FIXED: Use BSP's I2C bus instead of creating our own
        // BSP already initializes I2C on GPIO 14/15 during display initialization
        // Using BSP's bus avoids GPIO conflicts and follows BSP design pattern
        // According to Waveshare ESP32-S3-Touch-AMOLED-2.06 hardware spec:
        // - GPIO 15 (SDA) and GPIO 14 (SCL) are the standard I2C pins for ALL I2C devices
        // - GPIO 12 is LCD_CS (Chip Select) - must NOT be used for I2C
        // - GPIO 13 is LCD_TE (Tearing Effect) - must NOT be used for I2C
        ESP_LOGI(TAG, "Getting I2C bus handle from BSP...");
        s_i2c_bus_handle = bsp_i2c_get_handle();
        if (s_i2c_bus_handle == nullptr) {
            ESP_LOGE(TAG, "Failed to get BSP I2C bus handle");
            return nullptr;
        }
        ESP_LOGI(TAG, "I2C bus handle obtained from BSP: %p", s_i2c_bus_handle);
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

void scan_i2c_devices() {
    const char* TAG = "I2C_SCAN";
    i2c_master_bus_handle_t bus = get_i2c_bus_handle();
    if (bus == nullptr) {
        ESP_LOGE(TAG, "I2C bus not initialized, cannot scan");
        return;
    }
    
    ESP_LOGI(TAG, "Scanning I2C bus for devices...");
    int found_count = 0;
    
    for (uint8_t address = 1; address < 127; address++) {
        i2c_device_config_t dev_cfg = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address = address,
            .scl_speed_hz = 100000,
            .scl_wait_us = 0,
            .flags = {},
        };
        
        i2c_master_dev_handle_t dev_handle = nullptr;
        esp_err_t ret = i2c_master_bus_add_device(bus, &dev_cfg, &dev_handle);
        
        if (ret == ESP_OK && dev_handle != nullptr) {
            // Try to read 1 byte from the device to detect if it exists
            // Use a dummy register read (register 0x00) - most I2C devices support this
            uint8_t dummy_reg = 0x00;
            uint8_t dummy_data = 0;
            ret = i2c_master_transmit_receive(dev_handle, &dummy_reg, 1, &dummy_data, 1, pdMS_TO_TICKS(50));
            
            // ESP_OK means device responded, ESP_ERR_TIMEOUT might also indicate device exists
            // ESP_ERR_NOT_FOUND or ESP_ERR_INVALID_STATE means no device
            if (ret == ESP_OK) {
                ESP_LOGI(TAG, "Found device at address: 0x%02X", address);
                found_count++;
            }
            
            i2c_master_bus_rm_device(dev_handle);
        }
    }
    
    ESP_LOGI(TAG, "I2C scan complete. Found %d device(s)", found_count);
}
