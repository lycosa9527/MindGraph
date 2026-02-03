#include "AXP2101.h"
#include "i2c_bus_manager.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "AXP2101";

AXP2101::AXP2101() : _i2c_bus_handle(nullptr), _i2c_dev_handle(nullptr) {
}

AXP2101::~AXP2101() {
    if (_i2c_dev_handle) {
        i2c_master_bus_rm_device(_i2c_dev_handle);
    }
    _i2c_bus_handle = nullptr;
}

bool AXP2101::begin(uint8_t sda, uint8_t scl) {
    ESP_LOGI(TAG, "AXP2101::begin() called");
    _i2c_bus_handle = get_i2c_bus_handle();
    if (_i2c_bus_handle == nullptr) {
        ESP_LOGE(TAG, "Failed to get I2C bus handle");
        return false;
    }
    ESP_LOGI(TAG, "Got I2C bus handle: %p", _i2c_bus_handle);
    
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = AXP2101_I2C_ADDR,
        .scl_speed_hz = 100000,
        .scl_wait_us = 0,
        .flags = {},
    };
    
    ESP_LOGI(TAG, "Adding I2C device at address 0x%02X...", AXP2101_I2C_ADDR);
    esp_err_t     ret = i2c_master_bus_add_device(_i2c_bus_handle, &dev_cfg, &_i2c_dev_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add I2C device: %s", esp_err_to_name(ret));
        _i2c_bus_handle = nullptr;
        return false;
    }
    ESP_LOGI(TAG, "I2C device added successfully, handle: %p", _i2c_dev_handle);
    
    ESP_LOGI(TAG, "Reading chip ID from register 0x03...");
    uint8_t chipId = readRegister(0x03);
    ESP_LOGI(TAG, "Chip ID read: 0x%02X", chipId);
    if (chipId != 0x4A) {
        ESP_LOGE(TAG, "Chip ID mismatch: expected 0x4A, got 0x%02X", chipId);
        return false;
    }
    ESP_LOGI(TAG, "Chip ID verified successfully");
    
    // CRITICAL FIX: Factory library initImpl() does NOT write to register 0x10!
    // Writing to register 0x10 (COMMON_CONFIG) can trigger reset/shutdown bits
    // We should NOT modify register 0x10 during initialization - leave it as-is
    // The factory example only disables TSPinMeasure, which we do below
    
    ESP_LOGI(TAG, "Writing register 0x12 = 0x7D...");
    writeRegister(0x12, 0x7D);
    ESP_LOGI(TAG, "Register 0x12 written");
    
    ESP_LOGI(TAG, "Configuring power channels...");
    disableDC2();
    disableDC3();
    disableDC4();
    disableDC5();
    disableALDO1();
    disableALDO2();
    disableALDO3();
    disableALDO4();
    disableBLDO1();
    disableBLDO2();
    disableCPUSLDO();
    disableDLDO1();
    disableDLDO2();
    
    setDC1Voltage(3300);
    enableDC1();
    setALDO1Voltage(3300);
    enableALDO1();
    
    ESP_LOGI(TAG, "Configuring charging...");
    disableTSPinMeasure();
    setPrechargeCurr(0x00);
    setChargerConstantCurr(0x01);
    setChargerTerminationCurr(0x00);
    setChargeTargetVoltage(0x00);
    
    clearIrqStatus();
    
    ESP_LOGI(TAG, "AXP2101 initialized successfully");
    return true;
}

uint8_t AXP2101::readRegister(uint8_t reg) {
    if (_i2c_dev_handle == nullptr) {
        // Don't spam errors if handle is NULL - this is expected if init failed
        return 0;
    }
    
    uint8_t data = 0;
    ESP_LOGD(TAG, "Reading register 0x%02X...", reg);
    
    // Use 1000ms timeout to match factory example (pass milliseconds directly like factory example)
    esp_err_t ret = i2c_master_transmit_receive(_i2c_dev_handle, &reg, 1, &data, 1, 1000);
    if (ret != ESP_OK) {
        // CRITICAL FIX: Suppress repeated I2C errors to prevent log spam
        // Only log errors at DEBUG level - they're expected if I2C bus is in invalid state
        // The calling code should handle 0 return values gracefully
        ESP_LOGD(TAG, "Failed to read register 0x%02X: %s (I2C may be in invalid state)", reg, esp_err_to_name(ret));
        return 0;
    }
    ESP_LOGD(TAG, "Register 0x%02X = 0x%02X", reg, data);
    return data;
}

