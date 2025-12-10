/**
 * Mind Map Operations
 * ====================
 * 
 * Handles add/delete/update operations specific to Mind Maps.
 * Manages hierarchical branches and children with backend layout recalculation.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class MindMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('MindMapOperations', 'Mind Map Operations initialized');
    }
    
    /**
     * Add a new node to Mind Map
     * Requires backend layout recalculation for mind maps
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance (needed for layout recalculation)
     * @returns {Promise<Object>} Updated spec
     */
    async addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.children)) {
            this.logger.error('MindMapOperations', 'Invalid mind map spec');
            return null;
        }
        
        // Get selected nodes from editor
        const selectedNodes = editor?.selectedNodes ? Array.from(editor.selectedNodes) : [];
        
        // Check if no node is selected
        if (selectedNodes.length === 0) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Please select a branch or sub-item to add a new node',
                type: 'warning'
            });
            return null;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            this.logger.error('MindMapOperations', 'Selected node not found');
            return null;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        
        // Don't allow adding to the central topic
        if (nodeType === 'topic' || !nodeType) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Cannot add nodes to central topic',
                type: 'warning'
            });
            return null;
        }
        
        let addedNodeType = null;
        
        // Handle different node types
        if (nodeType === 'branch') {
            // Adding a new branch - find the branch index
            const branchIndex = parseInt(selectedElement.attr('data-array-index') || selectedElement.attr('data-branch-index'));
            
            if (isNaN(branchIndex) || branchIndex < 0) {
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Invalid branch index',
                    type: 'error'
                });
                return null;
            }
            
            // Add new branch - insert at end, then renumber for clockwise order
            // The layout system handles clockwise positioning, we just need to ensure numbering follows clockwise
            const numBranches = spec.children.length;
            const newBranchText = window.languageManager?.translate('newBranch') || 'New Branch';
            const newSubitemText = window.languageManager?.translate('newSubitem') || 'Sub-item';
            
            // Create new branch (will be numbered correctly after renumbering)
            const newBranch = {
                id: `branch_${numBranches}`,
                label: `${newBranchText} ${numBranches + 1}`,
                text: `${newBranchText} ${numBranches + 1}`,
                children: [
                    {
                        id: `sub_${numBranches}_0`,
                        label: `${newSubitemText} ${numBranches + 1}.1`,
                        text: `${newSubitemText} ${numBranches + 1}.1`,
                        children: []
                    },
                    {
                        id: `sub_${numBranches}_1`,
                        label: `${newSubitemText} ${numBranches + 1}.2`,
                        text: `${newSubitemText} ${numBranches + 1}.2`,
                        children: []
                    }
                ]
            };
            
            // Add to end of array (layout system will position it correctly)
            spec.children.push(newBranch);
            
            // Update all branch labels to reflect clockwise numbering order
            this._updateBranchNumbersForClockwise(spec);
            
            addedNodeType = 'branch';
            
            this.logger.debug('MindMapOperations', `Added new branch with clockwise numbering. Total branches: ${spec.children.length}`);
            
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const message = lang === 'zh' ? '新分支及2个子项已添加！' : 'New branch with 2 sub-items added!';
            this.eventBus.emit('diagram:operation_warning', {
                message: message,
                type: 'success'
            });
            
        } else if (nodeType === 'child' || nodeType === 'subitem') {
            // Adding a sub-item - find the parent branch
            const branchIndex = parseInt(selectedElement.attr('data-branch-index'));
            
            if (isNaN(branchIndex) || branchIndex < 0 || branchIndex >= spec.children.length) {
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Invalid branch index',
                    type: 'error'
                });
                return null;
            }
            
            const branch = spec.children[branchIndex];
            if (!branch || !Array.isArray(branch.children)) {
                this.logger.error('MindMapOperations', 'Invalid branch structure');
                return null;
            }
            
            // Get translated text for sub-item
            const newSubitemText = window.languageManager?.translate('newSubitem') || 'Sub-item';
            
            // Add new sub-item to the branch
            const newChildIndex = branch.children.length;
            branch.children.push({
                id: `sub_${branchIndex}_${newChildIndex}`,
                label: `${newSubitemText} ${branchIndex + 1}.${newChildIndex + 1}`,
                text: `${newSubitemText} ${branchIndex + 1}.${newChildIndex + 1}`,
                children: []
            });
            addedNodeType = 'child';
            
            this.logger.debug('MindMapOperations', `Added new sub-item to branch ${branchIndex}. Total sub-items: ${branch.children.length}`);
            
            // Get translated success message
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const message = lang === 'zh' ? '新子项已添加！' : 'New sub-item added!';
            this.eventBus.emit('diagram:operation_warning', {
                message: message,
                type: 'success'
            });
        } else {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Please select a branch or sub-item',
                type: 'error'
            });
            return null;
        }
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'mindmap',
            nodeType: addedNodeType,
            spec
        });
        
        // Emit operation completed for history
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'add_node',
            snapshot: JSON.parse(JSON.stringify(spec))
        });
        
        // For mind maps, we need to recalculate layout from backend before rendering
        // Emit event to request layout recalculation
        this.eventBus.emit('mindmap:layout_recalculation_requested', {
            spec
        });
        
        return spec;
    }
    
    /**
     * Delete selected nodes from Mind Map
     * Requires backend layout recalculation for mind maps
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Promise<Object>} Updated spec
     */
    async deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.children)) {
            this.logger.error('MindMapOperations', 'Invalid mind map spec');
            return null;
        }
        
        // Collect branches and sub-items to delete
        const branchesToDelete = new Set();
        const subItemsToDelete = new Map(); // Map of branchIndex -> Set of childIndices
        let attemptedTopicDelete = false;
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                this.logger.warn('MindMapOperations', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            // Check if user is trying to delete the central topic
            if (nodeType === 'topic') {
                attemptedTopicDelete = true;
                return;
            }
            
            if (nodeType === 'branch') {
                const branchIndex = parseInt(element.attr('data-array-index') || element.attr('data-branch-index'));
                if (!isNaN(branchIndex) && branchIndex >= 0) {
                    branchesToDelete.add(branchIndex);
                    this.logger.debug('MindMapOperations', `Marking branch ${branchIndex} for deletion`);
                }
            } else if (nodeType === 'child' || nodeType === 'subitem') {
                const branchIndex = parseInt(element.attr('data-branch-index'));
                const childIndex = parseInt(element.attr('data-child-index') || element.attr('data-array-index'));
                
                if (!isNaN(branchIndex) && !isNaN(childIndex)) {
                    if (!subItemsToDelete.has(branchIndex)) {
                        subItemsToDelete.set(branchIndex, new Set());
                    }
                    subItemsToDelete.get(branchIndex).add(childIndex);
                    this.logger.debug('MindMapOperations', `Marking sub-item ${childIndex} of branch ${branchIndex} for deletion`);
                }
            }
        });
        
        // Show warning if user attempted to delete the central topic
        if (attemptedTopicDelete) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Central topic cannot be deleted',
                type: 'warning'
            });
        }
        
        // If no valid nodes to delete, return early
        if (branchesToDelete.size === 0 && subItemsToDelete.size === 0) {
            return spec;
        }
        
        // Delete sub-items first (within each branch, delete from highest index to lowest)
        subItemsToDelete.forEach((childIndices, branchIndex) => {
            if (branchIndex >= 0 && branchIndex < spec.children.length) {
                const branch = spec.children[branchIndex];
                if (Array.isArray(branch.children)) {
                    // Sort child indices descending to avoid index shifting
                    const sortedIndices = Array.from(childIndices).sort((a, b) => b - a);
                    sortedIndices.forEach(childIndex => {
                        if (childIndex >= 0 && childIndex < branch.children.length) {
                            branch.children.splice(childIndex, 1);
                            this.logger.debug('MindMapOperations', `Deleted sub-item ${childIndex} from branch ${branchIndex}`);
                        }
                    });
                }
            }
        });
        
        // Delete branches (sort by index descending to avoid index shifting)
        const sortedBranchIndices = Array.from(branchesToDelete).sort((a, b) => b - a);
        sortedBranchIndices.forEach(index => {
            if (index >= 0 && index < spec.children.length) {
                spec.children.splice(index, 1);
                this.logger.debug('MindMapOperations', `Deleted branch ${index}`);
            }
        });
        
        const totalDeleted = sortedBranchIndices.length + Array.from(subItemsToDelete.values()).reduce((sum, set) => sum + set.size, 0);
        this.logger.debug('MindMapOperations', `Deleted ${totalDeleted} node(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'mindmap',
            deletedCount: totalDeleted,
            spec
        });
        
        // Emit operation completed for history
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'delete_nodes',
            snapshot: JSON.parse(JSON.stringify(spec))
        });
        
        // For mind maps, we need to recalculate layout from backend before rendering
        // Emit event to request layout recalculation
        this.eventBus.emit('mindmap:layout_recalculation_requested', {
            spec
        });
        
        return spec;
    }
    
    /**
     * Update a node in Mind Map
     * Updates both spec and _layout.positions if available
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec) {
            this.logger.error('MindMapOperations', 'Invalid mind map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('MindMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        
        // Declare branchIndex and childIndex at function scope
        let branchIndex = NaN;
        let childIndex = NaN;
        
        if (nodeType === 'topic') {
            // Update the central topic
            if (updates.text !== undefined) {
                spec.topic = updates.text;
            }
        } else if (nodeType === 'branch') {
            // Update branch label in children array
            branchIndex = parseInt(shapeElement.attr('data-branch-index'));
            if (!isNaN(branchIndex) && Array.isArray(spec.children)) {
                if (spec.children[branchIndex] && updates.text !== undefined) {
                    spec.children[branchIndex].label = updates.text;
                }
            }
        } else if (nodeType === 'child') {
            // Update child label in nested children array
            branchIndex = parseInt(shapeElement.attr('data-branch-index'));
            childIndex = parseInt(shapeElement.attr('data-child-index'));
            if (!isNaN(branchIndex) && !isNaN(childIndex) && 
                Array.isArray(spec.children) &&
                spec.children[branchIndex] &&
                Array.isArray(spec.children[branchIndex].children)) {
                if (spec.children[branchIndex].children[childIndex] && updates.text !== undefined) {
                    spec.children[branchIndex].children[childIndex].label = updates.text;
                }
            }
        }
        
        // Update the text in positions as well (if layout exists)
        // IMPORTANT: Also delete width/height so renderer recalculates based on new text
        if (spec._layout && spec._layout.positions && updates.text !== undefined) {
            const positions = spec._layout.positions;
            if (nodeType === 'topic' && positions.topic) {
                positions.topic.text = updates.text;
                // Clear dimensions so renderer recalculates based on new text
                delete positions.topic.width;
                delete positions.topic.height;
            } else if (nodeType === 'branch' && !isNaN(branchIndex) && positions[`branch_${branchIndex}`]) {
                positions[`branch_${branchIndex}`].text = updates.text;
                // Clear dimensions so renderer recalculates based on new text
                delete positions[`branch_${branchIndex}`].width;
                delete positions[`branch_${branchIndex}`].height;
            } else if (nodeType === 'child' && !isNaN(branchIndex) && !isNaN(childIndex) && positions[`child_${branchIndex}_${childIndex}`]) {
                positions[`child_${branchIndex}_${childIndex}`].text = updates.text;
                // Clear dimensions so renderer recalculates based on new text
                delete positions[`child_${branchIndex}_${childIndex}`].width;
                delete positions[`child_${branchIndex}_${childIndex}`].height;
            }
        }
        
        this.logger.debug('MindMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'mindmap',
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
        
        // For mind maps, text changes may affect node heights (due to text wrapping)
        // which requires recalculating y-positions to maintain proper spacing
        // Emit event to request layout recalculation from backend
        if (updates.text !== undefined) {
            this.eventBus.emit('mindmap:layout_recalculation_requested', {
                spec
            });
        }
        
        // Emit event to request selection restoration after re-render
        this.eventBus.emit('mindmap:selection_restore_requested', {
            nodeId
        });
        
        return spec;
    }
    
    /**
     * Update branch numbers to follow clockwise order
     * Clockwise layout: Right side shows branches 0,1,2... (top to bottom)
     *                   Left side shows branches ...5,4,3 (reversed, bottom to top)
     * Clockwise reading order: 0, 1, 2, 3, 4, 5 (right top→bottom, then left bottom→top)
     * So branch numbers should be: Branch 1 (index 0), Branch 2 (index 1), ..., Branch 6 (index 5)
     * 
     * @param {Object} spec - Mind map spec
     * @private
     */
    _updateBranchNumbersForClockwise(spec) {
        if (!spec || !Array.isArray(spec.children)) {
            return;
        }
        
        const numBranches = spec.children.length;
        const newBranchText = window.languageManager?.translate('newBranch') || 'New Branch';
        const newSubitemText = window.languageManager?.translate('newSubitem') || 'Sub-item';
        
        // Update branch labels to follow clockwise numbering
        // Clockwise order: array index 0 = Branch 1, index 1 = Branch 2, etc.
        // This matches the visual clockwise reading order
        spec.children.forEach((branch, index) => {
            // Clockwise number is simply index + 1 (array order matches clockwise reading order)
            const clockwiseNumber = index + 1;
            
            // Update branch label (preserve user edits if label doesn't match pattern)
            const currentLabel = branch.label || branch.text || '';
            // Match patterns: "Branch 1", "分支1", "New Branch 1", "新分支1", etc.
            // Include both short and full forms of translations
            const branchPattern = /^(分支|新分支|Branch|New Branch)\s*\d+/i;
            
            // Only update if label matches the pattern (auto-generated)
            if (branchPattern.test(currentLabel)) {
                branch.label = `${newBranchText} ${clockwiseNumber}`;
                branch.text = `${newBranchText} ${clockwiseNumber}`;
            }
            
            // Update sub-item labels to match branch number
            if (Array.isArray(branch.children)) {
                branch.children.forEach((child, childIndex) => {
                    const childLabel = child.label || child.text || '';
                    // Match patterns: "Sub-item 1.1", "子项1.1", "New Subitem 1.1", "新子项1.1", etc.
                    // Include both short and full forms of translations
                    const childPattern = /^(子项|新子项|Sub-item|New Subitem)\s*\d+\.\d+/i;
                    
                    if (childPattern.test(childLabel)) {
                        child.label = `${newSubitemText} ${clockwiseNumber}.${childIndex + 1}`;
                        child.text = `${newSubitemText} ${clockwiseNumber}.${childIndex + 1}`;
                    }
                });
            }
        });
        
        this.logger.debug('MindMapOperations', `Updated branch numbers for clockwise order (${numBranches} branches)`);
    }
    
    /**
     * Validate Mind Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!spec.topic || typeof spec.topic !== 'string') {
            this.logger.warn('MindMapOperations', 'Invalid or missing topic');
            return false;
        }
        
        if (!Array.isArray(spec.children)) {
            this.logger.warn('MindMapOperations', 'Invalid or missing children array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('MindMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.MindMapOperations = MindMapOperations;

