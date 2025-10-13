# Export Diagram Cutoff Fix

**Issue Date:** October 13, 2025  
**Author:** lycosa9527  
**Made by:** MindSpring Team

## Problem

When exporting diagrams to PNG, sometimes the diagram would be cut off, even though it rendered perfectly in the editor canvas. This happened because the export function was using `fitDiagramToWindow()`, which calculates the viewBox based on the **visible canvas area** (accounting for property panels, AI panels, etc.), not the **full diagram bounds**.

### Root Cause

1. **Export called `fitDiagramToWindow()`** which is designed for viewing, not exporting
2. **`fitDiagramToWindow()` considers panel visibility** and reduces available canvas width accordingly (lines 1131-1147 in interactive-editor.js)
3. **ViewBox was set to fit visible area only**, cutting off content that extended beyond the visible canvas
4. **`getBBox()` doesn't account for stroke widths**, causing elements with thick strokes to be partially cut off

## Solution

### 1. Created Dedicated Export Function

Added `fitDiagramForExport()` method in `interactive-editor.js` (lines 1219-1296):

**Key Differences from `fitDiagramToWindow()`:**
- ✅ Calculates **full diagram bounds** regardless of canvas/panel visibility
- ✅ Includes **all element types** (images, foreignObjects) in bounds calculation
- ✅ Accounts for **stroke widths** that `getBBox()` doesn't include
- ✅ Uses **15% padding** (vs 10%) for generous export margins
- ✅ Sets viewBox **immediately without transition** (faster, no animation needed)

### 2. Updated Export Flow

Modified `handleExport()` in `toolbar-manager.js` (lines 2900-2923):

**Before:**
```javascript
this.editor.fitDiagramToWindow();  // Panel-aware fitting
setTimeout(() => {
    this.performPNGExport();
}, 800); // Wait for 750ms transition
```

**After:**
```javascript
this.editor.fitDiagramForExport();  // Full diagram fitting
setTimeout(() => {
    this.performPNGExport();
}, 100); // Shorter delay (no transition)
```

### 3. Enhanced Bounds Calculation

The new export function accounts for stroke widths:

```javascript
const bbox = this.getBBox();
// Account for stroke width (getBBox doesn't include it)
let strokeWidth = 0;
const computedStyle = window.getComputedStyle(this);
const strokeWidthStr = computedStyle.strokeWidth || this.getAttribute('stroke-width') || '0';
strokeWidth = parseFloat(strokeWidthStr) || 0;

// Add half stroke width on each side
const halfStroke = strokeWidth / 2;
minX = Math.min(minX, bbox.x - halfStroke);
minY = Math.min(minY, bbox.y - halfStroke);
maxX = Math.max(maxX, bbox.x + bbox.width + halfStroke);
maxY = Math.max(maxY, bbox.y + bbox.height + halfStroke);
```

## Benefits

1. **Complete Diagram Capture** - Exports the entire diagram regardless of visible canvas area
2. **No Cutoff Issues** - Generous padding and stroke-aware bounds prevent any content from being cut off
3. **Faster Export** - No transition animation needed (100ms vs 800ms delay)
4. **Better Quality** - 15% padding provides better visual balance in exported images
5. **Robust Element Detection** - Includes images and foreignObjects that might be missed

## Files Modified

1. **static/js/editor/interactive-editor.js**
   - Added `fitDiagramForExport()` method (lines 1219-1296)
   - Enhanced bounds calculation with stroke width support (lines 1253-1264)

2. **static/js/editor/toolbar-manager.js**
   - Updated `handleExport()` to use `fitDiagramForExport()` (lines 2900-2923)
   - Reduced export delay from 800ms to 100ms

## Testing

To verify the fix works:

1. Create a diagram with elements near the edges
2. Open the property panel or AI panel (reduces visible canvas area)
3. Click the export button
4. Verify the exported PNG includes **all diagram elements** with proper margins
5. Compare with the canvas view - they should match completely

## Related Issues

- Export quality: Already addressed with 3x DingTalk quality scaling
- Watermark positioning: Uses viewBox coordinates for accurate placement
- Filename format: `{diagram_type}_{llm_model}_{timestamp}.png`

