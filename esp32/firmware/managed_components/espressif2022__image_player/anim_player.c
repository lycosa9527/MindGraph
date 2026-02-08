#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <string.h>
#include <stdint.h>
#include <limits.h>
#include "esp_timer.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "anim_player.h"
#include "anim_vfs.h"
#include "anim_dec.h"

static const char *TAG = "anim_player";

#define NEED_DELETE     BIT0
#define DELETE_DONE     BIT1
#define WAIT_FLUSH_DONE BIT2
#define WAIT_STOP       BIT3
#define WAIT_STOP_DONE  BIT4

#define FPS_TO_MS(fps) (1000 / (fps))  // Convert FPS to milliseconds


typedef struct {
    player_action_t action;
} anim_player_event_t;

typedef struct {
    EventGroupHandle_t event_group;
    QueueHandle_t event_queue;
} anim_player_events_t;

typedef struct {
    uint32_t start;
    uint32_t end;
    anim_vfs_handle_t file_desc;
} anim_player_info_t;

// Animation player context
typedef struct {
    anim_player_info_t info;
    int run_start;
    int run_end;
    bool repeat;
    int fps;
    anim_flush_cb_t flush_cb;
    anim_update_cb_t update_cb;
    void *user_data;
    anim_player_events_t events;
    TaskHandle_t handle_task;
    struct {
        unsigned char swap: 1;
    } flags;
    // Reusable buffers to avoid per-frame allocation
    void *frame_buffer;          // Reusable frame buffer
    uint8_t *decode_buffer;      // Reusable decode buffer
    uint8_t *huffman_buffer;    // Reusable Huffman decode buffer
    size_t frame_buffer_size;    // Current frame buffer size
    size_t decode_buffer_size;   // Current decode buffer size
    size_t huffman_buffer_size;  // Current Huffman buffer size
    uint32_t *color_cache;       // Reusable color cache
    uint16_t color_cache_size;   // Current color cache size
} anim_player_context_t;

typedef struct {
    player_action_t action;
    int run_start;
    int run_end;
    bool repeat;
    int fps;
    int64_t last_frame_time;
} anim_player_run_ctx_t;

