/**
 * ToolbarManager - Manages toolbar actions and property panel
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
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'ToolbarManager';
        
        // Session management - store session ID for lifecycle management
        this.sessionId = editor.sessionId;
        this.diagramType = editor.diagramType;
        
        // NOTE: activeAbortControllers removed - now managed by LLMEngineManager
        // Cancellation is handled via Event Bus to LLMAutoCompleteManager
        
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
     * Delegates to LLMAutoCompleteManager via Event Bus
     */
    cancelAllLLMRequests() {
        logger.info('ToolbarManager', 'Requesting cancellation of all LLM requests');
        // Delegate to LLMAutoCompleteManager which manages actual abort controllers
        window.eventBus.emit('autocomplete:cancel_requested', {});
    }
    
    // NOTE: logToBackend() removed - use logger.debug/info/warn/error directly
    
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
        
        // LLM selector buttons (convert NodeList to Array for .find() support)
        this.llmButtons = Array.from(document.querySelectorAll('.llm-btn'));
        this.deleteNodeBtn = document.getElementById('delete-node-btn');
        this.autoCompleteBtn = document.getElementById('auto-complete-btn');
        this.lineModeBtn = document.getElementById('line-mode-btn');
        this.learningBtn = document.getElementById('learning-btn');  // 🆕 Learning Mode button
        this.thinkingBtn = document.getElementById('thinking-btn');  // 🆕 ThinkGuide button
        this.duplicateNodeBtn = document.getElementById('duplicate-node-btn');
        this.emptyNodeBtn = document.getElementById('empty-node-btn');
        this.flowMapOrientationBtn = document.getElementById('flow-map-orientation-btn');
        this.undoBtn = document.getElementById('undo-btn');
        this.redoBtn = document.getElementById('redo-btn');
        this.exportBtn = document.getElementById('export-btn');
        this.saveBtn = document.getElementById('save-btn');
        this.importBtn = document.getElementById('import-btn');
        this.importFileInput = document.getElementById('import-file-input');
        
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
        
        // Color properties - hidden inputs for actual values
        this.propTextColor = document.getElementById('prop-text-color');
        this.propFillColor = document.getElementById('prop-fill-color');
        this.propStrokeColor = document.getElementById('prop-stroke-color');
        
        // Color buttons and shared palette
        this.btnTextColor = document.getElementById('btn-text-color');
        this.btnFillColor = document.getElementById('btn-fill-color');
        this.btnStrokeColor = document.getElementById('btn-stroke-color');
        this.previewTextColor = document.getElementById('preview-text-color');
        this.previewFillColor = document.getElementById('preview-fill-color');
        this.previewStrokeColor = document.getElementById('preview-stroke-color');
        this.colorPaletteDropdown = document.getElementById('color-palette-dropdown');
        this.sharedColorPalette = document.getElementById('shared-color-palette');
        this.propColorHex = document.getElementById('prop-color-hex');
        this.activeColorType = null; // 'text', 'fill', or 'stroke'
        
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
        this.flowMapOrientationBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            // CRITICAL: Only allow flip for flow_map diagram type
            // Delegate to ViewManager via Event Bus
            if (this.editor && this.editor.diagramType === 'flow_map' && window.eventBus) {
                window.eventBus.emit('view:flip_orientation_requested');
            }
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
        this.exportBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleExport();
        });
        this.saveBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleSave();
        });
        this.importBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.handleImport();
        });
        this.importFileInput?.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                this.handleFileSelected(file);
            }
            // Reset input so same file can be selected again
            this.importFileInput.value = '';
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
        // Text input: Apply on Enter key (but allow Ctrl+Enter for line breaks)
        this.propText?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
                // Regular Enter: apply text
                e.stopPropagation();
                e.preventDefault();
                this.applyText();
            } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                // Ctrl+Enter: insert line break
                e.stopPropagation();
                e.preventDefault();
                const textarea = this.propText;
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                const value = textarea.value;
                
                // Insert newline at cursor position
                textarea.value = value.substring(0, start) + '\n' + value.substring(end);
                
                // Restore cursor position after the newline
                textarea.selectionStart = textarea.selectionEnd = start + 1;
                
                // Auto-resize after inserting newline
                this.autoResizeTextarea(textarea);
            }
        });
        
        // Auto-resize textarea on input
        this.propText?.addEventListener('input', (e) => {
            this.autoResizeTextarea(e.target);
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
        
        // Initialize shared color palette
        this.initColorPalette();
        
        // Color button click handlers
        this.btnTextColor?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleColorPalette('text');
        });
        this.btnFillColor?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleColorPalette('fill');
        });
        this.btnStrokeColor?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleColorPalette('stroke');
        });
        
        // Hex input for custom colors
        this.propColorHex?.addEventListener('input', (e) => {
            if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                this.applyColorFromHex(e.target.value);
            }
        });
        
        // Close palette when clicking outside
        document.addEventListener('click', (e) => {
            if (this.colorPaletteDropdown && 
                !this.colorPaletteDropdown.contains(e.target) &&
                !this.btnTextColor?.contains(e.target) &&
                !this.btnFillColor?.contains(e.target) &&
                !this.btnStrokeColor?.contains(e.target)) {
                this.closeColorPalette();
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
        
        // Listen to history state changes to update undo/redo button states
        if (window.eventBus) {
            window.eventBus.onWithOwner('history:state_changed', (data) => {
                this.updateUndoRedoButtonStates(data.canUndo, data.canRedo);
            }, this.ownerId);
        }
    }
    
    /**
     * Update undo/redo button enabled/disabled states
     * @param {boolean} canUndo - Whether undo is possible
     * @param {boolean} canRedo - Whether redo is possible
     */
    updateUndoRedoButtonStates(canUndo, canRedo) {
        if (this.undoBtn) {
            this.undoBtn.disabled = !canUndo;
            this.undoBtn.style.opacity = canUndo ? '1' : '0.5';
        }
        if (this.redoBtn) {
            this.redoBtn.disabled = !canRedo;
            this.redoBtn.style.opacity = canRedo ? '1' : '0.5';
        }
    }
    
    /**
     * Handle LLM model selection button click
     * EVENT BUS WRAPPER - Delegates to UIStateLLMManager
     */
    handleLLMSelection(button) {
        window.eventBus.emit('llm:model_selection_clicked', { button });
        logger.debug('ToolbarManager', 'LLM selection requested via Event Bus');
    }
    
    /**
     * Render cached LLM result
     * EVENT BUS WRAPPER - Delegates to LLMAutoCompleteManager
     */
    renderCachedLLMResult(llmModel) {
        window.eventBus.emit('autocomplete:render_cached_requested', { llmModel });
        logger.debug('ToolbarManager', `Render cached result requested for ${llmModel} via Event Bus`);
    }
    
    /**
     * Update LLM button active states
     * EVENT BUS WRAPPER - Delegates to LLMAutoCompleteManager
     */
    updateLLMButtonStates() {
        window.eventBus.emit('autocomplete:update_button_states_requested', {});
        logger.debug('ToolbarManager', 'Button states update requested via Event Bus');
    }
    
    /**
     * Listen to selection changes from editor
     * ARCHITECTURE: Uses Event Bus instead of CustomEvent
     */
    listenToSelectionChanges() {
        // Listen to Event Bus for selection changes (from InteractionHandler)
        if (window.eventBus) {
            window.eventBus.onWithOwner('interaction:selection_changed', (data) => {
                this.currentSelection = data.selectedNodes || [];
                const hasSelection = this.currentSelection.length > 0;
                
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
            
            const currentPanel = window.panelManager?.getCurrentPanel();
            
            // Show/hide property panel based on selection
            // NOTE: Previously blocked property panel when MindMate/ThinkGuide were open
            // This caused confusion as users couldn't edit nodes while chatting.
            // Now property panel always opens when a node is selected, which will
            // close MindMate/ThinkGuide automatically (panel manager single-panel rule).
            if (hasSelection && this.currentSelection.length > 0) {
                this.showPropertyPanel();
                this.loadNodeProperties(this.currentSelection[0]);
            } else {
                // Hide property panel when no selection (only if it's currently open)
                if (currentPanel === 'property') {
                    this.hidePropertyPanel();
                    this.clearPropertyPanel();
                }
            }
        }, this.ownerId);
    }
        
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
        if (this.addNodeBtn) {
            // ARCHITECTURE: Use State Manager as source of truth for diagram type
            const diagramState = window.stateManager.getDiagramState();
            const diagramType = diagramState?.type;
            
            if (!diagramType) {
                logger.error('ToolbarManager', 'Cannot determine diagram type from State Manager');
                return;
            }
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
            // CanvasController will handle view adjustments without resetting zoom/pan
            if (window.panelManager) {
                window.panelManager.openPanel('property');
            } else {
                // Fallback
                this.propertyPanel.style.display = 'block';
            }
            
            // Removed view reset logic - CanvasController.handlePanelChange now preserves
            // the current viewBox when panels open/close, maintaining user's zoom/pan level
        } else {
            logger.warn('ToolbarManager', 'Property panel element not found');
        }
    }
    
    /**
     * Hide property panel
     */
    hidePropertyPanel() {
        if (this.propertyPanel) {
            // Check if panel is already closed - skip if already hidden
            const isAlreadyHidden = this.propertyPanel.style.display === 'none' || 
                                   (window.panelManager && !window.panelManager.isPanelOpen('property'));
            
            if (isAlreadyHidden) {
                logger.debug('ToolbarManager', 'Property panel already hidden - skipping close');
                return;
            }
            
            // Use centralized panel manager
            if (window.panelManager) {
                window.panelManager.closePanel('property');
            } else {
                // Fallback
                this.propertyPanel.style.display = 'none';
            }
            
            // CanvasController.handlePanelChange will handle view adjustments
            // ViewManager.fitToFullCanvas will check state and skip if already fitted
            // No need to explicitly request fit here - let the panel close event handle it
        }
    }
    
    /**
     * Clear property panel inputs to default values
     * Called when switching diagrams or clearing selection
     */
    clearPropertyPanel() {
        // Clear text input
        if (this.propText) {
            this.propText.value = '';
            // Reset textarea height to minimum
            if (this.propText.tagName === 'TEXTAREA') {
                this.autoResizeTextarea(this.propText);
            }
        }
        
        // Reset font properties to defaults
        if (this.propFontSize) this.propFontSize.value = 14;
        if (this.propFontFamily) this.propFontFamily.value = "'Microsoft YaHei', sans-serif";
        
        // Reset colors to defaults
        if (this.propTextColor) this.propTextColor.value = '#000000';
        if (this.propFillColor) this.propFillColor.value = '#2196f3';
        if (this.propStrokeColor) this.propStrokeColor.value = '#1976d2';
        
        // Reset stroke width and opacity to defaults
        if (this.propStrokeWidth) this.propStrokeWidth.value = 2;
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = '2px';
        if (this.propOpacity) this.propOpacity.value = 1;
        if (this.opacityValue) this.opacityValue.textContent = '100%';
        
        // Reset toggle buttons
        if (this.propBold) this.propBold.classList.remove('active');
        if (this.propItalic) this.propItalic.classList.remove('active');
        if (this.propUnderline) this.propUnderline.classList.remove('active');
        
        // Update color button previews
        this.updateColorPreviews();
        
        // Close color palette if open
        this.closeColorPalette();
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
        // Use explicit null check to preserve opacity 0 (fully transparent)
        const opacityAttr = nodeElement.attr('opacity');
        const opacity = (opacityAttr !== null && opacityAttr !== undefined) ? opacityAttr : '1';
        
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
            // Method 1: Try finding text elements by data-node-id (for multi-line text)
            let textElements = d3.selectAll(`text[data-node-id="${nodeId}"]`);
            if (!textElements.empty()) {
                textElement = d3.select(textElements.node()); // Get first for attributes
                // Use extractTextFromSVG to handle multi-line text
                text = (typeof window.extractTextFromSVG === 'function') 
                    ? window.extractTextFromSVG(textElement) 
                    : (textElement.text() || '');
            } else {
                // Method 2: Try as child
                textElement = nodeElement.select('text');
                if (!textElement.empty()) {
                    text = (typeof window.extractTextFromSVG === 'function') 
                        ? window.extractTextFromSVG(textElement) 
                        : (textElement.text() || '');
                } else {
                    // Method 3: Try data-text-for attribute
                    textElement = d3.select(`[data-text-for="${nodeId}"]`);
                    if (!textElement.empty()) {
                        text = (typeof window.extractTextFromSVG === 'function') 
                            ? window.extractTextFromSVG(textElement) 
                            : (textElement.text() || '');
                    } else {
                        // Method 4: Try next sibling
                        const shapeNode = nodeElement.node();
                        if (shapeNode && shapeNode.nextElementSibling && shapeNode.nextElementSibling.tagName === 'text') {
                            textElement = d3.select(shapeNode.nextElementSibling);
                            text = (typeof window.extractTextFromSVG === 'function') 
                                ? window.extractTextFromSVG(textElement) 
                                : (textElement.text() || '');
                        }
                    }
                }
            }
        }
        
        // Get text attributes (with fallbacks if text element not found)
        const fontSize = textElement && !textElement.empty() ? (textElement.attr('font-size') || '14') : '14';
        const fontFamily = textElement && !textElement.empty() ? (textElement.attr('font-family') || "'Microsoft YaHei', sans-serif") : "'Microsoft YaHei', sans-serif";
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
            // Auto-resize textarea after setting value
            if (this.propText.tagName === 'TEXTAREA') {
                this.autoResizeTextarea(this.propText);
            }
        }
        if (this.propFontSize) this.propFontSize.value = parseInt(fontSize);
        if (this.propFontFamily) this.propFontFamily.value = fontFamily;
        if (this.propTextColor) this.propTextColor.value = expandedTextColor;
        if (this.propFillColor) this.propFillColor.value = expandedFill;
        if (this.propStrokeColor) this.propStrokeColor.value = expandedStroke;
        if (this.propStrokeWidth) this.propStrokeWidth.value = parseFloat(strokeWidth);
        if (this.strokeWidthValue) this.strokeWidthValue.textContent = `${strokeWidth}px`;
        if (this.propOpacity) this.propOpacity.value = parseFloat(opacity);
        if (this.opacityValue) this.opacityValue.textContent = `${Math.round(parseFloat(opacity) * 100)}%`;
        
        // Update color button previews
        this.updateColorPreviews();
        
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
     * Auto-resize textarea based on content
     * @param {HTMLTextAreaElement} textarea - Textarea element to resize
     */
    autoResizeTextarea(textarea) {
        if (!textarea) return;
        
        // Debounce: skip if already resizing
        if (textarea._isResizing) return;
        textarea._isResizing = true;
        
        const minHeight = 60; // Minimum height in pixels
        const maxHeight = 300; // Maximum height in pixels
        
        // Save current scroll position to prevent jump
        const scrollTop = textarea.scrollTop;
        
        // Temporarily set height to 0 to get accurate scrollHeight
        textarea.style.height = '0px';
        
        // Get the actual content height needed
        const contentHeight = textarea.scrollHeight;
        
        // Calculate new height with constraints
        const newHeight = Math.min(Math.max(contentHeight, minHeight), maxHeight);
        
        // Set the new height
        textarea.style.height = `${newHeight}px`;
        textarea.style.overflowY = contentHeight > maxHeight ? 'auto' : 'hidden';
        
        // Restore scroll position
        textarea.scrollTop = scrollTop;
        
        // Clear the resizing flag after a short delay
        requestAnimationFrame(() => {
            textarea._isResizing = false;
        });
    }
    
    /**
     * Initialize shared color palette
     * Creates 32 predefined color swatches in the dropdown
     */
    initColorPalette() {
        // 32 carefully selected colors (4 rows x 8 columns)
        this.paletteColors = [
            // Row 1: Grayscale + Pure colors
            '#000000', '#333333', '#666666', '#999999', '#CCCCCC', '#FFFFFF', '#FF0000', '#00FF00',
            // Row 2: Blues and Purples
            '#0000FF', '#1976D2', '#2196F3', '#03A9F4', '#00BCD4', '#009688', '#4CAF50', '#8BC34A',
            // Row 3: Warm colors
            '#CDDC39', '#FFEB3B', '#FFC107', '#FF9800', '#FF5722', '#F44336', '#E91E63', '#9C27B0',
            // Row 4: Pastels and earth tones
            '#673AB7', '#3F51B5', '#795548', '#607D8B', '#FFCDD2', '#C8E6C9', '#BBDEFB', '#FFE0B2'
        ];
        
        if (!this.sharedColorPalette) return;
        
        this.sharedColorPalette.innerHTML = '';
        
        this.paletteColors.forEach(color => {
            const swatch = document.createElement('div');
            swatch.className = 'color-swatch';
            swatch.style.backgroundColor = color;
            swatch.dataset.color = color;
            
            // Add light-color class for light colors
            const rgb = this.hexToRgb(color);
            if (rgb && (rgb.r + rgb.g + rgb.b) > 600) {
                swatch.classList.add('light-color');
            }
            
            swatch.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectColor(color);
            });
            
            this.sharedColorPalette.appendChild(swatch);
        });
        
        // Initialize button previews
        this.updateColorPreviews();
    }
    
    /**
     * Toggle color palette dropdown for a specific color type
     */
    toggleColorPalette(colorType) {
        if (this.activeColorType === colorType && this.colorPaletteDropdown?.classList.contains('open')) {
            this.closeColorPalette();
        } else {
            this.openColorPalette(colorType);
        }
    }
    
    /**
     * Open color palette for a specific color type
     */
    openColorPalette(colorType) {
        this.activeColorType = colorType;
        
        // Update button active states
        this.btnTextColor?.classList.toggle('active', colorType === 'text');
        this.btnFillColor?.classList.toggle('active', colorType === 'fill');
        this.btnStrokeColor?.classList.toggle('active', colorType === 'stroke');
        
        // Get current color for this type
        let currentColor = '#000000';
        if (colorType === 'text' && this.propTextColor) {
            currentColor = this.propTextColor.value;
        } else if (colorType === 'fill' && this.propFillColor) {
            currentColor = this.propFillColor.value;
        } else if (colorType === 'stroke' && this.propStrokeColor) {
            currentColor = this.propStrokeColor.value;
        }
        
        // Update hex input
        if (this.propColorHex) {
            this.propColorHex.value = currentColor.toUpperCase();
        }
        
        // Update palette selection
        this.updatePaletteSelection(currentColor);
        
        // Show dropdown
        this.colorPaletteDropdown?.classList.add('open');
    }
    
    /**
     * Close color palette dropdown
     */
    closeColorPalette() {
        this.activeColorType = null;
        this.colorPaletteDropdown?.classList.remove('open');
        this.btnTextColor?.classList.remove('active');
        this.btnFillColor?.classList.remove('active');
        this.btnStrokeColor?.classList.remove('active');
    }
    
    /**
     * Select a color from the palette
     */
    selectColor(color) {
        if (!this.activeColorType) return;
        
        const upperColor = color.toUpperCase();
        
        // Update the appropriate hidden input
        if (this.activeColorType === 'text' && this.propTextColor) {
            this.propTextColor.value = color;
        } else if (this.activeColorType === 'fill' && this.propFillColor) {
            this.propFillColor.value = color;
        } else if (this.activeColorType === 'stroke' && this.propStrokeColor) {
            this.propStrokeColor.value = color;
        }
        
        // Update hex input
        if (this.propColorHex) {
            this.propColorHex.value = upperColor;
        }
        
        // Update palette selection visual
        this.updatePaletteSelection(color);
        
        // Update button previews
        this.updateColorPreviews();
        
        // Apply styles in real-time
        this.applyStylesRealtime();
        
        // Close palette after selection
        this.closeColorPalette();
    }
    
    /**
     * Apply color from hex input
     */
    applyColorFromHex(color) {
        if (!this.activeColorType) return;
        
        // Update the appropriate hidden input
        if (this.activeColorType === 'text' && this.propTextColor) {
            this.propTextColor.value = color;
        } else if (this.activeColorType === 'fill' && this.propFillColor) {
            this.propFillColor.value = color;
        } else if (this.activeColorType === 'stroke' && this.propStrokeColor) {
            this.propStrokeColor.value = color;
        }
        
        // Update palette selection visual
        this.updatePaletteSelection(color);
        
        // Update button previews
        this.updateColorPreviews();
        
        // Apply styles in real-time
        this.applyStylesRealtime();
    }
    
    /**
     * Update the selected state of the shared color palette
     */
    updatePaletteSelection(selectedColor) {
        if (!this.sharedColorPalette) return;
        
        const normalizedColor = selectedColor.toUpperCase();
        
        this.sharedColorPalette.querySelectorAll('.color-swatch').forEach(swatch => {
            if (swatch.dataset.color.toUpperCase() === normalizedColor) {
                swatch.classList.add('selected');
            } else {
                swatch.classList.remove('selected');
            }
        });
    }
    
    /**
     * Update color preview bars on buttons
     */
    updateColorPreviews() {
        if (this.previewTextColor && this.propTextColor) {
            this.previewTextColor.style.backgroundColor = this.propTextColor.value;
        }
        if (this.previewFillColor && this.propFillColor) {
            this.previewFillColor.style.backgroundColor = this.propFillColor.value;
        }
        if (this.previewStrokeColor && this.propStrokeColor) {
            this.previewStrokeColor.style.backgroundColor = this.propStrokeColor.value;
        }
    }
    
    /**
     * Convert hex color to RGB object
     */
    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }
    
    /**
     * Apply text to selected nodes - EVENT BUS WRAPPER
     */
    applyText(silent = false) {
        // ARCHITECTURE: Event Bus pattern - emit event, let handler validate state
        // The handler (TextToolbarStateManager) will check State Manager for selection
        window.eventBus.emit('text:apply_requested', { silent });
        logger.debug('ToolbarManager', 'Apply text requested via Event Bus');
    }
    
    /**
     * Apply all properties to selected nodes - EVENT BUS WRAPPER
     */
    applyAllProperties() {
        window.eventBus.emit('properties:apply_all_requested', {});
        logger.debug('ToolbarManager', 'Apply all properties requested via Event Bus');
    }
    
    /**
     * Apply styles in real-time (without notification) - EVENT BUS WRAPPER
     */
    applyStylesRealtime() {
        window.eventBus.emit('properties:apply_realtime_requested', {});
        logger.debug('ToolbarManager', 'Apply realtime styles requested via Event Bus');
    }
    
    /**
     * Reset styles to template defaults (keep text unchanged) - EVENT BUS WRAPPER
     */
    resetStyles() {
        window.eventBus.emit('properties:reset_requested', {});
        logger.debug('ToolbarManager', 'Reset styles requested via Event Bus');
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
    /**
     * Toggle bold - EVENT BUS WRAPPER
     */
    toggleBold() {
        window.eventBus.emit('properties:toggle_bold_requested', {});
    }
    
    /**
     * Toggle italic - EVENT BUS WRAPPER
     */
    toggleItalic() {
        window.eventBus.emit('properties:toggle_italic_requested', {});
    }
    
    /**
     * Toggle underline - EVENT BUS WRAPPER
     */
    toggleUnderline() {
        window.eventBus.emit('properties:toggle_underline_requested', {});
    }
    
    /**
     * Handle add node - EVENT BUS WRAPPER
     */
    handleAddNode() {
        window.eventBus.emit('node:add_requested', {});
        logger.debug('ToolbarManager', 'Add node requested via Event Bus');
    }
    
    /**
     * Handle delete node - EVENT BUS WRAPPER
     */
    handleDeleteNode() {
        window.eventBus.emit('node:delete_requested', {});
        logger.debug('ToolbarManager', 'Delete node requested via Event Bus');
    }
    
    /**
     * Handle empty node text (clear text but keep node) - EVENT BUS WRAPPER
     */
    handleEmptyNode() {
        window.eventBus.emit('node:empty_requested', {});
        logger.debug('ToolbarManager', 'Empty node requested via Event Bus');
    }
    
    /**
     * Handle auto-complete diagram with AI
     * EVENT BUS WRAPPER - Delegates to LLMAutoCompleteManager
     */
    async handleAutoComplete() {
        window.eventBus.emit('autocomplete:start_requested', {});
        logger.debug('ToolbarManager', 'Auto-complete requested via Event Bus');
    }
    
    // NOTE: LLM validation methods moved to PropertyValidator (property-validator.js)
    
    // NOTE: Button state methods moved to:
    // - LLMProgressRenderer.setAllLLMButtonsLoading() (llm-progress-renderer.js)
    // - LLMProgressRenderer.setLLMButtonState() (llm-progress-renderer.js)
    // - UIStateLLMManager also has its own implementation (ui-state-llm-manager.js)
    
    /**
     * Toggle line mode (black and white, no fill) - EVENT BUS WRAPPER
     */
    toggleLineMode() {
        window.eventBus.emit('ui:toggle_line_mode', {});
        logger.debug('ToolbarManager', 'Toggle line mode requested via Event Bus');
    }
    
    /**
     * Set loading state for auto button - EVENT BUS WRAPPER
     */
    setAutoButtonLoading(isLoading) {
        window.eventBus.emit('ui:set_auto_button_loading', { isLoading });
        logger.debug('ToolbarManager', 'Set auto button loading state via Event Bus', { isLoading });
    }
    
    /**
     * Handle duplicate node - EVENT BUS WRAPPER
     */
    handleDuplicateNode() {
        window.eventBus.emit('node:duplicate_requested', {});
        logger.debug('ToolbarManager', 'Duplicate node requested via Event Bus');
    }
    
    /**
     * Handle undo - EVENT BUS WRAPPER
     */
    handleUndo() {
        window.eventBus.emit('history:undo_requested', {});
        logger.debug('ToolbarManager', 'Undo requested via Event Bus');
    }
    
    /**
     * Handle redo - EVENT BUS WRAPPER
     */
    handleRedo() {
        window.eventBus.emit('history:redo_requested', {});
        logger.debug('ToolbarManager', 'Redo requested via Event Bus');
    }
    
    /**
     * Reset canvas to blank template - EVENT BUS WRAPPER
     */
    handleReset() {
        window.eventBus.emit('diagram:reset_requested', {});
        logger.debug('ToolbarManager', 'Reset diagram requested via Event Bus');
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
        // ARCHITECTURE NOTE: Direct call to fitDiagramForExport() is acceptable - this is an export-specific
        // operation that requires immediate synchronous execution. Event Bus is not suitable here.
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
            // STEP 1: Calculate accurate content bounds from ORIGINAL SVG (before cloning)
            // Using original SVG ensures getBBox works correctly (element is in DOM)
            let contentMinX = Infinity, contentMinY = Infinity;
            let contentMaxX = -Infinity, contentMaxY = -Infinity;
            let hasContent = false;
            
            const allElements = d3.select(svg).selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            allElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox.width > 0 && bbox.height > 0) {
                        contentMinX = Math.min(contentMinX, bbox.x);
                        contentMinY = Math.min(contentMinY, bbox.y);
                        contentMaxX = Math.max(contentMaxX, bbox.x + bbox.width);
                        contentMaxY = Math.max(contentMaxY, bbox.y + bbox.height);
                        hasContent = true;
                    }
                } catch (e) {
                    // Skip elements without getBBox
                }
            });
            
            if (!hasContent) {
                logger.warn('ToolbarManager', 'No content found for PNG export');
                this.showNotification(this.getNotif('noDiagramToExport'), 'error');
                return;
            }
            
            // STEP 2: Clone SVG for export (preserve original)
            const svgClone = svg.cloneNode(true);
            
            // Remove UI-only elements that should not appear in exports
            const svgD3Clone = d3.select(svgClone);
            svgD3Clone.selectAll('.learning-sheet-answer-key').remove();
            svgD3Clone.selectAll('.selected').classed('selected', false).style('filter', null);
            svgD3Clone.selectAll('.background, .background-rect').each(function() {
                const element = d3.select(this);
                const stroke = element.attr('stroke');
                if (stroke && stroke !== 'none' && stroke !== 'transparent') {
                    element.attr('stroke', 'none');
                }
                const styleStroke = element.style('stroke');
                if (styleStroke && styleStroke !== 'none' && styleStroke !== 'transparent') {
                    element.style('stroke', 'none');
                }
            });
            
            // STEP 3: Calculate optimal viewBox with proper padding
            const padding = 30; // Fixed padding for consistent exports
            const exportViewBoxX = contentMinX - padding;
            const exportViewBoxY = contentMinY - padding;
            const exportWidth = (contentMaxX - contentMinX) + (padding * 2);
            const exportHeight = (contentMaxY - contentMinY) + (padding * 2);
            
            logger.debug('ToolbarManager', 'Export dimensions calculated', {
                contentBounds: { contentMinX, contentMinY, contentMaxX, contentMaxY },
                exportViewBox: { x: exportViewBoxX, y: exportViewBoxY, width: exportWidth, height: exportHeight }
            });
            
            // STEP 4: Normalize viewBox to start at (0, 0) for canvas compatibility
            const normalizedWidth = exportWidth;
            const normalizedHeight = exportHeight;
            
            // Wrap all content in a group with translation to normalize coordinates
            const content = Array.from(svgClone.childNodes);
            const contentGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            contentGroup.setAttribute('transform', `translate(${-exportViewBoxX}, ${-exportViewBoxY})`);
            
            // Move all element nodes to the group
            content.forEach(child => {
                if (child.nodeType === 1) { // Element node
                    contentGroup.appendChild(child);
                }
            });
            
            // Clear SVG and rebuild with proper structure
            svgClone.innerHTML = '';
            
            // Add background rect FIRST (underneath everything)
            const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            bgRect.setAttribute('x', '0');
            bgRect.setAttribute('y', '0');
            bgRect.setAttribute('width', normalizedWidth);
            bgRect.setAttribute('height', normalizedHeight);
            bgRect.setAttribute('fill', '#f5f5f5');
            bgRect.setAttribute('class', 'export-background');
            svgClone.appendChild(bgRect);
            
            // Add content group
            svgClone.appendChild(contentGroup);
            
            // Update viewBox and dimensions
            svgClone.setAttribute('viewBox', `0 0 ${normalizedWidth} ${normalizedHeight}`);
            svgClone.setAttribute('width', normalizedWidth);
            svgClone.setAttribute('height', normalizedHeight);
            
            // STEP 5: Add watermark (positioned in normalized coordinates)
            const svgD3 = d3.select(svgClone);
            const watermarkFontSize = Math.max(12, Math.min(20, Math.min(normalizedWidth, normalizedHeight) * 0.025));
            const wmPadding = Math.max(10, Math.min(20, Math.min(normalizedWidth, normalizedHeight) * 0.02));
            const watermarkX = normalizedWidth - wmPadding;
            const watermarkY = normalizedHeight - wmPadding;
            
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
            
            // STEP 6: Create high-quality canvas (3x scale for Retina displays)
            const scale = 3;
            const canvas = document.createElement('canvas');
            canvas.width = normalizedWidth * scale;
            canvas.height = normalizedHeight * scale;
            const ctx = canvas.getContext('2d');
            
            ctx.scale(scale, scale);
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            
            // Fill white background (fallback in case SVG background fails)
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, normalizedWidth, normalizedHeight);
            
            // STEP 7: Convert SVG to PNG
            const svgData = new XMLSerializer().serializeToString(svgClone);
            const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(svgBlob);
            
            const img = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0, normalizedWidth, normalizedHeight);
                
                canvas.toBlob((blob) => {
                    const pngUrl = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = pngUrl;
                    
                    // Generate filename with diagram type and LLM model
                    const diagramType = window.stateManager?.getDiagramState()?.type || this.editor?.diagramType || 'diagram';
                    const llmModel = this.selectedLLM || 'qwen';
                    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                    link.download = `${diagramType}_${llmModel}_${timestamp}.png`;
                    
                    link.click();
                    
                    URL.revokeObjectURL(pngUrl);
                    URL.revokeObjectURL(url);
                    
                    logger.info('ToolbarManager', 'PNG export successful', {
                        dimensions: { width: normalizedWidth, height: normalizedHeight }
                    });
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
     * Handle save to .mg format
     */
    handleSave() {
        if (!this.editor || !this.editor.currentSpec) {
            this.showNotification(this.getNotif('noDiagramToSave'), 'error');
            return;
        }
        
        // Emit event for ExportManager to handle
        if (window.eventBus) {
            window.eventBus.emit('toolbar:export_requested', {
                format: 'mg',
                editor: this.editor
            });
            this.showNotification(this.getNotif('diagramSaved'), 'success');
        }
    }
    
    /**
     * Handle import button click
     */
    handleImport() {
        this.importFileInput?.click();
    }
    
    /**
     * Handle selected file for import
     * @param {File} file - Selected .mg file
     */
    async handleFileSelected(file) {
        logger.info('ToolbarManager', 'File selected for import', {
            name: file.name,
            size: file.size
        });
        
        // Warn if file is very large (> 1MB)
        if (file.size > 1024 * 1024) {
            logger.warn('ToolbarManager', 'Large file detected', { size: file.size });
        }
        
        try {
            // Read file contents
            const text = await file.text();
            
            let data;
            try {
                data = JSON.parse(text);
            } catch (parseError) {
                // JSON parse error - show specific message
                logger.error('ToolbarManager', 'JSON parse error', parseError);
                this.showNotification(this.getNotif('invalidFileFormat'), 'error');
                return;
            }
            
            // Validate and import via ExportManager
            if (window.eventBus) {
                window.eventBus.emit('toolbar:import_file', { data, filename: file.name });
            }
        } catch (error) {
            // File read error (rare)
            logger.error('ToolbarManager', 'Error reading import file', error);
            this.showNotification(this.getNotif('importFailed'), 'error');
        }
    }
    
    /**
     * Get translated notification message - EVENT BUS WRAPPER
     */
    getNotif(key, ...args) {
        if (window.languageManager && window.languageManager.getNotification) {
            return window.languageManager.getNotification(key, ...args);
        }
        return key;
    }
    
    /**
     * Show notification - EVENT BUS WRAPPER
     */
    showNotification(message, type = 'info') {
        window.eventBus.emit('notification:show', { message, type });
        logger.debug('ToolbarManager', 'Show notification via Event Bus', { message, type });
    }
    
    /**
     * Play notification sound - EVENT BUS WRAPPER
     */
    playNotificationSound() {
        window.eventBus.emit('notification:play_sound', {});
        logger.debug('ToolbarManager', 'Play notification sound via Event Bus');
    }
    
    /**
     * Set up automatic node counter using MutationObserver - EVENT BUS WRAPPER
     */
    setupNodeCounterObserver() {
        window.eventBus.emit('node_counter:setup', {});
        logger.debug('ToolbarManager', 'Setup node counter observer via Event Bus');
    }
    
    /**
     * Update node count in status bar - EVENT BUS WRAPPER
     */
    updateNodeCount() {
        window.eventBus.emit('node_counter:update', {});
        logger.debug('ToolbarManager', 'Update node count via Event Bus');
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
     * Validate diagram for Learning Mode - EVENT BUS WRAPPER
     */
    validateLearningMode() {
        window.eventBus.emit('learning_mode:validate', {});
        logger.debug('ToolbarManager', 'Validate learning mode via Event Bus');
    }
    
    /**
     * Handle Learning Mode button click - EVENT BUS WRAPPER
     */
    async handleLearningMode() {
        window.eventBus.emit('learning_mode:start_requested', {});
        logger.debug('ToolbarManager', 'Learning mode start requested via Event Bus');
    }
    
    /**
     * Handle Thinking Mode (ThinkGuide) button click - EVENT BUS WRAPPER
     */
    async handleThinkingMode() {
        window.eventBus.emit('thinking_mode:toggle_requested', {});
        logger.debug('ToolbarManager', 'Thinking mode toggle requested via Event Bus');
    }
    
    /**
     * Cleanup and remove all event listeners by cloning and replacing elements
     */
    destroy() {
        logger.debug('ToolbarManager', 'Destroying instance', {
            session: this.sessionId?.substr(-8)
        });
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (window.eventBus && this.ownerId) {
            const removedCount = window.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                logger.debug('ToolbarManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
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
        this.propertyPanel = null;
        this.currentSelection = [];
        this.sessionId = null;
        this.diagramType = null;
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.ToolbarManager = ToolbarManager;
}

