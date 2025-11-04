# Interactive Editor Refactoring Guide - Step by Step

**Author**: MindSpring Team  
**Date**: 2025-01-XX  
**Status**: 🚧 **IN PROGRESS**  
**Target**: Refactor `interactive-editor.js` (4,406 lines) into event-driven modules using Event Bus + State Manager

---

## 📋 Executive Summary

### Current State
- **File**: `static/js/editor/interactive-editor.js`
- **Size**: 4,406 lines (as of latest check - verified 2025-01-XX)
- **Problem**: Monolithic file with too many responsibilities, no Event Bus/State Manager integration
- **Target**: 600-700 lines coordinator + multiple focused modules (600-800 lines each)
- **Event Bus**: Available at `window.eventBus` (`static/js/core/event-bus.js`)
- **State Manager**: Available at `window.stateManager` (`static/js/core/state-manager.js`)

### Refactoring Approach
- **Architecture**: Event Bus + State Manager driven
- **Pattern**: Extract specialized modules, communicate via events
- **Goal**: Single responsibility per module, decoupled communication

### Already Extracted (✅ COMPLETE)
1. ✅ **CanvasController** (`static/js/managers/editor/canvas-controller.js`) - ~450 lines
   - Canvas sizing, responsive layout, viewport fitting
   - Uses Event Bus + State Manager
   - Status: EXTRACTED and working

2. ✅ **HistoryManager** (`static/js/managers/editor/history-manager.js`) - ~252 lines
   - Undo/redo system, history stack
   - Uses Event Bus + State Manager
   - Status: EXTRACTED and working

3. ✅ **CircleMapOperations** (`static/js/managers/editor/diagram-types/circle-map-operations.js`) - ~226 lines
   - Circle map add/delete/update operations
   - Uses Event Bus pattern
   - Status: EXTRACTED and working

4. ✅ **BubbleMapOperations** (`static/js/managers/editor/diagram-types/bubble-map-operations.js`) - ~226 lines
   - Bubble map add/delete/update operations
   - Uses Event Bus pattern
   - Status: EXTRACTED and working

5. ✅ **ExportManager** (`static/js/managers/toolbar/export-manager.js`) - ~468 lines
   - Export functions (PNG, SVG, JSON)
   - Uses Event Bus + State Manager
   - Status: EXTRACTED and working (registered in `diagram-selector.js`)

**Important Note**: Modules are instantiated in `diagram-selector.js` (lines 478-512), NOT in InteractiveEditor constructor. InteractiveEditor currently does NOT use Event Bus or State Manager - this needs to be added during refactoring.

### Still Need to Extract (⏳ PENDING)
1. ⏳ **ViewManager** - Zoom, pan, fit operations (~400-500 lines)
   - Methods still in InteractiveEditor: `enableZoomAndPan()`, `zoomIn()`, `zoomOut()`, `fitToFullCanvas()`, `fitToCanvasWithPanel()`, `calculateAdaptiveDimensions()`, `autoFitDiagramIfNeeded()`

2. ⏳ **InteractionHandler** - User interactions (~500-600 lines)
   - Methods still in InteractiveEditor: `addInteractionHandlers()`, `addDragBehavior()`, `findTextForNode()`, click handlers, text editing handlers

3. ⏳ **DiagramOperationsLoader** - Dynamic loading (~200-300 lines)
   - Need to create module to load diagram operations dynamically
   - Currently operations are manually registered in `diagram-selector.js`

4. ⏳ **10 Remaining Diagram Operations** - (~200-400 lines each)
   - Double Bubble Map Operations
   - Brace Map Operations
   - Bridge Map Operations
   - Tree Map Operations
   - Flow Map Operations
   - Multi-Flow Map Operations
   - Concept Map Operations
   - Mind Map Operations
   - Factor Analysis Operations
   - Four Quadrant Operations

### Current Progress
- **Modules Extracted**: 5 of ~17 modules (29% complete)
  - CanvasController ✅
  - HistoryManager ✅
  - CircleMapOperations ✅
  - BubbleMapOperations ✅
  - ExportManager ✅
- **InteractiveEditor Size**: Still 4,406 lines (modules extracted but NOT integrated)
- **InteractiveEditor Status**: NO Event Bus/State Manager integration yet
- **Module Instantiation**: Currently in `diagram-selector.js`, needs to move to InteractiveEditor
- **Next Priority**: Extract ViewManager and InteractionHandler (largest remaining chunks)

---

## 🎯 Step-by-Step Refactoring Plan

### Phase 1: Setup & Infrastructure ✅ COMPLETE

#### Step 1.1: Verify Event Bus & State Manager
- [x] Event Bus available at `window.eventBus` (in `static/js/core/event-bus.js`)
- [x] State Manager available at `window.stateManager` (in `static/js/core/state-manager.js`)
- [x] Both initialized before editor loads (in `templates/editor.html`)

#### Step 1.2: Verify Already Extracted Modules
**Already extracted and working:**
- [x] CanvasController - `static/js/managers/editor/canvas-controller.js` (~450 lines)
- [x] HistoryManager - `static/js/managers/editor/history-manager.js` (~252 lines)
- [x] CircleMapOperations - `static/js/managers/editor/diagram-types/circle-map-operations.js` (~226 lines)
- [x] BubbleMapOperations - `static/js/managers/editor/diagram-types/bubble-map-operations.js` (~226 lines)

**Note**: These modules are extracted and registered in `diagram-selector.js` (lines 478-512), but:
1. NOT YET INTEGRATED into InteractiveEditor - old code still exists
2. InteractiveEditor does NOT use Event Bus or State Manager yet
3. Modules are accessed via `window.currentEditor.modules.*` instead of `this.modules.*`
4. Need to move module instantiation from DiagramSelector to InteractiveEditor constructor

