/**
 * Brace Map Operations
 * =====================
 * 
 * Handles add/delete/update operations specific to Brace Maps.
 * Manages parts and subparts with hierarchical structure.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class BraceMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('BraceMapOperations', 'Brace Map Operations initialized');
    }
    
    /**
     * Add a new node to Brace Map
     * Requires user to select a part or subpart node first
     * - Clicking on part → adds new part (with 2 subparts)
     * - Clicking on subpart → adds new subpart to same part
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.parts)) {
            this.logger.error('BraceMapOperations', 'Invalid brace map spec');
            return null;
        }
        
        // Check if user has selected a node
        const selected = editor?.selectedNodes ? Array.from(editor.selectedNodes) : [];
        if (selected.length === 0) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Please select a part or subpart node to add a new node',
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
        
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        let addedNodeType = null;
        
        // Handle different node types
        switch(nodeType) {
            case 'part': {
                // Add new part node to the parts array with two default subparts
                const newPartText = lang === 'zh' ? '新部分' : 'New Part';
                const newSubpartText = lang === 'zh' ? '新子部分' : 'New Subpart';
                spec.parts.push({
                    name: newPartText,
                    subparts: [
                        { name: `${newSubpartText}1` },
                        { name: `${newSubpartText}2` }
                    ]
                });
                addedNodeType = 'part';
                this.logger.debug('BraceMapOperations', 'Added new part node with 2 subparts');
                
                const message = lang === 'zh' ? '新部分及2个子部分已添加！' : 'New part added with 2 subparts!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'subpart': {
                // Get part index from selected subpart
                const partIndexAttr = selectedElement.attr('data-part-index');
                const partIndex = parseInt(partIndexAttr);
                
                if (isNaN(partIndex) || partIndex < 0 || partIndex >= spec.parts.length) {
                    this.logger.error('BraceMapOperations', 'Invalid part index', {
                        partIndexAttr,
                        partIndex,
                        partsCount: spec.parts.length
                    });
                    this.eventBus.emit('diagram:operation_warning', {
                        message: 'Invalid part index',
                        type: 'error'
                    });
                    return null;
                }
                
                // Add new subpart to the same part as the selected subpart
                if (!Array.isArray(spec.parts[partIndex].subparts)) {
                    spec.parts[partIndex].subparts = [];
                }
                const newSubpartText = lang === 'zh' ? '新子部分' : 'New Subpart';
                spec.parts[partIndex].subparts.push({
                    name: newSubpartText
                });
                addedNodeType = 'subpart';
                this.logger.debug('BraceMapOperations', `Added new subpart to part ${partIndex}`);
                
                const message = lang === 'zh' ? '新子部分已添加！' : 'New subpart added!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'topic':
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Cannot add nodes to main topic',
                    type: 'warning'
                });
                return null;
                
            default:
                this.eventBus.emit('diagram:operation_warning', {
                    message: `Please select a part or subpart node`,
                    type: 'error'
                });
                return null;
        }
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'brace_map',
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
     * Delete selected nodes from Brace Map (parts and subparts)
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.parts)) {
            this.logger.error('BraceMapOperations', 'Invalid brace map spec');
            return null;
        }
        
        // Collect nodes to delete by type
        const partsToDelete = [];
        const subpartsToDelete = []; // Store as {partIndex, subpartIndex}
        let attemptedMainTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const nodeType = shapeElement.attr('data-node-type');
                
                switch(nodeType) {
                    case 'part': {
                        const partIndex = parseInt(shapeElement.attr('data-part-index'));
                        if (!isNaN(partIndex)) {
                            partsToDelete.push(partIndex);
                        }
                        break;
                    }
                        
                    case 'subpart': {
                        const partIndex = parseInt(shapeElement.attr('data-part-index'));
                        const subpartIndex = parseInt(shapeElement.attr('data-subpart-index'));
                        if (!isNaN(partIndex) && !isNaN(subpartIndex)) {
                            subpartsToDelete.push({partIndex, subpartIndex});
                        }
                        break;
                    }
                        
                    case 'topic':
                        attemptedMainTopicDelete = true;
                        break;
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
        if (partsToDelete.length === 0 && subpartsToDelete.length === 0) {
            return spec;
        }
        
        let deletedCount = 0;
        
        // Delete subparts first (before deleting parts, which would remove all subparts)
        if (subpartsToDelete.length > 0) {
            // Group subparts by part index for efficient deletion
            const subpartsByPart = {};
            subpartsToDelete.forEach(({partIndex, subpartIndex}) => {
                if (!subpartsByPart[partIndex]) {
                    subpartsByPart[partIndex] = [];
                }
                subpartsByPart[partIndex].push(subpartIndex);
            });
            
            // Delete subparts for each part (in descending order to avoid index shifts)
            Object.keys(subpartsByPart).forEach(partIndexStr => {
                const partIndex = parseInt(partIndexStr);
                if (partIndex >= 0 && partIndex < spec.parts.length) {
                    const part = spec.parts[partIndex];
                    if (part && Array.isArray(part.subparts)) {
                        // Sort indices in descending order
                        const sortedIndices = [...new Set(subpartsByPart[partIndex])].sort((a, b) => b - a);
                        sortedIndices.forEach(subpartIndex => {
                            if (subpartIndex >= 0 && subpartIndex < part.subparts.length) {
                                part.subparts.splice(subpartIndex, 1);
                                deletedCount++;
                            }
                        });
                    }
                }
            });
            this.logger.debug('BraceMapOperations', `Deleted ${deletedCount} subpart(s)`);
        }
        
        // Delete parts (this will also remove any remaining subparts)
        if (partsToDelete.length > 0) {
            // Remove duplicates and sort in descending order
            const uniquePartIndices = [...new Set(partsToDelete)].sort((a, b) => b - a);
            
            uniquePartIndices.forEach(partIndex => {
                if (partIndex >= 0 && partIndex < spec.parts.length) {
                    spec.parts.splice(partIndex, 1);
                    deletedCount++;
                }
            });
            this.logger.debug('BraceMapOperations', `Deleted ${uniquePartIndices.length} part(s)`);
        }
        
        this.logger.debug('BraceMapOperations', `Total deleted: ${deletedCount} node(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'brace_map',
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
     * Update a node in Brace Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec) {
            this.logger.error('BraceMapOperations', 'Invalid brace map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('BraceMapOperations', `Node not found: ${nodeId}`);
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
                this.logger.debug('BraceMapOperations', 'Preserved dimensions for empty node', {
                    nodeKey,
                    dimensions: spec._node_dimensions[nodeKey]
                });
            }
        };
        
        if (nodeType === 'topic') {
            // Update the main topic (whole in brace map terminology)
            if (updates.text !== undefined) {
                preserveDimensionsIfEmpty('topic', updates.text);
                spec.whole = updates.text;
            }
        } else if (nodeType === 'dimension') {
            // Update the decomposition dimension
            if (updates.text !== undefined) {
                preserveDimensionsIfEmpty('dimension', updates.text);
                spec.dimension = updates.text;
            }
        } else if (nodeType === 'part') {
            // Update part name in the parts array
            const partIndex = parseInt(shapeElement.attr('data-part-index'));
            if (!isNaN(partIndex) && spec.parts && partIndex < spec.parts.length) {
                if (updates.text !== undefined) {
                    preserveDimensionsIfEmpty(`part-${partIndex}`, updates.text);
                    spec.parts[partIndex].name = updates.text;
                }
            }
        } else if (nodeType === 'subpart') {
            // Update subpart name in the parts array
            const partIndex = parseInt(shapeElement.attr('data-part-index'));
            const subpartIndex = parseInt(shapeElement.attr('data-subpart-index'));
            
            if (!isNaN(partIndex) && !isNaN(subpartIndex) && spec.parts && partIndex < spec.parts.length) {
                const part = spec.parts[partIndex];
                if (part.subparts && subpartIndex < part.subparts.length) {
                    if (updates.text !== undefined) {
                        preserveDimensionsIfEmpty(`subpart-${partIndex}-${subpartIndex}`, updates.text);
                        part.subparts[subpartIndex].name = updates.text;
                    }
                }
            }
        }
        
        this.logger.debug('BraceMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'brace_map',
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
     * Validate Brace Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!spec.whole || typeof spec.whole !== 'string') {
            this.logger.warn('BraceMapOperations', 'Invalid or missing whole (topic)');
            return false;
        }
        
        if (!Array.isArray(spec.parts)) {
            this.logger.warn('BraceMapOperations', 'Invalid or missing parts array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('BraceMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.BraceMapOperations = BraceMapOperations;

