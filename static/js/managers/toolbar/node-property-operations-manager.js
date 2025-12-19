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
        
        // Store callback references for proper cleanup
        // CRITICAL: We must store these to be able to unregister listeners properly
        this.callbacks = {
            applyAll: () => this.applyAllProperties(),
            applyRealtime: () => this.applyStylesRealtime(),
            reset: () => this.resetStyles(),
            toggleBold: () => this.toggleBold(),
            toggleItalic: () => this.toggleItalic(),
            toggleUnderline: () => this.toggleUnderline(),
            toggleStrikethrough: () => this.toggleStrikethrough(),
            addNode: () => this.handleAddNode(),
            deleteNode: () => this.handleDeleteNode(),
            emptyNode: () => this.handleEmptyNode()
        };
        
        this.setupEventListeners();
        this.logger.info('NodePropertyOperationsManager', 'Node & Property Operations Manager initialized');
    }
    
    /**
     * Find text elements for a node based on diagram type and structure
     * SMART SOLUTION: Uses diagram-specific knowledge instead of fallbacks
     * @param {string} nodeId - Node ID
     * @param {d3.Selection} nodeElement - D3 selection of shape element
     * @returns {d3.Selection} Selection of all text elements for this node
     */
    findTextElementsForNode(nodeId, nodeElement) {
        const diagramType = this.editor?.diagramType;
        const node = nodeElement.node();
        
        // Strategy 1: Direct attribute matching (works for most diagrams)
        // Most diagrams use data-node-id or data-text-for on text elements
        let textElements = d3.selectAll(`text[data-node-id="${nodeId}"], text[data-text-for="${nodeId}"]`);
        
        // VERBOSE LOGGING: Track text element finding
        this.logger.info('NodePropertyOperationsManager', 'Finding text elements', {
            nodeId,
            diagramType,
            strategy1Found: !textElements.empty(),
            strategy1Count: textElements.size(),
            nodeElementTag: node?.tagName,
            nodeElementId: node?.getAttribute('data-node-id'),
            nodeElementType: node?.getAttribute('data-node-type')
        });
        
        if (!textElements.empty()) {
            // Log found text elements for debugging
            const foundElements = textElements.nodes().map(n => ({
                nodeId: n.getAttribute('data-node-id'),
                textFor: n.getAttribute('data-text-for'),
                lineIndex: n.getAttribute('data-line-index'),
                textContent: n.textContent?.substring(0, 20),
                parentTag: n.parentElement?.tagName
            }));
            this.logger.debug('NodePropertyOperationsManager', 'Text elements found via Strategy 1', {
                nodeId,
                count: foundElements.length,
                elements: foundElements
            });
            return textElements;
        }
        
        // Strategy 2: Diagram-specific structure-based finding
        switch (diagramType) {
            case 'concept_map':
                // Concept map: rect and text are siblings inside a <g> group
                // The rect has data-node-id, text elements don't
                if (node && node.parentElement && node.parentElement.tagName === 'g') {
                    const groupTextElements = d3.select(node.parentElement).selectAll('text');
                    this.logger.debug('NodePropertyOperationsManager', 'Concept map: Found text via group', {
                        nodeId,
                        groupTextCount: groupTextElements.size()
                    });
                    return groupTextElements;
                }
                break;
                
            case 'brace_map':
                // Brace map: text has data-node-id matching shape, but data-text-for uses different format
                // Already handled by Strategy 1, but verify both attributes are checked
                // Parts: data-node-id="brace-part-0", data-text-for="part_0"
                // Subparts: data-node-id="brace-subpart-0-0", data-text-for="subpart_0_0"
                // Strategy 1 should find via data-node-id
                this.logger.debug('NodePropertyOperationsManager', 'Brace map: Strategy 1 should have found text', {
                    nodeId,
                    textElementsEmpty: textElements.empty()
                });
                break;
                
            case 'double_bubble_map':
                // Double bubble: text elements have data-node-id matching shape
                // Similarities: data-node-id="similarity_0"
                // Differences: data-node-id="left_diff_0", data-node-id="right_diff_0"
                // Topics: data-node-id="topic_left", data-node-id="topic_right"
                // Strategy 1 should find via data-node-id
                this.logger.debug('NodePropertyOperationsManager', 'Double bubble map: Strategy 1 should have found text', {
                    nodeId,
                    textElementsEmpty: textElements.empty()
                });
                break;
                
            case 'flow_map':
            case 'multi_flow_map':
                // Flow maps: text elements have data-node-id matching shape
                // Strategy 1 should find via data-node-id
                this.logger.debug('NodePropertyOperationsManager', 'Flow map: Strategy 1 should have found text', {
                    nodeId,
                    textElementsEmpty: textElements.empty()
                });
                break;
                
            case 'bridge_map':
                // Bridge map: mixed - first pair has both attributes, regular pairs only data-node-id
                // Strategy 1 handles both cases
                this.logger.debug('NodePropertyOperationsManager', 'Bridge map: Strategy 1 should have found text', {
                    nodeId,
                    textElementsEmpty: textElements.empty(),
                    // Debug: Check what text elements exist in DOM
                    allTextElements: d3.selectAll('text').nodes().map(n => ({
                        nodeId: n.getAttribute('data-node-id'),
                        textFor: n.getAttribute('data-text-for'),
                        textContent: n.textContent?.substring(0, 20)
                    })).filter(t => t.nodeId || t.textFor)
                });
                break;
                
            case 'circle_map':
            case 'bubble_map':
            case 'tree_map':
            case 'mindmap':
                // These diagrams: text elements have both data-node-id and data-text-for
                // Strategy 1 should find them
                this.logger.debug('NodePropertyOperationsManager', 'Standard diagram: Strategy 1 should have found text', {
                    nodeId,
                    textElementsEmpty: textElements.empty()
                });
                break;
                
            default:
                // Unknown diagram type - log warning
                this.logger.warn('NodePropertyOperationsManager', `Unknown diagram type for text finding: ${diagramType}`);
                break;
        }
        
        // If still empty, log warning with details
        if (textElements.empty()) {
            this.logger.warn('NodePropertyOperationsManager', 'No text elements found for node', {
                nodeId,
                diagramType,
                nodeElementTag: node?.tagName,
                nodeElementId: node?.getAttribute('data-node-id'),
                nodeElementType: node?.getAttribute('data-node-type'),
                totalTextElementsInDOM: d3.selectAll('text').size()
            });
        }
        
        // If still empty, return empty selection (no fallbacks - fail explicitly)
        return textElements;
    }
    
    /**
     * Apply or remove strikethrough line for SVG text element
     * WORKAROUND: SVG text-decoration has poor browser support for line-through
     * Solution: Use a <line> element positioned over the text
     * @param {d3.Selection} textElement - D3 selection of text element
     * @param {boolean} apply - Whether to apply strikethrough
     */
    applyStrikethroughLine(textElement, apply) {
        if (textElement.empty()) return;
        
        const textNode = textElement.node();
        if (!textNode) return;
        
        const svg = d3.select(textNode.ownerSVGElement || textNode.closest('svg'));
        if (svg.empty()) return;
        
        // Get existing strikethrough line ID
        const nodeId = textNode.getAttribute('data-node-id') || 'unknown';
        const lineIndex = textNode.getAttribute('data-line-index') || '0';
        const lineId = `strikethrough-${nodeId}-${lineIndex}`;
        
        // Find existing line - always search in SVG root since we always append there
        // This ensures we find lines regardless of where text element is located
        let existingLine = svg.select(`#${lineId}`);
        
        if (apply) {
            // Remove existing line if present (in case of re-application)
            existingLine.remove();
            
            // Get text bounding box to position the line
            // CRITICAL: Use getBBox() for all coordinates - it returns screen coordinates
            // that work regardless of whether text is in a group or has transforms
            try {
                // VERBOSE LOGGING: Track strikethrough application for debugging
                this.logger.info('NodePropertyOperationsManager', 'Applying strikethrough', {
                    nodeId,
                    lineIndex,
                    lineId,
                    textContent: textNode.textContent?.substring(0, 30),
                    hasParent: !!textNode.parentElement,
                    parentTag: textNode.parentElement?.tagName,
                    isInSVG: !!textNode.ownerSVGElement,
                    svgId: svg.attr('id') || 'no-id'
                });
                
                const bbox = textNode.getBBox();
                
                // VERBOSE LOGGING: Log bbox details
                this.logger.info('NodePropertyOperationsManager', 'Text bbox retrieved', {
                    nodeId,
                    bbox: bbox ? {
                        x: bbox.x,
                        y: bbox.y,
                        width: bbox.width,
                        height: bbox.height
                    } : null,
                    isValid: bbox && bbox.width > 0 && bbox.height > 0
                });
                
                // If bbox is invalid (width/height are 0 or negative), skip
                if (!bbox || bbox.width <= 0 || bbox.height <= 0) {
                    this.logger.warn('NodePropertyOperationsManager', 'Invalid bbox for strikethrough - text may not be rendered', {
                        nodeId,
                        lineIndex,
                        bbox: bbox ? { x: bbox.x, y: bbox.y, width: bbox.width, height: bbox.height } : null,
                        textContent: textNode.textContent?.substring(0, 30),
                        textNodeVisible: textNode.offsetWidth > 0 || textNode.offsetHeight > 0,
                        computedStyle: window.getComputedStyle ? window.getComputedStyle(textNode).display : 'unknown'
                    });
                    return;
                }
                
                // Use bbox coordinates - these are relative to the text element's coordinate system
                // Position line horizontally across the text width, vertically centered
                const lineX1 = bbox.x;
                const lineX2 = bbox.x + bbox.width;
                const lineY = bbox.y + bbox.height / 2; // Middle of text vertically
                
                // Get text color for the line
                const textColor = textElement.style('fill') || textElement.attr('fill') || '#000000';
                
                // ROOT CAUSE FIX: getBBox() always returns coordinates in SVG coordinate space
                // If text is in a <g> group with transforms, appending line to the group would use wrong coordinates
                // Solution: Always append to SVG root to ensure coordinates match getBBox() results
                const textParent = textNode.parentElement;
                const targetContainer = svg; // Always use SVG root for consistent coordinate system
                
                this.logger.debug('NodePropertyOperationsManager', 'Appending strikethrough line to SVG root', {
                    nodeId,
                    textParentTag: textParent?.tagName,
                    textParentHasTransform: textParent?.getAttribute('transform') || 'none',
                    bboxCoords: { x: bbox.x, y: bbox.y, width: bbox.width, height: bbox.height }
                });
                
                // VERBOSE LOGGING: Log line creation details
                this.logger.info('NodePropertyOperationsManager', 'Creating strikethrough line', {
                    nodeId,
                    lineIndex,
                    lineId,
                    coordinates: { x1: lineX1, y1: lineY, x2: lineX2, y2: lineY },
                    textColor,
                    targetContainer: textParent ? textParent.tagName : 'svg',
                    targetContainerId: targetContainer.attr('id') || 'no-id'
                });
                
                // Create strikethrough line
                targetContainer.append('line')
                    .attr('id', lineId)
                    .attr('x1', lineX1)
                    .attr('y1', lineY)
                    .attr('x2', lineX2)
                    .attr('y2', lineY)
                    .attr('stroke', textColor)
                    .attr('stroke-width', '1.5')
                    .attr('stroke-linecap', 'round')
                    .attr('data-strikethrough-for', textNode.getAttribute('data-node-id'))
                    .attr('data-strikethrough-line-index', textNode.getAttribute('data-line-index') || '0')
                    .style('pointer-events', 'none'); // Don't interfere with text selection
                
                // VERBOSE LOGGING: Verify line was created and is visible
                const createdLine = targetContainer.select(`#${lineId}`);
                if (createdLine.empty()) {
                    this.logger.error('NodePropertyOperationsManager', 'Failed to create strikethrough line', {
                        nodeId,
                        lineIndex,
                        lineId,
                        targetContainer: textParent ? textParent.tagName : 'svg'
                    });
                } else {
                    const lineNode = createdLine.node();
                    const computedStyle = window.getComputedStyle ? window.getComputedStyle(lineNode) : null;
                    const lineBBox = lineNode.getBBox ? lineNode.getBBox() : null;
                    
                    // Log full details - expand object to see all values
                    const logData = {
                        nodeId,
                        lineIndex,
                        lineId,
                        stroke: createdLine.attr('stroke'),
                        strokeWidth: createdLine.attr('stroke-width'),
                        x1: createdLine.attr('x1'),
                        y1: createdLine.attr('y1'),
                        x2: createdLine.attr('x2'),
                        y2: createdLine.attr('y2'),
                        parentTag: lineNode.parentElement?.tagName,
                        parentId: lineNode.parentElement?.id || 'no-id',
                        isVisible: lineNode.offsetWidth > 0 || lineNode.offsetHeight > 0,
                        computedDisplay: computedStyle?.display,
                        computedOpacity: computedStyle?.opacity,
                        computedVisibility: computedStyle?.visibility,
                        computedStroke: computedStyle?.stroke,
                        bbox: lineBBox ? { 
                            x: lineBBox.x, 
                            y: lineBBox.y, 
                            width: lineBBox.width, 
                            height: lineBBox.height 
                        } : null,
                        textBbox: bbox ? {
                            x: bbox.x,
                            y: bbox.y,
                            width: bbox.width,
                            height: bbox.height
                        } : null
                    };
                    this.logger.info('NodePropertyOperationsManager', 'Strikethrough line created successfully', logData);
                    // Also log expanded version to console for debugging
                    console.log('[Strikethrough Debug] Line created:', logData);
                }
            } catch (e) {
                // VERBOSE LOGGING: Log detailed error information
                this.logger.error('NodePropertyOperationsManager', 'Exception applying strikethrough', {
                    nodeId,
                    lineIndex,
                    error: e.message,
                    stack: e.stack,
                    textNode: {
                        tagName: textNode.tagName,
                        textContent: textNode.textContent?.substring(0, 30),
                        hasParent: !!textNode.parentElement,
                        parentTag: textNode.parentElement?.tagName,
                        isConnected: textNode.isConnected,
                        ownerSVGElement: !!textNode.ownerSVGElement
                    },
                    svg: {
                        exists: !svg.empty(),
                        id: svg.attr('id') || 'no-id'
                    }
                });
            }
        } else {
            // Remove strikethrough line
            existingLine.remove();
        }
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
        this.eventBus.onWithOwner('properties:toggle_strikethrough_requested', this.callbacks.toggleStrikethrough, this.ownerId);
        
        // Node operations - use stored callback references with owner tracking
        this.eventBus.onWithOwner('node:add_requested', this.callbacks.addNode, this.ownerId);
        this.eventBus.onWithOwner('node:delete_requested', this.callbacks.deleteNode, this.ownerId);
        this.eventBus.onWithOwner('node:empty_requested', this.callbacks.emptyNode, this.ownerId);
        
        this.logger.debug('NodePropertyOperationsManager', 'Event Bus listeners registered with owner tracking');
    }
    
    /**
     * Apply all properties to selected nodes
     * EXTRACTED FROM: toolbar-manager.js lines 780-870
     */
    applyAllProperties() {
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (selectedNodes.length === 0) return;
        
        const properties = {
            text: this.toolbarManager.propText?.value,
            fontSize: this.toolbarManager.propFontSize?.value,
            fontFamily: this.toolbarManager.propFontFamily?.value,
            textColor: this.toolbarManager.propTextColor?.value,
            fillColor: this.toolbarManager.propFillColor?.value,
            strokeColor: this.toolbarManager.propStrokeColor?.value,
            strokeWidth: this.toolbarManager.propStrokeWidth?.value,
            bold: this.toolbarManager.propBold?.classList.contains('active'),
            italic: this.toolbarManager.propItalic?.classList.contains('active'),
            underline: this.toolbarManager.propUnderline?.classList.contains('active'),
            strikethrough: this.toolbarManager.propStrikethrough?.classList.contains('active')
        };
        
        this.logger.debug('NodePropertyOperationsManager', 'Applying all properties', {
            count: selectedNodes.length
        });
        
        // Apply text changes first using the proper method (silently - we'll show one notification at the end)
        if (properties.text && properties.text.trim()) {
            this.toolbarManager.applyText(true); // Pass true to suppress notification
        }
        
        selectedNodes.forEach(nodeId => {
            const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (nodeElement.empty()) return;
            
            // Check if node is currently selected (has selection highlight)
            const isCurrentlySelected = nodeElement.classed('selected');
            
            // Find ALL text elements for this node using diagram-specific smart finder
            // Uses knowledge of each diagram's structure instead of fallbacks
            const textElements = this.findTextElementsForNode(nodeId, nodeElement);
            
            // Apply shape properties - ALWAYS apply directly for real-time preview
            // The drop-shadow filter will remain as the selection indicator
            if (properties.fillColor) {
                nodeElement.attr('fill', properties.fillColor);
            }
            if (properties.strokeColor) {
                // Apply stroke directly for real-time preview
                nodeElement.attr('stroke', properties.strokeColor);
                // Also update data-original-stroke so correct color is tracked for deselection
                if (isCurrentlySelected) {
                    nodeElement.attr('data-original-stroke', properties.strokeColor);
                }
            }
            if (properties.strokeWidth) {
                // Apply via inline style (takes precedence, works in line mode)
                // This ensures changes work even when line mode has set inline styles
                nodeElement.style('stroke-width', properties.strokeWidth + 'px');
                // Also update attribute for when inline style is cleared (line mode disabled)
                nodeElement.attr('stroke-width', properties.strokeWidth);
                // Always update data-original-stroke-width for line mode restoration
                    nodeElement.attr('data-original-stroke-width', properties.strokeWidth);
            }
            
            // Apply text styling properties to ALL text elements (not content - that's handled by applyText)
            if (!textElements.empty()) {
                if (properties.fontSize) {
                    textElements.attr('font-size', properties.fontSize);
                }
                if (properties.fontFamily) {
                    textElements.attr('font-family', properties.fontFamily);
                }
                if (properties.textColor) {
                    textElements.attr('fill', properties.textColor);
                    // Update strikethrough line color if strikethrough is active
                    if (properties.strikethrough) {
                        textElements.each((d, i, nodes) => {
                            const textNode = nodes[i];
                            const textEl = d3.select(textNode);
                            const nodeId = textEl.attr('data-node-id') || 'unknown';
                            const lineIndex = textEl.attr('data-line-index') || '0';
                            const lineId = `strikethrough-${nodeId}-${lineIndex}`;
                            // Search in same parent as text element first, then root SVG
                            const textParent = textNode.parentElement;
                            const parentContainer = textParent ? d3.select(textParent) : d3.select(textNode.ownerSVGElement || textNode.closest('svg'));
                            let line = parentContainer.select(`#${lineId}`);
                            if (line.empty()) {
                                const svg = d3.select(textNode.ownerSVGElement || textNode.closest('svg'));
                                line = svg.select(`#${lineId}`);
                            }
                            if (!line.empty()) {
                                line.attr('stroke', properties.textColor);
                            }
                        });
                    }
                }
                if (properties.bold) {
                    textElements.attr('font-weight', 'bold');
                } else {
                    textElements.attr('font-weight', 'normal');
                }
                if (properties.italic) {
                    textElements.attr('font-style', 'italic');
                } else {
                    textElements.attr('font-style', 'normal');
                }
                // Apply text-decoration for underline (CSS style works well)
                const decorations = [];
                if (properties.underline) decorations.push('underline');
                const underlineValue = decorations.length > 0 ? decorations.join(' ') : 'none';
                textElements.style('text-decoration', underlineValue);
                textElements.attr('text-decoration', underlineValue);
                
                // Apply strikethrough using line elements (workaround for poor SVG text-decoration support)
                // SVG text-decoration has very poor browser support for line-through, especially in flow maps
                textElements.each((d, i, nodes) => {
                    const textEl = d3.select(nodes[i]);
                    this.applyStrikethroughLine(textEl, properties.strikethrough);
                });
            }
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
     */
    applyStylesRealtime() {
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (selectedNodes.length === 0) return;
        
        const properties = {
            fontSize: this.toolbarManager.propFontSize?.value,
            fontFamily: this.toolbarManager.propFontFamily?.value,
            textColor: this.toolbarManager.propTextColor?.value,
            fillColor: this.toolbarManager.propFillColor?.value,
            strokeColor: this.toolbarManager.propStrokeColor?.value,
            strokeWidth: this.toolbarManager.propStrokeWidth?.value,
            bold: this.toolbarManager.propBold?.classList.contains('active'),
            italic: this.toolbarManager.propItalic?.classList.contains('active'),
            underline: this.toolbarManager.propUnderline?.classList.contains('active'),
            strikethrough: this.toolbarManager.propStrikethrough?.classList.contains('active')
        };
        
        // Check if we're in line mode - if so, skip fill/stroke color changes
        // to preserve line mode's black/white styling
        const isLineMode = this.toolbarManager?.isLineMode || false;
        
        // Apply to all selected nodes
        selectedNodes.forEach(nodeId => {
            const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (nodeElement.empty()) return;
            
            // Check if node is currently selected (has selection highlight)
            const isCurrentlySelected = nodeElement.classed('selected');
            
            // Apply shape properties - ALWAYS apply directly for real-time preview
            // The drop-shadow filter will remain as the selection indicator
            // In line mode, skip fill/stroke to preserve black/white styling
            if (properties.fillColor && !isLineMode) {
                nodeElement.attr('fill', properties.fillColor);
            }
            if (properties.strokeColor && !isLineMode) {
                // Apply stroke directly for real-time preview
                nodeElement.attr('stroke', properties.strokeColor);
                // Also update data-original-stroke so correct color is tracked for deselection
                if (isCurrentlySelected) {
                    nodeElement.attr('data-original-stroke', properties.strokeColor);
                }
            }
            if (properties.strokeWidth) {
                // Apply via inline style (takes precedence, works in line mode)
                // This ensures changes work even when line mode has set inline styles
                nodeElement.style('stroke-width', properties.strokeWidth + 'px');
                // Also update attribute for when inline style is cleared (line mode disabled)
                nodeElement.attr('stroke-width', properties.strokeWidth);
                // Always update data-original-stroke-width for line mode restoration
                    nodeElement.attr('data-original-stroke-width', properties.strokeWidth);
            }
            
            // Find ALL text elements for this node using diagram-specific smart finder
            // Uses knowledge of each diagram's structure instead of fallbacks
            const textElements = this.findTextElementsForNode(nodeId, nodeElement);
            
            // Apply text properties to ALL text elements
            // In line mode, skip text color to preserve black text styling
            if (!textElements.empty()) {
                if (properties.fontSize) {
                    textElements.attr('font-size', properties.fontSize);
                }
                if (properties.fontFamily) {
                    textElements.attr('font-family', properties.fontFamily);
                }
                if (properties.textColor && !isLineMode) {
                    textElements.attr('fill', properties.textColor);
                    // Update strikethrough line color if strikethrough is active
                    if (properties.strikethrough) {
                        textElements.each((d, i, nodes) => {
                            const textNode = nodes[i];
                            const textEl = d3.select(textNode);
                            const nodeId = textEl.attr('data-node-id') || 'unknown';
                            const lineIndex = textEl.attr('data-line-index') || '0';
                            const lineId = `strikethrough-${nodeId}-${lineIndex}`;
                            // Search in same parent as text element first, then root SVG
                            const textParent = textNode.parentElement;
                            const parentContainer = textParent ? d3.select(textParent) : d3.select(textNode.ownerSVGElement || textNode.closest('svg'));
                            let line = parentContainer.select(`#${lineId}`);
                            if (line.empty()) {
                                const svg = d3.select(textNode.ownerSVGElement || textNode.closest('svg'));
                                line = svg.select(`#${lineId}`);
                            }
                            if (!line.empty()) {
                                line.attr('stroke', properties.textColor);
                            }
                        });
                    }
                }
                textElements.attr('font-weight', properties.bold ? 'bold' : 'normal');
                textElements.attr('font-style', properties.italic ? 'italic' : 'normal');
                // Apply text-decoration for underline (CSS style works well)
                const decorations = [];
                if (properties.underline) decorations.push('underline');
                const underlineValue = decorations.length > 0 ? decorations.join(' ') : 'none';
                textElements.style('text-decoration', underlineValue);
                textElements.attr('text-decoration', underlineValue);
                
                // Apply strikethrough using line elements (workaround for poor SVG text-decoration support)
                // SVG text-decoration has very poor browser support for line-through, especially in flow maps
                textElements.each((d, i, nodes) => {
                    const textEl = d3.select(nodes[i]);
                    this.applyStrikethroughLine(textEl, properties.strikethrough);
                });
            }
        });
        
        // Save to history silently
        this.editor?.saveToHistory('update_properties', { 
            nodes: selectedNodes, 
            properties 
        });
    }
    
    /**
     * Reset styles to template defaults (keep text unchanged)
     * FIXED: Now gets node-specific defaults based on node type, not generic diagram defaults
     */
    resetStyles() {
        if (!this.toolbarManager) return;
        
        const selectedNodes = this.getSelectedNodes();
        if (selectedNodes.length === 0) return;
        
        const diagramType = this.editor?.diagramType;
        if (!diagramType) return;
        
        // Get StyleManager theme as optional fallback (for future extensibility)
        const styleManager = window.styleManager;
        const theme = styleManager?.getDefaultTheme(diagramType) || {};
        
        // Apply diagram-specific and node-specific defaults to each selected node individually
        selectedNodes.forEach(nodeId => {
            const nodeDefaults = this.getNodeTypeDefaults(nodeId, diagramType, theme);
            if (nodeDefaults) {
                this.applyDefaultsToNode(nodeId, nodeDefaults);
            }
        });
        
        // Update UI to show first selected node's defaults (for consistency)
        const firstNodeDefaults = this.getNodeTypeDefaults(selectedNodes[0], diagramType, theme);
        if (firstNodeDefaults) {
            this.applyDefaultsToUI(firstNodeDefaults);
        } else {
            // Fallback to generic defaults
            const defaultProps = this.getTemplateDefaults();
            this.applyDefaultsToUI(defaultProps);
        }
        
        // Reset style toggles based on first node's defaults
        if (firstNodeDefaults) {
            // Set bold toggle based on fontWeight
            if (firstNodeDefaults.fontWeight === 'bold' || firstNodeDefaults.fontWeight === '600') {
                this.toolbarManager.propBold?.classList.add('active');
            } else {
                this.toolbarManager.propBold?.classList.remove('active');
            }
            // Set italic toggle based on fontStyle
            if (firstNodeDefaults.fontStyle === 'italic') {
                this.toolbarManager.propItalic?.classList.add('active');
            } else {
                this.toolbarManager.propItalic?.classList.remove('active');
            }
        } else {
            // Fallback: reset all toggles to off
            this.toolbarManager.propBold?.classList.remove('active');
            this.toolbarManager.propItalic?.classList.remove('active');
        }
        
        // Always reset underline and strikethrough to off (default)
        this.toolbarManager.propUnderline?.classList.remove('active');
        this.toolbarManager.propStrikethrough?.classList.remove('active');
        
        // Save to history
        this.editor?.saveToHistory('reset_styles', { 
            nodes: selectedNodes,
            diagramType
        });
        
        this.toolbarManager.showNotification(
            window.languageManager?.getCurrentLanguage() === 'zh' 
                ? '样式已重置为模板默认值' 
                : 'Styles reset to template defaults',
            'success'
        );
    }
    
    /**
     * Get diagram-specific and node-specific defaults
     * Uses comprehensive mapping based on actual renderer defaults
     * @param {string} nodeId - Node ID
     * @param {string} diagramType - Diagram type
     * @param {object} theme - StyleManager theme object (optional, used as fallback)
     * @returns {object|null} Node-specific defaults in property panel format
     */
    getNodeTypeDefaults(nodeId, diagramType, theme) {
        if (!nodeId) return null;
        
        // Get node type from shape element first, then text element
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (nodeElement.empty()) return null;
        
        let nodeType = nodeElement.attr('data-node-type');
        if (!nodeType) {
            // Try text element as fallback
            const textElements = this.findTextElementsForNode(nodeId, nodeElement);
            if (!textElements.empty()) {
                nodeType = textElements.attr('data-node-type');
            }
        }
        
        if (!nodeType) {
            // No node type found, use generic defaults
            return this.getTemplateDefaults();
        }
        
        // Get diagram-specific and node-specific defaults from comprehensive mapping
        const defaults = this.getDiagramNodeDefaults(diagramType, nodeType, theme);
        
        return defaults || this.getTemplateDefaults();
    }
    
    /**
     * Get diagram-specific and node-specific defaults mapping
     * Comprehensive mapping based on actual renderer THEME objects
     * @param {string} diagramType - Diagram type
     * @param {string} nodeType - Node type
     * @param {object} theme - StyleManager theme (optional, used for fallback)
     * @returns {object|null} Node-specific defaults
     */
    getDiagramNodeDefaults(diagramType, nodeType, theme = {}) {
        // Base defaults
        const baseDefaults = {
            fontSize: '14',
            fontFamily: "Inter, sans-serif",
            textColor: '#000000',
            fillColor: '#2196f3',
            strokeColor: '#1976d2',
            strokeWidth: '2',
            opacity: '1',
            fontWeight: 'normal',
            fontStyle: 'normal'
        };
        
        // Comprehensive diagram-specific and node-specific defaults mapping
        // Based on actual renderer THEME objects and StyleManager defaults
        const diagramNodeDefaults = {
            // ============================================================
            // BUBBLE MAP
            // ============================================================
            bubble_map: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#000000',
                    strokeWidth: '2',
                    fontSize: '20',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                attribute: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#000000',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            
            // ============================================================
            // DOUBLE BUBBLE MAP
            // ============================================================
            double_bubble_map: {
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#000000',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                center: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#000000',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                leftTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#000000',
                    strokeWidth: '2',
                    fontSize: '18',
                    fontWeight: '600',
                    fontFamily: "Inter, sans-serif"
                },
                left: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#000000',
                    strokeWidth: '2',
                    fontSize: '18',
                    fontWeight: '600',
                    fontFamily: "Inter, sans-serif"
                },
                rightTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#000000',
                    strokeWidth: '2',
                    fontSize: '18',
                    fontWeight: '600',
                    fontFamily: "Inter, sans-serif"
                },
                right: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#000000',
                    strokeWidth: '2',
                    fontSize: '18',
                    fontWeight: '600',
                    fontFamily: "Inter, sans-serif"
                },
                similarity: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                left_difference: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                right_difference: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            
            // ============================================================
            // CIRCLE MAP
            // ============================================================
            circle_map: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '20',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                center: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '20',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                context: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            
            // ============================================================
            // MIND MAP
            // ============================================================
            mindmap: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            
            // ============================================================
            // BRACE MAP
            // ============================================================
            brace_map: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '2', // Renderer hardcodes stroke-width: 2 (not 3 from StyleManager)
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Brace renderer parseFontSpec fallback uses this
                },
                part: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '1', // Renderer hardcodes stroke-width: 1 (not 2 from StyleManager)
                    fontSize: '16',
                    fontWeight: 'bold',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Brace renderer parseFontSpec uses this
                },
                subpart: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1', // Renderer hardcodes stroke-width: 1
                    fontSize: '16', // parseFontSpec returns fallback size 16 when fontSubpart is a number (12), not a string
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Brace renderer parseFontSpec uses this
                }
            },
            
            // ============================================================
            // TREE MAP
            // ============================================================
            tree_map: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '2',
                    fontSize: '20',
                    fontWeight: 'bold',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Tree renderer uses this
                },
                root: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '2',
                    fontSize: '20',
                    fontWeight: 'bold',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Tree renderer uses this
                },
                dimension: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '1.5',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Tree renderer uses this
                },
                category: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '1.5',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Tree renderer uses this
                },
                leaf: {
                    fillColor: '#ffffff',
                    textColor: '#333333',
                    strokeColor: '#c8d6e5',
                    strokeWidth: '1',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Tree renderer uses this
                }
            },
            
            // ============================================================
            // FLOW MAP
            // ============================================================
            flow_map: {
                title: {
                    fillColor: '#1976d2',
                    textColor: '#333333',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '20',
                    fontWeight: 'bold',
                    fontFamily: "Inter, Segoe UI, sans-serif"
                },
                step: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif"
                },
                substep: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '1', // Renderer uses Math.max(1, THEME.stepStrokeWidth - 1) = Math.max(1, 2-1) = 1
                    fontSize: '13', // Renderer uses Math.max(12, THEME.fontStep - 1) = Math.max(12, 14-1) = 13
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif"
                }
            },
            
            // ============================================================
            // MULTI FLOW MAP
            // ============================================================
            multi_flow_map: {
                event: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Multi flow map uses THEME.fontFamily from bridge map
                },
                cause: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Multi flow map uses THEME.fontFamily from bridge map
                },
                effect: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#1976d2',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif" // Multi flow map uses THEME.fontFamily from bridge map
                }
            },
            
            // ============================================================
            // CONCEPT MAP
            // ============================================================
            concept_map: {
                topic: {
                    fillColor: '#e3f2fd',
                    textColor: '#000000',
                    strokeColor: '#35506b',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: '600',
                    fontFamily: "Inter, sans-serif"
                },
                center: {
                    fillColor: '#e3f2fd',
                    textColor: '#000000',
                    strokeColor: '#35506b',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: '600',
                    fontFamily: "Inter, sans-serif"
                },
                concept: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: '400',
                    fontFamily: "Inter, sans-serif"
                }
            },
            
            // ============================================================
            // BRIDGE MAP
            // ============================================================
            bridge_map: {
                left: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '0', // Bridge map nodes don't have borders
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif"
                },
                right: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '0', // Bridge map nodes don't have borders
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, Segoe UI, sans-serif"
                }
            },
            
            // ============================================================
            // FLOWCHART
            // ============================================================
            flowchart: {
                start: {
                    fillColor: '#4caf50',
                    textColor: '#ffffff',
                    strokeColor: '#388e3c',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                process: {
                    fillColor: '#2196f3',
                    textColor: '#ffffff',
                    strokeColor: '#1976d2',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                decision: {
                    fillColor: '#ff9800',
                    textColor: '#ffffff',
                    strokeColor: '#f57c00',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                end: {
                    fillColor: '#f44336',
                    textColor: '#ffffff',
                    strokeColor: '#d32f2f',
                    strokeWidth: '2',
                    fontSize: '14',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            
            // ============================================================
            // THINKING TOOLS (all use mindmap structure)
            // ============================================================
            factor_analysis: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            three_position_analysis: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            perspective_analysis: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            goal_analysis: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            possibility_analysis: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            result_analysis: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            five_w_one_h: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            whwm_analysis: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            },
            four_quadrant: {
                topic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                centralTopic: {
                    fillColor: '#1976d2',
                    textColor: '#ffffff',
                    strokeColor: '#0d47a1',
                    strokeWidth: '3',
                    fontSize: '18',
                    fontWeight: 'bold',
                    fontFamily: "Inter, sans-serif"
                },
                branch: {
                    fillColor: '#e3f2fd',
                    textColor: '#333333',
                    strokeColor: '#4e79a7',
                    strokeWidth: '2',
                    fontSize: '16',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                },
                child: {
                    fillColor: '#bbdefb',
                    textColor: '#333333',
                    strokeColor: '#90caf9',
                    strokeWidth: '1',
                    fontSize: '12',
                    fontWeight: 'normal',
                    fontFamily: "Inter, sans-serif"
                }
            }
        };
        
        // Get diagram-specific defaults
        const diagramDefaults = diagramNodeDefaults[diagramType];
        if (!diagramDefaults) {
            // Diagram type not found, use generic defaults
            return null;
        }
        
        // Get node-specific defaults
        const nodeDefaults = diagramDefaults[nodeType];
        if (!nodeDefaults) {
            // Node type not found for this diagram, use generic defaults
            return null;
        }
        
        // Merge with base defaults and return
        return {
            ...baseDefaults,
            ...nodeDefaults
        };
    }
    
    /**
     * Get node-specific defaults based on node type (LEGACY - kept for compatibility)
     * Maps StyleManager theme properties to property panel format
     * @param {string} nodeId - Node ID
     * @param {string} diagramType - Diagram type
     * @param {object} theme - StyleManager theme object
     * @returns {object|null} Node-specific defaults in property panel format
     * @deprecated Use getDiagramNodeDefaults instead for better accuracy
     */
    getNodeTypeDefaultsLegacy(nodeId, diagramType, theme) {
        if (!theme || !nodeId) return null;
        
        // Get node type from shape element first, then text element
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (nodeElement.empty()) return null;
        
        let nodeType = nodeElement.attr('data-node-type');
        if (!nodeType) {
            // Try text element as fallback
            const textElements = this.findTextElementsForNode(nodeId, nodeElement);
            if (!textElements.empty()) {
                nodeType = textElements.attr('data-node-type');
            }
        }
        
        if (!nodeType) {
            // No node type found, use generic defaults
            return this.getTemplateDefaults();
        }
        
        // Map node type to StyleManager theme properties based on diagram type
        const defaults = {
            fontSize: '14',
            fontFamily: "Inter, sans-serif",
            textColor: '#000000',
            fillColor: '#2196f3',
            strokeColor: '#1976d2',
            strokeWidth: '2',
            opacity: '1',
            fontWeight: 'normal',
            fontStyle: 'normal'
        };
        
        // Map node type to theme properties for each diagram type
        switch (diagramType) {
            case 'bubble_map':
                if (nodeType === 'topic') {
                    defaults.fillColor = theme.topicFill || '#1976d2';
                    defaults.textColor = theme.topicText || '#ffffff';
                    defaults.strokeColor = theme.topicStroke || '#000000';
                    defaults.strokeWidth = String(theme.topicStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontTopic || 20);
                } else if (nodeType === 'attribute') {
                    defaults.fillColor = theme.attributeFill || '#e3f2fd';
                    defaults.textColor = theme.attributeText || '#333333';
                    defaults.strokeColor = theme.attributeStroke || '#000000';
                    defaults.strokeWidth = String(theme.attributeStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontAttribute || 14);
                }
                break;
                
            case 'double_bubble_map':
                if (nodeType === 'centralTopic' || nodeType === 'center') {
                    // Central topic uses fontCentralTopic: 18 (matches renderer's fontTopic: 18)
                    defaults.fillColor = theme.centralTopicFill || '#1976d2';
                    defaults.textColor = theme.centralTopicText || '#ffffff';
                    defaults.strokeColor = theme.centralTopicStroke || '#000000';
                    defaults.strokeWidth = String(theme.centralTopicStrokeWidth || 3);
                    defaults.fontSize = String(theme.fontCentralTopic || 18); // 18px, matching renderer
                    defaults.fontWeight = 'bold'; // Central topic uses bold
                } else if (nodeType === 'leftTopic' || nodeType === 'left') {
                    // Renderer uses fontTopic: 18 and font-weight: 600 for left/right topics
                    defaults.fillColor = theme.leftTopicFill || '#1976d2';
                    defaults.textColor = theme.leftTopicText || '#ffffff';
                    defaults.strokeColor = theme.leftTopicStroke || '#000000';
                    defaults.strokeWidth = String(theme.leftTopicStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontTopic || 18); // Renderer default is 18, not 16
                    defaults.fontWeight = '600'; // Renderer uses 600 for left/right topics
                } else if (nodeType === 'rightTopic' || nodeType === 'right') {
                    // Renderer uses fontTopic: 18 and font-weight: 600 for left/right topics
                    defaults.fillColor = theme.rightTopicFill || '#1976d2';
                    defaults.textColor = theme.rightTopicText || '#ffffff';
                    defaults.strokeColor = theme.rightTopicStroke || '#000000';
                    defaults.strokeWidth = String(theme.rightTopicStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontTopic || 18); // Renderer default is 18, not 16
                    defaults.fontWeight = '600'; // Renderer uses 600 for left/right topics
                } else if (nodeType === 'similarity') {
                    // Similarities use simFill, simText, simStroke (blue border, not black)
                    defaults.fillColor = theme.simFill || theme.attributeFill || '#e3f2fd';
                    defaults.textColor = theme.simText || theme.attributeText || '#333333';
                    defaults.strokeColor = theme.simStroke || '#1976d2'; // Blue border, matching renderer
                    defaults.strokeWidth = String(theme.simStrokeWidth || theme.attributeStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontSim || 14); // Renderer default is 14
                    defaults.fontWeight = 'normal'; // Similarities use normal weight
                } else if (nodeType === 'left_difference' || nodeType === 'right_difference') {
                    // Differences use diffFill, diffText, diffStroke (blue border, not black)
                    defaults.fillColor = theme.diffFill || theme.attributeFill || '#e3f2fd';
                    defaults.textColor = theme.diffText || theme.attributeText || '#333333';
                    defaults.strokeColor = theme.diffStroke || '#1976d2'; // Blue border, matching renderer
                    defaults.strokeWidth = String(theme.diffStrokeWidth || theme.attributeStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontDiff || 14); // Renderer default is 14
                    defaults.fontWeight = 'normal'; // Differences use normal weight
                }
                break;
                
            case 'mindmap':
                if (nodeType === 'topic' || nodeType === 'centralTopic') {
                    defaults.fillColor = theme.centralTopicFill || '#1976d2';
                    defaults.textColor = theme.centralTopicText || '#ffffff';
                    defaults.strokeColor = theme.centralTopicStroke || '#0d47a1';
                    defaults.strokeWidth = String(theme.centralTopicStrokeWidth || 3);
                    defaults.fontSize = String(theme.fontTopic || 18);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for central topic
                } else if (nodeType === 'branch') {
                    defaults.fillColor = theme.branchFill || '#e3f2fd';
                    defaults.textColor = theme.branchText || '#333333';
                    defaults.strokeColor = theme.branchStroke || '#4e79a7';
                    defaults.strokeWidth = String(theme.branchStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontBranch || 16);
                    defaults.fontWeight = 'normal'; // Branches use normal weight
                } else if (nodeType === 'child') {
                    defaults.fillColor = theme.childFill || '#bbdefb';
                    defaults.textColor = theme.childText || '#333333';
                    defaults.strokeColor = theme.childStroke || '#90caf9';
                    defaults.strokeWidth = String(theme.childStrokeWidth || 1);
                    defaults.fontSize = String(theme.fontChild || 12);
                    defaults.fontWeight = 'normal'; // Children use normal weight
                }
                break;
                
            case 'brace_map':
                if (nodeType === 'topic') {
                    defaults.fillColor = theme.topicFill || '#1976d2';
                    defaults.textColor = theme.topicText || '#ffffff';
                    defaults.strokeColor = theme.topicStroke || '#0d47a1';
                    defaults.strokeWidth = String(theme.topicStrokeWidth || 3);
                    defaults.fontSize = String(theme.fontTopic || 18);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for topic
                } else if (nodeType === 'part') {
                    defaults.fillColor = theme.partFill || '#e3f2fd';
                    defaults.textColor = theme.partText || '#333333';
                    defaults.strokeColor = theme.partStroke || '#4e79a7';
                    defaults.strokeWidth = String(theme.partStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontPart || 16);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for parts
                } else if (nodeType === 'subpart') {
                    defaults.fillColor = theme.subpartFill || '#bbdefb';
                    defaults.textColor = theme.subpartText || '#333333';
                    defaults.strokeColor = theme.subpartStroke || '#90caf9';
                    defaults.strokeWidth = String(theme.subpartStrokeWidth || 1);
                    defaults.fontSize = String(theme.fontSubpart || 12);
                    defaults.fontWeight = 'normal'; // Subparts use normal weight
                }
                break;
                
            case 'tree_map':
                if (nodeType === 'topic' || nodeType === 'root') {
                    defaults.fillColor = theme.rootFill || '#1976d2';
                    defaults.textColor = theme.rootText || '#ffffff';
                    defaults.strokeColor = theme.rootStroke || '#0d47a1';
                    defaults.strokeWidth = String(theme.rootStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontRoot || 20);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for root
                } else if (nodeType === 'dimension') {
                    // Dimension nodes use branch styling
                    defaults.fillColor = theme.branchFill || '#e3f2fd';
                    defaults.textColor = theme.branchText || '#333333';
                    defaults.strokeColor = theme.branchStroke || '#1976d2';
                    defaults.strokeWidth = String(theme.branchStrokeWidth || 1.5);
                    defaults.fontSize = String(theme.fontBranch || 16);
                    defaults.fontWeight = 'normal'; // Dimensions use normal weight
                } else if (nodeType === 'category') {
                    defaults.fillColor = theme.branchFill || '#e3f2fd';
                    defaults.textColor = theme.branchText || '#333333';
                    defaults.strokeColor = theme.branchStroke || '#1976d2';
                    defaults.strokeWidth = String(theme.branchStrokeWidth || 1.5);
                    defaults.fontSize = String(theme.fontBranch || 16);
                    defaults.fontWeight = 'normal'; // Categories use normal weight
                } else if (nodeType === 'leaf') {
                    defaults.fillColor = theme.leafFill || '#ffffff';
                    defaults.textColor = theme.leafText || '#333333';
                    defaults.strokeColor = theme.leafStroke || '#c8d6e5';
                    defaults.strokeWidth = String(theme.leafStrokeWidth || 1);
                    defaults.fontSize = String(theme.fontLeaf || 14);
                    defaults.fontWeight = 'normal'; // Leaves use normal weight
                }
                break;
                
            case 'flow_map':
                if (nodeType === 'title') {
                    defaults.fillColor = theme.titleFill || '#1976d2';
                    defaults.textColor = theme.titleText || '#333333';
                    defaults.strokeColor = theme.titleStroke || '#0d47a1';
                    defaults.strokeWidth = String(theme.titleStrokeWidth || 3);
                    defaults.fontSize = String(theme.fontTitle || 20);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for title
                } else if (nodeType === 'step') {
                    defaults.fillColor = theme.stepFill || '#1976d2';
                    defaults.textColor = theme.stepText || '#ffffff';
                    defaults.strokeColor = theme.stepStroke || '#0d47a1';
                    defaults.strokeWidth = String(theme.stepStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontStep || 14);
                    defaults.fontWeight = 'normal'; // Steps use normal weight
                } else if (nodeType === 'substep') {
                    defaults.fillColor = theme.substepFill || '#e3f2fd';
                    defaults.textColor = theme.substepText || '#333333';
                    defaults.strokeColor = theme.substepStroke || '#1976d2';
                    defaults.strokeWidth = String(theme.substepStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontStep || 14);
                    defaults.fontWeight = 'normal'; // Substeps use normal weight
                }
                break;
                
            case 'multi_flow_map':
                if (nodeType === 'event') {
                    defaults.fillColor = theme.eventFill || '#1976d2';
                    defaults.textColor = theme.eventText || '#ffffff';
                    defaults.strokeColor = theme.eventStroke || '#0d47a1';
                    defaults.strokeWidth = String(theme.eventStrokeWidth || 3);
                    defaults.fontSize = String(theme.fontEvent || 18);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for event
                } else if (nodeType === 'cause') {
                    defaults.fillColor = theme.causeFill || '#e3f2fd';
                    defaults.textColor = theme.causeText || '#333333';
                    defaults.strokeColor = theme.causeStroke || '#1976d2';
                    defaults.strokeWidth = String(theme.causeStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontCause || 14);
                    defaults.fontWeight = 'normal'; // Causes use normal weight
                } else if (nodeType === 'effect') {
                    defaults.fillColor = theme.effectFill || '#e3f2fd';
                    defaults.textColor = theme.effectText || '#333333';
                    defaults.strokeColor = theme.effectStroke || '#1976d2';
                    defaults.strokeWidth = String(theme.effectStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontEffect || 14);
                    defaults.fontWeight = 'normal'; // Effects use normal weight
                }
                break;
                
            case 'concept_map':
                if (nodeType === 'topic' || nodeType === 'center') {
                    defaults.fillColor = theme.topicFill || '#e3f2fd';
                    defaults.textColor = theme.topicText || '#000000';
                    defaults.strokeColor = theme.topicStroke || '#35506b';
                    defaults.strokeWidth = String(theme.topicStrokeWidth || 3);
                    defaults.fontSize = String(theme.fontTopic || 18);
                    defaults.fontWeight = '600'; // Renderer uses 600 for topic
                } else if (nodeType === 'concept') {
                    defaults.fillColor = theme.conceptFill || '#e3f2fd';
                    defaults.textColor = theme.conceptText || '#333333';
                    defaults.strokeColor = theme.conceptStroke || '#4e79a7';
                    defaults.strokeWidth = String(theme.conceptStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontConcept || 14);
                    defaults.fontWeight = '400'; // Renderer uses 400 for concepts
                }
                break;
                
            case 'bridge_map':
                if (nodeType === 'left' || nodeType === 'right') {
                    // Bridge map pairs use firstPair styling
                    defaults.fillColor = theme.firstPairFill || '#1976d2';
                    defaults.textColor = theme.firstPairText || '#ffffff';
                    defaults.strokeColor = theme.firstPairStroke || '#0d47a1';
                    defaults.strokeWidth = String(theme.firstPairStrokeWidth || 2);
                    defaults.fontSize = String(theme.analogyFontSize || 14);
                    defaults.fontWeight = 'normal'; // Bridge map pairs use normal weight
                }
                break;
                
            case 'bubble_map':
                if (nodeType === 'topic' || nodeType === 'center') {
                    defaults.fillColor = theme.topicFill || '#1976d2';
                    defaults.textColor = theme.topicText || '#ffffff';
                    defaults.strokeColor = theme.topicStroke || '#000000';
                    defaults.strokeWidth = String(theme.topicStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontTopic || 20);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for topic
                } else if (nodeType === 'attribute') {
                    defaults.fillColor = theme.attributeFill || '#e3f2fd';
                    defaults.textColor = theme.attributeText || '#333333';
                    defaults.strokeColor = theme.attributeStroke || '#000000';
                    defaults.strokeWidth = String(theme.attributeStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontAttribute || 14);
                    defaults.fontWeight = 'normal'; // Attributes use normal weight
                }
                break;
                
            case 'circle_map':
                // Circle map has different stroke colors than bubble map
                if (nodeType === 'topic' || nodeType === 'center') {
                    defaults.fillColor = theme.topicFill || '#1976d2';
                    defaults.textColor = theme.topicText || '#ffffff';
                    defaults.strokeColor = theme.topicStroke || '#0d47a1'; // Darker blue, matching renderer
                    defaults.strokeWidth = String(theme.topicStrokeWidth || 3);
                    defaults.fontSize = String(theme.fontTopic || 20);
                    defaults.fontWeight = 'bold'; // Renderer uses bold for topic
                } else if (nodeType === 'context') {
                    // Circle map context nodes use blue stroke, not black
                    defaults.fillColor = theme.contextFill || theme.attributeFill || '#e3f2fd';
                    defaults.textColor = theme.contextText || theme.attributeText || '#333333';
                    defaults.strokeColor = theme.contextStroke || '#1976d2'; // Blue border, matching renderer
                    defaults.strokeWidth = String(theme.contextStrokeWidth || theme.attributeStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontContext || theme.fontAttribute || 14);
                    defaults.fontWeight = 'normal'; // Context nodes use normal weight
                }
                break;
                
            case 'flowchart':
                // Flowchart has specific node types: start, process, decision, end
                if (nodeType === 'start') {
                    defaults.fillColor = theme.startFill || '#4caf50';
                    defaults.textColor = theme.startText || '#ffffff';
                    defaults.strokeColor = theme.startStroke || '#388e3c';
                    defaults.strokeWidth = String(theme.startStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontNode || 14);
                    defaults.fontWeight = 'normal'; // Flowchart nodes use normal weight
                } else if (nodeType === 'process') {
                    defaults.fillColor = theme.processFill || '#2196f3';
                    defaults.textColor = theme.processText || '#ffffff';
                    defaults.strokeColor = theme.processStroke || '#1976d2';
                    defaults.strokeWidth = String(theme.processStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontNode || 14);
                    defaults.fontWeight = 'normal'; // Flowchart nodes use normal weight
                } else if (nodeType === 'decision') {
                    defaults.fillColor = theme.decisionFill || '#ff9800';
                    defaults.textColor = theme.decisionText || '#ffffff';
                    defaults.strokeColor = theme.decisionStroke || '#f57c00';
                    defaults.strokeWidth = String(theme.decisionStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontNode || 14);
                    defaults.fontWeight = 'normal'; // Flowchart nodes use normal weight
                } else if (nodeType === 'end') {
                    defaults.fillColor = theme.endFill || '#f44336';
                    defaults.textColor = theme.endText || '#ffffff';
                    defaults.strokeColor = theme.endStroke || '#d32f2f';
                    defaults.strokeWidth = String(theme.endStrokeWidth || 2);
                    defaults.fontSize = String(theme.fontNode || 14);
                    defaults.fontWeight = 'normal'; // Flowchart nodes use normal weight
                }
                break;
                
            // Thinking tools use mindmap structure (topic, branch, child)
            case 'factor_analysis':
            case 'three_position_analysis':
            case 'perspective_analysis':
            case 'goal_analysis':
            case 'possibility_analysis':
            case 'result_analysis':
            case 'five_w_one_h':
            case 'whwm_analysis':
            case 'four_quadrant':
                // Thinking tools use the same structure as mindmap, so use mindmap theme
                // Get mindmap theme from StyleManager (thinking tools don't have their own themes)
                const styleManagerForThinking = window.styleManager;
                const mindmapTheme = styleManagerForThinking?.getDefaultTheme('mindmap') || {};
                if (nodeType === 'topic' || nodeType === 'centralTopic') {
                    defaults.fillColor = mindmapTheme.centralTopicFill || '#1976d2';
                    defaults.textColor = mindmapTheme.centralTopicText || '#ffffff';
                    defaults.strokeColor = mindmapTheme.centralTopicStroke || '#0d47a1';
                    defaults.strokeWidth = String(mindmapTheme.centralTopicStrokeWidth || 3);
                    defaults.fontSize = String(mindmapTheme.fontTopic || 18);
                    defaults.fontWeight = 'bold'; // Central topic uses bold (same as mindmap)
                } else if (nodeType === 'branch') {
                    defaults.fillColor = mindmapTheme.branchFill || '#e3f2fd';
                    defaults.textColor = mindmapTheme.branchText || '#333333';
                    defaults.strokeColor = mindmapTheme.branchStroke || '#4e79a7';
                    defaults.strokeWidth = String(mindmapTheme.branchStrokeWidth || 2);
                    defaults.fontSize = String(mindmapTheme.fontBranch || 16);
                    defaults.fontWeight = 'normal'; // Branches use normal weight (same as mindmap)
                } else if (nodeType === 'child') {
                    defaults.fillColor = mindmapTheme.childFill || '#bbdefb';
                    defaults.textColor = mindmapTheme.childText || '#333333';
                    defaults.strokeColor = mindmapTheme.childStroke || '#90caf9';
                    defaults.strokeWidth = String(mindmapTheme.childStrokeWidth || 1);
                    defaults.fontSize = String(mindmapTheme.fontChild || 12);
                    defaults.fontWeight = 'normal'; // Children use normal weight (same as mindmap)
                }
                break;
        }
        
        return defaults;
    }
    
    /**
     * Apply defaults to a specific node
     * @param {string} nodeId - Node ID
     * @param {object} defaults - Default properties
     */
    applyDefaultsToNode(nodeId, defaults) {
        if (!defaults) return;
        
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (nodeElement.empty()) return;
        
        // Check if node is currently selected (has selection highlight)
        const isCurrentlySelected = nodeElement.classed('selected');
        
        // Apply shape properties
        if (defaults.fillColor) {
            nodeElement.attr('fill', defaults.fillColor);
        }
        if (defaults.strokeColor) {
            // Apply stroke directly
            nodeElement.attr('stroke', defaults.strokeColor);
            // Also update data-original-stroke so correct color is tracked for deselection
            if (isCurrentlySelected) {
                nodeElement.attr('data-original-stroke', defaults.strokeColor);
            }
        }
        if (defaults.strokeWidth) {
            // Apply via inline style (takes precedence, works in line mode)
            // This ensures changes work even when line mode has set inline styles
            nodeElement.style('stroke-width', defaults.strokeWidth + 'px');
            // Also update attribute for when inline style is cleared (line mode disabled)
            nodeElement.attr('stroke-width', defaults.strokeWidth);
            // Always update data-original-stroke-width for line mode restoration
            nodeElement.attr('data-original-stroke-width', defaults.strokeWidth);
        }
        
        // Find and apply text properties
        const textElements = this.findTextElementsForNode(nodeId, nodeElement);
        if (!textElements.empty()) {
            if (defaults.fontSize) {
                // Ensure font-size is applied correctly (SVG accepts number or number with unit)
                // Convert to number if it's a string, or use as-is if it's already a number
                const fontSize = typeof defaults.fontSize === 'string' 
                    ? parseFloat(defaults.fontSize) || parseInt(defaults.fontSize, 10) || 14
                    : defaults.fontSize;
                textElements.attr('font-size', fontSize);
            }
            if (defaults.fontFamily) {
                textElements.attr('font-family', defaults.fontFamily);
            }
            if (defaults.textColor) {
                textElements.attr('fill', defaults.textColor);
            }
            // Apply font-weight from defaults (or 'normal' if not specified)
            if (defaults.fontWeight) {
                textElements.attr('font-weight', defaults.fontWeight);
            } else {
                textElements.attr('font-weight', 'normal');
            }
            // Apply font-style from defaults (or 'normal' if not specified)
            if (defaults.fontStyle) {
                textElements.attr('font-style', defaults.fontStyle);
            } else {
                textElements.attr('font-style', 'normal');
            }
            // Reset text decoration to none
            textElements.style('text-decoration', 'none');
            textElements.attr('text-decoration', 'none');
            
            // Remove strikethrough lines
            textElements.each((d, i, nodes) => {
                const textEl = d3.select(nodes[i]);
                this.applyStrikethroughLine(textEl, false);
            });
        }
    }
    
    /**
     * Apply defaults to UI inputs
     * @param {object} defaults - Default properties
     */
    applyDefaultsToUI(defaults) {
        if (!defaults || !this.toolbarManager) return;
        
        if (this.toolbarManager.propFontSize) this.toolbarManager.propFontSize.value = parseInt(defaults.fontSize || 14);
        if (this.toolbarManager.propFontFamily) this.toolbarManager.propFontFamily.value = defaults.fontFamily || "Inter, sans-serif";
        if (this.toolbarManager.propTextColor) this.toolbarManager.propTextColor.value = defaults.textColor || '#000000';
        if (this.toolbarManager.propTextColorHex) this.toolbarManager.propTextColorHex.value = (defaults.textColor || '#000000').toUpperCase();
        if (this.toolbarManager.propFillColor) this.toolbarManager.propFillColor.value = defaults.fillColor || '#2196f3';
        if (this.toolbarManager.propFillColorHex) this.toolbarManager.propFillColorHex.value = (defaults.fillColor || '#2196f3').toUpperCase();
        if (this.toolbarManager.propStrokeColor) this.toolbarManager.propStrokeColor.value = defaults.strokeColor || '#1976d2';
        if (this.toolbarManager.propStrokeColorHex) this.toolbarManager.propStrokeColorHex.value = (defaults.strokeColor || '#1976d2').toUpperCase();
        if (this.toolbarManager.propStrokeWidth) this.toolbarManager.propStrokeWidth.value = parseFloat(defaults.strokeWidth || 2);
        if (this.toolbarManager.strokeWidthValue) this.toolbarManager.strokeWidthValue.textContent = `${defaults.strokeWidth || 2}px`;
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
            fontFamily: "Inter, sans-serif",
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
     * Apply only text styles (font properties) without touching shape properties
     * This is used by toggle methods to avoid interfering with selection highlight
     */
    applyTextStylesOnly() {
        if (!this.toolbarManager) {
            this.logger.warn('NodePropertyOperationsManager', 'applyTextStylesOnly: toolbarManager not available');
            return;
        }
        
        const selectedNodes = this.getSelectedNodes();
        if (selectedNodes.length === 0) {
            this.logger.debug('NodePropertyOperationsManager', 'applyTextStylesOnly: No nodes selected');
            return;
        }
        
        const textProperties = {
            fontSize: this.toolbarManager.propFontSize?.value,
            fontFamily: this.toolbarManager.propFontFamily?.value,
            textColor: this.toolbarManager.propTextColor?.value,
            bold: this.toolbarManager.propBold?.classList.contains('active'),
            italic: this.toolbarManager.propItalic?.classList.contains('active'),
            underline: this.toolbarManager.propUnderline?.classList.contains('active'),
            strikethrough: this.toolbarManager.propStrikethrough?.classList.contains('active')
        };
        
        // VERBOSE LOGGING: Track function entry
        this.logger.info('NodePropertyOperationsManager', 'applyTextStylesOnly called', {
            selectedNodesCount: selectedNodes.length,
            selectedNodes,
            textProperties,
            diagramType: this.editor?.diagramType
        });
        
        // Apply ONLY text properties to selected nodes (skip shape properties like stroke/fill)
        selectedNodes.forEach(nodeId => {
            const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (nodeElement.empty()) {
                this.logger.warn('NodePropertyOperationsManager', 'Node element not found in DOM', {
                    nodeId,
                    diagramType: this.editor?.diagramType
                });
                return;
            }
            
            // Find text elements for this node using diagram-specific smart finder
            // Uses knowledge of each diagram's structure instead of fallbacks
            const textElements = this.findTextElementsForNode(nodeId, nodeElement);
            
            // Apply only text styling properties (NOT shape properties)
            if (textElements.empty()) {
                // VERBOSE LOGGING: Text elements not found
                this.logger.warn('NodePropertyOperationsManager', 'Cannot apply text styles - no text elements found', {
                    nodeId,
                    diagramType: this.editor?.diagramType,
                    nodeElementTag: nodeElement.node()?.tagName,
                    nodeElementId: nodeElement.attr('data-node-id'),
                    nodeElementType: nodeElement.attr('data-node-type')
                });
            } else {
                if (textProperties.fontSize) {
                    textElements.attr('font-size', textProperties.fontSize);
                }
                if (textProperties.fontFamily) {
                    textElements.attr('font-family', textProperties.fontFamily);
                }
                if (textProperties.textColor) {
                    textElements.attr('fill', textProperties.textColor);
                }
                textElements.attr('font-weight', textProperties.bold ? 'bold' : 'normal');
                textElements.attr('font-style', textProperties.italic ? 'italic' : 'normal');
                
                // Apply text-decoration for underline (CSS style works well)
                const decorations = [];
                if (textProperties.underline) decorations.push('underline');
                const underlineValue = decorations.length > 0 ? decorations.join(' ') : 'none';
                textElements.style('text-decoration', underlineValue);
                textElements.attr('text-decoration', underlineValue);
                
                // Apply strikethrough using line elements (workaround for poor SVG text-decoration support)
                // SVG text-decoration has very poor browser support for line-through, especially in flow maps
                this.logger.info('NodePropertyOperationsManager', 'Processing strikethrough for text elements', {
                    nodeId,
                    textElementsCount: textElements.size(),
                    strikethroughEnabled: textProperties.strikethrough
                });
                textElements.each((d, i, nodes) => {
                    const textEl = d3.select(nodes[i]);
                    this.applyStrikethroughLine(textEl, textProperties.strikethrough);
                });
            }
        });
        
        // Save to history silently
        this.editor?.saveToHistory('update_text_styles', { 
            nodes: selectedNodes, 
            properties: textProperties 
        });
    }
    
    /**
     * Toggle bold
     * EXTRACTED FROM: toolbar-manager.js lines 1017-1019
     * NOTE: Uses applyTextStylesOnly to avoid interfering with selection
     */
    toggleBold() {
        if (!this.toolbarManager) return;
        this.toolbarManager.propBold.classList.toggle('active');
        // Apply ONLY text styles - don't touch shape properties to preserve selection highlight
        this.applyTextStylesOnly();
    }
    
    /**
     * Toggle italic
     * EXTRACTED FROM: toolbar-manager.js lines 1024-1026
     * NOTE: Uses applyTextStylesOnly to avoid interfering with selection
     */
    toggleItalic() {
        if (!this.toolbarManager) return;
        this.toolbarManager.propItalic.classList.toggle('active');
        // Apply ONLY text styles - don't touch shape properties to preserve selection highlight
        this.applyTextStylesOnly();
    }
    
    /**
     * Toggle underline
     * EXTRACTED FROM: toolbar-manager.js lines 1031-1033
     * NOTE: Uses applyTextStylesOnly to avoid interfering with selection
     */
    toggleUnderline() {
        if (!this.toolbarManager) return;
        this.toolbarManager.propUnderline.classList.toggle('active');
        // Apply ONLY text styles - don't touch shape properties to preserve selection highlight
        this.applyTextStylesOnly();
    }
    
    /**
     * Toggle strikethrough
     * NOTE: Uses applyTextStylesOnly to avoid interfering with selection
     */
    toggleStrikethrough() {
        if (!this.toolbarManager) {
            this.logger.warn('NodePropertyOperationsManager', 'Cannot toggle strikethrough - toolbarManager not available');
            return;
        }
        
        const wasActive = this.toolbarManager.propStrikethrough.classList.contains('active');
        this.toolbarManager.propStrikethrough.classList.toggle('active');
        const isNowActive = this.toolbarManager.propStrikethrough.classList.contains('active');
        
        // VERBOSE LOGGING: Track toggle action
        const selectedNodes = this.getSelectedNodes();
        this.logger.info('NodePropertyOperationsManager', 'Toggling strikethrough', {
            wasActive,
            isNowActive,
            selectedNodesCount: selectedNodes.length,
            selectedNodes,
            diagramType: this.editor?.diagramType
        });
        
        // Apply ONLY text styles - don't touch shape properties to preserve selection highlight
        this.applyTextStylesOnly();
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
            
            // UNIFIED: For all diagram types, preserve node dimensions when emptying
            nodeIds.forEach(nodeId => {
                // Find the shape element to get current dimensions
                const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
                if (shapeElement.empty()) {
                    this.logger.warn('NodePropertyOperationsManager', `Shape not found for nodeId: ${nodeId}`);
                    return;
                }
                
                // Get current dimensions from the shape element
                // Support both rect (width/height) and circle (r) elements
                let currentWidth = 0;
                let currentHeight = 0;
                let currentRadius = 0;
                
                const tagName = shapeElement.node().tagName.toLowerCase();
                if (tagName === 'rect') {
                    currentWidth = parseFloat(shapeElement.attr('width')) || 0;
                    currentHeight = parseFloat(shapeElement.attr('height')) || 0;
                } else if (tagName === 'circle' || tagName === 'ellipse') {
                    currentRadius = parseFloat(shapeElement.attr('r')) || parseFloat(shapeElement.attr('ry')) || 0;
                    // For circles, use radius * 2 for both width and height
                    currentWidth = currentRadius * 2;
                    currentHeight = currentRadius * 2;
                } else {
                    // Try to get bounding box as fallback
                    try {
                        const bbox = shapeElement.node().getBBox();
                        currentWidth = bbox.width || 0;
                        currentHeight = bbox.height || 0;
                    } catch (e) {
                        this.logger.debug('NodePropertyOperationsManager', `Could not get bbox for ${nodeId}`, e);
                    }
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
                    
                    // Update the text to empty string with preserved dimensions
                    if (this.editor && typeof this.editor.updateNodeText === 'function') {
                        // Store dimensions in data attributes for the updateNode operation to pick up
                        if (currentWidth > 0 && currentHeight > 0) {
                            shapeElement.attr('data-preserved-width', currentWidth);
                            shapeElement.attr('data-preserved-height', currentHeight);
                            if (currentRadius > 0) {
                                shapeElement.attr('data-preserved-radius', currentRadius);
                            }
                        }
                        
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
            const currentSelectedNodes = this.getSelectedNodes();
            if (currentSelectedNodes.length > 0) {
                this.toolbarManager.loadNodeProperties(currentSelectedNodes[0]);
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
