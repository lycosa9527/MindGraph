# Manual Line Break Support Plan - Ctrl+Enter Line Breaks

**Date:** 2025-01-XX  
**Problem:** Users can press **Ctrl+Enter** in the properties panel text input field to insert line breaks (`\n`), but most diagrams don't render these line breaks - all text appears on a single line instead of wrapping to multiple lines.

---

## Executive Summary

**Main Idea:** When users wrap lines in the properties panel text input field (using Ctrl+Enter), the diagram's node should also show wrapped lines.

**Pipeline Status:**
- ✅ **Step 1-4:** All working correctly - `\n` flows from properties panel → spec → re-render trigger
- ❌ **Step 5:** Problem is ONLY in text rendering - most diagrams ignore `\n` characters

**Solution:** Update renderers to split text by `\n` and render each line as a separate `<tspan>` element.

**Affected Diagrams:** 9 diagrams need updates (Bubble Map, Tree Map, Brace Map, Flow Map, Multi-Flow Map, Mind Map, Circle Map, Double Bubble Map, Bridge Map)

**Working Diagrams:** Flowchart and Concept Map already work correctly.

---

## Problem Analysis

### Complete Pipeline Review

**Step 1: User Input (Properties Panel)**
- File: `static/js/editor/toolbar-manager.js` (lines 263-286)
- User types in textarea and presses **Ctrl+Enter**
- `\n` character is inserted into `textarea.value` ✅
- User presses **Enter** (without Ctrl) → `applyText()` is called

**Step 2: Text Application**
- File: `static/js/managers/toolbar/text-toolbar-state-manager.js` (lines 69-167)
- Gets text from `this.toolbarManager.propText.value` (contains `\n` characters) ✅
- Calls `this.editor.updateNodeText(nodeId, shapeNode, textNode, newText)` with text containing `\n`

**Step 3: Spec Update**
- File: `static/js/editor/interactive-editor.js` (lines 750-800)
- Calls `operations.updateNode(this.currentSpec, nodeId, { text: newText })`
- Updates spec with text containing `\n`:
  - Bubble Map: `spec.topic = updates.text` or `spec.attributes[index] = updates.text`
  - Tree Map: `spec.topic = updates.text` or `spec.children[index].label = updates.text`
  - Mind Map: `spec.topic = updates.text` or `spec.children[index].label = updates.text`
  - etc.
- Emits `diagram:node_updated` event ✅

**Step 4: Diagram Re-render**
- File: `static/js/editor/interactive-editor.js` (lines 208-244, 358+)
- Listens for `diagram:node_updated` event
- Calls `this.renderDiagram()`
- Calls renderer function: `renderBubbleMap(spec)`, `renderTreeMap(spec)`, etc.

**Step 5: Text Rendering** ❌ **THIS IS WHERE THE PROBLEM IS**
- Renderers read text from spec: `spec.topic`, `node.text`, `spec.attributes[index]`, etc.
- **Flowchart** (`flow-renderer.js` line 99): ✅ Uses `splitAndWrapText(txt, ...)` which splits by `\n`, then renders with `tspan` elements
- **Concept Map** (`concept-map-renderer.js` line 200): ✅ Uses `wrapIntoLines(text, ...)` which splits by `\n`, then renders with `tspan` elements
- **Bubble Map** (`bubble-map-renderer.js` line 257): ❌ Uses `.text(node.text)` directly - `\n` is ignored
- **Tree Map** (`tree-renderer.js`): ❌ Uses `.text(text)` directly - `\n` is ignored
- **Brace Map** (`brace-renderer.js`): ❌ Uses `.text(text)` directly - `\n` is ignored
- **Flow Map** (`flow-renderer.js` line 626): ❌ Uses `.text(s.text || '\u00A0')` directly - `\n` is ignored
- **Multi-Flow Map** (`flow-renderer.js`): ❌ Uses `.text(text)` directly - `\n` is ignored
- **Mind Map** (`mind-map-renderer.js`): ❌ Uses `.text(text)` directly - `\n` is ignored
- **Circle Map** (`bubble-map-renderer.js`): ❌ Uses `.text(node.text)` directly - `\n` is ignored
- **Double Bubble Map** (`bubble-map-renderer.js`): ❌ Uses `.text(node.text)` directly - `\n` is ignored
- **Bridge Map** (`flow-renderer.js`): ❌ Uses `.text(text)` directly - `\n` is ignored

### Root Cause

**The entire pipeline works correctly** - `\n` characters flow through:
1. ✅ Properties panel textarea (Ctrl+Enter inserts `\n`)
2. ✅ Text application (`applyText()` preserves `\n`)
3. ✅ Spec update (`operations.updateNode()` stores text with `\n`)
4. ✅ Diagram re-render (triggered correctly)

**The problem is ONLY in Step 5 (Text Rendering)**:
- Most renderers use `.text(node.text)` which ignores `\n` characters
- SVG `<text>` elements don't automatically break on `\n`
- Only Flowchart and Concept Map split by `\n` and use `tspan` elements

### Understanding `\n` (Newline Character)

**Important:** `\n` is an **invisible character** - you don't see it visually, but it represents a line break.

**What users see:**
- In the **properties panel text input**: When pressing Ctrl+Enter, the cursor moves to a new line (visual line break)
- In the **diagram** (if working correctly): Text appears on multiple lines
- In the **diagram** (if broken): Text appears on one line, `\n` is ignored

**What's actually stored:**
- The text string contains the invisible `\n` character: `"Line 1\nLine 2"`
- When you log it or inspect it, you see `\n` in the string representation
- But visually, it's just a line break

### SVG Text Behavior

