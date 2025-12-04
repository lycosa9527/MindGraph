# Word Wrapping and Placeholder Rendering - Complete Code Review

## Problem Statement

**CRITICAL INSIGHT:** Text wrapping doesn't work in most diagrams - only flowchart and concept map have wrapping implemented. Properties panel works because it uses HTML textarea with CSS word-wrap (native browser wrapping).

**Current State:**
- ✅ **Properties Panel**: HTML `<textarea>` with CSS `word-wrap: break-word` - works perfectly (native browser wrapping)
- ✅ **Flowchart**: Uses `splitAndWrapText()` + tspan - works
- ✅ **Concept Map**: Uses custom `wrapIntoLines()` + tspan - works  
- ❌ **Bubble Map**: No wrapping (simple `.text()`)
- ❌ **Tree Map**: No wrapping (simple `.text()`)
- ❌ **Brace Map**: No wrapping (removed due to placeholder issues)
- ❌ **Flow Map**: No wrapping (removed due to placeholder issues)

## Root Cause Analysis

### The Real Issue

When wrapping was attempted in brace/flow maps, placeholders stopped rendering. This suggests one of these problems:

1. **Empty text handling**: `splitAndWrapText('')` returns `['']` → empty tspan doesn't render visibly
2. **Measurement function mismatch**: Brace renderer uses different measurement function signature than flowchart
3. **Implementation bugs**: The wrapping code we added had incorrect checks/logic

### Key Differences Between Working and Non-Working Renderers

**Flowchart Renderer (WORKING):**
```javascript
// Simple measurement function
function measureLineWidth(text, fontSize) {
    const t = tempSvg.append('text')
        .attr('x', -9999)
        .attr('y', -9999)
        .attr('font-size', fontSize)
        .text(text || '');
    const w = t.node().getBBox().width;
    t.remove();
    return w;
}

// Usage
const lines = window.splitAndWrapText(txt, THEME.fontNode, maxTextWidth, measureLineWidth);
lines.forEach((line, i) => {
    textEl.append('tspan')
        .attr('x', n.x)
        .attr('dy', i === 0 ? 0 : lineHeight)
        .text(line);  // No checks, just render
});
```

**Brace Renderer (HAD ISSUES):**
```javascript
// Complex measurement function with fontSpec parsing
function measureTextWidth(text, fontSpec, fontWeight = 'normal') {
    const { size, family } = parseFontSpec(fontSpec);
    // ... creates temp SVG, measures, removes
    return width;
}

function measureLineWidth(text, fontSpec, fontWeight = 'normal') {
    return measureTextWidth(text, fontSpec, fontWeight);
}

// Previous usage (had issues):
const lines = window.splitAndWrapText(text, fontSize, maxWidth, measureFn);
// Had checks for empty lines that might have broken things
```

**Concept Map (WORKING):**
```javascript
// Simple measurement, similar to flowchart
function measureLineWidth(text, fontSize) {
    const container = getMeasurementContainer();
    const t = container.append('svg').append('text')
        .attr('font-size', fontSize)
        .text(text);
    const w = t.node().getBBox().width;
    t.remove();
    return w;
}

// Usage
const lines = wrapIntoLines(text, fontSize, maxWidth);
lines.forEach((ln, i) => {
    textEl.append('tspan')
        .attr('x', x)
        .attr('dy', i === 0 ? 0 : lineHeight)
        .text(ln);  // No checks
});
```

### Critical Finding: Measurement Function Signature Mismatch

**`splitAndWrapText` expects:**
```javascript
measureFn(candidate, fontSize)  // (text, fontSize) => number
```

**But brace renderer's `measureLineWidth` signature is:**
```javascript
measureLineWidth(text, fontSpec, fontWeight)  // (text, fontSpec, fontWeight) => number
```

**This mismatch could cause:**
- Incorrect width measurements
- Wrapping at wrong points
- Empty arrays returned
- Rendering failures

## Solution Options

### Option 1: Fix Measurement Function Signature ⭐ RECOMMENDED

**Approach:** Create a wrapper function that matches `splitAndWrapText`'s expected signature.