#### Step 1.3: Identify Remaining Responsibilities
**Current responsibilities still in InteractiveEditor (4,406 lines):**
1. Editor initialization & lifecycle ✅ KEEP
2. Diagram rendering coordination ✅ KEEP
3. User interactions (selection, drag, click) ⏳ EXTRACT → InteractionHandler
4. Diagram-specific operations (add/delete/update) ⏳ EXTRACT → 10 more operation modules
5. View management (zoom, pan, fit) ⏳ EXTRACT → ViewManager
6. History management ✅ EXTRACTED (but not integrated)
7. Canvas sizing & responsive layout ✅ EXTRACTED (but not integrated)
8. Session validation ✅ KEEP
9. Export functions ✅ EXTRACTED (but not integrated)
10. Integration with other managers ✅ KEEP

**Extraction Targets (Priority Order):**
1. ⏳ ViewManager (zoom, pan, fit) - lines 763-1181) - ~400-500 lines - HIGH PRIORITY
2. ⏳ InteractionHandler (selection, drag, click - lines 263, 419, 628) - ~500-600 lines - HIGH PRIORITY
3. ⏳ DiagramOperationsLoader (dynamic loading) - ~200-300 lines - MEDIUM PRIORITY
4. ⏳ 10 remaining diagram operations (lines 2300-4063) - ~200-400 lines each - MEDIUM PRIORITY
   - Double Bubble, Brace, Bridge, Tree, Flow, Multi-Flow, Concept, Mind Map, Factor Analysis, Four Quadrant

---

## 🔌 Event Bus & State Manager Implementation Guide

**CRITICAL**: Before extracting modules, understand how Event Bus and State Manager work in this codebase.

### Event Bus Overview

The Event Bus is a global pub/sub system (`window.eventBus`) that enables decoupled communication between modules. Instead of direct method calls, modules communicate via events.

**Location**: `static/js/core/event-bus.js`  
**Global Instance**: `window.eventBus` (initialized before editor loads)

### Event Bus API

#### Subscribing to Events

```javascript
// Subscribe to an event (persistent listener)
this.eventBus.on('event:name', (data) => {
    // Handle event
    console.log('Event received:', data);
});

// Subscribe once (auto-removes after first trigger)
this.eventBus.once('event:name', (data) => {
    // Handle event once
});

// Subscribe to all events (rare, use sparingly)
this.eventBus.onAny((event, data) => {
    // Handle any event
});
```

#### Emitting Events

```javascript
// Emit event with optional data
this.eventBus.emit('event:name', {
    key: 'value',
    // ... data payload
});

// Emit without data
this.eventBus.emit('event:name');
```

#### Unsubscribing

```javascript
// Unsubscribe specific listener
const unsubscribe = this.eventBus.on('event:name', callback);
unsubscribe(); // Remove listener

// Remove all listeners for an event
this.eventBus.removeAllListeners('event:name');
```

### Event Naming Conventions

**Format**: `module:action` or `module:action_result`

**Examples**:
- `view:zoom_in_requested` - Request to zoom in
- `view:zoomed` - Zoom operation completed
- `diagram:node_added` - Node was added to diagram
- `interaction:selection_changed` - Node selection changed
- `toolbar:export_requested` - Export button clicked
- `history:undo_completed` - Undo operation finished

**Patterns**:
- **Request events**: `module:action_requested` (e.g., `view:zoom_in_requested`)
- **Completion events**: `module:action_completed` (e.g., `diagram:rendered`)
- **State change events**: `module:state_changed` (e.g., `interaction:selection_changed`)

### State Manager Integration

State Manager (`window.stateManager`) provides centralized state storage. Update state, then emit events:

```javascript
// Update state
this.stateManager.updateState({
    diagram: {
        selectedNodes: [nodeId1, nodeId2]
    }
});

// Emit event to notify other modules
this.eventBus.emit('interaction:selection_changed', {
    selectedNodes: [nodeId1, nodeId2]
});
```

### Module Implementation Pattern

**Every module should follow this pattern:**

```javascript
class MyModule {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('MyModule', 'MyModule initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for requests
        this.eventBus.on('my_module:action_requested', (data) => {
            this.handleAction(data);
        });
        
        // Listen for other module events
        this.eventBus.on('other_module:event', (data) => {
            this.handleOtherEvent(data);
        });
    }
    
    /**
     * Handle action
     */
    handleAction(data) {
        // Perform action
        const result = this.doAction(data);
        
        // Update state if needed
        this.stateManager.updateState({
            myModule: {
                lastAction: result
            }
        });
        
        // Emit completion event
        this.eventBus.emit('my_module:action_completed', {
            result: result
        });
    }
    
    /**
     * Cleanup on destroy
     */
    destroy() {
        // Remove all listeners (optional - session lifecycle handles cleanup)
        // this.eventBus.removeAllListeners();
    }
}
```

### Best Practices

1. **Always subscribe in constructor**: Call `subscribeToEvents()` in constructor
2. **Use descriptive event names**: Follow naming convention `module:action`
3. **Emit events for state changes**: Notify other modules when state changes
4. **Update State Manager first**: Update state, then emit event
5. **Pass data in events**: Include relevant data in event payload
6. **Don't create circular dependencies**: Events should flow one way when possible
7. **Use request/response pattern**: For actions, use `_requested` events
8. **Clean up on destroy**: Remove listeners if module is destroyed (optional with session lifecycle)

### Event Flow Example

**Zoom In Operation:**

```
User clicks zoom button
  ↓
ToolbarManager emits: 'view:zoom_in_requested'
  ↓
ViewManager receives event → calls zoomIn()
  ↓
ViewManager updates zoom level
  ↓
ViewManager updates State Manager: { view: { zoomLevel: 1.2 } }
  ↓
ViewManager emits: 'view:zoomed' { level: 1.2, direction: 'in' }
  ↓
Other modules (e.g., CanvasController) can listen and react
```

