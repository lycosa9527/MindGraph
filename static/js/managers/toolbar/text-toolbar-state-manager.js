/**
 * Text & Toolbar State Manager
 * ===================================
 * 
 * Handles text operations, toolbar button states, and notification helpers.
 * Manages i18n text retrieval and notification display/sound.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 * @size ~140 lines
 */

class TextToolbarStateManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager; // Need access to UI elements
        
        this.setupEventListeners();
        this.logger.info('TextToolbarStateManager', 'Text & Toolbar State Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        this.eventBus.on('text:apply_requested', (data) => {
            this.applyText(data.silent);
        });
        
        this.eventBus.on('toolbar:update_state_requested', (data) => {
            this.updateToolbarState(data.hasSelection);
        });
        
        this.eventBus.on('notification:get_text', (data) => {
            const text = this.getNotif(data.key, ...(data.args || []));
            this.eventBus.emit('notification:text_retrieved', { key: data.key, text });
        });
        
        this.eventBus.on('notification:show_requested', (data) => {
            this.showNotification(data.message, data.type);
        });
        
        this.eventBus.on('notification:play_sound_requested', () => {
            this.playNotificationSound();
        });
        
        this.logger.debug('TextToolbarStateManager', 'Event Bus listeners registered');
    }
    
    /**
     * Apply text changes to selected nodes
     * EXTRACTED FROM: toolbar-manager.js lines 731-787
     */
    applyText(silent = false) {
        if (this.toolbarManager.currentSelection.length === 0) return;
        
        const newText = this.toolbarManager.propText.value.trim();
        if (!newText) {
            // If empty, no text to apply (user didn't type anything)
            this.showNotification(this.getNotif('textEmpty'), 'warning');
            return;
        }
        
        this.logger.debug('TextToolbarStateManager', 'Applying text to selected nodes', {
            count: this.toolbarManager.currentSelection.length
        });
        
        this.toolbarManager.currentSelection.forEach(nodeId => {
            // Get the shape node
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (shapeElement.empty()) {
                this.logger.warn('TextToolbarStateManager', `Node ${nodeId} not found`);
                return;
            }
            
            const shapeNode = shapeElement.node();
            
            // Find associated text element
            let textNode = null;
            
            // Method 1: Try data-text-for attribute
            const textByDataAttr = d3.select(`[data-text-for="${nodeId}"]`);
            if (!textByDataAttr.empty()) {
                textNode = textByDataAttr.node();
            } else {
                // Method 2: Try next sibling
                if (shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                    textNode = shapeNode.nextElementSibling;
                } else {
                    // Method 3: Try child text (for grouped elements)
                    const textChild = shapeElement.select('text');
                    if (!textChild.empty()) {
                        textNode = textChild.node();
                    }
                }
            }
            
            // Use the editor's updateNodeText method which handles all diagram types properly
            if (this.editor && typeof this.editor.updateNodeText === 'function') {
                this.editor.updateNodeText(nodeId, shapeNode, textNode, newText);
            } else {
                this.logger.error('TextToolbarStateManager', 'Editor updateNodeText method not available');
            }
        });
        
        // Only show notification if not called from applyAllProperties
        if (!silent) {
            this.showNotification(this.getNotif('textUpdated'), 'success');
        }
    }
    
    /**
     * Update toolbar button states based on selection
     * EXTRACTED FROM: toolbar-manager.js lines 668-698
     */
    updateToolbarState(hasSelection) {
        const deleteNodeBtn = this.toolbarManager.deleteNodeBtn;
        const emptyNodeBtn = this.toolbarManager.emptyNodeBtn;
        const duplicateNodeBtn = this.toolbarManager.duplicateNodeBtn;
        const addNodeBtn = this.toolbarManager.addNodeBtn;
        
        if (deleteNodeBtn) {
            deleteNodeBtn.disabled = !hasSelection;
            deleteNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        if (emptyNodeBtn) {
            emptyNodeBtn.disabled = !hasSelection;
            emptyNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        if (duplicateNodeBtn) {
            duplicateNodeBtn.disabled = !hasSelection;
            duplicateNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        // Add button state for diagrams that require selection
        if (addNodeBtn && this.editor) {
            const diagramType = this.editor.diagramType;
            const requiresSelection = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map'].includes(diagramType);
            
            if (requiresSelection) {
                addNodeBtn.disabled = !hasSelection;
                addNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
            } else {
                // For other diagram types, add button is always enabled
                addNodeBtn.disabled = false;
                addNodeBtn.style.opacity = '1';
            }
        }
    }
    
    /**
     * Get translated notification message
     * EXTRACTED FROM: toolbar-manager.js lines 2737-2742
     */
    getNotif(key, ...args) {
        if (window.languageManager && window.languageManager.getNotification) {
            return window.languageManager.getNotification(key, ...args);
        }
        return key; // Fallback to key if language manager not available
    }
    
    /**
     * Show notification using centralized notification manager
     * EXTRACTED FROM: toolbar-manager.js lines 2747-2753
     */
    showNotification(message, type = 'info') {
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        } else {
            this.logger.error('TextToolbarStateManager', 'NotificationManager not available');
        }
    }
    
    /**
     * Play notification sound when first diagram is rendered
     * EXTRACTED FROM: toolbar-manager.js lines 2758-2787
     */
    playNotificationSound() {
        try {
            // Create audio context for a pleasant "ding" sound
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            // Connect nodes
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Configure pleasant notification sound (two-tone ding)
            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime); // First tone (higher)
            oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1); // Second tone (lower)
            
            // Quick fade out for smooth sound
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
            
            // Play
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.3);
            
            this.logger.debug('TextToolbarStateManager', 'Notification sound played');
        } catch (error) {
            // Silently fail if audio is not supported or blocked
            this.logger.debug('TextToolbarStateManager', 'Could not play notification sound', error);
        }
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('TextToolbarStateManager', 'Destroying');
        
        // Remove Event Bus listeners
        this.eventBus.off('text:apply_requested');
        this.eventBus.off('toolbar:update_state_requested');
        this.eventBus.off('notification:get_text');
        this.eventBus.off('notification:show_requested');
        this.eventBus.off('notification:play_sound_requested');
        
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
    window.TextToolbarStateManager = TextToolbarStateManager;
}

