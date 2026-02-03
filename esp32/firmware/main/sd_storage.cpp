#include "sd_storage.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "driver/sdspi_host.h"
#include "driver/spi_common.h"
#include "sdmmc_cmd.h"
#include <cstring>
#include <cstdio>

static const char* TAG = "SD_STORAGE";
static const char* MOUNT_POINT = "/sdcard";

SDStorage::SDStorage() {
    _initialized = false;
}

bool SDStorage::init() {
    if (_initialized) {
        return true;
    }
    
    ESP_LOGW(TAG, "SD card initialization not fully implemented - using stub");
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
