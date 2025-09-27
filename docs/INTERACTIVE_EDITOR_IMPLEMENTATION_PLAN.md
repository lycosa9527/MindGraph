# MindGraph Interactive Editor Implementation Plan

**Project**: Building a fully functional interactive web interface for MindGraph  
**Current Status**: Production-ready prompt-based system with D3.js renderers  
**Target**: Interactive editing of nodes, branches, colors, fonts, and layout  
**Approach**: Extend existing D3.js system with interaction layers  

*Last Updated: January 2025*

---

## 🎯 **EXECUTIVE SUMMARY**

**Objective**: Create a professional interactive diagram editor with a polished user experience where users can:
- **Start**: Choose from a gallery of diagram types with previews
- **Create**: Select a diagram type to start with a blank template or AI-generated content
- **Edit**: Click and edit any node's text, colors, and fonts
- **Customize**: Drag and drop nodes to reposition them
- **Style**: Apply custom styling and themes in real-time
- **Save**: Save, load, and export customized diagrams

**Strategy**: Build a complete professional interface with diagram type selection, then interactive features on top of the existing, optimized D3.js renderer system.

**Timeline**: 8 weeks total (4 phases of 2 weeks each)  
**Risk Level**: Medium - complex interactive system with performance considerations  
**Expected Outcome**: Professional interactive diagram editor maintaining current performance and quality

---

## 📋 **PHASE 1: CORE INTERACTIVE FOUNDATION** (Weeks 1-2)

### **Week 1: Interactive Renderer Creation**

#### **1.1 Create Interactive Renderer System** (2 days)
**New Files:**
- `static/js/interactive/renderers/interactive-mind-map-renderer.js`
- `static/js/interactive/renderers/interactive-concept-map-renderer.js`
- `static/js/interactive/renderers/interactive-bubble-map-renderer.js`
- `static/js/interactive/renderers/interactive-flow-renderer.js`
- `static/js/interactive/renderers/interactive-brace-renderer.js`
- `static/js/interactive/renderers/interactive-tree-renderer.js`

**Implementation Strategy:**
```javascript
// Step 1: Copy existing renderer
// Step 2: Add interaction layers
// Step 3: Integrate with selection system
// Step 4: Add drag and drop functionality

class InteractiveMindMapRenderer {
    constructor(containerId) {
        this.containerId = containerId;
        this.selectedNodes = new Set();
        this.draggedNode = null;
        this.selectionManager = new SelectionManager();
    }
    
    render(spec, theme, dimensions) {
        // Copy existing rendering logic
        this.renderStaticElements(spec, theme, dimensions);
        
        // Add interaction layers
        this.addInteractionHandlers();
        this.addSelectionHandlers();
        this.addDragHandlers();
    }
    
    addInteractionHandlers() {
        // Click handlers for node editing
        this.nodes.on('click', (d) => this.handleNodeClick(d))
                 .on('dblclick', (d) => this.handleNodeDoubleClick(d))
                 .on('contextmenu', (d) => this.handleNodeRightClick(d));
    }
    
    addSelectionHandlers() {
        // Selection visual feedback
        this.nodes.on('click', (d) => {
            if (d3.event.ctrlKey || d3.event.metaKey) {
                this.toggleNodeSelection(d);
            } else {
                this.selectNode(d);
            }
        });
    }
    
    addDragHandlers() {
        // Drag and drop functionality
        const drag = d3.drag()
            .on('start', (d) => this.handleDragStart(d))
            .on('drag', (d) => this.handleDrag(d))
            .on('end', (d) => this.handleDragEnd(d));
            
        this.nodes.call(drag);
    }
}
```

**Deliverables:**
- [ ] Interactive versions of all 6 renderer types
- [ ] Click, drag, and selection handlers
- [ ] Visual feedback for interactions
- [ ] Integration with selection system

#### **1.2 Implement Main Editor Controller** (2 days)
**New Files:**
- `static/js/editor/interactive-editor.js`

**Features:**
- Central controller for entire editor system
- State management for diagrams and user interactions
- Integration between all editor components
- Real-time updates and synchronization

**Implementation:**
```javascript
class InteractiveEditor {
    constructor(diagramType, template) {
        this.diagramType = diagramType;
        this.currentSpec = template;
        this.selectedNodes = new Set();
        this.history = [];
        this.historyIndex = -1;
        
        // Initialize components
        this.selectionManager = new SelectionManager();
        this.toolbarManager = new ToolbarManager(this);
        this.canvasManager = new CanvasManager();
        this.connectionManager = new ConnectionManager();
        this.clipboardManager = new ClipboardManager();
        
        // Initialize renderer
        this.renderer = this.createRenderer(diagramType);
    }
    
    initialize() {
        // Setup canvas and container
        this.canvasManager.setupCanvas('#d3-container');
        
        // Initialize toolbar
        this.toolbarManager.initialize();
        
        // Render initial diagram
        this.renderDiagram();
        
        // Setup global event handlers
        this.setupGlobalEventHandlers();
    }
    
    createRenderer(diagramType) {
        const rendererMap = {
            'mindmap': InteractiveMindMapRenderer,
            'concept_map': InteractiveConceptMapRenderer,
            'bubble_map': InteractiveBubbleMapRenderer,
            'flow_map': InteractiveFlowRenderer,
            'brace_map': InteractiveBraceRenderer,
            'tree_map': InteractiveTreeRenderer
        };
        
        const RendererClass = rendererMap[diagramType];
        return new RendererClass('#d3-container');
    }
    
    renderDiagram() {
        this.renderer.render(this.currentSpec, this.getCurrentTheme(), this.getCurrentDimensions());
        this.updateToolbarState();
    }
    
    addNode(nodeData) {
        // Add node to spec
        this.currentSpec.nodes = this.currentSpec.nodes || [];
        this.currentSpec.nodes.push(nodeData);
        
        // Save to history
        this.saveToHistory('add_node', null, nodeData);
        
        // Re-render
        this.renderDiagram();
    }
    
    deleteNode(nodeId) {
        // Remove from spec
        this.currentSpec.nodes = this.currentSpec.nodes.filter(n => n.id !== nodeId);
        
        // Remove from selection
        this.selectedNodes.delete(nodeId);
        
        // Save to history
        this.saveToHistory('delete_node', { nodeId }, null);
        
        // Re-render
        this.renderDiagram();
    }
    
    updateNode(nodeId, updates) {
        const node = this.currentSpec.nodes.find(n => n.id === nodeId);
        if (node) {
            const oldData = { ...node };
            Object.assign(node, updates);
            
            // Save to history
            this.saveToHistory('update_node', { nodeId, oldData }, { nodeId, newData: node });
            
            // Re-render
            this.renderDiagram();
        }
    }
    
    selectNode(nodeId) {
        this.selectedNodes.add(nodeId);
        this.selectionManager.selectNode(nodeId);
        this.updateToolbarState();
    }
    
    deselectNode(nodeId) {
        this.selectedNodes.delete(nodeId);
        this.selectionManager.deselectNode(nodeId);
        this.updateToolbarState();
    }
    
    clearSelection() {
        this.selectedNodes.clear();
        this.selectionManager.clearSelection();
        this.updateToolbarState();
    }
    
    updateToolbarState() {
        this.toolbarManager.updateState(this.selectedNodes);
    }
    
    getCurrentDiagramData() {
        return {
            type: this.diagramType,
            spec: this.currentSpec,
            selectedNodes: Array.from(this.selectedNodes),
            timestamp: Date.now()
        };
    }
    
    saveToHistory(action, oldState, newState) {
        this.history = this.history.slice(0, this.historyIndex + 1);
        this.history.push({
            action,
            oldState: JSON.parse(JSON.stringify(oldState)),
            newState: JSON.parse(JSON.stringify(newState)),
            timestamp: Date.now()
        });
        this.historyIndex = this.history.length - 1;
    }
}
```

**Deliverables:**
- [ ] Main editor controller class
- [ ] State management system
- [ ] Component integration
- [ ] History management
- [ ] Real-time updates

#### **1.3 Implement Node Selection System** (1 day)
**New Files:**
- `static/js/editor/selection-manager.js`

**Features:**
- Visual selection indicators
- Multi-select functionality
- Selection persistence
- Keyboard navigation