uint16_t AXP2101::readRegister16(uint8_t reg) {
    uint8_t data[2] = {0, 0};
    esp_err_t ret = i2c_master_transmit_receive(_i2c_dev_handle, &reg, 1, data, 2, 1000);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read register 16-bit 0x%02X: %s", reg, esp_err_to_name(ret));
        return 0;
    }
    return (uint16_t)((data[1] << 8) | data[0]);
}

void AXP2101::writeRegister(uint8_t reg, uint8_t value) {
    if (_i2c_dev_handle == nullptr) {
        ESP_LOGE(TAG, "I2C device handle is NULL for write!");
        return;
    }
    
    uint8_t write_buf[2] = {reg, value};
    ESP_LOGI(TAG, "I2C write: reg=0x%02X val=0x%02X", reg, value);
    
    // Use 1000ms timeout to match factory example (pass milliseconds directly like factory example)
    esp_err_t ret = i2c_master_transmit(_i2c_dev_handle, write_buf, 2, 1000);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C write FAILED! reg=0x%02X val=0x%02X error=%s", reg, value, esp_err_to_name(ret));
        // Don't continue if critical register write fails
        if (reg == 0x10) {
            ESP_LOGE(TAG, "CRITICAL: Register 0x10 write failed - this may cause system instability!");
        }
    } else {
        ESP_LOGI(TAG, "I2C write SUCCESS: reg=0x%02X val=0x%02X", reg, value);
    }
}

int AXP2101::getBatteryPercentage() {
    uint8_t percentage = readRegister(AXP2101_REG_BATTERY_PERCENTAGE);
    if (percentage > 100) {
        return 100;
    }
    return percentage;
}

bool AXP2101::isCharging() {
    uint8_t status = readRegister(AXP2101_REG_POWER_STATUS);
    return (status & 0x04) != 0;
}

float AXP2101::getBatteryVoltage() {
    uint16_t voltage = readRegister16(AXP2101_REG_BATTERY_VOLTAGE_L);
    return voltage / 1000.0F;
}

bool AXP2101::isBatteryConnected() {
    uint8_t status = readRegister(AXP2101_REG_POWER_STATUS);
    return (status & 0x20) != 0;
}

void AXP2101::setChargingCurrent(uint16_t current) {
    uint8_t reg = 0x33;
    uint8_t value = 0;
    
    if (current <= 100) {
        value = 0x00;
    } else if (current <= 190) {
        value = 0x01;
    } else if (current <= 280) {
        value = 0x02;
    } else if (current <= 360) {
        value = 0x03;
    } else if (current <= 450) {
        value = 0x04;
    } else if (current <= 550) {
        value = 0x05;
    } else if (current <= 630) {
        value = 0x06;
    } else {
        value = 0x07;
    }
    
    uint8_t current_reg = readRegister(reg);
    current_reg &= 0xF8;
    current_reg |= value;
    writeRegister(reg, current_reg);
}

void AXP2101::disableDC2() {
    uint8_t reg = readRegister(0x26);
    reg &= ~(1 << 0);
    writeRegister(0x26, reg);
}

void AXP2101::disableDC3() {
    uint8_t reg = readRegister(0x26);
    reg &= ~(1 << 1);
    writeRegister(0x26, reg);
}

void AXP2101::disableDC4() {
    uint8_t reg = readRegister(0x26);
    reg &= ~(1 << 2);
    writeRegister(0x26, reg);
}

void AXP2101::disableDC5() {
    uint8_t reg = readRegister(0x26);
    reg &= ~(1 << 3);
    writeRegister(0x26, reg);
}

