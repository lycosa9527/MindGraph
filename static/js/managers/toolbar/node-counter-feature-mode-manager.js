/**
 * Node Counter & Feature Mode Manager
 * ===================================
 * 
 * Handles node counting (MutationObserver), session validation, and feature modes.
 * Manages Learning Mode and Thinking Mode (ThinkGuide) activation.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 * @size ~360 lines
 */

class NodeCounterFeatureModeManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager; // Need access to UI elements and validator
        
        this.setupEventListeners();
        this.logger.info('NodeCounterFeatureModeManager', 'Node Counter & Feature Mode Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        this.eventBus.on('node_counter:setup_observer', () => {
            this.setupNodeCounterObserver();
        });
        
        this.eventBus.on('node_counter:update_requested', () => {
            this.updateNodeCount();
        });
        
        this.eventBus.on('session:validate_requested', (data) => {
            const isValid = this.validateToolbarSession(data.operation);
            this.eventBus.emit('session:validated', { isValid, operation: data.operation });
        });
        
        this.eventBus.on('learning_mode:validate', () => {
            const result = this.validateLearningMode();
            this.eventBus.emit('learning_mode:validated', { result });
        });
        
        this.eventBus.on('learning_mode:start_requested', () => {
            this.handleLearningMode();
        });
        
        this.eventBus.on('thinking_mode:toggle_requested', () => {
            this.handleThinkingMode();
        });
        
        this.logger.debug('NodeCounterFeatureModeManager', 'Event Bus listeners registered');
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
        
        // Count all text elements that have data-node-id (all actual diagram nodes)
        let count = 0;
        const nodeIds = [];
        
        svg.selectAll('text').each(function() {
            const element = d3.select(this);
            const nodeId = element.attr('data-node-id');
            
            // Count any text element with a node-id
            if (nodeId) {
                count++;
                nodeIds.push(nodeId);
            }
        });
        
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
     * Handle Thinking Mode (ThinkGuide) button click
     * EXTRACTED FROM: toolbar-manager.js lines 2955-3106
     */
    async handleThinkingMode() {
        this.logger.info('NodeCounterFeatureModeManager', 'ThinkGuide Mode initiated - BUTTON CLICKED');
        
        // Check if panel is already open - toggle behavior like MindMate
        const thinkPanel = document.getElementById('thinking-panel');
        const isPanelOpen = thinkPanel && !thinkPanel.classList.contains('collapsed');
        
        this.logger.info('NodeCounterFeatureModeManager', 'Initial panel state:', {
            thinkPanelCollapsed: thinkPanel?.classList.contains('collapsed'),
            isPanelOpen: isPanelOpen,
            currentPanel: window.panelManager?.getCurrentPanel()
        });
        
        // If panel is already open, close it (toggle behavior)
        if (isPanelOpen) {
            this.logger.info('NodeCounterFeatureModeManager', 'ThinkGuide panel already open - closing it');
            if (window.panelManager) {
                window.panelManager.closeThinkGuidePanel();
                this.logger.info('NodeCounterFeatureModeManager', 'ThinkGuide panel closed');
            }
            return;
        }
        
        // Check if diagram type is supported by ThinkGuide BEFORE opening panel
        const diagramType = this.editor.diagramType;
        const supportedTypes = [
            'circle_map',
            'bubble_map', 
            'double_bubble_map',
            'tree_map',
            'flow_map',
            'multi_flow_map',
            'brace_map',
            'bridge_map',
            'mindmap'
        ];
        
        if (!supportedTypes.includes(diagramType)) {
            this.logger.warn('NodeCounterFeatureModeManager', `ThinkGuide not yet implemented for ${diagramType}`);
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const message = lang === 'zh' 
                ? `${diagramType} 暂不支持思考导航功能` 
                : `ThinkGuide is not yet available for ${diagramType}`;
            this.toolbarManager.showNotification(message, 'warning');
            return;
        }
        
        // Panel not open AND diagram type supported - open it
        this.logger.info('NodeCounterFeatureModeManager', 'Opening ThinkGuide panel...');
        
        if (window.panelManager) {
            try {
                // Emit event to initialize ThinkGuide manager if needed
                if (window.thinkGuideManager) {
                    window.thinkGuideManager.setDiagramContext(this.editor);
                }
                
                // Open the panel (which will trigger ThinkGuide initialization)
                await window.panelManager.openThinkGuidePanel();
                
                this.logger.info('NodeCounterFeatureModeManager', 'ThinkGuide panel opened successfully', {
                    diagramType: diagramType,
                    panelState: thinkPanel?.classList.contains('collapsed') ? 'collapsed' : 'open'
                });
                
            } catch (error) {
                this.logger.error('NodeCounterFeatureModeManager', 'Failed to open ThinkGuide panel', error);
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' 
                    ? '无法打开思考导航面板，请重试' 
                    : 'Failed to open ThinkGuide panel. Please try again.';
                this.toolbarManager.showNotification(message, 'error');
            }
        } else {
            this.logger.error('NodeCounterFeatureModeManager', 'PanelManager not available');
        }
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('NodeCounterFeatureModeManager', 'Destroying');
        
        // Remove Event Bus listeners
        this.eventBus.off('node_counter:setup_observer');
        this.eventBus.off('node_counter:update_requested');
        this.eventBus.off('session:validate_requested');
        this.eventBus.off('learning_mode:validate');
        this.eventBus.off('learning_mode:start_requested');
        this.eventBus.off('thinking_mode:toggle_requested');
        
        // Nullify references
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

