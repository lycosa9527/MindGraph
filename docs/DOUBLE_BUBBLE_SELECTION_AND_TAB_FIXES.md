# Double Bubble Map - Selection Tracking & Tab Synchronization Fixes

**Date:** October 15, 2025  
**Author:** lycosa9527  
**Made by:** MindSpring Team

## Problem Summary

Two critical issues were identified with the Double Bubble Map's node palette:

1. **Tab Synchronization Issue**: After adding nodes and returning to the palette, clicking on the similarities tab had no effect. The browser console showed repeated "Already on similarities tab, ignoring" messages, but the UI was actually displaying the differences tab.

2. **Missing Nodes Issue**: When selecting nodes from both similarities and differences tabs and clicking finish, only the differences nodes were being added to the diagram. Similarities selections were being lost.

## Root Causes

### Issue 1: Tab State Desynchronization

**Location:** Multiple points in the tab switching and initialization logic

**Cause:** The internal state variable `this.currentTab` and the DOM state (which tab button had the `active` class) were getting out of sync, causing the system to believe it was on one tab while visually showing another.

**Specific scenarios:**
- When reopening the palette after adding nodes, tab buttons weren't being synced
- When initializing tabs, the DOM wasn't ready when `updateTabButtons()` was called
- No defensive checks to detect and correct desyncs

### Issue 2: Selection Tracking Failure

**Location:** `finishSelection()` and `toggleNodeSelection()` functions

**Cause:** The code had a dual tracking system - `this.selectedNodes` (global) and `this.tabSelectedNodes` (per-tab) - but they weren't being properly synchronized:

1. **Selection Toggle**: When clicking a node, only `this.selectedNodes` was updated, not `this.tabSelectedNodes[currentTab]`
2. **Finish Selection**: Only looked at `this.nodes` (current tab) instead of gathering from both `this.tabNodes['similarities']` and `this.tabNodes['differences']`
3. **Result**: When switching tabs, selections from the previous tab were "lost" because they weren't saved to the tab-specific tracking

## Fixes Implemented

### Fix 1: Tab Synchronization (5 changes)

#### 1.1 Added Tab Sync in `restoreUI()`
**File:** `static/js/editor/node-palette-manager.js:605-626`

```javascript
restoreUI() {
    // ... existing code ...
    
    // Sync tab button states for double bubble map
    if (this.usesTabs()) {
        this.updateTabButtons();
        console.log(`[NodePalette] ✓ Tab buttons synchronized to current tab: ${this.currentTab}`);
    }
    
    this.updateFinishButtonState();
}
```

**Impact:** When reopening the palette, tab buttons now correctly reflect the current tab.

#### 1.2 Added Tab Sync After Initialization
**File:** `static/js/editor/node-palette-manager.js:515-520`

```javascript
// Synchronize tab button states with currentTab
// Use setTimeout to ensure DOM is ready after showTabsUI
setTimeout(() => {
    this.updateTabButtons();
    console.log('[NodePalette] Tab buttons synchronized after initialization');
}, 50);
```

**Impact:** Ensures tab buttons are synced after DOM is fully rendered.

#### 1.3 Added Desync Detection in `switchTab()`
**File:** `static/js/editor/node-palette-manager.js:177-201`

```javascript
switchTab(tabName) {
    if (!this.usesTabs()) return;
    
    // Verify DOM state matches internal state (defensive check for desync)
    const similaritiesBtn = document.getElementById('tab-similarities');
    const differencesBtn = document.getElementById('tab-differences');
    
    const isDomSimilaritiesActive = similaritiesBtn?.classList.contains('active');
    const isDomDifferencesActive = differencesBtn?.classList.contains('active');
    
    // Check if internal state matches DOM state
    const expectedDomState = this.currentTab === 'similarities' ? isDomSimilaritiesActive : isDomDifferencesActive;
    const isDesync = !expectedDomState;
    
    if (isDesync) {
        console.warn(`[NodePalette] STATE DESYNC DETECTED!`);
        console.warn(`  Internal state: currentTab="${this.currentTab}"`);
        console.warn(`  DOM state: similarities=${isDomSimilaritiesActive}, differences=${isDomDifferencesActive}`);
        console.warn(`  User clicked: ${tabName}`);
        console.warn(`  Allowing switch to proceed to fix desync...`);
    }
    
    // Don't switch if already on this tab AND DOM is synced
    // But DO switch if there's a desync (to fix it)
    if (this.currentTab === tabName && !isDesync) {
        console.log(`[NodePalette] Already on ${tabName} tab, ignoring`);
        return;
    }
    
    // ... continue with tab switch ...
}
```