// Ensure buffers are allocated/resized to required sizes
static esp_err_t anim_player_ensure_buffers(anim_player_context_t *ctx, size_t frame_buffer_size, size_t decode_buffer_size, uint16_t color_depth)
{
    // Check SPIRAM availability first
    size_t spiram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t spiram_largest = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
    
    ESP_LOGI(TAG, "Buffer allocation: frame=%zu, decode=%zu, SPIRAM free=%zu (largest=%zu)",
             frame_buffer_size, decode_buffer_size, spiram_free, spiram_largest);
    ESP_LOGI(TAG, "Current buffers: frame=%p (size=%zu), decode=%p (size=%zu)",
             ctx->frame_buffer, ctx->frame_buffer_size, ctx->decode_buffer, ctx->decode_buffer_size);
    
    // Check if pre-allocated buffers are sufficient (from anim_player_init())
    // If buffers were pre-allocated and are large enough, reuse them - no allocation needed
    if (ctx->frame_buffer != NULL && ctx->frame_buffer_size >= frame_buffer_size &&
        (decode_buffer_size == 0 || (ctx->decode_buffer != NULL && ctx->decode_buffer_size >= decode_buffer_size))) {
        ESP_LOGI(TAG, "Reusing pre-allocated buffers (frame: %zu >= %zu, decode: %zu >= %zu)",
                 ctx->frame_buffer_size, frame_buffer_size,
                 ctx->decode_buffer_size, decode_buffer_size);
        // Buffers are sufficient, skip to color cache allocation
        goto allocate_color_cache;
    }
    
    // Strategy: Allocate decode buffer FIRST (smaller), then check if frame buffer reallocation is needed.
    // Only free frame buffer AFTER ensuring decode buffer allocation succeeds AND frame buffer reallocation will succeed.
    // This prevents losing the pre-allocated frame buffer if reallocation fails.
    
    bool need_frame_realloc = (ctx->frame_buffer == NULL || ctx->frame_buffer_size < frame_buffer_size);
    bool need_decode_realloc = (decode_buffer_size > 0 && (ctx->decode_buffer == NULL || ctx->decode_buffer_size < decode_buffer_size));
    
    ESP_LOGI(TAG, "Reallocation needed: frame=%d, decode=%d", need_frame_realloc, need_decode_realloc);
    
    // If decode buffer needs reallocation and frame buffer also needs it, free decode buffer first
    // But DON'T free frame buffer yet - we'll check SPIRAM availability after decode buffer allocation
    if (need_decode_realloc && ctx->decode_buffer != NULL) {
        ESP_LOGI(TAG, "Freeing existing decode buffer before reallocation");
        free(ctx->decode_buffer);
        ctx->decode_buffer = NULL;
        ctx->decode_buffer_size = 0;
        // Re-check SPIRAM after freeing decode buffer
        spiram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
        spiram_largest = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
        ESP_LOGI(TAG, "After freeing decode buffer, SPIRAM free=%zu (largest=%zu)", spiram_free, spiram_largest);
    }
    
    // Allocate/resize decode buffer FIRST (smaller, allocate first to avoid fragmentation)
    if (decode_buffer_size > 0) {
        if (ctx->decode_buffer == NULL || ctx->decode_buffer_size < decode_buffer_size) {
            ESP_LOGI(TAG, "Allocating decode buffer: size=%zu, current=%p (size=%zu)",
                     decode_buffer_size, ctx->decode_buffer, ctx->decode_buffer_size);
            
            // Try SPIRAM first for decode buffer (smaller, allocate first)
            if (spiram_largest >= decode_buffer_size) {
                ctx->decode_buffer = (uint8_t *)heap_caps_malloc(decode_buffer_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
                if (ctx->decode_buffer != NULL) {
                    ESP_LOGI(TAG, "Allocated decode buffer (%zu bytes) from SPIRAM at %p", decode_buffer_size, ctx->decode_buffer);
                } else {
                    ESP_LOGW(TAG, "SPIRAM allocation failed for decode buffer, trying default heap");
                }
            } else {
                ESP_LOGW(TAG, "SPIRAM insufficient for decode buffer (need %zu, largest=%zu), trying default heap",
                         decode_buffer_size, spiram_largest);
            }
            
            // Fallback to default heap
            if (ctx->decode_buffer == NULL) {
                ctx->decode_buffer = (uint8_t *)malloc(decode_buffer_size);
                if (ctx->decode_buffer != NULL) {
                    ESP_LOGI(TAG, "Allocated decode buffer (%zu bytes) from default heap at %p", decode_buffer_size, ctx->decode_buffer);
                }
            }
            
            if (ctx->decode_buffer == NULL) {
                size_t internal_free = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
                size_t internal_largest = heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
                size_t default_free = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
                size_t default_largest = heap_caps_get_largest_free_block(MALLOC_CAP_DEFAULT);
                
                ESP_LOGW(TAG, "Failed to allocate decode buffer (size: %zu) - frame will be skipped", decode_buffer_size);
                ESP_LOGW(TAG, "Available memory - Internal: %zu bytes (largest: %zu), PSRAM: %zu bytes (largest: %zu), Default: %zu bytes (largest: %zu)",
                         internal_free, internal_largest, spiram_free, spiram_largest, default_free, default_largest);
                ESP_LOGW(TAG, "This frame cannot be decoded due to insufficient memory. Animation will continue with next frame.");
                // Don't return error - allow frame to be skipped gracefully
                // Return ESP_OK but decode_buffer will be NULL, caller should check
                return ESP_OK;
            }
            ctx->decode_buffer_size = decode_buffer_size;
            ESP_LOGI(TAG, "Decode buffer allocation successful: %p (size=%zu)", ctx->decode_buffer, ctx->decode_buffer_size);
        }
    }
    
    // Allocate/resize frame buffer AFTER decode buffer
    // CRITICAL FIX: Only free existing frame buffer if we're CERTAIN reallocation will succeed
    // This prevents losing the pre-allocated buffer if reallocation fails
    if (ctx->frame_buffer == NULL || ctx->frame_buffer_size < frame_buffer_size) {
        ESP_LOGI(TAG, "Frame buffer check: current=%p (size=%zu), needed=%zu",
                 ctx->frame_buffer, ctx->frame_buffer_size, frame_buffer_size);
        
        // Re-check SPIRAM after decode buffer allocation
        spiram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
        spiram_largest = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
        ESP_LOGI(TAG, "After decode buffer allocation, SPIRAM free=%zu (largest=%zu)", spiram_free, spiram_largest);
        
        // Check if we have enough SPIRAM for frame buffer BEFORE freeing existing buffer
        bool can_reallocate = false;
        if (spiram_largest >= frame_buffer_size) {
            can_reallocate = true;
            ESP_LOGI(TAG, "SPIRAM sufficient for frame buffer reallocation");
        } else {
            // Check default heap as fallback
            size_t default_largest = heap_caps_get_largest_free_block(MALLOC_CAP_DEFAULT);
            if (default_largest >= frame_buffer_size) {
                can_reallocate = true;
                ESP_LOGI(TAG, "Default heap sufficient for frame buffer reallocation (largest=%zu)", default_largest);
            } else {
                ESP_LOGW(TAG, "Cannot reallocate frame buffer: SPIRAM largest=%zu, default largest=%zu, needed=%zu",
                         spiram_largest, default_largest, frame_buffer_size);
                // If we have an existing buffer that's close to the required size, try to use it
                // This handles cases where pre-allocated buffer is slightly smaller but might still work
                if (ctx->frame_buffer != NULL && ctx->frame_buffer_size > 0) {
                    ESP_LOGW(TAG, "Keeping existing frame buffer (%zu bytes) - may cause issues if insufficient", ctx->frame_buffer_size);
                    // Don't free, but log warning - caller should handle this case
                }
            }
        }
        
        // Only free and reallocate if we're certain it will succeed
        if (can_reallocate) {
            if (ctx->frame_buffer) {
                ESP_LOGI(TAG, "Freeing existing frame buffer before reallocation");
                free(ctx->frame_buffer);
                ctx->frame_buffer = NULL;
                ctx->frame_buffer_size = 0;
            }
            
            // Try SPIRAM first for frame buffer if there's enough space
            if (spiram_largest >= frame_buffer_size) {
                ctx->frame_buffer = heap_caps_malloc(frame_buffer_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
                if (ctx->frame_buffer != NULL) {
                    ESP_LOGI(TAG, "Allocated frame buffer (%zu bytes) from SPIRAM at %p", frame_buffer_size, ctx->frame_buffer);
                } else {
                    ESP_LOGW(TAG, "SPIRAM allocation failed for frame buffer, trying default heap");
                }
            }
            
            // Fallback to default heap
            if (ctx->frame_buffer == NULL) {
                ctx->frame_buffer = malloc(frame_buffer_size);
                if (ctx->frame_buffer != NULL) {
                    ESP_LOGI(TAG, "Allocated frame buffer (%zu bytes) from default heap at %p", frame_buffer_size, ctx->frame_buffer);
                }
            }
            
            if (ctx->frame_buffer == NULL) {
                ESP_LOGE(TAG, "Failed to allocate frame buffer (size: %zu) after freeing existing buffer", frame_buffer_size);
                // Free decode buffer if we just allocated it
                if (ctx->decode_buffer_size == decode_buffer_size && ctx->decode_buffer != NULL) {
                    ESP_LOGE(TAG, "Freeing decode buffer due to frame buffer allocation failure");
                    free(ctx->decode_buffer);
                    ctx->decode_buffer = NULL;
                    ctx->decode_buffer_size = 0;
                }
                return ESP_FAIL;
            }
            ctx->frame_buffer_size = frame_buffer_size;
            ESP_LOGI(TAG, "Frame buffer allocation successful: %p (size=%zu)", ctx->frame_buffer, ctx->frame_buffer_size);
        } else {
            // Cannot reallocate - keep existing buffer if available
            if (ctx->frame_buffer == NULL) {
                ESP_LOGE(TAG, "No frame buffer available and cannot allocate new one (size: %zu)", frame_buffer_size);
                // Free decode buffer if we just allocated it
                if (ctx->decode_buffer_size == decode_buffer_size && ctx->decode_buffer != NULL) {
                    ESP_LOGE(TAG, "Freeing decode buffer due to frame buffer unavailability");
                    free(ctx->decode_buffer);
                    ctx->decode_buffer = NULL;
                    ctx->decode_buffer_size = 0;
                }
                return ESP_FAIL;
            }
            ESP_LOGW(TAG, "Using existing frame buffer (%zu bytes) which may be insufficient for required size (%zu)",
                     ctx->frame_buffer_size, frame_buffer_size);
        }
    } else {
        ESP_LOGI(TAG, "Frame buffer sufficient: %p (size=%zu >= %zu)", ctx->frame_buffer, ctx->frame_buffer_size, frame_buffer_size);
    }
    
allocate_color_cache:
    // Allocate/resize color cache
    ESP_LOGI(TAG, "Color cache check: current=%p (size=%zu), needed=%u",
             ctx->color_cache, ctx->color_cache_size, color_depth);
    
    if (ctx->color_cache == NULL || ctx->color_cache_size < color_depth) {
        if (ctx->color_cache) {
            ESP_LOGI(TAG, "Freeing existing color cache before reallocation");
            free(ctx->color_cache);
            ctx->color_cache = NULL;
        }
        
        size_t color_cache_size = color_depth * sizeof(uint32_t);
        ctx->color_cache = (uint32_t *)malloc(color_cache_size);
        if (ctx->color_cache == NULL) {
            ESP_LOGE(TAG, "Failed to allocate color cache (size: %zu)", color_cache_size);
            return ESP_FAIL;
        }
        ctx->color_cache_size = color_depth;
        ESP_LOGI(TAG, "Allocated color cache: %p (size=%zu)", ctx->color_cache, color_cache_size);
        
        // Initialize color cache
        for (uint16_t i = 0; i < color_depth; i++) {
            ctx->color_cache[i] = 0xFFFFFFFF;
        }
    } else {
        ESP_LOGI(TAG, "Color cache sufficient, resetting values");
        // Reset color cache
        for (uint16_t i = 0; i < color_depth; i++) {
            ctx->color_cache[i] = 0xFFFFFFFF;
        }
    }
    
    ESP_LOGI(TAG, "Buffer allocation complete: frame=%p, decode=%p, color_cache=%p",
             ctx->frame_buffer, ctx->decode_buffer, ctx->color_cache);
    
    return ESP_OK;
}

// Free reusable buffers
static void anim_player_free_buffers(anim_player_context_t *ctx)
{
    if (ctx->frame_buffer) {
        free(ctx->frame_buffer);
        ctx->frame_buffer = NULL;
        ctx->frame_buffer_size = 0;
    }
    
    if (ctx->decode_buffer) {
        free(ctx->decode_buffer);
        ctx->decode_buffer = NULL;
        ctx->decode_buffer_size = 0;
    }
    
    if (ctx->huffman_buffer) {
        free(ctx->huffman_buffer);
        ctx->huffman_buffer = NULL;
        ctx->huffman_buffer_size = 0;
    }
    
    if (ctx->color_cache) {
        free(ctx->color_cache);
        ctx->color_cache = NULL;
        ctx->color_cache_size = 0;
    }
}

static esp_err_t anim_player_parse(const uint8_t *data, size_t data_len, image_header_t *header, anim_player_context_t *ctx)
{
    // Validate header dimensions to prevent overflow
    if (header->width == 0 || header->split_height == 0 || header->width > 2000 || header->split_height > 2000) {
        ESP_LOGE(TAG, "Invalid header dimensions: width=%d, split_height=%d", header->width, header->split_height);
        anim_dec_free_header(header);
        return ESP_ERR_INVALID_ARG;
    }
    
    // Calculate buffer sizes with overflow protection
    if (header->width > SIZE_MAX / header->split_height / sizeof(uint16_t)) {
        ESP_LOGE(TAG, "Frame buffer size overflow: width=%d, split_height=%d", header->width, header->split_height);
        anim_dec_free_header(header);
        return ESP_ERR_INVALID_SIZE;
    }
    size_t frame_buffer_size = header->width * header->split_height * sizeof(uint16_t);
    
    size_t decode_buffer_size = 0;
    if (header->bit_depth == 4) {
        if (header->width > SIZE_MAX / header->split_height) {
            ESP_LOGE(TAG, "Decode buffer size overflow (4-bit): width=%d, split_height=%d", header->width, header->split_height);
            anim_dec_free_header(header);
            return ESP_ERR_INVALID_SIZE;
        }
        decode_buffer_size = header->width * (header->split_height + (header->split_height % 2)) / 2;
    } else if (header->bit_depth == 8) {
        if (header->width > SIZE_MAX / header->split_height) {
            ESP_LOGE(TAG, "Decode buffer size overflow (8-bit): width=%d, split_height=%d", header->width, header->split_height);
            anim_dec_free_header(header);
            return ESP_ERR_INVALID_SIZE;
        }
        decode_buffer_size = header->width * header->split_height;
    }

    uint16_t color_depth = 0;
    if (header->bit_depth == 4) {
        color_depth = 16;
    } else if (header->bit_depth == 8) {
        color_depth = 256;
    }

    // Log memory requirements for debugging
    size_t internal_free = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
    size_t spiram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t default_free = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
    ESP_LOGD(TAG, "Frame buffer size: %zu, decode buffer size: %zu, width: %d, split_height: %d",
             frame_buffer_size, decode_buffer_size, header->width, header->split_height);
    ESP_LOGD(TAG, "Available memory - Internal: %zu bytes, PSRAM: %zu bytes, Default: %zu bytes",
             internal_free, spiram_free, default_free);

    // Ensure reusable buffers are allocated/resized
    ESP_LOGI(TAG, "Calling anim_player_ensure_buffers");
    esp_err_t ret = anim_player_ensure_buffers(ctx, frame_buffer_size, decode_buffer_size, color_depth);
    ESP_LOGI(TAG, "anim_player_ensure_buffers returned: %s", esp_err_to_name(ret));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to ensure buffers");
        // Free header allocations before returning error
        anim_dec_free_header(header);
        return ret;
    }
    ESP_LOGI(TAG, "Buffers ensured successfully, checking decode buffer");

    // Check if decode buffer was allocated (may fail gracefully)
    if (ctx->decode_buffer == NULL && decode_buffer_size > 0) {
        ESP_LOGW(TAG, "Decode buffer not available - skipping frame decode");
        anim_dec_free_header(header);
        return ESP_OK;  // Skip frame gracefully, don't fail
    }

    // Validate buffers before use
    ESP_LOGI(TAG, "Starting buffer validation");
    if (ctx->frame_buffer == NULL) {
        ESP_LOGE(TAG, "Frame buffer is NULL after allocation - cannot proceed");
        anim_dec_free_header(header);
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "Frame buffer validation passed");
    
    if (ctx->frame_buffer_size < frame_buffer_size) {
        ESP_LOGE(TAG, "Frame buffer size insufficient: have %zu, need %zu", ctx->frame_buffer_size, frame_buffer_size);
        anim_dec_free_header(header);
        return ESP_FAIL;
    }
    
    if (decode_buffer_size > 0 && ctx->decode_buffer == NULL) {
        ESP_LOGE(TAG, "Decode buffer is NULL but required (size: %zu)", decode_buffer_size);
        anim_dec_free_header(header);
        return ESP_FAIL;
    }
    
    if (decode_buffer_size > 0 && ctx->decode_buffer_size < decode_buffer_size) {
        ESP_LOGE(TAG, "Decode buffer size insufficient: have %zu, need %zu", ctx->decode_buffer_size, decode_buffer_size);
        anim_dec_free_header(header);
        return ESP_FAIL;
    }
    
    if (ctx->color_cache == NULL) {
        ESP_LOGE(TAG, "Color cache is NULL after allocation");
        anim_dec_free_header(header);
        return ESP_FAIL;
    }
    
    // Validate buffer alignment (frame buffer should be 2-byte aligned for RGB565)
    if ((uintptr_t)ctx->frame_buffer % 2 != 0) {
        ESP_LOGW(TAG, "Frame buffer not 2-byte aligned: %p (may cause performance issues)", ctx->frame_buffer);
    }

    // Use reusable buffers from context
    void *frame_buffer = ctx->frame_buffer;
    uint8_t *decode_buffer = ctx->decode_buffer;
    uint32_t *color_cache = ctx->color_cache;
    uint16_t *pixels = (uint16_t *)frame_buffer;
    
    ESP_LOGI(TAG, "Using buffers: frame=%p, decode=%p, color_cache=%p", frame_buffer, decode_buffer, color_cache);

    // Allocate memory for split offsets
    ESP_LOGI(TAG, "Allocating split offsets: splits=%d, size=%zu", header->splits, header->splits * sizeof(uint16_t));
    uint16_t *offsets = (uint16_t *)malloc(header->splits * sizeof(uint16_t));
    if (offsets == NULL) {
        ESP_LOGE(TAG, "Failed to allocate memory for offsets");
        // Free header allocations before returning error
        anim_dec_free_header(header);
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "Split offsets allocated: %p", offsets);

    ESP_LOGI(TAG, "Calculating split offsets");
    anim_dec_calculate_offsets(header, offsets);
    ESP_LOGI(TAG, "Split offsets calculated, processing %d splits", header->splits);

    // Process each split
    for (int split = 0; split < header->splits; split++) {
        ESP_LOGI(TAG, "Processing split %d/%d", split + 1, header->splits);
        const uint8_t *compressed_data = data + offsets[split];
        int compressed_len = header->split_lengths[split];

        esp_err_t decode_result = ESP_FAIL;
        int valid_height;

        if (split == header->splits - 1) {
            valid_height = header->height - split * header->split_height;
        } else {
            valid_height = header->split_height;
        }
        ESP_LOGI(TAG, "split:%d(%d), height:%d(%d), compressed_len:%d, encoding=0x%02X", 
                 split, header->splits, header->split_height, valid_height, compressed_len, compressed_data[0]);

        // Check encoding type from first byte
        if (compressed_data[0] == ENCODING_TYPE_RLE) {
            ESP_LOGI(TAG, "Decoding split %d with RLE encoding", split);
            decode_result = anim_dec_rte_decode(compressed_data + 1, compressed_len - 1,
                                                decode_buffer, header->width * header->split_height);
            ESP_LOGI(TAG, "RLE decode result: %s", esp_err_to_name(decode_result));
        } else if (compressed_data[0] == ENCODING_TYPE_HUFFMAN) {
            ESP_LOGI(TAG, "Decoding split %d with Huffman encoding", split);
            size_t huffman_buffer_size = header->width * header->split_height;
            
            // Ensure huffman buffer is allocated/resized (reuse from context)
            if (ctx->huffman_buffer == NULL || ctx->huffman_buffer_size < huffman_buffer_size) {
                if (ctx->huffman_buffer) {
                    free(ctx->huffman_buffer);
                    ctx->huffman_buffer = NULL;
                }
                ctx->huffman_buffer = (uint8_t *)malloc(huffman_buffer_size);
                if (ctx->huffman_buffer == NULL) {
                    ESP_LOGE(TAG, "Failed to allocate memory for Huffman buffer (size: %zu)", huffman_buffer_size);
                    continue;
                }
                ctx->huffman_buffer_size = huffman_buffer_size;
            }

            size_t huffman_decoded_len = 0;
            ESP_LOGI(TAG, "Huffman decode step 1");
            anim_dec_huffman_decode(compressed_data, compressed_len, ctx->huffman_buffer, &huffman_decoded_len);
            ESP_LOGI(TAG, "Huffman decode step 1 complete, decoded_len=%zu", huffman_decoded_len);
            decode_result = ESP_OK;
            if (decode_result == ESP_OK) {
                ESP_LOGI(TAG, "Huffman decode step 2 (RLE)");
                decode_result = anim_dec_rte_decode(ctx->huffman_buffer, huffman_decoded_len,
                                                    decode_buffer, header->width * header->split_height);
                ESP_LOGI(TAG, "Huffman decode step 2 result: %s", esp_err_to_name(decode_result));
            }
        } else {
            ESP_LOGE(TAG, "Unknown encoding type: %02X", compressed_data[0]);
            continue;
        }

        if (decode_result != ESP_OK) {
            ESP_LOGE(TAG, "Failed to decode split %d", split);
            continue;
        }

        ESP_LOGI(TAG, "Decode successful, converting to RGB565 (bit_depth=%d)", header->bit_depth);
        // Convert to RGB565 based on bit depth
        if (header->bit_depth == 4) {
            // 4-bit mode: each byte contains two pixels
            for (int y = 0; y < valid_height; y++) {
                for (int x = 0; x < header->width; x += 2) {
                    uint8_t packed_gray = decode_buffer[y * (header->width / 2) + (x / 2)];
                    uint8_t index1 = (packed_gray & 0xF0) >> 4;
                    uint8_t index2 = (packed_gray & 0x0F);

                    if (color_cache[index1] == 0xFFFFFFFF) {
                        uint16_t color = anim_dec_parse_palette(header, index1, ctx->flags.swap);
                        color_cache[index1] = color;
                    }
                    pixels[y * header->width + x] = (uint16_t)color_cache[index1];

                    if (x + 1 < header->width) {
                        if (color_cache[index2] == 0xFFFFFFFF) {
                            uint16_t color = anim_dec_parse_palette(header, index2, ctx->flags.swap);
                            color_cache[index2] = color;
                        }
                        pixels[y * header->width + x + 1] = (uint16_t)color_cache[index2];
                    }
                }
            }
            
        } else if (header->bit_depth == 8) {
            // 8-bit mode: each byte is one pixel
            for (int y = 0; y < valid_height; y++) {
                // First process all indices in the line to ensure color_cache is populated
                for (int x = 0; x < header->width; x++) {
                    uint8_t index = decode_buffer[y * header->width + x];
                    if (color_cache[index] == 0xFFFFFFFF) {
                        uint16_t color = anim_dec_parse_palette(header, index, ctx->flags.swap);
                        color_cache[index] = color;
                    }
                    // Copy the color value directly
                    pixels[y * header->width + x] = (uint16_t)color_cache[index];
                }
            }
        } else {
            ESP_LOGE(TAG, "Unsupported bit depth: %d", header->bit_depth);
            continue;
        }

        ESP_LOGI(TAG, "Conversion complete, flushing split %d", split);
        // Flush decoded data
        xEventGroupClearBits(ctx->events.event_group, WAIT_FLUSH_DONE);
        if (ctx->flush_cb) {
            ESP_LOGI(TAG, "Calling flush callback for split %d: x1=0, y1=%d, x2=%d, y2=%d, data=%p",
                     split, split * header->split_height, header->width, split * header->split_height + valid_height, pixels);
            ctx->flush_cb(ctx, 0, split * header->split_height, header->width, split * header->split_height + valid_height, pixels);
            ESP_LOGI(TAG, "Flush callback returned for split %d", split);
        } else {
            ESP_LOGW(TAG, "No flush callback registered, setting flush done immediately");
            // If no flush callback, set flush done immediately to prevent deadlock
            xEventGroupSetBits(ctx->events.event_group, WAIT_FLUSH_DONE);
        }
        ESP_LOGI(TAG, "Waiting for flush done event");
        EventBits_t bits = xEventGroupWaitBits(ctx->events.event_group, WAIT_FLUSH_DONE, pdTRUE, pdFALSE, pdMS_TO_TICKS(20));
        if (!(bits & WAIT_FLUSH_DONE)) {
            ESP_LOGW(TAG, "Flush timeout for split %d - continuing anyway to prevent deadlock", split);
            // Set the bit manually to prevent deadlock
            xEventGroupSetBits(ctx->events.event_group, WAIT_FLUSH_DONE);
        }
        ESP_LOGI(TAG, "Flush done for split %d", split);
    }
    
    ESP_LOGI(TAG, "All splits processed, cleaning up");

    // Cleanup (buffers are reused, only free offsets)
    ESP_LOGI(TAG, "Freeing offsets and header");
    free(offsets);
    anim_dec_free_header(header);
    ESP_LOGI(TAG, "Frame parse complete, returning ESP_OK");

    return ESP_OK;
}

static void anim_player_task(void *arg)
{
    anim_player_context_t *ctx = (anim_player_context_t *)arg;
    anim_player_run_ctx_t run_ctx;
    anim_player_event_t player_event;
    
    // Allocate header on heap to reduce stack usage
    image_header_t *header = (image_header_t *)malloc(sizeof(image_header_t));
    if (header == NULL) {
        ESP_LOGE(TAG, "Failed to allocate header on heap");
        return;
    }
    // Initialize header to zero to ensure all pointers are NULL
    memset(header, 0, sizeof(image_header_t));

    run_ctx.action = PLAYER_ACTION_STOP;
    run_ctx.run_start = ctx->run_start;
    run_ctx.run_end = ctx->run_end;
    run_ctx.repeat = ctx->repeat;
    run_ctx.fps = ctx->fps;
    run_ctx.last_frame_time = esp_timer_get_time();

    while (1) {
        EventBits_t bits = xEventGroupWaitBits(ctx->events.event_group,
                                               NEED_DELETE | WAIT_STOP,
                                               pdTRUE, pdFALSE, pdMS_TO_TICKS(10));

        if (bits & NEED_DELETE) {
            ESP_LOGW(TAG, "Player deleted");
            xEventGroupSetBits(ctx->events.event_group, DELETE_DONE);
            vTaskDeleteWithCaps(NULL);
        }

        if (bits & WAIT_STOP) {
            xEventGroupSetBits(ctx->events.event_group, WAIT_STOP_DONE);
        }

        // Check for new events in queue
        if (xQueueReceive(ctx->events.event_queue, &player_event, 0) == pdTRUE) {
            run_ctx.action = player_event.action;
            run_ctx.run_start = ctx->run_start;
            run_ctx.run_end = ctx->run_end;
            run_ctx.repeat = ctx->repeat;
            run_ctx.fps = ctx->fps;
            ESP_LOGD(TAG, "Player updated [%s]: %d -> %d, repeat:%d, fps:%d",
                     run_ctx.action == PLAYER_ACTION_START ? "START" : "STOP",
                     run_ctx.run_start, run_ctx.run_end, run_ctx.repeat, run_ctx.fps);
        }

        if (run_ctx.action == PLAYER_ACTION_STOP) {
            continue;
        }

        // Process animation frames
        int consecutive_failures = 0;
        const int MAX_CONSECUTIVE_FAILURES = 5;  // Stop after 5 consecutive failures
        do {
            for (int i = run_ctx.run_start; (i <= run_ctx.run_end) && (run_ctx.action != PLAYER_ACTION_STOP); i++) {
                // Frame rate control
                int64_t elapsed = esp_timer_get_time() - run_ctx.last_frame_time;
                elapsed = elapsed / 1000;
                if (elapsed < FPS_TO_MS(run_ctx.fps)) {
                    vTaskDelay(pdMS_TO_TICKS(FPS_TO_MS(run_ctx.fps) - elapsed));
                    ESP_LOGD(TAG, "delay: %d ms", (int)(FPS_TO_MS(run_ctx.fps) - elapsed));
                }
                run_ctx.last_frame_time = esp_timer_get_time();

                // Check for new events or delete request
                bits = xEventGroupWaitBits(ctx->events.event_group,
                                           NEED_DELETE | WAIT_STOP,
                                           pdTRUE, pdFALSE, pdMS_TO_TICKS(0));
                if (bits & NEED_DELETE) {
                    ESP_LOGW(TAG, "Playing deleted");
                    xEventGroupSetBits(ctx->events.event_group, DELETE_DONE);
                    vTaskDelete(NULL);
                }
                if (bits & WAIT_STOP) {
                    xEventGroupSetBits(ctx->events.event_group, WAIT_STOP_DONE);
                }

                if (xQueueReceive(ctx->events.event_queue, &player_event, 0) == pdTRUE) {
                    run_ctx.action = player_event.action;
                    run_ctx.run_start = ctx->run_start;
                    run_ctx.run_end = ctx->run_end;
                    run_ctx.fps = ctx->fps;
                    if (run_ctx.action == PLAYER_ACTION_STOP) {
                        run_ctx.repeat = false;
                    } else {
                        run_ctx.repeat = ctx->repeat;
                    }

                    ESP_LOGD(TAG, "Playing updated [%s]: %d -> %d, repeat:%d, fps:%d",
                             run_ctx.action == PLAYER_ACTION_START ? "START" : "STOP",
                             run_ctx.run_start, run_ctx.run_end, run_ctx.repeat, run_ctx.fps);
                    break;
                }

                const void *frame_data = anim_vfs_get_frame_data(ctx->info.file_desc, i);
                size_t frame_size = anim_vfs_get_frame_size(ctx->info.file_desc, i);

                // Free any previous header allocations before parsing new frame
                anim_dec_free_header(header);
                image_format_t format = anim_dec_parse_header(frame_data, frame_size, header);

                if (format == IMAGE_FORMAT_INVALID) {
                    ESP_LOGE(TAG, "Invalid frame format");
                    // Header allocations already freed by anim_dec_free_header above
                    continue;
                } else if (format == IMAGE_FORMAT_REDIRECT) {
                    ESP_LOGE(TAG, "Invalid redirect frame");
                    // Free header allocations before continuing
                    anim_dec_free_header(header);
                    continue;
                } else if (format == IMAGE_FORMAT_SBMP) {
                    esp_err_t parse_result = anim_player_parse(frame_data, frame_size, header, ctx);
                    if (parse_result == ESP_OK) {
                        if (ctx->update_cb) {
                            ctx->update_cb(ctx, PLAYER_EVENT_ONE_FRAME_DONE);
                        }
                        // Header is freed inside anim_player_parse on success
                        // Reset failure counter on successful frame
                        consecutive_failures = 0;
                    } else {
                        ESP_LOGE(TAG, "Failed to parse frame %d, skipping", i);
                        // Free header allocations before continuing to next frame
                        anim_dec_free_header(header);
                        consecutive_failures++;
                        if (consecutive_failures >= MAX_CONSECUTIVE_FAILURES) {
                            ESP_LOGE(TAG, "Too many consecutive frame parse failures (%d), stopping animation", consecutive_failures);
                            run_ctx.action = PLAYER_ACTION_STOP;
                            run_ctx.repeat = false;
                            break;
                        }
                        continue;
                    }
                }
            }
            if (ctx->update_cb) {
                ctx->update_cb(ctx, PLAYER_EVENT_ALL_FRAME_DONE);
            }
            // Reset failure counter at end of loop iteration
            consecutive_failures = 0;
        } while (run_ctx.repeat);

        run_ctx.action = PLAYER_ACTION_STOP;

        if (ctx->update_cb) {
            ctx->update_cb(ctx, PLAYER_EVENT_IDLE);
        }
    }
    
    // Free header before task exits
    if (header) {
        free(header);
    }
}

bool anim_player_flush_ready(anim_player_handle_t handle)
{
    anim_player_context_t *ctx = (anim_player_context_t *)handle;
    if (ctx == NULL) {
        return false;
    }

    if (xPortInIsrContext()) {
        BaseType_t pxHigherPriorityTaskWoken = pdFALSE;
        bool result = xEventGroupSetBitsFromISR(ctx->events.event_group, WAIT_FLUSH_DONE, &pxHigherPriorityTaskWoken);
        if (pxHigherPriorityTaskWoken == pdTRUE) {
            portYIELD_FROM_ISR();
        }
        return result;
    } else {
        return xEventGroupSetBits(ctx->events.event_group, WAIT_FLUSH_DONE);
    }
}

void anim_player_update(anim_player_handle_t handle, player_action_t event)
{
    anim_player_context_t *ctx = (anim_player_context_t *)handle;
    if (ctx == NULL) {
        ESP_LOGE(TAG, "Invalid player context");
        return;
    }

    anim_player_event_t player_event = {
        .action = event,
    };

    if (xQueueSend(ctx->events.event_queue, &player_event, pdMS_TO_TICKS(10)) != pdTRUE) {
        ESP_LOGE(TAG, "Failed to send event to queue");
    }
    ESP_LOGD(TAG, "update event: %s", event == PLAYER_ACTION_START ? "START" : "STOP");
}

esp_err_t anim_player_set_src_data(anim_player_handle_t handle, const void *src_data, size_t src_len)
{
    anim_player_context_t *ctx = (anim_player_context_t *)handle;
    if (ctx == NULL) {
        ESP_LOGE(TAG, "Invalid player context");
        return ESP_FAIL;
    }

    anim_vfs_handle_t new_desc;
    anim_vfs_init(src_data, src_len, &new_desc);
    if (new_desc == NULL) {
        ESP_LOGE(TAG, "Failed to initialize asset parser");
        return ESP_FAIL;
    }

    anim_player_update(handle, PLAYER_ACTION_STOP);
    xEventGroupSetBits(ctx->events.event_group, WAIT_STOP);
    xEventGroupWaitBits(ctx->events.event_group, WAIT_STOP_DONE, pdTRUE, pdFALSE, portMAX_DELAY);

    //delete old file_desc
    if (ctx->info.file_desc) {
        anim_vfs_deinit(ctx->info.file_desc);
        ctx->info.file_desc = NULL;
    }

    ctx->info.file_desc = new_desc;
    ctx->info.start = 0;
    ctx->info.end = anim_vfs_get_total_frames(new_desc) - 1;

    //default segment
    ctx->run_start = ctx->info.start;
    ctx->run_end = ctx->info.end;
    ctx->repeat = true;
    ctx->fps = CONFIG_ANIM_PLAYER_DEFAULT_FPS;

    return ESP_OK;
}

void anim_player_get_segment(anim_player_handle_t handle, uint32_t *start, uint32_t *end)
{
    anim_player_context_t *ctx = (anim_player_context_t *)handle;
    if (ctx == NULL) {
        ESP_LOGE(TAG, "Invalid player context");
        return;
    }

    *start = ctx->info.start;
    *end = ctx->info.end;
}

void anim_player_set_segment(anim_player_handle_t handle, uint32_t start, uint32_t end, uint32_t fps, bool repeat)
{
    anim_player_context_t *ctx = (anim_player_context_t *)handle;
    if (ctx == NULL) {
        ESP_LOGE(TAG, "Invalid player context");
        return;
    }

    if (end > ctx->info.end || (start > end)) {
        ESP_LOGE(TAG, "Invalid segment");
        return;
    }

    ctx->run_start = start;
    ctx->run_end = end;
    ctx->repeat = repeat;
    ctx->fps = fps;
    ESP_LOGD(TAG, "set segment: %" PRIu32 " -> %" PRIu32 ", repeat:%d, fps:%" PRIu32 "", start, end, repeat, fps);
}

void *anim_player_get_user_data(anim_player_handle_t handle)
{
    anim_player_context_t *ctx = (anim_player_context_t *)handle;
    if (ctx == NULL) {
        ESP_LOGE(TAG, "Invalid player context");
        return NULL;
    }

    return ctx->user_data;
}

anim_player_handle_t anim_player_init(const anim_player_config_t *config)
{
    if (!config) {
        ESP_LOGE(TAG, "Invalid configuration");
        return NULL;
    }

    anim_player_context_t *player = malloc(sizeof(anim_player_context_t));
    if (!player) {
        ESP_LOGE(TAG, "Failed to allocate player context");
        return NULL;
    }

    player->info.file_desc = NULL;
    player->info.start = 0;
    player->info.end = 0;
    player->run_start = 0;
    player->run_end = 0;
    player->repeat = false;
    player->fps = CONFIG_ANIM_PLAYER_DEFAULT_FPS;
    player->flush_cb = config->flush_cb;
    player->update_cb = config->update_cb;
    player->user_data = config->user_data;
    player->flags.swap = config->flags.swap;
    player->events.event_group = xEventGroupCreate();
    player->events.event_queue = xQueueCreate(5, sizeof(anim_player_event_t));
    
    // Initialize reusable buffers to NULL
    player->frame_buffer = NULL;
    player->decode_buffer = NULL;
    player->huffman_buffer = NULL;
    player->frame_buffer_size = 0;
    player->decode_buffer_size = 0;
    player->huffman_buffer_size = 0;
    player->color_cache = NULL;
    player->color_cache_size = 0;

    // Pre-allocate buffers for maximum expected size (360x360) BEFORE LVGL fragments SPIRAM
    // This ensures we get contiguous SPIRAM allocation, matching Waveshare's advantage
    // Max sizes: decode_buffer = 360*360 = 129600 bytes (8-bit), frame_buffer = 360*360*2 = 259200 bytes (RGB565)
    const size_t max_decode_size = 360 * 360;  // 8-bit worst case
    const size_t max_frame_size = 360 * 360 * sizeof(uint16_t);  // RGB565
    
    // Check SPIRAM availability before allocation
    size_t spiram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t spiram_largest = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
    ESP_LOGI(TAG, "Pre-allocating buffers: decode=%zu, frame=%zu, SPIRAM free=%zu (largest=%zu)",
             max_decode_size, max_frame_size, spiram_free, spiram_largest);
    
    // ESP-IDF best practice: Allocate LARGER buffers FIRST to minimize fragmentation
    // This ensures the largest contiguous block is used for the largest allocation
    // Try SPIRAM first for frame buffer (larger, allocate first)
    if (spiram_largest >= max_frame_size) {
        player->frame_buffer = heap_caps_malloc(max_frame_size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (player->frame_buffer != NULL) {
            player->frame_buffer_size = max_frame_size;
            ESP_LOGI(TAG, "Pre-allocated frame buffer (%zu bytes) from SPIRAM", max_frame_size);
        }
    }
    
    // Fallback to default heap if SPIRAM failed
    if (player->frame_buffer == NULL) {
        player->frame_buffer = malloc(max_frame_size);
        if (player->frame_buffer != NULL) {
            player->frame_buffer_size = max_frame_size;
            ESP_LOGW(TAG, "Pre-allocated frame buffer (%zu bytes) from default heap (SPIRAM may be fragmented)", max_frame_size);
        } else {
            ESP_LOGE(TAG, "Failed to pre-allocate frame buffer (%zu bytes)", max_frame_size);
            // Continue anyway - will try to allocate later during frame parsing
        }
    }
    
    // Decode buffer: Don't pre-allocate - use lazy allocation during frame parsing
    // Reason: After allocating frame buffer, there isn't enough contiguous memory for decode buffer
    // By allocating on-demand, we can try different strategies or memory may have freed up
    // This is the BEST fix: pre-allocate only frame buffer (always needed), decode buffer allocates when needed
    player->decode_buffer = NULL;
    player->decode_buffer_size = 0;
    ESP_LOGI(TAG, "Decode buffer will be allocated on-demand during frame parsing (lazy allocation)");

    // Set default task configuration if not specified
    const uint32_t caps = config->task.task_stack_caps ? config->task.task_stack_caps : MALLOC_CAP_DEFAULT; // caps cannot be zero
    if (config->task.task_affinity < 0) {
        xTaskCreateWithCaps(anim_player_task, "Anim Player", config->task.task_stack, player, config->task.task_priority, &player->handle_task, caps);
    } else {
        xTaskCreatePinnedToCoreWithCaps(anim_player_task, "Anim Player", config->task.task_stack, player, config->task.task_priority, &player->handle_task, config->task.task_affinity, caps);
    }

    return (anim_player_handle_t)player;
}

void anim_player_deinit(anim_player_handle_t handle)
{
    anim_player_context_t *ctx = (anim_player_context_t *)handle;
    if (ctx == NULL) {
        ESP_LOGE(TAG, "Invalid player context");
        return;
    }

    // Send event to stop the task
    if (ctx->events.event_group) {
        xEventGroupSetBits(ctx->events.event_group, NEED_DELETE);
        xEventGroupWaitBits(ctx->events.event_group, DELETE_DONE, pdTRUE, pdFALSE, portMAX_DELAY);
    }

    // Delete event group
    if (ctx->events.event_group) {
        vEventGroupDelete(ctx->events.event_group);
        ctx->events.event_group = NULL;
    }

    // Delete event queue
    if (ctx->events.event_queue) {
        vQueueDelete(ctx->events.event_queue);
        ctx->events.event_queue = NULL;
    }

    if (ctx->info.file_desc) {
        anim_vfs_deinit(ctx->info.file_desc);
        ctx->info.file_desc = NULL;
    }

    // Free reusable buffers
    anim_player_free_buffers(ctx);

    // Free player context
    free(ctx);
}