### Integration Checklist

When creating a new module:
- [ ] Constructor receives `eventBus`, `stateManager`, `logger`
- [ ] Store references: `this.eventBus`, `this.stateManager`, `this.logger`
- [ ] Create `subscribeToEvents()` method
- [ ] Subscribe to relevant events in `subscribeToEvents()`
- [ ] Emit events when actions complete or state changes
- [ ] Update State Manager when state changes
- [ ] Use consistent event naming conventions
- [ ] Log important events with `this.logger.debug()`

---

### Phase 2: Extract View Management Module

#### Step 2.1: Create ViewManager Module
**File**: `static/js/managers/editor/view-manager.js`  
**Target Size**: 400-500 lines

**Extract from InteractiveEditor (lines 763-1216 based on grep results):**
- `enableZoomAndPan()` (~100 lines) - Line ~763
- `addMobileZoomControls()` (~50 lines) - Line ~820
- `zoomIn()` (~30 lines) - Line ~913
- `zoomOut()` (~30 lines) - Line ~925
- `fitToFullCanvas()` (~200 lines) - Line ~1003
- `fitToCanvasWithPanel()` (~200 lines) - Line ~1018
- `calculateAdaptiveDimensions()` (~100 lines) - Line ~939
- `autoFitDiagramIfNeeded()` (~50 lines) - Line ~1181
- `updateFlowMapOrientationButtonVisibility()` - Line ~865
- `flipFlowMapOrientation()` - Line ~888

**Note**: Check if CanvasController already handles some of these. CanvasController handles canvas sizing, but ViewManager should handle zoom/pan operations.

**Event Bus Integration:**
```javascript
class ViewManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        
        // Subscribe to events
        this.subscribeToEvents();
    }
    
    subscribeToEvents() {
        // Listen for zoom requests
        this.eventBus.on('view:zoom_in_requested', () => this.zoomIn());
        this.eventBus.on('view:zoom_out_requested', () => this.zoomOut());
        this.eventBus.on('view:fit_to_window_requested', (data) => {
            this.fitToFullCanvas(data.animate);
        });
        this.eventBus.on('view:fit_to_canvas_requested', (data) => {
            this.fitToCanvasWithPanel(data.animate);
        });
        
        // Listen for diagram rendered
        this.eventBus.on('diagram:rendered', () => {
            this.autoFitDiagramIfNeeded();
        });
        
        // Listen for window resize
        this.eventBus.on('window:resized', () => {
            this.handleWindowResize();
        });
    }
    
    // Emit events for view changes
    zoomIn() {
        // ... implementation ...
        this.eventBus.emit('view:zoomed', { 
            level: this.currentZoomLevel,
            direction: 'in'
        });
    }
    
    // ... other methods ...
}
```

**Checklist:**
- [ ] Create `view-manager.js` file
- [ ] Extract all zoom/pan methods
- [ ] Extract all fit-to-canvas methods
- [ ] Add Event Bus subscriptions
- [ ] Add Event Bus emissions
- [ ] Test zoom in/out functionality
- [ ] Test fit to canvas functionality
- [ ] Verify file size ≤ 600 lines

#### Step 2.2: Integrate ViewManager into InteractiveEditor
**Update InteractiveEditor:**

```javascript
class InteractiveEditor {
    constructor(diagramType, template) {
        // ... existing code ...
        
        // Initialize ViewManager
        this.viewManager = new ViewManager(
            window.eventBus,
            window.stateManager,
            logger
        );
    }
    
    // Replace inline methods with ViewManager calls
    enableZoomAndPan() {
        // Delegate to ViewManager (or remove if ViewManager auto-initializes)
        // ViewManager should auto-enable on init
    }
    
    zoomIn() {
        this.eventBus.emit('view:zoom_in_requested');
    }
    
    zoomOut() {
        this.eventBus.emit('view:zoom_out_requested');
    }
    
    fitDiagramToWindow(animate = false) {
        this.eventBus.emit('view:fit_to_window_requested', { animate });
    }
    
    fitToCanvasWithPanel(animate = false) {
        this.eventBus.emit('view:fit_to_canvas_requested', { animate });
    }
}
```

**Checklist:**
- [ ] Add ViewManager initialization in constructor
- [ ] Replace zoom methods with event emissions
- [ ] Replace fit methods with event emissions
- [ ] Remove old zoom/pan code
- [ ] Test all view operations work
- [ ] Verify InteractiveEditor size reduced

---

### Phase 3: Extract Interaction Handler Module

#### Step 3.1: Create InteractionHandler Module
**File**: `static/js/managers/editor/interaction-handler.js`  
**Target Size**: 500-600 lines

**Extract from InteractiveEditor (based on grep results):**
- `addInteractionHandlers()` (~200 lines) - Line ~419
- `addDragBehavior()` (~150 lines) - Line ~263, also used at ~3248
- `findTextForNode()` (~30 lines) - Line ~628
- Click handlers for nodes (~150 lines) - Inside `addInteractionHandlers()`
- Text editing handlers (~100 lines) - Inside `addInteractionHandlers()`

**Note**: These methods are still directly in InteractiveEditor. They handle:
- Node selection (single/multi-select with Ctrl/Cmd)
- Drag and drop (for concept maps)
- Click handlers for nodes, text, and connections
- Text editing in-place

