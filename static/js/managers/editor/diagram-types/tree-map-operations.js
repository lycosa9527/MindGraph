/**
 * Tree Map Operations
 * ===================
 * 
 * Handles add/delete/update operations specific to Tree Maps.
 * Manages categories and leaves (children) with hierarchical structure, plus topic and dimension.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class TreeMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('TreeMapOperations', 'Tree Map Operations initialized');
    }
    
    /**
     * Add a new node to Tree Map
     * Requires node selection (category or leaf)
     * - Clicking on category → adds new category (with 3 children) after the selected category
     * - Clicking on leaf → adds new leaf to same category after the selected leaf
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.children)) {
            this.logger.error('TreeMapOperations', 'Invalid tree map spec');
            return null;
        }
        
        // Check if a node is selected
        const selectedNodes = editor?.selectedNodes ? Array.from(editor.selectedNodes) : [];
        if (selectedNodes.length === 0) {
            this.eventBus.emit('diagram:operation_warning', {
                message: 'Please select a category or leaf to add a new node',
                type: 'warning'
            });
            return null;
        }
        
        // Get the first selected node
        const selectedNodeId = selectedNodes[0];
        const selectedElement = d3.select(`[data-node-id="${selectedNodeId}"]`);
        
        if (selectedElement.empty()) {
            this.logger.error('TreeMapOperations', 'Selected node not found');
            return null;
        }
        
        const nodeType = selectedElement.attr('data-node-type');
        this.logger.debug('TreeMapOperations', 'Adding to tree map, selected node type:', nodeType);
        
        let addedNodeType = null;
        
        // Handle different node types
        switch (nodeType) {
            case 'category': {
                // Add new category (with 3 children) to children array
                const categoryIndex = parseInt(selectedElement.attr('data-category-index'));
                const newCategoryText = window.languageManager?.translate('newCategory') || 'New Category';
                const newItemText = window.languageManager?.translate('newItem') || 'New Item';
                const newCategory = {
                    text: newCategoryText,
                    children: [
                        { text: `${newItemText}1` },
                        { text: `${newItemText}2` },
                        { text: `${newItemText}3` }
                    ]
                };
                
                // Insert after selected category
                spec.children.splice(categoryIndex + 1, 0, newCategory);
                addedNodeType = 'category';
                
                this.logger.debug('TreeMapOperations', `Added new category after index ${categoryIndex}. Total categories: ${spec.children.length}`);
                
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' ? '新类别及3个子项已添加！' : 'New category added with 3 children!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'leaf': {
                // Add new leaf/child to the parent category
                const categoryIndex = parseInt(selectedElement.attr('data-category-index'));
                const leafIndex = parseInt(selectedElement.attr('data-leaf-index'));
                
                if (categoryIndex < 0 || categoryIndex >= spec.children.length) {
                    this.logger.error('TreeMapOperations', 'Invalid category index');
                    this.eventBus.emit('diagram:operation_warning', {
                        message: 'Invalid category index',
                        type: 'error'
                    });
                    return null;
                }
                
                const category = spec.children[categoryIndex];
                if (!Array.isArray(category.children)) {
                    category.children = [];
                }
                
                // Insert after selected leaf
                const newItemText = window.languageManager?.translate('newItem') || 'New Child';
                category.children.splice(leafIndex + 1, 0, { text: newItemText });
                addedNodeType = 'leaf';
                
                this.logger.debug('TreeMapOperations', `Added new child to category ${categoryIndex} after leaf ${leafIndex}. Total children: ${category.children.length}`);
                
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' ? '新子项已添加！' : 'New child added!';
                this.eventBus.emit('diagram:operation_warning', {
                    message: message,
                    type: 'success'
                });
                break;
            }
                
            case 'topic':
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Cannot add nodes to topic. Please select a category or child',
                    type: 'warning'
                });
                return null;
                
            default:
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Please select a category or child',
                    type: 'warning'
                });
                return null;
        }
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'tree_map',
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
     * Delete selected nodes from Tree Map (categories and leaves)
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.children)) {
            this.logger.error('TreeMapOperations', 'Invalid tree map spec');
            return null;
        }
        
        // Separate node IDs by type and collect indices
        const categoriesToDelete = [];
        const leavesToDelete = [];
        
        nodeIds.forEach(nodeId => {
            const element = d3.select(`[data-node-id="${nodeId}"]`);
            if (element.empty()) {
                this.logger.warn('TreeMapOperations', `Node ${nodeId} not found`);
                return;
            }
            
            const nodeType = element.attr('data-node-type');
            
            if (nodeType === 'topic') {
                // Don't allow deletion of root topic
                this.eventBus.emit('diagram:operation_warning', {
                    message: 'Root topic cannot be deleted',
                    type: 'warning'
                });
                return;
            } else if (nodeType === 'category') {
                const categoryIndex = parseInt(element.attr('data-category-index'));
                if (!isNaN(categoryIndex)) {
                    categoriesToDelete.push(categoryIndex);
                }
            } else if (nodeType === 'leaf') {
                const categoryIndex = parseInt(element.attr('data-category-index'));
                const leafIndex = parseInt(element.attr('data-leaf-index'));
                if (!isNaN(categoryIndex) && !isNaN(leafIndex)) {
                    leavesToDelete.push({ categoryIndex, leafIndex });
                }
            }
        });
        
        this.logger.debug('TreeMapOperations', 'Deleting nodes', { categoriesToDelete, leavesToDelete });
        
        // Delete leaves first (sort by leaf index descending within each category)
        // Group by category
        const leavesByCategory = {};
        leavesToDelete.forEach(({ categoryIndex, leafIndex }) => {
            if (!leavesByCategory[categoryIndex]) {
                leavesByCategory[categoryIndex] = [];
            }
            leavesByCategory[categoryIndex].push(leafIndex);
        });
        
        // Sort and delete leaves within each category
        Object.keys(leavesByCategory).forEach(catIdx => {
            const categoryIndex = parseInt(catIdx);
            if (categoryIndex >= 0 && categoryIndex < spec.children.length) {
                const category = spec.children[categoryIndex];
                if (Array.isArray(category.children)) {
                    // Sort leaf indices descending to avoid index shifting
                    const sortedLeafIndices = leavesByCategory[catIdx].sort((a, b) => b - a);
                    sortedLeafIndices.forEach(leafIndex => {
                        if (leafIndex >= 0 && leafIndex < category.children.length) {
                            category.children.splice(leafIndex, 1);
                            this.logger.debug('TreeMapOperations', `Deleted leaf ${leafIndex} from category ${categoryIndex}`);
                        }
                    });
                }
            }
        });
        
        // Delete categories (sort by index descending to avoid index shifting)
        const sortedCategoryIndices = categoriesToDelete.sort((a, b) => b - a);
        sortedCategoryIndices.forEach(index => {
            if (index >= 0 && index < spec.children.length) {
                spec.children.splice(index, 1);
                this.logger.debug('TreeMapOperations', `Deleted category ${index}`);
            }
        });
        
        const deletedCount = categoriesToDelete.length + leavesToDelete.length;
        this.logger.debug('TreeMapOperations', `Deleted ${deletedCount} node(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'tree_map',
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
     * Update a node in Tree Map
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec) {
            this.logger.error('TreeMapOperations', 'Invalid tree map spec');
            return null;
        }
        
        // Find the node
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('TreeMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        const nodeType = shapeElement.attr('data-node-type');
        
        if (nodeType === 'topic') {
            // Update the root topic
            if (updates.text !== undefined) {
                spec.topic = updates.text;
            }
        } else if (nodeType === 'dimension') {
            // Update the classification dimension
            if (updates.text !== undefined) {
                spec.dimension = updates.text;
            }
        } else if (nodeType === 'category') {
            // Update category text in children array
            const categoryIndex = parseInt(shapeElement.attr('data-category-index'));
            if (!isNaN(categoryIndex) && spec.children && categoryIndex < spec.children.length) {
                if (updates.text !== undefined) {
                    spec.children[categoryIndex].text = updates.text;
                }
            }
        } else if (nodeType === 'leaf') {
            // Update leaf text within its category
            const categoryIndex = parseInt(shapeElement.attr('data-category-index'));
            const leafIndex = parseInt(shapeElement.attr('data-leaf-index'));
            if (!isNaN(categoryIndex) && !isNaN(leafIndex) && 
                spec.children && categoryIndex < spec.children.length) {
                const category = spec.children[categoryIndex];
                if (Array.isArray(category.children) && leafIndex < category.children.length) {
                    if (updates.text !== undefined) {
                        // Handle both object and string formats
                        if (typeof category.children[leafIndex] === 'object') {
                            category.children[leafIndex].text = updates.text;
                        } else {
                            category.children[leafIndex] = updates.text;
                        }
                    }
                }
            }
        }
        
        this.logger.debug('TreeMapOperations', 'Updated node', {
            nodeId,
            nodeType,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'tree_map',
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
     * Validate Tree Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!spec.topic || typeof spec.topic !== 'string') {
            this.logger.warn('TreeMapOperations', 'Invalid or missing topic');
            return false;
        }
        
        if (!Array.isArray(spec.children)) {
            this.logger.warn('TreeMapOperations', 'Invalid or missing children array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('TreeMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.TreeMapOperations = TreeMapOperations;

