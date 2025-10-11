# PNG Export Issues - Root Cause Analysis

**Date:** 2025-01-11  
**Status:** Analysis Complete - Ready for Fix  
**Issues:** Fixed resolution + Missing watermark

---

## Executive Summary

The PNG export endpoint (`/api/export_png`) successfully renders diagrams but has **two critical issues**:

1. **Fixed Resolution**: Canvas uses hardcoded dimensions (1200x800) instead of adapting to actual diagram content
2. **Missing Watermark**: The "MindGraph" watermark is not added to exported PNGs

Both issues stem from differences between the **editor export workflow** (client-side) and the **API export workflow** (server-side headless browser).

---

## Issue 1: Fixed Resolution Problem

### Current Behavior

```python
# routers/api.py line 275
<div id="d3-container" style="width: {req.width or 1200}px; height: {req.height or 800}px;"></div>
```

- Container div has **fixed dimensions** from request parameters
- Screenshot captures the **fixed 1200x800 container**, not the actual SVG content
- Small diagrams get unnecessary white space
- Large diagrams get clipped

### How It Should Work (Editor Workflow)

```javascript
// static/js/editor/toolbar-manager.js lines 2940-2958
const viewBox = svgClone.getAttribute('viewBox');
if (viewBox) {
    const viewBoxParts = viewBox.split(' ').map(Number);
    width = viewBoxParts[2];  // Use viewBox width
    height = viewBoxParts[3]; // Use viewBox height
}
```

**Editor export uses SVG viewBox** to determine actual content dimensions, not container size.

### Root Cause

1. **Renderers create SVG with dynamic viewBox**
   - Example: `renderBubbleMap` calculates actual content bounds
   - SVG viewBox = actual diagram size (e.g., 600x400)

2. **Container has fixed dimensions**
   - HTML div = fixed 1200x800 
   - Screenshot captures div, not viewBox content

3. **No dimension extraction before screenshot**
   - Python code doesn't read SVG viewBox before taking screenshot
   - Uses fixed container dimensions instead

### Where Dimensions Are Generated

```python
# Diagram data includes _recommended_dimensions
{
    "_recommended_dimensions": {
        "baseWidth": 600,
        "baseHeight": 300,
        "padding": 40,
        "width": 600,
        "height": 300
    }
}
```

**These are IGNORED** - the container uses `req.width or 1200` instead.

---

## Issue 2: Missing Watermark

### Current Behavior

- Renderers create SVG **without watermark**
- Comments in code say "watermark will be added during PNG export only"
- BUT: PNG export endpoint **never adds watermark**

```javascript
// static/js/renderers/bubble-map-renderer.js line 230
// Watermark removed from canvas display - will be added during PNG export only
```

**❌ This comment is misleading** - PNG export endpoint doesn't add watermark!

### How It Should Work (Editor Workflow)

```javascript
// static/js/editor/toolbar-manager.js lines 2967-2978
// Clone SVG and add watermark before export
const svgClone = svg.cloneNode(true);
const svgD3 = d3.select(svgClone);

svgD3.append('text')
    .attr('x', watermarkX)
    .attr('y', watermarkY)
    .attr('text-anchor', 'end')
    .attr('fill', '#2c3e50')
    .attr('font-size', watermarkFontSize)
    .attr('opacity', 0.8)
    .text('MindGraph');
```

**Editor clones SVG, adds watermark, then exports** - done client-side in browser.

### Root Cause

1. **Design Decision**: Renderers don't add watermarks to keep canvas clean
2. **Missing Step**: PNG export endpoint should add watermark before screenshot
3. **No Central Handler**: Unlike editor, API endpoint has no watermark injection

### Watermark Function Available

```javascript
// static/js/renderers/shared-utilities.js line 73
function addWatermark(svg, theme = null) {
    // Full implementation exists
    // Calculates position, adds text element
    // BUT: Never called by PNG export workflow
}
```

**The function exists** - just not called in PNG export flow!

---

## Code Flow Comparison

### ✅ Editor Export (Works Correctly)

```
User clicks Export
  ↓
handleExport() → fitDiagramToWindow()
  ↓
performPNGExport()
  ↓
Clone SVG → Read viewBox → Add watermark
  ↓
Create canvas with viewBox dimensions
  ↓
Draw SVG to canvas → Generate PNG → Download
```

**Key steps:**
- Uses viewBox for dimensions ✓
- Adds watermark manually ✓
- Client-side canvas conversion ✓

### ❌ API Export (Current - Has Issues)

```
POST /api/export_png
  ↓
Create HTML with FIXED container (1200x800)
  ↓
Load scripts → Render diagram
  ↓
Take screenshot of FIXED container
  ↓
Return PNG
```

**Missing steps:**
- ❌ Doesn't use viewBox - uses fixed container
- ❌ Doesn't add watermark
- ❌ Screenshot captures container, not content

---

## Step-by-Step Fix Plan

### Step 1: Add Watermark After Rendering

**Where:** `routers/api.py` in the JavaScript rendering code  
**When:** After `renderGraph()` completes, before screenshot

```javascript
// After checkRendering() confirms SVG exists
const svg = d3.select('#d3-container svg');
if (svg && typeof addWatermark === 'function') {
    addWatermark(svg.node(), null);
}
```

