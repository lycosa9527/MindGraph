#include "usb_msc.h"
#include "esp_log.h"
#include "tinyusb_msc.h"
#include "tinyusb_default_config.h"
#include "bsp/esp-bsp.h"
#include "bsp/esp32_s3_touch_amoled_2_06.h"
#include <cstring>

static const char* TAG = "USB_MSC";
static bool usb_msc_initialized = false;
static bool usb_msc_connected = false;
static tinyusb_msc_storage_handle_t msc_storage_handle = nullptr;

// USB device event callback
static void usb_device_event_handler(tinyusb_event_t* event, void* arg) {
    (void) arg;
    switch (event->id) {
        case TINYUSB_EVENT_ATTACHED:
            ESP_LOGI(TAG, "USB device attached");
            usb_msc_connected = true;
            break;
        case TINYUSB_EVENT_DETACHED:
            ESP_LOGI(TAG, "USB device detached");
            usb_msc_connected = false;
            break;
        default:
            break;
    }
}

bool usb_msc_init() {
    if (usb_msc_initialized) {
        return true;
    }
    
    ESP_LOGI(TAG, "Initializing USB Mass Storage...");
    
    // Get SD card handle from BSP
    sdmmc_card_t* sdcard = bsp_sdcard;
    if (sdcard == nullptr) {
        ESP_LOGW(TAG, "SD card not mounted, USB MSC will not be available");
        usb_msc_initialized = true;
        return false;
    }
    
    // Install TinyUSB driver with default config
    const tinyusb_config_t tusb_cfg = TINYUSB_DEFAULT_CONFIG(usb_device_event_handler);
    esp_err_t ret = tinyusb_driver_install(&tusb_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to install TinyUSB driver: %s", esp_err_to_name(ret));
        return false;
    }
    ESP_LOGI(TAG, "TinyUSB driver installed");
    
    // Install MSC driver
    tinyusb_msc_driver_config_t msc_driver_cfg = {};
    msc_driver_cfg.user_flags.val = 0;
    msc_driver_cfg.user_flags.auto_mount_off = 0;
    msc_driver_cfg.callback = nullptr;
    msc_driver_cfg.callback_arg = nullptr;
    ret = tinyusb_msc_install_driver(&msc_driver_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to install MSC driver: %s", esp_err_to_name(ret));
        return false;
    }
    ESP_LOGI(TAG, "MSC driver installed");
    
    // Configure MSC storage with SD card
    tinyusb_msc_storage_config_t storage_cfg = {};
    storage_cfg.medium.card = sdcard;
    storage_cfg.fat_fs.base_path = nullptr;  // Use default from Kconfig
    storage_cfg.fat_fs.config.format_if_mount_failed = false;
    storage_cfg.fat_fs.config.max_files = 5;
    storage_cfg.fat_fs.config.allocation_unit_size = 16 * 1024;
    storage_cfg.fat_fs.config.disk_status_check_enable = false;
    storage_cfg.fat_fs.config.use_one_fat = false;
    storage_cfg.fat_fs.do_not_format = true;  // Don't format if filesystem exists
    storage_cfg.fat_fs.format_flags = 0;  // Use default (FM_ANY)
    storage_cfg.mount_point = TINYUSB_MSC_STORAGE_MOUNT_APP;  // App owns it initially, can switch to USB later
    
    ret = tinyusb_msc_new_storage_sdmmc(&storage_cfg, &msc_storage_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create MSC storage: %s", esp_err_to_name(ret));
        return false;
    }
    ESP_LOGI(TAG, "MSC storage created");
    
    // Switch mount point to USB so it appears as USB drive
    ret = tinyusb_msc_set_storage_mount_point(msc_storage_handle, TINYUSB_MSC_STORAGE_MOUNT_USB);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to set mount point to USB: %s (will try on USB connect)", esp_err_to_name(ret));
    } else {
        ESP_LOGI(TAG, "SD card now exposed as USB Mass Storage");
        usb_msc_connected = true;
    }
    
    usb_msc_initialized = true;
    ESP_LOGI(TAG, "USB Mass Storage initialized");
    return true;
}

void usb_msc_deinit() {
    if (msc_storage_handle != nullptr) {
        tinyusb_msc_delete_storage(msc_storage_handle);
        msc_storage_handle = nullptr;
    }
    tinyusb_msc_uninstall_driver();
    usb_msc_initialized = false;
    usb_msc_connected = false;
}

bool usb_msc_is_connected() {
    return usb_msc_connected && usb_msc_initialized;
}

void usb_msc_switch_to_app() {
    if (msc_storage_handle != nullptr) {
        tinyusb_msc_set_storage_mount_point(msc_storage_handle, TINYUSB_MSC_STORAGE_MOUNT_APP);
        ESP_LOGI(TAG, "Switched storage access to application");
    }
}

void usb_msc_switch_to_usb() {
    if (msc_storage_handle != nullptr) {
        tinyusb_msc_set_storage_mount_point(msc_storage_handle, TINYUSB_MSC_STORAGE_MOUNT_USB);
        ESP_LOGI(TAG, "Switched storage access to USB host");
    }
}
