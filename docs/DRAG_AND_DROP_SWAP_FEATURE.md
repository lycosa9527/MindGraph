# Drag and Drop Node Swap Feature - Implementation Guide

## Executive Summary

This document outlines a step-by-step plan to implement an enhanced drag-and-drop feature for auto-complete diagrams. The feature allows users to hold-click on a node for 2 seconds, then drag it to swap positions with another same-level node.

**Key Requirements:**
- Hold-click detection (2-second threshold)
- Visual feedback (node follows cursor, original node at 30% opacity)
- Same-level node matching
- **Hierarchical swap: When swapping parent nodes (e.g., branches), swap their children nodes as well**
- Position swap animation

**Feasibility Assessment:** ✅ **FULLY FEASIBLE**

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Feature Requirements](#2-feature-requirements)
3. [Technical Feasibility](#3-technical-feasibility)
4. [Implementation Steps](#4-implementation-steps)
5. [Technical Challenges & Solutions](#5-technical-challenges--solutions)
6. [Testing Strategy](#6-testing-strategy)
7. [Edge Cases](#7-edge-cases)

---

## 1. Current State Analysis

### 1.1 Existing Drag Implementation

**Location:** `static/js/managers/editor/interaction-handler.js`

**Current Behavior:**
- Only works for concept maps (`diagramType === 'concept_map'`)
- Uses D3.js `d3.drag()` behavior
- Immediate drag on mousedown (no hold-click delay)
- Drags node and updates connected lines
- No same-level matching or swap functionality

**Key Code Reference:**
```299:475:static/js/managers/editor/interaction-handler.js
addDragBehavior(shapeElement, textElement) {
    // ... existing drag implementation
}
```

### 1.2 Node Structure

**Node Identification:**
- Nodes have `data-node-id` attribute (unique identifier)
- Nodes have `data-node-type` attribute (level/hierarchy indicator)
- Nodes can be in groups (`<g>`) or individual SVG elements

**Node Types by Diagram:**
- **Mind Maps:** `topic`, `branch`, `child`
- **Bubble Maps:** `topic`, `attribute`
- **Concept Maps:** `concept` (likely)
- **Tree Maps:** `topic`, `dimension`, `category`, `leaf`
- **Flow Maps:** `title`, `step`, `substep`
- **Double Bubble Maps:** `left`, `right`, `similarity`, `left_difference`, `right_difference`
- **Circle Maps:** `center`, `context`
- **Brace Maps:** `topic`, `dimension`, `part`, `subpart`

### 1.3 Auto-Complete Diagram Context

**Auto-Complete Flow:**
1. User triggers auto-complete via toolbar
2. LLM generates additional nodes
3. Diagram is re-rendered with new nodes
4. All nodes are interactive via `InteractionHandler`

**Current Limitation:**
- Drag only works for concept maps
- No swap functionality exists
- No hold-click detection

---

## 2. Feature Requirements

### 2.1 User Interaction Flow

1. **Hold-Click Detection:**
   - User presses mouse button on a node
   - System waits 2 seconds
   - If mouse is still pressed, enter drag mode

2. **Visual Feedback:**
   - Create a visual clone/follower node that follows mouse cursor
   - Set original node opacity to 30% (0.3)
   - Show visual indicator that drag mode is active

3. **Same-Level Matching:**
   - Detect when dragged node is over another node
   - Check if target node has same `data-node-type` as dragged node
   - Highlight valid target nodes (same level)
   - Show visual feedback when hovering over valid target

4. **Position Swap:**
   - When mouse is released over valid same-level node
   - **If swapping parent nodes (e.g., branches), identify and swap all child nodes as well**
   - Swap positions of the parent nodes AND their entire subtrees
   - Animate the swap transition (parent + children move together)
   - Update diagram spec and save to history

### 2.2 Hierarchical Swap Requirement

**Critical Feature:** When swapping parent nodes, their entire subtree (children) must swap with them.

**Examples:**
- **Mind Maps:** When swapping two branches, all children of each branch move with their parent branch
- **Tree Maps:** When swapping two categories, all leaf nodes under each category move with their parent category
- **Flow Maps:** When swapping two steps, all substeps under each step move with their parent step

**Why This Matters:**
- Maintains logical grouping and relationships
- Prevents orphaned children nodes
- Preserves diagram structure integrity
- Provides intuitive user experience

**Implementation:**
- Identify parent-child relationships via attributes (`data-branch-index`, `data-category-id`, etc.)
- When swapping parents, swap entire subtree (parent + all children)
- Update parent references in children after swap (e.g., `branch_index` in mind maps)
- Animate parent and children together as a cohesive group

### 2.3 Supported Diagram Types

**Phase 1 (Initial Implementation):**
- ✅ Mind Maps (topic, branch, child levels) - **Hierarchical: branches swap with children**
- ✅ Bubble Maps (attribute level) - No hierarchy, simple swap
- ✅ Concept Maps (concept level) - No hierarchy, simple swap
- ✅ Tree Maps (category, leaf levels) - **Hierarchical: categories swap with leaves**

**Phase 2 (Future Enhancement):**
- Flow Maps (step, substep levels) - **Hierarchical: steps swap with substeps**
- Double Bubble Maps (similarity, difference levels) - No hierarchy, simple swap
- Circle Maps (context level) - No hierarchy, simple swap
- Brace Maps (part, subpart levels) - **Hierarchical: parts swap with subparts**

### 2.4 Visual Design Requirements

- **Hold-Click Indicator:** Visual feedback during 2-second wait (e.g., progress ring, opacity change)
- **Drag Clone:** Semi-transparent copy of node following cursor
- **Original Node:** 30% opacity while dragging
- **Children Indication:** When dragging a parent node, show visual indication that children will also move (e.g., subtle outline or grouping indicator)
- **Valid Target Highlight:** Border glow or color change for same-level nodes
- **Invalid Target:** No highlight or different visual (e.g., red border)
- **Swap Animation:** Smooth transition when positions are swapped (parent + children move together as a group)

---

## 3. Technical Feasibility

### 3.1 ✅ Hold-Click Detection

**Feasibility:** ✅ **FULLY FEASIBLE**

**Implementation Approach:**
- Use `mousedown` event to start timer
- Use `setTimeout` for 2-second delay
- Cancel timer if `mouseup` occurs before 2 seconds
- Track mouse position to ensure user hasn't moved significantly

**Code Pattern:**
```javascript
let holdTimer = null;
let isHolding = false;

element.on('mousedown', function(event) {
    const startX = event.clientX;
    const startY = event.clientY;
    
    holdTimer = setTimeout(() => {
        // Check if mouse hasn't moved significantly
        const currentX = event.clientX;
        const currentY = event.clientY;
        const distance = Math.sqrt(
            Math.pow(currentX - startX, 2) + 
            Math.pow(currentY - startY, 2)
        );
        
        if (distance < 10) { // 10px tolerance
            isHolding = true;
            startDragMode(event);
        }
    }, 2000);
});

element.on('mouseup', function() {
    if (holdTimer) {
        clearTimeout(holdTimer);
        holdTimer = null;
    }
    if (isHolding) {
        endDragMode();
    }
});
```

### 3.2 ✅ Visual Clone Following Cursor

**Feasibility:** ✅ **FULLY FEASIBLE**

**Implementation Approach:**
- Create a temporary SVG element (clone) on mousedown
- Position clone at mouse coordinates using `mousemove` event
- Clone should match original node's appearance
- Remove clone on mouseup

**Code Pattern:**
```javascript
let dragClone = null;

function createDragClone(originalNode) {
    const clone = originalNode.cloneNode(true);
    clone.style.opacity = '0.7';
    clone.style.pointerEvents = 'none';
    clone.style.position = 'absolute';
    clone.classList.add('drag-clone');
    document.body.appendChild(clone);
    return clone;
}

function updateDragClonePosition(event) {
    if (dragClone) {
        dragClone.style.left = (event.clientX - 20) + 'px';
        dragClone.style.top = (event.clientY - 20) + 'px';
    }
}
```

**Alternative (SVG-based):**
- Create clone as SVG element in same SVG container
- Use `transform` attribute to position relative to SVG coordinates
- More accurate for SVG coordinate system

### 3.3 ✅ Same-Level Node Detection

**Feasibility:** ✅ **FULLY FEASIBLE**

**Implementation Approach:**
- Use `data-node-type` attribute to determine node level
- On `mousemove`, detect which node is under cursor
- Compare `data-node-type` of dragged node vs. target node
- Highlight valid targets

**Code Pattern:**
```javascript
function getNodeUnderCursor(event) {
    const svg = d3.select('#d3-container svg');
    const point = svg.node().createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    
    const element = document.elementFromPoint(event.clientX, event.clientY);
    if (element) {
        const shapeElement = element.closest('circle, rect, ellipse');
        if (shapeElement) {
            return d3.select(shapeElement);
        }
    }
    return null;
}

function isSameLevel(draggedNode, targetNode) {
    const draggedType = draggedNode.attr('data-node-type');
    const targetType = targetNode.attr('data-node-type');
    return draggedType === targetType;
}
```

### 3.4 ✅ Position Swap

**Feasibility:** ✅ **FULLY FEASIBLE**

**Implementation Approach:**
- Store original positions of both nodes
- **Identify children nodes for each parent node**
- Calculate new positions (swap coordinates for parent + children)
- Animate transition using D3 transitions (parent + children move together)
- Update diagram spec in `editor.currentSpec`
- **Update parent-child relationships in spec (e.g., branch_index for children)**
- Emit event to save to history

**Code Pattern:**
```javascript
function swapNodePositions(node1, node2, diagramType) {
    const pos1 = getNodePosition(node1);
    const pos2 = getNodePosition(node2);
    
    // Get children nodes for each parent
    const children1 = getChildrenNodes(node1, diagramType);
    const children2 = getChildrenNodes(node2, diagramType);
    
    // Calculate relative positions of children to their parents
    const children1Positions = children1.map(child => ({
        node: child,
        relativePos: getRelativePosition(child, node1)
    }));
    const children2Positions = children2.map(child => ({
        node: child,
        relativePos: getRelativePosition(child, node2)
    }));
    
    // Animate swap: parents first, then children
    animateNodeToPosition(node1, pos2);
    animateNodeToPosition(node2, pos1);
    
    // Animate children to new relative positions
    children1Positions.forEach(({node, relativePos}) => {
        const newPos = {
            x: pos2.x + relativePos.x,
            y: pos2.y + relativePos.y
        };
        animateNodeToPosition(node, newPos);
    });
    
    children2Positions.forEach(({node, relativePos}) => {
        const newPos = {
            x: pos1.x + relativePos.x,
            y: pos1.y + relativePos.y
        };
        animateNodeToPosition(node, newPos);
    });
    
    // Update spec: swap parent positions
    updateSpecPositions(node1, pos2);
    updateSpecPositions(node2, pos1);
    
    // Update spec: swap children positions and parent references
    updateChildrenInSpec(node1, children1, node2, children2, diagramType);
    
    // Save to history
    eventBus.emit('diagram:operation_completed', {
        operation: 'swap_nodes_hierarchical',
        snapshot: JSON.parse(JSON.stringify(editor.currentSpec))
    });
}

function getChildrenNodes(parentNode, diagramType) {
    const parentId = parentNode.attr('data-node-id');
    const parentType = parentNode.attr('data-node-type');
    const children = [];
    
    switch(diagramType) {
        case 'mindmap':
            if (parentType === 'branch') {
                const branchIndex = parseInt(parentNode.attr('data-branch-index'));
                // Find all child nodes with matching branch_index
                d3.selectAll('[data-node-type="child"]').each(function() {
                    const childNode = d3.select(this);
                    const childBranchIndex = parseInt(childNode.attr('data-branch-index'));
                    if (childBranchIndex === branchIndex) {
                        children.push(childNode);
                    }
                });
            }
            break;
        case 'tree_map':
            if (parentType === 'category') {
                // Find all leaf nodes belonging to this category
                const categoryId = parentId;
                d3.selectAll('[data-node-type="leaf"]').each(function() {
                    const leafNode = d3.select(this);
                    const leafCategoryId = leafNode.attr('data-category-id');
                    if (leafCategoryId === categoryId) {
                        children.push(leafNode);
                    }
                });
            }
            break;
        // Add more diagram types as needed
    }
    
    return children;
}
```

---

## 4. Implementation Steps

### Step 1: Extend InteractionHandler Class

**File:** `static/js/managers/editor/interaction-handler.js`

**Current Code Reference:**
```17:31:static/js/managers/editor/interaction-handler.js
class InteractionHandler {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.ownerId = 'InteractionHandler';
        this.subscribeToEvents();
        this.logger.info('InteractionHandler', 'Interaction Handler initialized');
    }
}
```

**Changes:**
1. Add new method `addHoldAndDragBehavior()` alongside existing `addDragBehavior()` (line 299)
2. Add instance properties in constructor to track hold-click state:
   ```javascript
   this.holdTimers = new Map(); // Map of nodeId -> timer
   this.isHolding = false;
   this.dragClone = null;
   this.draggedNode = null;
   this.draggedNodeId = null;
   this.targetNode = null;
   this.originalOpacity = null;
   this.childrenNodes = []; // Array of child nodes for hierarchical swap
   ```

**Estimated Lines:** ~60 lines (new method + properties)

### Step 2: Implement Hold-Click Detection

**Location:** Inside `addHoldAndDragBehavior()` method (new method in InteractionHandler)

**Implementation Pattern (based on existing `addDragBehavior` at line 299):**
```javascript
addHoldAndDragBehavior(shapeElement, textElement) {
    if (!this.editor) return;
    
    const diagramType = this.editor.diagramType;
    const nodeId = shapeElement.attr('data-node-id');
    const nodeType = shapeElement.attr('data-node-type');
    
    // Only enable for supported diagram types (mindmap, bubble_map, etc.)
    const supportedTypes = ['mindmap', 'bubble_map', 'concept_map', 'tree_map'];
    if (!supportedTypes.includes(diagramType)) {
        shapeElement.style('cursor', 'pointer');
        return;
    }
    
    const self = this;
    let startX, startY;
    let holdTimer = null;
    let initialMouseX, initialMouseY;
    
    shapeElement
        .on('mousedown', function(event) {
            event.stopPropagation();
            
            // Store initial mouse position
            initialMouseX = event.clientX;
            initialMouseY = event.clientY;
            
            // Get initial node position (diagram-type specific)
            const pos = self.getNodePosition(shapeElement, diagramType);
            startX = pos.x;
            startY = pos.y;
            
            // Start 2-second hold timer
            holdTimer = setTimeout(() => {
                // Check if mouse hasn't moved significantly (10px tolerance)
                const currentX = event.clientX;
                const currentY = event.clientY;
                const distance = Math.sqrt(
                    Math.pow(currentX - initialMouseX, 2) + 
                    Math.pow(currentY - initialMouseY, 2)
                );
                
                if (distance < 10) {
                    self.startDragMode(shapeElement, textElement, nodeId, nodeType, diagramType, startX, startY);
                }
            }, 2000);
            
            // Store timer for cleanup
            self.holdTimers.set(nodeId, holdTimer);
        })
        .on('mouseup', function(event) {
            event.stopPropagation();
            
            // Cancel hold timer if still active
            if (holdTimer) {
                clearTimeout(holdTimer);
                self.holdTimers.delete(nodeId);
                holdTimer = null;
            }
            
            // End drag mode if active
            if (self.isHolding) {
                self.endDragMode(event);
            }
        })
        .on('mousemove', function(event) {
            // Cancel timer if mouse moves significantly before 2 seconds
            if (holdTimer) {
                const distance = Math.sqrt(
                    Math.pow(event.clientX - initialMouseX, 2) + 
                    Math.pow(event.clientY - initialMouseY, 2)
                );
                
                if (distance > 10) {
                    clearTimeout(holdTimer);
                    self.holdTimers.delete(nodeId);
                    holdTimer = null;
                }
            }
        });
}
```

**Key Points:**
- Reuse pattern from existing `addDragBehavior()` (lines 317-388)
- Use `Map` to track multiple timers (one per node)
- Cancel timer on `mouseup` or significant mouse movement
- Store initial position for later use in drag mode

**Estimated Lines:** ~60 lines

### Step 3: Create Drag Clone System

**Location:** Inside `addHoldAndDragBehavior()` - create `startDragMode()` method

**Implementation Pattern (based on existing drag opacity handling at line 381):**
```javascript
startDragMode(shapeElement, textElement, nodeId, nodeType, diagramType, startX, startY) {
    this.isHolding = true;
    this.draggedNode = shapeElement;
    this.draggedNodeId = nodeId;
    
    // Set original node opacity to 30% (reuse pattern from line 381)
    shapeElement.style('opacity', 0.3);
    
    // Also set text opacity if exists
    if (textElement) {
        textElement.style('opacity', 0.3);
    }
    
    // Create drag clone
    this.dragClone = this.createDragClone(shapeElement, textElement, nodeType);
    
    // Get children nodes if this is a parent node
    this.childrenNodes = this.getChildrenNodes(shapeElement, diagramType);
    
    // Visual indication: Show subtle outline/glow on children when dragging parent
    if (this.childrenNodes.length > 0) {
        this.childrenNodes.forEach(child => {
            const childShape = d3.select(child.node());
            childShape.classed('drag-children-group', true);
            // Add subtle visual connection indicator (optional)
            this.showChildrenConnectionIndicator(shapeElement, childShape);
        });
    }
    
    // Set children opacity to 30% as well
    this.childrenNodes.forEach(child => {
        const childShape = d3.select(child.node());
        childShape.style('opacity', 0.3);
        // Also find and dim associated text
        const childText = this.findAssociatedText(childShape);
        if (childText) {
            childText.style('opacity', 0.3);
        }
    });
    
    // Attach mousemove handler to document for clone following (throttled for performance)
    let rafId = null;
    this.dragMoveHandler = (event) => {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
            this.updateDragClonePosition(event, diagramType);
            this.detectTargetNode(event, diagramType);
            rafId = null;
        });
    };
    
    document.addEventListener('mousemove', this.dragMoveHandler);
    
    // Also handle mouseleave on document to cancel drag if mouse leaves window
    this.dragLeaveHandler = (event) => {
        if (!event.relatedTarget || event.relatedTarget.nodeName === 'HTML') {
            this.cancelDrag();
        }
    };
    document.addEventListener('mouseleave', this.dragLeaveHandler);
    
    this.logger.debug('InteractionHandler', 'Drag mode started', {
        nodeId,
        nodeType,
        childrenCount: this.childrenNodes.length
    });
}

createDragClone(shapeElement, textElement, nodeType) {
    const svg = d3.select('#d3-container svg');
    if (svg.empty()) return null;
    
    const cloneGroup = svg.append('g')
        .attr('class', 'drag-clone')
        .style('opacity', 0.7)
        .style('pointer-events', 'none');
    
    // Clone shape
    const shapeClone = shapeElement.node().cloneNode(true);
    cloneGroup.node().appendChild(shapeClone);
    
    // Clone text if exists
    if (textElement && !textElement.empty()) {
        const textClone = textElement.node().cloneNode(true);
        cloneGroup.node().appendChild(textClone);
    }
    
    return cloneGroup;
}

updateDragClonePosition(event, diagramType) {
    if (!this.dragClone || this.dragClone.empty()) return;
    
    const svg = d3.select('#d3-container svg');
    if (svg.empty()) return;
    
    // Convert screen coordinates to SVG coordinates
    const pt = svg.node().createSVGPoint();
    pt.x = event.clientX;
    pt.y = event.clientY;
    const svgPoint = pt.matrixTransform(svg.node().getScreenCTM().inverse());
    
    // Position clone at mouse (offset slightly for visibility)
    this.dragClone.attr('transform', `translate(${svgPoint.x}, ${svgPoint.y})`);
}
```

**Key Points:**
- Reuse opacity pattern from existing drag (line 381: `shape.style('opacity', 0.7)`)
- Create clone as SVG group (similar to concept map groups at line 208)
- Use SVG coordinate transformation (similar to concept map at line 253)
- Handle both shape and text elements

**Estimated Lines:** ~80 lines

### Step 4: Implement Same-Level Detection

**Location:** Inside `addHoldAndDragBehavior()` - create `detectTargetNode()` method

**Implementation Pattern (based on existing node selection at line 90-104):**
```javascript
detectTargetNode(event, diagramType) {
    // Get element under cursor
    const element = document.elementFromPoint(event.clientX, event.clientY);
    if (!element) {
        this.clearTargetHighlight();
        this.targetNode = null;
        return;
    }
    
    // Find closest shape element (circle, rect, ellipse)
    const shapeElement = element.closest('circle, rect, ellipse');
    if (!shapeElement) {
        this.clearTargetHighlight();
        this.targetNode = null;
        return;
    }
    
    const targetNode = d3.select(shapeElement);
    const targetNodeId = targetNode.attr('data-node-id');
    const targetNodeType = targetNode.attr('data-node-type');
    
    // Skip if same as dragged node
    if (targetNodeId === this.draggedNodeId) {
        this.clearTargetHighlight();
        this.targetNode = null;
        return;
    }
    
    // Check if same level
    const draggedNodeType = this.draggedNode.attr('data-node-type');
    if (this.isSameLevel(draggedNodeType, targetNodeType, diagramType)) {
        // Valid target - highlight
        this.highlightTarget(targetNode, true);
        this.targetNode = targetNode;
    } else {
        // Invalid target - show different visual
        this.highlightTarget(targetNode, false);
        this.targetNode = null;
    }
}

isSameLevel(draggedType, targetType, diagramType) {
    // Simple case: same node type
    if (draggedType === targetType) {
        return true;
    }
    
    // Diagram-specific rules
    switch(diagramType) {
        case 'mindmap':
            // Branches can swap with branches, children can swap with children
            return draggedType === targetType;
        
        case 'bubble_map':
            // Attributes can swap with attributes
            return draggedType === 'attribute' && targetType === 'attribute';
        
        case 'tree_map':
            // Categories can swap with categories, leaves can swap with leaves
            return draggedType === targetType;
        
        default:
            return draggedType === targetType;
    }
}

highlightTarget(targetNode, isValid) {
    // Remove previous highlights
    d3.selectAll('.drag-target-valid, .drag-target-invalid')
        .classed('drag-target-valid', false)
        .classed('drag-target-invalid', false);
    
    if (isValid) {
        targetNode.classed('drag-target-valid', true);
        // Also highlight associated text
        const textElement = this.findAssociatedText(targetNode);
        if (textElement) {
            textElement.classed('drag-target-valid', true);
        }
    } else {
        targetNode.classed('drag-target-invalid', true);
    }
}

clearTargetHighlight() {
    d3.selectAll('.drag-target-valid, .drag-target-invalid')
        .classed('drag-target-valid', false)
        .classed('drag-target-invalid', false);
}
```

**Key Points:**
- Use `document.elementFromPoint()` for cursor detection
- Reuse node selection pattern from `attachInteractionHandlers()` (lines 90-104)
- Check `data-node-type` attribute (set in renderers, e.g., mind-map-renderer.js line 230)
- Add CSS classes for visual feedback

**Estimated Lines:** ~70 lines

### Step 5: Implement Position Swap

**Location:** Inside `addHoldAndDragBehavior()` - create `endDragMode()` and swap methods

**Implementation Pattern (based on mind map position structure from mind-map-renderer.js lines 202-292):**

```javascript
endDragMode(event) {
    if (!this.isHolding) return;
    
    // Check if we have a valid target for swap
    if (this.targetNode && !this.targetNode.empty()) {
        // Perform swap with animation
        this.performSwap(this.draggedNode, this.targetNode).then(() => {
            // Cleanup after animation completes
            this.cleanupDragMode();
        }).catch(() => {
            // Cleanup even if animation fails
            this.cleanupDragMode();
        });
    } else {
        // No valid target - just cleanup
        this.cleanupDragMode();
    }
}

cancelDrag() {
    if (!this.isHolding) return;
    
    // Cancel any ongoing animations
    d3.selectAll('*').interrupt();
    
    // Cleanup immediately
    this.cleanupDragMode();
    
    this.logger.debug('InteractionHandler', 'Drag cancelled');
}

performSwap(node1, node2) {
    const diagramType = this.editor.diagramType;
    
    // Get positions
    const pos1 = this.getNodePosition(node1, diagramType);
    const pos2 = this.getNodePosition(node2, diagramType);
    
    // Get children for both nodes
    const children1 = this.getChildrenNodes(node1, diagramType);
    const children2 = this.getChildrenNodes(node2, diagramType);
    
    // Calculate relative positions of children
    const children1Positions = children1.map(child => ({
        node: child,
        relativePos: this.getRelativePosition(child, node1, diagramType)
    }));
    const children2Positions = children2.map(child => ({
        node: child,
        relativePos: this.getRelativePosition(child, node2, diagramType)
    }));
    
    // Animate swap (returns promise)
    return this.animateSwap(node1, pos2, node2, pos1, children1Positions, children2Positions, diagramType)
        .then(() => {
            // Update spec after animation completes
            this.updateSpecAfterSwap(node1, node2, pos1, pos2, children1, children2, diagramType);
            
            // Emit history event (pattern from line 459)
            if (this.editor && this.editor.currentSpec) {
                this.eventBus.emit('diagram:operation_completed', {
                    operation: 'swap_nodes_hierarchical',
                    snapshot: JSON.parse(JSON.stringify(this.editor.currentSpec)),
                    data: {
                        node1Id: node1.attr('data-node-id'),
                        node2Id: node2.attr('data-node-id'),
                        diagramType
                    }
                });
            }
        });
}

getNodePosition(nodeElement, diagramType) {
    const nodeId = nodeElement.attr('data-node-id');
    const nodeType = nodeElement.attr('data-node-type');
    
    switch(diagramType) {
        case 'mindmap':
            // Mind map positions are in spec._layout.positions
            // Node IDs: branch_0, child_0_0 (from mind-map-renderer.js line 215, 260)
            const spec = this.editor.currentSpec;
            if (spec && spec._layout && spec._layout.positions) {
                const pos = spec._layout.positions[nodeId];
                if (pos) {
                    // Positions are relative to center (mind-map-renderer.js line 204-205)
                    const svg = d3.select('#d3-container svg');
                    const width = parseFloat(svg.attr('width')) || 700;
                    const height = parseFloat(svg.attr('height')) || 500;
                    const centerX = width / 2;
                    const centerY = height / 2;
                    return {
                        x: centerX + pos.x,
                        y: centerY + pos.y,
                        posKey: nodeId,
                        posData: pos
                    };
                }
            }
            // Fallback: get from DOM
            return this.getNodePositionFromDOM(nodeElement);
        
        case 'concept_map':
            // Concept maps use groups with transform (concept-map-renderer.js line 208)
            const parentNode = nodeElement.node().parentNode;
            if (parentNode && parentNode.tagName === 'g') {
                const transform = d3.select(parentNode).attr('transform') || 'translate(0,0)';
                const matches = transform.match(/translate\(([^,]+),([^)]+)\)/);
                if (matches) {
                    return {
                        x: parseFloat(matches[1]),
                        y: parseFloat(matches[2]),
                        isGroup: true,
                        groupElement: d3.select(parentNode)
                    };
                }
            }
            return this.getNodePositionFromDOM(nodeElement);
        
        default:
            return this.getNodePositionFromDOM(nodeElement);
    }
}

getNodePositionFromDOM(nodeElement) {
    const tagName = nodeElement.node().tagName.toLowerCase();
    if (tagName === 'circle') {
        return {
            x: parseFloat(nodeElement.attr('cx')),
            y: parseFloat(nodeElement.attr('cy'))
        };
    } else if (tagName === 'rect') {
        const width = parseFloat(nodeElement.attr('width')) || 0;
        const height = parseFloat(nodeElement.attr('height')) || 0;
        return {
            x: parseFloat(nodeElement.attr('x')) + width / 2,
            y: parseFloat(nodeElement.attr('y')) + height / 2
        };
    }
    return { x: 0, y: 0 };
}

getChildrenNodes(parentNode, diagramType) {
    const parentId = parentNode.attr('data-node-id');
    const parentType = parentNode.attr('data-node-type');
    const children = [];
    
    switch(diagramType) {
        case 'mindmap':
            if (parentType === 'branch') {
                const branchIndex = parseInt(parentNode.attr('data-branch-index'));
                // Find all child nodes with matching branch_index (mind-map-renderer.js line 276)
                d3.selectAll('[data-node-type="child"]').each(function() {
                    const childNode = d3.select(this);
                    const childBranchIndex = parseInt(childNode.attr('data-branch-index'));
                    if (childBranchIndex === branchIndex) {
                        children.push(childNode);
                    }
                });
            }
            break;
        
        case 'tree_map':
            if (parentType === 'category') {
                const categoryId = parentId;
                d3.selectAll('[data-node-type="leaf"]').each(function() {
                    const leafNode = d3.select(this);
                    const leafCategoryId = leafNode.attr('data-category-id');
                    if (leafCategoryId === categoryId) {
                        children.push(leafNode);
                    }
                });
            }
            break;
    }
    
    return children;
}

getRelativePosition(childNode, parentNode, diagramType) {
    const childPos = this.getNodePosition(childNode, diagramType);
    const parentPos = this.getNodePosition(parentNode, diagramType);
    return {
        x: childPos.x - parentPos.x,
        y: childPos.y - parentPos.y
    };
}

animateSwap(node1, pos1, node2, pos2, children1Positions, children2Positions, diagramType) {
    const duration = 300;
    const easing = d3.easeCubicOut; // Smooth deceleration for natural feel
    
    // Animate parent nodes simultaneously
    const parent1Transition = this.animateNodeToPosition(node1, pos2, diagramType, duration, easing);
    const parent2Transition = this.animateNodeToPosition(node2, pos1, diagramType, duration, easing);
    
    // Animate children with slight stagger (10ms delay between each) for visual appeal
    // This creates a "wave" effect as children follow their parent
    children1Positions.forEach(({node, relativePos}, index) => {
        const newPos = {
            x: pos2.x + relativePos.x,
            y: pos2.y + relativePos.y
        };
        setTimeout(() => {
            this.animateNodeToPosition(node, newPos, diagramType, duration, easing);
        }, index * 10); // Stagger children animations
    });
    
    children2Positions.forEach(({node, relativePos}, index) => {
        const newPos = {
            x: pos1.x + relativePos.x,
            y: pos1.y + relativePos.y
        };
        setTimeout(() => {
            this.animateNodeToPosition(node, newPos, diagramType, duration, easing);
        }, index * 10); // Stagger children animations
    });
    
    // Animate connection lines if applicable (concept maps, mind maps)
    this.animateConnectionLines(node1, node2, pos1, pos2, children1Positions, children2Positions, diagramType, duration, easing);
    
    // Return promise that resolves when all animations complete
    return Promise.all([parent1Transition, parent2Transition]);
}

animateNodeToPosition(nodeElement, targetPos, diagramType, duration = 300, easing = d3.easeCubicOut) {
    let transitionPromise = Promise.resolve();
    
    switch(diagramType) {
        case 'mindmap':
            // Mind maps: update rect attributes (mind-map-renderer.js line 218-222)
            const tagName = nodeElement.node().tagName.toLowerCase();
            if (tagName === 'rect') {
                const width = parseFloat(nodeElement.attr('width')) || 0;
                const height = parseFloat(nodeElement.attr('height')) || 0;
                
                // Animate shape with easing
                const shapeTransition = nodeElement.transition()
                    .duration(duration)
                    .ease(easing)
                    .attr('x', targetPos.x - width / 2)
                    .attr('y', targetPos.y - height / 2);
                
                // Also animate text with same easing
                const textElement = this.findAssociatedText(nodeElement);
                if (textElement) {
                    textElement.transition()
                        .duration(duration)
                        .ease(easing)
                        .attr('x', targetPos.x)
                        .attr('y', targetPos.y);
                }
                
                // Return promise that resolves when transition completes
                transitionPromise = new Promise(resolve => {
                    shapeTransition.on('end', resolve);
                });
            } else if (tagName === 'circle') {
                const circleTransition = nodeElement.transition()
                    .duration(duration)
                    .ease(easing)
                    .attr('cx', targetPos.x)
                    .attr('cy', targetPos.y);
                
                transitionPromise = new Promise(resolve => {
                    circleTransition.on('end', resolve);
                });
            }
            break;
        
        case 'concept_map':
            // Concept maps: update group transform (concept-map-renderer.js line 208)
            const parentNode = nodeElement.node().parentNode;
            if (parentNode && parentNode.tagName === 'g') {
                const groupTransition = d3.select(parentNode).transition()
                    .duration(duration)
                    .ease(easing)
                    .attr('transform', `translate(${targetPos.x}, ${targetPos.y})`);
                
                transitionPromise = new Promise(resolve => {
                    groupTransition.on('end', resolve);
                });
            }
            break;
    }
    
    return transitionPromise;
}

animateConnectionLines(node1, node2, pos1, pos2, children1Positions, children2Positions, diagramType, duration, easing) {
    if (diagramType === 'concept_map') {
        // Find and animate all lines connected to swapped nodes
        // Pattern from interaction-handler.js lines 359-379
        const node1Id = node1.attr('data-node-id');
        const node2Id = node2.attr('data-node-id');
        const tolerance = 10;
        
        d3.selectAll('line').each(function() {
            const line = d3.select(this);
            const x1 = parseFloat(line.attr('x1'));
            const y1 = parseFloat(line.attr('y1'));
            const x2 = parseFloat(line.attr('x2'));
            const y2 = parseFloat(line.attr('y2'));
            
            // Check if line connects to node1
            const connectsToNode1 = (Math.abs(x1 - pos1.x) < tolerance && Math.abs(y1 - pos1.y) < tolerance) ||
                                   (Math.abs(x2 - pos1.x) < tolerance && Math.abs(y2 - pos1.y) < tolerance);
            
            // Check if line connects to node2
            const connectsToNode2 = (Math.abs(x1 - pos2.x) < tolerance && Math.abs(y1 - pos2.y) < tolerance) ||
                                   (Math.abs(x2 - pos2.x) < tolerance && Math.abs(y2 - pos2.y) < tolerance);
            
            if (connectsToNode1 || connectsToNode2) {
                // Determine new endpoints based on which node moved
                let newX1 = x1, newY1 = y1, newX2 = x2, newY2 = y2;
                
                if (connectsToNode1) {
                    if (Math.abs(x1 - pos1.x) < tolerance && Math.abs(y1 - pos1.y) < tolerance) {
                        newX1 = pos2.x;
                        newY1 = pos2.y;
                    } else {
                        newX2 = pos2.x;
                        newY2 = pos2.y;
                    }
                }
                
                if (connectsToNode2) {
                    if (Math.abs(x1 - pos2.x) < tolerance && Math.abs(y1 - pos2.y) < tolerance) {
                        newX1 = pos1.x;
                        newY1 = pos1.y;
                    } else {
                        newX2 = pos1.x;
                        newY2 = pos1.y;
                    }
                }
                
                // Animate line to new position
                line.transition()
                    .duration(duration)
                    .ease(easing)
                    .attr('x1', newX1)
                    .attr('y1', newY1)
                    .attr('x2', newX2)
                    .attr('y2', newY2);
            }
        });
    } else if (diagramType === 'mindmap') {
        // Mind maps have connections in spec._layout.connections
        // These are rendered as lines, need to update them
        // Connection lines connect topic->branch and branch->child
        // After swap, connections need to be recalculated or updated
        // For now, lines will be updated on next render, but we could animate them here
        // This is more complex as connections are stored in spec, not directly in DOM
    }
}

updateSpecAfterSwap(node1, node2, pos1, pos2, children1, children2, diagramType) {
    const spec = this.editor.currentSpec;
    if (!spec) return;
    
    switch(diagramType) {
        case 'mindmap':
            // Update positions in spec._layout.positions (mind-map-renderer.js line 100)
            if (spec._layout && spec._layout.positions) {
                const positions = spec._layout.positions;
                const node1Id = node1.attr('data-node-id');
                const node2Id = node2.attr('data-node-id');
                
                // Get center offset
                const svg = d3.select('#d3-container svg');
                const width = parseFloat(svg.attr('width')) || 700;
                const height = parseFloat(svg.attr('height')) || 500;
                const centerX = width / 2;
                const centerY = height / 2;
                
                // Swap parent positions
                if (positions[node1Id] && positions[node2Id]) {
                    // Convert absolute to relative positions
                    positions[node1Id].x = pos2.x - centerX;
                    positions[node1Id].y = pos2.y - centerY;
                    positions[node2Id].x = pos1.x - centerX;
                    positions[node2Id].y = pos1.y - centerY;
                }
                
                // Swap children positions
                children1.forEach((child, i) => {
                    const childId = child.attr('data-node-id');
                    const relativePos = this.getRelativePosition(child, node1, diagramType);
                    if (positions[childId]) {
                        positions[childId].x = (pos2.x + relativePos.x) - centerX;
                        positions[childId].y = (pos2.y + relativePos.y) - centerY;
                    }
                });
                
                children2.forEach((child, i) => {
                    const childId = child.attr('data-node-id');
                    const relativePos = this.getRelativePosition(child, node2, diagramType);
                    if (positions[childId]) {
                        positions[childId].x = (pos1.x + relativePos.x) - centerX;
                        positions[childId].y = (pos1.y + relativePos.y) - centerY;
                    }
                });
                
                // Update branch_index in children's data attributes and spec
                this.updateChildrenBranchIndex(children1, node1, node2, diagramType);
                this.updateChildrenBranchIndex(children2, node2, node1, diagramType);
            }
            break;
    }
    
    // Emit node updated event (pattern from mindmap-operations.js line 374)
    this.eventBus.emit('diagram:node_updated', {
        diagramType,
        spec
    });
}

updateChildrenBranchIndex(children, oldParent, newParent, diagramType) {
    if (diagramType !== 'mindmap') return;
    
    const oldBranchIndex = parseInt(oldParent.attr('data-branch-index'));
    const newBranchIndex = parseInt(newParent.attr('data-branch-index'));
    
    // Update data attributes
    children.forEach(child => {
        child.attr('data-branch-index', newBranchIndex);
        
        // Update node ID pattern: child_0_0 -> child_1_0 (mind-map-renderer.js line 260)
        const childIndex = parseInt(child.attr('data-child-index'));
        const newChildId = `child_${newBranchIndex}_${childIndex}`;
        child.attr('data-node-id', newChildId);
        
        // Update associated text
        const textElement = this.findAssociatedText(child);
        if (textElement) {
            textElement.attr('data-node-id', newChildId);
            textElement.attr('data-text-for', newChildId);
        }
    });
    
    // Update spec structure (mindmap-operations.js line 336-340)
    const spec = this.editor.currentSpec;
    if (spec && Array.isArray(spec.children)) {
        // Swap branches in spec.children array
        const temp = spec.children[oldBranchIndex];
        spec.children[oldBranchIndex] = spec.children[newBranchIndex];
        spec.children[newBranchIndex] = temp;
    }
}

cleanupDragMode() {
    // Restore opacity
    if (this.draggedNode) {
        this.draggedNode.style('opacity', 1);
        const textElement = this.findAssociatedText(this.draggedNode);
        if (textElement) {
            textElement.style('opacity', 1);
        }
    }
    
    this.childrenNodes.forEach(child => {
        const childShape = d3.select(child.node());
        childShape.style('opacity', 1);
        const childText = this.findAssociatedText(childShape);
        if (childText) {
            childText.style('opacity', 1);
        }
    });
    
    // Remove clone (with fade-out animation)
    if (this.dragClone) {
        this.dragClone.transition()
            .duration(150)
            .style('opacity', 0)
            .on('end', () => {
                this.dragClone.remove();
                this.dragClone = null;
            });
    }
    
    // Remove children visual indicators
    d3.selectAll('.drag-children-group').classed('drag-children-group', false);
    d3.selectAll('.children-connection-indicator').remove();
    
    // Remove event listeners
    if (this.dragMoveHandler) {
        document.removeEventListener('mousemove', this.dragMoveHandler);
        this.dragMoveHandler = null;
    }
    if (this.dragLeaveHandler) {
        document.removeEventListener('mouseleave', this.dragLeaveHandler);
        this.dragLeaveHandler = null;
    }
    
    // Clear highlights
    this.clearTargetHighlight();
    
    // Reset state
    this.isHolding = false;
    this.draggedNode = null;
    this.draggedNodeId = null;
    this.targetNode = null;
    this.childrenNodes = [];
}

findAssociatedText(shapeElement) {
    // Pattern from interaction-handler.js line 107-108
    const shapeNode = shapeElement.node();
    const textNode = shapeNode.nextElementSibling;
    if (textNode && textNode.tagName === 'text') {
        return d3.select(textNode);
    }
    
    // Try by data-text-for attribute (mind-map-renderer.js line 242)
    const nodeId = shapeElement.attr('data-node-id');
    const textElement = d3.select(`[data-text-for="${nodeId}"]`);
    if (!textElement.empty()) {
        return textElement;
    }
    
    return null;
}

showChildrenConnectionIndicator(parentNode, childNode) {
    // Show visual line connecting parent to child during drag
    // This helps users understand which children will move with parent
    const svg = d3.select('#d3-container svg');
    if (svg.empty()) return;
    
    const parentPos = this.getNodePosition(parentNode, this.editor.diagramType);
    const childPos = this.getNodePosition(childNode, this.editor.diagramType);
    
    svg.append('line')
        .attr('class', 'children-connection-indicator')
        .attr('x1', parentPos.x)
        .attr('y1', parentPos.y)
        .attr('x2', childPos.x)
        .attr('y2', childPos.y)
        .attr('stroke', '#2196f3')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '3,3')
        .attr('opacity', 0.4)
        .style('pointer-events', 'none');
}
```

**Key Points:**
- Mind map positions stored in `spec._layout.positions` with keys like `branch_0`, `child_0_0` (mind-map-renderer.js line 100)
- Positions are relative to center: `centerX + pos.x` (mind-map-renderer.js line 204-205)
- Update both DOM and spec positions
- Update `branch_index` in children's data attributes and spec structure
- Use D3 transitions for smooth animation (pattern from existing code)
- Emit history event using existing pattern (line 459)

**Estimated Lines:** ~250 lines (increased due to hierarchical logic and diagram-type-specific handling)

### Step 6: Update Diagram Spec Structure

**Location:** Already handled in Step 5, but verify spec structure

**Current Spec Structure (Verified from codebase):**

**Mind Maps:**
- Positions: `spec._layout.positions` (mind-map-renderer.js line 100)
- Structure: `spec.children[branchIndex].children[childIndex]` (mindmap-operations.js line 336-340)
- Position keys: `branch_${branchIndex}`, `child_${branchIndex}_${childIndex}` (mind-map-renderer.js lines 215, 260)
- Positions are relative to center (mind-map-renderer.js line 204-205)

**Concept Maps:**
- Positions: `spec._layout.positions` keyed by concept text (concept-map-renderer.js line 288)
- DOM structure: Groups with transform attributes (concept-map-renderer.js line 208)
- Uses coordinate transformation system (concept-map-renderer.js line 253)

**Action Required:**
- ✅ Mind maps: Spec structure already supports position updates
- ✅ Concept maps: Spec structure already supports position updates
- No changes needed to renderer files - positions are already stored in spec

**Estimated Lines:** 0 lines (already supported)

### Step 7: Integrate with Auto-Complete Diagrams

**Location:** `static/js/managers/editor/interaction-handler.js` - modify `attachInteractionHandlers()` method

**Current Code Reference:**
```68:111:static/js/managers/editor/interaction-handler.js
attachInteractionHandlers() {
    // ... existing code ...
    d3.selectAll('circle, rect, ellipse').each((d, i, nodes) => {
        const element = d3.select(nodes[i]);
        // ... existing code ...
        // Add drag behavior (cursor style is set inside addDragBehavior based on diagram type)
        self.addDragBehavior(element, textElement);
        // ... existing code ...
    });
}
```

**Implementation:**
```javascript
attachInteractionHandlers() {
    // ... existing code up to line 109 ...
    
    // Find all node elements (shapes) and add click handlers
    d3.selectAll('circle, rect, ellipse').each((d, i, nodes) => {
        const element = d3.select(nodes[i]);
        
        // Skip background rectangles and other non-interactive elements
        const elemClass = element.attr('class') || '';
        if (elemClass.includes('background') || elemClass.includes('watermark')) {
            return;
        }
        
        const nodeId = element.attr('data-node-id') || `node_${i}`;
        
        // Add node ID attribute if not exists
        if (!element.attr('data-node-id')) {
            element.attr('data-node-id', nodeId);
        }
        
        // Find associated text
        const textNode = nodes[i].nextElementSibling;
        const textElement = (textNode && textNode.tagName === 'text') ? d3.select(textNode) : null;
        
        // Determine which interaction method to use
        const supportedTypes = ['mindmap', 'bubble_map', 'tree_map'];
        if (supportedTypes.includes(diagramType)) {
            // Use new hold-and-drag for swap functionality
            self.addHoldAndDragBehavior(element, textElement);
        } else if (diagramType === 'concept_map') {
            // Keep existing drag for concept maps (they already have drag)
            self.addDragBehavior(element, textElement);
        } else {
            // Other types: just pointer cursor
            element.style('cursor', 'pointer');
        }
        
        // ... rest of existing click handlers (lines 114-174) ...
    });
    
    // ... rest of existing code ...
}
```

**Key Points:**
- Modify `attachInteractionHandlers()` at line 68
- Add conditional logic to choose between `addHoldAndDragBehavior()` and `addDragBehavior()`
- Supported types: mindmap, bubble_map, tree_map (for swap)
- Concept maps keep existing drag (line 307)
- Auto-complete diagrams will automatically work since they use same renderers

**Estimated Lines:** ~15 lines (modification to existing method)

### Step 8: Add Visual Feedback Styles

**Location:** `static/css/editor.css` or new CSS file

**Styles Needed:**
- `.drag-clone` - styling for drag clone (semi-transparent, follows cursor)
- `.drag-target-valid` - highlight for valid swap targets (green glow/border)
- `.drag-target-invalid` - styling for invalid targets (red border or no highlight)
- `.hold-progress` - optional progress indicator (circular progress ring)
- `.drag-children-group` - visual indicator for children when dragging parent (subtle outline)
- `.children-connection-indicator` - visual line/connection showing parent-child relationship during drag

**CSS Example:**
```css
.drag-clone {
    opacity: 0.7;
    pointer-events: none;
    filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.2));
    z-index: 1000;
}

.drag-target-valid {
    stroke: #4caf50;
    stroke-width: 3px;
    filter: drop-shadow(0 0 8px rgba(76, 175, 80, 0.6));
    animation: pulse-valid 1s ease-in-out infinite;
}

.drag-target-invalid {
    stroke: #f44336;
    stroke-width: 2px;
    opacity: 0.5;
}

.drag-children-group {
    stroke: #2196f3;
    stroke-width: 2px;
    stroke-dasharray: 5, 5;
    opacity: 0.6;
}

.children-connection-indicator {
    stroke: #2196f3;
    stroke-width: 1px;
    stroke-dasharray: 3, 3;
    opacity: 0.4;
    pointer-events: none;
}

@keyframes pulse-valid {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.hold-progress {
    /* Circular progress indicator - can be implemented with SVG or CSS */
    stroke: #2196f3;
    stroke-width: 3px;
    fill: none;
    stroke-dasharray: 0, 100;
    transition: stroke-dasharray 2s linear;
}
```

**Estimated Lines:** ~60 lines

### Step 9: Handle Edge Cases

**Location:** Inside `addHoldAndDragBehavior()`

**Edge Cases:**
- Node dragged outside canvas
- Node dragged over non-node element
- Multiple rapid clicks
- Browser tab switch during drag
- Node deleted during drag

**Estimated Lines:** ~50 lines

### Step 10: Testing & Refinement

**Testing Checklist:**
- [ ] Hold-click works correctly (2-second delay)
- [ ] Visual clone follows cursor smoothly
- [ ] Original node opacity set to 30%
- [ ] Same-level detection works for all diagram types
- [ ] Position swap animates smoothly
- [ ] Spec updates correctly
- [ ] History saves correctly
- [ ] Works with auto-complete diagrams
- [ ] No conflicts with existing drag behavior

**Estimated Lines:** N/A (testing)

---

## 5. Technical Challenges & Solutions

### Challenge 1: SVG Coordinate System vs. Screen Coordinates

**Problem:**
- Mouse events provide screen coordinates
- SVG uses its own coordinate system
- Need to convert between systems

**Solution:**
- Use `SVGElement.createSVGPoint()` and `getScreenCTM()` for conversion
- Or use D3's built-in coordinate transformation

**Code Reference:**
```javascript
function screenToSVG(svg, screenX, screenY) {
    const pt = svg.createSVGPoint();
    pt.x = screenX;
    pt.y = screenY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
}
```

### Challenge 2: Node Position Storage Varies by Diagram Type

**Problem:**
- Mind maps: positions in `spec._layout.positions`
- Concept maps: positions in transform attributes
- Bubble maps: positions in attribute coordinates

**Solution:**
- Create diagram-type-specific position getters/setters
- Abstract position access through helper functions
- Store position format in node data attributes

**Code Pattern:**
```javascript
function getNodePosition(node, diagramType) {
    switch(diagramType) {
        case 'mindmap':
            return getMindMapNodePosition(node);
        case 'concept_map':
            return getConceptMapNodePosition(node);
        case 'bubble_map':
            return getBubbleMapNodePosition(node);
        default:
            return getGenericNodePosition(node);
    }
}
```

### Challenge 3: Grouped Elements (Concept Maps)

**Problem:**
- Concept maps use `<g>` groups containing shape + text
- Position is stored in `transform` attribute
- Need to handle group structure

**Solution:**
- Check if node is inside a group
- Extract transform values from group
- Update group transform on swap

**Code Reference:**
```299:475:static/js/managers/editor/interaction-handler.js
// Existing code handles groups - can reuse pattern
```

### Challenge 4: Connection Lines (Concept Maps)

**Problem:**
- Concept maps have connection lines between nodes
- Lines need to update when nodes swap positions

**Solution:**
- Reuse existing line update logic from `addDragBehavior()`
- Find all lines connected to swapped nodes
- Update line endpoints after swap

**Code Reference:**
```359:379:static/js/managers/editor/interaction-handler.js
// Existing line connection detection code
```

### Challenge 5: Hierarchical Node Relationships

**Problem:**
- Parent nodes (e.g., branches) have children that must move with them
- Need to identify parent-child relationships across different diagram types
- Need to update parent references in children (e.g., `branch_index` in mind maps)

**Solution:**
- Use `data-branch-index`, `data-category-id`, etc. attributes to identify relationships
- Create diagram-type-specific functions to find children
- When swapping parents, swap entire subtree (parent + all children)
- Update parent references in spec after swap

**Code Pattern:**
```javascript
// Mind Map example: branches have children via branch_index
function getMindMapChildren(branchNode) {
    const branchIndex = parseInt(branchNode.attr('data-branch-index'));
    return d3.selectAll(`[data-node-type="child"][data-branch-index="${branchIndex}"]`);
}

// After swap, update branch_index in children
function updateChildrenBranchIndex(oldBranchIndex, newBranchIndex) {
    d3.selectAll(`[data-node-type="child"][data-branch-index="${oldBranchIndex}"]`)
        .attr('data-branch-index', newBranchIndex);
    
    // Also update in spec structure
    const spec = editor.currentSpec;
    if (spec.children && spec.children[oldBranchIndex]) {
        const branch = spec.children[oldBranchIndex];
        if (branch.children) {
            branch.children.forEach(child => {
                // Update any branch_index references in child data
            });
        }
    }
}
```

### Challenge 6: Performance with Many Nodes

**Problem:**
- Auto-complete diagrams may have many nodes
- Continuous `mousemove` detection could be slow
- Hierarchical swaps involve multiple nodes (parent + children)

**Solution:**
- Use throttling for `mousemove` events (e.g., 16ms = 60fps)
- Use `requestAnimationFrame` for smooth updates
- Cache node positions to avoid repeated calculations
- Batch children updates together in single animation group

**Code Pattern:**
```javascript
let rafId = null;
function throttledMousemove(event) {
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
        updateDragClonePosition(event);
        detectTargetNode(event);
        rafId = null;
    });
}

// Batch children animations
function animateChildrenGroup(children, targetPositions) {
    const transitions = children.map((child, i) => 
        d3.select(child.node())
            .transition()
            .duration(300)
            .attr('transform', `translate(${targetPositions[i].x}, ${targetPositions[i].y})`)
    );
    return Promise.all(transitions);
}
```

---

## 6. Testing Strategy

### 6.1 Unit Testing

**Test Cases:**
1. Hold-click timer starts on mousedown
2. Timer cancels on mouseup before 2 seconds
3. Timer cancels if mouse moves >10px
4. Drag mode activates after 2 seconds
5. Clone created and positioned correctly
6. Original node opacity set to 0.3
7. Same-level detection works correctly
8. Position swap updates coordinates correctly

### 6.2 Integration Testing

**Test Scenarios:**
1. Complete swap flow: hold → drag → swap
2. Swap in mind map (branch level) - **verify children move with branches**
3. Swap in mind map (child level) - verify only children swap, not branches
4. Swap in bubble map (attribute level)
5. Swap in concept map (concept level)
6. Swap in tree map (category level) - **verify leaves move with categories**
7. Swap in tree map (leaf level) - verify only leaves swap
8. Cancel drag (release outside target)
9. Drag over invalid target (different level)
10. Multiple rapid hold-clicks
11. **Swap branches with different numbers of children** (e.g., branch with 3 children swaps with branch with 5 children)
12. **Verify parent-child relationships maintained after swap** (e.g., children still correctly linked to their new branch)

### 6.3 Visual Testing

**Visual Checks:**
1. Clone follows cursor smoothly (60fps, no lag)
2. Original node opacity is 30%
3. Children show visual indicator when dragging parent (outline/connection)
4. Valid targets highlight correctly (green glow with pulse animation)
5. Invalid targets show no highlight (or red border)
6. **Swap animation is smooth with easing (cubic-out)**
7. **Children animate with slight stagger (wave effect)**
8. **Connection lines animate smoothly (concept maps)**
9. Clone fades out smoothly on completion
10. No visual glitches or flickering
11. Animation completes in ~300ms (feels responsive)

### 6.4 Edge Case Testing

**Edge Cases:**
1. Node dragged outside canvas
2. Browser tab switched during drag
3. Node deleted during drag
4. Diagram re-rendered during drag
5. Multiple nodes selected during drag
6. Keyboard shortcuts during drag

---

## 7. Edge Cases

### 7.1 Node Dragged Outside Canvas

**Behavior:**
- Cancel drag operation
- Restore original node opacity
- Remove drag clone
- Reset to normal state

**Implementation:**
```javascript
function handleDragOutside(event) {
    if (!isPointInSVG(event.clientX, event.clientY)) {
        cancelDrag();
    }
}
```

### 7.2 Node Deleted During Drag

**Behavior:**
- Detect if dragged node still exists
- Cancel drag if node removed
- Clean up drag clone

**Implementation:**
```javascript
function validateDraggedNode() {
    const node = d3.select(`[data-node-id="${draggedNodeId}"]`);
    if (node.empty()) {
        cancelDrag();
        return false;
    }
    return true;
}
```

### 7.3 Diagram Re-rendered During Drag

**Behavior:**
- Cancel drag operation
- Re-render will restore normal state
- User can restart drag after render

**Implementation:**
```javascript
eventBus.on('diagram:rendered', () => {
    if (isHolding) {
        cancelDrag();
    }
});
```

### 7.4 Multiple Rapid Clicks

**Behavior:**
- Each click starts new timer
- Previous timer cancelled
- Only last timer activates drag

**Implementation:**
- Already handled by clearing timer on new mousedown

### 7.5 Browser Tab Switch During Drag

**Behavior:**
- Cancel drag on `blur` event
- Restore normal state

**Implementation:**
```javascript
window.addEventListener('blur', () => {
    if (isHolding) {
        cancelDrag();
    }
});
```

### 7.6 Swapping Parents with Different Numbers of Children

**Behavior:**
- When swapping branches with different numbers of children, all children should move
- Children maintain their relative positions to their parent
- No children are lost or duplicated

**Implementation:**
- Ensure `getChildrenNodes()` returns all children correctly
- Calculate relative positions for all children
- Animate all children to new positions
- Verify spec updates include all children

---

## 8. File Structure Changes

### 8.1 Modified Files

1. **`static/js/managers/editor/interaction-handler.js`**
   - Add `addHoldAndDragBehavior()` method
   - Modify `attachInteractionHandlers()` to use new method
   - Add helper functions for hold-click, clone, detection, swap

2. **`static/css/editor.css`** (or new CSS file)
   - Add styles for drag clone
   - Add styles for target highlighting
   - Add styles for hold-click feedback

### 8.2 New Files (Optional)

1. **`static/js/managers/editor/node-swap-handler.js`** (if separating concerns)
   - Extract swap logic into separate module
   - Imported by `InteractionHandler`

### 8.3 No Backend Changes Required

- All functionality is client-side
- No API changes needed
- History saving uses existing event system

---

## 9. Implementation Timeline Estimate

### Phase 1: Core Functionality (Week 1)
- Hold-click detection: 2-3 hours
- Drag clone system: 3-4 hours
- Same-level detection: 2-3 hours
- Position swap (basic): 3-4 hours
- **Hierarchical swap (parent + children): 4-6 hours**
- **Total: ~14-20 hours**

### Phase 2: Integration & Polish (Week 2)
- Integrate with diagram types: 2-3 hours
- Visual feedback styles: 2-3 hours
- Edge case handling: 3-4 hours
- Testing & refinement: 4-6 hours
- **Total: ~11-16 hours**

### Phase 3: Extended Support (Week 3 - Optional)
- Support additional diagram types: 4-6 hours
- Performance optimization: 2-3 hours
- Advanced animations: 2-3 hours
- **Total: ~8-12 hours**

**Grand Total: ~40-55 hours** (approximately 2-2.5 weeks of development)

**Note:** Time increased due to:
- Hierarchical swap requirement (parent nodes swap with children)
- Diagram-type-specific position handling (mind maps vs concept maps)
- Spec structure updates for multiple diagram types

---

## 10. Success Criteria

### 10.1 Functional Requirements
- ✅ Hold-click for 2 seconds activates drag mode
- ✅ Visual clone follows mouse cursor smoothly (60fps)
- ✅ Original node opacity set to 30%
- ✅ Children show visual indicator when dragging parent
- ✅ Same-level nodes are detected correctly
- ✅ Position swap works for all supported diagram types
- ✅ **When swapping parent nodes (e.g., branches), all children nodes swap with them**
- ✅ **Children maintain correct parent-child relationships after swap**
- ✅ **Swap animation is smooth with cubic-out easing (300ms duration)**
- ✅ **Children animate with slight stagger for visual appeal (wave effect)**
- ✅ **Connection lines animate smoothly (concept maps)**
- ✅ Clone fades out smoothly after swap

### 10.2 Technical Requirements
- ✅ No performance degradation with many nodes
- ✅ Works with auto-complete diagrams
- ✅ Compatible with existing drag behavior
- ✅ History saving works correctly
- ✅ No memory leaks or event listener issues

### 10.3 User Experience Requirements
- ✅ Intuitive interaction (users understand hold-click)
- ✅ Clear visual feedback at all stages
- ✅ **Smooth, polished animations with easing**
- ✅ **Visual connection indicators show parent-child relationships**
- ✅ **Staggered children animation creates pleasing visual effect**
- ✅ No unexpected behavior or glitches
- ✅ Animation feels responsive and natural (not too fast, not too slow)

---

## 11. Conclusion

**Feasibility:** ✅ **FULLY FEASIBLE**

The proposed drag-and-drop swap feature is technically feasible and can be implemented using existing technologies and patterns in the codebase. The main challenges are:

1. **Coordinate system conversion** - Solvable with SVG APIs
2. **Diagram-type-specific position handling** - Solvable with abstraction layer
3. **Performance optimization** - Solvable with throttling and caching

**Recommendation:** Proceed with implementation, starting with Phase 1 (core functionality) for mind maps and bubble maps, then expanding to other diagram types.

**Next Steps:**
1. Review this document with team
2. Get approval for implementation
3. Start with Step 1 (extend InteractionHandler)
4. Iterate through implementation steps
5. Test thoroughly before deployment

---

## Appendix A: Code Structure Preview

### A.1 New Method Signature

```javascript
/**
 * Add hold-and-drag behavior for node swapping
 * @param {d3.Selection} shapeElement - The shape element (circle, rect, ellipse)
 * @param {d3.Selection} textElement - Associated text element (optional)
 * @param {string} diagramType - Type of diagram
 */
addHoldAndDragBehavior(shapeElement, textElement, diagramType) {
    // Implementation
}
```

### A.2 Helper Functions

```javascript
// Hold-click detection
startHoldTimer(element, event) { }
cancelHoldTimer() { }
checkHoldComplete(event) { }

// Drag clone
createDragClone(originalNode) { }
updateDragClonePosition(event) { }
removeDragClone() { }

// Same-level detection
getNodeUnderCursor(event) { }
isSameLevel(draggedNode, targetNode) { }
highlightValidTargets() { }

// Hierarchical relationships
getChildrenNodes(parentNode, diagramType) { }
getRelativePosition(childNode, parentNode) { }
isParentNode(node, diagramType) { }
updateChildrenParentReference(children, oldParentIndex, newParentIndex, diagramType) { }

// Position swap
getNodePosition(node, diagramType) { }
setNodePosition(node, position, diagramType) { }
swapNodePositions(node1, node2, diagramType) { }
swapNodePositionsHierarchical(node1, node2, diagramType) { }
animateSwap(node1, pos1, node2, pos2) { }
animateSwapHierarchical(parent1, children1, parent2, children2) { }
```

---

## 12. Code File Reference Summary

### Files to Modify

1. **`static/js/managers/editor/interaction-handler.js`**
   - Add `addHoldAndDragBehavior()` method (~250 lines)
   - Modify `attachInteractionHandlers()` method (~15 lines)
   - Add helper methods for position handling (~150 lines)
   - **Total: ~415 lines added/modified**

2. **`static/css/editor.css`** (or create new CSS file)
   - Add styles for drag clone, target highlighting (~40 lines)

### Files Referenced (No Changes Needed)

1. **`static/js/renderers/mind-map-renderer.js`**
   - Reference: Node structure (lines 202-292)
   - Reference: Position storage (line 100)
   - Reference: Node IDs (lines 215, 260)

2. **`static/js/renderers/concept-map-renderer.js`**
   - Reference: Group structure (line 208)
   - Reference: Coordinate transformation (line 253)

3. **`static/js/managers/editor/diagram-types/mindmap-operations.js`**
   - Reference: Spec structure (lines 336-340)
   - Reference: History events (line 383)

### Key Code Patterns to Reuse

1. **Opacity handling:** `interaction-handler.js` line 381
2. **Position extraction:** `interaction-handler.js` lines 330-357
3. **Group handling:** `interaction-handler.js` lines 331-341, 401-403
4. **History events:** `interaction-handler.js` line 459
5. **Node selection:** `interaction-handler.js` lines 90-104

---

**Document Version:** 1.1  
**Last Updated:** 2025-01-XX  
**Author:** AI Assistant  
**Status:** Ready for Implementation - All steps updated with actual code references

