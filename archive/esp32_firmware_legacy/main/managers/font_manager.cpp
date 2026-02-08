#include "font_manager.h"
#include "asset_manager.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include <lvgl.h>
#include <cstdio>
#include <cstring>
#include <cstdint>

static const char* TAG = "FONT_MGR";
static const char* FONT_BIN_PATH = "/spiffs/fonts/chinese_font_16.bin";

const lv_font_t* chinese_font_16_ptr = nullptr;
static void* font_data_ptr = nullptr;  // Points to loaded font data in PSRAM

bool has_chinese_char(const char* text) {
    if (text == nullptr) {
        return false;
    }
    
    while (*text) {
        unsigned char c = *text;
        if (c >= 0xE0 && c <= 0xEF) {
            return true;
        }
        text++;
    }
    return false;
}


void font_manager_init() {
    ESP_LOGI(TAG, "Initializing font manager (compiled font from SPIFFS)...");
    
    // Verify LVGL is initialized
    lv_display_t* disp = lv_display_get_default();
    if (disp == nullptr) {
        ESP_LOGE(TAG, "LVGL not initialized!");
        // Still set compiled font as fallback
        extern const lv_font_t chinese_font_16;
        chinese_font_16_ptr = &chinese_font_16;
        ESP_LOGW(TAG, "Using compiled font (LVGL not ready)");
        return;
    }
    
    // Initialize asset manager (handles SPIFFS)
    // If this fails, we'll still use compiled font
    bool asset_mgr_ok = asset_manager_init();
    if (!asset_mgr_ok) {
        ESP_LOGW(TAG, "Asset manager initialization failed, using compiled font");
    }
    
    // Load compiled font binary from SPIFFS using asset manager (if available)
    size_t file_size = 0;
    font_data_ptr = nullptr;
    
    if (asset_mgr_ok) {
        font_data_ptr = asset_load_binary(FONT_BIN_PATH, &file_size);
    }
    
    if (font_data_ptr != nullptr && file_size > 0) {
        ESP_LOGI(TAG, "Font binary loaded: %s (%zu bytes)", FONT_BIN_PATH, file_size);
        
        // Parse binary format
        // Format: Header (32 bytes) + bitmap_size (4 bytes) + bitmap_data
        uint8_t* data = static_cast<uint8_t*>(font_data_ptr);
        
        // Check magic
        if (memcmp(data, "LVFN", 4) == 0) {
            // Parse header
            uint8_t version = data[4];
            uint8_t line_height = data[5];
            uint8_t base_line = data[6];
            uint16_t cmap_num = (data[8] << 8) | data[7];  // Little-endian
            uint8_t bpp = data[9];
            uint8_t kern_scale = data[10];
            
            ESP_LOGI(TAG, "Font binary header:");
            ESP_LOGI(TAG, "  Version: %d", version);
            ESP_LOGI(TAG, "  line_height: %d", line_height);
            ESP_LOGI(TAG, "  base_line: %d", base_line);
            ESP_LOGI(TAG, "  cmap_num: %d", cmap_num);
            ESP_LOGI(TAG, "  bpp: %d", bpp);
            ESP_LOGI(TAG, "  kern_scale: %d", kern_scale);
            
            // Get bitmap size
            uint32_t bitmap_size = (data[31] << 24) | (data[30] << 16) | (data[29] << 8) | data[28];  // Little-endian
            
            ESP_LOGI(TAG, "Bitmap data: %u bytes at offset 36", bitmap_size);
            (void)bitmap_size;  // Will be used when font reconstruction is implemented
            
            // TODO: Reconstruct full font structure
            // Currently we only have glyph_bitmap extracted
            // We still need: glyph_dsc, cmaps, kern_pairs arrays
            // For now, use compiled font as fallback
            ESP_LOGW(TAG, "Full font reconstruction not yet implemented");
            ESP_LOGW(TAG, "Need to extract glyph_dsc and cmaps arrays from C file");
            ESP_LOGW(TAG, "Using compiled font as fallback for now");
        } else {
            ESP_LOGE(TAG, "Invalid font binary format - bad magic");
            heap_caps_free(font_data_ptr);
            font_data_ptr = nullptr;
        }
    } else {
        if (asset_mgr_ok) {
            ESP_LOGW(TAG, "Font binary not found in SPIFFS: %s", FONT_BIN_PATH);
            ESP_LOGW(TAG, "Using compiled font from firmware");
        }
    }
    
    // ALWAYS set compiled font (it's included in build)
    // This ensures fonts work even if SPIFFS fails
    extern const lv_font_t chinese_font_16;
    chinese_font_16_ptr = &chinese_font_16;
    
    if (chinese_font_16_ptr == nullptr) {
        ESP_LOGE(TAG, "CRITICAL: Compiled font is NULL! Font linking issue!");
        return;
    }
    
    ESP_LOGI(TAG, "[OK] Compiled font loaded");
    ESP_LOGI(TAG, "  Font: line_height=%d, base_line=%d", 
             chinese_font_16_ptr->line_height, 
             chinese_font_16_ptr->base_line);
    
    // Log partition usage
    size_t total_kb = 0, used_kb = 0;
    if (asset_get_partition_info(&total_kb, &used_kb)) {
        ESP_LOGI(TAG, "SPIFFS usage: %zu KB / %zu KB (%.1f%%)", 
                 used_kb, total_kb, (used_kb * 100.0f) / total_kb);
        ESP_LOGI(TAG, "Free space available for icons/backgrounds: %zu KB", total_kb - used_kb);
    }
    
    // Test font with Chinese characters
    const char* test_chars = "智回就绪已连接";
    ESP_LOGI(TAG, "Testing font with Chinese characters");
    
    for (const char* p = test_chars; *p != '\0'; ) {
        uint32_t unicode = 0;
        int bytes = 0;
        if ((*p & 0xF0) == 0xE0) {
            unicode = ((p[0] & 0x0F) << 12) | ((p[1] & 0x3F) << 6) | (p[2] & 0x3F);
            bytes = 3;
        } else {
            p++;
            continue;
        }
        
        lv_font_glyph_dsc_t gdsc;
        bool found = chinese_font_16_ptr->get_glyph_dsc(chinese_font_16_ptr, &gdsc, unicode, 0);
        if (found) {
            ESP_LOGI(TAG, "[OK] Character U+%04X found (w=%d, h=%d)", unicode, gdsc.box_w, gdsc.box_h);
        } else {
            ESP_LOGW(TAG, "[WARN] Character U+%04X not found", unicode);
        }
        p += bytes;
    }
}

const lv_font_t* font_manager_get_font(int size, bool needs_chinese) {
    if (chinese_font_16_ptr == nullptr) {
        ESP_LOGE(TAG, "font_manager_get_font: chinese_font_16_ptr is NULL!");
        return nullptr;
    }
    
    // Note: Compiled font is fixed at 16px
    // For other sizes, you'd need separate compiled fonts
    if (size != 16) {
        ESP_LOGW(TAG, "Requested font size %d, but compiled font is 16px", size);
    }
    
    ESP_LOGD(TAG, "font_manager_get_font: returning compiled font (line_height=%d)", 
             chinese_font_16_ptr->line_height);
    return chinese_font_16_ptr;
}