**Event Bus Integration:**
```javascript
class InteractionHandler {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        this.editor = editor;
        
        this.subscribeToEvents();
    }
    
    subscribeToEvents() {
        // Listen for diagram rendered to attach handlers
        this.eventBus.on('diagram:rendered', () => {
            this.attachInteractionHandlers();
        });
        
        // Listen for node selection requests
        this.eventBus.on('interaction:select_node_requested', (data) => {
            this.selectNode(data.nodeId, data.multiSelect);
        });
        
        // Listen for text editing requests
        this.eventBus.on('interaction:edit_text_requested', (data) => {
            this.startTextEditing(data.nodeId);
        });
    }
    
    attachInteractionHandlers() {
        // Add click handlers, drag handlers, etc.
        // Emit events for user actions
        this.eventBus.emit('interaction:handlers_attached');
    }
    
    selectNode(nodeId, multiSelect = false) {
        // Update selection
        // Emit selection changed event
        this.eventBus.emit('interaction:selection_changed', {
            selectedNodes: Array.from(this.selectedNodes),
            nodeId,
            multiSelect
        });
        
        // Update state manager
        this.stateManager.updateState({
            diagram: {
                selectedNodes: Array.from(this.selectedNodes)
            }
        });
    }
    
    // Emit events for drag operations
    onDragStart(nodeId, position) {
        this.eventBus.emit('interaction:drag_started', {
            nodeId,
            position
        });
    }
    
    onDragEnd(nodeId, position) {
        this.eventBus.emit('interaction:drag_ended', {
            nodeId,
            position
        });
        
        // Update state
        this.stateManager.updateState({
            diagram: {
                nodes: {
                    [nodeId]: { position }
                }
            }
        });
    }
}
```

**Checklist:**
- [ ] Create `interaction-handler.js` file
- [ ] Extract all interaction methods
- [ ] Add Event Bus subscriptions
- [ ] Add Event Bus emissions for user actions
- [ ] Update state manager on selection changes
- [ ] Test node selection
- [ ] Test drag and drop
- [ ] Test text editing
- [ ] Verify file size ≤ 600 lines

#### Step 3.2: Integrate InteractionHandler into InteractiveEditor
**Update InteractiveEditor:**

```javascript
class InteractiveEditor {
    constructor(diagramType, template) {
        // ... existing code ...
        
        // Initialize InteractionHandler
        this.interactionHandler = new InteractionHandler(
            window.eventBus,
            window.stateManager,
            logger,
            this // Pass editor reference
        );
    }
    
    // Remove old methods - InteractionHandler handles everything
    // Keep only session validation if needed
}
```

**Checklist:**
- [ ] Add InteractionHandler initialization
- [ ] Remove old interaction methods
- [ ] Subscribe to interaction events if needed
- [ ] Test all interactions work
- [ ] Verify InteractiveEditor size reduced

---

### Phase 4: Extract Remaining Diagram Operations

#### Step 4.1: Extract Double Bubble Map Operations
**File**: `static/js/managers/editor/diagram-types/double-bubble-map-operations.js`  
**Template**: Copy `bubble-map-operations.js`  
**Target Size**: 250-300 lines

**Extract from InteractiveEditor (actual method names):**
- `addNodeToDoubleBubbleMap()` (~100 lines) - Line ~2375
- `deleteDoubleBubbleMapNodes()` (~100 lines) - Line ~3307
- `updateDoubleBubbleMapText()` (~50 lines) - Line ~1898

**Checklist:**
- [ ] Create file using bubble-map-operations.js as template
- [ ] Adapt for double bubble structure (left/right topics, similarities, differences)
- [ ] Add Event Bus emissions
- [ ] Test add/delete/update operations
- [ ] Verify file size ≤ 600 lines

#### Step 4.2: Extract Brace Map Operations
**File**: `static/js/managers/editor/diagram-types/brace-map-operations.js`  
**Template**: Copy `circle-map-operations.js`  
**Target Size**: 300-350 lines

**Extract from InteractiveEditor (actual method names):**
- `addNodeToBraceMap()` (~150 lines) - Line ~2295, implementation starts ~2435
- `deleteBraceMapNodes()` (~100 lines) - Line ~3309, implementation starts ~3562
- `updateBraceMapText()` (~50 lines) - Line ~1967, implementation starts ~1967

**Checklist:**
- [ ] Create file using circle-map-operations.js as template
- [ ] Adapt for brace structure (topic, parts, subparts)
- [ ] Add Event Bus emissions
- [ ] Test add/delete/update operations
- [ ] Verify file size ≤ 600 lines

#### Step 4.3: Extract Flow Map Operations
**File**: `static/js/managers/editor/diagram-types/flow-map-operations.js`  
**Target Size**: 250-300 lines

**Extract from InteractiveEditor (actual method names):**
- `addNodeToFlowMap()` (~100 lines) - Line ~2298, implementation starts ~2595
- `deleteFlowMapNodes()` (~100 lines) - Line ~3311
- `updateFlowMapText()` (~50 lines) - Line ~1726
- `flipFlowMapOrientation()` (~50 lines) - Line ~888 (already in ViewManager section)

**Checklist:**
- [ ] Create file
- [ ] Implement flow map operations
- [ ] Add Event Bus emissions
- [ ] Test operations
- [ ] Verify file size ≤ 600 lines

#### Step 4.4: Extract Concept Map Operations
**File**: `static/js/managers/editor/diagram-types/concept-map-operations.js`  
**Target Size**: 300-350 lines

**Extract from InteractiveEditor (actual method names):**
- `addNodeToConceptMap()` (~100 lines) - Line ~2310
- `deleteConceptMapNodes()` (~100 lines) - Line ~3315
- `updateConceptMapNode()` (~100 lines) - Method name not found, check updateText() dispatcher
- Drag behavior specific to concept maps (~50 lines) - Already in InteractionHandler, but concept maps need special handling

