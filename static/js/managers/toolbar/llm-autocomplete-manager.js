/**
 * LLM Auto-Complete Manager
 * ==========================
 * 
 * Orchestrator for LLM-based diagram auto-completion with multi-model support.
 * Coordinates with multiple LLM providers (Qwen, DeepSeek, Kimi, Hunyuan)
 * using sub-managers for specific concerns.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class LLMAutoCompleteManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager, llmValidationManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager;
        this.llmValidationManager = llmValidationManager;
        
        // Initialize sub-managers
        this.propertyValidator = new PropertyValidator(this.logger);
        this.llmEngine = new LLMEngineManager(llmValidationManager, this.propertyValidator, this.logger);
        this.progressRenderer = new LLMProgressRenderer(toolbarManager, this.logger);
        this.resultCache = new LLMResultCache(this.logger);
        
        // State
        this.isAutoCompleting = false;
        this.selectedLLM = null;
        
        // Store callback references for cleanup
        this._eventCallbacks = {};
        
        this.setupEventListeners();
        this.logger.info('LLMAutoCompleteManager', 'LLM Auto-Complete Manager initialized (refactored)');
    }
    
    /**
     * Get cached LLM results
     * Exposes resultCache.results for backward compatibility
     */
    get llmResults() {
        return this.resultCache.results;
    }
    
    /**
     * Get isGeneratingMulti state
     */
    get isGeneratingMulti() {
        return this.isAutoCompleting;
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        // Store callbacks for later cleanup
        this._eventCallbacks.startRequested = () => {
            this.logger.debug('LLMAutoCompleteManager', 'Auto-complete requested');
            this.handleAutoComplete();
        };
        
        this._eventCallbacks.renderCached = (data) => {
            this.logger.debug('LLMAutoCompleteManager', 'Render cached result requested', {
                model: data.llmModel
            });
            this.renderCachedLLMResult(data.llmModel);
        };
        
        this._eventCallbacks.updateButtonStates = () => {
            this.updateLLMButtonStates();
        };
        
        this._eventCallbacks.cancelRequested = () => {
            this.logger.debug('LLMAutoCompleteManager', 'Cancellation requested');
            this.cancelAllLLMRequests();
        };
        
        this._eventCallbacks.analyzeConsistency = (data) => {
            if (data.llmResults) {
                this.propertyValidator.analyzeConsistency(data.llmResults, this.logger);
            }
        };
        
        // Register listeners
        this.eventBus.on('autocomplete:start_requested', this._eventCallbacks.startRequested);
        this.eventBus.on('autocomplete:render_cached_requested', this._eventCallbacks.renderCached);
        this.eventBus.on('autocomplete:update_button_states_requested', this._eventCallbacks.updateButtonStates);
        this.eventBus.on('autocomplete:cancel_requested', this._eventCallbacks.cancelRequested);
        this.eventBus.on('llm:analyze_consistency_requested', this._eventCallbacks.analyzeConsistency);
        
        this.logger.debug('LLMAutoCompleteManager', 'Event Bus listeners registered');
    }
    
    /**
     * Cancel all active LLM requests
     */
    cancelAllLLMRequests() {
        this.logger.info('LLMAutoCompleteManager', 'Cancelling all LLM requests');
        this.llmEngine.cancelAllRequests();
        this.progressRenderer.setAllLLMButtonsLoading(false);
    }
    
    /**
     * Main auto-complete orchestrator
     */
    async handleAutoComplete() {
        this.logger.info('LLMAutoCompleteManager', '=== AUTO-COMPLETE STARTED ===', {
            timestamp: new Date().toISOString(),
            diagramType: this.editor?.diagramType,
            sessionId: this.editor?.sessionId
        });
        
        // Validation checks
        if (this.isAutoCompleting) {
            this.logger.warn('LLMAutoCompleteManager', 'Auto-complete already in progress');
            return;
        }
        
        if (!this.editor) {
            this.toolbarManager.showNotification(
                this.toolbarManager.getNotif('editorNotInit'),
                'error'
            );
            return;
        }
        
        this.isAutoCompleting = true;
        
        try {
            // Store context - normalize diagram type to match rendering logic
            let currentDiagramType = this.editor.diagramType;
            if (currentDiagramType === 'mind_map') {
                currentDiagramType = 'mindmap';
            }
            const currentSessionId = this.editor.sessionId;
            
            // Extract nodes and topic from canvas
            const existingNodes = this.llmValidationManager.extractExistingNodes();
            
            // For initial generation from prompt, there might be only the topic node
            // That's fine - we'll generate the full diagram
            const mainTopic = this.llmValidationManager.identifyMainTopic(existingNodes);
            this.logger.info('LLMAutoCompleteManager', `Topic identified: "${mainTopic}"`);
            
            // Detect language
            const language = this._detectLanguage(mainTopic);
            
            // Build request - always use continue mode (canvas already has minimal template)
            const prompt = `Continue the following ${currentDiagramType} diagram with ${existingNodes.length} existing nodes. Main topic/center: "${mainTopic}". Generate additional nodes to complete the diagram structure.`;
            this.logger.info('LLMAutoCompleteManager', `Enriching diagram: ${existingNodes.length} existing nodes`);
            
            const requestBody = {
                prompt: prompt,
                diagram_type: currentDiagramType,
                language: language,
                request_type: 'autocomplete'  // Distinguish from diagram_generation for token tracking
                // Note: 'llm' parameter added per-model by LLMEngineManager
            };
            
            // Clear previous results
            this.resultCache.clear();
            
            // Run multi-model generation
            // Check if a model should be excluded (e.g., already used for initial generation)
            let models = ['qwen', 'deepseek', 'kimi', 'hunyuan'];
            
            // Catapult mode: exclude model that was already used for initial generation
            if (window._autoCompleteExcludeModel) {
                const excludeModel = window._autoCompleteExcludeModel;
                models = models.filter(m => m !== excludeModel);
                this.logger.info('LLMAutoCompleteManager', `Catapult mode: excluding ${excludeModel}, running ${models.length} models: ${models.join(', ')}`);
                // Clear the flag after reading
                window._autoCompleteExcludeModel = null;
            } else {
                this.logger.info('LLMAutoCompleteManager', `Running all ${models.length} models: ${models.join(', ')}`);
            }
            
            // Show loading state ONLY for models that will actually run
            this.toolbarManager.showNotification(
                language === 'zh' ? '正在生成内容...' : 'Generating content...',
                'info'
            );
            this.progressRenderer.setAllLLMButtonsLoading(true, models);
            
            // Emit generation started event
            this.eventBus.emit('llm:generation_started', {
                models: models,
                diagramType: currentDiagramType,
                nodeCount: existingNodes.length,
                mainTopic: mainTopic,
                language: language
            });
            
            const llmResults = await this.llmEngine.callMultipleModels(
                models,
                requestBody,
                {
                    onEachSuccess: (result) => this._handleModelSuccess(result, currentSessionId, currentDiagramType),
                    onEachError: (result) => this.progressRenderer.setLLMButtonState(result.model, 'error'),
                    onComplete: (allResults) => this._handleAllModelsComplete(allResults, language)
                }
            );
            
            // Analyze consistency
            this.eventBus.emit('llm:analyze_consistency_requested', {
                llmResults: llmResults
            });
            
        } catch (error) {
            this.logger.error('LLMAutoCompleteManager', 'Generation failed', error);
            
            // Emit generation failed event
            this.eventBus.emit('llm:generation_failed', {
                error: error.message,
                phase: 'execution'
            });
            
            this.toolbarManager.showNotification(
                'Generation failed. Please try again.',
                'error'
            );
        } finally {
            this.isAutoCompleting = false;
        }
    }
    
    /**
     * Handle successful model result
     */
    _handleModelSuccess(result, expectedSessionId, expectedDiagramType) {
        // Verify context hasn't changed
        if (this.editor.sessionId !== expectedSessionId) {
            this.logger.warn('LLMAutoCompleteManager', `Session changed during ${result.model} generation`);
            return;
        }
        
        // Normalize current diagram type for comparison (mind_map → mindmap)
        let currentDiagramType = this.editor.diagramType;
        if (currentDiagramType === 'mind_map') {
            currentDiagramType = 'mindmap';
        }
        
        if (currentDiagramType !== expectedDiagramType) {
            this.logger.warn('LLMAutoCompleteManager', `Diagram type changed during ${result.model} generation (expected: ${expectedDiagramType}, current: ${currentDiagramType})`);
            return;
        }
        
        // Cache result
        this.resultCache.store(result.model, result);
        this.progressRenderer.setLLMButtonState(result.model, 'ready');
        
        // Emit model completed event
        this.eventBus.emit('llm:model_completed', {
            model: result.model,
            success: true,
            hasSpec: !!result.result?.spec,
            elapsedTime: result.elapsed
        });
        
        // Render first successful result
        if (!this.selectedLLM) {
            this.selectedLLM = result.model;
            this.renderCachedLLMResult(result.model);
            this.updateLLMButtonStates();
            this.toolbarManager.playNotificationSound();
            
            const displayName = window.LLM_CONFIG?.MODEL_NAMES?.[result.model] || result.model;
            this.logger.info('LLMAutoCompleteManager', `First result from ${displayName} rendered`);
            
            // Emit first result available event
            this.eventBus.emit('llm:first_result_available', {
                model: result.model,
                elapsedTime: result.elapsed
            });
        }
    }
    
    /**
     * Handle completion of all models
     */
    _handleAllModelsComplete(llmResults, language) {
        this.progressRenderer.setAllLLMButtonsLoading(false);
        this.updateLLMButtonStates();
        
        const allFailed = Object.values(llmResults).every(r => !r.success);
        const successCount = Object.values(llmResults).filter(r => r.success).length;
        const totalCount = Object.values(llmResults).length;
        
        // Emit generation completed event
        this.eventBus.emit('llm:generation_completed', {
            successCount: successCount,
            totalCount: totalCount,
            allFailed: allFailed,
            results: llmResults
        });
        
        if (allFailed) {
            this.logger.error('LLMAutoCompleteManager', 'All LLM models failed');
            this.toolbarManager.showNotification(
                language === 'zh' ? '生成失败，请重试' : 'Generation failed, please try again',
                'error'
            );
        } else {
            this.logger.info('LLMAutoCompleteManager', `${successCount}/4 models succeeded`);
            this.toolbarManager.showNotification(
                language === 'zh' ? '内容生成成功' : 'Content generated successfully',
                'success'
            );
        }
    }
    
    /**
     * Render cached LLM result
     */
    renderCachedLLMResult(llmModel) {
        this.logger.info('LLMAutoCompleteManager', `Rendering result from ${llmModel.toUpperCase()}`);
        
        const cachedResult = this.resultCache.getResult(llmModel);
        if (!cachedResult || !cachedResult.success) {
            this.logger.error('LLMAutoCompleteManager', `Cannot render ${llmModel}: No valid cached data`);
            this.toolbarManager.showNotification(`Error loading ${llmModel} result`, 'error');
            return;
        }
        
        const spec = cachedResult.result.spec;
        let diagramType = cachedResult.result.diagram_type;
        
        // Normalize diagram type
        if (diagramType === 'mind_map') {
            diagramType = 'mindmap';
        }
        
        // Update editor and render
        if (this.editor) {
            this.editor.currentSpec = spec;
            this.editor.diagramType = diagramType;
            this.editor.renderDiagram();
            
            this.logger.info('LLMAutoCompleteManager', '✓ Diagram rendered successfully', {
                model: llmModel,
                diagramType: diagramType
            });
            
            // Emit result rendered event
            this.eventBus.emit('llm:result_rendered', {
                model: llmModel,
                diagramType: diagramType,
                nodeCount: spec?.nodes?.length || spec?.children?.length || 0
            });
            
            // Fit to window after render completes
            setTimeout(() => {
                this.editor.fitDiagramToWindow();
            }, 300);
        } else {
            this.logger.error('LLMAutoCompleteManager', 'Cannot render: editor not initialized');
        }
    }
    
    /**
     * Update LLM button states
     */
    updateLLMButtonStates() {
        const cachedModels = this.resultCache.getCachedModels();
        const allResults = this.resultCache.getAllResults();
        
        this.progressRenderer.updateButtonStates(allResults);
        
        if (this.selectedLLM) {
            this.progressRenderer.highlightSelectedModel(this.selectedLLM);
        }
    }
    
    /**
     * PRIVATE: Detect language from text
     */
    _detectLanguage(text) {
        const chinesePattern = /[\u4e00-\u9fa5]/;
        return chinesePattern.test(text) ? 'zh' : 'en';
    }
    
    /**
     * Cleanup method - remove Event Bus listeners and cancel requests
     */
    destroy() {
        this.logger.debug('LLMAutoCompleteManager', 'Destroying manager and cleaning up listeners');
        
        // Cancel any in-progress requests
        this.cancelAllLLMRequests();
        
        // Remove Event Bus listeners using stored callbacks
        if (this._eventCallbacks) {
            this.eventBus.off('autocomplete:start_requested', this._eventCallbacks.startRequested);
            this.eventBus.off('autocomplete:render_cached_requested', this._eventCallbacks.renderCached);
            this.eventBus.off('autocomplete:update_button_states_requested', this._eventCallbacks.updateButtonStates);
            this.eventBus.off('autocomplete:cancel_requested', this._eventCallbacks.cancelRequested);
            this.eventBus.off('llm:analyze_consistency_requested', this._eventCallbacks.analyzeConsistency);
        }
        
        // Clear cached results
        if (this.resultCache) {
            this.resultCache.clear();
        }
        
        // Nullify references
        this.editor = null;
        this.toolbarManager = null;
        this.llmValidationManager = null;
        this.llmEngine = null;
        this.progressRenderer = null;
        this.resultCache = null;
        this._eventCallbacks = null;
        
        this.logger.debug('LLMAutoCompleteManager', 'Cleanup complete');
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.LLMAutoCompleteManager = LLMAutoCompleteManager;
}