In SVG, the `<text>` element does NOT automatically break on `\n` characters. When you do:
```javascript
svg.append('text').text("Line 1\nLine 2");
```

The SVG will display: `"Line 1 Line 2"` as a **single line** (the `\n` is invisible and ignored - text appears on one line).

**To create multi-line text in SVG, you must:**
1. Split text by `\n` to get individual lines (the invisible newline character)
2. Create a `<text>` element
3. Add `<tspan>` elements for each line with proper `dy` attributes

**Example:**
```javascript
const lines = text.split(/\n/); // Split by invisible \n character
const textEl = svg.append('text').attr('x', x).attr('y', y);
lines.forEach((line, i) => {
    textEl.append('tspan')
        .attr('x', x)
        .attr('dy', i === 0 ? 0 : lineHeight)
        .text(line); // Each line renders separately
});
```

**Result:** Text appears on multiple visual lines in the diagram, even though `\n` itself is invisible.

### Current State

| Diagram Type | Wrapping Status | Implementation |
|-------------|----------------|----------------|
| Flowchart | ✅ Has wrapping | Uses `splitAndWrapText()` - but only wraps at spaces |
| Concept Map | ✅ Has wrapping | Uses `wrapIntoLines()` - but only wraps at spaces |
| Bubble Map | ❌ No wrapping | Simple `.text()` - single line |
| Tree Map | ❌ No wrapping | Simple `.text()` - single line |
| Brace Map | ❌ No wrapping | Simple `.text()` - single line |
| Flow Map | ❌ No wrapping | Simple `.text()` - single line |
| Multi-Flow Map | ❌ No wrapping | Simple `.text()` - single line |
| Mind Map | ❌ No wrapping | Simple `.text()` - single line |
| Circle Map | ❌ No wrapping | Simple `.text()` - single line |
| Double Bubble Map | ❌ No wrapping | Simple `.text()` - single line |
| Bridge Map | ❌ No wrapping | Simple `.text()` - single line |

---

## Solution Approach

### Strategy: Render Manual Line Breaks Using tspan Elements

When users press **Ctrl+Enter** in the properties panel, they're inserting `\n` characters into the text. The diagrams need to:

1. **Split text by `\n`** to get explicit line breaks (inserted via Ctrl+Enter in properties panel)
2. **Render each line as a separate `tspan` element** within a `<text>` element
3. **Set proper `dy` attributes** to position lines vertically with correct spacing
4. **Update node sizes** to accommodate multi-line text (height increases with more lines)

**Key Points:**
- This is about **displaying** the line breaks users already inserted (Ctrl+Enter)
- No automatic word wrapping needed - users control line breaks manually
- Simple string split operation - very fast and reliable
- Backward compatible - text without `\n` still renders as single line

### Key Requirements

1. **Simple and reliable**: Just split by `\n` and render as tspan elements
2. **Consistent**: Same pattern across all diagrams
3. **Backward compatible**: Existing text without `\n` still works
4. **Performance**: Minimal overhead - just string splitting and tspan creation
5. **Optional enhancement**: Can add automatic word wrapping later if needed

---

## Implementation Plan

### Phase 1: Create Simple Line Break Helper Function

**File:** `static/js/renderers/shared-utilities.js`

**New Function:** `splitTextLines(text)`

**Purpose:** Simple utility to split text by newlines, preserving empty lines appropriately.

**Implementation:**
```javascript
/**
 * Split text by newline characters, preserving explicit line breaks
 * @param {string} text - Text to split (may contain \n from Ctrl+Enter)
 * @returns {string[]} Array of lines
 */
function splitTextLines(text) {
    const textStr = String(text || '');
    if (textStr === '') return [''];
    
    // Split by newlines
    const lines = textStr.split(/\n/);
    
    // Return lines array (empty lines are preserved)
    return lines.length > 0 ? lines : [''];
}
```

**Note:** This is simpler than `splitAndWrapText()` - it only handles manual line breaks, not automatic wrapping.

---

### Phase 2: Verify Existing Diagrams (Flowchart & Concept Map)

**Files:**
- `static/js/renderers/flow-renderer.js` - Verify `renderFlowchart()` handles newlines
- `static/js/renderers/concept-map-renderer.js` - Verify `wrapIntoLines()` handles newlines

**Action:** Test that Ctrl+Enter line breaks work correctly in these diagrams. They should already work since they use wrapping functions that split by `\n`.

---

### Phase 3: Add Line Break Support to All Diagrams

**Diagrams to Update:**
1. Bubble Map (`bubble-map-renderer.js`) - Topic and attribute nodes
2. Tree Map (`tree-renderer.js`) - Root, branch, and leaf nodes
3. Brace Map (`brace-renderer.js`) - Topic and part nodes
4. Flow Map (`flow-renderer.js`) - Step nodes
5. Multi-Flow Map (`flow-renderer.js`) - Event, cause, and effect nodes
6. Mind Map (`mind-map-renderer.js`) - Topic and branch nodes
7. Circle Map (`bubble-map-renderer.js`) - Topic and context nodes
8. Double Bubble Map (`bubble-map-renderer.js`) - Topic and attribute nodes
9. Bridge Map (`flow-renderer.js`) - Analogy text nodes

**Implementation Pattern (for each diagram):**

**Before (broken - ignores `\n`):**
```javascript
svg.append('text')
    .attr('x', x)
    .attr('y', y)
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', fontSize)
    .text(node.text); // ❌ \n is ignored, shows as single line
```

