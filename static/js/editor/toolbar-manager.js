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
        this.initializeElements();
        this.attachEventListeners();
        this.listenToSelectionChanges();
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
        // Toolbar buttons
        this.addNodeBtn?.addEventListener('click', () => this.handleAddNode());
        this.deleteNodeBtn?.addEventListener('click', () => this.handleDeleteNode());
        this.autoCompleteBtn?.addEventListener('click', () => this.handleAutoComplete());
        this.lineModeBtn?.addEventListener('click', () => this.toggleLineMode());
        this.duplicateNodeBtn?.addEventListener('click', () => this.handleDuplicateNode());
        this.emptyNodeBtn?.addEventListener('click', () => this.handleEmptyNode());
        this.undoBtn?.addEventListener('click', () => this.handleUndo());
        this.redoBtn?.addEventListener('click', () => this.handleRedo());
        this.resetBtn?.addEventListener('click', () => this.handleReset());
        this.exportBtn?.addEventListener('click', () => this.handleExport());
        this.backBtn?.addEventListener('click', () => this.handleBackToGallery());
        
        // Property panel
        this.closePropBtn?.addEventListener('click', () => this.hidePropertyPanel());
        
        // Property inputs
        this.propTextApply?.addEventListener('click', () => this.applyText());
        this.propBold?.addEventListener('click', () => this.toggleBold());
        this.propItalic?.addEventListener('click', () => this.toggleItalic());
        this.propUnderline?.addEventListener('click', () => this.toggleUnderline());
        this.applyAllBtn?.addEventListener('click', () => this.applyAllProperties());
        
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
            
            // Show/hide property panel
            if (hasSelection && this.currentSelection.length > 0) {
                this.showPropertyPanel();
                this.loadNodeProperties(this.currentSelection[0]);
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
    applyText() {
        if (this.currentSelection.length === 0) return;
        
        const newText = this.propText.value.trim();
        if (!newText) {
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
        
        this.showNotification('Text updated successfully', 'success');
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
        
        console.log('Applying all properties:', properties);
        
        // Apply text changes first using the proper method
        if (properties.text && properties.text.trim()) {
            this.applyText();
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
        console.log('Add node clicked');
        if (this.editor) {
            this.editor.addNode();
            this.showNotification('Node added! Double-click to edit text.', 'success');
        } else {
            this.showNotification('Editor not initialized', 'error');
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
        console.log('Auto-complete clicked');
        
        if (!this.editor) {
            this.showNotification('Editor not initialized', 'error');
            return;
        }
        
        // Extract existing nodes from the diagram
        const existingNodes = this.extractExistingNodes();
        
        if (existingNodes.length === 0) {
            this.showNotification('Please add some nodes first before using Auto', 'warning');
            return;
        }
        
        // Identify the main/central topic (center-most or largest node)
        const mainTopic = this.identifyMainTopic(existingNodes);
        const diagramType = this.editor.diagramType;
        
        // Create a better prompt focused on the main topic
        let prompt;
        if (existingNodes.length === 1) {
            // Only one node - expand around it
            prompt = `Create a complete ${diagramType} about "${mainTopic}". Generate relevant nodes, connections, and details to make it comprehensive.`;
        } else {
            // Multiple nodes - use main topic and mention others
            const otherNodes = existingNodes
                .filter(n => n.text !== mainTopic)
                .map(n => n.text)
                .slice(0, 5); // Limit to avoid too long prompt
            
            if (otherNodes.length > 0) {
                prompt = `Create a complete ${diagramType} with "${mainTopic}" as the main topic. User has added: ${otherNodes.join(', ')}. Expand and complete the diagram with relevant nodes and connections.`;
            } else {
                prompt = `Create a complete ${diagramType} about "${mainTopic}". Generate relevant nodes, connections, and details to make it comprehensive.`;
            }
        }
        
        console.log('Auto-complete prompt:', prompt);
        console.log('Main topic identified:', mainTopic);
        console.log('Total existing nodes:', existingNodes.length);
        
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
                    diagram_type: diagramType
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
                this.editor.currentSpec = data.spec;
                this.editor.renderDiagram();
                this.showNotification('Diagram auto-completed successfully!', 'success');
            } else {
                throw new Error('No diagram specification returned');
            }
            
        } catch (error) {
            console.error('Auto-complete error:', error);
            this.showNotification(`Auto-complete failed: ${error.message}`, 'error');
        } finally {
            this.setAutoButtonLoading(false);
        }
    }
    
    /**
     * Identify the main topic from existing nodes
     * Uses heuristics: center position, font size, or first meaningful node
     */
    identifyMainTopic(nodes) {
        if (nodes.length === 0) return '';
        if (nodes.length === 1) return nodes[0].text;
        
        // Strategy 1: Find node closest to center of canvas
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
        
        // Fallback: Return first node with meaningful content
        const meaningfulNode = nodes.find(n => 
            n.text.length > 1 && 
            n.text !== 'New Node' && 
            !n.text.startsWith('Context')
        );
        
        return meaningfulNode ? meaningfulNode.text : nodes[0].text;
    }
    
    /**
     * Extract existing nodes from the current diagram
     */
    extractExistingNodes() {
        const nodes = [];
        
        // Find all text elements in the SVG
        d3.selectAll('#d3-container text').each(function() {
            const textElement = d3.select(this);
            const text = textElement.text().trim();
            
            // Skip empty or very short text
            if (text && text.length > 0 && text !== 'New Node') {
                const x = parseFloat(textElement.attr('x')) || 0;
                const y = parseFloat(textElement.attr('y')) || 0;
                
                nodes.push({
                    text: text,
                    x: x,
                    y: y
                });
            }
        });
        
        console.log(`Extracted ${nodes.length} existing nodes:`, nodes);
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
        
        // Hide property panel
        this.hidePropertyPanel();
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.style.position = 'fixed';
        notification.style.top = '80px';
        notification.style.right = '20px';
        notification.style.padding = '14px 24px';
        notification.style.borderRadius = '12px';
        notification.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.15)';
        notification.style.zIndex = '10001';
        notification.style.fontSize = '14px';
        notification.style.fontWeight = '600';
        notification.style.display = 'flex';
        notification.style.alignItems = 'center';
        notification.style.gap = '10px';
        notification.style.animation = 'slideInRight 0.3s ease';
        notification.style.minWidth = '250px';
        
        // Add animation keyframes if not exists
        if (!document.getElementById('notification-animations')) {
            const style = document.createElement('style');
            style.id = 'notification-animations';
            style.textContent = `
                @keyframes slideInRight {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Set colors based on type
        const styles = {
            success: {
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                icon: '✓'
            },
            error: {
                background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                icon: '✕'
            },
            info: {
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                icon: 'ℹ'
            },
            warning: {
                background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                icon: '⚠'
            }
        };
        
        const currentStyle = styles[type] || styles.info;
        notification.style.background = currentStyle.background;
        notification.style.color = 'white';
        
        // Add icon
        const icon = document.createElement('span');
        icon.style.fontSize = '18px';
        icon.style.fontWeight = 'bold';
        icon.textContent = currentStyle.icon;
        notification.appendChild(icon);
        
        // Add message
        const messageSpan = document.createElement('span');
        messageSpan.textContent = message;
        notification.appendChild(messageSpan);
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.transition = 'all 0.3s ease';
            notification.style.transform = 'translateX(400px)';
            notification.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.ToolbarManager = ToolbarManager;
}

