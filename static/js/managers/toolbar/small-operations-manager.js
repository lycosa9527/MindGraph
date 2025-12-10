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
        
        // NOTE: Undo/redo are now handled by HistoryManager directly
        // HistoryManager listens to history:undo_requested and history:redo_requested
        // and emits history:undo_completed/history:redo_completed which InteractiveEditor listens to
        // No need for SmallOperationsManager to intercept these events
        
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
     * DEPRECATED: Undo/redo are now handled by HistoryManager via Event Bus
     * HistoryManager listens to history:undo_requested and emits history:undo_completed
     * InteractiveEditor listens to history:undo_completed and applies the changes
     */
    handleUndo() {
        // No longer needed - HistoryManager handles this
        this.logger.debug('SmallOperationsManager', 'Undo request - handled by HistoryManager');
    }
    
    /**
     * Handle redo
     * DEPRECATED: Undo/redo are now handled by HistoryManager via Event Bus
     * HistoryManager listens to history:redo_requested and emits history:redo_completed
     * InteractiveEditor listens to history:redo_completed and applies the changes
     */
    handleRedo() {
        // No longer needed - HistoryManager handles this
        this.logger.debug('SmallOperationsManager', 'Redo request - handled by HistoryManager');
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

