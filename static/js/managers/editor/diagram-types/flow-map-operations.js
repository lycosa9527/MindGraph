/**
 * Flow Map Operations
 * ====================
 * 
 * Handles add/delete/update operations specific to Flow Maps.
 * Manages steps and substeps with hierarchical structure, plus title.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class FlowMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('FlowMapOperations', 'Flow Map Operations initialized');
    }
    
    /**
     * Add a new node to Flow Map
     * Requires node selection (step or substep)
     * - Clicking on step → adds new step (with 2 substeps) after the selected step
     * - Clicking on substep → adds new substep to same step after the selected substep
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.steps)) {
            this.logger.error('FlowMapOperations', 'Invalid flow map spec');
            return null;
        }
        
        // Check if a node is selected
        const selectedNodes = editor?.selectedNodes ? Array.from(editor.selectedNodes) : [];
        if (selectedNodes.length === 0) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Please select a step or substep to add a new node',
                type: 'warning'
            });
            return null;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            this.logger.error('FlowMapOperations', 'Selected node not found');
            return null;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        this.logger.debug('FlowMapOperations', 'Adding to flow map, selected node type:', nodeType);
        
        let addedNodeType = null;
        
        // Handle different node types
        switch (nodeType) {
            case 'step': {
                // Get the index of the selected step
                const stepIndex = parseInt(selectedElement.attr('data-step-index'));
                
                if (isNaN(stepIndex) || stepIndex < 0 || stepIndex >= spec.steps.length) {
                    this.eventBus.emit('diagram:operation_warning', {
                        message: 'Invalid step index',
                        type: 'error'
                    });
                    return null;
                }
                
                // Insert new step right after the selected step
                const newStep = window.languageManager?.translate('newStep') || 'New Step';
                spec.steps.splice(stepIndex + 1, 0, newStep);
                
                // Also insert substeps entry at the same position with 2 default substeps
                if (!Array.isArray(spec.substeps)) {
                    spec.substeps = [];
                }
                const newSubstepText = window.languageManager?.translate('newSubitem') || 'New Substep';
                spec.substeps.splice(stepIndex + 1, 0, {
                    step: newStep,
                    substeps: [`${newSubstepText}1`, `${newSubstepText}2`]
                });
                
                addedNodeType = 'step';
                this.logger.debug('FlowMapOperations', `Inserted new step after step ${stepIndex} with 2 substeps`);
                
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' ? '新步骤及2个子步骤已添加！' : 'New step added with 2 substeps!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'substep': {
                // Get step index and substep index from selected substep
                const stepIndex = parseInt(selectedElement.attr('data-step-index'));
                const substepIndex = parseInt(selectedElement.attr('data-substep-index'));
                
                if (isNaN(stepIndex) || stepIndex < 0 || stepIndex >= spec.steps.length) {
                    this.eventBus.emit('diagram:operation_warning', {
                        message: 'Invalid step index',
                        type: 'error'
                    });
                    return null;
                }
                
                if (isNaN(substepIndex) || substepIndex < 0) {
                    this.eventBus.emit('diagram:operation_warning', {
                        message: 'Invalid substep index',
                        type: 'error'
                    });
                    return null;
                }
                
                // Find the substeps entry for this step
                const stepName = spec.steps[stepIndex];
                let substepsEntry = spec.substeps?.find(s => s.step === stepName);
                
                if (!substepsEntry) {
                    // Create substeps entry if it doesn't exist
                    if (!Array.isArray(spec.substeps)) {
                        spec.substeps = [];
                    }
                    substepsEntry = { step: stepName, substeps: [] };
                    spec.substeps.push(substepsEntry);
                }
                
                // Insert new substep right after the selected substep
                if (!Array.isArray(substepsEntry.substeps)) {
                    substepsEntry.substeps = [];
                }
                const newSubstepText = window.languageManager?.translate('newSubitem') || 'New Substep';
                substepsEntry.substeps.splice(substepIndex + 1, 0, newSubstepText);
                
                addedNodeType = 'substep';
                this.logger.debug('FlowMapOperations', `Inserted new substep after substep ${substepIndex} in step ${stepIndex}`);
                
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' ? '新子步骤已添加！' : 'New substep added!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'title':
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Cannot add nodes to title',
                    type: 'warning'
                });
                return null;
                
            default:
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Please select a step or substep',
                    type: 'warning'
                });
                return null;
        }
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'flow_map',
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
     * Delete selected nodes from Flow Map (steps and substeps)
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.steps)) {
            this.logger.error('FlowMapOperations', 'Invalid flow map spec');
            return null;
        }
        
        // Separate node IDs by type
        const stepNodesToDelete = [];
        const substepNodesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                this.logger.warn('FlowMapOperations', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'title') {
                // Don't allow deletion of title
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Title cannot be deleted',
                    type: 'warning'
                });
                return;
            } else if (nodeType === 'step') {
                const stepIndex = parseInt(element.attr('data-step-index'));
                if (!isNaN(stepIndex)) {
                    stepNodesToDelete.push({ nodeId, stepIndex });
                }
            } else if (nodeType === 'substep') {
                const stepIndex = parseInt(element.attr('data-step-index'));
                const substepIndex = parseInt(element.attr('data-substep-index'));
                if (!isNaN(stepIndex) && !isNaN(substepIndex)) {
                    substepNodesToDelete.push({ nodeId, stepIndex, substepIndex });
                }
            }
        });
        
        this.logger.debug('FlowMapOperations', 'Deleting nodes', { stepNodesToDelete, substepNodesToDelete });
        
        // Delete substeps first (grouped by step, highest index first to avoid index shifting)
        const substepsByStep = {};
        substepNodesToDelete.forEach(item => {
            if (!substepsByStep[item.stepIndex]) {
                substepsByStep[item.stepIndex] = [];
            }
            substepsByStep[item.stepIndex].push(item.substepIndex);
        });
        
        Object.keys(substepsByStep).forEach(stepIndex => {
            const indices = substepsByStep[stepIndex].sort((a, b) => b - a); // Sort descending
            const stepName = spec.steps[parseInt(stepIndex)];
            const substepsEntry = spec.substeps?.find(s => s.step === stepName);
            
            if (substepsEntry && Array.isArray(substepsEntry.substeps)) {
                indices.forEach(index => {
                    if (index >= 0 && index < substepsEntry.substeps.length) {
                        substepsEntry.substeps.splice(index, 1);
                        this.logger.debug('FlowMapOperations', `Deleted substep ${index} from step ${stepIndex}`);
                    }
                });
            }
        });
        
        // Delete steps (sort by index descending to avoid index shifting)
        const stepIndicesToDelete = stepNodesToDelete
            .map(item => item.stepIndex)
            .sort((a, b) => b - a);
        
        stepIndicesToDelete.forEach(index => {
            if (index >= 0 && index < spec.steps.length) {
                const stepName = spec.steps[index];
                
                // Remove step from steps array
                spec.steps.splice(index, 1);
                this.logger.debug('FlowMapOperations', `Deleted step ${index}: ${stepName}`);
                
                // Remove corresponding substeps entry
                if (Array.isArray(spec.substeps)) {
                    const substepsIndex = spec.substeps.findIndex(s => s.step === stepName);
                    if (substepsIndex !== -1) {
                        spec.substeps.splice(substepsIndex, 1);
                        this.logger.debug('FlowMapOperations', `Deleted substeps entry for step: ${stepName}`);
                    }
                }
            }
        });
        
        const deletedCount = stepNodesToDelete.length + substepNodesToDelete.length;
        this.logger.debug('FlowMapOperations', `Deleted ${deletedCount} node(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'flow_map',
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
     * Update a node in Flow Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec) {
            this.logger.error('FlowMapOperations', 'Invalid flow map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('FlowMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        
        // Initialize node dimensions metadata if it doesn't exist
        if (!spec._node_dimensions) {
            spec._node_dimensions = {};
        }
        
        if (nodeType === 'title') {
            // Update the title
            if (updates.text !== undefined) {
                // Check if we should preserve dimensions (when emptying node)
                const preservedWidth = shapeElement.attr('data-preserved-width');
                const preservedHeight = shapeElement.attr('data-preserved-height');
                
                if (preservedWidth && preservedHeight && updates.text === '') {
                    spec._node_dimensions['title'] = {
                        w: parseFloat(preservedWidth),
                        h: parseFloat(preservedHeight)
                    };
                    this.logger.debug('FlowMapOperations', 'Preserved dimensions for empty title node');
                }
                
                spec.title = updates.text;
            }
        } else if (nodeType === 'step') {
            // Update step in the steps array
            const stepIndex = parseInt(shapeElement.attr('data-step-index'));
            if (!isNaN(stepIndex) && spec.steps && stepIndex < spec.steps.length) {
                // Get the old step name before updating
                const oldStepName = spec.steps[stepIndex];
                
                // Update step in the steps array
                if (updates.text !== undefined) {
                    spec.steps[stepIndex] = updates.text;
                }
                
                // CRITICAL: Update the corresponding substeps entry's step field
                // This ensures substeps remain linked to the step after editing
                if (Array.isArray(spec.substeps) && oldStepName !== updates.text) {
                    const substepsEntry = spec.substeps.find(s => s.step === oldStepName);
                    if (substepsEntry) {
                        substepsEntry.step = updates.text;
                        this.logger.debug('FlowMapOperations', `Updated substeps entry step field from "${oldStepName}" to "${updates.text}"`);
                    }
                }
            }
        } else if (nodeType === 'substep') {
            // Update substep in the substeps array
            const stepIndex = parseInt(shapeElement.attr('data-step-index'));
            const substepIndex = parseInt(shapeElement.attr('data-substep-index'));
            
            if (!isNaN(stepIndex) && !isNaN(substepIndex) && spec.substeps) {
                // Find the substeps entry for this step
                const substepsEntry = spec.substeps.find(s => s.step === spec.steps[stepIndex]);
                if (substepsEntry && substepsEntry.substeps && substepIndex < substepsEntry.substeps.length) {
                    if (updates.text !== undefined) {
                        // Check if we should preserve dimensions (when emptying node)
                        const preservedWidth = shapeElement.attr('data-preserved-width');
                        const preservedHeight = shapeElement.attr('data-preserved-height');
                        
                        if (preservedWidth && preservedHeight && updates.text === '') {
                            const nodeKey = `substep-${stepIndex}-${substepIndex}`;
                            spec._node_dimensions[nodeKey] = {
                                w: parseFloat(preservedWidth),
                                h: parseFloat(preservedHeight)
                            };
                            this.logger.debug('FlowMapOperations', 'Preserved dimensions for empty substep node', {
                                nodeKey,
                                dimensions: spec._node_dimensions[nodeKey]
                            });
                        }
                        
                        substepsEntry.substeps[substepIndex] = updates.text;
                    }
                }
            }
        }
        
        this.logger.debug('FlowMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'flow_map',
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
     * Validate Flow Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!Array.isArray(spec.steps)) {
            this.logger.warn('FlowMapOperations', 'Invalid or missing steps array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('FlowMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.FlowMapOperations = FlowMapOperations;

