/**
 * Multi Flow Map Operations
 * =========================
 * 
 * Handles add/delete/update operations specific to Multi Flow Maps.
 * Manages causes and effects with a central event.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class MultiFlowMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('MultiFlowMapOperations', 'Multi Flow Map Operations initialized');
    }
    
    /**
     * Add a new node to Multi Flow Map
     * Requires node selection (cause or effect)
     * - Clicking on cause → adds new cause
     * - Clicking on effect → adds new effect
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.causes) || !Array.isArray(spec.effects)) {
            this.logger.error('MultiFlowMapOperations', 'Invalid multi-flow map spec');
            return null;
        }
        
        // Check if a node is selected
        const selectedNodes = editor?.selectedNodes ? Array.from(editor.selectedNodes) : [];
        if (selectedNodes.length === 0) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Please select a cause or effect to add a new node',
                type: 'warning'
            });
            return null;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            this.logger.error('MultiFlowMapOperations', 'Selected node not found');
            return null;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        this.logger.debug('MultiFlowMapOperations', 'Adding to multi-flow map, selected node type:', nodeType);
        
        let addedNodeType = null;
        
        // Handle different node types
        switch (nodeType) {
            case 'cause': {
                // Add new cause to the causes array
                const newCauseText = window.languageManager?.translate('newCause') || 'New Cause';
                spec.causes.push(newCauseText);
                addedNodeType = 'cause';
                
                this.logger.debug('MultiFlowMapOperations', `Added new cause. Total causes: ${spec.causes.length}`);
                
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' ? '新原因已添加！' : 'New cause added!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'effect': {
                // Add new effect to the effects array
                const newEffectText = window.languageManager?.translate('newEffect') || 'New Effect';
                spec.effects.push(newEffectText);
                addedNodeType = 'effect';
                
                this.logger.debug('MultiFlowMapOperations', `Added new effect. Total effects: ${spec.effects.length}`);
                
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' ? '新结果已添加！' : 'New effect added!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'event':
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Cannot add nodes to central event',
                    type: 'warning'
                });
                return null;
                
            default:
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Please select a cause or effect',
                    type: 'warning'
                });
                return null;
        }
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'multi_flow_map',
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
     * Delete selected nodes from Multi Flow Map (causes and effects)
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.causes) || !Array.isArray(spec.effects)) {
            this.logger.error('MultiFlowMapOperations', 'Invalid multi-flow map spec');
            return null;
        }
        
        // Separate node IDs by type and collect indices
        const causeIndicesToDelete = [];
        const effectIndicesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                this.logger.warn('MultiFlowMapOperations', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'event') {
                // Don't allow deletion of central event
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Central event cannot be deleted',
                    type: 'warning'
                });
                return;
            } else if (nodeType === 'cause') {
                const causeIndex = parseInt(element.attr('data-cause-index'));
                if (!isNaN(causeIndex)) {
                    causeIndicesToDelete.push(causeIndex);
                }
            } else if (nodeType === 'effect') {
                const effectIndex = parseInt(element.attr('data-effect-index'));
                if (!isNaN(effectIndex)) {
                    effectIndicesToDelete.push(effectIndex);
                }
            }
        });
        
        this.logger.debug('MultiFlowMapOperations', 'Deleting nodes', { causeIndicesToDelete, effectIndicesToDelete });
        
        // Delete causes (sort by index descending to avoid index shifting)
        const sortedCauseIndices = causeIndicesToDelete.sort((a, b) => b - a);
        sortedCauseIndices.forEach(index => {
            if (index >= 0 && index < spec.causes.length) {
                const causeText = spec.causes[index];
                spec.causes.splice(index, 1);
                this.logger.debug('MultiFlowMapOperations', `Deleted cause ${index}: ${causeText}`);
            }
        });
        
        // Delete effects (sort by index descending to avoid index shifting)
        const sortedEffectIndices = effectIndicesToDelete.sort((a, b) => b - a);
        sortedEffectIndices.forEach(index => {
            if (index >= 0 && index < spec.effects.length) {
                const effectText = spec.effects[index];
                spec.effects.splice(index, 1);
                this.logger.debug('MultiFlowMapOperations', `Deleted effect ${index}: ${effectText}`);
            }
        });
        
        const deletedCount = causeIndicesToDelete.length + effectIndicesToDelete.length;
        this.logger.debug('MultiFlowMapOperations', `Deleted ${deletedCount} node(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'multi_flow_map',
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
     * Update a node in Multi Flow Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec) {
            this.logger.error('MultiFlowMapOperations', 'Invalid multi-flow map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('MultiFlowMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        
        // Initialize node dimensions metadata if it doesn't exist
        if (!spec._node_dimensions) {
            spec._node_dimensions = {};
        }
        
        if (nodeType === 'event') {
            // Update the central event
            if (updates.text !== undefined) {
                // Check if we should preserve dimensions (when emptying node)
                const preservedWidth = shapeElement.attr('data-preserved-width');
                const preservedHeight = shapeElement.attr('data-preserved-height');
                
                if (preservedWidth && preservedHeight && updates.text === '') {
                    // Store preserved dimensions for event node
                    spec._node_dimensions['event'] = {
                        w: parseFloat(preservedWidth),
                        h: parseFloat(preservedHeight)
                    };
                    this.logger.debug('MultiFlowMapOperations', 'Preserved dimensions for empty event node', {
                        width: preservedWidth,
                        height: preservedHeight
                    });
                }
                
                spec.event = updates.text;
            }
        } else if (nodeType === 'cause') {
            // Update cause in the causes array
            const causeIndex = parseInt(shapeElement.attr('data-cause-index'));
            if (!isNaN(causeIndex) && spec.causes && causeIndex < spec.causes.length) {
                if (updates.text !== undefined) {
                    // Check if we should preserve dimensions (when emptying node)
                    const preservedWidth = shapeElement.attr('data-preserved-width');
                    const preservedHeight = shapeElement.attr('data-preserved-height');
                    
                    if (preservedWidth && preservedHeight && updates.text === '') {
                        // Store preserved dimensions for this node
                        const nodeKey = `cause-${causeIndex}`;
                        spec._node_dimensions[nodeKey] = {
                            w: parseFloat(preservedWidth),
                            h: parseFloat(preservedHeight)
                        };
                        this.logger.debug('MultiFlowMapOperations', 'Preserved dimensions for empty cause node', {
                            nodeKey,
                            width: preservedWidth,
                            height: preservedHeight
                        });
                    }
                    
                    spec.causes[causeIndex] = updates.text;
                }
            }
        } else if (nodeType === 'effect') {
            // Update effect in the effects array
            const effectIndex = parseInt(shapeElement.attr('data-effect-index'));
            if (!isNaN(effectIndex) && spec.effects && effectIndex < spec.effects.length) {
                if (updates.text !== undefined) {
                    // Check if we should preserve dimensions (when emptying node)
                    const preservedWidth = shapeElement.attr('data-preserved-width');
                    const preservedHeight = shapeElement.attr('data-preserved-height');
                    
                    if (preservedWidth && preservedHeight && updates.text === '') {
                        // Store preserved dimensions for this node
                        const nodeKey = `effect-${effectIndex}`;
                        spec._node_dimensions[nodeKey] = {
                            w: parseFloat(preservedWidth),
                            h: parseFloat(preservedHeight)
                        };
                        this.logger.debug('MultiFlowMapOperations', 'Preserved dimensions for empty effect node', {
                            nodeKey,
                            width: preservedWidth,
                            height: preservedHeight
                        });
                    }
                    
                    spec.effects[effectIndex] = updates.text;
                }
            }
        }
        
        this.logger.debug('MultiFlowMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'multi_flow_map',
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
     * @param {string} nodeId - Node ID (e.g., 'multi-flow-cause-0', 'multi-flow-effect-0')
     * @param {number} x - X coordinate
     * @param {number} y - Y coordinate
     * @returns {Object} Updated spec
     */
    saveCustomPosition(spec, nodeId, x, y) {
        if (!spec) {
            this.logger.error('MultiFlowMapOperations', 'Invalid spec');
            return null;
        }
        
        // Initialize _customPositions if it doesn't exist
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        
        // Save position
        spec._customPositions[nodeId] = { x, y };
        
        this.logger.debug('MultiFlowMapOperations', 'Saved custom position', {
            nodeId,
            x,
            y
        });
        
        // Emit position saved event
        this.eventBus.emit('diagram:position_saved', {
            diagramType: 'multi_flow_map',
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
            this.logger.error('MultiFlowMapOperations', 'Invalid spec');
            return null;
        }
        
        // Clear custom positions
        delete spec._customPositions;
        
        this.logger.debug('MultiFlowMapOperations', 'Cleared custom positions');
        
        // Emit positions cleared event
        this.eventBus.emit('diagram:positions_cleared', {
            diagramType: 'multi_flow_map',
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
     * Validate Multi Flow Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!spec.event || typeof spec.event !== 'string') {
            this.logger.warn('MultiFlowMapOperations', 'Invalid or missing event');
            return false;
        }
        
        if (!Array.isArray(spec.causes)) {
            this.logger.warn('MultiFlowMapOperations', 'Invalid or missing causes array');
            return false;
        }
        
        if (!Array.isArray(spec.effects)) {
            this.logger.warn('MultiFlowMapOperations', 'Invalid or missing effects array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('MultiFlowMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.MultiFlowMapOperations = MultiFlowMapOperations;

