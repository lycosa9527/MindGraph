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
        
        // Session info (will be set by DiagramSelector)
        this.sessionId = null;
        this.sessionDiagramType = null;
        
        // Track current canvas sizing mode
        // true = sized with panel space reserved, false = full width
        this.isSizedForPanel = false;
        
        // Initialize components
        this.selectionManager = new SelectionManager();
        this.canvasManager = new CanvasManager();
        this.toolbarManager = null; // Will be initialized after render
        this.renderer = null;
        
        // Store event handler references for cleanup
        this.eventHandlers = {
            orientationChange: null,
            windowResize: null,
            resetViewClick: null
        };
        
        // Log editor initialization
        logger.debug('Editor', 'Editor created', { 
            diagramType, 
            hasTemplate: !!template 
        });
        
        // Bind selection change callback
        this.selectionManager.setSelectionChangeCallback((selectedNodes) => {
            this.selectedNodes = new Set(selectedNodes);
            
            // Verbose logging: Log node selection changes
            logger.debug('InteractiveEditor', 'Node Selection Changed', {
                count: selectedNodes.length,
                nodeIds: Array.from(selectedNodes),
                diagramType: this.diagramType,
                timestamp: Date.now()
            });
            
            this.updateToolbarState();
        });
    }
    
    /**
     * Legacy log method - now uses centralized logger
     * @deprecated Use logger.debug/info/warn/error directly
     */
    log(message, data = null) {
        logger.debug('Editor', message, data);
    }
    
    /**
     * Get translated notification message
     * @param {string} key - Notification key from language-manager
     * @param  {...any} args - Arguments for function-based notifications
     */
    getNotif(key, ...args) {
        if (window.languageManager && window.languageManager.getNotification) {
            return window.languageManager.getNotification(key, ...args);
        }
        return key; // Fallback to key if language manager not available
    }
    
    /**
     * Validate that we're operating within the correct session
     */
    validateSession(operation = 'Operation') {
        if (!this.sessionId) {
            logger.error('Editor', `${operation} blocked - No session ID set!`);
            return false;
        }
        
        if (this.diagramType !== this.sessionDiagramType) {
            logger.error('Editor', `${operation} blocked - Diagram type mismatch!`, {
                editorType: this.diagramType,
                sessionType: this.sessionDiagramType,
                sessionId: this.sessionId
            });
            return false;
        }
        
        // Cross-check with DiagramSelector session
        if (window.diagramSelector?.currentSession) {
            if (window.diagramSelector.currentSession.id !== this.sessionId) {
                logger.error('Editor', `${operation} blocked - Session ID mismatch!`, {
                    editorSession: this.sessionId,
                    selectorSession: window.diagramSelector.currentSession.id
                });
                return false;
            }
            
            if (window.diagramSelector.currentSession.diagramType !== this.diagramType) {
                logger.error('Editor', `${operation} blocked - DiagramSelector session type mismatch!`);
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Detect if user is on mobile device
     */
    isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) 
            || window.innerWidth <= 768;
    }
    
    /**
     * Initialize the editor
     */
    initialize() {
        logger.info('Editor', `Initializing editor for ${this.diagramType}`);
        
        // Setup canvas
        this.canvasManager.setupCanvas('#d3-container', {
            minHeight: '600px',
            backgroundColor: '#f5f5f5'
        });
        
        // Update school name display immediately and also after a short delay
        // (to ensure auth data is loaded if it wasn't ready)
        this.updateSchoolNameDisplay();
        setTimeout(() => {
            this.updateSchoolNameDisplay();
        }, 500);
        
        // Save initial state to history (so user can undo back to start)
        this.saveToHistory('initial_load', { diagramType: this.diagramType });
        
        // Update flow map orientation button visibility
        this.updateFlowMapOrientationButtonVisibility();
        
        // Render initial diagram
        this.renderDiagram();
        
        // Setup global event handlers
        this.setupGlobalEventHandlers();
        
        // Initialize toolbar manager
        if (typeof ToolbarManager !== 'undefined') {
            this.toolbarManager = new ToolbarManager(this);
            logger.debug('Editor', 'Toolbar manager initialized');
        }
        
        // Auto-fit for mobile devices on initial load
        if (this.isMobileDevice()) {
            logger.debug('Editor', 'Mobile device detected - auto-fitting to screen');
            setTimeout(() => {
                this.fitDiagramToWindow();
            }, 500); // Slight delay to ensure rendering is complete
        }
    }
    
    /**
     * Render the diagram
     */
    async renderDiagram() {
        this.log('InteractiveEditor: Starting diagram render', {
            specKeys: Object.keys(this.currentSpec || {})
        });
        
        // Update flow map orientation button visibility
        this.updateFlowMapOrientationButtonVisibility();
        
        try {
            // For templates: don't set adaptive dimensions during render
            // Let the renderer use its default size, then fitToCanvasWithPanel will handle sizing
            // For LLM-generated diagrams: keep their recommended dimensions
            const theme = null; // Use default theme
            let dimensions = null;
            
            if (this.currentSpec && this.currentSpec._llm_generated) {
                // LLM-generated: use their recommended dimensions
                dimensions = this.currentSpec._recommended_dimensions || null;
                logger.debug('Editor', 'Using LLM-generated dimensions', dimensions);
            } else {
                // Template: render at default size, fitToCanvasWithPanel will handle sizing via viewBox
                logger.debug('Editor', 'Will render at default size then fit to canvas');
                // Set flag to indicate we'll be sizing for panel after render
                this.isSizedForPanel = true;
            }
            
            if (typeof renderGraph === 'function') {
                logger.debug('Editor', `Rendering ${this.diagramType}`, {
                    nodes: this.currentSpec?.nodes?.length || 0,
                    hasTitle: !!this.currentSpec?.title,
                    hasTopic: !!(this.currentSpec?.topic || this.currentSpec?.whole)
                });
                await renderGraph(this.diagramType, this.currentSpec, theme, dimensions);
            } else {
                logger.error('Editor', 'renderGraph dispatcher not found');
                throw new Error('Renderer not available');
            }
            
            // Add interaction handlers after rendering
            this.addInteractionHandlers();
            
            // Enable zoom and pan for all devices
            // - Mouse wheel: zoom in/out
            // - Click and drag: pan around
            // - Middle mouse button drag: pan around
            this.enableZoomAndPan();
            
            // Update school name display in status bar (async, no await needed)
            this.updateSchoolNameDisplay().catch(err => {
                logger.debug('Editor', 'School name update failed', err);
            });
            
            // NOTE: Auto-fit is handled by DiagramSelector after initialization
            // This prevents duplicate triggers and ensures clean initial load
            
            // Update flow map orientation button visibility
            this.updateFlowMapOrientationButtonVisibility();
            
            // Dispatch event to update node count and other UI elements
            window.dispatchEvent(new CustomEvent('diagram-rendered'));
            
        } catch (error) {
            logger.error('Editor', 'Diagram rendering failed', error);
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
                
                // Verbose logging: Log drag start
                logger.debug('InteractiveEditor', '🖱️ Drag Start', {
                    nodeId,
                    diagramType: self.diagramType,
                    mouseX: event.x,
                    mouseY: event.y,
                    timestamp: Date.now()
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
                
                // Verbose logging: Log drag end
                logger.debug('InteractiveEditor', '🖱️ Drag End', {
                    nodeId,
                    finalX: startX,
                    finalY: startY,
                    diagramType: self.diagramType,
                    timestamp: Date.now()
                });
                
                d3.select(this).style('opacity', 1);
                connectedLines = []; // Clear references
                self.saveToHistory('move_node', { 
                    nodeId: nodeId,
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
                    
                    // Verbose logging: Log all mouse clicks
                    logger.debug('InteractiveEditor', '🖱️ Mouse Click', {
                        nodeId,
                        ctrlKey: event.ctrlKey,
                        metaKey: event.metaKey,
                        altKey: event.altKey,
                        shiftKey: event.shiftKey,
                        clientX: event.clientX,
                        clientY: event.clientY,
                        diagramType: self.diagramType
                    });
                    
                    if (event.ctrlKey || event.metaKey) {
                        self.selectionManager.toggleNodeSelection(nodeId);
                    } else {
                        self.selectionManager.clearSelection();
                        self.selectionManager.selectNode(nodeId);
                    }
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                    
                    // Verbose logging: Log double-click for editing
                    logger.debug('InteractiveEditor', 'Double-Click for Edit', {
                        nodeId,
                        diagramType: self.diagramType,
                        timestamp: Date.now()
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
                    const isMindMapNode = self.diagramType === 'mindmap' && 
                        (nodeType === 'topic' || nodeType === 'branch' || nodeType === 'child');
                    
                    if (!isMindMapNode) {
                        d3.select(this).style('opacity', 0.8);
                    }
                })
                .on('mouseout', function() {
                    // Skip opacity animation for mindmap nodes (topic, branch, and child)
                    const nodeType = element.attr('data-node-type');
                    const isMindMapNode = self.diagramType === 'mindmap' && 
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
                        // Skip opacity animation for mindmap nodes (topic, branch, and child)
                        // to keep connection lines visible
                        const nodeType = element.attr('data-node-type');
                        const isMindMapNode = self.diagramType === 'mindmap' && 
                            (nodeType === 'topic' || nodeType === 'branch' || nodeType === 'child');
                        
                        if (!isMindMapNode) {
                            d3.select(this).style('opacity', 0.8);
                        }
                    })
                    .on('mouseout', function() {
                        // Skip opacity animation for mindmap nodes (topic, branch, and child)
                        const nodeType = element.attr('data-node-type');
                        const isMindMapNode = self.diagramType === 'mindmap' && 
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
     * Enable zoom and pan functionality for canvas
     * - Mouse wheel: zoom in/out
     * - Left click + drag: pan around
     * - Middle mouse button + drag: pan around
     */
    /**
     * Update school name display in status bar
     */
    async updateSchoolNameDisplay() {
        try {
            const schoolNameDisplay = document.getElementById('school-name-display');
            if (!schoolNameDisplay) {
                console.warn('[Editor] School name display element not found in DOM');
                return;
            }
            
            // Try to get school name from user's organization
            const authHelper = window.auth || window.AuthHelper;
            if (!authHelper) {
                console.warn('[Editor] Auth helper not available');
                schoolNameDisplay.style.display = 'none';
                return;
            }
            
            // First try to get from localStorage
            let user = null;
            if (typeof authHelper.getUser === 'function') {
                user = authHelper.getUser();
                console.log('[Editor] User from localStorage:', user);
            }
            
            // If no user data, fetch it from server
            if (!user && typeof authHelper.getCurrentUser === 'function') {
                console.log('[Editor] Fetching user data from server...');
                user = await authHelper.getCurrentUser();
                console.log('[Editor] User from server:', user);
            }
            
            // Handle both string and object organization formats
            let schoolName = null;
            if (user && user.organization) {
                if (typeof user.organization === 'string') {
                    // Organization stored as string (from localStorage)
                    schoolName = user.organization;
                } else if (user.organization.name) {
                    // Organization stored as object with name property (from server)
                    schoolName = user.organization.name;
                }
            }
            
            if (schoolName) {
                schoolNameDisplay.textContent = schoolName;
                schoolNameDisplay.style.display = 'inline-block';
                schoolNameDisplay.style.marginRight = '12px';
                schoolNameDisplay.style.color = '#ffffff';
                schoolNameDisplay.style.fontSize = '12px';
                schoolNameDisplay.style.fontWeight = '500';
                console.log('[Editor] School name displayed:', schoolName);
            } else {
                // Check if we're in demo or enterprise mode
                let mode = authHelper.getMode();
                
                // If mode not set in localStorage, try to detect from server
                if (mode === 'standard' && typeof authHelper.detectMode === 'function') {
                    try {
                        mode = await authHelper.detectMode();
                        if (mode && mode !== 'standard') {
                            authHelper.setMode(mode);
                        }
                    } catch (e) {
                        console.debug('[Editor] Could not detect mode from server:', e);
                    }
                }
                
                if (mode === 'demo') {
                    schoolNameDisplay.textContent = 'Demo';
                    schoolNameDisplay.style.display = 'inline-block';
                    schoolNameDisplay.style.marginRight = '12px';
                    schoolNameDisplay.style.color = '#ffffff';
                    schoolNameDisplay.style.fontSize = '12px';
                    schoolNameDisplay.style.fontWeight = '500';
                    console.log('[Editor] Demo mode');
                } else if (mode === 'enterprise') {
                    schoolNameDisplay.textContent = 'Enterprise';
                    schoolNameDisplay.style.display = 'inline-block';
                    schoolNameDisplay.style.marginRight = '12px';
                    schoolNameDisplay.style.color = '#ffffff';
                    schoolNameDisplay.style.fontSize = '12px';
                    schoolNameDisplay.style.fontWeight = '500';
                    console.log('[Editor] Enterprise mode');
                } else {
                    console.warn('[Editor] No school name available. User:', user);
                    schoolNameDisplay.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('[Editor] Error updating school name display:', error);
            const schoolNameDisplay = document.getElementById('school-name-display');
            if (schoolNameDisplay) {
                schoolNameDisplay.style.display = 'none';
            }
        }
    }
    
    enableZoomAndPan() {
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            logger.warn('Editor', 'No SVG found - zoom/pan disabled');
            return;
        }
        
        // Create a group to hold all content if it doesn't exist
        let contentGroup = svg.select('g.zoom-group');
        if (contentGroup.empty()) {
            // Move all existing SVG children into a group
            const existingChildren = svg.selectAll('*:not(defs)').nodes();
            contentGroup = svg.insert('g', ':first-child')
                .attr('class', 'zoom-group');
            
            existingChildren.forEach(child => {
                contentGroup.node().appendChild(child);
            });
        }
        
        // Configure zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10]) // Allow 10x zoom in, 0.1x zoom out
            .filter((event) => {
                // Allow mouse wheel for zooming
                if (event.type === 'wheel') return true;
                
                // For panning: ONLY allow middle mouse button (scroll wheel click)
                // Block left mouse (button 0) and right mouse (button 2)
                if (event.type === 'mousedown') {
                    return event.button === 1; // Only middle mouse button for panning
                }
                
                // Allow other event types (mousemove, mouseup, etc.)
                return true;
            })
            .on('zoom', (event) => {
                contentGroup.attr('transform', event.transform);
                // Update zoom level display if needed
                if (this.currentZoomLevel) {
                    this.currentZoomLevel.textContent = `${Math.round(event.transform.k * 100)}%`;
                }
            });
        
        // Apply zoom behavior to SVG
        svg.call(zoom);
        
        // Store zoom behavior for programmatic control
        this.zoomBehavior = zoom;
        this.zoomTransform = d3.zoomIdentity;
        
        logger.debug('Editor', 'Zoom and pan enabled (mouse wheel + middle button)');
    }
    
    /**
     * Add zoom control buttons for mobile
     */
    addMobileZoomControls() {
        // Check if controls already exist
        if (document.getElementById('mobile-zoom-controls')) {
            return;
        }
        
        const controlsHtml = `
            <div id="mobile-zoom-controls" class="mobile-zoom-controls">
                <button id="zoom-in-btn" class="zoom-control-btn" title="Zoom In">
                    <span>+</span>
                </button>
                <button id="zoom-out-btn" class="zoom-control-btn" title="Zoom Out">
                    <span>−</span>
                </button>
                <button id="zoom-reset-btn" class="zoom-control-btn" title="Reset Zoom">
                    <span>⊙</span>
                </button>
            </div>
        `;
        
        // Add to d3-container
        const container = document.getElementById('d3-container');
        if (container) {
            container.insertAdjacentHTML('beforeend', controlsHtml);
            
            // Add event listeners
            document.getElementById('zoom-in-btn').addEventListener('click', () => {
                this.zoomIn();
            });
            
            document.getElementById('zoom-out-btn').addEventListener('click', () => {
                this.zoomOut();
            });
            
            document.getElementById('zoom-reset-btn').addEventListener('click', () => {
                this.fitDiagramToWindow();
            });
            
            logger.debug('Editor', 'Mobile zoom controls added');
        }
    }
    
    /**
     * Show flow map orientation button in toolbar (only for flow_map diagram type)
     */
    updateFlowMapOrientationButtonVisibility() {
        const btn = document.getElementById('flow-map-orientation-btn');
        if (btn) {
            // ONLY show for flow_map diagram type
            if (this.diagramType === 'flow_map') {
                btn.style.display = '';
            } else {
                btn.style.display = 'none';
            }
        }
    }
    
    /**
     * Flip flow map orientation between vertical and horizontal
     */
    flipFlowMapOrientation() {
        const currentSpec = this.currentSpec;
        if (!currentSpec || this.diagramType !== 'flow_map') {
            return;
        }
        
        // Toggle orientation
        const currentOrientation = currentSpec.orientation || 'vertical';
        const newOrientation = currentOrientation === 'vertical' ? 'horizontal' : 'vertical';
        currentSpec.orientation = newOrientation;
        
        // Save to history
        this.saveToHistory('flip_orientation', { 
            orientation: newOrientation 
        });
        
        // Re-render diagram
        this.renderDiagram();
        
        logger.debug('Editor', `Flow map orientation flipped to: ${newOrientation}`);
    }
    
    /**
     * Zoom in programmatically
     */
    zoomIn() {
        const svg = d3.select('#d3-container svg');
        if (svg.empty() || !this.zoomBehavior) return;
        
        svg.transition()
            .duration(300)
            .call(this.zoomBehavior.scaleBy, 1.3);
    }
    
    /**
     * Zoom out programmatically
     */
    zoomOut() {
        const svg = d3.select('#d3-container svg');
        if (svg.empty() || !this.zoomBehavior) return;
        
        svg.transition()
            .duration(300)
            .call(this.zoomBehavior.scaleBy, 0.77);
    }
    
    /**
     * Calculate adaptive dimensions based on current window size
     * This ensures templates are sized appropriately for the user's screen
     * CRITICAL: Always reserves space for properties panel to prevent overlap when clicking nodes
     */
    calculateAdaptiveDimensions() {
        try {
            // Get current window dimensions
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;
            
            // Calculate available canvas space (accounting for toolbar and status bar)
            // Toolbar height: ~60px, Status bar height: ~40px
            const toolbarHeight = 60;
            const statusBarHeight = 40;
            const availableHeight = windowHeight - toolbarHeight - statusBarHeight;
            
            // CRITICAL: Always reserve space for properties panel to prevent diagram overlap
            // When user clicks a node, the properties panel will appear and should not cover the diagram
            const propertyPanelWidth = 320;
            const availableWidth = windowWidth - propertyPanelWidth;
            
            // Calculate optimal dimensions with appropriate padding for visual comfort
            // Use 85% of available space to ensure good margins and prevent edge clipping
            const widthUsageRatio = 0.85;
            const heightUsageRatio = 0.88;
            
            // Calculate optimal dimensions with padding
            const padding = Math.min(40, Math.max(20, Math.min(availableWidth, availableHeight) * 0.05));
            
            // Ensure minimum dimensions for readability (especially on smaller screens)
            const minWidth = 400;
            const minHeight = 300;
            
            const adaptiveWidth = Math.max(minWidth, availableWidth * widthUsageRatio);
            const adaptiveHeight = Math.max(minHeight, availableHeight * heightUsageRatio);
            
            const dimensions = {
                width: Math.round(adaptiveWidth),
                height: Math.round(adaptiveHeight),
                padding: Math.round(padding)
            };
            
            logger.debug('Editor', 'InteractiveEditor: Calculated adaptive dimensions (reserved space for properties panel):', {
                windowSize: { width: windowWidth, height: windowHeight },
                reservedForPropertyPanel: propertyPanelWidth,
                availableSpace: { width: availableWidth, height: availableHeight },
                usageRatios: { width: widthUsageRatio, height: heightUsageRatio },
                finalDimensions: dimensions
            });
            
            return dimensions;
            
        } catch (error) {
            logger.error('Editor', 'Failed to calculate adaptive dimensions', error);
            // Fallback to reasonable defaults
            return {
                width: 800,
                height: 600,
                padding: 40
            };
        }
    }

    /**
     * Fit diagram to full canvas area (entire window width)
     * Used when properties panel is hidden - diagram expands to full width
     * @param {boolean} animate - Whether to animate the transition (default: true)
     */
    fitToFullCanvas(animate = true) {
        try {
            logger.debug('Editor', 'Fitting to full canvas width');
            this._fitToCanvas(animate, false);
            this.isSizedForPanel = false; // Update state
        } catch (error) {
            logger.error('Editor', 'Failed to fit to full canvas', error);
        }
    }

    /**
     * Fit diagram to canvas with properties panel space reserved
     * Used when properties panel is visible or will be visible - reserves 320px for panel
     * @param {boolean} animate - Whether to animate the transition (default: true)
     */
    fitToCanvasWithPanel(animate = true) {
        try {
            logger.debug('Editor', 'Fitting to canvas (panel space reserved)');
            this._fitToCanvas(animate, true);
            this.isSizedForPanel = true; // Update state
        } catch (error) {
            logger.error('Editor', 'Error fitting to canvas with panel:', error);
        }
    }

    /**
     * Internal method: Fit diagram to canvas area
     * @private
     * @param {boolean} animate - Whether to animate the transition
     * @param {boolean} reserveForPanel - Whether to reserve space for properties panel (320px)
     */
    _fitToCanvas(animate, reserveForPanel) {
        const container = d3.select('#d3-container');
        const svg = container.select('svg');
        
        if (svg.empty()) {
            logger.warn('Editor', 'No SVG found for auto-fit');
            return;
        }
        
        // Get all visual elements to calculate content bounds
        const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
        
        if (allElements.empty()) {
            logger.warn('Editor', 'No content found for auto-fit');
            return;
        }
        
        // Calculate content bounds
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        let hasContent = false;
        
        allElements.each(function() {
            try {
                const bbox = this.getBBox();
                if (bbox.width > 0 && bbox.height > 0) {
                    minX = Math.min(minX, bbox.x);
                    minY = Math.min(minY, bbox.y);
                    maxX = Math.max(maxX, bbox.x + bbox.width);
                    maxY = Math.max(maxY, bbox.y + bbox.height);
                    hasContent = true;
                }
            } catch (e) {
                // Skip elements without getBBox
            }
        });
        
        if (!hasContent) {
            logger.warn('Editor', 'No valid content for auto-fit');
            return;
        }
        
        const contentBounds = {
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY
        };
        
        // Get container dimensions
        const containerNode = container.node();
        const containerWidth = containerNode.clientWidth;
        const containerHeight = containerNode.clientHeight;
        const windowWidth = window.innerWidth;
        
        // Check panel visibility for CSS class updates
        const propertyPanel = document.getElementById('property-panel');
        const isPropertyPanelVisible = propertyPanel && propertyPanel.style.display !== 'none';
        
        const aiPanel = document.getElementById('ai-assistant-panel');
        const isAIPanelVisible = aiPanel && !aiPanel.classList.contains('collapsed');
        
        const thinkingPanel = document.getElementById('thinking-panel');
        const isThinkingPanelVisible = thinkingPanel && !thinkingPanel.classList.contains('collapsed');
        
        // Update canvas panel classes for dynamic width adjustment
        const canvasPanel = document.querySelector('.canvas-panel');
        if (canvasPanel) {
            canvasPanel.classList.toggle('property-panel-visible', isPropertyPanelVisible);
            canvasPanel.classList.toggle('ai-panel-visible', isAIPanelVisible && !isPropertyPanelVisible);
            canvasPanel.classList.toggle('thinking-panel-visible', isThinkingPanelVisible && !isPropertyPanelVisible);
        }
        
        // Calculate available canvas width based on reserveForPanel parameter and active panels
        // CRITICAL: Always use windowWidth as reference, not containerWidth (which may be CSS-constrained)
        const propertyPanelWidth = 320;
        const thinkingPanelWidth = 400;  // ThinkGuide panel width
        const aiPanelWidth = 450;        // AI Assistant panel width
        
        let reservedWidth = 0;
        if (reserveForPanel && isPropertyPanelVisible) {
            reservedWidth = propertyPanelWidth;
        } else if (isThinkingPanelVisible) {
            reservedWidth = thinkingPanelWidth;
        } else if (isAIPanelVisible) {
            reservedWidth = aiPanelWidth;
        }
        
        const availableCanvasWidth = windowWidth - reservedWidth;
        
        logger.debug('Editor', 'Canvas fit calculation:', {
            mode: reservedWidth > 0 ? `WITH ${reservedWidth}px panel reserved` : 'FULL width',
            windowWidth,
            containerSize: { width: containerWidth, height: containerHeight },
            isPropertyPanelVisible,
            isThinkingPanelVisible,
            isAIPanelVisible,
            reservedWidth,
            availableCanvasWidth,
            contentBounds,
            animate
        });
        
        // Calculate scale to fit available space with padding
        const padding = 0.12; // 12% padding around content for visual comfort
        const scale = Math.min(
            (availableCanvasWidth * (1 - 2 * padding)) / contentBounds.width,
            (containerHeight * (1 - 2 * padding)) / contentBounds.height
        );
        
        // Don't shrink diagrams that are already reasonably sized
        const minScale = Math.min(
            (availableCanvasWidth * 0.6) / contentBounds.width,
            (containerHeight * 0.6) / contentBounds.height
        );
        const finalScale = Math.max(scale, minScale);
        
        // Calculate viewBox to center content in available space
        const viewBoxX = contentBounds.x - (availableCanvasWidth * padding) / finalScale;
        const viewBoxY = contentBounds.y - (containerHeight * padding) / finalScale;
        const viewBoxWidth = availableCanvasWidth / finalScale;
        const viewBoxHeight = containerHeight / finalScale;
        
        const newViewBox = `${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`;
        
        logger.debug('Editor', 'Fit calculation result:', {
            availableCanvasWidth,
            finalScale: finalScale,
            viewBox: newViewBox
        });
        
        // Apply viewBox with or without animation
        if (animate) {
            svg.transition()
                .duration(750)
                .attr('viewBox', newViewBox)
                .attr('preserveAspectRatio', 'xMidYMid meet');
        } else {
            svg.attr('viewBox', newViewBox)
                .attr('preserveAspectRatio', 'xMidYMid meet');
        }
        
        logger.debug('Editor', `Diagram fitted ${animate ? 'with animation' : 'instantly'}`);
    }

    /**
     * Auto-fit diagram to window if it exceeds viewport bounds
     */
    autoFitDiagramIfNeeded() {
        try {
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                return;
            }
            
            // Get all visual elements
            const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            
            if (allElements.empty()) {
                return;
            }
            
            // Calculate the bounding box of all SVG content
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            let hasContent = false;
            
            allElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox.width > 0 && bbox.height > 0) {
                        minX = Math.min(minX, bbox.x);
                        minY = Math.min(minY, bbox.y);
                        maxX = Math.max(maxX, bbox.x + bbox.width);
                        maxY = Math.max(maxY, bbox.y + bbox.height);
                        hasContent = true;
                    }
                } catch (e) {
                    // Skip elements without getBBox
                }
            });
            
            if (!hasContent || minX === Infinity) {
                return;
            }
            
            const contentBounds = {
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };
            
            // Get container dimensions
            const containerNode = container.node();
            const containerWidth = containerNode.clientWidth;
            const containerHeight = containerNode.clientHeight;
            
            // Get SVG dimensions
            const svgWidth = parseFloat(svg.attr('width')) || containerWidth;
            const svgHeight = parseFloat(svg.attr('height')) || containerHeight;
            
            // Check if content exceeds the visible area (with 10% tolerance)
            const exceedsWidth = contentBounds.width > containerWidth * 0.9;
            const exceedsHeight = contentBounds.height > containerHeight * 0.9;
            const exceedsSvgBounds = (contentBounds.x + contentBounds.width > svgWidth * 0.9) || 
                                     (contentBounds.y + contentBounds.height > svgHeight * 0.9);
            
            if (exceedsWidth || exceedsHeight || exceedsSvgBounds) {
                logger.debug('Editor', 'Diagram exceeds window bounds - auto-fitting to view', {
                    contentBounds,
                    containerSize: { width: containerWidth, height: containerHeight },
                    exceedsWidth,
                    exceedsHeight,
                    exceedsSvgBounds
                });
                
                // Auto-fit with a slight delay to ensure rendering is complete
                setTimeout(() => {
                    this.fitDiagramToWindow();
                }, 100);
            } else {
                logger.debug('Editor', 'Diagram fits within window - no auto-fit needed');
            }
            
        } catch (error) {
            logger.error('Editor', 'Error in auto-fit check:', error);
        }
    }
    
    /**
     * Fit diagram to window - calculates diagram bounds and centers it
     */
    fitDiagramToWindow() {
        try {
            logger.debug('Editor', 'Reset View clicked - fitting diagram to window');
            
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                logger.warn('Editor', 'No SVG found, cannot reset view');
                return;
            }
            
            // Get the SVG node to calculate bounds
            const svgNode = svg.node();
            
            // Get all visual elements (groups, circles, rects, paths, text, etc.)
            const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            
            if (allElements.empty()) {
                logger.warn('Editor', 'No content found in SVG');
                return;
            }
            
            logger.debug('Editor', `Found ${allElements.size()} elements in SVG`);
            
            // Calculate the bounding box of all SVG content
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            let hasContent = false;
            
            allElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox.width > 0 && bbox.height > 0) {
                        minX = Math.min(minX, bbox.x);
                        minY = Math.min(minY, bbox.y);
                        maxX = Math.max(maxX, bbox.x + bbox.width);
                        maxY = Math.max(maxY, bbox.y + bbox.height);
                        hasContent = true;
                    }
                } catch (e) {
                    // Some elements might not have getBBox, skip them
                }
            });
            
            if (!hasContent || minX === Infinity) {
                logger.warn('Editor', 'No valid content bounds found');
                return;
            }
            
            const contentBounds = {
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };
            
            logger.debug('Editor', 'Content bounds:', contentBounds);
            
            // Get container dimensions - account for properties panel space
            const containerNode = container.node();
            const containerWidth = containerNode.clientWidth;
            const containerHeight = containerNode.clientHeight;
            
            // Check panel visibility
            const propertyPanel = document.getElementById('property-panel');
            const isPropertyPanelVisible = propertyPanel && propertyPanel.style.display !== 'none';
            logger.debug('Editor', 'DEBUG: Property panel check:', {
                panelExists: !!propertyPanel,
                displayStyle: propertyPanel?.style.display,
                isVisible: isPropertyPanelVisible
            });
            
            const aiPanel = document.getElementById('ai-assistant-panel');
            const isAIPanelVisible = aiPanel && !aiPanel.classList.contains('collapsed');
            
            // Update canvas panel classes for visual feedback (border, shadow, etc.)
            const canvasPanel = document.querySelector('.canvas-panel');
            if (canvasPanel) {
                canvasPanel.classList.toggle('property-panel-visible', isPropertyPanelVisible);
                canvasPanel.classList.toggle('ai-panel-visible', isAIPanelVisible && !isPropertyPanelVisible);
                logger.debug('Editor', 'DEBUG: Canvas panel classes updated:', {
                    hasPropertyClass: canvasPanel.classList.contains('property-panel-visible'),
                    hasAIClass: canvasPanel.classList.contains('ai-panel-visible'),
                    allClasses: canvasPanel.className
                });
            }
            
            // Calculate available width manually (don't wait for CSS transition)
            let availableCanvasWidth = containerWidth;
            if (isPropertyPanelVisible) {
                availableCanvasWidth = containerWidth - 320; // Property panel width
            } else if (isAIPanelVisible) {
                availableCanvasWidth = containerWidth - 420; // AI panel width
            }
            
            logger.debug('Editor', 'Container dimensions:', { 
                containerWidth, 
                containerHeight,
                panelReduction: containerWidth - availableCanvasWidth 
            });
            logger.debug('Editor', 'Available canvas space:', { 
                availableCanvasWidth, 
                propertyPanelVisible: isPropertyPanelVisible, 
                aiPanelVisible: isAIPanelVisible 
            });
            
            // Continue with the rest of the fitting logic
            this._applyViewBoxTransform(svg, contentBounds, availableCanvasWidth, containerHeight);
        } catch (error) {
            logger.error('Editor', 'Error fitting diagram to window:', error);
        }
    }
    
    /**
     * Apply viewBox transform to fit content
     * @private
     */
    _applyViewBoxTransform(svg, contentBounds, availableCanvasWidth, containerHeight) {
        try {
            // Calculate scale to fit with padding (85% to add margins)
            // Use available canvas width (accounting for properties panel)
            const scale = Math.min(
                availableCanvasWidth / contentBounds.width,
                containerHeight / contentBounds.height
            ) * 0.85;
            
            // Calculate translation to center the content in available space
            const translateX = (availableCanvasWidth - contentBounds.width * scale) / 2 - contentBounds.x * scale;
            const translateY = (containerHeight - contentBounds.height * scale) / 2 - contentBounds.y * scale;
            
            logger.debug('Editor', 'Applying transform:', { scale, translateX, translateY });
            
            // Make SVG responsive to fill container
            svg.attr('width', '100%')
               .attr('height', '100%');
            
            // Get the current viewBox or create one
            const viewBox = svg.attr('viewBox');
            
            // Calculate optimal viewBox with padding
            const padding = Math.min(contentBounds.width, contentBounds.height) * 0.1; // 10% padding
            const newViewBox = `${contentBounds.x - padding} ${contentBounds.y - padding} ${contentBounds.width + padding * 2} ${contentBounds.height + padding * 2}`;
            
            if (viewBox) {
                logger.debug('Editor', 'Old viewBox:', viewBox);
                logger.debug('Editor', 'New viewBox:', newViewBox);
                
                svg.transition()
                    .duration(750)
                    .attr('viewBox', newViewBox);
                    
                this.log('InteractiveEditor: Diagram fitted to window (existing viewBox)', {
                    bounds: contentBounds,
                    oldViewBox: viewBox,
                    newViewBox: newViewBox
                });
            } else {
                // No viewBox exists - create one
                logger.debug('Editor', 'No viewBox found, creating one:', newViewBox);
                
                svg.transition()
                    .duration(750)
                    .attr('viewBox', newViewBox)
                    .attr('preserveAspectRatio', 'xMidYMid meet');
                    
                this.log('InteractiveEditor: Diagram fitted to window (created viewBox)', {
                    bounds: contentBounds,
                    newViewBox: newViewBox
                });
            }
            
        } catch (error) {
            logger.error('Editor', 'Error applying viewBox transform:', error);
        }
    }
    
    /**
     * Fit diagram for export - calculates full diagram bounds regardless of visible canvas
     * This ensures the entire diagram is captured in export, even if parts are off-screen
     */
    fitDiagramForExport() {
        try {
            logger.debug('Editor', 'Fitting diagram for export - calculating full content bounds');
            
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                logger.warn('Editor', 'No SVG found, cannot fit for export');
                return;
            }
            
            // Get all visual elements (including images and foreignObjects that might be missed)
            const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline, image, foreignObject');
            
            if (allElements.empty()) {
                logger.warn('Editor', 'No content found in SVG for export');
                return;
            }
            
            logger.debug('Editor', `Found ${allElements.size()} elements for export bounds calculation`);
            
            // Calculate the bounding box of ALL SVG content
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            let hasContent = false;
            
            allElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox.width > 0 && bbox.height > 0) {
                        // Account for stroke width (getBBox doesn't include it)
                        let strokeWidth = 0;
                        const computedStyle = window.getComputedStyle(this);
                        const strokeWidthStr = computedStyle.strokeWidth || this.getAttribute('stroke-width') || '0';
                        strokeWidth = parseFloat(strokeWidthStr) || 0;
                        
                        // Add half stroke width on each side
                        const halfStroke = strokeWidth / 2;
                        minX = Math.min(minX, bbox.x - halfStroke);
                        minY = Math.min(minY, bbox.y - halfStroke);
                        maxX = Math.max(maxX, bbox.x + bbox.width + halfStroke);
                        maxY = Math.max(maxY, bbox.y + bbox.height + halfStroke);
                        hasContent = true;
                    }
                } catch (e) {
                    // Some elements might not have getBBox, skip them
                }
            });
            
            if (!hasContent || minX === Infinity) {
                logger.warn('Editor', 'No valid content bounds found for export');
                return;
            }
            
            const contentBounds = {
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };
            
            logger.debug('Editor', 'Export content bounds:', contentBounds);
            
            // Use exact content bounds (no padding - stroke widths already accounted for)
            const newViewBox = `${contentBounds.x} ${contentBounds.y} ${contentBounds.width} ${contentBounds.height}`;
            
            logger.debug('Editor', 'Setting export viewBox:', newViewBox);
            
            // Set viewBox immediately without transition (for export)
            svg.attr('viewBox', newViewBox)
               .attr('preserveAspectRatio', 'xMidYMid meet');
            
            this.log('InteractiveEditor: Diagram fitted for export', {
                bounds: contentBounds,
                exportViewBox: newViewBox
            });
            
        } catch (error) {
            logger.error('Editor', 'Error fitting diagram for export:', error);
        }
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
        
        // Reset view button
        const resetViewBtn = document.getElementById('reset-view-btn');
        if (resetViewBtn) {
            this.eventHandlers.resetViewClick = () => {
                this.fitDiagramToWindow();
            };
            resetViewBtn.addEventListener('click', this.eventHandlers.resetViewClick);
        }
        
        // Mobile: Auto-fit on orientation change
        if (this.isMobileDevice()) {
            this.eventHandlers.orientationChange = () => {
                logger.debug('Editor', 'Orientation changed - re-fitting diagram to screen');
                setTimeout(() => {
                    this.fitDiagramToWindow();
                }, 300); // Wait for orientation animation to complete
            };
            window.addEventListener('orientationchange', this.eventHandlers.orientationChange);
            
            // Also handle window resize for responsive mobile browsers
            let resizeTimeout;
            this.eventHandlers.windowResize = () => {
                if (this.isMobileDevice()) {
                    clearTimeout(resizeTimeout);
                    resizeTimeout = setTimeout(() => {
                        logger.debug('Editor', 'Mobile screen resized - re-fitting diagram');
                        this.fitDiagramToWindow();
                    }, 300);
                }
            };
            window.addEventListener('resize', this.eventHandlers.windowResize);
        }
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcut(event) {
        // Ignore shortcuts if user is typing in an input field, textarea, or contenteditable element
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.isContentEditable
        );
        
        // Delete selected nodes (only if not typing in an input)
        if (event.key === 'Delete' || event.key === 'Backspace') {
            if (!isTyping && this.selectedNodes.size > 0) {
                event.preventDefault();
                this.deleteSelectedNodes();
            }
        }
        
        // Undo
        if (event.ctrlKey && event.key === 'z') {
            if (!isTyping) {
                event.preventDefault();
                this.undo();
            }
        }
        
        // Redo
        if (event.ctrlKey && event.key === 'y') {
            if (!isTyping) {
                event.preventDefault();
                this.redo();
            }
        }
        
        // Select all - Allow Ctrl+A in inputs, but prevent on canvas
        if (event.ctrlKey && event.key === 'a') {
            if (!isTyping) {
                event.preventDefault();
                this.selectAll();
            }
        }
    }
    
    /**
     * Open node editor
     */
    openNodeEditor(nodeId, shapeNode, textNode, currentText) {
        // Verbose logging: Log node editor opening
        logger.debug('InteractiveEditor', 'Node Editor Opened', {
            nodeId,
            currentText: currentText?.substring(0, 50),
            textLength: currentText?.length || 0,
            diagramType: this.diagramType,
            timestamp: Date.now()
        });
        
        // Check if this is a dimension node
        let initialText = currentText || 'Edit me';
        const textElement = d3.select(textNode);
        const nodeType = textElement.attr('data-node-type');
        
        if (nodeType === 'dimension' && currentText) {
            // Check if current text is placeholder text (Chinese or English)
            const isPlaceholderCN = currentText.includes('点击填写');
            const isPlaceholderEN = currentText.includes('click to specify');
            
            if (isPlaceholderCN || isPlaceholderEN) {
                // Start with empty string so users can type immediately without deleting placeholder
                initialText = '';
                this.log('InteractiveEditor: Detected dimension placeholder, starting with empty text');
            } else {
                // Dimension has a value - extract ONLY the dimension value, not the wrapper
                // Format is: [拆解维度: 功能模块] or [Decomposition by: Physical Parts]
                // We want to extract only: 功能模块 or Physical Parts
                const dimensionValueMatch = currentText.match(/\[(?:拆解维度|Decomposition by):\s*(.+?)\]/);
                if (dimensionValueMatch && dimensionValueMatch[1]) {
                    initialText = dimensionValueMatch[1].trim();
                    this.log('InteractiveEditor: Extracted dimension value from wrapper', {
                        fullText: currentText,
                        extractedValue: initialText
                    });
                } else {
                    // Fallback: if no wrapper found, use current text as-is
                    initialText = currentText;
                }
            }
        }
        
        const editor = new NodeEditor(
            { id: nodeId, text: initialText },
            (newText) => {
                this.log('InteractiveEditor: Node editor - Save callback triggered', {
                    nodeId,
                    newText: newText?.substring(0, 50)
                });
                
                // For dimension nodes, strip any wrapper text that user might have included
                let finalText = newText;
                if (nodeType === 'dimension' && newText) {
                    // If user somehow included the wrapper, extract just the value
                    const valueMatch = newText.match(/\[(?:拆解维度|Decomposition by):\s*(.+?)\]/);
                    if (valueMatch && valueMatch[1]) {
                        finalText = valueMatch[1].trim();
                        this.log('InteractiveEditor: Stripped wrapper from dimension text', {
                            original: newText,
                            cleaned: finalText
                        });
                    }
                }
                
                this.updateNodeText(nodeId, shapeNode, textNode, finalText);
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
        } else if (this.diagramType === 'mindmap') {
            this.updateMindMapText(nodeId, shapeNode, newText);
        } else {
            // Generic text update for other diagram types
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
        }
        
        // Save to history
        this.saveToHistory('update_text', { nodeId, newText });
    }
    
    /**
     * Update Mind Map node text
     */
    updateMindMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        // Declare branchIndex and childIndex at function scope so they're accessible later
        let branchIndex = NaN;
        let childIndex = NaN;
        
        if (nodeType === 'topic') {
            // Update the central topic
            this.currentSpec.topic = newText;
            logger.debug('Editor', 'Updated MindMap topic to:', newText);
        } else if (nodeType === 'branch') {
            // Update branch label in children array
            branchIndex = parseInt(shape.attr('data-branch-index'));
            if (!isNaN(branchIndex) && Array.isArray(this.currentSpec.children)) {
                if (this.currentSpec.children[branchIndex]) {
                    this.currentSpec.children[branchIndex].label = newText;
                    logger.debug('Editor', `Updated branch[${branchIndex}].label to:`, newText);
                }
            }
        } else if (nodeType === 'child') {
            // Update child label in nested children array
            branchIndex = parseInt(shape.attr('data-branch-index'));
            childIndex = parseInt(shape.attr('data-child-index'));
            if (!isNaN(branchIndex) && !isNaN(childIndex) && 
                Array.isArray(this.currentSpec.children) &&
                this.currentSpec.children[branchIndex] &&
                Array.isArray(this.currentSpec.children[branchIndex].children)) {
                if (this.currentSpec.children[branchIndex].children[childIndex]) {
                    this.currentSpec.children[branchIndex].children[childIndex].label = newText;
                    logger.debug('Editor', `Updated branch[${branchIndex}].children[${childIndex}].label to:`, newText);
                }
            }
        }
        
        // Update the text in positions as well (if layout exists)
        if (this.currentSpec._layout && this.currentSpec._layout.positions) {
            const positions = this.currentSpec._layout.positions;
            if (nodeType === 'topic' && positions.topic) {
                positions.topic.text = newText;
            } else if (nodeType === 'branch' && !isNaN(branchIndex) && positions[`branch_${branchIndex}`]) {
                positions[`branch_${branchIndex}`].text = newText;
            } else if (nodeType === 'child' && !isNaN(branchIndex) && !isNaN(childIndex) && positions[`child_${branchIndex}_${childIndex}`]) {
                positions[`child_${branchIndex}_${childIndex}`].text = newText;
            }
        }
        
        // Store selected nodes before re-render
        const selectedNodesBeforeRender = this.selectionManager ? 
            Array.from(this.selectionManager.getSelectedNodes()) : [];
        
        // Re-render with updated text (positions stay the same)
        this.renderDiagram().then(() => {
            // Restore selection styling after re-render
            // When nodes are re-rendered, they lose their selection styling (stroke, stroke-width, filter)
            // We need to re-apply the selection styling to maintain visual feedback
            if (this.selectionManager && selectedNodesBeforeRender.length > 0) {
                selectedNodesBeforeRender.forEach(nodeId => {
                    // Re-apply selection styling to restore the border/highlight
                    this.selectionManager.updateVisualSelection(nodeId, true);
                });
            }
        }).catch(err => {
            logger.error('Editor', 'Error restoring selection after mindmap text update:', err);
        });
    }
    
    /**
     * Update Circle Map node text
     */
    updateCircleMapText(nodeId, shapeNode, newText) {
        if (!this.currentSpec) {
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        // CRITICAL FIX: Circle map uses 'center', not 'topic'!
        if (nodeType === 'topic' || nodeType === 'center') {
            // Update the central topic
            this.currentSpec.topic = newText;
            logger.debug('Editor', 'Updated Circle Map topic to:', newText);
        } else if (nodeType === 'context') {
            // Update context array
            const arrayIndex = parseInt(shape.attr('data-array-index'));
            if (!isNaN(arrayIndex) && Array.isArray(this.currentSpec.context)) {
                this.currentSpec.context[arrayIndex] = newText;
                logger.debug('Editor', `Updated context[${arrayIndex}] to:`, newText);
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
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the central topic
            this.currentSpec.topic = newText;
            logger.debug('Editor', 'Updated Bubble Map topic to:', newText);
        } else if (nodeType === 'attribute') {
            // Update attributes array
            const arrayIndex = parseInt(shape.attr('data-array-index'));
            if (!isNaN(arrayIndex) && Array.isArray(this.currentSpec.attributes)) {
                this.currentSpec.attributes[arrayIndex] = newText;
                logger.debug('Editor', `Updated attribute[${arrayIndex}] to:`, newText);
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
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        switch(nodeType) {
            case 'left':
                // Update left topic
                this.currentSpec.left = newText;
                logger.debug('Editor', 'Updated Double Bubble Map left topic to:', newText);
                break;
                
            case 'right':
                // Update right topic
                this.currentSpec.right = newText;
                logger.debug('Editor', 'Updated Double Bubble Map right topic to:', newText);
                break;
                
            case 'similarity':
                // Update similarities array
                const simIndex = parseInt(shape.attr('data-array-index'));
                if (!isNaN(simIndex) && Array.isArray(this.currentSpec.similarities)) {
                    this.currentSpec.similarities[simIndex] = newText;
                    logger.debug('Editor', `Updated similarity[${simIndex}] to:`, newText);
                }
                break;
                
            case 'left_difference':
                // Update left_differences array
                const leftDiffIndex = parseInt(shape.attr('data-array-index'));
                if (!isNaN(leftDiffIndex) && Array.isArray(this.currentSpec.left_differences)) {
                    this.currentSpec.left_differences[leftDiffIndex] = newText;
                    logger.debug('Editor', `Updated left_difference[${leftDiffIndex}] to:`, newText);
                }
                break;
                
            case 'right_difference':
                // Update right_differences array
                const rightDiffIndex = parseInt(shape.attr('data-array-index'));
                if (!isNaN(rightDiffIndex) && Array.isArray(this.currentSpec.right_differences)) {
                    this.currentSpec.right_differences[rightDiffIndex] = newText;
                    logger.debug('Editor', `Updated right_difference[${rightDiffIndex}] to:`, newText);
                }
                break;
                
            default:
                logger.warn('Editor', `Unknown node type: ${nodeType}`);
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
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the main topic (whole in brace map terminology)
            this.currentSpec.whole = newText;
            logger.debug('Editor', 'Updated Brace Map whole to:', newText);
        } else if (nodeType === 'dimension') {
            // Update the decomposition dimension
            // User can change this to specify how they want to decompose the topic
            this.currentSpec.dimension = newText;
            logger.debug('Editor', 'Updated Brace Map dimension to:', newText);
        } else if (nodeType === 'part') {
            // Update part name in the parts array
            const partIndex = parseInt(shape.attr('data-part-index'));
            if (!isNaN(partIndex) && this.currentSpec.parts && partIndex < this.currentSpec.parts.length) {
                this.currentSpec.parts[partIndex].name = newText;
                logger.debug('Editor', `Updated part ${partIndex} to:`, newText);
            }
        } else if (nodeType === 'subpart') {
            // Update subpart name in the parts array
            const partIndex = parseInt(shape.attr('data-part-index'));
            const subpartIndex = parseInt(shape.attr('data-subpart-index'));
            
            if (!isNaN(partIndex) && !isNaN(subpartIndex) && this.currentSpec.parts && partIndex < this.currentSpec.parts.length) {
                const part = this.currentSpec.parts[partIndex];
                if (part.subparts && subpartIndex < part.subparts.length) {
                    part.subparts[subpartIndex].name = newText;
                    logger.debug('Editor', `Updated subpart ${partIndex}-${subpartIndex} to:`, newText);
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
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'title') {
            // Update the title
            this.currentSpec.title = newText;
            logger.debug('Editor', 'Updated Flow Map title to:', newText);
        } else if (nodeType === 'step') {
            // Update step in the steps array
            const stepIndex = parseInt(shape.attr('data-step-index'));
            if (!isNaN(stepIndex) && this.currentSpec.steps && stepIndex < this.currentSpec.steps.length) {
                this.currentSpec.steps[stepIndex] = newText;
                logger.debug('Editor', `Updated step ${stepIndex} to:`, newText);
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
                    logger.debug('Editor', `Updated substep ${stepIndex}-${substepIndex} to:`, newText);
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
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'event') {
            // Update the central event
            this.currentSpec.event = newText;
            logger.debug('Editor', 'Updated Multi-Flow Map event to:', newText);
        } else if (nodeType === 'cause') {
            // Update cause in the causes array
            const causeIndex = parseInt(shape.attr('data-cause-index'));
            if (!isNaN(causeIndex) && this.currentSpec.causes && causeIndex < this.currentSpec.causes.length) {
                this.currentSpec.causes[causeIndex] = newText;
                logger.debug('Editor', `Updated cause ${causeIndex} to:`, newText);
            }
        } else if (nodeType === 'effect') {
            // Update effect in the effects array
            const effectIndex = parseInt(shape.attr('data-effect-index'));
            if (!isNaN(effectIndex) && this.currentSpec.effects && effectIndex < this.currentSpec.effects.length) {
                this.currentSpec.effects[effectIndex] = newText;
                logger.debug('Editor', `Updated effect ${effectIndex} to:`, newText);
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
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the root topic
            this.currentSpec.topic = newText;
            logger.debug('Editor', 'Updated Tree Map topic to:', newText);
        } else if (nodeType === 'dimension') {
            // Update the classification dimension
            this.currentSpec.dimension = newText;
            // Also update the data-dimension-value attribute
            shape.attr('data-dimension-value', newText);
            logger.debug('Editor', 'Updated Tree Map dimension to:', newText);
        } else if (nodeType === 'category') {
            // Update category text in children array
            const categoryIndex = parseInt(shape.attr('data-category-index'));
            if (!isNaN(categoryIndex) && this.currentSpec.children && categoryIndex < this.currentSpec.children.length) {
                this.currentSpec.children[categoryIndex].text = newText;
                logger.debug('Editor', `Updated category ${categoryIndex} to:`, newText);
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
                    logger.debug('Editor', `Updated leaf ${leafIndex} in category ${categoryIndex} to:`, newText);
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
            logger.error('Editor', 'No spec available');
            return;
        }
        
        // Get the shape element to extract metadata
        const shape = d3.select(shapeNode || `[data-node-id="${nodeId}"]`);
        if (shape.empty()) {
            logger.error('Editor', 'Cannot find node shape');
            return;
        }
        
        const nodeType = shape.attr('data-node-type');
        const pairIndex = parseInt(shape.attr('data-pair-index'));
        
        if (nodeType === 'dimension') {
            // Update dimension label
            this.currentSpec.dimension = newText;
            logger.debug('Editor', `Updated dimension to: "${newText}"`);
            
            // Update the data attribute
            shape.attr('data-dimension-value', newText);
            
            // Re-render the diagram to update the label
            this.renderDiagram();
            return;
        } else if (!isNaN(pairIndex) && pairIndex < this.currentSpec.analogies.length) {
            if (nodeType === 'left') {
                // Update left item in the pair
                this.currentSpec.analogies[pairIndex].left = newText;
                logger.debug('Editor', `Updated left item in pair ${pairIndex} to: "${newText}"`);
            } else if (nodeType === 'right') {
                // Update right item in the pair
                this.currentSpec.analogies[pairIndex].right = newText;
                logger.debug('Editor', `Updated right item in pair ${pairIndex} to: "${newText}"`);
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
        // Verbose logging: Log text edit
        logger.debug('InteractiveEditor', 'Text Edit Applied', {
            nodeId,
            newText: newText.substring(0, 50) + (newText.length > 50 ? '...' : ''),
            textLength: newText.length,
            diagramType: this.diagramType,
            timestamp: Date.now()
        });
        
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
            case 'mindmap':
                this.addNodeToMindMap();
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
            logger.error('Editor', 'Invalid circle map spec');
            return;
        }
        
        // Add new context item to spec with language support
        const newContextText = window.languageManager?.getCurrentLanguage() === 'zh' ? '新背景' : 'New Context';
        this.currentSpec.context.push(newContextText);
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'circle_map', 
            contextCount: this.currentSpec.context.length 
        });
        
        logger.debug('Editor', 'Added new context node to Circle Map');
    }
    
    /**
     * Add a new node to Bubble Map
     */
    addNodeToBubbleMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.attributes)) {
            logger.error('Editor', 'Invalid bubble map spec');
            return;
        }
        
        // Add new attribute item to spec with language support
        const newAttrText = window.languageManager?.translate('newAttribute') || 'New Attribute';
        this.currentSpec.attributes.push(newAttrText);
        
        // Re-render the diagram with new node
        this.renderDiagram();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'bubble_map', 
            attributeCount: this.currentSpec.attributes.length 
        });
        
        logger.debug('Editor', 'Added new attribute node to Bubble Map');
    }
    
    /**
     * Add a new node to Double Bubble Map
     * Requires user to select a node type first (similarity or difference)
     */
    addNodeToDoubleBubbleMap() {
        if (!this.currentSpec) {
            logger.error('Editor', 'Invalid double bubble map spec');
            return;
        }
        
        // Check if user has selected a node
        const selected = Array.from(this.selectedNodes);
        if (selected.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            logger.debug('Editor', 'DoubleBubbleMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the type of the selected node
        const selectedElement = d3.select(`[data-node-id="${selected[0]}"]`);
        const nodeType = selectedElement.attr('data-node-type');
        
        if (!nodeType) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('couldNotDetermineNodeType'), 'error');
            }
            return;
        }
        
        // Add node based on selected type
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        switch(nodeType) {
            case 'similarity':
                // Add similarity
                if (!Array.isArray(this.currentSpec.similarities)) {
                    this.currentSpec.similarities = [];
                }
                const newSimilarityText = lang === 'zh' ? '新相似点' : 'New Similarity';
                this.currentSpec.similarities.push(newSimilarityText);
                logger.debug('Editor', 'Added new similarity node');
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
                const leftDiffText = lang === 'zh' ? '左差异' : 'Left Difference';
                const rightDiffText = lang === 'zh' ? '右差异' : 'Right Difference';
                this.currentSpec.left_differences.push(leftDiffText);
                this.currentSpec.right_differences.push(rightDiffText);
                logger.debug('Editor', 'Added paired difference nodes');
                break;
                
            case 'left':
            case 'right':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotAddMainTopics'), 'warning');
                }
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('unknownNodeType'), 'error');
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
                this.toolbarManager.showNotification(this.getNotif('similarityNodeAdded'), 'success');
            } else {
                this.toolbarManager.showNotification(this.getNotif('differencePairAdded'), 'success');
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
            logger.error('Editor', 'Invalid brace map spec');
            return;
        }
        
        // Check if user has selected a node
        const selected = Array.from(this.selectedNodes);
        if (selected.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            logger.debug('Editor', 'BraceMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the type of the selected node
        const selectedElement = d3.select(`[data-node-id="${selected[0]}"]`);
        const nodeType = selectedElement.attr('data-node-type');
        
        if (!nodeType) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('couldNotDetermineNodeType'), 'error');
            }
            return;
        }
        
        // Handle different node types
        switch(nodeType) {
            case 'part': {
                // Add new part node to the parts array with two default subparts
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const newPartText = lang === 'zh' ? '新部分' : 'New Part';
                const newSubpartText = lang === 'zh' ? '新子部分' : 'New Subpart';
                this.currentSpec.parts.push({
                    name: newPartText,
                    subparts: [
                        { name: `${newSubpartText}1` },
                        { name: `${newSubpartText}2` }
                    ]
                });
                logger.debug('Editor', 'Added new part node with 2 subparts');
                
                if (this.toolbarManager) {
                    const message = lang === 'zh' ? '新部分及2个子部分已添加！' : 'New part added with 2 subparts!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'subpart': {
                // Get part index from selected subpart
                const partIndexAttr = selectedElement.attr('data-part-index');
                const partIndex = parseInt(partIndexAttr);
                
                // Enhanced error logging
                logger.debug('Editor', 'BraceMap subpart add: Parsing part index', {
                    selectedNodeId: selected[0],
                    partIndexAttr: partIndexAttr,
                    partIndexParsed: partIndex,
                    isNaN: isNaN(partIndex),
                    partsArrayLength: this.currentSpec.parts.length,
                    allElementAttributes: {
                        'data-node-id': selectedElement.attr('data-node-id'),
                        'data-node-type': selectedElement.attr('data-node-type'),
                        'data-part-index': selectedElement.attr('data-part-index'),
                        'data-subpart-index': selectedElement.attr('data-subpart-index')
                    }
                });
                
                if (isNaN(partIndex) || partIndex < 0 || partIndex >= this.currentSpec.parts.length) {
                    logger.error('Editor', 'BraceMap subpart add FAILED: Invalid part index', {
                        partIndexAttr: partIndexAttr,
                        partIndexParsed: partIndex,
                        isNaN: isNaN(partIndex),
                        isNegative: partIndex < 0,
                        isOutOfBounds: partIndex >= this.currentSpec.parts.length,
                        partsCount: this.currentSpec.parts.length
                    });
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification(this.getNotif('invalidPartIndex'), 'error');
                    }
                    return;
                }
                
                // Add new subpart to the same part as the selected subpart
                if (!Array.isArray(this.currentSpec.parts[partIndex].subparts)) {
                    this.currentSpec.parts[partIndex].subparts = [];
                }
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const newSubpartText = lang === 'zh' ? '新子部分' : 'New Subpart';
                this.currentSpec.parts[partIndex].subparts.push({
                    name: newSubpartText
                });
                logger.debug('Editor', `Added new subpart to part ${partIndex}`);
                
                if (this.toolbarManager) {
                    const message = lang === 'zh' ? '新子部分已添加！' : 'New subpart added!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'topic':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotAddToTopic'), 'warning');
                }
                // Don't re-render, just return
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('unknownNodeSelectPart'), 'error');
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
            logger.error('Editor', 'Invalid flow map spec');
            return;
        }
        
        // Check if a node is selected
        const selectedNodes = Array.from(this.selectedNodes);
        if (selectedNodes.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            logger.debug('Editor', 'FlowMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            logger.error('Editor', 'Selected node not found');
            return;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        logger.debug('Editor', 'Adding to flow map, selected node type:', nodeType);
        
        // Handle different node types
        switch (nodeType) {
            case 'step': {
                // Get the index of the selected step
                const stepIndex = parseInt(selectedElement.attr('data-step-index'));
                
                if (isNaN(stepIndex) || stepIndex < 0 || stepIndex >= this.currentSpec.steps.length) {
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification(this.getNotif('invalidStepIndex'), 'error');
                    }
                    return;
                }
                
                // Insert new step right after the selected step
                const newStep = window.languageManager?.translate('newStep') || 'New Step';
                this.currentSpec.steps.splice(stepIndex + 1, 0, newStep);
                
                // Also insert substeps entry at the same position with 2 default substeps
                if (!Array.isArray(this.currentSpec.substeps)) {
                    this.currentSpec.substeps = [];
                }
                const newSubstepText = window.languageManager?.translate('newSubitem') || 'New Substep';
                this.currentSpec.substeps.splice(stepIndex + 1, 0, {
                    step: newStep,
                    substeps: [`${newSubstepText}1`, `${newSubstepText}2`]
                });
                
                logger.debug('Editor', `Inserted new step after step ${stepIndex} with 2 substeps`);
                
                if (this.toolbarManager) {
                    const message = window.languageManager?.getCurrentLanguage() === 'zh' ? '新步骤及2个子步骤已添加！' : 'New step added with 2 substeps!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'substep': {
                // Get step index and substep index from selected substep
                const stepIndex = parseInt(selectedElement.attr('data-step-index'));
                const substepIndex = parseInt(selectedElement.attr('data-substep-index'));
                
                if (isNaN(stepIndex) || stepIndex < 0 || stepIndex >= this.currentSpec.steps.length) {
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification(this.getNotif('invalidStepIndex'), 'error');
                    }
                    return;
                }
                
                if (isNaN(substepIndex) || substepIndex < 0) {
                    if (this.toolbarManager) {
                        this.toolbarManager.showNotification(this.getNotif('invalidSubstepIndex'), 'error');
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
                const newSubstepText = window.languageManager?.translate('newSubitem') || 'New Substep';
                substepsEntry.substeps.splice(substepIndex + 1, 0, newSubstepText);
                
                logger.debug('Editor', `Inserted new substep after substep ${substepIndex} in step ${stepIndex}`);
                
                if (this.toolbarManager) {
                    const message = window.languageManager?.getCurrentLanguage() === 'zh' ? '新子步骤已添加！' : 'New substep added!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'title':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotAddToTitle'), 'warning');
                }
                // Don't re-render, just return
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('selectStepOrSubstep'), 'warning');
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
            logger.error('Editor', 'Invalid multi-flow map spec');
            return;
        }
        
        // Check if a node is selected
        const selectedNodes = Array.from(this.selectedNodes);
        if (selectedNodes.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            // Don't show duplicate notification here
            logger.debug('Editor', 'MultiFlowMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            logger.error('Editor', 'Selected node not found');
            return;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        logger.debug('Editor', 'Adding to multi-flow map, selected node type:', nodeType);
        
        // Handle different node types
        switch (nodeType) {
            case 'cause': {
                // Add new cause to the causes array
                const newCauseText = window.languageManager?.translate('newCause') || 'New Cause';
                this.currentSpec.causes.push(newCauseText);
                
                logger.debug('Editor', `Added new cause. Total causes: ${this.currentSpec.causes.length}`);
                
                if (this.toolbarManager) {
                    const message = window.languageManager?.getCurrentLanguage() === 'zh' ? '新原因已添加！' : 'New cause added!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'effect': {
                // Add new effect to the effects array
                const newEffectText = window.languageManager?.translate('newEffect') || 'New Effect';
                this.currentSpec.effects.push(newEffectText);
                
                logger.debug('Editor', `Added new effect. Total effects: ${this.currentSpec.effects.length}`);
                
                if (this.toolbarManager) {
                    const message = window.languageManager?.getCurrentLanguage() === 'zh' ? '新结果已添加！' : 'New effect added!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'event':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotAddToEvent'), 'warning');
                }
                // Don't re-render, just return
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('selectCauseOrEffect'), 'warning');
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
            logger.error('Editor', 'Invalid tree map spec');
            return;
        }
        
        // Check if a node is selected
        const selectedNodes = Array.from(this.selectedNodes);
        if (selectedNodes.length === 0) {
            // NOTE: Notification is already shown by ToolbarManager.handleAddNode()
            logger.debug('Editor', 'TreeMap: No node selected, skipping add (notification already shown by toolbar)');
            return;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            logger.error('Editor', 'Selected node not found');
            return;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        logger.debug('Editor', 'Adding to tree map, selected node type:', nodeType);
        
        // Handle different node types
        switch (nodeType) {
            case 'category': {
                // Add new category (with 3 children) to children array
                const categoryIndex = parseInt(selectedElement.attr('data-category-index'));
                const newCategoryText = window.languageManager?.translate('newCategory') || 'New Category';
                const newItemText = window.languageManager?.translate('newItem') || 'New Item';
                const newCategory = {
                    text: newCategoryText,
                    children: [
                        { text: `${newItemText}1` },
                        { text: `${newItemText}2` },
                        { text: `${newItemText}3` }
                    ]
                };
                
                // Insert after selected category
                this.currentSpec.children.splice(categoryIndex + 1, 0, newCategory);
                
                logger.debug('Editor', `Added new category after index ${categoryIndex}. Total categories: ${this.currentSpec.children.length}`);
                
                if (this.toolbarManager) {
                    const message = window.languageManager?.getCurrentLanguage() === 'zh' ? '新类别及3个子项已添加！' : 'New category added with 3 children!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'leaf': {
                // Add new leaf/child to the parent category
                const categoryIndex = parseInt(selectedElement.attr('data-category-index'));
                const leafIndex = parseInt(selectedElement.attr('data-leaf-index'));
                
                if (categoryIndex < 0 || categoryIndex >= this.currentSpec.children.length) {
                    logger.error('Editor', 'Invalid category index');
                    return;
                }
                
                const category = this.currentSpec.children[categoryIndex];
                if (!Array.isArray(category.children)) {
                    category.children = [];
                }
                
                // Insert after selected leaf
                const newItemText = window.languageManager?.translate('newItem') || 'New Child';
                category.children.splice(leafIndex + 1, 0, { text: newItemText });
                
                logger.debug('Editor', `Added new child to category ${categoryIndex} after leaf ${leafIndex}. Total children: ${category.children.length}`);
                
                if (this.toolbarManager) {
                    const message = window.languageManager?.getCurrentLanguage() === 'zh' ? '新子项已添加！' : 'New child added!';
                    this.toolbarManager.showNotification(message, 'success');
                }
                break;
            }
                
            case 'topic':
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotAddToTopicSelectCategory'), 'warning');
                }
                return;
                
            default:
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('selectCategoryOrChild'), 'warning');
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
            logger.error('Editor', 'Invalid bridge map spec');
            return;
        }
        
        // For bridge map, always add pairs to the end (no selection required)
        // This is because bridge maps are sequential in nature
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        const newPair = {
            left: lang === 'zh' ? '新左项' : 'New Left',
            right: lang === 'zh' ? '新右项' : 'New Right'
        };
        
        this.currentSpec.analogies.push(newPair);
        
        logger.debug('Editor', `Added new analogy pair at end. Total pairs: ${this.currentSpec.analogies.length}`);
        
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
            logger.error('Editor', 'Invalid concept map spec');
            return;
        }
        
        // Add new concept to spec with language support
        const newConceptText = window.languageManager?.translate('newConcept') || 'New Concept';
        this.currentSpec.concepts.push({
            text: newConceptText,
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
        
        logger.debug('Editor', 'Added new concept node to Concept Map');
    }
    
    /**
     * Add a new node to Mind Map
     */
    async addNodeToMindMap() {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.children)) {
            logger.error('Editor', 'Invalid mind map spec');
            return;
        }
        
        // Get selected nodes
        const selectedNodes = Array.from(this.selectedNodes);
        
        // Check if no node is selected
        if (selectedNodes.length === 0) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('selectBranchOrSubitem'), 'warning');
            }
            logger.debug('Editor', 'MindMap: No node selected, skipping add');
            return;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            logger.error('Editor', 'Selected node not found');
            return;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        
        // Don't allow adding to the central topic
        if (nodeType === 'topic' || !nodeType) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('cannotAddToCentral'), 'warning');
            }
            logger.debug('Editor', 'MindMap: Cannot add to central topic');
            return;
        }
        
        // Handle different node types
        if (nodeType === 'branch') {
            // Adding a new branch - find the branch index
            const branchIndex = parseInt(selectedElement.attr('data-array-index') || selectedElement.attr('data-branch-index'));
            
            if (isNaN(branchIndex) || branchIndex < 0) {
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('invalidBranchIndex'), 'error');
                }
                return;
            }
            
            // Add new branch with 2 subitems (following the template pattern)
            const newBranchIndex = this.currentSpec.children.length;
            const newBranchText = window.languageManager?.translate('newBranch') || 'New Branch';
            const newSubitemText = window.languageManager?.translate('newSubitem') || 'Sub-item';
            this.currentSpec.children.push({
                id: `branch_${newBranchIndex}`,
                label: `${newBranchText}${newBranchIndex + 1}`,
                text: `${newBranchText}${newBranchIndex + 1}`,
                children: [
                    {
                        id: `sub_${newBranchIndex}_0`,
                        label: `${newSubitemText}${newBranchIndex + 1}.1`,
                        text: `${newSubitemText}${newBranchIndex + 1}.1`,
                        children: []
                    },
                    {
                        id: `sub_${newBranchIndex}_1`,
                        label: `${newSubitemText}${newBranchIndex + 1}.2`,
                        text: `${newSubitemText}${newBranchIndex + 1}.2`,
                        children: []
                    }
                ]
            });
            
            logger.debug('Editor', `Added new branch with 2 subitems. Total branches: ${this.currentSpec.children.length}`);
            
            if (this.toolbarManager) {
                const message = window.languageManager?.getCurrentLanguage() === 'zh' ? '新分支及2个子项已添加！' : 'New branch with 2 sub-items added!';
                this.toolbarManager.showNotification(message, 'success');
            }
            
        } else if (nodeType === 'child' || nodeType === 'subitem') {
            // Adding a sub-item - find the parent branch
            const branchIndex = parseInt(selectedElement.attr('data-branch-index'));
            
            if (isNaN(branchIndex) || branchIndex < 0 || branchIndex >= this.currentSpec.children.length) {
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('invalidBranchIndex'), 'error');
                }
                return;
            }
            
            const branch = this.currentSpec.children[branchIndex];
            if (!branch || !Array.isArray(branch.children)) {
                logger.error('Editor', 'Invalid branch structure');
                return;
            }
            
            // Add new sub-item to the branch
            const newChildIndex = branch.children.length;
            branch.children.push({
                id: `sub_${branchIndex}_${newChildIndex}`,
                label: `Sub-item ${branchIndex + 1}.${newChildIndex + 1}`,
                text: `Sub-item ${branchIndex + 1}.${newChildIndex + 1}`,
                children: []
            });
            
            logger.debug('Editor', `Added new sub-item to branch ${branchIndex}. Total sub-items: ${branch.children.length}`);
            
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('newSubitemAdded'), 'success');
            }
        } else {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('unknownNodeSelectBranch'), 'error');
            }
            return;
        }
        
        // For mind maps, we need to recalculate layout from backend before rendering
        await this.recalculateMindMapLayout();
        
        // Save to history
        this.saveToHistory('add_node', { 
            diagramType: 'mindmap',
            nodeType: nodeType,
            totalBranches: this.currentSpec.children.length
        });
    }
    
    /**
     * Recalculate Mind Map layout from backend
     * This is necessary because mind maps require positioned layout data
     */
    async recalculateMindMapLayout() {
        if (!this.currentSpec) {
            logger.error('Editor', 'No spec available for recalculation');
            return;
        }
        
        try {
            logger.debug('Editor', 'Recalculating mind map layout from backend...');
            
            // Show loading state
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('updatingLayout'), 'info');
            }
            
            // Call backend to recalculate layout
            const response = await window.auth.fetch('/api/recalculate_mindmap_layout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    spec: this.currentSpec
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Update spec with new layout data
            if (data.spec && data.spec._layout) {
                this.currentSpec._layout = data.spec._layout;
                this.currentSpec._recommended_dimensions = data.spec._recommended_dimensions;
                logger.debug('Editor', 'Layout recalculated successfully');
                
                // Re-render with new layout
                this.renderDiagram();
            } else {
                logger.warn('Editor', 'Backend did not return layout data');
                // Still try to render
                this.renderDiagram();
            }
            
        } catch (error) {
            logger.error('Editor', 'Error recalculating mind map layout:', error);
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('layoutUpdateFailed'), 'warning');
            }
            // Still try to render even if layout calculation failed
            this.renderDiagram();
        }
    }
    
    /**
     * Add a generic node (fallback for other diagram types)
     */
    addGenericNode() {
        // Get SVG container dimensions for positioning
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            logger.error('Editor', 'SVG container not found');
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
            .text(window.languageManager?.translate('newNode') || 'New Node');
        
        // Add drag behavior to this specific node only
        this.addDragBehavior(circle, text);
        
        // Add click handlers to this specific node
        const self = this;
        const newNodeText = window.languageManager?.translate('newNode') || 'New Node';
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
            self.openNodeEditor(nodeId, circle.node(), text.node(), newNodeText);
        });
        
        text.on('dblclick', (event) => {
            event.stopPropagation();
            self.openNodeEditor(nodeId, circle.node(), text.node(), newNodeText);
        });
        
        // Select the new node
        this.selectionManager.clearSelection();
        this.selectionManager.selectNode(nodeId);
        
        // Save to history
        this.saveToHistory('add_node', { nodeId, x: newX, y: newY });
        
        logger.debug('Editor', `Node ${nodeId} added at (${newX.toFixed(0)}, ${newY.toFixed(0)})`);
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
        } else if (this.diagramType === 'mindmap') {
            this.deleteMindMapNodes(nodesToDelete);
        } else {
            this.deleteGenericNodes(nodesToDelete);
        }
        
        // Clear selection
        this.selectionManager.clearSelection();
        
        // Save to history
        this.saveToHistory('delete_nodes', { nodeIds: nodesToDelete });
        
        logger.debug('Editor', `Successfully deleted ${nodesToDelete.length} node(s)`);
    }
    
    /**
     * Delete Circle Map nodes
     */
    deleteCircleMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.context)) {
            logger.error('Editor', 'Invalid circle map spec');
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
        
        logger.debug('Editor', `Deleted ${indicesToDelete.length} context node(s) from Circle Map`);
        
        // Re-render
        this.renderDiagram();
    }
    
    /**
     * Delete Bubble Map nodes
     */
    deleteBubbleMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.attributes)) {
            logger.error('Editor', 'Invalid bubble map spec');
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
        
        logger.debug('Editor', `Deleted ${indicesToDelete.length} attribute node(s) from Bubble Map`);
        
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
            logger.error('Editor', 'Invalid double bubble map spec');
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
            logger.debug('Editor', `Deleted ${uniqueIndices.length} similarity node(s)`);
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
            logger.debug('Editor', `Deleted ${uniqueIndices.length} difference pair(s) (${uniqueIndices.length * 2} nodes total)`);
            
            // Show notification about paired deletion
            window.dispatchEvent(new CustomEvent('show-notification', {
                detail: {
                    message: `Deleted ${uniqueIndices.length} difference pair${uniqueIndices.length > 1 ? 's' : ''} (left & right)`,
                    type: 'success'
                }
            }));
        }
        
        logger.debug('Editor', `Total deleted from Double Bubble Map: ${deletedCount} node(s)`);
        
        // Re-render - this will automatically remove connecting lines
        this.renderDiagram();
    }
    
    /**
     * Delete Brace Map nodes (parts and subparts)
     */
    deleteBraceMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.parts)) {
            logger.error('Editor', 'Invalid brace map spec');
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
            logger.debug('Editor', `Deleted ${deletedCount} subpart(s)`);
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
            logger.debug('Editor', `Deleted ${uniquePartIndices.length} part(s)`);
        }
        
        logger.debug('Editor', `Total deleted from Brace Map: ${deletedCount} node(s)`);
        
        // Re-render - this will automatically rebuild the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Flow Map nodes (steps and substeps)
     */
    deleteFlowMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.steps)) {
            logger.error('Editor', 'Invalid flow map spec');
            return;
        }
        
        // Separate node IDs by type
        const stepNodesToDelete = [];
        const substepNodesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                logger.warn('Editor', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'title') {
                // Don't allow deletion of title
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotDeleteTitle'), 'warning');
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
        
        logger.debug('Editor', 'Flow map deletion:', { stepNodesToDelete, substepNodesToDelete });
        
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
                        logger.debug('Editor', `Deleted substep ${index} from step ${stepIndex}`);
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
                logger.debug('Editor', `Deleted step ${index}: ${stepName}`);
                
                // Remove corresponding substeps entry
                if (Array.isArray(this.currentSpec.substeps)) {
                    const substepsIndex = this.currentSpec.substeps.findIndex(s => s.step === stepName);
                    if (substepsIndex !== -1) {
                        this.currentSpec.substeps.splice(substepsIndex, 1);
                        logger.debug('Editor', `Deleted substeps entry for step: ${stepName}`);
                    }
                }
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        logger.debug('Editor', `FlowMap: Deleted ${stepNodesToDelete.length + substepNodesToDelete.length} node(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Multi-Flow Map nodes (causes and effects)
     */
    deleteMultiFlowMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.causes) || !Array.isArray(this.currentSpec.effects)) {
            logger.error('Editor', 'Invalid multi-flow map spec');
            return;
        }
        
        // Separate node IDs by type and collect indices
        const causeIndicesToDelete = [];
        const effectIndicesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                logger.warn('Editor', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'event') {
                // Don't allow deletion of central event
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotDeleteCentralEvent'), 'warning');
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
        
        logger.debug('Editor', 'Multi-flow map deletion:', { causeIndicesToDelete, effectIndicesToDelete });
        
        // Delete causes (sort by index descending to avoid index shifting)
        const sortedCauseIndices = causeIndicesToDelete.sort((a, b) => b - a);
        sortedCauseIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.causes.length) {
                const causeText = this.currentSpec.causes[index];
                this.currentSpec.causes.splice(index, 1);
                logger.debug('Editor', `Deleted cause ${index}: ${causeText}`);
            }
        });
        
        // Delete effects (sort by index descending to avoid index shifting)
        const sortedEffectIndices = effectIndicesToDelete.sort((a, b) => b - a);
        sortedEffectIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.effects.length) {
                const effectText = this.currentSpec.effects[index];
                this.currentSpec.effects.splice(index, 1);
                logger.debug('Editor', `Deleted effect ${index}: ${effectText}`);
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        logger.debug('Editor', `MultiFlowMap: Deleted ${causeIndicesToDelete.length + effectIndicesToDelete.length} node(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Tree Map nodes
     */
    deleteTreeMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.children)) {
            logger.error('Editor', 'Invalid tree map spec');
            return;
        }
        
        // Separate node IDs by type and collect indices
        const categoriesToDelete = [];
        const leavesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                logger.warn('Editor', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'topic') {
                // Don't allow deletion of root topic
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(this.getNotif('cannotDeleteRootTopic'), 'warning');
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
        
        logger.debug('Editor', 'Tree map deletion:', { categoriesToDelete, leavesToDelete });
        
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
                            logger.debug('Editor', `Deleted leaf ${leafIndex} from category ${categoryIndex}: ${leafText}`);
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
                logger.debug('Editor', `Deleted category ${index}: ${categoryText}`);
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        logger.debug('Editor', `TreeMap: Deleted ${categoriesToDelete.length + leavesToDelete.length} node(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Bridge Map analogy pairs
     */
    deleteBridgeMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.analogies)) {
            logger.error('Editor', 'Invalid bridge map spec');
            return;
        }
        
        // Collect unique pair indices to delete
        // Bridge map deletes complete pairs (both left and right together)
        const pairIndicesToDelete = new Set();
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                logger.warn('Editor', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            const pairIndex = parseInt(element.attr('data-pair-index'));
            
            if (!isNaN(pairIndex)) {
                // Add the pair index (whether it's left or right, we delete the whole pair)
                pairIndicesToDelete.add(pairIndex);
                logger.debug('Editor', `Marking pair ${pairIndex} for deletion (${nodeType} node)`);
            }
        });
        
        logger.debug('Editor', 'Bridge map deletion:', { pairIndicesToDelete: Array.from(pairIndicesToDelete) });
        
        // Prevent deletion of the first pair (like the topic in other maps)
        if (pairIndicesToDelete.has(0)) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('cannotDeleteFirstAnalogy'), 'warning');
            }
            pairIndicesToDelete.delete(0);
        }
        
        // Delete pairs (sort by index descending to avoid index shifting)
        const sortedPairIndices = Array.from(pairIndicesToDelete).sort((a, b) => b - a);
        sortedPairIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.analogies.length) {
                const pair = this.currentSpec.analogies[index];
                this.currentSpec.analogies.splice(index, 1);
                logger.debug('Editor', `Deleted pair ${index}: "${pair.left}" / "${pair.right}"`);
            }
        });
        
        // Note: Notification is shown by ToolbarManager.handleDeleteNode()
        // Don't show duplicate notification here
        logger.debug('Editor', `BridgeMap: Deleted ${sortedPairIndices.length} pair(s)`);
        
        // Re-render the diagram
        this.renderDiagram();
    }
    
    /**
     * Delete Concept Map nodes
     */
    deleteConceptMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.concepts)) {
            logger.error('Editor', 'Invalid concept map spec');
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
        
        logger.debug('Editor', `Deleted ${textsToDelete.size} concept node(s) from Concept Map`);
        
        // Re-render to update layout and connections
        this.renderDiagram();
    }
    
    /**
     * Delete Mind Map nodes
     */
    async deleteMindMapNodes(nodeIds) {
        if (!this.currentSpec || !Array.isArray(this.currentSpec.children)) {
            logger.error('Editor', 'Invalid mind map spec');
            return;
        }
        
        // Collect branches and sub-items to delete
        const branchesToDelete = new Set();
        const subItemsToDelete = new Map(); // Map of branchIndex -> Set of childIndices
        let attemptedTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                logger.warn('Editor', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            // Check if user is trying to delete the central topic
            if (nodeType === 'topic') {
                attemptedTopicDelete = true;
                return;
            }
            
            if (nodeType === 'branch') {
                const branchIndex = parseInt(element.attr('data-array-index') || element.attr('data-branch-index'));
                if (!isNaN(branchIndex) && branchIndex >= 0) {
                    branchesToDelete.add(branchIndex);
                    logger.debug('Editor', `Marking branch ${branchIndex} for deletion`);
                }
            } else if (nodeType === 'child' || nodeType === 'subitem') {
                const branchIndex = parseInt(element.attr('data-branch-index'));
                const childIndex = parseInt(element.attr('data-child-index') || element.attr('data-array-index'));
                
                if (!isNaN(branchIndex) && !isNaN(childIndex)) {
                    if (!subItemsToDelete.has(branchIndex)) {
                        subItemsToDelete.set(branchIndex, new Set());
                    }
                    subItemsToDelete.get(branchIndex).add(childIndex);
                    logger.debug('Editor', `Marking sub-item ${childIndex} of branch ${branchIndex} for deletion`);
                }
            }
        });
        
        // Show warning if user attempted to delete the central topic
        if (attemptedTopicDelete) {
            if (this.toolbarManager) {
                this.toolbarManager.showNotification(this.getNotif('cannotDeleteCentralTopic'), 'warning');
            }
        }
        
        // Delete sub-items first (within each branch, delete from highest index to lowest)
        subItemsToDelete.forEach((childIndices, branchIndex) => {
            if (branchIndex >= 0 && branchIndex < this.currentSpec.children.length) {
                const branch = this.currentSpec.children[branchIndex];
                if (Array.isArray(branch.children)) {
                    // Sort child indices descending to avoid index shifting
                    const sortedIndices = Array.from(childIndices).sort((a, b) => b - a);
                    sortedIndices.forEach(childIndex => {
                        if (childIndex >= 0 && childIndex < branch.children.length) {
                            const childText = branch.children[childIndex].text || branch.children[childIndex].label || 'unknown';
                            branch.children.splice(childIndex, 1);
                            logger.debug('Editor', `Deleted sub-item ${childIndex} from branch ${branchIndex}: ${childText}`);
                        }
                    });
                }
            }
        });
        
        // Delete branches (sort by index descending to avoid index shifting)
        const sortedBranchIndices = Array.from(branchesToDelete).sort((a, b) => b - a);
        sortedBranchIndices.forEach(index => {
            if (index >= 0 && index < this.currentSpec.children.length) {
                const branchText = this.currentSpec.children[index].text || this.currentSpec.children[index].label || 'unknown';
                this.currentSpec.children.splice(index, 1);
                logger.debug('Editor', `Deleted branch ${index}: ${branchText}`);
            }
        });
        
        const totalDeleted = sortedBranchIndices.length + Array.from(subItemsToDelete.values()).reduce((sum, set) => sum + set.size, 0);
        logger.debug('Editor', `MindMap: Deleted ${totalDeleted} node(s)`);
        
        // For mind maps, we need to recalculate layout from backend before rendering
        await this.recalculateMindMapLayout();
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
        
        logger.debug('Editor', `Deleted ${nodeIds.length} generic node(s) - DOM only (no spec update)`);
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
    saveToHistory(action, metadata) {
        // Remove any history after current index (branch cut)
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Save a deep clone of the ENTIRE currentSpec, not just metadata
        this.history.push({
            action,
            metadata: metadata ? JSON.parse(JSON.stringify(metadata)) : {},
            spec: JSON.parse(JSON.stringify(this.currentSpec)), // ← THE FIX!
            timestamp: Date.now()
        });
        
        this.historyIndex = this.history.length - 1;
        
        // Limit history size (50 states)
        if (this.history.length > 50) {
            this.history.shift();
            this.historyIndex--;
        }
        
        logger.debug('Editor', `History saved: ${action}, total states: ${this.history.length}, current index: ${this.historyIndex}`);
    }
    
    /**
     * Undo last action
     */
    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            const historyEntry = this.history[this.historyIndex];
            logger.debug('Editor', `Undo: ${historyEntry.action}`, historyEntry.metadata);
            
            // Restore the spec from history
            this.currentSpec = JSON.parse(JSON.stringify(historyEntry.spec));
            
            // Clear selection (nodes may no longer exist)
            this.selectionManager.clearSelection();
            
            // Re-render diagram with restored state
            this.renderDiagram();
            
            if (this.toolbarManager) {
                this.toolbarManager.showNotification('Undo: ' + historyEntry.action, 'info');
            }
        } else {
            logger.debug('Editor', 'Undo: No more history to undo');
            if (this.toolbarManager) {
                this.toolbarManager.showNotification('Nothing to undo', 'warning');
            }
        }
    }
    
    /**
     * Redo last undone action
     */
    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            const historyEntry = this.history[this.historyIndex];
            logger.debug('Editor', `Redo: ${historyEntry.action}`, historyEntry.metadata);
            
            // Restore the spec from history
            this.currentSpec = JSON.parse(JSON.stringify(historyEntry.spec));
            
            // Clear selection (nodes may no longer exist)
            this.selectionManager.clearSelection();
            
            // Re-render diagram with restored state
            this.renderDiagram();
            
            if (this.toolbarManager) {
                this.toolbarManager.showNotification('Redo: ' + historyEntry.action, 'info');
            }
        } else {
            logger.debug('Editor', 'Redo: No more history to redo');
            if (this.toolbarManager) {
                this.toolbarManager.showNotification('Nothing to redo', 'warning');
            }
        }
    }
    
    /**
     * Update toolbar state
     */
    updateToolbarState() {
        const hasSelection = this.selectedNodes.size > 0;
        const selectedNodesArray = Array.from(this.selectedNodes);
        
        // Update State Manager (source of truth for selection)
        if (window.stateManager && typeof window.stateManager.selectNodes === 'function') {
            window.stateManager.selectNodes(selectedNodesArray);
        }
        
        // Dispatch custom event for toolbar to listen
        window.dispatchEvent(new CustomEvent('editor-selection-change', {
            detail: {
                selectedNodes: selectedNodesArray,
                hasSelection: hasSelection
            }
        }));
    }
    
    /**
     * Destroy the editor and clean up all resources
     * Called by DiagramSelector when transitioning back to gallery
     */
    destroy() {
        logger.debug('Editor', 'Destroying InteractiveEditor instance', { diagramType: this.diagramType });
        
        // ========================================
        // 1. REMOVE ALL EVENT LISTENERS
        // ========================================
        
        // Remove D3 event handlers
        d3.select('#d3-container').on('click', null);
        d3.select('body').on('keydown', null);
        
        // Remove DOM event listeners
        const resetViewBtn = document.getElementById('reset-view-btn');
        if (resetViewBtn && this.eventHandlers.resetViewClick) {
            resetViewBtn.removeEventListener('click', this.eventHandlers.resetViewClick);
        }
        
        if (this.eventHandlers.orientationChange) {
            window.removeEventListener('orientationchange', this.eventHandlers.orientationChange);
        }
        
        if (this.eventHandlers.windowResize) {
            window.removeEventListener('resize', this.eventHandlers.windowResize);
        }
        
        // ========================================
        // 2. DESTROY ALL MANAGERS
        // ========================================
        
        // Destroy ToolbarManager
        if (this.toolbarManager) {
            this.toolbarManager.destroy();
            this.toolbarManager = null;
        }
        
        // Clear SelectionManager
        if (this.selectionManager) {
            this.selectionManager.clearSelection();
            this.selectionManager.setSelectionChangeCallback(null);
            this.selectionManager = null;
        }
        
        // Clear CanvasManager
        if (this.canvasManager) {
            this.canvasManager.clear();
            this.canvasManager = null;
        }
        
        // ========================================
        // 2.5 DESTROY ALL REFACTORED MODULES
        // ========================================
        // NOTE: All 18 managers (4 session + 14 modules) are now managed by SessionLifecycleManager
        // They're destroyed in DiagramSelector.backToGallery() via sessionLifecycle.cleanup()
        // We just need to nullify the references here
        if (this.modules) {
            logger.debug('Editor', 'Clearing module references (destroyed by SessionLifecycleManager)');
            this.modules = null;
        }
        
        // Nullify session manager references
        this.thinkGuide = null;
        this.mindMate = null;
        this.nodePalette = null;
        this.voiceAgent = null;
        
        // ========================================
        // 3. CLEAR ALL DATA STRUCTURES
        // ========================================
        
        this.selectedNodes.clear();
        this.history = [];
        this.historyIndex = -1;
        this.eventHandlers = {};
        
        // ========================================
        // 4. NULLIFY ALL REFERENCES
        // ========================================
        
        this.currentSpec = null;
        this.renderer = null;
        this.sessionId = null;
        this.sessionDiagramType = null;
        this.zoomBehavior = null;
        this.zoomTransform = null;
        
        logger.debug('Editor', 'InteractiveEditor destroyed successfully');
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

