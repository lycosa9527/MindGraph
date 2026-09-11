#include "kitty_ptt_button.hpp"

#include <cstdint>

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"

namespace {

constexpr const char *TAG = "kitty_boot";
constexpr gpio_num_t k_boot_gpio = GPIO_NUM_0;
constexpr int64_t k_press_us = 20000;
constexpr int64_t k_release_us = 80000;

bool g_ready = false;
bool g_latched = false;
int64_t g_changed_us = 0;

int64_t now_us()
{
    return esp_timer_get_time();
}

} // namespace

bool kitty_ptt_button_init()
{
    gpio_config_t cfg = {};
    cfg.pin_bit_mask = 1ULL << static_cast<uint32_t>(k_boot_gpio);
    cfg.mode = GPIO_MODE_INPUT;
    cfg.pull_up_en = GPIO_PULLUP_ENABLE;
    cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    cfg.intr_type = GPIO_INTR_DISABLE;
    const esp_err_t err = gpio_config(&cfg);
    g_ready = err == ESP_OK;
    g_latched = false;
    g_changed_us = now_us();
    if (!g_ready) {
        ESP_LOGW(TAG, "BOOT GPIO0 init failed: %s", esp_err_to_name(err));
        return false;
    }
    ESP_LOGI(TAG, "BOOT GPIO0 mapped as mic hold");
    return true;
}

bool kitty_ptt_button_held()
{
    if (!g_ready) {
        return false;
    }
    const bool raw = gpio_get_level(k_boot_gpio) == 0;
    const int64_t now = now_us();
    if (raw == g_latched) {
        g_changed_us = now;
        return g_latched;
    }
    const int64_t need = raw ? k_press_us : k_release_us;
    if (now - g_changed_us < need) {
        return g_latched;
    }
    g_latched = raw;
    g_changed_us = now;
    return g_latched;
}
