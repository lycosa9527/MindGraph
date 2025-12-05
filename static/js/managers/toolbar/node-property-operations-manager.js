/**
 * Node & Property Operations Manager
 * ===================================
 * 
 * Handles property panel operations and basic node operations (add, delete, empty).
 * Manages style applications, resets, and template defaults.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class NodePropertyOperationsManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager; // Need access to UI elements and notifications
        
        // Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'NodePropertyOperationsManager';
        
        // Helper function to normalize color values (expand shorthand hex, ensure valid format)
        this.normalizeColor = (color) => {
            if (!color) return color;
            const colorStr = String(color).trim();
            // If it's a hex color, expand shorthand (e.g., #fff -> #ffffff)
            if (colorStr.startsWith('#')) {
                if (colorStr.length === 4) {
                    // Expand 3-digit hex to 6-digit
                    return '#' + colorStr[1] + colorStr[1] + colorStr[2] + colorStr[2] + colorStr[3] + colorStr[3];
                }
                return colorStr;
            }
            // Return as-is for named colors or rgb() values
            return colorStr;
        };
        
        // Storage for preserved dimensions (survives re-render)
        this.preservedDimensions = new Map();
        
        // Store callback references for proper cleanup
        // CRITICAL: We must store these to be able to unregister listeners properly
        this.callbacks = {
            applyAll: () => this.applyAllProperties(),
            applyRealtime: () => this.applyStylesRealtime(),
            reset: () => this.resetStyles(),
            toggleBold: () => this.toggleBold(),
            toggleItalic: () => this.toggleItalic(),
            toggleUnderline: () => this.toggleUnderline(),
            addNode: () => this.handleAddNode(),
            deleteNode: () => this.handleDeleteNode(),
            emptyNode: () => this.handleEmptyNode()
        };
        
        this.setupEventListeners();
        
        // Listen for diagram re-render completion to restore dimensions
        this.eventBus.onWithOwner('diagram:node_updated', (data) => {
            // Restore dimensions after a delay to ensure render is complete
            // Use longer delay for brace maps which may take more time to render
            setTimeout(() => this.restorePreservedDimensions(), 300);
        }, this.ownerId);
        
        this.logger.info('NodePropertyOperationsManager', 'Node & Property Operations Manager initialized');
    }
    
    /**
     * Get selected nodes from State Manager (source of truth) with fallback
     * ARCHITECTURE: Uses State Manager as primary source, falls back to toolbarManager if needed
     */
    getSelectedNodes() {
        // Try State Manager first (source of truth)
        if (this.stateManager && typeof this.stateManager.getDiagramState === 'function') {
            const diagramState = this.stateManager.getDiagramState();
            const selectedNodes = diagramState?.selectedNodes || [];
            if (selectedNodes.length > 0) {
                return selectedNodes;
            }
        }
        
        // Fallback to toolbarManager local state
        if (this.toolbarManager?.currentSelection) {
            return this.toolbarManager.currentSelection;
        }
        
        return [];
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        // Property operations - use stored callback references with owner tracking
        this.eventBus.onWithOwner('properties:apply_all_requested', this.callbacks.applyAll, this.ownerId);
        this.eventBus.onWithOwner('properties:apply_realtime_requested', this.callbacks.applyRealtime, this.ownerId);
        this.eventBus.onWithOwner('properties:reset_requested', this.callbacks.reset, this.ownerId);
        this.eventBus.onWithOwner('properties:toggle_bold_requested', this.callbacks.toggleBold, this.ownerId);
        this.eventBus.onWithOwner('properties:toggle_italic_requested', this.callbacks.toggleItalic, this.ownerId);
        this.eventBus.onWithOwner('properties:toggle_underline_requested', this.callbacks.toggleUnderline, this.ownerId);
        
        // Node operations - use stored callback references with owner tracking
        this.eventBus.onWithOwner('node:add_requested', this.callbacks.addNode, this.ownerId);
        this.eventBus.onWithOwner('node:delete_requested', this.callbacks.deleteNode, this.ownerId);
        this.eventBus.onWithOwner('node:empty_requested', this.callbacks.emptyNode, this.ownerId);
        
        this.logger.debug('NodePropertyOperationsManager', 'Event Bus listeners registered with owner tracking');
    }
    
    /**
     * Apply all properties to selected nodes
     * EXTRACTED FROM: toolbar-manager.js lines 780-870
     * REFACTORED: Now uses applyPropertiesToNode helper method to eliminate code duplication
     */
    applyAllProperties() {
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (selectedNodes.length === 0) return;
        
        const properties = {
            text: this.toolbarManager.propText?.value,
            fontSize: this.toolbarManager.propFontSize?.value,
            fontFamily: this.toolbarManager.propFontFamily?.value,
            textColor: this.normalizeColor(this.toolbarManager.propTextColor?.value),
            fillColor: this.normalizeColor(this.toolbarManager.propFillColor?.value),
            strokeColor: this.normalizeColor(this.toolbarManager.propStrokeColor?.value),
            strokeWidth: this.toolbarManager.propStrokeWidth?.value,
            opacity: this.toolbarManager.propOpacity?.value !== undefined && this.toolbarManager.propOpacity?.value !== null 
                ? parseFloat(this.toolbarManager.propOpacity.value) || 1 
                : 1,
            bold: this.toolbarManager.propBold?.classList.contains('active'),
            italic: this.toolbarManager.propItalic?.classList.contains('active'),
            underline: this.toolbarManager.propUnderline?.classList.contains('active')
        };
        
        this.logger.debug('NodePropertyOperationsManager', 'Applying all properties', {
            count: selectedNodes.length,
            opacity: properties.opacity
        });
        
        // Apply text changes first using the proper method (silently - we'll show one notification at the end)
        if (properties.text && properties.text.trim()) {
            this.toolbarManager.applyText(true); // Pass true to suppress notification
        }
        
        // Apply styles to all selected nodes using helper method
        selectedNodes.forEach(nodeId => {
            this.applyPropertiesToNode(nodeId, properties);
        });
        
        this.editor?.saveToHistory('update_properties', { 
            nodes: selectedNodes, 
            properties 
        });
        
        this.toolbarManager.showNotification(this.toolbarManager.getNotif('propertiesApplied'), 'success');
    }
    
    /**
     * Apply styles in real-time (without notification)
     * EXTRACTED FROM: toolbar-manager.js lines 875-937
     * REFACTORED: Now uses applyPropertiesToNode helper method to eliminate code duplication
     */
    applyStylesRealtime() {
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (selectedNodes.length === 0) return;
        
        const properties = {
            fontSize: this.toolbarManager.propFontSize?.value,
            fontFamily: this.toolbarManager.propFontFamily?.value,
            textColor: this.normalizeColor(this.toolbarManager.propTextColor?.value),
            fillColor: this.normalizeColor(this.toolbarManager.propFillColor?.value),
            strokeColor: this.normalizeColor(this.toolbarManager.propStrokeColor?.value),
            strokeWidth: this.toolbarManager.propStrokeWidth?.value,
            opacity: this.toolbarManager.propOpacity?.value !== undefined && this.toolbarManager.propOpacity?.value !== null 
                ? parseFloat(this.toolbarManager.propOpacity.value) || 1 
                : 1,
            bold: this.toolbarManager.propBold?.classList.contains('active'),
            italic: this.toolbarManager.propItalic?.classList.contains('active'),
            underline: this.toolbarManager.propUnderline?.classList.contains('active')
        };
        
        // Apply to all selected nodes using helper method
        selectedNodes.forEach(nodeId => {
            this.applyPropertiesToNode(nodeId, properties);
        });
        
        // Save to history silently
        this.editor?.saveToHistory('update_properties', { 
            nodes: selectedNodes, 
            properties 
        });
    }
    
    /**
     * Apply properties to a single node (helper method)
     * Reusable method for applying properties consistently across different operations
     * @param {string} nodeId - Node ID
     * @param {object} properties - Properties object with style values
     */
    applyPropertiesToNode(nodeId, properties) {
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (nodeElement.empty()) return;
        
        // Find text element using multiple methods (consistent with other methods)
        let textElement = d3.select(`[data-text-for="${nodeId}"]`);
        if (textElement.empty()) {
            const node = nodeElement.node();
            if (node && node.nextElementSibling && node.nextElementSibling.tagName === 'text') {
                textElement = d3.select(node.nextElementSibling);
            } else {
                textElement = nodeElement.select('text');
            }
        }
        
        // Apply shape properties (with null checks)
        if (properties.fillColor) {
            nodeElement.attr('fill', this.normalizeColor(properties.fillColor));
        }
        if (properties.strokeColor) {
            nodeElement.attr('stroke', this.normalizeColor(properties.strokeColor));
        }
        if (properties.strokeWidth !== undefined && properties.strokeWidth !== null) {
            nodeElement.attr('stroke-width', properties.strokeWidth);
        }
        // Opacity: Always apply (even if 0) - use proper number parsing
        if (properties.opacity !== undefined && properties.opacity !== null) {
            nodeElement.attr('opacity', parseFloat(properties.opacity) || 1);
        }
        
        // Apply text styling properties
        if (!textElement.empty()) {
            // Font size
            if (properties.fontSize) {
                const fontSize = String(properties.fontSize).trim();
                textElement.attr('font-size', fontSize);
            }
            
            // Font family
            if (properties.fontFamily) {
                textElement.attr('font-family', properties.fontFamily);
            }
            
            // Text color (fill)
            if (properties.textColor) {
                textElement.attr('fill', this.normalizeColor(properties.textColor));
            }
            
            // Font weight (bold)
            if (properties.bold !== undefined) {
                textElement.attr('font-weight', properties.bold ? 'bold' : 'normal');
            }
            
            // Font style (italic)
            if (properties.italic !== undefined) {
                textElement.attr('font-style', properties.italic ? 'italic' : 'normal');
            }
            
            // Text decoration (underline)
            if (properties.underline !== undefined) {
                textElement.attr('text-decoration', properties.underline ? 'underline' : 'none');
            }
        }
    }
    
    /**
     * Reset styles to template defaults (keep text unchanged)
     * FIXED: Now applies correct defaults to each node individually based on its own node type
     * Uses helper method to avoid code duplication
     */
    resetStyles() {
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (selectedNodes.length === 0) return;
        
        // Track what was reset for history
        const resetProperties = [];
        
        // Get defaults for each node individually based on its own node type
        // Apply correct defaults to each node separately
        selectedNodes.forEach(nodeId => {
            const defaultProps = this.getTemplateDefaults(nodeId);
            
            // Normalize colors and ensure proper types
            const properties = {
                fontSize: defaultProps.fontSize,
                fontFamily: defaultProps.fontFamily,
                textColor: this.normalizeColor(defaultProps.textColor),
                fillColor: this.normalizeColor(defaultProps.fillColor),
                strokeColor: this.normalizeColor(defaultProps.strokeColor),
                strokeWidth: defaultProps.strokeWidth,
                opacity: parseFloat(defaultProps.opacity) || 1,
                bold: false,
                italic: false,
                underline: false
            };
            
            // Apply properties to this node
            this.applyPropertiesToNode(nodeId, properties);
            
            // Track for history
            resetProperties.push({
                nodeId,
                properties
            });
        });
        
        // Update UI inputs to show defaults for the first selected node (for UI consistency)
        const firstNodeId = selectedNodes[0];
        const firstNodeDefaults = this.getTemplateDefaults(firstNodeId);
        
        if (this.toolbarManager.propFontSize) this.toolbarManager.propFontSize.value = parseInt(firstNodeDefaults.fontSize);
        if (this.toolbarManager.propFontFamily) this.toolbarManager.propFontFamily.value = firstNodeDefaults.fontFamily;
        if (this.toolbarManager.propTextColor) this.toolbarManager.propTextColor.value = this.normalizeColor(firstNodeDefaults.textColor);
        if (this.toolbarManager.propTextColorHex) this.toolbarManager.propTextColorHex.value = this.normalizeColor(firstNodeDefaults.textColor).toUpperCase();
        if (this.toolbarManager.propFillColor) this.toolbarManager.propFillColor.value = this.normalizeColor(firstNodeDefaults.fillColor);
        if (this.toolbarManager.propFillColorHex) this.toolbarManager.propFillColorHex.value = this.normalizeColor(firstNodeDefaults.fillColor).toUpperCase();
        if (this.toolbarManager.propStrokeColor) this.toolbarManager.propStrokeColor.value = this.normalizeColor(firstNodeDefaults.strokeColor);
        if (this.toolbarManager.propStrokeColorHex) this.toolbarManager.propStrokeColorHex.value = this.normalizeColor(firstNodeDefaults.strokeColor).toUpperCase();
        if (this.toolbarManager.propStrokeWidth) this.toolbarManager.propStrokeWidth.value = parseFloat(firstNodeDefaults.strokeWidth);
        if (this.toolbarManager.strokeWidthValue) this.toolbarManager.strokeWidthValue.textContent = `${firstNodeDefaults.strokeWidth}px`;
        if (this.toolbarManager.propOpacity) this.toolbarManager.propOpacity.value = parseFloat(firstNodeDefaults.opacity);
        if (this.toolbarManager.opacityValue) this.toolbarManager.opacityValue.textContent = `${Math.round(parseFloat(firstNodeDefaults.opacity) * 100)}%`;
        
        // Reset style toggles to defaults (off)
        this.toolbarManager.propBold?.classList.remove('active');
        this.toolbarManager.propItalic?.classList.remove('active');
        this.toolbarManager.propUnderline?.classList.remove('active');
        
        // Save to history with detailed information
        this.editor?.saveToHistory('reset_styles', { 
            nodes: selectedNodes,
            resetProperties: resetProperties
        });
        
        this.toolbarManager.showNotification(
            window.languageManager?.getCurrentLanguage() === 'zh' 
                ? '样式已重置为模板默认值' 
                : 'Styles reset to template defaults',
            'success'
        );
    }
    
    /**
     * Get template default styles based on diagram type and node type
     * FIXED: Now uses StyleManager to get correct defaults matching the actual template
     * @param {string} nodeId - Optional node ID to get node-specific defaults
     * @returns {object} Default properties object
     */
    getTemplateDefaults(nodeId = null) {
        const diagramType = this.editor?.diagramType;
        
        // Try to get defaults from StyleManager if available
        if (typeof window !== 'undefined' && window.styleManager && window.styleManager.getDefaultTheme) {
            const theme = window.styleManager.getDefaultTheme(diagramType);
            if (theme && Object.keys(theme).length > 0) {
                // Get node type from selected node if provided
                // Try multiple methods to find node type (shape element, text element, or both)
                let nodeType = null;
                if (nodeId) {
                    // Method 1: Try shape element (circle, rect, etc.)
                    const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
                    if (!nodeElement.empty()) {
                        nodeType = nodeElement.attr('data-node-type');
                    }
                    
                    // Method 2: If not found, try text element
                    if (!nodeType) {
                        let textElement = d3.select(`[data-text-for="${nodeId}"]`);
                        if (textElement.empty()) {
                            // Try next sibling
                            const node = nodeElement.node();
                            if (node && node.nextElementSibling && node.nextElementSibling.tagName === 'text') {
                                textElement = d3.select(node.nextElementSibling);
                            } else {
                                textElement = nodeElement.select('text');
                            }
                        }
                        if (!textElement.empty()) {
                            nodeType = textElement.attr('data-node-type');
                        }
                    }
                    
                    // Log for debugging
                    this.logger.debug('NodePropertyOperationsManager', 'Getting template defaults', {
                        nodeId,
                        nodeType,
                        diagramType,
                        themeKeys: Object.keys(theme),
                        themeAttributeFill: theme.attributeFill,
                        themeAttributeText: theme.attributeText
                    });
                }
                
                // Map theme properties to property panel format based on node type
                const mappedProps = this.mapThemeToProperties(theme, diagramType, nodeType);
                this.logger.debug('NodePropertyOperationsManager', 'Mapped theme properties', {
                    nodeType,
                    diagramType,
                    fillColor: mappedProps.fillColor,
                    textColor: mappedProps.textColor,
                    strokeColor: mappedProps.strokeColor
                });
                return mappedProps;
            }
        }
        
        // Fallback to standard defaults if StyleManager not available
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
     * Map StyleManager theme properties to property panel format
     * @param {object} theme - Theme object from StyleManager
     * @param {string} diagramType - Diagram type
     * @param {string} nodeType - Node type (topic, attribute, branch, etc.)
     * @returns {object} Properties object for property panel
     */
    mapThemeToProperties(theme, diagramType, nodeType) {
        // Default values (fallback only if theme doesn't have the property)
        let fillColor = '#2196f3';
        let textColor = '#000000';
        let strokeColor = '#1976d2';
        let strokeWidth = '2';
        let fontSize = '14';
        const fontFamily = 'Inter, sans-serif';
        const opacity = '1';
        
        // Log theme structure for debugging
        this.logger.debug('NodePropertyOperationsManager', 'Mapping theme to properties', {
            diagramType,
            nodeType,
            themeHasAttributeFill: theme.hasOwnProperty('attributeFill'),
            themeHasAttributeText: theme.hasOwnProperty('attributeText'),
            attributeFillValue: theme.attributeFill,
            attributeTextValue: theme.attributeText,
            allThemeKeys: Object.keys(theme)
        });
        
        // Map based on diagram type and node type
        switch (diagramType) {
            case 'bubble_map':
                if (nodeType === 'topic' || nodeType === 'center') {
                    // Topic node defaults
                    fillColor = (theme.topicFill !== undefined && theme.topicFill !== null) ? theme.topicFill : fillColor;
                    textColor = (theme.topicText !== undefined && theme.topicText !== null) ? theme.topicText : textColor;
                    strokeColor = (theme.topicStroke !== undefined && theme.topicStroke !== null) ? theme.topicStroke : strokeColor;
                    strokeWidth = String((theme.topicStrokeWidth !== undefined && theme.topicStrokeWidth !== null) ? theme.topicStrokeWidth : strokeWidth);
                    fontSize = String((theme.fontTopic !== undefined && theme.fontTopic !== null) ? theme.fontTopic : fontSize);
                } else {
                    // Attribute node defaults (most common node type in bubble map)
                    // This handles attribute, context, or null nodeType
                    fillColor = (theme.attributeFill !== undefined && theme.attributeFill !== null) ? theme.attributeFill : fillColor;
                    textColor = (theme.attributeText !== undefined && theme.attributeText !== null) ? theme.attributeText : textColor;
                    strokeColor = (theme.attributeStroke !== undefined && theme.attributeStroke !== null) ? theme.attributeStroke : strokeColor;
                    strokeWidth = String((theme.attributeStrokeWidth !== undefined && theme.attributeStrokeWidth !== null) ? theme.attributeStrokeWidth : strokeWidth);
                    fontSize = String((theme.fontAttribute !== undefined && theme.fontAttribute !== null) ? theme.fontAttribute : fontSize);
                }
                break;
                
            case 'double_bubble_map':
                if (nodeType === 'central' || nodeType === 'center') {
                    fillColor = theme.centralTopicFill || fillColor;
                    textColor = theme.centralTopicText || textColor;
                    strokeColor = theme.centralTopicStroke || strokeColor;
                    strokeWidth = String(theme.centralTopicStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontCentralTopic || fontSize);
                } else if (nodeType === 'left' || nodeType === 'right') {
                    fillColor = theme.leftTopicFill || theme.rightTopicFill || fillColor;
                    textColor = theme.leftTopicText || theme.rightTopicText || textColor;
                    strokeColor = theme.leftTopicStroke || theme.rightTopicStroke || strokeColor;
                    strokeWidth = String(theme.leftTopicStrokeWidth || theme.rightTopicStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontTopic || fontSize);
                } else if (nodeType === 'attribute') {
                    fillColor = theme.attributeFill || fillColor;
                    textColor = theme.attributeText || textColor;
                    strokeColor = theme.attributeStroke || strokeColor;
                    strokeWidth = String(theme.attributeStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontAttribute || fontSize);
                }
                break;
                
            case 'mindmap':
                if (nodeType === 'topic' || nodeType === 'center') {
                    fillColor = theme.centralTopicFill || fillColor;
                    textColor = theme.centralTopicText || textColor;
                    strokeColor = theme.centralTopicStroke || strokeColor;
                    strokeWidth = String(theme.centralTopicStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontTopic || fontSize);
                } else if (nodeType === 'branch') {
                    fillColor = theme.branchFill || fillColor;
                    textColor = theme.branchText || textColor;
                    strokeColor = theme.branchStroke || strokeColor;
                    strokeWidth = String(theme.branchStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontBranch || fontSize);
                } else if (nodeType === 'child') {
                    fillColor = theme.childFill || fillColor;
                    textColor = theme.childText || textColor;
                    strokeColor = theme.childStroke || strokeColor;
                    strokeWidth = String(theme.childStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontChild || fontSize);
                }
                break;
                
            case 'concept_map':
                if (nodeType === 'topic' || nodeType === 'center') {
                    fillColor = theme.topicFill || fillColor;
                    textColor = theme.topicText || textColor;
                    strokeColor = theme.topicStroke || strokeColor;
                    strokeWidth = String(theme.topicStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontTopic || fontSize);
                } else if (nodeType === 'concept') {
                    fillColor = theme.conceptFill || fillColor;
                    textColor = theme.conceptText || textColor;
                    strokeColor = theme.conceptStroke || strokeColor;
                    strokeWidth = String(theme.conceptStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontConcept || fontSize);
                }
                break;
                
            case 'brace_map':
                if (nodeType === 'topic' || nodeType === 'center') {
                    fillColor = theme.topicFill || fillColor;
                    textColor = theme.topicText || textColor;
                    strokeColor = theme.topicStroke || strokeColor;
                    strokeWidth = String(theme.topicStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontTopic || fontSize);
                } else if (nodeType === 'part') {
                    fillColor = theme.partFill || fillColor;
                    textColor = theme.partText || textColor;
                    strokeColor = theme.partStroke || strokeColor;
                    strokeWidth = String(theme.partStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontPart || fontSize);
                } else if (nodeType === 'subpart') {
                    fillColor = theme.subpartFill || fillColor;
                    textColor = theme.subpartText || textColor;
                    strokeColor = theme.subpartStroke || strokeColor;
                    strokeWidth = String(theme.subpartStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontSubpart || fontSize);
                }
                break;
                
            case 'tree_map':
                if (nodeType === 'root') {
                    fillColor = theme.rootFill || fillColor;
                    textColor = theme.rootText || textColor;
                    strokeColor = theme.rootStroke || strokeColor;
                    strokeWidth = String(theme.rootStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontRoot || fontSize);
                } else if (nodeType === 'branch') {
                    fillColor = theme.branchFill || fillColor;
                    textColor = theme.branchText || textColor;
                    strokeColor = theme.branchStroke || strokeColor;
                    strokeWidth = String(theme.branchStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontBranch || fontSize);
                } else if (nodeType === 'leaf') {
                    fillColor = theme.leafFill || fillColor;
                    textColor = theme.leafText || textColor;
                    strokeColor = theme.leafStroke || strokeColor;
                    strokeWidth = String(theme.leafStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontLeaf || fontSize);
                }
                break;
                
            case 'flow_map':
            case 'multi_flow_map':
            case 'flowchart':
                if (nodeType === 'step' || nodeType === 'process') {
                    fillColor = theme.stepFill || theme.processFill || fillColor;
                    textColor = theme.stepText || theme.processText || textColor;
                    strokeColor = theme.stepStroke || theme.processStroke || strokeColor;
                    strokeWidth = String(theme.stepStrokeWidth || theme.processStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontStep || theme.fontNode || fontSize);
                } else if (nodeType === 'start') {
                    fillColor = theme.startFill || fillColor;
                    textColor = theme.startText || textColor;
                    strokeColor = theme.startStroke || strokeColor;
                    strokeWidth = String(theme.startStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontNode || fontSize);
                } else if (nodeType === 'end') {
                    fillColor = theme.endFill || fillColor;
                    textColor = theme.endText || textColor;
                    strokeColor = theme.endStroke || strokeColor;
                    strokeWidth = String(theme.endStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontNode || fontSize);
                } else if (nodeType === 'decision') {
                    fillColor = theme.decisionFill || fillColor;
                    textColor = theme.decisionText || textColor;
                    strokeColor = theme.decisionStroke || strokeColor;
                    strokeWidth = String(theme.decisionStrokeWidth || strokeWidth);
                    fontSize = String(theme.fontNode || fontSize);
                }
                break;
        }
        
        return {
            fontSize: fontSize,
            fontFamily: fontFamily,
            textColor: textColor,
            fillColor: fillColor,
            strokeColor: strokeColor,
            strokeWidth: strokeWidth,
            opacity: opacity
        };
    }
    
    /**
     * Toggle bold
     * EXTRACTED FROM: toolbar-manager.js lines 1017-1019
     */
    toggleBold() {
        if (!this.toolbarManager) return;
        this.toolbarManager.propBold.classList.toggle('active');
    }
    
    /**
     * Toggle italic
     * EXTRACTED FROM: toolbar-manager.js lines 1024-1026
     */
    toggleItalic() {
        if (!this.toolbarManager) return;
        this.toolbarManager.propItalic.classList.toggle('active');
    }
    
    /**
     * Toggle underline
     * EXTRACTED FROM: toolbar-manager.js lines 1031-1033
     */
    toggleUnderline() {
        if (!this.toolbarManager) return;
        this.toolbarManager.propUnderline.classList.toggle('active');
    }
    
    /**
     * Handle add node
     * EXTRACTED FROM: toolbar-manager.js lines 1038-1068
     */
    handleAddNode() {
        // Defensive checks for null references
        if (!this.logger) {
            console.error('[NodePropertyOperationsManager] Logger is null, using console fallback');
            this.logger = console;
        }
        
        if (!this.toolbarManager) {
            console.error('[NodePropertyOperationsManager] ToolbarManager is null, cannot proceed');
            this.logger.error('NodePropertyOperationsManager', 'handleAddNode blocked - toolbarManager not initialized');
            return;
        }
        
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
        const selectedNodes = this.getSelectedNodes();
        if (requiresSelection && selectedNodes.length === 0) {
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('selectNodeToAdd'), 'warning');
            return;
        }
        
        // Call editor's addNode method (it will handle diagram-specific logic)
        this.editor.addNode();
        
        // Only show generic success notification for diagram types that don't show their own
        const showsOwnNotification = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map', 'bridge_map', 'circle_map', 'bubble_map', 'concept_map', 'mindmap'].includes(diagramType);
        if (!showsOwnNotification && this.toolbarManager) {
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('nodeAdded'), 'success');
        }
        
        // Node count updates automatically via MutationObserver
    }
    
    /**
     * Handle delete node
     * EXTRACTED FROM: toolbar-manager.js lines 1073-1084
     */
    handleDeleteNode() {
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (this.editor && selectedNodes.length > 0) {
            const count = selectedNodes.length;
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
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (this.editor && selectedNodes.length > 0) {
            const nodeIds = [...selectedNodes];
            
            nodeIds.forEach(nodeId => {
                // Find the shape element
                const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
                if (shapeElement.empty()) {
                    this.logger.warn('NodePropertyOperationsManager', `Shape not found for nodeId: ${nodeId}`);
                    return;
                }
                
                // Store current dimensions before emptying to preserve them
                // Store in memory (Map) so they survive re-render
                // Handle both rectangles (width/height) and circles (r/radius)
                const nodeTag = shapeElement.node().tagName.toLowerCase();
                const currentWidth = shapeElement.attr('width');
                const currentHeight = shapeElement.attr('height');
                const currentRx = shapeElement.attr('rx');
                const currentRy = shapeElement.attr('ry');
                const currentRadius = shapeElement.attr('r');
                const currentCx = shapeElement.attr('cx');
                const currentCy = shapeElement.attr('cy');
                
                // Also try to get computed dimensions if attributes are not set
                let width = currentWidth;
                let height = currentHeight;
                let radius = currentRadius;
                
                if ((nodeTag === 'rect' && (!width || !height)) || (nodeTag === 'circle' && !radius)) {
                    try {
                        const bbox = shapeElement.node().getBBox();
                        if (nodeTag === 'rect') {
                            width = width || bbox.width;
                            height = height || bbox.height;
                        } else if (nodeTag === 'circle') {
                            radius = radius || (bbox.width / 2); // Use width/2 as radius approximation
                        }
                    } catch (e) {
                        // getBBox might fail, use attributes only
                    }
                }
                
                // Store dimensions based on node type
                const dimensions = {};
                if (nodeTag === 'rect') {
                    if (width || height) {
                        dimensions.type = 'rect';
                        if (width) dimensions.width = width;
                        if (height) dimensions.height = height;
                        if (currentRx) dimensions.rx = currentRx;
                        if (currentRy) dimensions.ry = currentRy;
                    }
                } else if (nodeTag === 'circle') {
                    if (radius) {
                        dimensions.type = 'circle';
                        dimensions.r = radius;
                        if (currentCx) dimensions.cx = currentCx;
                        if (currentCy) dimensions.cy = currentCy;
                    }
                }
                
                if (Object.keys(dimensions).length > 1) { // More than just 'type'
                    this.preservedDimensions.set(nodeId, dimensions);
                    this.logger.debug('NodePropertyOperationsManager', `Preserved dimensions for ${nodeId} (${nodeTag})`, dimensions);
                } else {
                    this.logger.warn('NodePropertyOperationsManager', `Could not determine dimensions for ${nodeId} (${nodeTag})`);
                }
                
                // Find the text element
                const shapeNode = shapeElement.node();
                let textElement = d3.select(`[data-text-for="${nodeId}"]`);
                
                // If not found, try to find text as sibling or in parent group
                if (textElement.empty()) {
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
                    // This will trigger a re-render via diagram:node_updated event
                    if (this.editor && typeof this.editor.updateNodeText === 'function') {
                        this.editor.updateNodeText(nodeId, shapeElement.node(), textNode, '');
                    } else {
                        // Fallback: just update the DOM and restore dimensions immediately
                        textElement.text('');
                        if (currentWidth) shapeElement.attr('width', currentWidth);
                        if (currentHeight) shapeElement.attr('height', currentHeight);
                        if (currentRx) shapeElement.attr('rx', currentRx);
                        if (currentRy) shapeElement.attr('ry', currentRy);
                    }
                }
            });
            
            const count = nodeIds.length;
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('nodesEmptied', count), 'success');
            
            // Update property panel if still showing
            const currentSelectedNodes = this.getSelectedNodes();
            if (currentSelectedNodes.length > 0) {
                this.toolbarManager.loadNodeProperties(currentSelectedNodes[0]);
            }
        } else {
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('selectNodeToEmpty'), 'warning');
        }
    }
    
    /**
     * Restore preserved dimensions after re-render
     */
    restorePreservedDimensions() {
        if (this.preservedDimensions.size === 0) return;
        
        let restoredCount = 0;
        const nodesToRetry = [];
        
        this.preservedDimensions.forEach((dimensions, nodeId) => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeTag = shapeElement.node().tagName.toLowerCase();
                let restored = false;
                
                // Restore dimensions based on node type
                if (dimensions.type === 'rect' && nodeTag === 'rect') {
                    // Restore rectangle dimensions
                    if (dimensions.width) {
                        shapeElement.attr('width', dimensions.width);
                    }
                    if (dimensions.height) {
                        shapeElement.attr('height', dimensions.height);
                    }
                    if (dimensions.rx) {
                        shapeElement.attr('rx', dimensions.rx);
                    }
                    if (dimensions.ry) {
                        shapeElement.attr('ry', dimensions.ry);
                    }
                    
                    // Verify restoration worked
                    const restoredWidth = shapeElement.attr('width');
                    const restoredHeight = shapeElement.attr('height');
                    
                    if ((!dimensions.width || restoredWidth === dimensions.width) &&
                        (!dimensions.height || restoredHeight === dimensions.height)) {
                        restored = true;
                    }
                } else if (dimensions.type === 'circle' && nodeTag === 'circle') {
                    // Restore circle dimensions
                    if (dimensions.r) {
                        shapeElement.attr('r', dimensions.r);
                    }
                    if (dimensions.cx) {
                        shapeElement.attr('cx', dimensions.cx);
                    }
                    if (dimensions.cy) {
                        shapeElement.attr('cy', dimensions.cy);
                    }
                    
                    // Verify restoration worked
                    const restoredRadius = shapeElement.attr('r');
                    
                    if (!dimensions.r || restoredRadius === dimensions.r) {
                        restored = true;
                    }
                }
                
                if (restored) {
                    this.preservedDimensions.delete(nodeId);
                    restoredCount++;
                    this.logger.debug('NodePropertyOperationsManager', `Successfully restored dimensions for ${nodeId} (${nodeTag})`, dimensions);
                } else {
                    // Keep for retry
                    nodesToRetry.push(nodeId);
                    this.logger.debug('NodePropertyOperationsManager', `Restoration incomplete for ${nodeId} (${nodeTag}), will retry`, {
                        expected: dimensions,
                        actualType: nodeTag
                    });
                }
            } else {
                // Node not found yet, keep for retry
                nodesToRetry.push(nodeId);
                this.logger.debug('NodePropertyOperationsManager', `Node ${nodeId} not found yet, will retry`);
            }
        });
        
        if (restoredCount > 0) {
            this.logger.debug('NodePropertyOperationsManager', `Restored dimensions for ${restoredCount} node(s)`);
        }
        
        // If there are still preserved dimensions that weren't restored, retry
        if (nodesToRetry.length > 0) {
            // Remove successfully restored nodes, keep retry candidates
            nodesToRetry.forEach(nodeId => {
                // Already handled above - nodes that need retry are still in the map
            });
            
            // Limit retries to prevent infinite loops
            const maxRetries = 5;
            if (!this._restoreRetryCount) this._restoreRetryCount = 0;
            if (this._restoreRetryCount < maxRetries) {
                this._restoreRetryCount++;
                setTimeout(() => {
                    this.restorePreservedDimensions();
                    this._restoreRetryCount = 0; // Reset after retry
                }, 200);
            } else {
                // Give up after max retries
                this.logger.warn('NodePropertyOperationsManager', `Failed to restore dimensions after ${maxRetries} retries`);
                this.preservedDimensions.clear();
                this._restoreRetryCount = 0;
            }
        } else {
            this._restoreRetryCount = 0;
        }
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('NodePropertyOperationsManager', 'Destroying');
        
        // Remove all Event Bus listeners using Listener Registry
        if (this.eventBus && this.ownerId) {
            this.eventBus.removeAllListenersForOwner(this.ownerId);
            this.logger.debug('NodePropertyOperationsManager', 'Event listeners successfully removed');
        }
        
        // Nullify references (now safe since listeners are actually removed)
        this.callbacks = null;
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

