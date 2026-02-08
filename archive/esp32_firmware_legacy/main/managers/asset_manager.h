#ifndef ASSET_MANAGER_H
#define ASSET_MANAGER_H

#include <lvgl.h>
#include <cstdint>

/**
 * Asset Manager for loading files from SPIFFS
 * Supports fonts, images, icons, backgrounds, and other assets
 */

// Asset paths (all relative to /spiffs)
#define ASSET_PATH_FONTS       "/spiffs/fonts"
#define ASSET_PATH_ICONS       "/spiffs/icons"
#define ASSET_PATH_BACKGROUNDS "/spiffs/backgrounds"
#define ASSET_PATH_CONFIG      "/spiffs/config"

/**
 * Initialize asset manager and SPIFFS
 * @return true if successful, false otherwise
 */
bool asset_manager_init();

/**
 * Check if an asset file exists
 * @param path Full path to asset (e.g., "/spiffs/icons/wifi.png")
 * @return true if file exists, false otherwise
 */
bool asset_exists(const char* path);

/**
 * Get file size of an asset
 * @param path Full path to asset
 * @return File size in bytes, or 0 if not found
 */
size_t asset_get_size(const char* path);

/**
 * Load an image from SPIFFS
 * @param path Full path to image file (e.g., "/spiffs/icons/wifi.png")
 * @return LVGL image object, or nullptr on failure
 */
lv_obj_t* asset_load_image(lv_obj_t* parent, const char* path);

/**
 * Load an image and return the image descriptor (for use in styles)
 * @param path Full path to image file
 * @return LVGL image descriptor, or nullptr on failure
 */
lv_image_dsc_t* asset_load_image_dsc(const char* path);

/**
 * Load raw binary data from SPIFFS into PSRAM
 * @param path Full path to file
 * @param size_out Output parameter for file size
 * @return Pointer to allocated data in PSRAM, or nullptr on failure
 *         Caller must free with heap_caps_free() when done
 */
void* asset_load_binary(const char* path, size_t* size_out);

/**
 * Get SPIFFS partition info
 * @param total_kb Output: Total size in KB
 * @param used_kb Output: Used size in KB
 * @return true if successful
 */
bool asset_get_partition_info(size_t* total_kb, size_t* used_kb);

#endif // ASSET_MANAGER_H
