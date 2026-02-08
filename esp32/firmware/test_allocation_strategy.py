#!/usr/bin/env python3
"""
Standalone test to verify SPIRAM allocation strategy
Run: python test_allocation_strategy.py
"""

import random

class MemoryState:
    def __init__(self, spiram_free, spiram_largest, internal_free, internal_largest, default_free, default_largest):
        self.spiram_free = spiram_free
        self.spiram_largest = spiram_largest
        self.internal_free = internal_free
        self.internal_largest = internal_largest
        self.default_free = default_free
        self.default_largest = default_largest

class AllocationResult:
    def __init__(self):
        self.frame_buffer = None
        self.decode_buffer = None
        self.frame_from_spiram = False
        self.decode_from_default = False
        self.success = False

def test_allocation_strategy(mem, test_name):
    result = AllocationResult()
    
    max_decode_size = 360 * 360  # 129600 bytes
    max_frame_size = 360 * 360 * 2  # 259200 bytes (RGB565)
    
    print(f"\n=== {test_name} ===")
    print(f"Memory state:")
    print(f"  SPIRAM free: {mem.spiram_free:,} bytes, largest: {mem.spiram_largest:,} bytes")
    print(f"  Internal free: {mem.internal_free:,} bytes, largest: {mem.internal_largest:,} bytes")
    print(f"  Default free: {mem.default_free:,} bytes, largest: {mem.default_largest:,} bytes")
    print(f"\nBuffer requirements:")
    print(f"  Frame buffer: {max_frame_size:,} bytes")
    print(f"  Decode buffer: {max_decode_size:,} bytes")
    print(f"  Total needed: {max_frame_size + max_decode_size:,} bytes")
    
    # Strategy: Frame buffer from SPIRAM first (larger)
    print(f"\n--- Step 1: Allocate frame buffer from SPIRAM ---")
    if mem.spiram_largest >= max_frame_size:
        # Simulate successful allocation
        result.frame_buffer = "allocated"
        result.frame_from_spiram = True
        mem.spiram_free -= max_frame_size
        # Simulate fragmentation: reduce largest block
        mem.spiram_largest = max(0, mem.spiram_free - random.randint(0, 50000))
        print(f"  [OK] Frame buffer allocated from SPIRAM ({max_frame_size:,} bytes)")
        print(f"  Remaining SPIRAM: free={mem.spiram_free:,}, largest={mem.spiram_largest:,}")
    else:
        print(f"  [FAIL] SPIRAM largest block ({mem.spiram_largest:,}) < frame buffer ({max_frame_size:,})")
    
    # Fallback: Frame buffer from default heap
    if result.frame_buffer is None:
        print(f"\n--- Step 1b: Fallback - frame buffer from default heap ---")
        if mem.default_largest >= max_frame_size:
            result.frame_buffer = "allocated"
            mem.default_free -= max_frame_size
            print(f"  [OK] Frame buffer allocated from default heap ({max_frame_size:,} bytes)")
        else:
            print(f"  [FAIL] Default heap largest block ({mem.default_largest:,}) < frame buffer ({max_frame_size:,})")
    
    # Strategy: Decode buffer from default heap (flexible)
    print(f"\n--- Step 2: Allocate decode buffer from default heap ---")
    # ESP-IDF default heap can allocate from internal RAM OR SPIRAM fragments
    # It tries internal RAM first, then SPIRAM
    # But it still needs contiguous memory in the chosen region
    
    # Try internal RAM first (if large enough)
    if mem.internal_largest >= max_decode_size:
        result.decode_buffer = "allocated"
        result.decode_from_default = True
        mem.internal_free -= max_decode_size
        print(f"  [OK] Decode buffer allocated from default heap (using internal RAM, {max_decode_size:,} bytes)")
    # Try SPIRAM fragments (remaining after frame buffer)
    elif mem.spiram_largest >= max_decode_size:
        result.decode_buffer = "allocated"
        result.decode_from_default = True
        mem.spiram_free -= max_decode_size
        mem.spiram_largest = max(0, mem.spiram_largest - max_decode_size - random.randint(0, 10000))
        print(f"  [OK] Decode buffer allocated from default heap (using SPIRAM fragments, {max_decode_size:,} bytes)")
    # Try default heap (which might combine sources, but realistically needs contiguous block)
    elif mem.default_largest >= max_decode_size:
        result.decode_buffer = "allocated"
        result.decode_from_default = True
        mem.default_free -= max_decode_size
        print(f"  [OK] Decode buffer allocated from default heap ({max_decode_size:,} bytes)")
    else:
        print(f"  [FAIL] Default heap insufficient:")
        print(f"    - Internal RAM largest: {mem.internal_largest:,} < {max_decode_size:,}")
        print(f"    - SPIRAM largest: {mem.spiram_largest:,} < {max_decode_size:,}")
        print(f"    - Default heap largest: {mem.default_largest:,} < {max_decode_size:,}")
    
    # Check success
    result.success = (result.frame_buffer is not None and result.decode_buffer is not None)
    
    print(f"\n=== Result ===")
    if result.success:
        print(f"[SUCCESS] Both buffers allocated")
        print(f"  Frame buffer: {'SPIRAM' if result.frame_from_spiram else 'default heap'}")
        print(f"  Decode buffer: {'default heap' if result.decode_from_default else 'unknown'}")
    else:
        print(f"[FAILED] Buffer allocation incomplete")
        if result.frame_buffer is None:
            print(f"  - Frame buffer not allocated")
        if result.decode_buffer is None:
            print(f"  - Decode buffer not allocated")
    
    return result

def main():
    print("SPIRAM Allocation Strategy Test")
    print("=" * 40)
    
    # Test Case 1: Your actual scenario (from logs)
    print("\n\nTEST CASE 1: Your actual scenario")
    print("=" * 40)
    scenario1 = MemoryState(
        spiram_free=362736,
        spiram_largest=352256,
        internal_free=114483,
        internal_largest=69632,
        default_free=210836,
        default_largest=92160
    )
    result1 = test_allocation_strategy(scenario1, "Your actual scenario")
    
    # Test Case 2: Better SPIRAM state (more contiguous)
    print("\n\nTEST CASE 2: Better SPIRAM state")
    print("=" * 40)
    scenario2 = MemoryState(
        spiram_free=500000,
        spiram_largest=450000,
        internal_free=114483,
        internal_largest=69632,
        default_free=210836,
        default_largest=92160
    )
    result2 = test_allocation_strategy(scenario2, "Better SPIRAM state")
    
    # Test Case 3: Worst case (highly fragmented)
    print("\n\nTEST CASE 3: Worst case (highly fragmented)")
    print("=" * 40)
    scenario3 = MemoryState(
        spiram_free=400000,
        spiram_largest=200000,  # Too small for frame buffer
        internal_free=114483,
        internal_largest=69632,
        default_free=300000,
        default_largest=150000
    )
    result3 = test_allocation_strategy(scenario3, "Worst case")
    
    # Summary
    print("\n\n=== SUMMARY ===")
    print(f"Test Case 1 (Your scenario): {'PASS' if result1.success else 'FAIL'}")
    print(f"Test Case 2 (Better SPIRAM): {'PASS' if result2.success else 'FAIL'}")
    print(f"Test Case 3 (Worst case):    {'PASS' if result3.success else 'FAIL'}")
    
    if result1.success:
        print("\n[SUCCESS] Fix should work for your scenario!")
    else:
        print("\n[FAILED] Fix may not work - need alternative strategy")

if __name__ == "__main__":
    main()
