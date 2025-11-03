/**
 * UI State & LLM Selector Manager
 * ===================================
 * 
 * Handles UI state management, visual modes (line mode), and LLM model selection.
 * Manages button states for LLM selection and auto-complete operations.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class UIStateLLMManager {
    constructor(eventBus, stateManager, logger, editor, toolbarManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.toolbarManager = toolbarManager; // Need access to UI elements
        
        this.isLineMode = false;
        
        // Store callback references for cleanup
        this._eventCallbacks = {};
        
        this.setupEventListeners();
        this.logger.info('UIStateLLMManager', 'UI State & LLM Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        // Store callbacks for later cleanup
        this._eventCallbacks.toggleLineMode = () => {
            this.toggleLineMode();
        };
        
        this._eventCallbacks.setAutoButtonLoading = (data) => {
            this.setAutoButtonLoading(data.isLoading);
        };
        
        this._eventCallbacks.setAllLLMButtonsLoading = (data) => {
            this.setAllLLMButtonsLoading(data.isLoading);
        };
        
        this._eventCallbacks.setLLMButtonState = (data) => {
            this.setLLMButtonState(data.model, data.state);
        };
        
        this._eventCallbacks.modelSelectionClicked = (data) => {
            this.handleLLMSelection(data.button);
        };
        
        // Register listeners
        this.eventBus.on('ui:toggle_line_mode', this._eventCallbacks.toggleLineMode);
        this.eventBus.on('ui:set_auto_button_loading', this._eventCallbacks.setAutoButtonLoading);
        this.eventBus.on('ui:set_all_llm_buttons_loading', this._eventCallbacks.setAllLLMButtonsLoading);
        this.eventBus.on('ui:set_llm_button_state', this._eventCallbacks.setLLMButtonState);
        this.eventBus.on('llm:model_selection_clicked', this._eventCallbacks.modelSelectionClicked);
        
        this.logger.debug('UIStateLLMManager', 'Event Bus listeners registered');
    }
    
    /**
     * Toggle line mode (B&W for printing)
     * EXTRACTED FROM: toolbar-manager.js lines 2510-2640
     */
    toggleLineMode() {
        this.isLineMode = !this.isLineMode;
        
        // Toggle button active state
        const lineModeBtn = this.toolbarManager.lineModeBtn;
        if (this.isLineMode) {
            lineModeBtn.classList.add('active');
        } else {
            lineModeBtn.classList.remove('active');
        }
        
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            this.logger.warn('UIStateLLMManager', 'No SVG found in container');
            return;
        }
        
        if (this.isLineMode) {
            // Apply black and white line mode
            
            // Remove canvas background
            svg.style('background-color', 'transparent');
            
            // Select all shapes (circles, rects, ellipses, polygons, paths)
            svg.selectAll('circle, rect, ellipse, polygon, path')
                .each(function() {
                    const element = d3.select(this);
                    
                    // Store original styles as data attributes (for restoration)
                    if (!element.attr('data-original-fill')) {
                        element.attr('data-original-fill', element.style('fill') || element.attr('fill') || 'none');
                    }
                    if (!element.attr('data-original-stroke')) {
                        element.attr('data-original-stroke', element.style('stroke') || element.attr('stroke') || 'none');
                    }
                    if (!element.attr('data-original-stroke-width')) {
                        element.attr('data-original-stroke-width', element.style('stroke-width') || element.attr('stroke-width') || '1');
                    }
                    
                    // Apply line mode: no fill, black stroke
                    element
                        .style('fill', 'none')
                        .style('stroke', '#000000')
                        .style('stroke-width', '2px');
                });
            
            // Make all text black
            svg.selectAll('text')
                .each(function() {
                    const element = d3.select(this);
                    
                    // Store original text color
                    if (!element.attr('data-original-fill')) {
                        element.attr('data-original-fill', element.style('fill') || element.attr('fill') || '#000000');
                    }
                    
                    // Apply black text
                    element.style('fill', '#000000');
                });
            
            // Make all lines/connections black
            svg.selectAll('line')
                .each(function() {
                    const element = d3.select(this);
                    
                    // Store original stroke
                    if (!element.attr('data-original-stroke')) {
                        element.attr('data-original-stroke', element.style('stroke') || element.attr('stroke') || '#000000');
                    }
                    
                    // Apply black stroke
                    element.style('stroke', '#000000');
                });
            
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('lineModeEnabled'), 'success');
            
        } else {
            // Restore original colors
            
            // Restore canvas background (if it had one)
            svg.style('background-color', null);
            
            // Restore shapes
            svg.selectAll('circle, rect, ellipse, polygon, path')
                .each(function() {
                    const element = d3.select(this);
                    
                    const originalFill = element.attr('data-original-fill');
                    const originalStroke = element.attr('data-original-stroke');
                    const originalStrokeWidth = element.attr('data-original-stroke-width');
                    
                    if (originalFill) {
                        element.style('fill', originalFill === 'none' ? 'none' : originalFill);
                        element.attr('data-original-fill', null);
                    }
                    if (originalStroke) {
                        element.style('stroke', originalStroke === 'none' ? 'none' : originalStroke);
                        element.attr('data-original-stroke', null);
                    }
                    if (originalStrokeWidth) {
                        element.style('stroke-width', originalStrokeWidth);
                        element.attr('data-original-stroke-width', null);
                    }
                });
            
            // Restore text colors
            svg.selectAll('text')
                .each(function() {
                    const element = d3.select(this);
                    const originalFill = element.attr('data-original-fill');
                    
                    if (originalFill) {
                        element.style('fill', originalFill);
                        element.attr('data-original-fill', null);
                    }
                });
            
            // Restore line colors
            svg.selectAll('line')
                .each(function() {
                    const element = d3.select(this);
                    const originalStroke = element.attr('data-original-stroke');
                    
                    if (originalStroke) {
                        element.style('stroke', originalStroke);
                        element.attr('data-original-stroke', null);
                    }
                });
            
            this.toolbarManager.showNotification(this.toolbarManager.getNotif('lineModeDisabled'), 'success');
        }
    }
    
    /**
     * Set loading state for auto-complete button
     * EXTRACTED FROM: toolbar-manager.js lines 2645-2655
     */
    setAutoButtonLoading(isLoading) {
        const autoCompleteBtn = this.toolbarManager.autoCompleteBtn;
        if (!autoCompleteBtn) return;
        
        if (isLoading) {
            autoCompleteBtn.classList.add('loading');
            autoCompleteBtn.disabled = true;
        } else {
            autoCompleteBtn.classList.remove('loading');
            autoCompleteBtn.disabled = false;
        }
    }
    
    /**
     * Set loading state for all LLM buttons
     * EXTRACTED FROM: toolbar-manager.js lines 2088-2098
     */
    setAllLLMButtonsLoading(isLoading) {
        const llmButtons = this.toolbarManager.llmButtons;
        llmButtons.forEach(btn => {
            if (isLoading) {
                btn.classList.add('loading');
                btn.disabled = true;
            } else {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        });
    }
    
    /**
     * Set state for specific LLM button
     * EXTRACTED FROM: toolbar-manager.js lines 2103-2119
     */
    setLLMButtonState(model, state) {
        const llmButtons = this.toolbarManager.llmButtons;
        llmButtons.forEach(btn => {
            const llmModel = btn.getAttribute('data-llm');
            if (llmModel === model) {
                btn.classList.remove('loading');
                btn.disabled = false;
                
                if (state === 'ready') {
                    btn.classList.add('ready');
                    btn.classList.remove('error');
                } else if (state === 'error') {
                    btn.classList.add('error');
                    btn.classList.remove('ready');
                }
            }
        });
    }
    
    /**
     * Handle LLM model selection
     * EXTRACTED FROM: toolbar-manager.js lines 347-435
     */
    handleLLMSelection(button) {
        const llmModel = button.getAttribute('data-llm');
        if (!llmModel) return;
        
        // Access llmResults from LLMAutoCompleteManager
        const llmResults = this.editor?.modules?.llmAutoComplete?.llmResults || {};
        const selectedLLM = this.editor?.modules?.llmAutoComplete?.selectedLLM;
        
        // VERBOSE LOG: LLM model switched
        this.logger.info('UIStateLLMManager', '=== LLM MODEL BUTTON CLICKED ===', {
            timestamp: new Date().toISOString(),
            clickedModel: llmModel,
            previousModel: selectedLLM,
            modelState: {
                hasCachedResult: !!llmResults[llmModel],
                isSuccess: llmResults[llmModel]?.success || false,
                hasError: !!(llmResults[llmModel]?.error),
                errorMessage: llmResults[llmModel]?.error || null
            },
            systemState: {
                isGeneratingMulti: this.editor?.modules?.llmAutoComplete?.isGeneratingMulti,
                totalCachedModels: Object.keys(llmResults).length
            },
            allModelsStatus: Object.keys(llmResults).map(model => ({
                model: model,
                success: llmResults[model].success,
                error: llmResults[model].error || null
            }))
        });
        
        // Check if this LLM has cached results
        if (llmResults[llmModel]) {
            // Check if it's a successful result
            if (llmResults[llmModel].success) {
                this.logger.info('UIStateLLMManager', `✓ Switching to successful ${llmModel} result`);
                
                // Update selectedLLM in LLMAutoCompleteManager
                if (this.editor?.modules?.llmAutoComplete) {
                    this.editor.modules.llmAutoComplete.selectedLLM = llmModel;
                }
                
                // Update button states via Event Bus
                window.eventBus.emit('autocomplete:update_button_states_requested', {});
                
                // Render the cached result via Event Bus
                window.eventBus.emit('autocomplete:render_cached_requested', { llmModel });
                
                const modelNames = {
                    'qwen': 'Qwen',
                    'deepseek': 'DeepSeek',
                    'kimi': 'Kimi',
                    'hunyuan': 'HunYuan'
                };
                this.logger.debug('UIStateLLMManager', `Switched to ${modelNames[llmModel] || llmModel} result`);
            } else {
                // Error result - show notification
                const error = llmResults[llmModel].error || 'Generation failed';
                this.logger.warn('UIStateLLMManager', `User clicked on failed ${llmModel} result`, {
                    error: error
                });
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' 
                    ? `${llmModel} 生成失败: ${error}` 
                    : `${llmModel} generation failed: ${error}`;
                this.toolbarManager.showNotification(message, 'error');
            }
        } else if (this.editor?.modules?.llmAutoComplete?.isGeneratingMulti) {
            // CRITICAL FIX: User clicked before this LLM finished generating
            // Show notification instead of silently ignoring the click
            this.logger.debug('UIStateLLMManager', `User clicked ${llmModel} while still generating`);
            const lang = window.languageManager?.getCurrentLanguage() || 'en';
            const modelNames = {
                'qwen': 'Qwen',
                'deepseek': 'DeepSeek',
                'kimi': 'Kimi',
                'hunyuan': 'HunYuan'
            };
            const modelName = modelNames[llmModel] || llmModel;
            const message = lang === 'zh' 
                ? `${modelName} 还在生成中，请稍候...` 
                : `${modelName} is still generating, please wait...`;
            this.toolbarManager.showNotification(message, 'warning');
        } else {
            // No cached results yet, not generating - just update selection
            this.logger.debug('UIStateLLMManager', `${llmModel} selected (no cached results yet)`);
            if (this.editor?.modules?.llmAutoComplete) {
                this.editor.modules.llmAutoComplete.selectedLLM = llmModel;
            }
            // Update button states to show selection
            window.eventBus.emit('autocomplete:update_button_states_requested', {});
        }
    }
    
    /**
     * Cleanup method - remove Event Bus listeners
     */
    destroy() {
        this.logger.debug('UIStateLLMManager', 'Destroying manager and cleaning up listeners');
        
        // Remove Event Bus listeners using stored callbacks
        if (this._eventCallbacks) {
            this.eventBus.off('ui:toggle_line_mode', this._eventCallbacks.toggleLineMode);
            this.eventBus.off('ui:set_auto_button_loading', this._eventCallbacks.setAutoButtonLoading);
            this.eventBus.off('ui:set_all_llm_buttons_loading', this._eventCallbacks.setAllLLMButtonsLoading);
            this.eventBus.off('ui:set_llm_button_state', this._eventCallbacks.setLLMButtonState);
            this.eventBus.off('llm:model_selection_clicked', this._eventCallbacks.modelSelectionClicked);
        }
        
        // Nullify references
        this.editor = null;
        this.toolbarManager = null;
        this._eventCallbacks = null;
        
        this.logger.debug('UIStateLLMManager', 'Cleanup complete');
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.UIStateLLMManager = UIStateLLMManager;
}

