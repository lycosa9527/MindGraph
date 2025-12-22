/**
 * Double Bubble Map Operations
 * ==============================
 * 
 * Handles add/delete/update operations specific to Double Bubble Maps.
 * Manages similarities and paired differences (left_differences/right_differences).
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class DoubleBubbleMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('DoubleBubbleMapOperations', 'Double Bubble Map Operations initialized');
    }
    
    /**
     * Add a new node to Double Bubble Map
     * Requires editor to have selectedNodes to determine which type to add
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec) {
            this.logger.error('DoubleBubbleMapOperations', 'Invalid double bubble map spec');
            return null;
        }
        
        // Check if user has selected a node
        const selected = editor?.selectedNodes ? Array.from(editor.selectedNodes) : [];
        if (selected.length === 0) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Please select a node to add a new node',
                type: 'warning'
            });
            return null;
        }
        
        // Get the type of the selected node
        const selectedElement = d3.select(`[data-node-id="${selected[0]}"]`);
        const nodeType = selectedElement.attr('data-node-type');
        
        if (!nodeType) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Could not determine node type',
                type: 'error'
            });
            return null;
        }
        
        // Add node based on selected type
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        let addedNodeType = null;
        
        switch(nodeType) {
            case 'similarity':
                // Add similarity
                if (!Array.isArray(spec.similarities)) {
                    spec.similarities = [];
                }
                const newSimilarityText = lang === 'zh' ? '新相似点' : 'New Similarity';
                spec.similarities.push(newSimilarityText);
                addedNodeType = 'similarity';
                this.logger.debug('DoubleBubbleMapOperations', 'Added new similarity node');
                break;
                
            case 'left_difference':
            case 'right_difference':
                // Add paired differences (one to each side)
                if (!Array.isArray(spec.left_differences)) {
                    spec.left_differences = [];
                }
                if (!Array.isArray(spec.right_differences)) {
                    spec.right_differences = [];
                }
                const leftDiffText = lang === 'zh' ? '左不同点' : 'Left Difference';
                const rightDiffText = lang === 'zh' ? '右不同点' : 'Right Difference';
                spec.left_differences.push(leftDiffText);
                spec.right_differences.push(rightDiffText);
                addedNodeType = 'difference_pair';
                this.logger.debug('DoubleBubbleMapOperations', 'Added paired difference nodes');
                break;
                
            case 'left':
            case 'right':
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Cannot add nodes to main topics',
                    type: 'warning'
                });
                return null;
                
            default:
                this.eventBus.emit('diagram:operation_warning', {
                    message: `Unknown node type: ${nodeType}`,
                    type: 'error'
                });
                return null;
        }
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'double_bubble_map',
            nodeType: addedNodeType,
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
     * Delete selected nodes from Double Bubble Map
     * - Similarities: delete normally
     * - Differences: delete in PAIRS (same index from both left and right)
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec) {
            this.logger.error('DoubleBubbleMapOperations', 'Invalid double bubble map spec');
            return null;
        }
        
        // Collect indices to delete by type
        const similarityIndicesToDelete = [];
        const differenceIndicesToDelete = []; // For paired deletion
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                const arrayIndex = parseInt(shapeElement.attr('data-array-index'));
                
                switch(nodeType) {
                    case 'similarity':
                        if (!isNaN(arrayIndex)) {
                            similarityIndicesToDelete.push(arrayIndex);
                        }
                        break;
                        
                    case 'left_difference':
                    case 'right_difference':
                        // For differences, delete in pairs at the same index
                        if (!isNaN(arrayIndex)) {
                            differenceIndicesToDelete.push(arrayIndex);
                        }
                        break;
                        
                    case 'left':
                    case 'right':
                        attemptedMainTopicDelete = true;
                        break;
                }
            }
        });
        
        // Warn if trying to delete main topics
        if (attemptedMainTopicDelete) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Main topic nodes cannot be deleted',
                type: 'warning'
            });
        }
        
        // If no valid nodes to delete, return early
        if (similarityIndicesToDelete.length === 0 && differenceIndicesToDelete.length === 0) {
            return spec;
        }
        
        let deletedCount = 0;
        
        // Delete similarities
        if (similarityIndicesToDelete.length > 0 && Array.isArray(spec.similarities)) {
            // Sort in descending order to delete from end to start
            const uniqueIndices = [...new Set(similarityIndicesToDelete)].sort((a, b) => b - a);
            uniqueIndices.forEach(index => {
                spec.similarities.splice(index, 1);
                deletedCount++;
            });
            this.logger.debug('DoubleBubbleMapOperations', `Deleted ${uniqueIndices.length} similarity node(s)`);
        }
        
        // Delete differences in PAIRS
        if (differenceIndicesToDelete.length > 0) {
            // Remove duplicates and sort in descending order
            const uniqueIndices = [...new Set(differenceIndicesToDelete)].sort((a, b) => b - a);
            
            uniqueIndices.forEach(index => {
                // Delete from both left and right at the same index
                if (Array.isArray(spec.left_differences) && index < spec.left_differences.length) {
                    spec.left_differences.splice(index, 1);
                }
                if (Array.isArray(spec.right_differences) && index < spec.right_differences.length) {
                    spec.right_differences.splice(index, 1);
                }
            });
            
            deletedCount += uniqueIndices.length * 2; // Count both left and right
            this.logger.debug('DoubleBubbleMapOperations', `Deleted ${uniqueIndices.length} difference pair(s) (${uniqueIndices.length * 2} nodes total)`);
            
            // Emit notification about paired deletion
            this.eventBus.emit('diagram:operation_warning', {
                message: `Deleted ${uniqueIndices.length} difference pair${uniqueIndices.length > 1 ? 's' : ''} (left & right)`,
                type: 'success'
            });
        }
        
        this.logger.debug('DoubleBubbleMapOperations', `Total deleted: ${deletedCount} node(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'double_bubble_map',
            deletedCount: deletedCount,
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
     * Update a node in Double Bubble Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec) {
            this.logger.error('DoubleBubbleMapOperations', 'Invalid double bubble map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('DoubleBubbleMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        
        // Initialize node dimensions metadata if it doesn't exist
        if (!spec._node_dimensions) {
            spec._node_dimensions = {};
        }
        
        // Helper function to preserve dimensions when emptying
        const preserveDimensionsIfEmpty = (nodeKey, text) => {
            const preservedWidth = shapeElement.attr('data-preserved-width');
            const preservedHeight = shapeElement.attr('data-preserved-height');
            const preservedRadius = shapeElement.attr('data-preserved-radius');
            
            if ((preservedWidth && preservedHeight || preservedRadius) && text === '') {
                spec._node_dimensions[nodeKey] = {};
                if (preservedWidth && preservedHeight) {
                    spec._node_dimensions[nodeKey].w = parseFloat(preservedWidth);
                    spec._node_dimensions[nodeKey].h = parseFloat(preservedHeight);
                }
                if (preservedRadius) {
                    spec._node_dimensions[nodeKey].r = parseFloat(preservedRadius);
                }
                this.logger.debug('DoubleBubbleMapOperations', 'Preserved dimensions for empty node', {
                    nodeKey,
                    dimensions: spec._node_dimensions[nodeKey]
                });
            }
        };
        
        switch(nodeType) {
            case 'left':
                // Update left topic
                if (updates.text !== undefined) {
                    preserveDimensionsIfEmpty('left', updates.text);
                    spec.left = updates.text;
                }
                break;
                
            case 'right':
                // Update right topic
                if (updates.text !== undefined) {
                    preserveDimensionsIfEmpty('right', updates.text);
                    spec.right = updates.text;
                }
                break;
                
            case 'similarity':
                // Update similarities array
                const simIndex = parseInt(shapeElement.attr('data-array-index'));
                if (!isNaN(simIndex) && Array.isArray(spec.similarities) && simIndex < spec.similarities.length) {
                    if (updates.text !== undefined) {
                        preserveDimensionsIfEmpty(`similarity-${simIndex}`, updates.text);
                        spec.similarities[simIndex] = updates.text;
                    }
                }
                break;
                
            case 'left_difference':
                // Update left_differences array
                const leftDiffIndex = parseInt(shapeElement.attr('data-array-index'));
                if (!isNaN(leftDiffIndex) && Array.isArray(spec.left_differences) && leftDiffIndex < spec.left_differences.length) {
                    if (updates.text !== undefined) {
                        preserveDimensionsIfEmpty(`left_difference-${leftDiffIndex}`, updates.text);
                        spec.left_differences[leftDiffIndex] = updates.text;
                    }
                }
                break;
                
            case 'right_difference':
                // Update right_differences array
                const rightDiffIndex = parseInt(shapeElement.attr('data-array-index'));
                if (!isNaN(rightDiffIndex) && Array.isArray(spec.right_differences) && rightDiffIndex < spec.right_differences.length) {
                    if (updates.text !== undefined) {
                        preserveDimensionsIfEmpty(`right_difference-${rightDiffIndex}`, updates.text);
                        spec.right_differences[rightDiffIndex] = updates.text;
                    }
                }
                break;
                
            default:
                this.logger.warn('DoubleBubbleMapOperations', `Unknown node type: ${nodeType}`);
                return spec;
        }
        
        this.logger.debug('DoubleBubbleMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'double_bubble_map',
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
     * @param {string} nodeId - Node ID (e.g., 'similarity_0', 'left_diff_0', 'right_diff_0')
     * @param {number} x - X coordinate
     * @param {number} y - Y coordinate
     * @returns {Object} Updated spec
     */
    saveCustomPosition(spec, nodeId, x, y) {
        if (!spec) {
            this.logger.error('DoubleBubbleMapOperations', 'Invalid spec');
            return null;
        }
        
        // Initialize _customPositions if it doesn't exist
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        
        // Save position
        spec._customPositions[nodeId] = { x, y };
        
        this.logger.debug('DoubleBubbleMapOperations', 'Saved custom position', {
            nodeId,
            x,
            y
        });
        
        // Emit position saved event
        this.eventBus.emit('diagram:position_saved', {
            diagramType: 'double_bubble_map',
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
            this.logger.error('DoubleBubbleMapOperations', 'Invalid spec');
            return null;
        }
        
        // Clear custom positions
        delete spec._customPositions;
        
        this.logger.debug('DoubleBubbleMapOperations', 'Cleared custom positions');
        
        // Emit positions cleared event
        this.eventBus.emit('diagram:positions_cleared', {
            diagramType: 'double_bubble_map',
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
     * Validate Double Bubble Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!spec.left || typeof spec.left !== 'string') {
            this.logger.warn('DoubleBubbleMapOperations', 'Invalid or missing left topic');
            return false;
        }
        
        if (!spec.right || typeof spec.right !== 'string') {
            this.logger.warn('DoubleBubbleMapOperations', 'Invalid or missing right topic');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('DoubleBubbleMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.DoubleBubbleMapOperations = DoubleBubbleMapOperations;

