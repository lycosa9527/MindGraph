#!/usr/bin/env python3
"""
Inspect AAF file header to see what settings were used
"""
import struct
import sys
import os

def inspect_aaf(filename):
    """Read AAF file header and display settings"""
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return
    
    with open(filename, 'rb') as f:
        # Read format identifier (2 bytes)
        format_bytes = f.read(2)
        if format_bytes != b'_S':
            print(f"Invalid format: {format_bytes}")
            return
        
        # Skip version (6 bytes)
        f.read(6)
        
        # Read bit depth (1 byte)
        bit_depth = struct.unpack('B', f.read(1))[0]
        
        # Read width (2 bytes, little endian)
        width = struct.unpack('<H', f.read(2))[0]
        
        # Read height (2 bytes, little endian)
        height = struct.unpack('<H', f.read(2))[0]
        
        # Read splits (2 bytes, little endian)
        splits = struct.unpack('<H', f.read(2))[0]
        
        # Read split_height (2 bytes, little endian)
        split_height = struct.unpack('<H', f.read(2))[0]
        
        print(f"File: {os.path.basename(filename)}")
        print(f"  Dimensions: {width}x{height}")
        print(f"  Bit depth: {bit_depth} ({'4-bit (16 colors)' if bit_depth == 4 else '8-bit (256 colors)'})")
        print(f"  Split height: {split_height}")
        print(f"  Number of splits: {splits}")
        print(f"  Calculated splits: {height // split_height + (1 if height % split_height else 0)}")
        print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python inspect_aaf.py <aaf_file> [<aaf_file> ...]")
        sys.exit(1)
    
    for filename in sys.argv[1:]:
        inspect_aaf(filename)
