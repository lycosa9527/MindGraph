/**
 * ToolbarManager - Manages toolbar actions and property panel
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

// Multi-LLM Configuration
const LLM_CONFIG = {
    MODELS: ['qwen', 'deepseek', 'hunyuan', 'kimi'],
    TIMEOUT_MS: 60000, // 60 seconds per LLM request
    RENDER_DELAY_MS: 300, // Delay before fitting diagram to window
    MODEL_NAMES: {
        'qwen': 'Qwen',
        'deepseek': 'DeepSeek',
        'hunyuan': 'Hunyuan',
        'kimi': 'Kimi'
    }
};

class ToolbarManager {
    constructor(editor) {
        this.editor = editor;
        this.propertyPanel = null;
        this.currentSelection = [];
        this.isAutoCompleting = false; // Flag to prevent concurrent auto-complete operations
        
        // Session management - store session ID for lifecycle management
        this.sessionId = editor.sessionId;
        this.diagramType = editor.diagramType;
        
        // Track in-progress LLM requests for cancellation
        this.activeAbortControllers = new Map(); // Map<modelName, AbortController>
        
        // Initialize DiagramValidator and LearningModeManager for Learning Mode
        this.validator = new DiagramValidator();
        this.learningModeManager = null; // Initialize on first use to access editor reference
        
        logger.debug('ToolbarManager', `Created for session ${this.sessionId?.substr(-8)}`, {
            diagramType: this.diagramType
        });
        
        // Register this instance in the global registry
        this.registerInstance();
        
        this.initializeElements();
        this.attachEventListeners();
        this.listenToSelectionChanges();
    }
    
    /**
     * Cancel all in-progress LLM requests
     * Called when returning to gallery or destroying the editor
     */
    cancelAllLLMRequests() {
        if (this.activeAbortControllers.size > 0) {
            logger.info('ToolbarManager', `Cancelling ${this.activeAbortControllers.size} LLM requests`);
            this.activeAbortControllers.forEach((controller, model) => {
                controller.abort();
            });
            this.activeAbortControllers.clear();
        }
    }
    
    /**
     * @deprecated - Use logger.debug/info/warn/error directly instead
     * Legacy method for backward compatibility
     */
    logToBackend(level, message, data = null) {
        // Now handled by centralized logger
        const levelMap = {
            'DEBUG': () => logger.debug('ToolbarManager', message, data),
            'INFO': () => logger.info('ToolbarManager', message, data),
            'WARN': () => logger.warn('ToolbarManager', message, data),
            'ERROR': () => logger.error('ToolbarManager', message, data)
        };
        (levelMap[level] || levelMap['INFO'])();
    }
    
    /**
     * Register this toolbar manager instance globally, cleaning up old instances from different sessions
     */
    registerInstance() {
        // Initialize global registry if it doesn't exist
        if (!window.toolbarManagerRegistry) {
            window.toolbarManagerRegistry = new Map();
            logger.debug('ToolbarManager', 'Registry initialized');
        }
        
        // Clean up any existing toolbar manager from a different session
        window.toolbarManagerRegistry.forEach((oldManager, oldSessionId) => {
            if (oldSessionId !== this.sessionId) {
                logger.debug('ToolbarManager', 'Cleaning up old instance', {
                    oldSession: oldSessionId?.substr(-8)
                });
                oldManager.destroy();
                window.toolbarManagerRegistry.delete(oldSessionId);
            }
        });
        
        // Register this instance
        window.toolbarManagerRegistry.set(this.sessionId, this);
        logger.debug('ToolbarManager', 'Instance registered', {
            session: this.sessionId?.substr(-8)
        });
    }
    
    /**
     * Initialize DOM elements
     */
    initializeElements() {
        // Toolbar buttons
        this.addNodeBtn = document.getElementById('add-node-btn');
        
        // LLM selector buttons
        this.llmButtons = document.querySelectorAll('.llm-btn');
        this.deleteNodeBtn = document.getElementById('delete-node-btn');
        this.autoCompleteBtn = document.getElementById('auto-complete-btn');
        this.lineModeBtn = document.getElementById('line-mode-btn');
        this.learningBtn = document.getElementById('learning-btn');  // 🆕 Learning Mode button
        this.thinkingBtn = document.getElementById('thinking-btn');  // 🆕 ThinkGuide button
        this.duplicateNodeBtn = document.getElementById('duplicate-node-btn');
        this.emptyNodeBtn = document.getElementById('empty-node-btn');
        this.undoBtn = document.getElementById('undo-btn');
        this.redoBtn = document.getElementById('redo-btn');
        this.resetBtn = document.getElementById('reset-btn');
        this.exportBtn = document.getElementById('export-btn');
        
        // Line mode state
        this.isLineMode = false;
        
        // Property panel
        this.propertyPanel = document.getElementById('property-panel');
        this.closePropBtn = document.getElementById('close-properties');
        
        // Property inputs
        this.propText = document.getElementById('prop-text');
        this.propTextApply = document.getElementById('prop-text-apply');
        this.propFontSize = document.getElementById('prop-font-size');
        this.propFontFamily = document.getElementById('prop-font-family');
        this.propBold = document.getElementById('prop-bold');
        this.propItalic = document.getElementById('prop-italic');
        this.propUnderline = document.getElementById('prop-underline');
        this.propTextColor = document.getElementById('prop-text-color');
        this.propTextColorHex = document.getElementById('prop-text-color-hex');
        this.propFillColor = document.getElementById('prop-fill-color');
        this.propFillColorHex = document.getElementById('prop-fill-color-hex');
        this.propStrokeColor = document.getElementById('prop-stroke-color');
        this.propStrokeColorHex = document.getElementById('prop-stroke-color-hex');
        this.propStrokeWidth = document.getElementById('prop-stroke-width');
        this.propOpacity = document.getElementById('prop-opacity');
        
        // Value displays
        this.strokeWidthValue = document.getElementById('stroke-width-value');
        this.opacityValue = document.getElementById('opacity-value');
        
        // Status bar elements
        this.nodeCountElement = document.getElementById('node-count');
        
        // Initialize LLM selection and results cache
        this.selectedLLM = 'qwen';  // Default to Qwen
        this.llmResults = {};  // Cache for all LLM results
        this.isGeneratingMulti = false;  // Flag for multi-LLM generation
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // LLM selector buttons
        this.llmButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.handleLLMSelection(btn);
            });
        });
        
        // Set initial active state based on saved selection
        this.updateLLMButtonStates();
        
        // Toolbar buttons - stop event propagation to prevent conflicts
        this.addNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleAddNode();
        });
        this.deleteNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleDeleteNode();
        });
        this.autoCompleteBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();  // Also prevent default to be extra safe
            
            // VERBOSE LOG: Mouse click on auto-complete button
            logger.info('ToolbarManager', '=== AUTO-COMPLETE BUTTON CLICKED ===', {
                timestamp: new Date().toISOString(),
                mouseEvent: {
                    clientX: e.clientX,
                    clientY: e.clientY,
                    target: e.target?.id || 'unknown',
                    button: e.button
                },
                currentState: {
                    diagramType: this.editor?.diagramType,
                    sessionId: this.editor?.sessionId,
                    isAutoCompleting: this.isAutoCompleting,
                    isGeneratingMulti: this.isGeneratingMulti
                }
            });
            
            this.handleAutoComplete();
        });
        this.lineModeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleLineMode();
        });
        this.learningBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleLearningMode();
        });
        this.thinkingBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleThinkingMode();
        });
        this.duplicateNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleDuplicateNode();
        });
        this.emptyNodeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleEmptyNode();
        });
        this.undoBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleUndo();
        });
        this.redoBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleRedo();
        });
        this.resetBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleReset();
        });
        this.exportBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleExport();
        });
        // Note: Back button handled by DiagramSelector.backToGallery()
        // which properly calls cancelAllLLMRequests() before cleanup
        
        // Property panel
        this.closePropBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.hidePropertyPanel();
            this.clearPropertyPanel();
        });
        
        // Property inputs - prevent event bubbling to avoid accidental diagram switches
        // Text input: Apply on Enter key
        this.propText?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.stopPropagation();
                e.preventDefault();
                this.applyText();
            }
        });
        
        // Text apply button - applies text changes
        this.propTextApply?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.applyText();
        });
        
        // Reset styles button - resets to template defaults
        const resetStylesBtn = document.getElementById('reset-styles-btn');
        resetStylesBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.resetStyles();
        });
        this.propBold?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.toggleBold();
            this.applyStylesRealtime(); // Apply immediately
        });
        this.propItalic?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.toggleItalic();
            this.applyStylesRealtime(); // Apply immediately
        });
        this.propUnderline?.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.toggleUnderline();
            this.applyStylesRealtime(); // Apply immediately
        });
        
        // Real-time style updates
        this.propFontSize?.addEventListener('input', () => this.applyStylesRealtime());
        this.propFontFamily?.addEventListener('change', () => this.applyStylesRealtime());
        this.propStrokeWidth?.addEventListener('input', () => this.applyStylesRealtime());
        this.propOpacity?.addEventListener('input', () => this.applyStylesRealtime());
        
        // Color pickers sync and real-time update
        this.propTextColor?.addEventListener('input', (e) => {
            this.propTextColorHex.value = e.target.value.toUpperCase();
            this.applyStylesRealtime(); // Apply immediately
        });
        this.propTextColorHex?.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                this.propTextColor.value = e.target.value;
                this.applyStylesRealtime(); // Apply immediately
            }
        });
        
        this.propFillColor?.addEventListener('input', (e) => {
            this.propFillColorHex.value = e.target.value.toUpperCase();
            this.applyStylesRealtime(); // Apply immediately
        });
        this.propFillColorHex?.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                this.propFillColor.value = e.target.value;
                this.applyStylesRealtime(); // Apply immediately
            }
        });
        
        this.propStrokeColor?.addEventListener('input', (e) => {
            this.propStrokeColorHex.value = e.target.value.toUpperCase();
            this.applyStylesRealtime(); // Apply immediately
        });
        this.propStrokeColorHex?.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                this.propStrokeColor.value = e.target.value;
                this.applyStylesRealtime(); // Apply immediately
            }
        });
        
        // Sliders
        this.propStrokeWidth?.addEventListener('input', (e) => {
            this.strokeWidthValue.textContent = `${e.target.value}px`;
        });
        
        this.propOpacity?.addEventListener('input', (e) => {
            const percent = Math.round(e.target.value * 100);
            this.opacityValue.textContent = `${percent}%`;
        });
    }
    
    /**
     * Handle LLM selection button click
     */
    handleLLMSelection(button) {
        const llmModel = button.getAttribute('data-llm');
        if (!llmModel) return;
        
        // VERBOSE LOG: LLM model switched
        logger.info('ToolbarManager', '=== LLM MODEL BUTTON CLICKED ===', {
            timestamp: new Date().toISOString(),
            clickedModel: llmModel,
            previousModel: this.selectedLLM,
            modelState: {
                hasCachedResult: !!this.llmResults[llmModel],
                isSuccess: this.llmResults[llmModel]?.success || false,
                hasError: !!(this.llmResults[llmModel]?.error),
                errorMessage: this.llmResults[llmModel]?.error || null
            },
            systemState: {
                isGeneratingMulti: this.isGeneratingMulti,
                totalCachedModels: Object.keys(this.llmResults).length
            },
            allModelsStatus: Object.keys(this.llmResults).map(model => ({
                model: model,
                success: this.llmResults[model].success,
                error: this.llmResults[model].error || null
            }))
        });
        
        // Check if this LLM has cached results
        if (this.llmResults[llmModel]) {
            // Check if it's a successful result
            if (this.llmResults[llmModel].success) {
                logger.info('ToolbarManager', `✓ Switching to successful ${llmModel} result`);
                this.selectedLLM = llmModel;
                this.updateLLMButtonStates();
                
                // Render the cached result
                this.renderCachedLLMResult(llmModel);
                
                const modelNames = {
                    'qwen': 'Qwen',
                    'deepseek': 'DeepSeek',
                    'kimi': 'Kimi',
                    'hunyuan': 'HunYuan'
                };
                logger.debug('ToolbarManager', `Switched to ${modelNames[llmModel] || llmModel} result`);
            } else {
                // Error result - show notification
                const error = this.llmResults[llmModel].error || 'Generation failed';
                logger.warn('ToolbarManager', `User clicked on failed ${llmModel} result`, {
                    error: error
                });
                const lang = window.languageManager?.getCurrentLanguage() || 'en';
                const message = lang === 'zh' 
                    ? `${llmModel} 生成失败: ${error}` 
                    : `${llmModel} generation failed: ${error}`;
                this.showNotification(message, 'error');
            }
        } else if (this.isGeneratingMulti) {
            // CRITICAL FIX: User clicked before this LLM finished generating
            // Show notification instead of silently ignoring the click
            logger.debug('ToolbarManager', `User clicked ${llmModel} while still generating`);
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
            this.showNotification(message, 'warning');
        } else {
            // No cached results yet, not generating - just update selection
            logger.debug('ToolbarManager', `${llmModel} selected (no cached results yet)`);
            this.selectedLLM = llmModel;
            this.updateLLMButtonStates();
        }
    }
    
    /**
     * Render cached LLM result
     */
    renderCachedLLMResult(llmModel) {
        logger.info('ToolbarManager', `=== RENDERING CACHED RESULT FROM ${llmModel.toUpperCase()} ===`, {
            timestamp: new Date().toISOString(),
            model: llmModel
        });
        
        const cachedData = this.llmResults[llmModel];
        if (!cachedData || !cachedData.success) {
            logger.error('ToolbarManager', `Cannot render ${llmModel}: No cached data or failed`, {
                hasCachedData: !!cachedData,
                success: cachedData?.success
            });
            this.showNotification(`Error loading ${llmModel} result`, 'error');
            return;
        }
        
        const result = cachedData.result;
        const spec = result.spec;
        
        // VERBOSE LOG: Detailed spec analysis
        logger.info('ToolbarManager', `Analyzing spec from ${llmModel}`, {
            diagramType: result.diagram_type,
            specStructure: {
                hasNodes: !!spec?.nodes,
                nodeCount: spec?.nodes?.length || 0,
                hasChildren: !!spec?.children,
                childrenCount: spec?.children?.length || 0,
                hasTopic: !!spec?.topic,
                topic: spec?.topic,
                hasSteps: !!spec?.steps,
                stepsCount: spec?.steps?.length || 0,
                hasAnalogies: !!spec?.analogies,
                analogiesCount: spec?.analogies?.length || 0,
                allKeys: spec ? Object.keys(spec) : []
            }
        });
        
        // VERBOSE LOG: Extract and log all nodes/children with positions
        let nodesInfo = [];
        if (spec?.nodes) {
            nodesInfo = spec.nodes.map((node, i) => ({
                index: i,
                id: node.id || 'no-id',
                text: node.text || node.label || 'no-text',
                position: { x: node.x || 0, y: node.y || 0 },
                type: node.type || 'unknown',
                level: node.level || 'unknown'
            }));
        } else if (spec?.children) {
            nodesInfo = spec.children.map((child, i) => ({
                index: i,
                text: child.text || child.label || child,
                type: 'child'
            }));
        } else if (spec?.steps) {
            nodesInfo = spec.steps.map((step, i) => ({
                index: i,
                text: typeof step === 'string' ? step : step.text || step.label,
                type: 'step'
            }));
        }
        
        logger.info('ToolbarManager', `=== NODES GENERATED BY ${llmModel.toUpperCase()} ===`, {
            timestamp: new Date().toISOString(),
            totalNodes: nodesInfo.length,
            nodes: nodesInfo
        });
        
        logger.debug('ToolbarManager', `Rendering ${llmModel} result`, {
            nodes: spec?.nodes?.length || 0
        });
        
        // Normalize diagram type (backend returns "mind_map", frontend uses "mindmap")
        let diagramType = result.diagram_type;
        if (diagramType === 'mind_map') {
            diagramType = 'mindmap';
        }
        
        // Update editor with cached spec
        if (this.editor) {
            logger.info('ToolbarManager', 'Updating editor with new spec and rendering', {
                diagramType: diagramType,
                sessionId: this.editor.sessionId
            });
            
            this.editor.currentSpec = spec;
            this.editor.diagramType = diagramType;
            this.editor.renderDiagram();
            
            logger.info('ToolbarManager', '✓ Diagram rendered successfully', {
                model: llmModel,
                diagramType: diagramType
            });
            
            // Reset view to optimal position after rendering completes
            setTimeout(() => {
                this.editor.fitDiagramToWindow();
                logger.debug('ToolbarManager', 'View fitted to window');
            }, 300);
        } else {
            logger.error('ToolbarManager', 'Cannot render: editor not initialized');
        }
    }
    
    /**
     * Update LLM button active states
     */
    updateLLMButtonStates() {
        this.llmButtons.forEach(btn => {
            const llmModel = btn.getAttribute('data-llm');
            
            // Set active state
            if (llmModel === this.selectedLLM) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
            
            // Set ready/error/disabled states based on cached results
            if (this.llmResults[llmModel] && this.llmResults[llmModel].success) {
                // Has successful result - enable and mark as ready
                btn.classList.add('ready');
                btn.classList.remove('error', 'disabled');
                btn.disabled = false;
            } else if (this.llmResults[llmModel] && !this.llmResults[llmModel].success) {
                // Has error result - enable but mark as error (user can click to see error)
                btn.classList.add('error');
                btn.classList.remove('ready', 'disabled');
                btn.disabled = false;
            } else if (this.isGeneratingMulti) {
                // CRITICAL FIX: No result yet and still generating - disable to prevent confusion
                btn.classList.add('disabled');
                btn.classList.remove('ready', 'error');
                btn.disabled = true; // Actually disable the button
            } else {
                // No result yet, not generating - reset to default state
                btn.classList.remove('ready', 'error', 'disabled');
                btn.disabled = false;
            }
        });
    }
    
    /**
     * Listen to selection changes from editor
     */
    listenToSelectionChanges() {
        window.addEventListener('editor-selection-change', (event) => {
            this.currentSelection = event.detail.selectedNodes;
            const hasSelection = event.detail.hasSelection;
            
            // VERBOSE LOG: Node selection via mouse click
            if (hasSelection && this.currentSelection.length > 0) {
                logger.info('ToolbarManager', '=== NODE SELECTED (MOUSE CLICK) ===', {
                    timestamp: new Date().toISOString(),
                    selectedNodes: this.currentSelection.map(nodeId => {
                        // nodeId is a string, need to get the actual DOM element
                        const element = document.querySelector(`[data-node-id="${nodeId}"]`);
                        if (element) {
                            return {
                                id: nodeId,
                                text: element.textContent || element.getAttribute('data-text-for') || 'no text',
                                type: element.getAttribute('data-node-type') || 'unknown',
                                tagName: element.tagName,
                                attributes: {
                                    partIndex: element.getAttribute('data-part-index'),
                                    subpartIndex: element.getAttribute('data-subpart-index'),
                                    categoryIndex: element.getAttribute('data-category-index'),
                                    leafIndex: element.getAttribute('data-leaf-index')
                                },
                                position: {
                                    x: element.getAttribute('x') || element.getAttribute('cx') || 'N/A',
                                    y: element.getAttribute('y') || element.getAttribute('cy') || 'N/A'
                                }
                            };
                        } else {
                            return {
                                id: nodeId,
                                text: 'element not found',
                                type: 'unknown',
                                tagName: 'N/A',
                                attributes: {},
                                position: { x: 'N/A', y: 'N/A' }
                            };
                        }
                    }),
                    totalSelected: this.currentSelection.length,
                    diagramType: this.editor?.diagramType
                });
            } else {
                logger.debug('ToolbarManager', 'Node selection cleared');
            }
            
            // Update toolbar button states
            this.updateToolbarState(hasSelection);
            
            // Check if ThinkGuide or MindMate AI panels are currently open
            // If so, don't auto-open the property panel (user is in a different mode)
            const currentPanel = window.panelManager?.getCurrentPanel();
            const isInAssistantMode = currentPanel === 'thinkguide' || currentPanel === 'mindmate';
            
            // Show/hide property panel based on selection (unless in assistant mode)
            if (hasSelection && this.currentSelection.length > 0) {
                // Only auto-open property panel if not in ThinkGuide/MindMate mode
                if (!isInAssistantMode) {
                    this.showPropertyPanel();
                    this.loadNodeProperties(this.currentSelection[0]);
                } else {
                    // In assistant mode: just load properties without showing panel
                    this.loadNodeProperties(this.currentSelection[0]);
                }
            } else {
                // Hide property panel when no selection (only if it's currently open)
                if (currentPanel === 'property') {
                    this.hidePropertyPanel();
                    this.clearPropertyPanel();
                }
            }
        });
        
        // Listen for notification requests from editor
        window.addEventListener('show-notification', (event) => {
            const { message, type } = event.detail;
            this.showNotification(message, type || 'info');
        });
        
        // Set up automatic node counter that watches for DOM changes
        this.setupNodeCounterObserver();
    }
    
    /**
     * Update toolbar button states
     */
    updateToolbarState(hasSelection) {
        if (this.deleteNodeBtn) {
            this.deleteNodeBtn.disabled = !hasSelection;
            this.deleteNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        if (this.emptyNodeBtn) {
            this.emptyNodeBtn.disabled = !hasSelection;
            this.emptyNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        if (this.duplicateNodeBtn) {
            this.duplicateNodeBtn.disabled = !hasSelection;
            this.duplicateNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
        }
        
        // Add button state for diagrams that require selection (brace_map, double_bubble_map, flow_map, multi_flow_map)
        if (this.addNodeBtn && this.editor) {
            const diagramType = this.editor.diagramType;
            const requiresSelection = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map'].includes(diagramType);
            
            if (requiresSelection) {
                this.addNodeBtn.disabled = !hasSelection;
                this.addNodeBtn.style.opacity = hasSelection ? '1' : '0.5';
            } else {
                // For other diagram types, add button is always enabled
                this.addNodeBtn.disabled = false;
                this.addNodeBtn.style.opacity = '1';
            }
        }
    }
    
    /**
     * Show property panel
     */
    showPropertyPanel() {
        if (this.propertyPanel) {
            logger.debug('ToolbarManager', 'Showing property panel');
            
            // Use centralized panel manager
            if (window.panelManager) {
                window.panelManager.openPanel('property');
            } else {
                // Fallback
                this.propertyPanel.style.display = 'block';
            }
            
            // Only resize if diagram is currently at full width
            // If already sized for panel, just show the panel without resizing
            if (window.currentEditor && !window.currentEditor.isSizedForPanel) {
                setTimeout(() => {
                    if (typeof window.currentEditor.fitToCanvasWithPanel === 'function') {
                        window.currentEditor.fitToCanvasWithPanel(true); // true = animate
                    }
                }, 50); // Small delay to ensure panel is visible
            }
        } else {
            logger.warn('ToolbarManager', 'Property panel element not found');
        }
    }
    
    /**
     * Hide property panel
     */
    hidePropertyPanel() {
        if (this.propertyPanel) {
            // Use centralized panel manager
            if (window.panelManager) {
                window.panelManager.closePanel('property');
            } else {
                // Fallback
                this.propertyPanel.style.display = 'none';
            }
            
            // Always resize to full width when panel is hidden
            // This allows diagram to expand and use all available space
            setTimeout(() => {
                if (window.currentEditor && typeof window.currentEditor.fitToFullCanvas === 'function') {
                    window.currentEditor.fitToFullCanvas(true); // true = animate
                }
            }, 50); // Small delay to ensure panel is hidden
        }
    }
    
    /**
     * Clear property panel inputs to default values
     * Called when switching diagrams or clearing selection
     */
    clearPropertyPanel() {
        // Clear text input
        if (this.propText) this.propText.value = '';
        
        // Reset font properties to defaults
        if (this.propFontSize) this.propFontSize.value = 14;
        if (this.propFontFamily) this.propFontFamily.value = 'Inter, sans-serif';
        
        // Reset colors to defaults
        if (this.propTextColor) this.propTextColor.value = '#000000';
        if (this.propTextColorHex) this.propTextColorHex.value = '#000000';
        if (this.propFillColor) this.propFillColor.value = '#2196f3';
        if (this.propFillColorHex) this.propFillColorHex.value = '#2196F3';
        if (this.propStrokeColor) this.propStrokeColor.value = '#1976d2';
        if (this.propStrokeColorHex) this.propStrokeColorHex.value = '#1976D2';
        
        // Reset stroke width and opacity to defaults
        if (this.propStrokeWidth) this.propStrokeWidth.value = 2;
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = '2px';
        if (this.propOpacity) this.propOpacity.value = 1;
        if (this.opacityValue) this.opacityValue.textContent = '100%';
        
        // Reset toggle buttons
        if (this.propBold) this.propBold.classList.remove('active');
        if (this.propItalic) this.propItalic.classList.remove('active');
        if (this.propUnderline) this.propUnderline.classList.remove('active');
        
    }
    
    /**
     * Load properties from selected node
     */
    loadNodeProperties(nodeId) {
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        
        if (nodeElement.empty()) return;
        
        // Get node attributes (current values)
        const fill = nodeElement.attr('fill') || '#2196f3';
        const stroke = nodeElement.attr('stroke') || '#1976d2';
        const strokeWidth = nodeElement.attr('stroke-width') || '2';
        const opacity = nodeElement.attr('opacity') || '1';
        
        // Get text element - try multiple methods to find it
        let textElement = null;
        let text = '';
        
        // Check if this is a dimension node - special handling needed
        const nodeType = nodeElement.attr('data-node-type');
        if (nodeType === 'dimension') {
            // For dimension nodes, get the actual value from data-dimension-value attribute
            const dimensionValue = nodeElement.attr('data-dimension-value') || '';
            text = dimensionValue;
            
            // Still find the text element for styling attributes
            textElement = d3.select(`[data-text-for="${nodeId}"]`);
            if (textElement.empty()) {
                // Try as child
                textElement = nodeElement.select('text');
            }
        } else {
            // Regular node handling - get display text
            // Method 1: Try as child
            textElement = nodeElement.select('text');
            if (!textElement.empty()) {
                text = textElement.text() || '';
            } else {
                // Method 2: Try data-text-for attribute
                textElement = d3.select(`[data-text-for="${nodeId}"]`);
                if (!textElement.empty()) {
                    text = textElement.text() || '';
                } else {
                    // Method 3: Try next sibling
                    const shapeNode = nodeElement.node();
                    if (shapeNode && shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                        textElement = d3.select(shapeNode.nextElementSibling);
                        text = textElement.text() || '';
                    }
                }
            }
        }
        
        // Get text attributes (with fallbacks if text element not found)
        const fontSize = textElement && !textElement.empty() ? (textElement.attr('font-size') || '14') : '14';
        const fontFamily = textElement && !textElement.empty() ? (textElement.attr('font-family') || 'Inter, sans-serif') : 'Inter, sans-serif';
        const textColor = textElement && !textElement.empty() ? (textElement.attr('fill') || '#000000') : '#000000';
        const fontWeight = textElement && !textElement.empty() ? (textElement.attr('font-weight') || 'normal') : 'normal';
        const fontStyle = textElement && !textElement.empty() ? (textElement.attr('font-style') || 'normal') : 'normal';
        const textDecoration = textElement && !textElement.empty() ? (textElement.attr('text-decoration') || 'none') : 'none';
        
        // Helper function to expand shorthand hex color codes (e.g., #fff -> #ffffff)
        const expandHexColor = (hex) => {
            if (!hex || !hex.startsWith('#')) return hex;
            // If it's a 3-digit hex code, expand it to 6 digits
            if (hex.length === 4) {
                return '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3];
            }
            return hex;
        };
        
        // Expand shorthand hex codes for color inputs (HTML color inputs require 6-digit format)
        const expandedFill = expandHexColor(fill);
        const expandedStroke = expandHexColor(stroke);
        const expandedTextColor = expandHexColor(textColor);
        
        /**
         * Check if text is a default placeholder using smart pattern matching
         * This covers ALL template variations without hardcoding every possible combination
         */
        const isDefaultPlaceholder = (text) => {
            const trimmedText = text.trim();
            
            // === English Patterns ===
            const englishPatterns = [
                // "New X" patterns
                /^New (Attribute|Step|Cause|Effect|Branch|Node|Item|Category|Subitem|Concept|Context|Similarity|Part|Subpart|Left|Right)$/,
                // "X Difference" patterns (including alphanumeric like "Difference A1")
                /^(Left|Right) Difference$/,
                /^Difference [A-Z]\d+$/,
                // Topic variations
                /^(Main|Central|Root) Topic$/,
                /^Main (Concept|Event|Idea)$/,
                /^Topic [A-Z]$/,
                // Numbered patterns: "Context 1", "Attribute 5", etc.
                /^(Context|Attribute|Similarity|Cause|Effect|Item|Step|Part|Concept|Branch|Category) \d+$/,
                // Lettered patterns: "Item A", "Item B", etc.
                /^Item [A-Z]$/,
                // Hierarchical patterns: "Substep 1.1", "Subpart 2.3", "Sub-item 4.1", "Child 3.2", "Item 1.1"
                /^(Substep|Subpart|Sub-item|Child|Item) \d+\.\d+$/,
                // Flow/Process
                /^(Process Flow|Title)$/,
                // Bridge Map relating factor
                /^as$/,
                // Concept Map relationship labels (edge text)
                /^(relates to|includes|leads to)$/
            ];
            
            // === Chinese Patterns ===
            const chinesePatterns = [
                // "新X" patterns
                /^新(属性|步骤|原因|结果|分支|节点|项目|类别|子项|概念|背景|相似点|部分|子部分|左项|右项)$/,
                // "X差异" patterns (including alphanumeric like "差异A1")
                /^(左|右)差异$/,
                /^差异[A-Z]\d+$/,
                // Topic variations
                /^(主题|中心主题|主要概念|根主题|主要事件|核心概念)$/,
                /^主题[A-Z]$/,
                // Numbered patterns: "背景1", "属性5", "项目99", etc.
                /^(背景|属性|相似点|原因|结果|项目|步骤|部分|概念|分支|类别)\d+$/,
                // Lettered patterns: "项目A", "项目B", etc.
                /^项目[A-Z]$/,
                // Hierarchical patterns: "子步骤1.1", "子部分2.3", "子项4.1", "子节点3.2", "项目1.1"
                /^(子步骤|子部分|子项|子节点|项目)\d+\.\d+$/,
                // Flow/Process
                /^(流程|标题)$/,
                // Bridge Map relating factor
                /^如同$/,
                // Concept Map relationship labels (edge text)
                /^(关联|包含|导致)$/
            ];
            
            // Test against all patterns
            const allPatterns = [...englishPatterns, ...chinesePatterns];
            return allPatterns.some(pattern => pattern.test(trimmedText));
        };
        
        // For dimension nodes, never treat as placeholder since we're showing the actual value
        const isPlaceholder = (nodeType === 'dimension') ? false : isDefaultPlaceholder(text);
        
        // Update property inputs
        if (this.propText) {
            if (isPlaceholder) {
                // Set as placeholder attribute (grey text that disappears on type)
                this.propText.value = '';
                this.propText.placeholder = text;
            } else {
                // Set as actual value
                this.propText.value = text;
                this.propText.placeholder = window.languageManager?.translate('nodeTextPlaceholder') || 'Node text';
            }
        }
        if (this.propFontSize) this.propFontSize.value = parseInt(fontSize);
        if (this.propFontFamily) this.propFontFamily.value = fontFamily;
        if (this.propTextColor) this.propTextColor.value = expandedTextColor;
        if (this.propTextColorHex) this.propTextColorHex.value = expandedTextColor.toUpperCase();
        if (this.propFillColor) this.propFillColor.value = expandedFill;
        if (this.propFillColorHex) this.propFillColorHex.value = expandedFill.toUpperCase();
        if (this.propStrokeColor) this.propStrokeColor.value = expandedStroke;
        if (this.propStrokeColorHex) this.propStrokeColorHex.value = expandedStroke.toUpperCase();
        if (this.propStrokeWidth) this.propStrokeWidth.value = parseFloat(strokeWidth);
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = `${strokeWidth}px`;
        if (this.propOpacity) this.propOpacity.value = parseFloat(opacity);
        if (this.opacityValue) this.opacityValue.textContent = `${Math.round(parseFloat(opacity) * 100)}%`;
        
        // Update toggle buttons
        if (this.propBold) {
            this.propBold.classList.toggle('active', fontWeight === 'bold');
        }
        if (this.propItalic) {
            this.propItalic.classList.toggle('active', fontStyle === 'italic');
        }
        if (this.propUnderline) {
            this.propUnderline.classList.toggle('active', textDecoration === 'underline');
        }
    }
    
    /**
     * Apply text changes
     */
    applyText(silent = false) {
        if (this.currentSelection.length === 0) return;
        
        const newText = this.propText.value.trim();
        if (!newText) {
            // If empty, no text to apply (user didn't type anything)
            this.showNotification(this.getNotif('textEmpty'), 'warning');
            return;
        }
        
        logger.debug('ToolbarManager', 'Applying text to selected nodes', {
            count: this.currentSelection.length
        });
        
        this.currentSelection.forEach(nodeId => {
            // Get the shape node
            const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (shapeElement.empty()) {
                logger.warn('ToolbarManager', `Node ${nodeId} not found`);
                return;
            }
            
            const shapeNode = shapeElement.node();
            
            // Find associated text element
            let textNode = null;
            
            // Method 1: Try data-text-for attribute
            const textByDataAttr = d3.select(`[data-text-for="${nodeId}"]`);
            if (!textByDataAttr.empty()) {
                textNode = textByDataAttr.node();
            } else {
                // Method 2: Try next sibling
                if (shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                    textNode = shapeNode.nextElementSibling;
                } else {
                    // Method 3: Try child text (for grouped elements)
                    const textChild = shapeElement.select('text');
                    if (!textChild.empty()) {
                        textNode = textChild.node();
                    }
                }
            }
            
            // Use the editor's updateNodeText method which handles all diagram types properly
            if (this.editor && typeof this.editor.updateNodeText === 'function') {
                this.editor.updateNodeText(nodeId, shapeNode, textNode, newText);
            } else {
                logger.error('ToolbarManager', 'Editor updateNodeText method not available');
            }
        });
        
        // Only show notification if not called from applyAllProperties
        if (!silent) {
            this.showNotification(this.getNotif('textUpdated'), 'success');
        }
    }
    
    /**
     * Apply all properties to selected nodes
     */
    applyAllProperties() {
        if (this.currentSelection.length === 0) return;
        
        const properties = {
            text: this.propText?.value,
            fontSize: this.propFontSize?.value,
            fontFamily: this.propFontFamily?.value,
            textColor: this.propTextColor?.value,
            fillColor: this.propFillColor?.value,
            strokeColor: this.propStrokeColor?.value,
            strokeWidth: this.propStrokeWidth?.value,
            opacity: this.propOpacity?.value,
            bold: this.propBold?.classList.contains('active'),
            italic: this.propItalic?.classList.contains('active'),
            underline: this.propUnderline?.classList.contains('active')
        };
        
        logger.debug('ToolbarManager', 'Applying all properties', {
            count: this.currentSelection.length
        });
        
        // Apply text changes first using the proper method (silently - we'll show one notification at the end)
        if (properties.text && properties.text.trim()) {
            this.applyText(true); // Pass true to suppress notification
        }
        
        this.currentSelection.forEach(nodeId => {
            const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (nodeElement.empty()) return;
            
            // Find text element using multiple methods
            let textElement = d3.select(`[data-text-for="${nodeId}"]`);
            if (textElement.empty()) {
                const node = nodeElement.node();
                if (node.nextElementSibling && node.nextElementSibling.tagName === 'text') {
                    textElement = d3.select(node.nextElementSibling);
                } else {
                    textElement = nodeElement.select('text');
                }
            }
            
            // Apply shape properties
            if (properties.fillColor) {
                nodeElement.attr('fill', properties.fillColor);
            }
            if (properties.strokeColor) {
                nodeElement.attr('stroke', properties.strokeColor);
            }
            if (properties.strokeWidth) {
                nodeElement.attr('stroke-width', properties.strokeWidth);
            }
            if (properties.opacity) {
                nodeElement.attr('opacity', properties.opacity);
            }
            
            // Apply text styling properties (not content - that's handled by applyText)
            if (!textElement.empty()) {
                if (properties.fontSize) {
                    textElement.attr('font-size', properties.fontSize);
                }
                if (properties.fontFamily) {
                    textElement.attr('font-family', properties.fontFamily);
                }
                if (properties.textColor) {
                    textElement.attr('fill', properties.textColor);
                }
                if (properties.bold) {
                    textElement.attr('font-weight', 'bold');
                } else {
                    textElement.attr('font-weight', 'normal');
                }
                if (properties.italic) {
                    textElement.attr('font-style', 'italic');
                } else {
                    textElement.attr('font-style', 'normal');
                }
                if (properties.underline) {
                    textElement.attr('text-decoration', 'underline');
                } else {
                    textElement.attr('text-decoration', 'none');
                }
            }
        });
        
        this.editor?.saveToHistory('update_properties', { 
            nodes: this.currentSelection, 
            properties 
        });
        
        this.showNotification(this.getNotif('propertiesApplied'), 'success');
    }
    
    /**
     * Apply styles in real-time (without notification)
     */
    applyStylesRealtime() {
        if (this.currentSelection.length === 0) return;
        
        const properties = {
            fontSize: this.propFontSize?.value,
            fontFamily: this.propFontFamily?.value,
            textColor: this.propTextColor?.value,
            fillColor: this.propFillColor?.value,
            strokeColor: this.propStrokeColor?.value,
            strokeWidth: this.propStrokeWidth?.value,
            opacity: this.propOpacity?.value,
            bold: this.propBold?.classList.contains('active'),
            italic: this.propItalic?.classList.contains('active'),
            underline: this.propUnderline?.classList.contains('active')
        };
        
        // Apply to all selected nodes
        this.currentSelection.forEach(nodeId => {
            const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
            if (nodeElement.empty()) return;
            
            // Apply shape properties
            if (properties.fillColor) {
                nodeElement.attr('fill', properties.fillColor);
            }
            if (properties.strokeColor) {
                nodeElement.attr('stroke', properties.strokeColor);
            }
            if (properties.strokeWidth) {
                nodeElement.attr('stroke-width', properties.strokeWidth);
            }
            if (properties.opacity) {
                nodeElement.attr('opacity', properties.opacity);
            }
            
            // Find and apply text properties
            let textElement = nodeElement.select('text');
            if (textElement.empty()) {
                textElement = d3.select(`[data-text-for="${nodeId}"]`);
            }
            
            if (!textElement.empty()) {
                if (properties.fontSize) {
                    textElement.attr('font-size', properties.fontSize);
                }
                if (properties.fontFamily) {
                    textElement.attr('font-family', properties.fontFamily);
                }
                if (properties.textColor) {
                    textElement.attr('fill', properties.textColor);
                }
                textElement.attr('font-weight', properties.bold ? 'bold' : 'normal');
                textElement.attr('font-style', properties.italic ? 'italic' : 'normal');
                textElement.attr('text-decoration', properties.underline ? 'underline' : 'none');
            }
        });
        
        // Save to history silently
        this.editor?.saveToHistory('update_properties', { 
            nodes: this.currentSelection, 
            properties 
        });
    }
    
    /**
     * Reset styles to template defaults (keep text unchanged)
     */
    resetStyles() {
        if (this.currentSelection.length === 0) return;
        
        // Get template defaults based on diagram type
        const defaultProps = this.getTemplateDefaults();
        
        // Update UI inputs to template defaults
        if (this.propFontSize) this.propFontSize.value = parseInt(defaultProps.fontSize);
        if (this.propFontFamily) this.propFontFamily.value = defaultProps.fontFamily;
        if (this.propTextColor) this.propTextColor.value = defaultProps.textColor;
        if (this.propTextColorHex) this.propTextColorHex.value = defaultProps.textColor.toUpperCase();
        if (this.propFillColor) this.propFillColor.value = defaultProps.fillColor;
        if (this.propFillColorHex) this.propFillColorHex.value = defaultProps.fillColor.toUpperCase();
        if (this.propStrokeColor) this.propStrokeColor.value = defaultProps.strokeColor;
        if (this.propStrokeColorHex) this.propStrokeColorHex.value = defaultProps.strokeColor.toUpperCase();
        if (this.propStrokeWidth) this.propStrokeWidth.value = parseFloat(defaultProps.strokeWidth);
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = `${defaultProps.strokeWidth}px`;
        if (this.propOpacity) this.propOpacity.value = parseFloat(defaultProps.opacity);
        if (this.opacityValue) this.opacityValue.textContent = `${Math.round(parseFloat(defaultProps.opacity) * 100)}%`;
        
        // Reset style toggles to defaults (off)
        this.propBold?.classList.remove('active');
        this.propItalic?.classList.remove('active');
        this.propUnderline?.classList.remove('active');
        
        // Apply template defaults to selected nodes
        this.applyStylesRealtime();
        
        this.showNotification(
            window.languageManager?.getCurrentLanguage() === 'zh' 
                ? '样式已重置为模板默认值' 
                : 'Styles reset to template defaults',
            'success'
        );
    }
    
    /**
     * Get template default styles based on diagram type
     */
    getTemplateDefaults() {
        const diagramType = this.editor?.diagramType;
        
        // Standard defaults used across all diagram types
        const standardDefaults = {
            fontSize: '14',
            fontFamily: 'Inter, sans-serif',
            textColor: '#000000',
            fillColor: '#2196f3',
            strokeColor: '#1976d2',
            strokeWidth: '2',
            opacity: '1'
        };
        
        // Diagram-specific overrides (if needed)
        const typeSpecificDefaults = {
            'double_bubble_map': {
                ...standardDefaults,
                fillColor: '#4caf50', // Green for similarities
            },
            'multi_flow_map': {
                ...standardDefaults,
                fillColor: '#ff9800', // Orange for events
            },
            'concept_map': {
                ...standardDefaults,
                fillColor: '#9c27b0', // Purple for concepts
            }
        };
        
        return typeSpecificDefaults[diagramType] || standardDefaults;
    }
    
    /**
     * Toggle bold
     */
    toggleBold() {
        this.propBold.classList.toggle('active');
    }
    
    /**
     * Toggle italic
     */
    toggleItalic() {
        this.propItalic.classList.toggle('active');
    }
    
    /**
     * Toggle underline
     */
    toggleUnderline() {
        this.propUnderline.classList.toggle('active');
    }
    
    /**
     * Handle add node
     */
    handleAddNode() {
        logger.debug('ToolbarManager', 'handleAddNode called', {
            diagramType: this.editor?.diagramType
        });
        
        if (!this.editor) {
            logger.error('ToolbarManager', 'handleAddNode blocked - editor not initialized');
            this.showNotification(this.getNotif('editorNotInit'), 'error');
            return;
        }
        
        const diagramType = this.editor.diagramType;
        const requiresSelection = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map', 'mindmap'].includes(diagramType);

        // Check if selection is required for this diagram type
        if (requiresSelection && this.currentSelection.length === 0) {
            this.showNotification(this.getNotif('selectNodeToAdd'), 'warning');
            return;
        }
        
        // Call editor's addNode method (it will handle diagram-specific logic)
        this.editor.addNode();
        
        // Only show generic success notification for diagram types that don't show their own
            const showsOwnNotification = ['brace_map', 'double_bubble_map', 'flow_map', 'multi_flow_map', 'tree_map', 'bridge_map', 'circle_map', 'bubble_map', 'concept_map', 'mindmap'].includes(diagramType);
            if (!showsOwnNotification) {
                this.showNotification(this.getNotif('nodeAdded'), 'success');
            }
        
        // Node count updates automatically via MutationObserver
    }
    
    /**
     * Handle delete node
     */
    handleDeleteNode() {
        if (this.editor && this.currentSelection.length > 0) {
            const count = this.currentSelection.length;
            this.editor.deleteSelectedNodes();
            this.hidePropertyPanel();
            this.showNotification(this.getNotif('nodesDeleted', count), 'success');
            
            // Node count updates automatically via MutationObserver
        } else {
            this.showNotification(this.getNotif('selectNodeToDelete'), 'warning');
        }
    }
    
    /**
     * Handle empty node text (clear text but keep node)
     */
    handleEmptyNode() {
        if (this.editor && this.currentSelection.length > 0) {
            const nodeIds = [...this.currentSelection];
            
            nodeIds.forEach(nodeId => {
                // Find the shape element
                const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
                if (shapeElement.empty()) {
                    logger.warn('ToolbarManager', `Shape not found for nodeId: ${nodeId}`);
                    return;
                }
                
                // Find the text element
                let textElement = d3.select(`[data-text-for="${nodeId}"]`);
                
                // If not found, try to find text as sibling or in parent group
                if (textElement.empty()) {
                    const shapeNode = shapeElement.node();
                    const nextSibling = shapeNode.nextElementSibling;
                    if (nextSibling && nextSibling.tagName === 'text') {
                        textElement = d3.select(nextSibling);
                    } else if (shapeNode.parentElement && shapeNode.parentElement.tagName === 'g') {
                        textElement = d3.select(shapeNode.parentElement).select('text');
                    }
                }
                
                if (!textElement.empty()) {
                    const textNode = textElement.node();
                    
                    // Update the text to empty string
                    if (this.editor && typeof this.editor.updateNodeText === 'function') {
                        this.editor.updateNodeText(nodeId, shapeElement.node(), textNode, '');
                    } else {
                        // Fallback: just update the DOM
                        textElement.text('');
                    }
                }
            });
            
            const count = nodeIds.length;
            this.showNotification(this.getNotif('nodesEmptied', count), 'success');
            
            // Update property panel if still showing
            if (this.currentSelection.length > 0) {
                this.loadNodeProperties(this.currentSelection[0]);
            }
        } else {
            this.showNotification(this.getNotif('selectNodeToEmpty'), 'warning');
        }
    }
    
    /**
     * Handle auto-complete diagram with AI
     */
    async handleAutoComplete() {
        // VERBOSE LOG: Complete environment and state at start
        logger.info('ToolbarManager', '=== AUTO-COMPLETE FUNCTION STARTED ===', {
            timestamp: new Date().toISOString(),
            diagramState: {
                type: this.editor?.diagramType,
                sessionId: this.editor?.sessionId,
                hasSpec: !!this.editor?.currentSpec,
                specKeys: this.editor?.currentSpec ? Object.keys(this.editor.currentSpec) : []
            },
            systemState: {
                selectedLLM: this.selectedLLM,
                cachedResultsCount: Object.keys(this.llmResults).length,
                isAutoCompleting: this.isAutoCompleting,
                isGeneratingMulti: this.isGeneratingMulti,
                activeAbortControllers: this.activeAbortControllers.size
            },
            environment: {
                userAgent: navigator.userAgent,
                language: navigator.language,
                platform: navigator.platform,
                onLine: navigator.onLine,
                cookieEnabled: navigator.cookieEnabled,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight,
                    devicePixelRatio: window.devicePixelRatio
                },
                memory: navigator.deviceMemory ? `${navigator.deviceMemory} GB` : 'unknown',
                connectionType: navigator.connection ? navigator.connection.effectiveType : 'unknown'
            },
            performance: {
                loadTime: performance.now() + 'ms since page load',
                timing: performance.timing ? {
                    domComplete: performance.timing.domComplete - performance.timing.navigationStart + 'ms',
                    loadComplete: performance.timing.loadEventEnd - performance.timing.navigationStart + 'ms'
                } : 'unavailable'
            }
        });
        
        logger.info('ToolbarManager', 'Auto-complete started', {
            diagramType: this.editor?.diagramType
        });
        
        // Prevent concurrent auto-complete operations
        if (this.isAutoCompleting) {
            logger.warn('ToolbarManager', 'Auto-complete already in progress - rejecting new request', {
                timestamp: new Date().toISOString(),
                isGeneratingMulti: this.isGeneratingMulti,
                cachedResults: Object.keys(this.llmResults)
            });
            return;
        }
        
        if (!this.editor) {
            this.showNotification(this.getNotif('editorNotInit'), 'error');
            logger.error('ToolbarManager', 'Auto-complete failed - editor not initialized');
            return;
        }
        
        // Set flag to prevent concurrent operations
        this.isAutoCompleting = true;
        
        // CRITICAL: Validate session before auto-complete
        if (!this.editor.validateSession('Auto-complete')) {
            logger.error('ToolbarManager', 'Session validation failed, aborting auto-complete');
            this.isAutoCompleting = false; // Clear flag on early return
            return;
        }
        
        // CRITICAL: Store the current diagram type and session ID to prevent accidental switching
        const currentDiagramType = this.editor.diagramType;
        const currentSessionId = this.editor.sessionId;
        
        // Extract existing nodes from the diagram
        const existingNodes = this.extractExistingNodes();
        logger.debug('ToolbarManager', 'Extracted existing nodes', {
            count: existingNodes.length
        });
        
        if (existingNodes.length === 0) {
            this.showNotification(this.getNotif('addNodesFirst'), 'warning');
            this.isAutoCompleting = false; // Clear flag on early return
            return;
        }
        
        // Identify the main/central topic (center-most or largest node)
        const mainTopic = this.identifyMainTopic(existingNodes);
        const diagramType = currentDiagramType; // Use locked type
        
        // Log what we identified
        logger.info('ToolbarManager', `Main topic identified: "${mainTopic}"`, {
            spec_topic: this.editor.currentSpec?.topic,
            nodes_count: existingNodes.length
        });
        
        // Store the original topic to preserve it later
        const originalTopic = this.editor.currentSpec?.topic || mainTopic;
        
        // For flow maps, prioritize title for language detection
        let textForLanguageDetection = mainTopic;
        if (diagramType === 'flow_map' && this.editor.currentSpec?.title) {
            textForLanguageDetection = this.editor.currentSpec.title;
        }
        
        // For bridge maps, check all existing nodes for Chinese characters (prioritize user content)
        if (diagramType === 'bridge_map' && existingNodes.length > 0) {
            // Check if any existing node has Chinese characters
            const hasChineseInNodes = existingNodes.some(node => /[\u4e00-\u9fa5]/.test(node.text));
            if (hasChineseInNodes) {
                textForLanguageDetection = existingNodes.find(node => /[\u4e00-\u9fa5]/.test(node.text)).text;
            }
        }
        
        // For brace maps, check all existing nodes for Chinese characters (prioritize user content)
        if (diagramType === 'brace_map' && existingNodes.length > 0) {
            // Check if any existing node has Chinese characters
            const hasChineseInNodes = existingNodes.some(node => /[\u4e00-\u9fa5]/.test(node.text));
            if (hasChineseInNodes) {
                textForLanguageDetection = existingNodes.find(node => /[\u4e00-\u9fa5]/.test(node.text)).text;
            }
        }
        
        // Detect language from the topic/title text (if contains Chinese characters, use Chinese)
        const hasChinese = /[\u4e00-\u9fa5]/.test(textForLanguageDetection);
        const language = hasChinese ? 'zh' : (window.languageManager?.getCurrentLanguage() || 'en');
        
        // Send clean topic to backend - let the agent add the instructions
        // The backend agents already wrap the prompt with proper instructions
        // (e.g., "请为以下描述创建一个圆圈图：{topic}")
        let prompt = mainTopic;
        
        // For brace maps, tree maps, and bridge maps, check if user has specified a dimension
        let dimensionPreference = null;
        if (diagramType === 'brace_map' || diagramType === 'tree_map' || diagramType === 'bridge_map') {
            const dimensionNode = d3.select('[data-node-type="dimension"]');
            if (!dimensionNode.empty()) {
                const rawDimension = dimensionNode.attr('data-dimension-value') || this.editor.currentSpec?.dimension;
                
                // Only use dimension if it's actually filled (not empty, not just whitespace)
                // If empty, let LLM auto-select the best dimension for the topic
                if (rawDimension && rawDimension.trim() !== '') {
                    dimensionPreference = rawDimension.trim();
                }
            }
        }
        
        // Show loading state
        this.setAutoButtonLoading(true);
        this.showNotification(this.getNotif('aiCompleting', mainTopic), 'info');
        
        try {
            // Prepare base request body
            const baseRequestBody = {
                prompt: prompt,
                diagram_type: diagramType,
                language: language,
                session_id: this.editor.sessionId  // Track session
            };
            
            // Add dimension preference if specified
            if (dimensionPreference) {
                baseRequestBody.dimension_preference = dimensionPreference;
            }
            
            // VERBOSE LOG: Base request body prepared
            logger.info('ToolbarManager', '=== LLM REQUEST BODY PREPARED ===', {
                timestamp: new Date().toISOString(),
                requestBody: {
                    prompt: prompt,
                    diagram_type: diagramType,
                    language: language,
                    session_id: this.editor.sessionId,
                    dimension_preference: dimensionPreference || 'not set',
                    prompt_length: prompt.length,
                    has_chinese: /[\u4e00-\u9fa5]/.test(prompt)
                },
                contextInfo: {
                    existingNodesCount: existingNodes.length,
                    mainTopic: mainTopic,
                    originalTopic: originalTopic,
                    textForLanguageDetection: textForLanguageDetection
                }
            });
            
            logger.info('ToolbarManager', 'Starting PARALLEL LLM generation');
            this.isGeneratingMulti = true;
            
            // Set all buttons to loading state
            this.setAllLLMButtonsLoading(true);
            
            // Clear previous results
            this.llmResults = {};
            
            // PARALLEL EXECUTION: Call all LLMs simultaneously using new endpoint!
            const models = LLM_CONFIG.MODELS;
            let firstSuccessfulModel = null;
            
            // Prepare request for parallel generation
            const parallelRequestBody = {
                ...baseRequestBody,
                models: models  // Request all 4 models in parallel
            };
            
            // VERBOSE LOG: Actual request being sent to backend
            logger.info('ToolbarManager', '=== SENDING REQUEST TO LLM MIDDLEWARE ===', {
                timestamp: new Date().toISOString(),
                endpoint: '/api/generate_multi_progressive',
                method: 'POST',
                models: models,
                fullRequestBody: JSON.parse(JSON.stringify(parallelRequestBody)), // Deep copy for logging
                requestSize: JSON.stringify(parallelRequestBody).length + ' bytes'
            });
            
            try {
                logger.info('ToolbarManager', 'Calling progressive generation endpoint (SSE)');
                
                // CRITICAL: Create AbortController for cancellation
                const abortController = new AbortController();
                this.activeAbortControllers.set('multi_progressive', abortController);
                
                // Set timeout (same as sequential mode)
                const timeoutId = setTimeout(() => {
                    logger.warn('ToolbarManager', 'Multi-progressive timeout, aborting');
                    abortController.abort();
                }, LLM_CONFIG.TIMEOUT_MS);
                
                // Use SSE streaming (same pattern as MindMate ai-assistant-manager.js:333-380)
                const response = await auth.fetch('/api/generate_multi_progressive', {
                    method: 'POST',
                    signal: abortController.signal, // Enable cancellation
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(parallelRequestBody)
                });
                
                // Clear timeout on successful connection
                clearTimeout(timeoutId);
                
                // VERBOSE LOG: Response received from server
                logger.info('ToolbarManager', '=== LLM MIDDLEWARE RESPONSE RECEIVED ===', {
                    timestamp: new Date().toISOString(),
                    status: response.status,
                    statusText: response.statusText,
                    ok: response.ok,
                    headers: {
                        contentType: response.headers.get('content-type'),
                        contentLength: response.headers.get('content-length')
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                // Read SSE stream with clean async/await pattern
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let completedCount = 0;
                const startTime = Date.now();
                
                // Modern async/await loop - much cleaner than .then() recursion
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) {
                        // Stream ended
                        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
                        logger.info('ToolbarManager', `Progressive generation stream ended after ${elapsed}s`);
                        break;
                    }
                    
                    // Decode chunk
                    const chunk = decoder.decode(value, { stream: true });
                    buffer += chunk;
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line in buffer (critical!)
                    
                    // Process each complete line
                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            // VERBOSE LOG: Raw SSE data received
                            logger.debug('ToolbarManager', '=== SSE DATA CHUNK RECEIVED ===', {
                                timestamp: new Date().toISOString(),
                                rawLine: line.substring(0, 200) + (line.length > 200 ? '...' : ''),
                                parsedData: {
                                    event: data.event || 'model_result',
                                    model: data.model || 'unknown',
                                    success: data.success,
                                    hasSpec: !!data.spec,
                                    hasDuration: !!data.duration
                                }
                            });
                            
                            // Handle completion event
                            if (data.event === 'complete') {
                                const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
                                logger.info('ToolbarManager', `All models completed in ${elapsed}s`);
                                continue;
                            }
                            
                            // Handle error event
                            if (data.event === 'error') {
                                logger.error('ToolbarManager', `Progressive generation error: ${data.message}`);
                                continue;
                            }
                            
                            // Handle model result
                            const model = data.model;
                            if (!model) continue;
                            
                            completedCount++;
                            const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
                            logger.debug('ToolbarManager', `${model} completed (${completedCount}/${models.length}) in ${elapsed}s`);
                            
                            if (data.success) {
                                // Validate spec before accepting it
                                const specValidation = this._validateLLMSpec(model, data.spec, diagramType);
                                
                                // VERBOSE LOG: Successful LLM response JSON with validation
                                logger.info('ToolbarManager', `=== JSON RESPONSE FROM ${model.toUpperCase()} ===`, {
                                    timestamp: new Date().toISOString(),
                                    model: model,
                                    duration: data.duration ? data.duration.toFixed(2) + 's' : 'unknown',
                                    response: {
                                        diagram_type: data.diagram_type,
                                        has_spec: !!data.spec,
                                        spec_keys: data.spec ? Object.keys(data.spec) : [],
                                        topics: data.topics || [],
                                        style_preferences: data.style_preferences || {},
                                        raw_spec: data.spec  // Full spec for debugging
                                    },
                                    validation: specValidation,
                                    elapsed: elapsed + 's'
                                });
                                
                                // Log validation issues if any
                                if (!specValidation.isValid) {
                                    logger.warn('ToolbarManager', `⚠️ ${model.toUpperCase()} SPEC VALIDATION WARNINGS`, {
                                        model: model,
                                        issues: specValidation.issues,
                                        missingFields: specValidation.missingFields,
                                        invalidFields: specValidation.invalidFields,
                                        spec: data.spec
                                    });
                                }
                                
                                // Normalize diagram type
                                let responseDiagramType = data.diagram_type || diagramType;
                                if (responseDiagramType === 'mind_map') {
                                    responseDiagramType = 'mindmap';
                                }
                                
                                // Cache this model's result
                                this.llmResults[model] = {
                                    model: model,
                                    success: true,
                                    result: {
                                        spec: data.spec,
                                        diagram_type: responseDiagramType,
                                        topics: data.topics || [],
                                        style_preferences: data.style_preferences || {}
                                    },
                                    validation: specValidation
                                };
                                
                                // Update button state
                                this.setLLMButtonState(model, 'ready');
                                
                                // Render FIRST successful result IMMEDIATELY
                                if (!firstSuccessfulModel) {
                                    firstSuccessfulModel = model;
                                    this.selectedLLM = model;
                                    this.renderCachedLLMResult(model);
                                    this.updateLLMButtonStates();
                                    
                                    const modelName = LLM_CONFIG.MODEL_NAMES[model] || model;
                                    logger.info('ToolbarManager', `First result from ${modelName} rendered at ${elapsed}s`);
                                    
                                    // Play success sound notification
                                    this.playNotificationSound();
                                }
                                
                                logger.debug('ToolbarManager', `${model} result cached (${data.duration.toFixed(2)}s)`);
                            } else {
                                // Model failed
                                const errorMessage = data.error || 'Unknown error';
                                
                                // VERBOSE LOG: LLM failure details
                                logger.error('ToolbarManager', `=== LLM FAILURE: ${model.toUpperCase()} ===`, {
                                    timestamp: new Date().toISOString(),
                                    model: model,
                                    error: errorMessage,
                                    errorDetails: {
                                        hasError: !!data.error,
                                        errorType: data.error_type || 'unknown',
                                        errorCode: data.error_code || 'unknown',
                                        rawResponse: data
                                    },
                                    requestInfo: {
                                        prompt: prompt,
                                        diagram_type: diagramType,
                                        language: language
                                    },
                                    elapsed: elapsed + 's'
                                });
                                
                                this.llmResults[model] = {
                                    model: model,
                                    success: false,
                                    error: errorMessage,
                                    timestamp: Date.now()
                                };
                                
                                this.setLLMButtonState(model, 'error');
                                logger.warn('ToolbarManager', `${model} failed: ${errorMessage}`);
                            }
                            
                        } catch (e) {
                            logger.debug('ToolbarManager', 'Skipping malformed SSE line');
                        }
                    }
                }
                
            } catch (error) {
                // Handle abort gracefully (user cancelled or timeout)
                if (error.name === 'AbortError') {
                    logger.info('ToolbarManager', 'Multi-progressive request cancelled', {
                        reason: 'User cancelled or timeout',
                        activeControllers: this.activeAbortControllers.size
                    });
                    this.showNotification(this.getNotif('requestCancelled') || 'Request cancelled', 'info');
                    this.llmResults = {}; // Clear partial results
                    return; // Exit cleanly without fallback
                }
                
                // VERBOSE LOG: Parallel endpoint failure details
                logger.error('ToolbarManager', '=== PARALLEL ENDPOINT FAILED ===', {
                    timestamp: new Date().toISOString(),
                    error: error.message,
                    errorStack: error.stack,
                    endpoint: '/api/generate_multi_progressive',
                    requestBody: {
                        prompt: prompt,
                        diagram_type: diagramType,
                        models: models,
                        language: language
                    },
                    fallback: 'sequential generation'
                });
                
                logger.error('ToolbarManager', 'Parallel generation endpoint failed, falling back to sequential', error);
                
                // FALLBACK: If parallel endpoint fails, fall back to sequential (original code)
                for (const model of models) {
                // Check if diagram type changed during generation (session ID may change when spec updates)
                // We only check diagram type to allow spec updates from the first successful result
                if (this.editor.diagramType !== currentDiagramType) {
                    logger.warn('ToolbarManager', 'Auto-complete aborted - diagram type changed');
                    throw new Error('Diagram type changed during generation');
                }
                
                try {
                    const requestId = `${currentSessionId}_${model}_${Date.now()}`;
                    
                    // Call single LLM endpoint with model parameter
                    const modelRequestBody = {
                        ...baseRequestBody,
                        llm: model,  // Fixed: backend expects 'llm', not 'llm_model'
                        request_id: requestId
                    };
                    
                    // Create abort controller for timeout and cancellation
                    const abortController = new AbortController();
                    this.activeAbortControllers.set(model, abortController); // Track for cancellation
                    const timeoutId = setTimeout(() => abortController.abort(), LLM_CONFIG.TIMEOUT_MS);
                    
                    const response = await auth.fetch('/api/generate_graph', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(modelRequestBody),
                        signal: abortController.signal
                    });
                    
                    clearTimeout(timeoutId);
                    this.activeAbortControllers.delete(model); // Remove when complete
                    
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        throw new Error(data.error);
                    }
                    
                    logger.debug('ToolbarManager', `${model} received spec`, {
                        nodes: data.spec?.nodes?.length || 0
                    });
                    
                    // Normalize diagram type (backend returns "mind_map", frontend uses "mindmap")
                    let responseDiagramType = data.diagram_type || diagramType;
                    if (responseDiagramType === 'mind_map') {
                        responseDiagramType = 'mindmap';
                    }
                    
                    // Cache this model's result
                    this.llmResults[model] = {
                        model: model,
                        success: true,
                        result: {
                            spec: data.spec,
                            diagram_type: responseDiagramType,
                            topics: data.topics || [],
                            style_preferences: data.style_preferences || {}
                        }
                    };
                    
                    // Update button state for this model immediately
                    this.setLLMButtonState(model, 'ready');
                    
                    // Render first successful result
                    if (!firstSuccessfulModel) {
                        firstSuccessfulModel = model;
                        this.selectedLLM = model;
                        this.renderCachedLLMResult(model);
                        this.updateLLMButtonStates();
                    }
                    
                } catch (error) {
                    // Remove abortController from tracking when request fails
                    this.activeAbortControllers.delete(model);
                    
                    // Handle different error types
                    let errorMessage = error.message;
                    if (error.name === 'AbortError') {
                        errorMessage = `Timeout (>${LLM_CONFIG.TIMEOUT_MS/1000}s)`;
                        logger.warn('ToolbarManager', `${model} timed out`);
                    } else {
                        logger.error('ToolbarManager', `${model} failed`, error);
                    }
                    
                    // Cache error result with details
                    this.llmResults[model] = {
                        model: model,
                        success: false,
                        error: errorMessage,
                        timestamp: Date.now()
                    };
                    
                    // Update button to error state
                    this.setLLMButtonState(model, 'error');
                }
                }  // End of fallback sequential loop
            } finally {
                // CRITICAL: Clean up abort controller
                this.activeAbortControllers.delete('multi_progressive');
            }  // End of try-catch-finally for parallel vs sequential
            
            // Count successful results
            const successCount = Object.values(this.llmResults).filter(r => r.success).length;
            logger.info('ToolbarManager', `Auto-complete: ${successCount}/4 LLMs completed`);
            
            // VERBOSE LOG: Compare all LLM results for inconsistencies
            if (successCount > 1) {
                this._logLLMConsistencyAnalysis();
            }
            
            // Clear loading states
            this.setAllLLMButtonsLoading(false);
            this.updateLLMButtonStates();
            
            // Validate at least one model succeeded
            if (!firstSuccessfulModel || successCount === 0) {
                throw new Error('All LLMs failed to generate results');
            }
            
            // Success notification (firstSuccessfulModel already rendered in loop)
            const notifMessage = this.getNotif('multiLLMReady', 
                successCount, 
                LLM_CONFIG.MODELS.length, 
                LLM_CONFIG.MODEL_NAMES[firstSuccessfulModel]
            );
            this.showNotification(notifMessage, 'success');
            
            // Reset view to optimal position after rendering completes
            setTimeout(() => {
                this.editor.fitDiagramToWindow();
            }, LLM_CONFIG.RENDER_DELAY_MS);
            
        } catch (error) {
            // VERBOSE LOG: Complete auto-complete failure details
            logger.error('ToolbarManager', '=== AUTO-COMPLETE FATAL ERROR ===', {
                timestamp: new Date().toISOString(),
                error: error.message,
                errorStack: error.stack,
                errorName: error.name,
                context: {
                    diagramType: diagramType,
                    sessionId: this.editor?.sessionId,
                    existingNodesCount: existingNodes?.length || 0,
                    mainTopic: mainTopic || 'unknown',
                    language: language,
                    currentStep: this.isGeneratingMulti ? 'during_generation' : 'before_generation',
                    llmResultsCount: Object.keys(this.llmResults).length,
                    isAutoCompleting: this.isAutoCompleting,
                    isGeneratingMulti: this.isGeneratingMulti
                },
                browser: {
                    userAgent: navigator.userAgent,
                    language: navigator.language,
                    onLine: navigator.onLine,
                    viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight
                    }
                }
            });
            
            logger.error('ToolbarManager', 'Auto-complete error', error);
            this.showNotification(this.getNotif('autoCompleteFailed', error.message), 'error');
            this.setAllLLMButtonsLoading(false);
        } finally {
            // VERBOSE LOG: Auto-complete cleanup
            logger.debug('ToolbarManager', '=== AUTO-COMPLETE CLEANUP ===', {
                timestamp: new Date().toISOString(),
                flags: {
                    wasAutoCompleting: this.isAutoCompleting,
                    wasGeneratingMulti: this.isGeneratingMulti
                },
                results: {
                    totalCached: Object.keys(this.llmResults).length,
                    successful: Object.values(this.llmResults).filter(r => r.success).length,
                    failed: Object.values(this.llmResults).filter(r => !r.success).length
                }
            });
            
            this.setAutoButtonLoading(false);
            this.isAutoCompleting = false;
            this.isGeneratingMulti = false;
        }
    }
    
    /**
     * Validate LLM spec structure for inconsistencies
     */
    _validateLLMSpec(model, spec, expectedDiagramType) {
        const issues = [];
        const missingFields = [];
        const invalidFields = [];
        
        // Basic validation
        if (!spec || typeof spec !== 'object') {
            return {
                isValid: false,
                issues: ['Spec is not an object'],
                missingFields: [],
                invalidFields: ['spec']
            };
        }
        
        // Diagram-specific validation
        switch (expectedDiagramType) {
            case 'bubble_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.attributes || !Array.isArray(spec.attributes)) {
                    invalidFields.push('attributes');
                } else if (spec.attributes.length === 0) {
                    issues.push('Empty attributes array');
                }
                break;
                
            case 'circle_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.context || !Array.isArray(spec.context)) {
                    invalidFields.push('context');
                } else if (spec.context.length === 0) {
                    issues.push('Empty context array');
                }
                break;
                
            case 'mindmap':
            case 'mind_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.children || !Array.isArray(spec.children)) {
                    invalidFields.push('children');
                } else if (spec.children.length === 0) {
                    issues.push('Empty children array');
                }
                break;
                
            case 'tree_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.children || !Array.isArray(spec.children)) {
                    invalidFields.push('children');
                } else if (spec.children.length === 0) {
                    issues.push('Empty children array');
                }
                break;
                
            case 'brace_map':
                if (!spec.whole) missingFields.push('whole');
                if (!spec.parts || !Array.isArray(spec.parts)) {
                    invalidFields.push('parts');
                } else if (spec.parts.length === 0) {
                    issues.push('Empty parts array');
                }
                break;
                
            case 'bridge_map':
                if (!spec.analogies || !Array.isArray(spec.analogies)) {
                    invalidFields.push('analogies');
                } else if (spec.analogies.length === 0) {
                    issues.push('Empty analogies array');
                } else {
                    // Check each analogy has left and right
                    spec.analogies.forEach((analogy, i) => {
                        if (!analogy.left) missingFields.push(`analogies[${i}].left`);
                        if (!analogy.right) missingFields.push(`analogies[${i}].right`);
                    });
                }
                break;
                
            case 'double_bubble_map':
                if (!spec.left) missingFields.push('left');
                if (!spec.right) missingFields.push('right');
                if (!spec.similarities || !Array.isArray(spec.similarities)) {
                    invalidFields.push('similarities');
                }
                if (!spec.left_differences || !Array.isArray(spec.left_differences)) {
                    invalidFields.push('left_differences');
                }
                if (!spec.right_differences || !Array.isArray(spec.right_differences)) {
                    invalidFields.push('right_differences');
                }
                break;
                
            case 'flow_map':
                if (!spec.title) missingFields.push('title');
                if (!spec.steps || !Array.isArray(spec.steps)) {
                    invalidFields.push('steps');
                } else if (spec.steps.length === 0) {
                    issues.push('Empty steps array');
                }
                break;
                
            case 'multi_flow_map':
                if (!spec.event) missingFields.push('event');
                if (!spec.causes || !Array.isArray(spec.causes)) {
                    invalidFields.push('causes');
                }
                if (!spec.effects || !Array.isArray(spec.effects)) {
                    invalidFields.push('effects');
                }
                break;
                
            case 'concept_map':
                if (!spec.nodes || !Array.isArray(spec.nodes)) {
                    invalidFields.push('nodes');
                } else if (spec.nodes.length === 0) {
                    issues.push('Empty nodes array');
                }
                if (!spec.connections || !Array.isArray(spec.connections)) {
                    invalidFields.push('connections');
                }
                break;
        }
        
        const isValid = missingFields.length === 0 && invalidFields.length === 0 && issues.length === 0;
        
        return {
            isValid: isValid,
            issues: issues,
            missingFields: missingFields,
            invalidFields: invalidFields
        };
    }
    
    /**
     * Log consistency analysis comparing all LLM results
     */
    _logLLMConsistencyAnalysis() {
        const successful = Object.entries(this.llmResults)
            .filter(([_, result]) => result.success)
            .map(([model, result]) => ({ model, ...result }));
        
        if (successful.length < 2) return;
        
        logger.info('ToolbarManager', '=== LLM CONSISTENCY ANALYSIS ===', {
            timestamp: new Date().toISOString(),
            totalModels: successful.length,
            models: successful.map(r => r.model)
        });
        
        // Compare specs
        const specComparison = {
            models: successful.map(r => r.model),
            specs: {}
        };
        
        successful.forEach(({ model, result, validation }) => {
            const spec = result.spec;
            specComparison.specs[model] = {
                diagram_type: result.diagram_type,
                spec_keys: spec ? Object.keys(spec) : [],
                validation: validation,
                structure: {}
            };
            
            // Extract key structural info
            if (spec) {
                if (spec.topic) specComparison.specs[model].structure.topic = spec.topic;
                if (spec.children) specComparison.specs[model].structure.childrenCount = spec.children.length;
                if (spec.nodes) specComparison.specs[model].structure.nodesCount = spec.nodes.length;
                if (spec.categories) specComparison.specs[model].structure.categoriesCount = spec.categories.length;
                if (spec.parts) specComparison.specs[model].structure.partsCount = spec.parts.length;
                if (spec.analogies) specComparison.specs[model].structure.analogiesCount = spec.analogies.length;
                if (spec.steps) specComparison.specs[model].structure.stepsCount = spec.steps.length;
            }
        });
        
        logger.info('ToolbarManager', 'Spec comparison across models:', specComparison);
        
        // Identify inconsistencies
        const inconsistencies = [];
        
        // Check if all have same number of children/nodes
        const childCounts = successful
            .map(r => r.result.spec?.children?.length || r.result.spec?.nodes?.length || 0)
            .filter(c => c > 0);
        
        if (childCounts.length > 1) {
            const min = Math.min(...childCounts);
            const max = Math.max(...childCounts);
            if (max - min > 2) {
                inconsistencies.push({
                    type: 'content_count_variance',
                    message: `Large variance in content count: ${min} to ${max}`,
                    models: successful.map((r, i) => ({
                        model: r.model,
                        count: childCounts[i]
                    }))
                });
            }
        }
        
        // Check for validation failures
        const validationIssues = successful.filter(r => r.validation && !r.validation.isValid);
        if (validationIssues.length > 0) {
            inconsistencies.push({
                type: 'validation_failures',
                message: `${validationIssues.length} model(s) have validation issues`,
                models: validationIssues.map(r => ({
                    model: r.model,
                    issues: r.validation.issues,
                    missingFields: r.validation.missingFields,
                    invalidFields: r.validation.invalidFields
                }))
            });
        }
        
        // Log inconsistencies
        if (inconsistencies.length > 0) {
            logger.warn('ToolbarManager', '⚠️ LLM INCONSISTENCIES DETECTED', {
                timestamp: new Date().toISOString(),
                inconsistencyCount: inconsistencies.length,
                inconsistencies: inconsistencies
            });
        } else {
            logger.info('ToolbarManager', '✓ All LLM results are consistent', {
                timestamp: new Date().toISOString(),
                modelsCompared: successful.length
            });
        }
    }
    
    /**
     * Set loading state for all LLM buttons
     */
    setAllLLMButtonsLoading(isLoading) {
        this.llmButtons.forEach(btn => {
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
     */
    setLLMButtonState(model, state) {
        this.llmButtons.forEach(btn => {
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
     * Identify the main topic from existing nodes
     * Uses diagram-specific structure first, then falls back to heuristics
     */
    identifyMainTopic(nodes) {
        logger.info('ToolbarManager', '=== IDENTIFYING MAIN TOPIC ===', {
            timestamp: new Date().toISOString(),
            nodeCount: nodes.length,
            diagramType: this.editor?.diagramType,
            hasSpec: !!this.editor?.currentSpec
        });
        
        if (nodes.length === 0) {
            logger.warn('ToolbarManager', 'No nodes provided, returning empty string');
            return '';
        }
        
        if (nodes.length === 1) {
            logger.info('ToolbarManager', `Single node detected: "${nodes[0].text}"`);
            return nodes[0].text;
        }
        
        const diagramType = this.editor.diagramType;
        const spec = this.editor.currentSpec;
        
        // Strategy 1: For diagrams with topic field, prioritize spec (source of truth)
        // The spec is updated by updateNodeText when user edits the topic
        if (diagramType === 'bubble_map' || diagramType === 'circle_map' || 
            diagramType === 'tree_map') {
            
            logger.info('ToolbarManager', `Strategy 1: Diagram type "${diagramType}" - checking spec.topic`);
            
            // Check spec first (updated by updateNodeText)
            if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
                logger.info('ToolbarManager', `✓ Main topic from spec.topic: "${spec.topic}"`);
                return spec.topic;
            }
            
            // Fallback: Check DOM if spec is not available
            // CRITICAL: Circle map uses 'center', not 'topic'!
            const topicNode = nodes.find(node => 
                node.nodeType === 'topic' || node.nodeType === 'center'
            );
            if (topicNode && topicNode.text && !this.validator.isPlaceholderText(topicNode.text)) {
                logger.info('ToolbarManager', `✓ Main topic from DOM node (type: ${topicNode.nodeType}): "${topicNode.text}"`);
                return topicNode.text;
            }
            
            logger.debug('ToolbarManager', 'Strategy 1 failed, continuing to next strategy');
        }
        
        // Strategy 1e: For Brace Map, check spec.whole (not spec.topic!)
        if (diagramType === 'brace_map') {
            logger.info('ToolbarManager', 'Strategy 1e: Brace map - checking spec.whole');
            
            // Check spec first (updated by updateNodeText)
            if (spec && spec.whole && !this.validator.isPlaceholderText(spec.whole)) {
                logger.info('ToolbarManager', `✓ Main topic from spec.whole: "${spec.whole}"`);
                return spec.whole;
            }
            
            // Fallback: Check DOM if spec is not available
            const wholeNode = nodes.find(node => node.nodeType === 'topic');
            if (wholeNode && wholeNode.text && !this.validator.isPlaceholderText(wholeNode.text)) {
                logger.info('ToolbarManager', `✓ Main topic from DOM node (whole): "${wholeNode.text}"`);
                return wholeNode.text;
            }
            
            logger.debug('ToolbarManager', 'Strategy 1e failed, continuing to next strategy');
        }
        
        // Strategy 1-flow: For Flow Map, check spec.title (NOT spec.topic)
        // Flow Map uses 'title' field, similar to how Circle Map uses 'center' nodeType
        if (diagramType === 'flow_map') {
            // Check spec first (updated by updateFlowMapText)
            if (spec && spec.title && !this.validator.isPlaceholderText(spec.title)) {
                return spec.title;
            }
            // Fallback: Check DOM if spec is not available
            const titleNode = nodes.find(node => node.nodeType === 'title');
            if (titleNode && titleNode.text && !this.validator.isPlaceholderText(titleNode.text)) {
                return titleNode.text;
            }
        }
        
        // Strategy 1-multiflow: For Multi-Flow Map, check spec.event (NOT spec.topic)
        // Multi-Flow Map uses 'event' field for the central event
        if (diagramType === 'multi_flow_map') {
            // Check spec first (updated by updateMultiFlowMapText)
            if (spec && spec.event && !this.validator.isPlaceholderText(spec.event)) {
                return spec.event;
            }
            // Fallback: Check DOM if spec is not available
            const eventNode = nodes.find(node => node.nodeType === 'event');
            if (eventNode && eventNode.text && !this.validator.isPlaceholderText(eventNode.text)) {
                return eventNode.text;
            }
        }
        
        // Strategy 1b: For double bubble maps, ALWAYS read from currentSpec first
        // CONSISTENCY FIX: Like bridge_map, use spec as source of truth
        if (diagramType === 'double_bubble_map') {
            logger.info('ToolbarManager', 'Strategy 1b: Double bubble map - checking spec.left and spec.right');
            
            if (spec && spec.left && spec.right) {
                const combinedTopic = `${spec.left} vs ${spec.right}`;
                logger.info('ToolbarManager', `✓ Main topic from spec: "${combinedTopic}"`, {
                    left: spec.left,
                    right: spec.right
                });
                return combinedTopic;
            }
            logger.warn('ToolbarManager', 'Double bubble map: No valid left/right topics in spec');
        }
        
        // Strategy 1c: For bridge maps, ALWAYS read from currentSpec
        // ROOT CAUSE FIX: DOM node array order ≠ pair index order
        // currentSpec.analogies[0] is the source of truth (updated by updateBridgeMapText)
        if (diagramType === 'bridge_map') {
            logger.info('ToolbarManager', 'Strategy 1c: Bridge map - checking spec.analogies[0]');
            
            if (spec && spec.analogies && spec.analogies.length > 0) {
                const firstPair = spec.analogies[0];
                if (firstPair.left && firstPair.right) {
                    const mainTopic = `${firstPair.left}/${firstPair.right}`;
                    logger.info('ToolbarManager', `✓ Main topic from spec.analogies[0]: "${mainTopic}"`, {
                        left: firstPair.left,
                        right: firstPair.right,
                        relatingFactor: spec.relatingFactor || 'not set'
                    });
                    return mainTopic;
                }
            }
            logger.warn('ToolbarManager', 'Bridge map: No valid analogies in spec');
        }
        
        // Strategy 1d: For MindMap, prioritize spec first
        // CONSISTENCY FIX: Read from spec before geometric detection
        if (diagramType === 'mindmap') {
            logger.info('ToolbarManager', 'Strategy 1d: MindMap - checking spec.topic');
            
            // First, try to get from spec (source of truth)
            if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
                logger.info('ToolbarManager', `✓ Main topic from spec.topic: "${spec.topic}"`);
                return spec.topic;
            }
            
            logger.debug('ToolbarManager', 'Spec topic not available, falling back to geometric center detection');
            
            // Fallback: Find the node closest to center by position
            const svg = d3.select('#d3-container svg');
            if (!svg.empty()) {
                const width = parseFloat(svg.attr('width')) || 800;
                const height = parseFloat(svg.attr('height')) || 600;
                const centerX = width / 2;
                const centerY = height / 2;
                
                // Find the node closest to center
                let centralNode = nodes[0];
                let minDistance = Infinity;
                
                nodes.forEach(node => {
                    const distance = Math.sqrt(
                        Math.pow(node.x - centerX, 2) + 
                        Math.pow(node.y - centerY, 2)
                    );
                    
                    if (distance < minDistance) {
                        minDistance = distance;
                        centralNode = node;
                    }
                });
                
                // Return the text from the central node (skip if placeholder)
                if (centralNode && centralNode.text && !this.validator.isPlaceholderText(centralNode.text)) {
                    return centralNode.text;
                }
            }
        }
        
        // Strategy 2: Use diagram-specific structure from spec (fallback)
        if (spec) {
            let mainTopic = null;
            
            switch (diagramType) {
                case 'bubble_map':
                    // For bubble map, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'circle_map':
                    // For circle map, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'tree_map':
                case 'mindmap':
                    // For tree/mind maps, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'brace_map':
                    // For brace map, the main topic is spec.whole (skip placeholders)
                    mainTopic = spec.whole && !this.validator.isPlaceholderText(spec.whole) ? spec.whole : null;
                    break;
                    
                case 'double_bubble_map':
                    // For double bubble map, use the left topic as primary (skip placeholders)
                    const leftTopic = spec.left && !this.validator.isPlaceholderText(spec.left) ? spec.left : null;
                    const rightTopic = spec.right && !this.validator.isPlaceholderText(spec.right) ? spec.right : null;
                    mainTopic = leftTopic || rightTopic;
                    break;
                    
                case 'multi_flow_map':
                    // For multi-flow map, the main topic is spec.event (skip placeholders)
                    mainTopic = spec.event && !this.validator.isPlaceholderText(spec.event) ? spec.event : null;
                    break;
                    
                case 'flow_map':
                    // For flow map, use the title or first step (skip placeholders)
                    const title = spec.title && !this.validator.isPlaceholderText(spec.title) ? spec.title : null;
                    const firstStep = spec.steps && spec.steps[0] && !this.validator.isPlaceholderText(spec.steps[0]) ? spec.steps[0] : null;
                    mainTopic = title || firstStep;
                    break;
                    
                case 'concept_map':
                    // For concept map, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'bridge_map':
                    // For bridge map, extract from actual SVG nodes (Strategy 1c above)
                    // This fallback uses spec only if node extraction failed
                    if (spec.analogies && spec.analogies.length > 0) {
                        const firstPair = spec.analogies[0];
                        const leftItem = firstPair.left && !this.validator.isPlaceholderText(firstPair.left) ? firstPair.left : null;
                        const rightItem = firstPair.right && !this.validator.isPlaceholderText(firstPair.right) ? firstPair.right : null;
                        if (leftItem && rightItem) {
                            mainTopic = `${leftItem}/${rightItem}`;
                        }
                    }
                    break;
            }
            
            if (mainTopic) {
                return mainTopic;
            }
        }
        
        // Strategy 2: Find node closest to center of canvas (geometric fallback)
        const svg = d3.select('#d3-container svg');
        if (!svg.empty()) {
            const width = parseFloat(svg.attr('width')) || 800;
            const height = parseFloat(svg.attr('height')) || 600;
            const centerX = width / 2;
            const centerY = height / 2;
            
            // Calculate distance from center for each node (skip placeholders)
            let closestNode = null;
            let minDistance = Infinity;
            
            nodes.forEach(node => {
                if (!this.validator.isPlaceholderText(node.text)) {
                    const distance = Math.sqrt(
                        Math.pow(node.x - centerX, 2) + 
                        Math.pow(node.y - centerY, 2)
                    );
                    
                    if (distance < minDistance) {
                        minDistance = distance;
                        closestNode = node;
                    }
                }
            });
            
            if (closestNode) {
                return closestNode.text;
            }
        }
        
        // Strategy 3: Fallback - find first meaningful node (skip placeholders)
        const meaningfulNode = nodes.find(n => 
            n.text && 
            n.text.trim().length > 1 && 
            !this.validator.isPlaceholderText(n.text)
        );
        
        // Last resort: return first node's text (even if placeholder - user needs to edit it)
        return meaningfulNode ? meaningfulNode.text : (nodes[0]?.text || '');
    }
    
    /**
     * Extract existing nodes from the current diagram
     */
    extractExistingNodes() {
        logger.info('ToolbarManager', '=== EXTRACTING EXISTING NODES ===', {
            timestamp: new Date().toISOString(),
            diagramType: this.editor?.diagramType
        });
        
        const nodes = [];
        let skippedPlaceholders = 0;
        let skippedEmpty = 0;
        
        // Define placeholder/template text patterns to skip
        const placeholderPatterns = [
            /^New Node$/i,
            /^New (Left|Right|Item|Concept|Step|Substep|Category|Child|Part|Subpart|Cause|Effect|Attribute|Context|Branch)$/i,
            /^Item [A-Z0-9]+$/i,  // Item 1, Item A, Item B, etc.
            /^Item \d+$/i,        // Item 1, Item 2, Item 3, etc.
            /^Branch\s*\d+$/i,    // Branch 1, Branch 2, Branch 3, Branch 4, etc.
            /^as$/i,              // Bridge map relating factor default
            /^Main Topic$/i,
            /^Central Topic$/i,   // Central topic placeholder
            /^Topic [A-Z]?$/i,
            /^主题$/,
            /^中心主题$/,          // Chinese "Central Topic"
            /^新节点$/,
            /^新分支$/,            // Chinese "New Branch"
            /^分支\d+$/,           // Chinese "Branch 1", "Branch 2", etc.
            /^项目[A-Z0-9]+$/
        ];
        
        // Find all text elements in the SVG
        d3.selectAll('#d3-container text').each(function() {
            const textElement = d3.select(this);
            const text = textElement.text().trim();
            
            // Skip empty or placeholder text
            if (!text || text.length === 0) {
                skippedEmpty++;
                return;
            }
            
            // Check if this is placeholder text
            const isPlaceholder = placeholderPatterns.some(pattern => pattern.test(text));
            if (isPlaceholder) {
                skippedPlaceholders++;
                logger.debug('ToolbarManager', `Skipping placeholder node: "${text}"`);
                return;
            }
            
            const x = parseFloat(textElement.attr('x')) || 0;
            const y = parseFloat(textElement.attr('y')) || 0;
            
            // Capture data-node-type and data-node-id from the text element itself
            // (these attributes help identify the central topic vs. children/branches)
            const nodeType = textElement.attr('data-node-type') || '';
            const nodeId = textElement.attr('data-node-id') || '';
            
            const nodeData = {
                text: text,
                x: x,
                y: y,
                nodeType: nodeType,
                nodeId: nodeId
            };
            
            nodes.push(nodeData);
            
            // VERBOSE LOG: Each node extracted
            logger.info('ToolbarManager', `✓ Node extracted: "${text}"`, {
                index: nodes.length,
                nodeType: nodeType || 'unknown',
                nodeId: nodeId || 'unknown',
                position: { x, y },
                textLength: text.length
            });
        });
        
        // VERBOSE LOG: Summary of extraction
        logger.info('ToolbarManager', '=== NODE EXTRACTION COMPLETE ===', {
            totalNodesExtracted: nodes.length,
            skippedEmpty: skippedEmpty,
            skippedPlaceholders: skippedPlaceholders,
            extractedNodes: nodes.map((n, i) => ({
                index: i + 1,
                text: n.text.substring(0, 50) + (n.text.length > 50 ? '...' : ''),
                type: n.nodeType || 'unknown',
                position: { x: Math.round(n.x), y: Math.round(n.y) }
            }))
        });
        
        return nodes;
    }
    
    /**
     * Toggle line mode (black and white, no fill)
     */
    toggleLineMode() {
        this.isLineMode = !this.isLineMode;
        
        // Toggle button active state
        if (this.isLineMode) {
            this.lineModeBtn.classList.add('active');
        } else {
            this.lineModeBtn.classList.remove('active');
        }
        
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            logger.warn('ToolbarManager', 'No SVG found in container');
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
            
            this.showNotification(this.getNotif('lineModeEnabled'), 'success');
            
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
            
            this.showNotification(this.getNotif('lineModeDisabled'), 'success');
        }
    }
    
    /**
     * Set loading state for auto button
     */
    setAutoButtonLoading(isLoading) {
        if (!this.autoCompleteBtn) return;
        
        if (isLoading) {
            this.autoCompleteBtn.classList.add('loading');
            this.autoCompleteBtn.disabled = true;
        } else {
            this.autoCompleteBtn.classList.remove('loading');
            this.autoCompleteBtn.disabled = false;
        }
    }
    
    /**
     * Handle duplicate node
     */
    handleDuplicateNode() {
        this.showNotification(this.getNotif('duplicateComingSoon'));
    }
    
    /**
     * Handle undo
     */
    handleUndo() {
        if (this.editor) {
            this.editor.undo();
        }
    }
    
    /**
     * Handle redo
     */
    handleRedo() {
        if (this.editor) {
            this.editor.redo();
        }
    }
    
    /**
     * Reset canvas to blank template
     */
    handleReset() {
        if (!this.editor) return;
        
        // Confirm with user - language-aware message
        const confirmMessage = this.getNotif('resetConfirm');
        const confirmed = confirm(confirmMessage);
        if (!confirmed) return;
        
        // Get the diagram selector to retrieve blank template
        const diagramSelector = window.diagramSelector;
        if (!diagramSelector) {
            logger.error('ToolbarManager', 'Diagram selector not available');
            this.showNotification(this.getNotif('resetFailed'), 'error');
            return;
        }
        
        // Get blank template for current diagram type
        const blankTemplate = diagramSelector.getTemplate(this.editor.diagramType);
        if (!blankTemplate) {
            logger.error('ToolbarManager', `Failed to get blank template for: ${this.editor.diagramType}`);
            this.showNotification(this.getNotif('templateNotFound'), 'error');
            return;
        }
        
        // Reset the spec and re-render
        this.editor.currentSpec = blankTemplate;
        this.editor.renderDiagram();
        
        // Clear history
        if (this.editor.history) {
            this.editor.history = [JSON.parse(JSON.stringify(blankTemplate))];
            this.editor.historyIndex = 0;
        }
        
        // Clear selection
        if (this.editor.selectionManager) {
            this.editor.selectionManager.clearSelection();
        }
        
        this.showNotification(this.getNotif('canvasReset'), 'success');
    }
    
    /**
     * Handle export - Export diagram as PNG (DingTalk quality - 3x)
     */
    handleExport() {
        const svg = document.querySelector('#d3-container svg');
        if (!svg) {
            this.showNotification(this.getNotif('noDiagramToExport'), 'error');
            return;
        }
        
        // Fit diagram for export (ensures full diagram is captured, not just visible area)
        if (this.editor && typeof this.editor.fitDiagramForExport === 'function') {
            this.editor.fitDiagramForExport();
            
            // Wait briefly for viewBox update (no transition, so shorter delay)
            setTimeout(() => {
                this.performPNGExport();
            }, 100);
        } else {
            // Fallback if editor not available or method not found - export immediately
            logger.warn('ToolbarManager', 'fitDiagramForExport not available, exporting with current view');
            this.performPNGExport();
        }
    }
    
    /**
     * Perform the actual PNG export after view reset (if needed)
     * Filename format: {diagram_type}_{llm_model}_{timestamp}.png
     * Example: bubble_map_qwen_2025-10-07T12-30-45.png
     */
    performPNGExport() {
        const svg = document.querySelector('#d3-container svg');
        if (!svg) {
            this.showNotification(this.getNotif('noDiagramToExport'), 'error');
            return;
        }
        
        try {
            // Clone SVG for export (preserve original)
            const svgClone = svg.cloneNode(true);
            
            // CRITICAL FIX: Use viewBox dimensions for accurate export
            // viewBox defines the actual coordinate system, not width/height attributes
            const viewBox = svgClone.getAttribute('viewBox');
            let width, height, viewBoxX = 0, viewBoxY = 0;
            
            if (viewBox) {
                // Use viewBox dimensions (the actual content coordinate system)
                // viewBox format: "minX minY width height"
                const viewBoxParts = viewBox.split(' ').map(Number);
                viewBoxX = viewBoxParts[0];
                viewBoxY = viewBoxParts[1];
                width = viewBoxParts[2];
                height = viewBoxParts[3];
            } else {
                // Fallback to getBoundingClientRect for actual displayed size
                const rect = svg.getBoundingClientRect();
                width = rect.width;
                height = rect.height;
            }
            
            // Calculate watermark position (bottom-right corner in viewBox coordinates)
            const svgD3 = d3.select(svgClone);
            const watermarkFontSize = Math.max(12, Math.min(20, Math.min(width, height) * 0.025));
            const wmPadding = Math.max(10, Math.min(20, Math.min(width, height) * 0.02));
            const watermarkX = viewBoxX + width - wmPadding;
            const watermarkY = viewBoxY + height - wmPadding;
            
            // Add watermark to clone
            svgD3.append('text')
                .attr('x', watermarkX)
                .attr('y', watermarkY)
                .attr('text-anchor', 'end')
                .attr('dominant-baseline', 'alphabetic')
                .attr('fill', '#2c3e50')
                .attr('font-size', watermarkFontSize)
                .attr('font-family', 'Inter, Segoe UI, sans-serif')
                .attr('font-weight', '600')
                .attr('opacity', 0.8)
                .text('MindGraph');
            
            // Use DingTalk quality (3x scale for Retina displays)
            const scale = 3;
            
            // Create high-quality canvas
            const canvas = document.createElement('canvas');
            canvas.width = width * scale;
            canvas.height = height * scale;
            const ctx = canvas.getContext('2d');
            
            ctx.scale(scale, scale);
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            
            // Fill white background
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, width, height);
            
            // Convert SVG to PNG
            const svgData = new XMLSerializer().serializeToString(svgClone);
            const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(svgBlob);
            
            const img = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob((blob) => {
                    const pngUrl = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = pngUrl;
                    
                    // Generate filename with diagram type and LLM model
                    const diagramType = this.editor.diagramType || 'diagram';
                    const llmModel = this.selectedLLM || 'qwen';
                    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                    link.download = `${diagramType}_${llmModel}_${timestamp}.png`;
                    
                    link.click();
                    
                    URL.revokeObjectURL(pngUrl);
                    URL.revokeObjectURL(url);
                    
                    this.showNotification(this.getNotif('diagramExported'), 'success');
                }, 'image/png');
            };
            
            img.onerror = (error) => {
                logger.error('ToolbarManager', 'Error loading SVG', error);
                URL.revokeObjectURL(url);
                this.showNotification(this.getNotif('exportFailed'), 'error');
            };
            
            img.src = url;
            
        } catch (error) {
            logger.error('ToolbarManager', 'Error exporting diagram', error);
            this.showNotification(this.getNotif('exportFailed'), 'error');
        }
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
     * Show notification using centralized notification manager
     */
    showNotification(message, type = 'info') {
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        } else {
            logger.error('ToolbarManager', 'NotificationManager not available');
        }
    }
    
    /**
     * Play notification sound when first diagram is rendered
     */
    playNotificationSound() {
        try {
            // Create audio context for a pleasant "ding" sound
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            // Connect nodes
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Configure pleasant notification sound (two-tone ding)
            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime); // First tone (higher)
            oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1); // Second tone (lower)
            
            // Quick fade out for smooth sound
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
            
            // Play
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.3);
            
            logger.debug('ToolbarManager', 'Notification sound played');
        } catch (error) {
            // Silently fail if audio is not supported or blocked
            logger.debug('ToolbarManager', 'Could not play notification sound', error);
        }
    }
    
    /**
     * Set up automatic node counter using MutationObserver
     * Watches the SVG container and updates count whenever it changes
     */
    setupNodeCounterObserver() {
        const container = document.getElementById('d3-container');
        if (!container) {
            logger.warn('ToolbarManager', 'd3-container not found for node counter observer');
            return;
        }
        
        // Create a MutationObserver to watch for DOM changes in the SVG
        // Use minimal configuration for better performance
        this.nodeCountObserver = new MutationObserver((mutations) => {
            // Debounce updates to avoid excessive calls
            if (this.nodeCountUpdateTimeout) {
                clearTimeout(this.nodeCountUpdateTimeout);
            }
            this.nodeCountUpdateTimeout = setTimeout(() => {
                this.updateNodeCount();
                this.validateLearningMode(); // Also validate diagram for Learning Mode
            }, 100); // Update after 100ms of no changes
        });
        
        // Start observing - only watch for added/removed children
        // This is the most efficient way and catches all diagram updates
        this.nodeCountObserver.observe(container, {
            childList: true,      // Watch for added/removed children
            subtree: true         // Watch all descendants
            // No attributes watching - not needed, saves resources
        });
        
        logger.debug('ToolbarManager', 'Node counter observer set up');
        
        // Initial count and validation with longer delay to ensure SVG is fully rendered
        setTimeout(() => {
            this.updateNodeCount();
            this.validateLearningMode();
        }, 500);
    }
    
    /**
     * Update node count in status bar
     */
    updateNodeCount() {
        if (!this.nodeCountElement) {
            logger.warn('ToolbarManager', 'Node count element not found');
            return;
        }
        
        // Count all text elements in the SVG
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            const label = window.languageManager?.translate('nodeCount') || 'Nodes';
            this.nodeCountElement.textContent = `${label}: 0`;
            return;
        }
        
        // Count all text elements that have data-node-id (all actual diagram nodes)
        let count = 0;
        const nodeIds = [];
        
        svg.selectAll('text').each(function() {
            const element = d3.select(this);
            const nodeId = element.attr('data-node-id');
            
            // Count any text element with a node-id
            if (nodeId) {
                count++;
                nodeIds.push(nodeId);
            }
        });
        
        // Update the display
        const label = window.languageManager?.translate('nodeCount') || 'Nodes';
        this.nodeCountElement.textContent = `${label}: ${count}`;
    }
    
    /**
     * Validate that this toolbar manager is still valid for the current session
     */
    validateToolbarSession(operation = 'Operation') {
        // Check if we have a session ID
        if (!this.sessionId) {
            logger.warn('ToolbarManager', `${operation} - No session ID set`);
            return false;
        }
        
        // Check if the editor's session matches our session
        if (this.editor && this.editor.sessionId !== this.sessionId) {
            logger.warn('ToolbarManager', `${operation} blocked - Session mismatch`, {
                toolbarSession: this.sessionId?.substr(-8),
                editorSession: this.editor.sessionId?.substr(-8)
            });
            return false;
        }
        
        // Check with DiagramSelector's session
        if (window.diagramSelector?.currentSession) {
            if (window.diagramSelector.currentSession.id !== this.sessionId) {
                logger.warn('ToolbarManager', `${operation} blocked - DiagramSelector session mismatch`, {
                    toolbarSession: this.sessionId?.substr(-8),
                    activeSession: window.diagramSelector.currentSession.id?.substr(-8)
                });
                return false;
            }
        }
        
        return true;
    }
    
    /**
     * 🧠 Validate diagram for Learning Mode and enable/disable button
     */
    validateLearningMode() {
        if (!this.validator || !this.learningBtn) {
            return;
        }
        
        const result = this.validator.validateAndUpdateButton(this.learningBtn, this.diagramType);
        
        // Store validation result for later use
        this.lastValidationResult = result;
        
        return result;
    }
    
    /**
     * 🆕 Handle Learning Mode button click
     */
    async handleLearningMode() {
        logger.info('ToolbarManager', 'Learning Mode initiated');
        
        // Validate diagram first
        const validationResult = this.validateLearningMode();
        
        if (!validationResult || !validationResult.isValid) {
            // Show validation error message
            const lang = window.languageManager;
            const currentLang = lang?.currentLanguage || 'en';
            const message = this.validator.getValidationMessage(validationResult, currentLang);
            
            this.showNotification(message, 'error');
            logger.warn('ToolbarManager', 'Learning Mode validation failed', {
                reason: validationResult.reason
            });
            return;
        }
        
        // Validation passed - Enter Learning Mode!
        logger.info('ToolbarManager', 'Diagram validation passed');
        
        try {
            // Initialize LearningModeManager if not already done
            if (!this.learningModeManager) {
                this.learningModeManager = new LearningModeManager(this, this.editor);
            }
            
            // Start Learning Mode
            await this.learningModeManager.startLearningMode(validationResult);
            
            logger.info('ToolbarManager', 'Learning Mode started successfully');
            
        } catch (error) {
            logger.error('ToolbarManager', 'Failed to start Learning Mode', error);
            this.showNotification(
                'Failed to start Learning Mode. Please try again.',
                'error'
            );
        }
    }
    
    /**
     * Handle Thinking Mode (ThinkGuide) button click
     */
    async handleThinkingMode() {
        logger.info('ToolbarManager', 'ThinkGuide Mode initiated - BUTTON CLICKED');
        
        // Check if panel is already open - toggle behavior like MindMate
        const thinkPanel = document.getElementById('thinking-panel');
        const isPanelOpen = thinkPanel && !thinkPanel.classList.contains('collapsed');
        
        logger.info('ToolbarManager', 'Initial panel state:', {
            thinkPanelCollapsed: thinkPanel?.classList.contains('collapsed'),
            isPanelOpen: isPanelOpen,
            currentPanel: window.panelManager?.getCurrentPanel()
        });
        
        // If panel is already open, close it (toggle behavior)
        if (isPanelOpen) {
            logger.info('ToolbarManager', 'ThinkGuide panel already open - closing it');
            if (window.panelManager) {
                window.panelManager.closeThinkGuidePanel();
                logger.info('ToolbarManager', 'ThinkGuide panel closed');
            }
            return;
        }
        
        // Check if diagram type is supported by ThinkGuide BEFORE opening panel
        const diagramType = this.editor.diagramType;
        const supportedTypes = [
            'circle_map',
            'bubble_map', 
            'double_bubble_map',
            'tree_map',
            'flow_map',
            'multi_flow_map',
            'brace_map',
            'bridge_map',
            'mindmap'
        ];
        
        if (!supportedTypes.includes(diagramType)) {
            logger.warn('ToolbarManager', `ThinkGuide not yet implemented for ${diagramType}`);
            
            // Show friendly message - only concept_map is unsupported now
            const diagramNames = {
                'concept_map': 'Concept Map'
            };
            const diagramDisplayName = diagramNames[diagramType] || diagramType;
            
            const message = this.validator.language === 'zh'
                ? `ThinkGuide 暂不支持 ${diagramDisplayName}，敬请期待！`
                : `ThinkGuide is not yet available for ${diagramDisplayName}. Coming soon!`;
            
            alert(message);
            return;
        }
        
        // Panel is closed and diagram is supported, open it
        logger.info('ToolbarManager', 'Opening ThinkGuide (diagram type supported)');
        
        try {
            // DIAGNOSTIC: Log everything about the editor state
            logger.info('ToolbarManager', 'ThinkGuide clicked - Diagnostic Info:', {
                hasThisEditor: !!this.editor,
                hasWindowEditor: !!window.currentEditor,
                editorsMatch: this.editor === window.currentEditor,
                thisEditorType: this.editor?.diagramType,
                thisEditorSpec: !!this.editor?.currentSpec,
                thisEditorSpecKeys: this.editor?.currentSpec ? Object.keys(this.editor.currentSpec) : [],
                windowEditorType: window.currentEditor?.diagramType,
                windowEditorSpec: !!window.currentEditor?.currentSpec,
                sessionId: this.sessionId?.substr(-8)
            });
            
            // Use global thinkingModeManager instance
            if (!window.thinkingModeManager) {
                const errorMsg = 'ThinkGuide not initialized. Please reload the page.';
                logger.error('ToolbarManager', errorMsg);
                this.showNotification(errorMsg, 'error');
                return;
            }
            
            // Check if we have a valid editor with data
            if (!this.editor) {
                logger.error('ToolbarManager', 'CRITICAL: this.editor is null!', {
                    sessionId: this.sessionId,
                    windowEditor: !!window.currentEditor,
                    registrySize: window.toolbarManagerRegistry?.size,
                    registryKeys: Array.from(window.toolbarManagerRegistry?.keys() || [])
                });
                throw new Error('ToolbarManager has no editor reference');
            }
            
            if (!this.editor.currentSpec) {
                logger.error('ToolbarManager', 'this.editor.currentSpec is undefined!', {
                    editorType: this.editor.diagramType,
                    editorKeys: Object.keys(this.editor),
                    hasHistory: !!this.editor.history,
                    historyLength: this.editor.history?.length
                });
                throw new Error('No diagram data found in editor.currentSpec');
            }
            
            // Get current diagram data - normalize it to ThinkGuide format
            const diagramType = this.editor.diagramType || 'circle_map';
            const rawSpec = this.editor.currentSpec;
            
            // Normalize diagram data to standard format
            const diagramData = window.thinkingModeManager.normalizeDiagramData(rawSpec, diagramType);
            
            // Extract center topic based on diagram type for logging
            let centerTopic;
            if (['tree_map', 'mindmap'].includes(diagramType)) {
                centerTopic = diagramData.topic;
            } else if (diagramType === 'flow_map') {
                centerTopic = diagramData.title;
            } else if (diagramType === 'brace_map') {
                centerTopic = diagramData.whole;
            } else if (diagramType === 'double_bubble_map') {
                centerTopic = { left: diagramData.left, right: diagramData.right };
            } else if (diagramType === 'multi_flow_map') {
                centerTopic = diagramData.event;
            } else if (diagramType === 'bridge_map') {
                centerTopic = diagramData.dimension;
            } else {
                centerTopic = diagramData.center;
            }
            
            logger.info('ToolbarManager', 'ThinkGuide starting with data:', {
                diagramType,
                center: centerTopic,
                childCount: diagramData.children?.length || 0
            });
            
            // Start Thinking Mode (this will call openPanel internally)
            logger.info('ToolbarManager', 'Calling thinkingModeManager.startThinkingMode()');
            await window.thinkingModeManager.startThinkingMode(diagramType, diagramData);
            
            logger.info('ToolbarManager', 'ThinkGuide Mode started successfully');
            
        } catch (error) {
            logger.error('ToolbarManager', 'Failed to start ThinkGuide Mode', {
                error: error,
                message: error.message,
                stack: error.stack
            });
            this.showNotification(
                `Failed to start ThinkGuide Mode: ${error.message}`,
                'error'
            );
        }
    }
    
    /**
     * Cleanup and remove all event listeners by cloning and replacing elements
     */
    destroy() {
        logger.debug('ToolbarManager', 'Destroying instance', {
            session: this.sessionId?.substr(-8)
        });
        
        // CRITICAL: Cancel all in-progress LLM requests before destroying
        this.cancelAllLLMRequests();
        
        // Clone and replace buttons to remove all event listeners
        // This is the most reliable way to remove event listeners added with arrow functions
        const buttonsToClean = [
            'add-node-btn', 'delete-node-btn', 'duplicate-node-btn', 'empty-node-btn', 'auto-complete-btn',
            'line-mode-btn', 'learning-btn', 'thinking-btn', 'undo-btn', 'redo-btn', 'reset-btn', 
            'export-btn', 'export-image-btn', 'zoom-in-btn', 'zoom-out-btn', 'fit-diagram-btn', 'mindmate-ai-btn',
            // Note: 'back-to-gallery' is NOT included - it's managed by DiagramSelector
            // and its event listener must persist across diagram switches
            'close-properties', 'prop-text-apply', 'prop-bold',
            'prop-italic', 'prop-underline', 'reset-styles-btn'
        ];
        
        let cleanedCount = 0;
        buttonsToClean.forEach(btnId => {
            const btn = document.getElementById(btnId);
            if (btn && btn.parentNode) {
                const clone = btn.cloneNode(true);
                btn.parentNode.replaceChild(clone, btn);
                cleanedCount++;
            }
        });
        
        // Also clean up LLM selector buttons
        const llmButtons = document.querySelectorAll('.llm-btn');
        llmButtons.forEach(btn => {
            if (btn.parentNode) {
                const clone = btn.cloneNode(true);
                btn.parentNode.replaceChild(clone, btn);
                cleanedCount++;
            }
        });
        
        logger.debug('ToolbarManager', `Event listeners cleaned from ${cleanedCount} buttons`);
        
        // Disconnect node counter observer
        if (this.nodeCountObserver) {
            this.nodeCountObserver.disconnect();
            this.nodeCountObserver = null;
        }
        
        // Clear node count update timeout
        if (this.nodeCountUpdateTimeout) {
            clearTimeout(this.nodeCountUpdateTimeout);
            this.nodeCountUpdateTimeout = null;
        }
        
        // Unregister from global registry
        if (window.toolbarManagerRegistry) {
            window.toolbarManagerRegistry.delete(this.sessionId);
        }
        
        // Clear all references
        this.editor = null;
        this.currentSelection = [];
        this.sessionId = null;
        this.diagramType = null;
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.ToolbarManager = ToolbarManager;
}

