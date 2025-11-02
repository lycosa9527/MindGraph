# Brace Map Node Palette System - Code Review

**Date:** 2025-11-02  
**Reviewer:** AI Assistant  
**Component:** `static/js/editor/node-palette-manager.js` & related files

## Expected Workflow

1. ✅ **Pre-load dimensions** when ThinkGuide opens (background loading)
2. ✅ **Wait for user to pick ONE dimension** (radio button behavior - single selection)
3. ✅ **Lock dimensions tab** after selection
4. ✅ **Generate parts** based on selected dimension (Stage 2)
5. ✅ **Lock parts tab** after selection
6. ✅ **Generate subparts** with dynamic tabs per part (Stage 3)

## Code Review Findings

### ✅ **WORKING CORRECTLY**

#### 1. Stage Detection (Lines 1667-1713)
- Correctly detects current stage from diagram data
- Handles Stage 1 (dimensions), Stage 2 (parts), Stage 3 (subparts)
- Properly extracts dimension and parts from existing diagram

#### 2. Single Dimension Selection (Lines 501-540)
- ✅ Takes `selectedTexts[0]` - enforces single selection
- ✅ Radio button behavior implemented (Lines 3542-3562)
- ✅ Clears previous selection when new one is clicked
- ✅ Locks dimensions tab after selection

#### 3. Stage Progression (Lines 501-629)
- ✅ Stage 1→2: Locks dimensions, moves to parts
- ✅ Stage 2→3: Locks parts, creates dynamic tabs, generates subparts
- ✅ Proper stage generation incrementing
- ✅ Tab locking at each stage

#### 4. Tab UI Management (Lines 2067-2102)
- ✅ Visual disabling of parts tab in Stage 1
- ✅ Tab locking for dimensions in Stage 2
- ✅ Tab locking for both in Stage 3
- ✅ Alert prevents invalid tab switching

#### 5. Auto-Loading on Open (Lines 2220-2256)
- ✅ Auto-loads dimensions for Stage 1
- ✅ Auto-loads parts for Stage 2
- ✅ Auto-loads subparts for Stage 3 (per-part tabs)

#### 6. Node Assembly (Lines 4826-4971)
- ✅ Properly assembles brace map structure
- ✅ Groups subparts by part using `node.mode`
- ✅ Handles empty subparts correctly
- ✅ Sets dimension in diagram spec

### ⚠️ **CRITICAL ISSUES FOUND**

#### 1. **PRE-LOADING NOT IMPLEMENTED FOR BRACE MAP** ❌

**Location:** `node-palette-manager.js:1482-1548`

**Issue:**
```javascript
} else if (this.diagramType === 'tree_map') {
    // Tree map: Don't pre-load - it has complex 3-stage workflow
    console.log('[NodePalette-Preload] Skipping tree_map pre-load (uses multi-stage workflow)');
    return;
} else {
    // Other diagrams: load single batch (4 LLMs)
    console.log('[NodePalette-Preload] Standard diagram - firing catapult (4 LLMs)');
    await this.loadNextBatch();
}
```

**Problem:** Brace map is NOT explicitly handled in the preload function. It falls through to the `else` case which would:
- Try to preload with generic logic
- BUT: Generic preload doesn't respect staged workflow
- Could cause confusion: preloading might happen for wrong stage

**Expected Behavior:**
- Preload Stage 1 dimensions ONLY when no dimension is selected
- Similar to how tree_map should work

**Fix Required:**
```javascript
} else if (this.diagramType === 'tree_map') {
    // Tree map: Pre-load Stage 1 dimensions if no dimension selected
    const hasDimension = diagramData?.dimension?.trim().length > 0;
    if (!hasDimension) {
        // Initialize staged workflow
        this.currentStage = 'dimensions';
        this.currentTab = 'dimensions';
        // Pre-load dimensions
        await this.loadNextBatch();
    }
} else if (this.diagramType === 'brace_map') {
    // Brace map: Pre-load Stage 1 dimensions if no dimension selected
    const hasDimension = diagramData?.dimension?.trim().length > 0;
    if (!hasDimension) {
        console.log('[NodePalette-Preload] Brace map Stage 1 - pre-loading dimensions');
        this.currentStage = 'dimensions';
        this.currentTab = 'dimensions';
        // Initialize tab storage
        if (!this.tabNodes) {
            this.tabNodes = { dimensions: [], parts: [] };
            this.tabSelectedNodes = { dimensions: new Set(), parts: new Set() };
        }
        // Pre-load dimensions
        await this.loadNextBatch();
    } else {
        console.log('[NodePalette-Preload] Brace map has dimension - skipping preload');
    }
} else {
    // Other diagrams: load single batch (4 LLMs)
    console.log('[NodePalette-Preload] Standard diagram - firing catapult (4 LLMs)');
    await this.loadNextBatch();
}
```

