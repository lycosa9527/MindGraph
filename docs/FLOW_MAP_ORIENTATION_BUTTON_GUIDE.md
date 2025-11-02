# Flow Map Orientation Button - Implementation Guide

## Overview
Add a canvas button labeled "转向" or "Flip" to toggle flow maps between vertical and horizontal orientations.

## Layout Confirmation

**✅ Confirmed Layout for Horizontal Mode:**
- **Steps**: Arranged horizontally (side by side, left to right)
- **Substeps**: Positioned **BELOW** each step node (not to the side)
- Each step's substeps are vertically stacked underneath that step
- This is the natural "flip" from vertical mode where substeps are to the right

## Button Visibility Confirmation

**✅ CONFIRMED: Orientation button appears ONLY for flow maps**
- **Button visibility**: ONLY when `diagramType === 'flow_map'`
- **NOT shown for**: multi_flow_map, tree_map, circle_map, bubble_map, or any other diagram type
- **Removal**: Button is automatically removed when switching to any other diagram type
- **Re-appearance**: Button appears automatically when switching to flow map

---

## Step 1: Add Orientation Property to Flow Map Spec

### 1.1 Location
- **File**: `static/js/renderers/flow-renderer.js`
- **Function**: `renderFlowMap()`

### 1.2 Changes
- Check for `spec.orientation` property (default to `'vertical'`)
- Store orientation in spec: `spec.orientation = spec.orientation || 'vertical'`
- This allows the renderer to know which layout to use

### 1.3 Implementation Details
```javascript
// At the start of renderFlowMap function
const orientation = spec.orientation || 'vertical'; // 'vertical' | 'horizontal'
```

---

## Step 2: Implement Horizontal Layout Logic

### 2.1 Location
- **File**: `static/js/renderers/flow-renderer.js`
- **Function**: `renderFlowMap()`

### 2.2 Changes Required

#### A. Position Calculation

**Current (Vertical) Layout:**
```
    [Title]
      |
    [Step 1] ──→ [Substep 1.1]
      |           [Substep 1.2]
      ↓
    [Step 2] ──→ [Substep 2.1]
      |
      ↓
    [Step 3]
```
- Title: top center
- Steps: vertical stack (all at same X = centerX, varying Y positions)
- Substeps: positioned to the **right** of each step (same Y grouping as their step)

**New (Horizontal) Layout:**
```
    [Title]
      |
    [Step 1] ──→ [Step 2] ──→ [Step 3]
      |            |            |
      ↓            ↓            ↓
    [Substep 1.1] [Substep 2.1] [Substep 3.1]
    [Substep 1.2] [Substep 2.2]
```
- Title: top center (same)
- Steps: horizontal row (all at same Y = centerY, varying X positions)
- Substeps: positioned **below** each step (same X alignment as their step)

#### B. Arrow Direction
- **Vertical**: Arrows point down (`y1` → `y2`, same `x`)
- **Horizontal**: Arrows point right (`x1` → `x2`, same `y`)

#### C. L-shaped Connectors

**Vertical Mode:**
- Step → Substep connector path:
  1. Horizontal line from step's **right edge** 
  2. Vertical line **down** to substep's Y level
  3. Horizontal line **right** to substep

**Horizontal Mode:**
- Step → Substep connector path:
  1. Vertical line from step's **bottom edge**
  2. Horizontal line **right** (if multiple substeps, this connects them)
  3. Vertical line **down** to each substep

#### D. Canvas Dimensions
- **Vertical**: Calculate based on `maxStepHeight + substepsHeight`
- **Horizontal**: Calculate based on `totalStepWidth + maxSubstepWidth`

### 2.3 Key Variables to Swap (Based on Actual Code)

**Current Variables (Vertical Mode):**
- `centerX = baseWidth / 2` - Steps all use same X
- `stepXCenter = centerX` (line 534) - Fixed X for all steps
- `stepYCenter = stepCenters[index]` - Varying Y positions
- `subOffsetX = 40` (line 328) - Gap between step and substeps (to the right)
- Substeps X: `centerX + stepSizes[stepIdx].w / 2 + subOffsetX` (line 427)
- Substeps Y: `currentSubY` - Varies and increments

