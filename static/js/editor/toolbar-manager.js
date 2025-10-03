/**
 * ToolbarManager - Manages toolbar actions and property panel
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class ToolbarManager {
    constructor(editor) {
        this.editor = editor;
        this.propertyPanel = null;
        this.currentSelection = [];
        this.isAutoCompleting = false; // Flag to prevent concurrent auto-complete operations
        
        // Session management - store session ID for lifecycle management
        this.sessionId = editor.sessionId;
        this.diagramType = editor.diagramType;
        
        const logMessage = `Created for session: ${this.sessionId?.substr(-8)} | Type: ${this.diagramType}`;
        console.log('ToolbarManager:', logMessage);
        
        // Send to backend terminal
        this.logToBackend('INFO', logMessage);
        
        // Register this instance in the global registry
        this.registerInstance();
        
        this.initializeElements();
        this.attachEventListeners();
        this.listenToSelectionChanges();
    }
    
    /**
     * Send log to backend terminal console
     */
    logToBackend(level, message, data = null) {
        try {
            fetch('/api/frontend_log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    level: level,
                    message: message,
                    data: data,
                    source: 'ToolbarManager',
                    sessionId: this.sessionId
                })
            }).catch(() => {});
        } catch (e) {}
    }
    
    /**
     * Register this toolbar manager instance globally, cleaning up old instances from different sessions
     */
    registerInstance() {
        // Initialize global registry if it doesn't exist
        if (!window.toolbarManagerRegistry) {
            window.toolbarManagerRegistry = new Map();
            console.log('ToolbarManager: Registry initialized');
        }
        
        // Clean up any existing toolbar manager from a different session
        window.toolbarManagerRegistry.forEach((oldManager, oldSessionId) => {
            if (oldSessionId !== this.sessionId) {
                console.log('ToolbarManager: Cleaning up old instance from session:', oldSessionId?.substr(-8));
                oldManager.destroy();
                window.toolbarManagerRegistry.delete(oldSessionId);
            }
        });
        
        // Register this instance
        window.toolbarManagerRegistry.set(this.sessionId, this);
        console.log('ToolbarManager: Instance registered for session:', this.sessionId?.substr(-8));
    }
    
    /**
     * Initialize DOM elements
     */
    initializeElements() {
        // Toolbar buttons
        this.addNodeBtn = document.getElementById('add-node-btn');
        this.deleteNodeBtn = document.getElementById('delete-node-btn');
        this.autoCompleteBtn = document.getElementById('auto-complete-btn');
        this.lineModeBtn = document.getElementById('line-mode-btn');
        this.duplicateNodeBtn = document.getElementById('duplicate-node-btn');
        this.emptyNodeBtn = document.getElementById('empty-node-btn');
        this.undoBtn = document.getElementById('undo-btn');
        this.redoBtn = document.getElementById('redo-btn');
        this.resetBtn = document.getElementById('reset-btn');
        this.exportBtn = document.getElementById('export-btn');
        this.backBtn = document.getElementById('back-to-gallery');
        
        // Line mode state
        this.isLineMode = false;
        
        // Property panel
        this.propertyPanel = document.getElementById('property-panel');
        this.closePropBtn = document.getElementById('close-properties');
        
        // Property inputs
        this.propText = document.getElementById('prop-text');
        this.propTextApply = document.getElementById('prop-text-apply');
        this.propFontSize = document.getElementById('prop-font-size');
        this.propFontFamily = document.getElementById('prop-font-family');
        this.propBold = document.getElementById('prop-bold');
        this.propItalic = document.getElementById('prop-italic');
        this.propUnderline = document.getElementById('prop-underline');
        this.propTextColor = document.getElementById('prop-text-color');
        this.propTextColorHex = document.getElementById('prop-text-color-hex');
        this.propFillColor = document.getElementById('prop-fill-color');
        this.propFillColorHex = document.getElementById('prop-fill-color-hex');
        this.propStrokeColor = document.getElementById('prop-stroke-color');
        this.propStrokeColorHex = document.getElementById('prop-stroke-color-hex');
        this.propStrokeWidth = document.getElementById('prop-stroke-width');
        this.propOpacity = document.getElementById('prop-opacity');
        this.applyAllBtn = document.getElementById('apply-all-properties');
        
        // Value displays
        this.strokeWidthValue = document.getElementById('stroke-width-value');
        this.opacityValue = document.getElementById('opacity-value');
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Toolbar buttons - stop event propagation to prevent conflicts
        this.addNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Add Node button clicked');
            this.handleAddNode();
        });
        this.deleteNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Delete Node button clicked');
            this.handleDeleteNode();
        });
        this.autoCompleteBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();  // Also prevent default to be extra safe
            console.log('ToolbarManager: Auto-Complete button clicked');
            this.handleAutoComplete();
        });
        this.lineModeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Line Mode button clicked');
            this.toggleLineMode();
        });
        this.duplicateNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Duplicate Node button clicked');
            this.handleDuplicateNode();
        });
        this.emptyNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Empty Node button clicked');
            this.handleEmptyNode();
        });
        this.undoBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Undo button clicked');
            this.handleUndo();
        });
        this.redoBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Redo button clicked');
            this.handleRedo();
        });
        this.resetBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Reset button clicked');
            this.handleReset();
        });
        this.exportBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Export button clicked');
            this.handleExport();
        });
        this.backBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('ToolbarManager: Back to Gallery button clicked');
            this.handleBackToGallery();
        });
        
        // Property panel
        this.closePropBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.hidePropertyPanel();
            this.clearPropertyPanel();
        });
        
        // Property inputs - prevent event bubbling to avoid accidental diagram switches
        this.propTextApply?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.applyText();
        });
        this.propBold?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.toggleBold();
        });
        this.propItalic?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.toggleItalic();
        });
        this.propUnderline?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.toggleUnderline();
        });
        this.applyAllBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.applyAllProperties();
        });
        
        // Color pickers sync
        this.propTextColor?.addEventListener('input', (e) => {
            this.propTextColorHex.value = e.target.value.toUpperCase();
        });
        this.propTextColorHex?.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                this.propTextColor.value = e.target.value;
            }
        });
        
        this.propFillColor?.addEventListener('input', (e) => {
            this.propFillColorHex.value = e.target.value.toUpperCase();
        });
        this.propFillColorHex?.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                this.propFillColor.value = e.target.value;
            }
        });
        
        this.propStrokeColor?.addEventListener('input', (e) => {
            this.propStrokeColorHex.value = e.target.value.toUpperCase();
        });
        this.propStrokeColorHex?.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                this.propStrokeColor.value = e.target.value;
            }
        });
        
        // Sliders
        this.propStrokeWidth?.addEventListener('input', (e) => {
            this.strokeWidthValue.textContent = `${e.target.value}px`;
        });
        
        this.propOpacity?.addEventListener('input', (e) => {
            const percent = Math.round(e.target.value * 100);
            this.opacityValue.textContent = `${percent}%`;
        });
    }
    
    /**
     * Listen to selection changes from editor
     */
    listenToSelectionChanges() {
        window.addEventListener('editor-selection-change', (event) => {
            this.currentSelection = event.detail.selectedNodes;
            const hasSelection = event.detail.hasSelection;
            
            // Update toolbar button states
            this.updateToolbarState(hasSelection);
            
            // Show/hide property panel based on selection
            if (hasSelection && this.currentSelection.length > 0) {
                this.showPropertyPanel();
                this.loadNodeProperties(this.currentSelection[0]);
            } else {
                // Hide property panel when no selection
                this.hidePropertyPanel();
                this.clearPropertyPanel();
            }
        });
        
        // Listen for notification requests from editor
        window.addEventListener('show-notification', (event) => {
            const { message, type } = event.detail;
            this.showNotification(message, type || 'info');
        });
    }
    
    /**
     * Update toolbar button states
     */
    updateToolbarState(hasSelection) {
        if (this.deleteNodeBtn) {
            this.deleteNodeBtn.disabled = !hasSelection;
            this.deleteNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        if (this.emptyNodeBtn) {
            this.emptyNodeBtn.disabled = !hasSelection;
            this.emptyNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        if (this.duplicateNodeBtn) {
            this.duplicateNodeBtn.disabled = !hasSelection;
            this.duplicateNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        // Add button state for diagrams that require selection (brace_map, double_bubble_map, flow_map, multi_flow_map)
        if (this.addNodeBtn && this.editor) {
            const diagramType = this.editor.diagramType;
            const requiresSelection = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map'].includes(diagramType);
            
            if (requiresSelection) {
                this.addNodeBtn.disabled = !hasSelection;
                this.addNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
            } else {
                // For other diagram types, add button is always enabled
                this.addNodeBtn.disabled = false;
                this.addNodeBtn.style.opacity = '1';
            }
        }
    }
    
    /**
     * Show property panel
     */
    showPropertyPanel() {
        if (this.propertyPanel) {
            this.propertyPanel.style.display = 'block';
        }
    }
    
    /**
     * Hide property panel
     */
    hidePropertyPanel() {
        if (this.propertyPanel) {
            this.propertyPanel.style.display = 'none';
        }
    }
    
    /**
     * Clear property panel inputs to default values
     * Called when switching diagrams or clearing selection
     */
    clearPropertyPanel() {
        // Clear text input
        if (this.propText) this.propText.value = '';
        
        // Reset font properties to defaults
        if (this.propFontSize) this.propFontSize.value = 14;
        if (this.propFontFamily) this.propFontFamily.value = 'Inter, sans-serif';
        
        // Reset colors to defaults
        if (this.propTextColor) this.propTextColor.value = '#000000';
        if (this.propTextColorHex) this.propTextColorHex.value = '#000000';
        if (this.propFillColor) this.propFillColor.value = '#2196f3';
        if (this.propFillColorHex) this.propFillColorHex.value = '#2196F3';
        if (this.propStrokeColor) this.propStrokeColor.value = '#1976d2';
        if (this.propStrokeColorHex) this.propStrokeColorHex.value = '#1976D2';
        
        // Reset stroke width and opacity to defaults
        if (this.propStrokeWidth) this.propStrokeWidth.value = 2;
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = '2px';
        if (this.propOpacity) this.propOpacity.value = 1;
        if (this.opacityValue) this.opacityValue.textContent = '100%';
        
        // Reset toggle buttons
        if (this.propBold) this.propBold.classList.remove('active');
        if (this.propItalic) this.propItalic.classList.remove('active');
        if (this.propUnderline) this.propUnderline.classList.remove('active');
        
        console.log('Property panel cleared to default values');
    }
    
    /**
     * Load properties from selected node
     */
    loadNodeProperties(nodeId) {
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        
        if (nodeElement.empty()) return;
        
        // Get node attributes
        const fill = nodeElement.attr('fill') || '#2196f3';
        const stroke = nodeElement.attr('stroke') || '#1976d2';
        const strokeWidth = nodeElement.attr('stroke-width') || '2';
        const opacity = nodeElement.attr('opacity') || '1';
        
        // Get text element
        const textElement = nodeElement.select('text');
        const text = textElement.text() || '';
        const fontSize = textElement.attr('font-size') || '14';
        const fontFamily = textElement.attr('font-family') || 'Inter, sans-serif';
        const textColor = textElement.attr('fill') || '#000000';
        const fontWeight = textElement.attr('font-weight') || 'normal';
        const fontStyle = textElement.attr('font-style') || 'normal';
        const textDecoration = textElement.attr('text-decoration') || 'none';
        
        // Update property inputs
        if (this.propText) this.propText.value = text;
        if (this.propFontSize) this.propFontSize.value = parseInt(fontSize);
        if (this.propFontFamily) this.propFontFamily.value = fontFamily;
        if (this.propTextColor) this.propTextColor.value = textColor;
        if (this.propTextColorHex) this.propTextColorHex.value = textColor.toUpperCase();
        if (this.propFillColor) this.propFillColor.value = fill;
        if (this.propFillColorHex) this.propFillColorHex.value = fill.toUpperCase();
        if (this.propStrokeColor) this.propStrokeColor.value = stroke;
        if (this.propStrokeColorHex) this.propStrokeColorHex.value = stroke.toUpperCase();
        if (this.propStrokeWidth) this.propStrokeWidth.value = parseFloat(strokeWidth);
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = `${strokeWidth}px`;
        if (this.propOpacity) this.propOpacity.value = parseFloat(opacity);
        if (this.opacityValue) this.opacityValue.textContent = `${Math.round(parseFloat(opacity) * 100)}%`;
        
        // Update toggle buttons
        if (this.propBold) {
            this.propBold.classList.toggle('active', fontWeight === 'bold');
        }
        if (this.propItalic) {
            this.propItalic.classList.toggle('active', fontStyle === 'italic');
        }
        if (this.propUnderline) {
            this.propUnderline.classList.toggle('active', textDecoration === 'underline');
        }
    }
    
    /**
     * Apply text changes
     */
    applyText(silent = false) {
        if (this.currentSelection.length === 0) return;
        
        const newText = this.propText.value.trim();
        if (!newText) {
            // Always show warning for empty text
            this.showNotification('Text cannot be empty', 'warning');
            return;
        }
        
        console.log('Applying text to selected nodes:', this.currentSelection);
        
        this.currentSelection.forEach(nodeId => {
            // Get the shape node
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (shapeElement.empty()) {
                console.warn(`Node ${nodeId} not found`);
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
                console.error('Editor updateNodeText method not available');
            }
        });
        
        // Only show notification if not called from applyAllProperties
        if (!silent) {
            console.log('ToolbarManager: applyText showing notification (silent=false)');
            this.showNotification('Text updated successfully', 'success');
        } else {
            console.log('ToolbarManager: applyText notification suppressed (silent=true)');
        }
    }
    
    /**
     * Apply all properties to selected nodes
     */
    applyAllProperties() {
        if (this.currentSelection.length === 0) return;
        
        const properties = {
            text: this.propText?.value,
            fontSize: this.propFontSize?.value,
            fontFamily: this.propFontFamily?.value,
            textColor: this.propTextColor?.value,
            fillColor: this.propFillColor?.value,
            strokeColor: this.propStrokeColor?.value,
            strokeWidth: this.propStrokeWidth?.value,
            opacity: this.propOpacity?.value,
            bold: this.propBold?.classList.contains('active'),
            italic: this.propItalic?.classList.contains('active'),
            underline: this.propUnderline?.classList.contains('active')
        };
        
        console.log('ToolbarManager: Applying all properties', {
            diagramType: this.editor?.diagramType,
            sessionId: this.editor?.sessionId?.substr(-8),
            selectedNodes: this.currentSelection,
            properties
        });
        
        // Apply text changes first using the proper method (silently - we'll show one notification at the end)
        if (properties.text && properties.text.trim()) {
            this.applyText(true); // Pass true to suppress notification
        }
        
        this.currentSelection.forEach(nodeId => {
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
            nodes: this.currentSelection, 
            properties 
        });
        
        console.log('ToolbarManager: applyAllProperties showing final notification');
        this.showNotification('All properties applied successfully!', 'success');
    }
    
    /**
     * Toggle bold
     */
    toggleBold() {
        this.propBold.classList.toggle('active');
    }
    
    /**
     * Toggle italic
     */
    toggleItalic() {
        this.propItalic.classList.toggle('active');
    }
    
    /**
     * Toggle underline
     */
    toggleUnderline() {
        this.propUnderline.classList.toggle('active');
    }
    
    /**
     * Handle add node
     */
    handleAddNode() {
        console.log('ToolbarManager: handleAddNode called', {
            diagramType: this.editor?.diagramType,
            sessionId: this.editor?.sessionId?.substr(-8),
            hasSelection: this.editor?.selectedNodes?.size > 0,
            selectedCount: this.editor?.selectedNodes?.size || 0
        });
        
        if (!this.editor) {
            console.error('ToolbarManager: handleAddNode blocked - Editor not initialized');
            this.showNotification('Editor not initialized', 'error');
            return;
        }
        
        const diagramType = this.editor.diagramType;
        const requiresSelection = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map'].includes(diagramType);

        // Check if selection is required for this diagram type
        if (requiresSelection && this.currentSelection.length === 0) {
            this.showNotification('Please select a node first to add', 'warning');
            return;
        }
        
        // Call editor's addNode method (it will handle diagram-specific logic)
        this.editor.addNode();
        
        // Only show generic success notification for diagram types that don't show their own
            const showsOwnNotification = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map', 'bridge_map', 'circle_map', 'bubble_map', 'concept_map'].includes(diagramType);
            if (!showsOwnNotification) {
                this.showNotification('Node added! Double-click to edit text.', 'success');
            }
    }
    
    /**
     * Handle delete node
     */
    handleDeleteNode() {
        if (this.editor && this.currentSelection.length > 0) {
            const count = this.currentSelection.length;
            this.editor.deleteSelectedNodes();
            this.hidePropertyPanel();
            this.showNotification(`Deleted ${count} node${count > 1 ? 's' : ''}`, 'success');
        } else {
            this.showNotification('Select a node first to delete', 'warning');
        }
    }
    
    /**
     * Handle empty node text (clear text but keep node)
     */
    handleEmptyNode() {
        if (this.editor && this.currentSelection.length > 0) {
            const nodeIds = [...this.currentSelection];
            
            nodeIds.forEach(nodeId => {
                // Find the shape element
                const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
                if (shapeElement.empty()) {
                    console.warn(`Shape not found for nodeId: ${nodeId}`);
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
            this.showNotification(`Emptied ${count} node${count > 1 ? 's' : ''}`, 'success');
            
            // Update property panel if still showing
            if (this.currentSelection.length > 0) {
                this.loadNodeProperties(this.currentSelection[0]);
            }
        } else {
            this.showNotification('Select a node first to empty', 'warning');
        }
    }
    
    /**
     * Handle auto-complete diagram with AI
     */
    async handleAutoComplete() {
        console.log('ToolbarManager: =============== AUTO-COMPLETE STARTED ===============');
        console.log('ToolbarManager: Current diagram type:', this.editor?.diagramType);
        console.log('ToolbarManager: Current spec:', this.editor?.currentSpec);
        
        // Prevent concurrent auto-complete operations
        if (this.isAutoCompleting) {
            console.log('ToolbarManager: Auto-complete already in progress, ignoring duplicate request');
            return;
        }
        
        if (!this.editor) {
            this.showNotification('Editor not initialized', 'error');
            console.error('ToolbarManager: Auto-complete failed - Editor not initialized');
            return;
        }
        
        // Set flag to prevent concurrent operations
        this.isAutoCompleting = true;
        
        // CRITICAL: Validate session before auto-complete
        if (!this.editor.validateSession('Auto-complete')) {
            // validateSession already logs the error to console
            // Don't show notification here as it creates confusion when it still works
            console.error('ToolbarManager: Session validation failed, aborting auto-complete');
            this.isAutoCompleting = false; // Clear flag on early return
            return;
        }
        
        // CRITICAL: Store the current diagram type and session ID to prevent accidental switching
        const currentDiagramType = this.editor.diagramType;
        const currentSessionId = this.editor.sessionId;
        console.log('ToolbarManager: Locked diagram type:', currentDiagramType);
        console.log('ToolbarManager: Locked session ID:', currentSessionId);
        
        // Extract existing nodes from the diagram
        const existingNodes = this.extractExistingNodes();
        console.log('ToolbarManager: Extracted nodes:', existingNodes.length);
        
        if (existingNodes.length === 0) {
            this.showNotification('Please add some nodes first before using Auto', 'warning');
            console.log('ToolbarManager: Auto-complete aborted - No nodes found');
            this.isAutoCompleting = false; // Clear flag on early return
            return;
        }
        
        // Identify the main/central topic (center-most or largest node)
        const mainTopic = this.identifyMainTopic(existingNodes);
        const diagramType = currentDiagramType; // Use locked type
        console.log('ToolbarManager: Main topic:', mainTopic);
        console.log('ToolbarManager: Diagram type:', diagramType);
        
        // Store the original topic to preserve it later
        const originalTopic = this.editor.currentSpec?.topic || mainTopic;
        console.log('Original topic to preserve:', originalTopic);
        
        // For flow maps, prioritize title for language detection
        let textForLanguageDetection = mainTopic;
        if (diagramType === 'flow_map' && this.editor.currentSpec?.title) {
            textForLanguageDetection = this.editor.currentSpec.title;
            console.log('Flow map detected - using title for language detection:', textForLanguageDetection);
        }
        
        // For bridge maps, check all existing nodes for Chinese characters (prioritize user content)
        if (diagramType === 'bridge_map' && existingNodes.length > 0) {
            // Check if any existing node has Chinese characters
            const hasChineseInNodes = existingNodes.some(node => /[\u4e00-\u9fa5]/.test(node.text));
            if (hasChineseInNodes) {
                textForLanguageDetection = existingNodes.find(node => /[\u4e00-\u9fa5]/.test(node.text)).text;
                console.log('Bridge map - Found Chinese text in nodes, using for language detection:', textForLanguageDetection);
            }
        }
        
        // For brace maps, check all existing nodes for Chinese characters (prioritize user content)
        if (diagramType === 'brace_map' && existingNodes.length > 0) {
            // Check if any existing node has Chinese characters
            const hasChineseInNodes = existingNodes.some(node => /[\u4e00-\u9fa5]/.test(node.text));
            if (hasChineseInNodes) {
                textForLanguageDetection = existingNodes.find(node => /[\u4e00-\u9fa5]/.test(node.text)).text;
                console.log('Brace map - Found Chinese text in nodes, using for language detection:', textForLanguageDetection);
            }
        }
        
        // Detect language from the topic/title text (if contains Chinese characters, use Chinese)
        const hasChinese = /[\u4e00-\u9fa5]/.test(textForLanguageDetection);
        const language = hasChinese ? 'zh' : (window.languageManager?.getCurrentLanguage() || 'en');
        console.log('Detected language from text:', language, '(hasChinese:', hasChinese, ', text:', textForLanguageDetection, ')');
        
        // Create a better prompt focused on the main topic (language-aware)
        let prompt;
        
        // For flow maps, only use the title in the prompt, not the steps/substeps
        // (to avoid LLM being influenced by default English template)
        if (diagramType === 'flow_map') {
            if (language === 'zh') {
                prompt = `为主题"${mainTopic}"创建一个完整的流程图。生成相关的主要步骤和子步骤，使其内容完整。`;
            } else {
                prompt = `Create a complete flow map about "${mainTopic}". Generate relevant steps and substeps to make it comprehensive.`;
            }
        } else if (diagramType === 'brace_map') {
            // For brace maps, only use the main topic, not the placeholder parts/subparts
            // (to avoid LLM being influenced by default template placeholders)
            if (language === 'zh') {
                prompt = `为主题"${mainTopic}"创建一个完整的括号图。生成相关的主要部分和子部分，使其内容完整。`;
            } else {
                prompt = `Create a complete brace map about "${mainTopic}". Generate relevant parts and subparts to make it comprehensive.`;
            }
        } else if (existingNodes.length === 1) {
            // Only one node - expand around it
            if (language === 'zh') {
                prompt = `为主题"${mainTopic}"创建一个完整的${diagramType}。生成相关的节点、连接和详细信息，使其内容完整。`;
            } else {
                prompt = `Create a complete ${diagramType} about "${mainTopic}". Generate relevant nodes, connections, and details to make it comprehensive.`;
            }
        } else {
            // Multiple nodes - use main topic and mention others
            const otherNodes = existingNodes
                .filter(n => n.text !== mainTopic)
                .map(n => n.text)
                .slice(0, 5); // Limit to avoid too long prompt
            
            if (otherNodes.length > 0) {
                if (language === 'zh') {
                    prompt = `以"${mainTopic}"为主题创建一个完整的${diagramType}。用户已添加：${otherNodes.join('、')}。扩展并完善图表，添加相关节点和连接。`;
                } else {
                    prompt = `Create a complete ${diagramType} with "${mainTopic}" as the main topic. User has added: ${otherNodes.join(', ')}. Expand and complete the diagram with relevant nodes and connections.`;
                }
            } else {
                if (language === 'zh') {
                    prompt = `为主题"${mainTopic}"创建一个完整的${diagramType}。生成相关的节点、连接和详细信息，使其内容完整。`;
                } else {
                    prompt = `Create a complete ${diagramType} about "${mainTopic}". Generate relevant nodes, connections, and details to make it comprehensive.`;
                }
            }
        }
        
        console.log('Auto-complete prompt:', prompt);
        console.log('Main topic identified:', mainTopic);
        console.log('Total existing nodes:', existingNodes.length);
        console.log('Language:', language);
        
        // Show loading state
        this.setAutoButtonLoading(true);
        this.showNotification(`AI is completing diagram about "${mainTopic}"...`, 'info');
        
        try {
            // Call API to generate diagram
            const response = await fetch('/api/generate_graph', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: prompt,
                    diagram_type: diagramType,
                    language: language
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Update diagram with new specification
            if (data.spec) {
                console.log('ToolbarManager: Received spec from LLM');
                console.log('ToolbarManager: Spec preview:', JSON.stringify(data.spec).substring(0, 200));
                
                // CRITICAL SAFEGUARD: Verify diagram type and session haven't changed
                if (this.editor.diagramType !== currentDiagramType) {
                    console.error('ToolbarManager: DIAGRAM TYPE MISMATCH DETECTED!');
                    console.error('ToolbarManager: Expected:', currentDiagramType);
                    console.error('ToolbarManager: Current:', this.editor.diagramType);
                    // Only show notification if there's actually a mismatch
                    this.showNotification('Diagram changed during auto-complete', 'error');
                    this.isAutoCompleting = false; // Clear flag on early return
                    return;
                }
                
                if (this.editor.sessionId !== currentSessionId) {
                    console.error('ToolbarManager: SESSION ID MISMATCH DETECTED!');
                    console.error('ToolbarManager: Expected:', currentSessionId);
                    console.error('ToolbarManager: Current:', this.editor.sessionId);
                    // Only show notification if there's actually a mismatch
                    this.showNotification('Session changed during auto-complete', 'error');
                    this.isAutoCompleting = false; // Clear flag on early return
                    return;
                }
                
                // CRITICAL: Preserve the original root topic to prevent it from being overwritten
                // For tree maps and other hierarchical diagrams, always keep the user's original topic
                // Note: Bridge maps don't have a topic field, so skip this for bridge_map
                if (diagramType !== 'bridge_map') {
                    if (originalTopic && data.spec.topic) {
                        console.log(`ToolbarManager: Preserving original topic: "${originalTopic}" (LLM generated: "${data.spec.topic}")`);
                        data.spec.topic = originalTopic;
                    } else if (originalTopic) {
                        console.warn(`ToolbarManager: Original topic exists but spec.topic is missing. Adding original topic.`);
                        data.spec.topic = originalTopic;
                    } else {
                        console.warn(`ToolbarManager: No original topic found. Using LLM generated topic: "${data.spec.topic}"`);
                    }
                }
                
                // For flow maps, preserve the title field (but replace steps/substeps with LLM output)
                if (diagramType === 'flow_map') {
                    const originalTitle = this.editor.currentSpec?.title || mainTopic;
                    if (originalTitle && data.spec.title) {
                        console.log(`ToolbarManager: Preserving original flow map title: "${originalTitle}" (LLM generated: "${data.spec.title}")`);
                        data.spec.title = originalTitle;
                    } else if (originalTitle) {
                        console.warn(`ToolbarManager: Original title exists but spec.title is missing. Adding original title.`);
                        data.spec.title = originalTitle;
                    }
                    // Note: Steps and substeps are completely replaced by LLM output
                    console.log(`ToolbarManager: Flow map - Replacing with ${data.spec.steps?.length || 0} new steps`);
                }
                
                // For brace maps, preserve the topic but replace parts/subparts with LLM output
                if (diagramType === 'brace_map') {
                    // Topic is already preserved above in the generic topic preservation
                    // Note: Parts and subparts are completely replaced by LLM output
                    console.log(`ToolbarManager: Brace map - Replacing with ${data.spec.parts?.length || 0} new parts`);
                }
                
                // For bridge maps, just use the LLM output directly (no topic preservation needed)
                if (diagramType === 'bridge_map') {
                    console.log(`ToolbarManager: Bridge map - Using ${data.spec.analogies?.length || 0} analogy pairs from LLM`);
                }
                
                console.log('ToolbarManager: Updating editor spec');
                this.editor.currentSpec = data.spec;
                console.log('ToolbarManager: Rendering updated diagram');
                this.editor.renderDiagram();
                console.log('ToolbarManager: Auto-complete completed successfully');
                this.showNotification('Diagram auto-completed successfully!', 'success');
            } else {
                throw new Error('No diagram specification returned');
            }
            
        } catch (error) {
            console.error('ToolbarManager: Auto-complete error:', error);
            console.error('ToolbarManager: Error stack:', error.stack);
            this.showNotification(`Auto-complete failed: ${error.message}`, 'error');
        } finally {
            this.setAutoButtonLoading(false);
            this.isAutoCompleting = false; // Clear flag
            console.log('ToolbarManager: =============== AUTO-COMPLETE ENDED ===============');
        }
    }
    
    /**
     * Identify the main topic from existing nodes
     * Uses diagram-specific structure first, then falls back to heuristics
     */
    identifyMainTopic(nodes) {
        if (nodes.length === 0) return '';
        if (nodes.length === 1) return nodes[0].text;
        
        const diagramType = this.editor.diagramType;
        const spec = this.editor.currentSpec;
        
        // Strategy 1: Use diagram-specific structure
        if (spec) {
            let mainTopic = null;
            
            switch (diagramType) {
                case 'bubble_map':
                    // For bubble map, the main topic is spec.topic
                    mainTopic = spec.topic;
                    break;
                    
                case 'circle_map':
                    // For circle map, the main topic is spec.topic
                    mainTopic = spec.topic;
                    break;
                    
                case 'tree_map':
                case 'mindmap':
                    // For tree/mind maps, the main topic is spec.topic
                    mainTopic = spec.topic;
                    break;
                    
                case 'brace_map':
                    // For brace map, the main topic is spec.topic
                    mainTopic = spec.topic;
                    break;
                    
                case 'double_bubble_map':
                    // For double bubble map, use the left topic as primary
                    mainTopic = spec.left || spec.right;
                    break;
                    
                case 'multi_flow_map':
                    // For multi-flow map, the main topic is spec.event
                    mainTopic = spec.event;
                    break;
                    
                case 'flow_map':
                    // For flow map, use the title or first step
                    mainTopic = spec.title || (spec.steps && spec.steps[0]);
                    break;
                    
                case 'concept_map':
                    // For concept map, the main topic is spec.topic
                    mainTopic = spec.topic;
                    break;
                    
                case 'bridge_map':
                    // For bridge map, use the relating_factor (usually "as") or first analogy
                    mainTopic = spec.relating_factor || (spec.analogies && spec.analogies[0]?.left);
                    break;
            }
            
            if (mainTopic) {
                console.log('Main topic identified from spec structure:', mainTopic);
                return mainTopic;
            }
        }
        
        // Strategy 2: Find node closest to center of canvas (geometric fallback)
        const svg = d3.select('#d3-container svg');
        if (!svg.empty()) {
            const width = parseFloat(svg.attr('width')) || 800;
            const height = parseFloat(svg.attr('height')) || 600;
            const centerX = width / 2;
            const centerY = height / 2;
            
            // Calculate distance from center for each node
            let closestNode = nodes[0];
            let minDistance = Infinity;
            
            nodes.forEach(node => {
                const distance = Math.sqrt(
                    Math.pow(node.x - centerX, 2) + 
                    Math.pow(node.y - centerY, 2)
                );
                
                if (distance < minDistance) {
                    minDistance = distance;
                    closestNode = node;
                }
            });
            
            console.log('Main topic identified by position:', closestNode.text, 'at', closestNode.x, closestNode.y);
            return closestNode.text;
        }
        
        // Strategy 3: Fallback - find first meaningful node
        const meaningfulNode = nodes.find(n => 
            n.text.length > 1 && 
            n.text !== 'New Node' && 
            !n.text.startsWith('Context') &&
            !n.text.startsWith('Attribute')
        );
        
        return meaningfulNode ? meaningfulNode.text : nodes[0].text;
    }
    
    /**
     * Extract existing nodes from the current diagram
     */
    extractExistingNodes() {
        const nodes = [];
        
        // Define placeholder/template text patterns to skip
        const placeholderPatterns = [
            /^New Node$/i,
            /^New (Left|Right|Item|Concept|Step|Substep|Category|Child|Part|Subpart|Cause|Effect|Attribute|Context)$/i,
            /^Item [A-Z0-9]+$/i,  // Item 1, Item A, Item B, etc.
            /^Item \d+$/i,        // Item 1, Item 2, Item 3, etc.
            /^as$/i,              // Bridge map relating factor default
            /^Main Topic$/i,
            /^Topic [A-Z]?$/i,
            /^主题$/,
            /^新节点$/,
            /^项目[A-Z0-9]+$/
        ];
        
        // Find all text elements in the SVG
        d3.selectAll('#d3-container text').each(function() {
            const textElement = d3.select(this);
            const text = textElement.text().trim();
            
            // Skip empty or placeholder text
            if (!text || text.length === 0) {
                return;
            }
            
            // Check if this is placeholder text
            const isPlaceholder = placeholderPatterns.some(pattern => pattern.test(text));
            if (isPlaceholder) {
                console.log(`Skipping placeholder text: "${text}"`);
                return;
            }
            
            const x = parseFloat(textElement.attr('x')) || 0;
            const y = parseFloat(textElement.attr('y')) || 0;
            
            nodes.push({
                text: text,
                x: x,
                y: y
            });
        });
        
        console.log(`Extracted ${nodes.length} real nodes (filtered out placeholders):`, nodes);
        return nodes;
    }
    
    /**
     * Toggle line mode (black and white, no fill)
     */
    toggleLineMode() {
        this.isLineMode = !this.isLineMode;
        
        // Toggle button active state
        if (this.isLineMode) {
            this.lineModeBtn.classList.add('active');
        } else {
            this.lineModeBtn.classList.remove('active');
        }
        
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            console.warn('No SVG found in container');
            return;
        }
        
        if (this.isLineMode) {
            // Apply black and white line mode
            console.log('Applying line mode: black and white');
            
            // Remove canvas background
            svg.style('background-color', 'transparent');
            
            // Select all shapes (circles, rects, ellipses, polygons, paths)
            svg.selectAll('circle, rect, ellipse, polygon, path')
                .each(function() {
                    const element = d3.select(this);
                    
                    // Store original styles as data attributes (for restoration)
                    if (!element.attr('data-original-fill')) {
                        element.attr('data-original-fill', element.style('fill') || element.attr('fill') || 'none');
                    }
                    if (!element.attr('data-original-stroke')) {
                        element.attr('data-original-stroke', element.style('stroke') || element.attr('stroke') || 'none');
                    }
                    if (!element.attr('data-original-stroke-width')) {
                        element.attr('data-original-stroke-width', element.style('stroke-width') || element.attr('stroke-width') || '1');
                    }
                    
                    // Apply line mode: no fill, black stroke
                    element
                        .style('fill', 'none')
                        .style('stroke', '#000000')
                        .style('stroke-width', '2px');
                });
            
            // Make all text black
            svg.selectAll('text')
                .each(function() {
                    const element = d3.select(this);
                    
                    // Store original text color
                    if (!element.attr('data-original-fill')) {
                        element.attr('data-original-fill', element.style('fill') || element.attr('fill') || '#000000');
                    }
                    
                    // Apply black text
                    element.style('fill', '#000000');
                });
            
            // Make all lines/connections black
            svg.selectAll('line')
                .each(function() {
                    const element = d3.select(this);
                    
                    // Store original stroke
                    if (!element.attr('data-original-stroke')) {
                        element.attr('data-original-stroke', element.style('stroke') || element.attr('stroke') || '#000000');
                    }
                    
                    // Apply black stroke
                    element.style('stroke', '#000000');
                });
            
            this.showNotification('Line mode enabled', 'success');
            
        } else {
            // Restore original colors
            console.log('Restoring original colors');
            
            // Restore canvas background (if it had one)
            svg.style('background-color', null);
            
            // Restore shapes
            svg.selectAll('circle, rect, ellipse, polygon, path')
                .each(function() {
                    const element = d3.select(this);
                    
                    const originalFill = element.attr('data-original-fill');
                    const originalStroke = element.attr('data-original-stroke');
                    const originalStrokeWidth = element.attr('data-original-stroke-width');
                    
                    if (originalFill) {
                        element.style('fill', originalFill === 'none' ? 'none' : originalFill);
                        element.attr('data-original-fill', null);
                    }
                    if (originalStroke) {
                        element.style('stroke', originalStroke === 'none' ? 'none' : originalStroke);
                        element.attr('data-original-stroke', null);
                    }
                    if (originalStrokeWidth) {
                        element.style('stroke-width', originalStrokeWidth);
                        element.attr('data-original-stroke-width', null);
                    }
                });
            
            // Restore text colors
            svg.selectAll('text')
                .each(function() {
                    const element = d3.select(this);
                    const originalFill = element.attr('data-original-fill');
                    
                    if (originalFill) {
                        element.style('fill', originalFill);
                        element.attr('data-original-fill', null);
                    }
                });
            
            // Restore line colors
            svg.selectAll('line')
                .each(function() {
                    const element = d3.select(this);
                    const originalStroke = element.attr('data-original-stroke');
                    
                    if (originalStroke) {
                        element.style('stroke', originalStroke);
                        element.attr('data-original-stroke', null);
                    }
                });
            
            this.showNotification('Line mode disabled', 'success');
        }
    }
    
    /**
     * Set loading state for auto button
     */
    setAutoButtonLoading(isLoading) {
        if (!this.autoCompleteBtn) return;
        
        if (isLoading) {
            this.autoCompleteBtn.classList.add('loading');
            this.autoCompleteBtn.disabled = true;
        } else {
            this.autoCompleteBtn.classList.remove('loading');
            this.autoCompleteBtn.disabled = false;
        }
    }
    
    /**
     * Handle duplicate node
     */
    handleDuplicateNode() {
        console.log('Duplicate node clicked');
        this.showNotification('Duplicate node feature coming soon!');
    }
    
    /**
     * Handle undo
     */
    handleUndo() {
        if (this.editor) {
            this.editor.undo();
        }
    }
    
    /**
     * Handle redo
     */
    handleRedo() {
        if (this.editor) {
            this.editor.redo();
        }
    }
    
    /**
     * Reset canvas to blank template
     */
    handleReset() {
        if (!this.editor) return;
        
        // Confirm with user
        const confirmed = confirm('Are you sure you want to reset the canvas to a blank template? All current changes will be lost.');
        if (!confirmed) return;
        
        console.log('Resetting canvas to blank template');
        
        // Get the diagram selector to retrieve blank template
        const diagramSelector = window.diagramSelector;
        if (!diagramSelector) {
            console.error('Diagram selector not available');
            this.showNotification('Failed to reset: diagram selector not found', 'error');
            return;
        }
        
        // Get blank template for current diagram type
        const blankTemplate = diagramSelector.getTemplate(this.editor.diagramType);
        if (!blankTemplate) {
            console.error('Failed to get blank template for:', this.editor.diagramType);
            this.showNotification('Failed to reset: template not found', 'error');
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
        
        this.showNotification('Canvas reset to blank template', 'success');
    }
    
    /**
     * Handle export - Export diagram as PNG
     */
    handleExport() {
        const svg = document.querySelector('#d3-container svg');
        if (!svg) {
            this.showNotification('No diagram to export!', 'error');
            return;
        }
        
        try {
            // Temporarily show watermarks for export
            const watermarks = svg.querySelectorAll('.watermark');
            watermarks.forEach(wm => wm.style.display = 'block');
            
            // Get SVG dimensions
            const svgRect = svg.getBoundingClientRect();
            const width = parseFloat(svg.getAttribute('width')) || svgRect.width;
            const height = parseFloat(svg.getAttribute('height')) || svgRect.height;
            
            // Create canvas
            const canvas = document.createElement('canvas');
            const scale = 2; // Higher resolution
            canvas.width = width * scale;
            canvas.height = height * scale;
            const ctx = canvas.getContext('2d');
            
            // Scale context for higher resolution
            ctx.scale(scale, scale);
            
            // Fill white background
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, width, height);
            
            // Serialize SVG
            const svgData = new XMLSerializer().serializeToString(svg);
            const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(svgBlob);
            
            // Create image from SVG
            const img = new Image();
            img.onload = () => {
                // Draw image to canvas
                ctx.drawImage(img, 0, 0, width, height);
                
                // Convert canvas to PNG
                canvas.toBlob((blob) => {
                    const pngUrl = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = pngUrl;
                    link.download = `mindgraph-${Date.now()}.png`;
                    link.click();
                    
                    // Cleanup
                    URL.revokeObjectURL(pngUrl);
                    URL.revokeObjectURL(url);
                    
                    // Hide watermarks again after export
                    watermarks.forEach(wm => wm.style.display = 'none');
                    
                    this.showNotification('Diagram exported as PNG!', 'success');
                }, 'image/png');
            };
            
            img.onerror = (error) => {
                console.error('Error loading SVG:', error);
                URL.revokeObjectURL(url);
                
                // Hide watermarks on error
                watermarks.forEach(wm => wm.style.display = 'none');
                
                this.showNotification('Failed to export diagram', 'error');
            };
            
            img.src = url;
            
        } catch (error) {
            console.error('Error exporting diagram:', error);
            this.showNotification('Failed to export diagram', 'error');
        }
    }
    
    /**
     * Handle back to gallery
     */
    handleBackToGallery() {
        // Clean up canvas and editor first
        this.cleanupCanvas();
        
        // Hide and clear property panel
        this.hidePropertyPanel();
        this.clearPropertyPanel();
        
        // Close AI assistant if open and reset button state
        const aiPanel = document.getElementById('ai-assistant-panel');
        if (aiPanel && !aiPanel.classList.contains('collapsed')) {
            aiPanel.classList.add('collapsed');
        }
        const mindmateBtn = document.getElementById('mindmate-ai-btn');
        if (mindmateBtn) {
            mindmateBtn.classList.remove('active');
        }
        
        // Hide editor interface
        const editorInterface = document.getElementById('editor-interface');
        if (editorInterface) {
            editorInterface.style.display = 'none';
        }
        
        // Show landing page
        const landing = document.getElementById('editor-landing');
        if (landing) {
            landing.style.display = 'block';
        }
        
        console.log('Returned to gallery - canvas cleaned');
    }
    
    /**
     * Clean up canvas and previous editor
     */
    cleanupCanvas() {
        // Clear the D3 container
        const container = document.getElementById('d3-container');
        if (container) {
            // Remove all SVG elements
            d3.select('#d3-container').selectAll('*').remove();
            console.log('Canvas cleared');
        }
        
        // Clear any existing editor instance
        if (window.currentEditor) {
            window.currentEditor = null;
        }
        
        // Reset selection state
        this.currentSelection = [];
        if (this.editor && this.editor.selectedNodes) {
            this.editor.selectedNodes.clear();
        }
    }
    
    /**
     * Show notification using centralized notification manager
     */
    showNotification(message, type = 'info') {
        console.log(`ToolbarManager: showNotification called - "${message}" [${type}]`);
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        } else {
            console.error('NotificationManager not available');
        }
    }
    
    /**
     * Validate that this toolbar manager is still valid for the current session
     */
    validateToolbarSession(operation = 'Operation') {
        // Check if we have a session ID
        if (!this.sessionId) {
            console.warn(`ToolbarManager: ${operation} - No session ID set`);
            return false;
        }
        
        // Check if the editor's session matches our session
        if (this.editor && this.editor.sessionId !== this.sessionId) {
            console.warn(`ToolbarManager: ${operation} blocked - Session mismatch`);
            console.warn('  Toolbar session:', this.sessionId?.substr(-8));
            console.warn('  Editor session:', this.editor.sessionId?.substr(-8));
            return false;
        }
        
        // Check with DiagramSelector's session
        if (window.diagramSelector?.currentSession) {
            if (window.diagramSelector.currentSession.id !== this.sessionId) {
                console.warn(`ToolbarManager: ${operation} blocked - DiagramSelector session mismatch`);
                console.warn('  Toolbar session:', this.sessionId?.substr(-8));
                console.warn('  Active session:', window.diagramSelector.currentSession.id?.substr(-8));
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Cleanup and remove all event listeners by cloning and replacing elements
     */
    destroy() {
        console.log('ToolbarManager: Destroying instance for session:', this.sessionId?.substr(-8));
        
        // Clone and replace buttons to remove all event listeners
        // This is the most reliable way to remove event listeners added with arrow functions
        const buttonsToClean = [
            'add-node-btn', 'delete-node-btn', 'empty-node-btn', 'auto-complete-btn',
            'line-mode-btn', 'undo-btn', 'redo-btn', 'reset-btn', 'export-btn',
            'back-to-gallery', 'close-properties', 'prop-text-apply', 'prop-bold',
            'prop-italic', 'prop-underline', 'apply-all-properties'
        ];
        
        buttonsToClean.forEach(btnId => {
            const btn = document.getElementById(btnId);
            if (btn && btn.parentNode) {
                const clone = btn.cloneNode(true);
                btn.parentNode.replaceChild(clone, btn);
            }
        });
        
        // Unregister from global registry
        if (window.toolbarManagerRegistry) {
            window.toolbarManagerRegistry.delete(this.sessionId);
            console.log('ToolbarManager: Unregistered from registry');
        }
        
        // Clear all references
        this.editor = null;
        this.currentSelection = [];
        this.sessionId = null;
        this.diagramType = null;
        
        console.log('ToolbarManager: Destruction complete');
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.ToolbarManager = ToolbarManager;
}