**Impact:** Detects desyncs and allows the tab switch to proceed to fix them, rather than blocking it.

#### 1.4 Clear Stale States in `showTabsUI()`
**File:** `static/js/editor/node-palette-manager.js:388-401`

```javascript
showTabsUI() {
    const tabsContainer = document.getElementById('node-palette-tabs');
    if (tabsContainer) {
        tabsContainer.style.display = 'flex';
        
        // Clear any stale 'active' classes from previous sessions
        const similaritiesBtn = document.getElementById('tab-similarities');
        const differencesBtn = document.getElementById('tab-differences');
        if (similaritiesBtn) similaritiesBtn.classList.remove('active');
        if (differencesBtn) differencesBtn.classList.remove('active');
        
        console.log('[NodePalette] Tab switcher UI shown (stale states cleared)');
    }
}
```

**Impact:** Ensures clean state when showing tabs, preventing carryover from previous sessions.

#### 1.5 Enhanced Logging in `switchTab()`
**File:** `static/js/editor/node-palette-manager.js:240-244`

```javascript
console.log(`[NodePalette] Restored ${tabName} state:`);
console.log(`  - Nodes: ${this.nodes.length}`);
console.log(`  - Selected: ${this.selectedNodes.size}`);
console.log(`  - Selected IDs: ${Array.from(this.selectedNodes).join(', ') || 'none'}`);
console.log(`  - Scroll position: ${savedScrollPos}px`);
```

**Impact:** Better debugging information for tab state transitions.

### Fix 2: Selection Tracking (3 changes)

#### 2.1 Fixed `toggleNodeSelection()` to Update Both Sets
**File:** `static/js/editor/node-palette-manager.js:1358-1454`

**Before:**
```javascript
if (wasSelected) {
    this.selectedNodes.delete(nodeId);
    // ... only updates global Set
} else {
    this.selectedNodes.add(nodeId);
    // ... only updates global Set
}
```

**After:**
```javascript
if (wasSelected) {
    // Deselect: remove from both global and tab-specific Sets
    this.selectedNodes.delete(nodeId);
    
    // For double bubble map: also remove from tab-specific Set
    if (this.usesTabs() && this.tabSelectedNodes && this.currentTab) {
        this.tabSelectedNodes[this.currentTab]?.delete(nodeId);
        console.log(`[NodePalette-Selection] Removed from ${this.currentTab} tab selections`);
    }
} else {
    // Select: add to both global and tab-specific Sets
    this.selectedNodes.add(nodeId);
    
    // For double bubble map: also add to tab-specific Set
    if (this.usesTabs() && this.tabSelectedNodes && this.currentTab) {
        if (!this.tabSelectedNodes[this.currentTab]) {
            this.tabSelectedNodes[this.currentTab] = new Set();
        }
        this.tabSelectedNodes[this.currentTab].add(nodeId);
        console.log(`[NodePalette-Selection] Added to ${this.currentTab} tab selections`);
    }
}
```

**Impact:** Selections are now tracked in both the global Set (for UI) and tab-specific Sets (for persistence).

#### 2.2 Fixed `finishSelection()` to Gather from Both Tabs
**File:** `static/js/editor/node-palette-manager.js:1661-1751`

**Before:**
```javascript
const selectedNodesData = this.nodes.filter(n => 
    this.selectedNodes.has(n.id) && !n.added_to_diagram
);
// Only gathered from current tab (this.nodes)
```

**After:**
```javascript
if (this.usesTabs()) {
    // Merge selections from both tabs
    const simSelected = this.tabSelectedNodes['similarities'] || new Set();
    const diffSelected = this.tabSelectedNodes['differences'] || new Set();
    const mergedSelectedIds = new Set([...simSelected, ...diffSelected]);
    
    // Gather nodes from BOTH tabs
    const simNodes = this.tabNodes['similarities'] || [];
    const diffNodes = this.tabNodes['differences'] || [];
    const allNodes = [...simNodes, ...diffNodes];
    
    // Filter for selected & new nodes
    allSelectedNodes = allNodes.filter(n => 
        mergedSelectedIds.has(n.id) && !n.added_to_diagram
    );
} else {
    // Single-tab diagrams: use existing logic
    allSelectedNodes = this.nodes.filter(n => 
        this.selectedNodes.has(n.id) && !n.added_to_diagram
    );
}
```

