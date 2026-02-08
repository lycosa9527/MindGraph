#include "QMI8658.h"
#include "i2c_bus_manager.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "QMI8658";

QMI8658::QMI8658() : _i2c_dev_handle(nullptr) {
}

bool QMI8658::begin(uint8_t sda, uint8_t scl) {
    _i2c_dev_handle = create_i2c_device(QMI8658_I2C_ADDR);
    if (_i2c_dev_handle == nullptr) {
        ESP_LOGE(TAG, "Failed to create I2C device");
        return false;
    }
    
    vTaskDelay(pdMS_TO_TICKS(10));
    
    uint8_t whoAmI = readRegister(QMI8658_REG_WHO_AM_I);
    if (whoAmI != 0x05) {
        ESP_LOGE(TAG, "Chip ID mismatch: expected 0x05, got 0x%02X", whoAmI);
        return false;
    }
    
    writeRegister(QMI8658_REG_CTRL1, 0x60);
    vTaskDelay(pdMS_TO_TICKS(10));
    
    return true;
}

uint8_t QMI8658::readRegister(uint8_t reg) {
    if (_i2c_dev_handle == nullptr) {
        return 0;
    }
    uint8_t data = 0;
    esp_err_t ret = i2c_master_transmit_receive(_i2c_dev_handle, &reg, 1, &data, 1, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read register 0x%02X: %s", reg, esp_err_to_name(ret));
        return 0;
    }
    return data;
}

int16_t QMI8658::readRegister16(uint8_t reg) {
    if (_i2c_dev_handle == nullptr) {
        return 0;
    }
    uint8_t data[2] = {0, 0};
    esp_err_t ret = i2c_master_transmit_receive(_i2c_dev_handle, &reg, 1, data, 2, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read register 16-bit 0x%02X: %s", reg, esp_err_to_name(ret));
        return 0;
    }
    return (int16_t)((data[1] << 8) | data[0]);
}

void QMI8658::writeRegister(uint8_t reg, uint8_t value) {
    if (_i2c_dev_handle == nullptr) {
        return;
    }
    uint8_t write_buf[2] = {reg, value};
    esp_err_t ret = i2c_master_transmit(_i2c_dev_handle, write_buf, 2, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to write register 0x%02X: %s", reg, esp_err_to_name(ret));
    }
}

void QMI8658::readAccelerometer(float* accel) {
    int16_t x = readRegister16(QMI8658_REG_ACC_X_L);
    int16_t y = readRegister16(QMI8658_REG_ACC_X_L + 2);
    int16_t z = readRegister16(QMI8658_REG_ACC_X_L + 4);
    
    accel[0] = x / 16384.0f;
    accel[1] = y / 16384.0f;
    accel[2] = z / 16384.0f;
}

void QMI8658::readGyroscope(float* gyro) {
    int16_t x = readRegister16(QMI8658_REG_GYRO_X_L);
    int16_t y = readRegister16(QMI8658_REG_GYRO_X_L + 2);
    int16_t z = readRegister16(QMI8658_REG_GYRO_X_L + 4);
    
    gyro[0] = x / 131.0f;
    gyro[1] = y / 131.0f;
    gyro[2] = z / 131.0f;
}

void QMI8658::readMotion(float* accel, float* gyro) {
    readAccelerometer(accel);
    readGyroscope(gyro);
}

bool QMI8658::isDataReady() {
    uint8_t status = readRegister(0x14);
    return (status & 0x01) != 0;
}