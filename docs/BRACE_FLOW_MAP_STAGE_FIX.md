# Brace Map / Flow Map / Mindmap Stage Bug Fix

## Issue Summary

When advancing from one stage to another in brace map, flow map, or mindmap node palettes, nodes were being tagged with the wrong stage. For example, when advancing from `dimensions` to `parts` in brace map, the backend was still generating nodes with `mode='dimensions'` instead of `mode='parts'`.

## Root Cause

The API router (`routers/thinking.py`) was only passing `stage` and `stage_data` parameters to the backend generator for `tree_map`, but not for `brace_map`, `flow_map`, or `mindmap`. These diagrams fell into the default `else` block which called `generator.generate_batch()` without the stage parameters.

This caused the backend generators to use their default stage values:
- `brace_map`: default stage = `'dimensions'` (should use the requested stage)
- `flow_map`: default stage = `'dimensions'` (should use the requested stage)
- `mindmap`: default stage = `'branches'` (should use the requested stage)

## The Fix

Updated both `/start` and `/next_batch` endpoints in `routers/thinking.py` to include `brace_map`, `flow_map`, and `mindmap` in the multi-stage diagram handling:

**Before:**
```python
elif req.diagram_type == 'tree_map':
    # Tree maps: pass stage and stage_data for multi-stage workflow
    logger.info("[NodePalette-API] Tree map stage: %s | Stage data: %s", stage, stage_data)
    async for chunk in generator.generate_batch(
        session_id=session_id,
        center_topic=center_topic,
        educational_context=req.educational_context,
        nodes_per_llm=15,
        stage=stage,  # dimensions, categories, or children
        stage_data=stage_data  # dimension, category_name, etc.
    ):
        ...
else:
    # Other diagram types: standard call (NO stage parameters!)
    async for chunk in generator.generate_batch(
        session_id=session_id,
        center_topic=center_topic,
        educational_context=req.educational_context,
        nodes_per_llm=15
    ):
        ...
```

**After:**
```python
elif req.diagram_type in ['tree_map', 'brace_map', 'flow_map', 'mindmap']:
    # Multi-stage diagrams: pass stage and stage_data for progressive workflow
    logger.info("[NodePalette-API] %s stage: %s | Stage data: %s", req.diagram_type, stage, stage_data)
    async for chunk in generator.generate_batch(
        session_id=session_id,
        center_topic=center_topic,
        educational_context=req.educational_context,
        nodes_per_llm=15,
        stage=stage,  # Current stage (dimensions, categories, parts, etc.)
        stage_data=stage_data  # Stage-specific data (dimension, category_name, part_name, etc.)
    ):
        ...
else:
    # Other diagram types: standard call
    async for chunk in generator.generate_batch(
        session_id=session_id,
        center_topic=center_topic,
        educational_context=req.educational_context,
        nodes_per_llm=15
    ):
        ...
```

## Files Modified

1. **`routers/thinking.py`**: 
   - `/start` endpoint (lines 282-296)
   - `/next_batch` endpoint (lines 404-418)

2. **`static/js/editor/node-palette-manager.js`**:
   - `advanceBraceMapToNextStage()` - Added `attachTabButtonListeners()` call after creating dynamic part tabs in Stage 3
   - `advanceFlowMapToNextStage()` - Added `attachTabButtonListeners()` call after creating dynamic step tabs in Stage 3

## Additional Bug Fix: Tab Switching in Stage 3

### Issue
In Stage 3 of brace map and flow map, after selecting multiple parts/steps, dynamic tabs were created but the tab buttons were not clickable. Users could only interact with the first tab.

### Root Cause
After calling `showDynamicCategoryTabsUI()` to create the tab buttons, the code was not calling `attachTabButtonListeners()` to attach click event listeners to the newly created tabs.

**Tree Map (correct):**
```javascript
this.showDynamicCategoryTabsUI(selectedCategories);
this.attachTabButtonListeners();  // ✅ Event listeners attached
```

**Brace Map & Flow Map (incorrect):**
```javascript
this.showDynamicCategoryTabsUI(selectedParts);
// Missing: this.attachTabButtonListeners();  // ❌ No event listeners!
```

### Fix
Added `this.attachTabButtonListeners();` after `showDynamicCategoryTabsUI()` in both:
- `advanceBraceMapToNextStage()` (Stage 2→3 transition)
- `advanceFlowMapToNextStage()` (Stage 2→3 transition)

## Impact

This fix ensures that:
1. **Brace Map**: When advancing from `dimensions` → `parts` → `subparts`, nodes are correctly tagged with the current stage, and all part tabs are clickable in Stage 3
2. **Flow Map**: When advancing from `dimensions` → `steps` → `substeps`, nodes are correctly tagged with the current stage, and all step tabs are clickable in Stage 3
3. **Mindmap**: When advancing from `branches` → `children`, nodes are correctly tagged with the current stage (mindmap already had correct tab listener attachment)

## Testing

### Test 1: Stage Progression (Backend Fix)
1. Create a new brace map
2. Generate dimension nodes (Stage 1)
3. Select a dimension and click "Next"
4. Verify that the parts tab now shows nodes with `mode='parts'` instead of `mode='dimensions'`
5. Backend logs should show: `[BraceMapPalette] Stage: parts` instead of `[BraceMapPalette] Stage: dimensions`
6. Console should show no "Node mode mismatch" warnings

### Test 2: Tab Switching (Frontend Fix)
1. Create a new brace map
2. Generate and select a dimension (Stage 1)
3. Click "Next" to advance to Stage 2 (parts)
4. Select **multiple parts** (e.g., 3 different parts)
5. Click "Next" to advance to Stage 3 (subparts)
6. Verify that you see **3 tabs** (one for each selected part)
7. **Click on each tab** and verify:
   - Tab switches successfully
   - Nodes load for each tab
   - You can select nodes in all tabs, not just the first one
8. Repeat for flow map (dimensions → steps → substeps)

## Related Issues

This was the real root cause of the "Node mode mismatch" warnings seen in the console. The stage generation counter and AbortController mechanisms were working correctly, but the backend was generating nodes with the wrong stage because it never received the correct stage parameter.

## Date

October 19, 2025

## Author

MindGraph Team (with AI assistance)


