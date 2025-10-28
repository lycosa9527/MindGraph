/**
 * Node & Property Operations Manager
 * ===================================
 * 
 * Handles property panel operations and basic node operations (add, delete, empty).
 * Manages style applications, resets, and template defaults.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 * @size_target ~400 lines (property operations + node CRUD)
 */

class NodePropertyOperationsManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager; // Need access to UI elements and notifications
        
        this.setupEventListeners();
        this.logger.info('NodePropertyOperationsManager', 'Node & Property Operations Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        // Property operations
        this.eventBus.on('properties:apply_all_requested', () => {
            this.applyAllProperties();
        });
        
        this.eventBus.on('properties:apply_realtime_requested', () => {
            this.applyStylesRealtime();
        });
        
        this.eventBus.on('properties:reset_requested', () => {
            this.resetStyles();
        });
        
        this.eventBus.on('properties:toggle_bold_requested', () => {
            this.toggleBold();
        });
        
        this.eventBus.on('properties:toggle_italic_requested', () => {
            this.toggleItalic();
        });
        
        this.eventBus.on('properties:toggle_underline_requested', () => {
            this.toggleUnderline();
        });
        
        // Node operations
        this.eventBus.on('node:add_requested', () => {
            this.handleAddNode();
        });
        
        this.eventBus.on('node:delete_requested', () => {
            this.handleDeleteNode();
        });
        
        this.eventBus.on('node:empty_requested', () => {
            this.handleEmptyNode();
        });
        
        this.logger.debug('NodePropertyOperationsManager', 'Event Bus listeners registered');
    }
    
    /**
     * Apply all properties to selected nodes
     * EXTRACTED FROM: toolbar-manager.js lines 780-870
     */
    applyAllProperties() {
        if (this.toolbarManager.currentSelection.length === 0) return;
        
        const properties = {
            text: this.toolbarManager.propText?.value,
            fontSize: this.toolbarManager.propFontSize?.value,
            fontFamily: this.toolbarManager.propFontFamily?.value,
            textColor: this.toolbarManager.propTextColor?.value,
            fillColor: this.toolbarManager.propFillColor?.value,
            strokeColor: this.toolbarManager.propStrokeColor?.value,
            strokeWidth: this.toolbarManager.propStrokeWidth?.value,
            opacity: this.toolbarManager.propOpacity?.value,
            bold: this.toolbarManager.propBold?.classList.contains('active'),
            italic: this.toolbarManager.propItalic?.classList.contains('active'),
            underline: this.toolbarManager.propUnderline?.classList.contains('active')
        };
        
        this.logger.debug('NodePropertyOperationsManager', 'Applying all properties', {
            count: this.toolbarManager.currentSelection.length
        });
        
        // Apply text changes first using the proper method (silently - we'll show one notification at the end)
        if (properties.text && properties.text.trim()) {
            this.toolbarManager.applyText(true); // Pass true to suppress notification
        }
        
        this.toolbarManager.currentSelection.forEach(nodeId => {
            const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (nodeElement.empty()) return;
            
            // Find text element using multiple methods
            let textElement = d3.select(`[data-text-for="${nodeId}"]`);
            if (textElement.empty()) {
                const node = nodeElement.node();
                if (node.nextElementSibling && node.nextElementSibling.tagName === 'text') {
                    textElement = d3.select(node.nextElementSibling);
                } else {
                    textElement = nodeElement.select('text');
                }
            }
            
            // Apply shape properties
            if (properties.fillColor) {
                nodeElement.attr('fill', properties.fillColor);
            }
            if (properties.strokeColor) {
                nodeElement.attr('stroke', properties.strokeColor);
            }
            if (properties.strokeWidth) {
                nodeElement.attr('stroke-width', properties.strokeWidth);
            }
            if (properties.opacity) {
                nodeElement.attr('opacity', properties.opacity);
            }
            
            // Apply text styling properties (not content - that's handled by applyText)
            if (!textElement.empty()) {
                if (properties.fontSize) {
                    textElement.attr('font-size', properties.fontSize);
                }
                if (properties.fontFamily) {
                    textElement.attr('font-family', properties.fontFamily);
                }
                if (properties.textColor) {
                    textElement.attr('fill', properties.textColor);
                }
                if (properties.bold) {
                    textElement.attr('font-weight', 'bold');
                } else {
                    textElement.attr('font-weight', 'normal');
                }
                if (properties.italic) {
                    textElement.attr('font-style', 'italic');
                } else {
                    textElement.attr('font-style', 'normal');
                }
                if (properties.underline) {
                    textElement.attr('text-decoration', 'underline');
                } else {
                    textElement.attr('text-decoration', 'none');
                }
            }
        });
        
        this.editor?.saveToHistory('update_properties', { 
            nodes: this.toolbarManager.currentSelection, 
            properties 
        });
        
        this.toolbarManager.showNotification(this.toolbarManager.getNotif('propertiesApplied'), 'success');
    }
    
    /**
     * Apply styles in real-time (without notification)
     * EXTRACTED FROM: toolbar-manager.js lines 875-937
     */
    applyStylesRealtime() {
        if (this.toolbarManager.currentSelection.length === 0) return;
        
        const properties = {
            fontSize: this.toolbarManager.propFontSize?.value,
            fontFamily: this.toolbarManager.propFontFamily?.value,
            textColor: this.toolbarManager.propTextColor?.value,
            fillColor: this.toolbarManager.propFillColor?.value,
            strokeColor: this.toolbarManager.propStrokeColor?.value,
            strokeWidth: this.toolbarManager.propStrokeWidth?.value,
            opacity: this.toolbarManager.propOpacity?.value,
            bold: this.toolbarManager.propBold?.classList.contains('active'),
            italic: this.toolbarManager.propItalic?.classList.contains('active'),
            underline: this.toolbarManager.propUnderline?.classList.contains('active')
        };
        
        // Apply to all selected nodes
        this.toolbarManager.currentSelection.forEach(nodeId => {
            const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (nodeElement.empty()) return;
            
            // Apply shape properties
            if (properties.fillColor) {
                nodeElement.attr('fill', properties.fillColor);
            }
            if (properties.strokeColor) {
                nodeElement.attr('stroke', properties.strokeColor);
            }
            if (properties.strokeWidth) {
                nodeElement.attr('stroke-width', properties.strokeWidth);
            }
            if (properties.opacity) {
                nodeElement.attr('opacity', properties.opacity);
            }
            
            // Find and apply text properties
            let textElement = nodeElement.select('text');
            if (textElement.empty()) {
                textElement = d3.select(`[data-text-for="${nodeId}"]`);
            }
            
            if (!textElement.empty()) {
                if (properties.fontSize) {
                    textElement.attr('font-size', properties.fontSize);
                }
                if (properties.fontFamily) {
                    textElement.attr('font-family', properties.fontFamily);
                }
                if (properties.textColor) {
                    textElement.attr('fill', properties.textColor);
                }
                textElement.attr('font-weight', properties.bold ? 'bold' : 'normal');
                textElement.attr('font-style', properties.italic ? 'italic' : 'normal');
                textElement.attr('text-decoration', properties.underline ? 'underline' : 'none');
            }
        });
        
        // Save to history silently
        this.editor?.saveToHistory('update_properties', { 
            nodes: this.toolbarManager.currentSelection, 
            properties 
        });
    }
    
    /**
     * Reset styles to template defaults (keep text unchanged)
     * EXTRACTED FROM: toolbar-manager.js lines 942-976
     */
    resetStyles() {
        if (this.toolbarManager.currentSelection.length === 0) return;
        
        // Get template defaults based on diagram type
        const defaultProps = this.getTemplateDefaults();
        
        // Update UI inputs to template defaults
        if (this.toolbarManager.propFontSize) this.toolbarManager.propFontSize.value = parseInt(defaultProps.fontSize);
        if (this.toolbarManager.propFontFamily) this.toolbarManager.propFontFamily.value = defaultProps.fontFamily;
        if (this.toolbarManager.propTextColor) this.toolbarManager.propTextColor.value = defaultProps.textColor;
        if (this.toolbarManager.propTextColorHex) this.toolbarManager.propTextColorHex.value = defaultProps.textColor.toUpperCase();
        if (this.toolbarManager.propFillColor) this.toolbarManager.propFillColor.value = defaultProps.fillColor;
        if (this.toolbarManager.propFillColorHex) this.toolbarManager.propFillColorHex.value = defaultProps.fillColor.toUpperCase();
        if (this.toolbarManager.propStrokeColor) this.toolbarManager.propStrokeColor.value = defaultProps.strokeColor;
        if (this.toolbarManager.propStrokeColorHex) this.toolbarManager.propStrokeColorHex.value = defaultProps.strokeColor.toUpperCase();
        if (this.toolbarManager.propStrokeWidth) this.toolbarManager.propStrokeWidth.value = parseFloat(defaultProps.strokeWidth);
        if (this.toolbarManager.strokeWidthValue) this.toolbarManager.strokeWidthValue.textContent = `${defaultProps.strokeWidth}px`;
        if (this.toolbarManager.propOpacity) this.toolbarManager.propOpacity.value = parseFloat(defaultProps.opacity);
        if (this.toolbarManager.opacityValue) this.toolbarManager.opacityValue.textContent = `${Math.round(parseFloat(defaultProps.opacity) * 100)}%`;
        
        // Reset style toggles to defaults (off)
        this.toolbarManager.propBold?.classList.remove('active');
        this.toolbarManager.propItalic?.classList.remove('active');
        this.toolbarManager.propUnderline?.classList.remove('active');
        
        // Apply template defaults to selected nodes
        this.applyStylesRealtime();
        
        this.toolbarManager.showNotification(
            window.languageManager?.getCurrentLanguage() === 'zh' 
                ? '样式已重置为模板默认值' 
                : 'Styles reset to template defaults',
            'success'
        );
    }
    
    /**
     * Get template default styles based on diagram type
     * EXTRACTED FROM: toolbar-manager.js lines 981-1012
     */
    getTemplateDefaults() {
        const diagramType = this.editor?.diagramType;
        
        // Standard defaults used across all diagram types
        const standardDefaults = {
            fontSize: '14',
            fontFamily: 'Inter, sans-serif',
            textColor: '#000000',
            fillColor: '#2196f3',
            strokeColor: '#1976d2',
            strokeWidth: '2',
            opacity: '1'
        };
        
        // Diagram-specific overrides (if needed)
        const typeSpecificDefaults = {
            'double_bubble_map': {
                ...standardDefaults,
                fillColor: '#4caf50', // Green for similarities
            },
            'multi_flow_map': {
                ...standardDefaults,
                fillColor: '#ff9800', // Orange for events
            },
            'concept_map': {
                ...standardDefaults,
                fillColor: '#9c27b0', // Purple for concepts
            }
        };
        
        return typeSpecificDefaults[diagramType] || standardDefaults;
    }
    
    /**
     * Toggle bold
     * EXTRACTED FROM: toolbar-manager.js lines 1017-1019
     */
    toggleBold() {
        this.toolbarManager.propBold.classList.toggle('active');
    }
    
    /**
     * Toggle italic
     * EXTRACTED FROM: toolbar-manager.js lines 1024-1026
     */
    toggleItalic() {
        this.toolbarManager.propItalic.classList.toggle('active');
    }
    
    /**
     * Toggle underline
     * EXTRACTED FROM: toolbar-manager.js lines 1031-1033
     */
    toggleUnderline() {
        this.toolbarManager.propUnderline.classList.toggle('active');
    }
    
    /**
     * Handle add node
     * EXTRACTED FROM: toolbar-manager.js lines 1038-1068
     */
    handleAddNode() {
        this.logger.debug('NodePropertyOperationsManager', 'handleAddNode called', {
            diagramType: this.editor?.diagramType
        });
        
        if (!this.editor) {
            this.logger.error('NodePropertyOperationsManager', 'handleAddNode blocked - editor not initialized');
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('editorNotInit'), 'error');
            return;
        }
        
        const diagramType = this.editor.diagramType;
        const requiresSelection = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map', 'mindmap'].includes(diagramType);

        // Check if selection is required for this diagram type
        if (requiresSelection && this.toolbarManager.currentSelection.length === 0) {
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('selectNodeToAdd'), 'warning');
            return;
        }
        
        // Call editor's addNode method (it will handle diagram-specific logic)
        this.editor.addNode();
        
        // Only show generic success notification for diagram types that don't show their own
        const showsOwnNotification = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map', 'bridge_map', 'circle_map', 'bubble_map', 'concept_map', 'mindmap'].includes(diagramType);
        if (!showsOwnNotification) {
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('nodeAdded'), 'success');
        }
        
        // Node count updates automatically via MutationObserver
    }
    
    /**
     * Handle delete node
     * EXTRACTED FROM: toolbar-manager.js lines 1073-1084
     */
    handleDeleteNode() {
        if (this.editor && this.toolbarManager.currentSelection.length > 0) {
            const count = this.toolbarManager.currentSelection.length;
            this.editor.deleteSelectedNodes();
            
            // Hide property panel via Event Bus
            window.eventBus.emit('property_panel:close_requested', {});
            
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('nodesDeleted', count), 'success');
            
            // Node count updates automatically via MutationObserver
        } else {
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('selectNodeToDelete'), 'warning');
        }
    }
    
    /**
     * Handle empty node text (clear text but keep node)
     * EXTRACTED FROM: toolbar-manager.js lines 1089-1138
     */
    handleEmptyNode() {
        if (this.editor && this.toolbarManager.currentSelection.length > 0) {
            const nodeIds = [...this.toolbarManager.currentSelection];
            
            nodeIds.forEach(nodeId => {
                // Find the shape element
                const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
                if (shapeElement.empty()) {
                    this.logger.warn('NodePropertyOperationsManager', `Shape not found for nodeId: ${nodeId}`);
                    return;
                }
                
                // Find the text element
                let textElement = d3.select(`[data-text-for="${nodeId}"]`);
                
                // If not found, try to find text as sibling or in parent group
                if (textElement.empty()) {
                    const shapeNode = shapeElement.node();
                    const nextSibling = shapeNode.nextElementSibling;
                    if (nextSibling && nextSibling.tagName === 'text') {
                        textElement = d3.select(nextSibling);
                    } else if (shapeNode.parentElement && shapeNode.parentElement.tagName === 'g') {
                        textElement = d3.select(shapeNode.parentElement).select('text');
                    }
                }
                
                if (!textElement.empty()) {
                    const textNode = textElement.node();
                    
                    // Update the text to empty string
                    if (this.editor && typeof this.editor.updateNodeText === 'function') {
                        this.editor.updateNodeText(nodeId, shapeElement.node(), textNode, '');
                    } else {
                        // Fallback: just update the DOM
                        textElement.text('');
                    }
                }
            });
            
            const count = nodeIds.length;
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('nodesEmptied', count), 'success');
            
            // Update property panel if still showing
            if (this.toolbarManager.currentSelection.length > 0) {
                this.toolbarManager.loadNodeProperties(this.toolbarManager.currentSelection[0]);
            }
        } else {
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('selectNodeToEmpty'), 'warning');
        }
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('NodePropertyOperationsManager', 'Destroying');
        
        // Remove all Event Bus listeners
        // Note: Since callbacks weren't stored, we remove by event name
        // This removes ALL listeners for these events (safe since manager is being destroyed)
        this.eventBus.off('properties:apply_all_requested');
        this.eventBus.off('properties:apply_realtime_requested');
        this.eventBus.off('properties:reset_requested');
        this.eventBus.off('properties:toggle_bold_requested');
        this.eventBus.off('properties:toggle_italic_requested');
        this.eventBus.off('properties:toggle_underline_requested');
        this.eventBus.off('node:add_requested');
        this.eventBus.off('node:delete_requested');
        this.eventBus.off('node:empty_requested');
        
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
    window.NodePropertyOperationsManager = NodePropertyOperationsManager;
}

