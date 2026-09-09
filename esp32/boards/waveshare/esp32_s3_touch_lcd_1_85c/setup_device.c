/*
 * Waveshare ESP32-S3-Touch-LCD-1.85C V1 bring-up.
 * LCD RST = TCA9554 EXIO2, touch RST = TCA9554 EXIO1.
 */

#include <string.h>

#include "driver/i2c_master.h"
#include "dev_gpio_expander.h"
#include "esp_board_device.h"
#include "esp_check.h"
#include "esp_io_expander.h"
#include "esp_io_expander_tca9554.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_st77916.h"
#include "esp_lcd_touch.h"
#include "esp_lcd_touch_cst816s.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "st77916_vendor_init.h"

static const char *TAG = "SETUP_1_85C";

#define LCD_RST_GPIO (IO_EXPANDER_PIN_NUM_1)
#define TP_RST_GPIO  (IO_EXPANDER_PIN_NUM_0)

static esp_err_t expander_pulse(const char *pin_name, uint32_t pin, uint32_t low_ms, uint32_t high_ms)
{
    esp_io_expander_handle_t *io_expander = NULL;
    ESP_RETURN_ON_ERROR(
        esp_board_device_get_handle("gpio_expander", (void **)&io_expander),
        TAG,
        "gpio_expander handle"
    );
    ESP_LOGI(TAG, "Pulse %s (mask 0x%lx) low %lums then high", pin_name, (unsigned long)pin, (unsigned long)low_ms);
    ESP_RETURN_ON_ERROR(esp_io_expander_set_level(*io_expander, pin, 0), TAG, "expander low");
    vTaskDelay(pdMS_TO_TICKS(low_ms));
    ESP_RETURN_ON_ERROR(esp_io_expander_set_level(*io_expander, pin, 1), TAG, "expander high");
    vTaskDelay(pdMS_TO_TICKS(high_ms));
    return ESP_OK;
}

esp_err_t io_expander_factory_entry_t(
    i2c_master_bus_handle_t i2c_handle,
    const uint16_t dev_addr,
    esp_io_expander_handle_t *handle_ret)
{
    ESP_LOGI(TAG, "TCA9554 factory addr=0x%02x", dev_addr);
    ESP_RETURN_ON_ERROR(
        esp_io_expander_new_i2c_tca9554(i2c_handle, dev_addr, handle_ret), TAG, "TCA9554 create"
    );
    const uint32_t rst_pins = LCD_RST_GPIO | TP_RST_GPIO;
    ESP_RETURN_ON_ERROR(
        esp_io_expander_set_dir(*handle_ret, rst_pins, IO_EXPANDER_OUTPUT), TAG, "expander dir"
    );
    ESP_RETURN_ON_ERROR(esp_io_expander_set_level(*handle_ret, rst_pins, 1), TAG, "expander high");
    // CST816 is probed before lcd_touch_factory_entry_t; release reset now.
    ESP_RETURN_ON_ERROR(esp_io_expander_set_level(*handle_ret, TP_RST_GPIO, 0), TAG, "touch rst low");
    vTaskDelay(pdMS_TO_TICKS(10));
    ESP_RETURN_ON_ERROR(esp_io_expander_set_level(*handle_ret, TP_RST_GPIO, 1), TAG, "touch rst high");
    vTaskDelay(pdMS_TO_TICKS(50));
    ESP_LOGI(TAG, "TCA9554 ready, CST816 reset released");
    return ESP_OK;
}

esp_err_t lcd_panel_factory_entry_t(
    esp_lcd_panel_io_handle_t io,
    const esp_lcd_panel_dev_config_t *panel_dev_config,
    esp_lcd_panel_handle_t *ret_panel)
{
    size_t init_count = 0;
    const st77916_lcd_init_cmd_t *init_cmds = st77916_waveshare_1_85c_init_cmds(&init_count);
    static st77916_vendor_config_t vendor_config = {
        .flags = {
            .use_qspi_interface = 1,
        },
    };
    vendor_config.init_cmds = init_cmds;
    vendor_config.init_cmds_size = (uint16_t)init_count;

    ESP_LOGI(TAG, "LCD factory: %u vendor cmds, QSPI", (unsigned)init_count);
    ESP_RETURN_ON_ERROR(expander_pulse("LCD_RST/EXIO2", LCD_RST_GPIO, 10, 50), TAG, "LCD reset");

    esp_lcd_panel_dev_config_t panel_cfg = {0};
    memcpy(&panel_cfg, panel_dev_config, sizeof(panel_cfg));
    panel_cfg.vendor_config = &vendor_config;

    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_st77916(io, &panel_cfg, ret_panel), TAG, "st77916");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_reset(*ret_panel), TAG, "reset");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_init(*ret_panel), TAG, "init");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_disp_on_off(*ret_panel, true), TAG, "on");
    ESP_LOGI(TAG, "ST77916 panel ready");
    return ESP_OK;
}

esp_err_t lcd_touch_factory_entry_t(
    esp_lcd_panel_io_handle_t io,
    const esp_lcd_touch_config_t *touch_dev_config,
    esp_lcd_touch_handle_t *ret_touch)
{
    ESP_LOGI(TAG, "Touch factory: CST816S");
    ESP_RETURN_ON_ERROR(expander_pulse("TP_RST/EXIO1", TP_RST_GPIO, 10, 50), TAG, "touch reset");

    esp_lcd_touch_config_t touch_cfg = {0};
    memcpy(&touch_cfg, touch_dev_config, sizeof(touch_cfg));
    esp_err_t ret = esp_lcd_touch_new_i2c_cst816s(io, &touch_cfg, ret_touch);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "CST816S create failed: %s", esp_err_to_name(ret));
    }
    return ret;
}
