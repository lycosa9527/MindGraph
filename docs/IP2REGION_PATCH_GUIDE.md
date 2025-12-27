# IP2Region Database Patch Guide

## Overview

ip2region provides patches and fixes in the `data/fix` folder on GitHub. These patches contain corrections and updates to IP geolocation data that need to be applied to keep the database accurate.

## Patch Location

- **GitHub**: https://github.com/lionsoul2014/ip2region/tree/master/data/fix
- **Format**: Text files with IP location corrections

## How Patches Work

### Patch File Format

Patches are typically in one of these formats:

1. **Pipe-separated format**:
   ```
   IP|Country|Region|Province|City|ISP
   1.2.3.4|中国|0|北京|北京|0
   ```

2. **Tab-separated format**:
   ```
   IP<TAB>Location
   1.2.3.4<TAB>中国|北京|北京
   ```

### Applying Patches

There are several ways to apply patches:

#### Method 1: Use ip2region Maker Tools (Recommended)

ip2region provides data editor tools in the `maker/` folder:

1. **Golang Editor** (supports IPv4 and IPv6):
   ```bash
   cd ip2region/maker/golang
   # Use the editor to apply patches and rebuild xdb
   ```

2. **Java Editor** (IPv4 only):
   ```bash
   cd ip2region/maker/java
   # Use the editor to apply patches
   ```

3. **C++ Editor** (supports IPv4 and IPv6):
   ```bash
   cd ip2region/maker/cpp
   # Use the editor to apply patches
   ```

#### Method 2: Wait for Updated Releases

- ip2region releases updated xdb files periodically
- Download the latest `ip2region_v4.xdb` and `ip2region_v6.xdb`
- Replace your existing database files

#### Method 3: Manual Patch Application

1. Download patch files from: https://github.com/lionsoul2014/ip2region/tree/master/data/fix
2. Review patches for your use case
3. Use ip2region maker tools to apply patches
4. Rebuild xdb database files

## Automated Patch Checking

We provide a script to check and download patches:

```bash
python scripts/apply_ip2region_patches.py
```

This script:
- Fetches patch files from GitHub
- Downloads them to `data/ip2region_patches/`
- Logs patches for reference
- Provides instructions for applying patches

## Current Implementation

Our system:
- ✅ Loads xdb databases from `data/ip2region_v4.xdb` and `data/ip2region_v6.xdb`
- ✅ Supports both IPv4 and IPv6
- ✅ Checks database age and warns if outdated
- ⚠️ Patches need to be applied manually using ip2region tools

## Recommendations

1. **Regular Updates**: Update databases monthly or when patches are released
2. **Monitor Patches**: Check the fix folder periodically for important corrections
3. **Use Maker Tools**: Apply patches using official ip2region maker tools for best results
4. **Backup**: Always backup your database files before applying patches

## References

- ip2region Repository: https://github.com/lionsoul2014/ip2region
- Data Fix Folder: https://github.com/lionsoul2014/ip2region/tree/master/data/fix
- Maker Tools: https://github.com/lionsoul2014/ip2region/tree/master/maker
- Official Community: https://ip2region.net

