/**
 * Auto-Complete Manager
 * =====================
 * 
 * Manages 4-LLM auto-complete workflow with SSE streaming.
 * Handles parallel model execution, progress tracking, and result selection.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

// Multi-LLM Configuration
const LLM_CONFIG = {
    MODELS: ['qwen', 'deepseek', 'hunyuan', 'kimi'],
    TIMEOUT_MS: 60000,
    RENDER_DELAY_MS: 300,
    MODEL_NAMES: {
        'qwen': 'Qwen',
        'deepseek': 'DeepSeek',
        'hunyuan': 'Hunyuan',
        'kimi': 'Kimi'
    }
};

class AutoCompleteManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Owner ID for Event Bus Listener Registry
        this.ownerId = 'AutoCompleteManager';
        
        // Auto-complete state
        this.isAutoCompleting = false;
        this.activeAbortControllers = new Map();
        this.llmResults = {};
        this.selectedLLM = null;
        
        // UI elements
        this.autoCompleteBtn = null;
        this.llmResultsContainer = null;
        this.llmButtons = {};
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('AutoCompleteManager', 'Auto-Complete Manager initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for auto-complete requests
        this.eventBus.onWithOwner('toolbar:autocomplete_requested', (data) => {
            this.startAutoComplete(data.editor);
        }, this.ownerId);
        
        // Listen for auto-complete cancel requests
        this.eventBus.onWithOwner('autocomplete:cancel_requested', () => {
            this.cancelAllRequests();
        }, this.ownerId);
        
        // Listen for LLM selection
        this.eventBus.onWithOwner('autocomplete:llm_selected', (data) => {
            this.selectLLMResult(data.model);
        }, this.ownerId);
        
        // Listen for session cleanup (cancel any pending requests)
        this.eventBus.onWithOwner('session:cleanup_requested', () => {
            this.cancelAllRequests();
        }, this.ownerId);
        
        this.logger.debug('AutoCompleteManager', 'Subscribed to events with owner tracking');
    }
    
    /**
     * Start auto-complete workflow
     * @param {Object} editor - Editor instance
     */
    async startAutoComplete(editor) {
        if (!editor || !editor.currentSpec) {
            this.logger.error('AutoCompleteManager', 'No editor or diagram data');
            this.eventBus.emit('autocomplete:error', {
                error: 'No diagram data'
            });
            return;
        }
        
        if (this.isAutoCompleting) {
            this.logger.warn('AutoCompleteManager', 'Auto-complete already in progress');
            return;
        }
        
        this.isAutoCompleting = true;
        this.llmResults = {};
        this.selectedLLM = null;
        
        // Extract existing nodes
        const existingNodes = this.extractExistingNodes();
        
        // Detect main topic
        const mainTopic = this.detectMainTopic(existingNodes, editor.currentSpec, editor.diagramType);
        
        if (!mainTopic) {
            this.logger.error('AutoCompleteManager', 'Could not detect main topic');
            this.eventBus.emit('autocomplete:error', {
                error: 'Could not detect main topic'
            });
            this.isAutoCompleting = false;
            return;
        }
        
        this.logger.info('AutoCompleteManager', 'Starting auto-complete', {
            mainTopic,
            existingNodesCount: existingNodes.length,
            diagramType: editor.diagramType
        });
        
        // Emit started event
        this.eventBus.emit('autocomplete:started', {
            mainTopic,
            diagramType: editor.diagramType,
            models: LLM_CONFIG.MODELS
        });
        
        // Start parallel LLM generation
        await this.runParallelGeneration(mainTopic, editor);
        
        this.isAutoCompleting = false;
    }
    
    /**
     * Run parallel LLM generation
     * @param {string} mainTopic - Main topic
     * @param {Object} editor - Editor instance
     */
    async runParallelGeneration(mainTopic, editor) {
        // TODO: Extract parallel LLM logic from toolbar-manager.js - Day 5
        // This includes:
        // - SSE streaming setup
        // - Parallel model execution
        // - Progress tracking
        // - Result caching
        // - UI updates
        this.logger.info('AutoCompleteManager', 'Parallel generation - implementation pending');
        
        // Emit placeholder completed event
        this.eventBus.emit('autocomplete:finished', {
            resultsCount: 0
        });
    }
    
    /**
     * Extract existing nodes from diagram
     * @returns {Array} Array of node objects
     */
    extractExistingNodes() {
        // TODO: Extract from toolbar-manager.js - Day 5
        this.logger.debug('AutoCompleteManager', 'Extract existing nodes - implementation pending');
        return [];
    }
    
    /**
     * Detect main topic from existing nodes or spec
     * @param {Array} existingNodes - Existing nodes
     * @param {Object} spec - Diagram spec
     * @param {string} diagramType - Diagram type
     * @returns {string|null} Main topic
     */
    detectMainTopic(existingNodes, spec, diagramType) {
        // TODO: Extract from toolbar-manager.js - Day 5
        this.logger.debug('AutoCompleteManager', 'Detect main topic - implementation pending');
        return null;
    }
    
    /**
     * Select and apply LLM result
     * @param {string} model - Model name
     */
    selectLLMResult(model) {
        if (!this.llmResults[model] || !this.llmResults[model].success) {
            this.logger.warn('AutoCompleteManager', `No valid result for model: ${model}`);
            return;
        }
        
        this.selectedLLM = model;
        
        this.logger.info('AutoCompleteManager', `Selected LLM result: ${model}`);
        
        // Emit selection event
        this.eventBus.emit('autocomplete:llm_result_selected', {
            model,
            result: this.llmResults[model]
        });
        
        // Update UI
        this.updateLLMButtonStates();
    }
    
    /**
     * Update LLM button states
     */
    updateLLMButtonStates() {
        // TODO: Extract from toolbar-manager.js - Day 5
        this.logger.debug('AutoCompleteManager', 'Update LLM button states - implementation pending');
    }
    
    /**
     * Cancel all active LLM requests
     */
    cancelAllRequests() {
        if (this.activeAbortControllers.size > 0) {
            this.logger.info('AutoCompleteManager', `Cancelling ${this.activeAbortControllers.size} LLM requests`);
            
            this.activeAbortControllers.forEach((controller, model) => {
                controller.abort();
                
                this.eventBus.emit('autocomplete:model_cancelled', {
                    model
                });
            });
            
            this.activeAbortControllers.clear();
            this.isAutoCompleting = false;
            
            this.eventBus.emit('autocomplete:all_cancelled', {});
        }
    }
    
    /**
     * Get auto-complete state
     * @returns {Object} State object
     */
    getState() {
        return {
            isAutoCompleting: this.isAutoCompleting,
            activeRequests: this.activeAbortControllers.size,
            results: Object.keys(this.llmResults),
            selectedLLM: this.selectedLLM
        };
    }
    
    /**
     * Destroy auto-complete manager
     */
    destroy() {
        this.logger.info('AutoCompleteManager', 'Destroying Auto-Complete Manager');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('AutoCompleteManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        this.cancelAllRequests();
    }
}

// Make available globally
window.AutoCompleteManager = AutoCompleteManager;