#### 2. **PRELOAD FUNCTION DOESN'T INITIALIZE STAGED WORKFLOW** ❌

**Location:** `node-palette-manager.js:1482-1548`

**Issue:** The `preload()` function doesn't initialize:
- `currentStage`
- `currentTab`  
- `tabNodes` for staged diagrams
- `stageData`

This means even if we add brace_map handling, it won't properly store nodes in tab storage.

**Fix Required:**
Need to initialize staged workflow state in preload function similar to `start()` function.

#### 3. **PRELOAD CHECK LOGIC TOO STRICT** ⚠️

**Location:** `node-palette-manager.js:2128-2153`

**Issue:** The preload detection logic forces loading for Stage 1/2, but doesn't account for preloaded data properly.

**Current Logic:**
```javascript
if (!isResumingStage3Plus) {
    hasPreloadedData = false; // Force loading for Stage 1/2
}
```

**Problem:** If dimensions were preloaded, they should be detected and used, not reloaded.

**Fix Suggestion:**
Check if `tabNodes['dimensions']` has data from preload, and if so, use it.

### 📋 **MINOR IMPROVEMENTS NEEDED**

#### 1. **Preload Function Missing Stage Initialization**

The preload function needs to mirror the initialization logic from `start()`:

**Missing:**
- Stage detection logic
- Tab storage initialization for staged diagrams
- Proper stage/tab state setup

#### 2. **Better Preload Detection**

The preload detection should check:
- If `tabNodes['dimensions']` has nodes from preload
- If current stage matches preloaded data
- Avoid reloading if preload already happened

#### 3. **Error Handling**

Preload errors are caught but don't provide context about which stage failed.

## Recommendations

### Priority 1: Fix Pre-Loading ⚠️ CRITICAL

1. Add explicit brace_map handling in `preload()` function
2. Initialize staged workflow state during preload
3. Pre-load Stage 1 dimensions only when no dimension exists
4. Store preloaded nodes in `tabNodes['dimensions']`

### Priority 2: Improve Preload Detection

1. Check `tabNodes` for preloaded data before forcing reload
2. Distinguish between "no data" and "preloaded data available"

### Priority 3: Code Organization

1. Extract stage initialization logic into reusable function
2. Share initialization between `preload()` and `start()`

## Implementation Plan

1. **Update `preload()` function:**
   - Add brace_map stage detection
   - Initialize tab storage for staged diagrams
   - Pre-load dimensions for Stage 1

2. **Update preload detection:**
   - Check `tabNodes` for existing preloaded data
   - Use preloaded data if available

3. **Test workflow:**
   - Open ThinkGuide → dimensions preload in background
   - Click palette button → dimensions appear instantly
   - Select dimension → locks, moves to parts
   - Select parts → locks, moves to subparts

## Testing Checklist

- [ ] Preload dimensions when ThinkGuide opens (Stage 1)
- [ ] Dimensions appear instantly when palette opens
- [ ] Only one dimension can be selected
- [ ] Dimensions tab locks after selection
- [ ] Parts generate based on selected dimension
- [ ] Parts tab locks after selection
- [ ] Dynamic tabs created for each part
- [ ] Subparts generate correctly per part
- [ ] Tab switching prevented at invalid stages
- [ ] All tabs properly locked at appropriate stages

## Conclusion

The brace map node palette system has **solid stage workflow implementation** but **lacks proper pre-loading support**. The main issue is that preload function doesn't handle brace_map's staged workflow, causing dimensions not to preload in the background.

**Status: 85% Complete** - Core functionality works, but pre-loading needs implementation.

