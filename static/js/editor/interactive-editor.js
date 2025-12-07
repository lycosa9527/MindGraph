/**
 * InteractiveEditor - Main controller for the interactive diagram editor
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * PROPRIETARY LICENSE - ALL RIGHTS RESERVED
 * 
 * This software and associated documentation files (the "Software") are the proprietary
 * and confidential information of 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.).
 * 
 * WITHOUT EXPLICIT WRITTEN PERMISSION FROM THE COPYRIGHT HOLDER, ALL USE IS PROHIBITED,
 * including but not limited to:
 * - Use, execution, or deployment
 * - Copying, downloading, or access
 * - Modification or creation of derivative works
 * - Distribution, redistribution, or sharing
 * - Commercial use or any production deployment
 * 
 * Unauthorized use may result in severe civil and criminal penalties.
 * 
 * For licensing inquiries, please contact the copyright holder.
 * 
 * @author WANG CUNCHI
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
        
        // Initialize Event Bus and State Manager references (early, before selection callback)
        this.eventBus = window.eventBus;
        this.stateManager = window.stateManager;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'InteractiveEditor';
        
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
        
        // Store Event Bus listener callbacks (still needed for callback references)
        this.eventBusListeners = {};
        
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
            
            // Emit selection changed event (InteractionHandler will also emit, but this ensures it's always emitted)
            if (this.eventBus) {
                this.eventBus.emit('interaction:selection_changed', {
                    selectedNodes: Array.from(selectedNodes)
                });
            }
            
            // Update state manager (use updateDiagram method)
            if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                this.stateManager.updateDiagram({
                    selectedNodes: Array.from(selectedNodes)
                });
            }
            
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
        
        // CRITICAL: Update State Manager with diagram type (single source of truth)
        if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
            this.stateManager.updateDiagram({
                type: this.diagramType,
                data: this.currentSpec
            });
            logger.debug('InteractiveEditor', 'Updated State Manager with diagram type', {
                diagramType: this.diagramType
            });
        }
        
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
        
        // Event Bus and State Manager already initialized in constructor
        
        // Subscribe to events
        if (this.eventBus) {
            // Listen for render requests from ViewManager (e.g., after orientation flip)
            this.eventBusListeners.renderRequested = (data) => {
                if (data.spec) {
                    this.currentSpec = data.spec;
                    this.renderDiagram();
                }
            };
            this.eventBus.onWithOwner('diagram:render_requested', this.eventBusListeners.renderRequested, this.ownerId);
            
            // Listen for operations loaded to ensure operations are available
            this.eventBusListeners.operationsLoaded = (data) => {
                logger.debug('InteractiveEditor', `Operations loaded for ${data.diagramType}`);
            };
            this.eventBus.onWithOwner('diagram:operations_loaded', this.eventBusListeners.operationsLoaded, this.ownerId);
            
            // Listen for operations unavailable (fallback to old methods)
            this.eventBusListeners.operationsUnavailable = (data) => {
                logger.warn('InteractiveEditor', `Operations not available for ${data.diagramType} - using fallback methods`);
            };
            this.eventBus.onWithOwner('diagram:operations_unavailable', this.eventBusListeners.operationsUnavailable, this.ownerId);
            
            // Listen for diagram operations (from operations modules)
            this.eventBusListeners.nodeAdded = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring diagram:node_added - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // CRITICAL: Use State Manager as source of truth - update it if event has different type
                if (data.diagramType && data.diagramType !== this.diagramType) {
                    logger.warn('InteractiveEditor', `Diagram type mismatch: event has ${data.diagramType}, editor has ${this.diagramType}. Updating State Manager.`);
                    // Update State Manager (single source of truth)
                    if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                        this.stateManager.updateDiagram({ type: data.diagramType });
                    }
                    this.diagramType = data.diagramType;
                }
                this.renderDiagram();
            };
            this.eventBus.onWithOwner('diagram:node_added', this.eventBusListeners.nodeAdded, this.ownerId);
            
            this.eventBusListeners.nodesDeleted = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring diagram:nodes_deleted - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // CRITICAL: Use State Manager as source of truth - update it if event has different type
                if (data.diagramType && data.diagramType !== this.diagramType) {
                    logger.warn('InteractiveEditor', `Diagram type mismatch: event has ${data.diagramType}, editor has ${this.diagramType}. Updating State Manager.`);
                    // Update State Manager (single source of truth)
                    if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                        this.stateManager.updateDiagram({ type: data.diagramType });
                    }
                    this.diagramType = data.diagramType;
                }
                // ARCHITECTURE: Clear selection via State Manager (single source of truth)
                if (this.stateManager && typeof this.stateManager.selectNodes === 'function') {
                    this.stateManager.selectNodes([]);
                }
                // Clear local selection manager
                this.selectionManager.clearSelection();
                this.renderDiagram();
            };
            this.eventBus.onWithOwner('diagram:nodes_deleted', this.eventBusListeners.nodesDeleted, this.ownerId);
            
            this.eventBusListeners.nodeUpdated = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring diagram:node_updated - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // CRITICAL: Use State Manager as source of truth - update it if event has different type
                if (data.diagramType && data.diagramType !== this.diagramType) {
                    logger.warn('InteractiveEditor', `Diagram type mismatch: event has ${data.diagramType}, editor has ${this.diagramType}. Updating State Manager.`);
                    // Update State Manager (single source of truth)
                    if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                        this.stateManager.updateDiagram({ type: data.diagramType });
                    }
                    this.diagramType = data.diagramType;
                }
                this.renderDiagram();
            };
            this.eventBus.onWithOwner('diagram:node_updated', this.eventBusListeners.nodeUpdated, this.ownerId);
            
            // Listen for Mind Map layout recalculation requests
            this.eventBusListeners.layoutRecalculationRequested = async (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring mindmap:layout_recalculation_requested - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // Recalculate layout before rendering
                await this.recalculateMindMapLayout();
            };
            this.eventBus.onWithOwner('mindmap:layout_recalculation_requested', this.eventBusListeners.layoutRecalculationRequested, this.ownerId);
            
            // Listen for Mind Map selection restore requests (after text update)
            this.eventBusListeners.selectionRestoreRequested = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring mindmap:selection_restore_requested - editor destroyed');
                    return;
                }
                // The selection manager will handle this during render
                // This is just a notification that re-render may be needed
            };
            this.eventBus.onWithOwner('mindmap:selection_restore_requested', this.eventBusListeners.selectionRestoreRequested, this.ownerId);
        }
        
        // Update flow map orientation button visibility (via ViewManager)
        if (this.eventBus) {
            // ViewManager will handle this via event subscription
            this.eventBus.emit('diagram:type_changed', { diagramType: this.diagramType });
        }
        
        // Render initial diagram
        this.renderDiagram();
        
        // Setup global event handlers
        this.setupGlobalEventHandlers();
        
        // Initialize toolbar manager
        if (typeof ToolbarManager !== 'undefined') {
            this.toolbarManager = new ToolbarManager(this);
            logger.debug('Editor', 'Toolbar manager initialized');
        }
        
            // Auto-fit for mobile devices on initial load (via ViewManager)
        if (this.isMobileDevice()) {
            logger.debug('Editor', 'Mobile device detected - auto-fitting to screen');
            if (this.eventBus) {
            setTimeout(() => {
                    this.eventBus.emit('view:fit_diagram_requested');
            }, 500); // Slight delay to ensure rendering is complete
            }
        }
    }
    
    /**
     * Render the diagram
     */
    async renderDiagram() {
        this.log('InteractiveEditor: Starting diagram render', {
            specKeys: Object.keys(this.currentSpec || {})
        });
        
        // Update flow map orientation button visibility (via ViewManager)
        if (this.eventBus) {
            this.eventBus.emit('diagram:type_changed', { diagramType: this.diagramType });
        }
        
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
                // CRITICAL: Use State Manager as source of truth for diagram type
                let diagramTypeToRender = this.diagramType;
                if (this.stateManager && typeof this.stateManager.getDiagramState === 'function') {
                    const diagramState = this.stateManager.getDiagramState();
                    if (diagramState && diagramState.type) {
                        diagramTypeToRender = diagramState.type;
                        // Sync local copy if different (for backward compatibility)
                        if (diagramTypeToRender !== this.diagramType) {
                            logger.debug('InteractiveEditor', `Using diagram type from State Manager: ${diagramTypeToRender} (was ${this.diagramType})`);
                            this.diagramType = diagramTypeToRender;
                        }
                    }
                }
                
                // CRITICAL: Validate diagramType before rendering
                if (!diagramTypeToRender) {
                    logger.error('Editor', 'diagramType is undefined/null, cannot render');
                    throw new Error('diagramType is required for rendering');
                }
                
                // Defensive logging: Check if spec structure matches diagram type
                const hasContext = Array.isArray(this.currentSpec?.context);
                const hasAttributes = Array.isArray(this.currentSpec?.attributes);
                const hasTopic = !!this.currentSpec?.topic;
                
                if (diagramTypeToRender === 'circle_map' && !hasContext) {
                    logger.warn('Editor', `Circle map spec missing context array. Has: topic=${hasTopic}, attributes=${hasAttributes}, context=${hasContext}`);
                } else if (diagramTypeToRender === 'bubble_map' && !hasAttributes) {
                    logger.warn('Editor', `Bubble map spec missing attributes array. Has: topic=${hasTopic}, attributes=${hasAttributes}, context=${hasContext}`);
                }
                
                logger.debug('Editor', `Rendering ${diagramTypeToRender}`, {
                    diagramType: diagramTypeToRender,
                    fromStateManager: diagramTypeToRender !== this.diagramType,
                    nodes: this.currentSpec?.nodes?.length || 0,
                    hasTitle: !!this.currentSpec?.title,
                    hasTopic,
                    hasContext,
                    hasAttributes
                });
                await renderGraph(diagramTypeToRender, this.currentSpec, theme, dimensions);
            } else {
                logger.error('Editor', 'renderGraph dispatcher not found');
                throw new Error('Renderer not available');
            }
            
            // Add interaction handlers after rendering (via InteractionHandler)
            // InteractionHandler will handle this via diagram:rendered event subscription
            
            // Enable zoom and pan for all devices (via ViewManager)
            // ViewManager will handle this via event subscription on diagram:rendered
            
            // Update school name display in status bar (async, no await needed)
            this.updateSchoolNameDisplay().catch(err => {
                logger.debug('Editor', 'School name update failed', err);
            });
            
            // NOTE: Auto-fit is handled by ViewManager via diagram:rendered event
            // This prevents duplicate triggers and ensures clean initial load
            
            // Update flow map orientation button visibility (via ViewManager)
            if (this.eventBus) {
                this.eventBus.emit('diagram:type_changed', { diagramType: this.diagramType });
            }
            
            // Emit diagram rendered event (for ViewManager and other modules)
            if (this.eventBus) {
                this.eventBus.emit('diagram:rendered', {
                    diagramType: this.diagramType,
                    spec: this.currentSpec
                });
            }
            
        } catch (error) {
            logger.error('Editor', 'Diagram rendering failed', error);
            throw error;
        }
    }
    
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
    
    /**
     * Setup global event handlers
     */
    setupGlobalEventHandlers() {
        // Click on canvas to deselect all (delegate to InteractionHandler via Event Bus)
        d3.select('#d3-container').on('click', () => {
            if (this.eventBus) {
                this.eventBus.emit('interaction:clear_selection_requested');
            } else {
                // Fallback if Event Bus not available
            this.selectionManager.clearSelection();
            }
        });
        
        // Keyboard shortcuts
        d3.select('body').on('keydown', (event) => {
            this.handleKeyboardShortcut(event);
        });
        
        // Reset view button (delegate to ViewManager via Event Bus)
        const resetViewBtn = document.getElementById('reset-view-btn');
        if (resetViewBtn) {
            this.eventHandlers.resetViewClick = () => {
                if (this.eventBus) {
                    this.eventBus.emit('view:fit_diagram_requested');
                }
            };
            resetViewBtn.addEventListener('click', this.eventHandlers.resetViewClick);
        }
        
        // Mobile: Auto-fit on orientation change
        if (this.isMobileDevice()) {
            this.eventHandlers.orientationChange = () => {
                logger.debug('Editor', 'Orientation changed - re-fitting diagram to screen');
                if (this.eventBus) {
                setTimeout(() => {
                        this.eventBus.emit('view:fit_diagram_requested');
                }, 300); // Wait for orientation animation to complete
                }
            };
            window.addEventListener('orientationchange', this.eventHandlers.orientationChange);
            
            // Also handle window resize for responsive mobile browsers
            let resizeTimeout;
            this.eventHandlers.windowResize = () => {
                if (this.isMobileDevice()) {
                    clearTimeout(resizeTimeout);
                    resizeTimeout = setTimeout(() => {
                        logger.debug('Editor', 'Mobile screen resized - re-fitting diagram');
                        if (this.eventBus) {
                            this.eventBus.emit('view:fit_diagram_requested');
                        }
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
        
        // Use DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            logger.warn('InteractiveEditor', 'DiagramOperationsLoader not available');
            // Fallback to generic update
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
        this.saveToHistory('update_text', { nodeId, newText });
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations || typeof operations.updateNode !== 'function') {
            logger.warn('InteractiveEditor', `No operations available for diagram type: ${this.diagramType}`);
            // Fallback to generic update
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
            this.saveToHistory('update_text', { nodeId, newText });
            return;
        }
        
        try {
            const updatedSpec = operations.updateNode(this.currentSpec, nodeId, { text: newText });
            if (updatedSpec) {
                this.currentSpec = updatedSpec;
                // Operations module will emit diagram:node_updated event
                // which is already handled by the persistent listener above
                // Save to history will be handled by operations module via diagram:operation_completed
                    } else {
                // Fallback to generic update if operations module returns null
                this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
                this.saveToHistory('update_text', { nodeId, newText });
            }
        } catch (error) {
            logger.error('InteractiveEditor', 'Error updating node via operations module', error);
            // Fallback to generic update on error
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
            this.saveToHistory('update_text', { nodeId, newText });
        }
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
        
        // Use DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            logger.warn('InteractiveEditor', 'DiagramOperationsLoader not available');
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations || typeof operations.addNode !== 'function') {
            logger.warn('InteractiveEditor', `No operations available for diagram type: ${this.diagramType}`);
            this.eventBus?.emit('diagram:operation_warning', {
                message: `Add node operation not supported for ${this.diagramType}`,
                type: 'warning'
            });
            return;
        }
        
        try {
            const result = operations.addNode(this.currentSpec, this);
            // Handle both sync and async operations
            if (result instanceof Promise) {
                result.then((updatedSpec) => {
                    if (updatedSpec) {
                        this.currentSpec = updatedSpec;
                        // Operations module will emit diagram:node_added event
                        // which is already handled by the persistent listener above
                    }
                }).catch((error) => {
                    logger.error('InteractiveEditor', 'Error adding node via operations module', error);
                    this.eventBus?.emit('diagram:operation_warning', {
                        message: 'Failed to add node',
                        type: 'error'
                    });
                });
            } else if (result) {
                this.currentSpec = result;
                // Operations module will emit diagram:node_added event
                // which is already handled by the persistent listener above
            }
        } catch (error) {
            logger.error('InteractiveEditor', 'Error adding node via operations module', error);
            this.eventBus?.emit('diagram:operation_warning', {
                message: 'Failed to add node',
                type: 'error'
            });
        }
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
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: this.getNotif('updatingLayout'), 
                type: 'info' 
            });
            
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
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: this.getNotif('layoutUpdateFailed'), 
                type: 'warning' 
            });
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
        
        // Add drag behavior and click handlers (via InteractionHandler)
        // Re-attach handlers to include the new node
        if (this.eventBus) {
            this.eventBus.emit('interaction:attach_handlers_requested');
        }
        
        // Legacy handlers for new nodes (will be replaced by InteractionHandler)
        const self = this;
        const newNodeText = window.languageManager?.translate('newNode') || 'New Node';
        
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
        
        // Use DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            logger.warn('InteractiveEditor', 'DiagramOperationsLoader not available');
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations || typeof operations.deleteNodes !== 'function') {
            logger.warn('InteractiveEditor', `No operations available for diagram type: ${this.diagramType}`);
            this.eventBus?.emit('diagram:operation_warning', {
                message: `Delete operation not supported for ${this.diagramType}`,
                    type: 'warning'
            });
            return;
        }
        
        try {
            const result = operations.deleteNodes(this.currentSpec, nodesToDelete);
            // Handle both sync and async operations
            if (result instanceof Promise) {
                result.then((updatedSpec) => {
                    if (updatedSpec) {
                        this.currentSpec = updatedSpec;
                        // Operations module will emit diagram:nodes_deleted event
                        // which is already handled by the persistent listener above
                    }
                }).catch((error) => {
                    logger.error('InteractiveEditor', 'Error deleting nodes via operations module', error);
                    this.eventBus?.emit('diagram:operation_warning', {
                        message: 'Failed to delete nodes',
                        type: 'error'
                    });
                });
            } else if (result) {
                this.currentSpec = result;
                // Operations module will emit diagram:nodes_deleted event
                // which is already handled by the persistent listener above
            }
        } catch (error) {
            logger.error('InteractiveEditor', 'Error deleting nodes via operations module', error);
            this.eventBus?.emit('diagram:operation_warning', {
                message: 'Failed to delete nodes',
                type: 'error'
            });
        }
    }
    
    /**
     * Delete generic nodes (fallback for other diagram types)
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
            
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Undo: ' + historyEntry.action, 
                type: 'info' 
            });
        } else {
            logger.debug('Editor', 'Undo: No more history to undo');
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Nothing to undo', 
                type: 'warning' 
            });
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
            
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Redo: ' + historyEntry.action, 
                type: 'info' 
            });
        } else {
            logger.debug('Editor', 'Redo: No more history to redo');
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Nothing to redo', 
                type: 'warning' 
            });
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
        
        // NOTE: Selection changes are handled by InteractionHandler via Event Bus
        // which emits 'interaction:selection_changed' event
        // This method is kept for backward compatibility but no longer needs to dispatch events
        // The Event Bus pattern ensures all modules are notified automatically
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
        
        // Remove Event Bus listeners (CRITICAL: prevents handlers from executing on destroyed instance)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                logger.debug('Editor', `Removed ${removedCount} Event Bus listeners`);
            }
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
        // Note: eventBusListeners cleanup handled by removeAllListenersForOwner()
        
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
     * Fit diagram for export - calculates optimal viewBox to capture entire diagram
     * This ensures the exported PNG contains the complete diagram properly centered
     */
    fitDiagramForExport() {
        try {
            const svg = d3.select('#d3-container svg');
            if (svg.empty()) {
                logger.warn('Editor', 'No SVG found for export fitting');
                return;
            }
            
            // Get all visual elements (excluding defs)
            const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            
            if (allElements.empty()) {
                logger.warn('Editor', 'No content found for export fitting');
                return;
            }
            
            // Calculate the bounding box of all SVG content
            // Note: getBBox() returns geometric bounds, not including stroke width
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            let hasContent = false;
            let maxStrokeWidth = 0;
            
            allElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox.width > 0 && bbox.height > 0) {
                        // Account for stroke width extending beyond geometric bounds
                        const strokeWidth = parseFloat(d3.select(this).attr('stroke-width')) || 0;
                        const strokeOffset = strokeWidth / 2;
                        
                        minX = Math.min(minX, bbox.x - strokeOffset);
                        minY = Math.min(minY, bbox.y - strokeOffset);
                        maxX = Math.max(maxX, bbox.x + bbox.width + strokeOffset);
                        maxY = Math.max(maxY, bbox.y + bbox.height + strokeOffset);
                        hasContent = true;
                        
                        if (strokeWidth > maxStrokeWidth) {
                            maxStrokeWidth = strokeWidth;
                        }
                    }
                } catch (e) {
                    // Some elements might not have getBBox, skip them
                }
            });
            
            if (!hasContent || minX === Infinity) {
                logger.warn('Editor', 'No valid content bounds found for export');
                return;
            }
            
            const contentWidth = maxX - minX;
            const contentHeight = maxY - minY;
            
            // Add padding around the content
            // Use larger of 5% ratio or minimum 40px for better export margins
            const paddingRatio = 0.05;
            const minPadding = 40 + Math.ceil(maxStrokeWidth);
            const paddingX = Math.max(contentWidth * paddingRatio, minPadding);
            const paddingY = Math.max(contentHeight * paddingRatio, minPadding);
            
            // Calculate optimal viewBox for export
            const viewBoxX = minX - paddingX;
            const viewBoxY = minY - paddingY;
            const viewBoxWidth = contentWidth + (paddingX * 2);
            const viewBoxHeight = contentHeight + (paddingY * 2);
            
            // Apply the optimized viewBox (no animation for export)
            svg.attr('viewBox', `${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`)
               .attr('preserveAspectRatio', 'xMidYMid meet');
            
            logger.debug('Editor', 'Fitted diagram for export:', {
                contentBounds: { minX, minY, maxX, maxY },
                viewBox: `${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`
            });
            
        } catch (error) {
            logger.error('Editor', 'Error fitting diagram for export:', error);
        }
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