**Checklist:**
- [ ] Create file
- [ ] Implement concept map operations
- [ ] Handle drag behavior
- [ ] Add Event Bus emissions
- [ ] Test operations
- [ ] Verify file size ≤ 600 lines

#### Step 4.5: Extract Mind Map Operations
**File**: `static/js/managers/editor/diagram-types/mindmap-operations.js`  
**Target Size**: 300-350 lines

**Extract from InteractiveEditor (actual method names):**
- `addNodeToMindMap()` (~150 lines) - Line ~2312, implementation starts ~2999
- `deleteMindMapNodes()` (~100 lines) - Line ~4049, implementation starts ~4049
- `updateMindMapText()` (~100 lines) - Line ~1747, implementation starts ~1747
- `recalculateMindMapLayout()` (~50 lines) - Line ~3130, implementation starts ~3130

**Checklist:**
- [ ] Create file
- [ ] Implement mind map operations
- [ ] Handle layout recalculation
- [ ] Add Event Bus emissions
- [ ] Test operations
- [ ] Verify file size ≤ 600 lines

#### Step 4.6: Extract Remaining Diagram Operations
**Remaining diagrams to extract (actual method names from InteractiveEditor):**

- [ ] **Bridge Map Operations** (~250 lines)
  - `addNodeToBridgeMap()` - Line ~2306
  - `deleteBridgeMapNodes()` - Check deleteSelectedNodes() dispatcher
  - `updateBridgeMapText()` - Check updateText() dispatcher

- [ ] **Tree Map Operations** (~300 lines)
  - `addNodeToTreeMap()` - Line ~2303
  - `deleteTreeMapNodes()` - Check deleteSelectedNodes() dispatcher
  - `updateTreeMapText()` - Check updateText() dispatcher

- [ ] **Multi-Flow Map Operations** (~350 lines)
  - `addNodeToMultiFlowMap()` - Line ~2300
  - `deleteMultiFlowMapNodes()` - Line ~3313
  - `updateMultiFlowMapText()` - Check updateText() dispatcher

- [ ] **Factor Analysis Operations** (~200 lines)
  - `addNodeToFactorAnalysis()` - Check `addNode()` dispatcher for factor_analysis case (line ~2327)
  - `deleteFactorAnalysisNodes()` - Check `deleteSelectedNodes()` dispatcher
  - `updateFactorAnalysisText()` - Check `updateText()` dispatcher

- [ ] **Four Quadrant Operations** (~200 lines)
  - `addNodeToFourQuadrant()` - Check `addNode()` dispatcher for four_quadrant case (line ~2329)
  - `deleteFourQuadrantNodes()` - Check `deleteSelectedNodes()` dispatcher
  - `updateFourQuadrantText()` - Check `updateText()` dispatcher

**For each:**
- [ ] Search InteractiveEditor for exact method names
- [ ] Create file using appropriate template
- [ ] Extract operations from InteractiveEditor
- [ ] Add Event Bus emissions
- [ ] Test operations
- [ ] Verify file size ≤ 600 lines

---

### Phase 5: Create Diagram Operations Loader

#### Step 5.1: Create DiagramOperationsLoader
**File**: `static/js/managers/editor/diagram-operations-loader.js`  
**Target Size**: 200-300 lines

**Purpose**: Dynamically load and manage diagram-specific operations

```javascript
class DiagramOperationsLoader {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        
        // Operations registry
        this.operationsRegistry = {
            'circle_map': CircleMapOperations,
            'bubble_map': BubbleMapOperations,
            'double_bubble_map': DoubleBubbleMapOperations,
            'brace_map': BraceMapOperations,
            'bridge_map': BridgeMapOperations,
            'tree_map': TreeMapOperations,
            'flow_map': FlowMapOperations,
            'multi_flow_map': MultiFlowMapOperations,
            'concept_map': ConceptMapOperations,
            'mindmap': MindMapOperations,
            'factor_analysis': FactorAnalysisOperations,
            'four_quadrant': FourQuadrantOperations
        };
        
        this.currentOperations = null;
        
        this.subscribeToEvents();
    }
    
    subscribeToEvents() {
        // Listen for diagram type changes
        this.eventBus.on('diagram:type_changed', (data) => {
            this.loadOperations(data.diagramType);
        });
        
        // Listen for diagram loaded
        this.eventBus.on('diagram:loaded', (data) => {
            this.loadOperations(data.diagramType);
        });
    }
    
    loadOperations(diagramType) {
        const OperationsClass = this.operationsRegistry[diagramType];
        
        if (!OperationsClass) {
            this.logger.warn('DiagramOperationsLoader', 
                `No operations handler for ${diagramType}`);
            this.currentOperations = null;
            return;
        }
        
        // Create new instance
        this.currentOperations = new OperationsClass(
            this.eventBus,
            this.stateManager,
            this.logger
        );
        
        this.eventBus.emit('diagram:operations_loaded', {
            diagramType,
            operations: this.currentOperations
        });
    }
    
    getOperations() {
        return this.currentOperations;
    }
}
```

**Checklist:**
- [ ] Create `diagram-operations-loader.js` file
- [ ] Implement operations registry
- [ ] Add dynamic loading logic
- [ ] Add Event Bus subscriptions
- [ ] Add Event Bus emissions
- [ ] Test loading operations for each diagram type
- [ ] Verify file size ≤ 600 lines

---

### Phase 6: Extract Export Manager

#### Step 6.1: ExportManager Status
**File**: `static/js/managers/toolbar/export-manager.js`  
**Status**: ✅ **ALREADY EXTRACTED** (~468 lines)

**Note**: ExportManager is already extracted and registered in `diagram-selector.js` (line 479-482). However:
- It's in the `toolbar/` folder, not `editor/` folder
- InteractiveEditor may still have old export code that needs to be removed
- Need to verify integration and remove duplicate code from InteractiveEditor

