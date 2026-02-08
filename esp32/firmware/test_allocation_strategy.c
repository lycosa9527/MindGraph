/*
 * Standalone test to verify SPIRAM allocation strategy
 * Compile: gcc -o test_allocation test_allocation_strategy.c -lm
 * Run: ./test_allocation
 */

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

// Simulate memory state
typedef struct {
    size_t spiram_free;
    size_t spiram_largest;
    size_t internal_free;
    size_t internal_largest;
    size_t default_free;
    size_t default_largest;
} memory_state_t;

// Simulate allocation results
typedef struct {
    void *frame_buffer;
    void *decode_buffer;
    bool frame_from_spiram;
    bool decode_from_default;
    bool success;
} allocation_result_t;

// Test allocation strategy
allocation_result_t test_allocation_strategy(memory_state_t *mem) {
    allocation_result_t result = {0};
    
    const size_t max_decode_size = 360 * 360;  // 129600 bytes
    const size_t max_frame_size = 360 * 360 * sizeof(uint16_t);  // 259200 bytes
    
    printf("\n=== Testing Allocation Strategy ===\n");
    printf("Memory state:\n");
    printf("  SPIRAM free: %zu bytes, largest: %zu bytes\n", mem->spiram_free, mem->spiram_largest);
    printf("  Internal free: %zu bytes, largest: %zu bytes\n", mem->internal_free, mem->internal_largest);
    printf("  Default free: %zu bytes, largest: %zu bytes\n", mem->default_free, mem->default_largest);
    printf("\nBuffer requirements:\n");
    printf("  Frame buffer: %zu bytes\n", max_frame_size);
    printf("  Decode buffer: %zu bytes\n", max_decode_size);
    printf("  Total needed: %zu bytes\n", max_frame_size + max_decode_size);
    
    // Strategy: Frame buffer from SPIRAM first (larger)
    printf("\n--- Step 1: Allocate frame buffer from SPIRAM ---\n");
    if (mem->spiram_largest >= max_frame_size) {
        result.frame_buffer = malloc(max_frame_size);  // Simulate allocation
        if (result.frame_buffer != NULL) {
            result.frame_from_spiram = true;
            mem->spiram_free -= max_frame_size;
            // Simulate fragmentation: reduce largest block
            mem->spiram_largest = mem->spiram_free - (rand() % 50000);  // Simulate fragmentation
            if (mem->spiram_largest < 0) mem->spiram_largest = 0;
            printf("  ✓ Frame buffer allocated from SPIRAM (%zu bytes)\n", max_frame_size);
            printf("  Remaining SPIRAM: free=%zu, largest=%zu\n", mem->spiram_free, mem->spiram_largest);
        } else {
            printf("  ✗ Frame buffer allocation failed from SPIRAM\n");
        }
    } else {
        printf("  ✗ SPIRAM largest block (%zu) < frame buffer (%zu)\n", mem->spiram_largest, max_frame_size);
    }
    
    // Fallback: Frame buffer from default heap
    if (result.frame_buffer == NULL) {
        printf("\n--- Step 1b: Fallback - frame buffer from default heap ---\n");
        if (mem->default_largest >= max_frame_size) {
            result.frame_buffer = malloc(max_frame_size);
            if (result.frame_buffer != NULL) {
                mem->default_free -= max_frame_size;
                printf("  ✓ Frame buffer allocated from default heap (%zu bytes)\n", max_frame_size);
            } else {
                printf("  ✗ Frame buffer allocation failed from default heap\n");
            }
        } else {
            printf("  ✗ Default heap largest block (%zu) < frame buffer (%zu)\n", mem->default_largest, max_frame_size);
        }
    }
    
    // Strategy: Decode buffer from default heap (flexible)
    printf("\n--- Step 2: Allocate decode buffer from default heap ---\n");
    if (mem->default_largest >= max_decode_size || mem->internal_largest >= max_decode_size) {
        result.decode_buffer = malloc(max_decode_size);
        if (result.decode_buffer != NULL) {
            result.decode_from_default = true;
            // Default heap can use internal RAM or SPIRAM fragments
            if (mem->internal_largest >= max_decode_size) {
                mem->internal_free -= max_decode_size;
                printf("  ✓ Decode buffer allocated from default heap (using internal RAM, %zu bytes)\n", max_decode_size);
            } else {
                mem->default_free -= max_decode_size;
                printf("  ✓ Decode buffer allocated from default heap (using SPIRAM fragments, %zu bytes)\n", max_decode_size);
            }
        } else {
            printf("  ✗ Decode buffer allocation failed from default heap\n");
        }
    } else {
        printf("  ✗ Default heap insufficient (largest=%zu) < decode buffer (%zu)\n", 
               mem->default_largest > mem->internal_largest ? mem->default_largest : mem->internal_largest, 
               max_decode_size);
    }
    
    // Check success
    result.success = (result.frame_buffer != NULL && result.decode_buffer != NULL);
    
    printf("\n=== Result ===\n");
    if (result.success) {
        printf("✓ SUCCESS: Both buffers allocated\n");
        printf("  Frame buffer: %s (%p)\n", result.frame_from_spiram ? "SPIRAM" : "default heap", result.frame_buffer);
        printf("  Decode buffer: %s (%p)\n", result.decode_from_default ? "default heap" : "unknown", result.decode_buffer);
    } else {
        printf("✗ FAILED: Buffer allocation incomplete\n");
        if (result.frame_buffer == NULL) printf("  - Frame buffer not allocated\n");
        if (result.decode_buffer == NULL) printf("  - Decode buffer not allocated\n");
    }
    
    // Cleanup
    if (result.frame_buffer) free(result.frame_buffer);
    if (result.decode_buffer) free(result.decode_buffer);
    
    return result;
}

