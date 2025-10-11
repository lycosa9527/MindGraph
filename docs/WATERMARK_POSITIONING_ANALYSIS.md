# Watermark Positioning Analysis - All 9 Diagrams

**Date:** 2025-01-11  
**Issue:** Watermarks positioned incorrectly in diagrams with negative viewBox offsets

---

## ViewBox Patterns by Diagram Type

### ✅ Diagrams with Standard ViewBox (origin at 0,0)

1. **tree_map** - `viewBox="0 0 ${width} ${height}"`
2. **brace_map** - `viewBox="0 0 ${width} ${height}"`
3. **mindmap** - `viewBox="0 0 ${width} ${height}"`
4. **concept_map** - `viewBox="0 0 ${width} ${height}"`
5. **flow_map** - `viewBox="0 0 ${width} ${height}"`
6. **bridge_map** - `viewBox="0 0 ${width} ${height}"`
7. **multi_flow_map** - `viewBox="0 0 ${width} ${height}"`

**These work correctly** - viewBox starts at (0, 0)

---

### ❌ Diagrams with NEGATIVE ViewBox Offsets

1. **bubble_map** - `viewBox="${minX} ${minY} ${width} ${height}"`
   - Example: `viewBox="-100 -80 800 600"`
   - Coordinates range: x from -100 to 700, y from -80 to 520

2. **circle_map** - `viewBox="${minX} ${minY} ${width} ${height}"`
   - Example: `viewBox="-150 -120 900 700"`
   - Coordinates range: x from -150 to 750, y from -120 to 580

**These have WRONG watermark position!**

---

## The Bug in addWatermark()

### Current Code (Lines 87-94 of shared-utilities.js)

```javascript
// Get SVG dimensions from the SVG element itself
const svgNode = svg.node();
const svgWidth = svgNode.getAttribute('width') || svgNode.getAttribute('viewBox')?.split(' ')[2] || 800;
const svgHeight = svgNode.getAttribute('height') || svgNode.getAttribute('viewBox')?.split(' ')[3] || 600;

// Parse dimensions if they're strings
const width = parseFloat(svgWidth);
const height = parseFloat(svgHeight);
```

**Problem:**
- Extracts index [2] and [3] from viewBox = WIDTH and HEIGHT only
- **IGNORES index [0] and [1] = minX and minY offsets!**

### Current Watermark Calculation (Lines 115-120)

```javascript
case 'bottom-right':
default:
    x = width - config.padding;      // ❌ WRONG for negative viewBox!
    y = height - config.padding;     // ❌ WRONG for negative viewBox!
    textAnchor = 'end';
    break;
```

---

## Example of the Bug

### Scenario: bubble_map with viewBox="-100 -80 800 600"

**Coordinate Space:**
- minX = -100, minY = -80
- width = 800, height = 600
- **Actual visible area:** x from -100 to 700, y from -80 to 520

**Current (Buggy) Watermark Position:**
```javascript
x = 800 - 10 = 790  // ❌ OUTSIDE visible area (ends at 700)
y = 600 - 10 = 590  // ❌ OUTSIDE visible area (ends at 520)
```

**Watermark appears OFF-SCREEN** (to the right and below)

**Correct Watermark Position:**
```javascript
x = -100 + 800 - 10 = 690  // ✅ Inside visible area
y = -80 + 600 - 10 = 510   // ✅ Inside visible area
```

---

## The Fix

### Parse Full ViewBox with Offsets

```javascript
// Get SVG dimensions AND offsets from viewBox
const svgNode = svg.node();
let width, height, offsetX = 0, offsetY = 0;

// Try to get viewBox first (most reliable)
const viewBox = svgNode.getAttribute('viewBox');
if (viewBox) {
    const parts = viewBox.split(' ').map(Number);
    offsetX = parts[0];  // ✅ Get minX offset
    offsetY = parts[1];  // ✅ Get minY offset
    width = parts[2];    // Get width
    height = parts[3];   // Get height
} else {
    // Fallback to width/height attributes
    width = parseFloat(svgNode.getAttribute('width')) || 800;
    height = parseFloat(svgNode.getAttribute('height')) || 600;
}
```

### Update Position Calculation

```javascript
case 'bottom-right':
default:
    x = offsetX + width - config.padding;   // ✅ Account for offset
    y = offsetY + height - config.padding;  // ✅ Account for offset
    textAnchor = 'end';
    break;

case 'top-left':
    x = offsetX + config.padding;           // ✅ Account for offset
    y = offsetY + config.padding + 12;      // ✅ Account for offset
    textAnchor = 'start';
    break;

case 'top-right':
    x = offsetX + width - config.padding;   // ✅ Account for offset
    y = offsetY + config.padding + 12;      // ✅ Account for offset
    textAnchor = 'end';
    break;

case 'bottom-left':
    x = offsetX + config.padding;           // ✅ Account for offset
    y = offsetY + height - config.padding;  // ✅ Account for offset
    textAnchor = 'start';
    break;
```

---

## Impact by Diagram

### ✅ Currently Working (7 diagrams)
- tree_map
- brace_map
- mindmap
- concept_map
- flow_map
- bridge_map
- multi_flow_map

**Why:** viewBox starts at (0, 0), so offsetX=0 and offsetY=0  
**After Fix:** Still works (0 + width - padding = width - padding)

### ❌ Currently Broken (2 diagrams)
- **bubble_map** - Watermark off-screen to right/bottom
- **circle_map** - Watermark off-screen to right/bottom

**Why:** viewBox has negative offsets that are ignored  
**After Fix:** Watermark appears correctly in bottom-right corner

---

## Testing Plan

### Before Fix - Watermark Issues:
- [ ] bubble_map - Watermark not visible or cut off
- [ ] circle_map - Watermark not visible or cut off
- [x] double_bubble_map - Already uses viewBox="0 0 w h", works fine

### After Fix - All Should Work:
- [ ] bubble_map - Watermark in visible bottom-right corner ✅
- [ ] circle_map - Watermark in visible bottom-right corner ✅
- [ ] double_bubble_map - Still works (no regression) ✅
- [ ] tree_map - Still works (no regression) ✅
- [ ] brace_map - Still works (no regression) ✅
- [ ] mindmap - Still works (no regression) ✅
- [ ] flow_map - Still works (no regression) ✅
- [ ] bridge_map - Still works (no regression) ✅
- [ ] multi_flow_map - Still works (no regression) ✅

---

## Code Changes Required

**File:** `static/js/renderers/shared-utilities.js`  
**Function:** `addWatermark()`  
**Lines:** 87-120

Replace the dimension extraction and position calculation logic.

---

**Ready to implement fix**