**Implementation:**
```javascript
class SelectionManager {
    constructor() {
        this.selectedNodes = new Set();
        this.selectionBox = null;
        this.isSelecting = false;
        this.selectionStart = null;
    }
    
    selectNode(nodeId) {
        this.selectedNodes.add(nodeId);
        this.updateVisualSelection(nodeId, true);
    }
    
    deselectNode(nodeId) {
        this.selectedNodes.delete(nodeId);
        this.updateVisualSelection(nodeId, false);
    }
    
    toggleNodeSelection(nodeId) {
        if (this.selectedNodes.has(nodeId)) {
            this.deselectNode(nodeId);
        } else {
            this.selectNode(nodeId);
        }
    }
    
    clearSelection() {
        this.selectedNodes.forEach(nodeId => {
            this.updateVisualSelection(nodeId, false);
        });
        this.selectedNodes.clear();
    }
    
    updateVisualSelection(nodeId, isSelected) {
        const nodeElement = d3.select(`#node-${nodeId}`);
        
        if (isSelected) {
            nodeElement.classed('selected', true)
                     .attr('stroke', '#ff6b6b')
                     .attr('stroke-width', 3)
                     .style('filter', 'drop-shadow(0 0 8px rgba(255, 107, 107, 0.6))');
        } else {
            nodeElement.classed('selected', false)
                     .attr('stroke', null)
                     .attr('stroke-width', null)
                     .style('filter', null);
        }
    }
    
    startBoxSelection(event) {
        this.isSelecting = true;
        this.selectionStart = { x: event.clientX, y: event.clientY };
        
        this.selectionBox = d3.select('#d3-container')
            .append('rect')
            .attr('class', 'selection-box')
            .attr('x', this.selectionStart.x)
            .attr('y', this.selectionStart.y)
            .attr('width', 0)
            .attr('height', 0)
            .style('fill', 'rgba(100, 150, 255, 0.1)')
            .style('stroke', '#6496ff')
            .style('stroke-width', 2)
            .style('stroke-dasharray', '5,5');
    }
    
    updateBoxSelection(event) {
        if (!this.isSelecting) return;
        
        const width = event.clientX - this.selectionStart.x;
        const height = event.clientY - this.selectionStart.y;
        
        this.selectionBox
            .attr('width', Math.abs(width))
            .attr('height', Math.abs(height))
            .attr('x', width < 0 ? event.clientX : this.selectionStart.x)
            .attr('y', height < 0 ? event.clientY : this.selectionStart.y);
    }
    
    endBoxSelection() {
        if (!this.isSelecting) return;
        
        this.isSelecting = false;
        this.selectionBox.remove();
        
        // Select nodes within selection box
        const selectionBounds = this.getSelectionBounds();
        this.selectNodesInBounds(selectionBounds);
    }
    
    selectNodesInBounds(bounds) {
        d3.selectAll('.node').each(function(d) {
            const nodeBounds = this.getBoundingClientRect();
            const containerBounds = document.getElementById('d3-container').getBoundingClientRect();
            
            const nodeX = nodeBounds.left - containerBounds.left;
            const nodeY = nodeBounds.top - containerBounds.top;
            
            if (nodeX >= bounds.x && nodeX <= bounds.x + bounds.width &&
                nodeY >= bounds.y && nodeY <= bounds.y + bounds.height) {
                
                d3.select(this).node().click();
            }
        });
    }
    
    getSelectionBounds() {
        return {
            x: Math.min(this.selectionStart.x, d3.event.clientX),
            y: Math.min(this.selectionStart.y, d3.event.clientY),
            width: Math.abs(d3.event.clientX - this.selectionStart.x),
            height: Math.abs(d3.event.clientY - this.selectionStart.y)
        };
    }
}
```

**Deliverables:**
- [ ] Visual selection indicators
- [ ] Multi-select with Ctrl+click
- [ ] Box selection with mouse drag
- [ ] Selection persistence
- [ ] Keyboard navigation support

### **Week 2: Canvas and Viewport Management**

#### **1.1 Add Click Handlers to All Renderers** (2 days)
**Files to Modify:**
- `static/js/renderers/mind-map-renderer.js`
- `static/js/renderers/concept-map-renderer.js`
- `static/js/renderers/bubble-map-renderer.js`
- `static/js/renderers/flow-renderer.js`
- `static/js/renderers/brace-renderer.js`
- `static/js/renderers/tree-renderer.js`

**Implementation:**
```javascript
// Add to each renderer's node creation
nodes.on('click', function(d) {
    event.stopPropagation();
    openNodeEditor(d, spec);
})
.on('mouseover', function(d) {
    showEditIndicator(this);
})
.on('mouseout', function(d) {
    hideEditIndicator(this);
});
```

**Deliverables:**
- [ ] All nodes clickable across all diagram types
- [ ] Visual feedback on hover (edit cursor, highlight)
- [ ] Event handling system established

#### **1.2 Create Node Editor Component** (2 days)
**New Files:**
- `static/js/editors/node-editor.js`
- `static/js/widgets/text-editor.js`

**Features:**
- Modal popup for editing node text
- Input validation (text length, character limits)
- Real-time preview of changes
- Cancel/Apply buttons

**Implementation:**
```javascript
class NodeEditor {
    constructor(nodeData, spec, onSave, onCancel) {
        this.nodeData = nodeData;
        this.spec = spec;
        this.onSave = onSave;
        this.onCancel = onCancel;
    }
    
    show() {
        // Create modal with text input
        // Show current text for editing
        // Handle save/cancel actions
    }
}
```

**Deliverables:**
- [ ] Modal editor for text changes
- [ ] Input validation and error handling
- [ ] Integration with all renderer types

#### **1.3 Implement Basic Drag-and-Drop** (1 day)
**Files to Modify:**
- All renderer files (add drag behavior)

**Implementation:**
```javascript
// Add to node creation in each renderer
nodes.call(d3.drag()
    .on('start', function(d) {
        d3.select(this).raise();
        d3.select(this).classed('dragging', true);
    })
    .on('drag', function(d) {
        d3.select(this)
            .attr('transform', `translate(${d3.event.x}, ${d3.event.y})`);
    })
    .on('end', function(d) {
        d3.select(this).classed('dragging', false);
        // Update spec with new position
        updateNodePosition(d.id, d3.event.x, d3.event.y);
    })
);
```

**Deliverables:**
- [ ] All nodes draggable
- [ ] Visual feedback during drag
- [ ] Position updates saved to spec

### **Week 2: Style Management Foundation**

#### **2.1 Extend StyleManager for Runtime Editing** (2 days)
**Files to Modify:**
- `static/js/style-manager.js`

**New Features:**
```javascript
class InteractiveStyleManager extends StyleManager {
    constructor() {
        super();
        this.nodeStyles = new Map(); // nodeId -> style object
        this.listeners = []; // For style change notifications
    }
    
    updateNodeStyle(nodeId, styleProperties) {
        const currentStyle = this.nodeStyles.get(nodeId) || {};
        this.nodeStyles.set(nodeId, { ...currentStyle, ...styleProperties });
        this.notifyListeners(nodeId, this.nodeStyles.get(nodeId));
    }
    
    getNodeStyle(nodeId) {
        return this.nodeStyles.get(nodeId) || this.getDefaultNodeStyle();
    }
}
```

**Deliverables:**
- [ ] Runtime style modification system
- [ ] Style change event notifications
- [ ] Node-specific style storage

#### **2.2 Create Style Property Panel** (2 days)
**New Files:**
- `static/js/widgets/style-panel.js`
- `static/js/widgets/color-picker.js`
- `static/js/widgets/font-selector.js`

**Features:**
- Color picker for node backgrounds
- Font family and size selectors
- Text color picker
- Border color and width controls
- Real-time preview of changes

**Implementation:**
```javascript
class StylePanel {
    constructor(selectedNode, onStyleChange) {
        this.selectedNode = selectedNode;
        this.onStyleChange = onStyleChange;
        this.createPanel();
    }
    
    createPanel() {
        // Create HTML form with:
        // - Color pickers
        // - Font selectors
        // - Border controls
        // - Live preview
    }
}
```

**Deliverables:**
- [ ] Visual style editing panel
- [ ] Color picker widget
- [ ] Font selection controls
- [ ] Real-time style updates

#### **2.3 Implement Node Selection System** (1 day)
**Files to Modify:**
- All renderer files
- `static/js/editors/selection-manager.js` (new)

**Features:**
- Click to select nodes
- Multi-select with Ctrl+click
- Visual selection indicators
- Selected node highlighting

**Implementation:**
```javascript
class SelectionManager {
    constructor() {
        this.selectedNodes = new Set();
        this.renderers = new Map();
    }
    
    selectNode(nodeId, renderer) {
        this.selectedNodes.add(nodeId);
        this.renderers.set(nodeId, renderer);
        this.updateVisualSelection();
    }
    
    updateVisualSelection() {
        // Update visual indicators for selected nodes
    }
}
```

**Deliverables:**
- [ ] Single and multi-node selection
- [ ] Visual selection indicators
- [ ] Integration with style panel

---

## 📋 **PHASE 2: ADVANCED EDITING FEATURES** (Weeks 3-4)

### **Week 3: Advanced Styling and Layout**

#### **3.1 Implement Theme System Integration** (2 days)
**Files to Modify:**
- `static/js/style-manager.js`
- `static/js/theme-config.js`

**Features:**
- Apply predefined themes to selected nodes
- Create custom theme presets
- Theme preview system
- Bulk theme application

**Implementation:**
```javascript
class ThemeManager {
    constructor() {
        this.customThemes = new Map();
        this.currentTheme = 'default';
    }
    
