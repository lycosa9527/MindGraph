# PNG Export Fix - Dynamic Renderer Loader Issue

## Problem

The `/api/export_png` endpoint was failing with error:
```
Error: Dynamic renderer loader is required but not available. Cannot render bubble_map.
```

## Root Cause Analysis

1. **Missing Dependency**: The `export_png` endpoint loads scripts via HTTP URLs but was missing `dynamic-renderer-loader.js` in the scripts array.

2. **Dependency Chain**: 
   - `renderer-dispatcher.js` requires `window.dynamicRendererLoader` (line 44)
   - `dynamic-renderer-loader.js` creates `window.dynamicRendererLoader` (line 237)
   - `dynamic-renderer-loader.js` requires `logger` (used throughout)
   
3. **Load Order Issue**: Scripts must load in this order:
   - logger.js (first - required by dynamic-renderer-loader)
   - dynamic-renderer-loader.js (before renderer-dispatcher)
   - renderer-dispatcher.js (uses dynamicRendererLoader)

4. **Port Mismatch**: Default port was 5000 but server runs on 9527, causing script load failures.

## Fixes Applied

### 1. Added Missing Script
```javascript
// Added to scripts array:
'{base_url}/static/js/dynamic-renderer-loader.js',  // REQUIRED: renderer-dispatcher depends on this
```

### 2. Fixed Load Order
```javascript
const scripts = [
    '{base_url}/static/js/theme-config.js',
    '{base_url}/static/js/style-manager.js',
    '{base_url}/static/js/logger.js',                    // First - required by dynamic-renderer-loader
    '{base_url}/static/js/dynamic-renderer-loader.js',   // Before renderer-dispatcher
    '{base_url}/static/js/renderers/shared-utilities.js',
    '{base_url}/static/js/renderers/renderer-dispatcher.js'  // Uses dynamicRendererLoader
];
```

### 3. Fixed Port Default
```python
# Changed from:
port = os.getenv('PORT', '5000')

# To:
port = os.getenv('PORT', '9527')  # Match standard dev port
```

### 4. Added Base URL Detection
```python
# Now uses request URL to detect correct host/port (handles reverse proxies)
try:
    request_url = str(request.url)
    parsed = urlparse(request_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
except Exception:
    port = os.getenv('PORT', '9527')
    base_url = f"http://localhost:{port}"
```

### 5. Added Verification and Retry Logic
```javascript
// Wait for scripts to initialize
await new Promise(resolve => setTimeout(resolve, 200));

// Retry check for dynamicRendererLoader
let retries = 5;
while (typeof window.dynamicRendererLoader === 'undefined' && retries > 0) {
    await new Promise(resolve => setTimeout(resolve, 200));
    retries--;
}
```

## Testing

After restarting the server, test the `/api/export_png` endpoint manually or with your preferred testing tool.

Expected: `/api/export_png` should now return 200 OK with PNG image data.

## Notes

- Server restart required for changes to take effect
- Scripts load sequentially with 100ms delay between each
- Additional 200ms wait + retry logic ensures initialization completes
- Base URL now auto-detects from request (works with reverse proxies)


