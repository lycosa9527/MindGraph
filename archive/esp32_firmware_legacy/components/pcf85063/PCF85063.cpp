#include "PCF85063.h"
#include "i2c_bus_manager.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "PCF85063";

PCF85063::PCF85063() : _i2c_dev_handle(nullptr) {
}

bool PCF85063::begin(uint8_t sda, uint8_t scl) {
    _i2c_dev_handle = create_i2c_device(PCF85063_I2C_ADDR);
    if (_i2c_dev_handle == nullptr) {
        ESP_LOGE(TAG, "Failed to create I2C device");
        return false;
    }
    
    vTaskDelay(pdMS_TO_TICKS(50));
    
    for (int retry = 0; retry < 3; retry++) {
        uint8_t test_reg = readRegister(PCF85063_REG_CONTROL_1);
        if (test_reg != 0xFF) {
            writeRegister(PCF85063_REG_CONTROL_1, 0x00);
            vTaskDelay(pdMS_TO_TICKS(10));
            ESP_LOGI(TAG, "PCF85063 initialized successfully");
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
    
    ESP_LOGW(TAG, "PCF85063 initialization failed after retries");
    return false;
}

uint8_t PCF85063::readRegister(uint8_t reg) {
    if (_i2c_dev_handle == nullptr) {
        return 0xFF;
    }
    uint8_t data = 0xFF;
    esp_err_t ret = i2c_master_transmit_receive(_i2c_dev_handle, &reg, 1, &data, 1, pdMS_TO_TICKS(200));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read register 0x%02X: %s", reg, esp_err_to_name(ret));
        return 0xFF;
    }
    return data;
}

void PCF85063::writeRegister(uint8_t reg, uint8_t value) {
    if (_i2c_dev_handle == nullptr) {
        return;
    }
    uint8_t write_buf[2] = {reg, value};
    esp_err_t ret = i2c_master_transmit(_i2c_dev_handle, write_buf, 2, pdMS_TO_TICKS(200));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to write register 0x%02X: %s", reg, esp_err_to_name(ret));
    }
}

uint8_t PCF85063::bcdToDec(uint8_t bcd) {
    return ((bcd / 16) * 10) + (bcd % 16);
}

uint8_t PCF85063::decToBcd(uint8_t dec) {
    return ((dec / 10) * 16) + (dec % 10);
}

void PCF85063::setTime(uint8_t hour, uint8_t minute, uint8_t second) {
    writeRegister(PCF85063_REG_SECONDS, decToBcd(second));
    writeRegister(PCF85063_REG_SECONDS + 1, decToBcd(minute));
    writeRegister(PCF85063_REG_SECONDS + 2, decToBcd(hour));
}

void PCF85063::setDate(uint8_t day, uint8_t month, uint16_t year) {
    writeRegister(PCF85063_REG_SECONDS + 3, decToBcd(day));
    writeRegister(PCF85063_REG_SECONDS + 4, decToBcd(month));
    writeRegister(PCF85063_REG_SECONDS + 5, decToBcd(year % 100));
}

void PCF85063::setDateTime(uint8_t year, uint8_t month, uint8_t day, uint8_t hour, uint8_t minute, uint8_t second) {
    setTime(hour, minute, second);
    setDate(day, month, year);
}

void PCF85063::getTime(uint8_t* hour, uint8_t* minute, uint8_t* second) {
    *second = bcdToDec(readRegister(PCF85063_REG_SECONDS) & 0x7F);
    *minute = bcdToDec(readRegister(PCF85063_REG_SECONDS + 1) & 0x7F);
    *hour = bcdToDec(readRegister(PCF85063_REG_SECONDS + 2) & 0x3F);
}

void PCF85063::getDate(uint8_t* day, uint8_t* month, uint16_t* year) {
    *day = bcdToDec(readRegister(PCF85063_REG_SECONDS + 3) & 0x3F);
    *month = bcdToDec(readRegister(PCF85063_REG_SECONDS + 4) & 0x1F);
    *year = 2000 + bcdToDec(readRegister(PCF85063_REG_SECONDS + 5));
}

bool PCF85063::isValid() {
    uint8_t seconds = readRegister(PCF85063_REG_SECONDS);
    return (seconds & 0x80) == 0;
}