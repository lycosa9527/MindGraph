#include "motion_sensor.h"
#include "esp_timer.h"
#include "esp_log.h"

static const char* TAG = "MOTION";

MotionSensor::MotionSensor() {
    _lastCheckTime = 0;
    _handRaiseDetected = false;
    _initialized = false;
    for (int i = 0; i < 3; i++) {
        _lastAccel[i] = 0.0f;
    }
}

bool MotionSensor::init() {
    if (_initialized) {
        return true;
    }
    
    bool result = _imu.begin();
    if (result) {
        _initialized = true;
        ESP_LOGI(TAG, "Motion sensor initialized successfully");
    } else {
        ESP_LOGW(TAG, "Motion sensor initialization failed");
    }
    return result;
}

bool MotionSensor::detectHandRaise() {
    if (!_initialized) {
        return false;
    }
    
    if (!isDataReady()) {
        return false;
    }
    
    float accel[3];
    _imu.readAccelerometer(accel);
    
    int64_t currentTime = esp_timer_get_time() / 1000;
    if (currentTime - _lastCheckTime < 100) {
        return _handRaiseDetected;
    }
    _lastCheckTime = currentTime;
    
    float deltaZ = accel[2] - _lastAccel[2];
    
    if (accel[2] > 1.5f && deltaZ > 0.5f) {
        _handRaiseDetected = true;
        for (int i = 0; i < 3; i++) {
            _lastAccel[i] = accel[i];
        }
        return true;
    }
    
    if (accel[2] < 0.5f) {
        _handRaiseDetected = false;
    }
    
    for (int i = 0; i < 3; i++) {
        _lastAccel[i] = accel[i];
    }
    
    return false;
}

void MotionSensor::getMotion(float* accel, float* gyro) {
    if (!_initialized) {
        if (accel) {
            accel[0] = accel[1] = accel[2] = 0.0f;
        }
        if (gyro) {
            gyro[0] = gyro[1] = gyro[2] = 0.0f;
        }
        return;
    }
    _imu.readMotion(accel, gyro);
}

bool MotionSensor::isDataReady() {
    if (!_initialized) {
        return false;
    }
    return _imu.isDataReady();
}