**After (fixed - handles `\n`):**
```javascript
// 1. Split text by newlines (from Ctrl+Enter in properties panel)
const lines = window.splitTextLines(text); // or: text.split(/\n/)
const lineHeight = Math.round(fontSize * 1.2);

// 2. Calculate text dimensions based on lines
// Option A: Use existing measurement function if available
const textWidth = Math.max(...lines.map(l => {
    // Use existing measureTextWidth or measureLineWidth function
    return measureTextWidth(l, fontSize);
}), 20);
const textHeight = lines.length * lineHeight;

// Option B: Simple approximation (if no measurement function)
// const textWidth = Math.max(...lines.map(l => l.length * fontSize * 0.6), 20);

// 3. Update node size calculations (if needed)
// const nodeHeight = textHeight + padding * 2;
// const nodeWidth = Math.max(nodeWidth, textWidth + padding * 2);

// 4. Render using tspan elements
const textEl = svg.append('text')
    .attr('x', x)
    .attr('y', y - (lines.length - 1) * lineHeight / 2) // Center vertically for multi-line
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', fontSize)
    .attr('font-family', THEME.fontFamily)
    .attr('fill', textColor);

lines.forEach((line, i) => {
    textEl.append('tspan')
        .attr('x', x)
        .attr('dy', i === 0 ? 0 : lineHeight)
        .text(line || '\u00A0'); // Non-breaking space for empty lines
});
```

**Key Points:**
- Simple: Just split by `\n` (invisible character from Ctrl+Enter) and render as tspan
- No automatic wrapping needed - users control line breaks with Ctrl+Enter in properties panel
- Update node size calculations to account for multi-line text (height increases)
- Preserve existing styling and positioning
- Works for both single-line (no `\n`) and multi-line (with `\n`) text

---

### Phase 4: Testing & Validation

**Test Workflow:**

1. **Open properties panel** for a node (select node in diagram)
2. **Type text** in the text input field: `"First line"`
3. **Press Ctrl+Enter** → Cursor moves to new line, `\n` character inserted
4. **Type more text**: `"Second line"`
5. **Press Enter** (or click Apply button) → Text is applied to diagram
6. **Verify diagram renders** → Should show two separate lines, not one long line

**Test Cases:**

1. **Single line text** (no line breaks - backward compatibility)
   - Type: `"Hello"` → Press Enter → Should render as single line
   - Type: `"你好"` → Press Enter → Should render as single line
   - Type: `"Hello 你好"` → Press Enter → Should render as single line

2. **Multi-line text** (with Ctrl+Enter line breaks)
   - Type: `"Line 1"`, press Ctrl+Enter (cursor moves to new line), type `"Line 2"`, press Enter → Should render as 2 separate lines in diagram
   - Type: `"第一行"`, press Ctrl+Enter (cursor moves to new line), type `"第二行"`, press Enter → Should render as 2 separate lines in diagram
   - Type: `"Line 1"`, press Ctrl+Enter, type `"Line 2"`, press Ctrl+Enter, type `"Line 3"`, press Enter → Should render as 3 separate lines in diagram
   
   **Note:** The `\n` character is invisible - you see the cursor move to a new line in the input field, and text should appear on multiple lines in the diagram.

3. **Edge cases**
   - Empty text: Clear text field, press Enter → Should render as empty (or single space)
   - Single line with trailing newline: Type text, press Ctrl+Enter at end, press Enter → Should show blank line below
   - Multiple consecutive newlines: Type text, press Ctrl+Enter twice, type more text, press Enter → Should show blank line
   - Text starting with newline: Press Ctrl+Enter first, then type text, press Enter → Should show blank line above

4. **All diagram types**
   - Test each diagram type with single-line text (no Ctrl+Enter)
   - Test each diagram type with multi-line text (using Ctrl+Enter in properties panel)
   - Verify line breaks render correctly in diagram
   - Verify node sizes adjust properly (height increases with more lines)
   - Verify text remains editable (select node again, Ctrl+Enter still works when editing)
   - Verify text alignment (centered, left-aligned, etc.) works correctly
   - Verify properties panel shows text with line breaks when node is selected again

---

## Technical Details

### SVG Text and tspan Elements

**How SVG handles text:**
- `<text>` element contains the text
- `<tspan>` elements define individual lines within the text
- `dy` attribute on tspan controls vertical offset from previous line
- First tspan uses `dy="0"`, subsequent tspan elements use `dy="lineHeight"`

**Example:**
```xml
<text x="100" y="50" text-anchor="middle">
  <tspan x="100" dy="0">Line 1</tspan>
  <tspan x="100" dy="20">Line 2</tspan>
  <tspan x="100" dy="20">Line 3</tspan>
</text>
```

### Line Height Calculation

**Standard approach:**
```javascript
const lineHeight = Math.round(fontSize * 1.2); // 20% spacing between lines
```

**Alternative (more precise):**
```javascript
const lineHeight = fontSize * 1.2; // Can use decimal for finer control
```

### Text Measurement (if needed for sizing)

**Simple measurement function:**
```javascript
function measureTextWidth(text, fontSize, fontFamily) {
    const t = tempSvg.append('text')
        .attr('x', -9999)
        .attr('y', -9999)
        .attr('font-size', fontSize)
        .attr('font-family', fontFamily || THEME.fontFamily)
        .text(text || '');
    const w = t.node().getBBox().width;
    t.remove();
    return w;
}
```

**Note:** Measurement is only needed if you want to adjust node sizes based on text width. For simple line break support, you can use approximate calculations or existing measurement functions.

---

## Implementation Steps

### Step 1: Add `splitTextLines()` Helper Function

**File:** `static/js/renderers/shared-utilities.js`

**Location:** After `splitAndWrapText()` function (around line 335), before export section (line 480)