**Checklist:**
- [x] ExportManager exists and uses Event Bus + State Manager
- [ ] Verify old export code removed from InteractiveEditor
- [ ] Test export functionality works
- [ ] Consider moving to `editor/` folder for consistency (optional)

**Event Bus Integration:**
```javascript
class ExportManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        this.editor = editor;
        
        this.subscribeToEvents();
    }
    
    subscribeToEvents() {
        // Listen for export requests
        this.eventBus.on('toolbar:export_requested', (data) => {
            this.handleExport(data.format);
        });
        
        // Listen for PNG export requests
        this.eventBus.on('export:png_requested', () => {
            this.performPNGExport();
        });
    }
    
    handleExport(format) {
        // Handle different export formats
        switch(format) {
            case 'png':
                this.performPNGExport();
                break;
            // Add other formats as needed
        }
        
        this.eventBus.emit('export:completed', { format });
    }
    
    performPNGExport() {
        // ... implementation ...
        this.eventBus.emit('export:png_completed', { 
            dataUrl: pngDataUrl 
        });
    }
}
```

**Integration Checklist:**
- [ ] Verify ExportManager is accessible from InteractiveEditor
- [ ] Remove any duplicate export code from InteractiveEditor
- [ ] Ensure export events are properly emitted/consumed
- [ ] Test PNG export works
- [ ] Test other export formats (SVG, JSON) if any

---

### Phase 7: Refactor InteractiveEditor to Use Modules

**CRITICAL**: Currently, modules are instantiated in `diagram-selector.js` (lines 478-512). This phase moves module instantiation to InteractiveEditor constructor and integrates Event Bus + State Manager.

#### Step 7.1: Update InteractiveEditor Constructor
**Current State**: Modules are instantiated in `diagram-selector.js` (lines 478-512). Need to move to InteractiveEditor constructor.

**Replace direct implementation with module initialization:**

```javascript
class InteractiveEditor {
    constructor(diagramType, template) {
        this.diagramType = diagramType;
        this.currentSpec = template;
        this.sessionId = null;
        this.sessionDiagramType = null;
        
        // Initialize Event Bus and State Manager (CURRENTLY MISSING - needs to be added)
        this.eventBus = window.eventBus;
        this.stateManager = window.stateManager;
        
        if (!this.eventBus || !this.stateManager) {
            logger.error('InteractiveEditor', 'Event Bus or State Manager not available');
            throw new Error('Event Bus and State Manager must be initialized before InteractiveEditor');
        }
        
        // Initialize managers (Event Bus + State Manager driven)
        // Register with session lifecycle for cleanup
        this.modules = {
            canvas: window.sessionLifecycle.register(
                new CanvasController(this.eventBus, this.stateManager, logger),
                'canvas'
            ),
            history: window.sessionLifecycle.register(
                new HistoryManager(this.eventBus, this.stateManager, logger),
                'history'
            ),
            view: window.sessionLifecycle.register(
                new ViewManager(this.eventBus, this.stateManager, logger),
                'view'
            ),
            interaction: window.sessionLifecycle.register(
                new InteractionHandler(this.eventBus, this.stateManager, logger, this),
                'interaction'
            ),
            export: window.sessionLifecycle.register(
                new ExportManager(this.eventBus, this.stateManager, logger),
                'export'
            ),
            diagramOperationsLoader: window.sessionLifecycle.register(
                new DiagramOperationsLoader(this.eventBus, this.stateManager, logger),
                'diagramOperationsLoader'
            )
        };
        
        // Load diagram operations for current type
        this.modules.diagramOperationsLoader.loadOperations(diagramType);
        
        // Subscribe to events
        this.subscribeToEvents();
        
        // Initialize components (keep these for now)
        this.selectionManager = new SelectionManager();
        this.canvasManager = new CanvasManager();
        this.toolbarManager = null; // Will be initialized after render
        this.renderer = null;
    }
    
    subscribeToEvents() {
        // Listen for diagram operations
        this.eventBus.on('diagram:node_added', (data) => {
            this.currentSpec = data.spec;
            this.renderDiagram();
        });
        
        this.eventBus.on('diagram:nodes_deleted', (data) => {
            this.currentSpec = data.spec;
            this.clearSelection();
            this.renderDiagram();
        });
        
        this.eventBus.on('diagram:node_updated', (data) => {
            this.currentSpec = data.spec;
            this.renderDiagram();
        });
        
        // Listen for history events
        this.eventBus.on('history:undo_completed', (data) => {
            this.currentSpec = data.spec;
            this.renderDiagram();
        });
        
        this.eventBus.on('history:redo_completed', (data) => {
            this.currentSpec = data.spec;
            this.renderDiagram();
        });
        
        // Listen for view events
        this.eventBus.on('view:fit_requested', (data) => {
            this.viewManager.fitToCanvasWithPanel(data.animate);
        });
        
        // Listen for session events
        this.eventBus.on('session:validate_requested', (data) => {
            const isValid = this.validateSession(data.operation);
            this.eventBus.emit('session:validation_result', {
                valid: isValid,
                operation: data.operation
            });
        });
    }
}
```

**Checklist:**
- [ ] Add Event Bus and State Manager initialization to constructor
- [ ] Move module instantiation from `diagram-selector.js` to InteractiveEditor constructor
- [ ] Update `diagram-selector.js` to remove module instantiation (lines 478-512)
- [ ] Register all managers with session lifecycle
- [ ] Add Event Bus subscriptions
- [ ] Remove old manager initialization code
- [ ] Test editor initialization
- [ ] Verify all managers initialize correctly
- [ ] Verify modules accessible via `this.modules.*` instead of `window.currentEditor.modules.*`

#### Step 7.2: Replace Methods with Event Emissions
**Replace inline methods with event emissions:**

