/**
 * InteractiveEditor - Main controller for the interactive diagram editor
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class InteractiveEditor {
    constructor(diagramType, template) {
        this.diagramType = diagramType;
        this.currentSpec = template;
        this.selectedNodes = new Set();
        this.history = [];
        this.historyIndex = -1;
        
        // Initialize components
        this.selectionManager = new SelectionManager();
        this.canvasManager = new CanvasManager();
        this.toolbarManager = null; // Will be initialized after render
        this.renderer = null;
        
        // Bind selection change callback
        this.selectionManager.setSelectionChangeCallback((selectedNodes) => {
            this.selectedNodes = new Set(selectedNodes);
            this.updateToolbarState();
        });
    }
    
    /**
     * Initialize the editor
     */
    initialize() {
        console.log(`Initializing interactive editor for ${this.diagramType}`);
        
        // Setup canvas
        this.canvasManager.setupCanvas('#d3-container', {
            minHeight: '600px',
            backgroundColor: '#f5f5f5'
        });
        
        // Render initial diagram
        this.renderDiagram();
        
        // Setup global event handlers
        this.setupGlobalEventHandlers();
        
        // Initialize toolbar manager
        if (typeof ToolbarManager !== 'undefined') {
            this.toolbarManager = new ToolbarManager(this);
            console.log('Toolbar manager initialized');
        }
    }
    
    /**
     * Render the diagram
     */
    renderDiagram() {
        try {
            // Use the renderGraph dispatcher function to handle all diagram types
            const theme = null; // Use default theme
            const dimensions = this.currentSpec._recommended_dimensions || null;
            
            if (typeof renderGraph === 'function') {
                console.log(`Rendering ${this.diagramType} with template:`, this.currentSpec);
                renderGraph(this.diagramType, this.currentSpec, theme, dimensions);
            } else {
                console.error('renderGraph dispatcher function not found');
                throw new Error('Renderer not available');
            }
            
            // Add interaction handlers after rendering
            this.addInteractionHandlers();
            
        } catch (error) {
            console.error('Error rendering diagram:', error);
            throw error;
        }
    }
    
    /**
     * Add drag behavior to a node and its text
     */
    addDragBehavior(shapeElement, textElement) {
        const self = this;
        
        const drag = d3.drag()
            .on('start', function(event) {
                d3.select(this).style('opacity', 0.7);
            })
            .on('drag', function(event) {
                const shape = d3.select(this);
                const tagName = this.tagName.toLowerCase();
                
                // Update shape position based on type
                if (tagName === 'circle') {
                    shape.attr('cx', event.x).attr('cy', event.y);
                } else if (tagName === 'rect') {
                    const width = parseFloat(shape.attr('width')) || 0;
                    const height = parseFloat(shape.attr('height')) || 0;
                    shape.attr('x', event.x - width / 2).attr('y', event.y - height / 2);
                } else if (tagName === 'ellipse') {
                    shape.attr('cx', event.x).attr('cy', event.y);
                }
                
                // Update associated text position
                if (textElement) {
                    textElement.attr('x', event.x).attr('y', event.y);
                } else {
                    // Try to find and move associated text
                    const nextSibling = this.nextElementSibling;
                    if (nextSibling && nextSibling.tagName === 'text') {
                        d3.select(nextSibling).attr('x', event.x).attr('y', event.y);
                    }
                }
            })
            .on('end', function(event) {
                d3.select(this).style('opacity', 1);
                self.saveToHistory('move_node', { 
                    nodeId: d3.select(this).attr('data-node-id'),
                    x: event.x,
                    y: event.y
                });
            });
        
        shapeElement.call(drag);
    }
    
    /**
     * Add interaction handlers to rendered elements
     */
    addInteractionHandlers() {
        const self = this;
        
        // Find all node elements (shapes) and add click handlers
        d3.selectAll('circle, rect, ellipse').each((d, i, nodes) => {
            const element = d3.select(nodes[i]);
            const nodeId = element.attr('data-node-id') || `node_${i}`;
            
            // Add node ID attribute if not exists
            if (!element.attr('data-node-id')) {
                element.attr('data-node-id', nodeId);
            }
            
            // Find associated text
            const textNode = nodes[i].nextElementSibling;
            const textElement = (textNode && textNode.tagName === 'text') ? d3.select(textNode) : null;
            
            // Add drag behavior
            self.addDragBehavior(element, textElement);
            
            // Add click handler for selection
            element
                .style('cursor', 'move')
                .on('click', (event) => {
                    event.stopPropagation();
                    
                    if (event.ctrlKey || event.metaKey) {
                        self.selectionManager.toggleNodeSelection(nodeId);
                    } else {
                        self.selectionManager.clearSelection();
                        self.selectionManager.selectNode(nodeId);
                    }
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                    // Find associated text element
                    const textNode = element.node().nextElementSibling;
                    if (textNode && textNode.tagName === 'text') {
                        const currentText = d3.select(textNode).text();
                        self.openNodeEditor(nodeId, element.node(), textNode, currentText);
                    } else {
                        // Try to find text by position
                        const currentText = self.findTextForNode(element.node());
                        self.openNodeEditor(nodeId, element.node(), null, currentText);
                    }
                })
                .on('mouseover', function() {
                    d3.select(this).style('opacity', 0.8);
                })
                .on('mouseout', function() {
                    d3.select(this).style('opacity', 1);
                });
        });
        
        // Add text click handlers with better text extraction
        d3.selectAll('text').each((d, i, nodes) => {
            const element = d3.select(nodes[i]);
            const nodeId = `text_${i}`;
            const textNode = nodes[i];
            
            element
                .attr('data-text-id', nodeId)
                .style('cursor', 'pointer')
                .on('click', (event) => {
                    event.stopPropagation();
                    
                    if (event.ctrlKey || event.metaKey) {
                        this.selectionManager.toggleNodeSelection(nodeId);
                    } else {
                        this.selectionManager.clearSelection();
                        this.selectionManager.selectNode(nodeId);
                    }
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                    const currentText = element.text();
                    // Find associated shape element
                    const shapeNode = textNode.previousElementSibling;
                    this.openNodeEditor(nodeId, shapeNode, textNode, currentText);
                });
        });
    }
    
    /**
     * Find text associated with a shape node
     */
    findTextForNode(shapeNode) {
        // Try sibling
        const nextSibling = shapeNode.nextElementSibling;
        if (nextSibling && nextSibling.tagName === 'text') {
            return d3.select(nextSibling).text();
        }
        
        // Try by proximity (find closest text element)
        const shapeBBox = shapeNode.getBBox();
        const centerX = shapeBBox.x + shapeBBox.width / 2;
        const centerY = shapeBBox.y + shapeBBox.height / 2;
        
        let closestText = null;
        let minDistance = Infinity;
        
        d3.selectAll('text').each(function() {
            const textBBox = this.getBBox();
            const textX = textBBox.x + textBBox.width / 2;
            const textY = textBBox.y + textBBox.height / 2;
            const distance = Math.sqrt(Math.pow(centerX - textX, 2) + Math.pow(centerY - textY, 2));
            
            if (distance < minDistance) {
                minDistance = distance;
                closestText = this;
            }
        });
        
        return closestText ? d3.select(closestText).text() : 'Edit me';
    }
    
    /**
     * Setup global event handlers
     */
    setupGlobalEventHandlers() {
        // Click on canvas to deselect all
        d3.select('#d3-container').on('click', () => {
            this.selectionManager.clearSelection();
        });
        
        // Keyboard shortcuts
        d3.select('body').on('keydown', (event) => {
            this.handleKeyboardShortcut(event);
        });
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcut(event) {
        // Delete selected nodes
        if (event.key === 'Delete' || event.key === 'Backspace') {
            if (this.selectedNodes.size > 0) {
                event.preventDefault();
                this.deleteSelectedNodes();
            }
        }
        
        // Undo
        if (event.ctrlKey && event.key === 'z') {
            event.preventDefault();
            this.undo();
        }
        
        // Redo
        if (event.ctrlKey && event.key === 'y') {
            event.preventDefault();
            this.redo();
        }
        
        // Select all
        if (event.ctrlKey && event.key === 'a') {
            event.preventDefault();
            this.selectAll();
        }
    }
    
    /**
     * Open node editor
     */
    openNodeEditor(nodeId, shapeNode, textNode, currentText) {
        const editor = new NodeEditor(
            { id: nodeId, text: currentText || 'Edit me' },
            (newText) => {
                this.updateNodeText(nodeId, shapeNode, textNode, newText);
            },
            () => {
                // Cancel callback
            }
        );
        
        editor.show();
    }
    
    /**
     * Update node text
     */
    updateNodeText(nodeId, shapeNode, textNode, newText) {
        // Update the text element
        if (textNode) {
            // Direct text node provided
            d3.select(textNode).text(newText);
        } else if (shapeNode) {
            // Find text near the shape
            const nextSibling = shapeNode.nextElementSibling;
            if (nextSibling && nextSibling.tagName === 'text') {
                d3.select(nextSibling).text(newText);
            }
        } else {
            // Fallback: try to find by data attribute
            const textElement = d3.select(`[data-text-id="${nodeId}"]`);
            if (!textElement.empty()) {
                textElement.text(newText);
            } else {
                // Try by node-id
                const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
                if (!shapeElement.empty()) {
                    const node = shapeElement.node();
                    const nextSibling = node.nextElementSibling;
                    if (nextSibling && nextSibling.tagName === 'text') {
                        d3.select(nextSibling).text(newText);
                    }
                }
            }
        }
        
        // Save to history
        this.saveToHistory('update_text', { nodeId, newText });
    }
    
    /**
     * Add a new node to the diagram
     */
    addNode() {
        console.log(`Adding new node to ${this.diagramType}`);
        
        // Get SVG container dimensions for positioning
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            console.error('SVG container not found');
            return;
        }
        
        const svgNode = svg.node();
        const bbox = svgNode.getBBox();
        const width = parseFloat(svg.attr('width')) || 800;
        const height = parseFloat(svg.attr('height')) || 600;
        
        // Create new node in center of visible area
        const centerX = width / 2;
        const centerY = height / 2;
        
        // Add some randomness to avoid overlapping when adding multiple nodes
        const offsetX = (Math.random() - 0.5) * 100;
        const offsetY = (Math.random() - 0.5) * 100;
        
        const newX = centerX + offsetX;
        const newY = centerY + offsetY;
        
        // Create a group for the new node
        const g = svg.append('g')
            .attr('class', 'node-group');
        
        // Default node appearance
        const nodeRadius = 30;
        const nodeId = `node_${Date.now()}`;
        
        // Add circle (shape)
        const circle = g.append('circle')
            .attr('cx', newX)
            .attr('cy', newY)
            .attr('r', nodeRadius)
            .attr('fill', '#667eea')
            .attr('stroke', '#5568d3')
            .attr('stroke-width', 2)
            .attr('data-node-id', nodeId)
            .style('cursor', 'move');
        
        // Add text
        const text = g.append('text')
            .attr('x', newX)
            .attr('y', newY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', 'white')
            .attr('font-size', '14px')
            .attr('font-weight', '500')
            .attr('data-text-id', `text_${Date.now()}`)
            .style('cursor', 'move')
            .style('pointer-events', 'none')
            .text('New Node');
        
        // Add drag behavior
        this.addDragBehavior(circle, text);
        
        // Add interaction handlers to the new node
        this.addInteractionHandlers();
        
        // Select the new node
        this.selectionManager.clearSelection();
        this.selectionManager.selectNode(nodeId);
        
        // Save to history
        this.saveToHistory('add_node', { nodeId, x: newX, y: newY });
        
        console.log(`Node ${nodeId} added at (${newX.toFixed(0)}, ${newY.toFixed(0)})`);
    }
    
    /**
     * Delete selected nodes
     */
    deleteSelectedNodes() {
        if (this.selectedNodes.size === 0) {
            console.log('No nodes selected to delete');
            return;
        }
        
        const nodesToDelete = Array.from(this.selectedNodes);
        console.log(`Deleting ${nodesToDelete.length} node(s):`, nodesToDelete);
        
        // Remove both the shape and associated text for each node
        nodesToDelete.forEach(nodeId => {
            // Remove the shape element
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const shapeNode = shapeElement.node();
                
                // Remove associated text (next sibling)
                if (shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                    d3.select(shapeNode.nextElementSibling).remove();
                }
                
                // Remove the shape
                shapeElement.remove();
            }
            
            // Also try to remove by text-id (in case it's a text selection)
            d3.select(`[data-text-id="${nodeId}"]`).remove();
        });
        
        // Clear selection
        this.selectionManager.clearSelection();
        
        // Save to history
        this.saveToHistory('delete_nodes', { nodeIds: nodesToDelete });
        
        console.log(`Successfully deleted ${nodesToDelete.length} node(s)`);
    }
    
    /**
     * Select all nodes
     */
    selectAll() {
        d3.selectAll('[data-node-id]').each((d, i, nodes) => {
            const nodeId = d3.select(nodes[i]).attr('data-node-id');
            if (nodeId) {
                this.selectionManager.selectNode(nodeId);
            }
        });
    }
    
    /**
     * Save state to history
     */
    saveToHistory(action, state) {
        // Remove any history after current index
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Add new history entry
        this.history.push({
            action,
            state: JSON.parse(JSON.stringify(state)),
            timestamp: Date.now()
        });
        
        this.historyIndex = this.history.length - 1;
        
        // Limit history size
        if (this.history.length > 50) {
            this.history.shift();
            this.historyIndex--;
        }
    }
    
    /**
     * Undo last action
     */
    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            console.log('Undo:', this.history[this.historyIndex]);
            // Re-render diagram with previous state
            this.renderDiagram();
        }
    }
    
    /**
     * Redo last undone action
     */
    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            console.log('Redo:', this.history[this.historyIndex]);
            // Re-render diagram with next state
            this.renderDiagram();
        }
    }
    
    /**
     * Update toolbar state
     */
    updateToolbarState() {
        const hasSelection = this.selectedNodes.size > 0;
        
        // Dispatch custom event for toolbar to listen
        window.dispatchEvent(new CustomEvent('editor-selection-change', {
            detail: {
                selectedNodes: Array.from(this.selectedNodes),
                hasSelection: hasSelection
            }
        }));
    }
    
    /**
     * Get current diagram data
     */
    getCurrentDiagramData() {
        return {
            type: this.diagramType,
            spec: this.currentSpec,
            selectedNodes: Array.from(this.selectedNodes),
            timestamp: Date.now()
        };
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.InteractiveEditor = InteractiveEditor;
}

