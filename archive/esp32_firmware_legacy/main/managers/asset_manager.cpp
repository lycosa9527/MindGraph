#include "asset_manager.h"
#include "esp_log.h"
#include "esp_spiffs.h"
#include "esp_heap_caps.h"
#include <lvgl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char* TAG = "ASSET_MGR";
static const char* SPIFFS_BASE_PATH = "/spiffs";
static bool asset_manager_initialized = false;

bool asset_manager_init() {
    if (asset_manager_initialized) {
        return true;
    }
    
    ESP_LOGI(TAG, "Initializing asset manager...");
    
    // Configure SPIFFS
    esp_vfs_spiffs_conf_t conf = {
        .base_path = SPIFFS_BASE_PATH,
        .partition_label = "fonts",  // Using fonts partition for all assets
        .max_files = 10,  // Increased for multiple asset types
        .format_if_mount_failed = false
    };
    
    esp_err_t ret = esp_vfs_spiffs_register(&conf);
    if (ret != ESP_OK) {
        if (ret == ESP_FAIL) {
            ESP_LOGE(TAG, "Failed to mount or format SPIFFS filesystem");
        } else if (ret == ESP_ERR_NOT_FOUND) {
            ESP_LOGE(TAG, "SPIFFS partition not found");
        } else {
            ESP_LOGE(TAG, "Failed to initialize SPIFFS (%s)", esp_err_to_name(ret));
        }
        return false;
    }
    
    // Get partition info
    size_t total = 0;
    size_t used = 0;
    ret = esp_spiffs_info("fonts", &total, &used);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SPIFFS partition: total=%zu KB, used=%zu KB, free=%zu KB", 
                 total / 1024, used / 1024, (total - used) / 1024);
    } else {
        ESP_LOGW(TAG, "Failed to get SPIFFS partition information");
    }
    
    asset_manager_initialized = true;
    ESP_LOGI(TAG, "[OK] Asset manager initialized");
    return true;
}

bool asset_exists(const char* path) {
    if (!asset_manager_initialized) {
        ESP_LOGW(TAG, "Asset manager not initialized");
        return false;
    }
    
    FILE* f = fopen(path, "r");
    if (f != nullptr) {
        fclose(f);
        return true;
    }
    return false;
}

size_t asset_get_size(const char* path) {
    if (!asset_manager_initialized) {
        return 0;
    }
    
    FILE* f = fopen(path, "rb");
    if (f == nullptr) {
        return 0;
    }
    
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fclose(f);
    
    return (size > 0) ? static_cast<size_t>(size) : 0;
}

lv_obj_t* asset_load_image(lv_obj_t* parent, const char* path) {
    if (!asset_manager_initialized) {
        ESP_LOGE(TAG, "Asset manager not initialized");
        return nullptr;
    }
    
    if (!asset_exists(path)) {
        ESP_LOGE(TAG, "Image not found: %s", path);
        return nullptr;
    }
    
    // LVGL v9 uses lv_image_create and lv_image_set_src with file path
    lv_obj_t* img = lv_image_create(parent);
    if (img == nullptr) {
        ESP_LOGE(TAG, "Failed to create image object");
        return nullptr;
    }
    
    // Set image source from file
    lv_image_set_src(img, path);
    
    ESP_LOGI(TAG, "Loaded image: %s", path);
    return img;
}

lv_image_dsc_t* asset_load_image_dsc(const char* path) {
    // For LVGL v9, images are loaded differently
    // This function is a placeholder for future implementation
    ESP_LOGW(TAG, "asset_load_image_dsc not yet implemented for LVGL v9");
    return nullptr;
}

void* asset_load_binary(const char* path, size_t* size_out) {
    if (!asset_manager_initialized) {
        ESP_LOGE(TAG, "Asset manager not initialized");
        if (size_out != nullptr) {
            *size_out = 0;
        }
        return nullptr;
    }
    
    if (!asset_exists(path)) {
        ESP_LOGE(TAG, "File not found: %s", path);
        if (size_out != nullptr) {
            *size_out = 0;
        }
        return nullptr;
    }
    
    size_t file_size = asset_get_size(path);
    if (file_size == 0) {
        ESP_LOGE(TAG, "File is empty: %s", path);
        if (size_out != nullptr) {
            *size_out = 0;
        }
        return nullptr;
    }
    
    // Load into PSRAM if available, otherwise use regular heap
    void* data = heap_caps_malloc(file_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (data == nullptr) {
        // Fallback to regular heap
        data = malloc(file_size);
        if (data == nullptr) {
            ESP_LOGE(TAG, "Failed to allocate %zu bytes for %s", file_size, path);
            if (size_out != nullptr) {
                *size_out = 0;
            }
            return nullptr;
        }
        ESP_LOGW(TAG, "Loaded %s into regular heap (PSRAM unavailable)", path);
    }
    
    FILE* f = fopen(path, "rb");
    if (f == nullptr) {
        ESP_LOGE(TAG, "Failed to open file: %s", path);
        heap_caps_free(data);
        if (size_out != nullptr) {
            *size_out = 0;
        }
        return nullptr;
    }
    
    size_t bytes_read = fread(data, 1, file_size, f);
    fclose(f);
    
    if (bytes_read != file_size) {
        ESP_LOGE(TAG, "Failed to read file: read %zu bytes, expected %zu", bytes_read, file_size);
        heap_caps_free(data);
        if (size_out != nullptr) {
            *size_out = 0;
        }
        return nullptr;
    }
    
    if (size_out != nullptr) {
        *size_out = file_size;
    }
    
    ESP_LOGI(TAG, "Loaded binary: %s (%zu bytes)", path, file_size);
    return data;
}

bool asset_get_partition_info(size_t* total_kb, size_t* used_kb) {
    if (!asset_manager_initialized) {
        return false;
    }
    
    size_t total = 0;
    size_t used = 0;
    esp_err_t ret = esp_spiffs_info("fonts", &total, &used);
    if (ret == ESP_OK) {
        if (total_kb != nullptr) {
            *total_kb = total / 1024;
        }
        if (used_kb != nullptr) {
            *used_kb = used / 1024;
        }
        return true;
    }
    
    return false;
}
