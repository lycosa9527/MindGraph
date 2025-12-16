/**
 * InteractiveEditor - Main controller for the interactive diagram editor
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

class InteractiveEditor {
    constructor(diagramType, template) {
        this.diagramType = diagramType;
        this.currentSpec = template;
        this.selectedNodes = new Set();
        this.history = [];
        this.historyIndex = -1;
        
        // Session info (will be set by DiagramSelector)
        this.sessionId = null;
        this.sessionDiagramType = null;
        
        // Track current canvas sizing mode
        // true = sized with panel space reserved, false = full width
        this.isSizedForPanel = false;
        
        // Initialize Event Bus and State Manager references (early, before selection callback)
        this.eventBus = window.eventBus;
        this.stateManager = window.stateManager;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'InteractiveEditor';
        
        // Initialize components
        this.selectionManager = new SelectionManager();
        this.canvasManager = new CanvasManager();
        this.toolbarManager = null; // Will be initialized after render
        this.renderer = null;
        
        // Initialize modules reference (will be populated by DiagramSelector)
        this.modules = null;
        
        // Store event handler references for cleanup
        this.eventHandlers = {
            orientationChange: null,
            windowResize: null,
            resetViewClick: null
        };
        
        // Store Event Bus listener callbacks (still needed for callback references)
        this.eventBusListeners = {};
        
        // Log editor initialization
        logger.debug('Editor', 'Editor created', { 
            diagramType, 
            hasTemplate: !!template 
        });
        
        // Bind selection change callback
        this.selectionManager.setSelectionChangeCallback((selectedNodes) => {
            this.selectedNodes = new Set(selectedNodes);
            
            // Verbose logging: Log node selection changes
            logger.debug('InteractiveEditor', 'Node Selection Changed', {
                count: selectedNodes.length,
                nodeIds: Array.from(selectedNodes),
                diagramType: this.diagramType,
                timestamp: Date.now()
            });
            
            // Emit selection changed event (InteractionHandler will also emit, but this ensures it's always emitted)
            if (this.eventBus) {
                this.eventBus.emit('interaction:selection_changed', {
                    selectedNodes: Array.from(selectedNodes)
                });
            }
            
            // Update state manager (use updateDiagram method)
            if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                this.stateManager.updateDiagram({
                    selectedNodes: Array.from(selectedNodes)
                });
            }
            
            this.updateToolbarState();
        });
    }
    
    /**
     * Legacy log method - now uses centralized logger
     * @deprecated Use logger.debug/info/warn/error directly
     */
    log(message, data = null) {
        logger.debug('Editor', message, data);
    }
    
    /**
     * Get translated notification message
     * @param {string} key - Notification key from language-manager
     * @param  {...any} args - Arguments for function-based notifications
     */
    getNotif(key, ...args) {
        if (window.languageManager && window.languageManager.getNotification) {
            return window.languageManager.getNotification(key, ...args);
        }
        return key; // Fallback to key if language manager not available
    }
    
    /**
     * Validate that we're operating within the correct session
     */
    validateSession(operation = 'Operation') {
        if (!this.sessionId) {
            logger.error('Editor', `${operation} blocked - No session ID set!`);
            return false;
        }
        
        if (this.diagramType !== this.sessionDiagramType) {
            logger.error('Editor', `${operation} blocked - Diagram type mismatch!`, {
                editorType: this.diagramType,
                sessionType: this.sessionDiagramType,
                sessionId: this.sessionId
            });
            return false;
        }
        
        // Cross-check with DiagramSelector session
        if (window.diagramSelector?.currentSession) {
            if (window.diagramSelector.currentSession.id !== this.sessionId) {
                logger.error('Editor', `${operation} blocked - Session ID mismatch!`, {
                    editorSession: this.sessionId,
                    selectorSession: window.diagramSelector.currentSession.id
                });
                return false;
            }
            
            if (window.diagramSelector.currentSession.diagramType !== this.diagramType) {
                logger.error('Editor', `${operation} blocked - DiagramSelector session type mismatch!`);
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * Detect if user is on mobile device
     */
    isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) 
            || window.innerWidth <= 768;
    }
    
    /**
     * Initialize the editor
     */
    initialize() {
        logger.info('Editor', `Initializing editor for ${this.diagramType}`);
        
        // CRITICAL: Update State Manager with diagram type (single source of truth)
        if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
            this.stateManager.updateDiagram({
                type: this.diagramType,
                data: this.currentSpec
            });
            logger.debug('InteractiveEditor', 'Updated State Manager with diagram type', {
                diagramType: this.diagramType
            });
        }
        
        // Setup canvas
        this.canvasManager.setupCanvas('#d3-container', {
            minHeight: '600px',
            backgroundColor: '#f5f5f5'
        });
        
        // Update school name display immediately and also after a short delay
        // (to ensure auth data is loaded if it wasn't ready)
        this.updateSchoolNameDisplay();
        setTimeout(() => {
            this.updateSchoolNameDisplay();
        }, 500);
        
        // Save initial state to history (so user can undo back to start)
        this.saveToHistory('initial_load', { diagramType: this.diagramType });
        
        // Event Bus and State Manager already initialized in constructor
        
        // Subscribe to events
        if (this.eventBus) {
            // Listen for render requests from ViewManager (e.g., after orientation flip)
            this.eventBusListeners.renderRequested = (data) => {
                if (data.spec) {
                    this.currentSpec = data.spec;
                    this.renderDiagram();
                }
            };
            this.eventBus.onWithOwner('diagram:render_requested', this.eventBusListeners.renderRequested, this.ownerId);
            
            // Listen for operations loaded to ensure operations are available
            this.eventBusListeners.operationsLoaded = (data) => {
                logger.debug('InteractiveEditor', `Operations loaded for ${data.diagramType}`);
            };
            this.eventBus.onWithOwner('diagram:operations_loaded', this.eventBusListeners.operationsLoaded, this.ownerId);
            
            // Listen for operations unavailable (fallback to old methods)
            this.eventBusListeners.operationsUnavailable = (data) => {
                logger.warn('InteractiveEditor', `Operations not available for ${data.diagramType} - using fallback methods`);
            };
            this.eventBus.onWithOwner('diagram:operations_unavailable', this.eventBusListeners.operationsUnavailable, this.ownerId);
            
            // Listen for diagram operations (from operations modules)
            this.eventBusListeners.nodeAdded = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring diagram:node_added - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // CRITICAL: Use State Manager as source of truth - update it if event has different type
                if (data.diagramType && data.diagramType !== this.diagramType) {
                    logger.warn('InteractiveEditor', `Diagram type mismatch: event has ${data.diagramType}, editor has ${this.diagramType}. Updating State Manager.`);
                    // Update State Manager (single source of truth)
                    if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                        this.stateManager.updateDiagram({ type: data.diagramType });
                    }
                    this.diagramType = data.diagramType;
                }
                this.renderDiagram();
            };
            this.eventBus.onWithOwner('diagram:node_added', this.eventBusListeners.nodeAdded, this.ownerId);
            
            this.eventBusListeners.nodesDeleted = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring diagram:nodes_deleted - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // CRITICAL: Use State Manager as source of truth - update it if event has different type
                if (data.diagramType && data.diagramType !== this.diagramType) {
                    logger.warn('InteractiveEditor', `Diagram type mismatch: event has ${data.diagramType}, editor has ${this.diagramType}. Updating State Manager.`);
                    // Update State Manager (single source of truth)
                    if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                        this.stateManager.updateDiagram({ type: data.diagramType });
                    }
                    this.diagramType = data.diagramType;
                }
                // ARCHITECTURE: Clear selection via State Manager (single source of truth)
                if (this.stateManager && typeof this.stateManager.selectNodes === 'function') {
                    this.stateManager.selectNodes([]);
                }
                // Clear local selection manager
                this.selectionManager.clearSelection();
                this.renderDiagram();
            };
            this.eventBus.onWithOwner('diagram:nodes_deleted', this.eventBusListeners.nodesDeleted, this.ownerId);
            
            this.eventBusListeners.nodeUpdated = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring diagram:node_updated - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // CRITICAL: Use State Manager as source of truth - update it if event has different type
                if (data.diagramType && data.diagramType !== this.diagramType) {
                    logger.warn('InteractiveEditor', `Diagram type mismatch: event has ${data.diagramType}, editor has ${this.diagramType}. Updating State Manager.`);
                    // Update State Manager (single source of truth)
                    if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
                        this.stateManager.updateDiagram({ type: data.diagramType });
                    }
                    this.diagramType = data.diagramType;
                }
                this.renderDiagram();
            };
            this.eventBus.onWithOwner('diagram:node_updated', this.eventBusListeners.nodeUpdated, this.ownerId);
            
            // Listen for spec updates (e.g., custom positions saved)
            this.eventBusListeners.specUpdated = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring diagram:spec_updated - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                    logger.info('InteractiveEditor', 'Spec updated, triggering re-render', {
                        diagramType: this.diagramType,
                        hasCustomPositions: !!(data.spec._customPositions && Object.keys(data.spec._customPositions).length > 0),
                        customPositionsCount: data.spec._customPositions ? Object.keys(data.spec._customPositions).length : 0
                    });
                    this.renderDiagram();
                }
            };
            this.eventBus.onWithOwner('diagram:spec_updated', this.eventBusListeners.specUpdated, this.ownerId);
            
            // Listen for Mind Map layout recalculation requests
            this.eventBusListeners.layoutRecalculationRequested = async (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring mindmap:layout_recalculation_requested - editor destroyed');
                    return;
                }
                if (data.spec) {
                    this.currentSpec = data.spec;
                }
                // Recalculate layout before rendering
                await this.recalculateMindMapLayout();
            };
            this.eventBus.onWithOwner('mindmap:layout_recalculation_requested', this.eventBusListeners.layoutRecalculationRequested, this.ownerId);
            
            // Listen for Mind Map selection restore requests (after text update)
            this.eventBusListeners.selectionRestoreRequested = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring mindmap:selection_restore_requested - editor destroyed');
                    return;
                }
                // The selection manager will handle this during render
                // This is just a notification that re-render may be needed
            };
            this.eventBus.onWithOwner('mindmap:selection_restore_requested', this.eventBusListeners.selectionRestoreRequested, this.ownerId);
            
            // Listen for history undo/redo completion events from HistoryManager
            this.eventBusListeners.historyUndoCompleted = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring history:undo_completed - editor destroyed');
                    return;
                }
                if (data.spec) {
                    // Restore the spec from history
                    this.currentSpec = JSON.parse(JSON.stringify(data.spec));
                    
                    // Clear selection (nodes may no longer exist)
                    this.selectionManager.clearSelection();
                    
                    // Re-render diagram with restored state
                    this.renderDiagram();
                    
                    logger.debug('InteractiveEditor', `Undo completed: ${data.action}`);
                }
            };
            this.eventBus.onWithOwner('history:undo_completed', this.eventBusListeners.historyUndoCompleted, this.ownerId);
            
            this.eventBusListeners.historyRedoCompleted = (data) => {
                // CRITICAL: Check if editor is destroyed before proceeding
                if (!this.selectionManager) {
                    logger.debug('InteractiveEditor', 'Ignoring history:redo_completed - editor destroyed');
                    return;
                }
                if (data.spec) {
                    // Restore the spec from history
                    this.currentSpec = JSON.parse(JSON.stringify(data.spec));
                    
                    // Clear selection (nodes may no longer exist)
                    this.selectionManager.clearSelection();
                    
                    // Re-render diagram with restored state
                    this.renderDiagram();
                    
                    logger.debug('InteractiveEditor', `Redo completed: ${data.action}`);
                }
            };
            this.eventBus.onWithOwner('history:redo_completed', this.eventBusListeners.historyRedoCompleted, this.ownerId);
            
            // ========== Voice Agent Events (Omni Agent control via Event Bus) ==========
            
            // Update center topic from voice command
            // LLM now returns structured data - no keyword parsing needed!
            this.eventBusListeners.voiceUpdateCenter = (data) => {
                if (!this.currentSpec) return;
                
                // Handle diagram-type-specific center updates using structured data from LLM
                if (this.diagramType === 'double_bubble_map') {
                    // Double bubble map: use left/right from structured data
                    const left = data.left;
                    const right = data.right;
                    if (left && right) {
                        this.currentSpec.left = left;
                        this.currentSpec.right = right;
                        this.renderDiagram();
                        this.saveToHistory('voice_update_center', { left, right });
                        logger.info('InteractiveEditor', `Voice: Updated double bubble map - left="${left}", right="${right}"`);
                    } else if (data.new_text) {
                        // Fallback: if LLM didn't parse properly, log warning
                        logger.warn('InteractiveEditor', 'Double bubble map update missing left/right fields, got:', data);
                    }
                    
                } else if (this.diagramType === 'flow_map') {
                    // Flow map uses 'title' field
                    const title = data.title;
                    if (title) {
                        this.currentSpec.title = title;
                        if (this.currentSpec.topic) this.currentSpec.topic = title;
                        this.renderDiagram();
                        this.saveToHistory('voice_update_center', { title });
                        logger.info('InteractiveEditor', `Voice: Updated flow map title to "${title}"`);
                    }
                    
                } else if (this.diagramType === 'multi_flow_map') {
                    // Multi-flow map uses 'event' field
                    const event = data.event;
                    if (event) {
                        this.currentSpec.event = event;
                        this.renderDiagram();
                        this.saveToHistory('voice_update_center', { event });
                        logger.info('InteractiveEditor', `Voice: Updated multi-flow map event to "${event}"`);
                    }
                    
                } else if (this.diagramType === 'brace_map') {
                    // Brace map uses 'whole' field
                    const whole = data.whole;
                    if (whole) {
                        this.currentSpec.whole = whole;
                        this.renderDiagram();
                        this.saveToHistory('voice_update_center', { whole });
                        logger.info('InteractiveEditor', `Voice: Updated brace map whole to "${whole}"`);
                    }
                    
                } else if (this.diagramType === 'bridge_map') {
                    // Bridge map uses 'dimension' field
                    const dimension = data.dimension;
                    if (dimension) {
                        this.currentSpec.dimension = dimension;
                        this.renderDiagram();
                        this.saveToHistory('voice_update_center', { dimension });
                        logger.info('InteractiveEditor', `Voice: Updated bridge map dimension to "${dimension}"`);
                    }
                    
                } else {
                    // Default: most diagrams use 'topic' field
                    // Backend sends 'new_text'
                    const text = data.new_text;
                    if (text) {
                        this.currentSpec.topic = text;
                        // Also update 'center.text' if it exists (for circle_map, bubble_map, etc.)
                        if (this.currentSpec.center && typeof this.currentSpec.center === 'object') {
                            this.currentSpec.center.text = text;
                        }
                        // CRITICAL: Some diagrams use _layout.positions for rendering center text
                        // Mindmap: uses _layout.positions['topic'].text
                        if (this.diagramType === 'mindmap' && this.currentSpec._layout && this.currentSpec._layout.positions) {
                            if (this.currentSpec._layout.positions['topic']) {
                                this.currentSpec._layout.positions['topic'].text = text;
                            }
                        }
                        // Circle map & Concept map: Update _layout.positions key if it exists
                        // These diagrams use spec.topic for rendering, but _layout.positions stores position by topic text key
                        if ((this.diagramType === 'circle_map' || this.diagramType === 'concept_map') && 
                            this.currentSpec._layout && this.currentSpec._layout.positions) {
                            // Find the old topic key (the one with position data)
                            const oldTopicKey = Object.keys(this.currentSpec._layout.positions).find(key => {
                                const pos = this.currentSpec._layout.positions[key];
                                return pos && (pos.x !== undefined || pos.y !== undefined);
                            });
                            if (oldTopicKey && oldTopicKey !== text) {
                                // Move position data to new key
                                this.currentSpec._layout.positions[text] = this.currentSpec._layout.positions[oldTopicKey];
                                delete this.currentSpec._layout.positions[oldTopicKey];
                            } else if (!oldTopicKey) {
                                // Create default position if none exists (for circle map)
                                if (this.diagramType === 'circle_map') {
                                    this.currentSpec._layout.positions[text] = { x: 350, y: 250 };
                                }
                            }
                        }
                        this.renderDiagram();
                        this.saveToHistory('voice_update_center', { text });
                        logger.info('InteractiveEditor', `Voice: Updated center to "${text}"`);
                    }
                }
            };
            this.eventBus.onWithOwner('diagram:update_center', this.eventBusListeners.voiceUpdateCenter, this.ownerId);
            
            // Update nodes from voice command
            this.eventBusListeners.voiceUpdateNodes = (data) => {
                if (!this.currentSpec || !data.nodes) return;
                
                // Handle diagram-type-specific node updates
                if (this.diagramType === 'double_bubble_map') {
                    // Double bubble map: nodes have categories (similarities, left_differences, right_differences)
                    data.nodes.forEach(update => {
                        if (!update.new_text) return;
                        const category = update.category || 'similarities'; // Default to similarities
                        const index = update.index !== undefined ? update.index : undefined;
                        
                        // Initialize arrays if needed
                        if (!this.currentSpec.similarities) this.currentSpec.similarities = [];
                        if (!this.currentSpec.left_differences) this.currentSpec.left_differences = [];
                        if (!this.currentSpec.right_differences) this.currentSpec.right_differences = [];
                        
                        // Update in appropriate category array
                        if (category === 'similarities') {
                            if (index !== undefined && index < this.currentSpec.similarities.length) {
                                this.currentSpec.similarities[index] = update.new_text;
                            } else if (index !== undefined) {
                                // Insert at specific position
                                while (this.currentSpec.similarities.length < index) {
                                    this.currentSpec.similarities.push('');
                                }
                                this.currentSpec.similarities[index] = update.new_text;
                            } else {
                                // Update first matching node or add to end
                                const foundIndex = this.currentSpec.similarities.findIndex((n, i) => 
                                    update.node_id && update.node_id.includes(`_${i}`)
                                );
                                if (foundIndex >= 0) {
                                    this.currentSpec.similarities[foundIndex] = update.new_text;
                                } else {
                                    this.currentSpec.similarities.push(update.new_text);
                                }
                            }
                        } else if (category === 'left_differences') {
                            if (index !== undefined && index < this.currentSpec.left_differences.length) {
                                this.currentSpec.left_differences[index] = update.new_text;
                            } else if (index !== undefined) {
                                while (this.currentSpec.left_differences.length < index) {
                                    this.currentSpec.left_differences.push('');
                                }
                                this.currentSpec.left_differences[index] = update.new_text;
                            } else {
                                const foundIndex = this.currentSpec.left_differences.findIndex((n, i) => 
                                    update.node_id && update.node_id.includes(`_${i}`)
                                );
                                if (foundIndex >= 0) {
                                    this.currentSpec.left_differences[foundIndex] = update.new_text;
                                } else {
                                    this.currentSpec.left_differences.push(update.new_text);
                                }
                            }
                        } else if (category === 'right_differences') {
                            if (index !== undefined && index < this.currentSpec.right_differences.length) {
                                this.currentSpec.right_differences[index] = update.new_text;
                            } else if (index !== undefined) {
                                while (this.currentSpec.right_differences.length < index) {
                                    this.currentSpec.right_differences.push('');
                                }
                                this.currentSpec.right_differences[index] = update.new_text;
                            } else {
                                const foundIndex = this.currentSpec.right_differences.findIndex((n, i) => 
                                    update.node_id && update.node_id.includes(`_${i}`)
                                );
                                if (foundIndex >= 0) {
                                    this.currentSpec.right_differences[foundIndex] = update.new_text;
                                } else {
                                    this.currentSpec.right_differences.push(update.new_text);
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'multi_flow_map') {
                    // Multi-flow map: nodes have categories (causes, effects)
                    data.nodes.forEach(update => {
                        if (!update.new_text) return;
                        const category = update.category || 'causes'; // Default to causes
                        const index = update.index !== undefined ? update.index : undefined;
                        
                        // Initialize arrays if needed
                        if (!this.currentSpec.causes) this.currentSpec.causes = [];
                        if (!this.currentSpec.effects) this.currentSpec.effects = [];
                        
                        // Update in appropriate category array
                        if (category === 'causes') {
                            if (index !== undefined && index < this.currentSpec.causes.length) {
                                this.currentSpec.causes[index] = update.new_text;
                            } else if (index !== undefined) {
                                while (this.currentSpec.causes.length < index) {
                                    this.currentSpec.causes.push('');
                                }
                                this.currentSpec.causes[index] = update.new_text;
                            } else {
                                const foundIndex = this.currentSpec.causes.findIndex((n, i) => 
                                    update.node_id && update.node_id.includes(`_${i}`)
                                );
                                if (foundIndex >= 0) {
                                    this.currentSpec.causes[foundIndex] = update.new_text;
                                } else {
                                    this.currentSpec.causes.push(update.new_text);
                                }
                            }
                        } else if (category === 'effects') {
                            if (index !== undefined && index < this.currentSpec.effects.length) {
                                this.currentSpec.effects[index] = update.new_text;
                            } else if (index !== undefined) {
                                while (this.currentSpec.effects.length < index) {
                                    this.currentSpec.effects.push('');
                                }
                                this.currentSpec.effects[index] = update.new_text;
                            } else {
                                const foundIndex = this.currentSpec.effects.findIndex((n, i) => 
                                    update.node_id && update.node_id.includes(`_${i}`)
                                );
                                if (foundIndex >= 0) {
                                    this.currentSpec.effects[foundIndex] = update.new_text;
                                } else {
                                    this.currentSpec.effects.push(update.new_text);
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'bridge_map') {
                    // Bridge map: nodes are analogies with left/right pairs
                    data.nodes.forEach(update => {
                        if (!this.currentSpec.analogies) this.currentSpec.analogies = [];
                        
                        const left = update.left;
                        const right = update.right;
                        const index = update.index !== undefined ? update.index : undefined;
                        
                        if (left && right) {
                            // Update as structured analogy pair
                            const analogy = { left: left, right: right };
                            if (index !== undefined && index < this.currentSpec.analogies.length) {
                                this.currentSpec.analogies[index] = analogy;
                            } else if (index !== undefined) {
                                while (this.currentSpec.analogies.length < index) {
                                    this.currentSpec.analogies.push('');
                                }
                                this.currentSpec.analogies[index] = analogy;
                            } else {
                                const foundIndex = this.currentSpec.analogies.findIndex((a, i) => 
                                    update.node_id && update.node_id.includes(`_${i}`)
                                );
                                if (foundIndex >= 0) {
                                    this.currentSpec.analogies[foundIndex] = analogy;
                                } else {
                                    this.currentSpec.analogies.push(analogy);
                                }
                            }
                        } else if (update.new_text) {
                            // Fallback: update text if left/right not provided
                            if (index !== undefined && index < this.currentSpec.analogies.length) {
                                this.currentSpec.analogies[index] = update.new_text;
                            } else {
                                const foundIndex = this.currentSpec.analogies.findIndex((a, i) => 
                                    update.node_id && update.node_id.includes(`_${i}`)
                                );
                                if (foundIndex >= 0) {
                                    this.currentSpec.analogies[foundIndex] = update.new_text;
                                } else {
                                    this.currentSpec.analogies.push(update.new_text);
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'tree_map') {
                    // Tree map: handle categories and items
                    data.nodes.forEach(update => {
                        if (!update.new_text) return;
                        
                        const categoryIndex = update.category_index !== undefined ? update.category_index : undefined;
                        const itemIndex = update.item_index !== undefined ? update.item_index : undefined;
                        
                        if (categoryIndex !== undefined && itemIndex !== undefined) {
                            // Updating an item within a category
                            if (this.currentSpec.children && 0 <= categoryIndex && categoryIndex < this.currentSpec.children.length) {
                                const category = this.currentSpec.children[categoryIndex];
                                if (category.children && Array.isArray(category.children) && 
                                    0 <= itemIndex && itemIndex < category.children.length) {
                                    const item = category.children[itemIndex];
                                    if (typeof item === 'object') {
                                        item.text = update.new_text;
                                    } else {
                                        category.children[itemIndex] = { text: update.new_text, children: [] };
                                    }
                                }
                            }
                        } else if (update.node_id) {
                            // Updating a category
                            const match = update.node_id.match(/_(\d+)$/);
                            const nodeIndex = match ? parseInt(match[1]) : null;
                            
                            if (this.currentSpec.children && Array.isArray(this.currentSpec.children)) {
                                if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.children.length) {
                                    const category = this.currentSpec.children[nodeIndex];
                                    if (typeof category === 'object') {
                                        category.text = update.new_text;
                                    } else {
                                        this.currentSpec.children[nodeIndex] = { text: update.new_text, children: [] };
                                    }
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'brace_map') {
                    // Brace map: handle parts and subparts
                    data.nodes.forEach(update => {
                        if (!update.new_text) return;
                        
                        const partIndex = update.part_index !== undefined ? update.part_index : undefined;
                        const subpartIndex = update.subpart_index !== undefined ? update.subpart_index : undefined;
                        
                        if (partIndex !== undefined && subpartIndex !== undefined) {
                            // Updating a subpart within a part
                            if (this.currentSpec.parts && 0 <= partIndex && partIndex < this.currentSpec.parts.length) {
                                const part = this.currentSpec.parts[partIndex];
                                if (part.subparts && Array.isArray(part.subparts) && 
                                    0 <= subpartIndex && subpartIndex < part.subparts.length) {
                                    const subpart = part.subparts[subpartIndex];
                                    if (typeof subpart === 'object') {
                                        subpart.name = update.new_text;
                                    } else {
                                        part.subparts[subpartIndex] = { name: update.new_text };
                                    }
                                }
                            }
                        } else if (update.node_id) {
                            // Updating a part
                            const match = update.node_id.match(/_(\d+)$/);
                            const nodeIndex = match ? parseInt(match[1]) : null;
                            
                            if (this.currentSpec.parts && Array.isArray(this.currentSpec.parts)) {
                                if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.parts.length) {
                                    const part = this.currentSpec.parts[nodeIndex];
                                    if (typeof part === 'object') {
                                        part.name = update.new_text;
                                    } else {
                                        this.currentSpec.parts[nodeIndex] = { name: update.new_text, subparts: [] };
                                    }
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'mindmap') {
                    // Mindmap: handle branches and children
                    data.nodes.forEach(update => {
                        if (!update.new_text) return;
                        
                        const branchIndex = update.branch_index !== undefined ? update.branch_index : undefined;
                        const childIndex = update.child_index !== undefined ? update.child_index : undefined;
                        
                        if (branchIndex !== undefined && childIndex !== undefined) {
                            // Updating a child within a branch
                            if (this.currentSpec.children && 0 <= branchIndex && branchIndex < this.currentSpec.children.length) {
                                const branch = this.currentSpec.children[branchIndex];
                                if (branch.children && Array.isArray(branch.children) && 
                                    0 <= childIndex && childIndex < branch.children.length) {
                                    const child = branch.children[childIndex];
                                    if (typeof child === 'object') {
                                        child.label = update.new_text;
                                        child.text = update.new_text;
                                    } else {
                                        branch.children[childIndex] = { id: `sub_${branchIndex}_${childIndex}`, label: update.new_text, text: update.new_text, children: [] };
                                    }
                                }
                            }
                        } else if (update.node_id) {
                            // Updating a branch
                            const match = update.node_id.match(/_(\d+)$/);
                            const nodeIndex = match ? parseInt(match[1]) : null;
                            
                            if (this.currentSpec.children && Array.isArray(this.currentSpec.children)) {
                                if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.children.length) {
                                    const branch = this.currentSpec.children[nodeIndex];
                                    if (typeof branch === 'object') {
                                        branch.label = update.new_text;
                                        branch.text = update.new_text;
                                    } else {
                                        this.currentSpec.children[nodeIndex] = { id: `branch_${nodeIndex}`, label: update.new_text, text: update.new_text, children: [] };
                                    }
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'concept_map') {
                    // Concept map: handle concepts and relationships
                    data.nodes.forEach(update => {
                        const relationshipIndex = update.relationship_index !== undefined ? update.relationship_index : undefined;
                        const from = update.from;
                        const to = update.to;
                        const label = update.label || update.new_text;
                        
                        if (relationshipIndex !== undefined) {
                            // Updating a relationship
                            if (this.currentSpec.relationships && Array.isArray(this.currentSpec.relationships) &&
                                0 <= relationshipIndex && relationshipIndex < this.currentSpec.relationships.length) {
                                const rel = this.currentSpec.relationships[relationshipIndex];
                                if (from) rel.from = from;
                                if (to) rel.to = to;
                                if (label) rel.label = label;
                            }
                        } else if (update.node_id && update.new_text) {
                            // Updating a concept
                            const match = update.node_id.match(/_(\d+)$/);
                            const nodeIndex = match ? parseInt(match[1]) : null;
                            
                            if (this.currentSpec.concepts && Array.isArray(this.currentSpec.concepts)) {
                                if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.concepts.length) {
                                    this.currentSpec.concepts[nodeIndex] = update.new_text;
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'flow_map') {
                    // Flow map: handle steps and substeps
                    data.nodes.forEach(update => {
                        if (!update.new_text) return;
                        
                        const stepIndex = update.step_index !== undefined ? update.step_index : undefined;
                        const substepIndex = update.substep_index !== undefined ? update.substep_index : undefined;
                        
                        if (stepIndex !== undefined && substepIndex !== undefined) {
                            // Updating a substep
                            if (this.currentSpec.steps && this.currentSpec.steps[stepIndex]) {
                                const stepName = typeof this.currentSpec.steps[stepIndex] === 'string' 
                                    ? this.currentSpec.steps[stepIndex] 
                                    : this.currentSpec.steps[stepIndex].text || '';
                                
                                if (stepName && this.currentSpec.substeps) {
                                    const substepsEntry = this.currentSpec.substeps.find(entry => 
                                        entry && typeof entry === 'object' && entry.step === stepName
                                    );
                                    
                                    if (substepsEntry && Array.isArray(substepsEntry.substeps) && 
                                        substepIndex >= 0 && substepIndex < substepsEntry.substeps.length) {
                                        substepsEntry.substeps[substepIndex] = update.new_text;
                                    }
                                }
                            }
                        } else if (update.node_id) {
                            // Updating a step
                            const match = update.node_id.match(/_(\d+)$/);
                            const nodeIndex = match ? parseInt(match[1]) : null;
                            
                            if (this.currentSpec.steps && Array.isArray(this.currentSpec.steps)) {
                                if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.steps.length) {
                                    this.currentSpec.steps[nodeIndex] = update.new_text;
                                } else {
                                    // Try to find by node_id
                                    const foundIndex = this.currentSpec.steps.findIndex((step, i) => 
                                        update.node_id.includes(`_${i}`)
                                    );
                                    if (foundIndex >= 0) {
                                        this.currentSpec.steps[foundIndex] = update.new_text;
                                    }
                                }
                            }
                        }
                    });
                } else {
                    // Standard diagrams: update nodes directly in spec
                    data.nodes.forEach(update => {
                        if (!update.node_id || !update.new_text) return;
                        
                        // Extract index from node_id (e.g., "context_0" -> 0, "step_1" -> 1)
                        const match = update.node_id.match(/_(\d+)$/);
                        const nodeIndex = match ? parseInt(match[1]) : null;
                        
                        // Determine the correct array based on diagram type
                        const arrayName = this.currentSpec.context ? 'context' : 
                                         this.currentSpec.attributes ? 'attributes' :
                                         this.currentSpec.children ? 'children' :
                                         this.currentSpec.items ? 'items' :
                                         this.currentSpec.steps ? 'steps' :
                                         this.currentSpec.parts ? 'parts' :
                                         this.currentSpec.branches ? 'branches' :
                                         this.currentSpec.concepts ? 'concepts' :
                                         'context';
                        
                        if (this.currentSpec[arrayName] && Array.isArray(this.currentSpec[arrayName])) {
                            if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec[arrayName].length) {
                                // Update by index
                                if (typeof this.currentSpec[arrayName][nodeIndex] === 'string') {
                                    this.currentSpec[arrayName][nodeIndex] = update.new_text;
                                } else if (typeof this.currentSpec[arrayName][nodeIndex] === 'object') {
                                    this.currentSpec[arrayName][nodeIndex].text = update.new_text;
                                    if (this.currentSpec[arrayName][nodeIndex].label !== undefined) {
                                        this.currentSpec[arrayName][nodeIndex].label = update.new_text;
                                    }
                                }
                            } else {
                                // Try to find by node_id
                                const foundIndex = this.currentSpec[arrayName].findIndex((node, i) => {
                                    if (typeof node === 'object' && node.id) {
                                        return node.id === update.node_id;
                                    }
                                    return update.node_id.includes(`_${i}`);
                                });
                                if (foundIndex >= 0) {
                                    if (typeof this.currentSpec[arrayName][foundIndex] === 'string') {
                                        this.currentSpec[arrayName][foundIndex] = update.new_text;
                                    } else if (typeof this.currentSpec[arrayName][foundIndex] === 'object') {
                                        this.currentSpec[arrayName][foundIndex].text = update.new_text;
                                        if (this.currentSpec[arrayName][foundIndex].label !== undefined) {
                                            this.currentSpec[arrayName][foundIndex].label = update.new_text;
                                        }
                                    }
                                }
                            }
                        }
                    });
                }
                
                this.renderDiagram();
                this.saveToHistory('voice_update_nodes', { count: data.nodes.length });
                logger.info('InteractiveEditor', `Voice: Updated ${data.nodes.length} node(s)`);
            };
            this.eventBus.onWithOwner('diagram:update_nodes', this.eventBusListeners.voiceUpdateNodes, this.ownerId);
            
            // Add nodes from voice command
            this.eventBusListeners.voiceAddNodes = (data) => {
                if (!this.currentSpec || !data.nodes) return;
                
                // Handle diagram-type-specific node addition with category support
                if (this.diagramType === 'double_bubble_map') {
                    // Double bubble map: nodes have categories (similarities, left_differences, right_differences)
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const category = node.category || 'similarities'; // Default to similarities
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (text) {
                            // Initialize arrays if needed
                            if (!this.currentSpec.similarities) this.currentSpec.similarities = [];
                            if (!this.currentSpec.left_differences) this.currentSpec.left_differences = [];
                            if (!this.currentSpec.right_differences) this.currentSpec.right_differences = [];
                            
                            // Add to appropriate category array
                            if (category === 'similarities') {
                                if (index !== undefined && index < this.currentSpec.similarities.length) {
                                    this.currentSpec.similarities[index] = text;
                                } else {
                                    this.currentSpec.similarities.push(text);
                                }
                            } else if (category === 'left_differences') {
                                if (index !== undefined && index < this.currentSpec.left_differences.length) {
                                    this.currentSpec.left_differences[index] = text;
                                } else {
                                    this.currentSpec.left_differences.push(text);
                                }
                            } else if (category === 'right_differences') {
                                if (index !== undefined && index < this.currentSpec.right_differences.length) {
                                    this.currentSpec.right_differences[index] = text;
                                } else {
                                    this.currentSpec.right_differences.push(text);
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'multi_flow_map') {
                    // Multi-flow map: nodes have categories (causes, effects)
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const category = node.category || 'causes'; // Default to causes
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (text) {
                            // Initialize arrays if needed
                            if (!this.currentSpec.causes) this.currentSpec.causes = [];
                            if (!this.currentSpec.effects) this.currentSpec.effects = [];
                            
                            // Add to appropriate category array
                            if (category === 'causes') {
                                if (index !== undefined && index < this.currentSpec.causes.length) {
                                    this.currentSpec.causes[index] = text;
                                } else {
                                    this.currentSpec.causes.push(text);
                                }
                            } else if (category === 'effects') {
                                if (index !== undefined && index < this.currentSpec.effects.length) {
                                    this.currentSpec.effects[index] = text;
                                } else {
                                    this.currentSpec.effects.push(text);
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'bridge_map') {
                    // Bridge map: nodes are analogies with left/right pairs
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const left = node.left;
                        const right = node.right;
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (text || (left && right)) {
                            if (!this.currentSpec.analogies) this.currentSpec.analogies = [];
                            
                            if (left && right) {
                                // Add as structured analogy pair
                                const analogy = { left: left, right: right };
                                if (index !== undefined && index < this.currentSpec.analogies.length) {
                                    this.currentSpec.analogies[index] = analogy;
                                } else {
                                    this.currentSpec.analogies.push(analogy);
                                }
                            } else if (text) {
                                // Fallback: parse text if left/right not provided
                                if (index !== undefined && index < this.currentSpec.analogies.length) {
                                    this.currentSpec.analogies[index] = text;
                                } else {
                                    this.currentSpec.analogies.push(text);
                                }
                            }
                        }
                    });
                } else if (this.diagramType === 'tree_map') {
                    // Tree map: handle categories and items
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const categoryIndex = node.category_index !== undefined ? node.category_index : undefined;
                        const itemIndex = node.item_index !== undefined ? node.item_index : undefined;
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (categoryIndex !== undefined && itemIndex !== undefined) {
                            // Adding/updating an item within a category
                            if (!this.currentSpec.children) {
                                this.currentSpec.children = [];
                            }
                            
                            if (0 <= categoryIndex && categoryIndex < this.currentSpec.children.length) {
                                const category = this.currentSpec.children[categoryIndex];
                                if (!category.children || !Array.isArray(category.children)) {
                                    category.children = [];
                                }
                                
                                // Add/update item at specified position
                                if (itemIndex < category.children.length) {
                                    const item = category.children[itemIndex];
                                    if (typeof item === 'object') {
                                        item.text = text;
                                    } else {
                                        category.children[itemIndex] = { text: text, children: [] };
                                    }
                                } else if (itemIndex !== undefined) {
                                    // Pad with empty items if needed
                                    while (category.children.length < itemIndex) {
                                        category.children.push({ text: '', children: [] });
                                    }
                                    category.children[itemIndex] = { text: text, children: [] };
                                } else {
                                    category.children.push({ text: text, children: [] });
                                }
                            }
                        } else if (text) {
                            // Adding/updating a category
                            if (!this.currentSpec.children) {
                                this.currentSpec.children = [];
                            }
                            
                            if (index !== undefined && index < this.currentSpec.children.length) {
                                // Update existing category at position
                                const category = this.currentSpec.children[index];
                                if (typeof category === 'object') {
                                    category.text = text;
                                } else {
                                    this.currentSpec.children[index] = { text: text, children: [] };
                                }
                            } else if (index !== undefined) {
                                // Insert at specific position
                                while (this.currentSpec.children.length < index) {
                                    this.currentSpec.children.push({ text: '', children: [] });
                                }
                                this.currentSpec.children[index] = { text: text, children: [] };
                            } else {
                                // Add to end (default)
                                this.currentSpec.children.push({ text: text, children: [] });
                            }
                        }
                    });
                } else if (this.diagramType === 'brace_map') {
                    // Brace map: handle parts and subparts
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const partIndex = node.part_index !== undefined ? node.part_index : undefined;
                        const subpartIndex = node.subpart_index !== undefined ? node.subpart_index : undefined;
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (partIndex !== undefined && subpartIndex !== undefined) {
                            // Adding/updating a subpart within a part
                            if (!this.currentSpec.parts) {
                                this.currentSpec.parts = [];
                            }
                            
                            if (0 <= partIndex && partIndex < this.currentSpec.parts.length) {
                                const part = this.currentSpec.parts[partIndex];
                                if (!part.subparts || !Array.isArray(part.subparts)) {
                                    part.subparts = [];
                                }
                                
                                // Add/update subpart at specified position
                                if (subpartIndex < part.subparts.length) {
                                    const subpart = part.subparts[subpartIndex];
                                    if (typeof subpart === 'object') {
                                        subpart.name = text;
                                    } else {
                                        part.subparts[subpartIndex] = { name: text };
                                    }
                                } else if (subpartIndex !== undefined) {
                                    // Pad with empty subparts if needed
                                    while (part.subparts.length < subpartIndex) {
                                        part.subparts.push({ name: '' });
                                    }
                                    part.subparts[subpartIndex] = { name: text };
                                } else {
                                    part.subparts.push({ name: text });
                                }
                            }
                        } else if (text) {
                            // Adding/updating a part
                            if (!this.currentSpec.parts) {
                                this.currentSpec.parts = [];
                            }
                            
                            if (index !== undefined && index < this.currentSpec.parts.length) {
                                // Update existing part at position
                                const part = this.currentSpec.parts[index];
                                if (typeof part === 'object') {
                                    part.name = text;
                                } else {
                                    this.currentSpec.parts[index] = { name: text, subparts: [] };
                                }
                            } else if (index !== undefined) {
                                // Insert at specific position
                                while (this.currentSpec.parts.length < index) {
                                    this.currentSpec.parts.push({ name: '', subparts: [] });
                                }
                                this.currentSpec.parts[index] = { name: text, subparts: [] };
                            } else {
                                // Add to end (default)
                                this.currentSpec.parts.push({ name: text, subparts: [] });
                            }
                        }
                    });
                } else if (this.diagramType === 'mindmap') {
                    // Mindmap: handle branches and children
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const branchIndex = node.branch_index !== undefined ? node.branch_index : undefined;
                        const childIndex = node.child_index !== undefined ? node.child_index : undefined;
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (branchIndex !== undefined && childIndex !== undefined) {
                            // Adding/updating a child within a branch
                            if (!this.currentSpec.children) {
                                this.currentSpec.children = [];
                            }
                            
                            if (0 <= branchIndex && branchIndex < this.currentSpec.children.length) {
                                const branch = this.currentSpec.children[branchIndex];
                                if (!branch.children || !Array.isArray(branch.children)) {
                                    branch.children = [];
                                }
                                
                                // Add/update child at specified position
                                const childId = `sub_${branchIndex}_${branch.children.length}`;
                                if (childIndex < branch.children.length) {
                                    const child = branch.children[childIndex];
                                    if (typeof child === 'object') {
                                        child.label = text;
                                        child.text = text;
                                    } else {
                                        branch.children[childIndex] = { id: childId, label: text, text: text, children: [] };
                                    }
                                } else if (childIndex !== undefined) {
                                    // Pad with empty children if needed
                                    while (branch.children.length < childIndex) {
                                        branch.children.push({ id: `sub_${branchIndex}_${branch.children.length}`, label: '', text: '', children: [] });
                                    }
                                    branch.children[childIndex] = { id: childId, label: text, text: text, children: [] };
                                } else {
                                    branch.children.push({ id: childId, label: text, text: text, children: [] });
                                }
                            }
                        } else if (text) {
                            // Adding/updating a branch
                            if (!this.currentSpec.children) {
                                this.currentSpec.children = [];
                            }
                            
                            if (index !== undefined && index < this.currentSpec.children.length) {
                                // Update existing branch at position
                                const branch = this.currentSpec.children[index];
                                if (typeof branch === 'object') {
                                    branch.label = text;
                                    branch.text = text;
                                } else {
                                    this.currentSpec.children[index] = { id: `branch_${index}`, label: text, text: text, children: [] };
                                }
                            } else if (index !== undefined) {
                                // Insert at specific position
                                while (this.currentSpec.children.length < index) {
                                    this.currentSpec.children.push({ id: `branch_${this.currentSpec.children.length}`, label: '', text: '', children: [] });
                                }
                                this.currentSpec.children[index] = { id: `branch_${index}`, label: text, text: text, children: [] };
                            } else {
                                // Add to end (default)
                                const branchId = `branch_${this.currentSpec.children.length}`;
                                this.currentSpec.children.push({ id: branchId, label: text, text: text, children: [] });
                            }
                        }
                    });
                } else if (this.diagramType === 'concept_map') {
                    // Concept map: handle concepts and relationships
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const from = node.from;
                        const to = node.to;
                        const label = node.label;
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (from && to && label) {
                            // Adding a relationship
                            if (!this.currentSpec.relationships) {
                                this.currentSpec.relationships = [];
                            }
                            this.currentSpec.relationships.push({ from: from, to: to, label: label });
                        } else if (text) {
                            // Adding/updating a concept
                            if (!this.currentSpec.concepts) {
                                this.currentSpec.concepts = [];
                            }
                            
                            if (index !== undefined && index < this.currentSpec.concepts.length) {
                                // Update existing concept at position
                                this.currentSpec.concepts[index] = text;
                            } else if (index !== undefined) {
                                // Insert at specific position
                                while (this.currentSpec.concepts.length < index) {
                                    this.currentSpec.concepts.push('');
                                }
                                this.currentSpec.concepts[index] = text;
                            } else {
                                // Add to end (default)
                                this.currentSpec.concepts.push(text);
                            }
                        }
                    });
                } else if (this.diagramType === 'flow_map') {
                    // Flow map: handle steps and substeps
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const stepIndex = node.step_index !== undefined ? node.step_index : undefined;
                        const substepIndex = node.substep_index !== undefined ? node.substep_index : undefined;
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (stepIndex !== undefined && substepIndex !== undefined) {
                            // Adding/updating a substep
                            if (!this.currentSpec.substeps) {
                                this.currentSpec.substeps = [];
                            }
                            
                            const stepName = this.currentSpec.steps && this.currentSpec.steps[stepIndex] 
                                ? (typeof this.currentSpec.steps[stepIndex] === 'string' 
                                    ? this.currentSpec.steps[stepIndex] 
                                    : this.currentSpec.steps[stepIndex].text || '')
                                : '';
                            
                            if (stepName) {
                                // Find or create substeps entry for this step
                                let substepsEntry = this.currentSpec.substeps.find(entry => 
                                    entry && typeof entry === 'object' && entry.step === stepName
                                );
                                
                                if (!substepsEntry) {
                                    substepsEntry = { step: stepName, substeps: [] };
                                    this.currentSpec.substeps.push(substepsEntry);
                                }
                                
                                if (!Array.isArray(substepsEntry.substeps)) {
                                    substepsEntry.substeps = [];
                                }
                                
                                // Add/update substep at specified position
                                if (substepIndex < substepsEntry.substeps.length) {
                                    substepsEntry.substeps[substepIndex] = text;
                                } else if (substepIndex !== undefined) {
                                    // Pad with empty strings if needed
                                    while (substepsEntry.substeps.length < substepIndex) {
                                        substepsEntry.substeps.push('');
                                    }
                                    substepsEntry.substeps[substepIndex] = text;
                                } else {
                                    substepsEntry.substeps.push(text);
                                }
                            }
                        } else if (text) {
                            // Adding/updating a step
                            if (!this.currentSpec.steps) {
                                this.currentSpec.steps = [];
                            }
                            
                            if (index !== undefined && index < this.currentSpec.steps.length) {
                                // Update existing step at position
                                this.currentSpec.steps[index] = text;
                            } else if (index !== undefined) {
                                // Insert at specific position (pad with empty strings if needed)
                                while (this.currentSpec.steps.length < index) {
                                    this.currentSpec.steps.push('');
                                }
                                this.currentSpec.steps[index] = text;
                            } else {
                                // Add to end (default)
                                this.currentSpec.steps.push(text);
                            }
                        }
                    });
                } else {
                    // Standard diagrams: determine the correct array based on diagram type
                    const arrayName = this.currentSpec.context ? 'context' : 
                                     this.currentSpec.attributes ? 'attributes' :
                                     this.currentSpec.children ? 'children' :
                                     this.currentSpec.items ? 'items' :
                                     this.currentSpec.steps ? 'steps' :
                                     this.currentSpec.parts ? 'parts' :
                                     'context';
                    
                    if (!this.currentSpec[arrayName]) {
                        this.currentSpec[arrayName] = [];
                    }
                    
                    data.nodes.forEach(node => {
                        const text = typeof node === 'string' ? node : (node.text || node);
                        const index = node.index !== undefined ? node.index : undefined;
                        
                        if (text) {
                            // Handle position-based insertion if index is specified
                            if (index !== undefined && index < this.currentSpec[arrayName].length) {
                                // Update existing node at position
                                this.currentSpec[arrayName][index] = text;
                            } else if (index !== undefined) {
                                // Insert at specific position (pad with empty strings if needed)
                                while (this.currentSpec[arrayName].length < index) {
                                    this.currentSpec[arrayName].push('');
                                }
                                this.currentSpec[arrayName][index] = text;
                            } else {
                                // Add to end (default)
                                this.currentSpec[arrayName].push(text);
                            }
                        }
                    });
                }
                
                this.renderDiagram();
                this.saveToHistory('voice_add_nodes', { count: data.nodes.length });
                logger.info('InteractiveEditor', `Voice: Added ${data.nodes.length} node(s) to ${this.diagramType}`);
            };
            this.eventBus.onWithOwner('diagram:add_nodes', this.eventBusListeners.voiceAddNodes, this.ownerId);
            
            // Remove nodes from voice command
            this.eventBusListeners.voiceRemoveNodes = (data) => {
                if (!this.currentSpec || !data.nodeIds) return;
                
                // Handle diagram-type-specific node deletion with category support
                if (this.diagramType === 'double_bubble_map') {
                    // Double bubble map: nodes have categories (similarities, left_differences, right_differences)
                    data.nodeIds.forEach(nodeIdOrObj => {
                        const nodeId = typeof nodeIdOrObj === 'string' ? nodeIdOrObj : nodeIdOrObj.node_id;
                        const category = typeof nodeIdOrObj === 'object' ? nodeIdOrObj.category : undefined;
                        
                        // Extract index from node_id (e.g., "node_0" -> 0)
                        const match = nodeId.match(/_(\d+)$/);
                        const nodeIndex = match ? parseInt(match[1]) : null;
                        
                        if (category === 'similarities' && this.currentSpec.similarities) {
                            if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.similarities.length) {
                                this.currentSpec.similarities.splice(nodeIndex, 1);
                            }
                        } else if (category === 'left_differences' && this.currentSpec.left_differences) {
                            if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.left_differences.length) {
                                this.currentSpec.left_differences.splice(nodeIndex, 1);
                            }
                        } else if (category === 'right_differences' && this.currentSpec.right_differences) {
                            if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.right_differences.length) {
                                this.currentSpec.right_differences.splice(nodeIndex, 1);
                            }
                        } else if (nodeIndex !== null) {
                            // Try all categories if category not specified
                            if (this.currentSpec.similarities && nodeIndex < this.currentSpec.similarities.length) {
                                this.currentSpec.similarities.splice(nodeIndex, 1);
                            } else if (this.currentSpec.left_differences && nodeIndex < this.currentSpec.left_differences.length) {
                                this.currentSpec.left_differences.splice(nodeIndex, 1);
                            } else if (this.currentSpec.right_differences && nodeIndex < this.currentSpec.right_differences.length) {
                                this.currentSpec.right_differences.splice(nodeIndex, 1);
                            }
                        }
                    });
                } else if (this.diagramType === 'multi_flow_map') {
                    // Multi-flow map: nodes have categories (causes, effects)
                    data.nodeIds.forEach(nodeIdOrObj => {
                        const nodeId = typeof nodeIdOrObj === 'string' ? nodeIdOrObj : nodeIdOrObj.node_id;
                        const category = typeof nodeIdOrObj === 'object' ? nodeIdOrObj.category : undefined;
                        
                        // Extract index from node_id (e.g., "step_0" -> 0)
                        const match = nodeId.match(/_(\d+)$/);
                        const nodeIndex = match ? parseInt(match[1]) : null;
                        
                        if (category === 'causes' && this.currentSpec.causes) {
                            if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.causes.length) {
                                this.currentSpec.causes.splice(nodeIndex, 1);
                            }
                        } else if (category === 'effects' && this.currentSpec.effects) {
                            if (nodeIndex !== null && nodeIndex >= 0 && nodeIndex < this.currentSpec.effects.length) {
                                this.currentSpec.effects.splice(nodeIndex, 1);
                            }
                        } else if (nodeIndex !== null) {
                            // Try both categories if category not specified
                            if (this.currentSpec.causes && nodeIndex < this.currentSpec.causes.length) {
                                this.currentSpec.causes.splice(nodeIndex, 1);
                            } else if (this.currentSpec.effects && nodeIndex < this.currentSpec.effects.length) {
                                this.currentSpec.effects.splice(nodeIndex, 1);
                            }
                        }
                    });
                } else {
                    // Standard diagrams: use generic removal
                    data.nodeIds.forEach(nodeId => {
                        if (nodeId && this.thinkGuide) {
                            this.thinkGuide.removeDiagramNode(nodeId);
                        }
                    });
                }
                
                this.renderDiagram();
                this.saveToHistory('voice_remove_nodes', { count: data.nodeIds.length });
                logger.info('InteractiveEditor', `Voice: Removed ${data.nodeIds.length} node(s)`);
            };
            this.eventBus.onWithOwner('diagram:remove_nodes', this.eventBusListeners.voiceRemoveNodes, this.ownerId);
            
            // Auto-complete from voice command
            this.eventBusListeners.voiceAutoComplete = () => {
                const autoCompleteBtn = document.getElementById('auto-complete-btn');
                if (autoCompleteBtn) {
                    autoCompleteBtn.click();
                    logger.info('InteractiveEditor', 'Voice: Triggered auto-complete');
                }
            };
            this.eventBus.onWithOwner('diagram:auto_complete_requested', this.eventBusListeners.voiceAutoComplete, this.ownerId);
            
            // Select node from voice command (by nodeId or nodeIndex)
            this.eventBusListeners.voiceSelectNode = (data) => {
                if (!this.selectionManager) return;
                
                let nodeId = data.nodeId;
                
                // If nodeIndex is provided but no nodeId, resolve it
                if (!nodeId && data.nodeIndex !== undefined) {
                    // Get nodes from current spec
                    const nodes = this.currentSpec?.context || 
                                 this.currentSpec?.attributes ||
                                 this.currentSpec?.children ||
                                 this.currentSpec?.items || [];
                    
                    if (data.nodeIndex >= 0 && data.nodeIndex < nodes.length) {
                        // Generate nodeId based on diagram type
                        const prefixMap = {
                            'circle_map': 'context',
                            'bubble_map': 'attribute',
                            'tree_map': 'item',
                            'flow_map': 'step',
                            'brace_map': 'part',
                            'mindmap': 'branch',
                            'concept_map': 'concept'
                        };
                        const prefix = prefixMap[this.diagramType] || 'node';
                        nodeId = `${prefix}_${data.nodeIndex}`;
                    }
                }
                
                if (nodeId) {
                    // Clear previous selection and select the new node
                    this.selectionManager.clearSelection();
                    this.selectionManager.selectNode(nodeId);
                    logger.info('InteractiveEditor', `Voice: Selected node "${nodeId}"`);
                }
            };
            this.eventBus.onWithOwner('selection:select_requested', this.eventBusListeners.voiceSelectNode, this.ownerId);
        }
        
        // Update flow map orientation button visibility (via ViewManager)
        if (this.eventBus) {
            // ViewManager will handle this via event subscription
            this.eventBus.emit('diagram:type_changed', { diagramType: this.diagramType });
        }
        
        // Render initial diagram
        this.renderDiagram();
        
        // Setup global event handlers
        this.setupGlobalEventHandlers();
        
        // Initialize toolbar manager
        if (typeof ToolbarManager !== 'undefined') {
            this.toolbarManager = new ToolbarManager(this);
            logger.debug('Editor', 'Toolbar manager initialized');
        }
        
            // Auto-fit for mobile devices on initial load (via ViewManager)
        if (this.isMobileDevice()) {
            logger.debug('Editor', 'Mobile device detected - auto-fitting to screen');
            if (this.eventBus) {
            setTimeout(() => {
                    this.eventBus.emit('view:fit_diagram_requested');
            }, 500); // Slight delay to ensure rendering is complete
            }
        }
    }
    
    /**
     * Render the diagram
     */
    async renderDiagram() {
        this.log('InteractiveEditor: Starting diagram render', {
            specKeys: Object.keys(this.currentSpec || {})
        });
        
        // Update flow map orientation button visibility (via ViewManager)
        if (this.eventBus) {
            this.eventBus.emit('diagram:type_changed', { diagramType: this.diagramType });
        }
        
        try {
            // For templates: don't set adaptive dimensions during render
            // Let the renderer use its default size, then fitToCanvasWithPanel will handle sizing
            // For LLM-generated diagrams: keep their recommended dimensions
            const theme = null; // Use default theme
            let dimensions = null;
            
            if (this.currentSpec && this.currentSpec._llm_generated) {
                // LLM-generated: use their recommended dimensions
                dimensions = this.currentSpec._recommended_dimensions || null;
                logger.debug('Editor', 'Using LLM-generated dimensions', dimensions);
            } else {
                // Template: render at default size, fitToCanvasWithPanel will handle sizing via viewBox
                logger.debug('Editor', 'Will render at default size then fit to canvas');
                // Set flag to indicate we'll be sizing for panel after render
                this.isSizedForPanel = true;
            }
            
            if (typeof renderGraph === 'function') {
                // CRITICAL: Use State Manager as source of truth for diagram type
                let diagramTypeToRender = this.diagramType;
                if (this.stateManager && typeof this.stateManager.getDiagramState === 'function') {
                    const diagramState = this.stateManager.getDiagramState();
                    if (diagramState && diagramState.type) {
                        diagramTypeToRender = diagramState.type;
                        // Sync local copy if different (for backward compatibility)
                        if (diagramTypeToRender !== this.diagramType) {
                            logger.debug('InteractiveEditor', `Using diagram type from State Manager: ${diagramTypeToRender} (was ${this.diagramType})`);
                            this.diagramType = diagramTypeToRender;
                        }
                    }
                }
                
                // CRITICAL: Validate diagramType before rendering
                if (!diagramTypeToRender) {
                    logger.error('Editor', 'diagramType is undefined/null, cannot render');
                    throw new Error('diagramType is required for rendering');
                }
                
                // Defensive logging: Check if spec structure matches diagram type
                const hasContext = Array.isArray(this.currentSpec?.context);
                const hasAttributes = Array.isArray(this.currentSpec?.attributes);
                const hasTopic = !!this.currentSpec?.topic;
                
                if (diagramTypeToRender === 'circle_map' && !hasContext) {
                    logger.warn('Editor', `Circle map spec missing context array. Has: topic=${hasTopic}, attributes=${hasAttributes}, context=${hasContext}`);
                } else if (diagramTypeToRender === 'bubble_map' && !hasAttributes) {
                    logger.warn('Editor', `Bubble map spec missing attributes array. Has: topic=${hasTopic}, attributes=${hasAttributes}, context=${hasContext}`);
                }
                
                logger.debug('Editor', `Rendering ${diagramTypeToRender}`, {
                    diagramType: diagramTypeToRender,
                    fromStateManager: diagramTypeToRender !== this.diagramType,
                    nodes: this.currentSpec?.nodes?.length || 0,
                    hasTitle: !!this.currentSpec?.title,
                    hasTopic,
                    hasContext,
                    hasAttributes
                });
                await renderGraph(diagramTypeToRender, this.currentSpec, theme, dimensions);
            } else {
                logger.error('Editor', 'renderGraph dispatcher not found');
                throw new Error('Renderer not available');
            }
            
            // Add interaction handlers after rendering (via InteractionHandler)
            // InteractionHandler will handle this via diagram:rendered event subscription
            
            // Enable zoom and pan for all devices (via ViewManager)
            // ViewManager will handle this via event subscription on diagram:rendered
            
            // Update school name display in status bar (async, no await needed)
            this.updateSchoolNameDisplay().catch(err => {
                logger.debug('Editor', 'School name update failed', err);
            });
            
            // NOTE: Auto-fit is handled by ViewManager via diagram:rendered event
            // This prevents duplicate triggers and ensures clean initial load
            
            // Update flow map orientation button visibility (via ViewManager)
            if (this.eventBus) {
                this.eventBus.emit('diagram:type_changed', { diagramType: this.diagramType });
            }
            
            // Emit diagram rendered event (for ViewManager and other modules)
            if (this.eventBus) {
                this.eventBus.emit('diagram:rendered', {
                    diagramType: this.diagramType,
                    spec: this.currentSpec
                });
            }
            
        } catch (error) {
            logger.error('Editor', 'Diagram rendering failed', error);
            throw error;
        }
    }
    
    /**
     * Update school name display in status bar
     */
    async updateSchoolNameDisplay() {
        try {
            const schoolNameDisplay = document.getElementById('school-name-display');
            if (!schoolNameDisplay) {
                console.warn('[Editor] School name display element not found in DOM');
                return;
            }
            
            // Try to get school name from user's organization
            const authHelper = window.auth || window.AuthHelper;
            if (!authHelper) {
                console.warn('[Editor] Auth helper not available');
                schoolNameDisplay.style.display = 'none';
                return;
            }
            
            // First try to get from localStorage
            let user = null;
            if (typeof authHelper.getUser === 'function') {
                user = authHelper.getUser();
                console.log('[Editor] User from localStorage:', user);
            }
            
            // If no user data, fetch it from server
            if (!user && typeof authHelper.getCurrentUser === 'function') {
                console.log('[Editor] Fetching user data from server...');
                user = await authHelper.getCurrentUser();
                console.log('[Editor] User from server:', user);
            }
            
            // Handle both string and object organization formats
            let schoolName = null;
            if (user && user.organization) {
                if (typeof user.organization === 'string') {
                    // Organization stored as string (from localStorage)
                    schoolName = user.organization;
                } else if (user.organization.name) {
                    // Organization stored as object with name property (from server)
                    schoolName = user.organization.name;
                }
            }
            
            if (schoolName) {
                schoolNameDisplay.textContent = schoolName;
                schoolNameDisplay.style.display = 'inline-block';
                schoolNameDisplay.style.marginRight = '12px';
                schoolNameDisplay.style.color = '#ffffff';
                schoolNameDisplay.style.fontSize = '12px';
                schoolNameDisplay.style.fontWeight = '500';
                console.log('[Editor] School name displayed:', schoolName);
            } else {
                // Check if we're in demo or enterprise mode
                let mode = authHelper.getMode();
                
                // If mode not set in localStorage, try to detect from server
                if (mode === 'standard' && typeof authHelper.detectMode === 'function') {
                    try {
                        mode = await authHelper.detectMode();
                        if (mode && mode !== 'standard') {
                            authHelper.setMode(mode);
                        }
                    } catch (e) {
                        console.debug('[Editor] Could not detect mode from server:', e);
                    }
                }
                
                if (mode === 'demo') {
                    schoolNameDisplay.textContent = 'Demo';
                    schoolNameDisplay.style.display = 'inline-block';
                    schoolNameDisplay.style.marginRight = '12px';
                    schoolNameDisplay.style.color = '#ffffff';
                    schoolNameDisplay.style.fontSize = '12px';
                    schoolNameDisplay.style.fontWeight = '500';
                    console.log('[Editor] Demo mode');
                } else if (mode === 'enterprise') {
                    schoolNameDisplay.textContent = 'Enterprise';
                    schoolNameDisplay.style.display = 'inline-block';
                    schoolNameDisplay.style.marginRight = '12px';
                    schoolNameDisplay.style.color = '#ffffff';
                    schoolNameDisplay.style.fontSize = '12px';
                    schoolNameDisplay.style.fontWeight = '500';
                    console.log('[Editor] Enterprise mode');
                } else {
                    console.warn('[Editor] No school name available. User:', user);
                    schoolNameDisplay.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('[Editor] Error updating school name display:', error);
            const schoolNameDisplay = document.getElementById('school-name-display');
            if (schoolNameDisplay) {
                schoolNameDisplay.style.display = 'none';
            }
        }
    }
    
    /**
     * Setup global event handlers
     */
    setupGlobalEventHandlers() {
        // Click on canvas to deselect all - ONLY if clicking on empty space
        // If clicking on a node, the node's click handler will handle selection
        d3.select('#d3-container').on('click', (event) => {
            // Check if click was on a node element (has data-node-id attribute)
            // Use multiple detection methods for robustness across all diagram types
            const target = event.target;
            
            // Method 1: Direct attribute check using getAttribute (more reliable than hasAttribute)
            const hasNodeId = target.getAttribute && target.getAttribute('data-node-id');
            const hasTextFor = target.getAttribute && target.getAttribute('data-text-for');
            
            // Method 2: Check if target is a shape element (circle, rect, ellipse, text)
            // These are the interactive elements in all diagram types
            const tagName = target.tagName?.toLowerCase();
            const isShapeElement = ['circle', 'rect', 'ellipse', 'text', 'tspan'].includes(tagName);
            
            // Method 3: Check parent chain for data-node-id (for nested elements)
            const hasNodeIdParent = target.closest && target.closest('[data-node-id]');
            
            // Consider it a node element if any of these conditions are true
            const isNodeElement = hasNodeId || hasTextFor || (isShapeElement && hasNodeIdParent);
            
            // Only clear selection if clicking on empty space (not on a node)
            if (!isNodeElement) {
            if (this.eventBus) {
                this.eventBus.emit('interaction:clear_selection_requested');
            } else {
                // Fallback if Event Bus not available
            this.selectionManager.clearSelection();
                }
            }
        });
        
        // Keyboard shortcuts
        d3.select('body').on('keydown', (event) => {
            this.handleKeyboardShortcut(event);
        });
        
        // Reset view button (delegate to ViewManager via Event Bus)
        const resetViewBtn = document.getElementById('reset-view-btn');
        if (resetViewBtn) {
            this.eventHandlers.resetViewClick = () => {
                if (this.eventBus) {
                    this.eventBus.emit('view:fit_diagram_requested');
                }
            };
            resetViewBtn.addEventListener('click', this.eventHandlers.resetViewClick);
        }
        
        // Mobile: Auto-fit on orientation change
        if (this.isMobileDevice()) {
            this.eventHandlers.orientationChange = () => {
                logger.debug('Editor', 'Orientation changed - re-fitting diagram to screen');
                if (this.eventBus) {
                setTimeout(() => {
                        this.eventBus.emit('view:fit_diagram_requested');
                }, 300); // Wait for orientation animation to complete
                }
            };
            window.addEventListener('orientationchange', this.eventHandlers.orientationChange);
            
            // Also handle window resize for responsive mobile browsers
            let resizeTimeout;
            this.eventHandlers.windowResize = () => {
                if (this.isMobileDevice()) {
                    clearTimeout(resizeTimeout);
                    resizeTimeout = setTimeout(() => {
                        logger.debug('Editor', 'Mobile screen resized - re-fitting diagram');
                        if (this.eventBus) {
                            this.eventBus.emit('view:fit_diagram_requested');
                        }
                    }, 300);
                }
            };
            window.addEventListener('resize', this.eventHandlers.windowResize);
        }
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcut(event) {
        // Ignore shortcuts if user is typing in an input field, textarea, or contenteditable element
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.isContentEditable
        );
        
        // Delete selected nodes (only if not typing in an input)
        if (event.key === 'Delete' || event.key === 'Backspace') {
            if (!isTyping && this.selectedNodes.size > 0) {
                event.preventDefault();
                this.deleteSelectedNodes();
            }
        }
        
        // Undo - Use Event Bus for consistency
        if (event.ctrlKey && event.key === 'z') {
            if (!isTyping) {
                event.preventDefault();
                this.eventBus.emit('history:undo_requested', {});
            }
        }
        
        // Redo - Use Event Bus for consistency
        if (event.ctrlKey && event.key === 'y') {
            if (!isTyping) {
                event.preventDefault();
                this.eventBus.emit('history:redo_requested', {});
            }
        }
        
        // Select all - Allow Ctrl+A in inputs, but prevent on canvas
        if (event.ctrlKey && event.key === 'a') {
            if (!isTyping) {
                event.preventDefault();
                this.selectAll();
            }
        }
    }
    
    /**
     * Open node editor
     */
    openNodeEditor(nodeId, shapeNode, textNode, currentText) {
        // Verbose logging: Log node editor opening
        logger.debug('InteractiveEditor', 'Node Editor Opened', {
            nodeId,
            currentText: currentText?.substring(0, 50),
            textLength: currentText?.length || 0,
            diagramType: this.diagramType,
            timestamp: Date.now()
        });
        
        // Check if this is a dimension node
        let initialText = currentText || 'Edit me';
        const textElement = d3.select(textNode);
        const nodeType = textElement.attr('data-node-type');
        
        if (nodeType === 'dimension' && currentText) {
            // Check if current text is placeholder text (Chinese or English)
            const isPlaceholderCN = currentText.includes('点击填写');
            const isPlaceholderEN = currentText.includes('click to specify');
            
            if (isPlaceholderCN || isPlaceholderEN) {
                // Start with empty string so users can type immediately without deleting placeholder
                initialText = '';
                this.log('InteractiveEditor: Detected dimension placeholder, starting with empty text');
            } else {
                // Dimension has a value - extract ONLY the dimension value, not the wrapper
                // Format is: [拆解维度: 功能模块] or [Decomposition by: Physical Parts]
                // We want to extract only: 功能模块 or Physical Parts
                const dimensionValueMatch = currentText.match(/\[(?:拆解维度|Decomposition by):\s*(.+?)\]/);
                if (dimensionValueMatch && dimensionValueMatch[1]) {
                    initialText = dimensionValueMatch[1].trim();
                    this.log('InteractiveEditor: Extracted dimension value from wrapper', {
                        fullText: currentText,
                        extractedValue: initialText
                    });
                } else {
                    // Fallback: if no wrapper found, use current text as-is
                    initialText = currentText;
                }
            }
        }
        
        const editor = new NodeEditor(
            { id: nodeId, text: initialText },
            (newText) => {
                this.log('InteractiveEditor: Node editor - Save callback triggered', {
                    nodeId,
                    newText: newText?.substring(0, 50)
                });
                
                // For dimension nodes, strip any wrapper text that user might have included
                let finalText = newText;
                if (nodeType === 'dimension' && newText) {
                    // If user somehow included the wrapper, extract just the value
                    const valueMatch = newText.match(/\[(?:拆解维度|Decomposition by):\s*(.+?)\]/);
                    if (valueMatch && valueMatch[1]) {
                        finalText = valueMatch[1].trim();
                        this.log('InteractiveEditor: Stripped wrapper from dimension text', {
                            original: newText,
                            cleaned: finalText
                        });
                    }
                }
                
                this.updateNodeText(nodeId, shapeNode, textNode, finalText);
            },
            () => {
                // Cancel callback
                this.log('InteractiveEditor: Node editor - Cancel callback triggered', { nodeId });
            }
        );
        
        editor.show();
    }
    
    /**
     * Update node text
     */
    updateNodeText(nodeId, shapeNode, textNode, newText) {
        this.log('InteractiveEditor: Updating node text', {
            nodeId,
            diagramType: this.diagramType,
            newText: newText?.substring(0, 50),
            textLength: newText?.length || 0
        });
        
        // Validate session
        if (!this.validateSession('Update node text')) {
            return;
        }
        
        // Use DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            logger.warn('InteractiveEditor', 'DiagramOperationsLoader not available');
            // Fallback to generic update
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
        this.saveToHistory('update_text', { nodeId, newText });
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations || typeof operations.updateNode !== 'function') {
            logger.warn('InteractiveEditor', `No operations available for diagram type: ${this.diagramType}`);
            // Fallback to generic update
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
            this.saveToHistory('update_text', { nodeId, newText });
            return;
        }
        
        try {
            const updatedSpec = operations.updateNode(this.currentSpec, nodeId, { text: newText });
            if (updatedSpec) {
                this.currentSpec = updatedSpec;
                // Operations module will emit diagram:node_updated event
                // which is already handled by the persistent listener above
                // Save to history will be handled by operations module via diagram:operation_completed
                    } else {
                // Fallback to generic update if operations module returns null
                this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
                this.saveToHistory('update_text', { nodeId, newText });
            }
        } catch (error) {
            logger.error('InteractiveEditor', 'Error updating node via operations module', error);
            // Fallback to generic update on error
            this.updateGenericNodeText(nodeId, shapeNode, textNode, newText);
            this.saveToHistory('update_text', { nodeId, newText });
        }
    }
    
    /**
     * Update generic node text (for other diagram types)
     */
    updateGenericNodeText(nodeId, shapeNode, textNode, newText) {
        // Verbose logging: Log text edit
        logger.debug('InteractiveEditor', 'Text Edit Applied', {
            nodeId,
            newText: newText.substring(0, 50) + (newText.length > 50 ? '...' : ''),
            textLength: newText.length,
            diagramType: this.diagramType,
            timestamp: Date.now()
        });
        
        // Update the text element
        if (textNode) {
            // Direct text node provided
            d3.select(textNode).text(newText);
        } else if (shapeNode) {
            // Find text near the shape
            const nextSibling = shapeNode.nextElementSibling;
            if (nextSibling && nextSibling.tagName === 'text') {
                d3.select(nextSibling).text(newText);
            }
        } else {
            // Fallback: try to find by data attribute
            const textElement = d3.select(`[data-text-id="${nodeId}"]`);
        if (!textElement.empty()) {
            textElement.text(newText);
            } else {
                // Try by node-id
                const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
                if (!shapeElement.empty()) {
                    const node = shapeElement.node();
                    const nextSibling = node.nextElementSibling;
                    if (nextSibling && nextSibling.tagName === 'text') {
                        d3.select(nextSibling).text(newText);
                    }
                }
            }
        }
    }
    
    /**
     * Add a new node to the diagram
     */
    addNode() {
        this.log('InteractiveEditor: Add node requested', { hasSelection: this.selectedNodes.size > 0 });
        
        // Validate session before adding
        if (!this.validateSession('Add node')) {
            return;
        }
        
        // Use DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            logger.warn('InteractiveEditor', 'DiagramOperationsLoader not available');
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations || typeof operations.addNode !== 'function') {
            logger.warn('InteractiveEditor', `No operations available for diagram type: ${this.diagramType}`);
            this.eventBus?.emit('diagram:operation_warning', {
                message: `Add node operation not supported for ${this.diagramType}`,
                type: 'warning'
            });
            return;
        }
        
        try {
            const result = operations.addNode(this.currentSpec, this);
            // Handle both sync and async operations
            if (result instanceof Promise) {
                result.then((updatedSpec) => {
                    if (updatedSpec) {
                        this.currentSpec = updatedSpec;
                        // Operations module will emit diagram:node_added event
                        // which is already handled by the persistent listener above
                    }
                }).catch((error) => {
                    logger.error('InteractiveEditor', 'Error adding node via operations module', error);
                    this.eventBus?.emit('diagram:operation_warning', {
                        message: 'Failed to add node',
                        type: 'error'
                    });
                });
            } else if (result) {
                this.currentSpec = result;
                // Operations module will emit diagram:node_added event
                // which is already handled by the persistent listener above
            }
        } catch (error) {
            logger.error('InteractiveEditor', 'Error adding node via operations module', error);
            this.eventBus?.emit('diagram:operation_warning', {
                message: 'Failed to add node',
                type: 'error'
            });
        }
    }
    
    /**
     * Recalculate Mind Map layout from backend
     * This is necessary because mind maps require positioned layout data
     */
    async recalculateMindMapLayout() {
        if (!this.currentSpec) {
            logger.error('Editor', 'No spec available for recalculation');
            return;
        }
        
        try {
            logger.debug('Editor', 'Recalculating mind map layout from backend...');
            
            // Show loading state
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: this.getNotif('updatingLayout'), 
                type: 'info' 
            });
            
            // Call backend to recalculate layout
            const response = await window.auth.fetch('/api/recalculate_mindmap_layout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    spec: this.currentSpec
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Update spec with new layout data
            if (data.spec && data.spec._layout) {
                this.currentSpec._layout = data.spec._layout;
                this.currentSpec._recommended_dimensions = data.spec._recommended_dimensions;
                
                // Debug: Verify connections are included
                const connectionCount = data.spec._layout.connections?.length || 0;
                const positionCount = Object.keys(data.spec._layout.positions || {}).length;
                logger.debug('Editor', `Layout recalculated: ${positionCount} positions, ${connectionCount} connections`);
                
                if (connectionCount === 0 && positionCount > 0) {
                    logger.warn('Editor', 'WARNING: Layout has positions but no connections!');
                }
                
                // Re-render with new layout
                this.renderDiagram();
            } else {
                logger.warn('Editor', 'Backend did not return layout data');
                // Still try to render
                this.renderDiagram();
            }
            
        } catch (error) {
            logger.error('Editor', 'Error recalculating mind map layout:', error);
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: this.getNotif('layoutUpdateFailed'), 
                type: 'warning' 
            });
            // Still try to render even if layout calculation failed
            this.renderDiagram();
        }
    }
    
    /**
     * Add a generic node (fallback for other diagram types)
     */
    addGenericNode() {
        // Get SVG container dimensions for positioning
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            logger.error('Editor', 'SVG container not found');
            return;
        }
        
        const svgNode = svg.node();
        const bbox = svgNode.getBBox();
        const width = parseFloat(svg.attr('width')) || 800;
        const height = parseFloat(svg.attr('height')) || 600;
        
        // Create new node in center of visible area
        const centerX = width / 2;
        const centerY = height / 2;
        
        // Add some randomness to avoid overlapping when adding multiple nodes
        const offsetX = (Math.random() - 0.5) * 100;
        const offsetY = (Math.random() - 0.5) * 100;
        
        const newX = centerX + offsetX;
        const newY = centerY + offsetY;
        
        // Create a group for the new node
        const g = svg.append('g')
            .attr('class', 'node-group');
        
        // Default node appearance
        const nodeRadius = 30;
        const nodeId = `node_${Date.now()}`;
        
        // Add circle (shape)
        const circle = g.append('circle')
            .attr('cx', newX)
            .attr('cy', newY)
            .attr('r', nodeRadius)
            .attr('fill', '#667eea')
            .attr('stroke', '#5568d3')
            .attr('stroke-width', 2)
            .attr('data-node-id', nodeId);
        
        // Add text
        const text = g.append('text')
            .attr('x', newX)
            .attr('y', newY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', 'white')
            .attr('font-size', '14px')
            .attr('font-weight', '500')
            .attr('data-text-id', `text_${Date.now()}`)
            .style('pointer-events', 'none')
            .text(window.languageManager?.translate('newNode') || 'New Node');
        
        // Add drag behavior and click handlers (via InteractionHandler)
        // Re-attach handlers to include the new node
        if (this.eventBus) {
            this.eventBus.emit('interaction:attach_handlers_requested');
        }
        
        // Select the new node
        this.selectionManager.clearSelection();
        this.selectionManager.selectNode(nodeId);
        
        // Save to history
        this.saveToHistory('add_node', { nodeId, x: newX, y: newY });
        
        logger.debug('Editor', `Node ${nodeId} added at (${newX.toFixed(0)}, ${newY.toFixed(0)})`);
    }
    
    /**
     * Delete selected nodes
     */
    deleteSelectedNodes() {
        if (this.selectedNodes.size === 0) {
            this.log('InteractiveEditor: Delete requested but no nodes selected');
            return;
        }
        
        // Validate session before deleting
        if (!this.validateSession('Delete nodes')) {
            return;
        }
        
        const nodesToDelete = Array.from(this.selectedNodes);
        this.log('InteractiveEditor: Deleting nodes', { count: nodesToDelete.length, nodeIds: nodesToDelete });
        
        // Use DiagramOperationsLoader
        const operationsLoader = window.currentEditor?.modules?.diagramOperationsLoader;
        if (!operationsLoader) {
            logger.warn('InteractiveEditor', 'DiagramOperationsLoader not available');
            return;
        }
        
        const operations = operationsLoader.getOperations();
        if (!operations || typeof operations.deleteNodes !== 'function') {
            logger.warn('InteractiveEditor', `No operations available for diagram type: ${this.diagramType}`);
            this.eventBus?.emit('diagram:operation_warning', {
                message: `Delete operation not supported for ${this.diagramType}`,
                    type: 'warning'
            });
            return;
        }
        
        try {
            const result = operations.deleteNodes(this.currentSpec, nodesToDelete);
            // Handle both sync and async operations
            if (result instanceof Promise) {
                result.then((updatedSpec) => {
                    if (updatedSpec) {
                        this.currentSpec = updatedSpec;
                        // Operations module will emit diagram:nodes_deleted event
                        // which is already handled by the persistent listener above
                    }
                }).catch((error) => {
                    logger.error('InteractiveEditor', 'Error deleting nodes via operations module', error);
                    this.eventBus?.emit('diagram:operation_warning', {
                        message: 'Failed to delete nodes',
                        type: 'error'
                    });
                });
            } else if (result) {
                this.currentSpec = result;
                // Operations module will emit diagram:nodes_deleted event
                // which is already handled by the persistent listener above
            }
        } catch (error) {
            logger.error('InteractiveEditor', 'Error deleting nodes via operations module', error);
            this.eventBus?.emit('diagram:operation_warning', {
                message: 'Failed to delete nodes',
                type: 'error'
            });
        }
    }
    
    /**
     * Delete generic nodes (fallback for other diagram types)
     */
    deleteGenericNodes(nodeIds) {
        // Remove both the shape and associated text for each node
        nodeIds.forEach(nodeId => {
            // Remove the shape element
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (!shapeElement.empty()) {
                const shapeNode = shapeElement.node();
                
                // Check if inside a group
                if (shapeNode.parentNode && shapeNode.parentNode.tagName === 'g') {
                    // Remove the entire group (shape + text together)
                    d3.select(shapeNode.parentNode).remove();
                } else {
                    // Remove associated text (next sibling)
                    if (shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                        d3.select(shapeNode.nextElementSibling).remove();
                    }
                    
                    // Also check for text by data-text-for attribute
                    d3.select(`[data-text-for="${nodeId}"]`).remove();
                    
                    // Remove the shape
                    shapeElement.remove();
                }
            }
            
            // Also try to remove by text-id (in case it's a text selection)
            d3.select(`[data-text-id="${nodeId}"]`).remove();
        });
        
        logger.debug('Editor', `Deleted ${nodeIds.length} generic node(s) - DOM only (no spec update)`);
    }
    
    /**
     * Select all nodes
     */
    selectAll() {
        d3.selectAll('[data-node-id]').each((d, i, nodes) => {
            const nodeId = d3.select(nodes[i]).attr('data-node-id');
            if (nodeId) {
                this.selectionManager.selectNode(nodeId);
            }
        });
    }
    
    /**
     * Save state to history
     */
    saveToHistory(action, metadata) {
        // Remove any history after current index (branch cut)
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Save a deep clone of the ENTIRE currentSpec, not just metadata
        this.history.push({
            action,
            metadata: metadata ? JSON.parse(JSON.stringify(metadata)) : {},
            spec: JSON.parse(JSON.stringify(this.currentSpec)), // ← THE FIX!
            timestamp: Date.now()
        });
        
        this.historyIndex = this.history.length - 1;
        
        // Limit history size (50 states)
        if (this.history.length > 50) {
            this.history.shift();
            this.historyIndex--;
        }
        
        logger.debug('Editor', `History saved: ${action}, total states: ${this.history.length}, current index: ${this.historyIndex}`);
    }
    
    /**
     * Undo last action
     */
    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            const historyEntry = this.history[this.historyIndex];
            logger.debug('Editor', `Undo: ${historyEntry.action}`, historyEntry.metadata);
            
            // Restore the spec from history
            this.currentSpec = JSON.parse(JSON.stringify(historyEntry.spec));
            
            // Clear selection (nodes may no longer exist)
            this.selectionManager.clearSelection();
            
            // Re-render diagram with restored state
            this.renderDiagram();
            
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Undo: ' + historyEntry.action, 
                type: 'info' 
            });
        } else {
            logger.debug('Editor', 'Undo: No more history to undo');
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Nothing to undo', 
                type: 'warning' 
            });
        }
    }
    
    /**
     * Redo last undone action
     */
    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            const historyEntry = this.history[this.historyIndex];
            logger.debug('Editor', `Redo: ${historyEntry.action}`, historyEntry.metadata);
            
            // Restore the spec from history
            this.currentSpec = JSON.parse(JSON.stringify(historyEntry.spec));
            
            // Clear selection (nodes may no longer exist)
            this.selectionManager.clearSelection();
            
            // Re-render diagram with restored state
            this.renderDiagram();
            
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Redo: ' + historyEntry.action, 
                type: 'info' 
            });
        } else {
            logger.debug('Editor', 'Redo: No more history to redo');
            // ARCHITECTURE: Use Event Bus for notifications
            this.eventBus.emit('notification:show', { 
                message: 'Nothing to redo', 
                type: 'warning' 
            });
        }
    }
    
    /**
     * Update toolbar state
     */
    updateToolbarState() {
        const hasSelection = this.selectedNodes.size > 0;
        const selectedNodesArray = Array.from(this.selectedNodes);
        
        // Update State Manager (source of truth for selection)
        if (window.stateManager && typeof window.stateManager.selectNodes === 'function') {
            window.stateManager.selectNodes(selectedNodesArray);
        }
        
        // NOTE: Selection changes are handled by InteractionHandler via Event Bus
        // which emits 'interaction:selection_changed' event
        // This method is kept for backward compatibility but no longer needs to dispatch events
        // The Event Bus pattern ensures all modules are notified automatically
    }
    
    /**
     * Destroy the editor and clean up all resources
     * Called by DiagramSelector when transitioning back to gallery
     */
    destroy() {
        logger.debug('Editor', 'Destroying InteractiveEditor instance', { diagramType: this.diagramType });
        
        // ========================================
        // 1. REMOVE ALL EVENT LISTENERS
        // ========================================
        
        // Remove D3 event handlers
        d3.select('#d3-container').on('click', null);
        d3.select('body').on('keydown', null);
        
        // Remove DOM event listeners
        const resetViewBtn = document.getElementById('reset-view-btn');
        if (resetViewBtn && this.eventHandlers.resetViewClick) {
            resetViewBtn.removeEventListener('click', this.eventHandlers.resetViewClick);
        }
        
        if (this.eventHandlers.orientationChange) {
            window.removeEventListener('orientationchange', this.eventHandlers.orientationChange);
        }
        
        if (this.eventHandlers.windowResize) {
            window.removeEventListener('resize', this.eventHandlers.windowResize);
        }
        
        // Remove Event Bus listeners (CRITICAL: prevents handlers from executing on destroyed instance)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                logger.debug('Editor', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        // ========================================
        // 2. DESTROY ALL MANAGERS
        // ========================================
        
        // Destroy ToolbarManager
        if (this.toolbarManager) {
            this.toolbarManager.destroy();
            this.toolbarManager = null;
        }
        
        // Clear SelectionManager
        if (this.selectionManager) {
            this.selectionManager.clearSelection();
            this.selectionManager.setSelectionChangeCallback(null);
            this.selectionManager = null;
        }
        
        // Clear CanvasManager
        if (this.canvasManager) {
            this.canvasManager.clear();
            this.canvasManager = null;
        }
        
        // ========================================
        // 2.5 DESTROY ALL REFACTORED MODULES
        // ========================================
        // NOTE: All 18 managers (4 session + 14 modules) are now managed by SessionLifecycleManager
        // They're destroyed in DiagramSelector.backToGallery() via sessionLifecycle.cleanup()
        // We just need to nullify the references here
        if (this.modules) {
            logger.debug('Editor', 'Clearing module references (destroyed by SessionLifecycleManager)');
            this.modules = null;
        }
        
        // Nullify session manager references
        this.thinkGuide = null;
        this.mindMate = null;
        this.nodePalette = null;
        this.voiceAgent = null;
        
        // ========================================
        // 3. CLEAR ALL DATA STRUCTURES
        // ========================================
        
        this.selectedNodes.clear();
        this.history = [];
        this.historyIndex = -1;
        this.eventHandlers = {};
        // Note: eventBusListeners cleanup handled by removeAllListenersForOwner()
        
        // ========================================
        // 4. NULLIFY ALL REFERENCES
        // ========================================
        
        this.currentSpec = null;
        this.renderer = null;
        this.sessionId = null;
        this.sessionDiagramType = null;
        this.zoomBehavior = null;
        this.zoomTransform = null;
        
        logger.debug('Editor', 'InteractiveEditor destroyed successfully');
    }
    
    /**
     * Get current diagram data
     */
    getCurrentDiagramData() {
        return {
            type: this.diagramType,
            spec: this.currentSpec,
            selectedNodes: Array.from(this.selectedNodes),
            timestamp: Date.now()
        };
    }
    
    /**
     * Fit diagram for export - delegates to ViewManager
     * Ensures full diagram is captured, not just visible area
     * 
     * ROOT CAUSE: This method must access ViewManager through this.modules.view
     * Modules are initialized by DiagramSelector after editor.initialize() is called.
     * If modules are not initialized, this indicates a bug in the initialization sequence.
     */
    fitDiagramForExport() {
        if (!this.modules) {
            logger.error('InteractiveEditor', 'fitDiagramForExport: modules not initialized', {
                diagramType: this.diagramType,
                sessionId: this.sessionId,
                hasWindowCurrentEditor: !!window.currentEditor,
                windowCurrentEditorModules: !!window.currentEditor?.modules
            });
            return;
        }
        
        if (!this.modules.view) {
            logger.error('InteractiveEditor', 'fitDiagramForExport: ViewManager module not found', {
                diagramType: this.diagramType,
                availableModules: Object.keys(this.modules || {}),
                sessionId: this.sessionId
            });
            return;
        }
        
        if (typeof this.modules.view.fitDiagramForExport !== 'function') {
            logger.error('InteractiveEditor', 'fitDiagramForExport: ViewManager.fitDiagramForExport method not found', {
                diagramType: this.diagramType,
                viewManagerType: this.modules.view.constructor?.name
            });
            return;
        }
        
        // Call ViewManager's fitDiagramForExport method
        this.modules.view.fitDiagramForExport();
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.InteractiveEditor = InteractiveEditor;
}

