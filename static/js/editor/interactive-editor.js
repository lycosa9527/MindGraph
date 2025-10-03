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
        
        // Enable debug logging
        this.debugMode = true;
        
        // Session info (will be set by DiagramSelector)
        this.sessionId = null;
        this.sessionDiagramType = null;
        
        // Initialize components
        this.selectionManager = new SelectionManager();
        this.canvasManager = new CanvasManager();
        this.toolbarManager = null; // Will be initialized after render
        this.renderer = null;
        
        // Log editor initialization
        this.log('InteractiveEditor: Created', { diagramType, templateKeys: Object.keys(template || {}) });
        
        // Bind selection change callback
        this.selectionManager.setSelectionChangeCallback((selectedNodes) => {
            this.selectedNodes = new Set(selectedNodes);
            this.log('InteractiveEditor: Selection changed', { count: selectedNodes.length, nodes: selectedNodes });
            this.updateToolbarState();
        });
    }
    
    /**
     * Centralized logging for debugging
     */
    log(message, data = null) {
        if (!this.debugMode) return;
        
        const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
        const sessionInfo = this.sessionId ? ` [Session: ${this.sessionId.substr(-8)}]` : '';
        const prefix = `[${timestamp}]${sessionInfo} [${this.diagramType}]`;
        
        if (data) {
            console.log(`${prefix} ${message}`, data);
        } else {
            console.log(`${prefix} ${message}`);
        }
    }
    
    /**
     * Validate that we're operating within the correct session
     */
    validateSession(operation = 'Operation') {
        if (!this.sessionId) {
            console.error(`${operation} blocked - No session ID set!`);
            return false;
        }
        
        if (this.diagramType !== this.sessionDiagramType) {
            console.error(`${operation} blocked - Diagram type mismatch!`);
            console.error('Editor diagram type:', this.diagramType);
            console.error('Session diagram type:', this.sessionDiagramType);
            console.error('Session ID:', this.sessionId);
            return false;
        }
        
        // Cross-check with DiagramSelector session
        if (window.diagramSelector?.currentSession) {
            if (window.diagramSelector.currentSession.id !== this.sessionId) {
                console.error(`${operation} blocked - Session ID mismatch!`);
                console.error('Editor session:', this.sessionId);
                console.error('DiagramSelector session:', window.diagramSelector.currentSession.id);
                return false;
            }
            
            if (window.diagramSelector.currentSession.diagramType !== this.diagramType) {
                console.error(`${operation} blocked - DiagramSelector session type mismatch!`);
                console.error('Editor type:', this.diagramType);
                console.error('Session type:', window.diagramSelector.currentSession.diagramType);
                return false;
            }
        }
        
        return true;
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
        this.log('InteractiveEditor: Starting diagram render', {
            specKeys: Object.keys(this.currentSpec || {})
        });
        
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
     * Only applies to concept maps - other diagram types have fixed layouts
     */
    addDragBehavior(shapeElement, textElement) {
        // Only allow dragging for concept maps
        if (this.diagramType !== 'concept_map') {
            // For non-concept maps, change cursor to default instead of move
            shapeElement.style('cursor', 'pointer');
            return;
        }
        
        const self = this;
        let startX, startY;
        let connectedLines = []; // Store which lines connect to this node
        
        const drag = d3.drag()
            .on('start', function(event) {
                const shape = d3.select(this);
                const parentNode = this.parentNode;
                const nodeId = shape.attr('data-node-id');
                
                // Store starting position
                if (parentNode && parentNode.tagName === 'g') {
                    // For grouped elements, get the group's transform
                    const transform = d3.select(parentNode).attr('transform') || 'translate(0,0)';
                    const matches = transform.match(/translate\(([^,]+),([^)]+)\)/);
                    if (matches) {
                        startX = parseFloat(matches[1]);
                        startY = parseFloat(matches[2]);
                    } else {
                        startX = 0;
                        startY = 0;
                    }
                } else {
                    // For individual elements
                    const tagName = this.tagName.toLowerCase();
                    if (tagName === 'circle') {
                        startX = parseFloat(shape.attr('cx'));
                        startY = parseFloat(shape.attr('cy'));
                    } else if (tagName === 'rect') {
                        const width = parseFloat(shape.attr('width')) || 0;
                        const height = parseFloat(shape.attr('height')) || 0;
                        startX = parseFloat(shape.attr('x')) + width / 2;
                        startY = parseFloat(shape.attr('y')) + height / 2;
                    } else if (tagName === 'ellipse') {
                        startX = parseFloat(shape.attr('cx'));
                        startY = parseFloat(shape.attr('cy'));
                    }
                }
                
                // Find all lines connected to this node (within tolerance)
                connectedLines = [];
                const tolerance = 10;
                d3.selectAll('line').each(function() {
                    const line = d3.select(this);
                    const x1 = parseFloat(line.attr('x1'));
                    const y1 = parseFloat(line.attr('y1'));
                    const x2 = parseFloat(line.attr('x2'));
                    const y2 = parseFloat(line.attr('y2'));
                    
                    const connectsAtStart = Math.abs(x1 - startX) < tolerance && Math.abs(y1 - startY) < tolerance;
                    const connectsAtEnd = Math.abs(x2 - startX) < tolerance && Math.abs(y2 - startY) < tolerance;
                    
                    if (connectsAtStart || connectsAtEnd) {
                        connectedLines.push({
                            line: line,
                            connectsAtStart: connectsAtStart,
                            connectsAtEnd: connectsAtEnd
                        });
                    }
                });
                
                shape.style('opacity', 0.7);
            })
            .on('drag', function(event) {
                const shape = d3.select(this);
                const tagName = this.tagName.toLowerCase();
                const parentNode = this.parentNode;
                
                // Calculate new position
                const newX = startX + event.dx;
                const newY = startY + event.dy;
                startX = newX;
                startY = newY;
                
                // Check if this element is inside a group (concept map style)
                if (parentNode && parentNode.tagName === 'g') {
                    // Move the entire group using transform
                    d3.select(parentNode).attr('transform', `translate(${newX}, ${newY})`);
                    
                    // Update all connected lines
                    connectedLines.forEach(conn => {
                        if (conn.connectsAtStart) {
                            conn.line.attr('x1', newX).attr('y1', newY);
                        }
                        if (conn.connectsAtEnd) {
                            conn.line.attr('x2', newX).attr('y2', newY);
                        }
                    });
                } else {
                    // Move individual elements (original behavior)
                    if (tagName === 'circle') {
                        shape.attr('cx', newX).attr('cy', newY);
                    } else if (tagName === 'rect') {
                        const width = parseFloat(shape.attr('width')) || 0;
                        const height = parseFloat(shape.attr('height')) || 0;
                        shape.attr('x', newX - width / 2).attr('y', newY - height / 2);
                    } else if (tagName === 'ellipse') {
                        shape.attr('cx', newX).attr('cy', newY);
                    }
                    
                    // Update associated text position
                    if (textElement) {
                        textElement.attr('x', newX).attr('y', newY);
                    } else {
                        // Try to find and move associated text
                        const nextSibling = this.nextElementSibling;
                        if (nextSibling && nextSibling.tagName === 'text') {
                            d3.select(nextSibling).attr('x', newX).attr('y', newY);
                        }
                    }
                }
            })
            .on('end', function(event) {
                d3.select(this).style('opacity', 1);
                connectedLines = []; // Clear references
                self.saveToHistory('move_node', { 
                    nodeId: d3.select(this).attr('data-node-id'),
                    x: startX,
                    y: startY
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
        // Filter out background elements and decorative elements
        d3.selectAll('circle, rect, ellipse').each((d, i, nodes) => {
            const element = d3.select(nodes[i]);
            
            // Skip background rectangles and other non-interactive elements
            const elemClass = element.attr('class') || '';
            if (elemClass.includes('background') || elemClass.includes('watermark')) {
                return; // Skip this element
            }
            
            const nodeId = element.attr('data-node-id') || `node_${i}`;
            
            // Add node ID attribute if not exists
            if (!element.attr('data-node-id')) {
            element.attr('data-node-id', nodeId);
            }
            
            // Find associated text
            const textNode = nodes[i].nextElementSibling;
            const textElement = (textNode && textNode.tagName === 'text') ? d3.select(textNode) : null;
            
            // Add drag behavior (cursor style is set inside addDragBehavior based on diagram type)
            self.addDragBehavior(element, textElement);
            
            // Add click handler for selection
            element
                .on('click', (event) => {
                    event.stopPropagation();
                    self.log('InteractiveEditor: Node clicked', { nodeId, ctrl: event.ctrlKey || event.metaKey });
                    
                    if (event.ctrlKey || event.metaKey) {
                        self.selectionManager.toggleNodeSelection(nodeId);
                    } else {
                        self.selectionManager.clearSelection();
                        self.selectionManager.selectNode(nodeId);
                    }
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                    self.log('InteractiveEditor: Node double-clicked for editing', { nodeId });
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
        
        // Add text click handlers - link to associated shape node
        d3.selectAll('text').each((d, i, nodes) => {
            const element = d3.select(nodes[i]);
            const textNode = nodes[i];
            
            // Skip watermark text
            const elemClass = element.attr('class') || '';
            if (elemClass.includes('watermark')) {
                return;
            }
            
            // Check if this is a standalone text element with its own node-id (e.g., flow map title)
            const ownNodeId = element.attr('data-node-id');
            const ownNodeType = element.attr('data-node-type');
            
            if (ownNodeId && ownNodeType) {
                // This is a standalone editable text element
                element
                    .style('cursor', 'pointer')
                    .style('pointer-events', 'all')
                    .on('click', (event) => {
                        event.stopPropagation();
                        
                        if (event.ctrlKey || event.metaKey) {
                            self.selectionManager.toggleNodeSelection(ownNodeId);
                        } else {
                            self.selectionManager.clearSelection();
                            self.selectionManager.selectNode(ownNodeId);
                        }
                    })
                    .on('dblclick', (event) => {
                        event.stopPropagation();
                        const currentText = element.text();
                        // For standalone text elements, the text element is both the shape and text
                        self.openNodeEditor(ownNodeId, textNode, textNode, currentText);
                    })
                    .on('mouseover', function() {
                        d3.select(this).style('opacity', 0.8);
                    })
                    .on('mouseout', function() {
                        d3.select(this).style('opacity', 1);
                    });
                return; // Skip the associated node logic below
            }
            
            // Find associated shape node ID
            let associatedNodeId = null;
            
            // Method 1: Check if text has data-text-for attribute (Circle/Bubble Map)
            const textFor = element.attr('data-text-for');
            if (textFor) {
                associatedNodeId = textFor;
            }
            // Method 2: Check previous sibling (common pattern)
            else if (textNode.previousElementSibling) {
                const prevElement = d3.select(textNode.previousElementSibling);
                associatedNodeId = prevElement.attr('data-node-id');
            }
            // Method 3: Check parent group (Concept Map)
            else if (textNode.parentNode && textNode.parentNode.tagName === 'g') {
                const groupElement = d3.select(textNode.parentNode);
                const shapeInGroup = groupElement.select('circle, rect, ellipse');
                if (!shapeInGroup.empty()) {
                    associatedNodeId = shapeInGroup.attr('data-node-id');
                }
            }
            
            // Only add handlers if we found an associated node
            if (associatedNodeId) {
            element
                .style('cursor', 'pointer')
                    .style('pointer-events', 'all')  // Enable pointer events on text
                .on('click', (event) => {
                    event.stopPropagation();
                    
                    if (event.ctrlKey || event.metaKey) {
                            self.selectionManager.toggleNodeSelection(associatedNodeId);
                    } else {
                            self.selectionManager.clearSelection();
                            self.selectionManager.selectNode(associatedNodeId);
                    }
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                        const currentText = element.text();
                        // Find associated shape element
                        const shapeElement = d3.select(`[data-node-id="${associatedNodeId}"]`);
                        if (!shapeElement.empty()) {
                            self.openNodeEditor(associatedNodeId, shapeElement.node(), textNode, currentText);
                        }
                    });
            }
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
        this.log('InteractiveEditor: Opening node editor', {
            nodeId,
            currentText: currentText?.substring(0, 50),
            textLength: currentText?.length || 0
        });
        
        const editor = new NodeEditor(
            { id: nodeId, text: currentText || 'Edit me' },
            (newText) => {
                this.log('InteractiveEditor: Node editor - Save callback triggered', {
                    nodeId,
                    newText: newText?.substring(0, 50)
                });
                this.updateNodeText(nodeId, shapeNode, textNode, newText);
            },
            () => {
                // Cancel callback
                this.log('InteractiveEditor: Node editor - Cancel callback triggered', { nodeId });
            }
        );
        
        editor.show();
    }
    
    /**
     * Update node text
     */
    updateNodeText(nodeId, shapeNode, textNode, newText) {
        this.log('InteractiveEditor: Updating node text', {
            nodeId,
            diagramType: this.diagramType,
            newText: newText?.substring(0, 50),
            textLength: newText?.length || 0
        });
        
        // Validate session
        if (!this.validateSession('Update node text')) {
            return;
        }
        
        // Handle diagram-specific text updates
        if (this.diagramType === 'circle_map') {
            this.updateCircleMapText(nodeId, shapeNode, newText);
        } else if (this.diagramType === 'bubble_map') {
            this.updateBubbleMapText(nodeId, shapeNode, newText);
        } else if (this.diagramType === 'double_bubble_map') {
            this.updateDoubleBubbleMapText(nodeId, shapeNode, newText);
        } else if (this.diagramType === 'brace_map') {
            this.updateBraceMapText(nodeId, shapeNode, newText);
        } else if (this.diagramType === 'flow_map') {
            this.updateFlowMapText(nodeId, shapeNode, newText);
        } else if (this.diagramType === 'multi_flow_map') {
            this.updateMultiFlowMapText(nodeId, shapeNode, newText);
        } else if (this.diagramType === 'tree_map') {
            this.updateTreeMapText(nodeId, shapeNode, newText);
        } else if (this.diagramType === 'bridge_map') {
            this.updateBridgeMapText(nodeId, shapeNode, newText);
        } else {
            // Generic text update for other diagram types
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
        }
        
        // Save to history
        this.saveToHistory('update_text', { nodeId, newText });
    }
    
    /**
     * Update Circle Map node text
     */
    updateCircleMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the central topic
            this.currentSpec.topic = newText;
            console.log('Updated Circle Map topic to:', newText);
        } else if (nodeType === 'context') {
            // Update context array
            const arrayIndex = parseInt(shape.attr('data-array-index'));
            if (!isNaN(arrayIndex) && Array.isArray(this.currentSpec.context)) {
                this.currentSpec.context[arrayIndex] = newText;
                console.log(`Updated context[${arrayIndex}] to:`, newText);
            }
        }
        
        // Re-render to update layout and text sizes
        this.renderDiagram();
    }
    
    /**
     * Update Bubble Map node text
     */
    updateBubbleMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the central topic
            this.currentSpec.topic = newText;
            console.log('Updated Bubble Map topic to:', newText);
        } else if (nodeType === 'attribute') {
            // Update attributes array
            const arrayIndex = parseInt(shape.attr('data-array-index'));
            if (!isNaN(arrayIndex) && Array.isArray(this.currentSpec.attributes)) {
                this.currentSpec.attributes[arrayIndex] = newText;
                console.log(`Updated attribute[${arrayIndex}] to:`, newText);
            }
        }
        
        // Re-render to update layout and text sizes
        this.renderDiagram();
    }
    
    /**
     * Update Double Bubble Map node text
     */
    updateDoubleBubbleMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        switch(nodeType) {
            case 'left':
                // Update left topic
                this.currentSpec.left = newText;
                console.log('Updated Double Bubble Map left topic to:', newText);
                break;
                
            case 'right':
                // Update right topic
                this.currentSpec.right = newText;
                console.log('Updated Double Bubble Map right topic to:', newText);
                break;
                
            case 'similarity':
                // Update similarities array
                const simIndex = parseInt(shape.attr('data-array-index'));
                if (!isNaN(simIndex) && Array.isArray(this.currentSpec.similarities)) {
                    this.currentSpec.similarities[simIndex] = newText;
                    console.log(`Updated similarity[${simIndex}] to:`, newText);
                }
                break;
                
            case 'left_difference':
                // Update left_differences array
                const leftDiffIndex = parseInt(shape.attr('data-array-index'));
                if (!isNaN(leftDiffIndex) && Array.isArray(this.currentSpec.left_differences)) {
                    this.currentSpec.left_differences[leftDiffIndex] = newText;
                    console.log(`Updated left_difference[${leftDiffIndex}] to:`, newText);
                }
                break;
                
            case 'right_difference':
                // Update right_differences array
                const rightDiffIndex = parseInt(shape.attr('data-array-index'));
                if (!isNaN(rightDiffIndex) && Array.isArray(this.currentSpec.right_differences)) {
                    this.currentSpec.right_differences[rightDiffIndex] = newText;
                    console.log(`Updated right_difference[${rightDiffIndex}] to:`, newText);
                }
                break;
                
            default:
                console.warn(`Unknown node type: ${nodeType}`);
                return;
        }
        
        // Re-render to update layout and text sizes
        this.renderDiagram();
    }
    
    /**
     * Update Brace Map node text
     */
    updateBraceMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the main topic
            this.currentSpec.topic = newText;
            console.log('Updated Brace Map topic to:', newText);
        } else if (nodeType === 'part') {
            // Update part name in the parts array
            const partIndex = parseInt(shape.attr('data-part-index'));
            if (!isNaN(partIndex) && this.currentSpec.parts && partIndex < this.currentSpec.parts.length) {
                this.currentSpec.parts[partIndex].name = newText;
                console.log(`Updated part ${partIndex} to:`, newText);
            }
        } else if (nodeType === 'subpart') {
            // Update subpart name in the parts array
            const partIndex = parseInt(shape.attr('data-part-index'));
            const subpartIndex = parseInt(shape.attr('data-subpart-index'));
            
            if (!isNaN(partIndex) && !isNaN(subpartIndex) && this.currentSpec.parts && partIndex < this.currentSpec.parts.length) {
                const part = this.currentSpec.parts[partIndex];
                if (part.subparts && subpartIndex < part.subparts.length) {
                    part.subparts[subpartIndex].name = newText;
                    console.log(`Updated subpart ${partIndex}-${subpartIndex} to:`, newText);
                }
            }
        }
        
        // Re-render to update layout and text sizes
        this.renderDiagram();
    }
    
    /**
     * Update Flow Map node text
     */
    updateFlowMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'title') {
            // Update the title
            this.currentSpec.title = newText;
            console.log('Updated Flow Map title to:', newText);
        } else if (nodeType === 'step') {
            // Update step in the steps array
            const stepIndex = parseInt(shape.attr('data-step-index'));
            if (!isNaN(stepIndex) && this.currentSpec.steps && stepIndex < this.currentSpec.steps.length) {
                this.currentSpec.steps[stepIndex] = newText;
                console.log(`Updated step ${stepIndex} to:`, newText);
            }
        } else if (nodeType === 'substep') {
            // Update substep in the substeps array
            const stepIndex = parseInt(shape.attr('data-step-index'));
            const substepIndex = parseInt(shape.attr('data-substep-index'));
            
            if (!isNaN(stepIndex) && !isNaN(substepIndex) && this.currentSpec.substeps) {
                // Find the substeps entry for this step
                const substepsEntry = this.currentSpec.substeps.find(s => s.step === this.currentSpec.steps[stepIndex]);
                if (substepsEntry && substepsEntry.substeps && substepIndex < substepsEntry.substeps.length) {
                    substepsEntry.substeps[substepIndex] = newText;
                    console.log(`Updated substep ${stepIndex}-${substepIndex} to:`, newText);
                }
            }
        }
        
        // Update the visual text element
        shape.text(newText);
        
        // Re-render to reflect changes
        this.renderDiagram();
    }
    
    /**
     * Update Multi-Flow Map node text
     */
    updateMultiFlowMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'event') {
            // Update the central event
            this.currentSpec.event = newText;
            console.log('Updated Multi-Flow Map event to:', newText);
        } else if (nodeType === 'cause') {
            // Update cause in the causes array
            const causeIndex = parseInt(shape.attr('data-cause-index'));
            if (!isNaN(causeIndex) && this.currentSpec.causes && causeIndex < this.currentSpec.causes.length) {
                this.currentSpec.causes[causeIndex] = newText;
                console.log(`Updated cause ${causeIndex} to:`, newText);
            }
        } else if (nodeType === 'effect') {
            // Update effect in the effects array
            const effectIndex = parseInt(shape.attr('data-effect-index'));
            if (!isNaN(effectIndex) && this.currentSpec.effects && effectIndex < this.currentSpec.effects.length) {
                this.currentSpec.effects[effectIndex] = newText;
                console.log(`Updated effect ${effectIndex} to:`, newText);
            }
        }
        
        // Update the visual text element
        shape.text(newText);
        
        // Re-render to reflect changes
        this.renderDiagram();
    }
    
    /**
     * Update Tree Map text
     */
    updateTreeMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the root topic
            this.currentSpec.topic = newText;
            console.log('Updated Tree Map topic to:', newText);
        } else if (nodeType === 'category') {
            // Update category text in children array
            const categoryIndex = parseInt(shape.attr('data-category-index'));
            if (!isNaN(categoryIndex) && this.currentSpec.children && categoryIndex < this.currentSpec.children.length) {
                this.currentSpec.children[categoryIndex].text = newText;
                console.log(`Updated category ${categoryIndex} to:`, newText);
            }
        } else if (nodeType === 'leaf') {
            // Update leaf text within its category
            const categoryIndex = parseInt(shape.attr('data-category-index'));
            const leafIndex = parseInt(shape.attr('data-leaf-index'));
            if (!isNaN(categoryIndex) && !isNaN(leafIndex) && 
                this.currentSpec.children && categoryIndex < this.currentSpec.children.length) {
                const category = this.currentSpec.children[categoryIndex];
                if (Array.isArray(category.children) && leafIndex < category.children.length) {
                    // Handle both object and string formats
                    if (typeof category.children[leafIndex] === 'object') {
                        category.children[leafIndex].text = newText;
                    } else {
                        category.children[leafIndex] = newText;
                    }
                    console.log(`Updated leaf ${leafIndex} in category ${categoryIndex} to:`, newText);
                }
            }
        }
        
        // Update the visual text element
        shape.text(newText);
        
        // Re-render to reflect changes
        this.renderDiagram();
    }
    
    /**
     * Update Bridge Map text
     */
    updateBridgeMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            console.error('No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            console.error('Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        const pairIndex = parseInt(shape.attr('data-pair-index'));
        
        if (!isNaN(pairIndex) && pairIndex < this.currentSpec.analogies.length) {
            if (nodeType === 'left') {
                // Update left item in the pair
                this.currentSpec.analogies[pairIndex].left = newText;
                console.log(`Updated left item in pair ${pairIndex} to: "${newText}"`);
            } else if (nodeType === 'right') {
                // Update right item in the pair
                this.currentSpec.analogies[pairIndex].right = newText;
                console.log(`Updated right item in pair ${pairIndex} to: "${newText}"`);
            }
        }
        
        // Update the visual text element
        const textElement = d3.select(`[data-text-for="${nodeId}"]`);
        if (!textElement.empty()) {
            textElement.text(newText);
        } else {
            // If no separate text element, try to update the shape itself if it's text
            if (shape.node().tagName === 'text') {
                shape.text(newText);
            }
        }
        
        // Re-render to reflect changes
        this.renderDiagram();
    }
    
    /**
     * Update generic node text (for other diagram types)
     */
    updateGenericNodeText(nodeId, shapeNode, textNode, newText) {
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
    }
    
    /**
     * Add a new node to the diagram
     */
    addNode() {
        this.log('InteractiveEditor: Add node requested', { hasSelection: this.selectedNodes.size > 0 });
        
        // Validate session before adding
        if (!this.validateSession('Add node')) {
            return;
        }
        
        // Handle diagram-specific node addition
        switch(this.diagramType) {
            case 'circle_map':
                this.addNodeToCircleMap();
                break;
            case 'bubble_map':
                this.addNodeToBubbleMap();
                break;
            case 'double_bubble_map':
                this.addNodeToDoubleBubbleMap();
                break;
            case 'brace_map':
                this.addNodeToBraceMap();
                break;
            case 'flow_map':
                this.addNodeToFlowMap();
                break;
            case 'multi_flow_map':
                this.addNodeToMultiFlowMap();
                break;
            case 'tree_map':
                this.addNodeToTreeMap();
                break;
            case 'bridge_map':
                this.addNodeToBridgeMap();
                break;
            case 'concept_map':
                this.addNodeToConceptMap();
                break;
            default:
                this.addGenericNode();
                break;
        }
    }
    
    /**
     * Add a new node to Circle Map
     */
    addNodeToCircleMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.context)) {
            console.error('Invalid circle map spec');
            return;
        }
        
        // Add new context item to spec
        this.currentSpec.context.push('New Context');
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'circle_map', 
            contextCount: this.currentSpec.context.length 
        });
        
        console.log('Added new context node to Circle Map');
    }
    
    /**
     * Add a new node to Bubble Map
     */
    addNodeToBubbleMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.attributes)) {
            console.error('Invalid bubble map spec');
            return;
        }
        
        // Add new attribute item to spec
        this.currentSpec.attributes.push('New Attribute');
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'bubble_map', 
            attributeCount: this.currentSpec.attributes.length 
        });
        
        console.log('Added new attribute node to Bubble Map');
    }
    
    /**
     * Add a new node to Double Bubble Map
     * Requires user to select a node type first (similarity or difference)
     */
    addNodeToDoubleBubbleMap() {
        if (!this.currentSpec) {
            console.error('Invalid double bubble map spec');
            return;
        }
        
        // Check if user has selected a node
        const selected = Array.from(this.selectedNodes);
        if (selected.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            console.log('DoubleBubbleMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the type of the selected node
        const selectedElement = d3.select(`[data-node-id="${selected[0]}"]`);
        const nodeType = selectedElement.attr('data-node-type');
        
        if (!nodeType) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification('Could not determine node type. Please try again.', 'error');
            }
            return;
        }
        
        // Add node based on selected type
        switch(nodeType) {
            case 'similarity':
                // Add similarity
                if (!Array.isArray(this.currentSpec.similarities)) {
                    this.currentSpec.similarities = [];
                }
                this.currentSpec.similarities.push('New Similarity');
                console.log('Added new similarity node');
                break;
                
            case 'left_difference':
            case 'right_difference':
                // Add paired differences (one to each side)
                if (!Array.isArray(this.currentSpec.left_differences)) {
                    this.currentSpec.left_differences = [];
                }
                if (!Array.isArray(this.currentSpec.right_differences)) {
                    this.currentSpec.right_differences = [];
                }
                this.currentSpec.left_differences.push('Left Difference');
                this.currentSpec.right_differences.push('Right Difference');
                console.log('Added paired difference nodes');
                break;
                
            case 'left':
            case 'right':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot add main topics. Please select a similarity or difference node.', 'warning');
                }
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Unknown node type. Please select a similarity or difference node.', 'error');
                }
                return;
        }
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'double_bubble_map',
            nodeType: nodeType
        });
        
        if (this.toolbarManager) {
            if (nodeType === 'similarity') {
                this.toolbarManager.showNotification('Similarity node added!', 'success');
            } else {
                this.toolbarManager.showNotification('Difference pair added!', 'success');
            }
        }
    }
    
    /**
     * Add a new node to Brace Map
     * Requires user to select a part or subpart node first
     * - Clicking on part → adds new part
     * - Clicking on subpart → adds new subpart to same part
     */
    addNodeToBraceMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.parts)) {
            console.error('Invalid brace map spec');
            return;
        }
        
        // Check if user has selected a node
        const selected = Array.from(this.selectedNodes);
        if (selected.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            console.log('BraceMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the type of the selected node
        const selectedElement = d3.select(`[data-node-id="${selected[0]}"]`);
        const nodeType = selectedElement.attr('data-node-type');
        
        if (!nodeType) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification('Could not determine node type. Please try again.', 'error');
            }
            return;
        }
        
        // Handle different node types
        switch(nodeType) {
            case 'part': {
                // Add new part node to the parts array with two default subparts
                this.currentSpec.parts.push({
                    name: 'New Part',
                    subparts: [
                        { name: 'New Subpart 1' },
                        { name: 'New Subpart 2' }
                    ]
                });
                console.log('Added new part node with 2 subparts');
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New part added with 2 subparts!', 'success');
                }
                break;
            }
                
            case 'subpart': {
                // Get part index from selected subpart
                const partIndex = parseInt(selectedElement.attr('data-part-index'));
                
                if (isNaN(partIndex) || partIndex < 0 || partIndex >= this.currentSpec.parts.length) {
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification('Invalid part index', 'error');
                    }
                    return;
                }
                
                // Add new subpart to the same part as the selected subpart
                if (!Array.isArray(this.currentSpec.parts[partIndex].subparts)) {
                    this.currentSpec.parts[partIndex].subparts = [];
                }
                this.currentSpec.parts[partIndex].subparts.push({
                    name: 'New Subpart'
                });
                console.log(`Added new subpart to part ${partIndex}`);
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New subpart added!', 'success');
                }
                break;
            }
                
            case 'topic':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot add to topic. Please select a part or subpart node.', 'warning');
                }
                // Don't re-render, just return
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Unknown node type. Please select a part or subpart node.', 'error');
                }
                return;
        }
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'brace_map',
            nodeType: nodeType
        });
    }
    
    /**
     * Add a new node to Flow Map
     * Requirements:
     * - Requires node selection (step or substep)
     * - Clicking on step → adds new step (with 2 substeps)
     * - Clicking on substep → adds new substep to same step
     */
    addNodeToFlowMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.steps)) {
            console.error('Invalid flow map spec');
            return;
        }
        
        // Check if a node is selected
        const selectedNodes = Array.from(this.selectedNodes);
        if (selectedNodes.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            console.log('FlowMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            console.error('Selected node not found');
            return;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        console.log('Adding to flow map, selected node type:', nodeType);
        
        // Handle different node types
        switch (nodeType) {
            case 'step': {
                // Get the index of the selected step
                const stepIndex = parseInt(selectedElement.attr('data-step-index'));
                
                if (isNaN(stepIndex) || stepIndex < 0 || stepIndex >= this.currentSpec.steps.length) {
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification('Invalid step index', 'error');
                    }
                    return;
                }
                
                // Insert new step right after the selected step
                const newStep = 'New Step';
                this.currentSpec.steps.splice(stepIndex + 1, 0, newStep);
                
                // Also insert substeps entry at the same position with 2 default substeps
                if (!Array.isArray(this.currentSpec.substeps)) {
                    this.currentSpec.substeps = [];
                }
                this.currentSpec.substeps.splice(stepIndex + 1, 0, {
                    step: newStep,
                    substeps: ['New Substep 1', 'New Substep 2']
                });
                
                console.log(`Inserted new step after step ${stepIndex} with 2 substeps`);
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New step added with 2 substeps!', 'success');
                }
                break;
            }
                
            case 'substep': {
                // Get step index and substep index from selected substep
                const stepIndex = parseInt(selectedElement.attr('data-step-index'));
                const substepIndex = parseInt(selectedElement.attr('data-substep-index'));
                
                if (isNaN(stepIndex) || stepIndex < 0 || stepIndex >= this.currentSpec.steps.length) {
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification('Invalid step index', 'error');
                    }
                    return;
                }
                
                if (isNaN(substepIndex) || substepIndex < 0) {
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification('Invalid substep index', 'error');
                    }
                    return;
                }
                
                // Find the substeps entry for this step
                const stepName = this.currentSpec.steps[stepIndex];
                let substepsEntry = this.currentSpec.substeps?.find(s => s.step === stepName);
                
                if (!substepsEntry) {
                    // Create substeps entry if it doesn't exist
                    if (!Array.isArray(this.currentSpec.substeps)) {
                        this.currentSpec.substeps = [];
                    }
                    substepsEntry = { step: stepName, substeps: [] };
                    this.currentSpec.substeps.push(substepsEntry);
                }
                
                // Insert new substep right after the selected substep
                if (!Array.isArray(substepsEntry.substeps)) {
                    substepsEntry.substeps = [];
                }
                substepsEntry.substeps.splice(substepIndex + 1, 0, 'New Substep');
                
                console.log(`Inserted new substep after substep ${substepIndex} in step ${stepIndex}`);
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New substep added!', 'success');
                }
                break;
            }
                
            case 'title':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot add to title. Please select a step or substep node.', 'warning');
                }
                // Don't re-render, just return
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Please select a step or substep node', 'warning');
                }
                return;
        }
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'flow_map',
            nodeType: nodeType
        });
    }
    
    /**
     * Add a new node to Multi-Flow Map
     * Requirements:
     * - Requires node selection (cause or effect)
     * - Clicking on cause → adds new cause
     * - Clicking on effect → adds new effect
     * - They don't go in pairs
     */
    addNodeToMultiFlowMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.causes) || !Array.isArray(this.currentSpec.effects)) {
            console.error('Invalid multi-flow map spec');
            return;
        }
        
        // Check if a node is selected
        const selectedNodes = Array.from(this.selectedNodes);
        if (selectedNodes.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            console.log('MultiFlowMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            console.error('Selected node not found');
            return;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        console.log('Adding to multi-flow map, selected node type:', nodeType);
        
        // Handle different node types
        switch (nodeType) {
            case 'cause': {
                // Add new cause to the causes array
                this.currentSpec.causes.push('New Cause');
                
                console.log(`Added new cause. Total causes: ${this.currentSpec.causes.length}`);
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New cause added!', 'success');
                }
                break;
            }
                
            case 'effect': {
                // Add new effect to the effects array
                this.currentSpec.effects.push('New Effect');
                
                console.log(`Added new effect. Total effects: ${this.currentSpec.effects.length}`);
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New effect added!', 'success');
                }
                break;
            }
                
            case 'event':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot add to event. Please select a cause or effect node.', 'warning');
                }
                // Don't re-render, just return
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Please select a cause or effect node', 'warning');
                }
                return;
        }
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'multi_flow_map',
            nodeType: nodeType
        });
    }
    
    /**
     * Add a new node to Tree Map
     */
    addNodeToTreeMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.children)) {
            console.error('Invalid tree map spec');
            return;
        }
        
        // Check if a node is selected
        const selectedNodes = Array.from(this.selectedNodes);
        if (selectedNodes.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            console.log('TreeMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            console.error('Selected node not found');
            return;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        console.log('Adding to tree map, selected node type:', nodeType);
        
        // Handle different node types
        switch (nodeType) {
            case 'category': {
                // Add new category (with 3 children) to children array
                const categoryIndex = parseInt(selectedElement.attr('data-category-index'));
                const newCategory = {
                    text: 'New Category',
                    children: [
                        { text: 'New Child 1' },
                        { text: 'New Child 2' },
                        { text: 'New Child 3' }
                    ]
                };
                
                // Insert after selected category
                this.currentSpec.children.splice(categoryIndex + 1, 0, newCategory);
                
                console.log(`Added new category after index ${categoryIndex}. Total categories: ${this.currentSpec.children.length}`);
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New category added with 3 children!', 'success');
                }
                break;
            }
                
            case 'leaf': {
                // Add new leaf/child to the parent category
                const categoryIndex = parseInt(selectedElement.attr('data-category-index'));
                const leafIndex = parseInt(selectedElement.attr('data-leaf-index'));
                
                if (categoryIndex < 0 || categoryIndex >= this.currentSpec.children.length) {
                    console.error('Invalid category index');
                    return;
                }
                
                const category = this.currentSpec.children[categoryIndex];
                if (!Array.isArray(category.children)) {
                    category.children = [];
                }
                
                // Insert after selected leaf
                category.children.splice(leafIndex + 1, 0, { text: 'New Child' });
                
                console.log(`Added new child to category ${categoryIndex} after leaf ${leafIndex}. Total children: ${category.children.length}`);
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('New child added!', 'success');
                }
                break;
            }
                
            case 'topic':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot add to topic. Please select a category or child node.', 'warning');
                }
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Please select a category or child node', 'warning');
                }
                return;
        }
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'tree_map',
            nodeType: nodeType
        });
    }
    
    /**
     * Add a new analogy pair to Bridge Map
     */
    addNodeToBridgeMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.analogies)) {
            console.error('Invalid bridge map spec');
            return;
        }
        
        // For bridge map, always add pairs to the end (no selection required)
        // This is because bridge maps are sequential in nature
        const newPair = {
            left: 'New Left',
            right: 'New Right'
        };
        
        this.currentSpec.analogies.push(newPair);
        
        console.log(`Added new analogy pair at end. Total pairs: ${this.currentSpec.analogies.length}`);
        
        // Re-render the diagram with new pair
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'bridge_map',
            totalPairs: this.currentSpec.analogies.length
        });
    }
    
    /**
     * Add a new node to Concept Map
     */
    addNodeToConceptMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.concepts)) {
            console.error('Invalid concept map spec');
            return;
        }
        
        // Add new concept to spec
        this.currentSpec.concepts.push({
            text: 'New Concept',
            x: 400,
            y: 300
        });
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'concept_map', 
            conceptCount: this.currentSpec.concepts.length 
        });
        
        console.log('Added new concept node to Concept Map');
    }
    
    /**
     * Add a generic node (fallback for other diagram types)
     */
    addGenericNode() {
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
            .attr('data-node-id', nodeId);
        
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
            .style('pointer-events', 'none')
            .text('New Node');
        
        // Add drag behavior to this specific node only
        this.addDragBehavior(circle, text);
        
        // Add click handlers to this specific node
        const self = this;
        circle.on('click', (event) => {
            event.stopPropagation();
            if (event.ctrlKey || event.metaKey) {
                self.selectionManager.toggleNode(nodeId);
            } else {
                self.selectionManager.clearSelection();
                self.selectionManager.selectNode(nodeId);
            }
        });
        
        // Add double-click handler for editing
        circle.on('dblclick', (event) => {
            event.stopPropagation();
            self.openNodeEditor(nodeId, circle.node(), text.node(), 'New Node');
        });
        
        text.on('dblclick', (event) => {
            event.stopPropagation();
            self.openNodeEditor(nodeId, circle.node(), text.node(), 'New Node');
        });
        
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
            this.log('InteractiveEditor: Delete requested but no nodes selected');
            return;
        }
        
        // Validate session before deleting
        if (!this.validateSession('Delete nodes')) {
            return;
        }
        
        const nodesToDelete = Array.from(this.selectedNodes);
        this.log('InteractiveEditor: Deleting nodes', { count: nodesToDelete.length, nodeIds: nodesToDelete });
        
        // Handle diagram-specific deletion
        if (this.diagramType === 'circle_map') {
            this.deleteCircleMapNodes(nodesToDelete);
        } else if (this.diagramType === 'bubble_map') {
            this.deleteBubbleMapNodes(nodesToDelete);
        } else if (this.diagramType === 'double_bubble_map') {
            this.deleteDoubleBubbleMapNodes(nodesToDelete);
        } else if (this.diagramType === 'brace_map') {
            this.deleteBraceMapNodes(nodesToDelete);
        } else if (this.diagramType === 'flow_map') {
            this.deleteFlowMapNodes(nodesToDelete);
        } else if (this.diagramType === 'multi_flow_map') {
            this.deleteMultiFlowMapNodes(nodesToDelete);
        } else if (this.diagramType === 'tree_map') {
            this.deleteTreeMapNodes(nodesToDelete);
        } else if (this.diagramType === 'bridge_map') {
            this.deleteBridgeMapNodes(nodesToDelete);
        } else if (this.diagramType === 'concept_map') {
            this.deleteConceptMapNodes(nodesToDelete);
        } else {
            this.deleteGenericNodes(nodesToDelete);
        }
        
        // Clear selection
        this.selectionManager.clearSelection();
        
        // Save to history
        this.saveToHistory('delete_nodes', { nodeIds: nodesToDelete });
        
        console.log(`Successfully deleted ${nodesToDelete.length} node(s)`);
    }
    
    /**
     * Delete Circle Map nodes
     */
    deleteCircleMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.context)) {
            console.error('Invalid circle map spec');
            return;
        }
        
        // Collect indices to delete and check for main topic
        const indicesToDelete = [];
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                
                if (nodeType === 'context') {
                    const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
                    if (!isNaN(arrayIndex)) {
                        indicesToDelete.push(arrayIndex);
                    }
                } else if (nodeType === 'topic') {
                    attemptedMainTopicDelete = true;
                }
            }
        });
        
        // Show notification if user tried to delete main topic
        if (attemptedMainTopicDelete) {
            // Dispatch event for toolbar to show notification
            window.dispatchEvent(new CustomEvent('show-notification', {
                detail: {
                    message: 'Main topic node cannot be deleted',
                    type: 'warning'
                }
            }));
        }
        
        // If no valid nodes to delete, return early
        if (indicesToDelete.length === 0) {
            return;
        }
        
        // Sort indices in descending order to delete from end to start
        indicesToDelete.sort((a, b) => b - a);
        
        // Remove from spec
        indicesToDelete.forEach(index => {
            this.currentSpec.context.splice(index, 1);
        });
        
        console.log(`Deleted ${indicesToDelete.length} context node(s) from Circle Map`);
        
        // Re-render
        this.renderDiagram();
    }
    
    /**
     * Delete Bubble Map nodes
     */
    deleteBubbleMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.attributes)) {
            console.error('Invalid bubble map spec');
            return;
        }
        
        // Collect indices to delete and check for main topic
        const indicesToDelete = [];
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                
                if (nodeType === 'attribute') {
                    const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
                    if (!isNaN(arrayIndex)) {
                        indicesToDelete.push(arrayIndex);
                    }
                } else if (nodeType === 'topic') {
                    attemptedMainTopicDelete = true;
                }
            }
        });
        
        // Show notification if user tried to delete main topic
        if (attemptedMainTopicDelete) {
            // Dispatch event for toolbar to show notification
            window.dispatchEvent(new CustomEvent('show-notification', {
                detail: {
                    message: 'Main topic node cannot be deleted',
                    type: 'warning'
                }
            }));
        }
        
        // If no valid nodes to delete, return early
        if (indicesToDelete.length === 0) {
            return;
        }
        
        // Sort indices in descending order to delete from end to start
        indicesToDelete.sort((a, b) => b - a);
        
        // Remove from spec
        indicesToDelete.forEach(index => {
            this.currentSpec.attributes.splice(index, 1);
        });
        
        console.log(`Deleted ${indicesToDelete.length} attribute node(s) from Bubble Map`);
        
        // Re-render
        this.renderDiagram();
    }
    
    /**
     * Delete Double Bubble Map nodes
     * - Similarities: delete normally
     * - Differences: delete in PAIRS (same index from both left and right)
     */
    deleteDoubleBubbleMapNodes(nodeIds) {
        if (!this.currentSpec) {
            console.error('Invalid double bubble map spec');
            return;
        }
        
        // Collect indices to delete by type
        const similarityIndicesToDelete = [];
        const differenceIndicesToDelete = []; // For paired deletion
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
                
                switch(nodeType) {
                    case 'similarity':
                        if (!isNaN(arrayIndex)) {
                            similarityIndicesToDelete.push(arrayIndex);
                        }
                        break;
                        
                    case 'left_difference':
                    case 'right_difference':
                        // For differences, delete in pairs at the same index
                        if (!isNaN(arrayIndex)) {
                            differenceIndicesToDelete.push(arrayIndex);
                        }
                        break;
                        
                    case 'left':
                    case 'right':
                        attemptedMainTopicDelete = true;
                        break;
                }
            }
        });
        
        // Show notification if user tried to delete main topics
        if (attemptedMainTopicDelete) {
            window.dispatchEvent(new CustomEvent('show-notification', {
                detail: {
                    message: 'Main topic nodes cannot be deleted',
                    type: 'warning'
                }
            }));
        }
        
        // If no valid nodes to delete, return early
        if (similarityIndicesToDelete.length === 0 && differenceIndicesToDelete.length === 0) {
            return;
        }
        
        let deletedCount = 0;
        
        // Delete similarities
        if (similarityIndicesToDelete.length > 0 && Array.isArray(this.currentSpec.similarities)) {
            // Sort in descending order to delete from end to start
            const uniqueIndices = [...new Set(similarityIndicesToDelete)].sort((a, b) => b - a);
            uniqueIndices.forEach(index => {
                this.currentSpec.similarities.splice(index, 1);
                deletedCount++;
            });
            console.log(`Deleted ${uniqueIndices.length} similarity node(s)`);
        }
        
        // Delete differences in PAIRS
        if (differenceIndicesToDelete.length > 0) {
            // Remove duplicates and sort in descending order
            const uniqueIndices = [...new Set(differenceIndicesToDelete)].sort((a, b) => b - a);
            
            uniqueIndices.forEach(index => {
                // Delete from both left and right at the same index
                if (Array.isArray(this.currentSpec.left_differences) && index < this.currentSpec.left_differences.length) {
                    this.currentSpec.left_differences.splice(index, 1);
                }
                if (Array.isArray(this.currentSpec.right_differences) && index < this.currentSpec.right_differences.length) {
                    this.currentSpec.right_differences.splice(index, 1);
                }
            });
            
            deletedCount += uniqueIndices.length * 2; // Count both left and right
            console.log(`Deleted ${uniqueIndices.length} difference pair(s) (${uniqueIndices.length * 2} nodes total)`);
            
            // Show notification about paired deletion
            window.dispatchEvent(new CustomEvent('show-notification', {
                detail: {
                    message: `Deleted ${uniqueIndices.length} difference pair${uniqueIndices.length > 1 ? 's' : ''} (left & right)`,
                    type: 'success'
                }
            }));
        }
        
        console.log(`Total deleted from Double Bubble Map: ${deletedCount} node(s)`);
        
        // Re-render - this will automatically remove connecting lines
        this.renderDiagram();
    }
    
    /**
     * Delete Brace Map nodes (parts and subparts)
     */
    deleteBraceMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.parts)) {
            console.error('Invalid brace map spec');
            return;
        }
        
        // Collect nodes to delete by type
        const partsToDelete = [];
        const subpartsToDelete = []; // Store as {partIndex, subpartIndex}
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                
                switch(nodeType) {
                    case 'part': {
                        const partIndex = parseInt(shapeElement.attr('data-part-index'));
                        if (!isNaN(partIndex)) {
                            partsToDelete.push(partIndex);
                        }
                        break;
                    }
                        
                    case 'subpart': {
                        const partIndex = parseInt(shapeElement.attr('data-part-index'));
                        const subpartIndex = parseInt(shapeElement.attr('data-subpart-index'));
                        if (!isNaN(partIndex) && !isNaN(subpartIndex)) {
                            subpartsToDelete.push({partIndex, subpartIndex});
                        }
                        break;
                    }
                        
                    case 'topic':
                        attemptedMainTopicDelete = true;
                        break;
                }
            }
        });
        
        // Show notification if user tried to delete main topic
        if (attemptedMainTopicDelete) {
            window.dispatchEvent(new CustomEvent('show-notification', {
                detail: {
                    message: 'Main topic node cannot be deleted',
                    type: 'warning'
                }
            }));
        }
        
        // If no valid nodes to delete, return early
        if (partsToDelete.length === 0 && subpartsToDelete.length === 0) {
            return;
        }
        
        let deletedCount = 0;
        
        // Delete subparts first (before deleting parts, which would remove all subparts)
        if (subpartsToDelete.length > 0) {
            // Group subparts by part index for efficient deletion
            const subpartsByPart = {};
            subpartsToDelete.forEach(({partIndex, subpartIndex}) => {
                if (!subpartsByPart[partIndex]) {
                    subpartsByPart[partIndex] = [];
                }
                subpartsByPart[partIndex].push(subpartIndex);
            });
            
            // Delete subparts for each part (in descending order to avoid index shifts)
            Object.keys(subpartsByPart).forEach(partIndexStr => {
                const partIndex = parseInt(partIndexStr);
                if (partIndex >= 0 && partIndex < this.currentSpec.parts.length) {
                    const part = this.currentSpec.parts[partIndex];
                    if (part && Array.isArray(part.subparts)) {
                        // Sort indices in descending order
                        const sortedIndices = [...new Set(subpartsByPart[partIndex])].sort((a, b) => b - a);
                        sortedIndices.forEach(subpartIndex => {
                            if (subpartIndex >= 0 && subpartIndex < part.subparts.length) {
                                part.subparts.splice(subpartIndex, 1);
                                deletedCount++;
                            }
                        });
                    }
                }
            });
            console.log(`Deleted ${deletedCount} subpart(s)`);
        }
        
        // Delete parts (this will also remove any remaining subparts)
        if (partsToDelete.length > 0) {
            // Remove duplicates and sort in descending order
            const uniquePartIndices = [...new Set(partsToDelete)].sort((a, b) => b - a);
            
            uniquePartIndices.forEach(partIndex => {
                if (partIndex >= 0 && partIndex < this.currentSpec.parts.length) {
                    this.currentSpec.parts.splice(partIndex, 1);
                    deletedCount++;
                }
            });
            console.log(`Deleted ${uniquePartIndices.length} part(s)`);
        }
        
        console.log(`Total deleted from Brace Map: ${deletedCount} node(s)`);
        
        // Re-render - this will automatically rebuild the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Flow Map nodes (steps and substeps)
     */
    deleteFlowMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.steps)) {
            console.error('Invalid flow map spec');
            return;
        }
        
        // Separate node IDs by type
        const stepNodesToDelete = [];
        const substepNodesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                console.warn(`Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'title') {
                // Don't allow deletion of title
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot delete the title', 'warning');
                }
                return;
            } else if (nodeType === 'step') {
                const stepIndex = parseInt(element.attr('data-step-index'));
                if (!isNaN(stepIndex)) {
                    stepNodesToDelete.push({ nodeId, stepIndex });
                }
            } else if (nodeType === 'substep') {
                const stepIndex = parseInt(element.attr('data-step-index'));
                const substepIndex = parseInt(element.attr('data-substep-index'));
                if (!isNaN(stepIndex) && !isNaN(substepIndex)) {
                    substepNodesToDelete.push({ nodeId, stepIndex, substepIndex });
                }
            }
        });
        
        console.log('Flow map deletion:', { stepNodesToDelete, substepNodesToDelete });
        
        // Delete substeps first (grouped by step, highest index first to avoid index shifting)
        const substepsByStep = {};
        substepNodesToDelete.forEach(item => {
            if (!substepsByStep[item.stepIndex]) {
                substepsByStep[item.stepIndex] = [];
            }
            substepsByStep[item.stepIndex].push(item.substepIndex);
        });
        
        Object.keys(substepsByStep).forEach(stepIndex => {
            const indices = substepsByStep[stepIndex].sort((a, b) => b - a); // Sort descending
            const stepName = this.currentSpec.steps[parseInt(stepIndex)];
            const substepsEntry = this.currentSpec.substeps?.find(s => s.step === stepName);
            
            if (substepsEntry && Array.isArray(substepsEntry.substeps)) {
                indices.forEach(index => {
                    if (index >= 0 && index < substepsEntry.substeps.length) {
                        substepsEntry.substeps.splice(index, 1);
                        console.log(`Deleted substep ${index} from step ${stepIndex}`);
                    }
                });
            }
        });
        
        // Delete steps (sort by index descending to avoid index shifting)
        const stepIndicesToDelete = stepNodesToDelete
            .map(item => item.stepIndex)
            .sort((a, b) => b - a);
        
        stepIndicesToDelete.forEach(index => {
            if (index >= 0 && index < this.currentSpec.steps.length) {
                const stepName = this.currentSpec.steps[index];
                
                // Remove step from steps array
                this.currentSpec.steps.splice(index, 1);
                console.log(`Deleted step ${index}: ${stepName}`);
                
                // Remove corresponding substeps entry
                if (Array.isArray(this.currentSpec.substeps)) {
                    const substepsIndex = this.currentSpec.substeps.findIndex(s => s.step === stepName);
                    if (substepsIndex !== -1) {
                        this.currentSpec.substeps.splice(substepsIndex, 1);
                        console.log(`Deleted substeps entry for step: ${stepName}`);
                    }
                }
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        console.log(`FlowMap: Deleted ${stepNodesToDelete.length + substepNodesToDelete.length} node(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Multi-Flow Map nodes (causes and effects)
     */
    deleteMultiFlowMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.causes) || !Array.isArray(this.currentSpec.effects)) {
            console.error('Invalid multi-flow map spec');
            return;
        }
        
        // Separate node IDs by type and collect indices
        const causeIndicesToDelete = [];
        const effectIndicesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                console.warn(`Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'event') {
                // Don't allow deletion of central event
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot delete the central event', 'warning');
                }
                return;
            } else if (nodeType === 'cause') {
                const causeIndex = parseInt(element.attr('data-cause-index'));
                if (!isNaN(causeIndex)) {
                    causeIndicesToDelete.push(causeIndex);
                }
            } else if (nodeType === 'effect') {
                const effectIndex = parseInt(element.attr('data-effect-index'));
                if (!isNaN(effectIndex)) {
                    effectIndicesToDelete.push(effectIndex);
                }
            }
        });
        
        console.log('Multi-flow map deletion:', { causeIndicesToDelete, effectIndicesToDelete });
        
        // Delete causes (sort by index descending to avoid index shifting)
        const sortedCauseIndices = causeIndicesToDelete.sort((a, b) => b - a);
        sortedCauseIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.causes.length) {
                const causeText = this.currentSpec.causes[index];
                this.currentSpec.causes.splice(index, 1);
                console.log(`Deleted cause ${index}: ${causeText}`);
            }
        });
        
        // Delete effects (sort by index descending to avoid index shifting)
        const sortedEffectIndices = effectIndicesToDelete.sort((a, b) => b - a);
        sortedEffectIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.effects.length) {
                const effectText = this.currentSpec.effects[index];
                this.currentSpec.effects.splice(index, 1);
                console.log(`Deleted effect ${index}: ${effectText}`);
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        console.log(`MultiFlowMap: Deleted ${causeIndicesToDelete.length + effectIndicesToDelete.length} node(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Tree Map nodes
     */
    deleteTreeMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.children)) {
            console.error('Invalid tree map spec');
            return;
        }
        
        // Separate node IDs by type and collect indices
        const categoriesToDelete = [];
        const leavesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                console.warn(`Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'topic') {
                // Don't allow deletion of root topic
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification('Cannot delete the root topic', 'warning');
                }
                return;
            } else if (nodeType === 'category') {
                const categoryIndex = parseInt(element.attr('data-category-index'));
                if (!isNaN(categoryIndex)) {
                    categoriesToDelete.push(categoryIndex);
                }
            } else if (nodeType === 'leaf') {
                const categoryIndex = parseInt(element.attr('data-category-index'));
                const leafIndex = parseInt(element.attr('data-leaf-index'));
                if (!isNaN(categoryIndex) && !isNaN(leafIndex)) {
                    leavesToDelete.push({ categoryIndex, leafIndex });
                }
            }
        });
        
        console.log('Tree map deletion:', { categoriesToDelete, leavesToDelete });
        
        // Delete leaves first (sort by leaf index descending within each category)
        // Group by category
        const leavesByCategory = {};
        leavesToDelete.forEach(({ categoryIndex, leafIndex }) => {
            if (!leavesByCategory[categoryIndex]) {
                leavesByCategory[categoryIndex] = [];
            }
            leavesByCategory[categoryIndex].push(leafIndex);
        });
        
        // Sort and delete leaves within each category
        Object.keys(leavesByCategory).forEach(catIdx => {
            const categoryIndex = parseInt(catIdx);
            if (categoryIndex >= 0 && categoryIndex < this.currentSpec.children.length) {
                const category = this.currentSpec.children[categoryIndex];
                if (Array.isArray(category.children)) {
                    // Sort leaf indices descending to avoid index shifting
                    const sortedLeafIndices = leavesByCategory[catIdx].sort((a, b) => b - a);
                    sortedLeafIndices.forEach(leafIndex => {
                        if (leafIndex >= 0 && leafIndex < category.children.length) {
                            const leafText = category.children[leafIndex].text || category.children[leafIndex];
                            category.children.splice(leafIndex, 1);
                            console.log(`Deleted leaf ${leafIndex} from category ${categoryIndex}: ${leafText}`);
                        }
                    });
                }
            }
        });
        
        // Delete categories (sort by index descending to avoid index shifting)
        const sortedCategoryIndices = categoriesToDelete.sort((a, b) => b - a);
        sortedCategoryIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.children.length) {
                const categoryText = this.currentSpec.children[index].text;
                this.currentSpec.children.splice(index, 1);
                console.log(`Deleted category ${index}: ${categoryText}`);
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        console.log(`TreeMap: Deleted ${categoriesToDelete.length + leavesToDelete.length} node(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Bridge Map analogy pairs
     */
    deleteBridgeMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.analogies)) {
            console.error('Invalid bridge map spec');
            return;
        }
        
        // Collect unique pair indices to delete
        // Bridge map deletes complete pairs (both left and right together)
        const pairIndicesToDelete = new Set();
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                console.warn(`Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            const pairIndex = parseInt(element.attr('data-pair-index'));
            
            if (!isNaN(pairIndex)) {
                // Add the pair index (whether it's left or right, we delete the whole pair)
                pairIndicesToDelete.add(pairIndex);
                console.log(`Marking pair ${pairIndex} for deletion (${nodeType} node)`);
            }
        });
        
        console.log('Bridge map deletion:', { pairIndicesToDelete: Array.from(pairIndicesToDelete) });
        
        // Prevent deletion of the first pair (like the topic in other maps)
        if (pairIndicesToDelete.has(0)) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification('Cannot delete the first analogy pair', 'warning');
            }
            pairIndicesToDelete.delete(0);
        }
        
        // Delete pairs (sort by index descending to avoid index shifting)
        const sortedPairIndices = Array.from(pairIndicesToDelete).sort((a, b) => b - a);
        sortedPairIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.analogies.length) {
                const pair = this.currentSpec.analogies[index];
                this.currentSpec.analogies.splice(index, 1);
                console.log(`Deleted pair ${index}: "${pair.left}" / "${pair.right}"`);
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        console.log(`BridgeMap: Deleted ${sortedPairIndices.length} pair(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Concept Map nodes
     */
    deleteConceptMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.concepts)) {
            console.error('Invalid concept map spec');
            return;
        }
        
        // Collect node texts to delete from spec
        const textsToDelete = new Set();
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                // Find associated text to match with spec
                const parentGroup = shapeElement.node()?.parentNode;
                let nodeText = '';
                
                if (parentGroup && parentGroup.tagName === 'g') {
                    const textElement = d3.select(parentGroup).select('text');
                    if (!textElement.empty()) {
                        nodeText = textElement.text();
                    }
                } else {
                    const textElement = d3.select(`[data-text-for="${nodeId}"]`);
                    if (!textElement.empty()) {
                        nodeText = textElement.text();
                    }
                }
                
                if (nodeText) {
                    textsToDelete.add(nodeText);
                }
            }
        });
        
        // Remove from concepts array
        this.currentSpec.concepts = this.currentSpec.concepts.filter(
            concept => !textsToDelete.has(concept.text)
        );
        
        // Remove connections involving deleted nodes
        if (Array.isArray(this.currentSpec.connections)) {
            this.currentSpec.connections = this.currentSpec.connections.filter(
                conn => !textsToDelete.has(conn.from) && !textsToDelete.has(conn.to)
            );
        }
        
        console.log(`Deleted ${textsToDelete.size} concept node(s) from Concept Map`);
        
        // Re-render to update layout and connections
        this.renderDiagram();
    }
    
    /**
     * Delete generic nodes (for other diagram types)
     */
    deleteGenericNodes(nodeIds) {
        // Remove both the shape and associated text for each node
        nodeIds.forEach(nodeId => {
            // Remove the shape element
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const shapeNode = shapeElement.node();
                
                // Check if inside a group
                if (shapeNode.parentNode && shapeNode.parentNode.tagName === 'g') {
                    // Remove the entire group (shape + text together)
                    d3.select(shapeNode.parentNode).remove();
                } else {
                    // Remove associated text (next sibling)
                    if (shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                        d3.select(shapeNode.nextElementSibling).remove();
                    }
                    
                    // Also check for text by data-text-for attribute
                    d3.select(`[data-text-for="${nodeId}"]`).remove();
                    
                    // Remove the shape
                    shapeElement.remove();
                }
            }
            
            // Also try to remove by text-id (in case it's a text selection)
            d3.select(`[data-text-id="${nodeId}"]`).remove();
        });
        
        console.log(`Deleted ${nodeIds.length} generic node(s) - DOM only (no spec update)`);
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

