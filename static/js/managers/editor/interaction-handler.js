/**
 * Interaction Handler
 * ===================
 * 
 * Manages user interactions with diagram nodes: selection, drag, click, text editing.
 * Handles node selection (single/multi-select), drag behavior for concept maps, and text editing.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class InteractionHandler {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor; // Need editor reference for SelectionManager and openNodeEditor
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'InteractionHandler';
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('InteractionHandler', 'Interaction Handler initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for diagram rendered to attach handlers
        this.eventBus.onWithOwner('diagram:rendered', () => {
            this.attachInteractionHandlers();
        }, this.ownerId);
        
        // Listen for node selection requests
        this.eventBus.onWithOwner('interaction:select_node_requested', (data) => {
            this.selectNode(data.nodeId, data.multiSelect);
        }, this.ownerId);
        
        // Listen for text editing requests
        this.eventBus.onWithOwner('interaction:edit_text_requested', (data) => {
            this.startTextEditing(data.nodeId);
        }, this.ownerId);
        
        // Listen for selection clear requests
        this.eventBus.onWithOwner('interaction:clear_selection_requested', () => {
            this.clearSelection();
        }, this.ownerId);
        
        // Listen for handler attachment requests (for dynamically added nodes)
        this.eventBus.onWithOwner('interaction:attach_handlers_requested', () => {
            this.attachInteractionHandlers();
        }, this.ownerId);
        
        this.logger.debug('InteractionHandler', 'Subscribed to events');
    }
    
    /**
     * Attach interaction handlers to rendered elements
     */
    attachInteractionHandlers() {
        if (!this.editor || !this.editor.selectionManager) {
            // Editor might not be fully initialized yet - retry after a short delay
            // This can happen if diagram:rendered is emitted before editor is ready
            // Use debug level instead of warn to reduce noise (retry will handle it)
            this.logger.debug('InteractionHandler', 'Editor or SelectionManager not available yet - retrying...');
            setTimeout(() => {
                if (this.editor && this.editor.selectionManager) {
                    this.attachInteractionHandlers();
                } else {
                    this.logger.debug('InteractionHandler', 'Editor or SelectionManager still not available - will retry on next render');
                }
            }, 100);
            return;
        }
        
        const self = this;
        const selectionManager = this.editor.selectionManager;
        const diagramType = this.editor.diagramType;
        
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
                    
                    this.logger.debug('InteractionHandler', 'Mouse Click', {
                        nodeId,
                        ctrlKey: event.ctrlKey,
                        metaKey: event.metaKey,
                        diagramType: diagramType
                    });
                    
                    if (event.ctrlKey || event.metaKey) {
                        selectionManager.toggleNodeSelection(nodeId);
                    } else {
                        selectionManager.clearSelection();
                        selectionManager.selectNode(nodeId);
                    }
                    
                    // Emit selection changed event
                    self.emitSelectionChanged();
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                    
                    this.logger.debug('InteractionHandler', 'Double-Click for Edit', {
                        nodeId,
                        diagramType: diagramType
                    });
                    
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
                    // Skip opacity animation for mindmap nodes (topic, branch, and child)
                    // to keep connection lines visible
                    const nodeType = element.attr('data-node-type');
                    const isMindMapNode = diagramType === 'mindmap' && 
                        (nodeType === 'topic' || nodeType === 'branch' || nodeType === 'child');
                    
                    if (!isMindMapNode) {
                        d3.select(this).style('opacity', 0.8);
                    }
                })
                .on('mouseout', function() {
                    // Skip opacity animation for mindmap nodes (topic, branch, and child)
                    const nodeType = element.attr('data-node-type');
                    const isMindMapNode = diagramType === 'mindmap' && 
                        (nodeType === 'topic' || nodeType === 'branch' || nodeType === 'child');
                    
                    if (!isMindMapNode) {
                        d3.select(this).style('opacity', 1);
                    }
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
                            selectionManager.toggleNodeSelection(ownNodeId);
                        } else {
                            selectionManager.clearSelection();
                            selectionManager.selectNode(ownNodeId);
                        }
                        
                        // Emit selection changed event
                        self.emitSelectionChanged();
                    })
                    .on('dblclick', (event) => {
                        event.stopPropagation();
                        const currentText = element.text();
                        // For standalone text elements, the text element is both the shape and text
                        self.openNodeEditor(ownNodeId, textNode, textNode, currentText);
                    })
                    .on('mouseover', function() {
                        // Skip opacity animation for mindmap nodes
                        const nodeType = element.attr('data-node-type');
                        const isMindMapNode = diagramType === 'mindmap' && 
                            (nodeType === 'topic' || nodeType === 'branch' || nodeType === 'child');
                        
                        if (!isMindMapNode) {
                            d3.select(this).style('opacity', 0.8);
                        }
                    })
                    .on('mouseout', function() {
                        // Skip opacity animation for mindmap nodes
                        const nodeType = element.attr('data-node-type');
                        const isMindMapNode = diagramType === 'mindmap' && 
                            (nodeType === 'topic' || nodeType === 'branch' || nodeType === 'child');
                        
                        if (!isMindMapNode) {
                            d3.select(this).style('opacity', 1);
                        }
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
                            selectionManager.toggleNodeSelection(associatedNodeId);
                        } else {
                            selectionManager.clearSelection();
                            selectionManager.selectNode(associatedNodeId);
                        }
                        
                        // Emit selection changed event
                        self.emitSelectionChanged();
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
        
        // Emit event that handlers are attached
        this.eventBus.emit('interaction:handlers_attached');
    }
    
    /**
     * Add drag behavior to a node and its text
     * Only applies to concept maps - other diagram types have fixed layouts
     */
    addDragBehavior(shapeElement, textElement) {
        if (!this.editor) {
            return;
        }
        
        const diagramType = this.editor.diagramType;
        
        // Only allow dragging for concept maps
        if (diagramType !== 'concept_map') {
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
                
                self.logger.debug('InteractionHandler', 'Drag Start', {
                    nodeId,
                    diagramType: diagramType,
                    mouseX: event.x,
                    mouseY: event.y
                });
                
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
                
                // Emit drag started event
                self.eventBus.emit('interaction:drag_started', {
                    nodeId,
                    position: { x: startX, y: startY }
                });
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
                const nodeId = d3.select(this).attr('data-node-id');
                
                self.logger.debug('InteractionHandler', 'Drag End', {
                    nodeId,
                    finalX: startX,
                    finalY: startY,
                    diagramType: diagramType
                });
                
                d3.select(this).style('opacity', 1);
                connectedLines = []; // Clear references
                
                // Emit drag ended event (for history saving)
                self.eventBus.emit('interaction:drag_ended', {
                    nodeId,
                    position: { x: startX, y: startY }
                });
                
                // Emit operation completed for history (if editor has currentSpec)
                if (self.editor && self.editor.currentSpec) {
                    self.eventBus.emit('diagram:operation_completed', {
                        operation: 'move_node',
                        snapshot: JSON.parse(JSON.stringify(self.editor.currentSpec)),
                        data: {
                            nodeId: nodeId,
                            x: startX,
                            y: startY
                        }
                    });
                }
                
                // Update state manager (drag position is saved to history, no need to update state)
                // State manager tracks selection, not node positions
            });
        
        shapeElement.call(drag);
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
     * Select a node
     */
    selectNode(nodeId, multiSelect = false) {
        if (!this.editor || !this.editor.selectionManager) {
            return;
        }
        
        if (multiSelect) {
            this.editor.selectionManager.toggleNodeSelection(nodeId);
        } else {
            this.editor.selectionManager.clearSelection();
            this.editor.selectionManager.selectNode(nodeId);
        }
        
        this.emitSelectionChanged();
    }
    
    /**
     * Clear selection
     */
    clearSelection() {
        if (!this.editor || !this.editor.selectionManager) {
            return;
        }
        
        this.editor.selectionManager.clearSelection();
        this.emitSelectionChanged();
    }
    
    /**
     * Start text editing
     */
    startTextEditing(nodeId) {
        if (!this.editor || !this.editor.openNodeEditor) {
            this.logger.warn('InteractionHandler', 'Editor or openNodeEditor not available');
            return;
        }
        
        // Find the node and text elements
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            return;
        }
        
        const shapeNode = shapeElement.node();
        const textNode = shapeNode.nextElementSibling;
        let currentText = 'Edit me';
        
        if (textNode && textNode.tagName === 'text') {
            currentText = d3.select(textNode).text();
            this.editor.openNodeEditor(nodeId, shapeNode, textNode, currentText);
        } else {
            currentText = this.findTextForNode(shapeNode);
            this.editor.openNodeEditor(nodeId, shapeNode, null, currentText);
        }
    }
    
    /**
     * Open node editor (delegates to editor)
     */
    openNodeEditor(nodeId, shapeNode, textNode, currentText) {
        if (!this.editor || !this.editor.openNodeEditor) {
            this.logger.warn('InteractionHandler', 'Editor or openNodeEditor not available');
            return;
        }
        
        this.editor.openNodeEditor(nodeId, shapeNode, textNode, currentText);
    }
    
    /**
     * Emit selection changed event and update state
     */
    emitSelectionChanged() {
        if (!this.editor || !this.editor.selectionManager) {
            return;
        }
        
        const selectedNodes = Array.from(this.editor.selectionManager.selectedNodes);
        
        // Update state manager (use updateDiagram method)
        if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
            this.stateManager.updateDiagram({
                selectedNodes: selectedNodes
            });
        }
        
        // Emit selection changed event
        this.eventBus.emit('interaction:selection_changed', {
            selectedNodes: selectedNodes
        });
    }
    
    /**
     * Cleanup on destroy
     */
    destroy() {
        this.logger.debug('InteractionHandler', 'Destroying');
        
        // Remove all Event Bus listeners
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('InteractionHandler', `Removed ${removedCount} listeners`);
            }
        }
        
        // Remove all interaction handlers (D3 will handle cleanup when elements are removed)
        // No explicit cleanup needed as handlers are attached to DOM elements
        
        // Clear references
        this.editor = null;
    }
}