    applyTheme(themeName, nodeIds = null) {
        const theme = this.getTheme(themeName);
        const targets = nodeIds || Array.from(this.selectedNodes);
        
        targets.forEach(nodeId => {
            this.styleManager.updateNodeStyle(nodeId, theme);
        });
        
        this.refreshRenderer();
    }
    
    saveCustomTheme(name, themeData) {
        this.customThemes.set(name, themeData);
        localStorage.setItem('customThemes', JSON.stringify([...this.customThemes]));
    }
}
```

**Deliverables:**
- [ ] Theme application system
- [ ] Custom theme creation
- [ ] Theme persistence in localStorage

#### **3.2 Add Layout Tools** (2 days)
**New Files:**
- `static/js/tools/layout-manager.js`
- `static/js/tools/alignment-tools.js`

**Features:**
- Auto-arrange nodes
- Align left/right/center/top/bottom
- Distribute nodes evenly
- Snap to grid functionality
- Undo/redo for layout changes

**Implementation:**
```javascript
class LayoutManager {
    constructor(spec, renderer) {
        this.spec = spec;
        this.renderer = renderer;
        this.history = [];
    }
    
    autoArrange() {
        // Use existing layout algorithms
        const newLayout = this.calculateOptimalLayout();
        this.applyLayout(newLayout);
        this.saveToHistory();
    }
    
    alignNodes(direction) {
        // Align selected nodes
        const positions = this.calculateAlignment(direction);
        this.applyPositions(positions);
        this.saveToHistory();
    }
}
```

**Deliverables:**
- [ ] Auto-arrange functionality
- [ ] Alignment tools
- [ ] Grid snapping
- [ ] Layout undo/redo

#### **3.3 Implement Undo/Redo System** (1 day)
**New Files:**
- `static/js/editors/history-manager.js`

**Features:**
- Track all user actions (text changes, moves, style changes)
- Undo/redo with keyboard shortcuts (Ctrl+Z, Ctrl+Y)
- Visual undo/redo buttons
- History state persistence

**Implementation:**
```javascript
class HistoryManager {
    constructor() {
        this.history = [];
        this.currentIndex = -1;
        this.maxHistorySize = 50;
    }
    
    saveState(action, oldState, newState) {
        this.history = this.history.slice(0, this.currentIndex + 1);
        this.history.push({
            action,
            oldState: JSON.parse(JSON.stringify(oldState)),
            newState: JSON.parse(JSON.stringify(newState)),
            timestamp: Date.now()
        });
        
        this.currentIndex = this.history.length - 1;
        this.trimHistory();
    }
    
    undo() {
        if (this.canUndo()) {
            const state = this.history[this.currentIndex];
            this.applyState(state.oldState);
            this.currentIndex--;
        }
    }
}
```

**Deliverables:**
- [ ] Complete undo/redo system
- [ ] Keyboard shortcuts
- [ ] History state management

### **Week 4: Data Persistence and Export**

#### **4.1 Implement Save/Load System** (2 days)
**Files to Modify:**
- `api_routes.py` (add new endpoints)
- `static/js/api/save-manager.js` (new)

**New API Endpoints:**
```python
@api.route('/save_diagram', methods=['POST'])
def save_diagram():
    """Save edited diagram with custom styling"""
    
@api.route('/load_diagram/<diagram_id>', methods=['GET'])
def load_diagram(diagram_id):
    """Load saved diagram"""
    
@api.route('/list_diagrams', methods=['GET'])
def list_diagrams():
    """List all saved diagrams"""
```

**Frontend Implementation:**
```javascript
class SaveManager {
    constructor() {
        this.currentDiagram = null;
        this.autoSaveInterval = null;
    }
    
    saveDiagram(diagramData) {
        return fetch('/api/save_diagram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                spec: diagramData.spec,
                styles: diagramData.styles,
                metadata: diagramData.metadata
            })
        });
    }
    
    loadDiagram(diagramId) {
        return fetch(`/api/load_diagram/${diagramId}`)
            .then(response => response.json());
    }
    
    enableAutoSave(intervalMs = 30000) {
        this.autoSaveInterval = setInterval(() => {
            this.autoSave();
        }, intervalMs);
    }
}
```

**Deliverables:**
- [ ] Save/load API endpoints
- [ ] Frontend save manager
- [ ] Auto-save functionality
- [ ] Diagram listing interface

#### **4.2 Enhanced Export System** (2 days)
**Files to Modify:**
- `api_routes.py` (enhance existing endpoints)
- `static/js/api/export-manager.js` (new)

**Features:**
- Export with custom styling
- Multiple export formats (PNG, SVG, PDF)
- High-resolution export options
- Batch export for multiple diagrams

**Implementation:**
```javascript
class ExportManager {
    constructor() {
        this.exportFormats = ['png', 'svg', 'pdf'];
    }
    
