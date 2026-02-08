# Quick Test Guide

## Fastest Way to Test Memory Leak Fixes

### 1. Build Test App (5 minutes)

```powershell
cd esp32\firmware\managed_components\espressif2022__image_player\test_apps
& C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562
idf.py build
```

### 2. Flash & Monitor

```powershell
idf.py flash monitor
```

### 3. What to Look For

**✅ Good Signs:**
- No "Failed to allocate" errors after initial frames
- Memory stays stable: `Available memory - Default: ~XXXXX bytes` (consistent)
- No stack overflow errors
- Tests complete successfully

**❌ Bad Signs:**
- Memory decreasing: `Default: 90852 -> 81456 -> ...` (decreasing)
- Multiple "Failed to allocate decode buffer" errors
- Stack overflow in main task
- Unity test reports memory leaks > 500 bytes

### 4. Expected Test Output

```
I (1234) player: Flush: (000,000) (240,135)
I (1234) player: Event: ALL_FRAME_DONE
I (5678) player: Event: IDLE
...
I (9999) player: test done
```

**Memory should be stable throughout!**

### 5. Key Fixes Being Tested

1. ✅ Header allocations freed on errors
2. ✅ Partial buffer allocations cleaned up
3. ✅ Huffman buffer reused (no per-split allocation)
4. ✅ SPIRAM checked before allocation
5. ✅ Iterative tree freeing (no stack overflow)
6. ✅ Stops after 5 consecutive failures

### 6. Manual Memory Check

In monitor, you can also manually check memory:

```c
// Add this to test code temporarily:
size_t mem_before = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
// ... play animation ...
size_t mem_after = heap_caps_get_free_size(MALLOC_CAP_DEFAULT);
ESP_LOGI("TEST", "Memory: before=%zu, after=%zu, diff=%zu", 
         mem_before, mem_after, mem_before - mem_after);
// diff should be < 1000 bytes (small tolerance)
```

### 7. If Tests Pass

✅ Memory leaks fixed!
✅ Ready to integrate into main firmware

### 8. If Tests Fail

Check:
- Are all `anim_dec_free_header()` calls in place?
- Is `huffman_buffer` being reused?
- Are buffers freed on allocation failure?
- Check stack sizes in sdkconfig