**Changes:**
- Add simple `splitTextLines()` function after `splitAndWrapText()`
- Export it in `MindGraphUtils` object (add to line 494)
- Make it available globally as `window.splitTextLines` (add after line 500)

**Implementation:**
```javascript
/**
 * Split text by newline characters (from Ctrl+Enter in properties panel)
 * Preserves explicit line breaks inserted by users
 * @param {string} text - Text to split (may contain \n from Ctrl+Enter)
 * @returns {string[]} Array of lines
 */
function splitTextLines(text) {
    const textStr = String(text || '');
    if (textStr === '') return [''];
    
    // Split by newlines (invisible \n character inserted via Ctrl+Enter)
    const lines = textStr.split(/\n/);
    
    // Return lines array (empty lines are preserved)
    return lines.length > 0 ? lines : [''];
}
```

**Export Changes:**
- Add `splitTextLines` to `MindGraphUtils` object (line 494)
- Add global export: `window.splitTextLines = splitTextLines;` (after line 500)

**Estimated Lines:** ~15-20 lines (function + exports)

---

### Step 2: Verify Flowchart & Concept Map

**Files:**
- `static/js/renderers/flow-renderer.js`
- `static/js/renderers/concept-map-renderer.js`

**Action:** Test that Ctrl+Enter line breaks already work (they should, since they use wrapping functions that split by `\n`)

**Estimated Time:** 5-10 minutes testing

---

### Step 3: Add Line Break Support to Bubble Map

**File:** `static/js/renderers/bubble-map-renderer.js`

**Function:** `renderBubbleMap()` (starts at line 27)

**Changes:**
1. **Topic text rendering** (line 221-232):
   - Current: `.text(spec.topic)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Note: Topic uses circle, so may need height calculation for radius adjustment

2. **Attribute text rendering** (line 247-257):
   - Current: `.text(node.text)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Note: Attributes use circles with `getTextRadius()` - may need separate height calculation

**Node Size Considerations:**
- Topic: Uses `getTextRadius(spec.topic, THEME.fontTopic, 20)` (line 95)
- Attributes: Uses `getTextRadius()` for uniform radius (line 98)
- For multi-line text, `getTextRadius()` may need enhancement or separate height calculation

**Estimated Lines:** ~40-50 lines (text rendering + potential radius adjustments)

---

### Step 4: Add Line Break Support to Tree Map

**File:** `static/js/renderers/tree-renderer.js`

**Function:** `renderTreeMap()` (starts at line 38)

**Changes:**
1. **Root topic rendering** (line 293):
   - Current: `.text(spec.topic)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureSvgTextBox()` (line 140) - needs height update

2. **Branch text rendering** (line 365):
   - Current: `.text(childText)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureSvgTextBox()` (line 156) - needs height update

3. **Leaf text rendering** (find location):
   - Current: `.text(leafText)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureSvgTextBox()` (line 165) - needs height update

**Node Size Updates Required:**
- `measureSvgTextBox()` function (line 112-135): Currently uses fixed height `fontPx * 1.2`
- Update to: Calculate height based on number of lines
- Or: Create separate function for multi-line measurement

**Estimated Lines:** ~50-60 lines (text rendering + measurement function update)

---

### Step 5: Add Line Break Support to Brace Map

**File:** `static/js/renderers/brace-renderer.js`

**Function:** `renderBraceMap()` (starts at line 25)

**Changes:**
1. **Topic text rendering** (find location - likely around line 300-350):
   - Current: `.text(topicText)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureLineWidth()` (line 244) - needs height update

2. **Part text rendering** (line 405-418):
   - Current: `.text(partInfo.text || '\u00A0')` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureLineWidth()` (line 251) - needs height update

3. **Subpart text rendering** (find location - likely after line 450):
   - Current: `.text(subpartText)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureLineWidth()` (line 263) - needs height update

**Node Size Updates Required:**
- Topic: `topicBoxHeight = topicFontSize + topicPadding * 2` (line 246) - needs multi-line calculation
- Parts: `boxHeight = partFontSize + partPadding * 2` (line 253) - needs multi-line calculation
- Subparts: `boxHeight = subpartFontSize + subpartPadding * 2` (line 265) - needs multi-line calculation

**Estimated Lines:** ~50-60 lines (text rendering + size calculations)

---

### Step 6: Add Line Break Support to Flow Map

**File:** `static/js/renderers/flow-renderer.js`

**Function:** `renderFlowMap()` (starts at line 243)

**Changes:**
1. **Step text rendering** (line 614-626):
   - Current: `.text(s.text || '\u00A0')` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureLineWidth()` (line 346) - needs height update

**Node Size Updates Required:**
- Step sizes calculation (line 342-352):
  - Current: `h: Math.max(42, THEME.fontStep + THEME.vPadStep * 2)` - fixed single-line height
  - Update to: Calculate height based on number of lines

**Estimated Lines:** ~40-50 lines (text rendering + size calculation update)

---

### Step 7: Add Line Break Support to Multi-Flow Map

**File:** `static/js/renderers/flow-renderer.js`

**Function:** `renderMultiFlowMap()` (starts at line 1338)

**Changes:**
1. **Event text rendering** (find location - likely around line 1600-1650):
   - Current: `.text(spec.event)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureTextSize()` (line 1484) - needs height update

2. **Cause text rendering** (line 1582-1594):
   - Current: `.text(n.text)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureTextSize()` (line 1490) - needs height update

