/**
 * Node Counter & Feature Mode Manager
 * ===================================
 * 
 * Handles node counting (MutationObserver), session validation, and feature modes.
 * Manages Learning Mode and Node Palette activation.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class NodeCounterFeatureModeManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager; // Need access to UI elements and validator
        
        // Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'NodeCounterFeatureModeManager';
        
        // Store callback references for proper cleanup
        this.callbacks = {
            setupObserver: () => this.setupNodeCounterObserver(),
            updateCounter: () => this.updateNodeCount(),
            validateSession: (data) => {
                const isValid = this.validateToolbarSession(data.operation);
                this.eventBus.emit('session:validated', { isValid, operation: data.operation });
            },
            validateLearningMode: () => {
                const result = this.validateLearningMode();
                this.eventBus.emit('learning_mode:validated', { result });
            },
            startLearningMode: () => this.handleLearningMode(),
            toggleNodePaletteMode: () => this.handleNodePaletteMode()
        };
        
        this.setupEventListeners();
        this.logger.info('NodeCounterFeatureModeManager', 'Node Counter & Feature Mode Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        // Register with stored callback references with owner tracking
        this.eventBus.onWithOwner('node_counter:setup_observer', this.callbacks.setupObserver, this.ownerId);
        this.eventBus.onWithOwner('node_counter:update_requested', this.callbacks.updateCounter, this.ownerId);
        this.eventBus.onWithOwner('session:validate_requested', this.callbacks.validateSession, this.ownerId);
        this.eventBus.onWithOwner('learning_mode:validate', this.callbacks.validateLearningMode, this.ownerId);
        this.eventBus.onWithOwner('learning_mode:start_requested', this.callbacks.startLearningMode, this.ownerId);
        this.eventBus.onWithOwner('node_palette:toggle_requested', this.callbacks.toggleNodePaletteMode, this.ownerId);
        
        this.logger.debug('NodeCounterFeatureModeManager', 'Event Bus listeners registered with owner tracking');
    }
    
    /**
     * Setup node counter MutationObserver
     * EXTRACTED FROM: toolbar-manager.js lines 2793-2828
     */
    setupNodeCounterObserver() {
        const container = document.getElementById('d3-container');
        if (!container) {
            this.logger.warn('NodeCounterFeatureModeManager', 'd3-container not found for node counter observer');
            return;
        }
        
        // Create a MutationObserver to watch for DOM changes in the SVG
        this.nodeCountObserver = new MutationObserver((mutations) => {
            // Debounce updates to avoid excessive calls
            if (this.nodeCountUpdateTimeout) {
                clearTimeout(this.nodeCountUpdateTimeout);
            }
            this.nodeCountUpdateTimeout = setTimeout(() => {
                this.updateNodeCount();
                this.validateLearningMode(); // Also validate diagram for Learning Mode
            }, 100); // Update after 100ms of no changes
        });
        
        // Start observing - only watch for added/removed children
        this.nodeCountObserver.observe(container, {
            childList: true,      // Watch for added/removed children
            subtree: true         // Watch all descendants
        });
        
        this.logger.debug('NodeCounterFeatureModeManager', 'Node counter observer set up');
        
        // Initial count and validation with longer delay to ensure SVG is fully rendered
        setTimeout(() => {
            this.updateNodeCount();
            this.validateLearningMode();
        }, 500);
    }
    
    /**
     * Update node count in status bar
     * EXTRACTED FROM: toolbar-manager.js lines 2833-2865
     */
    updateNodeCount() {
        const nodeCountElement = this.toolbarManager.nodeCountElement;
        if (!nodeCountElement) {
            this.logger.warn('NodeCounterFeatureModeManager', 'Node count element not found');
            return;
        }
        
        // Count all text elements in the SVG
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            const label = window.languageManager?.translate('nodeCount') || 'Nodes';
            nodeCountElement.textContent = `${label}: 0`;
            return;
        }
        
        // Count unique nodes (multi-line text creates multiple text elements with same data-node-id)
        // Use Set to deduplicate - each unique data-node-id = 1 node
        const uniqueNodeIds = new Set();
        
        svg.selectAll('text').each(function() {
            const element = d3.select(this);
            const nodeId = element.attr('data-node-id');
            
            // Only count text elements with a node-id
            if (nodeId) {
                uniqueNodeIds.add(nodeId);
            }
        });
        
        const count = uniqueNodeIds.size;
        
        // Update the display
        const label = window.languageManager?.translate('nodeCount') || 'Nodes';
        nodeCountElement.textContent = `${label}: ${count}`;
    }
    
    /**
     * Validate that this toolbar manager is still valid for the current session
     * EXTRACTED FROM: toolbar-manager.js lines 2870-2889
     */
    validateToolbarSession(operation = 'Operation') {
        // Check if we have a session ID
        if (!this.toolbarManager.sessionId) {
            this.logger.error('NodeCounterFeatureModeManager', `${operation} blocked - No session ID`);
            return false;
        }
        
        // Check if session matches editor
        if (this.editor.sessionId !== this.toolbarManager.sessionId) {
            this.logger.warn('NodeCounterFeatureModeManager', `${operation} blocked - Session mismatch`, {
                toolbarSession: this.toolbarManager.sessionId?.substr(-8),
                editorSession: this.editor.sessionId?.substr(-8)
            });
            return false;
        }
        
        // Check with DiagramSelector's session
        if (window.diagramSelector?.currentSession) {
            if (window.diagramSelector.currentSession.id !== this.toolbarManager.sessionId) {
                this.logger.warn('NodeCounterFeatureModeManager', `${operation} blocked - DiagramSelector session mismatch`, {
                    toolbarSession: this.toolbarManager.sessionId?.substr(-8),
                    activeSession: window.diagramSelector.currentSession.id?.substr(-8)
                });
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Validate diagram for Learning Mode and enable/disable button
     * EXTRACTED FROM: toolbar-manager.js lines 2894-2905
     */
    validateLearningMode() {
        const validator = this.toolbarManager.validator;
        const learningBtn = this.toolbarManager.learningBtn;
        
        if (!validator || !learningBtn) {
            return;
        }
        
        const result = validator.validateAndUpdateButton(learningBtn, this.toolbarManager.diagramType);
        
        // Store validation result for later use
        this.toolbarManager.lastValidationResult = result;
        
        return result;
    }
    
    /**
     * Handle Learning Mode button click
     * EXTRACTED FROM: toolbar-manager.js lines 2910-2950
     */
    async handleLearningMode() {
        this.logger.info('NodeCounterFeatureModeManager', 'Learning Mode initiated');
        
        // Validate diagram first
        const validationResult = this.validateLearningMode();
        
        if (!validationResult || !validationResult.isValid) {
            // Show validation error message
            const lang = window.languageManager;
            const currentLang = lang?.currentLanguage || 'en';
            const message = this.toolbarManager.validator.getValidationMessage(validationResult, currentLang);
            
            this.toolbarManager.showNotification(message, 'error');
            this.logger.warn('NodeCounterFeatureModeManager', 'Learning Mode validation failed', {
                reason: validationResult.reason
            });
            return;
        }
        
        // Validation passed - Enter Learning Mode!
        this.logger.info('NodeCounterFeatureModeManager', 'Diagram validation passed');
        
        try {
            // Initialize LearningModeManager if not already done
            if (!this.toolbarManager.learningModeManager) {
                this.toolbarManager.learningModeManager = new LearningModeManager(this.toolbarManager, this.editor);
            }
            
            // Start Learning Mode
            await this.toolbarManager.learningModeManager.startLearningMode(validationResult);
            
            this.logger.info('NodeCounterFeatureModeManager', 'Learning Mode started successfully');
            
        } catch (error) {
            this.logger.error('NodeCounterFeatureModeManager', 'Failed to start Learning Mode', error);
            this.toolbarManager.showNotification(
                'Failed to start Learning Mode. Please try again.',
                'error'
            );
        }
    }
    
    /**
     * Extract center topic from diagram spec based on diagram type
     * @param {string} diagramType - The diagram type
     * @param {Object} diagramSpec - The diagram spec object
     * @returns {string} The center topic
     */
    extractCenterTopic(diagramType, diagramSpec) {
        if (['tree_map', 'mindmap'].includes(diagramType)) {
            return diagramSpec.topic || '';
        } else if (diagramType === 'flow_map') {
            return diagramSpec.title || '';
        } else if (diagramType === 'brace_map') {
            return diagramSpec.whole || '';
        } else if (diagramType === 'double_bubble_map') {
            return `${diagramSpec.left || ''} vs ${diagramSpec.right || ''}`;
        } else if (diagramType === 'multi_flow_map') {
            return diagramSpec.event || '';
        } else if (diagramType === 'bridge_map') {
            return diagramSpec.dimension || '';
        } else if (diagramType === 'circle_map') {
            return diagramSpec.topic || '';
        } else if (diagramType === 'bubble_map') {
            return diagramSpec.topic || '';
        } else {
            // Generic fallback
            return diagramSpec.center?.text || diagramSpec.topic || '';
        }
    }
    
    /**
     * Extract educational context from current diagram
     * @returns {Object} Educational context object
     */
    extractEducationalContext() {
        // Try to get from Node Palette if available, otherwise return empty context
        const nodePalette = window.currentEditor?.nodePalette;
        if (nodePalette && nodePalette.educationalContext) {
            return nodePalette.educationalContext;
        }
        return {};
    }
    
    /**
     * Handle Node Palette button click
     * Opens Node Palette directly for brainstorming nodes with AI
     */
    async handleNodePaletteMode() {
        this.logger.info('NodeCounterFeatureModeManager', 'Node Palette button clicked');
        
        // Check if node palette panel is already open - toggle behavior
        // Use PanelManager instead of direct DOM check
        const isPaletteOpen = window.panelManager?.isPanelOpen('nodePalette') || false;
        
        this.logger.info('NodeCounterFeatureModeManager', 'Initial palette state:', {
            isPaletteOpen: isPaletteOpen,
            currentPanel: window.panelManager?.getCurrentPanel()
        });
        
        // If palette is already open, close it (toggle behavior)
        if (isPaletteOpen) {
            this.logger.info('NodeCounterFeatureModeManager', 'Node Palette already open - closing it');
            if (window.panelManager) {
                window.panelManager.closePanel('nodePalette');
                this.logger.info('NodeCounterFeatureModeManager', 'Node Palette closed');
            }
            return;
        }
        
        // Get current diagram data
        const diagramData = this.editor?.getCurrentDiagramData();
        if (!diagramData) {
            this.logger.error('NodeCounterFeatureModeManager', 'No diagram data available');
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const message = lang === 'zh' 
                ? '无法获取图表数据，请重试' 
                : 'Unable to get diagram data. Please try again.';
            this.toolbarManager.showNotification(message, 'error');
            return;
        }
        
        // Extract spec from diagram data structure
        const diagramSpec = diagramData.spec || diagramData;
        const diagramType = this.editor.diagramType;
        
        // Extract center topic based on diagram type
        const centerTopic = this.extractCenterTopic(diagramType, diagramSpec);
        
        if (!centerTopic) {
            this.logger.warn('NodeCounterFeatureModeManager', 'No center topic found');
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const message = lang === 'zh' 
                ? '无法获取中心主题，请确保图表已正确创建' 
                : 'Unable to get center topic. Please ensure the diagram is properly created.';
            this.toolbarManager.showNotification(message, 'warning');
            return;
        }
        
        // Reuse existing session ID if available (preserves state when re-entering)
        // Only generate new session if nodePalette doesn't have one yet
        const nodePalette = window.currentEditor?.nodePalette;
        let sessionId;
        
        if (nodePalette?.sessionId && nodePalette.nodes?.length > 0) {
            // Reuse existing session - user is returning to palette with existing nodes
            sessionId = nodePalette.sessionId;
            this.logger.info('NodeCounterFeatureModeManager', 'Reusing existing Node Palette session', {
                diagramType,
                centerTopic,
                sessionId,
                existingNodes: nodePalette.nodes.length,
                selectedNodes: nodePalette.selectedNodes?.size || 0
            });
        } else {
            // Generate new session ID
            sessionId = `node-palette-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            this.logger.info('NodeCounterFeatureModeManager', 'Opening new Node Palette session', {
                diagramType,
                centerTopic,
                sessionId
            });
        }
        
        // Open panel first
        if (window.panelManager) {
            window.panelManager.openPanel('nodePalette');
        } else {
            this.eventBus.emit('panel:open_requested', { panel: 'nodePalette' });
        }
        
        // Start Node Palette Manager (nodePalette already retrieved above for session check)
        if (nodePalette) {
            try {
                // Extract educational context
                const educationalContext = this.extractEducationalContext();
                
                // Start node palette
                await nodePalette.start(
                    centerTopic,
                    diagramSpec,
                    sessionId,
                    educationalContext,
                    diagramType
                );
                
                this.logger.info('NodeCounterFeatureModeManager', 'Node Palette opened successfully', {
                    diagramType,
                    centerTopic
                });
                
            } catch (error) {
                this.logger.error('NodeCounterFeatureModeManager', 'Failed to open Node Palette', error);
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' 
                    ? '无法打开节点选择板，请重试' 
                    : 'Failed to open Node Palette. Please try again.';
                this.toolbarManager.showNotification(message, 'error');
            }
        } else {
            this.logger.error('NodeCounterFeatureModeManager', 'NodePaletteManager not available at window.currentEditor.nodePalette');
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const message = lang === 'zh' 
                ? '节点选择板功能不可用' 
                : 'Node Palette feature is not available.';
            this.toolbarManager.showNotification(message, 'error');
        }
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('NodeCounterFeatureModeManager', 'Destroying');
        
        // Remove all Event Bus listeners using Listener Registry
        if (this.eventBus && this.ownerId) {
            this.eventBus.removeAllListenersForOwner(this.ownerId);
            this.logger.debug('NodeCounterFeatureModeManager', 'Event listeners successfully removed');
        }
        
        // Nullify references
        this.callbacks = null;
        this.eventBus = null;
        this.stateManager = null;
        this.editor = null;
        this.toolbarManager = null;
        this.logger = null;
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.NodeCounterFeatureModeManager = NodeCounterFeatureModeManager;
}


