/**
 * Property Panel Manager
 * ======================
 * 
 * Manages property panel UI for node styling and editing.
 * Handles color pickers, font styling, and property updates.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class PropertyPanelManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Owner ID for Event Bus Listener Registry
        this.ownerId = 'PropertyPanelManager';
        
        // Property panel elements
        this.panel = null;
        this.propText = null;
        this.propFontSize = null;
        this.propFontFamily = null;
        this.propTextColor = null;
        this.propFillColor = null;
        this.propStrokeColor = null;
        this.propStrokeWidth = null;
        this.propOpacity = null;
        this.propBold = null;
        this.propItalic = null;
        this.propUnderline = null;
        this.propStrikethrough = null;
        
        // Color button previews
        this.previewTextColor = null;
        this.previewFillColor = null;
        this.previewStrokeColor = null;
        
        // Current selection
        this.currentNodeId = null;
        
        // Initialize
        this.initializeElements();
        this.attachEventListeners();
        this.subscribeToEvents();
        
        this.logger.info('PropertyPanelManager', 'Property Panel Manager initialized');
    }
    
    /**
     * Initialize DOM elements
     */
    initializeElements() {
        this.panel = document.getElementById('property-panel');
        this.propText = document.getElementById('prop-text');
        this.propFontSize = document.getElementById('prop-font-size');
        this.propFontFamily = document.getElementById('prop-font-family');
        this.propTextColor = document.getElementById('prop-text-color');
        this.propFillColor = document.getElementById('prop-fill-color');
        this.propStrokeColor = document.getElementById('prop-stroke-color');
        this.propStrokeWidth = document.getElementById('prop-stroke-width');
        this.propOpacity = document.getElementById('prop-opacity');
        this.propBold = document.getElementById('prop-bold');
        this.propItalic = document.getElementById('prop-italic');
        this.propUnderline = document.getElementById('prop-underline');
        this.propStrikethrough = document.getElementById('prop-strikethrough');
        
        // Color button previews
        this.previewTextColor = document.getElementById('preview-text-color');
        this.previewFillColor = document.getElementById('preview-fill-color');
        this.previewStrokeColor = document.getElementById('preview-stroke-color');
        
        if (!this.panel) {
            this.logger.warn('PropertyPanelManager', 'Property panel element not found');
        }
    }
    
    /**
     * Auto-resize textarea based on content
     * @param {HTMLTextAreaElement} textarea - Textarea element to resize
     */
    autoResizeTextarea(textarea) {
        if (!textarea || textarea.tagName !== 'TEXTAREA') return;
        
        // Debounce: skip if already resizing (toolbar-manager.js handles it)
        if (textarea._isResizing) return;
        textarea._isResizing = true;
        
        const minHeight = 60; // Minimum height in pixels
        const maxHeight = 300; // Maximum height in pixels
        
        // Save current scroll position to prevent jump
        const scrollTop = textarea.scrollTop;
        
        // Temporarily set height to 0 to get accurate scrollHeight
        textarea.style.height = '0px';
        
        // Get the actual content height needed
        const contentHeight = textarea.scrollHeight;
        
        // Calculate new height with constraints
        const newHeight = Math.min(Math.max(contentHeight, minHeight), maxHeight);
        
        // Set the new height
        textarea.style.height = `${newHeight}px`;
        textarea.style.overflowY = contentHeight > maxHeight ? 'auto' : 'hidden';
        
        // Restore scroll position
        textarea.scrollTop = scrollTop;
        
        // Clear the resizing flag after a short delay
        requestAnimationFrame(() => {
            textarea._isResizing = false;
        });
    }
    
    /**
     * Attach event listeners to property panel controls
     */
    attachEventListeners() {
        if (!this.panel) return;
        
        // NOTE: Ctrl+Enter handling is done in toolbar-manager.js
        // Only attach input listener here for auto-resize
        if (this.propText && this.propText.tagName === 'TEXTAREA') {
            this.propText.addEventListener('input', (e) => {
                this.autoResizeTextarea(e.target);
            });
            
            // Setup Tab Mode autocomplete if enabled
            if (window.currentEditor?.modules?.tabMode && this.currentNodeId) {
                window.currentEditor.modules.tabMode.setupAutocomplete(
                    this.propText,
                    this.currentNodeId,
                    window.currentEditor?.diagramType
                );
            }
        }
        
        // TODO: Extract event listener setup from toolbar-manager.js - Day 5
        // This includes:
        // - Color picker sync (hex <-> color input)
        // - Font style toggles (bold, italic, underline)
        // - Stroke width/opacity sliders
        // - Apply button
        // - Real-time property updates
        
        this.logger.debug('PropertyPanelManager', 'Event listeners attached');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for node selection
        this.eventBus.onWithOwner('selection:changed', (data) => {
            if (data.selectedNodes.length === 1) {
                this.loadNodeProperties(data.selectedNodes[0]);
                // Auto-open panel if requested (not in assistant mode)
                if (data.shouldAutoOpenPanel) {
                    this.openPanel(data.nodeId);
                }
            } else {
                this.clearPanel();
            }
        }, this.ownerId);
        
        // Listen for selection cleared
        this.eventBus.onWithOwner('selection:cleared', (data) => {
            if (data.shouldHidePanel) {
                this.closePanel();
            }
            this.clearPanel();
        }, this.ownerId);
        
        // Listen for property panel open requests
        this.eventBus.onWithOwner('property_panel:open_requested', (data) => {
            this.openPanel(data.nodeId);
        }, this.ownerId);
        
        // Listen for property panel close requests
        this.eventBus.onWithOwner('property_panel:close_requested', () => {
            this.closePanel();
        }, this.ownerId);
        
        // Listen for property panel clear requests
        this.eventBus.onWithOwner('property_panel:clear_requested', () => {
            this.clearPanel();
        }, this.ownerId);
        
        // Listen for property change requests
        this.eventBus.onWithOwner('property_panel:update_requested', (data) => {
            this.updateNodeProperties(data.nodeId, data.properties);
        }, this.ownerId);
        
        this.logger.debug('PropertyPanelManager', 'Subscribed to events with owner tracking');
    }
    
    /**
     * Open property panel
     * @param {string} nodeId - Node ID
     */
    openPanel(nodeId = null) {
        if (!this.panel) return;
        
        this.logger.debug('PropertyPanelManager', 'Opening property panel', { nodeId });
        
        // Mobile: Lock body scroll to prevent page shift
        if (window.innerWidth <= 768) {
            document.body.style.overflow = 'hidden';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
            document.body.style.top = `-${window.scrollY}px`;
        }
        
        // Use centralized panel manager
        if (window.panelManager) {
            window.panelManager.openPanel('property');
        } else {
            // Fallback
            this.panel.style.display = 'block';
        }
        
        // Load node properties if nodeId provided
        if (nodeId) {
            this.loadNodeProperties(nodeId);
        }
        
        // Emit opened event
        this.eventBus.emit('property_panel:opened', { nodeId });
    }
    
    /**
     * Close property panel
     */
    closePanel() {
        if (!this.panel) return;
        
        this.logger.debug('PropertyPanelManager', 'Closing property panel');
        
        // Mobile: Unlock body scroll
        if (window.innerWidth <= 768) {
            const scrollY = document.body.style.top;
            document.body.style.overflow = '';
            document.body.style.position = '';
            document.body.style.width = '';
            document.body.style.top = '';
            window.scrollTo(0, parseInt(scrollY || '0') * -1);
        }
        
        // Use centralized panel manager
        if (window.panelManager) {
            window.panelManager.closePanel('property');
        } else {
            // Fallback
            this.panel.style.display = 'none';
        }
        
        // Clear current selection
        this.currentNodeId = null;
        
        // Emit closed event
        this.eventBus.emit('property_panel:closed', {});
    }
    
    /**
     * Load properties from selected node
     * @param {string} nodeId - Node ID
     */
    loadNodeProperties(nodeId) {
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        
        if (nodeElement.empty()) {
            this.logger.warn('PropertyPanelManager', 'Node element not found', { nodeId });
            return;
        }
        
        this.currentNodeId = nodeId;
        
        // Setup Tab Mode autocomplete for property panel text input
        if (this.propText && window.currentEditor?.modules?.tabMode) {
            window.currentEditor.modules.tabMode.setupAutocomplete(
                this.propText,
                nodeId,
                window.currentEditor?.diagramType
            );
        }
        
        // Get node attributes (current values)
        const fill = nodeElement.attr('fill') || '#2196f3';
        const stroke = nodeElement.attr('stroke') || '#1976d2';
        const strokeWidth = nodeElement.attr('stroke-width') || '2';
        // Use explicit null check to preserve opacity 0 (fully transparent)
        const opacityAttr = nodeElement.attr('opacity');
        const opacity = (opacityAttr !== null && opacityAttr !== undefined) ? opacityAttr : '1';
        
        // Get text element - try multiple methods to find it
        let textElement = null;
        let text = '';
        
        // Check if this is a dimension node - special handling needed
        const nodeType = nodeElement.attr('data-node-type');
        if (nodeType === 'dimension') {
            // For dimension nodes, get the actual value from data-dimension-value attribute
            const dimensionValue = nodeElement.attr('data-dimension-value') || '';
            text = dimensionValue;
            
            // Still find the text element for styling attributes
            textElement = d3.select(`[data-text-for="${nodeId}"]`);
            if (textElement.empty()) {
                textElement = nodeElement.select('text');
            }
        } else {
            // Regular node handling - get display text
            // Method 1: Try finding text elements by data-node-id (for multi-line text)
            let textElements = d3.selectAll(`text[data-node-id="${nodeId}"]`);
            if (!textElements.empty()) {
                textElement = d3.select(textElements.node()); // Get first for attributes
                // Use extractTextFromSVG to handle multi-line text
                text = (typeof window.extractTextFromSVG === 'function') 
                    ? window.extractTextFromSVG(textElement) 
                    : (textElement.text() || '');
            } else {
                // Method 2: Try as child
                textElement = nodeElement.select('text');
                if (!textElement.empty()) {
                    text = (typeof window.extractTextFromSVG === 'function') 
                        ? window.extractTextFromSVG(textElement) 
                        : (textElement.text() || '');
                } else {
                    // Method 3: Try data-text-for attribute
                    textElement = d3.select(`[data-text-for="${nodeId}"]`);
                    if (!textElement.empty()) {
                        text = (typeof window.extractTextFromSVG === 'function') 
                            ? window.extractTextFromSVG(textElement) 
                            : (textElement.text() || '');
                    } else {
                        // Method 4: Try next sibling
                        const shapeNode = nodeElement.node();
                        if (shapeNode && shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                            textElement = d3.select(shapeNode.nextElementSibling);
                            text = (typeof window.extractTextFromSVG === 'function') 
                                ? window.extractTextFromSVG(textElement) 
                                : (textElement.text() || '');
                        }
                    }
                }
            }
        }
        
        // Get text attributes (with fallbacks if text element not found)
        const fontSize = textElement && !textElement.empty() ? (textElement.attr('font-size') || '14') : '14';
        const fontFamily = textElement && !textElement.empty() ? (textElement.attr('font-family') || "Inter, sans-serif") : "Inter, sans-serif";
        const textColor = textElement && !textElement.empty() ? (textElement.attr('fill') || '#000000') : '#000000';
        const fontWeight = textElement && !textElement.empty() ? (textElement.attr('font-weight') || 'normal') : 'normal';
        const fontStyle = textElement && !textElement.empty() ? (textElement.attr('font-style') || 'normal') : 'normal';
        const textDecoration = textElement && !textElement.empty() ? (textElement.attr('text-decoration') || 'none') : 'none';
        
        // Expand shorthand hex codes for color inputs
        const expandedFill = this.expandHexColor(fill);
        const expandedStroke = this.expandHexColor(stroke);
        const expandedTextColor = this.expandHexColor(textColor);
        
        // Check if text is a default placeholder
        const isPlaceholder = (nodeType === 'dimension') ? false : this.isDefaultPlaceholder(text);
        
        // Update property inputs
        if (this.propText) {
            if (isPlaceholder) {
                // Set as placeholder attribute (grey text that disappears on type)
                this.propText.value = '';
                this.propText.placeholder = text;
            } else {
                // Set as actual value
                this.propText.value = text;
                this.propText.placeholder = window.languageManager?.translate('nodeTextPlaceholder') || 'Node text';
            }
            // Auto-resize textarea after setting value
            if (this.propText.tagName === 'TEXTAREA') {
                this.autoResizeTextarea(this.propText);
            }
        }
        if (this.propFontSize) this.propFontSize.value = parseInt(fontSize);
        if (this.propFontFamily) this.propFontFamily.value = fontFamily;
        if (this.propTextColor) this.propTextColor.value = expandedTextColor;
        if (this.propFillColor) this.propFillColor.value = expandedFill;
        if (this.propStrokeColor) this.propStrokeColor.value = expandedStroke;
        if (this.propStrokeWidth) this.propStrokeWidth.value = parseFloat(strokeWidth);
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = `${strokeWidth}px`;
        if (this.propOpacity) this.propOpacity.value = parseFloat(opacity);
        if (this.opacityValue) this.opacityValue.textContent = `${Math.round(parseFloat(opacity) * 100)}%`;
        
        // Update color button previews
        this.updateColorPreviews();
        
        // Update toggle buttons
        if (this.propBold) {
            this.propBold.classList.toggle('active', fontWeight === 'bold');
        }
        if (this.propItalic) {
            this.propItalic.classList.toggle('active', fontStyle === 'italic');
        }
        if (this.propUnderline) {
            // textDecoration can contain multiple values like 'underline line-through'
            this.propUnderline.classList.toggle('active', textDecoration.includes('underline'));
        }
        if (this.propStrikethrough) {
            this.propStrikethrough.classList.toggle('active', textDecoration.includes('line-through'));
        }
        
        this.logger.debug('PropertyPanelManager', 'Loaded node properties', {
            nodeId,
            nodeType,
            isPlaceholder,
            textLength: text.length
        });
    }
    
    /**
     * Update node properties
     * @param {string} nodeId - Node ID
     * @param {Object} properties - Properties to update
     */
    updateNodeProperties(nodeId, properties) {
        if (!nodeId || !properties) return;
        
        this.logger.debug('PropertyPanelManager', 'Updating node properties', {
            nodeId,
            properties
        });
        
        // TODO: Extract from toolbar-manager.js - Day 5
        // This includes:
        // - Apply colors (fill, stroke, text)
        // - Apply font properties
        // - Apply opacity and stroke width
        // - Update D3 elements
        // - Trigger re-render if needed
        
        // Emit property changed event
        this.eventBus.emit('property_panel:changed', {
            nodeId,
            properties
        });
    }
    
    /**
     * Clear property panel inputs
     */
    clearPanel() {
        if (!this.panel) return;
        
        // Reset to default values
        if (this.propText) this.propText.value = '';
        if (this.propFontSize) this.propFontSize.value = 14;
        if (this.propFontFamily) this.propFontFamily.value = "Inter, sans-serif";
        if (this.propTextColor) this.propTextColor.value = '#000000';
        if (this.propFillColor) this.propFillColor.value = '#2196f3';
        if (this.propStrokeColor) this.propStrokeColor.value = '#1976d2';
        if (this.propStrokeWidth) this.propStrokeWidth.value = 2;
        if (this.propOpacity) this.propOpacity.value = 1;
        
        // Reset toggle buttons
        if (this.propBold) this.propBold.classList.remove('active');
        if (this.propItalic) this.propItalic.classList.remove('active');
        if (this.propUnderline) this.propUnderline.classList.remove('active');
        if (this.propStrikethrough) this.propStrikethrough.classList.remove('active');
        
        // Update color button previews
        this.updateColorPreviews();
        
        this.currentNodeId = null;
        
        this.logger.debug('PropertyPanelManager', 'Property panel cleared');
    }
    
    /**
     * Update color preview bars on buttons
     */
    updateColorPreviews() {
        if (this.previewTextColor && this.propTextColor) {
            this.previewTextColor.style.backgroundColor = this.propTextColor.value;
        }
        if (this.previewFillColor && this.propFillColor) {
            this.previewFillColor.style.backgroundColor = this.propFillColor.value;
        }
        if (this.previewStrokeColor && this.propStrokeColor) {
            this.previewStrokeColor.style.backgroundColor = this.propStrokeColor.value;
        }
    }
    
    /**
     * Check if text is a default placeholder using smart pattern matching
     * This covers ALL template variations without hardcoding every possible combination
     * @param {string} text - Text to check
     * @returns {boolean} Whether text is placeholder
     */
    isDefaultPlaceholder(text) {
        const trimmedText = text.trim();
        
        // === English Patterns ===
        const englishPatterns = [
            // "New X" patterns
            /^New (Attribute|Step|Cause|Effect|Branch|Node|Item|Category|Subitem|Concept|Context|Similarity|Part|Subpart|Left|Right)$/,
            // "X Difference" patterns (including alphanumeric like "Difference A1")
            /^(Left|Right) Difference$/,
            /^Difference [A-Z]\d+$/,
            // Topic variations
            /^(Main|Central|Root) Topic$/,
            /^Main (Concept|Event|Idea)$/,
            /^Topic [A-Z]$/,
            // Numbered patterns: "Context 1", "Attribute 5", etc.
            /^(Context|Attribute|Similarity|Cause|Effect|Item|Step|Part|Concept|Branch|Category) \d+$/,
            // Lettered patterns: "Item A", "Item B", etc.
            /^Item [A-Z]$/,
            // Hierarchical patterns: "Substep 1.1", "Subpart 2.3", "Sub-item 4.1", "Child 3.2", "Item 1.1"
            /^(Substep|Subpart|Sub-item|Child|Item) \d+\.\d+$/,
            // Flow/Process
            /^(Process Flow|Title)$/,
            // Bridge Map relating factor
            /^as$/,
            // Concept Map relationship labels (edge text)
            /^(relates to|includes|leads to)$/
        ];
        
        // === Chinese Patterns ===
        const chinesePatterns = [
            // "新X" patterns
            /^新(属性|步骤|原因|结果|分支|节点|项目|类别|子项|概念|联想|相似点|部分|子部分|左项|右项|事物[AB])$/,
            // "X不同点" patterns (including alphanumeric like "不同点A1")
            /^(左|右)不同点$/,
            /^不同点[A-Z]\d+$/,
            // Topic variations
            /^(主题|中心主题|主要概念|根主题|事件|核心概念)$/,
            /^主题[A-Z]$/,
            // Numbered patterns: "联想1", "属性5", etc.
            /^(联想|属性|相似点|原因|结果|步骤|部分|概念|分支|类别)\d+$/,
            // Bridge Map paired patterns: "事物A1", "事物B1", etc.
            /^事物[A-Z]\d+$/,
            // Hierarchical patterns: "子步骤1.1", "子部分2.3", "子项4.1", "子节点3.2", "项目1.1"
            /^(子步骤|子部分|子项|子节点|项目)\d+\.\d+$/,
            // Flow/Process
            /^(事件流程|标题)$/,
            // Bridge Map relating factor
            /^如同$/,
            // Concept Map relationship labels (edge text)
            /^(关联|包含|导致)$/
        ];
        
        // Test against all patterns
        const allPatterns = [...englishPatterns, ...chinesePatterns];
        return allPatterns.some(pattern => pattern.test(trimmedText));
    }
    
    /**
     * Expand shorthand hex color codes
     * @param {string} hex - Hex color code
     * @returns {string} Expanded hex code
     */
    expandHexColor(hex) {
        if (!hex || !hex.startsWith('#')) return hex;
        
        // If it's a 3-digit hex code, expand it to 6 digits
        if (hex.length === 4) {
            return '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3];
        }
        
        return hex;
    }
    
    /**
     * Destroy property panel manager
     */
    destroy() {
        this.logger.info('PropertyPanelManager', 'Destroying Property Panel Manager');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('PropertyPanelManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        this.clearPanel();
        this.closePanel();
    }
}

// Make available globally
window.PropertyPanelManager = PropertyPanelManager;