3. **Effect text rendering** (find location - likely after line 1595):
   - Current: `.text(n.text)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `measureTextSize()` (line 1494) - needs height update

**Node Size Updates Required:**
- Event: `eventH = evSize.h + THEME.vPadEvent * 2` (line 1486) - `measureTextSize()` needs multi-line support
- Causes: `h: s.h + THEME.vPadNode * 2` (line 1491) - `measureTextSize()` needs multi-line support
- Effects: `h: s.h + THEME.vPadNode * 2` (line 1495) - `measureTextSize()` needs multi-line support

**Note:** `measureTextSize()` function (line 1417-1424) currently returns single-line height - may need update or create wrapper

**Estimated Lines:** ~60-70 lines (text rendering + measurement function updates)

---

### Step 8: Add Line Break Support to Mind Map

**File:** `static/js/renderers/mind-map-renderer.js`

**Function:** `renderMindMapWithLayout()` (starts at line 115)

**Changes:**
1. **Topic text rendering** (line 189-200):
   - Current: `.text(pos.text || 'Topic')` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `getTextRadius()` (line 164) - may need height adjustment

2. **Branch text rendering** (find location - likely after line 200):
   - Current: `.text(pos.text)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `pos.width` and `pos.height` from layout - may need update

**Node Size Considerations:**
- Topic: Uses `getTextRadius()` for circular nodes - may need separate height calculation
- Branches: Uses `pos.width` and `pos.height` from Python agent layout - may need recalculation

**Estimated Lines:** ~50-60 lines (text rendering + potential size adjustments)

---

### Step 9: Add Line Break Support to Circle Map & Double Bubble Map

**File:** `static/js/renderers/bubble-map-renderer.js`

**Changes:**

**A. Circle Map** - Function: `renderCircleMap()` (starts at line 320)

1. **Topic text rendering** (line 608):
   - Current: `.text(spec.topic)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `getTextRadius()` (line 410) - may need height adjustment

2. **Context text rendering** (line 569-580):
   - Current: `.text(node.text)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `getTextRadius()` (line 389) - may need height adjustment

**B. Double Bubble Map** - Function: `renderDoubleBubbleMap()` (starts at line 624)

1. **Left topic text rendering** (find location):
   - Current: `.text(spec.left)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `getTextRadius()` (line 706) - may need height adjustment

2. **Right topic text rendering** (find location):
   - Current: `.text(spec.right)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `getTextRadius()` (line 707) - may need height adjustment

3. **Similarity text rendering** (find location):
   - Current: `.text(similarity)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `getTextRadius()` (line 710) - may need height adjustment

4. **Difference text rendering** (find location):
   - Current: `.text(difference)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Size calculation: Uses `getTextRadius()` (line 714) - may need height adjustment

**Node Size Considerations:**
- All nodes use `getTextRadius()` for circular nodes
- For multi-line text, may need separate height calculation or enhance `getTextRadius()`

**Estimated Lines:** ~60-80 lines (text rendering for both functions + potential radius adjustments)

---

### Step 10: Add Line Break Support to Bridge Map

**File:** `static/js/renderers/flow-renderer.js`

**Function:** `renderBridgeMap()` (starts at line 988)