    exportDiagram(format, options = {}) {
        const exportData = {
            spec: this.getCurrentSpec(),
            styles: this.getCurrentStyles(),
            format: format,
            options: {
                resolution: options.resolution || 'standard',
                includeWatermark: options.includeWatermark !== false,
                ...options
            }
        };
        
        return fetch('/api/export_custom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(exportData)
        });
    }
    
    downloadAsFile(data, filename) {
        const blob = new Blob([data], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }
}
```

**Deliverables:**
- [ ] Custom styling export
- [ ] Multiple format support
- [ ] High-resolution options
- [ ] Download management

#### **4.3 Create Professional Diagram Selection Interface** (1 day)
**New Files:**
- `templates/editor.html` (new editor landing page)
- `static/js/editor/diagram-gallery.js` (new)
- `static/css/editor.css` (new)

**Features:**
- Professional landing page with diagram type gallery
- Visual previews for each diagram type (Mind Map, Bubble Map, Flow Map, etc.)
- Clean, modern UI design with categories
- "Generate with AI" option as alternative
- Responsive layout for all devices

**Layout:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>MindGraph Interactive Editor</title>
    <link rel="stylesheet" href="/static/css/editor.css">
</head>
<body>
    <div class="editor-landing">
        <header class="editor-header">
            <h1>🧠 MindGraph Interactive Editor</h1>
            <p>Choose a diagram type to start creating</p>
        </header>
        
        <div class="diagram-gallery">
            <div class="diagram-category">
                <h2>🧠 Thinking Maps</h2>
                <div class="diagram-grid">
                    <div class="diagram-card" data-type="mindmap">
                        <div class="diagram-preview">
                            <svg><!-- Mind map preview --></svg>
                        </div>
                        <h3>Mind Map</h3>
                        <p>Central topic with radiating branches</p>
                        <button class="select-diagram-btn">Select</button>
                    </div>
                    
                    <div class="diagram-card" data-type="bubble_map">
                        <div class="diagram-preview">
                            <svg><!-- Bubble map preview --></svg>
                        </div>
                        <h3>Bubble Map</h3>
                        <p>Central topic with descriptive attributes</p>
                        <button class="select-diagram-btn">Select</button>
                    </div>
                    
                    <div class="diagram-card" data-type="double_bubble_map">
                        <div class="diagram-preview">
                            <svg><!-- Double bubble map preview --></svg>
                        </div>
                        <h3>Double Bubble Map</h3>
                        <p>Compare and contrast two topics</p>
                        <button class="select-diagram-btn">Select</button>
                    </div>
                    
                    <div class="diagram-card" data-type="flow_map">
                        <div class="diagram-preview">
                            <svg><!-- Flow map preview --></svg>
                        </div>
                        <h3>Flow Map</h3>
                        <p>Sequential process or workflow</p>
                        <button class="select-diagram-btn">Select</button>
                    </div>
                </div>
            </div>
            
            <div class="diagram-category">
                <h2>📊 Advanced Diagrams</h2>
                <div class="diagram-grid">
                    <div class="diagram-card" data-type="concept_map">
                        <div class="diagram-preview">
                            <svg><!-- Concept map preview --></svg>
                        </div>
                        <h3>Concept Map</h3>
                        <p>Complex relationships between concepts</p>
                        <button class="select-diagram-btn">Select</button>
                    </div>
                    
                    <div class="diagram-card" data-type="tree_map">
                        <div class="diagram-preview">
                            <svg><!-- Tree map preview --></svg>
                        </div>
                        <h3>Tree Map</h3>
                        <p>Hierarchical data visualization</p>
                        <button class="select-diagram-btn">Select</button>
                    </div>
                    
                    <div class="diagram-card" data-type="brace_map">
                        <div class="diagram-preview">
                            <svg><!-- Brace map preview --></svg>
                        </div>
                        <h3>Brace Map</h3>
                        <p>Whole-part relationships</p>
                        <button class="select-diagram-btn">Select</button>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="landing-footer">
            <button id="ai-generate-btn" class="btn-primary">
                🤖 Generate with AI Instead
            </button>
            <p>Or use AI to generate a diagram from your description</p>
        </div>
    </div>
    
    <!-- Editor Interface (hidden initially) -->
    <div class="editor-interface" style="display: none;">
        <div class="editor-toolbar">
            <!-- Left Section: Navigation & File Operations -->
            <div class="toolbar-section toolbar-left">
                <button id="back-to-gallery" class="btn-secondary">← Back to Gallery</button>
                <button id="save-btn" class="btn-primary">💾 Save</button>
                <button id="load-btn" class="btn-primary">📂 Load</button>
                <button id="export-btn" class="btn-success">📤 Export</button>
            </div>
            
            <!-- Center Section: Node Management -->
            <div class="toolbar-section toolbar-center">
                <div class="toolbar-group">
                    <label>Nodes:</label>
                    <button id="add-node-btn" class="btn-tool" title="Add Node">➕ Add</button>
                    <button id="delete-node-btn" class="btn-tool" title="Delete Selected">🗑️ Delete</button>
                    <button id="duplicate-node-btn" class="btn-tool" title="Duplicate Selected">📋 Copy</button>
                </div>
                
                <div class="toolbar-group">
                    <label>Text:</label>
                    <select id="font-family" class="tool-select">
                        <option value="Inter">Inter</option>
                        <option value="Arial">Arial</option>
                        <option value="Helvetica">Helvetica</option>
                        <option value="Times New Roman">Times New Roman</option>
                        <option value="Georgia">Georgia</option>
                    </select>
                    <select id="font-size" class="tool-select">
                        <option value="10">10px</option>
                        <option value="12">12px</option>
                        <option value="14" selected>14px</option>
                        <option value="16">16px</option>
                        <option value="18">18px</option>
                        <option value="20">20px</option>
                        <option value="24">24px</option>
                        <option value="28">28px</option>
                        <option value="32">32px</option>
                    </select>
                    <button id="bold-btn" class="btn-tool" title="Bold">B</button>
                    <button id="italic-btn" class="btn-tool" title="Italic">I</button>
                </div>
            </div>
            
            <!-- Right Section: Styling & Tools -->
            <div class="toolbar-section toolbar-right">
                <div class="toolbar-group">
                    <label>Colors:</label>
                    <input type="color" id="fill-color" class="color-picker" title="Fill Color" value="#1976d2">
                    <input type="color" id="text-color" class="color-picker" title="Text Color" value="#ffffff">
                    <input type="color" id="border-color" class="color-picker" title="Border Color" value="#000000">
                </div>
                
                <div class="toolbar-group">
                    <label>Border:</label>
                    <select id="border-width" class="tool-select">
                        <option value="0">No Border</option>
                        <option value="1">1px</option>
                        <option value="2" selected>2px</option>
                        <option value="3">3px</option>
                        <option value="4">4px</option>
                        <option value="5">5px</option>
                    </select>
                    <select id="border-style" class="tool-select">
                        <option value="solid" selected>Solid</option>
                        <option value="dashed">Dashed</option>
                        <option value="dotted">Dotted</option>
                        <option value="double">Double</option>
                    </select>
                </div>
                
                <div class="toolbar-group">
                    <label>Tools:</label>
                    <button id="undo-btn" class="btn-tool" title="Undo">↶</button>
                    <button id="redo-btn" class="btn-tool" title="Redo">↷</button>
                    <button id="align-left-btn" class="btn-tool" title="Align Left">⬅️</button>
                    <button id="align-center-btn" class="btn-tool" title="Align Center">↔️</button>
                    <button id="align-right-btn" class="btn-tool" title="Align Right">➡️</button>
                    <button id="auto-layout-btn" class="btn-tool" title="Auto Layout">📐</button>
                </div>
            </div>
        </div>
        
        <div class="editor-main-content">
            <div class="canvas-panel">
                <div id="d3-container"></div>
            </div>
            
            <div class="control-panel">
                <div id="style-panel"></div>
                <div id="layout-tools"></div>
                <div id="theme-selector"></div>
            </div>
        </div>
        
        <div class="editor-status-bar">
            <span id="node-count">Nodes: 0</span>
            <span id="edit-mode">Edit Mode: Active</span>
        </div>
    </div>
</body>
</html>
```

**Deliverables:**
- [ ] Professional diagram selection gallery
- [ ] Visual previews for all diagram types
- [ ] Clean, modern UI design
- [ ] Responsive layout for all devices
- [ ] Integration with AI generator option

#### **4.5 Create Professional Toolbar CSS** (1 day)
**New Files:**
- `static/css/editor-toolbar.css`

**Features:**
- Professional toolbar styling with organized sections
- Color pickers, dropdowns, and tool buttons
- Responsive design that works on all screen sizes
- Hover effects and active states
- Professional typography and spacing

**Implementation:**
```css
/* Professional Toolbar Styling */
.editor-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 12px 20px;
    border-bottom: 2px solid #e0e0e0;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    min-height: 60px;
    flex-wrap: wrap;
    gap: 15px;
}

.toolbar-section {
    display: flex;
    align-items: center;
    gap: 15px;
    flex-wrap: wrap;
}

.toolbar-left {
    flex: 0 0 auto;
}

.toolbar-center {
    flex: 1;
    justify-content: center;
    min-width: 400px;
}

.toolbar-right {
    flex: 0 0 auto;
}

.toolbar-group {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255,255,255,0.1);
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.2);
}

.toolbar-group label {
    color: white;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-right: 5px;
    white-space: nowrap;
}

/* Button Styles */
.btn-tool {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.3);
    color: white;
    padding: 6px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s ease;
    min-width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-tool:hover {
    background: rgba(255,255,255,0.3);
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}

.btn-tool:active {
    transform: translateY(0);
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.btn-tool.active {
    background: rgba(255,255,255,0.4);
    border-color: rgba(255,255,255,0.6);
}

/* Select Dropdowns */
.tool-select {
    background: rgba(255,255,255,0.9);
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
    color: #333;
    cursor: pointer;
    min-width: 80px;
    height: 32px;
}

.tool-select:hover {
    border-color: #999;
}

.tool-select:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
}

/* Color Pickers */
.color-picker {
    width: 32px;
    height: 32px;
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 6px;
    cursor: pointer;
    background: none;
    padding: 0;
}

.color-picker:hover {
    border-color: rgba(255,255,255,0.6);
    transform: scale(1.1);
}

.color-picker::-webkit-color-swatch-wrapper {
    padding: 0;
    border-radius: 4px;
    overflow: hidden;
}

.color-picker::-webkit-color-swatch {
    border: none;
    border-radius: 4px;
}

/* Primary Buttons */
.btn-primary {
    background: #4CAF50;
    border: none;
    color: white;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
}

.btn-primary:hover {
    background: #45a049;
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(76, 175, 80, 0.3);
}

.btn-secondary {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.3);
    color: white;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s ease;
}

.btn-secondary:hover {
    background: rgba(255,255,255,0.3);
    border-color: rgba(255,255,255,0.5);
}

.btn-success {
    background: #2196F3;
    border: none;
    color: white;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s ease;
}

.btn-success:hover {
    background: #1976D2;
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(33, 150, 243, 0.3);
}

/* Responsive Design */
@media (max-width: 1200px) {
    .toolbar-center {
        min-width: 300px;
    }
    
    .toolbar-group {
        padding: 6px 8px;
    }
    
    .toolbar-group label {
        font-size: 10px;
    }
}

@media (max-width: 768px) {
    .editor-toolbar {
        flex-direction: column;
        gap: 10px;
        padding: 10px;
    }
    
    .toolbar-section {
        width: 100%;
        justify-content: center;
    }
    
    .toolbar-center {
        min-width: auto;
    }
    
    .toolbar-group {
        flex-wrap: wrap;
        justify-content: center;
    }
}

/* Tooltip Styles */
[title] {
    position: relative;
}

[title]:hover::after {
    content: attr(title);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.8);
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    white-space: nowrap;
    z-index: 1000;
    margin-bottom: 5px;
}

/* Active States for Selected Elements */
.toolbar-group.active {
    background: rgba(255,255,255,0.2);
    border-color: rgba(255,255,255,0.4);
}

/* Animation for toolbar interactions */
@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
}

.btn-tool:active {
    animation: pulse 0.2s ease;
}
```

