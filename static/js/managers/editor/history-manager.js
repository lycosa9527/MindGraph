/**
 * History Manager
 * ===============
 * 
 * Manages undo/redo history for diagram editing.
 * Handles state snapshots and history stack operations.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class HistoryManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'HistoryManager';
        
        // History stack
        this.history = [];
        this.historyIndex = -1;
        this.maxHistorySize = 50; // Limit history to prevent memory issues
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('HistoryManager', 'History Manager initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for history save requests
        this.eventBus.onWithOwner('diagram:operation_completed', (data) => {
            // saveToHistory expects: (action, metadata, spec)
            // data.operation = action, data.snapshot = spec
            this.saveToHistory(data.operation, {}, data.snapshot);
        }, this.ownerId);
        
        // Listen for undo requests
        this.eventBus.onWithOwner('history:undo_requested', () => {
            this.undo();
        }, this.ownerId);
        
        // Listen for redo requests
        this.eventBus.onWithOwner('history:redo_requested', () => {
            this.redo();
        }, this.ownerId);
        
        // Listen for history clear requests
        this.eventBus.onWithOwner('history:clear_requested', () => {
            this.clearHistory();
        }, this.ownerId);
        
        this.logger.debug('HistoryManager', 'Subscribed to events');
    }
    
    /**
     * Save current state to history
     * @param {string} action - Action name (add_node, delete_node, etc.)
     * @param {Object} metadata - Action metadata
     * @param {Object} spec - Complete diagram spec
     */
    saveToHistory(action, metadata, spec) {
        if (!spec) {
            this.logger.warn('HistoryManager', 'Cannot save to history - no spec provided');
            return;
        }
        
        // Remove any history after current index (branch cut)
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Save a deep clone of the ENTIRE spec
        this.history.push({
            action,
            metadata: metadata ? JSON.parse(JSON.stringify(metadata)) : {},
            spec: JSON.parse(JSON.stringify(spec)), // Deep clone
            timestamp: Date.now()
        });
        
        this.historyIndex = this.history.length - 1;
        
        // Limit history size (50 states)
        if (this.history.length > this.maxHistorySize) {
            this.history.shift();
            this.historyIndex--;
        }
        
        this.logger.debug('HistoryManager', `History saved: ${action}, total states: ${this.history.length}, current index: ${this.historyIndex}`);
        
        // Emit history saved event
        this.eventBus.emit('history:saved', {
            action,
            metadata,
            historyIndex: this.historyIndex,
            historySize: this.history.length,
            canUndo: this.canUndo(),
            canRedo: this.canRedo()
        });
        
        // Update toolbar button states
        this.updateToolbarButtons();
    }
    
    /**
     * Undo last operation
     */
    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            const historyEntry = this.history[this.historyIndex];
            
            this.logger.debug('HistoryManager', `Undo: ${historyEntry.action}`, historyEntry.metadata);
            
            // Emit undo event with restored spec
            this.eventBus.emit('history:undo_completed', {
                action: historyEntry.action,
                metadata: historyEntry.metadata,
                spec: JSON.parse(JSON.stringify(historyEntry.spec)), // Deep clone
                historyIndex: this.historyIndex,
                canUndo: this.canUndo(),
                canRedo: this.canRedo()
            });
            
            // Update toolbar button states
            this.updateToolbarButtons();
        } else {
            this.logger.debug('HistoryManager', 'Undo: No more history to undo');
            
            // Emit warning event
            this.eventBus.emit('history:undo_failed', {
                reason: 'No more history to undo'
            });
        }
    }
    
    /**
     * Redo last undone operation
     */
    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            const historyEntry = this.history[this.historyIndex];
            
            this.logger.debug('HistoryManager', `Redo: ${historyEntry.action}`, historyEntry.metadata);
            
            // Emit redo event with restored spec
            this.eventBus.emit('history:redo_completed', {
                action: historyEntry.action,
                metadata: historyEntry.metadata,
                spec: JSON.parse(JSON.stringify(historyEntry.spec)), // Deep clone
                historyIndex: this.historyIndex,
                canUndo: this.canUndo(),
                canRedo: this.canRedo()
            });
            
            // Update toolbar button states
            this.updateToolbarButtons();
        } else {
            this.logger.debug('HistoryManager', 'Redo: No more history to redo');
            
            // Emit warning event
            this.eventBus.emit('history:redo_failed', {
                reason: 'No more history to redo'
            });
        }
    }
    
    /**
     * Check if undo is possible
     * @returns {boolean}
     */
    canUndo() {
        return this.historyIndex > 0;
    }
    
    /**
     * Check if redo is possible
     * @returns {boolean}
     */
    canRedo() {
        return this.historyIndex < this.history.length - 1;
    }
    
    /**
     * Clear all history
     */
    clearHistory() {
        this.logger.info('HistoryManager', 'Clearing history');
        
        this.history = [];
        this.historyIndex = -1;
        
        // Emit history cleared event
        this.eventBus.emit('history:cleared', {
            canUndo: false,
            canRedo: false
        });
        
        // Update toolbar button states
        this.updateToolbarButtons();
    }
    
    /**
     * Get current history state
     * @returns {Object} History state
     */
    getHistoryState() {
        return {
            size: this.history.length,
            index: this.historyIndex,
            canUndo: this.canUndo(),
            canRedo: this.canRedo()
        };
    }
    
    /**
     * Get history snapshot at specific index
     * @param {number} index - History index
     * @returns {Object|null} Snapshot
     */
    getSnapshot(index) {
        if (index < 0 || index >= this.history.length) {
            return null;
        }
        
        return this.history[index].snapshot;
    }
    
    /**
     * Update toolbar undo/redo button states
     */
    updateToolbarButtons() {
        this.eventBus.emit('history:state_changed', {
            canUndo: this.canUndo(),
            canRedo: this.canRedo(),
            historySize: this.history.length,
            historyIndex: this.historyIndex
        });
    }
    
    /**
     * Destroy history manager
     */
    destroy() {
        this.logger.info('HistoryManager', 'Destroying History Manager');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('HistoryManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        this.clearHistory();
    }
}

// Make available globally
window.HistoryManager = HistoryManager;

