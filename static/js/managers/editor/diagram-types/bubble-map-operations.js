/**
 * Bubble Map Operations
 * =====================
 * 
 * Handles add/delete/update operations specific to Bubble Maps.
 * Manages attribute nodes around a central topic.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class BubbleMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Bubble map configuration
        this.nodeType = 'attribute';
        this.arrayField = 'attributes';
        
        this.logger.info('BubbleMapOperations', 'Bubble Map Operations initialized');
    }
    
    /**
     * Add a new attribute node to Bubble Map
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.attributes)) {
            this.logger.error('BubbleMapOperations', 'Invalid bubble map spec');
            return null;
        }
        
        // Get language for new node text
        const newAttrText = window.languageManager?.translate('newAttribute') || 'New Attribute';
        
        // Add new attribute item
        spec.attributes.push(newAttrText);
        
        this.logger.debug('BubbleMapOperations', 'Added new attribute node', {
            attributeCount: spec.attributes.length,
            newText: newAttrText
        });
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'bubble_map',
            nodeType: 'attribute',
            nodeIndex: spec.attributes.length - 1,
            spec
        });
        
        // Emit operation completed for history
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'add_node',
            snapshot: JSON.parse(JSON.stringify(spec))
        });
        
        return spec;
    }
    
    /**
     * Delete selected nodes from Bubble Map
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.attributes)) {
            this.logger.error('BubbleMapOperations', 'Invalid bubble map spec');
            return null;
        }
        
        // Collect indices to delete and check for main topic
        const indicesToDelete = [];
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                
                if (nodeType === 'attribute') {
                    const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
                    if (!isNaN(arrayIndex)) {
                        indicesToDelete.push(arrayIndex);
                    }
                } else if (nodeType === 'topic') {
                    attemptedMainTopicDelete = true;
                }
            }
        });
        
        // Warn if trying to delete main topic
        if (attemptedMainTopicDelete) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Main topic node cannot be deleted',
                type: 'warning'
            });
        }
        
        // If no valid nodes to delete, return early
        if (indicesToDelete.length === 0) {
            return spec;
        }
        
        // Sort indices in descending order to delete from end to start
        indicesToDelete.sort((a, b) => b - a);
        
        // Remove from spec
        indicesToDelete.forEach(index => {
            spec.attributes.splice(index, 1);
        });
        
        this.logger.debug('BubbleMapOperations', 'Deleted attribute nodes', {
            deletedCount: indicesToDelete.length,
            remainingCount: spec.attributes.length
        });
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'bubble_map',
            nodeType: 'attribute',
            deletedIndices: indicesToDelete,
            spec
        });
        
        // Emit operation completed for history
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'delete_nodes',
            snapshot: JSON.parse(JSON.stringify(spec))
        });
        
        return spec;
    }
    
    /**
     * Update a node in Bubble Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec || !Array.isArray(spec.attributes)) {
            this.logger.error('BubbleMapOperations', 'Invalid bubble map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('BubbleMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        
        // Initialize node dimensions metadata if it doesn't exist
        if (!spec._node_dimensions) {
            spec._node_dimensions = {};
        }
        
        if (nodeType === 'attribute') {
            // Update attribute node
            const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
            if (!isNaN(arrayIndex) && arrayIndex < spec.attributes.length) {
                if (updates.text !== undefined) {
                    // Check if we should preserve dimensions (when emptying node)
                    const preservedWidth = shapeElement.attr('data-preserved-width');
                    const preservedHeight = shapeElement.attr('data-preserved-height');
                    const preservedRadius = shapeElement.attr('data-preserved-radius');
                    
                    if ((preservedWidth && preservedHeight || preservedRadius) && updates.text === '') {
                        // Store preserved dimensions for this node
                        const nodeKey = `attribute-${arrayIndex}`;
                        spec._node_dimensions[nodeKey] = {};
                        if (preservedWidth && preservedHeight) {
                            spec._node_dimensions[nodeKey].w = parseFloat(preservedWidth);
                            spec._node_dimensions[nodeKey].h = parseFloat(preservedHeight);
                        }
                        if (preservedRadius) {
                            spec._node_dimensions[nodeKey].r = parseFloat(preservedRadius);
                        }
                        this.logger.debug('BubbleMapOperations', 'Preserved dimensions for empty attribute node', {
                            nodeKey,
                            dimensions: spec._node_dimensions[nodeKey]
                        });
                    }
                    
                    spec.attributes[arrayIndex] = updates.text;
                }
            }
        } else if (nodeType === 'topic') {
            // Update main topic
            if (updates.text !== undefined) {
                // Check if we should preserve dimensions (when emptying node)
                const preservedWidth = shapeElement.attr('data-preserved-width');
                const preservedHeight = shapeElement.attr('data-preserved-height');
                const preservedRadius = shapeElement.attr('data-preserved-radius');
                
                if ((preservedWidth && preservedHeight || preservedRadius) && updates.text === '') {
                    // Store preserved dimensions for topic
                    spec._node_dimensions['topic'] = {};
                    if (preservedWidth && preservedHeight) {
                        spec._node_dimensions['topic'].w = parseFloat(preservedWidth);
                        spec._node_dimensions['topic'].h = parseFloat(preservedHeight);
                    }
                    if (preservedRadius) {
                        spec._node_dimensions['topic'].r = parseFloat(preservedRadius);
                    }
                    this.logger.debug('BubbleMapOperations', 'Preserved dimensions for empty topic node');
                }
                
                spec.topic = updates.text;
            }
        }
        
        this.logger.debug('BubbleMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'bubble_map',
            nodeId,
            nodeType,
            updates,
            spec
        });
        
        // Emit operation completed for history
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'update_node',
            snapshot: JSON.parse(JSON.stringify(spec))
        });
        
        return spec;
    }
    
    /**
     * Save custom position for a node (free-form positioning)
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID (e.g., 'attribute_0')
     * @param {number} x - X coordinate
     * @param {number} y - Y coordinate
     * @returns {Object} Updated spec
     */
    saveCustomPosition(spec, nodeId, x, y) {
        if (!spec) {
            this.logger.error('BubbleMapOperations', 'Invalid spec');
            return null;
        }
        
        // Initialize _customPositions if it doesn't exist
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        
        // Save position
        spec._customPositions[nodeId] = { x, y };
        
        this.logger.debug('BubbleMapOperations', 'Saved custom position', {
            nodeId,
            x,
            y
        });
        
        // Emit position saved event
        this.eventBus.emit('diagram:position_saved', {
            diagramType: 'bubble_map',
            nodeId,
            position: { x, y },
            spec
        });
        
        // Emit operation completed for history
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'save_custom_position',
            snapshot: JSON.parse(JSON.stringify(spec)),
            data: {
                nodeId,
                x,
                y
            }
        });
        
        return spec;
    }
    
    /**
     * Clear all custom positions (reset to auto-layout)
     * @param {Object} spec - Current diagram spec
     * @returns {Object} Updated spec
     */
    clearCustomPositions(spec) {
        if (!spec) {
            this.logger.error('BubbleMapOperations', 'Invalid spec');
            return null;
        }
        
        // Clear custom positions
        delete spec._customPositions;
        
        this.logger.debug('BubbleMapOperations', 'Cleared custom positions');
        
        // Emit positions cleared event
        this.eventBus.emit('diagram:positions_cleared', {
            diagramType: 'bubble_map',
            spec
        });
        
        // Emit operation completed for history
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'clear_custom_positions',
            snapshot: JSON.parse(JSON.stringify(spec))
        });
        
        return spec;
    }
    
    /**
     * Validate Bubble Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!spec.topic || typeof spec.topic !== 'string') {
            this.logger.warn('BubbleMapOperations', 'Invalid or missing topic');
            return false;
        }
        
        if (!Array.isArray(spec.attributes)) {
            this.logger.warn('BubbleMapOperations', 'Invalid or missing attributes array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('BubbleMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.BubbleMapOperations = BubbleMapOperations;



