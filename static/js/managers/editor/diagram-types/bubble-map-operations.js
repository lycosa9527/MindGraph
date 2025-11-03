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
        
        if (nodeType === 'attribute') {
            // Update attribute node
            const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
            if (!isNaN(arrayIndex) && arrayIndex < spec.attributes.length) {
                if (updates.text !== undefined) {
                    spec.attributes[arrayIndex] = updates.text;
                }
            }
        } else if (nodeType === 'topic') {
            // Update main topic
            if (updates.text !== undefined) {
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



