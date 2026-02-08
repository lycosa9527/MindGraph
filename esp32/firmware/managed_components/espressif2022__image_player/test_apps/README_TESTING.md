# Testing anim_player Module

This directory contains standalone tests for the `anim_player` module that can be run without building the entire firmware.

## Quick Start

### Option 1: Run Unity Tests (Recommended for Memory Leak Testing)

```bash
# Navigate to test directory
cd esp32/firmware/managed_components/espressif2022__image_player/test_apps

# Initialize ESP-IDF environment (if not already done)
# On Windows PowerShell:
& C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562

# Build the test app
idf.py build

# Flash and monitor (connect your ESP32-S3 device)
idf.py flash monitor
```

The test will:
- Test both 4-bit and 8-bit animations
- Automatically detect memory leaks (threshold: 500 bytes)
- Run multiple animation files sequentially
- Test init/deinit cycles

### Option 2: Run Python Pytest (Automated Testing)

```bash
# Navigate to test directory
cd esp32/firmware/managed_components/espressif2022__image_player/test_apps

# Run pytest (requires pytest-embedded)
pytest pytest_anim_player.py --target esp32s3
```

## What the Tests Cover

1. **Memory Leak Detection**: 
   - Checks for leaks in 8BIT and 32BIT heaps
   - Threshold: 500 bytes
   - Runs before/after each test case

2. **Animation Playback**:
   - Tests 4-bit and 8-bit encoded animations
   - Multiple animation files (emotions, gestures)
   - Frame-by-frame playback verification

3. **Buffer Management**:
   - Tests buffer allocation/deallocation
   - SPIRAM fallback behavior
   - Buffer reuse across frames

4. **Error Handling**:
   - Invalid frame handling
   - Memory allocation failures
   - Animation stop/start cycles

## Test Output

The tests will output:
- Memory usage before/after each test
- Frame flush events
- Animation events (IDLE, FRAME_DONE, etc.)
- Any memory leaks detected

## Expected Results After Fixes

After applying the memory leak fixes, you should see:
- ✅ No memory leaks detected
- ✅ Consistent memory usage across frames
- ✅ Successful SPIRAM allocation (when available)
- ✅ No stack overflow errors
- ✅ Proper cleanup on errors

## Troubleshooting

### If tests fail with memory leaks:
1. Check if buffers are being freed properly
2. Verify `anim_dec_free_header()` is called on all error paths
3. Check for partial allocations (frame_buffer allocated but decode_buffer failed)

### If SPIRAM allocation fails:
- This is expected if decode_buffer_size (129600) > available SPIRAM (80692)
- The code should fallback to default heap automatically
- Check logs for "SPIRAM allocation failed" warnings

### If stack overflow occurs:
- Verify iterative `free_tree()` implementation is used
- Check task stack sizes in sdkconfig
- Monitor stack usage with `uxTaskGetStackHighWaterMark()`

## Manual Testing Checklist

To manually verify fixes:

1. **Memory Leak Test**:
   ```c
   // Before animation
   size_t before = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
   
   // Play animation for 100 frames
   // ...
   
   // After animation
   size_t after = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
   // Should be: after >= before - 1000 (small tolerance)
   ```

2. **Buffer Reuse Test**:
   - Play same animation twice
   - Second playback should reuse buffers (no reallocation)
   - Check logs for buffer size messages

3. **Error Recovery Test**:
   - Simulate memory pressure
   - Verify graceful failure after 5 consecutive errors
   - Check that buffers are freed on failure

4. **SPIRAM Test**:
   - Monitor SPIRAM usage: `heap_caps_get_free_size(MALLOC_CAP_SPIRAM)`
   - Verify it only attempts SPIRAM when enough is available
   - Check fallback to default heap works

## Test Files Structure

```
test_apps/
├── main/
│   ├── test_anim_player.c      # Main test code
│   ├── mmap_generate_test_4bit.h
│   └── mmap_generate_test_8bit.h
├── test_4bit/                  # 4-bit animation test files
├── test_8bit/                  # 8-bit animation test files
├── pytest_anim_player.py       # Python test runner
└── CMakeLists.txt              # Build configuration
```

## Notes

- Tests require ESP32-S3 hardware with display
- Test animations are included in the repository
- Memory leak detection is automatic via Unity framework
- Tests can be run independently of main firmware
