#include "rtc_manager.h"
#include "esp_log.h"

static const char* TAG = "RTC";

RTCManager::RTCManager() {
    _initialized = false;
}

bool RTCManager::init() {
    if (_initialized) {
        return true;
    }
    
    bool result = _rtc.begin();
    if (result) {
        _initialized = true;
        ESP_LOGI(TAG, "RTC initialized successfully");
    } else {
        ESP_LOGW(TAG, "RTC initialization failed");
    }
    return result;
}

void RTCManager::setTime(uint8_t hour, uint8_t minute, uint8_t second) {
    if (!_initialized) {
        ESP_LOGW(TAG, "RTC not initialized, cannot set time");
        return;
    }
    _rtc.setTime(hour, minute, second);
}

void RTCManager::setDate(uint8_t day, uint8_t month, uint16_t year) {
    if (!_initialized) {
        ESP_LOGW(TAG, "RTC not initialized, cannot set date");
        return;
    }
    _rtc.setDate(day, month, year);
}

void RTCManager::getTime(uint8_t* hour, uint8_t* minute, uint8_t* second) {
    if (!_initialized || hour == nullptr || minute == nullptr || second == nullptr) {
        if (hour) *hour = 0;
        if (minute) *minute = 0;
        if (second) *second = 0;
        return;
    }
    _rtc.getTime(hour, minute, second);
}

void RTCManager::getDate(uint8_t* day, uint8_t* month, uint16_t* year) {
    if (!_initialized || day == nullptr || month == nullptr || year == nullptr) {
        if (day) *day = 1;
        if (month) *month = 1;
        if (year) *year = 2026;
        return;
    }
    _rtc.getDate(day, month, year);
}

void RTCManager::setDateTime(uint8_t year, uint8_t month, uint8_t day, uint8_t hour, uint8_t minute, uint8_t second) {
    if (!_initialized) {
        ESP_LOGW(TAG, "RTC not initialized, cannot set date/time");
        return;
    }
    _rtc.setDateTime(year, month, day, hour, minute, second);
}

std::string RTCManager::getTimeString() {
    uint8_t hour, minute, second;
    getTime(&hour, &minute, &second);
    char buffer[16];
    snprintf(buffer, sizeof(buffer), "%02d:%02d:%02d", (int)hour, (int)minute, (int)second);
    return std::string(buffer);
}

std::string RTCManager::getDateString() {
    uint8_t day, month;
    uint16_t year;
    getDate(&day, &month, &year);
    char buffer[16];
    snprintf(buffer, sizeof(buffer), "%04d-%02d-%02d", (int)year, (int)month, (int)day);
    return std::string(buffer);
}

bool RTCManager::isValid() {
    if (!_initialized) {
        return false;
    }
    return _rtc.isValid();
}