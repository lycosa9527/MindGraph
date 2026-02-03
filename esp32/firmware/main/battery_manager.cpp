#include "battery_manager.h"
#include "esp_timer.h"
#include "esp_log.h"

static const char* TAG = "BATTERY";

BatteryManager::BatteryManager() {
    _batteryLevel = 0;
    _isCharging = false;
    _lastUpdateTime = 0;
    _initialized = false;
}

bool BatteryManager::init() {
    ESP_LOGI("BATTERY", "BatteryManager::init() called");
    ESP_LOGI("BATTERY", "Calling _pmic.begin()...");
    bool result = _pmic.begin();
    ESP_LOGI("BATTERY", "_pmic.begin() returned: %s", result ? "true" : "false");
    if (!result) {
        ESP_LOGE("BATTERY", "PMIC initialization failed!");
        _initialized = false;
    } else {
        ESP_LOGI("BATTERY", "PMIC initialized successfully");
        _initialized = true;
    }
    return result;
}

int BatteryManager::getBatteryLevel() {
    return _batteryLevel;
}

bool BatteryManager::isCharging() {
    return _isCharging;
}

float BatteryManager::getBatteryVoltage() {
    return _pmic.getBatteryVoltage();
}

bool BatteryManager::isBatteryConnected() {
    return _pmic.isBatteryConnected();
}

void BatteryManager::update() {
    // Only update if initialization was successful
    if (!_initialized) {
        return;
    }
    
    // CRITICAL FIX: Reduce update frequency to prevent I2C bus overload
    // Update every 5 seconds instead of 1 second to reduce I2C traffic
    int64_t currentTime = esp_timer_get_time() / 1000;
    if (currentTime - _lastUpdateTime < 5000) {
        return;
    }
    _lastUpdateTime = currentTime;
    
    // NOTE: If I2C is in invalid state, readRegister() will return 0
    // and log a warning. This is acceptable - we'll retry on next update cycle.
    // The warnings are already suppressed to LOGW level in AXP2101::readRegister()
    _batteryLevel = _pmic.getBatteryPercentage();
    _isCharging = _pmic.isCharging();
}