**Deliverables:**
- [ ] Professional toolbar styling
- [ ] Organized sections (left, center, right)
- [ ] Color pickers and dropdown controls
- [ ] Responsive design for all screen sizes
- [ ] Hover effects and active states
- [ ] Professional typography and spacing

#### **4.4 Implement Diagram Selection Logic** (1 day)
**New Files:**
- `static/js/editor/diagram-selector.js`
- `static/js/editor/template-manager.js`

**Features:**
- Click handler for diagram type selection
- Template loading system for each diagram type
- Transition to editing interface
- Blank template generation for each diagram type

**Implementation:**
```javascript
class DiagramSelector {
    constructor() {
        this.diagramTypes = {
            'mindmap': {
                name: 'Mind Map',
                template: this.getMindMapTemplate(),
                description: 'Central topic with radiating branches'
            },
            'bubble_map': {
                name: 'Bubble Map',
                template: this.getBubbleMapTemplate(),
                description: 'Central topic with descriptive attributes'
            },
            'double_bubble_map': {
                name: 'Double Bubble Map',
                template: this.getDoubleBubbleMapTemplate(),
                description: 'Compare and contrast two topics'
            },
            'concept_map': {
                name: 'Concept Map',
                template: this.getConceptMapTemplate(),
                description: 'Complex relationships between concepts'
            },
            'flow_map': {
                name: 'Flow Map',
                template: this.getFlowMapTemplate(),
                description: 'Sequential process or workflow'
            },
            'tree_map': {
                name: 'Tree Map',
                template: this.getTreeMapTemplate(),
                description: 'Hierarchical data visualization'
            },
            'brace_map': {
                name: 'Brace Map',
                template: this.getBraceMapTemplate(),
                description: 'Whole-part relationships'
            }
        };
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        document.querySelectorAll('.select-diagram-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const diagramCard = e.target.closest('.diagram-card');
                const diagramType = diagramCard.dataset.type;
                this.selectDiagram(diagramType);
            });
        });
        
        document.getElementById('ai-generate-btn').addEventListener('click', () => {
            this.openAIGenerator();
        });
    }
    
    selectDiagram(diagramType) {
        const diagramConfig = this.diagramTypes[diagramType];
        if (diagramConfig) {
            // Transition to editing interface
            this.transitionToEditor(diagramType, diagramConfig.template);
        }
    }
    
    transitionToEditor(diagramType, template) {
        // Hide landing page
        document.querySelector('.editor-landing').style.display = 'none';
        
        // Show editor interface
        document.querySelector('.editor-interface').style.display = 'block';
        
        // Initialize editor with selected diagram type
        const editor = new InteractiveEditor(diagramType, template);
        editor.initialize();
    }
    
    getMindMapTemplate() {
        return {
            topic: 'Central Topic',
            children: [
                { text: 'Branch 1', children: [] },
                { text: 'Branch 2', children: [] },
                { text: 'Branch 3', children: [] }
            ]
        };
    }
    
    getBubbleMapTemplate() {
        return {
            topic: 'Main Topic',
            attributes: [
                'Attribute 1',
                'Attribute 2',
                'Attribute 3',
                'Attribute 4'
            ]
        };
    }
    
    getDoubleBubbleMapTemplate() {
        return {
            left: 'Topic A',
            right: 'Topic B',
            similarities: ['Similarity 1', 'Similarity 2'],
            left_differences: ['Difference A1', 'Difference A2'],
            right_differences: ['Difference B1', 'Difference B2']
        };
    }
    
    getConceptMapTemplate() {
        return {
            topic: 'Main Concept',
            concepts: ['Concept 1', 'Concept 2', 'Concept 3'],
            relationships: [
                { from: 'Main Concept', to: 'Concept 1', label: 'relates to' },
                { from: 'Main Concept', to: 'Concept 2', label: 'includes' },
                { from: 'Concept 1', to: 'Concept 3', label: 'leads to' }
            ]
        };
    }
    
    getFlowMapTemplate() {
        return {
            title: 'Process Flow',
            steps: [
                'Step 1',
                'Step 2',
                'Step 3',
                'Step 4'
            ]
        };
    }
    
    getTreeMapTemplate() {
        return {
            root: 'Root Topic',
            children: [
                { text: 'Category 1', children: ['Item 1', 'Item 2'] },
                { text: 'Category 2', children: ['Item 3', 'Item 4'] }
            ]
        };
    }
    
    getBraceMapTemplate() {
        return {
            topic: 'Main Topic',
            parts: [
                'Part 1',
                'Part 2',
                'Part 3'
            ]
        };
    }
    
    openAIGenerator() {
        // Redirect to current debug interface for AI generation
        window.location.href = '/debug';
    }
}
```

**Deliverables:**
- [ ] Diagram selection logic
- [ ] Template system for all diagram types
- [ ] Transition to editing interface
- [ ] Integration with AI generator
- [ ] Blank template generation for each diagram type

#### **4.6 Implement Toolbar Functionality** (1 day)
**New Files:**
- `static/js/editor/toolbar-manager.js`

**Features:**
- Complete toolbar functionality for all controls
- Node management (add, delete, duplicate)
- Text formatting (font, size, bold, italic)
- Color management (fill, text, border)
- Border styling (width, style)
- Layout tools (align, auto-layout)
- Undo/redo functionality

