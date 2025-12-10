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
        
        // Owner ID for Event Bus Listener Registry
        this.ownerId = 'SmallOperationsManager';
        
        this.setupEventListeners();
        this.logger.info('SmallOperationsManager', 'Small Operations Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        this.eventBus.onWithOwner('node:duplicate_requested', () => {
            this.handleDuplicateNode();
        }, this.ownerId);
        
        this.eventBus.onWithOwner('history:undo_requested', () => {
            this.handleUndo();
        }, this.ownerId);
        
        this.eventBus.onWithOwner('history:redo_requested', () => {
            this.handleRedo();
        }, this.ownerId);
        
        this.eventBus.onWithOwner('diagram:reset_requested', () => {
            this.handleReset();
        }, this.ownerId);
        
        this.logger.debug('SmallOperationsManager', 'Event Bus listeners registered with owner tracking');
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
        // ARCHITECTURE: Use State Manager as source of truth for diagram type
        const diagramType = this.stateManager?.getDiagramState()?.type || this.editor?.diagramType;
        const blankTemplate = diagramSelector.getTemplate(diagramType);
        if (!blankTemplate) {
            this.logger.error('SmallOperationsManager', `Failed to get blank template for: ${diagramType}`);
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('templateNotFound'), 'error');
            return;
        }
        
        // Reset the spec and re-render
        this.editor.currentSpec = blankTemplate;
        this.editor.renderDiagram();
        
        // Clear editor's local history
        if (this.editor.history) {
            this.editor.history = [JSON.parse(JSON.stringify(blankTemplate))];
            this.editor.historyIndex = 0;
        }
        
        // Clear HistoryManager's history via Event Bus
        // This ensures HistoryManager doesn't retain old history entries that could be undone
        if (this.eventBus) {
            this.eventBus.emit('history:clear_requested', {});
            this.logger.debug('SmallOperationsManager', 'Requested HistoryManager to clear history');
            
            // Save the blank template as initial state in HistoryManager
            // This allows users to undo back to the reset state if needed
            this.eventBus.emit('diagram:operation_completed', {
                operation: 'reset',
                snapshot: JSON.parse(JSON.stringify(blankTemplate))
            });
            this.logger.debug('SmallOperationsManager', 'Saved reset state to HistoryManager');
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
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('SmallOperationsManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
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
