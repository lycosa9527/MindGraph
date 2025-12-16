/**
 * Drag Drop Manager
 * ==================
 * 
 * Manages universal drag-and-drop functionality for all diagram types.
 * Supports two modes:
 * 1. Hierarchical Moves: Move nodes between branches/containers (mindmaps, tree maps, etc.)
 * 2. Free-Form Positioning: Drag nodes to any position with real-time adaptation (bubble maps, etc.)
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class DragDropManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'DragDropManager';
        
        // Drag state
        this.isDragging = false;
        this.dragMode = null; // 'hierarchical' or 'free-form'
        this.draggedNode = null;
        this.draggedNodeId = null;
        this.draggedNodeType = null;
        this.diagramType = null;
        
        // Document-level mouse tracking handlers
        this.documentMouseMoveHandler = null;
        this.documentMouseUpHandler = null;
        this._processingDragEnd = false; // Flag to prevent duplicate drag end calls
        
        // Hierarchical mode state
        this.sourceBranchIndex = null;
        this.sourceChildIndex = null;
        this.currentDropTarget = null;
        this.dropZoneHighlights = [];
        
        // Free-form mode state
        this.forceSimulation = null;
        this.dragClone = null;
        this.originalNodeOpacity = null;
        this.customPositions = {};
        
        // Hold timer for drag activation
        this.holdTimer = null;
        this.holdDuration = 1000; // 1 second
        this.initialMouseX = null;
        this.initialMouseY = null;
        this.moveThreshold = 10; // pixels
        
        // RequestAnimationFrame throttling
        this.rafId = null;
        
        this.logger.info('DragDropManager', 'Drag Drop Manager initialized');
    }
    
    /**
     * Determine drag mode based on diagram type
     * @param {string} diagramType - Diagram type
     * @returns {string} 'hierarchical' or 'free-form'
     */
    getDragMode(diagramType) {
        const hierarchicalTypes = ['mindmap', 'tree_map', 'flow_map', 'brace_map'];
        return hierarchicalTypes.includes(diagramType) ? 'hierarchical' : 'free-form';
    }
    
    /**
     * Check if a node is draggable
     * @param {string} nodeType - Node type attribute
     * @param {string} nodeId - Node ID
     * @param {string} diagramType - Diagram type
     * @returns {boolean} Whether node is draggable
     */
    isNodeDraggable(nodeType, nodeId, diagramType) {
        // Non-draggable central nodes
        const nonDraggableTypes = ['topic', 'center', 'title', 'event', 'dimension'];
        if (nonDraggableTypes.includes(nodeType)) {
            return false;
        }
        
        // Special cases for Double Bubble Map
        if (diagramType === 'double_bubble_map') {
            // Only topic_left and topic_right are non-draggable (check node ID)
            if (nodeId && (nodeId.includes('topic_left') || nodeId.includes('topic_right'))) {
                return false;
            }
        }
        
        // Special case for Circle Map - exclude boundary (decorative outer circle)
        if (diagramType === 'circle_map' && nodeType === 'boundary') {
            return false;
        }
        
        // Special case for Bridge Map - left and right ARE draggable (they're analogy pairs)
        // Dimension is not draggable (central label)
        if (diagramType === 'bridge_map' && nodeType === 'dimension') {
            return false;
        }
        
        return true;
    }
    
    /**
     * Start drag operation
     * @param {Object} nodeElement - D3 selection of node element
     * @param {Object} textElement - D3 selection of text element (optional)
     * @param {string} nodeId - Node ID
     * @param {string} nodeType - Node type
     * @param {string} diagramType - Diagram type
     */
    startDrag(nodeElement, textElement, nodeId, nodeType, diagramType) {
        // Verbose logging for double bubble map
        if (diagramType === 'double_bubble_map') {
            this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - startDrag() called', {
                nodeId,
                nodeType,
                diagramType,
                isDragging: this.isDragging,
                dragMode: this.dragMode,
                hasNodeElement: !!nodeElement,
                hasTextElement: !!textElement,
                processingDragEnd: this._processingDragEnd
            });
        }
        
        if (this.isDragging) {
            this.logger.warn('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Drag already in progress, blocking new drag', {
                currentDragMode: this.dragMode,
                currentDraggedNodeId: this.draggedNodeId,
                attemptedNodeId: nodeId,
                diagramType
            });
            return;
        }
        
        if (!this.isNodeDraggable(nodeType, nodeId, diagramType)) {
            this.logger.debug('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Node is not draggable', { nodeId, nodeType, diagramType });
            return;
        }
        
        this.isDragging = true;
        this.dragMode = this.getDragMode(diagramType);
        this.draggedNode = nodeElement;
        this.draggedNodeId = nodeId;
        this.draggedNodeType = nodeType;
        this.diagramType = diagramType;
        
        // Store original positions for comparison (before drag)
        this.originalPositions = null;
        if (diagramType === 'circle_map' || diagramType === 'bubble_map' || diagramType === 'double_bubble_map') {
            // CRITICAL: Use diagram-specific node array to avoid cross-contamination between sessions
            let originalNodes = null;
            if (diagramType === 'circle_map') {
                originalNodes = window.circleMapNodes;
            } else if (diagramType === 'bubble_map') {
                originalNodes = window.bubbleMapNodes;
            } else if (diagramType === 'double_bubble_map') {
                originalNodes = window.doubleBubbleMapNodes;
            }
            
            if (originalNodes) {
                this.originalPositions = originalNodes.map(n => ({
                    nodeId: n.nodeId || (diagramType === 'circle_map' ? `context_${n.id}` : 
                                         diagramType === 'double_bubble_map' ? n.nodeId : 
                                         `attribute_${n.id}`),
                    x: Math.round(n.x),
                    y: Math.round(n.y),
                    type: n.type
                })).sort((a, b) => a.nodeId.localeCompare(b.nodeId));
                
                // VERBOSE LOGGING: Log original positions when drag starts
                if (diagramType === 'bubble_map') {
                    console.log('[DragDropManager] 🔵 BUBBLE MAP DRAG START - Original positions stored:', {
                        draggedNodeId: nodeId,
                        totalNodes: originalNodes.length,
                        originalPositions: this.originalPositions.map(p => ({
                            nodeId: p.nodeId,
                            x: p.x,
                            y: p.y,
                            isDragged: p.nodeId === nodeId
                        }))
                    });
                } else if (diagramType === 'double_bubble_map') {
                    this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP DRAG START - Original positions stored', {
                        draggedNodeId: nodeId,
                        totalNodes: originalNodes.length,
                        originalPositions: this.originalPositions
                    });
                }
            }
        }
        
        this.logger.info('DragDropManager', 'Drag started', {
            nodeId,
            nodeType,
            diagramType,
            dragMode: this.dragMode,
            originalPositions: this.originalPositions
        });
        
        // Store original opacity
        this.originalNodeOpacity = nodeElement.style('opacity') || '1';
        
        // Dim original node
        nodeElement.style('opacity', '0.3');
        
        // Create drag clone for visual feedback
        this.createDragClone(nodeElement, textElement);
        
        // Initialize mode-specific drag behavior
        if (this.dragMode === 'hierarchical') {
            this.initializeHierarchicalDrag(nodeElement, nodeId, nodeType);
        } else {
            this.initializeFreeFormDrag(nodeElement, nodeId, nodeType, diagramType);
        }
        
        // Emit drag started event
        this.eventBus.emit('drag:started', {
            nodeId,
            nodeType,
            diagramType,
            dragMode: this.dragMode
        });
    }
    
    /**
     * Create drag clone for visual feedback
     */
    createDragClone(nodeElement, textElement) {
        const node = nodeElement.node();
        
        // Get current position - handle both grouped and individual elements
        let currentX, currentY;
        const parentNode = node.parentNode;
        
        if (parentNode && parentNode.tagName === 'g') {
            // For grouped elements, get the group's transform
            const transform = d3.select(parentNode).attr('transform') || 'translate(0,0)';
            const matches = transform.match(/translate\(([^,]+),([^)]+)\)/);
            if (matches) {
                currentX = parseFloat(matches[1]);
                currentY = parseFloat(matches[2]);
            } else {
                currentX = 0;
                currentY = 0;
            }
        } else {
            // For individual elements, get position from attributes
            const tagName = node.tagName.toLowerCase();
            if (tagName === 'circle') {
                currentX = parseFloat(nodeElement.attr('cx')) || 0;
                currentY = parseFloat(nodeElement.attr('cy')) || 0;
            } else if (tagName === 'rect') {
                const width = parseFloat(nodeElement.attr('width')) || 0;
                const height = parseFloat(nodeElement.attr('height')) || 0;
                currentX = parseFloat(nodeElement.attr('x')) + width / 2;
                currentY = parseFloat(nodeElement.attr('y')) + height / 2;
            } else if (tagName === 'ellipse') {
                currentX = parseFloat(nodeElement.attr('cx')) || 0;
                currentY = parseFloat(nodeElement.attr('cy')) || 0;
            } else {
                currentX = 0;
                currentY = 0;
            }
        }
        
        // Store initial position for drag offset calculation
        this.cloneInitialX = currentX;
        this.cloneInitialY = currentY;
        
        // Create clone group at initial position
        const svg = d3.select('#d3-container svg');
        this.dragClone = svg.append('g')
            .attr('class', 'drag-clone')
            .attr('transform', `translate(${currentX}, ${currentY})`)
            .style('opacity', 0.7)
            .style('pointer-events', 'all')
            .style('cursor', 'grabbing');
        
        // Clone shape (centered at origin since we use transform)
        const tagName = node.tagName.toLowerCase();
        let cloneShape;
        
        if (tagName === 'circle') {
            const r = parseFloat(nodeElement.attr('r'));
            cloneShape = this.dragClone.append('circle')
                .attr('cx', 0)
                .attr('cy', 0)
                .attr('r', r)
                .attr('fill', nodeElement.attr('fill'))
                .attr('stroke', nodeElement.attr('stroke'))
                .attr('stroke-width', nodeElement.attr('stroke-width'));
        } else if (tagName === 'rect') {
            const width = parseFloat(nodeElement.attr('width')) || 0;
            const height = parseFloat(nodeElement.attr('height')) || 0;
            cloneShape = this.dragClone.append('rect')
                .attr('x', -width / 2)
                .attr('y', -height / 2)
                .attr('width', width)
                .attr('height', height)
                .attr('fill', nodeElement.attr('fill'))
                .attr('stroke', nodeElement.attr('stroke'))
                .attr('stroke-width', nodeElement.attr('stroke-width'))
                .attr('rx', nodeElement.attr('rx'))
                .attr('ry', nodeElement.attr('ry'));
        } else if (tagName === 'ellipse') {
            const rx = parseFloat(nodeElement.attr('rx'));
            const ry = parseFloat(nodeElement.attr('ry'));
            cloneShape = this.dragClone.append('ellipse')
                .attr('cx', 0)
                .attr('cy', 0)
                .attr('rx', rx)
                .attr('ry', ry)
                .attr('fill', nodeElement.attr('fill'))
                .attr('stroke', nodeElement.attr('stroke'))
                .attr('stroke-width', nodeElement.attr('stroke-width'));
        }
        
        // Clone text if exists
        if (textElement && !textElement.empty()) {
            const textContent = (typeof window.extractTextFromSVG === 'function')
                ? window.extractTextFromSVG(textElement)
                : textElement.text();
            
            this.dragClone.append('text')
                .attr('x', 0)
                .attr('y', 0)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', textElement.attr('fill'))
                .attr('font-size', textElement.attr('font-size'))
                .attr('font-family', textElement.attr('font-family'))
                .text(textContent);
        }
    }
    
    /**
     * Initialize hierarchical drag mode
     */
    initializeHierarchicalDrag(nodeElement, nodeId, nodeType) {
        // Extract source indices
        if (nodeType === 'child' || nodeType === 'subitem') {
            this.sourceBranchIndex = parseInt(nodeElement.attr('data-branch-index'));
            this.sourceChildIndex = parseInt(nodeElement.attr('data-child-index') || nodeElement.attr('data-array-index'));
        } else if (nodeType === 'branch') {
            this.sourceBranchIndex = parseInt(nodeElement.attr('data-branch-index') || nodeElement.attr('data-array-index'));
        }
        
        // Setup document-level mouse tracking
        this.setupDocumentMouseTracking();
    }
    
    /**
     * Initialize free-form drag mode with real-time force simulation
     */
    initializeFreeFormDrag(nodeElement, nodeId, nodeType, diagramType) {
        // Setup document-level mouse tracking
        this.setupDocumentMouseTracking();
        
        // Initialize force simulation for real-time adaptation
        this.initializeForceSimulation(diagramType, nodeId);
    }
    
    /**
     * Initialize force simulation for real-time adaptation during drag
     */
    initializeForceSimulation(diagramType, nodeId) {
        // Get simulation and nodes from renderer (stored globally)
        if (diagramType === 'bubble_map') {
            this.forceSimulation = window.bubbleMapSimulation;
            this.forceNodes = window.bubbleMapNodes;
            this.forceCentralNode = window.bubbleMapCentralNode;
            
            // Find the dragged node in the simulation
            this.draggedSimulationNode = this.forceNodes.find(n => n.nodeId === nodeId);
            
            // VERBOSE LOGGING: Log all original positions when drag starts
            if (this.forceNodes && this.forceNodes.length > 0) {
                const originalPositions = this.forceNodes.map(node => ({
                    nodeId: node.nodeId || `attribute_${node.id}`,
                    x: Math.round(node.x),
                    y: Math.round(node.y),
                    isDragged: node.nodeId === nodeId
                }));
                
                console.log('[DragDropManager] 🔵 BUBBLE MAP DRAG START - Original positions:', {
                    draggedNodeId: nodeId,
                    totalNodes: this.forceNodes.length,
                    positions: originalPositions,
                    boundaries: window.bubbleMapBoundaries ? {
                        centerX: Math.round(window.bubbleMapBoundaries.centerX),
                        centerY: Math.round(window.bubbleMapBoundaries.centerY),
                        innerRadius: Math.round(window.bubbleMapBoundaries.innerRadius),
                        outerRadius: Math.round(window.bubbleMapBoundaries.outerRadius)
                    } : null
                });
            }
            
            if (this.forceSimulation && this.draggedSimulationNode) {
                // Setup tick handler for real-time updates
                this.forceSimulation.on('tick', () => {
                    this.updateFreeFormPositions();
                });
            }
        } else if (diagramType === 'circle_map') {
            // Circle map force simulation - enable "marbles in a donut" effect
            this.forceSimulation = window.circleMapSimulation;
            this.forceNodes = window.circleMapNodes;
            this.forceCentralNode = window.circleMapCentralNode;
            
            // Find the dragged node in the simulation
            this.draggedSimulationNode = this.forceNodes?.find(n => n.nodeId === nodeId);
            
            this.logger.info('DragDropManager', 'Circle map simulation initialization', {
                hasSimulation: !!this.forceSimulation,
                hasNodes: !!this.forceNodes,
                nodeCount: this.forceNodes?.length || 0,
                foundDraggedNode: !!this.draggedSimulationNode,
                nodeIds: this.forceNodes?.map(n => n.nodeId) || [],
                targetNodeId: nodeId,
                windowHasSimulation: !!window.circleMapSimulation,
                windowHasNodes: !!window.circleMapNodes
            });
            
            if (!this.forceSimulation) {
                this.logger.error('DragDropManager', 'Circle map simulation not found in window', {
                    availableKeys: Object.keys(window).filter(k => k.includes('circle') || k.includes('Circle'))
                });
            }
            
            if (!this.draggedSimulationNode && this.forceNodes) {
                this.logger.error('DragDropManager', 'Dragged node not found in simulation nodes', {
                    targetNodeId: nodeId,
                    availableNodeIds: this.forceNodes.map(n => n.nodeId)
                });
            }
            
            if (this.forceSimulation && this.draggedSimulationNode) {
                // Clear any existing tick handlers
                this.forceSimulation.on('tick', null);
                
                // Setup tick handler for real-time updates during drag
                // This creates the "marbles shuffling" effect
                this.forceSimulation.on('tick', () => {
                    this.updateFreeFormPositions();
                });
                
                // Start simulation running continuously during drag
                this.forceSimulation.alpha(1).restart();
            }
        } else if (diagramType === 'double_bubble_map') {
            // Double bubble map - use force simulation for marbles effect within columns
            // Get fresh references from window (they may have been updated after re-render)
            this.forceSimulation = window.doubleBubbleMapSimulation;
            this.forceNodes = window.doubleBubbleMapNodes;
            this.forceCentralNodes = window.doubleBubbleMapCentralNodes;
            
            this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Initializing force simulation', {
                nodeId,
                hasSimulation: !!this.forceSimulation,
                hasNodes: !!this.forceNodes,
                nodeCount: this.forceNodes?.length || 0,
                hasCentralNodes: !!this.forceCentralNodes,
                hasLeftTopic: !!this.forceCentralNodes?.left,
                hasRightTopic: !!this.forceCentralNodes?.right,
                windowHasSimulation: !!window.doubleBubbleMapSimulation,
                windowHasNodes: !!window.doubleBubbleMapNodes,
                windowNodeCount: window.doubleBubbleMapNodes?.length || 0
            });
            
            // Validate that we have valid references
            if (!this.forceSimulation) {
                this.logger.error('DragDropManager', 'Double bubble map simulation not found in window');
                return;
            }
            if (!this.forceNodes || this.forceNodes.length === 0) {
                this.logger.error('DragDropManager', 'Double bubble map nodes not found in window', {
                    hasNodes: !!window.doubleBubbleMapNodes,
                    nodeCount: window.doubleBubbleMapNodes?.length || 0
                });
                return;
            }
            if (!this.forceCentralNodes || !this.forceCentralNodes.left || !this.forceCentralNodes.right) {
                this.logger.error('DragDropManager', 'Double bubble map central nodes not found in window', {
                    hasCentralNodes: !!this.forceCentralNodes,
                    hasLeft: !!this.forceCentralNodes?.left,
                    hasRight: !!this.forceCentralNodes?.right
                });
                return;
            }
            
            // Log all nodes with their initial positions
            const nodePositions = this.forceNodes.map(n => ({
                nodeId: n.nodeId,
                type: n.type,
                x: Math.round(n.x),
                y: Math.round(n.y),
                fx: n.fx,
                fy: n.fy,
                radius: n.radius
            }));
            const centralPositions = {
                left: {
                    x: Math.round(this.forceCentralNodes.left.x),
                    y: Math.round(this.forceCentralNodes.left.y),
                    radius: this.forceCentralNodes.left.radius
                },
                right: {
                    x: Math.round(this.forceCentralNodes.right.x),
                    y: Math.round(this.forceCentralNodes.right.y),
                    radius: this.forceCentralNodes.right.radius
                }
            };
            
            this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Node positions at drag start', {
                draggedNodeId: nodeId,
                totalNodes: this.forceNodes.length,
                nodePositions,
                centralPositions
            });
            
            // Find the dragged node in the simulation
            this.draggedSimulationNode = this.forceNodes.find(n => n.nodeId === nodeId);
            
            if (!this.draggedSimulationNode) {
                this.logger.error('DragDropManager', 'Dragged node not found in simulation', {
                    nodeId,
                    availableNodeIds: this.forceNodes.map(n => n.nodeId)
                });
                return;
            }
            
            this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Dragged node found', {
                nodeId: this.draggedSimulationNode.nodeId,
                type: this.draggedSimulationNode.type,
                x: Math.round(this.draggedSimulationNode.x),
                y: Math.round(this.draggedSimulationNode.y),
                fx: this.draggedSimulationNode.fx,
                fy: this.draggedSimulationNode.fy
            });
            
            if (this.forceSimulation && this.draggedSimulationNode) {
                // CRITICAL: Release all nodes from fixed positions (fx/fy) to allow dragging
                // Nodes might have been fixed to custom positions during render
                this.forceNodes.forEach(node => {
                    // Only release draggable nodes, not central topics
                    if (node.type !== 'left' && node.type !== 'right' && node.nodeId !== 'topic_left' && node.nodeId !== 'topic_right') {
                        node.fx = null;
                        node.fy = null;
                    }
                });
                
                // Clear any existing tick handlers (don't stop simulation - let it decay naturally)
                this.forceSimulation.on('tick', null);
                
                // Setup tick handler for real-time updates during drag
                // This creates the "marbles shuffling" effect within columns
                // updateFreeFormPositions() already updates all connection lines
                this.forceSimulation.on('tick', () => {
                    this.updateFreeFormPositions();
                });
                
                // Start simulation running continuously during drag
                this.forceSimulation.alpha(1).restart();
                
                this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Force simulation started', {
                    alpha: this.forceSimulation.alpha(),
                    hasTickHandler: true,
                    nodesReleased: this.forceNodes.filter(n => n.fx === null && n.fy === null).length,
                    totalNodes: this.forceNodes.length
                });
            }
        } else if (diagramType === 'multi_flow_map') {
            // Multi-flow map - store node references (no force simulation for side layout)
            this.forceNodes = window.multiFlowMapNodes;
            this.draggedSimulationNode = this.forceNodes?.find(n => n.nodeId === nodeId);
            
            // For multi-flow map, we'll update positions directly without force simulation
            // since it uses a side-based layout (causes left, effects right)
        } else if (diagramType === 'bridge_map') {
            // Bridge map - store node references (no force simulation for horizontal layout)
            this.forceNodes = window.bridgeMapNodes;
            this.draggedSimulationNode = this.forceNodes?.find(n => n.nodeId === nodeId);
            
            // For bridge map, we'll update positions directly without force simulation
            // since it uses a horizontal layout
        }
    }
    
    /**
     * Update node positions during free-form drag (called on simulation tick)
     */
    updateFreeFormPositions() {
        if (!this.forceNodes || !this.forceSimulation) return;
        
        // Update all node positions in DOM
        this.forceNodes.forEach(node => {
            const nodeId = node.nodeId || (this.diagramType === 'circle_map' ? `context_${node.id}` : 
                                          this.diagramType === 'double_bubble_map' ? node.nodeId : 
                                          `attribute_${node.id}`);
            
            // Handle different node types
            if (this.diagramType === 'double_bubble_map') {
                // Circle nodes for double bubble map
            const circleElement = d3.select(`[data-node-id="${nodeId}"]`);
            
            if (!circleElement.empty()) {
                circleElement
                    .attr('cx', node.x)
                    .attr('cy', node.y);
                }
            } else {
                // Circle nodes for bubble/circle maps
                const circleElement = d3.select(`[data-node-id="${nodeId}"]`);
                
                if (!circleElement.empty()) {
                    circleElement
                        .attr('cx', node.x)
                        .attr('cy', node.y);
                }
            }
            
            // Update text positions - handle both single and multiple text elements
            const textElements = d3.selectAll(`[data-text-for="${nodeId}"]`);
            
            if (!textElements.empty()) {
                const textNodes = textElements.nodes();
                // Get font size from first text element
                const fontSize = parseFloat(textElements.attr('font-size')) || 14;
                const lineHeight = fontSize * 1.2;
                const numLines = textNodes.length;
                const startY = node.y - (numLines - 1) * lineHeight / 2;
                
                textNodes.forEach((line, i) => {
                    d3.select(line)
                        .attr('x', node.x)
                        .attr('y', startY + i * lineHeight);
                });
            }
        });
        
        // Update connection lines (if any)
        if (this.diagramType === 'double_bubble_map') {
            // Update all connection lines for double bubble map
            let linesUpdated = 0;
            this.forceNodes.forEach(node => {
                const linesBefore = d3.selectAll(`line[data-line-for="${node.nodeId}"]`).size();
                this.updateDoubleBubbleLines(node.nodeId, node.x, node.y);
                const linesAfter = d3.selectAll(`line[data-line-for="${node.nodeId}"]`).size();
                if (linesAfter > 0) linesUpdated += linesAfter;
            });
            
            // Verbose logging every 10 ticks to avoid spam
            if (!this._tickCount) this._tickCount = 0;
            this._tickCount++;
            if (this._tickCount % 10 === 0) {
                this.logger.debug('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Position update tick', {
                    tickCount: this._tickCount,
                    nodeCount: this.forceNodes.length,
                    linesUpdated,
                    draggedNode: this.draggedSimulationNode ? {
                        nodeId: this.draggedSimulationNode.nodeId,
                        x: Math.round(this.draggedSimulationNode.x),
                        y: Math.round(this.draggedSimulationNode.y),
                        fx: this.draggedSimulationNode.fx,
                        fy: this.draggedSimulationNode.fy
                    } : null
                });
            }
        } else {
        this.updateConnectionLines();
        }
    }
    
    /**
     * Update connection lines during drag
     */
    updateConnectionLines() {
        if (!this.forceCentralNode || !this.forceNodes) return;
        
        const centerX = this.forceCentralNode.x;
        const centerY = this.forceCentralNode.y;
        const centerR = this.forceCentralNode.radius;
        
        this.forceNodes.forEach(node => {
            const nodeId = node.nodeId || `attribute_${node.id}`;
            const lineElement = d3.select(`line[data-line-for="${nodeId}"]`);
            
            if (!lineElement.empty()) {
                const dx = node.x - centerX;
                const dy = node.y - centerY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist > 0) {
                    const lineStartX = centerX + (dx / dist) * centerR;
                    const lineStartY = centerY + (dy / dist) * centerR;
                    const lineEndX = node.x - (dx / dist) * node.radius;
                    const lineEndY = node.y - (dy / dist) * node.radius;
                    
                    lineElement
                        .attr('x1', lineStartX)
                        .attr('y1', lineStartY)
                        .attr('x2', lineEndX)
                        .attr('y2', lineEndY);
                }
            }
        });
    }
    
    /**
     * Update connection lines for double bubble map during drag
     * Similar to updateConnectionLines but handles two central topics
     */
    updateDoubleBubbleLines(nodeId, nodeX, nodeY) {
        // Find all lines connected to this node
        const lineElements = d3.selectAll(`line[data-line-for="${nodeId}"]`);
        
        if (lineElements.empty()) {
            // Only log if we expect lines (not for central topics)
            if (!nodeId.startsWith('topic_')) {
                this.logger.debug('DragDropManager', 'No connection lines found for node', { nodeId });
            }
            return;
        }
        
        // Get node radius from the node element
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (nodeElement.empty()) {
            this.logger.warn('DragDropManager', 'Node element not found for line update', { nodeId });
            return;
        }
        
        const nodeR = parseFloat(nodeElement.attr('r')) || 0;
        
        // Get central topic positions from DOM (more reliable than stored references)
        const leftTopicElement = d3.select('[data-node-id="topic_left"]');
        const rightTopicElement = d3.select('[data-node-id="topic_right"]');
        
        if (leftTopicElement.empty() || rightTopicElement.empty()) {
            // Fallback: try to get from stored references
            const centralNodes = window.doubleBubbleMapCentralNodes || this.forceCentralNodes;
            if (!centralNodes || !centralNodes.left || !centralNodes.right) return;
            
            const leftTopic = centralNodes.left;
            const rightTopic = centralNodes.right;
            const topicR = leftTopic.radius || rightTopic.radius || 0;
            
            // Update each line based on its type
            lineElements.each(function() {
                const line = d3.select(this);
                const lineType = line.attr('data-line-type');
                
                let topicX, topicY;
                
                if (lineType === 'left-to-similarity' || lineType === 'left-to-left-diff') {
                    topicX = leftTopic.x;
                    topicY = leftTopic.y;
                } else if (lineType === 'right-to-similarity' || lineType === 'right-to-right-diff') {
                    topicX = rightTopic.x;
                    topicY = rightTopic.y;
                } else {
                    return;
                }
                
                const dx = topicX - nodeX;
                const dy = topicY - nodeY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist > 0) {
                    const lineStartX = nodeX + (dx / dist) * nodeR;
                    const lineStartY = nodeY + (dy / dist) * nodeR;
                    const lineEndX = topicX - (dx / dist) * topicR;
                    const lineEndY = topicY - (dy / dist) * topicR;
                    
                    const oldX1 = parseFloat(line.attr('x1')) || 0;
                    const oldY1 = parseFloat(line.attr('y1')) || 0;
                    const oldX2 = parseFloat(line.attr('x2')) || 0;
                    const oldY2 = parseFloat(line.attr('y2')) || 0;
                    
                    line
                        .attr('x1', lineStartX)
                        .attr('y1', lineStartY)
                        .attr('x2', lineEndX)
                        .attr('y2', lineEndY);
                    
                    // Log line update (throttled to avoid spam)
                    if (!this._lineUpdateCount) this._lineUpdateCount = {};
                    if (!this._lineUpdateCount[nodeId]) this._lineUpdateCount[nodeId] = 0;
                    this._lineUpdateCount[nodeId]++;
                    
                    if (this._lineUpdateCount[nodeId] % 20 === 0) {
                        this.logger.debug('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Connection line updated (fallback)', {
                            nodeId,
                            lineType,
                            nodePos: { x: Math.round(nodeX), y: Math.round(nodeY) },
                            topicPos: { x: Math.round(topicX), y: Math.round(topicY) },
                            lineStart: { x: Math.round(lineStartX), y: Math.round(lineStartY) },
                            lineEnd: { x: Math.round(lineEndX), y: Math.round(lineEndY) },
                            updateCount: this._lineUpdateCount[nodeId]
                        });
                    }
                }
            });
            return;
        }
        
        // Get topic positions and radius from DOM
        const leftTopicX = parseFloat(leftTopicElement.attr('cx')) || 0;
        const leftTopicY = parseFloat(leftTopicElement.attr('cy')) || 0;
        const leftTopicR = parseFloat(leftTopicElement.attr('r')) || 0;
        
        const rightTopicX = parseFloat(rightTopicElement.attr('cx')) || 0;
        const rightTopicY = parseFloat(rightTopicElement.attr('cy')) || 0;
        const rightTopicR = parseFloat(rightTopicElement.attr('r')) || 0;
        
        // Update each line based on its type
        const self = this;
        let linesUpdatedForNode = 0;
        lineElements.each(function() {
            const line = d3.select(this);
            const lineType = line.attr('data-line-type');
            
            let topicX, topicY, topicR;
            
            // Determine which topic this line connects to
            if (lineType === 'left-to-similarity' || lineType === 'left-to-left-diff') {
                topicX = leftTopicX;
                topicY = leftTopicY;
                topicR = leftTopicR;
            } else if (lineType === 'right-to-similarity' || lineType === 'right-to-right-diff') {
                topicX = rightTopicX;
                topicY = rightTopicY;
                topicR = rightTopicR;
            } else {
                return; // Unknown line type
            }
            
            // Calculate direction vector from node to topic
            const dx = topicX - nodeX;
            const dy = topicY - nodeY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            
            if (dist > 0) {
                // Line starts at node edge (pointing towards topic)
                const lineStartX = nodeX + (dx / dist) * nodeR;
                const lineStartY = nodeY + (dy / dist) * nodeR;
                
                // Line ends at topic edge (pointing towards node)
                const lineEndX = topicX - (dx / dist) * topicR;
                const lineEndY = topicY - (dy / dist) * topicR;
                
                // Update line coordinates
                line
                    .attr('x1', lineStartX)
                    .attr('y1', lineStartY)
                    .attr('x2', lineEndX)
                    .attr('y2', lineEndY);
                
                linesUpdatedForNode++;
            }
        });
        
        // Log line updates (throttled to avoid spam)
        if (!self._lineUpdateCount) self._lineUpdateCount = {};
        if (!self._lineUpdateCount[nodeId]) self._lineUpdateCount[nodeId] = 0;
        self._lineUpdateCount[nodeId]++;
        
        if (self._lineUpdateCount[nodeId] % 20 === 0) {
            self.logger.debug('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Connection lines updated', {
                nodeId,
                linesCount: linesUpdatedForNode,
                nodePos: { x: Math.round(nodeX), y: Math.round(nodeY) },
                leftTopicPos: { x: Math.round(leftTopicX), y: Math.round(leftTopicY) },
                rightTopicPos: { x: Math.round(rightTopicX), y: Math.round(rightTopicY) },
                updateCount: self._lineUpdateCount[nodeId]
            });
        }
    }
    
    /**
     * Setup document-level mouse tracking for drag operations
     */
    setupDocumentMouseTracking() {
        const self = this;
        
        // Create mouse move handler
        this.documentMouseMoveHandler = (event) => {
            if (!self.isDragging) return;
            
            // Create a mock event object for compatibility
            const mockEvent = {
                sourceEvent: event,
                x: event.clientX,
                y: event.clientY
            };
            
            if (self.dragMode === 'hierarchical') {
                self.onHierarchicalDrag(mockEvent);
            } else {
                self.onFreeFormDrag(mockEvent);
            }
        };
        
        // Create mouse up handler
        this.documentMouseUpHandler = (event) => {
            self.logger.info('DragDropManager', 'Document mouseup event', {
                isDragging: self.isDragging,
                dragMode: self.dragMode,
                diagramType: self.diagramType,
                processingDragEnd: self._processingDragEnd
            });
            
            if (!self.isDragging || self._processingDragEnd) {
                // Remove handler immediately if not dragging or already processing
                if (self.documentMouseUpHandler) {
                    document.removeEventListener('mouseup', self.documentMouseUpHandler);
                    self.documentMouseUpHandler = null;
                }
                return;
            }
            
            // Remove handler IMMEDIATELY to prevent duplicate calls
            if (self.documentMouseUpHandler) {
                document.removeEventListener('mouseup', self.documentMouseUpHandler);
                self.documentMouseUpHandler = null;
            }
            
            // Create a mock event object for compatibility
            const mockEvent = {
                sourceEvent: event,
                x: event.clientX,
                y: event.clientY
            };
            
            if (self.dragMode === 'hierarchical') {
                self.logger.debug('DragDropManager', 'Calling onHierarchicalDragEnd');
                self.onHierarchicalDragEnd(mockEvent);
            } else {
                self.logger.debug('DragDropManager', 'Calling onFreeFormDragEnd');
                self.onFreeFormDragEnd(mockEvent);
            }
        };
        
        // Attach handlers to document
        document.addEventListener('mousemove', this.documentMouseMoveHandler);
        document.addEventListener('mouseup', this.documentMouseUpHandler);
        
        // Prevent text selection during drag
        document.body.style.userSelect = 'none';
    }
    
    /**
     * Handle hierarchical drag move
     */
    onHierarchicalDrag(event) {
        if (!this.isDragging) return;
        
        // Convert event coordinates to SVG coordinates
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) return;
        
        const point = svg.node().createSVGPoint();
        point.x = event.sourceEvent.clientX;
        point.y = event.sourceEvent.clientY;
        const svgPoint = point.matrixTransform(svg.node().getScreenCTM().inverse());
        
        // Update clone position
        if (this.dragClone) {
            this.dragClone.attr('transform', `translate(${svgPoint.x}, ${svgPoint.y})`);
        }
        
        // Detect drop target
        this.updateDropZoneDetection(event);
    }
    
    /**
     * Handle hierarchical drag end
     */
    onHierarchicalDragEnd(event) {
        if (!this.isDragging) return;
        
        // Check if dropped on valid target
        const dropTarget = this.detectDropTarget(event);
        
        if (dropTarget && this.isValidDropTarget(dropTarget)) {
            // Execute move operation
            this.executeHierarchicalMove(dropTarget);
        } else {
            // Cancel drag - return node to original position
            this.cancelDrag();
        }
        
        // Cleanup
        this.endDrag();
    }
    
    /**
     * Handle free-form drag move
     */
    onFreeFormDrag(event) {
        if (!this.isDragging) return;
        
        // Convert event coordinates to SVG coordinates
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) return;
        
        const point = svg.node().createSVGPoint();
        point.x = event.sourceEvent.clientX;
        point.y = event.sourceEvent.clientY;
        const svgPoint = point.matrixTransform(svg.node().getScreenCTM().inverse());
        
        // Update clone position
        if (this.dragClone) {
            this.dragClone.attr('transform', `translate(${svgPoint.x}, ${svgPoint.y})`);
        }
        
        // Update dragged node position
        if (this.diagramType === 'double_bubble_map') {
            // Double bubble map uses force simulation - fix dragged node to cursor
            if (this.draggedSimulationNode && this.forceSimulation) {
                // Get column X positions from stored column info
                const columns = window.doubleBubbleMapColumns;
                if (!columns) {
                    // Fallback: calculate from SVG
                    const svg = d3.select('#d3-container svg');
                    if (!svg.empty()) {
                        const viewBox = svg.attr('viewBox');
                        if (viewBox) {
                            const [x, y, width, height] = viewBox.split(' ').map(Number);
                            columns = {
                                simX: x + width / 2,
                                leftDiffX: x + width * 0.25,
                                rightDiffX: x + width * 0.75
                            };
                        }
                    }
                }
                
                // Constrain X position to node's column (allow vertical movement)
                const nodeType = this.draggedSimulationNode.type;
                let constrainedX = svgPoint.x;
                
                if (columns) {
                    if (nodeType === 'similarity') {
                        // Keep similarities in center column
                        constrainedX = columns.simX;
                    } else if (nodeType === 'left_difference') {
                        // Keep left differences in left column
                        constrainedX = columns.leftDiffX;
                    } else if (nodeType === 'right_difference') {
                        // Keep right differences in right column
                        constrainedX = columns.rightDiffX;
                    }
                }
                
                // Fix dragged node to cursor Y position, but constrain X to column
                // Force simulation will handle collision and shuffling (marbles effect)
                this.draggedSimulationNode.fx = constrainedX;
                this.draggedSimulationNode.fy = svgPoint.y;
                
                // Keep simulation running
                this.forceSimulation.alpha(1).restart();
            }
        } else if (this.diagramType === 'multi_flow_map' || 
            this.diagramType === 'bridge_map') {
            // For these diagrams, update position directly (no force simulation)
            if (this.draggedSimulationNode) {
                this.draggedSimulationNode.x = svgPoint.x;
                this.draggedSimulationNode.y = svgPoint.y;
                
                // Update DOM element position based on node type
                if (this.diagramType === 'multi_flow_map') {
                    // Rectangle nodes
                    const rectElement = d3.select(`[data-node-id="${this.draggedNodeId}"]`);
                    const textElements = d3.selectAll(`[data-text-for="${this.draggedNodeId}"]`);
                    
                    if (!rectElement.empty() && this.draggedSimulationNode.width && this.draggedSimulationNode.height) {
                        rectElement
                            .attr('x', svgPoint.x - this.draggedSimulationNode.width / 2)
                            .attr('y', svgPoint.y - this.draggedSimulationNode.height / 2);
                    }
                    
                    // Update text positions
                    if (!textElements.empty()) {
                        const textNodes = textElements.nodes();
                        const lineHeight = parseFloat(textElements.attr('font-size')) * 1.2 || 14.4;
                        const numLines = textNodes.length;
                        const startY = svgPoint.y - (numLines - 1) * lineHeight / 2;
                        
                        textNodes.forEach((line, i) => {
                            d3.select(line)
                                .attr('x', svgPoint.x)
                                .attr('y', startY + i * lineHeight);
                        });
                    }
                } else if (this.diagramType === 'bridge_map') {
                    // Rectangle nodes for bridge map
                    const rectElement = d3.select(`[data-node-id="${this.draggedNodeId}"]`);
                    const textElements = d3.selectAll(`[data-text-for="${this.draggedNodeId}"]`);
                    
                    if (!rectElement.empty() && this.draggedSimulationNode.width && this.draggedSimulationNode.height) {
                        rectElement
                            .attr('x', svgPoint.x - this.draggedSimulationNode.width / 2)
                            .attr('y', svgPoint.y - this.draggedSimulationNode.height / 2);
                    }
                    
                    // Update text positions
                    if (!textElements.empty()) {
                        const textNodes = textElements.nodes();
                        const lineHeight = parseFloat(textElements.attr('font-size')) * 1.2 || 14.4;
                        const numLines = textNodes.length;
                        const startY = svgPoint.y - (numLines - 1) * lineHeight / 2;
                        
                        textNodes.forEach((line, i) => {
                            d3.select(line)
                                .attr('x', svgPoint.x)
                                .attr('y', startY + i * lineHeight);
                        });
                    }
                }
            }
        } else if (this.forceSimulation && this.draggedSimulationNode) {
            // For circle map and bubble map with force simulation
            // Fix dragged node to cursor position (but constrain to boundary ring)
            if (this.diagramType === 'circle_map') {
                // Constrain dragged position to donut ring using stored boundary info
                const boundaries = window.circleMapBoundaries;
                if (boundaries) {
                    const centerX = boundaries.centerX;
                    const centerY = boundaries.centerY;
                    const dx = svgPoint.x - centerX;
                    const dy = svgPoint.y - centerY;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance > 0) {
                        let constrainedX = svgPoint.x;
                        let constrainedY = svgPoint.y;
                        
                        // Constrain to outer boundary
                        if (distance > boundaries.outerRadius) {
                            const scale = boundaries.outerRadius / distance;
                            constrainedX = centerX + dx * scale;
                            constrainedY = centerY + dy * scale;
                        }
                        
                        // Constrain to inner boundary (donut hole edge)
                        if (distance < boundaries.innerRadius) {
                            const scale = boundaries.innerRadius / distance;
                            constrainedX = centerX + dx * scale;
                            constrainedY = centerY + dy * scale;
                        }
                        
                        this.draggedSimulationNode.fx = constrainedX;
                        this.draggedSimulationNode.fy = constrainedY;
                    } else {
                        // If at center, push to inner radius
                        this.draggedSimulationNode.fx = centerX + boundaries.innerRadius;
                        this.draggedSimulationNode.fy = centerY;
                    }
                } else {
                    // Fallback if boundaries not available
                    this.draggedSimulationNode.fx = svgPoint.x;
                    this.draggedSimulationNode.fy = svgPoint.y;
                }
            } else if (this.diagramType === 'bubble_map') {
                // Constrain dragged position to constraint ring using stored boundary info
                const boundaries = window.bubbleMapBoundaries;
                
                if (boundaries) {
                    const centerX = boundaries.centerX;
                    const centerY = boundaries.centerY;
                    const dx = svgPoint.x - centerX;
                    const dy = svgPoint.y - centerY;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    // Get original position before constraint
                    const originalX = svgPoint.x;
                    const originalY = svgPoint.y;
                    const originalDistance = distance;
                    
                    if (distance > 0) {
                        let constrainedX = svgPoint.x;
                        let constrainedY = svgPoint.y;
                        let wasConstrained = false;
                        let constraintType = null;
                        
                        // Constrain to outer boundary (prevent nodes from going too far)
                        if (distance > boundaries.outerRadius) {
                            const scale = boundaries.outerRadius / distance;
                            constrainedX = centerX + dx * scale;
                            constrainedY = centerY + dy * scale;
                            wasConstrained = true;
                            constraintType = 'outer';
                        }
                        
                        // Constrain to inner boundary (prevent nodes from overlapping central topic)
                        if (distance < boundaries.innerRadius) {
                            const scale = boundaries.innerRadius / distance;
                            constrainedX = centerX + dx * scale;
                            constrainedY = centerY + dy * scale;
                            wasConstrained = true;
                            constraintType = 'inner';
                        }
                        
                        // Verbose logging for drag constraint
                        if (wasConstrained) {
                            const constrainedDistance = Math.sqrt(
                                Math.pow(constrainedX - centerX, 2) + 
                                Math.pow(constrainedY - centerY, 2)
                            );
                            console.log(`[DragDropManager] 🔵 Bubble drag constraint applied (${constraintType}):`, {
                                nodeId: this.draggedSimulationNode.nodeId,
                                originalPosition: { x: Math.round(originalX), y: Math.round(originalY) },
                                originalDistance: Math.round(originalDistance),
                                constrainedPosition: { x: Math.round(constrainedX), y: Math.round(constrainedY) },
                                constrainedDistance: Math.round(constrainedDistance),
                                boundaryRadius: Math.round(constraintType === 'outer' ? boundaries.outerRadius : boundaries.innerRadius),
                                center: { x: Math.round(centerX), y: Math.round(centerY) }
                            });
                        }
                        
                        this.draggedSimulationNode.fx = constrainedX;
                        this.draggedSimulationNode.fy = constrainedY;
                    } else {
                        // If at center, push to inner radius
                        this.draggedSimulationNode.fx = centerX + boundaries.innerRadius;
                        this.draggedSimulationNode.fy = centerY;
                        console.log('[DragDropManager] 🔵 Bubble at center, pushed to inner radius:', {
                            nodeId: this.draggedSimulationNode.nodeId,
                            pushedTo: { x: Math.round(centerX + boundaries.innerRadius), y: Math.round(centerY) },
                            innerRadius: Math.round(boundaries.innerRadius)
                        });
                    }
                } else {
                    // Boundaries should always be set before drag starts
                    // If not available, something went wrong - log error but don't constrain
                    this.logger.error('DragDropManager', 'Bubble map boundaries not available - should be set before drag starts', {
                        hasSimulation: !!window.bubbleMapSimulation,
                        hasNodes: !!window.bubbleMapNodes,
                        hasCentralNode: !!window.bubbleMapCentralNode
                    });
                    this.draggedSimulationNode.fx = svgPoint.x;
                    this.draggedSimulationNode.fy = svgPoint.y;
                }
            } else {
                // For other diagrams, fix to cursor position directly
                this.draggedSimulationNode.fx = svgPoint.x;
                this.draggedSimulationNode.fy = svgPoint.y;
            }
            
            // Restart simulation with high alpha for responsive updates
            this.forceSimulation
                .alpha(1)
                .restart();
        }
    }
    
    /**
     * Handle free-form drag end
     */
    onFreeFormDragEnd(event) {
        // Prevent multiple calls - if already processing drag end, ignore
        if (this._processingDragEnd) {
            this.logger.debug('DragDropManager', 'Drag end already processing, ignoring duplicate call');
            return;
        }
        
        this.logger.info('DragDropManager', 'onFreeFormDragEnd called', {
            isDragging: this.isDragging,
            diagramType: this.diagramType,
            hasForceSimulation: !!this.forceSimulation,
            hasDraggedSimulationNode: !!this.draggedSimulationNode,
            draggedNodeId: this.draggedNodeId
        });
        
        if (!this.isDragging) {
            this.logger.debug('DragDropManager', 'Not dragging, returning early');
            return;
        }
        
        // Mark as processing to prevent duplicate calls
        this._processingDragEnd = true;
        
        // Handle diagrams without force simulation (multi_flow_map and bridge_map)
        // Note: double_bubble_map uses force simulation, so it's handled below
        if ((this.diagramType === 'multi_flow_map' || 
             this.diagramType === 'bridge_map') && 
            this.draggedSimulationNode) {
            // Save position directly
            this.saveFreeFormPosition(
                this.draggedNodeId,
                this.draggedSimulationNode.x,
                this.draggedSimulationNode.y
            );
            this.endDrag();
            return;
        }
        
        // For circle map, bubble map, and double bubble map, let simulation settle then save ALL node positions
        // This creates the "marbles in a donut" effect where all nodes adapt
        if ((this.diagramType === 'circle_map' || this.diagramType === 'bubble_map' || this.diagramType === 'double_bubble_map') && 
            this.forceSimulation && this.draggedSimulationNode) {
            this.logger.info('DragDropManager', 'Starting drag end for circle/bubble map', {
                diagramType: this.diagramType,
                hasForceNodes: !!this.forceNodes,
                nodeCount: this.forceNodes?.length || 0
            });
            
            // Release fixed position to let simulation settle naturally
            const draggedNodeBeforeRelease = {
                nodeId: this.draggedSimulationNode.nodeId,
                x: Math.round(this.draggedSimulationNode.x),
                y: Math.round(this.draggedSimulationNode.y),
                fx: this.draggedSimulationNode.fx,
                fy: this.draggedSimulationNode.fy
            };
            
            this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Releasing fixed position', {
                draggedNode: draggedNodeBeforeRelease,
                nodeCount: this.forceNodes?.length || 0
            });
            
            this.draggedSimulationNode.fx = null;
            this.draggedSimulationNode.fy = null;
            
            // Let simulation settle briefly, then save ALL positions
            const self = this;
            let settleTicks = 0;
            const maxSettleTicks = 50; // Increased for better settling
            
            const settleHandler = () => {
                settleTicks++;
                // Update positions in real-time during settling
                self.updateFreeFormPositions();
                
                const alpha = self.forceSimulation.alpha();
                const shouldStop = settleTicks >= maxSettleTicks || alpha < 0.01;
                
                // Log every 10 ticks during settling
                if (settleTicks % 10 === 0 || shouldStop) {
                    const finalPositions = self.forceNodes?.map(n => ({
                        nodeId: n.nodeId,
                        type: n.type,
                        x: Math.round(n.x),
                        y: Math.round(n.y),
                        fx: n.fx,
                        fy: n.fy
                    })) || [];
                    
                    self.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Simulation settling', {
                        ticks: settleTicks,
                        alpha: alpha.toFixed(4),
                        nodeCount: self.forceNodes?.length || 0,
                        shouldStop,
                        nodePositions: finalPositions
                    });
                }
                
                if (shouldStop) {
                    const finalPositions = self.forceNodes?.map(n => ({
                        nodeId: n.nodeId,
                        type: n.type,
                        x: Math.round(n.x),
                        y: Math.round(n.y)
                    })) || [];
                    
                    self.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - Simulation settled', {
                        ticks: settleTicks,
                        finalAlpha: alpha,
                        nodeCount: self.forceNodes?.length || 0,
                        finalPositions
                    });
                    
                    // Clear tick handler and let simulation decay naturally
                    // Don't call stop() as it can break the simulation for future use
                    self.forceSimulation.on('tick', null);
                    self.forceSimulation.alphaTarget(0);
                    
                    // Save ALL node positions (not just dragged one)
                    if (self.forceNodes && self.forceNodes.length > 0) {
                        self.logger.info('DragDropManager', 'Saving all node positions', {
                            nodeCount: self.forceNodes.length,
                            nodes: self.forceNodes.map(n => ({
                                nodeId: n.nodeId,
                                x: Math.round(n.x),
                                y: Math.round(n.y)
                            }))
                        });
                        self.saveAllFreeFormPositions();
                    } else {
                        self.logger.error('DragDropManager', 'No force nodes available to save');
                    }
                    
                    self.endDrag();
                }
            };
            
            // Restart simulation with higher alpha to ensure it runs
            this.forceSimulation
                .alpha(0.5) // Higher alpha for more movement
                .restart();
            
            this.forceSimulation.on('tick', settleHandler);
            
            // Also ensure simulation runs at least once
            this.forceSimulation.tick();
        } else if (this.forceSimulation && this.draggedSimulationNode) {
            // For other diagrams with force simulation, let it settle
            // Release fixed position
            this.draggedSimulationNode.fx = null;
            this.draggedSimulationNode.fy = null;
            
            // Let simulation settle to final position
            this.forceSimulation.alpha(1).restart();
            
            // Wait for simulation to settle, then save position
            const self = this;
            let settleTicks = 0;
            const maxSettleTicks = 50;
            
            const settleHandler = () => {
                settleTicks++;
                if (settleTicks >= maxSettleTicks || self.forceSimulation.alpha() < 0.01) {
                    // Clear tick handler and let simulation decay naturally
                    // Don't call stop() as it can break the simulation for future use
                    self.forceSimulation.on('tick', null);
                    self.forceSimulation.alphaTarget(0);
                    
                    // Save final position
                    if (self.draggedSimulationNode) {
                        self.saveFreeFormPosition(
                            self.draggedNodeId, 
                            self.draggedSimulationNode.x, 
                            self.draggedSimulationNode.y
                        );
                    }
                    
                    self.endDrag();
                }
            };
            
            this.forceSimulation.on('tick', settleHandler);
        } else {
            // Fallback: save current position immediately
            const svg = d3.select('#d3-container svg');
            if (!svg.empty()) {
                const point = svg.node().createSVGPoint();
                point.x = event.sourceEvent.clientX;
                point.y = event.sourceEvent.clientY;
                const svgPoint = point.matrixTransform(svg.node().getScreenCTM().inverse());
                this.saveFreeFormPosition(this.draggedNodeId, svgPoint.x, svgPoint.y);
            }
            this.endDrag();
        }
    }
    
    /**
     * Save all free-form positions (for circle map / bubble map - marbles effect)
     * For circle maps, recalculates even spread layout instead of saving exact positions
     */
    saveAllFreeFormPositions() {
        if (!this.editor || !this.editor.currentSpec || !this.forceNodes) {
            this.logger.error('DragDropManager', 'Editor, spec, or nodes not available');
            return;
        }
        
        const spec = this.editor.currentSpec;
        const diagramType = this.diagramType;
        
        // Get operations via DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            this.logger.error('DragDropManager', 'Operations loader not available');
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations) {
            this.logger.error('DragDropManager', 'Operations not available', { diagramType });
            return;
        }
        
        if (!operations.saveCustomPosition) {
            this.logger.error('DragDropManager', 'saveCustomPosition method not available');
            return;
        }
        
        // Initialize _customPositions if it doesn't exist
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        
        let savedCount = 0;
        const savedPositions = [];
        
        if (diagramType === 'circle_map') {
            // For circle maps, recalculate even spread layout instead of saving exact positions
            // This ensures nodes are evenly distributed around the circle after drop
            const contextNodes = this.forceNodes.filter(n => n.id !== 'central' && n.nodeId !== 'central_topic');
            const nodeCount = contextNodes.length;
            
            // Get center position from central node
            const centralNode = this.forceNodes.find(n => n.id === 'central' || n.nodeId === 'central_topic');
            let centerX, centerY;
            
            if (centralNode) {
                centerX = centralNode.x;
                centerY = centralNode.y;
            } else {
                // Fallback: try to get from window.circleMapCentralNode or calculate from SVG
                const svg = d3.select('#d3-container svg');
                if (!svg.empty()) {
                    const viewBox = svg.attr('viewBox');
                    if (viewBox) {
                        const [x, y, width, height] = viewBox.split(' ').map(Number);
                        centerX = x + width / 2;
                        centerY = y + height / 2;
                    } else {
                        centerX = parseFloat(svg.attr('width')) / 2;
                        centerY = parseFloat(svg.attr('height')) / 2;
                    }
                } else {
                    // Last resort: calculate from average of context nodes
                    const sumX = contextNodes.reduce((sum, n) => sum + n.x, 0);
                    const sumY = contextNodes.reduce((sum, n) => sum + n.y, 0);
                    centerX = sumX / nodeCount;
                    centerY = sumY / nodeCount;
                }
            }
            
            // Calculate average distance from center (to maintain similar radius)
            // This preserves the general size of the circle while creating even spread
            const avgDistance = contextNodes.length > 0
                ? contextNodes.reduce((sum, n) => {
                    const dx = n.x - centerX;
                    const dy = n.y - centerY;
                    return sum + Math.sqrt(dx * dx + dy * dy);
                }, 0) / contextNodes.length
                : 117; // Default radius if we can't calculate
            
            // Log current positions before recalculation (for debugging)
            const currentPositionsBeforeRecalc = contextNodes.map(node => {
                const nodeId = node.nodeId || `context_${node.id}`;
                const dx = node.x - centerX;
                const dy = node.y - centerY;
                const distance = Math.sqrt(dx * dx + dy * dy);
                let angle = Math.atan2(dy, dx) * 180 / Math.PI;
                angle = (angle + 90 + 360) % 360;
                return { nodeId, x: Math.round(node.x), y: Math.round(node.y), angle: Math.round(angle), distance: Math.round(distance) };
            });
            this.logger.info('DragDropManager', 'Current node positions before recalculation (after drag)', {
                positions: currentPositionsBeforeRecalc.map(p => `${p.nodeId}: (${p.x}, ${p.y}) angle:${p.angle}°`).join(', ')
            });
            
            // Sort nodes by their current angle from center to preserve relative order after drag
            // This ensures nodes maintain their new positions relative to each other
            const nodesWithAngles = contextNodes.map(node => {
                const dx = node.x - centerX;
                const dy = node.y - centerY;
                // Calculate angle in degrees (0-360, with 0 at right, 90 at top)
                let angle = Math.atan2(dy, dx) * 180 / Math.PI;
                // Convert to 0-360 range starting from top (-90 offset)
                angle = (angle + 90 + 360) % 360;
                return { node, angle };
            });
            
            // Sort by angle to preserve relative order
            nodesWithAngles.sort((a, b) => a.angle - b.angle);
            
            // Log sorted order (for debugging)
            const sortedOrder = nodesWithAngles.map((item, i) => {
                const nodeId = item.node.nodeId || `context_${item.node.id}`;
                const originalIndex = item.node.id;
                return `${nodeId} (was index ${originalIndex}): angle ${Math.round(item.angle)}° → slot ${i}`;
            });
            this.logger.info('DragDropManager', 'Nodes sorted by angle (preserving relative order)', {
                sortedOrder: sortedOrder.join(', ')
            });
            
            // CRITICAL FIX: Reorder spec.context array to match sorted order
            // This ensures node IDs (context_0, context_1, etc.) match the new positions
            const reorderedContext = nodesWithAngles.map(item => {
                const originalIndex = item.node.id;
                return spec.context[originalIndex];
            });
            
            // Log reordering for debugging
            const reorderLog = nodesWithAngles.map((item, i) => {
                const originalIndex = item.node.id;
                const oldText = spec.context[originalIndex];
                const newText = reorderedContext[i];
                return `Slot ${i}: "${oldText}" (was index ${originalIndex}) → "${newText}"`;
            });
            this.logger.info('DragDropManager', 'Reordering spec.context array to match sorted positions', {
                reorderLog: reorderLog.join(', ')
            });
            
            // Update spec.context with reordered array
            spec.context = reorderedContext;
            
            // Clear old custom positions to avoid conflicts
            if (spec._customPositions) {
                // Only clear context node positions, keep other custom positions if any
                Object.keys(spec._customPositions).forEach(key => {
                    if (key.startsWith('context_')) {
                        delete spec._customPositions[key];
                    }
                });
            }
            
            // Recalculate even spread positions using NEW indices (which match sorted order)
            nodesWithAngles.forEach((item, i) => {
                // Use NEW index (i) which matches the sorted order
                const nodeId = `context_${i}`;
                
                // Calculate even angle distribution around the circle
                const newAngle = (i * 360 / nodeCount) - 90; // -90 to start from top
                const x = centerX + avgDistance * Math.cos(newAngle * Math.PI / 180);
                const y = centerY + avgDistance * Math.sin(newAngle * Math.PI / 180);
                
                // Use operations method to save recalculated position
                const updatedSpec = operations.saveCustomPosition(spec, nodeId, x, y, false);
                if (updatedSpec) {
                    Object.assign(spec, updatedSpec);
                    savedCount++;
                    savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
                } else {
                    // Fallback: directly modify if operations method fails
                    if (!spec._customPositions) {
                        spec._customPositions = {};
                    }
                    spec._customPositions[nodeId] = { x, y };
                    savedCount++;
                    savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
                }
            });
            
            this.logger.info('DragDropManager', 'Recalculated even spread layout for circle map', {
                nodeCount: contextNodes.length,
                centerX: Math.round(centerX),
                centerY: Math.round(centerY),
                avgDistance: Math.round(avgDistance),
                method: centralNode ? 'from_central_node' : 'calculated',
                reorderedArray: spec.context.map((ctx, i) => `[${i}] "${ctx}"`).join(', ')
            });
        } else if (diagramType === 'bubble_map') {
            // For bubble maps, recalculate even spread layout instead of saving exact positions
            // This ensures nodes are evenly distributed around the center after drop, just like circle map
            const attributeNodes = this.forceNodes.filter(n => n.id !== 'central' && n.nodeId !== 'central_topic');
            const nodeCount = attributeNodes.length;
            
            // Get center position from central node
            const centralNode = this.forceNodes.find(n => n.id === 'central' || n.nodeId === 'central_topic') || this.forceCentralNode;
            let centerX, centerY;
            
            if (centralNode) {
                centerX = centralNode.x;
                centerY = centralNode.y;
            } else if (window.bubbleMapBoundaries) {
                // Use boundaries center if available
                centerX = window.bubbleMapBoundaries.centerX;
                centerY = window.bubbleMapBoundaries.centerY;
        } else {
                // Fallback: calculate from SVG or average of nodes
                const svg = d3.select('#d3-container svg');
                if (!svg.empty()) {
                    const viewBox = svg.attr('viewBox');
                    if (viewBox) {
                        const [x, y, width, height] = viewBox.split(' ').map(Number);
                        centerX = x + width / 2;
                        centerY = y + height / 2;
                    } else {
                        centerX = parseFloat(svg.attr('width')) / 2;
                        centerY = parseFloat(svg.attr('height')) / 2;
                    }
                } else {
                    // Last resort: calculate from average of attribute nodes
                    const sumX = attributeNodes.reduce((sum, n) => sum + n.x, 0);
                    const sumY = attributeNodes.reduce((sum, n) => sum + n.y, 0);
                    centerX = sumX / nodeCount;
                    centerY = sumY / nodeCount;
                }
            }
            
            // Get boundaries to determine target distance
            const boundaries = window.bubbleMapBoundaries;
            const targetDistance = boundaries 
                ? (boundaries.outerRadius + boundaries.innerRadius) / 2 // Use middle of constraint ring
                : attributeNodes.length > 0
                    ? attributeNodes.reduce((sum, n) => {
                        const dx = n.x - centerX;
                        const dy = n.y - centerY;
                        return sum + Math.sqrt(dx * dx + dy * dy);
                    }, 0) / attributeNodes.length
                    : 117; // Default distance
            
            // Log current positions before recalculation
            const currentPositionsBeforeRecalc = attributeNodes.map(node => {
                const nodeId = node.nodeId || `attribute_${node.id}`;
                const dx = node.x - centerX;
                const dy = node.y - centerY;
                const distance = Math.sqrt(dx * dx + dy * dy);
                let angle = Math.atan2(dy, dx) * 180 / Math.PI;
                angle = (angle + 90 + 360) % 360;
                return { nodeId, x: Math.round(node.x), y: Math.round(node.y), angle: Math.round(angle), distance: Math.round(distance) };
            });
            console.log('[DragDropManager] 🔵 BUBBLE MAP - Current positions before recalculation:', {
                positions: currentPositionsBeforeRecalc.map(p => `${p.nodeId}: (${p.x}, ${p.y}) angle:${p.angle}° dist:${p.distance}`).join(', ')
            });
            
            // Sort nodes by their current angle from center to preserve relative order after drag
            const nodesWithAngles = attributeNodes.map(node => {
                const dx = node.x - centerX;
                const dy = node.y - centerY;
                let angle = Math.atan2(dy, dx) * 180 / Math.PI;
                angle = (angle + 90 + 360) % 360;
                return { node, angle };
            });
            
            // Sort by angle to preserve relative order
            nodesWithAngles.sort((a, b) => a.angle - b.angle);
            
            // Log sorted order
            const sortedOrder = nodesWithAngles.map((item, i) => {
                const nodeId = item.node.nodeId || `attribute_${item.node.id}`;
                const originalIndex = item.node.id;
                return `${nodeId} (was index ${originalIndex}): angle ${Math.round(item.angle)}° → slot ${i}`;
            });
            console.log('[DragDropManager] 🔵 BUBBLE MAP - Nodes sorted by angle:', {
                sortedOrder: sortedOrder.join(', ')
            });
            
            // Reorder spec.attributes array to match sorted order
            const reorderedAttributes = nodesWithAngles.map(item => {
                const originalIndex = item.node.id;
                return spec.attributes[originalIndex];
            });
            
            // Log reordering
            const reorderLog = nodesWithAngles.map((item, i) => {
                const originalIndex = item.node.id;
                const oldText = typeof spec.attributes[originalIndex] === 'object' 
                    ? spec.attributes[originalIndex].text 
                    : spec.attributes[originalIndex];
                const newText = typeof reorderedAttributes[i] === 'object'
                    ? reorderedAttributes[i].text
                    : reorderedAttributes[i];
                return `Slot ${i}: "${oldText}" (was index ${originalIndex}) → "${newText}"`;
            });
            console.log('[DragDropManager] 🔵 BUBBLE MAP - Reordering spec.attributes array:', {
                reorderLog: reorderLog.join(', ')
            });
            
            // Update spec.attributes with reordered array
            spec.attributes = reorderedAttributes;
            
            // CRITICAL: Clear ALL old custom positions before saving new ones
            // This ensures node IDs match the new array order
            if (spec._customPositions) {
                Object.keys(spec._customPositions).forEach(key => {
                    if (key.startsWith('attribute_')) {
                        delete spec._customPositions[key];
                    }
                });
            }
            
            // Calculate even spread positions around the circle
            // IMPORTANT: Use NEW index (i) for node IDs, which matches the reordered array
            const angleStep = (2 * Math.PI) / nodeCount;
            nodesWithAngles.forEach((item, i) => {
                const angle = i * angleStep - Math.PI / 2; // Start from top
                const x = centerX + targetDistance * Math.cos(angle);
                const y = centerY + targetDistance * Math.sin(angle);
                // Use NEW index (i) for node ID, which matches the reordered spec.attributes array
                const nodeId = `attribute_${i}`;
                
                // Save new position with new node ID
                if (!spec._customPositions) {
                    spec._customPositions = {};
                }
                spec._customPositions[nodeId] = { x, y };
                savedCount++;
                savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
            });
            
            console.log('[DragDropManager] 🔵 BUBBLE MAP - Recalculated even spread layout:', {
                nodeCount: nodeCount,
                centerX: Math.round(centerX),
                centerY: Math.round(centerY),
                targetDistance: Math.round(targetDistance),
                savedPositions: savedPositions.map(p => `${p.nodeId}: (${p.x}, ${p.y})`).join(', ')
            });
            
            this.logger.info('DragDropManager', 'Recalculated even spread layout for bubble map', {
                nodeCount: nodeCount,
                centerX: Math.round(centerX),
                centerY: Math.round(centerY),
                targetDistance: Math.round(targetDistance),
                savedCount: savedCount
            });
        } else if (diagramType === 'double_bubble_map') {
            // For double bubble maps, recalculate vertical stacks for each category
            // Similarities in center, left_differences on left, right_differences on right
            const similarityNodes = this.forceNodes.filter(n => n.type === 'similarity');
            const leftDiffNodes = this.forceNodes.filter(n => n.type === 'left_difference');
            const rightDiffNodes = this.forceNodes.filter(n => n.type === 'right_difference');
            
            // Get center positions from central topics (if available)
            const leftTopic = this.forceNodes.find(n => n.type === 'left' || n.nodeId === 'topic_left');
            const rightTopic = this.forceNodes.find(n => n.type === 'right' || n.nodeId === 'topic_right');
            const svg = d3.select('#d3-container svg');
            let simX, leftX, rightX, centerY;
            
            if (!svg.empty()) {
                const viewBox = svg.attr('viewBox');
                if (viewBox) {
                    const [x, y, width, height] = viewBox.split(' ').map(Number);
                    centerY = y + height / 2;
                    simX = x + width / 2;
                    leftX = x + width * 0.25;
                    rightX = x + width * 0.75;
                } else {
                    const width = parseFloat(svg.attr('width')) || 700;
                    const height = parseFloat(svg.attr('height')) || 500;
                    centerY = height / 2;
                    simX = width / 2;
                    leftX = width * 0.25;
                    rightX = width * 0.75;
                }
            } else {
                // Fallback: use node positions
                centerY = 250;
                simX = 350;
                leftX = 175;
                rightX = 525;
            }
            
            // Clear old custom positions
            if (spec._customPositions) {
                Object.keys(spec._customPositions).forEach(key => {
                    if (key.startsWith('similarity_') || key.startsWith('left_diff_') || key.startsWith('right_diff_')) {
                        delete spec._customPositions[key];
                    }
                });
            }
            
            // Sort nodes by Y position to preserve relative order after drag
            similarityNodes.sort((a, b) => a.y - b.y);
            leftDiffNodes.sort((a, b) => a.y - b.y);
            rightDiffNodes.sort((a, b) => a.y - b.y);
            
            // Debug: Log node IDs and original indices before reordering
            console.log('[DragDropManager] 🔵 DOUBLE BUBBLE MAP - Before reordering:', {
                similarities: similarityNodes.map(n => ({
                    nodeId: n.nodeId,
                    id: n.id,
                    y: Math.round(n.y),
                    content: spec.similarities?.[n.id] || 'N/A'
                })),
                leftDiffs: leftDiffNodes.map(n => ({
                    nodeId: n.nodeId,
                    id: n.id,
                    y: Math.round(n.y),
                    content: spec.left_differences?.[n.id] || 'N/A'
                })),
                rightDiffs: rightDiffNodes.map(n => ({
                    nodeId: n.nodeId,
                    id: n.id,
                    y: Math.round(n.y),
                    content: spec.right_differences?.[n.id] || 'N/A'
                }))
            });
            
            // Reorder arrays to match sorted order
            // CRITICAL: Extract original index from nodeId (e.g., 'similarity_2' -> 2)
            // because node.id might not match the current array index after reordering
            if (spec.similarities && Array.isArray(spec.similarities)) {
                const reorderedSimilarities = similarityNodes.map(node => {
                    // Extract index from nodeId (e.g., 'similarity_2' -> 2)
                    const nodeIdMatch = node.nodeId?.match(/similarity_(\d+)/);
                    const originalIndex = nodeIdMatch ? parseInt(nodeIdMatch[1]) : node.id;
                    
                    if (originalIndex >= 0 && originalIndex < spec.similarities.length) {
                        return spec.similarities[originalIndex];
                    } else {
                        this.logger.warn('DragDropManager', 'Invalid similarity index', {
                            nodeId: node.nodeId,
                            originalIndex,
                            arrayLength: spec.similarities.length
                        });
                        return spec.similarities[node.id] || spec.similarities[0];
                    }
                });
                spec.similarities = reorderedSimilarities;
                
                console.log('[DragDropManager] 🔵 DOUBLE BUBBLE MAP - After reordering similarities:', {
                    original: spec.similarities.map((item, i) => `[${i}] "${typeof item === 'string' ? item : (item?.text || item?.content || String(item))}"`).join(', '),
                    reordered: reorderedSimilarities.map((item, i) => `[${i}] "${typeof item === 'string' ? item : (item?.text || item?.content || String(item))}"`).join(', ')
                });
            }
            
            if (spec.left_differences && Array.isArray(spec.left_differences)) {
                const reorderedLeftDiffs = leftDiffNodes.map(node => {
                    // Extract index from nodeId (e.g., 'left_diff_2' -> 2)
                    const nodeIdMatch = node.nodeId?.match(/left_diff_(\d+)/);
                    const originalIndex = nodeIdMatch ? parseInt(nodeIdMatch[1]) : node.id;
                    
                    if (originalIndex >= 0 && originalIndex < spec.left_differences.length) {
                        return spec.left_differences[originalIndex];
                    } else {
                        this.logger.warn('DragDropManager', 'Invalid left_diff index', {
                            nodeId: node.nodeId,
                            originalIndex,
                            arrayLength: spec.left_differences.length
                        });
                        return spec.left_differences[node.id] || spec.left_differences[0];
                    }
                });
                spec.left_differences = reorderedLeftDiffs;
            }
            
            if (spec.right_differences && Array.isArray(spec.right_differences)) {
                const reorderedRightDiffs = rightDiffNodes.map(node => {
                    // Extract index from nodeId (e.g., 'right_diff_2' -> 2)
                    const nodeIdMatch = node.nodeId?.match(/right_diff_(\d+)/);
                    const originalIndex = nodeIdMatch ? parseInt(nodeIdMatch[1]) : node.id;
                    
                    if (originalIndex >= 0 && originalIndex < spec.right_differences.length) {
                        return spec.right_differences[originalIndex];
                    } else {
                        this.logger.warn('DragDropManager', 'Invalid right_diff index', {
                            nodeId: node.nodeId,
                            originalIndex,
                            arrayLength: spec.right_differences.length
                        });
                        return spec.right_differences[node.id] || spec.right_differences[0];
                    }
                });
                spec.right_differences = reorderedRightDiffs;
            }
            
            // Recalculate similarities (center column, vertical stack)
            const simR = similarityNodes[0]?.radius || 31;
            const simSpacing = simR * 2 + 12;
            const simStartY = centerY - ((similarityNodes.length - 1) * simSpacing) / 2;
            similarityNodes.forEach((node, i) => {
                // Use NEW index (i) which matches the reordered array
                const nodeId = `similarity_${i}`;
                const y = simStartY + i * simSpacing;
                const x = simX;
                
                if (!spec._customPositions) spec._customPositions = {};
                spec._customPositions[nodeId] = { x, y };
                savedCount++;
                savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
            });
            
            // Recalculate left differences (left column, vertical stack)
            const leftR = leftDiffNodes[0]?.radius || 31;
            const leftSpacing = leftR * 2 + 12;
            const leftStartY = centerY - ((leftDiffNodes.length - 1) * leftSpacing) / 2;
            leftDiffNodes.forEach((node, i) => {
                // Use NEW index (i) which matches the reordered array
                const nodeId = `left_diff_${i}`;
                const y = leftStartY + i * leftSpacing;
                const x = leftX;
                
                if (!spec._customPositions) spec._customPositions = {};
                spec._customPositions[nodeId] = { x, y };
                savedCount++;
                savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
            });
            
            // Recalculate right differences (right column, vertical stack)
            const rightR = rightDiffNodes[0]?.radius || 31;
            const rightSpacing = rightR * 2 + 12;
            const rightStartY = centerY - ((rightDiffNodes.length - 1) * rightSpacing) / 2;
            rightDiffNodes.forEach((node, i) => {
                // Use NEW index (i) which matches the reordered array
                const nodeId = `right_diff_${i}`;
                const y = rightStartY + i * rightSpacing;
                const x = rightX;
                
                if (!spec._customPositions) spec._customPositions = {};
                spec._customPositions[nodeId] = { x, y };
                savedCount++;
                savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
            });
            
            console.log('[DragDropManager] 🔵 DOUBLE BUBBLE MAP - Recalculated vertical stacks:', {
                similarities: similarityNodes.length,
                leftDiffs: leftDiffNodes.length,
                rightDiffs: rightDiffNodes.length,
                savedCount
            });
            
        } else if (diagramType === 'multi_flow_map') {
            // For multi-flow maps, recalculate vertical stacks for causes (left) and effects (right)
            const causeNodes = this.forceNodes.filter(n => n.type === 'cause');
            const effectNodes = this.forceNodes.filter(n => n.type === 'effect');
            
            // Get center position
            const eventNode = this.forceNodes.find(n => n.type === 'event' || n.nodeId === 'multi-flow-event');
            const svg = d3.select('#d3-container svg');
            let centerX, centerY, causeCX, effectCX;
            
            if (!svg.empty()) {
                const viewBox = svg.attr('viewBox');
                if (viewBox) {
                    const [x, y, width, height] = viewBox.split(' ').map(Number);
                    centerX = x + width / 2;
                    centerY = y + height / 2;
                } else {
                    const width = parseFloat(svg.attr('width')) || 700;
                    const height = parseFloat(svg.attr('height')) || 500;
                    centerX = width / 2;
                    centerY = height / 2;
                }
                
                // Calculate side positions (causes on left, effects on right)
                const sideMargin = 100;
                const maxCauseW = Math.max(...causeNodes.map(n => n.width || 100), 100);
                const maxEffectW = Math.max(...effectNodes.map(n => n.width || 100), 100);
                causeCX = sideMargin + maxCauseW / 2;
                effectCX = (viewBox ? parseFloat(viewBox.split(' ')[2]) : parseFloat(svg.attr('width')) || 700) - sideMargin - maxEffectW / 2;
            } else {
                centerX = 350;
                centerY = 250;
                causeCX = 100;
                effectCX = 600;
            }
            
            // Clear old custom positions
            if (spec._customPositions) {
                Object.keys(spec._customPositions).forEach(key => {
                    if (key.startsWith('multi-flow-cause-') || key.startsWith('multi-flow-effect-')) {
                        delete spec._customPositions[key];
                    }
                });
            }
            
            // Sort nodes by Y position to preserve relative order after drag
            causeNodes.sort((a, b) => a.y - b.y);
            effectNodes.sort((a, b) => a.y - b.y);
            
            // Reorder arrays to match sorted order
            if (spec.causes && Array.isArray(spec.causes)) {
                const reorderedCauses = causeNodes.map(node => {
                    const originalIndex = node.id;
                    return spec.causes[originalIndex];
                });
                spec.causes = reorderedCauses;
            }
            
            if (spec.effects && Array.isArray(spec.effects)) {
                const reorderedEffects = effectNodes.map(node => {
                    const originalIndex = node.id;
                    return spec.effects[originalIndex];
                });
                spec.effects = reorderedEffects;
            }
            
            // Recalculate causes (left side, vertical stack)
            const vSpacing = 20;
            let totalCauseH = causeNodes.reduce((sum, n) => sum + (n.height || 40), 0) + (causeNodes.length - 1) * vSpacing;
            let cy = centerY - totalCauseH / 2;
            causeNodes.forEach((node, i) => {
                // Use NEW index (i) which matches the reordered array
                const nodeId = `multi-flow-cause-${i}`;
                const h = node.height || 40;
                const y = cy + h / 2;
                const x = causeCX;
                
                if (!spec._customPositions) spec._customPositions = {};
                spec._customPositions[nodeId] = { x, y };
                savedCount++;
                savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
                cy += h + vSpacing;
            });
            
            // Recalculate effects (right side, vertical stack)
            let totalEffectH = effectNodes.reduce((sum, n) => sum + (n.height || 40), 0) + (effectNodes.length - 1) * vSpacing;
            let ey = centerY - totalEffectH / 2;
            effectNodes.forEach((node, i) => {
                // Use NEW index (i) which matches the reordered array
                const nodeId = `multi-flow-effect-${i}`;
                const h = node.height || 40;
                const y = ey + h / 2;
                const x = effectCX;
                
                if (!spec._customPositions) spec._customPositions = {};
                spec._customPositions[nodeId] = { x, y };
                savedCount++;
                savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
                ey += h + vSpacing;
            });
            
            console.log('[DragDropManager] 🔵 MULTI-FLOW MAP - Recalculated vertical stacks:', {
                causes: causeNodes.length,
                effects: effectNodes.length,
                savedCount
            });
            
        } else if (diagramType === 'bridge_map') {
            // For bridge maps, recalculate horizontal spacing for analogy pairs
            const pairNodes = this.forceNodes.filter(n => n.type === 'left' || n.type === 'right');
            let leftNodes = this.forceNodes.filter(n => n.type === 'left');
            let rightNodes = this.forceNodes.filter(n => n.type === 'right');
            
            // Sort nodes by X position to preserve relative order after drag
            leftNodes.sort((a, b) => a.x - b.x);
            rightNodes.sort((a, b) => a.x - b.x);
            
            const pairCount = Math.max(leftNodes.length, rightNodes.length);
            
            // Reorder spec.analogies array to match sorted order
            if (spec.analogies && Array.isArray(spec.analogies)) {
                const reorderedAnalogies = [];
                for (let i = 0; i < pairCount; i++) {
                    const leftNode = leftNodes[i];
                    const rightNode = rightNodes[i];
                    if (leftNode && rightNode) {
                        // Find original indices - use the minimum to find the pair
                        const originalIndex = Math.min(leftNode.id, rightNode.id);
                        if (spec.analogies[originalIndex]) {
                            reorderedAnalogies.push(spec.analogies[originalIndex]);
                        }
                    } else if (leftNode && spec.analogies[leftNode.id]) {
                        reorderedAnalogies.push(spec.analogies[leftNode.id]);
                    } else if (rightNode && spec.analogies[rightNode.id]) {
                        reorderedAnalogies.push(spec.analogies[rightNode.id]);
                    }
                }
                // Fill any remaining pairs if arrays don't match
                while (reorderedAnalogies.length < spec.analogies.length && reorderedAnalogies.length < pairCount) {
                    const missingIndex = reorderedAnalogies.length;
                    if (spec.analogies[missingIndex]) {
                        reorderedAnalogies.push(spec.analogies[missingIndex]);
                    } else {
                        break;
                    }
                }
                spec.analogies = reorderedAnalogies;
            }
            
            // Get dimensions
            const svg = d3.select('#d3-container svg');
            let width, height, leftPadding, rightPadding;
            
            if (!svg.empty()) {
                const viewBox = svg.attr('viewBox');
                if (viewBox) {
                    const [x, y, w, h] = viewBox.split(' ').map(Number);
                    width = w;
                    height = h;
                    leftPadding = 50;
                    rightPadding = 50;
                } else {
                    width = parseFloat(svg.attr('width')) || 700;
                    height = parseFloat(svg.attr('height')) || 500;
                    leftPadding = 50;
                    rightPadding = 50;
                }
            } else {
                width = 700;
                height = 500;
                leftPadding = 50;
                rightPadding = 50;
            }
            
            // Calculate even horizontal spacing
            const sectionWidth = (width - leftPadding - rightPadding) / pairCount;
            const nodePositions = [];
            for (let i = 0; i < pairCount; i++) {
                nodePositions.push(leftPadding + (i + 0.5) * sectionWidth);
            }
            
            // Clear old custom positions
            if (spec._customPositions) {
                Object.keys(spec._customPositions).forEach(key => {
                    if (key.startsWith('bridge-left-') || key.startsWith('bridge-right-')) {
                        delete spec._customPositions[key];
                    }
                });
            }
            
            // Recalculate positions for each pair
            for (let i = 0; i < pairCount; i++) {
                const xPos = nodePositions[i];
                const leftNodeId = `bridge-left-${i}`;
                const rightNodeId = `bridge-right-${i}`;
                
                const leftY = height / 2 - 30;
                const rightY = height / 2 + 40;
                
                if (!spec._customPositions) spec._customPositions = {};
                spec._customPositions[leftNodeId] = { x: xPos, y: leftY };
                spec._customPositions[rightNodeId] = { x: xPos, y: rightY };
                savedCount += 2;
                savedPositions.push({ nodeId: leftNodeId, x: Math.round(xPos), y: Math.round(leftY) });
                savedPositions.push({ nodeId: rightNodeId, x: Math.round(xPos), y: Math.round(rightY) });
            }
            
            console.log('[DragDropManager] 🔵 BRIDGE MAP - Recalculated horizontal spacing:', {
                pairCount,
                savedCount
            });
            
        } else {
            // For other diagrams (tree_map, flow_map, brace_map, mindmap), save exact positions
            // These are hierarchical diagrams, so they maintain their exact positions
            this.forceNodes.forEach(node => {
                const nodeId = node.nodeId || `node_${node.id}`;
                const x = node.x;
                const y = node.y;
                
                // Use operations method to save each position (skip events to avoid multiple re-renders)
                const updatedSpec = operations.saveCustomPosition(spec, nodeId, x, y, false);
                if (updatedSpec) {
                    // Update spec reference
                    Object.assign(spec, updatedSpec);
                    savedCount++;
                    savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
                } else {
                    // Fallback: directly modify if operations method fails
                    spec._customPositions[nodeId] = { x, y };
                    savedCount++;
                    savedPositions.push({ nodeId, x: Math.round(x), y: Math.round(y) });
                }
            });
        }
        
        // Update spec reference
        this.editor.currentSpec = spec;
        
        // VERBOSE LOGGING: For bubble maps, log detailed position comparison
        if (diagramType === 'bubble_map') {
            console.log('[DragDropManager] 🔵 BUBBLE MAP - Position comparison summary:', {
                totalNodes: this.forceNodes?.length || 0,
                savedCount: savedCount,
                hasOriginalPositions: !!this.originalPositions,
                originalPositionsCount: this.originalPositions?.length || 0
            });
        }
        
        // Log saved positions with comparison to original positions
        const savedPositionsSorted = savedPositions.sort((a, b) => a.nodeId.localeCompare(b.nodeId));
        const positionComparison = this.originalPositions ? savedPositionsSorted.map(saved => {
            const original = this.originalPositions.find(orig => orig.nodeId === saved.nodeId);
            if (original && original.x !== undefined && original.y !== undefined) {
                const dx = saved.x - original.x;
                const dy = saved.y - original.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                return {
                    nodeId: saved.nodeId,
                    original: { x: original.x, y: original.y },
                    saved: { x: saved.x, y: saved.y },
                    delta: { x: dx, y: dy, distance: Math.round(distance) }
                };
            }
            // Original position not found or invalid - log warning
            if (!original) {
                this.logger.debug('DragDropManager', 'Original position not found for node', {
                    nodeId: saved.nodeId,
                    availableOriginalIds: this.originalPositions?.map(p => p.nodeId) || []
                });
            }
            return {
                nodeId: saved.nodeId,
                original: null,
                saved: { x: saved.x, y: saved.y },
                delta: null
            };
        }) : null;
        
        // Log original positions - expanded format
        if (this.originalPositions) {
            const originalPositionsList = this.originalPositions.sort((a, b) => a.nodeId.localeCompare(b.nodeId));
            this.logger.info('DragDropManager', 'Original positions (before drag)', {
                count: originalPositionsList.length,
                positions: originalPositionsList.map(p => `${p.nodeId}: (${Math.round(p.x)}, ${Math.round(p.y)})`).join(', ')
            });
            // Also log as individual entries for easier reading
            originalPositionsList.forEach(pos => {
                this.logger.info('DragDropManager', `  Original: ${pos.nodeId}`, { x: Math.round(pos.x), y: Math.round(pos.y) });
            });
        }
        
        // Log saved positions - expanded format
        this.logger.info('DragDropManager', 'Saved positions (after drag)', {
            count: savedPositionsSorted.length,
            positions: savedPositionsSorted.map(p => `${p.nodeId}: (${Math.round(p.x)}, ${Math.round(p.y)})`).join(', ')
        });
        savedPositionsSorted.forEach(pos => {
            this.logger.info('DragDropManager', `  Saved: ${pos.nodeId}`, { x: Math.round(pos.x), y: Math.round(pos.y) });
        });
        
        // Log position comparison - expanded format
        if (positionComparison) {
            const comparisonSummary = positionComparison.map(c => {
                if (c.original && c.delta) {
                    return `${c.nodeId}: (${Math.round(c.original.x)}, ${Math.round(c.original.y)}) → (${Math.round(c.saved.x)}, ${Math.round(c.saved.y)}) [Δ${Math.round(c.delta.distance)}px]`;
                } else {
                    return `${c.nodeId}: (no original) → (${Math.round(c.saved.x)}, ${Math.round(c.saved.y)})`;
                }
            }).join(', ');
            
            this.logger.info('DragDropManager', 'Position comparison: Original → Saved', {
                count: positionComparison.length,
                summary: comparisonSummary
            });
            
            positionComparison.forEach(comp => {
                if (comp.original && comp.delta) {
                    this.logger.info('DragDropManager', `  ${comp.nodeId}`, {
                        original: { x: Math.round(comp.original.x), y: Math.round(comp.original.y) },
                        saved: { x: Math.round(comp.saved.x), y: Math.round(comp.saved.y) },
                        delta: { x: Math.round(comp.delta.x), y: Math.round(comp.delta.y), distance: Math.round(comp.delta.distance) }
                    });
                } else {
                    this.logger.info('DragDropManager', `  ${comp.nodeId}`, {
                        original: null,
                        saved: { x: Math.round(comp.saved.x), y: Math.round(comp.saved.y) },
                        delta: null
                    });
                }
            });
        }
        
        this.logger.info('DragDropManager', 'Positions saved to spec._customPositions', {
            savedCount,
            totalNodes: this.forceNodes.length,
            positionsCount: Object.keys(spec._customPositions || {}).length,
            allCustomPositions: Object.keys(spec._customPositions || {}).reduce((acc, key) => {
                acc[key] = {
                    x: Math.round(spec._customPositions[key].x),
                    y: Math.round(spec._customPositions[key].y)
                };
                return acc;
            }, {})
        });
        
        // Trigger re-render
        if (this.eventBus) {
            this.logger.info('DragDropManager', 'Emitting spec_updated event to trigger re-render', {
                savedCount,
                totalNodes: this.forceNodes.length,
                positionsCount: Object.keys(spec._customPositions || {}).length
            });
            
            this.eventBus.emit('diagram:spec_updated', { spec });
            
            // Also emit operation completed for history
            this.eventBus.emit('diagram:operation_completed', {
                operation: 'save_all_custom_positions',
                snapshot: JSON.parse(JSON.stringify(spec)),
                data: {
                    positions: spec._customPositions,
                    nodeCount: savedCount
                }
            });
        }
        
        this.logger.debug('DragDropManager', 'Saved all node positions', {
            nodeCount: this.forceNodes.length,
            savedCount,
            positions: spec._customPositions
        });
    }
    
    /**
     * Save free-form position via operations
     */
    saveFreeFormPosition(nodeId, x, y) {
        if (!this.editor || !this.editor.currentSpec) {
            this.logger.error('DragDropManager', 'Editor or spec not available');
            return;
        }
        
        const spec = this.editor.currentSpec;
        const diagramType = this.diagramType;
        
        // Get operations via DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            this.logger.error('DragDropManager', 'Operations loader not available');
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations) {
            this.logger.error('DragDropManager', 'Operations not available', { diagramType });
            return;
        }
        
        if (operations.saveCustomPosition) {
            // Pass emitEvents=false to prevent double emissions
            // We'll emit diagram:spec_updated here instead for consistency
            const updatedSpec = operations.saveCustomPosition(spec, nodeId, x, y, false);
            if (updatedSpec) {
                this.editor.currentSpec = updatedSpec;
                // Emit re-render trigger (single emission point)
                if (this.eventBus) {
                    this.eventBus.emit('diagram:spec_updated', { spec: updatedSpec });
                }
            }
        } else {
            this.logger.error('DragDropManager', 'saveCustomPosition method not available');
        }
    }
    
    /**
     * Update drop zone detection (hierarchical mode)
     */
    updateDropZoneDetection(event) {
        if (this.rafId) return;
        
        this.rafId = requestAnimationFrame(() => {
            const dropTarget = this.detectDropTarget(event);
            this.highlightDropZone(dropTarget);
            this.rafId = null;
        });
    }
    
    /**
     * Detect drop target at current mouse position
     */
    detectDropTarget(event) {
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) return null;
        
        // Convert screen coordinates to SVG coordinates
        const point = svg.node().createSVGPoint();
        point.x = event.sourceEvent.clientX;
        point.y = event.sourceEvent.clientY;
        const svgPoint = point.matrixTransform(svg.node().getScreenCTM().inverse());
        
        // Find element at point
        const element = document.elementFromPoint(event.sourceEvent.clientX, event.sourceEvent.clientY);
        if (!element) return null;
        
        // Find closest shape element
        const shapeElement = element.closest('rect, circle, ellipse');
        if (!shapeElement) return null;
        
        const targetElement = d3.select(shapeElement);
        const targetNodeType = targetElement.attr('data-node-type');
        const targetNodeId = targetElement.attr('data-node-id');
        
        // Validate drop target based on dragged node type
        if (this.draggedNodeType === 'child' || this.draggedNodeType === 'subitem') {
            // Children can be dropped on branches
            if (targetNodeType === 'branch') {
                const branchIndex = parseInt(targetElement.attr('data-branch-index') || targetElement.attr('data-array-index'));
                return {
                    type: 'branch',
                    branchIndex: branchIndex,
                    element: targetElement,
                    nodeId: targetNodeId
                };
            }
        } else if (this.draggedNodeType === 'branch') {
            // Branches can be reordered (dropped between branches)
            // This is more complex - would need to detect insertion point
            // For now, return null (reordering not implemented in Phase 1)
            return null;
        }
        
        return null;
    }
    
    /**
     * Check if drop target is valid
     */
    isValidDropTarget(dropTarget) {
        if (!dropTarget) return false;
        
        // Can't drop on same branch
        if (this.draggedNodeType === 'child' && dropTarget.type === 'branch') {
            if (dropTarget.branchIndex === this.sourceBranchIndex) {
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Highlight drop zone
     */
    highlightDropZone(dropTarget) {
        // Clear previous highlights
        this.clearDropZoneHighlights();
        
        if (dropTarget && this.isValidDropTarget(dropTarget)) {
            // Add highlight
            dropTarget.element
                .classed('drop-zone-valid', true)
                .transition()
                .duration(200)
                .style('stroke', '#4CAF50')
                .style('stroke-width', '3px');
            
            this.dropZoneHighlights.push(dropTarget.element);
        } else {
            // Show invalid feedback (optional)
        }
    }
    
    /**
     * Clear drop zone highlights
     */
    clearDropZoneHighlights() {
        this.dropZoneHighlights.forEach(element => {
            element
                .classed('drop-zone-valid', false)
                .transition()
                .duration(200)
                .style('stroke', null)
                .style('stroke-width', null);
        });
        this.dropZoneHighlights = [];
    }
    
    /**
     * Execute hierarchical move operation
     */
    executeHierarchicalMove(dropTarget) {
        if (!this.editor || !this.editor.currentSpec) {
            this.logger.error('DragDropManager', 'Editor or spec not available');
            return;
        }
        
        const spec = this.editor.currentSpec;
        const diagramType = this.diagramType;
        
        // Get operations via DiagramOperationsLoader (same pattern as InteractiveEditor)
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            this.logger.error('DragDropManager', 'Operations loader not available');
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations) {
            this.logger.error('DragDropManager', 'Operations not available', { diagramType });
            return;
        }
        
        if (this.draggedNodeType === 'child' || this.draggedNodeType === 'subitem') {
            // Move child to branch
            if (dropTarget.type === 'branch') {
                if (operations.moveChildToBranch) {
                    const updatedSpec = operations.moveChildToBranch(
                        spec, 
                        this.sourceBranchIndex, 
                        this.sourceChildIndex, 
                        dropTarget.branchIndex
                    );
                    if (updatedSpec) {
                        this.editor.currentSpec = updatedSpec;
                    }
                } else {
                    this.logger.error('DragDropManager', 'moveChildToBranch method not available');
                }
            }
        } else if (this.draggedNodeType === 'branch') {
            // Move branch (reorder)
            if (operations.moveBranch) {
                // For branch reordering, we need to detect insertion point
                // For now, just move to target branch index
                const updatedSpec = operations.moveBranch(
                    spec, 
                    this.sourceBranchIndex, 
                    dropTarget.branchIndex
                );
                if (updatedSpec) {
                    this.editor.currentSpec = updatedSpec;
                }
            } else {
                this.logger.error('DragDropManager', 'moveBranch method not available');
            }
        }
        
        // Operations will emit events for history and re-render
        // No need to emit diagram:spec_updated here as operations handle it
    }
    
    /**
     * Cancel drag operation
     */
    cancelDrag() {
        // Return node to original opacity
        if (this.draggedNode) {
            this.draggedNode.style('opacity', this.originalNodeOpacity);
        }
    }
    
    /**
     * End drag operation and cleanup
     */
    endDrag() {
        this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - endDrag() called', {
            isDragging: this.isDragging,
            dragMode: this.dragMode,
            diagramType: this.diagramType,
            draggedNodeId: this.draggedNodeId,
            hasForceSimulation: !!this.forceSimulation,
            hasForceNodes: !!this.forceNodes,
            processingDragEnd: this._processingDragEnd
        });
        
        // Reset processing flag first
        this._processingDragEnd = false;
        
        // Clear drop zone highlights
        this.clearDropZoneHighlights();
        
        // Remove drag clone
        if (this.dragClone) {
            this.dragClone.remove();
            this.dragClone = null;
        }
        
        // Remove document-level mouse tracking
        if (this.documentMouseMoveHandler) {
            document.removeEventListener('mousemove', this.documentMouseMoveHandler);
            this.documentMouseMoveHandler = null;
        }
        if (this.documentMouseUpHandler) {
            document.removeEventListener('mouseup', this.documentMouseUpHandler);
            this.documentMouseUpHandler = null;
        }
        
        // Restore text selection
        document.body.style.userSelect = '';
        
        // Restore original node opacity
        if (this.draggedNode) {
            this.draggedNode.style('opacity', this.originalNodeOpacity);
        }
        
        // Store dragged node ID for event emission before clearing
        const draggedNodeId = this.draggedNodeId;
        
        // Clear force simulation references
        if (this.forceSimulation) {
            // Clear tick handlers and let simulation decay naturally
            // Don't call stop() as it can break the simulation for future use
            this.forceSimulation.on('tick', null);
            // Set alpha target to 0 to let simulation cool down naturally
            this.forceSimulation.alphaTarget(0);
        }
        this.forceSimulation = null;
        this.forceNodes = null;
        this.forceCentralNode = null;
        this.forceCentralNodes = null; // Clear double bubble map central nodes
        this.draggedSimulationNode = null;
        
        // Clear state
        this.isDragging = false;
        this.dragMode = null;
        this.draggedNode = null;
        this.draggedNodeId = null;
        this.draggedNodeType = null;
        this.diagramType = null;
        this.sourceBranchIndex = null;
        this.sourceChildIndex = null;
        this.currentDropTarget = null;
        this.originalNodeOpacity = null;
        this.cloneInitialX = null;
        this.cloneInitialY = null;
        
        // Clear tick count tracking
        this._tickCount = null;
        this._lineUpdateCount = null;
        
        // Cancel RAF
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
        
        this.logger.info('DragDropManager', '🔵 DOUBLE BUBBLE MAP - endDrag() completed, state cleared', {
            isDragging: this.isDragging,
            dragMode: this.dragMode,
            hasForceSimulation: !!this.forceSimulation,
            hasForceNodes: !!this.forceNodes
        });
        
        // Emit drag ended event
        this.eventBus.emit('drag:ended', {
            nodeId: draggedNodeId
        });
    }
    
    /**
     * Cleanup on destroy
     */
    destroy() {
        this.logger.debug('DragDropManager', 'Destroying');
        
        // End any active drag
        if (this.isDragging) {
            this.endDrag();
        }
        
        // Remove all Event Bus listeners
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('DragDropManager', `Removed ${removedCount} listeners`);
            }
        }
        
        // Clear references
        this.eventBus = null;
        this.stateManager = null;
        this.editor = null;
    }
}

// Make available globally
window.DragDropManager = DragDropManager;