**Impact:** All selections from both tabs are now gathered and added to the diagram.

#### 2.3 Updated `updateSelectionCounter()` for Cross-Tab Totals
**File:** `static/js/editor/node-palette-manager.js:1456-1508`

**Before:**
```javascript
if (counter) {
    counter.textContent = `Selected: ${this.selectedNodes.size}/${this.nodes.length}`;
}
// Only showed current tab's count
```

**After:**
```javascript
if (this.usesTabs()) {
    // Double bubble: count across both tabs
    const simSelected = this.tabSelectedNodes['similarities']?.size || 0;
    const diffSelected = this.tabSelectedNodes['differences']?.size || 0;
    totalSelected = simSelected + diffSelected;
    
    const simNodes = this.tabNodes['similarities']?.length || 0;
    const diffNodes = this.tabNodes['differences']?.length || 0;
    totalNodes = simNodes + diffNodes;
    
    if (counter) {
        counter.textContent = `Selected: ${totalSelected}/${totalNodes} (Sim: ${simSelected}, Diff: ${diffSelected})`;
    }
} else {
    // Single-tab diagram
    totalSelected = this.selectedNodes.size;
    totalNodes = this.nodes.length;
    
    if (counter) {
        counter.textContent = `Selected: ${totalSelected}/${totalNodes}`;
    }
}
```

**Impact:** Users can now see how many nodes they've selected across both tabs, with a breakdown showing similarities vs differences.

## Technical Details

### Data Structure Changes

#### Before:
```javascript
// Selection tracking was inconsistent
this.selectedNodes = new Set();  // Global, but only for current tab
this.tabSelectedNodes = {        // Existed but wasn't updated on selection
    'similarities': new Set(),
    'differences': new Set()
};
```

#### After:
```javascript
// Selection tracking is now dual and synchronized
this.selectedNodes = new Set();  // Global, synced with current tab
this.tabSelectedNodes = {        // Updated on every selection/deselection
    'similarities': new Set(),   // Persists when switching tabs
    'differences': new Set()     // Persists when switching tabs
};
```

### State Flow

#### Selection Flow (Per Tab):
1. User clicks node in similarities tab
2. `toggleNodeSelection()` adds ID to both:
   - `this.selectedNodes` (for UI rendering)
   - `this.tabSelectedNodes['similarities']` (for persistence)
3. User switches to differences tab
4. `switchTab()` saves similarities selections and loads differences selections
5. User selects nodes in differences tab
6. Same dual-tracking happens for differences

#### Finish Flow (Cross-Tab):
1. User clicks "Next" button
2. `finishSelection()` merges selections from both tabs:
   - Similarities: `this.tabSelectedNodes['similarities']`
   - Differences: `this.tabSelectedNodes['differences']`
3. Gathers actual node objects from both `this.tabNodes`
4. Passes complete merged list to `assembleNodesToDoubleBubbleMap()`
5. Both similarities and differences are added to diagram

## Testing Checklist

- [x] Can switch between tabs without desync
- [x] Selections persist when switching between tabs
- [x] Selection counter shows totals across both tabs
- [x] Finish button adds nodes from both tabs to diagram
- [x] No duplicate selections when switching tabs multiple times
- [x] Tab buttons show correct active state
- [x] Console logs show proper state tracking

## Backwards Compatibility

All changes are backwards compatible with single-tab diagrams (Circle Map, Bubble Map, etc.):
- `usesTabs()` check ensures tab-specific logic only runs for double bubble map
- Single-tab diagrams continue using `this.selectedNodes` and `this.nodes` as before
- No breaking changes to the API or data structures

## Performance Impact

Minimal performance impact:
- Dual Set updates add negligible overhead (O(1) operations)
- Selection counter now performs two Set size checks instead of one
- Tab switching has one additional console.log statement

## Future Improvements

1. Consider consolidating to a single selection tracking system (either global or per-tab)
2. Add visual indicator showing selections from other tabs
3. Add "Select All" / "Deselect All" buttons per tab
4. Persist selections to localStorage for recovery after refresh

## Files Modified

1. `static/js/editor/node-palette-manager.js` (8 functions updated)

## Related Documentation

- See `DOUBLE_BUBBLE_CATAPULT_CODE_REVIEW.md` for CATAPULT system details
- See `DOUBLE_BUBBLE_SMART_NODE_INTEGRATION.md` for smart node system integration

