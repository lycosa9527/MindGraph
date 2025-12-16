/**
 * Circle Map Operations
 * =====================
 * 
 * Handles add/delete/update operations specific to Circle Maps.
 * Manages context nodes around a central topic.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class CircleMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Circle map configuration
        this.nodeType = 'context';
        this.arrayField = 'context';
        
        this.logger.info('CircleMapOperations', 'Circle Map Operations initialized');
    }
    
    /**
     * Add a new context node to Circle Map
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.context)) {
            this.logger.error('CircleMapOperations', 'Invalid circle map spec');
            return null;
        }
        
        // Get language for new node text
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        const newContextText = lang === 'zh' ? '新联想' : 'New Context';
        
        // Add new context item
        spec.context.push(newContextText);
        
        this.logger.debug('CircleMapOperations', 'Added new context node', {
            contextCount: spec.context.length,
            newText: newContextText
        });
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'circle_map',
            nodeType: 'context',
            nodeIndex: spec.context.length - 1,
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
     * Delete selected nodes from Circle Map
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.context)) {
            this.logger.error('CircleMapOperations', 'Invalid circle map spec');
            return null;
        }
        
        // Collect indices to delete and check for main topic
        const indicesToDelete = [];
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                
                if (nodeType === 'context') {
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
            spec.context.splice(index, 1);
        });
        
        this.logger.debug('CircleMapOperations', 'Deleted context nodes', {
            deletedCount: indicesToDelete.length,
            remainingCount: spec.context.length
        });
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'circle_map',
            nodeType: 'context',
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
     * Update a node in Circle Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec || !Array.isArray(spec.context)) {
            this.logger.error('CircleMapOperations', 'Invalid circle map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('CircleMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        
        // Initialize node dimensions metadata if it doesn't exist
        if (!spec._node_dimensions) {
            spec._node_dimensions = {};
        }
        
        this.logger.debug('CircleMapOperations', 'Updating node', {
            nodeId,
            nodeType,
            updates,
            hasTextUpdate: updates.text !== undefined
        });
        
        if (nodeType === 'context') {
            // Update context node
            const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
            if (!isNaN(arrayIndex) && arrayIndex < spec.context.length) {
                if (updates.text !== undefined) {
                    // Check if we should preserve dimensions (when emptying node)
                    const preservedWidth = shapeElement.attr('data-preserved-width');
                    const preservedHeight = shapeElement.attr('data-preserved-height');
                    const preservedRadius = shapeElement.attr('data-preserved-radius');
                    
                    if ((preservedWidth && preservedHeight || preservedRadius) && updates.text === '') {
                        const nodeKey = `context-${arrayIndex}`;
                        spec._node_dimensions[nodeKey] = {};
                        if (preservedWidth && preservedHeight) {
                            spec._node_dimensions[nodeKey].w = parseFloat(preservedWidth);
                            spec._node_dimensions[nodeKey].h = parseFloat(preservedHeight);
                        }
                        if (preservedRadius) {
                            spec._node_dimensions[nodeKey].r = parseFloat(preservedRadius);
                        }
                        this.logger.debug('CircleMapOperations', 'Preserved dimensions for empty context node', {
                            nodeKey,
                            dimensions: spec._node_dimensions[nodeKey]
                        });
                    }
                    
                    spec.context[arrayIndex] = updates.text;
                    this.logger.debug('CircleMapOperations', 'Updated context node', {
                        arrayIndex,
                        newText: updates.text
                    });
                }
            } else {
                this.logger.warn('CircleMapOperations', 'Invalid array index for context node', {
                    arrayIndex,
                    contextLength: spec.context.length
                });
            }
        } else if (nodeType === 'topic' || nodeType === 'center') {
            // Update main topic (renderer uses both 'topic' and 'center' for topic node)
            if (updates.text !== undefined) {
                // Check if we should preserve dimensions (when emptying node)
                const preservedWidth = shapeElement.attr('data-preserved-width');
                const preservedHeight = shapeElement.attr('data-preserved-height');
                const preservedRadius = shapeElement.attr('data-preserved-radius');
                
                if ((preservedWidth && preservedHeight || preservedRadius) && updates.text === '') {
                    spec._node_dimensions['topic'] = {};
                    if (preservedWidth && preservedHeight) {
                        spec._node_dimensions['topic'].w = parseFloat(preservedWidth);
                        spec._node_dimensions['topic'].h = parseFloat(preservedHeight);
                    }
                    if (preservedRadius) {
                        spec._node_dimensions['topic'].r = parseFloat(preservedRadius);
                    }
                    this.logger.debug('CircleMapOperations', 'Preserved dimensions for empty topic node');
                }
                
                const oldTopic = spec.topic;
                spec.topic = updates.text;
                this.logger.debug('CircleMapOperations', 'Updated topic node', {
                    oldTopic,
                    newTopic: updates.text
                });
            }
        } else {
            this.logger.warn('CircleMapOperations', `Unknown node type: ${nodeType}`, {
                nodeId,
                nodeType
            });
        }
        
        this.logger.debug('CircleMapOperations', 'Node update completed', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'circle_map',
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
     * @param {string} nodeId - Node ID (e.g., 'context_0')
     * @param {number} x - X coordinate
     * @param {number} y - Y coordinate
     * @returns {Object} Updated spec
     */
    saveCustomPosition(spec, nodeId, x, y, emitEvents = true) {
        if (!spec) {
            this.logger.error('CircleMapOperations', 'Invalid spec');
            return null;
        }
        
        // Initialize _customPositions if it doesn't exist
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        
        // Save position
        spec._customPositions[nodeId] = { x, y };
        
        this.logger.debug('CircleMapOperations', 'Saved custom position', {
            nodeId,
            x,
            y,
            emitEvents
        });
        
        // Only emit events if requested (skip when saving multiple positions at once)
        if (emitEvents) {
            // Emit position saved event
            this.eventBus.emit('diagram:position_saved', {
                diagramType: 'circle_map',
                nodeId,
                position: { x, y },
                spec
            });
            
            // Emit spec updated to trigger re-render
            this.eventBus.emit('diagram:spec_updated', { spec });
            
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
        }
        
        return spec;
    }
    
    /**
     * Clear all custom positions (reset to auto-layout)
     * @param {Object} spec - Current diagram spec
     * @returns {Object} Updated spec
     */
    clearCustomPositions(spec) {
        if (!spec) {
            this.logger.error('CircleMapOperations', 'Invalid spec');
            return null;
        }
        
        // Clear custom positions
        delete spec._customPositions;
        
        this.logger.debug('CircleMapOperations', 'Cleared custom positions');
        
        // Emit positions cleared event
        this.eventBus.emit('diagram:positions_cleared', {
            diagramType: 'circle_map',
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
     * Validate Circle Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!spec.topic || typeof spec.topic !== 'string') {
            this.logger.warn('CircleMapOperations', 'Invalid or missing topic');
            return false;
        }
        
        if (!Array.isArray(spec.context)) {
            this.logger.warn('CircleMapOperations', 'Invalid or missing context array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('CircleMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.CircleMapOperations = CircleMapOperations;