**Implementation:**
```javascript
class ToolbarManager {
    constructor(editor) {
        this.editor = editor;
        this.selectedNodes = new Set();
        this.history = [];
        this.historyIndex = -1;
        
        this.initializeEventListeners();
        this.updateToolbarState();
    }
    
    initializeEventListeners() {
        // Node Management
        document.getElementById('add-node-btn').addEventListener('click', () => {
            this.addNode();
        });
        
        document.getElementById('delete-node-btn').addEventListener('click', () => {
            this.deleteSelectedNodes();
        });
        
        document.getElementById('duplicate-node-btn').addEventListener('click', () => {
            this.duplicateSelectedNodes();
        });
        
        // Text Formatting
        document.getElementById('font-family').addEventListener('change', (e) => {
            this.updateSelectedNodes('fontFamily', e.target.value);
        });
        
        document.getElementById('font-size').addEventListener('change', (e) => {
            this.updateSelectedNodes('fontSize', parseInt(e.target.value));
        });
        
        document.getElementById('bold-btn').addEventListener('click', () => {
            this.toggleTextStyle('fontWeight', 'bold', 'normal');
        });
        
        document.getElementById('italic-btn').addEventListener('click', () => {
            this.toggleTextStyle('fontStyle', 'italic', 'normal');
        });
        
        // Color Management
        document.getElementById('fill-color').addEventListener('change', (e) => {
            this.updateSelectedNodes('fillColor', e.target.value);
        });
        
        document.getElementById('text-color').addEventListener('change', (e) => {
            this.updateSelectedNodes('textColor', e.target.value);
        });
        
        document.getElementById('border-color').addEventListener('change', (e) => {
            this.updateSelectedNodes('borderColor', e.target.value);
        });
        
        // Border Styling
        document.getElementById('border-width').addEventListener('change', (e) => {
            this.updateSelectedNodes('borderWidth', parseInt(e.target.value));
        });
        
        document.getElementById('border-style').addEventListener('change', (e) => {
            this.updateSelectedNodes('borderStyle', e.target.value);
        });
        
        // Layout Tools
        document.getElementById('align-left-btn').addEventListener('click', () => {
            this.alignNodes('left');
        });
        
        document.getElementById('align-center-btn').addEventListener('click', () => {
            this.alignNodes('center');
        });
        
        document.getElementById('align-right-btn').addEventListener('click', () => {
            this.alignNodes('right');
        });
        
        document.getElementById('auto-layout-btn').addEventListener('click', () => {
            this.autoLayout();
        });
        
        // Undo/Redo
        document.getElementById('undo-btn').addEventListener('click', () => {
            this.undo();
        });
        
        document.getElementById('redo-btn').addEventListener('click', () => {
            this.redo();
        });
        
        // File Operations
        document.getElementById('save-btn').addEventListener('click', () => {
            this.saveDiagram();
        });
        
        document.getElementById('load-btn').addEventListener('click', () => {
            this.loadDiagram();
        });
        
        document.getElementById('export-btn').addEventListener('click', () => {
            this.exportDiagram();
        });
        
        document.getElementById('back-to-gallery').addEventListener('click', () => {
            this.backToGallery();
        });
    }
    
    addNode() {
        const newNode = {
            id: this.generateNodeId(),
            text: 'New Node',
            x: 100,
            y: 100,
            style: {
                fillColor: '#1976d2',
                textColor: '#ffffff',
                borderColor: '#000000',
                borderWidth: 2,
                borderStyle: 'solid',
                fontFamily: 'Inter',
                fontSize: 14,
                fontWeight: 'normal',
                fontStyle: 'normal'
            }
        };
        
        this.saveToHistory('add_node', null, newNode);
        this.editor.addNode(newNode);
        this.updateToolbarState();
    }
    
    deleteSelectedNodes() {
        if (this.selectedNodes.size === 0) return;
        
        const nodesToDelete = Array.from(this.selectedNodes);
        this.saveToHistory('delete_nodes', nodesToDelete, null);
        
        nodesToDelete.forEach(nodeId => {
            this.editor.deleteNode(nodeId);
            this.selectedNodes.delete(nodeId);
        });
        
        this.updateToolbarState();
    }
    
    duplicateSelectedNodes() {
        if (this.selectedNodes.size === 0) return;
        
        const nodesToDuplicate = Array.from(this.selectedNodes);
        const duplicatedNodes = [];
        
        nodesToDuplicate.forEach(nodeId => {
            const originalNode = this.editor.getNode(nodeId);
            const duplicatedNode = {
                ...originalNode,
                id: this.generateNodeId(),
                x: originalNode.x + 50,
                y: originalNode.y + 50
            };
            duplicatedNodes.push(duplicatedNode);
        });
        
        this.saveToHistory('duplicate_nodes', null, duplicatedNodes);
        duplicatedNodes.forEach(node => this.editor.addNode(node));
        this.updateToolbarState();
    }
    
    updateSelectedNodes(property, value) {
        if (this.selectedNodes.size === 0) return;
        
        const updates = [];
        this.selectedNodes.forEach(nodeId => {
            const node = this.editor.getNode(nodeId);
            const oldValue = node.style[property];
            node.style[property] = value;
            updates.push({ nodeId, property, oldValue, newValue: value });
        });
        
        this.saveToHistory('update_style', updates, null);
        this.editor.refreshRenderer();
        this.updateToolbarState();
    }
    
    toggleTextStyle(property, activeValue, inactiveValue) {
        if (this.selectedNodes.size === 0) return;
        
        const updates = [];
        let newValue = inactiveValue;
        
        // Check if any selected node has the active value
        for (const nodeId of this.selectedNodes) {
            const node = this.editor.getNode(nodeId);
            if (node.style[property] === activeValue) {
                newValue = inactiveValue;
                break;
            } else {
                newValue = activeValue;
            }
        }
        
        this.selectedNodes.forEach(nodeId => {
            const node = this.editor.getNode(nodeId);
            const oldValue = node.style[property];
            node.style[property] = newValue;
            updates.push({ nodeId, property, oldValue, newValue });
        });
        
        this.saveToHistory('toggle_style', updates, null);
        this.editor.refreshRenderer();
        this.updateToolbarState();
    }
    
    alignNodes(direction) {
        if (this.selectedNodes.size < 2) return;
        
        const nodes = Array.from(this.selectedNodes).map(id => this.editor.getNode(id));
        const positions = this.calculateAlignment(nodes, direction);
        
        const updates = [];
        positions.forEach((pos, index) => {
            const nodeId = Array.from(this.selectedNodes)[index];
            const node = this.editor.getNode(nodeId);
            updates.push({ 
                nodeId, 
                property: 'position', 
                oldValue: { x: node.x, y: node.y }, 
                newValue: pos 
            });
            node.x = pos.x;
            node.y = pos.y;
        });
        
        this.saveToHistory('align_nodes', updates, null);
        this.editor.refreshRenderer();
    }
    
    calculateAlignment(nodes, direction) {
        if (direction === 'left') {
            const minX = Math.min(...nodes.map(n => n.x));
            return nodes.map(n => ({ x: minX, y: n.y }));
        } else if (direction === 'right') {
            const maxX = Math.max(...nodes.map(n => n.x));
            return nodes.map(n => ({ x: maxX, y: n.y }));
        } else if (direction === 'center') {
            const avgX = nodes.reduce((sum, n) => sum + n.x, 0) / nodes.length;
            return nodes.map(n => ({ x: avgX, y: n.y }));
        }
        return nodes.map(n => ({ x: n.x, y: n.y }));
    }
    
    autoLayout() {
        this.saveToHistory('auto_layout', this.editor.getCurrentLayout(), null);
        this.editor.autoLayout();
        this.updateToolbarState();
    }
    
    saveToHistory(action, oldState, newState) {
        // Remove any history after current index
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Add new history entry
        this.history.push({
            action,
            oldState: JSON.parse(JSON.stringify(oldState)),
            newState: JSON.parse(JSON.stringify(newState)),
            timestamp: Date.now()
        });
        
        this.historyIndex = this.history.length - 1;
        
        // Limit history size
        if (this.history.length > 50) {
            this.history.shift();
            this.historyIndex--;
        }
        
        this.updateToolbarState();
    }
    
    undo() {
        if (this.canUndo()) {
            const historyEntry = this.history[this.historyIndex];
            this.applyHistoryEntry(historyEntry, true);
            this.historyIndex--;
            this.updateToolbarState();
        }
    }
    
    redo() {
        if (this.canRedo()) {
            this.historyIndex++;
            const historyEntry = this.history[this.historyIndex];
            this.applyHistoryEntry(historyEntry, false);
            this.updateToolbarState();
        }
    }
    
    applyHistoryEntry(entry, isUndo) {
        const state = isUndo ? entry.oldState : entry.newState;
        
        switch (entry.action) {
            case 'add_node':
                if (isUndo) {
                    this.editor.deleteNode(state.id);
                } else {
                    this.editor.addNode(state);
                }
                break;
            case 'delete_nodes':
                if (isUndo) {
                    state.forEach(node => this.editor.addNode(node));
                } else {
                    state.forEach(node => this.editor.deleteNode(node.id));
                }
                break;
            case 'update_style':
            case 'toggle_style':
                state.forEach(update => {
                    const node = this.editor.getNode(update.nodeId);
                    if (update.property === 'position') {
                        node.x = update.newValue.x;
                        node.y = update.newValue.y;
                    } else {
                        node.style[update.property] = update.newValue;
                    }
                });
                this.editor.refreshRenderer();
                break;
            case 'auto_layout':
                if (isUndo) {
                    this.editor.applyLayout(state);
                } else {
                    this.editor.autoLayout();
                }
                break;
        }
    }
    
    canUndo() {
        return this.historyIndex >= 0;
    }
    
    canRedo() {
        return this.historyIndex < this.history.length - 1;
    }
    
    updateToolbarState() {
        // Update button states based on current selection and history
        const hasSelection = this.selectedNodes.size > 0;
        const hasMultipleSelection = this.selectedNodes.size > 1;
        
        // Enable/disable buttons
        document.getElementById('delete-node-btn').disabled = !hasSelection;
        document.getElementById('duplicate-node-btn').disabled = !hasSelection;
        document.getElementById('align-left-btn').disabled = !hasMultipleSelection;
        document.getElementById('align-center-btn').disabled = !hasMultipleSelection;
        document.getElementById('align-right-btn').disabled = !hasMultipleSelection;
        
        // Undo/Redo buttons
        document.getElementById('undo-btn').disabled = !this.canUndo();
        document.getElementById('redo-btn').disabled = !this.canRedo();
        
        // Update style controls based on selected nodes
        if (hasSelection) {
            this.updateStyleControls();
        }
    }
    
    updateStyleControls() {
        const firstNode = this.editor.getNode(Array.from(this.selectedNodes)[0]);
        const style = firstNode.style;
        
        // Update color pickers
        document.getElementById('fill-color').value = style.fillColor;
        document.getElementById('text-color').value = style.textColor;
        document.getElementById('border-color').value = style.borderColor;
        
        // Update dropdowns
        document.getElementById('font-family').value = style.fontFamily;
        document.getElementById('font-size').value = style.fontSize;
        document.getElementById('border-width').value = style.borderWidth;
        document.getElementById('border-style').value = style.borderStyle;
        
        // Update text style buttons
        document.getElementById('bold-btn').classList.toggle('active', style.fontWeight === 'bold');
        document.getElementById('italic-btn').classList.toggle('active', style.fontStyle === 'italic');
    }
    
    generateNodeId() {
        return 'node_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    selectNode(nodeId) {
        this.selectedNodes.add(nodeId);
        this.updateToolbarState();
    }
    
    deselectNode(nodeId) {
        this.selectedNodes.delete(nodeId);
        this.updateToolbarState();
    }
    
    clearSelection() {
        this.selectedNodes.clear();
        this.updateToolbarState();
    }
    
    saveDiagram() {
        const diagramData = this.editor.getCurrentDiagramData();
        // Implementation for saving diagram
        console.log('Saving diagram:', diagramData);
    }
    
    loadDiagram() {
        // Implementation for loading diagram
        console.log('Loading diagram');
    }
    
    exportDiagram() {
        const diagramData = this.editor.getCurrentDiagramData();
        // Implementation for exporting diagram
        console.log('Exporting diagram:', diagramData);
    }
    
    backToGallery() {
        // Hide editor interface and show gallery
        document.querySelector('.editor-interface').style.display = 'none';
        document.querySelector('.editor-landing').style.display = 'block';
    }
}
```