**Current dispatcher methods in InteractiveEditor (need to be updated):**
- `addNode()` - Line ~2275, dispatches to `addNodeToCircleMap()`, `addNodeToBubbleMap()`, etc.
- `deleteSelectedNodes()` - Line ~3287, dispatches to `deleteCircleMapNodes()`, `deleteBubbleMapNodes()`, etc.
- `updateText()` - Line ~1718, dispatches to `updateCircleMapText()`, `updateBubbleMapText()`, etc.

**Replace with:**

```javascript
// OLD: Direct method calls with switch statement
addNode() {
    switch(this.diagramType) {
        case 'circle_map':
            this.addNodeToCircleMap();
            break;
        case 'bubble_map':
            this.addNodeToBubbleMap();
            break;
        // ... many cases ...
    }
}

// NEW: Event-driven with operations loader
addNode() {
    if (!this.validateSession('Add node')) {
        return;
    }
    
    const operations = this.diagramOperationsLoader.getOperations();
    if (operations) {
        const updatedSpec = operations.addNode(this.currentSpec, this);
        if (updatedSpec) {
            this.currentSpec = updatedSpec;
            this.renderDiagram();
        }
    } else {
        // Fallback for unsupported diagram types
        logger.warn('Editor', `No operations handler for ${this.diagramType}`);
    }
}

// Similar for deleteSelectedNodes() and updateText()
deleteSelectedNodes() {
    if (!this.validateSession('Delete nodes')) {
        return;
    }
    
    const selectedNodes = Array.from(this.selectedNodes);
    if (selectedNodes.length === 0) {
        return;
    }
    
    const operations = this.diagramOperationsLoader.getOperations();
    if (operations) {
        const updatedSpec = operations.deleteNodes(this.currentSpec, selectedNodes);
        if (updatedSpec) {
            this.currentSpec = updatedSpec;
            this.clearSelection();
            this.renderDiagram();
        }
    }
}

// Similar for deleteNodes, updateNode, etc.
deleteNodes() {
    if (!this.validateSession('Delete nodes')) {
        return;
    }
    
    const selectedNodes = this.getSelectedNodes();
    if (selectedNodes.length === 0) {
        return;
    }
    
    const operations = this.diagramOperationsLoader.getOperations();
    if (operations) {
        const updatedSpec = operations.deleteNodes(
            this.currentSpec,
            selectedNodes
        );
        if (updatedSpec) {
            this.currentSpec = updatedSpec;
            this.clearSelection();
            this.renderDiagram();
        }
    }
}
```

**Checklist:**
- [ ] Replace `addNode()` with operations loader call
- [ ] Replace `deleteNodes()` with operations loader call
- [ ] Replace `updateNode()` with operations loader call
- [ ] Remove all switch statements
- [ ] Remove all diagram-specific methods
- [ ] Test all operations work

#### Step 7.3: Keep Core Responsibilities Only
**What stays in InteractiveEditor (600-700 lines target):**
- Editor initialization (constructor, initialize())
- Session management & validation (validateSession())
- Diagram rendering coordination (renderDiagram())
- Manager coordination (initialize managers, subscribe to events)
- Event subscriptions (subscribeToEvents())
- Cleanup/destruction (destroy())

**What gets removed (actual method names from codebase):**
- All zoom/pan methods → ViewManager
  - `enableZoomAndPan()` (line ~763)
  - `zoomIn()`, `zoomOut()` (lines ~913, ~925)
  - `fitToFullCanvas()`, `fitToCanvasWithPanel()` (lines ~1003, ~1018)
  - `calculateAdaptiveDimensions()` (line ~939)
  - `autoFitDiagramIfNeeded()` (line ~1181)
  
- All interaction handlers → InteractionHandler
  - `addInteractionHandlers()` (line ~419)
  - `addDragBehavior()` (line ~263, also ~3248)
  - `findTextForNode()` (line ~628)
  
- All diagram-specific operations → DiagramOperationsLoader
  - `addNodeToCircleMap()`, `addNodeToBubbleMap()`, etc. (lines ~2324, ~2349)
  - `deleteCircleMapNodes()`, `deleteBubbleMapNodes()`, etc. (lines ~3303, ~3305)
  - `updateCircleMapText()`, `updateBubbleMapText()`, etc. (lines ~1829, ~1865)
  - Switch statements in `addNode()`, `deleteSelectedNodes()`, `updateText()`
  
- All export methods → ExportManager
  - `handleExport()` (check for export methods)
  - `performPNGExport()` (check for export methods)
  
- All history management → HistoryManager (already extracted)
  - `saveToHistory()` (remove if exists)
  - `history` array (remove if exists)
  
- All canvas sizing → CanvasController (already extracted)
  - Canvas sizing methods (already extracted)

**Checklist:**
- [ ] Remove all extracted code
- [ ] Keep only core coordination logic
- [ ] Verify file size ≤ 700 lines
- [ ] Test all functionality works
- [ ] Run linter to check for errors

---

### Phase 8: Update Script Loading Order

#### Step 8.1: Update editor.html Template
**File**: `templates/editor.html`

**Current script loading (lines 790-846 in `templates/editor.html`):**
- ✅ Event Bus Infrastructure loaded (lines 795-798)
- ✅ Editor Managers loaded (lines 838-839)
  - HistoryManager ✅
  - CanvasController ✅
- ✅ ExportManager loaded (line 822) - in toolbar folder
- ✅ Diagram Operations loaded (lines 841-842)
  - CircleMapOperations ✅
  - BubbleMapOperations ✅
- ⏳ Need to add new modules as they're extracted

**Add script tags in correct order (after existing modules):**