void AXP2101::disableALDO1() {
    uint8_t reg = readRegister(0x27);
    reg &= ~(1 << 0);
    writeRegister(0x27, reg);
}

void AXP2101::disableALDO2() {
    uint8_t reg = readRegister(0x27);
    reg &= ~(1 << 1);
    writeRegister(0x27, reg);
}

void AXP2101::disableALDO3() {
    uint8_t reg = readRegister(0x27);
    reg &= ~(1 << 2);
    writeRegister(0x27, reg);
}

void AXP2101::disableALDO4() {
    uint8_t reg = readRegister(0x27);
    reg &= ~(1 << 3);
    writeRegister(0x27, reg);
}

void AXP2101::disableBLDO1() {
    uint8_t reg = readRegister(0x28);
    reg &= ~(1 << 0);
    writeRegister(0x28, reg);
}

void AXP2101::disableBLDO2() {
    uint8_t reg = readRegister(0x28);
    reg &= ~(1 << 1);
    writeRegister(0x28, reg);
}

void AXP2101::disableCPUSLDO() {
    uint8_t reg = readRegister(0x28);
    reg &= ~(1 << 2);
    writeRegister(0x28, reg);
}

void AXP2101::disableDLDO1() {
    uint8_t reg = readRegister(0x28);
    reg &= ~(1 << 3);
    writeRegister(0x28, reg);
}

void AXP2101::disableDLDO2() {
    uint8_t reg = readRegister(0x28);
    reg &= ~(1 << 4);
    writeRegister(0x28, reg);
}

void AXP2101::setDC1Voltage(uint16_t voltage_mv) {
    uint8_t reg = 0x23;
    uint8_t value = 0;
    if (voltage_mv >= 1500 && voltage_mv <= 3400) {
        value = ((voltage_mv - 1500) / 100) & 0x1F;
    }
    uint8_t current_reg = readRegister(reg);
    current_reg &= 0xE0;
    current_reg |= value;
    writeRegister(reg, current_reg);
}

void AXP2101::enableDC1() {
    uint8_t reg = readRegister(0x26);
    reg |= (1 << 0);
    writeRegister(0x26, reg);
}

void AXP2101::setALDO1Voltage(uint16_t voltage_mv) {
    uint8_t reg = 0x2B;
    uint8_t value = 0;
    if (voltage_mv >= 500 && voltage_mv <= 3500) {
        value = ((voltage_mv - 500) / 100) & 0x1F;
    }
    uint8_t current_reg = readRegister(reg);
    current_reg &= 0xE0;
    current_reg |= value;
    writeRegister(reg, current_reg);
}

void AXP2101::enableALDO1() {
    uint8_t reg = readRegister(0x27);
    reg |= (1 << 0);
    writeRegister(0x27, reg);
}

void AXP2101::disableTSPinMeasure() {
    uint8_t reg = 0x36;
    uint8_t value = readRegister(reg);
    value |= (1 << 3);
    writeRegister(reg, value);
}

void AXP2101::setPrechargeCurr(uint8_t current) {
    uint8_t reg = 0x33;
    uint8_t value = readRegister(reg);
    value &= 0xCF;
    value |= ((current & 0x03) << 4);
    writeRegister(reg, value);
}

void AXP2101::setChargerConstantCurr(uint8_t current) {
    uint8_t reg = 0x33;
    uint8_t value = readRegister(reg);
    value &= 0xF8;
    value |= (current & 0x07);
    writeRegister(reg, value);
}

void AXP2101::setChargerTerminationCurr(uint8_t current) {
    uint8_t reg = 0x34;
    uint8_t value = readRegister(reg);
    value &= 0xF0;
    value |= (current & 0x0F);
    writeRegister(reg, value);
}

void AXP2101::setChargeTargetVoltage(uint8_t voltage) {
    uint8_t reg = 0x34;
    uint8_t value = readRegister(reg);
    value &= 0xCF;
    value |= ((voltage & 0x03) << 4);
    writeRegister(reg, value);
}

void AXP2101::clearIrqStatus() {
    writeRegister(0x48, 0xFF);
    writeRegister(0x49, 0xFF);
}