**Deliverables:**
- [ ] Complete toolbar functionality
- [ ] Node management (add, delete, duplicate)
- [ ] Text formatting controls
- [ ] Color and border styling
- [ ] Layout and alignment tools
- [ ] Undo/redo system
- [ ] File operations (save, load, export)

---

## 📋 **PHASE 3: ADVANCED FEATURES** (Weeks 5-6)

### **Week 5: Mobile and Touch Support**

#### **5.1 Implement Touch Interface** (2 days)
**New Files:**
- `static/js/editor/touch-manager.js`
- `static/css/mobile-editor.css`

**Features:**
- Touch gestures for pan, zoom, select
- Mobile-optimized toolbar
- Touch-friendly node editing
- Responsive design for tablets and phones

#### **5.2 Keyboard Shortcuts System** (2 days)
**New Files:**
- `static/js/editor/keyboard-manager.js`

**Features:**
- Standard shortcuts (Ctrl+C, Ctrl+V, Delete, Arrow keys)
- Custom shortcuts for diagram operations
- Shortcut customization and help display
- Accessibility keyboard navigation

#### **5.3 Grid and Snap System** (1 day)
**New Files:**
- `static/js/editor/grid-manager.js`

**Features:**
- Optional grid overlay for precise positioning
- Snap-to-grid toggle and grid size controls
- Snap-to-object functionality
- Visual grid customization

### **Week 6: Performance and Optimization**

#### **6.1 Performance Optimization** (2 days)
**New Files:**
- `static/js/editor/optimization-manager.js`

**Features:**
- Rendering optimization for large diagrams
- Memory management for long editing sessions
- Lazy loading for complex diagrams
- Virtual scrolling for large node sets

#### **6.2 Error Handling and Validation** (2 days)
**New Files:**
- `static/js/editor/error-manager.js`
- `static/js/validation/validator.js`

**Features:**
- Input validation for all user operations
- Error recovery mechanisms
- User-friendly error messages
- Comprehensive error logging

#### **6.3 Testing and Quality Assurance** (1 day)
**New Files:**
- `test/test_interactive_editor.py`
- `static/js/tests/editor-tests.js`

**Features:**
- Unit tests for all editor components
- Integration testing between components
- Performance benchmarking
- Cross-browser compatibility testing

---

## 📋 **PHASE 4: POLISH AND DEPLOYMENT** (Weeks 7-8)

### **Week 7: User Experience and Help System**

#### **7.1 Comprehensive Help System** (2 days)
**New Files:**
- `static/js/help/help-system.js`
- `static/js/help/tutorial-manager.js`

**Features:**
- Interactive tutorial for new users
- Help tooltips for all features
- Keyboard shortcuts reference
- Video tutorials integration
- FAQ section

#### **7.2 Accessibility Features** (2 days)
**New Files:**
- `static/js/accessibility/accessibility-manager.js`

**Features:**
- ARIA labels for screen readers
- Keyboard accessibility
- Color contrast validation
- High contrast mode
- Voice navigation support

#### **7.3 User Documentation** (1 day)
**New Files:**
- `docs/INTERACTIVE_EDITOR_USER_GUIDE.md`
- `docs/KEYBOARD_SHORTCUTS.md`

**Features:**
- Complete user documentation
- Step-by-step tutorials
- Troubleshooting guide
- Best practices documentation

### **Week 8: Final Integration and Deployment**

#### **8.1 Final Integration Testing** (2 days)
**Tasks:**
- End-to-end testing of all features
- Performance benchmarking
- Cross-browser compatibility testing
- User acceptance testing
- Load testing for concurrent users

#### **8.2 Production Deployment** (2 days)
**Tasks:**
- Production environment setup
- Database migration (if needed)
- CDN configuration for assets
- Monitoring and logging setup
- Backup and recovery procedures

#### **8.3 User Training and Support** (1 day)
**Tasks:**
- User training materials
- Support documentation
- Feedback collection system
- Performance monitoring dashboard

---

## 🚨 **UPDATED RISK ASSESSMENT**

### **Technical Risks**
1. **Performance Impact**: Real-time editing may impact performance for large diagrams
2. **Browser Compatibility**: Advanced features may not work on all browsers
3. **Complexity Overrun**: Interactive system is more complex than estimated
4. **Memory Management**: Long editing sessions may cause memory issues
5. **Touch Interface**: Mobile support adds significant complexity

### **Mitigation Strategies**
1. **Performance Monitoring**: Continuous benchmarking and optimization
2. **Progressive Enhancement**: Core features work on all browsers
3. **Incremental Development**: Build and test each feature independently
4. **Memory Optimization**: Implement cleanup and garbage collection
5. **Fallback Options**: Maintain current prompt-based system as fallback

### **Updated Timeline Risks**
- **Original**: 6 weeks - Too aggressive for complete implementation
- **Updated**: 8 weeks - More realistic for professional-quality system
- **Buffer**: 2 additional weeks available for unexpected issues

---

## 📊 **UPDATED SUCCESS METRICS**

### **Phase 1 Success Criteria**
- [ ] Interactive renderers for all diagram types
- [ ] Main editor controller functional
- [ ] Node selection system working
- [ ] Basic drag-and-drop operational

### **Phase 2 Success Criteria**
- [ ] Canvas management and zoom working
- [ ] Connection editing system functional
- [ ] Copy/paste system operational
- [ ] Professional toolbar complete

### **Phase 3 Success Criteria**
- [ ] Mobile and touch support working
- [ ] Keyboard shortcuts functional
- [ ] Grid and snap system operational
- [ ] Performance optimization complete

### **Phase 4 Success Criteria**
- [ ] Help system and tutorials complete
- [ ] Accessibility compliance achieved
- [ ] User documentation complete
- [ ] Production deployment successful

### **Overall Success Metrics**
- **Performance**: No more than 15% performance impact vs current system
- **Usability**: New users can edit diagrams within 3 minutes
- **Reliability**: 99.9% uptime with comprehensive error handling
- **Accessibility**: WCAG 2.1 AA compliance achieved
- **Mobile**: Full functionality on tablets and phones
- **Browser**: Support for Chrome, Firefox, Safari, Edge (last 2 versions)
- All renderer files
- `static/js/editors/context-menu.js` (new)

**Features:**
- Right-click context menus
- Keyboard navigation (Tab, Arrow keys)
- Multi-select with drag selection box
- Copy/paste nodes
- Delete nodes with confirmation

**Implementation:**
```javascript
class ContextMenu {
    constructor() {
        this.menu = null;
        this.currentNode = null;
    }
    
    show(event, nodeData) {
        this.currentNode = nodeData;
        this.createMenu(event.pageX, event.pageY);
    }
    
    createMenu(x, y) {
        const menu = d3.select('body')
            .append('div')
            .attr('class', 'context-menu')
            .style('position', 'absolute')
            .style('left', x + 'px')
            .style('top', y + 'px');
            
        menu.append('div')
            .text('Edit Text')
            .on('click', () => this.editText());
            
        menu.append('div')
            .text('Change Color')
            .on('click', () => this.changeColor());
            
        menu.append('div')
            .text('Delete Node')
            .on('click', () => this.deleteNode());
    }
}
```

**Deliverables:**
- [ ] Context menus for all node types
- [ ] Keyboard navigation
- [ ] Multi-select functionality
- [ ] Copy/paste/delete operations

#### **5.2 Performance Optimization** (2 days)
**Files to Modify:**
- All renderer files
- `static/js/performance/optimization-manager.js` (new)

**Optimizations:**
- Debounced style updates
- Virtual scrolling for large diagrams
- Efficient re-rendering on changes
- Memory management for undo/redo

**Implementation:**
```javascript
class OptimizationManager {
    constructor() {
        this.updateQueue = [];
        this.updateTimeout = null;
        this.batchSize = 10;
    }
    
    queueUpdate(updateFunction) {
        this.updateQueue.push(updateFunction);
        
        if (!this.updateTimeout) {
            this.updateTimeout = setTimeout(() => {
                this.processUpdates();
            }, 16); // ~60fps
        }
    }
    
    processUpdates() {
        const updates = this.updateQueue.splice(0, this.batchSize);
        updates.forEach(update => update());
        
        if (this.updateQueue.length > 0) {
            this.updateTimeout = setTimeout(() => {
                this.processUpdates();
            }, 16);
        } else {
            this.updateTimeout = null;
        }
    }
}
```

**Deliverables:**
- [ ] Optimized rendering performance
- [ ] Efficient update batching
- [ ] Memory usage optimization
- [ ] Smooth 60fps interactions

