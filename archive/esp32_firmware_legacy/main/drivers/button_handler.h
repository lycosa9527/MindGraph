#ifndef BUTTON_HANDLER_H
#define BUTTON_HANDLER_H

#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdint.h>
#include <stdbool.h>

#define BUTTON_PWR_PIN GPIO_NUM_10
#define BUTTON_BOOT_PIN GPIO_NUM_0

typedef void (*ButtonCallback)();

class ButtonHandler {
public:
    ButtonHandler();
    void init();
    void setPWRCallback(ButtonCallback callback);
    void setBOOTCallback(ButtonCallback callback);
    void handleButtons();
    bool isPWRPressed();
    bool isBOOTPressed();

private:
    ButtonCallback _pwrCallback;
    ButtonCallback _bootCallback;
    bool _pwrLastState;
    bool _bootLastState;
    int64_t _pwrLastPressTime;
    int64_t _bootLastPressTime;
};

#endif