**Changes:**
1. **Left analogy text rendering** (line 1105-1116):
   - Current: `.text(analogy.left)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Note: First pair has special styling (line 1095-1102) - handle separately

2. **Right analogy text rendering** (line 1141-1149):
   - Current: `.text(analogy.right)` - single line
   - Change: Split by `\n`, render with tspan elements
   - Note: First pair has rectangle background (line 1126-1138) - may need height adjustment

**Node Size Considerations:**
- Bridge Map uses fixed dimensions: `textHeight = 40` (line 1021)
- Rectangle for first pair: `rectHeight = 30` (line 1123) - may need adjustment for multi-line
- May need to calculate height based on number of lines

**Estimated Lines:** ~40-50 lines (text rendering + potential rectangle height adjustments)

---

### Step 11: Comprehensive Testing

**Tasks:**
1. Test each diagram with single-line text (backward compatibility)
2. Test each diagram with multi-line text (Ctrl+Enter)
3. Test edge cases (empty text, multiple newlines, etc.)
4. Verify text editing still works (Ctrl+Enter in editor)
5. Verify node sizes adjust correctly (height increases with more lines)
6. Verify text alignment works correctly
7. Verify no console errors
8. Test with Chinese, English, and mixed text

---

## Node Size Adjustments

**When adding multi-line support, update node size calculations:**

**Before (single line):**
```javascript
const textHeight = fontSize * 1.2; // Single line height
const nodeHeight = textHeight + padding * 2;
```

**After (multi-line):**
```javascript
const lines = text.split(/\n/);
const lineHeight = Math.round(fontSize * 1.2);
const textHeight = lines.length * lineHeight; // Multi-line height
const nodeHeight = textHeight + padding * 2;
```

**Width calculation:**
- Option 1: Use longest line width (simpler)
- Option 2: Use existing measurement functions if available
- Option 3: Keep current width calculation if it works well

**Note:** Node size adjustments ensure that multi-line text doesn't overflow node boundaries.

---

## Risk Assessment

### Low Risk
- ✅ Adding simple `splitTextLines()` helper function
- ✅ Adding line break support to diagrams (simple string split + tspan rendering)
- ✅ Backward compatible (text without `\n` still works)

### Medium Risk
- ⚠️ Updating node size calculations (need to ensure height adjusts correctly)
- ⚠️ Testing all diagram types thoroughly

### High Risk
- ⚠️ Brace Map and Flow Map (had placeholder rendering issues before - need to test carefully)

### Mitigation Strategies

1. **Incremental rollout**: Implement one diagram at a time, test thoroughly
2. **Fallback logic**: If line splitting fails, fall back to single-line rendering
3. **Simple implementation**: Just split by `\n` - no complex logic needed
4. **Thorough testing**: Test all edge cases before moving to next diagram
5. **Preserve existing behavior**: Text without `\n` should render exactly as before

---

## Success Criteria

✅ **Properties panel integration:**
- Users can press Ctrl+Enter in properties panel text input to insert line breaks
- Line breaks are preserved when text is applied to diagram
- When node is selected again, properties panel shows text with line breaks intact

✅ **All diagrams support manual line breaks:**
- `\n` characters (inserted via Ctrl+Enter) are rendered as line breaks in all diagrams
- Multi-line text displays correctly with proper spacing between lines
- Each `\n` creates a visually distinct new line

✅ **Line breaks render correctly:**
- Each `\n` creates a new line in the diagram
- Lines are properly spaced (lineHeight between lines)
- Text alignment (center, left, etc.) works correctly for multi-line text
- Empty lines (consecutive `\n`) are preserved and displayed as blank lines

✅ **Node sizing works correctly:**
- Node height increases with number of lines
- Node width adjusts if needed (based on longest line)
- Canvas dimensions adjust properly to accommodate larger nodes
- No text overflow or clipping

✅ **Backward compatibility:**
- Text without `\n` renders exactly as before (single line)
- No breaking changes to API or existing functionality
- Existing diagrams without line breaks render correctly

✅ **User experience:**
- Users can control line breaks precisely using Ctrl+Enter
- Line breaks are visible immediately after applying changes
- Text editing workflow remains smooth and intuitive

✅ **Performance:**
- Line splitting is instant (simple string operation)
- No noticeable lag during rendering
- Efficient memory usage

---

## User-Facing Behavior

**How it works for users:**

1. **User selects a node** in a diagram → Properties panel opens on the right side
2. **User clicks in the text input field** in properties panel
3. **User types**: `"First line"`
4. **User presses Ctrl+Enter** → Cursor moves to a new line (visual line break in input field)
   - Behind the scenes: invisible `\n` character is inserted into the text string
5. **User types**: `"Second line"`
6. **User presses Enter** (or clicks Apply button) → Text is applied to diagram
7. **Diagram re-renders** → Should show:
   ```
   First line
   Second line
   ```
   (as two separate visual lines, not one long line)

**What users see vs. what's stored:**
- **In properties panel**: Cursor moves to new line when Ctrl+Enter is pressed (visual line break)
- **In diagram (working)**: Text appears on multiple lines
- **In diagram (broken)**: Text appears on one line (invisible `\n` is ignored)
- **In code**: Text string contains `"First line\nSecond line"` (the `\n` is invisible but present)

**Key points:**
- **Ctrl+Enter** = insert line break (cursor moves to new line in properties panel)
- **Enter** (without Ctrl) = apply text changes to diagram
- The `\n` character is invisible - users see the effect (line break), not the character itself
- Line breaks must be rendered properly in diagrams using tspan elements
- Users have full control over where line breaks occur
- When node is selected again, properties panel shows text with line breaks intact

---

## Next Steps

1. **Review this plan** - Confirm approach and priorities
2. **Start with Step 1** - Add `splitTextLines()` helper function to shared utilities
3. **Test Step 2** - Verify Flowchart and Concept Map already work with Ctrl+Enter line breaks
4. **Proceed with Steps 3-10** - Add line break support to each diagram type
5. **Comprehensive testing** - Test all diagrams:
   - Open properties panel
   - Type text and use Ctrl+Enter to insert line breaks
   - Apply changes and verify diagram renders correctly
6. **Documentation** - Update code comments if needed

---

## Optional Future Enhancement: Automatic Word Wrapping

**Note:** This plan focuses on **manual line breaks** (Ctrl+Enter in properties panel). If automatic word wrapping is needed later, we can:

1. Enhance `splitTextLines()` to also wrap long lines automatically
2. Add measurement functions to calculate when to wrap
3. Support both manual breaks (`\n` from Ctrl+Enter) and automatic wrapping

**But for now:** Manual line breaks (Ctrl+Enter) is the priority and simpler to implement. Users can control exactly where lines break.

---

## References

- [MDN - SVG Text Element](https://developer.mozilla.org/en-US/docs/Web/SVG/Element/text)
- [MDN - SVG TSpan Element](https://developer.mozilla.org/en-US/docs/Web/SVG/Element/tspan)
- [SVG Text Layout Guide](https://css-tricks.com/svg-text-layout/)

---

---

## Complete Review - Additional Considerations

### ✅ Export Functionality

**PNG Export:**
- File: `static/js/editor/toolbar-manager.js` (line 1049+), `static/js/managers/toolbar/export-manager.js`
- Uses SVG clone: `const svgClone = svg.cloneNode(true);`
- **Status:** ✅ Will work correctly once renderers use tspan elements
- If SVG has `<text><tspan>Line 1</tspan><tspan dy="20">Line 2</tspan></text>`, export will preserve it
- **Action:** No changes needed - export will automatically work once rendering is fixed

**SVG Export:**
- File: `static/js/managers/toolbar/export-manager.js` (line 361+)
- Exports SVG directly: `const svgString = new XMLSerializer().serializeToString(svgClone);`
- **Status:** ✅ Will work correctly once renderers use tspan elements
- **Action:** No changes needed

**JSON Export:**
- File: `static/js/managers/toolbar/export-manager.js` (line 438+)
- Exports spec: `spec: editor.currentSpec`
- **Status:** ✅ Already works - spec contains text with `\n` characters preserved
- JSON.stringify preserves `\n` in strings: `"Line 1\nLine 2"`
- **Action:** No changes needed

**Backend PNG Export:**
- File: `routers/api.py` (line 228+)
- Uses Playwright to render diagram in headless browser
- **Status:** ✅ Will work correctly once renderers use tspan elements
- **Action:** No changes needed

---

### ❌ Text Loading from Properties Panel - CRITICAL ISSUE FOUND

**Problem:** When loading text from SVG to populate properties panel, `.text()` only gets first line!

**Files Affected:**
- `static/js/editor/toolbar-manager.js` (line 664, 669, 675)
- `static/js/managers/toolbar/property-panel-manager.js` (line 263, 268, 274)

**Current Code:**
```javascript
textElement = nodeElement.select('text');
text = textElement.text() || ''; // ❌ Only gets first tspan!
```

**Issue:**
- If text was rendered with tspan elements:
  ```xml
  <text>
    <tspan>Line 1</tspan>
    <tspan dy="20">Line 2</tspan>
  </text>
  ```
- `textElement.text()` returns only `"Line 1"`, not `"Line 1\nLine 2"`!

**Solution Required:**
```javascript
// Extract text from all tspan elements
function extractTextFromSVG(textElement) {
    const node = textElement.node();
    if (!node) return '';
    
    // Check if it has tspan children
    const tspans = textElement.selectAll('tspan');
    if (!tspans.empty() && tspans.size() > 0) {
        // Multiple lines - join with \n
        const lines = [];
        tspans.each(function() {
            const tspanText = d3.select(this).text();
            lines.push(tspanText);
        });
        return lines.join('\n');
    } else {
        // Single line - use text() directly
        return textElement.text() || '';
    }
}