**For Horizontal Mode:**
- `centerY = baseHeight / 2` - Steps all use same Y
- `stepXCenter = stepCenters[index]` - Varying X positions (calculate based on step widths + spacing)
- `stepYCenter = centerY` - Fixed Y for all steps
- `subOffsetY = 40` - Gap between step and substeps (below)
- Substeps X: `stepXCenter` (aligned with step)
- Substeps Y: `stepYCenter + stepSizes[stepIdx].h / 2 + subOffsetY + (accumulated substep Y)`

**Step Center Calculation (lines 441-464):**
- Current: `stepCenters` is array of Y positions
- Horizontal: `stepCenters` should be array of X positions
- Logic: If substeps exist, center step on its substep group (X-center of substeps)
- Logic: If no substeps, use sequential horizontal spacing (prev step right edge + spacing)

**Key Code Locations to Modify:**
- Line 386: `const centerX` → needs `const centerY` for horizontal
- Line 427: Substeps X calculation → use `stepXCenter` instead
- Line 428: Substeps Y calculation → use `stepYCenter + step.h/2 + subOffsetY` 
- Line 496: `stepRightX` → `stepBottomY` for horizontal
- Line 503-528: L-shaped connector paths need to be swapped

### 2.4 Implementation Approach

**Option 1: Conditional Logic (Recommended)**
Add `if (orientation === 'horizontal')` blocks throughout the function to handle both modes. This keeps all code in one place.

**Option 2: Separate Functions**
Extract horizontal layout logic into separate helper functions, keeping the main function cleaner but requiring more refactoring.

**Recommended Structure:**
```javascript
function renderFlowMap(spec, theme = null, dimensions = null) {
    const orientation = spec.orientation || 'vertical';
    
    // ... theme setup, measurements (same for both) ...
    
    if (orientation === 'vertical') {
        // Current vertical layout code (lines 386-662)
    } else {
        // New horizontal layout code
        // - Calculate step X positions (horizontal spacing)
        // - Position substeps below each step
        // - Draw horizontal arrows between steps
        // - Draw inverted L-shaped connectors (down, then right)
    }
}
```

---

## Step 3: Add Canvas Button to Flow Maps

### 3.1 Location
- **File**: `static/js/editor/interactive-editor.js`
- **Method**: Add new method `addFlowMapOrientationButton()`
- **Call Location**: In `renderDiagram()` method, after `enableZoomAndPan()`

### 3.2 Implementation Pattern
Follow the pattern from `addMobileZoomControls()` (lines 762-802):

**CRITICAL: Button must ONLY appear for flow maps**

```javascript
addFlowMapOrientationButton() {
    // ONLY show for flow_map diagram type
    if (this.diagramType !== 'flow_map') {
        return; // Exit immediately if not a flow map
    }
    
    // Check if button already exists (prevent duplicates)
    if (document.getElementById('flow-map-orientation-controls')) {
        return;
    }
    
    // Create button HTML with ID: `flow-map-orientation-btn`
    // Insert into `#d3-container` (same as zoom controls)
    // Add click event listener
}
```

**Key Requirements:**
- Check `this.diagramType === 'flow_map'` FIRST (early return if not flow map)
- Only create button if diagram type is flow_map
- Remove button when switching away from flow map (see Step 8)

### 3.3 Button HTML Structure
```html
<div id="flow-map-orientation-controls" class="flow-map-controls">
    <button id="flow-map-orientation-btn" class="flow-map-control-btn" title="转向 / Flip Orientation">
        <span>转向</span>
    </button>
</div>
```

### 3.4 Button Position
- Top-right corner of canvas (similar to mobile zoom controls)
- Use absolute positioning within `#d3-container`
- Position: `top: 10px; right: 10px;` (or adjust based on existing controls)

---

## Step 4: Implement Flip Functionality

### 4.1 Location
- **File**: `static/js/editor/interactive-editor.js`
- **Method**: Add new method `flipFlowMapOrientation()`

### 4.2 Implementation Steps

#### A. Get Current Spec
```javascript
const currentSpec = this.currentSpec;
if (!currentSpec || this.diagramType !== 'flow_map') {
    return;
}
```

#### B. Toggle Orientation
```javascript
const currentOrientation = currentSpec.orientation || 'vertical';
const newOrientation = currentOrientation === 'vertical' ? 'horizontal' : 'vertical';
currentSpec.orientation = newOrientation;
```

#### C. Save to History
```javascript
this.saveToHistory('flip_orientation', { 
    orientation: newOrientation 
});
```

