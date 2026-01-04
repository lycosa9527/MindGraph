/**
 * Concept Map Operations
 * ======================
 * 
 * Handles add/delete/update operations specific to Concept Maps.
 * Manages concepts (freeform nodes with positions) and connections.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class ConceptMapOperations {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        this.logger.info('ConceptMapOperations', 'Concept Map Operations initialized');
    }
    
    /**
     * Add a new concept node to Concept Map
     * @param {Object} spec - Current diagram spec
     * @param {Object} editor - Editor instance
     * @returns {Object} Updated spec
     */
    addNode(spec, editor) {
        if (!spec || !Array.isArray(spec.concepts)) {
            this.logger.error('ConceptMapOperations', 'Invalid concept map spec');
            return null;
        }
        
        // Add new concept to spec with language support
        const newConceptText = window.languageManager?.translate('newConcept') || 'New Concept';
        spec.concepts.push({
            text: newConceptText,
            x: 400,
            y: 300
        });
        
        this.logger.debug('ConceptMapOperations', `Added new concept. Total concepts: ${spec.concepts.length}`);
        
        // Emit node added event
        this.eventBus.emit('diagram:node_added', {
            diagramType: 'concept_map',
            nodeType: 'concept',
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
     * Delete selected concept nodes from Concept Map
     * Also removes connections involving deleted nodes
     * @param {Object} spec - Current diagram spec
     * @param {Array} nodeIds - Node IDs to delete
     * @returns {Object} Updated spec
     */
    deleteNodes(spec, nodeIds) {
        if (!spec || !Array.isArray(spec.concepts)) {
            this.logger.error('ConceptMapOperations', 'Invalid concept map spec');
            return null;
        }
        
        // Collect node texts to delete from spec
        const textsToDelete = new Set();
        
        nodeIds.forEach(nodeId => {
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                // Find associated text to match with spec
                const parentGroup = shapeElement.node()?.parentNode;
                let nodeText = '';
                
                if (parentGroup && parentGroup.tagName === 'g') {
                    const textElement = d3.select(parentGroup).select('text');
                    if (!textElement.empty()) {
                        // Use extractTextFromSVG to properly read tspan content
                        nodeText = (typeof window.extractTextFromSVG === 'function')
                            ? window.extractTextFromSVG(textElement)
                            : textElement.text();
                    }
                } else {
                    const textElement = d3.select(`[data-text-for="${nodeId}"]`);
                    if (!textElement.empty()) {
                        // Use extractTextFromSVG to properly read tspan content
                        nodeText = (typeof window.extractTextFromSVG === 'function')
                            ? window.extractTextFromSVG(textElement)
                            : textElement.text();
                    }
                }
                
                if (nodeText) {
                    textsToDelete.add(nodeText);
                }
            }
        });
        
        // Remove from concepts array
        spec.concepts = spec.concepts.filter(
            concept => !textsToDelete.has(concept.text)
        );
        
        // Remove connections involving deleted nodes
        if (Array.isArray(spec.connections)) {
            spec.connections = spec.connections.filter(
                conn => !textsToDelete.has(conn.from) && !textsToDelete.has(conn.to)
            );
        }
        
        const deletedCount = textsToDelete.size;
        this.logger.debug('ConceptMapOperations', `Deleted ${deletedCount} concept node(s)`);
        
        // Emit nodes deleted event
        this.eventBus.emit('diagram:nodes_deleted', {
            diagramType: 'concept_map',
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
     * Update a concept node in Concept Map
     * Concept maps use generic text update (text is stored in spec.concepts)
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID
     * @param {Object} updates - Updates to apply
     * @returns {Object} Updated spec
     */
    updateNode(spec, nodeId, updates) {
        if (!spec || !Array.isArray(spec.concepts)) {
            this.logger.error('ConceptMapOperations', 'Invalid concept map spec');
            return null;
        }
        
        // Find the concept by matching text from the DOM
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (shapeElement.empty()) {
            this.logger.warn('ConceptMapOperations', `Node not found: ${nodeId}`);
            return spec;
        }
        
        // Find associated text to match with spec
        const parentGroup = shapeElement.node()?.parentNode;
        let nodeText = '';
        
        if (parentGroup && parentGroup.tagName === 'g') {
            const textElement = d3.select(parentGroup).select('text');
            if (!textElement.empty()) {
                // Use extractTextFromSVG to properly read tspan content
                nodeText = (typeof window.extractTextFromSVG === 'function')
                    ? window.extractTextFromSVG(textElement)
                    : textElement.text();
            }
        } else {
            const textElement = d3.select(`[data-text-for="${nodeId}"]`);
            if (!textElement.empty()) {
                // Use extractTextFromSVG to properly read tspan content
                nodeText = (typeof window.extractTextFromSVG === 'function')
                    ? window.extractTextFromSVG(textElement)
                    : textElement.text();
            }
        }
        
        // Initialize node dimensions metadata if it doesn't exist
        if (!spec._node_dimensions) {
            spec._node_dimensions = {};
        }
        
        // Find the concept in spec and update it
        if (nodeText && updates.text !== undefined) {
            const concept = spec.concepts.find(c => c.text === nodeText);
            if (concept) {
                // Check if we should preserve dimensions (when emptying node)
                const preservedWidth = shapeElement.attr('data-preserved-width');
                const preservedHeight = shapeElement.attr('data-preserved-height');
                const preservedRadius = shapeElement.attr('data-preserved-radius');
                
                if ((preservedWidth && preservedHeight || preservedRadius) && updates.text === '') {
                    // Use the old text as key since we're updating it
                    const nodeKey = `concept-${nodeText}`;
                    spec._node_dimensions[nodeKey] = {};
                    if (preservedWidth && preservedHeight) {
                        spec._node_dimensions[nodeKey].w = parseFloat(preservedWidth);
                        spec._node_dimensions[nodeKey].h = parseFloat(preservedHeight);
                    }
                    if (preservedRadius) {
                        spec._node_dimensions[nodeKey].r = parseFloat(preservedRadius);
                    }
                    // Also store with new (empty) text key for lookup after update
                    spec._node_dimensions[`concept-${updates.text}`] = spec._node_dimensions[nodeKey];
                    this.logger.debug('ConceptMapOperations', 'Preserved dimensions for empty concept node', {
                        nodeKey,
                        dimensions: spec._node_dimensions[nodeKey]
                    });
                }
                
                // Update the text in the concept
                const oldText = concept.text;
                concept.text = updates.text;
                
                // Update connections that reference this concept
                if (Array.isArray(spec.connections)) {
                    spec.connections.forEach(conn => {
                        if (conn.from === oldText) {
                            conn.from = updates.text;
                        }
                        if (conn.to === oldText) {
                            conn.to = updates.text;
                        }
                    });
                }
                
                this.logger.debug('ConceptMapOperations', `Updated concept from "${oldText}" to "${updates.text}"`);
            }
        }
        
        // Update position if provided
        if (updates.x !== undefined || updates.y !== undefined) {
            const concept = spec.concepts.find(c => c.text === (updates.text || nodeText));
            if (concept) {
                if (updates.x !== undefined) {
                    concept.x = updates.x;
                }
                if (updates.y !== undefined) {
                    concept.y = updates.y;
                }
            }
        }
        
        this.logger.debug('ConceptMapOperations', 'Updated node', {
            nodeId,
            updates
        });
        
        // Emit node updated event
        this.eventBus.emit('diagram:node_updated', {
            diagramType: 'concept_map',
            nodeId,
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
     * Save node styles to spec
     * @param {Object} spec - Current diagram spec
     * @param {string} nodeId - Node ID (concept node identifier)
     * @param {Object} styles - Style properties (fill, stroke, strokeWidth, fontSize, textColor, etc.)
     * @returns {Object} Updated spec
     */
    saveNodeStyles(spec, nodeId, styles) {
        if (!spec) {
            this.logger.error('ConceptMapOperations', 'Invalid spec');
            return null;
        }
        
        // Initialize _node_styles if it doesn't exist
        if (!spec._node_styles) {
            spec._node_styles = {};
        }
        
        // Merge with existing styles (preserve other properties)
        if (!spec._node_styles[nodeId]) {
            spec._node_styles[nodeId] = {};
        }
        
        // Save/update styles for this node
        Object.assign(spec._node_styles[nodeId], styles);
        
        this.logger.debug('ConceptMapOperations', 'Saved node styles', {
            nodeId,
            styles: Object.keys(styles)
        });
        
        return spec;
    }
    
    /**
     * Validate Concept Map spec
     * @param {Object} spec - Diagram spec
     * @returns {boolean} Whether spec is valid
     */
    validateSpec(spec) {
        if (!spec) {
            return false;
        }
        
        if (!Array.isArray(spec.concepts)) {
            this.logger.warn('ConceptMapOperations', 'Invalid or missing concepts array');
            return false;
        }
        
        return true;
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('ConceptMapOperations', 'Destroying');
        
        // This manager doesn't register event listeners (only emits)
        // Just nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.ConceptMapOperations = ConceptMapOperations;