// Usage
text = extractTextFromSVG(textElement);
```

**Action Required:** Fix text extraction in both files before implementing rendering fixes.

---

### ✅ Node Dimensions - Adaptive Sizing Review

**Current State - Width (All Diagrams):**
- ✅ **All diagrams** measure text width adaptively based on actual text content
- ✅ Use measurement functions: `measureTextWidth()`, `measureLineWidth()`, `getTextRadius()`, `getComputedTextLength()`
- ✅ Node width = measured text width + padding

**Current State - Height (Multi-line Support):**
- ✅ **Flowchart** (`flow-renderer.js` line 101-104): Fully adaptive
  ```javascript
  const textWidth = Math.max(...lines.map(l => measureLineWidth(l, fontSize)), 20);
  const textHeight = lines.length * lineHeight; // ✅ Multi-line height
  const w = Math.max(100, textWidth + hPad * 2);
  const h = Math.max(40, textHeight + vPad * 2);
  ```
- ✅ **Concept Map** (`concept-map-renderer.js` line 202-206): Fully adaptive
  ```javascript
  const textWidth = Math.max(...lines.map(l => measureLineWidth(l, fontSize)), 20);
  const boxH = Math.ceil(lines.length * lineHeight + paddingY * 2); // ✅ Multi-line height
  ```
- ⚠️ **Bubble Map**: Uses `getTextRadius()` - adaptive width, but radius assumes single line
  - Current: `getTextRadius(text, fontSize, padding)` - measures width, calculates radius
  - Issue: Radius calculation doesn't account for multi-line height
  - Fix: When adding multi-line support, need to calculate height separately
- ⚠️ **Tree Map** (`tree-renderer.js` line 129): Adaptive width, fixed height
  ```javascript
  const textWidth = node.getComputedTextLength(); // ✅ Adaptive width
  const textHeight = Math.max(1, fontPx * 1.2); // ❌ Fixed single-line height
  ```
- ⚠️ **Flow Map** (`flow-renderer.js` line 346-350): Adaptive width, fixed height
  ```javascript
  const textWidth = Math.max(measureLineWidth(text, fontSize), 20); // ✅ Adaptive width
  h: Math.max(42, fontSize + vPad * 2) // ❌ Fixed single-line height
  ```
- ⚠️ **Multi-Flow Map** (`flow-renderer.js` line 1490-1491): Adaptive width, fixed height
  ```javascript
  const s = measureTextSize(text, fontSize); // ✅ Measures width
  h: s.h + padding * 2 // ❌ s.h is single-line height
  ```
- ⚠️ **Brace Map** (`brace-renderer.js` line 244-252): Adaptive width, fixed height
  ```javascript
  const textWidth = Math.max(measureLineWidth(text, fontSize), 20); // ✅ Adaptive width
  // Height is fixed based on fontSize, not calculated
  ```
- ⚠️ **Mind Map**: Uses `getTextRadius()` - adaptive width, but radius assumes single line
- ⚠️ **Circle Map**: Uses `getTextRadius()` - adaptive width, but radius assumes single line
- ⚠️ **Double Bubble Map**: Uses `getTextRadius()` - adaptive width, but radius assumes single line
- ⚠️ **Bridge Map**: Fixed dimensions - doesn't measure text

**Summary:**
- ✅ **Width**: All diagrams are adaptive to text content (characters and length)
- ✅ **Height (with wrapping)**: Flowchart and Concept Map already adaptive
- ⚠️ **Height (without wrapping)**: All other diagrams use fixed single-line height
- ⚠️ **Height (after adding multi-line)**: Need to update to `lines.length * lineHeight`

**Action Required:** 
- When adding multi-line support, update height calculations in all 9 diagrams
- For circular nodes (Bubble/Circle/Double Bubble/Mind Map), may need separate height calculation
- Width calculations are already adaptive and will work correctly with multi-line (uses longest line)

---

### ✅ Save/Load from Backend

**Status:** ✅ Already works correctly
- Spec is stored as JSON in backend
- JSON preserves `\n` characters in strings
- When loading, spec contains text with `\n` intact
- **Action:** No changes needed

---

### ✅ Undo/Redo

**Status:** ✅ Already works correctly
- History stores spec snapshots: `JSON.parse(JSON.stringify(spec))`
- JSON preserves `\n` characters
- When undoing/redoing, spec with `\n` is restored
- **Action:** No changes needed

---

### ⚠️ Copy/Paste

**Status:** ⚠️ Needs verification
- If copying text from properties panel: Should work (textarea preserves `\n`)
- If copying from diagram: May only copy first line if using `.text()`
- **Action:** Test after implementation, may need fixes

---

### ⚠️ LLM Validation/Extraction

**File:** `static/js/managers/toolbar/llm-validation-manager.js` (line 413)
- Uses `textElement.text()` to extract text from nodes
- **Issue:** Same problem as properties panel loading - only gets first line
- **Action:** Use same fix as properties panel loading

---

## Updated Implementation Checklist

### Phase 1: Fix Text Extraction (CRITICAL - Do First)
- [ ] Fix `loadNodeProperties()` in `toolbar-manager.js` to extract all tspan lines
- [ ] Fix `loadNodeProperties()` in `property-panel-manager.js` to extract all tspan lines
- [ ] Fix `extractExistingNodes()` in `llm-validation-manager.js` to extract all tspan lines
- [ ] Test: Select node with multi-line text, verify properties panel shows all lines

### Phase 2: Add Helper Function
- [ ] Add `splitTextLines()` to `shared-utilities.js`
- [ ] Export in `MindGraphUtils` and globally

### Phase 3: Update Renderers (9 diagrams)
- [ ] Bubble Map - Add line break support + update dimensions
- [ ] Tree Map - Add line break support + update dimensions
- [ ] Brace Map - Add line break support + update dimensions
- [ ] Flow Map - Add line break support + update dimensions
- [ ] Multi-Flow Map - Add line break support + update dimensions
- [ ] Mind Map - Add line break support + update dimensions
- [ ] Circle Map - Add line break support + update dimensions
- [ ] Double Bubble Map - Add line break support + update dimensions
- [ ] Bridge Map - Add line break support + update dimensions

### Phase 4: Testing
- [ ] Test text input/output cycle: Type → Apply → Select → Edit → Apply
- [ ] Test export: PNG, SVG, JSON
- [ ] Test node dimensions: Height increases with more lines
- [ ] Test edge cases: Empty lines, multiple newlines, etc.
- [ ] Test copy/paste functionality
- [ ] Test undo/redo with multi-line text

---

---

## Adaptive Sizing & Async Patterns Review

### ✅ Adaptive Sizing Status

**Canvas Dimensions:**
- ✅ **All renderers** use adaptive dimensions:
  - Primary: `spec._recommended_dimensions` (from Python agent based on window size)
  - Fallback: `dimensions` parameter
  - Default: Hardcoded fallbacks (700x500, 800x600, etc.) - only used if no dimensions provided
- ✅ **Node sizes** are adaptive to text content:
  - Width: Measured using `measureTextWidth()`, `measureLineWidth()`, `getTextRadius()`, `getComputedTextLength()`
  - Height: Currently single-line, will be adaptive after multi-line support added

**Hardcoded Values Found (Acceptable):**
- Default canvas dimensions (700x500, etc.) - ✅ Acceptable as fallback when no dimensions provided
- Padding values (40, 80, etc.) - ✅ Acceptable as design constants
- Spacing values (stepSpacing: 40, etc.) - ✅ Acceptable as design constants
- Minimum sizes (min radius: 30, min width: 100, etc.) - ✅ Acceptable as design constraints

**Hardcoded Values That Should Be Adaptive:**
- ⚠️ **Bridge Map** (`flow-renderer.js` line 1021): `const textHeight = 40;` - Should be calculated based on text content
  - Current: Fixed 40px height
  - Should be: Calculated based on number of lines after adding multi-line support
- ⚠️ **Bridge Map** (`flow-renderer.js` line 1123): `const rectHeight = 30;` - Should be adaptive to text content
  - Current: Fixed 30px for first pair rectangle
  - Should be: Calculated based on number of lines after adding multi-line support

**Action Required:**
- When adding multi-line support to Bridge Map, make `textHeight` and `rectHeight` adaptive
- All other hardcoded values are acceptable (fallbacks, constants, minimums)

---

### ✅ Async Patterns Status

**Renderer Functions:**
- ✅ **All renderer functions are synchronous** - This is correct
  - `renderFlowchart()`, `renderBubbleMap()`, `renderTreeMap()`, etc. are all synchronous
  - They perform DOM operations synchronously (D3.js operations)
  - No async operations needed (no network calls, no file I/O)

**Renderer Dispatcher:**
- ✅ **`renderGraph()` is async** (`renderer-dispatcher.js` line 20)
  - Handles dynamic loading of renderer modules
  - Uses `await window.dynamicRendererLoader.renderGraph()`
  - Properly awaited in `interactive-editor.js` line 427: `await renderGraph(...)`

**Call Chain:**
```
interactive-editor.js: renderDiagram() [async]
  └─> await renderGraph() [async dispatcher]
      └─> await dynamicRendererLoader.renderGraph() [async loader]
          └─> renderFlowchart() [sync - actual rendering]
```

**Status:** ✅ **All async patterns are correct**
- Dispatcher is async (for dynamic loading) ✅
- Renderers are sync (DOM operations) ✅
- Properly awaited in editor ✅

**Action Required:** None - async patterns are already correct

---

**Document Status:** Complete Review - Ready for Implementation  
**Last Updated:** 2025-01-XX  
**Critical Issues Found:** 1 (Text extraction from SVG)  
**Adaptive Sizing:** ✅ Mostly adaptive, 2 hardcoded values in Bridge Map need fixing  
**Async Patterns:** ✅ All correct

