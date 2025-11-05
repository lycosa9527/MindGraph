/**
 * State Manager - Centralized state management for MindGraph
 * 
 * Single source of truth for application state.
 * All state changes emit events via Event Bus.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * PROPRIETARY LICENSE - ALL RIGHTS RESERVED
 * 
 * This software and associated documentation files (the "Software") are the proprietary
 * and confidential information of 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.).
 * 
 * WITHOUT EXPLICIT WRITTEN PERMISSION FROM THE COPYRIGHT HOLDER, ALL USE IS PROHIBITED,
 * including but not limited to:
 * - Use, execution, or deployment
 * - Copying, downloading, or access
 * - Modification or creation of derivative works
 * - Distribution, redistribution, or sharing
 * - Commercial use or any production deployment
 * 
 * Unauthorized use may result in severe civil and criminal penalties.
 * 
 * For licensing inquiries, please contact the copyright holder.
 * 
 * @author WANG CUNCHI
 */

class StateManager {
    constructor(eventBus, logger) {
        this.eventBus = eventBus;
        this.logger = logger || console;
        
        // Initialize state structure
        this.state = this.getInitialState();
        
        // Create immutable proxy for external access
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.logger.info('StateManager', 'State Manager initialized', {
            initialState: this._getStateSnapshot()
        });
    }
    
    /**
     * Get initial state structure
     */
    getInitialState() {
        return {
            panels: {
                thinkguide: {
                    open: false,
                    sessionId: null,
                    isStreaming: false,
                    currentState: 'CONTEXT_GATHERING',
                    cognitiveConflicts: [], // Parsed cognitive conflict examples
                    currentMessage: '', // Current streaming buffer
                    messages: [] // Message history
                },
                mindmate: {
                    open: false,
                    conversationId: null,
                    isStreaming: false,
                    messages: [], // Message history
                    uploadedFiles: [] // File upload context
                },
                nodePalette: {
                    open: false,
                    suggestions: [], // Available node suggestions
                    selected: [], // Selected node IDs to add
                    mode: null // double_bubble, multi_flow, etc.
                },
                property: {
                    open: false,
                    nodeId: null,
                    nodeData: null
                }
            },
            diagram: {
                type: null, // tree, flow, bubble, etc.
                sessionId: null,
                data: null, // Current diagram spec
                selectedNodes: [], // Currently selected node IDs
                history: [], // Undo/redo stack
                historyIndex: -1
            },
            voice: {
                active: false,
                sessionId: null,
                lastTranscription: '', // Last user speech
                isListening: false,
                isSpeaking: false
            },
            ui: {
                theme: 'light',
                language: 'en',
                mobile: false
            }
        };
    }
    
    /**
     * Get full state (read-only)
     */
    getState() {
        return this.readOnlyState;
    }
    
    /**
     * Get specific panel state (read-only)
     */
    getPanelState(panelName) {
        return this.state.panels[panelName] ? 
            this.createReadOnlyProxy(this.state.panels[panelName]) : 
            null;
    }
    
    /**
     * Get diagram state (read-only)
     */
    getDiagramState() {
        return this.createReadOnlyProxy(this.state.diagram);
    }
    
    /**
     * Get voice state (read-only)
     */
    getVoiceState() {
        return this.createReadOnlyProxy(this.state.voice);
    }
    
