#include "button_handler.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

ButtonHandler::ButtonHandler() {
    _pwrCallback = nullptr;
    _bootCallback = nullptr;
    _pwrLastState = true;
    _bootLastState = true;
    _pwrLastPressTime = 0;
    _bootLastPressTime = 0;
}

void ButtonHandler::init() {
    gpio_config_t io_conf = {};
    io_conf.intr_type = GPIO_INTR_DISABLE;
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pin_bit_mask = (1ULL << BUTTON_PWR_PIN) | (1ULL << BUTTON_BOOT_PIN);
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.pull_up_en = GPIO_PULLUP_ENABLE;
    gpio_config(&io_conf);
}

void ButtonHandler::setPWRCallback(ButtonCallback callback) {
    _pwrCallback = callback;
}

void ButtonHandler::setBOOTCallback(ButtonCallback callback) {
    _bootCallback = callback;
}

bool ButtonHandler::isPWRPressed() {
    return gpio_get_level(BUTTON_PWR_PIN) == 0;
}

bool ButtonHandler::isBOOTPressed() {
    return gpio_get_level(BUTTON_BOOT_PIN) == 0;
}

void ButtonHandler::handleButtons() {
    bool pwrState = isPWRPressed();
    bool bootState = isBOOTPressed();
    
    int64_t currentTime = esp_timer_get_time() / 1000;
    
    if (pwrState != _pwrLastState && pwrState == true) {
        if (currentTime - _pwrLastPressTime > 200) {
            if (_pwrCallback) {
                _pwrCallback();
            }
            _pwrLastPressTime = currentTime;
        }
    }
    _pwrLastState = pwrState;
    
    if (bootState != _bootLastState && bootState == true) {
        if (currentTime - _bootLastPressTime > 200) {
            if (_bootCallback) {
                _bootCallback();
            }
            _bootLastPressTime = currentTime;
        }
    }
    _bootLastState = bootState;
}