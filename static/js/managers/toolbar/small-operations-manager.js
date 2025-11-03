/**
 * Small Operations Manager
 * ===================================
 * 
 * Handles small utility operations: duplicate, undo, redo, and reset.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class SmallOperationsManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager;
        
        this.setupEventListeners();
        this.logger.info('SmallOperationsManager', 'Small Operations Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        this.eventBus.on('node:duplicate_requested', () => {
            this.handleDuplicateNode();
        });
        
        this.eventBus.on('history:undo_requested', () => {
            this.handleUndo();
        });
        
        this.eventBus.on('history:redo_requested', () => {
            this.handleRedo();
        });
        
        this.eventBus.on('diagram:reset_requested', () => {
            this.handleReset();
        });
        
        this.logger.debug('SmallOperationsManager', 'Event Bus listeners registered');
    }
    
    /**
     * Handle duplicate node (coming soon feature)
     * EXTRACTED FROM: toolbar-manager.js lines 2660-2662
     */
    handleDuplicateNode() {
        this.toolbarManager.showNotification(this.toolbarManager.getNotif('duplicateComingSoon'));
    }
    
    /**
     * Handle undo
     * EXTRACTED FROM: toolbar-manager.js lines 2667-2671
     */
    handleUndo() {
        if (this.editor) {
            this.editor.undo();
        }
    }
    
    /**
     * Handle redo
     * EXTRACTED FROM: toolbar-manager.js lines 2676-2680
     */
    handleRedo() {
        if (this.editor) {
            this.editor.redo();
        }
    }
    
    /**
     * Reset canvas to blank template
     * EXTRACTED FROM: toolbar-manager.js lines 2685-2725
     */
    handleReset() {
        if (!this.editor) return;
        
        // Confirm with user - language-aware message
        const confirmMessage = this.toolbarManager.getNotif('resetConfirm');
        const confirmed = confirm(confirmMessage);
        if (!confirmed) return;
        
        // Get the diagram selector to retrieve blank template
        const diagramSelector = window.diagramSelector;
        if (!diagramSelector) {
            this.logger.error('SmallOperationsManager', 'Diagram selector not available');
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('resetFailed'), 'error');
            return;
        }
        
        // Get blank template for current diagram type
        const blankTemplate = diagramSelector.getTemplate(this.editor.diagramType);
        if (!blankTemplate) {
            this.logger.error('SmallOperationsManager', `Failed to get blank template for: ${this.editor.diagramType}`);
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('templateNotFound'), 'error');
            return;
        }
        
        // Reset the spec and re-render
        this.editor.currentSpec = blankTemplate;
        this.editor.renderDiagram();
        
        // Clear history
        if (this.editor.history) {
            this.editor.history = [JSON.parse(JSON.stringify(blankTemplate))];
            this.editor.historyIndex = 0;
        }
        
        // Clear selection
        if (this.editor.selectionManager) {
            this.editor.selectionManager.clearSelection();
        }
        
        this.toolbarManager.showNotification(this.toolbarManager.getNotif('canvasReset'), 'success');
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('SmallOperationsManager', 'Destroying');
        
        // Remove Event Bus listeners
        this.eventBus.off('node:duplicate_requested');
        this.eventBus.off('history:undo_requested');
        this.eventBus.off('history:redo_requested');
        this.eventBus.off('diagram:reset_requested');
        
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
    window.SmallOperationsManager = SmallOperationsManager;
}