#### **5.3 Accessibility and Validation** (1 day)
**Files to Modify:**
- All renderer files
- `static/js/validation/validator.js` (new)

**Features:**
- ARIA labels for screen readers
- Keyboard accessibility
- Color contrast validation
- Text length validation
- Accessibility testing tools

**Implementation:**
```javascript
class AccessibilityManager {
    constructor() {
        this.contrastChecker = new ColorContrastChecker();
    }
    
    validateAccessibility(spec) {
        const issues = [];
        
        spec.nodes.forEach(node => {
            // Check color contrast
            const contrast = this.contrastChecker.checkContrast(
                node.style.textColor,
                node.style.backgroundColor
            );
            
            if (contrast < 4.5) {
                issues.push({
                    type: 'contrast',
                    nodeId: node.id,
                    message: 'Insufficient color contrast'
                });
            }
            
            // Check text length
            if (node.text.length > 50) {
                issues.push({
                    type: 'text_length',
                    nodeId: node.id,
                    message: 'Text too long for optimal readability'
                });
            }
        });
        
        return issues;
    }
}
```

**Deliverables:**
- [ ] ARIA accessibility support
- [ ] Keyboard navigation
- [ ] Color contrast validation
- [ ] Accessibility testing tools

### **Week 6: Testing and Documentation**

#### **6.1 Comprehensive Testing** (2 days)
**New Files:**
- `test/test_interactive_editor.py`
- `static/js/tests/editor-tests.js`

**Test Coverage:**
- Unit tests for all editor components
- Integration tests for save/load functionality
- Performance tests for large diagrams
- Cross-browser compatibility tests
- User interaction tests

**Implementation:**
```javascript
// Example test structure
describe('Interactive Editor', () => {
    describe('Node Editing', () => {
        it('should allow text editing on click', () => {
            // Test implementation
        });
        
        it('should validate text input', () => {
            // Test implementation
        });
    });
    
    describe('Style Management', () => {
        it('should apply color changes in real-time', () => {
            // Test implementation
        });
        
        it('should persist styles across sessions', () => {
            // Test implementation
        });
    });
});
```

**Deliverables:**
- [ ] Complete test suite
- [ ] Performance benchmarks
- [ ] Cross-browser testing
- [ ] User acceptance tests

#### **6.2 User Documentation and Help System** (2 days)
**New Files:**
- `docs/INTERACTIVE_EDITOR_USER_GUIDE.md`
- `static/js/help/help-system.js`

**Features:**
- Interactive tutorial for new users
- Help tooltips for all features
- Keyboard shortcuts reference
- Video tutorials (optional)
- FAQ section

**Implementation:**
```javascript
class HelpSystem {
    constructor() {
        this.tutorials = new Map();
        this.currentTutorial = null;
    }
    
    showTutorial(tutorialName) {
        const tutorial = this.tutorials.get(tutorialName);
        if (tutorial) {
            this.currentTutorial = new Tutorial(tutorial);
            this.currentTutorial.start();
        }
    }
    
    showTooltip(element, message) {
        const tooltip = d3.select('body')
            .append('div')
            .attr('class', 'help-tooltip')
            .text(message);
            
        // Position and show tooltip
    }
}
```

**Deliverables:**
- [ ] Complete user documentation
- [ ] Interactive tutorials
- [ ] Help system integration
- [ ] Keyboard shortcuts guide

#### **6.3 Final Integration and Deployment** (1 day)
**Tasks:**
- Final integration testing
- Performance optimization
- Production deployment preparation
- User training materials

**Deliverables:**
- [ ] Production-ready interactive editor
- [ ] Deployment documentation
- [ ] User training materials
- [ ] Performance benchmarks

---

## 🛠️ **TECHNICAL ARCHITECTURE**

### **File Structure Changes**
```
templates/
├── editor.html                # New professional editor landing page
└── debug.html                 # Keep existing debug interface unchanged

static/js/
├── editor/                    # New professional editor system
│   ├── diagram-gallery.js     # Diagram type selection interface
│   ├── diagram-selector.js    # Diagram selection logic
│   ├── template-manager.js    # Template generation system
│   ├── interactive-editor.js  # Main editor controller
│   ├── editors/               # Interactive editing components
│   │   ├── node-editor.js     # Node text editing
│   │   ├── selection-manager.js # Node selection system
│   │   ├── history-manager.js # Undo/redo functionality
│   │   └── context-menu.js    # Right-click menus
│   ├── widgets/               # UI components
│   │   ├── style-panel.js     # Style editing panel
│   │   ├── color-picker.js    # Color selection widget
│   │   ├── font-selector.js   # Font controls
│   │   └── layout-tools.js    # Layout manipulation tools
│   ├── tools/                 # Advanced tools
│   │   ├── layout-manager.js  # Auto-arrange and alignment
│   │   ├── theme-manager.js   # Theme application
│   │   └── optimization-manager.js # Performance optimization
│   ├── api/                   # API integration
│   │   ├── save-manager.js    # Save/load functionality
│   │   └── export-manager.js  # Enhanced export system
│   ├── validation/            # Validation and accessibility
│   │   ├── validator.js       # Input validation
│   │   └── accessibility-manager.js # Accessibility features
│   └── help/                  # Help system
│       ├── help-system.js     # Help and tutorials
│       └── tutorial-manager.js # Interactive tutorials
└── interactive/               # Interactive renderers (separate from current)
    └── renderers/             # Interactive versions of all renderers
        ├── interactive-mind-map-renderer.js
        ├── interactive-concept-map-renderer.js
        ├── interactive-bubble-map-renderer.js
        ├── interactive-flow-renderer.js
        ├── interactive-brace-renderer.js
        └── interactive-tree-renderer.js

static/css/
├── editor.css                 # New professional editor styling
└── editor-interface.css       # Editor interface specific styles
```

### **Backend API Extensions**
```python
# New endpoints in api_routes.py
@api.route('/save_diagram', methods=['POST'])
@api.route('/load_diagram/<diagram_id>', methods=['GET'])
@api.route('/list_diagrams', methods=['GET'])
@api.route('/export_custom', methods=['POST'])
@api.route('/validate_diagram', methods=['POST'])
```

### **Database Schema (Optional)**
```sql
-- For persistent storage
CREATE TABLE saved_diagrams (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    spec JSONB,
    styles JSONB,
    metadata JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## 📊 **SUCCESS METRICS**

### **Phase 1 Success Criteria**
- [ ] All node types are clickable and editable
- [ ] Basic drag-and-drop works smoothly
- [ ] Style changes apply in real-time
- [ ] No performance degradation from current system

### **Phase 2 Success Criteria**
- [ ] Complete undo/redo system functional
- [ ] Save/load system working reliably
- [ ] Export with custom styling successful
- [ ] Layout tools improve diagram organization

### **Phase 3 Success Criteria**
- [ ] Professional user experience
- [ ] Comprehensive help system
- [ ] Accessibility compliance
- [ ] Production-ready performance

### **Overall Success Metrics**
- **Performance**: No more than 10% performance impact vs current system
- **Usability**: New users can edit diagrams within 5 minutes
- **Reliability**: 99.9% uptime with no data loss
- **Accessibility**: WCAG 2.1 AA compliance

---

## 🚨 **RISK MITIGATION**

### **Technical Risks**
1. **Performance Impact**: Monitor rendering performance, implement optimizations
2. **Browser Compatibility**: Test across Chrome, Firefox, Safari, Edge
3. **Data Loss**: Implement robust save system with auto-backup
4. **Complexity**: Keep implementation simple, avoid over-engineering

### **Mitigation Strategies**
1. **Incremental Development**: Build and test each feature independently
2. **Performance Monitoring**: Continuous benchmarking during development
3. **User Testing**: Regular testing with real users throughout development
4. **Fallback Options**: Maintain current prompt-based system as fallback

---

## 🎯 **DELIVERABLES SUMMARY**

### **Week 1-2: Foundation**
- Interactive click handlers for all node types
- Basic node text editing
- Drag-and-drop positioning
- Style property panel
- Node selection system

### **Week 3-4: Advanced Features**
- Theme system integration
- Layout tools and auto-arrange
- Complete undo/redo system
- Save/load functionality
- Enhanced export system

### **Week 5-6: Polish**
- Advanced interactions (context menus, keyboard shortcuts)
- Performance optimization
- Accessibility features
- Comprehensive testing
- User documentation

### **Final Deliverable**
A professional, interactive diagram editor that:
- Maintains the quality and performance of the current system
- Provides intuitive editing capabilities for all diagram types
- Includes comprehensive save/load and export functionality
- Offers professional user experience with help system
- Is ready for production deployment

---

*This implementation plan builds on the existing MindGraph architecture to create a world-class interactive diagram editor while maintaining the proven performance and reliability of the current system.*
