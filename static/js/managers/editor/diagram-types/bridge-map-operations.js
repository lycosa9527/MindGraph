/**
 * Bridge Map Operations
 * =====================
 * 
 * Handles add/delete/update operations specific to Bridge Maps.
 * Manages analogy pairs (left/right items) with a dimension label.
 * Bridge maps always add pairs to the end (no selection required).
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class BridgeMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('BridgeMapOperations', 'Bridge Map Operations initialized');
    }
    
    /**
     * Add a new analogy pair to Bridge Map
     * Bridge maps always add pairs to the end (no selection required)
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance (not used for bridge map)
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.analogies)) {
            this.logger.error('BridgeMapOperations', 'Invalid bridge map spec');
            return null;
        }
        
        // For bridge map, always add pairs to the end (no selection required)
        // This is because bridge maps are sequential in nature
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        const newPair = {
            left: lang === 'zh' ? '新事物A' : 'New Left',
            right: lang === 'zh' ? '新事物B' : 'New Right'
        };
        
        spec.analogies.push(newPair);
        
        this.logger.debug('BridgeMapOperations', `Added new analogy pair at end. Total pairs: ${spec.analogies.length}`);
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'bridge_map',
            nodeType: 'analogy_pair',
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
     * Delete selected analogy pairs from Bridge Map
     * Bridge map deletes complete pairs (both left and right together)
     * Cannot delete the first pair (index 0)
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.analogies)) {
            this.logger.error('BridgeMapOperations', 'Invalid bridge map spec');
            return null;
        }
        
        // Collect unique pair indices to delete
        // Bridge map deletes complete pairs (both left and right together)
        const pairIndicesToDelete = new Set();
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                this.logger.warn('BridgeMapOperations', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            const pairIndex = parseInt(element.attr('data-pair-index'));
            
            if (!isNaN(pairIndex)) {
                // Add the pair index (whether it's left or right, we delete the whole pair)
                pairIndicesToDelete.add(pairIndex);
                this.logger.debug('BridgeMapOperations', `Marking pair ${pairIndex} for deletion (${nodeType} node)`);
            }
        });
        
        this.logger.debug('BridgeMapOperations', 'Deleting pairs', { pairIndicesToDelete: Array.from(pairIndicesToDelete) });
        
        // Prevent deletion of the first pair (like the topic in other maps)
        if (pairIndicesToDelete.has(0)) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'First analogy pair cannot be deleted',
                type: 'warning'
            });
            pairIndicesToDelete.delete(0);
        }
        
        // If no valid pairs to delete, return early
        if (pairIndicesToDelete.size === 0) {
            return spec;
        }
        
        // Delete pairs (sort by index descending to avoid index shifting)
        const sortedPairIndices = Array.from(pairIndicesToDelete).sort((a, b) => b - a);
        sortedPairIndices.forEach(index => {
            if (index >= 0 && index < spec.analogies.length) {
                const pair = spec.analogies[index];
                spec.analogies.splice(index, 1);
                this.logger.debug('BridgeMapOperations', `Deleted pair ${index}: "${pair.left}" / "${pair.right}"`);
            }
        });
        
        const deletedCount = sortedPairIndices.length;
        this.logger.debug('BridgeMapOperations', `Deleted ${deletedCount} pair(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'bridge_map',
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
     * Update a node in Bridge Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec) {
            this.logger.error('BridgeMapOperations', 'Invalid bridge map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('BridgeMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        const pairIndex = parseInt(shapeElement.attr('data-pair-index'));
        
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
                this.logger.debug('BridgeMapOperations', 'Preserved dimensions for empty node', {
                    nodeKey,
                    dimensions: spec._node_dimensions[nodeKey]
                });
            }
        };
        
        if (nodeType === 'dimension') {
            // Update dimension label
            if (updates.text !== undefined) {
                preserveDimensionsIfEmpty('dimension', updates.text);
                spec.dimension = updates.text;
            }
        } else if (!isNaN(pairIndex) && pairIndex < spec.analogies.length) {
            if (nodeType === 'left') {
                // Update left item in the pair
                if (updates.text !== undefined) {
                    preserveDimensionsIfEmpty(`left-${pairIndex}`, updates.text);
                    spec.analogies[pairIndex].left = updates.text;
                }
            } else if (nodeType === 'right') {
                // Update right item in the pair
                if (updates.text !== undefined) {
                    preserveDimensionsIfEmpty(`right-${pairIndex}`, updates.text);
                    spec.analogies[pairIndex].right = updates.text;
                }
            }
        }
        
        this.logger.debug('BridgeMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'bridge_map',
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
     * @param {string} nodeId - Node ID (e.g., 'bridge-left-0', 'bridge-right-0')
     * @param {number} x - X coordinate
     * @param {number} y - Y coordinate
     * @returns {Object} Updated spec
     */
    saveCustomPosition(spec, nodeId, x, y) {
        if (!spec) {
            this.logger.error('BridgeMapOperations', 'Invalid spec');
            return null;
        }
        
        // Initialize _customPositions if it doesn't exist
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        
        // Save position
        spec._customPositions[nodeId] = { x, y };
        
        // If dragging left node, also move corresponding right node (same pair index)
        // Extract pair index from nodeId (e.g., 'bridge-left-0' -> 0)
        const match = nodeId.match(/bridge-(left|right)-(\d+)/);
        if (match) {
            const pairIndex = parseInt(match[2]);
            const side = match[1];
            
            // Find corresponding node in the pair
            const otherSide = side === 'left' ? 'right' : 'left';
            const otherNodeId = `bridge-${otherSide}-${pairIndex}`;
            
            // Calculate offset from center to maintain pair relationship
            // For now, just save the position - renderer will handle pair positioning
            // This is a placeholder - full implementation would require renderer updates
        }
        
        this.logger.debug('BridgeMapOperations', 'Saved custom position', {
            nodeId,
            x,
            y
        });
        
        // Emit position saved event
        this.eventBus.emit('diagram:position_saved', {
            diagramType: 'bridge_map',
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
            this.logger.error('BridgeMapOperations', 'Invalid spec');
            return null;
        }
        
        // Clear custom positions
        delete spec._customPositions;
        
        this.logger.debug('BridgeMapOperations', 'Cleared custom positions');
        
        // Emit positions cleared event
        this.eventBus.emit('diagram:positions_cleared', {
            diagramType: 'bridge_map',
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
     * Validate Bridge Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!Array.isArray(spec.analogies)) {
            this.logger.warn('BridgeMapOperations', 'Invalid or missing analogies array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('BridgeMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.BridgeMapOperations = BridgeMapOperations;

