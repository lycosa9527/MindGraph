/**
 * Diagram Operations Loader
 * =========================
 * 
 * Dynamically loads and manages diagram-specific operations modules.
 * Provides a single interface for all diagram operations (add/delete/update).
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class DiagramOperationsLoader {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'DiagramOperationsLoader';
        
        // Operations registry - maps diagram type to operation class
        this.operationsRegistry = {
            'circle_map': CircleMapOperations,
            'bubble_map': BubbleMapOperations,
            'double_bubble_map': DoubleBubbleMapOperations,
            'brace_map': BraceMapOperations,
            'bridge_map': BridgeMapOperations,
            'tree_map': TreeMapOperations,
            'flow_map': FlowMapOperations,
            'multi_flow_map': MultiFlowMapOperations,
            'concept_map': ConceptMapOperations,
            'mindmap': MindMapOperations,
            'factor_analysis': MindMapOperations, // Uses same structure as mind map
            'four_quadrant': MindMapOperations // Uses same structure as mind map
        };
        
        this.currentOperations = null;
        this.currentDiagramType = null;
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('DiagramOperationsLoader', 'Diagram Operations Loader initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for diagram type changes
        this.eventBus.onWithOwner('diagram:type_changed', (data) => {
            this.loadOperations(data.diagramType);
        }, this.ownerId);
        
        // Listen for diagram loaded
        this.eventBus.onWithOwner('diagram:loaded', (data) => {
            this.loadOperations(data.diagramType);
        }, this.ownerId);
        
        // Listen for diagram rendered (ensure operations are loaded)
        this.eventBus.onWithOwner('diagram:rendered', (data) => {
            if (data.diagramType && data.diagramType !== this.currentDiagramType) {
                this.loadOperations(data.diagramType);
            }
        }, this.ownerId);
        
        this.logger.debug('DiagramOperationsLoader', 'Subscribed to events');
    }
    
    /**
     * Load operations for a specific diagram type
     * @param {string} diagramType - Diagram type (circle_map, bubble_map, etc.)
     */
    loadOperations(diagramType) {
        if (!diagramType) {
            this.logger.warn('DiagramOperationsLoader', 'No diagram type provided');
            this.currentOperations = null;
            this.currentDiagramType = null;
            return;
        }
        
        // If already loaded for this type, skip
        if (this.currentDiagramType === diagramType && this.currentOperations) {
            this.logger.debug('DiagramOperationsLoader', `Operations already loaded for ${diagramType}`);
            return;
        }
        
        const OperationsClass = this.operationsRegistry[diagramType];
        
        if (!OperationsClass) {
            this.logger.warn('DiagramOperationsLoader', 
                `No operations handler for ${diagramType} - operations not yet extracted`);
            this.currentOperations = null;
            this.currentDiagramType = diagramType;
            
            // Emit event that operations are not available (fallback to old methods)
            this.eventBus.emit('diagram:operations_unavailable', {
                diagramType: diagramType
            });
            return;
        }
        
        try {
            // Create new instance
            this.currentOperations = new OperationsClass(
                this.eventBus,
                this.stateManager,
                this.logger
            );
            
            this.currentDiagramType = diagramType;
            
            this.logger.info('DiagramOperationsLoader', `Operations loaded for ${diagramType}`);
            
            // Emit event that operations are loaded
            this.eventBus.emit('diagram:operations_loaded', {
                diagramType: diagramType,
                operations: this.currentOperations
            });
        } catch (error) {
            this.logger.error('DiagramOperationsLoader', `Failed to load operations for ${diagramType}`, error);
            this.currentOperations = null;
            this.currentDiagramType = diagramType;
            
            // Emit error event
            this.eventBus.emit('diagram:operations_load_error', {
                diagramType: diagramType,
                error: error.message
            });
        }
    }
    
    /**
     * Get current operations instance
     * @returns {Object|null} Current operations instance or null if not available
     */
    getOperations() {
        return this.currentOperations;
    }
    
    /**
     * Check if operations are available for current diagram type
     * @returns {boolean} True if operations are available
     */
    hasOperations() {
        return this.currentOperations !== null;
    }
    
    /**
     * Register a new operations class
     * @param {string} diagramType - Diagram type
     * @param {Function} OperationsClass - Operations class constructor
     */
    registerOperations(diagramType, OperationsClass) {
        this.operationsRegistry[diagramType] = OperationsClass;
        this.logger.debug('DiagramOperationsLoader', `Registered operations for ${diagramType}`);
        
        // If this is the current diagram type, reload operations
        if (this.currentDiagramType === diagramType) {
            this.loadOperations(diagramType);
        }
    }
    
    /**
     * Get list of available diagram types
     * @returns {Array} Array of diagram types with operations available
     */
    getAvailableDiagramTypes() {
        return Object.keys(this.operationsRegistry).filter(
            type => this.operationsRegistry[type] !== null
        );
    }
    
    /**
     * Get list of diagram types that need operations extraction
     * @returns {Array} Array of diagram types without operations
     */
    getPendingDiagramTypes() {
        return Object.keys(this.operationsRegistry).filter(
            type => this.operationsRegistry[type] === null
        );
    }
    
    /**
     * Cleanup on destroy
     */
    destroy() {
        this.logger.debug('DiagramOperationsLoader', 'Destroying');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('DiagramOperationsLoader', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        // Clear current operations
        this.currentOperations = null;
        this.currentDiagramType = null;
        
        // Clear registry (optional - might want to keep for future use)
        // this.operationsRegistry = {};
    }
}