#### D. Re-render Diagram
```javascript
this.renderDiagram();
```

### 4.3 Event Listener
```javascript
document.getElementById('flow-map-orientation-btn').addEventListener('click', () => {
    this.flipFlowMapOrientation();
});
```

---

## Step 5: Update Renderer Dispatcher

### 5.1 Location
- **File**: `static/js/renderers/renderer-dispatcher.js` (or wherever `renderGraph` is defined)
- **Purpose**: Ensure orientation parameter is passed to `renderFlowMap()`

### 5.2 Verification
- Check that `renderFlowMap(spec, theme, dimensions)` receives the full spec
- The `spec.orientation` should automatically be passed through
- No changes needed if spec is passed as-is

---

## Step 6: Add CSS Styling

### 6.1 Location
- **File**: `static/css/editor.css` (or create new `flow-map-controls.css`)

### 6.2 CSS Styles
```css
/* Flow Map Orientation Controls */
.flow-map-controls {
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 1000;
    display: flex;
    gap: 8px;
}

.flow-map-control-btn {
    background-color: rgba(255, 255, 255, 0.9);
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    color: #333;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    transition: all 0.2s ease;
}

.flow-map-control-btn:hover {
    background-color: #fff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transform: translateY(-1px);
}

.flow-map-control-btn:active {
    transform: translateY(0);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}
```

### 6.3 Responsive Considerations
- Button should be visible on both desktop and mobile
- Consider hiding if canvas is too small
- Ensure button doesn't overlap with zoom controls on mobile

---

## Step 7: State Persistence

### 7.1 Location
- **File**: `static/js/editor/interactive-editor.js`
- **Method**: `saveToHistory()` (already exists)

### 7.2 Implementation
- Orientation is part of `currentSpec`, so it's automatically saved to history
- Undo/redo will restore orientation state
- When exporting or saving, orientation will be included in the spec

### 7.3 Validation
- Check that orientation persists through:
  - Undo/redo operations
  - Auto-complete operations
  - Node palette operations
  - Template loading (should default to 'vertical')

---

## Step 8: Cleanup on Diagram Change

### 8.1 Location
- **File**: `static/js/editor/interactive-editor.js`
- **Method**: `renderDiagram()` or diagram change handlers

### 8.2 Implementation

**CRITICAL: Always remove button when NOT on flow map**

```javascript
// Remove button when switching away from flow map
// This should be called:
// 1. At the start of renderDiagram() before rendering
// 2. When diagram type changes in DiagramSelector

removeFlowMapOrientationButton() {
    const btnContainer = document.getElementById('flow-map-orientation-controls');
    if (btnContainer) {
        btnContainer.remove();
        logger.debug('Editor', 'Removed flow map orientation button');
    }
}

// Call this in renderDiagram() BEFORE rendering:
async renderDiagram() {
    // Remove flow map button if we're not on a flow map
    if (this.diagramType !== 'flow_map') {
        this.removeFlowMapOrientationButton();
    }
    
    // ... rest of rendering code ...
    
    // After rendering, add button ONLY if flow map
    if (this.diagramType === 'flow_map') {
        this.addFlowMapOrientationButton();
    }
}
```

---

## Step 9: Button Visibility Logic

### 9.1 Show Button Only For Flow Maps

**✅ CONFIRMED: Button appears ONLY for flow maps**

**Implementation Checklist:**
- ✅ Check `this.diagramType === 'flow_map'` before adding button (early return if false)
- ✅ Remove button when diagram type changes (in renderDiagram and diagram switch handlers)
- ✅ Never show button for other diagram types (multi_flow_map, tree_map, etc.)
- ✅ Button should not appear in any other context

**Pattern to Follow:**
```javascript
// Pattern from codebase (similar to how flow_map-specific handlers work):
if (this.diagramType === 'flow_map') {
    // Flow map specific code here
} else {
    // Do nothing, or ensure button is removed
}
```

### 9.2 Integration Points
- **Initial Render**: Check in `renderDiagram()` after render completes
- **Diagram Switch**: Remove in diagram selector or editor initialization
- **Re-render**: Check if button exists, if not and diagram is flow_map, add it

---

## Implementation Order