```html
<!-- Event Bus Infrastructure (already loaded at lines 795-798) -->
<!-- Editor Managers (already loaded at lines 838-839) -->
<!-- Add new managers here as extracted: -->
<script src="/static/js/managers/editor/view-manager.js"></script>
<script src="/static/js/managers/editor/interaction-handler.js"></script>
<script src="/static/js/managers/editor/diagram-operations-loader.js"></script>
<!-- ExportManager already loaded at line 822 (toolbar folder) -->

<!-- Diagram Operations (already loaded at lines 841-842) -->
<!-- Add new operations as extracted: -->
<script src="/static/js/managers/editor/diagram-types/double-bubble-map-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/brace-map-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/bridge-map-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/tree-map-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/flow-map-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/multi-flow-map-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/concept-map-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/mindmap-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/factor-analysis-operations.js"></script>
<script src="/static/js/managers/editor/diagram-types/four-quadrant-operations.js"></script>

<!-- Main Editor (already loaded at line 846) -->
```

**Checklist:**
- [ ] Add all manager script tags
- [ ] Add all diagram operations script tags
- [ ] Verify correct loading order
- [ ] Test page loads without errors
- [ ] Test all functionality works

---

### Phase 9: Testing & Verification

#### Step 9.1: Test All Diagram Types
**For each diagram type, test:**
- [ ] Circle Map: add, delete, update, undo/redo
- [ ] Bubble Map: add, delete, update, undo/redo
- [ ] Double Bubble Map: add, delete, update, undo/redo
- [ ] Brace Map: add, delete, update, undo/redo
- [ ] Bridge Map: add, delete, update, undo/redo
- [ ] Tree Map: add, delete, update, undo/redo
- [ ] Flow Map: add, delete, update, orientation flip, undo/redo
- [ ] Multi-Flow Map: add, delete, update, undo/redo
- [ ] Concept Map: add, delete, update, drag, undo/redo
- [ ] Mind Map: add, delete, update, layout recalculation, undo/redo
- [ ] Factor Analysis: add, delete, update, undo/redo
- [ ] Four Quadrant: add, delete, update, undo/redo

#### Step 9.2: Test View Operations
- [ ] Zoom in/out
- [ ] Pan around
- [ ] Fit to window
- [ ] Fit to canvas with panel
- [ ] Mobile zoom controls
- [ ] Auto-fit on render

#### Step 9.3: Test Interactions
- [ ] Node selection (single, multi-select)
- [ ] Drag and drop (concept maps)
- [ ] Text editing
- [ ] Click handlers

#### Step 9.4: Test Export
- [ ] PNG export
- [ ] Export with correct dimensions
- [ ] Export quality

#### Step 9.5: Test Integration
- [ ] Event Bus events fire correctly
- [ ] State Manager updates correctly
- [ ] All managers communicate via events
- [ ] No direct method calls between managers
- [ ] Session validation works

#### Step 9.6: Performance & Quality
- [ ] No console errors
- [ ] No memory leaks
- [ ] Performance same or better
- [ ] All files ≤ 800 lines
- [ ] Code follows Event Bus pattern

---

### Phase 10: Documentation & Cleanup

#### Step 10.1: Update Documentation
- [ ] Update CHANGELOG.md with refactoring details
- [ ] Document new architecture
- [ ] Document Event Bus events used
- [ ] Document State Manager state structure
- [ ] Add code examples

#### Step 10.2: Code Cleanup
- [ ] Remove commented-out code
- [ ] Remove unused imports
- [ ] Update method documentation
- [ ] Ensure consistent naming
- [ ] Run linter and fix issues

---

## 📊 Success Criteria

### File Size Targets
- [ ] InteractiveEditor: ≤ 700 lines
- [ ] ViewManager: ≤ 600 lines
- [ ] InteractionHandler: ≤ 600 lines
- [ ] DiagramOperationsLoader: ≤ 300 lines
- [ ] ExportManager: ≤ 400 lines
- [ ] Each diagram operations file: ≤ 400 lines

### Architecture Targets
- [ ] All communication via Event Bus
- [ ] All state in State Manager
- [ ] No direct method calls between managers
- [ ] Single responsibility per module
- [ ] Clear separation of concerns

### Functionality Targets
- [ ] All 12 diagram types work
- [ ] All operations work (add/delete/update)
- [ ] Undo/redo works
- [ ] View operations work
- [ ] Interactions work
- [ ] Export works

---

## 🎯 Quick Reference

**📖 For detailed Event Bus implementation guide, see: [Event Bus & State Manager Implementation Guide](#-event-bus--state-manager-implementation-guide)**

### Event Bus Events Used

**View Events:**
- `view:zoom_in_requested`
- `view:zoom_out_requested`
- `view:fit_to_window_requested`
- `view:fit_to_canvas_requested`
- `view:zoomed`
- `view:fitted`

**Interaction Events:**
- `interaction:select_node_requested`
- `interaction:selection_changed`
- `interaction:drag_started`
- `interaction:drag_ended`
- `interaction:edit_text_requested`

**Diagram Events:**
- `diagram:node_added`
- `diagram:nodes_deleted`
- `diagram:node_updated`
- `diagram:rendered`
- `diagram:type_changed`
- `diagram:operations_loaded`

**History Events:**
- `history:undo_completed`
- `history:redo_completed`
- `history:saved`

**Export Events:**
- `toolbar:export_requested`
- `export:png_requested`
- `export:completed`

### State Manager State Structure

```javascript
{
    diagram: {
        type: 'circle_map',
        sessionId: '...',
        data: { /* spec */ },
        selectedNodes: [],
        history: [],
        historyIndex: -1
    },
    view: {
        zoomLevel: 1,
        panX: 0,
        panY: 0,
        fitMode: 'canvas_with_panel'
    }
}
```

---

**END OF DOCUMENT**