**Pros:**
- Minimal changes
- Works with existing `splitAndWrapText`
- Consistent with flowchart pattern
- Fixes root cause

**Cons:**
- Need to create wrapper for each renderer

**Implementation:**
```javascript
// In brace-renderer.js
function measureLineWidthForWrap(text, fontSize) {
    // Create wrapper that matches splitAndWrapText's expected signature
    const fontSpec = `${fontSize}px ${parseFontSpec(THEME.fontPart).family}`;
    return measureTextWidth(text, fontSpec, 'bold');
}

// Usage
const lines = window.splitAndWrapText(text, fontSize, maxWidth, measureLineWidthForWrap);
const textEl = svg.append('text')...;
lines.forEach((line, i) => {
    textEl.append('tspan')
        .attr('x', x)
        .attr('dy', i === 0 ? 0 : lineHeight)
        .text(line);  // No checks - trust splitAndWrapText
});
```

---

### Option 2: Fix `splitAndWrapText` to Handle Empty Text

**Approach:** Modify `splitAndWrapText` to return non-empty string for empty input.

**Pros:**
- Centralized fix
- All renderers benefit
- Handles edge case

**Cons:**
- Doesn't fix measurement function mismatch
- May mask other issues

**Implementation:**
```javascript
function splitAndWrapText(text, fontSize, maxWidth, measureFn) {
    const textStr = String(text || '');
    const allLines = [];
    
    // ... existing wrapping logic ...
    
    // CRITICAL FIX: Ensure at least one renderable line
    if (allLines.length === 0 || (allLines.length === 1 && allLines[0] === '')) {
        return ['\u00A0']; // Non-breaking space ensures element renders
    }
    
    return allLines;
}
```

---

### Option 3: Use Concept Map's `wrapIntoLines` Pattern

**Approach:** Each renderer implements its own wrapping function (like concept map).

**Pros:**
- Renderer-specific control
- No signature mismatch issues
- Can optimize per diagram type

**Cons:**
- Code duplication
- More maintenance
- Inconsistent implementations

---

### Option 4: Unified Wrapper Function

**Approach:** Create a unified wrapper that handles signature conversion automatically.

**Pros:**
- Single solution for all renderers
- Handles signature differences
- Backward compatible

**Cons:**
- More complex
- Need to detect function signature

**Implementation:**
```javascript
// In shared-utilities.js
function createMeasureWrapper(measureFn, fontSpec, fontWeight) {
    return function(text, fontSize) {
        // If measureFn expects (text, fontSize), use directly
        if (measureFn.length === 2) {
            return measureFn(text, fontSize);
        }
        // If measureFn expects (text, fontSpec, fontWeight), convert
        if (measureFn.length === 3) {
            const spec = fontSpec || `${fontSize}px Inter, sans-serif`;
            return measureFn(text, spec, fontWeight || 'normal');
        }
        // Fallback
        return measureFn(text);
    };
}
```

---

## Recommendation

**Option 1 + Option 2 Combined** is recommended:

1. **Fix measurement function signature** (Option 1) - This is likely the root cause
2. **Fix empty text handling** (Option 2) - Safety net for edge cases
3. **Restore wrapping code** using flowchart pattern (no extra checks)

**Why This Approach:**
- ✅ Addresses measurement function mismatch (likely root cause)
- ✅ Handles empty text edge case
- ✅ Uses proven pattern from flowchart renderer
- ✅ Minimal changes, low risk

**Implementation Steps:**
1. Fix `splitAndWrapText()` to return `['\u00A0']` for empty input
2. Create measurement wrapper functions in brace/flow renderers
3. Restore wrapping code exactly like flowchart (simple forEach, no checks)
4. Test with empty text, placeholder text, and long text

## Testing Checklist

- [ ] Empty text nodes render (show space)
- [ ] Placeholder text ("Part 1", "Step 1") renders correctly
- [ ] Long text wraps properly at maxWidth
- [ ] Multi-line text (with \n) renders correctly
- [ ] Text editing still works after rendering
- [ ] All node types work correctly
- [ ] Measurement function returns correct widths
- [ ] No console errors during rendering