1. **Step 1**: Add orientation property** - Foundation
2. **Step 2**: Implement horizontal layout logic** - Core rendering changes
3. **Step 3**: Add canvas button** - UI element
4. **Step 4**: Implement flip functionality** - Button action
5. **Step 6**: Add CSS styling** - Visual appearance
6. **Step 7**: Verify state persistence** - Testing
7. **Step 8**: Cleanup logic** - Prevent button from appearing on other diagrams
8. **Step 9**: Visibility logic** - Polish

**Note**: Steps 5 (renderer dispatcher) likely needs no changes if spec is passed through correctly.

---

## Testing Checklist

### Functionality
- [ ] Button appears only on flow maps
- [ ] Button toggles between vertical and horizontal
- [ ] Flow map renders correctly in both orientations
- [ ] Steps are positioned correctly in horizontal mode
- [ ] Substeps are positioned correctly in horizontal mode
- [ ] Arrows point in correct direction
- [ ] L-shaped connectors work in both orientations
- [ ] Canvas dimensions adjust correctly

### State Management
- [ ] Orientation persists through undo/redo
- [ ] Orientation persists through auto-complete
- [ ] Orientation is saved in diagram export
- [ ] Orientation defaults to 'vertical' for new/template flow maps

### UI/UX
- [ ] **Button ONLY appears for flow_map (critical requirement)**
- [ ] Button is NOT visible for other diagram types (multi_flow_map, tree_map, circle_map, etc.)
- [ ] Button disappears immediately when switching away from flow map
- [ ] Button reappears when switching back to flow map
- [ ] Button is visible and accessible on flow maps
- [ ] Button styling matches design guidelines
- [ ] Button doesn't overlap with other controls
- [ ] Button works on mobile devices

### Edge Cases
- [ ] Works with flow maps with many steps
- [ ] Works with flow maps with many substeps
- [ ] Works with flow maps with no substeps
- [ ] Works with single-step flow maps

---

## Key Files to Modify

1. **`static/js/renderers/flow-renderer.js`**
   - Modify `renderFlowMap()` to support both orientations
   - Add horizontal layout calculations

2. **`static/js/editor/interactive-editor.js`**
   - Add `addFlowMapOrientationButton()` method
   - Add `flipFlowMapOrientation()` method
   - Call button creation in `renderDiagram()`
   - Add cleanup logic

3. **`static/css/editor.css`** (or new CSS file)
   - Add `.flow-map-controls` styles
   - Add `.flow-map-control-btn` styles

---

## Potential Challenges & Solutions

### Challenge 1: Canvas Dimension Calculation
**Issue**: Horizontal layout needs different width/height calculations  
**Solution**: Create separate calculation functions for vertical vs horizontal, or use conditional logic based on orientation

### Challenge 2: Arrow Direction
**Issue**: Arrows need to point right instead of down  
**Solution**: Swap x/y coordinates and adjust arrowhead rotation (90 degrees)

### Challenge 3: Connector Shapes
**Issue**: L-shaped connectors need different orientation  
**Solution**: For horizontal: vertical line down from step → horizontal line right → vertical line to substep

### Challenge 4: Button Positioning
**Issue**: Button might overlap with zoom controls  
**Solution**: Position button in different corner, or stack vertically with spacing

### Challenge 5: Performance
**Issue**: Re-rendering entire diagram on flip  
**Solution**: This is acceptable - current architecture already does full re-renders on changes

---

## Notes

- **Orientation State**: Stored in `spec.orientation`, so it's part of the diagram data
- **Default Behavior**: New flow maps default to 'vertical' orientation
- **Backward Compatibility**: Existing flow maps without orientation property default to 'vertical'
- **Button Label**: Use "转向" (Chinese) or "Flip" (English) - consider language manager integration for i18n
- **Accessibility**: Add proper ARIA labels and keyboard support if needed

---

## Future Enhancements (Out of Scope)

- Keyboard shortcut for flipping (e.g., 'F' key)
- Animation during orientation change
- Remember user's preferred orientation in user settings
- Orientation indicator (small icon showing current orientation)

---

## Estimated Complexity

- **Rendering Logic Changes**: Medium-High (requires careful coordinate swapping)
- **UI Button**: Low (similar to existing zoom controls)
- **State Management**: Low (leverages existing spec structure)
- **CSS Styling**: Low (standard button styling)
- **Testing**: Medium (need to test both orientations thoroughly)

**Total Estimated Time**: 4-6 hours for implementation + testing