**Requirements:**
- `addWatermark` function already loaded from `shared-utilities.js` ✓
- Must execute **after** rendering complete
- Must execute **before** screenshot

### Step 2: Use Dynamic Dimensions from ViewBox

**Approach A: Extract viewBox before screenshot (Recommended)**

```python
# After rendering, before screenshot
svg_dimensions = await page.evaluate("""
    (() => {
        const svg = document.querySelector('#d3-container svg');
        if (!svg) return null;
        
        const viewBox = svg.getAttribute('viewBox');
        if (viewBox) {
            const parts = viewBox.split(' ').map(Number);
            return { width: parts[2], height: parts[3] };
        }
        
        return { 
            width: parseFloat(svg.getAttribute('width')) || 800,
            height: parseFloat(svg.getAttribute('height')) || 600
        };
    })()
""")

# Screenshot only the actual SVG dimensions, not fixed container
```

**Approach B: Use recommended dimensions from diagram data**

```python
# Use _recommended_dimensions if available
if '_recommended_dimensions' in diagram_data:
    dims = diagram_data['_recommended_dimensions']
    container_width = dims.get('width', 1200)
    container_height = dims.get('height', 800)
else:
    container_width = req.width or 1200
    container_height = req.height or 800
```

**Approach C: Let container auto-size, then measure**

```html
<div id="d3-container" style="display: inline-block;"></div>
```

Then measure actual rendered size before screenshot.

### Step 3: Modify Screenshot Strategy

**Option 1: Screenshot SVG element directly**

```python
svg_element = await page.query_selector('#d3-container svg')
screenshot_bytes = await svg_element.screenshot()
```

**Option 2: Adjust container to match SVG**

```python
# Set container to match SVG viewBox dimensions
await page.evaluate("""
    const svg = document.querySelector('#d3-container svg');
    const container = document.getElementById('d3-container');
    const viewBox = svg.getAttribute('viewBox').split(' ');
    container.style.width = viewBox[2] + 'px';
    container.style.height = viewBox[3] + 'px';
""")
```

---

## Recommended Fix Order

### Phase 1: Add Watermark (Easy, High Impact)
1. Call `addWatermark()` in checkRendering() function
2. Ensure it executes after rendering, before screenshot
3. Test all diagram types

**Expected Result:** All exported PNGs have watermark ✓

### Phase 2: Dynamic Dimensions (Medium Difficulty)
1. Extract viewBox dimensions after rendering
2. Adjust screenshot to capture actual content
3. Test with various diagram sizes

**Expected Result:** PNGs match actual diagram size ✓

### Phase 3: Optimization (Optional)
1. Use recommended dimensions for initial container size hint
2. Add scale parameter support (2x for retina, 3x for print)
3. Add padding options

---

## Testing Checklist

After fixes, test each diagram type:

- [ ] bubble_map - Small diagram (5-8 attributes)
- [ ] bubble_map - Large diagram (15+ attributes)  
- [ ] circle_map - Small (3 circles)
- [ ] circle_map - Large (5 circles)
- [ ] double_bubble_map - Standard
- [ ] tree_map - 2 levels
- [ ] tree_map - 4+ levels
- [ ] flow_map - Simple
- [ ] multi_flow_map - Many causes/effects
- [ ] brace_map - 2 categories
- [ ] brace_map - 4+ categories
- [ ] bridge_map - 3 analogies
- [ ] bridge_map - 6+ analogies
- [ ] mindmap - Small tree
- [ ] mindmap - Large tree
- [ ] concept_map - Few nodes
- [ ] concept_map - Many nodes

**Verify for each:**
- ✅ Watermark present in bottom-right
- ✅ No excessive white space
- ✅ Content not clipped
- ✅ Text readable
- ✅ Resolution appropriate

---

## Files to Modify

1. **`routers/api.py`** (Lines 366-429)
   - Add watermark call after rendering
   - Extract viewBox dimensions
   - Adjust screenshot logic

2. **No other files need changes** (all utilities already exist)

---

## Success Criteria

✅ **Watermark Fix:**
- "MindGraph" appears in bottom-right corner
- Font size ~12-20px depending on diagram size
- Opacity 0.8
- Color #2c3e50

✅ **Dimension Fix:**
- Small diagrams: Tight PNG (e.g., 600x400 for simple bubble map)
- Large diagrams: Full content visible (e.g., 1200x900 for complex tree)
- No unnecessary white space
- No clipped content

---

## Additional Notes

### Why Renderers Don't Add Watermarks

Intentional design to keep editor canvas clean. Users should see diagrams without watermark while editing, but get watermark in exported files. This is correct behavior - the bug is that PNG export endpoint doesn't add it.

### Why Editor Works

Editor export uses **client-side JavaScript** with full browser APIs:
- Can clone and modify DOM
- Can measure rendered dimensions
- Can use Canvas API for high-quality export

### Why API Export Needs Different Approach

API export uses **headless browser automation**:
- Must inject watermark via page.evaluate()
- Must extract dimensions via page.evaluate()  
- Must coordinate timing (render → measure → watermark → screenshot)

---

**End of Analysis**

