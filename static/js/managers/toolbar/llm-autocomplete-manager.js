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
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'LLMAutoCompleteManager';
        
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
     * Check if manager is still active (has Event Bus listeners)
     * When destroy() is called, listeners are removed, so this detects destruction
     */
    _isActive() {
        if (!this.eventBus || !this.ownerId) {
            return false;
        }
        // Check if we still have listeners registered (manager is active)
        const allListeners = this.eventBus.getAllListeners?.();
        return allListeners?.[this.ownerId]?.length > 0;
    }
    
    /**
     * Get cached LLM results (TTL-validated)
     * Exposes only valid (non-expired) results for UI consistency
     */
    get llmResults() {
        // Return TTL-validated results to match getResult() behavior
        // This prevents UI/cache mismatch when cache expires
        const validResults = {};
        for (const model of Object.keys(this.resultCache.results)) {
            const result = this.resultCache.getResult(model);  // Uses TTL check
            if (result) {
                validResults[model] = result;
            }
        }
        return validResults;
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
        
        // Listen to lifecycle events for graceful cancellation
        this._eventCallbacks.sessionEnding = () => {
            this.logger.debug('LLMAutoCompleteManager', 'Session ending - cancelling all operations');
            this.cancelAllLLMRequests();
        };
        
        // Register listeners
        this.eventBus.onWithOwner('autocomplete:start_requested', this._eventCallbacks.startRequested, this.ownerId);
        this.eventBus.onWithOwner('autocomplete:render_cached_requested', this._eventCallbacks.renderCached, this.ownerId);
        this.eventBus.onWithOwner('autocomplete:update_button_states_requested', this._eventCallbacks.updateButtonStates, this.ownerId);
        this.eventBus.onWithOwner('autocomplete:cancel_requested', this._eventCallbacks.cancelRequested, this.ownerId);
        this.eventBus.onWithOwner('llm:analyze_consistency_requested', this._eventCallbacks.analyzeConsistency, this.ownerId);
        this.eventBus.onWithOwner('lifecycle:session_ending', this._eventCallbacks.sessionEnding, this.ownerId);
        
        this.logger.debug('LLMAutoCompleteManager', 'Event Bus listeners registered');
    }
    
    /**
     * Cancel all active LLM requests
     */
    cancelAllLLMRequests() {
        this.logger.info('LLMAutoCompleteManager', 'Cancelling all LLM requests');
        if (this.llmEngine) {
            this.llmEngine.cancelAllRequests();
        }
        if (this.progressRenderer) {
            this.progressRenderer.setAllLLMButtonsLoading(false);
        }
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
        
        // Reset selection for fresh generation (critical for re-generation after topic change)
        // Without this, the first result won't auto-render because selectedLLM still holds old value
        this.selectedLLM = null;
        
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
            let prompt;
            let requestBody;
            
            // BRIDGE MAP SPECIAL HANDLING: Send existing pairs for relationship identification
            if (currentDiagramType === 'bridge_map' && this.editor.currentSpec?.analogies) {
                // Placeholder patterns to filter out (match llm-validation-manager.js patterns)
                const placeholderPatterns = [
                    /^事物[A-Z]\d+$/i,   // 事物A1, 事物B1, etc.
                    /^Item\s*\d+$/i,     // Item 1, Item 2, etc.
                    /^Item\s*[A-Z]$/i,   // Item A, Item B, etc.
                    /^New\s*(Left|Right)$/i,  // New Left, New Right
                    /^新事物[AB]$/,       // Chinese "New Item A/B"
                    /^左项\d*$/,          // 左项, 左项1, etc.
                    /^右项\d*$/,          // 右项, 右项1, etc.
                ];
                
                const isPlaceholder = (text) => {
                    if (!text || !text.trim()) return true;
                    return placeholderPatterns.some(pattern => pattern.test(text.trim()));
                };
                
                const existingAnalogies = this.editor.currentSpec.analogies
                    .filter(pair => pair.left && pair.right && !isPlaceholder(pair.left) && !isPlaceholder(pair.right))  // Filter out placeholders
                    .map(pair => ({ left: pair.left, right: pair.right }));
                
                if (existingAnalogies.length > 0) {
                    // For auto-complete with existing pairs: send pairs but NOT dimension
                    // Let LLM infer the relationship pattern from the user-edited pairs
                    // This allows users to edit pairs and get new suggestions based on the new pattern
                    prompt = `Analyze these bridge map analogy pairs and identify the relationship pattern (dimension). Preserve all existing pairs exactly as provided.`;
                    this.logger.info('LLMAutoCompleteManager', `Bridge map: auto-complete with ${existingAnalogies.length} pairs (no fixed dimension - LLM will infer)`);
                    
                    requestBody = {
                        prompt: prompt,
                        diagram_type: currentDiagramType,
                        language: language,
                        request_type: 'autocomplete',
                        existing_analogies: existingAnalogies  // Send existing pairs, LLM infers dimension
                        // NOTE: Do NOT send fixed_dimension - let LLM determine from pairs
                    };
                } else {
                    // No valid pairs - check if user has specified a dimension (relationship-only mode)
                    const currentDimension = this.editor.currentSpec?.dimension;
                    const hasFixedDimension = currentDimension && currentDimension.trim() !== '';
                    
                    if (hasFixedDimension) {
                        // Mode 3: Relationship-only mode - user has specified a dimension but no pairs
                        prompt = `Generate bridge map analogy pairs using the relationship pattern: "${currentDimension}"`;
                        this.logger.info('LLMAutoCompleteManager', `Bridge map: Relationship-only mode with dimension "${currentDimension}" (no pairs)`);
                        requestBody = {
                            prompt: prompt,
                            diagram_type: currentDiagramType,
                            language: language,
                            request_type: 'autocomplete',
                            existing_analogies: [],  // No existing pairs
                            fixed_dimension: currentDimension  // Send the relationship pattern
                        };
                    } else {
                        // No pairs and no dimension - use standard generation
                        prompt = `Continue the following ${currentDiagramType} diagram with ${existingNodes.length} existing nodes. Main topic/center: "${mainTopic}". Generate additional nodes to complete the diagram structure.`;
                        requestBody = {
                            prompt: prompt,
                            diagram_type: currentDiagramType,
                            language: language,
                            request_type: 'autocomplete'
                        };
                    }
                }
            } else if (currentDiagramType === 'tree_map' || currentDiagramType === 'brace_map') {
                // Tree Map and Brace Map: For auto-complete, send ONLY the topic
                // Do NOT send the dimension - let LLM generate fresh content based on the topic
                // This allows users to edit the topic and get new suggestions without being constrained by old dimension
                const dimType = currentDiagramType === 'tree_map' ? 'classification' : 'decomposition';
                prompt = `Generate a ${currentDiagramType.replace('_', ' ')} for topic "${mainTopic}". Determine the best ${dimType} dimension based on the topic.`;
                this.logger.info('LLMAutoCompleteManager', `${currentDiagramType}: auto-complete with topic only (no fixed dimension)`);
                
                requestBody = {
                    prompt: prompt,
                    diagram_type: currentDiagramType,
                    language: language,
                    request_type: 'autocomplete'
                    // NOTE: Do NOT send fixed_dimension - let LLM determine dimension from topic
                };
            } else {
                // Standard prompt for other diagram types
                prompt = `Continue the following ${currentDiagramType} diagram with ${existingNodes.length} existing nodes. Main topic/center: "${mainTopic}". Generate additional nodes to complete the diagram structure.`;
                this.logger.info('LLMAutoCompleteManager', `Enriching diagram: ${existingNodes.length} existing nodes`);
                
                requestBody = {
                    prompt: prompt,
                    diagram_type: currentDiagramType,
                    language: language,
                    request_type: 'autocomplete'  // Distinguish from diagram_generation for token tracking
                    // Note: 'llm' parameter added per-model by LLMEngineManager
                };
            }
            
            // Clear previous results
            this.resultCache.clear();
            
            // Run multi-model generation
            // Check if a model should be excluded (e.g., already used for initial generation)
            let models = ['qwen', 'deepseek', 'kimi', 'hunyuan', 'doubao'];
            
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
            if (this.toolbarManager) {
            this.toolbarManager.showNotification(
                language === 'zh' ? '正在生成内容...' : 'Generating content...',
                'info'
            );
            }
            if (this.progressRenderer) {
            this.progressRenderer.setAllLLMButtonsLoading(true, models);
            }
            
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
                    onEachError: (result) => {
                        // Safety check before updating UI
                        if (this._isActive() && this.progressRenderer) {
                            this.progressRenderer.setLLMButtonState(result.model, 'error');
                        }
                    },
                    onComplete: (allResults) => this._handleAllModelsComplete(allResults, language)
                }
            );
            
            // Analyze consistency
            this.eventBus.emit('llm:analyze_consistency_requested', {
                llmResults: llmResults
            });
            
        } catch (error) {
            // Only log and notify if manager is still active (abort errors are expected during cancellation)
            if (this._isActive()) {
                this.logger.error('LLMAutoCompleteManager', 'Generation failed', error);
                
                // Emit generation failed event
                if (this.eventBus) {
                    this.eventBus.emit('llm:generation_failed', {
                        error: error.message,
                        phase: 'execution'
                    });
                }
                
                if (this.toolbarManager) {
                    this.toolbarManager.showNotification(
                        'Generation failed. Please try again.',
                        'error'
                    );
                }
            } else {
                // Log cancellation silently (manager destroyed, listeners removed)
                this.logger.debug('LLMAutoCompleteManager', 'Generation cancelled during navigation');
            }
        } finally {
            this.isAutoCompleting = false;
        }
    }
    
    /**
     * Handle successful model result
     */
    _handleModelSuccess(result, expectedSessionId, expectedDiagramType) {
        // Safety check: don't process if manager is no longer active (listeners removed = destroyed)
        if (!this._isActive() || !this.editor || !this.progressRenderer) {
            this.logger.debug('LLMAutoCompleteManager', `Skipping ${result.model} success handler - manager no longer active`);
            return;
        }
        
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
        if (this.resultCache) {
            this.resultCache.store(result.model, result);
        }
        if (this.progressRenderer) {
            this.progressRenderer.setLLMButtonState(result.model, 'ready');
        }
        
        // Emit model completed event
        if (this.eventBus) {
            this.eventBus.emit('llm:model_completed', {
                model: result.model,
                success: true,
                hasSpec: !!result.result?.spec,
                elapsedTime: result.elapsed
            });
        }
        
        // Render first successful result
        if (!this.selectedLLM && this._isActive()) {
            this.selectedLLM = result.model;
            this.renderCachedLLMResult(result.model);
            this.updateLLMButtonStates();
            if (this.toolbarManager) {
                this.toolbarManager.playNotificationSound();
            }
            
            const displayName = window.LLM_CONFIG?.MODEL_NAMES?.[result.model] || result.model;
            this.logger.info('LLMAutoCompleteManager', `First result from ${displayName} rendered`);
            
            // Emit first result available event
            if (this.eventBus) {
                this.eventBus.emit('llm:first_result_available', {
                    model: result.model,
                    elapsedTime: result.elapsed
                });
            }
        }
    }
    
    /**
     * Handle completion of all models
     */
    _handleAllModelsComplete(llmResults, language) {
        // Safety check: don't update UI if manager is no longer active (listeners removed = destroyed)
        if (!this._isActive()) {
            this.logger.debug('LLMAutoCompleteManager', 'Skipping completion handler - manager no longer active');
            return;
        }
        
        // Only update UI if components are still available
        if (this.progressRenderer) {
            this.progressRenderer.setAllLLMButtonsLoading(false);
            this.updateLLMButtonStates();
        }
        
        const allFailed = Object.values(llmResults).every(r => !r.success);
        const successCount = Object.values(llmResults).filter(r => r.success).length;
        const totalCount = Object.values(llmResults).length;
        
        // Emit generation completed event
        if (this.eventBus) {
            this.eventBus.emit('llm:generation_completed', {
                successCount: successCount,
                totalCount: totalCount,
                allFailed: allFailed,
                results: llmResults
            });
        }
        
        // Only show notifications if toolbarManager is still available
        if (this.toolbarManager) {
            if (allFailed) {
                // Log detailed failure information
                const failedModels = Object.keys(this.results).filter(model => 
                    !this.results[model]?.success
                );
                const errorDetails = failedModels.map(model => {
                    const result = this.results[model];
                    return `${model}: ${result?.error || 'Unknown error'}`;
                }).join('; ');
                
                this.logger.error('LLMAutoCompleteManager', `All LLM models failed: ${errorDetails}`, {
                    failedModels,
                    results: this.results
                });
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
    }
    
    /**
     * Render cached LLM result
     */
    renderCachedLLMResult(llmModel) {
        this.logger.info('LLMAutoCompleteManager', `Rendering result from ${llmModel.toUpperCase()}`);
        
        const cachedResult = this.resultCache.getResult(llmModel);
        if (!cachedResult || !cachedResult.success) {
            // This can happen if cache expired between UI check and render
            // Log as debug (not error) since it's an edge case, not a bug
            this.logger.debug('LLMAutoCompleteManager', `Cannot render ${llmModel}: No valid cached data (may have expired)`);
            // Don't show error notification - just inform user to regenerate
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const message = lang === 'zh' 
                ? '缓存已过期，请重新生成' 
                : 'Cache expired, please regenerate';
            this.toolbarManager.showNotification(message, 'info');
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
            
            // Fit to window after render completes (via ViewManager Event Bus)
            setTimeout(() => {
                if (this.eventBus) {
                    this.eventBus.emit('view:fit_diagram_requested');
                } else if (this.editor && typeof this.editor.fitDiagramToWindow === 'function') {
                    // Fallback for backward compatibility
                    this.editor.fitDiagramToWindow();
                } else {
                    this.logger.warn('LLMAutoCompleteManager', 'Cannot fit diagram - ViewManager not available');
                }
            }, 300);
        } else {
            this.logger.error('LLMAutoCompleteManager', 'Cannot render: editor not initialized');
        }
    }
    
    /**
     * Update LLM button states
     */
    updateLLMButtonStates() {
        // Safety check: don't update UI if manager is no longer active
        if (!this._isActive() || !this.progressRenderer || !this.resultCache) {
            return;
        }
        
        const cachedModels = this.resultCache.getCachedModels();
        const allResults = this.resultCache.getAllResults();
        
        if (this.progressRenderer) {
            this.progressRenderer.updateButtonStates(allResults);
            
            // Only highlight selected LLM if it has cached results (auto-complete has been used)
            if (this.selectedLLM && allResults[this.selectedLLM]) {
                this.progressRenderer.highlightSelectedModel(this.selectedLLM);
            }
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
        
        // Cancel any in-progress requests first
        if (this.llmEngine) {
            this.llmEngine.cancelAllRequests();
        }
        
        // Remove all Event Bus listeners (this makes _isActive() return false)
        // Using Listener Registry
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('LLMAutoCompleteManager', `Removed ${removedCount} Event Bus listeners`);
            }
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

