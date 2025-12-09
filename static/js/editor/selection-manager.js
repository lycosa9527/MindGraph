/**
 * SelectionManager - Handles node selection and visual feedback
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class SelectionManager {
    constructor() {
        this.selectedNodes = new Set();
        this.selectionBox = null;
        this.isSelecting = false;
        this.selectionStart = null;
        this.onSelectionChange = null;
    }
    
    /**
     * Select a single node
     * @param {string} nodeId - ID of the node to select
     */
    selectNode(nodeId) {
        this.selectedNodes.add(nodeId);
        this.updateVisualSelection(nodeId, true);
        this.notifySelectionChange();
    }
    
    /**
     * Deselect a specific node
     * @param {string} nodeId - ID of the node to deselect
     */
    deselectNode(nodeId) {
        this.selectedNodes.delete(nodeId);
        this.updateVisualSelection(nodeId, false);
        this.notifySelectionChange();
    }
    
    /**
     * Toggle selection state of a node
     * @param {string} nodeId - ID of the node to toggle
     */
    toggleNodeSelection(nodeId) {
        if (this.selectedNodes.has(nodeId)) {
            this.deselectNode(nodeId);
        } else {
            this.selectNode(nodeId);
        }
    }
    
    /**
     * Clear all selections
     */
    clearSelection() {
        this.selectedNodes.forEach(nodeId => {
            this.updateVisualSelection(nodeId, false);
        });
        this.selectedNodes.clear();
        this.notifySelectionChange();
    }
    
    /**
     * Update visual selection indicator for a node
     * @param {string} nodeId - ID of the node
     * @param {boolean} isSelected - Whether the node is selected
     */
    updateVisualSelection(nodeId, isSelected) {
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        
        if (nodeElement.empty()) {
            return;
        }
        
        if (isSelected) {
            // Store original stroke attributes to restore later
            const originalStroke = nodeElement.attr('stroke');
            const originalStrokeWidth = nodeElement.attr('stroke-width');
            
            if (!nodeElement.attr('data-original-stroke')) {
                nodeElement
                    .attr('data-original-stroke', originalStroke || 'none')
                    .attr('data-original-stroke-width', originalStrokeWidth || '0');
            }
            
            // Apply selection highlight with contrasting blue/purple color
            nodeElement
                .classed('selected', true)
                .attr('stroke', '#667eea')  // Blue/purple from app theme
                .attr('stroke-width', 4)
                .style('filter', 'drop-shadow(0 0 12px rgba(102, 126, 234, 0.7))');
        } else {
            // Get stored original stroke (if exists)
            const storedOriginalStroke = nodeElement.attr('data-original-stroke');
            const storedOriginalStrokeWidth = nodeElement.attr('data-original-stroke-width');
            
            // Remove selection styling
            nodeElement
                .classed('selected', false)
                .style('filter', null);
            
            // Only restore stroke if we have stored original values
            // This prevents destroying strokes on re-rendered elements that don't have
            // the data-original-stroke attribute (they already have correct strokes from renderer)
            if (storedOriginalStroke !== null) {
                // Restore original stroke if it was a valid stroke, otherwise remove
                if (storedOriginalStroke && storedOriginalStroke !== 'none') {
                nodeElement
                        .attr('stroke', storedOriginalStroke)
                        .attr('stroke-width', storedOriginalStrokeWidth);
            } else {
                nodeElement
                    .attr('stroke', null)
                    .attr('stroke-width', null);
            }
            
            // Clean up data attributes
            nodeElement
                .attr('data-original-stroke', null)
                .attr('data-original-stroke-width', null);
            }
            // If storedOriginalStroke is null (element was re-rendered and never had selection applied),
            // don't touch the stroke at all - it's already correct from the renderer
        }
    }
    
    /**
     * Start box selection
     * @param {Event} event - Mouse event
     */
    startBoxSelection(event) {
        this.isSelecting = true;
        this.selectionStart = { x: event.clientX, y: event.clientY };
        
        const container = document.getElementById('d3-container');
        const rect = container.getBoundingClientRect();
        
        this.selectionBox = d3.select('#d3-container svg')
            .append('rect')
            .attr('class', 'selection-box')
            .attr('x', event.clientX - rect.left)
            .attr('y', event.clientY - rect.top)
            .attr('width', 0)
            .attr('height', 0)
            .style('fill', 'rgba(100, 150, 255, 0.1)')
            .style('stroke', '#6496ff')
            .style('stroke-width', 2)
            .style('stroke-dasharray', '5,5');
    }
    
    /**
     * Update box selection during drag
     * @param {Event} event - Mouse event
     */
    updateBoxSelection(event) {
        if (!this.isSelecting || !this.selectionBox) return;
        
        const container = document.getElementById('d3-container');
        const rect = container.getBoundingClientRect();
        
        const currentX = event.clientX - rect.left;
        const currentY = event.clientY - rect.top;
        const startX = this.selectionStart.x - rect.left;
        const startY = this.selectionStart.y - rect.top;
        
        const width = currentX - startX;
        const height = currentY - startY;
        
        this.selectionBox
            .attr('width', Math.abs(width))
            .attr('height', Math.abs(height))
            .attr('x', width < 0 ? currentX : startX)
            .attr('y', height < 0 ? currentY : startY);
    }
    
    /**
     * End box selection
     */
    endBoxSelection() {
        if (!this.isSelecting) return;
        
        this.isSelecting = false;
        
        if (this.selectionBox) {
            const bounds = this.getSelectionBounds();
            this.selectNodesInBounds(bounds);
            this.selectionBox.remove();
            this.selectionBox = null;
        }
    }
    
    /**
     * Select all nodes within bounds
     * @param {Object} bounds - Selection bounds
     */
    selectNodesInBounds(bounds) {
        const container = document.getElementById('d3-container');
        const containerBounds = container.getBoundingClientRect();
        
        d3.selectAll('[data-node-id]').each((d, i, nodes) => {
            const node = nodes[i];
            const nodeBounds = node.getBoundingClientRect();
            
            const nodeX = nodeBounds.left - containerBounds.left;
            const nodeY = nodeBounds.top - containerBounds.top;
            
            if (nodeX >= bounds.x && nodeX <= bounds.x + bounds.width &&
                nodeY >= bounds.y && nodeY <= bounds.y + bounds.height) {
                
                const nodeId = node.getAttribute('data-node-id');
                if (nodeId) {
                    this.selectNode(nodeId);
                }
            }
        });
    }
    
    /**
     * Get selection bounds
     * @returns {Object} Bounds object
     */
    getSelectionBounds() {
        if (!this.selectionBox) return null;
        
        return {
            x: parseFloat(this.selectionBox.attr('x')),
            y: parseFloat(this.selectionBox.attr('y')),
            width: parseFloat(this.selectionBox.attr('width')),
            height: parseFloat(this.selectionBox.attr('height'))
        };
    }
    
    /**
     * Get selected node IDs
     * @returns {Set} Set of selected node IDs
     */
    getSelectedNodes() {
        return this.selectedNodes;
    }
    
    /**
     * Check if a node is selected
     * @param {string} nodeId - ID of the node
     * @returns {boolean} True if selected
     */
    isNodeSelected(nodeId) {
        return this.selectedNodes.has(nodeId);
    }
    
    /**
     * Notify listeners of selection change
     */
    notifySelectionChange() {
        if (this.onSelectionChange) {
            this.onSelectionChange(Array.from(this.selectedNodes));
        }
    }
    
    /**
     * Set selection change callback
     * @param {Function} callback - Callback function
     */
    setSelectionChangeCallback(callback) {
        this.onSelectionChange = callback;
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.SelectionManager = SelectionManager;
}

