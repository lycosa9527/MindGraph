#include "sd_storage.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "driver/sdspi_host.h"
#include "driver/spi_common.h"
#include "sdmmc_cmd.h"
#include "bsp/esp-bsp.h"
#include "bsp/esp32_s3_touch_amoled_2_06.h"
#include <cstring>
#include <cstdio>

static const char* TAG = "SD_STORAGE";
// Use BSP mount point
#define MOUNT_POINT BSP_SD_MOUNT_POINT

SDStorage::SDStorage() {
    _initialized = false;
}

bool SDStorage::init() {
    if (_initialized) {
        return true;
    }
    
    ESP_LOGI(TAG, "Initializing SD card...");
    
    // Use BSP's SD card mount function
    esp_err_t ret = bsp_sdcard_mount();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to mount SD card: %s", esp_err_to_name(ret));
        _initialized = false;
        return false;
    }
    
    ESP_LOGI(TAG, "SD card mounted successfully at %s", MOUNT_POINT);
    _initialized = true;
    return true;
}

bool SDStorage::saveAudio(const char* filename, uint8_t* data, size_t len) {
    if (!_initialized) {
        return false;
    }
    
    char filepath[128];
    snprintf(filepath, sizeof(filepath), "%s/%s", MOUNT_POINT, filename);
    
    FILE* file = fopen(filepath, "wb");
    if (file == nullptr) {
        ESP_LOGE(TAG, "Failed to open file %s", filepath);
        return false;
    }
    
    size_t written = fwrite(data, 1, len, file);
    fclose(file);
    
    return written == len;
}

bool SDStorage::loadConfig(const char* filename, char* buffer, size_t len) {
    if (!_initialized) {
        return false;
    }
    
    char filepath[128];
    snprintf(filepath, sizeof(filepath), "%s/%s", MOUNT_POINT, filename);
    
    FILE* file = fopen(filepath, "rb");
    if (file == nullptr) {
        return false;
    }
    
    size_t read = fread(buffer, 1, len - 1, file);
    buffer[read] = '\0';
    fclose(file);
    
    return read > 0;
}

bool SDStorage::saveConfig(const char* filename, const char* data) {
    if (!_initialized) {
        return false;
    }
    
    char filepath[128];
    snprintf(filepath, sizeof(filepath), "%s/%s", MOUNT_POINT, filename);
    
    FILE* file = fopen(filepath, "wb");
    if (file == nullptr) {
        return false;
    }
    
    size_t written = fwrite(data, 1, strlen(data), file);
    fclose(file);
    
    return written == strlen(data);
}

bool SDStorage::fileExists(const char* filename) {
    if (!_initialized) {
        return false;
    }
    
    char filepath[128];
    snprintf(filepath, sizeof(filepath), "%s/%s", MOUNT_POINT, filename);
    
    FILE* file = fopen(filepath, "rb");
    if (file != nullptr) {
        fclose(file);
        return true;
    }
    return false;
}

bool SDStorage::deleteFile(const char* filename) {
    if (!_initialized) {
        return false;
    }
    
    char filepath[128];
    snprintf(filepath, sizeof(filepath), "%s/%s", MOUNT_POINT, filename);
    
    return remove(filepath) == 0;
}

bool SDStorage::format() {
    ESP_LOGW(TAG, "Formatting SD card - this will erase all data!");
    
    // Unmount first if mounted
    if (_initialized) {
        esp_err_t ret = bsp_sdcard_unmount();
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "Failed to unmount SD card: %s", esp_err_to_name(ret));
        }
        _initialized = false;
    }
    
    // Mount with format_if_mount_failed = true to force format
    const esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = true,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024,
        .disk_status_check_enable = false,
        .use_one_fat = false
    };
    
    const sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    const sdmmc_slot_config_t slot_config = {
        .clk = BSP_SD_CLK,
        .cmd = BSP_SD_CMD,
        .d0 = BSP_SD_D0,
        .d1 = GPIO_NUM_NC,
        .d2 = GPIO_NUM_NC,
        .d3 = GPIO_NUM_NC,
        .d4 = GPIO_NUM_NC,
        .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC,
        .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 1,
        .flags = 0,
    };
    
    // Re-initialize and mount (will format if needed)
    sdmmc_card_t* card = nullptr;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount(MOUNT_POINT, &host, &slot_config, &mount_config, &card);
    
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SD card formatted and mounted successfully");
        _initialized = true;
        // Update BSP's card pointer
        extern sdmmc_card_t* bsp_sdcard;
        bsp_sdcard = card;
        return true;
    } else {
        ESP_LOGE(TAG, "Failed to format SD card: %s", esp_err_to_name(ret));
        return false;
    }
}