int main() {
    printf("SPIRAM Allocation Strategy Test\n");
    printf("===============================\n");
    
    // Test Case 1: Your actual scenario (from logs)
    printf("\n\nTEST CASE 1: Your actual scenario\n");
    printf("===================================\n");
    memory_state_t scenario1 = {
        .spiram_free = 362736,
        .spiram_largest = 352256,
        .internal_free = 114483,
        .internal_largest = 69632,
        .default_free = 210836,
        .default_largest = 92160
    };
    allocation_result_t result1 = test_allocation_strategy(&scenario1);
    
    // Test Case 2: Better SPIRAM state (more contiguous)
    printf("\n\nTEST CASE 2: Better SPIRAM state\n");
    printf("===================================\n");
    memory_state_t scenario2 = {
        .spiram_free = 500000,
        .spiram_largest = 450000,
        .internal_free = 114483,
        .internal_largest = 69632,
        .default_free = 210836,
        .default_largest = 92160
    };
    allocation_result_t result2 = test_allocation_strategy(&scenario2);
    
    // Test Case 3: Worst case (highly fragmented)
    printf("\n\nTEST CASE 3: Worst case (highly fragmented)\n");
    printf("=============================================\n");
    memory_state_t scenario3 = {
        .spiram_free = 400000,
        .spiram_largest = 200000,  // Too small for frame buffer
        .internal_free = 114483,
        .internal_largest = 69632,
        .default_free = 300000,
        .default_largest = 150000
    };
    allocation_result_t result3 = test_allocation_strategy(&scenario3);
    
    // Summary
    printf("\n\n=== SUMMARY ===\n");
    printf("Test Case 1 (Your scenario): %s\n", result1.success ? "PASS" : "FAIL");
    printf("Test Case 2 (Better SPIRAM): %s\n", result2.success ? "PASS" : "FAIL");
    printf("Test Case 3 (Worst case):    %s\n", result3.success ? "PASS" : "FAIL");
    
    return 0;
}