    /**
     * Open a panel (closes other panels based on rules)
     */
    openPanel(panelName, options = {}) {
        if (!this.state.panels[panelName]) {
            this.logger.error('StateManager', `Unknown panel: ${panelName}`);
            return false;
        }
        
        // Close exclusive panels (managed by Panel Coordinator)
        // For now, just update state
        this.state.panels[panelName] = {
            ...this.state.panels[panelName],
            open: true,
            ...options
        };
        
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:panel_opened', {
            panel: panelName,
            state: this.state.panels[panelName]
        });
        
        this.logger.debug('StateManager', `Panel opened: ${panelName}`, options);
        
        return true;
    }
    
    /**
     * Close a panel
     */
    closePanel(panelName) {
        if (!this.state.panels[panelName]) {
            this.logger.error('StateManager', `Unknown panel: ${panelName}`);
            return false;
        }
        
        this.state.panels[panelName].open = false;
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:panel_closed', {
            panel: panelName
        });
        
        this.logger.debug('StateManager', `Panel closed: ${panelName}`);
        
        return true;
    }
    
    /**
     * Update panel state
     */
    updatePanelState(panelName, updates) {
        if (!this.state.panels[panelName]) {
            this.logger.error('StateManager', `Unknown panel: ${panelName}`);
            return false;
        }
        
        this.state.panels[panelName] = {
            ...this.state.panels[panelName],
            ...updates
        };
        
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:panel_updated', {
            panel: panelName,
            updates
        });
        
        this.logger.debug('StateManager', `Panel updated: ${panelName}`, updates);
        
        return true;
    }
    
    /**
     * Set streaming status for a panel
     */
    setStreamingStatus(panelName, isStreaming) {
        return this.updatePanelState(panelName, { isStreaming });
    }
    
    /**
     * Add cognitive conflict to ThinkGuide state
     */
    addCognitiveConflict(conflict) {
        if (!this.state.panels.thinkguide.cognitiveConflicts) {
            this.state.panels.thinkguide.cognitiveConflicts = [];
        }
        
        this.state.panels.thinkguide.cognitiveConflicts.push(conflict);
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:cognitive_conflict_added', { conflict });
        
        this.logger.debug('StateManager', 'Cognitive conflict added', conflict);
    }
    
    /**
     * Update diagram state
     */
    updateDiagram(updates) {
        // Validate critical updates
        if (!this.validateStateUpdate(updates, 'diagram')) {
            this.logger.error('StateManager', 'Diagram update validation failed', updates);
            return false;
        }
        
        this.state.diagram = {
            ...this.state.diagram,
            ...updates
        };
        
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:diagram_updated', { updates });
        
        this.logger.debug('StateManager', 'Diagram updated', updates);
        
        return true;
    }
    
    /**
     * Set selected nodes
     */
    selectNodes(nodeIds) {
        const selectedNodes = Array.isArray(nodeIds) ? nodeIds : [nodeIds];
        
        // Validate selection
        if (!this.validateStateUpdate({ selectedNodes }, 'selection')) {
            this.logger.error('StateManager', 'Selection update validation failed', { nodeIds });
            return false;
        }
        
        this.state.diagram.selectedNodes = selectedNodes;
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:selection_changed', {
            selectedNodes: this.state.diagram.selectedNodes
        });
        
        this.logger.debug('StateManager', 'Selection changed', {
            count: this.state.diagram.selectedNodes.length,
            nodeIds: this.state.diagram.selectedNodes
        });
        
        return true;
    }
    
    /**
     * Update voice state
     */
    updateVoice(updates) {
        this.state.voice = {
            ...this.state.voice,
            ...updates
        };
        
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:voice_updated', { updates });
        
        this.logger.debug('StateManager', 'Voice state updated', updates);
        
        return true;
    }
    
    /**
     * Update UI state
     */
    updateUI(updates) {
        this.state.ui = {
            ...this.state.ui,
            ...updates
        };
        
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:ui_updated', { updates });
        
        this.logger.debug('StateManager', 'UI state updated', updates);
        
        return true;
    }
    
    /**
     * Reset state to initial
     */
    reset() {
        this.state = this.getInitialState();
        this.readOnlyState = this.createReadOnlyProxy(this.state);
        
        this.eventBus.emit('state:reset', {});
        
        this.logger.info('StateManager', 'State reset to initial');
    }
    
    /**
     * Create read-only proxy to prevent external modifications
     */
    createReadOnlyProxy(obj) {
        if (obj === null || typeof obj !== 'object') {
            return obj;
        }
        
        return new Proxy(obj, {
            set: (target, property, value) => {
                this.logger.error('StateManager', 'Attempted direct state mutation blocked', {
                    property,
                    value
                });
                console.error('[StateManager] Direct state mutation not allowed. Use StateManager methods instead.');
                return false;
            },
            deleteProperty: (target, property) => {
                this.logger.error('StateManager', 'Attempted state deletion blocked', {
                    property
                });
                console.error('[StateManager] Direct state deletion not allowed. Use StateManager methods instead.');
                return false;
            },
            get: (target, property) => {
                const value = target[property];
                // Recursively create proxies for nested objects
                if (value !== null && typeof value === 'object') {
                    return this.createReadOnlyProxy(value);
                }
                return value;
            }
        });
    }
    
    /**
     * Get state snapshot for logging (without proxy)
     */
    _getStateSnapshot() {
        return JSON.parse(JSON.stringify(this.state));
    }
    
    /**
     * Validate state update
     * ARCHITECTURE: Validates critical state updates to prevent invalid state transitions
     */
    validateStateUpdate(updates, updateType = 'diagram') {
        // Valid diagram types (from DiagramType enum and diagram-selector.js)
        const validDiagramTypes = [
            'bubble_map', 'bridge_map', 'tree_map', 'circle_map',
            'double_bubble_map', 'flow_map', 'brace_map', 'multi_flow_map',
            'concept_map', 'mindmap', 'mind_map',
            'factor_analysis', 'three_position_analysis', 'perspective_analysis',
            'goal_analysis', 'possibility_analysis', 'result_analysis',
            'five_w_one_h', 'whwm_analysis', 'four_quadrant', 'diagram'
        ];
        
        // Validate diagram type
        if (updateType === 'diagram' && updates.type) {
            if (!validDiagramTypes.includes(updates.type)) {
                this.logger.error('StateManager', 'Invalid diagram type', {
                    type: updates.type,
                    validTypes: validDiagramTypes
                });
                return false;
            }
        }
        
        // Validate session ID format (should be non-empty string)
        if (updates.sessionId !== undefined) {
            if (typeof updates.sessionId !== 'string' || updates.sessionId.trim() === '') {
                this.logger.error('StateManager', 'Invalid session ID', {
                    sessionId: updates.sessionId,
                    type: typeof updates.sessionId
                });
                return false;
            }
        }
        
        // Validate selected nodes (should be array of strings)
        if (updateType === 'selection' && updates.selectedNodes !== undefined) {
            if (!Array.isArray(updates.selectedNodes)) {
                this.logger.error('StateManager', 'Invalid selected nodes - must be array', {
                    selectedNodes: updates.selectedNodes,
                    type: typeof updates.selectedNodes
                });
                return false;
            }
            
            // Check if all items in array are strings
            if (updates.selectedNodes.some(id => typeof id !== 'string')) {
                this.logger.error('StateManager', 'Invalid selected nodes - all IDs must be strings', {
                    selectedNodes: updates.selectedNodes
                });
                return false;
            }
        }
        
        return true;
    }
}

// Create global instance (after Event Bus is loaded)
if (typeof window !== 'undefined') {
    // Wait for Event Bus to be available
    const initStateManager = () => {
        if (window.eventBus) {
            window.stateManager = new StateManager(window.eventBus, window.logger);
            
            // Expose debug tools
            window.debugState = {
                get: () => window.stateManager._getStateSnapshot(),
                reset: () => window.stateManager.reset(),
                panels: () => window.stateManager._getStateSnapshot().panels,
                diagram: () => window.stateManager._getStateSnapshot().diagram,
                voice: () => window.stateManager._getStateSnapshot().voice
            };
            
            if (window.logger?.debugMode) {
                console.log('%c[StateManager] Debug tools available:', 'color: #2196f3; font-weight: bold;');
                console.log('  window.debugState.get()     - View full state');
                console.log('  window.debugState.panels()  - View panel states');
                console.log('  window.debugState.diagram() - View diagram state');
                console.log('  window.debugState.voice()   - View voice state');
                console.log('  window.debugState.reset()   - Reset to initial state');
            }
        } else {
            // Retry after a short delay
            setTimeout(initStateManager, 50);
        }
    };
    
    initStateManager();
}

